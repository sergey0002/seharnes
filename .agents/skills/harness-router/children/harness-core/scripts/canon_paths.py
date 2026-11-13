"""Read the deliberately restricted, portable YAML subset used by harness policies.

Supported: mappings, lists, double-quoted JSON-compatible strings, booleans and
integers; exactly two spaces per indentation level. No aliases, tags, nulls,
flow collections, multiline scalars or implicit strings. This reader does not
authenticate policy content or determine which paths are safe to overwrite.
"""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from types import MappingProxyType

_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*\Z")
_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")


def _without_comment(line: str) -> str:
    quoted = False
    escaped = False
    for index, char in enumerate(line):
        if quoted and escaped:
            escaped = False
        elif quoted and char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif char == "#" and not quoted:
            return line[:index].rstrip()
    if quoted:
        raise ValueError("unterminated quoted string")
    return line.rstrip()


def _scalar(value: str):
    if value.startswith('"'):
        try:
            result = json.loads(value)
        except (ValueError, TypeError) as error:
            raise ValueError("invalid quoted string") from error
        if not isinstance(result, str) or any(ord(char) < 32 for char in result):
            raise ValueError("invalid string value")
        return result
    if value in ("true", "false"):
        return value == "true"
    if _INTEGER.fullmatch(value):
        return int(value)
    raise ValueError("unsupported scalar")


def parse_policy(text: str) -> dict:
    if not isinstance(text, str) or len(text) > 2 * 1024 * 1024:
        raise ValueError("invalid or oversized policy")
    rows = []
    for number, original in enumerate(text.splitlines(), 1):
        if "\t" in original:
            raise ValueError(f"tab indentation or content at line {number}")
        line = _without_comment(original)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 or indent > 32:
            raise ValueError(f"invalid indentation at line {number}")
        value = line[indent:]
        # Normalize a YAML block-list mapping item to the equivalent nested
        # mapping; quoted scalar items with colons are left unchanged.
        inline_map = re.match(r'^- ([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]|$)', value)
        if inline_map:
            if indent + 2 > 32:
                raise ValueError(f"invalid indentation at line {number}")
            rows.append((indent, "-", number))
            rows.append((indent + 2, value[2:], number))
        else:
            rows.append((indent, value, number))
    if not rows or rows[0][0] != 0:
        raise ValueError("policy must begin with a top-level mapping")

    def block(index: int, indent: int):
        is_list = rows[index][1].startswith("- ") or rows[index][1] == "-"
        result = [] if is_list else {}
        while index < len(rows):
            level, value, number = rows[index]
            if level < indent:
                break
            if level != indent:
                raise ValueError(f"unexpected indentation at line {number}")
            if is_list:
                if value == "-":
                    rest = ""
                elif value.startswith("- "):
                    rest = value[2:].strip()
                else:
                    raise ValueError(f"mixed collection at line {number}")
                key = None
            else:
                if ":" not in value:
                    raise ValueError(f"missing mapping separator at line {number}")
                key, rest = value.split(":", 1)
                if not _KEY.fullmatch(key) or (rest and not rest.startswith(" ")):
                    raise ValueError(f"invalid mapping key at line {number}")
                if key in result:
                    raise ValueError(f"duplicate mapping key at line {number}")
                rest = rest.strip()
            index += 1
            if rest:
                value = _scalar(rest)
            else:
                if index >= len(rows) or rows[index][0] != indent + 2:
                    raise ValueError(f"missing nested value at line {number}")
                value, index = block(index, indent + 2)
            if is_list:
                result.append(value)
            else:
                result[key] = value
        return result, index

    result, index = block(0, 0)
    if index != len(rows) or not isinstance(result, dict):
        raise ValueError("invalid top-level policy")
    return result


def read_policy(path: Path) -> dict:
    """Read one stable regular file, rejecting links and hardlink aliases.

    Ancestor containment and platform-specific races remain caller gates; this
    routine alone does not authorize applying or trusting a candidate policy.
    """
    limit = 2 * 1024 * 1024
    path = Path(path)
    before_open = path.lstat()
    def acceptable(info) -> bool:
        return (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                not (getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)))
    if not acceptable(before_open):
        raise ValueError("policy is not an unlinked regular file")
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not acceptable(before) or (before.st_dev, before.st_ino) != (before_open.st_dev, before_open.st_ino):
            raise ValueError("policy changed while opening")
        if before.st_size > limit:
            raise ValueError("policy exceeds size limit")
        chunks = []
        count = 0
        while True:
            data = os.read(fd, min(65536, limit - count + 1))
            if not data:
                break
            count += len(data)
            if count > limit:
                raise ValueError("policy exceeds size limit")
            chunks.append(data)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if tuple(getattr(before, key) for key in fields) != tuple(getattr(after, key) for key in fields):
            raise ValueError("policy changed while reading")
    finally:
        os.close(fd)
    return parse_policy(b''.join(chunks).decode('utf-8'))


class PolicyError(ValueError):
    """Structured error from the preliminary policy declarations loader."""
    def __init__(self, code: str, policy_id: str, relative_path: str, field: str | None):
        self.code, self.policy_id, self.relative_path, self.field = code, policy_id, relative_path, field
        super().__init__(f'{code}: {policy_id}: {relative_path}: {field or "-"}')


_PRELIMINARY_FILES = {
    'skill_format': '.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml',
    'component_docs': '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml',
}
_RULE_FIELDS = {
    'SF01': ('skill', {'required_files': list}),
    'SF02': ('skill', {'allowed_directories': list, 'forbidden_directories': list,
                       'name_pattern': str, 'allowed_frontmatter': list}),
    'SF03': ('skill', {'resource_keys': list}),
    'CD01': ('skill_readme', {'filename': str, 'forbid_links': bool, 'forbid_relations_section': bool,
                             'forbidden_literals': list}),
    'CD02': ('script_doc', {'layout_key': str, 'required_sections': list}),
    'CD03': ('active_mcp_doc', {'layout_key': str}),
    'CD04': ('component_doc', {'forbid_duplicate_owner': bool}),
}
_DISTRIBUTION_FIELDS = {'ref', 'role', 'profiles', 'copy_policy', 'owner', 'doc_policy', 'scan_policy'}
_DISTRIBUTION_ROLES = {'authored', 'generated', 'local', 'state', 'secret', 'project', 'policy', 'config'}
_DISTRIBUTION_COPY = {'copy', 'merge', 'generate', 'preserve', 'exclude'}
_DISTRIBUTION_DOCS = {'required', 'optional', 'not_applicable'}
_DISTRIBUTION_SCAN = {'owned', 'generated', 'local', 'state', 'secret', 'project'}
_DISTRIBUTION_PROFILES = {'core', 'developer', 'project'}


def _layout_paths(layout: dict, prefix: str = 'layout'):
    for key, value in layout.items():
        if isinstance(value, str):
            yield prefix + '.' + key
        elif isinstance(value, dict):
            yield from _layout_paths(value, prefix + '.' + key)


def _distribution_path(canon: dict, reference: str) -> str | None:
    group, _, key = reference.partition('.')
    if group == 'canonical_roots':
        value = canon.get('canonical_roots', {}).get(key)
    elif group == 'layout':
        value = canon.get('layout', {})
        for part in key.split('.'):
            value = value.get(part) if isinstance(value, dict) else None
    else:
        return None
    return value if isinstance(value, str) else None


def _validate_distribution(canon: dict, canon_path: str) -> None:
    entries = canon.get('distribution')
    expected = ({'canonical_roots.' + key for key in canon.get('canonical_roots', {})}
                | set(_layout_paths(canon.get('layout', {}))))
    if not isinstance(entries, list) or not entries or len(entries) > 200:
        raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'distribution')
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != _DISTRIBUTION_FIELDS:
            raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'distribution')
        reference = entry['ref']
        if not isinstance(reference, str) or reference in seen or reference not in expected:
            raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'distribution.ref')
        if _distribution_path(canon, reference) is None:
            raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'distribution.ref')
        seen.add(reference)
        if entry['role'] not in _DISTRIBUTION_ROLES:
            raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'distribution.role')
        profiles = entry['profiles']
        if (not isinstance(profiles, list) or not profiles or len(profiles) > 3
                or any(not isinstance(item, str) or item not in _DISTRIBUTION_PROFILES for item in profiles)
                or len(profiles) != len(set(profiles))):
            raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'distribution.profiles')
        if entry['copy_policy'] not in _DISTRIBUTION_COPY:
            raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'distribution.copy_policy')
        if not isinstance(entry['owner'], str) or not entry['owner'].strip() or len(entry['owner']) > 128:
            raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'distribution.owner')
        if entry['doc_policy'] not in _DISTRIBUTION_DOCS:
            raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'distribution.doc_policy')
        if entry['scan_policy'] not in _DISTRIBUTION_SCAN:
            raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'distribution.scan_policy')
    if seen != expected:
        raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'distribution')


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _read_contained_policy(root: Path, relative: str, policy_id: str) -> dict:
    current = root
    for part in relative.split('/'):
        current = current / part
        try:
            info = current.lstat()
        except OSError as error:
            raise PolicyError('POLICY_MISSING', policy_id, relative, None) from error
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise PolicyError('POLICY_SCHEMA_ERROR', policy_id, relative, 'path')
    try:
        return read_policy(current)
    except OSError as error:
        raise PolicyError('POLICY_MISSING', policy_id, relative, None) from error
    except (ValueError, UnicodeError) as error:
        raise PolicyError('POLICY_SCHEMA_ERROR', policy_id, relative, 'yaml') from error


def load_preliminary_policy_bundle(root: Path):
    """Load and validate fixed policies, layout and distribution as immutable data.

    This does not authenticate releases or replace the existing validators.
    Ancestor checks are path-based, not apply-time locks.
    """
    root = Path(root).absolute()
    canon_path = '.doc/harnes/state/canon-paths.yaml'
    canon = _read_contained_policy(root, canon_path, 'canon_paths')
    if type(canon.get('schema_version')) is not int or canon['schema_version'] != 1:
        raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'schema_version')
    declared = canon.get('policies')
    if not isinstance(declared, dict) or set(declared) != set(_PRELIMINARY_FILES):
        raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'policies')
    local = canon.get('local_extension')
    if local != {'path': '.doc/harnes/state/canon-paths.local.yaml', 'allowed_sections': ['custom_components']}:
        raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'local_extension')
    _validate_distribution(canon, canon_path)
    loaded = {}
    for policy_id, relative in _PRELIMINARY_FILES.items():
        if declared[policy_id] != {'path': relative, 'required_profiles': ['core', 'developer', 'project']}:
            raise PolicyError('POLICY_SCHEMA_ERROR', 'canon_paths', canon_path, 'policies.' + policy_id)
        data = _read_contained_policy(root, relative, policy_id)
        if set(data) != {'schema_version', 'policy_id', 'self_path', 'owner', 'rules'}:
            raise PolicyError('POLICY_SCHEMA_ERROR', policy_id, relative, 'root')
        if type(data['schema_version']) is not int or data['schema_version'] != 1 or data['policy_id'] != policy_id or data['owner'] != 'harness-core':
            raise PolicyError('POLICY_SCHEMA_ERROR', policy_id, relative, 'identity')
        if data['self_path'] != relative:
            raise PolicyError('SELF_PATH_MISMATCH', policy_id, relative, 'self_path')
        rules = data['rules']
        expected = {'SF01', 'SF02', 'SF03'} if policy_id == 'skill_format' else {'CD01', 'CD02', 'CD03', 'CD04'}
        if not isinstance(rules, dict) or set(rules) != expected:
            raise PolicyError('POLICY_SCHEMA_ERROR', policy_id, relative, 'rules')
        for rule_id, rule in rules.items():
            scope, fields = _RULE_FIELDS[rule_id]
            if not isinstance(rule, dict) or set(rule) != {'severity', 'enabled', 'scope'} | set(fields):
                raise PolicyError('POLICY_SCHEMA_ERROR', policy_id, relative, rule_id)
            if type(rule['enabled']) is not bool or rule['severity'] not in ('error', 'warning') or rule['scope'] != scope:
                raise PolicyError('POLICY_SCHEMA_ERROR', policy_id, relative, rule_id)
            if not rule['enabled'] or rule['severity'] != 'error':
                raise PolicyError('TRUSTED_GATE_WEAKENING', policy_id, relative, rule_id)
            for key, kind in fields.items():
                value = rule[key]
                if type(value) is not kind or (kind is str and (not value.strip() or len(value) > 1024)):
                    raise PolicyError('POLICY_SCHEMA_ERROR', policy_id, relative, rule_id + '.' + key)
                if kind is list and (not value or len(value) > 100 or any(type(item) is not str or not item.strip() or len(item) > 1024 for item in value) or len(value) != len(set(value))):
                    raise PolicyError('POLICY_SCHEMA_ERROR', policy_id, relative, rule_id + '.' + key)
                if kind is bool and value is not True:
                    raise PolicyError('TRUSTED_GATE_WEAKENING', policy_id, relative, rule_id + '.' + key)
        if policy_id == 'skill_format' and set(rules['SF01']['required_files']) != {'SKILL.md', 'README.md', 'skill.json'}:
            raise PolicyError('TRUSTED_GATE_WEAKENING', policy_id, relative, 'SF01.required_files')
        if policy_id == 'component_docs':
            layout = canon.get('layout')
            docs = layout.get('docs') if isinstance(layout, dict) else None
            for rule_id, expected_key in (('CD02', 'layout.docs.script_skill'), ('CD03', 'layout.docs.mcp_skill')):
                if rules[rule_id]['layout_key'] != expected_key or not isinstance(docs, dict) or not isinstance(docs.get(expected_key.rsplit('.', 1)[-1]), str):
                    raise PolicyError('POLICY_SCHEMA_ERROR', policy_id, relative, rule_id + '.layout_key')
        loaded[policy_id] = data
    return _freeze({'policies': loaded, 'layout': canon['layout'], 'distribution': canon['distribution']})


def load_preliminary_policies(root: Path):
    """Compatibility view of preliminary policy rules without the layout."""
    return load_preliminary_policy_bundle(root)['policies']
