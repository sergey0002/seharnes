"""Deterministic, read-only autodoc bundle, renderer and audit pipeline.

The module is intentionally dependency free.  The canonical inputs remain the
workspace files; a bundle is a portable projection with embedded source bytes
for the small text/configuration formats used by todone.  HTML is a derived
view of that bundle and never reads the live workspace.

Public operations are used by both ``tcheck autodoc`` and the compatibility
entry point in ``scripts/todone-autodoc.py``::

    discover_workspace(root)
    build_bundle(root, path=...)
    render_bundle(bundle_or_path, html=...)
    audit_bundle(bundle_or_path, output=...)
    verify_bundle(bundle_or_path, html=...)
    reconstruct_bundle(bundle_or_path, target=...)

Volatile run timestamps and aggregate run ids are deliberately outside the
canonical digest.  Every other value is sorted/canonicalised before hashing.
"""

from __future__ import annotations

import ast
import base64
import copy
import hashlib
import html
import json
import mimetypes
import os
import posixpath
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .aggregate import (Aggregate, DEFAULT_EXCLUDES, _media_type, _rel,
                        _within, sha256_bytes, sha256_file)
from .errors import EXIT_FINDINGS, EXIT_OK, Issue, SkillError
from .flow import FlowIndex
from .typedefs import TypeIndex


AUTODOC_BUNDLE_SCHEMA = "AUTODOC-BUNDLE-1"
AUTODOC_ENTITY_SCHEMA = "AUTODOC-ENTITY-1"
AUTODOC_RELATION_SCHEMA = "AUTODOC-RELATION-1"
AUTODOC_SOURCE_SCHEMA = "AUTODOC-SOURCE-1"
AUTODOC_DIAGRAM_SCHEMA = "AUTODOC-DIAGRAM-1"
AUTODOC_AUDIT_SCHEMA = "AUTODOC-AUDIT-1"
AUTODOC_HTML_SCHEMA = "AUTODOC-HTML-1"
AUTODOC_RECONSTRUCTION_SCHEMA = "AUTODOC-RECONSTRUCTION-1"
AUTODOC_PACKET_SCHEMA = "AUTODOC-AUDIT-PACKET-1"
AUTODOC_MARKDOWN_SCHEMA = "AUTODOC-MARKDOWN-1"
AUTODOC_PREZA_SCHEMA = "AUTODOC-PREZA-MIGRATION-1"
PREZA_PARITY_SCHEMA = "PREZA-PARITY-1"
PREZA_PARITY_CATEGORIES = (
    "entity_sections", "lifecycle", "schema_notes", "faq", "command_notes",
    "file_overrides", "commands", "types", "flows", "schemas", "templates",
    "file_notes", "checks", "live_facts", "svg",
)
PREZA_PARITY_STATUSES = ("preserved", "transformed", "deprecated", "unknown")
AUTODOC_GENERATOR_VERSION = "autodoc-local-1"
MERMAID_RENDERER = "mermaid"
MERMAID_VERSION = "12.3.0"
MERMAID_VENDOR_REL = "scripts/tdcore/vendor/mermaid"
MERMAID_ADAPTER_REL = MERMAID_VENDOR_REL + "/render.cjs"
MERMAID_RUNTIME_REL = MERMAID_VENDOR_REL + "/mermaid.min.js"

RELATION_KINDS = (
    "contains", "parent", "depends_on", "blocks", "references", "defines",
    "implements", "verifies", "documents", "mirrors", "supersedes",
    "generated_from", "uses", "produces", "flows_to", "route_to",
    "attached_to", "source_of", "conflicts_with", "stale_against",
)
RESOLUTIONS = ("resolved", "unresolved", "ambiguous", "unknown")
STATUSES = ("complete", "partial", "blocked", "read", "missing", "unknown",
            "preserved", "transformed", "deprecated", "invalid")

# Keys which are volatile only at the bundle envelope level.  A task's
# created_at is source data and must not be removed from its canonical source.
_VOLATILE_TOP_LEVEL = {"created_at", "generated_at", "runtime", "timings",
                       "outputs", "canonical_digest", "bundle_id"}
_HTML_VOLATILE = {"generated_at", "runtime", "timings"}


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_dumps(value, *, pretty=False):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      indent=2 if pretty else None,
                      separators=None if pretty else (",", ":"))


def canonical_bytes(value):
    """Return the exact UTF-8 canonical representation used for digesting."""
    return _json_dumps(value).encode("utf-8")


def _canonical_bundle_view(bundle):
    value = copy.deepcopy(bundle)
    if isinstance(value, dict):
        for key in _VOLATILE_TOP_LEVEL:
            value.pop(key, None)
        # ``audit_input`` is deliberately deterministic.  It is retained in
        # the digest; the separately written audit report is not.
    return value


def canonical_digest(bundle):
    return sha256_bytes(canonical_bytes(_canonical_bundle_view(bundle)))


def _source_id(digest):
    return "source:" + str(digest or "sha256:unknown").split(":", 1)[-1]


def _slug(value, fallback="item"):
    text = str(value or "").strip().lower()
    text = re.sub(r"[^\w.-]+", "-", text, flags=re.UNICODE)
    text = re.sub(r"-+", "-", text).strip("-.")
    return text or fallback


def _anchor(value, used=None):
    base = _slug(value, "section")
    used = used if used is not None else set()
    candidate = base
    number = 2
    while candidate in used:
        candidate = "%s-%d" % (base, number)
        number += 1
    used.add(candidate)
    return candidate


def _path_error(path):
    return SkillError("AUTODOC_PATH_UNSAFE", "небезопасный относительный путь: %s" % path,
                      str(path), command="tcheck autodoc verify --bundle <path>")


def safe_relative_path(path):
    """Validate a portable source path and return POSIX spelling.

    Absolute paths, drive prefixes, NULs, traversal and empty components are
    rejected.  This is used for both source inventory and reconstruction.
    """
    raw = str(path or "")
    if not raw or "\x00" in raw or os.path.isabs(raw) or re.match(r"^[A-Za-z]:[\\/]", raw):
        raise _path_error(raw)
    normal = raw.replace("\\", "/")
    parts = normal.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise _path_error(raw)
    return "/".join(parts)


def _safe_output_name(value):
    return _slug(value, "source")[:120]


def _is_secret(path, data=None):
    lower = str(path).lower()
    if any(token in lower for token in (".env", ".netrc", "credentials", "secret", "private-key")):
        return True
    if lower.endswith((".pem", ".key", ".p12", ".pfx")):
        return True
    if data and re.search(r"-----begin (?:private|rsa|ec) key-----", data[:2000], re.I):
        return True
    return False


def _is_generated(relpath):
    parts = relpath.replace("\\", "/").split("/")
    if not parts:
        return True
    generated_dirs = {"docs_html", "site", "node_modules", "dist", "build", "out",
                      "coverage", ".cache", "__pycache__"}
    if any(part in generated_dirs for part in parts):
        return True
    if any(part.endswith((".tmp", ".bak", ".autodoc.bak")) for part in parts):
        return True
    if ".todone" in parts:
        idx = parts.index(".todone")
        tail = parts[idx + 1:]
        if tail and tail[0] in {"autodoc", "aggregate"}:
            return True
        if any(name.endswith((".tmp", ".bak")) for name in tail):
            return True
    return False


def _media(path):
    suffix = os.path.splitext(path)[1].lower()
    return ({".md": "text/markdown", ".markdown": "text/markdown",
             ".json": "application/json", ".yaml": "application/yaml",
             ".yml": "application/yaml", ".txt": "text/plain",
             ".py": "text/x-python", ".css": "text/css", ".js": "text/javascript",
             ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
             ".jpeg": "image/jpeg", ".gif": "image/gif"}.get(suffix)
            or mimetypes.guess_type(path)[0] or "application/octet-stream")


def _read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def _decode_text(data):
    try:
        return data.decode("utf-8"), True
    except UnicodeDecodeError:
        return None, False


def _write_json(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise SkillError("AUTODOC_BUNDLE_INVALID", "bundle JSON не читается: %s" % exc, path)


def _warning(code, path, message, severity="warning", **extra):
    value = {"code": code, "path": path or ".", "message": message,
             "severity": severity}
    value.update(extra)
    return value


def _provenance(source_ref, path, adapter, *, line=None, note=None):
    value = {"source_ref": source_ref, "path": path, "adapter": adapter}
    if line is not None:
        value["line"] = line
    if note:
        value["note"] = note
    return [value]


def _entity(entity_id, kind, namespace, status, source_refs, normalized,
            *, raw_ref=None, revision=None, adapter="autodoc"):
    value = {
        "$schema": AUTODOC_ENTITY_SCHEMA,
        "schema": AUTODOC_ENTITY_SCHEMA,
        "entity_id": entity_id,
        "kind": kind,
        "namespace": namespace,
        "status": status,
        "source_refs": sorted(set(str(item) for item in source_refs if item)),
        "provenance": _provenance(
            (source_refs or [None])[0],
            ((normalized.get("source_path") or normalized.get("canonical_path") or normalized.get("path"))
             if isinstance(normalized, dict) else None),
            adapter),
        "normalized": normalized,
    }
    if raw_ref:
        value["raw_ref"] = raw_ref
    if revision is not None:
        value["revision"] = revision
    return value


def _relation(relation_id, source, target, kind, resolution,
              source_refs=None, provenance=None, **extra):
    value = {
        "$schema": AUTODOC_RELATION_SCHEMA,
        "schema": AUTODOC_RELATION_SCHEMA,
        "relation_id": relation_id,
        "from": source,
        "to": target,
        "kind": kind,
        "resolution": resolution,
        "source_refs": sorted(set(str(item) for item in (source_refs or []) if item)),
        "provenance": provenance or _provenance((source_refs or [None])[0], None, "relation"),
    }
    value.update(extra)
    return value


def _source_record(path, data, *, root, domain="workspace", source_of_truth=True,
                   generated=False, archive=False, redact=False, external=False,
                   adapter="source-inventory"):
    """Build AUTODOC-SOURCE-1 without losing original bytes."""
    rel = path if external else _rel(root, path)
    rel = str(rel).replace(os.sep, "/")
    if external:
        # External adapters must still expose a portable path.  Callers pass an
        # already portable ``external/...`` value in this case.
        rel = rel.replace("\\", "/").lstrip("/")
    if not external:
        rel = safe_relative_path(rel)
    digest = sha256_bytes(data)
    text, is_text = _decode_text(data)
    secret = _is_secret(rel, text)
    should_redact = secret or redact
    if should_redact:
        raw = None
        raw_encoding = None
        redaction = {"status": "redacted", "reason": "secret_or_policy"}
    elif is_text:
        raw = text
        raw_encoding = "utf-8"
        redaction = {"status": "none"}
    elif archive:
        raw = base64.b64encode(data).decode("ascii")
        raw_encoding = "base64"
        redaction = {"status": "none"}
    else:
        raw = None
        raw_encoding = None
        redaction = {"status": "excluded", "reason": "binary_requires_archive"}
    source = {
        "$schema": AUTODOC_SOURCE_SCHEMA,
        "schema": AUTODOC_SOURCE_SCHEMA,
        "source_id": _source_id(digest),
        "canonical_path": rel,
        "source_domain": domain,
        "media_type": _media(rel),
        "byte_size": len(data),
        "sha256": digest,
        "mode_policy": "read-only",
        "raw": raw,
        "raw_encoding": raw_encoding,
        "redaction": redaction,
        "classification": "generated" if generated else ("secret" if secret else "canonical"),
        "source_of_truth": bool(source_of_truth and not generated),
        "generated": bool(generated),
        "provenance": _provenance(_source_id(digest), rel, adapter),
        "external": bool(external),
    }
    if text is not None and not should_redact:
        source["text_encoding"] = "utf-8"
    if raw is None and not should_redact:
        source["raw_available"] = False
    else:
        source["raw_available"] = True
    return source


# ---------------------------------------------------------------------------
# Markdown contract


def _frontmatter(lines):
    if not lines or lines[0].strip() != "---":
        return {}, 0
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            end = index
            break
    if end is None:
        return {}, 0
    result = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip("'\"")
    return result, end + 1


def _parse_markdown(text, source_path):
    """Parse the documented safe subset into lossless-ish tokens.

    Unknown lines are kept as ``raw_unknown`` tokens and escaped at render time;
    this is intentionally not a general HTML/Markdown execution engine.
    """
    lines = text.splitlines()
    metadata, start = _frontmatter(lines)
    tokens = []
    headings = []
    links = []
    images = []
    compatibility = []
    used = set()
    i = start
    paragraph = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            value = "\n".join(paragraph)
            tokens.append({"kind": "paragraph", "text": value,
                           "line": i - len(paragraph) + 1})
            paragraph = []

    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*<!--\s*AUTODOC:(?:BEGIN|END) diagram=", line):
            flush_paragraph()
            tokens.append({"kind": "generated_marker", "text": line, "line": i + 1})
            i += 1
            continue
        fence_match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence_match:
            flush_paragraph()
            marker = fence_match.group(1)
            marker_char = marker[0]
            language = fence_match.group(2).strip()
            body = []
            line_no = i + 1
            i += 1
            closed = False
            close_pattern = re.compile(r"^ {0,3}%s{%d,}\s*$" %
                                       (re.escape(marker_char), len(marker)))
            while i < len(lines):
                if close_pattern.match(lines[i]):
                    closed = True
                    i += 1
                    break
                body.append(lines[i])
                i += 1
            if not closed:
                compatibility.append({"kind": "unclosed_fence", "line": line_no,
                                      "message": "fenced code block is not closed"})
            normalized_language = language.split(None, 1)[0].lower() if language else ""
            is_mermaid = normalized_language in {"mermaid", "mmd"}
            tokens.append({"kind": "mermaid" if is_mermaid else "code",
                           "language": normalized_language if is_mermaid else language,
                           "text": "\n".join(body), "line": line_no,
                           "closed": closed})
            continue
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush_paragraph()
            title = match.group(2).strip().rstrip("#").strip()
            anchor = _anchor(re.sub(r"[`*_]", "", title), used)
            headings.append({"level": len(match.group(1)), "text": title,
                             "anchor": anchor, "line": i + 1})
            tokens.append({"kind": "heading", "level": len(match.group(1)),
                           "text": title, "anchor": anchor, "line": i + 1})
            i += 1
            continue
        if re.match(r"^\s*([-*_])(?:\s*\1){2,}\s*$", line):
            flush_paragraph()
            tokens.append({"kind": "thematic_break", "line": i + 1})
            i += 1
            continue
        # A simple GFM table: retain cells and the separator as structured data.
        if "|" in line and i + 1 < len(lines) and re.match(
                r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$",
                lines[i + 1]):
            flush_paragraph()
            def cells(value):
                return [item.strip() for item in value.strip().strip("|").split("|")]
            header = cells(line)
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i]))
                i += 1
            tokens.append({"kind": "table", "header": header, "rows": rows,
                           "line": i - len(rows) - 1})
            continue
        list_match = re.match(r"^\s*(?:[-+*]|\d+[.)])\s+(.+)$", line)
        if list_match:
            flush_paragraph()
            ordered = bool(re.match(r"^\s*\d", line))
            items = [list_match.group(1)]
            line_no = i + 1
            i += 1
            while i < len(lines):
                next_match = re.match(r"^\s*(?:[-+*]|\d+[.)])\s+(.+)$", lines[i])
                if not next_match:
                    break
                items.append(next_match.group(1))
                i += 1
            tokens.append({"kind": "list", "ordered": ordered, "items": items,
                           "line": line_no})
            continue
        quote_match = re.match(r"^\s*>\s?(.*)$", line)
        if quote_match:
            flush_paragraph()
            items = [quote_match.group(1)]
            line_no = i + 1
            i += 1
            while i < len(lines):
                next_match = re.match(r"^\s*>\s?(.*)$", lines[i])
                if not next_match:
                    break
                items.append(next_match.group(1))
                i += 1
            tokens.append({"kind": "blockquote", "items": items, "line": line_no})
            continue
        if line.strip().startswith("<") and re.search(r"</?[^>]+>", line):
            flush_paragraph()
            compatibility.append({"kind": "unsafe_html", "line": i + 1,
                                  "message": "raw HTML is escaped in generated pages"})
            tokens.append({"kind": "raw_unknown", "text": line, "line": i + 1})
            i += 1
            continue
        if not line.strip():
            flush_paragraph()
            i += 1
            continue
        paragraph.append(line)
        i += 1

    flush_paragraph()
    source_links = []
    source_images = []
    pattern = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+['\"]([^'\"]*)['\"])?\)")
    for token in tokens:
        if token["kind"] not in ("paragraph", "heading", "list", "blockquote", "table"):
            continue
        values = []
        if token["kind"] == "table":
            values = list(token.get("header", [])) + [x for row in token.get("rows", []) for x in row]
        elif token["kind"] == "list":
            values = token["items"]
        elif token["kind"] == "blockquote":
            values = token["items"]
        else:
            values = [token.get("text", "")]
        token["inline_values"] = values
        for value in values:
            for match in pattern.finditer(value):
                item = {"target": match.group(3), "label": match.group(2),
                        "line": token.get("line"), "raw": match.group(0)}
                if match.group(1):
                    images.append(item)
                    source_images.append(item)
                else:
                    links.append(item)
                    source_links.append(item)
    return {
        "$schema": AUTODOC_MARKDOWN_SCHEMA,
        "schema": AUTODOC_MARKDOWN_SCHEMA,
        "source_path": source_path,
        "encoding": "utf-8",
        "frontmatter": metadata,
        "headings": headings,
        "tokens": tokens,
        "links": links,
        "images": images,
        "raw_unknown": [token for token in tokens if token["kind"] == "raw_unknown"],
        "compatibility": compatibility,
        "source_digest": None,
        "rendered_html": "",
    }


def _safe_url(target):
    parsed = urlparse(str(target))
    if parsed.scheme.lower() in {"javascript", "data", "vbscript", "file"}:
        return None
    return str(target)


def _inline_html(text, *, source_path=None, page_path="", page_map=None,
                 image_map=None, compatibility=None, line=None):
    page_map = page_map or {}
    image_map = image_map or {}
    compatibility = compatibility if compatibility is not None else []
    pattern = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+['\"]([^'\"]*)['\"])?\)")
    pieces = []
    last = 0
    for match in pattern.finditer(text):
        pieces.append(html.escape(text[last:match.start()]))
        image = bool(match.group(1))
        label = html.escape(match.group(2), quote=True)
        target = match.group(3)
        safe = _safe_url(target)
        if safe is None:
            compatibility.append({"kind": "unsafe_url", "target": target, "line": line,
                                  "message": "unsafe URL was redacted"})
            pieces.append("[unsafe link redacted]")
            last = match.end()
            continue
        if image:
            mapped = image_map.get((source_path, target))
            if mapped:
                href = posixpath.relpath(mapped, posixpath.dirname(page_path) or ".")
                pieces.append('<img src="%s" alt="%s" loading="lazy">' %
                              (html.escape(href, quote=True), label))
            else:
                compatibility.append({"kind": "missing_image", "target": target,
                                      "line": line, "message": "image is not embedded"})
                pieces.append('<span class="missing-image">[image: %s]</span>' % label)
        else:
            href = safe
            if source_path and not urlparse(safe).scheme and not safe.startswith("#"):
                target_path, _, anchor = safe.partition("#")
                if target_path.endswith((".md", ".markdown")):
                    joined = posixpath.normpath(posixpath.join(posixpath.dirname(source_path), target_path))
                    mapped_page = page_map.get(joined)
                    if mapped_page:
                        href = posixpath.relpath(mapped_page, posixpath.dirname(page_path) or ".")
                        if anchor:
                            href += "#" + _slug(anchor)
                    else:
                        compatibility.append({"kind": "broken_link", "target": safe,
                                              "line": line, "message": "Markdown target not found"})
                        href = "#unresolved-link"
            title = (' title="%s"' % html.escape(match.group(4), quote=True)) if match.group(4) else ""
            pieces.append('<a href="%s"%s>%s</a>' %
                          (html.escape(href, quote=True), title, label))
        last = match.end()
    pieces.append(html.escape(text[last:]))
    result = "".join(pieces)
    # Inline code is escaped before replacement, so backticks cannot introduce
    # tags.  Strong/emphasis are intentionally a tiny safe subset.
    result = re.sub(r"`([^`]+)`", r"<code>\1</code>", result)
    result = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", result)
    result = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", result)
    return result


def render_markdown(markdown, *, source_path, page_path="", page_map=None,
                    image_map=None):
    compatibility = list(markdown.get("compatibility") or [])
    out = []
    for token in markdown.get("tokens") or []:
        kind = token.get("kind")
        line = token.get("line")
        if kind == "heading":
            level = max(1, min(6, int(token.get("level", 1))))
            text = _inline_html(token.get("text", ""), source_path=source_path,
                                page_path=page_path, page_map=page_map,
                                image_map=image_map, compatibility=compatibility, line=line)
            out.append('<h%d id="%s">%s</h%d>' %
                       (level, html.escape(token.get("anchor", "section"), quote=True), text, level))
        elif kind == "paragraph":
            text = token.get("text", "").replace("\n", "\n")
            out.append("<p>%s</p>" % _inline_html(text, source_path=source_path,
                                                    page_path=page_path, page_map=page_map,
                                                    image_map=image_map, compatibility=compatibility,
                                                    line=line))
        elif kind in {"code", "mermaid"}:
            language = _slug(token.get("language"), "text")
            out.append('<pre><code class="language-%s">%s</code></pre>' %
                       (html.escape(language, quote=True), html.escape(token.get("text", ""))))
        elif kind == "list":
            tag = "ol" if token.get("ordered") else "ul"
            out.append("<%s>%s</%s>" % (tag, "".join(
                "<li>%s</li>" % _inline_html(value, source_path=source_path,
                                                page_path=page_path, page_map=page_map,
                                                image_map=image_map, compatibility=compatibility,
                                                line=line)
                for value in token.get("items", [])), tag))
        elif kind == "blockquote":
            out.append("<blockquote>%s</blockquote>" % "<br>".join(
                _inline_html(value, source_path=source_path, page_path=page_path,
                             page_map=page_map, image_map=image_map,
                             compatibility=compatibility, line=line)
                for value in token.get("items", [])))
        elif kind == "table":
            header = "".join("<th>%s</th>" % _inline_html(value, source_path=source_path,
                                                               page_path=page_path, page_map=page_map,
                                                               image_map=image_map,
                                                               compatibility=compatibility, line=line)
                             for value in token.get("header", []))
            rows = []
            for row in token.get("rows", []):
                rows.append("<tr>%s</tr>" % "".join(
                    "<td>%s</td>" % _inline_html(value, source_path=source_path,
                                                   page_path=page_path, page_map=page_map,
                                                   image_map=image_map,
                                                   compatibility=compatibility, line=line)
                    for value in row))
            out.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" %
                       (header, "".join(rows)))
        elif kind == "thematic_break":
            out.append("<hr>")
        elif kind == "raw_unknown":
            out.append('<details class="unknown-markdown"><summary>Raw unknown Markdown</summary><pre>%s</pre></details>'
                       % html.escape(token.get("text", "")))
    return "\n".join(out), compatibility


def _mermaid_source_without_marker(source):
    lines = []
    diagram_id = None
    for line in str(source or "").splitlines():
        match = re.match(r"^\s*%%\s*AUTODOC-DIAGRAM:\s*(\S+)\s*$", line)
        if match:
            diagram_id = match.group(1)
            continue
        lines.append(line)
    return "\n".join(lines).strip(), diagram_id


def _autodoc_begin_metadata(text):
    match = re.search(r"AUTODOC:BEGIN\s+diagram=([^\s>]+)", str(text or ""), re.I)
    if not match:
        return None
    value = {"diagram_id": match.group(1)}
    for key in ("source_digest", "projection_digest", "spec_digest"):
        found = re.search(r"\b%s=([^\s>]+)" % key, str(text or ""), re.I)
        value[key] = found.group(1) if found else None
    return value


def _markdown_diagram_id(source_path, line, source):
    digest = hashlib.sha256((str(source_path) + "\0" + str(line) + "\0" +
                             str(source)).encode("utf-8")).hexdigest()[:20]
    return "markdown:%s:%s" % (_slug(source_path, "document")[:70], digest)


def _ensure_mermaid_accessibility(source, title, diagram_id):
    """Add deterministic Mermaid accessibility directives to a user block."""
    lines = str(source or "").splitlines()
    if not lines:
        return source
    if not any(re.match(r"^\s*accTitle\s*:", line) for line in lines):
        insert_at = 1 if lines[0].strip() else 0
        lines.insert(insert_at, "accTitle: %s" % _mermaid_label(title or diagram_id or "Диаграмма"))
    if not any(re.match(r"^\s*accDescr\s*:", line) for line in lines):
        insert_at = 2 if len(lines) > 1 else len(lines)
        lines.insert(insert_at, "accDescr: Офлайн Mermaid-диаграмма из Markdown.")
    return "\n".join(lines) + "\n"


def _inject_markdown_mermaid_blocks(rendered, diagram_svgs, diagram_specs, *, source_path=""):
    """Replace Mermaid fences with the SVG already recorded in the bundle.

    Rendering never creates an untracked diagram as a side effect. Every
    fenced block must have a corresponding ``AUTODOC-DIAGRAM-1`` record whose
    source digest and local SVG were finalized before HTML generation.
    """
    pattern = re.compile(r'<pre><code class="language-mermaid">(.*?)</code></pre>', re.S)
    matches = list(pattern.finditer(rendered))
    if not matches:
        return rendered, []
    specs_by_id = {spec.get("diagram_id"): spec for spec in diagram_specs}
    source_digest = {}
    for spec in diagram_specs:
        if spec.get("source_document_path") == source_path:
            source_digest.setdefault(spec.get("mermaid_source_digest"), []).append(spec)
    replacements = []
    errors = []
    for match in matches:
        raw_source = html.unescape(match.group(1))
        clean_source, marker_id = _mermaid_source_without_marker(raw_source)
        digest = sha256_bytes(clean_source.encode("utf-8"))
        known = specs_by_id.get(marker_id) if marker_id else None
        if known is None:
            candidates = source_digest.get(digest) or []
            known = candidates[0] if candidates else None
        title = (known or {}).get("title") or marker_id or "Markdown Mermaid"
        render_id = (known or {}).get("diagram_id")
        svg = diagram_svgs.get(render_id) if render_id else None
        if known and known.get("source_mode") == "markdown" and digest != known.get("mermaid_source_digest"):
            errors.append({"kind": "mermaid_source_digest", "message":
                           "исходник Mermaid не совпадает с provenance для %s" % known.get("diagram_id")})
            svg = None
        replacements.append({"match": match, "raw_source": raw_source, "title": title, "svg": svg})
    output = []
    cursor = 0
    for replacement in replacements:
        match = replacement["match"]
        output.append(rendered[cursor:match.start()])
        svg = replacement.get("svg")
        source_text = replacement["raw_source"]
        if svg:
            inline_svg = svg.replace(' xmlns="http://www.w3.org/2000/svg"', "")
            output.append(
                '<figure class="markdown-diagram"><div class="diagram">%s</div>'
                '<figcaption>Mermaid-диаграмма из Markdown · %s</figcaption>'
                '<details class="json-details"><summary>Показать исходник Mermaid</summary>'
                '<pre><code class="language-mermaid">%s</code></pre></details></figure>' %
                (inline_svg, html.escape(str(replacement["title"])), html.escape(source_text)))
        else:
            output.append('<div class="callout error"><strong>Mermaid source не отрисован.</strong>'
                          '<details class="json-details"><summary>Показать исходник</summary>'
                          '<pre><code class="language-mermaid">%s</code></pre></details></div>' %
                          html.escape(source_text))
        cursor = match.end()
    output.append(rendered[cursor:])
    return "".join(output), errors


# ---------------------------------------------------------------------------
# Discovery and bundle construction


class DiscoveryReport:
    """Serializable discovery result used by ``autodoc discover``."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.found = []
        self.skipped = []
        self.invalid = []
        self.unknowns = []
        self.warnings = []

    def as_dict(self):
        return {"root": ".", "found": sorted(self.found, key=lambda item: _json_dumps(item)),
                "skipped": sorted(self.skipped, key=lambda item: _json_dumps(item)),
                "invalid": sorted(self.invalid, key=lambda item: _json_dumps(item)),
                "unknowns": sorted(self.unknowns, key=lambda x: _json_dumps(x)),
                "warnings": sorted(self.warnings, key=lambda x: _json_dumps(x))}


def discover_workspace(root, *, legacy_root=None):
    """Read-only inventory of declared roots and relevant source families."""
    root = os.path.abspath(root)
    report = DiscoveryReport(root)
    if not os.path.isdir(root):
        raise SkillError("AUTODOC_ROOT_MISSING", "root не является каталогом", root)
    aggregate = Aggregate(root)
    try:
        workspaces, warnings = aggregate._discover()
    except Exception as exc:  # discovery must expose, not hide, adapter failures
        workspaces, warnings = [], [_warning("DISCOVERY_FAILED", ".", str(exc), "error")]
    for path, marker, mode in workspaces:
        report.found.append({"kind": "workspace", "workspace_id": marker.get("workspace_id"),
                             "path": _rel(root, path), "mode": mode})
        docs_path = marker.get("docs_path") or "docs"
        docs_abs = docs_path if os.path.isabs(docs_path) else os.path.join(path, docs_path)
        if not _within(path, docs_abs):
            report.invalid.append(_warning("DOCS_PATH_OUTSIDE_WORKSPACE", _rel(root, docs_abs),
                                           "docs path выходит из workspace", "error"))
        elif os.path.isdir(docs_abs):
            report.found.append({"kind": "docs", "workspace_id": marker.get("workspace_id"),
                                 "path": _rel(root, docs_abs)})
        else:
            report.unknowns.append({"kind": "docs", "workspace_id": marker.get("workspace_id"),
                                    "path": _rel(root, docs_abs), "status": "missing"})
        registry = os.path.join(path, ".todone", "queues.json")
        if os.path.isfile(registry):
            report.found.append({"kind": "queue_registry", "path": _rel(root, registry)})
        for alias, queue_path in aggregate._queue_entries(path, marker, []):
            if _within(path, queue_path):
                report.found.append({"kind": "queue", "workspace_id": marker.get("workspace_id"),
                                     "alias": alias, "path": _rel(root, queue_path)})
            else:
                report.unknowns.append({"kind": "external_queue", "workspace_id": marker.get("workspace_id"),
                                        "alias": alias, "path": queue_path,
                                        "status": "external_requires_policy"})
    for warning in warnings:
        report.warnings.append(warning)
    family_dirs = ("docs", "types", "flows", "schemas", "templates", "fixtures", "references")
    for family in family_dirs:
        path = os.path.join(root, family)
        if os.path.isdir(path):
            report.found.append({"kind": family, "path": family})
        else:
            report.skipped.append({"kind": family, "path": family, "reason": "not_present"})
    marker_paths = (os.path.join(root, ".todoc"), os.path.join(root, ".todone", "todoc.json"))
    if any(os.path.exists(path) for path in marker_paths):
        report.unknowns.append({"kind": "todoc", "status": "todoc_unavailable",
                                "reason": "explicit todoc marker found but no supported adapter"})
    legacy = _find_legacy_root(root, legacy_root)
    if legacy:
        report.found.append({"kind": "legacy_preza", "path": legacy})
    return report


def _find_legacy_root(root, explicit=None):
    """Return a legacy root only for an explicit parity request.

    The live project and its canonical Markdown are the only default sources of
    truth. A sibling ``/home/user/preza`` directory, ``PREZA_ROOT`` environment
    variable, or generated legacy site is never scanned implicitly. The explicit
    option remains available as a bounded migration/evidence adapter and its
    records are marked external/non-canonical below.
    """
    if not explicit:
        return None
    candidate = os.path.abspath(explicit)
    return candidate if os.path.isfile(os.path.join(candidate, "build.py")) else None


def _schema_identity(value):
    """Normalise a registry name, schema filename or JSON Schema title."""
    if value is None:
        return ""
    text = str(value).strip().strip("`")
    if text.startswith("schema:registry:"):
        text = text.rsplit(":", 1)[-1]
    text = posixpath.basename(text)
    if text.lower().endswith(".json"):
        text = text[:-5]
    if " " in text:
        prefix, rest = text.split(" ", 1)
        if "marker" in rest.lower() and prefix.upper().startswith("WORKSPACE"):
            text = "WORKSPACE_MARKER"
        else:
            text = prefix
    text = re.sub(r"[-_]?(?:v)?[0-9]+$", "", text)
    text = text.replace("-", "_").upper()
    # DOC-1 is the file-backed name of the DOC_MODULE contract.
    return "DOC_MODULE" if text == "DOC" else text


def _parse_schema_catalog(text):
    catalog = {}
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.count("|") < 3:
            continue
        cells = [item.strip() for item in stripped.strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() in {"идентификатор", "identifier"}:
            continue
        if all(set(cell.replace("-", "")) <= {":"} for cell in cells[:3]):
            continue
        key = cells[0].strip("`")
        if not key:
            continue
        item = {"human_name": cells[1].strip("`") or key,
                "description": cells[2],
                "description_source": "docs/21-schema-catalog.md"}
        for alias in (part.strip() for part in key.split(",")):
            if alias:
                catalog[alias] = item
                catalog[_schema_identity(alias)] = item
    return catalog


def _read_schema_catalog(root):
    path = os.path.join(root, "docs", "21-schema-catalog.md")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return _parse_schema_catalog(handle.read())
    except (OSError, UnicodeError):
        return {}


def _schema_meta(catalog, technical_id, *, payload=None, path=None):
    candidates = [technical_id, _schema_identity(technical_id), path,
                  _schema_identity(path), (payload or {}).get("title")]
    for candidate in candidates:
        item = catalog.get(candidate) or catalog.get(_schema_identity(candidate))
        if item:
            return dict(item)
    fallback = (payload or {}).get("title") or technical_id or path or "контракт"
    return {"human_name": str(fallback), "description": "",
            "description_source": None}


class AutodocBuilder:
    """Build one deterministic bundle without modifying canonical inputs."""

    def __init__(self, root, *, archive=False, redact=False, include=None,
                 exclude=None, legacy_root=None):
        self.root = os.path.abspath(root)
        self.archive = bool(archive)
        self.redact = bool(redact)
        self.include = set(str(item).replace("\\", "/") for item in (include or []))
        self.exclude = set(str(item).replace("\\", "/") for item in (exclude or []))
        self.legacy_root = _find_legacy_root(self.root, legacy_root)
        self.report = discover_workspace(self.root, legacy_root=self.legacy_root)
        self.schema_catalog = _read_schema_catalog(self.root)
        self.sources = []
        self.source_by_path = {}
        self.entities = []
        self.relations = []
        self.warnings = list(self.report.warnings)
        self.unknowns = list(self.report.unknowns)
        self.documents = []
        self.diagrams = []
        self.inventory = {key: [] for key in (
            "workspaces", "queues", "tasks", "documents", "types", "flows",
            "schemas", "templates", "policies", "tools", "roles", "mirrors",
            "flow_states", "flow_steps", "agents", "skills", "source_files")}

    def _add_source(self, path, *, domain="workspace", source_of_truth=True,
                    generated=False, external=False, portable_path=None,
                    adapter="source-inventory"):
        if external:
            raw_path = portable_path or path
            key = str(raw_path).replace("\\", "/")
            if key in self.source_by_path:
                return self.source_by_path[key]
            try:
                data = _read_bytes(path)
            except OSError as exc:
                self.unknowns.append({"kind": "source", "path": key,
                                      "status": "unreadable", "reason": str(exc)})
                return None
            record = _source_record(key, data, root=self.root, domain=domain,
                                    source_of_truth=source_of_truth, generated=generated,
                                    archive=self.archive, redact=self.redact,
                                    external=True, adapter=adapter)
        else:
            rel = _rel(self.root, path).replace(os.sep, "/")
            if _is_generated(rel) or (self.exclude and any(
                    rel == item or rel.startswith(item.rstrip("/") + "/") for item in self.exclude)):
                return None
            if self.include and not any(rel == item or rel.startswith(item.rstrip("/") + "/")
                                        for item in self.include):
                return None
            if rel in self.source_by_path:
                return self.source_by_path[rel]
            try:
                data = _read_bytes(path)
            except OSError as exc:
                self.unknowns.append({"kind": "source", "path": rel,
                                      "status": "unreadable", "reason": str(exc)})
                return None
            record = _source_record(path, data, root=self.root, domain=domain,
                                    source_of_truth=source_of_truth, generated=generated,
                                    archive=self.archive, redact=self.redact,
                                    adapter=adapter)
        self.sources.append(record)
        self.source_by_path[record["canonical_path"]] = record
        return record

    def _inventory_sources(self):
        """Inventory source families and preserve bytes before normalisation."""
        roots = []
        for folder in (".todone", "tasks", "docs", "types", "flows", "schemas", "templates",
                       "child-skills", "references", "fixtures", "examples", "scripts"):
            path = os.path.join(self.root, folder)
            if os.path.isdir(path):
                roots.append(path)
        # Include root-level canonical docs/config files, but not output/cache dirs.
        for folder in roots:
            for current, dirs, files in os.walk(folder, topdown=True, followlinks=False):
                dirs[:] = sorted(d for d in dirs if d not in DEFAULT_EXCLUDES
                                  and d not in {".git", ".hg", ".svn"}
                                  and (not d.startswith(".") or d == ".todone"))
                for name in sorted(files):
                    path = os.path.join(current, name)
                    rel = _rel(self.root, path).replace(os.sep, "/")
                    if os.path.islink(path):
                        self.warnings.append(_warning("SYMLINK_SKIPPED", rel,
                                                      "symlink source не читается"))
                        continue
                    self._add_source(path, domain=_domain_for(rel),
                                     source_of_truth=not _is_generated(rel),
                                     generated=_is_generated(rel))
        for name in sorted(os.listdir(self.root)):
            path = os.path.join(self.root, name)
            if os.path.isfile(path) and name not in {"bundle.json"}:
                self._add_source(path, domain=_domain_for(name))

    def _source_for(self, path):
        if not path:
            return None
        rel = str(path).replace(os.sep, "/")
        return self.source_by_path.get(rel)

    def _add_entity(self, *args, **kwargs):
        value = _entity(*args, **kwargs)
        self.entities.append(value)
        return value

    def _load_aggregate(self):
        aggregate = Aggregate(self.root)
        if hasattr(aggregate, "read_only_scan"):
            return aggregate.read_only_scan()
        # Compatibility fallback for older aggregate modules.  The operation is
        # still read-only from autodoc's point of view; the current repository
        # provides read_only_scan and never reaches this branch.
        return _aggregate_read_only_fallback(aggregate)

    def _collect_workspaces(self, data):
        for item in data.get("workspaces", []):
            workspace_id = item.get("workspace_id") or "unknown"
            source = self._source_for(item.get("marker_path"))
            if source is None:
                source = self._source_for(".todone/queues.json")
            source_refs = [source["source_id"]] if source else []
            entity_id = "workspace:%s" % workspace_id
            normalized = dict(item)
            normalized["source_path"] = item.get("source_path")
            self._add_entity(entity_id, "workspace", "workspace", item.get("status") or "complete",
                             source_refs, normalized, raw_ref=source["source_id"] if source else None,
                             adapter="workspace")
            self.inventory["workspaces"].append(entity_id)

    def _collect_aggregate(self, data):
        task_ids = set()
        doc_ids = set()
        self._index_rows = {}
        self._index_sources = {}
        for item in data.get("queues", []):
            entity_id = "queue:%s:%s" % (item.get("workspace_id"), item.get("alias"))
            source = self._source_for(item.get("source_path"))
            if source is None and item.get("source_path"):
                index_path = posixpath.join(item.get("source_path"), ".todone", "index.json")
                source = self._source_for(index_path)
            if source and source.get("raw"):
                try:
                    index_payload = json.loads(source["raw"])
                except ValueError:
                    index_payload = {}
                if isinstance(index_payload, dict):
                    self._index_sources[(item.get("workspace_id"), item.get("alias"))] = source
                    self._index_rows[(item.get("workspace_id"), item.get("alias"))] = {
                        str(row.get("id")): row for row in index_payload.get("items", [])
                        if isinstance(row, dict) and row.get("id")}
            normalized = dict(item)
            self._add_entity(entity_id, "queue", "todone", item.get("source_status") or "unknown",
                             [source["source_id"]] if source else [], normalized,
                             raw_ref=source["source_id"] if source else None, adapter="todone")
            self.inventory["queues"].append(entity_id)
            workspace_id = "workspace:%s" % item.get("workspace_id")
            self.relations.append(_relation("contains:%s:%s" % (workspace_id, entity_id),
                                             workspace_id, entity_id, "contains", "resolved",
                                             [source["source_id"]] if source else []))
        for item in data.get("tasks", []):
            entity_id = "task:%s:%s:%s" % (item.get("workspace_id"), item.get("queue"), item.get("local_id"))
            task_ids.add(entity_id)
            source = self._source_for(item.get("source_path"))
            task = item.get("task") if isinstance(item.get("task"), dict) else {}
            normalized = {key: value for key, value in item.items() if key != "task"}
            normalized["task"] = task
            index_row = (self._index_rows.get((item.get("workspace_id"), item.get("queue")), {})
                         .get(str(item.get("local_id"))))
            if index_row:
                normalized["index_row"] = index_row
                if index_row.get("flow") or index_row.get("flow_step"):
                    state_id = "flow-state:%s:%s:%s" % (item.get("workspace_id"), item.get("queue"), item.get("local_id"))
                    index_source = self._index_sources.get((item.get("workspace_id"), item.get("queue"))) or source
                    self._add_entity(state_id, "flow_state", "todone", "persisted",
                                     [index_source["source_id"]] if index_source else [],
                                     {"task": entity_id, "index_row": index_row,
                                      "source_path": (index_source or {}).get("canonical_path")},
                                     raw_ref=index_source["source_id"] if index_source else None,
                                     adapter="flow-state")
                    self.inventory["flow_states"].append(state_id)
                    self.relations.append(_relation("attached:%s:%s" % (entity_id, state_id),
                                                     entity_id, state_id, "attached_to", "resolved",
                                                     [source["source_id"]] if source else []))
            self._add_entity(entity_id, "task", "todone", item.get("source_status") or "read",
                             [source["source_id"]] if source else [], normalized,
                             raw_ref=source["source_id"] if source else None,
                             adapter="todone")
            self.inventory["tasks"].append(entity_id)
            # Task elements are first-class entities so an agent can select a
            # single acceptance/verify/ref without parsing provider data.
            for field in ("goals", "acceptance", "in_scope", "out_of_scope", "context",
                          "steps", "verify", "open_questions", "notes"):
                values = task.get(field) or []
                if not isinstance(values, list):
                    values = [values]
                for index, element in enumerate(values, 1):
                    element_id = element.get("id") if isinstance(element, dict) else None
                    element_id = element_id or "%s-%d" % (field, index)
                    child_id = "%s:element:%s" % (entity_id, element_id)
                    self._add_entity(child_id, "task_element", "todone", "read",
                                     [source["source_id"]] if source else [],
                                     {"task": entity_id, "field": field, "value": element,
                                      "source_path": item.get("source_path")},
                                     raw_ref=source["source_id"] if source else None,
                                     adapter="todone")
                    self.relations.append(_relation("contains:%s:%s" % (entity_id, child_id),
                                                     entity_id, child_id, "contains", "resolved",
                                                     [source["source_id"]] if source else []))
            for field, kind in (("comments", "comment"), ("refs", "reference"),
                                ("artifacts", "artifact"), ("report", "report"),
                                ("source", "mirror")):
                values = task.get(field)
                if values is None:
                    continue
                values = values if isinstance(values, list) else [values]
                for index, value in enumerate(values, 1):
                    child_id = "%s:%s:%d" % (entity_id, kind, index)
                    self._add_entity(child_id, kind, "todone", "read",
                                     [source["source_id"]] if source else [],
                                     {"task": entity_id, "value": value,
                                      "source_path": item.get("source_path")},
                                     raw_ref=source["source_id"] if source else None,
                                     adapter="todone")
                    self.relations.append(_relation("attached:%s:%s" % (entity_id, child_id),
                                                     entity_id, child_id, "attached_to", "resolved",
                                                     [source["source_id"]] if source else []))
        for item in data.get("documents", []):
            entity_id = "document:%s" % item.get("global_ref")
            doc_ids.add(entity_id)
            source = self._source_for(item.get("markdown_path")) or self._source_for(item.get("source_path"))
            self._add_entity(entity_id, "document", "documentation", item.get("status") or "read",
                             [source["source_id"]] if source else [], dict(item),
                             raw_ref=source["source_id"] if source else None,
                             revision=item.get("revision"), adapter="aggregate")
            self.inventory["documents"].append(entity_id)
        for item in data.get("relations", []):
            source = _find_task_entity(item.get("from"), self.entities)
            target = _find_task_entity(item.get("to"), self.entities)
            from_id = source or item.get("from")
            to_id = target or item.get("to")
            resolution = "resolved" if item.get("resolved") else "unresolved"
            kind = item.get("kind") or "references"
            if kind not in RELATION_KINDS:
                kind = "references"
            rid = "%s:%s:%s" % (kind, from_id, to_id)
            self.relations.append(_relation(rid, from_id, to_id, kind, resolution,
                                             [], [{"source_ref": None,
                                                   "path": item.get("source"),
                                                   "adapter": "aggregate"}]))
        for item in data.get("warnings", []):
            self.warnings.append(item)
        for item in data.get("unknowns", []) + data.get("invalid_sources", []):
            # Aggregate intentionally reports unregistered files under docs/;
            # autodoc's Markdown adapter registers those files losslessly, so
            # they are not unknown once this adapter has run.  Other unknowns
            # remain explicit provenance gaps.
            if (item.get("status") == "unknown_document"
                    and self._source_for(item.get("source_path"))):
                continue
            self.unknowns.append(item)
        # A parent/queue relation is added only after task ids are known.
        entity_set = {item["entity_id"] for item in self.entities}
        for item in data.get("tasks", []):
            current = "task:%s:%s:%s" % (item.get("workspace_id"), item.get("queue"), item.get("local_id"))
            parent = (item.get("task") or {}).get("parent")
            if parent:
                target = "task:%s:%s:%s" % (item.get("workspace_id"), item.get("queue"), parent)
                self.relations.append(_relation("parent:%s:%s" % (current, target), current,
                                                 target, "parent",
                                                 "resolved" if target in entity_set else "unresolved"))
            for dependency in (item.get("task") or {}).get("depends_on") or []:
                target = "task:%s:%s:%s" % (item.get("workspace_id"), item.get("queue"), dependency)
                self.relations.append(_relation("depends_on:%s:%s" % (current, target), current,
                                                 target, "depends_on",
                                                 "resolved" if target in entity_set else "unresolved"))
        # Inventory counts are useful in both CLI and HTML and intentionally
        # contain stable ids rather than copied unsorted objects.
        for key in self.inventory:
            self.inventory[key] = sorted(set(self.inventory[key]))

    def _collect_types_flows(self):
        types_root = os.path.join(self.root, "types")
        project_types = os.path.join(self.root, ".todone", "types")
        type_index = TypeIndex([types_root, project_types])
        try:
            typedefs = type_index.all()
        except SkillError as exc:
            self.warnings.append(_warning(exc.code, "types", exc.message, "error"))
            typedefs = []
        for typedef in typedefs:
            folder = typedef.folder
            path = os.path.join(folder, "type.json") if folder else None
            source = self._source_for(_rel(self.root, path)) if path and _within(self.root, path) else None
            if source is None:
                # Built-in type data is declared in typedefs.py; keep that
                # code provenance explicit instead of presenting a source-less
                # synthetic type as canonical.
                source = self._source_for("scripts/tdcore/typedefs.py")
            entity_id = "type:%s" % typedef.id
            type_rel = _rel(self.root, path) if path and _within(self.root, path) else None
            type_prefix = os.path.dirname(type_rel) if type_rel else "types/%s" % typedef.id
            instruction_rel = posixpath.join(type_prefix.replace(os.sep, "/"), "instruction.md")
            instruction_source = self.source_by_path.get(instruction_rel)
            if instruction_source is None and os.path.isfile(os.path.join(self.root, instruction_rel)):
                instruction_source = self._add_source(os.path.join(self.root, instruction_rel), domain="types",
                                                      adapter="type-instruction")
            instruction_document = next((item for item in self.documents
                                         if item.get("canonical_path") == instruction_rel), None)
            shared_sources = []
            shared_documents = []
            shared_root = os.path.join(self.root, "types", "_shared")
            if os.path.isdir(shared_root):
                for shared_name in sorted(os.listdir(shared_root)):
                    shared_path = os.path.join(shared_root, shared_name)
                    if not shared_name.endswith(".md") or not os.path.isfile(shared_path):
                        continue
                    shared_rel = _rel(self.root, shared_path).replace(os.sep, "/")
                    shared_source = self.source_by_path.get(shared_rel) or self._add_source(
                        shared_path, domain="types", adapter="type-shared-instruction")
                    if shared_source:
                        shared_sources.append(shared_source["source_id"])
                    shared_document = next((item for item in self.documents
                                            if item.get("canonical_path") == shared_rel), None)
                    if shared_document:
                        shared_documents.append(shared_document["document_id"])
            agent_refs = []
            agent_source_refs = []
            agents_root = os.path.join(type_prefix, "agents") if type_rel else os.path.join(self.root, "types", typedef.id, "agents")
            if not os.path.isabs(agents_root):
                agents_root = os.path.join(self.root, agents_root)
            if os.path.isdir(agents_root):
                for agent_name in sorted(os.listdir(agents_root)):
                    agent_path = os.path.join(agents_root, agent_name)
                    if not agent_name.endswith(".json") or not os.path.isfile(agent_path):
                        continue
                    agent_rel = _rel(self.root, agent_path).replace(os.sep, "/")
                    agent_source = self.source_by_path.get(agent_rel) or self._add_source(
                        agent_path, domain="types", adapter="agent-profile")
                    if not agent_source:
                        continue
                    try:
                        agent_payload = json.loads(agent_source.get("raw") or "{}")
                    except ValueError:
                        agent_payload = {"name": posixpath.splitext(agent_name)[0], "raw_invalid": True}
                        self.warnings.append(_warning("AGENT_JSON_INVALID", agent_rel,
                                                      "профиль агента не является JSON", "error"))
                    agent_id = "agent:%s:%s" % (typedef.id, agent_payload.get("name") or posixpath.splitext(agent_name)[0])
                    self._add_entity(agent_id, "agent", "agents", "read", [agent_source["source_id"]],
                                     {"id": agent_id, "name": agent_payload.get("name") or posixpath.splitext(agent_name)[0],
                                      "role": agent_payload.get("role"), "profile": agent_payload,
                                      "source_path": agent_rel, "type_id": typedef.id},
                                     raw_ref=agent_source["source_id"], adapter="agent-profile")
                    self.inventory["agents"].append(agent_id)
                    agent_refs.append(agent_id)
                    agent_source_refs.append(agent_source["source_id"])
                    role_name = agent_payload.get("role")
                    if role_name:
                        role_id = "role:%s" % role_name
                        if not any(item.get("entity_id") == role_id for item in self.entities):
                            self._add_entity(role_id, "role", "agents", "read", [agent_source["source_id"]],
                                             {"name": role_name, "role": role_name,
                                              "source_path": agent_rel,
                                              "declared_by": agent_id},
                                             raw_ref=agent_source["source_id"], adapter="agent-role")
                            self.inventory["roles"].append(role_id)
            normalized = {"id": typedef.id, "name": typedef.name, "class": typedef.klass,
                          "gates": typedef.gates, "fields": typedef.fields,
                          "capabilities": typedef.capabilities, "checks": typedef.checks,
                          "editor": typedef.editor, "executor": typedef.executor,
                          "stages": typedef.stages, "profile": typedef.profile,
                          "instruction_path": instruction_rel if instruction_source else None,
                          "instruction_document": instruction_document.get("document_id") if instruction_document else None,
                          "shared_instruction_paths": [ref for ref in sorted(
                              [doc.get("canonical_path") for doc in self.documents
                               if doc.get("canonical_path", "").startswith("types/_shared/")])],
                          "shared_instruction_documents": sorted(shared_documents),
                          "agent_refs": sorted(agent_refs), "agent_source_refs": sorted(agent_source_refs),
                          "source_path": type_rel}
            type_source_refs = [source["source_id"]] if source else []
            if instruction_source:
                type_source_refs.append(instruction_source["source_id"])
            type_source_refs.extend(shared_sources)
            self._add_entity(entity_id, "type", "types", "read", sorted(set(type_source_refs)), normalized,
                             raw_ref=source["source_id"] if source else None, adapter="type")
            self.inventory["types"].append(entity_id)
        flows_root = os.path.join(self.root, "flows")
        project_flows = os.path.join(self.root, ".todone", "flows")
        flow_index = FlowIndex(flows_root, project_flows)
        try:
            flows = flow_index.all()
        except SkillError as exc:
            self.warnings.append(_warning(exc.code, "flows", exc.message, "error"))
            flows = []
        for flow in flows:
            path = os.path.join(flow.folder, "flow.json") if flow.folder else None
            source = self._source_for(_rel(self.root, path)) if path and _within(self.root, path) else None
            entity_id = "flow:%s" % flow.id
            flow_rel = _rel(self.root, path).replace(os.sep, "/") if path and _within(self.root, path) else None
            instruction_path = None
            instruction_source = None
            if flow.folder:
                candidate = flow.instruction_path()
                if _within(self.root, candidate) and os.path.isfile(candidate):
                    instruction_path = _rel(self.root, candidate).replace(os.sep, "/")
                    instruction_source = self._source_for(instruction_path) or self._add_source(
                        candidate, domain="flows", adapter="flow-instruction")
            persisted = [entity["entity_id"] for entity in self.entities
                         if entity.get("kind") == "flow_state"
                         and ((entity.get("normalized") or {}).get("index_row") or {}).get("flow") == flow.id]
            normalized = {"id": flow.id, "name": flow.name, "schema": flow.schema,
                          "version": flow.version, "entry": flow.entry,
                          "max_batch": flow.max_batch, "capabilities": flow.capabilities,
                          "allowlist": flow.allowlist, "presets": flow.presets,
                          "entry_selection": flow.entry_selection, "choice": flow.choice,
                          "decision_tree": flow.decision_tree, "steps": [],
                          "step_refs": [], "transitions": flow.transitions, "policy": flow.policy,
                          "persisted_state_refs": sorted(persisted),
                          "instruction_path": instruction_path,
                          "source_path": flow_rel}
            self._add_entity(entity_id, "flow", "flows", "read",
                             sorted(set(([source["source_id"]] if source else []) +
                                        ([instruction_source["source_id"]] if instruction_source else []))),
                             normalized, raw_ref=source["source_id"] if source else None,
                             revision=flow.version, adapter="flow")
            self.inventory["flows"].append(entity_id)
            step_ids = set(flow.step_ids())
            for step in flow.steps:
                step_entity_id = "flow_step:%s:%s" % (flow.id, step.id)
                step_source_refs = [ref for ref in (source, instruction_source) if ref]
                self._add_entity(
                    step_entity_id, "flow_step", "flows", "read",
                    sorted(set(ref["source_id"] for ref in step_source_refs)),
                    {"id": step.id, "flow_id": flow.id, "flow_ref": entity_id,
                     "type": step.type, "position": step.position,
                     "executor": step.executor, "input_from": step.input_from,
                     "output": step.output, "brief": step.brief,
                     "optional": step.optional, "parallel": step.parallel,
                     "fan_out": step.fan_out, "step_control": step.step_control,
                     "documentation": step.documentation, "gate_out": step.gate_out,
                     "routes": step.routes, "decision_tree": step.decision_tree,
                     "source_path": flow_rel},
                    raw_ref=source["source_id"] if source else None, adapter="flow-step")
                self.inventory["flow_steps"].append(step_entity_id)
                normalized["step_refs"].append(step_entity_id)
                normalized["steps"].append(dict(step.data, position=step.position,
                                                 entity_id=step_entity_id))
            nodes = []
            edges = []
            for step in flow.steps:
                flags = []
                if step.optional:
                    flags.append("optional")
                if step.parallel:
                    flags.append("parallel")
                if step.fan_out:
                    flags.append("fan-out")
                if step.step_control:
                    flags.append("control")
                if step.gate_out:
                    flags.append("gate:%s" % step.gate_out)
                nodes.append({"node_id": "%s:%s" % (flow.id, step.id),
                              "label": step.id, "kind": "step", "flags": flags,
                              "data": {"type": step.type, "input_from": step.input_from,
                                       "output": step.output, "routes": step.routes,
                                       "decision_tree": step.decision_tree,
                                       "requires": step.requires, "fan_out": step.fan_out,
                                       "step_control": step.step_control,
                                       "optional": step.optional, "parallel": step.parallel,
                                       "gate_out": step.gate_out}})
                for prerequisite in step.input_from:
                    edges.append({"edge_id": "%s:%s:%s" % (flow.id, prerequisite, step.id),
                                  "from": "%s:%s" % (flow.id, prerequisite),
                                  "to": "%s:%s" % (flow.id, step.id),
                                  "kind": "flows_to", "label": "после"})
                for route, target in _declared_routes(step.data):
                    target_step = target[:-9] if target.endswith(".revision") else target
                    target_node = target_step if target_step in step_ids else target
                    if target in _FLOW_TERMINAL_TARGETS and "%s:%s" % (flow.id, target) not in {
                            item.get("node_id") for item in nodes}:
                        nodes.append({"node_id": "%s:%s" % (flow.id, target),
                                      "label": _FLOW_TERMINAL_TARGETS[target],
                                      "kind": "gate", "flags": ["terminal"]})
                    edges.append({"edge_id": "%s:route:%s:%s" % (flow.id, step.id, route),
                                  "from": "%s:%s" % (flow.id, step.id),
                                  "to": "%s:%s" % (flow.id, target_node),
                                  "kind": "route_to", "label": route,
                                  "resolved": target_step in step_ids or target in _FLOW_TERMINAL_TARGETS})
            problem_nodes = []
            problems = []
            for step in flow.steps:
                for route, target in _declared_routes(step.data):
                    target_step = target[:-9] if target.endswith(".revision") else target
                    if (isinstance(target, str) and target_step not in step_ids
                            and target not in _FLOW_TERMINAL_TARGETS):
                        node_id = "%s:%s" % (flow.id, step.id)
                        missing_id = "%s:%s" % (flow.id, target)
                        if not any(item.get("node_id") == missing_id for item in nodes):
                            nodes.append({"node_id": missing_id, "label": "%s (нет шага)" % target,
                                          "kind": "problem", "flags": ["missing route target"],
                                          "problem": True, "data": {"route": route}})
                        problem_nodes.extend((node_id, missing_id))
                        problems.append({"code": "AUTODOC_FLOW_ROUTE_TARGET_MISSING",
                                         "node_id": node_id, "target_node_id": missing_id,
                                         "route": route, "target": target})
            incoming = {step_id: 0 for step_id in step_ids}
            adjacency = defaultdict(list)
            for edge in edges:
                if edge.get("from") in {"%s:%s" % (flow.id, x) for x in step_ids} and edge.get("to") in {"%s:%s" % (flow.id, x) for x in step_ids}:
                    adjacency[edge["from"]].append(edge["to"])
                    incoming[edge["to"].split(":", 1)[-1]] += 1
            roots = sorted(step_ids - {step_id for step_id, count in incoming.items() if count}) or sorted(step_ids)[:1]
            reachable = {"%s:%s" % (flow.id, step_id) for step_id in roots}
            pending = list(sorted(reachable))
            while pending:
                current = pending.pop(0)
                for target in sorted(adjacency.get(current, [])):
                    if target not in reachable:
                        reachable.add(target); pending.append(target)
            for step_id in sorted(step_ids):
                node_id = "%s:%s" % (flow.id, step_id)
                if node_id not in reachable:
                    problem_nodes.append(node_id)
                    problems.append({"code": "AUTODOC_FLOW_UNREACHABLE", "node_id": node_id})
            persisted_state = []
            for state_id in normalized.get("persisted_state_refs") or []:
                state = next((item for item in self.entities if item.get("entity_id") == state_id), None)
                if state:
                    persisted_state.append(state.get("normalized"))
            spec = {"$schema": AUTODOC_DIAGRAM_SCHEMA, "schema": AUTODOC_DIAGRAM_SCHEMA,
                    "diagram_id": "flow:%s" % flow.id, "kind": "flow", "title": flow.name or flow.id,
                    "nodes": nodes, "edges": edges,
                    "legend": ["step", "optional", "parallel", "fan-out", "gate", "problem"],
                    "source_entity_refs": [entity_id], "layout": "stable-list",
                    "persisted_state": persisted_state, "problems": problems,
                    "problem_nodes": sorted(set(problem_nodes))}
            spec["asset_path"] = "assets/diagrams/flow-%s.svg" % _slug(flow.id)
            self.diagrams.append(_prepare_diagram_spec(spec))
        self.inventory["types"] = sorted(set(self.inventory["types"]))
        self.inventory["flows"] = sorted(set(self.inventory["flows"]))

    def _collect_contracts_and_config(self):
        for family, entity_kind in (("schemas", "schema"), ("templates", "template")):
            folder = os.path.join(self.root, family)
            for current, dirs, files in os.walk(folder, topdown=True, followlinks=False) if os.path.isdir(folder) else []:
                dirs[:] = sorted(dirs)
                for name in sorted(files):
                    path = os.path.join(current, name)
                    rel = _rel(self.root, path).replace(os.sep, "/")
                    source = self._source_for(rel) or self._add_source(path, domain=family)
                    entity_id = "%s:%s" % (entity_kind, rel)
                    normalized = {"path": rel, "name": name, "media_type": _media(rel)}
                    payload = None
                    if name.endswith(".json") and source and source.get("raw") is not None:
                        try:
                            payload = json.loads(source["raw"])
                            normalized["payload"] = payload
                        except ValueError:
                            self.warnings.append(_warning("CONTRACT_JSON_INVALID", rel,
                                                          "JSON source is not valid", "error"))
                    technical_id = _schema_identity((payload or {}).get("title") or name)
                    meta = _schema_meta(self.schema_catalog, technical_id,
                                        payload=payload, path=rel)
                    properties = (payload or {}).get("properties") if isinstance(payload, dict) else None
                    normalized.update({"schema_id": technical_id or name,
                                       "title": meta.get("human_name") or technical_id or name,
                                       "description": meta.get("description") or (payload or {}).get("description", "") if isinstance(payload, dict) else "",
                                       "description_source": meta.get("description_source") or (rel if isinstance(payload, dict) and payload.get("description") else None),
                                       "contract_title": (payload or {}).get("title") if isinstance(payload, dict) else None,
                                       "contract_version": technical_id or name,
                                       "required_fields": list((payload or {}).get("required") or []) if isinstance(payload, dict) else [],
                                       "field_names": sorted(properties) if isinstance(properties, dict) else [],
                                       "validators": ["JSON Schema", "runtime registry" if entity_kind == "schema" else "template payload"],
                                       "readers": ["runtime validators", "todone autodoc"],
                                       "source_path": rel})
                    if entity_kind == "template":
                        payload_schema = (payload or {}).get("schema") if isinstance(payload, dict) else None
                        normalized.update({"purpose": "Стартовая форма для создания или заполнения данных проекта.",
                                           "template_fields": sorted((payload or {}).keys()) if isinstance(payload, dict) else [],
                                           "schema_usage": [payload_schema] if payload_schema else [],
                                           "validator_usage": ["валидаторы соответствующего контракта", "CLI/project writers"]})
                    self._add_entity(entity_id, entity_kind, family, "read",
                                     [source["source_id"]] if source else [], normalized,
                                     raw_ref=source["source_id"] if source else None,
                                     adapter="contract")
                    self.inventory[family].append(entity_id)
        # The registry contains enum/key contracts which do not each have a
        # standalone file.  Keep those live names in the bundle as entities,
        # sourced from the runtime registry rather than from stale prose.
        try:
            from .check_cli import SCHEMAS
            registry_source = self._source_for("scripts/tdcore/check_cli.py")
            for name in sorted(SCHEMAS):
                entity_id = "schema:registry:%s" % name
                meta = _schema_meta(self.schema_catalog, name)
                self._add_entity(entity_id, "schema", "contracts", "read",
                                 [registry_source["source_id"]] if registry_source else [],
                                 {"name": name, "schema_id": name,
                                  "title": meta.get("human_name") or name,
                                  "description": meta.get("description") or "",
                                  "description_source": meta.get("description_source"),
                                  "keys": list(SCHEMAS[name]),
                                  "source_path": "scripts/tdcore/check_cli.py"},
                                 raw_ref=registry_source["source_id"] if registry_source else None,
                                 adapter="contract-registry")
                self.inventory["schemas"].append(entity_id)
        except Exception as exc:
            self.warnings.append(_warning("SCHEMA_REGISTRY_UNAVAILABLE", "schemas",
                                          str(exc), "warning"))
        for name, kind, inventory_key in (("roles.json", "role", "roles"),
                                           ("tools.json", "tool", "tools"),
                                           ("documentation.json", "policy", "policies"),
                                           ("docs-policy.json", "policy", "policies")):
            path = os.path.join(self.root, ".todone", name)
            if not os.path.isfile(path):
                continue
            rel = _rel(self.root, path).replace(os.sep, "/")
            source = self._source_for(rel)
            payload = None
            if source and source.get("raw") is not None:
                try:
                    payload = json.loads(source["raw"])
                except ValueError:
                    payload = {"raw_invalid": True}
            values = payload.get(inventory_key, []) if isinstance(payload, dict) else []
            if not values:
                values = [payload] if payload is not None else []
            for index, value in enumerate(values, 1):
                ident = value.get("role") if isinstance(value, dict) else None
                ident = ident or value.get("capability") if isinstance(value, dict) else None
                ident = ident or str(index)
                entity_id = "%s:%s" % (kind, ident)
                self._add_entity(entity_id, kind, "config", "read",
                                 [source["source_id"]] if source else [],
                                 {"path": rel, "value": value},
                                 raw_ref=source["source_id"] if source else None,
                                 adapter="config")
                self.inventory[inventory_key].append(entity_id)
        for key in self.inventory:
            self.inventory[key] = sorted(set(self.inventory[key]))

    def _collect_markdown_diagrams(self, document):
        """Register every closed ``mermaid`` fence as a diagram source.

        Flow projections already have a stable diagram record from ``flow.json``.
        When its owned Markdown block is current, the Markdown source wins; when
        the flow changed since the marker was written, augmentation will refresh
        the projection from the flow spec before the final rebuild.
        """
        markdown = document.get("markdown") or {}
        tokens = markdown.get("tokens") or []
        refs = []
        path = document.get("canonical_path", "")
        for index, token in enumerate(tokens):
            if token.get("kind") != "mermaid" or not token.get("closed"):
                continue
            clean_source, embedded_id = _mermaid_source_without_marker(token.get("text", ""))
            if not clean_source:
                self.warnings.append(_warning("AUTODOC_MERMAID_EMPTY", path,
                                              "пустой Mermaid source block", "warning"))
                continue
            marker = None
            if index > 0 and tokens[index - 1].get("kind") == "generated_marker":
                marker = _autodoc_begin_metadata(tokens[index - 1].get("text"))
            candidate_id = marker.get("diagram_id") if marker else None
            existing = next((item for item in self.diagrams
                             if item.get("diagram_id") == candidate_id), None) if candidate_id else None
            if existing is None and not candidate_id:
                flow_match = re.match(r"^flows/([^/]+)/instruction\.md$", path)
                if flow_match:
                    existing = next((item for item in self.diagrams
                                     if item.get("diagram_id") == "flow:%s" % flow_match.group(1)), None)
            if existing is None:
                diagram_id = _markdown_diagram_id(path, token.get("line"), clean_source)
                title = next((item.get("text") for item in markdown.get("headings") or []
                              if item.get("level") == 1), None) or document.get("doc_key") or "Markdown Mermaid"
                existing = _prepare_diagram_spec({
                    "$schema": AUTODOC_DIAGRAM_SCHEMA, "schema": AUTODOC_DIAGRAM_SCHEMA,
                    "diagram_id": diagram_id, "kind": "markdown", "title": title,
                    "nodes": [], "edges": [], "legend": ["markdown"],
                    "source_entity_refs": [document.get("document_id")], "layout": "markdown",
                    "asset_path": "assets/diagrams/markdown-%s.svg" %
                                  hashlib.sha256(diagram_id.encode("utf-8")).hexdigest()[:20],
                    "source_mode": "markdown", "mermaid_source": clean_source,
                    "source_document_path": path, "source_line": token.get("line"),
                    "source_block_digest": sha256_bytes(clean_source.encode("utf-8")),
                    "source_file_digest": (self.source_by_path.get(path) or {}).get("sha256"),
                })
                self.diagrams.append(existing)
            else:
                # Markdown is the selected source of truth for the current
                # bundle. If a flow projection is stale, augment_markdown uses
                # the preserved projection_source to refresh the owned block
                # before the final rebuild; render_bundle never mixes an old
                # fenced source with a newly generated SVG.
                existing["source_mode"] = "markdown"
                existing["mermaid_source"] = clean_source
                existing["source_document_path"] = path
                existing["source_line"] = token.get("line")
                existing["source_block_digest"] = sha256_bytes(clean_source.encode("utf-8"))
                existing["source_file_digest"] = (self.source_by_path.get(path) or {}).get("sha256")
                existing["source_entity_refs"] = sorted(set(existing.get("source_entity_refs") or []) |
                                                         {document.get("document_id")})
                _prepare_diagram_spec(existing)
            token["diagram_id"] = existing.get("diagram_id")
            token["source_digest"] = existing.get("mermaid_source_digest")
            refs.append(existing.get("diagram_id"))
        markdown["diagram_refs"] = sorted(set(refs))

    def _collect_markdown(self):
        # Every Markdown file, including instruction/reference/type docs, has a
        # source envelope and a page.  Module sidecars remain linked metadata.
        for source in list(self.sources):
            if source.get("media_type") != "text/markdown" or source.get("raw") is None:
                continue
            path = source["canonical_path"]
            markdown = _parse_markdown(source["raw"], path)
            markdown["source_digest"] = source["sha256"]
            rendered, compatibility = render_markdown(markdown, source_path=path)
            markdown["rendered_html"] = rendered
            markdown["compatibility"] = compatibility
            doc_key = posixpath.splitext(path)[0]
            # A module sidecar, if present, provides its revision/key.
            sidecar = self.source_by_path.get(posixpath.join(posixpath.dirname(path),
                                                               posixpath.basename(path)[:-3] + ".module.json"))
            revision = 1
            module = None
            if sidecar and sidecar.get("raw"):
                try:
                    module = json.loads(sidecar["raw"])
                    revision = int(module.get("revision") or 1)
                    doc_key = module.get("doc_key") or doc_key
                except (ValueError, TypeError):
                    self.warnings.append(_warning("DOCUMENT_MODULE_INVALID", sidecar["canonical_path"],
                                                  "module sidecar is not valid JSON", "error"))
            document_id = "doc:%s@r%s" % (doc_key, revision)
            document = {"$schema": AUTODOC_MARKDOWN_SCHEMA, "schema": AUTODOC_MARKDOWN_SCHEMA,
                        "document_id": document_id, "doc_key": doc_key, "revision": revision,
                        "canonical_path": path, "source_ref": source["source_id"],
                        "module": module, "markdown": markdown,
                        "provenance": _provenance(source["source_id"], path, "markdown")}
            self.documents.append(document)
            self._collect_markdown_diagrams(document)
            if not any(item["entity_id"] == document_id for item in self.entities):
                self._add_entity(document_id, "markdown", "documentation", "read",
                                 [source["source_id"]], {"doc_key": doc_key,
                                                           "canonical_path": path,
                                                           "revision": revision},
                                 raw_ref=source["source_id"], revision=revision,
                                 adapter="markdown")
            self.inventory["documents"].append(document_id)
            # Skills are Markdown-backed operational knowledge, not merely loose
            # documents. Keep a first-class entity so type/flow/agent cards can
            # link to the exact skill and its rendered page.
            skill_kind = None
            if path == "SKILL.md":
                skill_kind = "root"
            elif path.startswith("child-skills/") and path.endswith(".md"):
                skill_kind = path[:-3]
            if skill_kind:
                skill_id = "skill:%s" % skill_kind
                title = _doc_summary(document)
                self._add_entity(skill_id, "skill", "skills", "read", [source["source_id"]],
                                 {"id": skill_id, "name": title, "path": path,
                                  "document_id": document_id, "source_path": path,
                                  "parent_skill": "skill:root" if skill_kind != "root" else None},
                                 raw_ref=source["source_id"], revision=revision,
                                 adapter="skill")
                self.inventory["skills"].append(skill_id)
        self.inventory["documents"] = sorted(set(self.inventory["documents"]))
        self.inventory["skills"] = sorted(set(self.inventory["skills"]))

    def _link_canonical_entities(self):
        """Materialise deterministic cross-family links after all adapters ran."""
        by_id = {item.get("entity_id"): item for item in self.entities}
        docs_by_path = {item.get("canonical_path"): item for item in self.documents}
        docs_by_id = {item.get("document_id"): item for item in self.documents}
        skills = [item for item in self.entities if item.get("kind") == "skill"]
        root_skill = by_id.get("skill:root")

        def add(relation_id, source, target, kind, source_refs=None):
            if source not in by_id or target not in by_id or source == target:
                return
            self.relations.append(_relation(relation_id, source, target, kind, "resolved", source_refs or []))

        # The entity page owns the readable document but the canonical source
        # remains independently addressable.
        for entity in list(self.entities):
            normalized = entity.get("normalized") or {}
            if entity.get("kind") == "type":
                type_id = normalized.get("id") or entity["entity_id"].split(":", 1)[-1]
                instruction_path = normalized.get("instruction_path") or "types/%s/instruction.md" % type_id
                document = docs_by_path.get(instruction_path)
                if document:
                    normalized["instruction_document"] = document.get("document_id")
                    add("documents:%s:%s" % (entity["entity_id"], document["document_id"]),
                        entity["entity_id"], document.get("document_id"), "documents", entity.get("source_refs"))
                shared_docs = [doc for path, doc in docs_by_path.items()
                               if str(path).startswith("types/_shared/")]
                normalized["shared_instruction_paths"] = sorted(doc.get("canonical_path") for doc in shared_docs)
                normalized["shared_instruction_documents"] = sorted(doc.get("document_id") for doc in shared_docs)
                for doc in shared_docs:
                    add("shared:%s:%s" % (entity["entity_id"], doc["document_id"]),
                        entity["entity_id"], doc.get("document_id"), "uses", entity.get("source_refs"))
                for agent in self.entities:
                    if agent.get("kind") == "agent" and (agent.get("normalized") or {}).get("type_id") == type_id:
                        normalized.setdefault("agent_refs", []).append(agent["entity_id"])
                        add("agent:%s:%s" % (entity["entity_id"], agent["entity_id"]),
                            entity["entity_id"], agent["entity_id"], "uses", agent.get("source_refs"))
                normalized["agent_refs"] = sorted(set(normalized.get("agent_refs") or []))
                for schema in self.entities:
                    if schema.get("kind") != "schema":
                        continue
                    schema_id = str((schema.get("normalized") or {}).get("schema_id") or "")
                    if schema_id in {"TASK", "TYPE", "FIELD", "CHECK", "AGENT", "RETURN_CONTRACT"}:
                        add("type-schema:%s:%s" % (entity["entity_id"], schema["entity_id"]),
                            entity["entity_id"], schema["entity_id"], "uses", entity.get("source_refs"))
                if root_skill:
                    add("skill:type:%s" % type_id, entity["entity_id"], root_skill["entity_id"], "uses", entity.get("source_refs"))
            elif entity.get("kind") == "flow":
                flow_id = normalized.get("id") or entity["entity_id"].split(":", 1)[-1]
                instruction_path = normalized.get("instruction_path") or "flows/%s/instruction.md" % flow_id
                document = docs_by_path.get(instruction_path)
                if document:
                    normalized["instruction_document"] = document.get("document_id")
                    add("documents:%s:%s" % (entity["entity_id"], document["document_id"]),
                        entity["entity_id"], document.get("document_id"), "documents", entity.get("source_refs"))
                for step_ref in normalized.get("step_refs") or []:
                    step = by_id.get(step_ref)
                    if not step:
                        continue
                    add("contains:%s:%s" % (entity["entity_id"], step_ref), entity["entity_id"], step_ref,
                        "contains", entity.get("source_refs"))
                    step_data = step.get("normalized") or {}
                    step_type = by_id.get("type:%s" % step_data.get("type"))
                    if step_type:
                        add("step-type:%s:%s" % (step_ref, step_type["entity_id"]), step_ref,
                            step_type["entity_id"], "implements", step.get("source_refs"))
                    executor = step_data.get("executor") or {}
                    role = executor.get("role") if isinstance(executor, dict) else None
                    if role:
                        role_entity = by_id.get("role:%s" % role)
                        if role_entity:
                            add("step-role:%s:%s" % (step_ref, role_entity["entity_id"]), step_ref,
                                role_entity["entity_id"], "uses", step.get("source_refs"))
                        matching_agents = [agent for agent in self.entities if agent.get("kind") == "agent"
                                           and (agent.get("normalized") or {}).get("role") == role]
                        for agent in matching_agents:
                            add("step-agent:%s:%s" % (step_ref, agent["entity_id"]), step_ref,
                                agent["entity_id"], "uses", step.get("source_refs"))
                    if step_data.get("type"):
                        normalized.setdefault("task_types", []).append(step_data.get("type"))
                normalized["task_types"] = sorted(set(normalized.get("task_types") or []))
                for schema in self.entities:
                    if schema.get("kind") != "schema":
                        continue
                    schema_id = str((schema.get("normalized") or {}).get("schema_id") or "")
                    if schema_id in {"FLOW", "STEP", "FLOW_DOC", "FLOW_CHOICE", "FLOW_STEP_CONTROL", "FLOW_TRANSITION"}:
                        add("flow-schema:%s:%s" % (entity["entity_id"], schema["entity_id"]),
                            entity["entity_id"], schema["entity_id"], "uses", entity.get("source_refs"))
                if root_skill:
                    add("skill:flow:%s" % flow_id, entity["entity_id"], root_skill["entity_id"], "uses", entity.get("source_refs"))
            elif entity.get("kind") == "agent":
                role = normalized.get("role")
                if role:
                    add("agent-role:%s:%s" % (entity["entity_id"], role), entity["entity_id"],
                        "role:%s" % role, "implements", entity.get("source_refs"))
            elif entity.get("kind") == "skill":
                parent = normalized.get("parent_skill")
                if parent:
                    add("contains:%s:%s" % (parent, entity["entity_id"]), parent, entity["entity_id"],
                        "contains", entity.get("source_refs"))

        # Templates and schemas are related by the explicit schema/template
        # fields when present, and by a deterministic reference scan otherwise.
        schema_entities = [item for item in self.entities if item.get("kind") == "schema"]
        template_entities = [item for item in self.entities if item.get("kind") == "template"]
        for template in template_entities:
            template_normalized = template.get("normalized") or {}
            payload = template_normalized.get("payload") or {}
            text = _json_dumps(payload)
            refs = []
            declared_schema = template_normalized.get("schema_usage") or []
            for schema in schema_entities:
                schema_n = schema.get("normalized") or {}
                schema_id = str(schema_n.get("schema_id") or "")
                schema_title = str(schema_n.get("contract_title") or "")
                if (schema_id and (schema_id.lower() in text.lower() or
                                   any(str(item).lower() == schema_id.lower() for item in declared_schema))) or \
                        (schema_title and schema_title.lower() in text.lower()):
                    refs.append(schema["entity_id"])
                    add("template-schema:%s:%s" % (template["entity_id"], schema["entity_id"]),
                        template["entity_id"], schema["entity_id"], "uses", template.get("source_refs"))
            template_normalized["schema_refs"] = sorted(refs)
            # Every template is a first-class starter payload; connect it to the
            # type/flow families it names or visibly resembles.
            for target in self.entities:
                if target.get("kind") not in ("type", "flow"):
                    continue
                ident = target["entity_id"].split(":", 1)[-1]
                payload_kind = payload.get("kind") if isinstance(payload, dict) else None
                if (str(payload_kind).lower() == ident.lower() or
                        ident.lower() in template["entity_id"].lower() or ident.lower() in text.lower()):
                    add("template-usage:%s:%s" % (template["entity_id"], target["entity_id"]),
                        target["entity_id"], template["entity_id"], "uses", target.get("source_refs"))
        # Keep the relation list deterministic and duplicate-free even when a
        # source is referenced by multiple adapters.
        unique = {}
        for relation in self.relations:
            unique[relation["relation_id"]] = relation
        self.relations = [unique[key] for key in sorted(unique)]

    def _ensure_source_file_entities(self):
        """Give every canonical file a readable, linked fallback page contract."""
        existing = {item.get("entity_id") for item in self.entities}
        for source in sorted(self.sources, key=lambda item: item.get("canonical_path", "")):
            if source.get("external") or source.get("generated") or not source.get("source_of_truth"):
                continue
            path = source.get("canonical_path") or ""
            entity_id = "source_file:%s" % path
            if entity_id in existing:
                continue
            related = [entity["entity_id"] for entity in self.entities
                       if source.get("source_id") in (entity.get("source_refs") or [])]
            normalized = {"path": path, "name": posixpath.basename(path),
                          "media_type": source.get("media_type"),
                          "domain": source.get("source_domain"),
                          "byte_size": source.get("byte_size"),
                          "adapted_entity_refs": sorted(set(related)),
                          "source_path": path}
            self._add_entity(entity_id, "source_file", "sources", "read",
                             [source["source_id"]], normalized,
                             raw_ref=source["source_id"], adapter="source-file")
            self.inventory["source_files"].append(entity_id)
            existing.add(entity_id)
            for target in related:
                self.relations.append(_relation("source-of:%s:%s" % (entity_id, target),
                                                 entity_id, target, "source_of", "resolved",
                                                 [source["source_id"]]))
        unique = {relation["relation_id"]: relation for relation in self.relations}
        self.relations = [unique[key] for key in sorted(unique)]

    def _legacy(self):
        if not self.legacy_root:
            return None
        legacy = self.legacy_root
        files = {}
        for rel in ("build.py", "content.py", "README.md", "site/facts-v07.json", "site/index.html"):
            path = os.path.join(legacy, rel)
            if os.path.isfile(path):
                record = self._add_source(path, domain="legacy-preza", external=True,
                                          portable_path="external/preza/" + rel,
                                          source_of_truth=False,
                                          generated=rel.startswith("site/"), adapter="preza")
                if record:
                    files[rel] = record
        sections = [
            ("start", "build.py", "index.html", "transformed"),
            ("architecture", "build.py", "architecture/index.html", "transformed"),
            ("entities", "content.py", "entities/index.html", "preserved"),
            ("lifecycle", "content.py", "index.html#lifecycle", "preserved"),
            ("commands", "build.py", "commands/index.html", "transformed"),
            ("types", "build.py", "types/index.html", "transformed"),
            ("flows", "build.py", "flows/index.html", "transformed"),
            ("schemas", "content.py", "schemas/index.html", "preserved"),
            ("templates", "build.py", "schemas/index.html#templates", "transformed"),
            ("file-catalog", "build.py", "sources/index.html", "transformed"),
            ("checks", "build.py", "audit/index.html", "transformed"),
            ("faq", "content.py", "index.html#faq", "preserved"),
            ("live-facts", "site/facts-v07.json", "audit/index.html#legacy-facts", "unknown"),
            ("footer", "build.py", "index.html#footer", "preserved"),
        ]
        entries = []
        for ident, rel, target, status in sections:
            record = files.get(rel)
            digest = record["sha256"] if record else None
            entries.append({"id": ident, "source": "external/preza/" + rel,
                            "content_digest": digest, "target_page": target,
                            "status": status if record else "unknown",
                            "source_refs": [record["source_id"]] if record else []})
        assets = []
        build = files.get("build.py")
        if build and build.get("raw"):
            match = re.search(r"(<svg\b.*?</svg>)", build["raw"], re.I | re.S)
            if match:
                svg_text = match.group(1)
                opening = re.search(r"<svg\b[^>]*>", svg_text, re.I | re.S)
                if opening:
                    tag = opening.group(0)
                    if not re.search(r"\brole=[\"']img[\"']", tag, re.I):
                        tag = tag[:-1] + ' role="img"'
                    if "aria-labelledby=" not in tag and "aria-label=" not in tag:
                        tag = tag[:-1] + ' aria-labelledby="title desc"'
                    svg_text = svg_text[:opening.start()] + tag + svg_text[opening.end():]
                    if not re.search(r"<title\b", svg_text, re.I):
                        svg_text = svg_text.replace(tag, tag +
                            '<title id="title">Legacy todone architecture</title>'
                            '<desc id="desc">Offline legacy architecture projection.</desc>', 1)
                data = svg_text.encode("utf-8")
                record = _source_record("external/preza/legacy-architecture.svg", data,
                                        root=self.root, domain="legacy-preza", external=True,
                                        source_of_truth=False, generated=True, archive=True,
                                        adapter="preza-svg")
                self.sources.append(record)
                self.source_by_path[record["canonical_path"]] = record
                assets.append({"id": "legacy-architecture-svg", "digest": record["sha256"],
                               "target": "assets/diagrams/legacy-architecture.svg",
                               "status": "transformed", "source_refs": [record["source_id"]]})

        def literal(name, rel="content.py"):
            source = files.get(rel)
            if not source or not source.get("raw"):
                return None
            try:
                tree = ast.parse(source["raw"], filename=rel)
                for node in tree.body:
                    if isinstance(node, (ast.Assign, ast.AnnAssign)):
                        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                        if any(getattr(target, "id", None) == name for target in targets):
                            return ast.literal_eval(node.value)
            except (SyntaxError, ValueError, TypeError):
                return None
            return None

        def item(source_rel, ident, value, target, status="transformed"):
            source = files.get(source_rel)
            source_ref = source["source_id"] if source else None
            digest = sha256_bytes(canonical_bytes({"source": source_rel, "id": ident, "value": value}))
            return {"id": ident, "source": "external/preza/" + source_rel,
                    "content_digest": digest, "target_page": target,
                    "status": status if source else "unknown",
                    "source_refs": [source_ref] if source_ref else [],
                    "value": value}

        # The category rows above preserve page-level migration.  This nested
        # inventory preserves every curated/live item so parity cannot pass by
        # merely keeping one section heading.
        migration_inventory = {}
        curated = (("entity_sections", "ENTITY_SECTIONS", "content.py", "entities/index.html", "preserved"),
                   ("lifecycle", "LIFECYCLE", "content.py", "index.html#lifecycle", "preserved"),
                   ("schema_notes", "SCHEMA_NOTES", "content.py", "schemas/index.html", "preserved"),
                   ("faq", "FAQ", "content.py", "index.html#faq", "preserved"),
                   ("command_notes", "COMMAND_NOTES", "content.py", "commands/index.html", "preserved"),
                   ("file_overrides", "FILE_OVERRIDES", "content.py", "sources/index.html", "preserved"))
        for key, variable, source_rel, target, status in curated:
            value = literal(variable, source_rel)
            values = value if isinstance(value, (list, tuple)) else list(value.items()) if isinstance(value, dict) else []
            migration_inventory[key] = [item(source_rel, "%s:%s" % (key, index + 1), entry, target, status)
                                        for index, entry in enumerate(values)]

        # Live lists are taken from the current runtime when available.  They
        # are migration evidence, not a replacement for current bundle facts.
        try:
            from .check_cli import CheckCli
            from .queue_cli import QueueCli
            from .task_cli import TaskCli
            command_items = []
            for cli_class in (QueueCli, TaskCli, CheckCli):
                for command in cli_class.commands:
                    command_items.append((cli_class.entry, command.name, command.summary,
                                          command.nested))
        except Exception:
            command_items = []
        migration_inventory["commands"] = [
            item("build.py", "%s.%s" % (entry, name),
                 {"entry": entry, "summary": summary, "nested": list(nested)},
                 "commands/index.html#%s" % _slug("%s-%s" % (entry, name)))
            for entry, name, summary, nested in command_items]
        migration_inventory["types"] = [
            item("build.py", "type:%s" % entity["entity_id"].split(":", 1)[-1],
                 entity.get("normalized", {}), "types/index.html#%s" % _slug(entity["entity_id"]))
            for entity in self.entities if entity.get("kind") == "type"]
        migration_inventory["flows"] = [
            item("build.py", "flow:%s" % entity["entity_id"].split(":", 1)[-1],
                 entity.get("normalized", {}), "flows/index.html#%s" % _slug(entity["entity_id"]))
            for entity in self.entities if entity.get("kind") == "flow"]
        schema_values = []
        for source in self.sources:
            path = source.get("canonical_path", "")
            if path.startswith("schemas/"):
                schema_values.append((path, {"path": path, "sha256": source.get("sha256")}))
        migration_inventory["schemas"] = [item("build.py", "schema:%s" % path, value,
                                                 "schemas/index.html#%s" % _slug(path))
                                          for path, value in sorted(schema_values)]
        template_values = [(source.get("canonical_path"), {"path": source.get("canonical_path"),
                                                            "sha256": source.get("sha256")})
                           for source in self.sources if source.get("canonical_path", "").startswith("templates/")]
        migration_inventory["templates"] = [item("build.py", "template:%s" % path, value,
                                                   "schemas/index.html#%s" % _slug(path))
                                            for path, value in sorted(template_values)]
        migration_inventory["file_notes"] = [
            {"id": "file:%s" % source.get("canonical_path"), "source": source.get("canonical_path"),
             "content_digest": source.get("sha256"), "target_page": "sources/index.html#%s" % _slug(source.get("canonical_path")),
             "status": "transformed", "source_refs": [source.get("source_id")],
             "value": {"media_type": source.get("media_type"), "classification": source.get("classification")}}
            for source in self.sources if not source.get("external")]
        facts = {}
        baseline = files.get("site/facts-v07.json")
        if baseline and baseline.get("raw"):
            try:
                facts = json.loads(baseline["raw"])
            except ValueError:
                facts = {}
        migration_inventory["checks"] = [item("site/facts-v07.json", "check:%s" % key,
                                                 {"fact": facts.get(key)}, "audit/index.html#checks", "transformed")
                                         for key in ("selftest", "doctor", "tests")]
        migration_inventory["live_facts"] = [item("site/facts-v07.json", "fact:%s" % key,
                                                     value, "audit/index.html#legacy-facts", "unknown")
                                              for key, value in sorted(facts.items())]
        migration_inventory["svg"] = [item("build.py", asset.get("id"), asset,
                                            asset.get("target", "architecture/index.html"), "transformed")
                                      for asset in assets]
        # A missing legacy source is itself parity evidence.  Keep one explicit
        # unknown row per required family instead of silently emitting an empty
        # list that could look like a successful migration.
        fallback_targets = {
            "entity_sections": ("content.py", "entities/index.html"),
            "lifecycle": ("content.py", "index.html#lifecycle"),
            "schema_notes": ("content.py", "schemas/index.html"),
            "faq": ("content.py", "index.html#faq"),
            "command_notes": ("content.py", "commands/index.html"),
            "file_overrides": ("content.py", "sources/index.html"),
            "commands": ("build.py", "commands/index.html"),
            "types": ("build.py", "types/index.html"),
            "flows": ("build.py", "flows/index.html"),
            "schemas": ("build.py", "schemas/index.html"),
            "templates": ("build.py", "schemas/index.html#templates"),
            "file_notes": ("build.py", "sources/index.html"),
            "checks": ("site/facts-v07.json", "audit/index.html#checks"),
            "live_facts": ("site/facts-v07.json", "audit/index.html#legacy-facts"),
            "svg": ("build.py", "architecture/index.html"),
        }
        for category in PREZA_PARITY_CATEGORIES:
            if migration_inventory.get(category):
                continue
            source_rel, target = fallback_targets[category]
            migration_inventory[category] = [{
                "id": "%s:unknown" % category,
                "source": "external/preza/" + source_rel,
                "content_digest": None,
                "target_page": target,
                "status": "unknown",
                "source_refs": [],
                "value": {"reason": "legacy source or adapter unavailable"},
            }]
        if not assets:
            assets = [{"id": "legacy-architecture-svg", "digest": None,
                       "target": "assets/diagrams/legacy-architecture.svg",
                       "status": "unknown", "source_refs": []}]
        parity = {"$schema": PREZA_PARITY_SCHEMA, "schema": PREZA_PARITY_SCHEMA,
                  "legacy_root": "external/preza",
                  "legacy_output": "external/preza/site/index.html",
                  "sections": entries, "assets": assets,
                  "inventory": migration_inventory}
        return {"$schema": AUTODOC_PREZA_SCHEMA, "schema": AUTODOC_PREZA_SCHEMA,
                "legacy_root": "external/preza",
                "legacy_output": "external/preza/site/index.html", "sections": entries,
                "assets": assets, "inventory": migration_inventory, "parity": parity,
                "facts_baseline": {"path": "external/preza/site/facts-v07.json",
                                    "digest": files.get("site/facts-v07.json", {}).get("sha256")
                                    if files.get("site/facts-v07.json") else None}}

    def _build_diagrams(self):
        """Create only AUTODOC-DIAGRAM-1 data; Mermaid renders the SVG later."""
        def add(spec):
            self.diagrams.append(_prepare_diagram_spec(spec))

        task_entities = [item for item in self.entities if item.get("kind") == "task"]
        task_pages = _entity_page_map({"entities": self.entities})
        task_nodes = [{"node_id": item["entity_id"],
                       "label": (item.get("normalized") or {}).get("title") or item["entity_id"].split(":")[-1],
                       "kind": "task", "flags": [],
                       "href": "../" + task_pages.get(item["entity_id"], "tasks/index.html")}
                      for item in sorted(task_entities, key=lambda item: item.get("entity_id", ""))]
        task_edges = [{"edge_id": item["relation_id"], "from": item["from"], "to": item["to"],
                       "kind": item["kind"], "label": item["kind"],
                       "resolved": item.get("resolution") == "resolved",
                       "resolution": item.get("resolution")}
                      for item in sorted(self.relations, key=lambda item: item.get("relation_id", ""))
                      if item.get("kind") in ("depends_on", "parent", "blocks")]
        add({"$schema": AUTODOC_DIAGRAM_SCHEMA, "schema": AUTODOC_DIAGRAM_SCHEMA,
             "diagram_id": "task-relations", "kind": "relations", "title": "Задачи и зависимости",
             "nodes": task_nodes, "edges": task_edges, "legend": ["task", "problem", "unresolved"],
             "source_entity_refs": [item["entity_id"] for item in task_entities],
             "layout": "stable-list", "asset_path": "assets/diagrams/task-relations.svg"})

        # The portable bundle keeps every relation, but a single Mermaid canvas
        # must remain legible and within Mermaid's text-size limit. Project the
        # relation view to human-facing domain entities; source-file fan-out and
        # registry noise stay available on entity cards and graph.json.
        relation_entity_kinds = {"type", "flow", "template", "schema", "skill",
                                 "agent", "role", "flow_step"}
        relation_kinds_for_diagram = {"contains", "implements", "uses", "documents"}
        candidate_relations = [item for item in sorted(self.relations, key=lambda item: item.get("relation_id", ""))
                               if item.get("kind") in relation_kinds_for_diagram
                               and item.get("from") in {entity.get("entity_id") for entity in self.entities
                                                         if entity.get("kind") in relation_entity_kinds}
                               and item.get("to") in {entity.get("entity_id") for entity in self.entities
                                                       if entity.get("kind") in relation_entity_kinds}]
        relation_edges = candidate_relations[:160]
        relation_refs = set()
        for relation in relation_edges:
            relation_refs.update(item for item in (relation.get("from"), relation.get("to")) if item)
        relation_nodes = []
        entity_by_id = {item.get("entity_id"): item for item in self.entities}
        entity_pages = _entity_page_map({"entities": self.entities})
        for endpoint in sorted(relation_refs):
            entity = entity_by_id.get(endpoint) or {}
            relation_nodes.append({"node_id": endpoint,
                                   "label": (entity.get("normalized") or {}).get("title") or
                                            (entity.get("normalized") or {}).get("name") or endpoint,
                                   "kind": entity.get("kind", "entity"), "flags": [],
                                   "href": "../" + entity_pages.get(endpoint, "entities/index.html")})
        if not relation_nodes:
            relation_nodes = [{"node_id": "relations:empty",
                               "label": "Нет связей",
                               "kind": "empty", "flags": []}]
        relation_edges = [{"edge_id": item["relation_id"], "from": item["from"], "to": item["to"],
                           "kind": item.get("kind"), "label": _ru_kind(item.get("kind", "relation")),
                           "resolved": item.get("resolution") == "resolved",
                           "resolution": item.get("resolution")}
                          for item in relation_edges]
        add({"$schema": AUTODOC_DIAGRAM_SCHEMA, "schema": AUTODOC_DIAGRAM_SCHEMA,
             "diagram_id": "entity-relations", "kind": "relations", "title": "Связи сущностей и файлов",
             "nodes": relation_nodes, "edges": relation_edges,
             "legend": ["entity", "relation", "unresolved"],
             "source_entity_refs": sorted(set(relation_refs) |
                                           {item["entity_id"] for item in self.entities}),
             "layout": "stable-list", "asset_path": "assets/diagrams/entity-relations.svg"})

        # Architecture is a compact map of the live bundle families. It avoids
        # hiding 170 individual records in one unreadable canvas while retaining
        # every entity as provenance in source_entity_refs.
        family_labels = {"workspace": "Проект", "markdown": "Документация",
                         "document": "Документация", "flow": "Потоки",
                         "type": "Профили задач", "schema": "Схемы",
                         "template": "Шаблоны", "task": "Задачи"}
        family_counts = defaultdict(int)
        for entity in self.entities:
            family_counts[entity.get("kind", "unknown")] += 1
        # Architecture is a real layered pipeline, not a flat inventory. The
        # detailed family counts remain available in the bundle/provenance
        # pages; this projection answers the human question "how does source
        # material become an offline catalog?" from top to bottom.
        source_count = len([source for source in self.sources if not source.get("generated")])
        adapter_count = len(set((entity.get("provenance") or [{}])[0].get("adapter")
                                for entity in self.entities if (entity.get("provenance") or [{}])[0].get("adapter")))
        root_id = "architecture:bundle"
        source_layer = "architecture:source-layer"
        adapter_layer = "architecture:adapter-layer"
        entity_layer = "architecture:entity-layer"
        relation_layer = "architecture:relation-layer"
        output_layer = "architecture:output-layer"
        architecture_nodes = [
            {"node_id": root_id, "label": "AUTODOC bundle", "kind": "component", "flags": ["gate"],
             "href": "../index.html"},
            {"node_id": source_layer, "label": "Канонические источники · %d" % source_count,
             "kind": "source", "flags": [], "href": "../sources/index.html"},
            {"node_id": adapter_layer, "label": "Source adapters · %d" % adapter_count,
             "kind": "component", "flags": [], "href": "../entities/index.html"},
            {"node_id": entity_layer, "label": "Нормализованные entities · %d" % len(self.entities),
             "kind": "entity", "flags": [], "href": "../entities/index.html"},
            {"node_id": relation_layer, "label": "Relations · %d" % len(self.relations),
             "kind": "relation", "flags": [], "href": "../entities/index.html"},
            {"node_id": output_layer, "label": "Offline HTML · Mermaid %s" % MERMAID_VERSION,
             "kind": "component", "flags": ["gate"], "href": "../index.html"},
        ]
        architecture_edges = [
            {"edge_id": "architecture:collect", "from": root_id, "to": source_layer,
             "kind": "contains", "label": "собирает", "resolved": True},
            {"edge_id": "architecture:adapt", "from": source_layer, "to": adapter_layer,
             "kind": "uses", "label": "читает", "resolved": True},
            {"edge_id": "architecture:normalize", "from": adapter_layer, "to": entity_layer,
             "kind": "generated_from", "label": "нормализует", "resolved": True},
            {"edge_id": "architecture:relate", "from": entity_layer, "to": relation_layer,
             "kind": "contains", "label": "связывает", "resolved": True},
            {"edge_id": "architecture:render", "from": relation_layer, "to": output_layer,
             "kind": "produces", "label": "рендерит", "resolved": True},
        ]
        add({"$schema": AUTODOC_DIAGRAM_SCHEMA, "schema": AUTODOC_DIAGRAM_SCHEMA,
             "diagram_id": "architecture", "kind": "architecture", "title": "Архитектура offline-каталога",
             "nodes": architecture_nodes, "edges": architecture_edges,
             "legend": ["component", "gate", "source", "entity", "relation"],
             "source_entity_refs": sorted(item["entity_id"] for item in self.entities),
             "layout": "hierarchy", "asset_path": "assets/diagrams/architecture.svg"})

        # A provenance/timeline projection connects source domains to the
        # normalized entity families. It is intentionally deterministic and
        # remains useful even when no task relations were discovered.
        source_domains = defaultdict(int)
        source_domain_by_id = {}
        for source in self.sources:
            domain = source.get("source_domain") or "workspace"
            source_domains[domain] += 1
            source_domain_by_id[source.get("source_id")] = domain
        # Do not draw an artificial complete bipartite graph. Connect a source
        # domain to an entity family only when an entity actually references a
        # source in that domain, and put the real aggregate count on the edge.
        domain_kind_counts = defaultdict(int)
        for entity in self.entities:
            kind = entity.get("kind", "unknown")
            for source_ref in set(entity.get("source_refs") or []):
                domain = source_domain_by_id.get(source_ref)
                if domain:
                    domain_kind_counts[(domain, kind)] += 1
        prov_nodes = [{"node_id": "provenance:source:%s" % domain,
                       "label": "%s · %d" % (domain, count),
                       "kind": "source", "flags": [],
                       "href": "#source-table"}
                      for domain, count in sorted(source_domains.items())]
        for kind, count in sorted(family_counts.items()):
            prov_nodes.append({"node_id": "provenance:entity:%s" % kind,
                               "label": "%s · %d" % (family_labels.get(kind, _ru_kind(kind)), count),
                               "kind": "entity", "flags": [],
                               "href": "../entities/index.html"})
        prov_edges = []
        for (domain, kind), count in sorted(domain_kind_counts.items()):
            prov_edges.append({"edge_id": "provenance:%s:%s" % (domain, kind),
                               "from": "provenance:source:%s" % domain,
                               "to": "provenance:entity:%s" % kind,
                               "kind": "generated_from", "label": "%d сущ." % count,
                               "resolved": True})
        add({"$schema": AUTODOC_DIAGRAM_SCHEMA, "schema": AUTODOC_DIAGRAM_SCHEMA,
             "diagram_id": "provenance-timeline", "kind": "provenance", "title": "Источники и provenance",
             "nodes": prov_nodes, "edges": prov_edges,
             "legend": ["source", "entity", "generated_from"],
             "source_entity_refs": sorted([item["source_id"] for item in self.sources] +
                                           [item["entity_id"] for item in self.entities]),
             "layout": "timeline", "asset_path": "assets/diagrams/provenance-timeline.svg"})

        # Audit map: known warnings, route problems and an explicit clean state
        # are shown as data; later audit_input findings are rendered alongside it
        # on the audit page without changing the source-of-truth projection.
        audit_nodes = []
        for index, warning in enumerate(sorted(self.warnings, key=lambda item: _json_dumps(item))):
            audit_nodes.append({"node_id": "audit:warning:%d" % index,
                                "label": warning.get("code") or warning.get("message") or "Предупреждение",
                                "kind": "problem", "flags": ["problem"], "problem": True})
        for diagram in sorted(self.diagrams, key=lambda item: item.get("diagram_id", "")):
            for index, problem in enumerate(diagram.get("problems") or []):
                audit_nodes.append({"node_id": "audit:%s:%d" % (diagram["diagram_id"], index),
                                    "label": problem.get("code") or "Проблемный узел",
                                    "kind": "problem", "flags": ["problem"], "problem": True})
        if not audit_nodes:
            audit_nodes.append({"node_id": "audit:clean", "label": "Проверки готовы · замечаний нет",
                                "kind": "status", "flags": ["empty"]})
        audit_root = {"node_id": "audit:root", "label": "Карта контроля", "kind": "component", "flags": ["gate"]}
        audit_edges = [{"edge_id": "audit:root:%s" % node["node_id"], "from": audit_root["node_id"],
                        "to": node["node_id"], "kind": "verifies", "label": "проверяет",
                        "resolved": True} for node in audit_nodes]
        add({"$schema": AUTODOC_DIAGRAM_SCHEMA, "schema": AUTODOC_DIAGRAM_SCHEMA,
             "diagram_id": "audit-map", "kind": "audit", "title": "Карта аудита и gates",
             "nodes": [audit_root] + audit_nodes, "edges": audit_edges,
             "legend": ["gate", "problem", "status"],
             "source_entity_refs": sorted(item["entity_id"] for item in self.entities
                                           if item.get("kind") in {"flow", "task"}),
             "layout": "stable-list", "asset_path": "assets/diagrams/audit-map.svg"})

    def _finalize_diagrams(self):
        _finalize_diagram_assets(self.diagrams)

    def build(self):
        self._inventory_sources()
        aggregate_data = self._load_aggregate()
        self._collect_workspaces(aggregate_data)
        self._collect_aggregate(aggregate_data)
        self._collect_types_flows()
        self._collect_contracts_and_config()
        self._collect_markdown()
        self._link_canonical_entities()
        self._ensure_source_file_entities()
        legacy = self._legacy()
        self._build_diagrams()
        # Stable and explicit relation/source ordering.
        self.sources.sort(key=lambda item: item.get("canonical_path", ""))
        self.entities.sort(key=lambda item: item.get("entity_id", ""))
        unique_relations = {}
        for relation in self.relations:
            unique_relations[relation["relation_id"]] = relation
        self.relations = [unique_relations[key] for key in sorted(unique_relations)]
        self.documents.sort(key=lambda item: item.get("document_id", ""))
        self.diagrams.sort(key=lambda item: item.get("diagram_id", ""))
        # SVG bytes are produced by the pinned local Mermaid adapter. Their
        # digest is recorded in the diagram contract before the bundle digest.
        self._finalize_diagrams()
        # Duplicate source identities are findings, never last-write-wins.
        by_id = defaultdict(list)
        for source in self.sources:
            by_id[source["source_id"]].append(source["canonical_path"])
        # ``source:<sha256>`` is content identity by contract.  Several
        # canonical paths may legitimately have the same bytes (for example,
        # copied instructions); preserve each path/provenance without turning
        # that into a false duplicate-identity error.
        completeness_status = "complete"
        if any(item.get("severity") in ("error", "blocker") for item in self.warnings):
            completeness_status = "blocked"
        elif self.warnings or self.unknowns:
            completeness_status = "partial"
        root_workspace_ids = sorted(item.get("workspace_id") for item in aggregate_data.get("workspaces", [])
                                    if item.get("workspace_id"))
        if not root_workspace_ids:
            root_workspace_ids = [_slug(os.path.basename(self.root), "root")]
        adapted_by_source = defaultdict(list)
        for entity in self.entities:
            if entity.get("kind") == "source_file":
                continue
            for source_ref in entity.get("source_refs") or []:
                adapted_by_source[source_ref].append(entity.get("entity_id"))
        canonical_sources = [item for item in self.sources
                             if item.get("source_of_truth") and not item.get("generated") and not item.get("external")]
        source_file_entities = [item for item in self.entities if item.get("kind") == "source_file"]
        raw_json_only_paths = sorted(source.get("canonical_path") for source in canonical_sources
                                     if source.get("media_type") == "application/json"
                                     and not adapted_by_source.get(source.get("source_id"))
                                     and not source.get("canonical_path", "").startswith(("fixtures/", "examples/")))
        coverage = {"canonical_sources": len(canonical_sources),
                    "source_file_entities": len(source_file_entities),
                    "adapted_sources": sum(1 for source in canonical_sources if adapted_by_source.get(source.get("source_id"))),
                    "fallback_sources": sum(1 for source in canonical_sources if not adapted_by_source.get(source.get("source_id"))),
                    "missing_source_entities": [], "raw_json_only_paths": raw_json_only_paths,
                    "contract": "every canonical source has a source_file entity and a deterministic consolidated provenance record; adapted families add a human view"}
        bundle = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "schema": AUTODOC_BUNDLE_SCHEMA,
            "bundle_id": "autodoc:pending",
            "bundle_revision": 1,
            "generator": {"name": "todone-autodoc", "version": AUTODOC_GENERATOR_VERSION,
                          "source_commit": None},
            "root": {"path": ".", "workspace_ids": root_workspace_ids,
                     "source_policy": "lossless-allowed-redacted",
                     "root_digest_scope": "canonical-files-under-root"},
            "created_at": _now(),
            "canonical_digest": "sha256:pending",
            "completeness": {"status": completeness_status,
                             "unknowns": self.unknowns, "invalid_sources": aggregate_data.get("invalid_sources", []),
                             "coverage": coverage},
            "inventory": {key: sorted(set(value)) for key, value in self.inventory.items()},
            "entities": self.entities,
            "relations": self.relations,
            "sources": self.sources,
            "documents": self.documents,
            "diagrams": self.diagrams,
            "warnings": sorted(self.warnings, key=lambda item: (str(item.get("path", "")),
                                                                  str(item.get("code", "")),
                                                                  str(item.get("message", "")))),
            "unknowns": sorted(self.unknowns, key=lambda item: _json_dumps(item)),
            "audit_input": {"algorithm_version": "audit-local-1", "findings": []},
            "reconstruction": {"$schema": AUTODOC_RECONSTRUCTION_SCHEMA,
                               "schema": AUTODOC_RECONSTRUCTION_SCHEMA,
                               "mode": "byte-identical-allowed-sources",
                               "source_refs": [], "skipped": [], "requires_human": []},
            "outputs": {},
        }
        if legacy:
            bundle["legacy_parity"] = legacy
        # Reconstruction eligibility is explicit and deterministic.
        for source in bundle["sources"]:
            if source.get("external") or source.get("generated") or not source.get("source_of_truth"):
                bundle["reconstruction"]["skipped"].append({"source_ref": source["source_id"],
                                                               "path": source["canonical_path"],
                                                               "reason": "external_or_derived"})
            elif source.get("raw_available"):
                bundle["reconstruction"]["source_refs"].append(source["source_id"])
            else:
                bundle["reconstruction"]["requires_human"].append({"source_ref": source["source_id"],
                                                                       "path": source["canonical_path"],
                                                                       "reason": source.get("redaction", {}).get("reason", "raw_unavailable")})
        bundle["reconstruction"]["source_refs"].sort()
        bundle["reconstruction"]["skipped"].sort(key=lambda item: item["path"])
        bundle["reconstruction"]["requires_human"].sort(key=lambda item: item["path"])
        digest = canonical_digest(bundle)
        bundle["canonical_digest"] = digest
        bundle["bundle_id"] = "autodoc:" + digest.split(":", 1)[1]
        return bundle


def _domain_for(path):
    first = str(path).replace("\\", "/").split("/", 1)[0]
    return {".todone": "todone", "docs": "documentation", "types": "types",
            "flows": "flows", "schemas": "contracts", "templates": "templates",
            "child-skills": "skills", "fixtures": "fixtures", "references": "references", "scripts": "runtime"}.get(first, "workspace")


def _find_task_entity(reference, entities):
    if not reference:
        return None
    ref = str(reference)
    for entity in entities:
        if entity.get("kind") != "task":
            continue
        normalized = entity.get("normalized") or {}
        if normalized.get("global_ref") == ref or entity.get("entity_id") == ref:
            return entity.get("entity_id")
    return None


def _aggregate_read_only_fallback(aggregate):
    """Compatibility adapter for a pre-read_only_scan Aggregate."""
    workspaces, warnings = aggregate._discover()
    rows = {"workspaces": [], "queues": [], "tasks": [], "documents": [],
            "entities": [], "relations": [], "warnings": list(warnings),
            "unknowns": [], "invalid_sources": []}
    for workspace_root, marker, discovery in workspaces:
        local_warnings = []
        queues, tasks, invalid = aggregate._read_tasks(workspace_root, marker, local_warnings,
                                                       "read-only", "read-only")
        docs, unknown = aggregate._read_documents(workspace_root, marker, local_warnings,
                                                   "read-only", "read-only")
        rows["workspaces"].append({"workspace_id": marker.get("workspace_id"),
                                   "source_root": _rel(aggregate.root, workspace_root),
                                   "source_path": _rel(aggregate.root, workspace_root),
                                   "marker_path": _rel(aggregate.root, os.path.join(workspace_root, ".todone", "workspace.json")),
                                   "status": "partial" if local_warnings else "complete"})
        rows["queues"].extend(queues); rows["tasks"].extend(tasks); rows["documents"].extend(docs)
        rows["unknowns"].extend(unknown); rows["invalid_sources"].extend(invalid); rows["warnings"].extend(local_warnings)
    rows["relations"] = aggregate._relations(rows["tasks"], rows["documents"])
    rows["entities"] = aggregate._entities(rows["documents"])
    for key in rows:
        if isinstance(rows[key], list):
            rows[key].sort(key=lambda value: _json_dumps(value))
    return rows


def build_bundle(root, path=None, **options):
    bundle = AutodocBuilder(root, **options).build()
    if path:
        path = os.path.abspath(path)
        if not _within(os.path.abspath(root), path) and os.path.isabs(path):
            # A caller may intentionally put the bundle outside root; it is
            # still a declared output, but the bundle must never enter sources.
            pass
        _write_json(path, bundle)
    return bundle


# ---------------------------------------------------------------------------
# Diagram and HTML rendering


def _mermaid_label(value):
    """Make one deterministic, non-executable Mermaid node/edge label."""
    text = " ".join(str(value or "").replace("\n", " ").split()) or "—"
    # Entity escaping keeps Mermaid's quoted labels stable even when a source
    # path contains brackets, quotes, or markup-looking text.
    return (text.replace("&", "&amp;").replace('"', "&quot;")
                .replace("`", "'").replace("<", "&lt;").replace(">", "&gt;"))


def _mermaid_node_id(value, index=0):
    base = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "node"))
    base = re.sub(r"_+", "_", base).strip("_") or "node"
    if base[0].isdigit():
        base = "n_" + base
    # The suffix prevents two different paths which slug to the same Mermaid
    # identifier from silently merging into one node.
    suffix = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:8]
    return "n_%s_%s_%d" % (base[:48], suffix, index)


def _mermaid_class(node):
    if node.get("problem") or "problem" in (node.get("flags") or []) or node.get("kind") == "problem":
        return "problem"
    flags = {str(flag).split(":", 1)[0] for flag in node.get("flags") or []}
    if "optional" in flags:
        return "optional"
    if "parallel" in flags or "fan-out" in flags:
        return "parallel"
    if "gate" in flags:
        return "gate"
    if "empty" in flags:
        return "muted"
    return "normal"


def _mermaid_source_for_spec(spec):
    """Project AUTODOC-DIAGRAM-1 data into Mermaid source.

    This is intentionally only a source adapter.  It never emits SVG elements;
    the pinned JS Mermaid runtime owns parsing, layout, shapes, labels, and SVG
    serialization.
    """
    nodes = list(spec.get("nodes") or [])
    edges = list(spec.get("edges") or [])
    if not nodes:
        nodes = [{"node_id": "%s:empty" % spec.get("diagram_id", "diagram"),
                  "label": "Нет данных", "kind": "empty", "flags": []}]
    node_ids = {}
    for index, node in enumerate(nodes):
        node_ids[node.get("node_id")] = _mermaid_node_id(node.get("node_id"), index)
    # A malformed or unresolved edge is still visible: add a named problem
    # node rather than silently dropping the relation from the diagram.
    for edge in edges:
        for endpoint in (edge.get("from"), edge.get("to")):
            if endpoint not in node_ids:
                node = {"node_id": endpoint, "label": "%s (нет узла)" % endpoint,
                        "kind": "problem", "flags": ["problem"], "problem": True}
                nodes.append(node)
                node_ids[endpoint] = _mermaid_node_id(endpoint, len(node_ids))

    direction = "LR" if spec.get("kind") in {"provenance", "timeline"} else "TB"
    lines = [
             '%%{init: {"theme":"base","themeVariables":{"background":"#f5f9fd","fontFamily":"Arial, sans-serif","fontSize":"14px","primaryColor":"#eaf3fc","primaryTextColor":"#132a42","primaryBorderColor":"#4b7697","lineColor":"#58758e","secondaryColor":"#e7f7f1","tertiaryColor":"#f0e9ff","edgeLabelBackground":"#eef4f8"},"flowchart":{"htmlLabels":false,"wrappingWidth":260,"nodeSpacing":55,"rankSpacing":60,"padding":16}}}%%',
             "flowchart %s" % direction,
             "accTitle: %s" % _mermaid_label(spec.get("title") or "Диаграмма"),
             "accDescr: Офлайн Mermaid-диаграмма «%s»: %d узлов и %d переходов." %
             (_mermaid_label(spec.get("title") or "диаграмма"), len(nodes), len(edges)),
             "classDef normal fill:#eaf3fc,stroke:#4b7697,color:#132a42,stroke-width:1.5px,font-size:14px;",
             "classDef optional fill:#eaf7ff,stroke:#2e86ab,color:#11384b,stroke-width:2px,font-size:14px;",
             "classDef parallel fill:#e7f7f1,stroke:#2b8a72,color:#123c32,stroke-width:2px,font-size:14px;",
             "classDef gate fill:#f0e9ff,stroke:#7651a6,color:#2c1d47,stroke-width:2px,font-size:14px;",
             "classDef problem fill:#ffe8ec,stroke:#b84458,color:#54121e,stroke-width:2px,font-size:14px;",
             "classDef muted fill:#edf2f6,stroke:#8391a0,color:#43505d,stroke-dasharray:4 3,font-size:14px;"]
    for node in nodes:
        node_id = node_ids[node.get("node_id")]
        label = _mermaid_label(node.get("label") or node.get("node_id"))
        flags = [str(flag) for flag in node.get("flags") or []]
        # Status is carried primarily by the class colour. Keep only compact
        # flow markers in the label; architecture/provenance labels must remain
        # one short human-readable line instead of becoming a yellow hairball.
        if spec.get("kind") == "flow" and flags:
            compact_flags = []
            for flag in flags:
                if flag.startswith("gate"):
                    token = "gate"
                elif flag == "fan-out":
                    token = "fan-out"
                elif flag == "optional":
                    token = "optional"
                elif flag == "parallel":
                    token = "parallel"
                elif flag == "control":
                    token = "control"
                else:
                    token = flag
                if token not in compact_flags:
                    compact_flags.append(token)
            if compact_flags:
                label += " · " + _mermaid_label(" / ".join(compact_flags))
        lines.append('  %s["%s"]:::%s' % (node_id, label, _mermaid_class(node)))
    for edge in sorted(edges, key=lambda item: (str(item.get("edge_id", "")),
                                                 str(item.get("from", "")),
                                                 str(item.get("to", "")))):
        source = node_ids.get(edge.get("from"))
        target = node_ids.get(edge.get("to"))
        if not source or not target:
            continue
        unresolved = edge.get("resolved") is False or edge.get("resolution") in {"unresolved", "ambiguous"}
        arrow = "-.->" if unresolved else "-->"
        label = _mermaid_label(edge.get("label") or edge.get("kind") or "переход")
        lines.append("  %s %s|%s| %s" % (source, arrow, label, target))
    # Flow steps are real anchors in the surrounding page. Mermaid emits an
    # SVG <a> around the node, so the offline diagram remains keyboard/mouse
    # navigable without a browser-side diagram runtime.
    for node in nodes:
        if node.get("kind") == "empty":
            continue
        target = node.get("href")
        title = "Открыть связанный раздел"
        if spec.get("kind") == "flow" and not target and node.get("kind") == "step":
            target = "#step-%s" % _slug(node.get("node_id"))
            title = "Открыть описание шага"
        if target:
            node_id = node_ids[node.get("node_id")]
            safe_target = str(target).replace('"', "")
            lines.append('  click %s href "%s" "%s"' %
                         (node_id, safe_target, title))
    # Mermaid's dashed arrow is the intentional visual distinction for missing
    # routes/unresolved relations; no post-layout SVG mutation is needed.
    return "\n".join(lines) + "\n"


def _prepare_diagram_spec(spec):
    spec = spec
    spec["renderer"] = MERMAID_RENDERER
    spec["renderer_version"] = MERMAID_VERSION
    spec["renderer_adapter"] = MERMAID_ADAPTER_REL
    spec["renderer_runtime"] = MERMAID_RUNTIME_REL
    spec["renderer_offline"] = True
    if spec.get("source_mode") == "markdown" and spec.get("mermaid_source") is not None:
        # For Markdown diagrams this is the exact source inside the canonical
        # fenced block. The accessibility-enriched form is only a render input;
        # it must never replace what the author can inspect in Markdown.
        spec["mermaid_source"] = str(spec.get("mermaid_source", "")).strip()
        spec["mermaid_render_source"] = _ensure_mermaid_accessibility(
            spec["mermaid_source"], spec.get("title"), spec.get("diagram_id"))
    else:
        spec["mermaid_source"] = _mermaid_source_for_spec(spec)
        spec.pop("mermaid_render_source", None)
        if spec.get("kind") == "flow":
            spec["projection_source"] = spec["mermaid_source"]
            spec["projection_digest"] = sha256_bytes(spec["projection_source"].encode("utf-8"))
    spec["mermaid_source_digest"] = sha256_bytes(spec["mermaid_source"].encode("utf-8"))
    # The full Markdown file digest includes this owned wrapper's spec digest;
    # exclude only that back-reference from the spec identity to avoid a hash
    # cycle while retaining the exact source-file digest in provenance.
    digest_view = copy.deepcopy(spec)
    digest_view.pop("source_file_digest", None)
    digest_view.pop("asset_digest", None)
    digest_view.pop("spec_digest", None)
    spec["spec_digest"] = sha256_bytes(canonical_bytes(digest_view))
    return spec


def _render_mermaid_specs(specs):
    """Render diagram specs through the local JS SDK in one deterministic batch."""
    if not specs:
        return {}
    # ``__file__`` is scripts/tdcore/autodoc.py; keep the path local and
    # refuse a network fallback so offline safety is a hard build invariant.
    adapter = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "mermaid", "render.cjs")
    runtime = os.path.join(os.path.dirname(adapter), "mermaid.min.js")
    node = shutil.which("node")
    if not node or not os.path.isfile(adapter) or not os.path.isfile(runtime):
        raise SkillError("AUTODOC_MERMAID_UNAVAILABLE",
                         "локальный Mermaid adapter/runtime не найден; сеть для autodoc запрещена",
                         MERMAID_ADAPTER_REL)
    jobs = [{"diagram_id": spec.get("diagram_id"),
             "source": spec.get("mermaid_render_source") or spec.get("mermaid_source") or _mermaid_source_for_spec(spec)}
            for spec in sorted(specs, key=lambda item: str(item.get("diagram_id", "")))]
    try:
        completed = subprocess.run(
            [node, adapter], input=_json_dumps(jobs), text=True, capture_output=True,
            cwd=os.path.dirname(adapter), check=False,
            env=dict(os.environ, NO_COLOR="1"))
    except OSError as exc:
        raise SkillError("AUTODOC_MERMAID_FAILED", "не удалось запустить Mermaid adapter: %s" % exc,
                         MERMAID_ADAPTER_REL)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown Mermaid error").strip()
        raise SkillError("AUTODOC_MERMAID_FAILED", detail[-4000:], MERMAID_ADAPTER_REL)
    try:
        rendered = json.loads(completed.stdout)
    except ValueError as exc:
        raise SkillError("AUTODOC_MERMAID_FAILED", "adapter вернул невалидный JSON: %s" % exc,
                         MERMAID_ADAPTER_REL)
    output = {}
    for spec in specs:
        diagram_id = spec.get("diagram_id")
        svg = rendered.get(diagram_id) if isinstance(rendered, dict) else None
        if not isinstance(svg, str) or "<svg" not in svg:
            raise SkillError("AUTODOC_MERMAID_FAILED", "adapter не вернул SVG для %s" % diagram_id,
                             str(diagram_id))
        if re.search(r"<(?:script|iframe|object|embed)\b", svg, re.I):
            raise SkillError("AUTODOC_MERMAID_UNSAFE_OUTPUT", "Mermaid SVG содержит executable markup",
                             str(diagram_id))
        output[diagram_id] = svg
    return output


def _svg_for_spec(spec, problem_nodes=None):
    """Compatibility name retained for callers; implementation is Mermaid-only."""
    if not spec.get("mermaid_source"):
        _prepare_diagram_spec(spec)
    return _render_mermaid_specs([spec])[spec.get("diagram_id")]


def _finalize_diagram_assets(diagrams):
    rendered = _render_mermaid_specs(diagrams)
    for spec in diagrams:
        svg = rendered[spec.get("diagram_id")]
        spec["asset_digest"] = sha256_bytes(svg.encode("utf-8"))
    return rendered


def _html_css():
    """Inline-first stylesheet for the offline catalog and the file viewer.

    The viewer deliberately runs the HTML in a sandbox where relative assets
    may be unavailable.  ``_page_shell`` therefore embeds the same CSS inline;
    ``assets/app.css`` remains available for a downloaded offline bundle.
    """
    return """*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#0a1220;color:#e9eef7;font:15px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:#7dd3fc;text-decoration:none}a:hover{text-decoration:underline}a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #f6c453;outline-offset:3px}.skip{position:absolute;left:-9999px;top:8px}.skip:focus{left:12px;z-index:20;background:#f6c453;color:#111827;padding:8px 12px;border-radius:8px}.layout{display:grid;grid-template-columns:260px minmax(0,1fr);min-height:100vh}.sidebar{background:linear-gradient(180deg,#101d31 0%,#0b1424 100%);border-right:1px solid #243957;padding:16px 12px;position:sticky;top:0;height:100vh;overflow:auto}.brand{display:block;color:#fff;font-size:19px;font-weight:800;letter-spacing:-.03em;margin:0 6px 3px}.brand small{display:block;color:#8ea4bf;font-size:10px;letter-spacing:.14em;text-transform:uppercase;margin-top:3px}.sidebar .hint{color:#8ea4bf;font-size:11px;line-height:1.4;margin:0 6px 13px}.sidebar label{display:block;color:#b5c4d7;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin:12px 6px 5px}.sidebar input{width:100%;padding:8px 9px;border:1px solid #314966;border-radius:8px;background:#07101e;color:#fff;font:inherit;font-size:13px}.sidebar nav{display:grid;gap:2px;margin-top:11px}.sidebar nav a{color:#c5d3e4;padding:6px 8px;border-radius:8px;font-size:12px;line-height:1.3}.sidebar nav a:hover,.sidebar nav a:focus-visible{background:#1b304c;color:#fff;text-decoration:none}.sidebar nav a.active{background:#164e63;color:#d9f7ff}.nav-group{border:0;background:transparent;margin:0}.nav-group summary{list-style:none;cursor:pointer;color:#d9e6f2;padding:6px 8px;border-radius:8px;font-size:13px;line-height:1.25;font-weight:700;display:flex;align-items:center;justify-content:flex-start;min-width:0}.nav-group summary::-webkit-details-marker{display:none}.nav-group summary:before{content:'›';color:#f6c453;font-size:17px;line-height:11px;flex:0 0 13px;margin-right:5px;transition:transform .15s}.nav-group[open] summary:before{transform:rotate(90deg)}.nav-group summary>span:first-of-type,.nav-subgroup summary>span:first-of-type{display:block;flex:1;min-width:0;text-align:left}.nav-group summary:hover,.nav-group summary:focus-visible{background:#1b304c}.nav-count{color:#8ea4bf;font-size:10px;font-weight:500;margin-left:auto;padding-left:7px;flex:0 0 auto}.nav-children{display:grid;gap:1px;padding:1px 0 3px 10px;border-left:1px solid #294764;margin-left:6px}.nav-children a{font-size:11px!important;padding:4px 7px!important;line-height:1.25;display:block}.nav-children .nav-all{color:#9bdcf5;font-weight:700}.nav-label{display:block}.nav-meta{display:block;color:#829ab1;font:9px/1.2 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}.nav-subgroup{margin:1px 0}.nav-subgroup summary{list-style:none;cursor:pointer;color:#d9e6f2;padding:5px 7px;border-radius:7px;font-size:11px;line-height:1.25;font-weight:700;display:flex;align-items:center;justify-content:flex-start;min-width:0}.nav-subgroup summary::-webkit-details-marker{display:none}.nav-subgroup summary:before{content:'›';color:#5fb9d6;font-size:15px;line-height:10px;flex:0 0 11px;margin-right:5px;transition:transform .15s}.nav-subgroup[open] summary:before{transform:rotate(90deg)}.nav-subgroup summary:hover,.nav-subgroup summary:focus-visible{background:#172b45}.nav-subchildren{display:grid;gap:1px;padding:1px 0 2px 8px;border-left:1px solid #31526d;margin-left:6px}.nav-subchildren a{font-size:10px!important;padding:4px 6px!important;line-height:1.25}.main{min-width:0}.layout main{max-width:1420px;width:100%;padding:28px clamp(18px,4vw,58px) 70px}.topline{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:22px;color:#8ea4bf;font-size:12px;text-transform:uppercase;letter-spacing:.14em}.topline strong{color:#f6c453}.breadcrumbs{color:#8ea4bf;font-size:13px;margin-bottom:24px}.breadcrumbs a{color:#9bdcf5}.hero{background:radial-gradient(circle at 85% 10%,#1d5264 0,#12334b 32%,#102238 70%);border:1px solid #2d526d;border-radius:22px;padding:30px clamp(20px,4vw,42px);box-shadow:0 20px 70px rgba(0,0,0,.22);margin-bottom:26px}.eyebrow,.kicker{color:#f6c453;font-size:12px;font-weight:800;letter-spacing:.17em;text-transform:uppercase}.hero h1{font-size:clamp(34px,5vw,66px);line-height:1.02;letter-spacing:-.055em;margin:12px 0 13px}.hero p{max-width:850px;color:#c9d9e8;font-size:18px;margin:0}.lead{font-size:18px;color:#c9d9e8;max-width:900px}.section-head{display:flex;justify-content:space-between;align-items:end;gap:20px;margin:35px 0 15px}.section-head h2{margin:0}.section-head p{margin:0;color:#8ea4bf}.stats,.grid,.catalog-grid,.split{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:13px}.stat,.card,.catalog-card,.callout,.step-card,.state-card{background:linear-gradient(145deg,#12243b,#0f1d31);border:1px solid #28435f;border-radius:15px;padding:17px;box-shadow:0 9px 24px rgba(0,0,0,.12)}.stat .metric,.metric{display:block;color:#f6c453;font-size:31px;font-weight:850;line-height:1}.stat .label{display:block;color:#a9bdd1;font-size:12px;margin-top:8px;text-transform:uppercase;letter-spacing:.08em}.catalog-card{display:block;color:#e9eef7;transition:transform .15s,border-color .15s}.catalog-card:hover{transform:translateY(-2px);border-color:#5fb9d6;text-decoration:none}.catalog-card h3{margin:0 0 5px;color:#fff}.catalog-card p{margin:0;color:#a9bdd1;font-size:14px}.catalog-card .meta,.meta{color:#8ea4bf;font-size:12px}.catalog-card .schema-code{margin:0 0 6px;color:#8ea4bf;font:11px/1.35 ui-monospace,SFMono-Regular,Consolas,monospace}.schema-purpose{background:#102b40;border:1px solid #2b607a;border-left:4px solid #5fb9d6;border-radius:12px;padding:13px 16px;margin:15px 0 24px;max-width:980px}.schema-purpose strong{color:#bdeeff}.schema-purpose p{margin:5px 0}.pill,.badge{display:inline-block;border:1px solid #35627e;border-radius:999px;padding:3px 9px;background:#123448;color:#bdeeff;font-size:12px;white-space:nowrap}.pill.good{background:#123e37;border-color:#32896f;color:#b6ffe3}.pill.warn{background:#4a3217;border-color:#9a6b2f;color:#ffd993}.pill.bad{background:#4a1e26;border-color:#9e4655;color:#ffd0d7}.callout{border-left:4px solid #f6c453}.callout strong{color:#f6c453}.warning{border-left:4px solid #f6c453;background:#3b2b15;padding:12px 15px;border-radius:10px;margin:8px 0}.error,.problem{border-left:4px solid #fb7185;background:#401d27;padding:12px 15px;border-radius:10px;margin:8px 0}.ok{border-left:4px solid #5eead4;background:#10342f;padding:12px 15px;border-radius:10px;margin:8px 0}h1,h2,h3,h4{line-height:1.2;color:#f4f7fb}h1{font-size:38px;letter-spacing:-.035em;margin:0 0 14px}h2{font-size:25px;margin:34px 0 13px;border-bottom:1px solid #263f5b;padding-bottom:8px}h3{font-size:18px;margin:22px 0 9px}h4{font-size:15px;color:#bdeeff;margin:18px 0 6px}p{color:#c2d0df}ul,ol{padding-left:25px}li{margin:5px 0;color:#c2d0df}.prose{max-width:1020px}.prose p{max-width:930px}.prose h1{font-size:31px;margin-top:26px}.prose h2{font-size:25px}.prose h3{font-size:19px}.prose blockquote{margin:16px 0;padding:10px 17px;border-left:4px solid #5fb9d6;background:#102b40;color:#c8dae8;border-radius:0 9px 9px 0}.prose table,.data-table{border-collapse:separate;border-spacing:0;width:100%;background:#0f1e31;border:1px solid #28435f;border-radius:12px;overflow:hidden;margin:15px 0}.prose th,.prose td,.data-table th,.data-table td{text-align:left;vertical-align:top;padding:10px 12px;border-bottom:1px solid #243c57;color:#c6d5e4}.prose th,.data-table th{background:#16304a;color:#dff6ff;font-size:13px}.prose tr:last-child td,.data-table tr:last-child td{border-bottom:0}.prose code,code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;color:#c8f7e8;background:#0b2430;border:1px solid #235165;border-radius:5px;padding:2px 5px}.prose pre,pre{overflow:auto;background:#07101b;color:#dce8f3;border:1px solid #253c57;border-radius:11px;padding:15px;white-space:pre-wrap}.prose pre code{border:0;background:transparent;padding:0;color:inherit}.doc-meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;color:#9bb0c4;margin:0 0 20px}.toc{background:#102238;border:1px solid #2b4965;border-radius:14px;padding:15px 18px;margin:18px 0 25px}.toc strong{color:#f6c453}.toc ul{columns:2;margin:9px 0 0}.toc li{break-inside:avoid}.compat{border:1px solid #624b28;background:#2a2115;border-radius:12px;padding:13px 16px;margin-top:26px}.compat summary{color:#ffd993;font-weight:700;cursor:pointer}.raw-details{margin-top:18px;border:1px solid #2b4965;border-radius:12px;padding:12px 15px}.raw-details summary{cursor:pointer;color:#9bdcf5;font-weight:700}.step-list{display:grid;gap:12px}.step-card{display:grid;grid-template-columns:54px 1fr;gap:15px;align-items:start}.step-no{width:44px;height:44px;display:grid;place-items:center;border-radius:50%;background:#f6c453;color:#101a29;font-weight:900;font-size:17px}.step-card h3{margin:1px 0 6px}.step-card p{margin:5px 0}.step-card .route{margin-top:9px;color:#bdeeff;font-size:13px}.flow-layout{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(280px,.85fr);gap:18px;align-items:start}.diagram{overflow:auto;border:1px solid #2b4965;background:#f8fbff;border-radius:15px;padding:12px;position:relative}.diagram svg{display:block;width:auto;max-width:100%;min-width:0;height:auto}.diagram svg a{cursor:pointer}.flow-layout .diagram svg{width:auto;min-width:900px;max-width:none}.diagram-caption{color:#6f879d;font-size:12px;margin-top:8px}.diagram-empty{border:1px solid #2b4965;background:linear-gradient(145deg,#12243b,#0d1a2c);border-radius:15px;padding:24px 26px;min-height:150px;display:grid;align-content:center;gap:5px}.diagram-empty strong{color:#f6c453;font-size:18px}.diagram-empty p{margin:0;color:#a9bdd1;max-width:720px}.diagram-empty .diagram-caption{margin-top:4px}.markdown-diagram .diagram svg{width:auto;min-width:0;max-width:100%}.markdown-diagram{margin:22px 0}.markdown-diagram figcaption{color:#8ea4bf;font-size:12px;margin:8px 0}.markdown-diagram .diagram{position:static}.markdown-diagram .diagram svg{width:auto;min-width:0;max-width:100%}.state-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.state-card h4{margin:0 0 5px}.state-card p{margin:0;font-size:13px}.json-details{margin-top:16px;border:1px solid #294764;border-radius:11px;padding:10px 13px;background:#0d1b2d}.json-details summary{cursor:pointer;color:#9bdcf5;font-weight:700}.entity-list{display:grid;gap:9px}.entity-row{display:flex;align-items:center;justify-content:space-between;gap:15px;background:#102238;border:1px solid #294764;border-radius:11px;padding:12px 14px}.entity-row:hover{border-color:#5fb9d6}.entity-row small{color:#91a8bd}.source-link{font-size:13px}.hidden{display:none!important}.entity-catalog{display:grid;gap:16px}.entity-catalog-intro{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}.entity-kind-stat{display:flex;align-items:center;gap:10px;background:#102238;border:1px solid #294764;border-radius:12px;padding:10px 13px;color:#d8e6f2}.entity-kind-stat strong{font-size:20px;color:#f6c453}.entity-kind-stat span{font-size:12px;color:#a9bdd1}.entity-tree{display:grid;gap:13px}.entity-group,.entity-node{border:1px solid #294764;border-radius:15px;background:#0f1d31;overflow:hidden}.entity-group>summary,.entity-node>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:12px;padding:15px 17px;color:#f4f7fb;font-weight:800}.entity-group>summary::-webkit-details-marker,.entity-node>summary::-webkit-details-marker{display:none}.entity-group>summary:before,.entity-node>summary:before{content:'›';flex:0 0 16px;color:var(--entity-accent,#f6c453);font-size:24px;line-height:14px;transition:transform .15s}.entity-group[open]>summary:before,.entity-node[open]>summary:before{transform:rotate(90deg)}.entity-group>summary:hover,.entity-node>summary:hover,.entity-group>summary:focus-visible,.entity-node>summary:focus-visible{background:#162b44}.entity-group__title,.entity-node__title{min-width:0;flex:1}.entity-group__title strong,.entity-node__title strong{display:block;font-size:18px}.entity-group__title small,.entity-node__title small{display:block;color:#91a8bd;font-size:12px;font-weight:500;margin-top:2px}.entity-count{flex:0 0 auto;color:#dff6ff;background:color-mix(in srgb,var(--entity-accent,#4fa6c7) 24%,#0d1b2d);border:1px solid var(--entity-accent,#4fa6c7);border-radius:999px;padding:3px 9px;font-size:12px}.entity-group__body{padding:0 17px 18px 48px;border-top:1px solid #223c56}.entity-group__body>p{margin:13px 0;color:#a9bdd1;font-size:14px}.entity-children{display:grid;gap:9px;margin-top:10px}.entity-node{background:#102238;border-radius:12px;border-color:#294764}.entity-node>summary{padding:12px 13px}.entity-node__title strong{font-size:15px}.entity-node__body{padding:0 13px 13px 42px;border-top:1px solid #294764}.entity-card{display:block;position:relative;color:#e9eef7;background:linear-gradient(145deg,#142a43,#102035);border:1px solid var(--entity-accent,#35627e);border-left:4px solid var(--entity-accent,#5fb9d6);border-radius:11px;padding:12px 14px;margin-top:10px}.entity-card:hover{border-color:#8bdaf2;text-decoration:none;transform:translateX(2px)}.entity-card__head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.entity-card__name{font-size:17px;font-weight:800;color:#f6f8fb;line-height:1.25}.entity-card__kind{color:var(--entity-accent,#7dd3fc);font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;white-space:nowrap}.entity-card__purpose{margin:6px 0 0;color:#c4d4e2;font-size:14px;line-height:1.45}.entity-card__technical{display:block;margin-top:8px;color:#7f9ab2;font:11px/1.35 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}.entity-card__links{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.entity-chip{display:inline-block;border:1px solid #35627e;border-radius:999px;background:#102f43;color:#aee7f8;font-size:11px;padding:2px 8px}.entity-inline-details{margin-top:12px;border-top:1px solid #294764;padding-top:9px}.entity-inline-details>summary{list-style:none;cursor:pointer;color:#9bdcf5;font-size:12px;font-weight:800}.entity-inline-details>summary::-webkit-details-marker{display:none}.entity-inline-details>summary:before{content:'＋';color:#5fb9d6;margin-right:6px}.entity-inline-details[open]>summary:before{content:'−'}.entity-inline-details .data-table{margin:9px 0;background:#0c1a2b;font-size:12px}.entity-inline-details .data-table th,.entity-inline-details .data-table td{padding:7px 9px}.entity-inline-details .json-details{margin-top:9px}.entity-inline-details .json-details pre{max-height:280px;font-size:11px}.unified-map{display:grid;gap:12px;margin:18px 0 28px}.unified-explainer{background:linear-gradient(145deg,#132d43,#102238);border:1px solid #2f6079;border-left:4px solid #f6c453;border-radius:14px;padding:15px 18px;color:#c9d9e8}.unified-explainer strong{color:#f6c453}.unified-explainer p{margin:5px 0}.unified-root{border:1px solid #f6c453;border-radius:17px;background:linear-gradient(145deg,#1c3145,#102035);padding:18px}.unified-root__head{display:flex;align-items:flex-start;justify-content:space-between;gap:15px}.unified-root__title{color:#fff;font-size:22px;font-weight:850}.unified-root__purpose{color:#b9cddd;font-size:14px;margin:4px 0 0}.unified-branches{display:grid;gap:11px;margin:16px 0 0 18px;padding-left:18px;border-left:2px solid #446780}.unified-branch{border:1px solid #2e526d;border-radius:14px;background:#102238;overflow:hidden}.unified-branch>summary,.unified-flow>summary,.unified-common>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:11px;padding:13px 15px;color:#f4f7fb;font-weight:800}.unified-branch>summary::-webkit-details-marker,.unified-flow>summary::-webkit-details-marker,.unified-common>summary::-webkit-details-marker{display:none}.unified-branch>summary:before,.unified-flow>summary:before,.unified-common>summary:before{content:'›';color:#58c7d9;font-size:23px;line-height:14px;transition:transform .15s}.unified-branch[open]>summary:before,.unified-flow[open]>summary:before,.unified-common[open]>summary:before{transform:rotate(90deg)}.unified-branch__title{flex:1;min-width:0}.unified-branch__title strong{display:block}.unified-branch__title small{display:block;color:#91a8bd;font-size:12px;font-weight:500;margin-top:2px}.unified-branch__body{padding:0 15px 15px 43px;border-top:1px solid #294764}.unified-flow{margin-top:10px;border-left:3px solid #58c7d9;border-radius:11px;background:#0d1d30}.unified-flow>summary{padding:12px 13px}.unified-flow__body{padding:0 13px 13px 35px;border-top:1px solid #294764}.unified-flow__steps{display:grid;gap:8px;margin-top:10px;padding-left:13px;border-left:2px solid #58c7d9}.unified-step{border:1px solid #355977;border-radius:11px;background:#11263d;overflow:hidden}.unified-step>summary{list-style:none;cursor:pointer;display:flex;align-items:flex-start;gap:10px;padding:11px 12px}.unified-step>summary::-webkit-details-marker{display:none}.unified-step>summary:before{content:'›';color:#73b8a5;font-size:21px;line-height:14px;transition:transform .15s}.unified-step[open]>summary:before{transform:rotate(90deg)}.unified-step__title{flex:1;min-width:0}.unified-step__title strong{display:block;color:#f4f7fb}.unified-step__title small{display:block;color:#9bb2c6;margin-top:3px}.unified-step__kind{color:#73b8a5;border:1px solid #4a8d7c;border-radius:999px;padding:2px 8px;font-size:10px;white-space:nowrap}.unified-step__body{padding:0 12px 12px 38px;border-top:1px solid #294764}.unified-relations{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-top:10px}.unified-relations__label{color:#819ab0;font-size:11px;text-transform:uppercase;letter-spacing:.08em}.unified-link{display:inline-flex;align-items:center;gap:5px;border:1px solid #37647f;border-radius:999px;background:#102f43;color:#bdeeff;padding:4px 9px;font-size:11px}.unified-link:hover{text-decoration:none;border-color:#8bdaf2;background:#173d53}.unified-link--type{border-color:#9d7bea}.unified-link--agent{border-color:#7dd3fc}.unified-link--role{border-color:#e7a7ff}.unified-link--skill{border-color:#5eead4}.unified-link--source{border-color:#829ab1}.unified-common-grid{display:grid;gap:10px;margin-top:11px}.unified-common{border:1px solid #31556e;border-radius:11px;background:#0d1d30;overflow:hidden}.unified-common__body{padding:0 12px 12px 35px;border-top:1px solid #294764}.unified-common__items{display:grid;gap:7px;margin-top:9px}.unified-relationship-note{color:#8ea4bf;font-size:12px;margin:10px 0 0}.process-page{display:grid;gap:18px}.process-filters{display:grid;grid-template-columns:minmax(220px,1.4fr) repeat(3,minmax(150px,1fr)) auto;gap:10px;align-items:end;padding:15px;background:#102238;border:1px solid #2e526d;border-radius:15px}.process-filter-field{display:grid;gap:5px}.process-filter-field label{color:#9bb2c6;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.process-filter-field input,.process-filter-field select{width:100%;min-height:39px;padding:8px 10px;border:1px solid #35627e;border-radius:9px;background:#091727;color:#e9eef7;font:inherit;font-size:13px}.process-filter-reset{min-height:39px;border:1px solid #5fb9d6;border-radius:9px;background:#123448;color:#bdeeff;padding:8px 12px;font:inherit;font-size:13px;cursor:pointer}.process-filter-reset:hover{background:#1b4b63}.process-filter-status{color:#8ea4bf;font-size:12px;margin:0}.process-flow-tree{display:grid;gap:11px}.process-no-results{display:none;border:1px solid #765c2c;border-left:4px solid #f6c453;border-radius:12px;background:#2d2417;color:#ffd993;padding:15px}.process-no-results.is-visible{display:block}@media(max-width:900px){.process-filters{grid-template-columns:1fr}}.entity-group--catalog{--entity-accent:#829ab1}.entity-group--workspace,.entity-node--workspace{--entity-accent:#f6c453}.entity-group--flow,.entity-node--flow{--entity-accent:#58c7d9}.entity-group--type,.entity-node--type{--entity-accent:#9d7bea}.entity-group--skill,.entity-node--skill{--entity-accent:#5eead4}.entity-group--schema,.entity-node--schema{--entity-accent:#64a9ff}.entity-group--template,.entity-node--template{--entity-accent:#f0a35b}.entity-group--role,.entity-node--role{--entity-accent:#e7a7ff}.entity-group--agent,.entity-node--agent{--entity-accent:#7dd3fc}.entity-group--markdown,.entity-node--markdown{--entity-accent:#b7d37d}.entity-group--source-file,.entity-node--source-file{--entity-accent:#829ab1}.entity-group--flow-step,.entity-node--flow-step{--entity-accent:#73b8a5}.entity-subgroup{border-left:2px solid var(--entity-accent,#4fa6c7);margin:12px 0 0 5px;padding-left:12px}.entity-subgroup>summary{list-style:none;cursor:pointer;color:#dcebf5;font-weight:700;padding:8px 0}.entity-subgroup>summary::-webkit-details-marker{display:none}.entity-subgroup>summary:before{content:'＋';color:var(--entity-accent,#4fa6c7);margin-right:7px}.entity-subgroup[open]>summary:before{content:'−'}.entity-empty{color:#8ea4bf;font-size:13px;padding:10px 0}.entity-legend{display:flex;flex-wrap:wrap;gap:7px;margin:7px 0 20px}.entity-legend .entity-chip{border-left:3px solid var(--entity-accent,#4fa6c7)}@media(max-width:900px){.entity-group__body{padding-left:18px}.entity-node__body{padding-left:18px}.entity-card__head{display:block}.entity-card__kind{display:block;margin-bottom:5px}}.source-note{color:#8ea4bf;font-size:13px}.footer-grid{display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}footer{border-top:1px solid #243c57;padding-top:18px;margin-top:55px;color:#8197ae;font-size:12px}@media(max-width:900px){.layout{display:block}.sidebar{position:static;height:auto;border-right:0;border-bottom:1px solid #243957}.sidebar nav{display:flex;flex-wrap:wrap}.sidebar nav a{font-size:13px}.flow-layout{grid-template-columns:1fr}.diagram{position:static}.toc ul{columns:1}.layout main{padding:22px 16px 55px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.catalog-card{transition:none}}/* flat information architecture */
:root{--ui-border:#29445c;--ui-border-strong:#42627b;--ui-surface:#0f1d2d;--ui-surface-2:#12263b;--ui-muted:#91a8bd;--flow:#58c7d9;--flow-step:#73b8a5;--type:#9d7bea;--agent:#7dd3fc;--role:#e7a7ff;--skill:#5eead4;--schema:#64a9ff;--template:#f0a35b;--doc:#b7d37d;--source:#829ab1}
.hero,.stat,.card,.catalog-card,.callout,.step-card,.state-card,.process-filters,.schema-purpose,.toc,.compat,.diagram,.diagram-empty,.entity-group,.entity-node,.entity-card,.unified-root,.unified-branch,.unified-flow,.unified-step,.unified-common,.json-details,.raw-details,.process-guide,.process-entity-line,.decision-tree,.process-provenance{border-radius:2px;box-shadow:none}
.hero{border-top:3px solid var(--flow);background:#102238;padding:26px clamp(18px,4vw,42px)}
.hero h1{letter-spacing:-.04em}.section-head{border-bottom:1px solid var(--ui-border);padding-bottom:10px}.catalog-card{border-color:var(--ui-border);border-left:3px solid var(--ui-border-strong);background:#101f31}.catalog-card:hover{transform:none;border-color:var(--flow);border-left-color:var(--flow)}
.pill,.badge,.entity-count,.entity-chip,.unified-link{border-radius:1px}.pill,.badge{padding:2px 7px}.entity-count{padding:2px 7px}
.entity-group,.entity-node{border-color:var(--ui-border);background:#0e1b2b}.entity-group>summary,.entity-node>summary{border-left:4px solid var(--entity-accent,var(--ui-border-strong));border-bottom:1px solid transparent}.entity-group[open]>summary,.entity-node[open]>summary{border-bottom-color:var(--ui-border)}.entity-group__body,.entity-node__body{background:#0b1726}.entity-card{border-color:var(--entity-accent,var(--ui-border));border-left-width:4px;background:#102238}.entity-card__kind{color:var(--entity-accent,var(--flow))}.entity-card--flow,.entity-node--flow{--entity-accent:var(--flow)}.entity-card--flow-step,.entity-node--flow-step{--entity-accent:var(--flow-step)}.entity-card--type,.entity-node--type{--entity-accent:var(--type)}.entity-card--agent,.entity-node--agent{--entity-accent:var(--agent)}.entity-card--role,.entity-node--role{--entity-accent:var(--role)}.entity-card--skill,.entity-node--skill{--entity-accent:var(--skill)}.entity-card--schema,.entity-node--schema{--entity-accent:var(--schema)}.entity-card--template,.entity-node--template{--entity-accent:var(--template)}.entity-card--markdown,.entity-node--markdown{--entity-accent:var(--doc)}.entity-card--source-file,.entity-node--source-file{--entity-accent:var(--source)}
.process-guide{border:1px solid var(--ui-border);border-left:5px solid #f6c453;background:#101f31;padding:14px 16px;margin:0 0 18px}.process-guide__title{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}.process-guide__title strong{font-size:17px;color:#fff}.process-grammar{display:flex;align-items:center;flex-wrap:wrap;gap:7px;margin:12px 0 9px;color:#c8d7e5;font-size:13px}.grammar-arrow{color:#718ba2;font-size:11px;text-transform:uppercase;letter-spacing:.08em}.kind-key,.legend-item{display:inline-flex;align-items:center;gap:6px;border-left:4px solid var(--key-color,var(--ui-border-strong));color:#e8f1f8;font-weight:750;font-size:12px;padding:3px 8px;background:#0c1a2a}.kind-key--flow,.legend-item--flow{--key-color:var(--flow)}.kind-key--flow-step,.legend-item--flow-step{--key-color:var(--flow-step)}.kind-key--type,.legend-item--type{--key-color:var(--type)}.kind-key--agent,.legend-item--agent{--key-color:var(--agent)}.kind-key--role,.legend-item--role{--key-color:var(--role)}.legend-item--skill{--key-color:var(--skill)}.legend-item--schema{--key-color:var(--schema)}.legend-item--template{--key-color:var(--template)}.legend-item--markdown{--key-color:var(--doc)}.legend-item i{display:block;width:7px;height:7px;background:var(--key-color)}.process-guide p{margin:10px 0 0;color:var(--ui-muted);font-size:13px}.process-legend{display:flex;flex-wrap:wrap;gap:5px}
.process-filters{border:1px solid var(--ui-border);border-left:5px solid var(--flow);background:#0e1b2b;padding:12px}.process-filter-field input,.process-filter-field select,.process-filter-reset{border-radius:1px}.process-filter-reset{box-shadow:none}.process-filter-status{border-left:3px solid var(--ui-border-strong);padding-left:9px}
.process-page .unified-map{gap:0;margin-top:14px}.process-page .unified-root{padding:0;border:0;background:transparent}.process-page .unified-root__head{border:1px solid var(--ui-border-strong);border-left:5px solid #f6c453;background:#13283d;padding:14px 16px}.process-page .process-flow-tree{display:grid;gap:14px;margin:0 0 0 18px;padding:14px 0 8px 24px;border-left:2px solid #31516a}.process-page .unified-branch{margin-top:14px;border-left:4px solid #f6c453}.process-page .unified-branch>summary{background:#101f31}.process-page .unified-branch__body{padding-bottom:12px}
.process-flow{--entity-accent:var(--flow);border:0;border-left:5px solid var(--entity-accent);background:transparent;overflow:visible}.process-flow>summary{border:1px solid var(--ui-border);border-left:0;background:#11263b;padding:13px 14px}.process-flow[open]>summary{border-bottom-color:var(--entity-accent);background:#142b42}.process-flow .unified-flow__body{padding:10px 0 8px 22px;border-left:1px solid var(--ui-border);border-top:0;background:#0c1928}.process-flow-number,.process-step-number{display:grid;place-items:center;flex:0 0 auto;background:var(--entity-accent);color:#07111c;font-weight:900;border-radius:1px}.process-flow-number{width:30px;height:30px}.process-step-number{width:27px;height:27px;font-size:12px}.process-flow .unified-branch__title{display:grid;gap:3px}.process-flow .process-kind-tag{margin-bottom:0}.process-flow-intro{border-left:3px solid var(--flow);padding:0 0 10px 12px;color:#cbd9e6}.process-flow-intro strong{color:#fff}.process-flow .unified-relationship-note{margin:9px 0;color:var(--ui-muted)}
.process-entity-line{border:1px solid var(--ui-border);border-left:4px solid var(--entity-accent,var(--ui-border-strong));background:#102238;padding:11px 13px;margin:0 0 10px}.process-entity-line.entity-kind--flow{--entity-accent:var(--flow)}.process-entity-line.entity-kind--flow-step{--entity-accent:var(--flow-step)}.process-entity-line.entity-kind--type{--entity-accent:var(--type)}.process-entity-line.entity-kind--agent{--entity-accent:var(--agent)}.process-entity-line.entity-kind--role{--entity-accent:var(--role)}.process-entity-line__head{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.process-entity-line__head>a{font-size:18px;font-weight:850;color:#fff}.process-kind-tag{color:var(--entity-accent,var(--flow));font-size:10px;font-weight:850;letter-spacing:.11em;text-transform:uppercase;border:1px solid var(--entity-accent,var(--flow));border-radius:1px;padding:2px 6px}.process-entity-line__purpose{margin:6px 0;color:#c6d5e3;font-size:13px}.process-entity-line__meta{display:flex;align-items:center;flex-wrap:wrap;gap:7px;color:var(--ui-muted);font-size:11px}.process-entity-line__meta code{font-size:10px;color:#9db1c2;background:#091522;border-color:#28455c}.process-entity-line__links{display:flex;flex-wrap:wrap;gap:4px}.process-open-entity{margin-left:auto;color:#9bdcf5;font-size:11px;white-space:nowrap}.process-flow .entity-inline-details{margin-top:10px}.process-flow .entity-inline-details>summary{color:#9bdcf5}.process-flow .entity-inline-details .data-table{border-radius:1px}
.process-step{--entity-accent:var(--flow-step);border:1px solid var(--ui-border);border-left:4px solid var(--entity-accent);background:#0e1d2d;overflow:visible}.process-step>summary{padding:10px 12px;background:#11263a}.process-step[open]>summary{background:#143044;border-bottom:1px solid var(--entity-accent)}.process-step .unified-step__title{display:grid;gap:2px}.process-step .unified-step__title strong{font-size:16px}.process-step .unified-step__title small{font-size:12px;color:#a9bfd1}.process-step .unified-step__kind{color:var(--flow-step);border-color:var(--flow-step);border-radius:1px}.process-step .unified-step__body{padding:12px 13px 15px 43px;background:#0b1827}.process-step-brief{border-left:3px solid var(--flow-step);padding:0 0 10px 11px;color:#d4e1eb;font-size:13px}.process-step-brief .process-entity-line{margin-top:10px}.process-step .unified-relations{margin:10px 0 0}.process-step .unified-link{border-radius:1px}.process-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0;margin:12px 0;border-top:1px solid var(--ui-border);border-left:1px solid var(--ui-border)}.process-fact{display:grid;grid-template-columns:minmax(105px,.35fr) minmax(0,1fr);gap:10px;padding:8px 10px;border-right:1px solid var(--ui-border);border-bottom:1px solid var(--ui-border);min-width:0}.process-fact dt{color:#91a8bd;font-size:10px;font-weight:850;letter-spacing:.08em;text-transform:uppercase}.process-fact dd{margin:0;color:#e2edf5;overflow-wrap:anywhere}.process-fact dd .unified-link{margin:0 3px 3px 0}.process-resource-groups{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:11px 0}.process-resource-group{border-left:3px solid var(--resource-color,var(--ui-border-strong));padding:7px 9px;background:#0f2133}.process-resource-group--markdown{--resource-color:var(--doc)}.process-resource-group--schema{--resource-color:var(--schema)}.process-resource-group--template{--resource-color:var(--template)}.process-resource-group--skill{--resource-color:var(--skill)}.process-resource-group h4{margin:0 0 6px;color:var(--resource-color);font-size:11px;text-transform:uppercase;letter-spacing:.08em}.process-resource-group .unified-link{display:inline-block;margin:0 3px 3px 0}.process-resource-summary{border:1px solid var(--resource-color,var(--ui-border));border-left:3px solid var(--resource-color,var(--ui-border));background:#0b1a29;min-width:105px}.process-resource-summary--markdown{--resource-color:var(--doc)}.process-resource-summary--schema{--resource-color:var(--schema)}.process-resource-summary--template{--resource-color:var(--template)}.process-resource-summary--skill{--resource-color:var(--skill)}.process-resource-summary>summary{display:flex;align-items:center;gap:6px;cursor:pointer;list-style:none;padding:3px 7px;color:#cfe0ec;font-size:11px;font-weight:800}.process-resource-summary>summary::-webkit-details-marker{display:none}.process-resource-summary>summary:before{content:'＋';color:var(--resource-color);font-size:13px}.process-resource-summary[open]>summary:before{content:'−'}.process-resource-summary>summary strong{margin-left:auto;color:var(--resource-color)}.resource-swatch{width:6px;height:6px;background:var(--resource-color);display:block}.process-resource-summary__body{display:flex;flex-wrap:wrap;gap:4px;padding:7px;border-top:1px solid var(--resource-color)}.process-resource-summary__body .unified-link{margin:0}.process-resource-group .process-resource-summary{width:100%}
.decision-tree{border:1px solid #765c94;border-left:4px solid var(--role);background:#1a2037;margin:12px 0;padding:10px 12px}.decision-tree__head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;color:#f5e7ff}.decision-tree__kind{color:var(--role);font-size:10px;font-weight:850;letter-spacing:.13em}.decision-tree__head code{color:#d8b8ff}.decision-tree__body{margin-top:8px;padding-left:17px;border-left:1px solid #765c94}.decision-node{display:flex;align-items:center;gap:7px;color:#dbe6ef}.decision-node__dot{width:8px;height:8px;background:var(--role);display:inline-block}.decision-tree ul{margin:7px 0 0;padding:0 0 0 16px;border-left:1px dashed #765c94;list-style:none}.decision-tree li{display:flex;align-items:center;gap:8px;margin:5px 0;color:#dbe6ef}.decision-choice{color:#ffd8f4;font-weight:750}.decision-arrow{color:#aa83c3}.decision-target{color:#aee7f8;border-bottom:1px dotted #5fb9d6}.decision-target--terminal{color:#ffd993;border-bottom-color:#f6c453}.process-provenance{border-top:1px solid var(--ui-border);margin-top:12px;padding-top:10px}.process-provenance h4{margin:0 0 7px;color:#b9cddd;font-size:12px;text-transform:uppercase;letter-spacing:.08em}.process-provenance ul{margin:0;padding-left:18px}.process-provenance li{font-size:12px;color:#c7d5e1}.process-provenance li code{margin-left:7px;color:#bdeeff}.process-provenance li small{display:block;color:#718ba1;font-size:10px;overflow-wrap:anywhere}.process-provenance-count{margin:6px 0 0;color:#718ba1;font-size:11px}.process-empty-note{color:#829ab1;font-size:12px}
.unified-relations{border-top:1px solid var(--ui-border);padding-top:8px}.unified-relations__label{color:#718ba1;font-weight:850}.unified-link{border-color:var(--link-color,var(--ui-border-strong));background:#0d2233;padding:3px 7px}.unified-link--flow{--link-color:var(--flow)}.unified-link--flow-step{--link-color:var(--flow-step)}.unified-link--type{--link-color:var(--type)}.unified-link--agent{--link-color:var(--agent)}.unified-link--role{--link-color:var(--role)}.unified-link--skill{--link-color:var(--skill)}.unified-link--schema{--link-color:var(--schema)}.unified-link--template{--link-color:var(--template)}.unified-link--markdown{--link-color:var(--doc)}.unified-link--source-file{--link-color:var(--source)}
@media(max-width:900px){.process-grammar{align-items:flex-start}.process-page .process-flow-tree{margin-left:5px;padding-left:12px}.process-flow .unified-flow__body{padding-left:10px}.process-step .unified-step__body{padding-left:14px}.process-facts{grid-template-columns:1fr}.process-resource-groups{grid-template-columns:repeat(2,minmax(0,1fr))}.process-open-entity{margin-left:0}}@media(max-width:560px){.process-resource-groups{grid-template-columns:1fr}.process-entity-line__head>a{font-size:16px}.process-flow>summary{align-items:flex-start}.process-flow .entity-count{margin-left:auto}}*,*::before,*::after{border-radius:0!important}
/* TODONE DOCUMENTATION DESIGN SYSTEM · v2 */
:root{--canvas:#070c14;--canvas-2:#0a111d;--surface:#0d1827;--surface-2:#112238;--surface-3:#162b42;--line:#263d54;--line-strong:#41627c;--text:#edf5fb;--text-soft:#c4d4e0;--text-muted:#8299ad;--accent:#70e4e1;--accent-warm:#f5c85d;--danger:#ff7e92;--flow:#59d4df;--flow-step:#79c5a8;--type:#ae8cff;--agent:#77cfff;--role:#f0a6ff;--skill:#63e3c8;--schema:#70aeff;--template:#ffae68;--doc:#c4df83;--source:#899caf}
html,body{background:var(--canvas);color:var(--text)}body{font-size:14px;line-height:1.55;letter-spacing:.005em}a{color:#8cdbf5}a:hover{color:#fff;text-decoration:none}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:2px solid var(--accent-warm);outline-offset:2px}
.layout{grid-template-columns:286px minmax(0,1fr);background:var(--canvas)}.sidebar{background:#09121f;border-right:1px solid #20354a;padding:22px 14px;box-shadow:12px 0 30px rgba(0,0,0,.12)}.brand{font-size:21px;letter-spacing:-.04em;margin:0 8px 4px}.brand small{color:#7994aa;letter-spacing:.18em}.sidebar .hint{margin:0 8px 18px;color:#87a0b5;font-size:11px;max-width:220px}.sidebar label{margin:14px 8px 6px;color:#708ba1;font-size:10px;letter-spacing:.14em}.sidebar input{border:1px solid #29445b;background:#07101b;padding:10px 11px}.sidebar nav{gap:4px;margin-top:14px}.nav-group summary{border-left:3px solid transparent;padding:8px 9px;color:#dce7ef;font-size:13px}.nav-group[open] summary{border-left-color:var(--accent)}.nav-group summary:hover,.nav-group summary:focus-visible{background:#10253a}.nav-group summary:before{color:var(--accent-warm)}.nav-count{color:#6f8aa0}.nav-children{padding:3px 0 6px 13px;margin-left:8px;border-left:1px solid #29455c}.nav-children a{padding:5px 8px!important;color:#adc1d0}.nav-children a.active{background:#123246;border-left:2px solid var(--accent);color:#fff}.nav-subgroup summary{color:#bdd0dc}.nav-subchildren{border-left-color:#31536c}.main{background:linear-gradient(90deg,#080e18 0%,#0a111d 60%,#09111c 100%)}.layout main{max-width:1560px;padding:24px clamp(20px,4vw,64px) 78px}.topline{position:sticky;top:0;z-index:4;margin:0 -1px 24px;padding:10px 0 12px;border-bottom:1px solid #20354a;background:rgba(9,16,27,.92);backdrop-filter:blur(8px);font-size:10px;color:#7891a5;letter-spacing:.16em}.topline strong{color:var(--accent);font-size:12px}.breadcrumbs{margin-bottom:18px;color:#7691a7;font-size:12px}.breadcrumbs a{color:#8fdcf2}
.hero{position:relative;overflow:hidden;border:1px solid #2a4a62;border-top:3px solid var(--accent);background:linear-gradient(120deg,#0f2436,#0e1c2c 70%);padding:28px clamp(20px,4vw,42px);margin-bottom:22px}.hero:after{content:'TODONE / OFFLINE';position:absolute;right:22px;top:19px;color:#365b72;font:10px/1 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:.16em}.hero h1{max-width:980px;font-size:clamp(34px,4.6vw,62px);line-height:1.02;margin:10px 0 14px;color:#f7fbff}.hero p,.lead{max-width:930px;color:#c5d6e3}.eyebrow,.kicker{color:var(--accent-warm);font-size:10px;letter-spacing:.18em}.source-note{color:#7891a5;font-size:12px}.section-head{align-items:center;margin:30px 0 12px;border-bottom:1px solid #22394f;padding-bottom:9px}.section-head h2{margin:0;color:#f0f7fb}.section-head>a{font-size:12px;color:var(--accent)}h1,h2,h3,h4{color:#f1f7fb}h2{font-size:24px;border-bottom-color:#263e55}h3{font-size:17px}
.stats,.grid,.catalog-grid,.split{gap:1px;border:1px solid var(--line);background:var(--line)}.stat,.card,.catalog-card,.callout,.step-card,.state-card{border:0;border-left:3px solid var(--line-strong);background:var(--surface);box-shadow:none;padding:16px}.stat .metric,.metric{color:var(--accent);font-size:30px}.stat .label{color:#a6bdcd;font-size:11px}.catalog-card{min-height:110px}.catalog-card h3{color:#f5f9fc}.catalog-card p{color:#9eb4c5}.catalog-card:hover{background:var(--surface-3);border-left-color:var(--accent)}
.data-table,.prose table{border:1px solid var(--line);background:#0b1624}.data-table th,.prose th{background:#142a40;color:#dff5fb;text-transform:none}.data-table td,.prose td{border-bottom-color:#20384e}.prose blockquote{border-left-color:var(--accent);background:#0d2435}.prose pre,pre{border:1px solid #29455b;background:#07101a}.toc{border:1px solid var(--line);background:#0c1928}.diagram{border:1px solid #38536a;background:#f3f7fb;padding:10px}.diagram-caption{color:#6d859a}.warning,.error,.problem,.ok{border-radius:0;border-left-width:4px}
.process-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;border:1px solid var(--line);background:var(--line);margin:0 0 18px}.process-metric{--metric-accent:var(--accent);border-left:4px solid var(--metric-accent);background:#0e1b2b;padding:13px 15px;display:grid;grid-template-columns:auto 1fr;column-gap:9px;align-items:baseline}.process-metric--flow{--metric-accent:var(--flow)}.process-metric--flow-step{--metric-accent:var(--flow-step)}.process-metric--type{--metric-accent:var(--type)}.process-metric--role{--metric-accent:var(--role)}.process-metric__value{grid-row:span 2;color:var(--metric-accent);font:800 28px/1 ui-monospace,SFMono-Regular,Consolas,monospace}.process-metric__label{color:#edf6fb;font-weight:800;font-size:13px}.process-metric small{color:#7892a6;font-size:10px}.process-guide{border:1px solid var(--line-strong);border-left:5px solid var(--accent-warm);background:#0d1a29;padding:16px 18px}.process-guide__title strong{font-size:18px;color:#fff}.process-grammar{margin:13px 0;padding:10px 0;border-top:1px solid #20394f;border-bottom:1px solid #20394f}.kind-key,.legend-item{background:#0a1624;border-color:var(--key-color,var(--line-strong));padding:4px 8px}.process-legend{gap:4px}.legend-item{color:#b9cfdd}
.process-page{max-width:1380px}.process-filters{position:sticky;top:48px;z-index:3;background:#0c1725;border:1px solid var(--line-strong);border-left:5px solid var(--accent);padding:12px;box-shadow:0 8px 24px rgba(0,0,0,.18)}.process-filter-field label{color:#86a0b4}.process-filter-field input,.process-filter-field select{border-color:#355671;background:#07111d;padding:9px 10px}.process-filter-reset{border-color:var(--accent);background:#103343;color:#c9f5f4}.process-filter-status{font:11px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace;color:#8aa4b8}.process-page .unified-root__head{border:1px solid #3d5d75;border-left:5px solid var(--accent-warm);background:#111f30;padding:16px 18px}.process-page .unified-root__title{font-size:24px;letter-spacing:-.02em}.process-page .unified-root__purpose{color:#91aabd}.process-page .process-flow-tree{margin-left:20px;padding:16px 0 10px 28px;border-left:2px solid #315169;gap:12px}
.process-flow{border-left:5px solid var(--flow);background:transparent}.process-flow>summary{border:1px solid #2d4b63;border-left:0;background:#102238;padding:13px 15px;transition:background .15s}.process-flow>summary:hover{background:#153047}.process-flow[open]>summary{border-bottom-color:var(--flow);background:#132b41}.process-flow .unified-flow__body{border-left:1px solid #2a475d;background:#0a1624;padding:12px 0 10px 24px}.process-flow-intro{font-size:13px;color:#c9d9e5;margin-bottom:12px}.process-flow .unified-flow__steps{gap:8px;border-left:2px solid #355970;padding-left:14px}.process-flow-number{background:var(--flow);color:#06131b;width:32px;height:32px}.process-flow .process-kind-tag{color:var(--flow);border-color:var(--flow)}
.process-entity-line{border:1px solid #2b475d;border-left:4px solid var(--entity-accent);background:#0f2032;padding:12px 14px}.process-entity-line__head>a{font-size:19px}.process-entity-line__purpose{color:#b8cad7}.process-entity-line__meta{gap:8px}.process-open-entity{color:var(--accent);text-transform:uppercase;letter-spacing:.08em}.process-entity-line__links{gap:5px;align-items:flex-start}.process-resource-summary{background:#0b1725}.process-resource-summary>summary{color:#bad0dc}.process-resource-summary__body{background:#081421}
.process-step{border-color:#2a485a;border-left:4px solid var(--flow-step);background:#0d1b2a}.process-step>summary{background:#102438;padding:11px 13px}.process-step>summary:hover{background:#143148}.process-step[open]>summary{border-bottom-color:var(--flow-step);background:#143044}.process-step .unified-step__title strong{font-size:17px}.process-step-number{width:28px;height:28px;background:var(--flow-step)}.process-step .unified-step__body{background:#091521;padding:14px 15px 17px 46px}.process-step-brief{font-size:13px;color:#cadbe6}.process-facts{border-color:#29465c}.process-fact{border-color:#29465c;background:#0d1b2a}.process-fact dt{color:#7993a7}.process-fact dd{color:#dfebf2}.process-resource-groups{gap:1px;background:#29465c;border:1px solid #29465c}.process-resource-group{background:#0d1a29;padding:0}.process-resource-summary{border:0;border-left:3px solid var(--resource-color)}.decision-tree{border-color:#6b5d8d;border-left-color:var(--role);background:#171b31}.decision-tree__body{border-left-color:#6b5d8d}.process-provenance{border-top-color:#29465c}.process-provenance h4{color:#b4c8d6}
.unified-relations{border-top-color:#29465c}.unified-relations__label{color:#7993a7}.unified-link{background:#0a1b29;border-color:var(--link-color)}.unified-link:hover{background:#14354a;border-color:#fff}.entity-chip{border-color:#3b5a70;background:#0b2232;color:#bcebf4}.entity-inline-details,.json-details,.raw-details{border-color:#2b475d;background:#0c1928}.entity-inline-details>summary,.json-details summary,.raw-details summary{color:var(--accent)}
.entity-group,.entity-node{border-color:#28445a;background:#0d1a29}.entity-group>summary,.entity-node>summary{background:#0f2133}.entity-group[open]>summary,.entity-node[open]>summary{background:#132b40}.entity-group__body,.entity-node__body{background:#091521}.entity-subgroup{border-left-color:var(--entity-accent)}.entity-card{background:#0f2031;border-color:var(--entity-accent)}.entity-card__name a{color:#f1f8fc}.entity-card__purpose{color:#b3c7d4}.entity-card__technical{color:#7691a6}
footer{border-top-color:#20384e;color:#6e879c}.process-resource-branch{border-left:5px solid var(--skill);background:#0c1928;margin-top:14px}.process-resource-branch>summary{background:#102438}.process-resource-map{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:#29465c;border:1px solid #29465c;margin-top:0}.process-resource-panel{--resource-panel-color:var(--skill);background:#0b1724;border-top:3px solid var(--resource-panel-color);min-width:0}.process-resource-panel--skill{--resource-panel-color:var(--skill)}.process-resource-panel--template{--resource-panel-color:var(--template)}.process-resource-panel__head{padding:14px 15px;border-bottom:1px solid #29465c}.process-resource-panel__head h3{margin:5px 0;color:#f3f8fb}.process-resource-panel__head p{margin:0;color:#9eb5c4;font-size:12px}.process-resource-panel__head code{color:var(--resource-panel-color)}.process-resource-list{display:grid;gap:1px;background:#29465c}.process-resource-row{--entity-accent:var(--ui-border-strong);background:#0e1d2c;padding:10px 12px;border-left:3px solid var(--entity-accent)}.process-resource-row.entity-kind--skill{--entity-accent:var(--skill)}.process-resource-row.entity-kind--template{--entity-accent:var(--template)}.process-resource-row__name{display:flex;align-items:center;gap:8px;min-width:0}.process-resource-row__name>a{color:#edf7fb;font-weight:800;overflow-wrap:anywhere}.process-resource-row__status{display:flex;align-items:flex-start;gap:7px;flex-wrap:wrap;margin-top:5px}.resource-status{font:10px/1.3 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:.02em;padding:2px 5px;border-left:2px solid var(--entity-accent);color:#b6cbd8;background:#0a1724}.resource-status--used{color:#b9f2e2}.resource-status--inventory{color:#ffd79c;border-left-color:var(--template)}.process-resource-row__consumers{display:flex;flex-wrap:wrap;gap:4px}.process-resource-row__consumers .unified-link{font-size:10px;padding:2px 5px}.nav-subgroup>summary{border-left:2px solid #31536c;padding-left:8px}.nav-subgroup[open]>summary{border-left-color:var(--accent)}.nav-subgroup .nav-count{color:#6e91a7}@media(max-width:900px){.layout{display:block}.sidebar{position:static;box-shadow:none}.topline{position:static}.process-filters{position:static}.process-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.process-resource-map{grid-template-columns:1fr}}@media(max-width:560px){.process-metrics{grid-template-columns:1fr}.hero:after{display:none}.process-guide__title{display:grid;gap:5px}}
"""

def _html_css_compact():
    """Critical inline CSS for detail-page previews.

    The complete design system is still written to assets/app.css. Detail
    pages only need this smaller fallback in the sandbox viewer; primary map
    pages keep the full inline stylesheet. This avoids copying ~48 KB of CSS
    into every one of the 462 generated files.
    """
    return """*{box-sizing:border-box}html,body{margin:0;background:#070c14;color:#edf5fb;font:14px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*,*::before,*::after{border-radius:0!important}a{color:#8cdbf5;text-decoration:none}a:hover{color:#fff}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:2px solid #f5c85d;outline-offset:2px}.layout{display:grid;grid-template-columns:286px minmax(0,1fr);min-height:100vh}.sidebar{background:#09121f;border-right:1px solid #20354a;padding:20px 14px;position:sticky;top:0;height:100vh;overflow:auto}.brand{display:block;color:#fff;font-size:21px;font-weight:800;margin:0 8px 4px}.brand small{display:block;color:#7994aa;font-size:10px;letter-spacing:.18em}.sidebar .hint{color:#87a0b5;font-size:11px;margin:0 8px 18px}.sidebar label{display:block;color:#708ba1;font-size:10px;letter-spacing:.14em;margin:14px 8px 6px}.sidebar input{width:100%;padding:9px 10px;border:1px solid #29445b;background:#07101b;color:#fff;font:inherit}.sidebar nav{display:grid;gap:3px;margin-top:14px}.nav-group,.nav-subgroup{border:0;background:transparent}.nav-group summary,.nav-subgroup summary{list-style:none;cursor:pointer;color:#dce7ef;padding:8px;border-left:3px solid transparent;font-weight:750}.nav-group summary::-webkit-details-marker,.nav-subgroup summary::-webkit-details-marker{display:none}.nav-group[open]>summary,.nav-subgroup[open]>summary{border-left-color:#70e4e1}.nav-group summary:before,.nav-subgroup summary:before{content:'›';color:#f5c85d;margin-right:6px}.nav-group[open]>summary:before,.nav-subgroup[open]>summary:before{content:'⌄'}.nav-count{float:right;color:#6f8aa0;font-size:11px}.nav-children{padding:3px 0 6px 12px;border-left:1px solid #29455c;margin-left:8px}.nav-children a,.nav-subchildren a{display:block;padding:5px 8px;color:#adc1d0;font-size:12px}.nav-children a.active{background:#123246;border-left:2px solid #70e4e1;color:#fff}.nav-meta{display:block;color:#718ba0;font-size:10px;overflow-wrap:anywhere}.nav-meta--hint{padding:5px 8px}.nav-subchildren{padding:2px 0 4px 8px;border-left:1px solid #31536c;margin-left:7px}.main{min-width:0;background:#0a111d}.layout main{max-width:1560px;padding:24px clamp(18px,4vw,60px) 70px}.topline{display:flex;justify-content:space-between;gap:18px;padding:10px 0 12px;border-bottom:1px solid #20354a;margin-bottom:20px;color:#7891a5;font-size:10px;letter-spacing:.14em}.topline strong{color:#70e4e1}.breadcrumbs{color:#7691a7;font-size:12px;margin-bottom:18px}.breadcrumbs a{color:#8fdcf2}.hero{border:1px solid #2a4a62;border-top:3px solid #70e4e1;background:#102238;padding:26px clamp(18px,4vw,40px);margin-bottom:22px}.hero h1{font-size:clamp(32px,4.5vw,58px);line-height:1.04;color:#f7fbff;margin:10px 0 14px}.hero p,.lead{color:#c5d6e3;max-width:930px}.eyebrow,.kicker{color:#f5c85d;font-size:10px;font-weight:800;letter-spacing:.18em}.source-note{color:#7891a5;font-size:12px}h1,h2,h3,h4{color:#f1f7fb}h2{font-size:24px;border-bottom:1px solid #263e55;padding-bottom:8px;margin:30px 0 12px}h3{font-size:17px}.doc-meta{display:flex;flex-wrap:wrap;align-items:center;gap:8px;color:#9bb0c4}.pill,.badge,.entity-count,.entity-chip,.unified-link{display:inline-block;border:1px solid #3b5a70;padding:3px 7px;background:#0b2232;color:#bcebf4;font-size:11px}.pill.good{border-color:#32896f;color:#b6ffe3}.stats,.grid,.catalog-grid,.split{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:1px;border:1px solid #263d54;background:#263d54}.stat,.card,.catalog-card,.callout,.step-card,.state-card{border:0;border-left:3px solid #41627c;background:#0d1827;padding:15px}.catalog-card{display:block;min-height:90px;color:#edf5fb}.catalog-card h3{margin:0 0 6px}.catalog-card p{margin:0;color:#9eb4c5}.catalog-card:hover{background:#162b42;border-left-color:#70e4e1}.metric{display:block;color:#70e4e1;font-size:28px;font-weight:800}.data-table,.prose table{border-collapse:separate;border-spacing:0;width:100%;border:1px solid #263d54;background:#0b1624;margin:14px 0}.data-table th,.data-table td,.prose th,.prose td{padding:9px 11px;text-align:left;vertical-align:top;border-bottom:1px solid #20384e;color:#c6d5e4}.data-table th,.prose th{background:#142a40;color:#dff5fb}.prose{max-width:1030px}.prose p{max-width:930px}.prose blockquote{border-left:4px solid #70e4e1;background:#0d2435;padding:10px 15px}.prose pre,pre{overflow:auto;white-space:pre-wrap;background:#07101a;color:#dce8f3;border:1px solid #29455b;padding:14px}.prose code,code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;color:#c8f7e8;background:#0b2430;border:1px solid #235165;padding:2px 4px}.toc,.compat,.raw-details,.json-details{border:1px solid #2b475d;background:#0c1928;padding:12px}.toc summary,.compat summary,.raw-details summary,.json-details summary{cursor:pointer;color:#70e4e1;font-weight:750}.callout{border-left-color:#f5c85d}.warning{border-left:4px solid #f5c85d;background:#3b2b15;padding:11px 14px}.error,.problem{border-left:4px solid #ff7e92;background:#401d27;padding:11px 14px}.ok{border-left:4px solid #63e3c8;background:#10342f;padding:11px 14px}.flow-layout{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(280px,.85fr);gap:18px}.diagram{overflow:auto;border:1px solid #38536a;background:#f3f7fb;padding:10px}.diagram svg{display:block;max-width:100%;height:auto}.diagram-empty{border:1px solid #38536a;background:#102238;padding:22px}.step-list{display:grid;gap:10px}.step-card{display:grid;grid-template-columns:44px 1fr;gap:13px}.step-no{width:36px;height:36px;display:grid;place-items:center;background:#79c5a8;color:#07111c;font-weight:900}.step-card p{margin:5px 0;color:#c6d5e3}.state-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1px;background:#263d54}.state-card h4{margin:0 0 5px}.entity-group,.entity-node{border:1px solid #28445a;background:#0d1a29}.entity-group>summary,.entity-node>summary{display:flex;gap:10px;cursor:pointer;padding:12px;border-left:4px solid #41627c;list-style:none}.entity-group>summary::-webkit-details-marker,.entity-node>summary::-webkit-details-marker{display:none}.entity-group__title,.entity-node__title{flex:1}.entity-group__title strong,.entity-node__title strong{display:block}.entity-group__title small,.entity-node__title small{display:block;color:#91a8bd;font-size:12px}.entity-group__body,.entity-node__body{padding:0 14px 14px;background:#091521}.entity-card{display:block;border:1px solid #41627c;border-left:4px solid #70e4e1;background:#0f2031;padding:11px 13px;margin-top:9px;color:#edf5fb}.entity-card__head{display:flex;justify-content:space-between;gap:10px}.entity-card__name{font-size:16px;font-weight:800}.entity-card__purpose{color:#b3c7d4;font-size:13px}.entity-card__technical{display:block;color:#7691a6;font:10px ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}.entity-inline-details{margin-top:10px;border-top:1px solid #2b475d;padding-top:8px}.entity-inline-details>summary{cursor:pointer;color:#70e4e1;font-weight:750}.entity-subgroup{border-left:2px solid #41627c;margin:10px 0;padding-left:10px}.entity-subgroup>summary{cursor:pointer;color:#dcebf5;font-weight:700}footer{border-top:1px solid #20384e;padding-top:16px;margin-top:50px;color:#6e879c;font-size:11px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}@media(max-width:900px){.layout{display:block}.sidebar{position:static;height:auto}.flow-layout{grid-template-columns:1fr}.layout main{padding:20px 15px 52px}}"""


def _html_js(*, process_page=False):
    base = """(function(){var input=document.getElementById('search');if(!input)return;var items=[].slice.call(document.querySelectorAll('[data-search-item]'));var empty=document.getElementById('search-empty');input.addEventListener('input',function(){var q=input.value.trim().toLowerCase();var visible=0;items.forEach(function(item){var hit=!q||item.textContent.toLowerCase().indexOf(q)!==-1;item.hidden=!hit;if(hit){visible++;var parent=item.parentElement;while(parent){if(parent.tagName==='DETAILS')parent.open=true;parent=parent.parentElement;}}});if(empty)empty.hidden=visible!==0;});})();"""
    if not process_page:
        return base
    return base + """
(function(){var root=document.querySelector('[data-process-filters]');if(!root)return;var search=root.querySelector('[data-process-search]');var process=root.querySelector('[data-process-select]');var type=root.querySelector('[data-type-select]');var role=root.querySelector('[data-role-select]');var reset=root.querySelector('[data-process-reset]');var flows=[].slice.call(document.querySelectorAll('.process-flow'));var status=document.querySelector('[data-process-status]');var empty=document.querySelector('[data-process-empty]');function has(list,value){return !value||(','+(list||'')+',').indexOf(','+value+',')!==-1}function apply(){var q=(search.value||'').trim().toLowerCase();var pv=process.value||'';var tv=type.value||'';var rv=role.value||'';var flowCount=0;var stepCount=0;flows.forEach(function(flow){var flowText=(flow.getAttribute('data-search-text')||'').toLowerCase();var flowProcess=flow.getAttribute('data-process-id')||'';var processOk=!pv||flowProcess===pv;var steps=[].slice.call(flow.querySelectorAll('.process-step'));var stepHits=0;steps.forEach(function(step){var stepText=(step.getAttribute('data-search-text')||'').toLowerCase();var hit=(!q||stepText.indexOf(q)!==-1||flowText.indexOf(q)!==-1)&&has(step.getAttribute('data-type-ids'),tv)&&has(step.getAttribute('data-role-ids'),rv);step.hidden=!hit;if(hit)stepHits++;});var flowHit=(!q||flowText.indexOf(q)!==-1||stepHits>0)&&processOk&&(!tv||stepHits>0)&&(!rv||stepHits>0);flow.hidden=!flowHit;if(flowHit){if(q||pv||tv||rv)flow.open=true;flowCount++;stepCount+=stepHits||steps.length;}});if(status)status.textContent='Показано процессов: '+flowCount+' · шагов: '+stepCount;if(empty)empty.classList.toggle('is-visible',flowCount===0)}[search,process,type,role].forEach(function(control){if(control)control.addEventListener('input',apply);if(control)control.addEventListener('change',apply)});if(reset)reset.addEventListener('click',function(){search.value='';process.value='';type.value='';role.value='';apply()});apply()})();"""


def _page_shell(title, body, *, page_path, bundle, nav=True):
    root = posixpath.relpath("index.html", posixpath.dirname(page_path) or ".")
    css = posixpath.relpath("assets/app.css", posixpath.dirname(page_path) or ".")
    js = posixpath.relpath("assets/app.js", posixpath.dirname(page_path) or ".")
    nav_html = ""
    if nav:
        page_map = _entity_page_map(bundle)
        doc_map = _document_page_map(bundle)

        def nav_link(label, target, *, all_link=False, description=None, technical=None):
            relative = posixpath.relpath(target, posixpath.dirname(page_path) or ".")
            active = page_path == target
            klass = " class=\"nav-all\"" if all_link else (" class=\"active\"" if active else "")
            title = (' title="%s"' % html.escape(str(description), quote=True)) if description else ""
            content = '<span class="nav-label">%s</span>' % html.escape(str(label))
            if technical and str(technical) != str(label):
                content += '<small class="nav-meta">%s</small>' % html.escape(str(technical))
            return '<a%s href="%s"%s>%s</a>' % (
                klass, html.escape(relative, quote=True), title, content)

        def unpack_entry(entry):
            values = tuple(entry)
            return (values + (None, None, None))[:4]

        def entry_target(entry):
            return unpack_entry(entry)[1]

        def render_entry(entry):
            child_label, child_target, description, technical = unpack_entry(entry)
            return nav_link(child_label, child_target, description=description, technical=technical)

        def nav_target_matches(target):
            target = str(target)
            return page_path == target or page_path == target.split("#", 1)[0]

        def nav_subgroup(label, entries):
            active_entries = [entry for entry in entries if nav_target_matches(entry_target(entry))]
            active = bool(active_entries)
            # Keep the sidebar a map, not a second full catalog. Long groups
            # expose their count and the section link; only the active item is
            # expanded when a detail page is being read.
            if len(entries) > 8:
                pinned_entries = [entry for entry in entries
                                  if "bundle" in str(unpack_entry(entry)[0]).lower()
                                  or "bundle" in str(unpack_entry(entry)[3]).lower()]
                visible_entries = []
                for entry in active_entries + pinned_entries + entries[:1]:
                    if entry not in visible_entries:
                        visible_entries.append(entry)
                summary_note = '<small class="nav-meta nav-meta--hint">Откройте раздел для полного списка</small>'
            else:
                visible_entries = entries
                summary_note = ""
            children = "".join(render_entry(entry) for entry in visible_entries)
            if summary_note:
                children += summary_note
            opened = " open" if active else ""
            return '<details class="nav-subgroup"%s><summary><span>%s</span><span class="nav-count">%d</span></summary><div class="nav-subchildren">%s</div></details>' % (
                opened, html.escape(label), len(entries), children)

        def nav_group(label, target, entries, *, subgroups=None):
            active_entries = list(entries)
            if subgroups:
                active_entries.extend(entry for _, group_entries in subgroups for entry in group_entries)
            active = nav_target_matches(target) or any(nav_target_matches(entry_target(entry)) for entry in active_entries)
            children = nav_link("Открыть раздел", target, all_link=True)
            if subgroups:
                children += "".join(nav_subgroup(group_label, group_entries)
                                     for group_label, group_entries in subgroups)
            else:
                if len(entries) > 12:
                    visible_entries = [entry for entry in entries if nav_target_matches(entry_target(entry))]
                    children += "".join(render_entry(entry) for entry in visible_entries)
                    children += '<small class="nav-meta nav-meta--hint">%d записей · полный список в разделе</small>' % len(entries)
                else:
                    children += "".join(render_entry(entry) for entry in entries)
            opened = " open" if active else ""
            return '<details class="nav-group"%s><summary><span>%s</span><span class="nav-count">%d</span></summary><div class="nav-children">%s</div></details>' % (
                opened, html.escape(label), len(entries), children)

        docs_entries = [( _doc_summary(document), target)
                        for document in bundle.get("documents") or []
                        if (target := doc_map.get(document.get("canonical_path")))]
        flow_entities = [entity for entity in bundle.get("entities") or [] if entity.get("kind") == "flow"]
        process_entries = [((entity.get("normalized") or {}).get("name") or entity["entity_id"],
                            "processes/index.html#process-%s" % _slug(entity["entity_id"]),
                            "Полный жизненный цикл процесса: шаги, виды задач, agents, роли и skills.",
                            entity["entity_id"].split(":", 1)[-1])
                           for entity in flow_entities]
        nav_entity_by_id = {entity.get("entity_id"): entity for entity in bundle.get("entities") or []}
        nav_relations = bundle.get("relations") or []

        def nav_incoming(target_id, *, relation_kinds=None, source_kinds=None):
            result = []
            allowed_relations = set(relation_kinds or {"uses", "contains", "implements", "documents"})
            allowed_sources = set(source_kinds or ())
            for relation in nav_relations:
                if relation.get("to") != target_id or relation.get("kind") not in allowed_relations:
                    continue
                source_id = relation.get("from")
                source = nav_entity_by_id.get(source_id)
                if source and (not allowed_sources or source.get("kind") in allowed_sources):
                    result.append(source_id)
            return sorted(set(result))

        skill_entries = []
        for entity in sorted((item for item in bundle.get("entities") or [] if item.get("kind") == "skill"),
                             key=lambda item: str((item.get("normalized") or {}).get("name") or item["entity_id"]).lower()):
            normalized = entity.get("normalized") or {}
            skill_id = entity["entity_id"]
            if skill_id == "skill:root":
                process_usage = nav_incoming(skill_id, source_kinds={"flow"})
                type_usage = nav_incoming(skill_id, source_kinds={"type"})
                usage = "общий router · %d процессов / %d видов задач" % (len(process_usage), len(type_usage))
            else:
                usage = "child-skill · через общий router"
            skill_entries.append(((normalized.get("name") or skill_id), page_map[skill_id],
                                  "Навык исполнения: %s" % usage, usage))
        template_entries = []
        for entity in sorted((item for item in bundle.get("entities") or [] if item.get("kind") == "template"),
                             key=lambda item: str((item.get("normalized") or {}).get("title") or item["entity_id"]).lower()):
            normalized = entity.get("normalized") or {}
            template_id = entity["entity_id"]
            type_usage = nav_incoming(template_id, source_kinds={"type"})
            usage = "виды задач: %d" % len(type_usage) if type_usage else "не подключён к виду задачи"
            template_entries.append(((normalized.get("title") or template_id), page_map[template_id],
                                     "Стартовая форма: %s" % usage, usage))
        contract_entries = []
        contract_groups = defaultdict(list)
        seen_contract_targets = set()
        group_labels = {
            "AUTODOC": "AUTODOC_ · каталог документации",
            "DOC": "DOC_ · документация",
            "FLOW": "FLOW_ · маршруты",
            "TASK": "TASK_ · задачи",
            "WORKSPACE": "WORKSPACE_ · рабочие области",
            "JIRA": "JIRA_ · внешние зеркала",
            "PREZA": "PREZA_ · миграционная совместимость",
            "ARTEFACT": "ARTEFACT_ · артефакты",
            "COMMENT": "COMMENT_ · рабочая лента",
            "REF": "REF_ · указатели",
            "SRC": "SRC_ · источники",
        }
        for entity in bundle.get("entities") or []:
            if entity.get("kind") not in ("schema", "template"):
                continue
            normalized = entity.get("normalized") or {}
            technical = normalized.get("schema_id") or entity["entity_id"].split(":", 2)[-1]
            label = normalized.get("title") or technical
            description = normalized.get("description") or None
            if entity.get("kind") == "template":
                group_key = "Шаблоны"
                group_label = "Шаблоны · стартовые формы"
                label = normalized.get("title") or "Шаблон " + entity["entity_id"].split(":", 2)[-1]
                technical = normalized.get("path") or technical
            else:
                group_key = _schema_identity(technical).split("_", 1)[0] or "OTHER"
                if group_key not in group_labels:
                    group_key = "OTHER"
                group_label = group_labels.get(group_key, "Прочие контракты")
            target = page_map[entity["entity_id"]]
            if entity.get("kind") == "schema" and target in seen_contract_targets:
                continue
            seen_contract_targets.add(target)
            entry = (label, target, description, technical)
            contract_entries.append(entry)
            contract_groups[group_key].append(entry)
        contract_subgroups = [(group_labels.get(key, "Шаблоны · стартовые формы" if key == "Шаблоны" else "Прочие контракты"),
                               sorted(entries, key=lambda item: (str(item[0]).lower(), str(item[3]).lower())))
                              for key, entries in sorted(contract_groups.items(), key=lambda item: item[0])]
        project_entries = [("Архитектура", "architecture/index.html"), ("Сущности", "entities/index.html"),
                           ("Источники", "sources/index.html")]
        control_entries = [("Аудит и совместимость", "audit/index.html"), ("Восстановление", "reconstruction/index.html")]
        agent_entries = [((entity.get("normalized") or {}).get("name") or entity["entity_id"],
                          page_map[entity["entity_id"]]) for entity in bundle.get("entities") or [] if entity.get("kind") == "agent"]
        nav_body = nav_link("Обзор проекта", "index.html", all_link=True)
        nav_body += nav_group("Документация", "docs/index.html", sorted(docs_entries, key=lambda item: item[0]))
        nav_body += nav_group("Проект", "architecture/index.html", project_entries)
        sorted_process_entries = sorted(process_entries, key=lambda item: item[0])
        sorted_skill_entries = [("Все навыки", "skills/index.html", "Общий инвентарь skills и child-skills.", "inventory")] + sorted(skill_entries, key=lambda item: item[0])
        sorted_template_entries = [("Все templates", "templates/index.html", "Инвентарь стартовых форм.", "inventory")] + sorted(template_entries, key=lambda item: item[0])
        nav_body += nav_group("Процессы", "processes/index.html", sorted_process_entries,
                               subgroups=[("Lifecycle-процессы", sorted_process_entries),
                                          ("Skills, общие для процессов", sorted_skill_entries),
                                          ("Templates видов задач", sorted_template_entries)])
        nav_body += nav_group("Роли и агенты", "agents/index.html", sorted(agent_entries, key=lambda item: item[0]))
        nav_body += nav_group("Схемы контрактов", "schemas/index.html", contract_entries,
                               subgroups=contract_subgroups)
        nav_body += nav_group("Контроль", "audit/index.html", control_entries)
        nav_html = ("<aside class=\"sidebar\"><a class=\"brand\" href=\"%s\">todone <small>офлайн-каталог</small></a><p class=\"hint\">Понятное представление проекта, документации и процессов.</p><label for=\"search\">Поиск по этой странице</label><input id=\"search\" type=\"search\" placeholder=\"Найти документ или раздел\"><nav>%s</nav></aside>" %
                    (html.escape(root, quote=True), nav_body))
    digest = bundle.get("canonical_digest", "sha256:unknown")
    full_inline_pages = {
        "index.html", "architecture/index.html", "entities/index.html",
        "processes/index.html", "audit/index.html", "sources/index.html", "reconstruction/index.html",
        "docs/index.html", "flows/index.html", "types/index.html", "schemas/index.html",
        "templates/index.html", "skills/index.html", "agents/index.html", "commands/index.html",
    }
    inline_css = _html_css() if page_path in full_inline_pages else _html_css_compact()
    inline_js = _html_js(process_page=page_path == "processes/index.html")
    return "<!doctype html><html lang=\"ru\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta name=\"color-scheme\" content=\"dark\"><title>%s · todone</title><link rel=\"stylesheet\" href=\"%s\"><style>%s</style></head><body data-bundle-digest=\"%s\"><a class=\"skip\" href=\"#content\">К содержимому</a><div class=\"layout\">%s<main id=\"content\"><div class=\"topline\"><span><strong>TODONE</strong> · каталог знаний</span><span>локальная копия · без сети</span></div><div class=\"breadcrumbs\"><a href=\"%s\">Главная</a> <span aria-hidden=\"true\">/</span> %s</div>%s<footer><div class=\"footer-grid\"><span>Собрано todone autodoc · digest %s</span><span>Все исходники остаются доступными для проверки</span></div></footer></main></div><script>%s</script><script src=\"%s\"></script></body></html>" % (
        html.escape(title), html.escape(css, quote=True), inline_css,
        html.escape(digest, quote=True), nav_html, html.escape(root, quote=True),
        html.escape(title), body, html.escape(digest), inline_js, html.escape(js, quote=True))


def _write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _href(from_page, to_page):
    return posixpath.relpath(to_page, posixpath.dirname(from_page) or ".")


def _entity_page_map(bundle):
    """Map every entity to one primary human-facing containment page.

    Technical projections may share a page: registry and JSON Schema records
    with the same logical contract resolve to one schema detail page; skills
    resolve to their canonical Markdown document; source files resolve to the
    consolidated provenance table. The bundle still retains every entity and
    relation, but the HTML no longer creates a page for each projection.
    """
    entities = list(bundle.get("entities") or [])
    schema_primary = {}
    for entity in entities:
        if entity.get("kind") != "schema":
            continue
        normalized = entity.get("normalized") or {}
        identity = _schema_identity(normalized.get("schema_id") or normalized.get("name") or entity.get("entity_id"))
        current = schema_primary.get(identity)
        # Prefer the registry view as the stable URL when both registry and
        # file-backed JSON Schema representations exist.
        if current is None or (
            str(entity.get("entity_id", "")).startswith("schema:registry:") and
            not str(current.get("entity_id", "")).startswith("schema:registry:")
        ):
            schema_primary[identity] = entity

    document_by_id = {item.get("document_id"): item for item in bundle.get("documents") or []}
    type_entity_ids = {item.get("entity_id") for item in entities if item.get("kind") == "type"}
    result = {}
    for entity in entities:
        ident = entity.get("entity_id")
        kind = entity.get("kind")
        if kind == "task":
            parts = ident.split(":")
            page = "tasks/%s/%s/%s.html" % (_slug(parts[1] if len(parts) > 1 else "workspace"),
                                              _slug(parts[2] if len(parts) > 2 else "queue"),
                                              _slug(parts[-1]))
        elif kind == "document" or kind == "markdown":
            normalized = entity.get("normalized") or {}
            canonical_path = normalized.get("canonical_path") or ""
            match = re.match(r"^types/([^/]+)/instruction\.md$", canonical_path)
            type_id = "type:%s" % match.group(1) if match else None
            page = ("types/%s.html" % _slug(type_id.split(":", 1)[-1])
                    if type_id in type_entity_ids else
                    "docs/%s.html" % _slug(ident.replace(":", "-")))
        elif kind == "flow":
            page = "flows/%s.html" % _slug(ident.split(":", 1)[-1])
        elif kind == "flow_step":
            normalized = entity.get("normalized") or {}
            page = "flows/%s.html#step-%s" % (_slug(normalized.get("flow_id") or "flow"),
                                               _slug("%s:%s" % (normalized.get("flow_id"), normalized.get("id"))))
        elif kind == "type":
            page = "types/%s.html" % _slug(ident.split(":", 1)[-1])
        elif kind == "schema":
            normalized = entity.get("normalized") or {}
            identity = _schema_identity(normalized.get("schema_id") or normalized.get("name") or ident)
            primary = schema_primary.get(identity, entity)
            primary_id = primary.get("entity_id", ident)
            if str(primary_id).startswith("schema:registry:"):
                page = "schemas/registry-%s.html" % _slug(primary_id.split(":", 2)[-1])
            else:
                page = "schemas/%s.html" % _slug(primary_id.split(":", 1)[-1])
        elif kind == "template":
            page = "templates/%s.html" % _slug(ident.split(":", 1)[-1])
        elif kind == "skill":
            normalized = entity.get("normalized") or {}
            document = document_by_id.get(normalized.get("document_id"))
            if document:
                page = "docs/%s.html" % _slug(document.get("document_id"))
            else:
                page = "skills/index.html#skill-%s" % _slug(ident.split(":", 1)[-1])
        elif kind == "agent":
            page = "agents/%s.html" % _slug(ident.split(":", 1)[-1])
        elif kind == "role":
            normalized = entity.get("normalized") or {}
            role = normalized.get("role") or normalized.get("name") or ident.split(":", 1)[-1]
            page = "agents/index.html#role-%s" % _slug(role)
        elif kind == "source_file":
            normalized = entity.get("normalized") or {}
            page = "sources/index.html#source-%s" % _slug(normalized.get("path") or ident)
        else:
            page = "entities/%s/%s.html" % (_slug(kind or "entity"), _slug(ident))
        result[ident] = page
    return result


def _document_page_map(bundle):
    type_pages = {
        item.get("entity_id"): "types/%s.html" % _slug(item.get("entity_id", "").split(":", 1)[-1])
        for item in bundle.get("entities") or [] if item.get("kind") == "type"
    }
    result = {}
    for item in bundle.get("documents") or []:
        path = item.get("canonical_path") or ""
        match = re.match(r"^types/([^/]+)/instruction\.md$", path)
        type_page = type_pages.get("type:%s" % match.group(1)) if match else None
        result[path] = type_page or "docs/%s.html" % _slug(item.get("document_id"))
    return result


_RU_LABELS = {
    "workspace": "проект", "queue": "очередь", "task": "задача", "document": "документ",
    "markdown": "документ", "flow": "поток", "type": "профиль задачи", "schema": "схема",
    "template": "шаблон", "role": "роль", "tool": "инструмент", "policy": "политика",
    "flow_state": "состояние потока", "flow_step": "шаг потока", "agent": "профиль агента",
    "skill": "навык", "source_file": "исходный файл", "contracts": "контракт",
}
_RU_STATUS = {
    "complete": "полно", "partial": "частично", "blocked": "заблокировано", "read": "прочитано",
    "unknown": "неизвестно", "preserved": "сохранено", "transformed": "преобразовано",
    "deprecated": "устарело", "invalid": "некорректно", "draft": "черновик",
    "ready": "готово", "in_progress": "в работе", "closed": "закрыто", "cancelled": "отменено",
    "parked": "отложено", "mirror": "зеркало",
}


_RU_TYPE_CLASSES = {
    "product": "продуктовая работа",
    "research": "исследование",
    "source": "источник или зеркало",
}


def _ru_kind(value):
    return _RU_LABELS.get(str(value), str(value).replace("_", " "))


def _ru_type_class(value):
    return _RU_TYPE_CLASSES.get(str(value), str(value).replace("_", " "))


def _ru_status(value):
    return _RU_STATUS.get(str(value), str(value).replace("_", " "))


def _status_pill(value):
    status = str(value or "unknown")
    klass = "good" if status in {"complete", "read", "preserved", "transformed", "ready", "closed"} else "bad" if status in {"blocked", "invalid", "cancelled"} else "warn"
    return '<span class="pill %s">%s</span>' % (klass, html.escape(_ru_status(status)))


def _tech_details(title, value, *, open=False):
    opening = " open" if open else ""
    return '<details class="json-details"%s><summary>%s</summary><pre>%s</pre></details>' % (
        opening, html.escape(title), html.escape(_json_dumps(value, pretty=True)))


def _human_value(value):
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, list):
        return ", ".join(_human_value(item) for item in value) or "—"
    if isinstance(value, dict):
        return "; ".join("%s: %s" % (key, _human_value(item)) for key, item in sorted(value.items())) or "—"
    return str(value)


_RU_ROLE_NAMES = {
    "developer": "Разработчик", "researcher": "Исследователь", "reviewer": "Ревьюер",
    "planner": "Планировщик", "tester": "Тестировщик", "writer": "Автор документации",
    "analyst": "Аналитик", "operator": "Оператор", "maintainer": "Сопровождающий",
}
_RU_ROLE_PURPOSES = {
    "developer": "вносит изменения в код и оставляет evidence",
    "researcher": "исследует факты, код и документацию перед решением",
    "reviewer": "проверяет изменение, план или результат и выносит вердикт",
    "planner": "собирает исполнимый план и связывает его с критериями приёмки",
    "tester": "готовит и выполняет проверки, фиксируя воспроизводимое evidence",
    "writer": "документирует реализованное поведение и проверяет рендер",
    "analyst": "формализует вход и отделяет факты от пробелов",
    "operator": "выполняет операционные действия по объявленному контракту",
    "maintainer": "поддерживает проектные контракты и их совместимость",
}
_RU_STEP_NAMES = {
    "intake": "Приём и формализация",
    "research": "Исследование",
    "planning": "Планирование",
    "test-prep": "Подготовка тестов",
    "feature": "Реализация возможности",
    "fix": "Исправление дефекта",
    "small-fix": "Мелкая правка",
    "code-review": "Разбор изменения",
    "plan-audit": "Аудит плана",
    "testing": "Проверка тестами",
    "test-fix": "Исправление тестов",
    "final-testing": "Финальная проверка",
    "documentation": "Документирование",
    "doc": "Проверка документации",
}
_RU_ENTITY_GROUPS = {
    "workspace": ("Проект", "Корень workspace и общая точка навигации."),
    "flow": ("Процессы", "Исполняемые потоки с шагами, gates, решениями и handoff."),
    "type": ("Виды задач", "Профили работы: назначение, поля, стадии, исполнитель и критерии приёмки."),
    "skill": ("Навыки", "Процедурные знания, которые маршрутизируют работу и связывают её с профилями."),
    "schema": ("Runtime-контракты", "Канонические схемы данных, которые читают runtime и валидаторы."),
    "template": ("Стартовые формы", "Шаблоны для создания записей; это не факты runtime."),
    "role": ("Роли", "Разрешённые роли исполнения и их назначение."),
    "agent": ("Профили агентов", "Исполнители с инструментами, границами и return contract."),
    "markdown": ("Документы", "Человекочитаемые Markdown-источники инструкций и знаний."),
    "source_file": ("Канонические файлы", "Полный список исходных файлов, из которых построен каталог."),
    "flow_step": ("Шаги процессов", "Нормализованные шаги, показанные внутри соответствующего потока."),
}


def _catalog_entity_name(entity, *, entities_by_id=None, documents_by_id=None):
    """Return a primary human label for the entity index.

    Technical identifiers are deliberately kept out of this label. They are
    rendered as the secondary provenance line by the entity-card renderer.
    """
    normalized = entity.get("normalized") or {}
    kind = entity.get("kind") or "entity"
    if kind == "workspace":
        return "Проект Todone"
    if kind == "flow":
        return normalized.get("name") or "Процесс «%s»" % normalized.get("id", "без имени")
    if kind == "type":
        return normalized.get("name") or "Профиль «%s»" % normalized.get("id", "без имени")
    if kind == "flow_step":
        step_id = str(normalized.get("type") or normalized.get("id") or entity.get("entity_id", "").split(":")[-1])
        return _RU_STEP_NAMES.get(step_id, "Шаг процесса")
    if kind == "agent":
        role = normalized.get("role") or normalized.get("name") or "исполнитель"
        role_label = _RU_ROLE_NAMES.get(str(role), str(role).replace("_", " ").capitalize())
        type_id = normalized.get("type_id")
        type_entity = (entities_by_id or {}).get("type:%s" % type_id) if type_id else None
        type_name = ((type_entity or {}).get("normalized") or {}).get("name") if type_entity else None
        return "%s%s" % (role_label, " · " + str(type_name) if type_name else "")
    if kind == "role":
        role = normalized.get("role") or normalized.get("name")
        return _RU_ROLE_NAMES.get(str(role), str(role or "Роль").replace("_", " ").capitalize())
    if kind == "skill":
        return str(normalized.get("name") or "Навык")
    if kind in {"schema", "template"}:
        fallback = normalized.get("schema_id") or normalized.get("path") or entity.get("entity_id", "").split(":")[-1]
        return str(normalized.get("title") or normalized.get("contract_title") or fallback)
    if kind == "markdown":
        document = (documents_by_id or {}).get(normalized.get("document_id"))
        return _doc_summary(document) if document else str(normalized.get("canonical_path") or entity.get("entity_id"))
    if kind == "source_file":
        return str(normalized.get("path") or normalized.get("name") or entity.get("entity_id"))
    return str(normalized.get("title") or normalized.get("name") or entity.get("entity_id", "Сущность"))


def _catalog_entity_purpose(entity, *, entities_by_id=None, documents_by_id=None):
    """Return a short Russian purpose/role sentence for the entity card."""
    normalized = entity.get("normalized") or {}
    kind = entity.get("kind") or "entity"
    if kind == "workspace":
        return "Корень проекта: здесь сходятся канонические источники, сущности, связи и generated offline-каталог."
    if kind == "flow":
        count = len(normalized.get("steps") or normalized.get("step_refs") or [])
        return "Исполняемый процесс на %d шаг%s; задаёт порядок работы, gates и переходы." % (
            count, "е" if count == 1 else "ах")
    if kind == "type":
        fields = len(normalized.get("fields") or [])
        agents = len(normalized.get("agent_refs") or [])
        return "Профиль работы: %d пол%s, %d agent-профил%s и набор gates/capabilities." % (
            fields, "е" if fields == 1 else "я" if fields in {2, 3, 4} else "ей",
            agents, "ь" if agents == 1 else "ей")
    if kind == "flow_step":
        return str(normalized.get("brief") or "Шаг процесса с executor, входами, выходами и gate.")
    if kind == "agent":
        role = str(normalized.get("role") or normalized.get("name") or "исполнитель")
        purpose = _RU_ROLE_PURPOSES.get(role, "исполняет объявленный профиль задачи по заданному контракту")
        type_id = normalized.get("type_id")
        type_suffix = (" Тип: %s" % _catalog_entity_name((entities_by_id or {}).get("type:%s" % type_id, {}),
                                                            entities_by_id=entities_by_id,
                                                            documents_by_id=documents_by_id)) if type_id else ""
        return "%s.%s" % (purpose.capitalize().rstrip("."), type_suffix)
    if kind == "role":
        role = str(normalized.get("role") or normalized.get("name") or "")
        return _RU_ROLE_PURPOSES.get(role, "Разрешённая роль исполнения в runtime.").capitalize() + "."
    if kind == "skill":
        parent = normalized.get("parent_skill")
        return "Процедурное знание%s: связывает правила и последовательность действий с рабочими профилями." % (
            " внутри %s" % parent.split(":", 1)[-1] if parent else "")
    if kind == "schema":
        description = str(normalized.get("description") or "").strip()
        if description:
            return description
        return "Канонический runtime-контракт «%s» для хранения, обмена и проверки данных." % (
            normalized.get("schema_id") or normalized.get("name") or "без имени")
    if kind == "template":
        return str(normalized.get("description") or normalized.get("purpose") or
                   "Стартовая форма для создания записи; не является фактом runtime.")
    if kind == "markdown":
        document = (documents_by_id or {}).get(normalized.get("document_id"))
        return "Канонический Markdown-документ%s." % (
            " с инструкциями и правилами" if document else " проекта")
    if kind == "source_file":
        return "Канонический исходный файл; его bytes остаются доступными для проверки и provenance."
    return str(normalized.get("description") or "Связанная сущность проекта.")


def _catalog_entity_technical(entity):
    normalized = entity.get("normalized") or {}
    kind = entity.get("kind") or "entity"
    if kind in {"schema", "template"}:
        return str(normalized.get("source_path") or normalized.get("path") or entity.get("entity_id", ""))
    if kind in {"markdown", "source_file"}:
        return str(normalized.get("canonical_path") or normalized.get("path") or entity.get("entity_id", ""))
    return str(entity.get("entity_id") or normalized.get("id") or "")


_FLOW_TERMINAL_TARGETS = {
    "human-decision": "Решение человека",
    "block": "Поток остановлен",
}


def _declared_routes(step):
    """Return display/audit routes, preferring DECISION-TREE-1 over legacy maps."""
    if not isinstance(step, dict):
        return []
    tree = step.get("decision_tree")
    if isinstance(tree, dict):
        nodes = tree.get("nodes")
        if isinstance(nodes, list):
            nodes = {item.get("id"): item for item in nodes
                     if isinstance(item, dict) and item.get("id")}
        if isinstance(nodes, dict):
            node_ids = set(nodes)
            result = []
            for node_id, node in sorted(nodes.items()):
                if not isinstance(node, dict) or not isinstance(node.get("routes"), dict):
                    continue
                for choice, raw_target in sorted(node["routes"].items(), key=lambda item: str(item[0])):
                    target = raw_target.get("target") if isinstance(raw_target, dict) else raw_target
                    if not isinstance(target, str) or target in node_ids:
                        continue
                    result.append(("%s=%s" % (node_id, choice), target))
            return result
    routes = step.get("routes") or {}
    return [(key, value) for key, value in sorted(routes.items())
            if isinstance(value, str)] if isinstance(routes, dict) else []


def _field_table(fields):
    rows = "".join("<tr><th>%s</th><td>%s</td></tr>" %
                   (html.escape(str(key).replace("_", " ")), html.escape(_human_value(value)))
                   for key, value in fields if value not in (None, "", [], {}))
    return '<table class="data-table"><tbody>%s</tbody></table>' % rows if rows else ""


_RU_FINDING = {
    "AUTODOC_FLOW_ROUTE_TARGET_MISSING": "Переход потока ведёт в несуществующий шаг",
    "AUTODOC_FLOW_UNREACHABLE": "Шаг потока недостижим",
    "AUTODOC_MARKDOWN_BROKEN_LINK": "В Markdown не разрешилась локальная ссылка",
    "AUTODOC_MARKDOWN_UNCLOSED_FENCE": "В Markdown не закрыт блок кода",
    "AUTODOC_MARKDOWN_UNSAFE_HTML": "HTML в Markdown экранирован ради безопасности",
    "AUTODOC_MARKDOWN_MISSING_IMAGE": "Изображение не найдено",
    "AUTODOC_PREZA_PARITY_UNKNOWN": "Legacy-материал требует ручного подтверждения",
    "AUTODOC_TASK_VERIFY_MISSING": "У задачи нет поля проверки",
}


def _finding_title(code):
    return _RU_FINDING.get(str(code), str(code).replace("AUTODOC_", "").replace("_", " ").capitalize())


def _doc_summary(document):
    markdown = document.get("markdown") or {}
    headings = markdown.get("headings") or []
    for heading in headings:
        if heading.get("level") == 1:
            return heading.get("text") or document.get("doc_key") or "Документ"
    return (headings[0].get("text") if headings else None) or document.get("doc_key") or "Документ"


def _rebase_body_links(body, page_path):
    """Rebase root-authored links without rebasing inline SVG links twice."""
    svg_blocks = []

    def protect_svg(match):
        svg_blocks.append(match.group(0))
        return "__AUTODOC_SVG_BLOCK_%d__" % (len(svg_blocks) - 1)

    protected = re.sub(r"<svg\b.*?</svg>", protect_svg, body, flags=re.I | re.S)

    def replace(match):
        target = match.group(1)
        parsed = urlparse(target)
        if parsed.scheme or parsed.netloc or target.startswith(("#", "/")):
            return match.group(0)
        path = parsed.path or "index.html"
        return 'href="%s"' % html.escape(_href(page_path, path) + ("#" + parsed.fragment if parsed.fragment else ""), quote=True)

    rebased = re.sub(r'href="([^"]+)"', replace, protected)
    for index, svg in enumerate(svg_blocks):
        rebased = rebased.replace("__AUTODOC_SVG_BLOCK_%d__" % index, svg)
    return rebased


def _render_bundle_files(bundle, html_root):
    if os.path.isdir(html_root):
        manifest_path = os.path.join(html_root, "manifest.json")
        if os.path.isfile(manifest_path):
            try:
                old = _read_json(manifest_path)
            except SkillError:
                old = None
            if not isinstance(old, dict) or old.get("schema") != AUTODOC_HTML_SCHEMA:
                raise SkillError("AUTODOC_OUTPUT_NOT_OWNED",
                                 "html output существует и не помечен todone-autodoc",
                                 html_root)
        else:
            # Empty caller-created directory is safe; non-empty unknown output is not.
            if os.listdir(html_root):
                raise SkillError("AUTODOC_OUTPUT_NOT_OWNED",
                                 "html output не является autodoc output", html_root)
        shutil.rmtree(html_root)
    os.makedirs(html_root, exist_ok=True)
    page_map = _entity_page_map(bundle)
    doc_map = _document_page_map(bundle)
    source_map = {item.get("source_id"): item for item in bundle.get("sources") or []}
    image_map = {}
    # Source download assets are local and are generated from embedded bytes.
    source_assets = {}
    for source in bundle.get("sources") or []:
        if source.get("raw") is None or not source.get("raw_available"):
            continue
        safe = _safe_output_name(source.get("source_id"))
        suffix = os.path.splitext(source.get("canonical_path", ""))[1]
        asset_rel = "assets/source/%s%s" % (safe, suffix)
        if source.get("raw_encoding") == "base64":
            data = base64.b64decode(source["raw"])
            _write_bytes(os.path.join(html_root, asset_rel), data)
        else:
            _write_text(os.path.join(html_root, asset_rel), source.get("raw", ""))
        source_assets[source["source_id"]] = asset_rel
    # Map embedded local images for Markdown links.
    for source in bundle.get("sources") or []:
        if not source.get("canonical_path", "").lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
            continue
        if source.get("raw_encoding") == "base64":
            source_assets.setdefault(source["source_id"], "assets/source/%s%s" %
                                     (_safe_output_name(source["source_id"]), os.path.splitext(source["canonical_path"])[1]))
    for document in bundle.get("documents") or []:
        for image in (document.get("markdown") or {}).get("images") or []:
            target = image.get("target") or ""
            joined = posixpath.normpath(posixpath.join(posixpath.dirname(document.get("canonical_path", "")), target))
            image_source = source_map.get(next((s["source_id"] for s in bundle.get("sources", [])
                                                 if s.get("canonical_path") == joined), ""))
            if image_source and image_source.get("source_id") in source_assets:
                image_map[(document.get("canonical_path"), target)] = source_assets[image_source["source_id"]]
    css = _html_css()
    js = _html_js()
    _write_text(os.path.join(html_root, "assets/app.css"), css)
    _write_text(os.path.join(html_root, "assets/app.js"), js)
    # Keep the pinned Mermaid runtime inside the deliverable as an auditable
    # offline asset. Generated pages use the already-rendered SVG, so opening
    # the catalog never needs a network fetch or a browser-side build.
    runtime_source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "mermaid", "mermaid.min.js")
    runtime_target = os.path.join(html_root, "assets/vendor/mermaid/mermaid.min.js")
    os.makedirs(os.path.dirname(runtime_target), exist_ok=True)
    shutil.copyfile(runtime_source, runtime_target)
    vendor_source_dir = os.path.dirname(runtime_source)
    for vendor_name in ("render.cjs", "dom-host.cjs", "package.json", "PACKAGE.json"):
        shutil.copyfile(os.path.join(vendor_source_dir, vendor_name),
                        os.path.join(html_root, "assets/vendor/mermaid", vendor_name))
    _write_json(os.path.join(html_root, "assets/vendor/mermaid/renderer.json"), {
        "renderer": MERMAID_RENDERER, "version": MERMAID_VERSION, "license": "MIT",
        "runtime": "assets/vendor/mermaid/mermaid.min.js",
        "adapter": "assets/vendor/mermaid/render.cjs",
        "dom_host": "assets/vendor/mermaid/dom-host.cjs", "offline": True,
        "runtime_sha256": sha256_file(runtime_target),
    })
    diagram_specs = list(bundle.get("diagrams") or [])
    diagram_svgs = _render_mermaid_specs(diagram_specs)
    for spec in diagram_specs:
        svg = diagram_svgs[spec.get("diagram_id")]
        expected_digest = spec.get("asset_digest")
        actual_digest = sha256_bytes(svg.encode("utf-8"))
        if expected_digest and expected_digest != actual_digest:
            raise SkillError("AUTODOC_MERMAID_DIGEST_MISMATCH",
                             "SVG digest не совпадает с bundle для %s" % spec.get("diagram_id"),
                             str(spec.get("diagram_id")))
        _write_text(os.path.join(html_root, spec["asset_path"]), svg)
    # Legacy SVGs remain parity evidence in the bundle, but are not published
    # as generated diagrams. The architecture page uses the Mermaid projection
    # above, so every diagram in the offline catalog has one SDK provenance.
    pages = []
    search = []

    def add_page(rel, title, body, entity_id=None):
        _write_text(os.path.join(html_root, rel), _page_shell(title, body, page_path=rel, bundle=bundle))
        digest = sha256_file(os.path.join(html_root, rel))
        pages.append({"path": rel, "title": title, "entity_id": entity_id,
                      "sha256": digest})
        search.append({"title": title, "path": rel, "entity_id": entity_id,
                       "text": re.sub(r"<[^>]+>", " ", body)[:1200]})

    def diagram_panel(diagram_id, caption):
        spec = next((item for item in diagram_specs if item.get("diagram_id") == diagram_id), {})
        # An empty relation set is not a diagram. Do not turn it into a giant
        # white Mermaid canvas with a lonely "Нет данных" box; explain the
        # state in the surrounding human UI instead.
        if spec and not (spec.get("nodes") or spec.get("edges")):
            empty_title = "Задач пока нет" if diagram_id == "task-relations" else "Для этой карты пока нет данных"
            empty_text = ("В текущем project tree нет сущностей типа task, поэтому зависимости нечего соединять. "
                          "Когда появится задача, здесь автоматически появятся её связи и статусы.")
            return '<div class="diagram-empty"><strong>%s</strong><p>%s</p><div class="diagram-caption">%s · пустое состояние, Mermaid не запускается для отсутствующего графа.</div></div>' % (
                html.escape(empty_title), html.escape(empty_text), html.escape(caption))
        svg = diagram_svgs.get(diagram_id)
        if not svg:
            return '<div class="callout">Диаграмма Mermaid «%s» не была построена.</div>' % html.escape(str(diagram_id))
        # Inline SVG does not need the standalone XML namespace declaration;
        # omitting it keeps the human-facing HTML free of URL-looking assets.
        inline_svg = svg.replace(' xmlns="http://www.w3.org/2000/svg"', "")
        click_note = " · Нажмите на шаг, чтобы открыть его описание" if spec.get("kind") == "flow" else ""
        return '<div class="diagram">%s<div class="diagram-caption">%s · Mermaid %s · SVG создан локальным adapter.%s</div></div>' % (
            inline_svg, html.escape(caption), html.escape(MERMAID_VERSION), click_note)

    counts = defaultdict(int)
    for entity in bundle.get("entities") or []:
        counts[entity.get("kind", "unknown")] += 1
    metric_kinds = (("workspace", "проект"), ("queue", "очередь"), ("task", "задачи"),
                    ("document", "документы"), ("flow", "процессы"), ("type", "виды задач внутри процессов"))
    metrics = "".join('<div class="stat"><span class="metric">%d</span><span class="label">%s</span></div>' %
                      (counts.get(kind, 0), label) for kind, label in metric_kinds)
    audit_findings = (bundle.get("audit_input") or {}).get("findings") or []
    audit_errors = sum(1 for item in audit_findings if item.get("severity") in {"error", "blocker"})
    audit_status = (bundle.get("audit_input") or {}).get("verdict") or "not_run"
    audit_text = "Проверка целостности и ссылок пройдена." if not audit_errors else "Найдены места, которые нужно просмотреть: %d ошибки, %d предупреждений." % (audit_errors, len(audit_findings) - audit_errors)
    audit_class = "ok" if not audit_errors else "warning"
    audit_html = '<div class="%s"><strong>Состояние аудита: %s.</strong> %s <a href="audit/index.html">Открыть подробный отчёт →</a></div>' % (audit_class, html.escape(_ru_status(audit_status)), html.escape(audit_text))
    flow_cards = "".join(
        '<a class="catalog-card" data-search-item href="%s"><span class="kicker">Поток</span><h3>%s</h3><p>%s шагов · полная SVG-диаграмма</p></a>' %
        (html.escape(_href("index.html", page_map.get(entity["entity_id"], "flows/index.html")), quote=True),
         html.escape((entity.get("normalized") or {}).get("name") or entity["entity_id"]),
         len((entity.get("normalized") or {}).get("steps") or []))
        for entity in bundle.get("entities") or [] if entity.get("kind") == "flow")
    doc_cards = "".join(
        '<a class="catalog-card" data-search-item href="%s"><span class="kicker">Документ</span><h3>%s</h3><p><code>%s</code> · %d разделов</p></a>' %
        (html.escape(_href("index.html", doc_map.get(document.get("canonical_path"), "docs/index.html")), quote=True),
         html.escape(_doc_summary(document)), html.escape(document.get("canonical_path", "")),
         len((document.get("markdown") or {}).get("headings") or []))
        for document in (bundle.get("documents") or [])[:12])
    overview = (
        '<section class="hero"><div class="eyebrow">TODONE · OFFLINE KNOWLEDGE CATALOG</div>'
        '<h1>Документация проекта<br><span class="kicker">в понятном виде</span></h1>'
        '<p class="lead">Единый русскоязычный каталог: инструкции из Markdown, процессы, связанные профили, схемы и audit-проверки. Никаких сетевых зависимостей — откройте файл и читайте.</p>'
        '<p class="source-note">Собрано из канонических источников. Исходники не подменяются производными страницами.</p></section>'
        '<div class="stats">%s</div>' % metrics
        + '<section class="section-head"><div><div class="kicker">Навигация</div><h2>С чего начать</h2></div></section>'
        '<div class="catalog-grid">'
        '<a class="catalog-card" data-search-item href="docs/index.html"><span class="kicker">01 · Читать</span><h3>Вся документация</h3><p>Markdown-документы с оглавлением, якорями, таблицами, списками и ссылкой на оригинал.</p></a>'
        '<a class="catalog-card" data-search-item href="processes/index.html"><span class="kicker">02 · Понять</span><h3>Процессы и жизненный цикл</h3><p>Один путь от входа до результата: этапы, виды задач, agents, роли, gates, skills и evidence.</p></a>'
        '<a class="catalog-card" data-search-item href="entities/index.html"><span class="kicker">03 · Связать</span><h3>Карта связей</h3><p>Единое дерево сущностей с раскрывающимися путями, каноническими файлами и JSON-проверкой.</p></a>'
        '<a class="catalog-card" data-search-item href="audit/index.html"><span class="kicker">04 · Проверить</span><h3>Аудит и совместимость</h3><p>Источники, parity PREZA, предупреждения и понятные действия по исправлению.</p></a>'
        '</div>'
        '<section class="section-head"><div><div class="kicker">Рабочая карта</div><h2>Жизненный цикл процессов</h2></div><a href="processes/index.html">Открыть процессы →</a></section>'
        '<div class="catalog-grid">%s</div>' % flow_cards
        + '<section class="section-head"><div><div class="kicker">Знания</div><h2>Документы</h2></div><a href="docs/index.html">Открыть каталог →</a></section>'
        '<div class="catalog-grid">%s</div>' % doc_cards
        + '<section class="section-head"><div><div class="kicker">Контроль</div><h2>Состояние сборки</h2></div></section>'
        + audit_html
        + '<p class="source-note">Статус bundle: %s · источников: %d · неизвестных: %d · digest: <code>%s</code></p>' %
        (html.escape(_ru_status(bundle.get("completeness", {}).get("status", "unknown"))),
         len(bundle.get("sources") or []), len(bundle.get("unknowns") or []),
         html.escape(bundle.get("canonical_digest", "")))
    )
    add_page("index.html", "Обзор проекта", overview)
    architecture = (
        '<section class="hero"><div class="eyebrow">АРХИТЕКТУРА</div><h1>Как устроен каталог</h1>'
        '<p class="lead">Канонические файлы читаются адаптерами, превращаются в стабильные сущности и связи, а затем показываются в этом offline-сайте.</p></section>'
        '<div class="grid">%s</div>' % metrics
        + '<h2>Карта слоёв</h2>' + diagram_panel("architecture", "Компоненты bundle и их provenance")
        + '<h2>Задачи и зависимости</h2>' + diagram_panel("task-relations", "Дерево задач, зависимости и нерешённые связи")
        + '<h2>Связи сущностей</h2>' + diagram_panel("entity-relations", "Документы, задачи, файлы и другие связи bundle")
        + '<h2>Что входит в сборку</h2><div class="catalog-grid">'
        '<div class="catalog-card"><h3>Канонические источники</h3><p>Markdown, task.json, типы, flows, schemas, templates и настройки остаются источниками истины.</p></div>'
        '<div class="catalog-card"><h3>Понятные представления</h3><p>Человекочитаемые страницы, оглавления, карточки, таблицы и диаграммы Mermaid строятся из bundle.</p></div>'
        '<div class="catalog-card"><h3>Доказуемость</h3><p>Каждый материал связан с provenance, SHA-256, исходным путём и отчётом совместимости.</p></div>'
        '<div class="catalog-card"><h3>Безопасность</h3><p>HTML экранируется, внешние assets не подключаются, reconstruction проверяет traversal и symlink.</p></div>'
        '</div><h2>Понятный маршрут чтения</h2><ol><li>Начните с <a href="docs/index.html">каталога документации</a>.</li><li>Затем откройте <a href="processes/index.html">процессы</a> и фильтруйте полный жизненный цикл.</li><li>Для проверки связей используйте <a href="entities/index.html">единое дерево сущностей</a>.</li><li>Для проверки результата откройте <a href="audit/index.html">аудит</a>.</li></ol>'
    )
    add_page("architecture/index.html", "Архитектура каталога", _rebase_body_links(architecture, "architecture/index.html"))
    # The entity index is a human-facing map, not a dump of 471 records. Keep
    # every entity reachable, but express containment first: flow -> steps,
    # type -> agent profile, skill -> child-skills, role -> agents, and
    # contract family -> schemas/templates. Technical IDs stay secondary.
    catalog_entity_by_id = {item.get("entity_id"): item for item in bundle.get("entities") or []}
    catalog_documents_by_id = {item.get("document_id"): item for item in bundle.get("documents") or []}
    catalog_entities_by_kind = defaultdict(list)
    for item in bundle.get("entities") or []:
        catalog_entities_by_kind[item.get("kind", "entity")].append(item)

    def catalog_href(entity):
        target = page_map.get(entity.get("entity_id"), "entities/index.html")
        return html.escape(_href("entities/index.html", target), quote=True)

    def catalog_chip(label, href=None):
        if href:
            return '<a class="entity-chip" href="%s">%s</a>' % (html.escape(href, quote=True), html.escape(str(label)))
        return '<span class="entity-chip">%s</span>' % html.escape(str(label))

    def catalog_inline_details(entity):
        """Human fields plus a collapsed normalized JSON payload.

        The operational tree should be useful without opening another page,
        while raw data remains explicitly secondary and collapsible.
        """
        kind = entity.get("kind", "entity")
        normalized = entity.get("normalized") or {}
        if kind not in {"workspace", "flow", "flow_step", "type", "skill", "agent", "role"}:
            return ""

        def label_for(entity_id):
            target = catalog_entity_by_id.get(entity_id)
            return _catalog_entity_name(target, entities_by_id=catalog_entity_by_id,
                                        documents_by_id=catalog_documents_by_id) if target else entity_id

        rows = [("канонический файл", normalized.get("source_path") or normalized.get("path"))]
        if kind == "flow":
            rows += [("инструкция", normalized.get("instruction_path")),
                     ("виды задач", [label_for("type:%s" % item) for item in normalized.get("task_types") or []]),
                     ("шаги", len(normalized.get("steps") or normalized.get("step_refs") or [])),
                     ("skill-маршрутизатор", [label_for(relation.get("to")) for relation in bundle.get("relations") or []
                                               if relation.get("from") == entity.get("entity_id") and
                                               relation.get("kind") == "uses" and
                                               catalog_entity_by_id.get(relation.get("to"), {}).get("kind") == "skill"]),
                     ("вход", normalized.get("entry")),
                     ("схема", normalized.get("schema"))]
        elif kind == "flow_step":
            type_id = "type:%s" % normalized.get("type") if normalized.get("type") else None
            executor = normalized.get("executor") if isinstance(normalized.get("executor"), dict) else {}
            rows += [("поток", label_for(normalized.get("flow_ref"))),
                     ("вид задачи", label_for(type_id) if type_id else None),
                     ("роль исполнения", _RU_ROLE_NAMES.get(str(executor.get("role")), executor.get("role"))),
                     ("режим / tier", "%s / %s" % (executor.get("mode", "—"), executor.get("tier", "—"))),
                     ("входы", normalized.get("input_from")),
                     ("выходы", normalized.get("output")),
                     ("gate", normalized.get("gate_out")),
                     ("необязательный", normalized.get("optional")),
                     ("параллельный", normalized.get("parallel")),
                     ("маршруты", _declared_routes(normalized)),
                     ("документация", normalized.get("documentation"))]
        elif kind == "type":
            rows += [("инструкция", normalized.get("instruction_path")),
                     ("поля", [field.get("name") for field in normalized.get("fields") or [] if isinstance(field, dict)]),
                     ("gates", normalized.get("gates")),
                     ("capabilities", normalized.get("capabilities")),
                     ("checks", normalized.get("checks")),
                     ("исполнитель", normalized.get("executor")),
                     ("agent profiles", [label_for(item) for item in normalized.get("agent_refs") or []]),
                     ("skill-маршрутизатор", [label_for(relation.get("to")) for relation in bundle.get("relations") or []
                                               if relation.get("from") == entity.get("entity_id") and
                                               relation.get("kind") == "uses" and
                                               catalog_entity_by_id.get(relation.get("to"), {}).get("kind") == "skill"]),
                     ("общие документы", normalized.get("shared_instruction_paths"))]
        elif kind == "skill":
            parent = normalized.get("parent_skill")
            document = catalog_documents_by_id.get(normalized.get("document_id"))
            rows += [("родитель", label_for(parent) if parent else None),
                     ("Markdown", normalized.get("path")),
                     ("документ", document.get("canonical_path") if document else None)]
        elif kind == "agent":
            profile = normalized.get("profile") if isinstance(normalized.get("profile"), dict) else {}
            return_contract = profile.get("return_contract") if isinstance(profile.get("return_contract"), dict) else {}
            rows += [("вид задачи", label_for("type:%s" % normalized.get("type_id")) if normalized.get("type_id") else None),
                     ("роль", _RU_ROLE_NAMES.get(str(normalized.get("role")), normalized.get("role"))),
                     ("инструменты", profile.get("tools")),
                     ("границы", profile.get("boundaries")),
                     ("return contract", return_contract),
                     ("общий бриф", profile.get("brief"))]
        elif kind == "role":
            rows += [("роль", _RU_ROLE_NAMES.get(str(normalized.get("role")), normalized.get("role"))),
                     ("объявлена в", normalized.get("declared_by"))]

        rows = [(key, value) for key, value in rows if value not in (None, "", [], {})]
        human = _field_table(rows) or '<p class="entity-empty">Дополнительных полей не заявлено.</p>'
        raw = '<details class="json-details"><summary>Исходный JSON сущности</summary><pre>%s</pre></details>' % html.escape(_json_dumps(normalized, pretty=True))
        return '<details class="entity-inline-details"><summary>Полная информация</summary><div class="entity-inline-content">%s%s</div></details>' % (human, raw)

    def catalog_card(entity, links=""):
        kind = entity.get("kind", "entity")
        name = _catalog_entity_name(entity, entities_by_id=catalog_entity_by_id,
                                    documents_by_id=catalog_documents_by_id)
        purpose = _catalog_entity_purpose(entity, entities_by_id=catalog_entity_by_id,
                                          documents_by_id=catalog_documents_by_id)
        technical = _catalog_entity_technical(entity)
        # The card itself is a div because the optional provenance chips may
        # contain links. Only the human name is the primary entity link; this
        # keeps the generated HTML valid and keyboard-navigable.
        return ('<div class="entity-card entity-card--%s" data-search-item>'
                '<div class="entity-card__head"><span class="entity-card__name"><a href="%s">%s</a></span>'
                '<span class="entity-card__kind">%s</span></div>'
                '<p class="entity-card__purpose">%s</p>'
                '<span class="entity-card__technical">%s</span>%s%s</div>' % (
                    html.escape(_slug(kind)), catalog_href(entity), html.escape(name),
                    html.escape(_ru_kind(kind).capitalize()), html.escape(purpose),
                    html.escape(technical),
                    '<span class="entity-card__links">%s</span>' % links if links else "",
                    _status_pill(entity.get("status", "unknown")) + catalog_inline_details(entity)))

    def catalog_node(entity, children="", *, open=False, links=""):
        kind = entity.get("kind", "entity")
        name = _catalog_entity_name(entity, entities_by_id=catalog_entity_by_id,
                                    documents_by_id=catalog_documents_by_id)
        purpose = _catalog_entity_purpose(entity, entities_by_id=catalog_entity_by_id,
                                          documents_by_id=catalog_documents_by_id)
        opening = " open" if open else ""
        body = catalog_card(entity, links=links)
        if children:
            body += '<div class="entity-subgroup"><div class="entity-children">%s</div></div>' % children
        return ('<details class="entity-node entity-node--%s"%s data-search-item>'
                '<summary><span class="entity-node__title"><strong>%s</strong><small>%s</small></span>'
                '<span class="entity-count">%s</span></summary>'
                '<div class="entity-node__body">%s</div></details>' % (
                    html.escape(_slug(kind)), opening, html.escape(name), html.escape(purpose),
                    html.escape(_ru_kind(kind).capitalize()), body))

    def catalog_group(kind, title, purpose, count, content, *, open=False):
        opening = " open" if open else ""
        return ('<details class="entity-group entity-group--%s"%s>'
                '<summary><span class="entity-group__title"><strong>%s</strong><small>%s</small></span>'
                '<span class="entity-count">%d</span></summary>'
                '<div class="entity-group__body"><p>%s</p>%s</div></details>' % (
                    html.escape(_slug(kind)), opening, html.escape(title), html.escape(purpose),
                    count, html.escape(purpose), content))

    def catalog_subgroup(title, entries, *, kind="entity", open=False):
        opening = " open" if open else ""
        cards = "".join(catalog_card(entry) for entry in entries)
        return ('<details class="entity-subgroup entity-subgroup--%s"%s>'
                '<summary>%s <span class="entity-count">%d</span></summary>'
                '<div class="entity-children">%s</div></details>' % (
                    html.escape(_slug(kind)), opening, html.escape(title), len(entries),
                    cards or '<p class="entity-empty">В этой группе пока нет элементов.</p>'))

    def declared_targets(source_id, *, relation_kind="uses", target_kind=None):
        values = []
        for relation in bundle.get("relations") or []:
            if relation.get("from") != source_id or relation.get("kind") != relation_kind:
                continue
            target = catalog_entity_by_id.get(relation.get("to"))
            if target and (target_kind is None or target.get("kind") == target_kind):
                values.append(target.get("entity_id"))
        return sorted(set(values))

    flow_nodes = []
    for flow in sorted(catalog_entities_by_kind.get("flow", []),
                       key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower()):
        flow_id = flow.get("entity_id")
        steps = [item for item in catalog_entities_by_kind.get("flow_step", [])
                 if (item.get("normalized") or {}).get("flow_ref") == flow_id]
        steps.sort(key=lambda item: ((item.get("normalized") or {}).get("position", 999),
                                     _catalog_entity_name(item, entities_by_id=catalog_entity_by_id)))
        step_nodes = "".join(catalog_node(step) for step in steps)
        normalized = flow.get("normalized") or {}
        instruction = catalog_documents_by_id.get(normalized.get("instruction_document"))
        if instruction is None:
            instruction = next((doc for doc in bundle.get("documents") or []
                                if doc.get("canonical_path") == normalized.get("instruction_path")), None)
        flow_links = []
        if instruction:
            flow_links.append(catalog_chip("Инструкция потока →",
                                           _href("entities/index.html", doc_map.get(instruction.get("canonical_path"), "docs/index.html"))))
        flow_links.append(catalog_chip("%d шагов" % len(steps)))
        for skill_id in declared_targets(flow_id, target_kind="skill"):
            flow_links.append(catalog_chip("Skill-маршрутизатор →", catalog_href(catalog_entity_by_id[skill_id])))
        nested = ('<div class="entity-subgroup"><details open><summary>Шаги процесса <span class="entity-count">%d</span></summary>'
                  '<div class="entity-children">%s</div></details></div>' %
                  (len(steps), step_nodes or '<p class="entity-empty">Шаги не обнаружены.</p>'))
        flow_nodes.append(catalog_node(flow, nested, links="".join(flow_links)))
    flow_content = '<div class="entity-children">%s</div>' % ("".join(flow_nodes) or '<p class="entity-empty">Потоки не обнаружены.</p>')

    type_nodes = []
    for task_type in sorted(catalog_entities_by_kind.get("type", []),
                            key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower()):
        normalized = task_type.get("normalized") or {}
        agents = [catalog_entity_by_id[agent_id] for agent_id in normalized.get("agent_refs") or []
                  if agent_id in catalog_entity_by_id]
        agent_nodes = "".join(catalog_node(agent) for agent in sorted(
            agents, key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower()))
        type_links = []
        instruction = catalog_documents_by_id.get(normalized.get("instruction_document"))
        if instruction:
            type_links.append(catalog_chip("Рабочая инструкция →",
                                            _href("entities/index.html", doc_map.get(instruction.get("canonical_path"), "docs/index.html"))))
        for doc_id in normalized.get("shared_instruction_documents") or []:
            shared_doc = catalog_documents_by_id.get(doc_id)
            if shared_doc:
                type_links.append(catalog_chip("Общий этап →",
                                                _href("entities/index.html", doc_map.get(shared_doc.get("canonical_path"), "docs/index.html"))))
        for skill_id in declared_targets(task_type.get("entity_id"), target_kind="skill"):
            type_links.append(catalog_chip("Skill-маршрутизатор →", catalog_href(catalog_entity_by_id[skill_id])))
        nested = ('<div class="entity-subgroup"><details><summary>Исполнители профиля <span class="entity-count">%d</span></summary>'
                  '<div class="entity-children">%s</div></details></div>' %
                  (len(agents), agent_nodes or '<p class="entity-empty">Agent profile не заявлен.</p>'))
        type_nodes.append(catalog_node(task_type, nested, links="".join(type_links)))
    type_content = '<div class="entity-children">%s</div>' % ("".join(type_nodes) or '<p class="entity-empty">Виды задач не обнаружены.</p>')

    skills = {item.get("entity_id"): item for item in catalog_entities_by_kind.get("skill", [])}
    skills_by_parent = defaultdict(list)
    for skill in skills.values():
        skills_by_parent[(skill.get("normalized") or {}).get("parent_skill")].append(skill)

    def render_skill_node(skill_id, trail=None):
        trail = set(trail or ())
        if skill_id in trail or skill_id not in skills:
            return ""
        children = []
        for child in sorted(skills_by_parent.get(skill_id, []),
                            key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower()):
            children.append(render_skill_node(child.get("entity_id"), trail | {skill_id}))
        nested = ('<div class="entity-subgroup"><details open><summary>Дочерние процедуры <span class="entity-count">%d</span></summary>'
                  '<div class="entity-children">%s</div></details></div>' %
                  (len(children), "".join(children) or '<p class="entity-empty">Дочерних процедур нет.</p>')) if children else ""
        return catalog_node(skills[skill_id], nested, open=(skill_id == "skill:root"))

    root_skill_ids = [skill_id for skill_id, skill in skills.items()
                      if not (skill.get("normalized") or {}).get("parent_skill") or
                      (skill.get("normalized") or {}).get("parent_skill") not in skills]
    skill_content = '<div class="entity-children">%s</div>' % "".join(
        render_skill_node(skill_id) for skill_id in sorted(root_skill_ids))

    schema_groups = defaultdict(list)
    for schema in catalog_entities_by_kind.get("schema", []):
        normalized = schema.get("normalized") or {}
        identity = _schema_identity(normalized.get("schema_id") or normalized.get("name"))
        prefix = identity.split("_", 1)[0] if identity else "OTHER"
        schema_groups[prefix].append(schema)
    schema_group_labels = {
        "AUTODOC": "AUTODOC · каталог документации", "DOC": "DOC · документы",
        "FLOW": "FLOW · процессы", "TASK": "TASK · задачи", "WORKSPACE": "WORKSPACE · проект",
        "JIRA": "JIRA · внешнее зеркало", "PREZA": "PREZA · совместимость",
        "ARTEFACT": "ARTEFACT · артефакты", "COMMENT": "COMMENT · рабочая лента",
        "REF": "REF · указатели", "SRC": "SRC · источники",
    }
    schema_subgroups = []
    for prefix, entries in sorted(schema_groups.items()):
        entries.sort(key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower())
        schema_subgroups.append(catalog_subgroup(schema_group_labels.get(prefix, "Контракты · %s" % prefix),
                                                  entries, kind="schema", open=False))
    schema_content = "".join(schema_subgroups) or '<p class="entity-empty">Схемы не обнаружены.</p>'

    template_entries = sorted(catalog_entities_by_kind.get("template", []),
                              key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower())
    template_content = catalog_subgroup("Все стартовые формы", template_entries, kind="template", open=True)

    roles = {item.get("entity_id"): item for item in catalog_entities_by_kind.get("role", [])}
    agents_by_role = defaultdict(list)
    for agent in catalog_entities_by_kind.get("agent", []):
        role = (agent.get("normalized") or {}).get("role")
        agents_by_role[role].append(agent)
    role_nodes = []
    for role in sorted(roles.values(), key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower()):
        role_name = (role.get("normalized") or {}).get("role") or (role.get("normalized") or {}).get("name")
        agents = sorted(agents_by_role.get(role_name, []),
                        key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower())
        children = "".join(catalog_node(agent) for agent in agents)
        nested = ('<div class="entity-subgroup"><details><summary>Профили в роли <span class="entity-count">%d</span></summary>'
                  '<div class="entity-children">%s</div></details></div>' %
                  (len(agents), children or '<p class="entity-empty">Профили не найдены.</p>'))
        role_nodes.append(catalog_node(role, nested))
    assigned_agents = {agent.get("entity_id") for values in agents_by_role.values() for agent in values}
    unassigned = [agent for agent in catalog_entities_by_kind.get("agent", []) if agent.get("entity_id") not in assigned_agents]
    if unassigned:
        role_nodes.append(catalog_subgroup("Профили без роли", unassigned, kind="agent", open=False))
    roles_content = '<div class="entity-children">%s</div>' % ("".join(role_nodes) or '<p class="entity-empty">Роли не обнаружены.</p>')

    def path_family(entity):
        path = str((entity.get("normalized") or {}).get("canonical_path") or
                   (entity.get("normalized") or {}).get("path") or "")
        if path == "SKILL.md":
            return "Главный skill"
        first = path.split("/", 1)[0] if "/" in path else "Корень проекта"
        return {"child-skills": "Дочерние skills", "docs": "Документация", "types": "Инструкции видов задач",
                "flows": "Инструкции потоков", "schemas": "Канонические schemas", "templates": "Канонические templates"}.get(first, first or "Корень проекта")

    markdown_groups = defaultdict(list)
    for document_entity in catalog_entities_by_kind.get("markdown", []):
        markdown_groups[path_family(document_entity)].append(document_entity)
    markdown_content = "".join(
        catalog_subgroup(group_name, sorted(entries, key=lambda item: _catalog_entity_name(item, documents_by_id=catalog_documents_by_id).lower()),
                          kind="markdown", open=(group_name in {"Главный skill", "Документация"}))
        for group_name, entries in sorted(markdown_groups.items()))
    source_groups = defaultdict(list)
    for source_entity in catalog_entities_by_kind.get("source_file", []):
        source_groups[path_family(source_entity)].append(source_entity)
    source_content = "".join(
        catalog_subgroup(group_name, sorted(entries, key=lambda item: _catalog_entity_technical(item).lower()),
                          kind="source-file", open=False)
        for group_name, entries in sorted(source_groups.items()))

    # One operational tree makes the declared relations visible in the order
    # people actually experience them: flow -> step -> task type -> agent ->
    # role, with the shared skill router and runtime contracts attached at the
    # same level. This is a projection of bundle relations, not a guessed graph.
    catalog_relations = bundle.get("relations") or []

    def relation_targets(source_id, *, relation_kinds=None, target_kind=None):
        allowed = set(relation_kinds or {"contains", "implements", "uses", "documents"})
        result = []
        for relation in catalog_relations:
            if relation.get("from") != source_id or relation.get("kind") not in allowed:
                continue
            target_id = relation.get("to")
            target = catalog_entity_by_id.get(target_id)
            if target and (target_kind is None or target.get("kind") == target_kind):
                result.append(target_id)
        return sorted(set(result))

    def unified_link(entity_id, label=None, *, relation_label=None):
        target = catalog_entity_by_id.get(entity_id)
        if not target:
            return ""
        kind = target.get("kind", "entity")
        text = label or _catalog_entity_name(target, entities_by_id=catalog_entity_by_id,
                                             documents_by_id=catalog_documents_by_id)
        title = relation_label or _ru_kind(kind).capitalize()
        return '<a class="unified-link unified-link--%s" href="%s" title="%s"><span>%s</span></a>' % (
            html.escape(_slug(kind)),
            catalog_href(target),
            html.escape(title, quote=True),
            html.escape(str(text)))

    def unified_relations(items):
        links = "".join(unified_link(entity_id, label=label, relation_label=relation_label)
                         for entity_id, label, relation_label in items if entity_id in catalog_entity_by_id)
        return ('<div class="unified-relations"><span class="unified-relations__label">Связано с</span>%s</div>' % links
                if links else '<p class="unified-relationship-note">Явных связей этого типа в bundle не заявлено.</p>')

    def process_relation_links(entity_ids, relation_label):
        return "".join(unified_link(entity_id, relation_label=relation_label)
                       for entity_id in sorted(set(entity_ids))
                       if entity_id in catalog_entity_by_id)

    def process_fact(label, value, *, links=None, css_class=""):
        if links:
            rendered = process_relation_links(links, label)
        elif value not in (None, "", [], {}):
            rendered = html.escape(_human_value(value))
        else:
            return ""
        return '<div class="process-fact %s"><dt>%s</dt><dd>%s</dd></div>' % (
            html.escape(css_class), html.escape(label), rendered)

    def process_resource_summary(kind, label, entity_ids):
        entity_ids = sorted(set(entity_ids))
        if not entity_ids:
            return ""
        links = process_relation_links(entity_ids, label)
        return ('<details class="process-resource-summary process-resource-summary--%s">'
                '<summary><span class="resource-swatch"></span><span>%s</span><strong>%d</strong></summary>'
                '<div class="process-resource-summary__body">%s</div></details>' % (
                    html.escape(_slug(kind)), html.escape(label), len(entity_ids), links))

    def process_provenance(entity):
        provenance = entity.get("provenance") or []
        source_refs = entity.get("source_refs") or []
        rows = []
        for item in provenance:
            if not isinstance(item, dict):
                continue
            adapter = item.get("adapter") or "adapter"
            path = item.get("path") or "канонический источник не указан"
            source_ref = item.get("source_ref") or ""
            rows.append('<li><strong>%s</strong><code>%s</code>%s</li>' % (
                html.escape(str(adapter)), html.escape(str(path)),
                ' <small>%s</small>' % html.escape(str(source_ref)) if source_ref else ""))
        if not rows and not source_refs:
            return '<p class="process-empty-note">Provenance не заявлен.</p>'
        source_note = '<p class="process-provenance-count">Source refs: %d</p>' % len(source_refs) if source_refs else ""
        return '<section class="process-provenance"><h4>Происхождение и source of truth</h4><ul>%s</ul>%s</section>' % (
            "".join(rows) or '<li>Источник не указан</li>', source_note)

    def process_decision_tree(step, flow_steps):
        normalized = step.get("normalized") or {}
        routes = _declared_routes(normalized)
        gate = normalized.get("gate_out")
        if not routes and not gate:
            return ""
        step_ids = {item.get("entity_id"): item for item in flow_steps}
        local_ids = {(item.get("normalized") or {}).get("id"): item.get("entity_id") for item in flow_steps}

        def target_markup(target):
            target_text = _FLOW_TERMINAL_TARGETS.get(target, target)
            local_id = str(target).split(".", 1)[0]
            target_id = local_ids.get(local_id)
            if target_id:
                return '<a class="decision-target" href="#step-%s">%s</a>' % (
                    html.escape(_slug(target_id)), html.escape(target_text))
            if target in _FLOW_TERMINAL_TARGETS:
                return '<span class="decision-target decision-target--terminal">%s</span>' % html.escape(target_text)
            return '<span class="decision-target">%s</span>' % html.escape(target_text)

        branches = "".join('<li><span class="decision-choice">%s</span><span class="decision-arrow">→</span>%s</li>' % (
            html.escape(str(choice)), target_markup(target)) for choice, target in routes)
        tree = normalized.get("decision_tree") or {}
        root = tree.get("root") or tree.get("id") or "решение" if isinstance(tree, dict) else "решение"
        schema = tree.get("schema") if isinstance(tree, dict) else None
        return '<section class="decision-tree"><div class="decision-tree__head"><span class="decision-tree__kind">GATE / DECISION</span><strong>%s</strong>%s</div><div class="decision-tree__body"><div class="decision-node"><span class="decision-node__dot"></span><span>Выйти из шага через <strong>%s</strong></span></div>%s</div></section>' % (
            html.escape(str(root)),
            ' <code>%s</code>' % html.escape(str(schema)) if schema else "",
            html.escape(str(gate or "решение")),
            '<ul>%s</ul>' % branches if branches else '<p>Ветвления не объявлены.</p>')

    def process_entity_line(entity, *, links="", details=""):
        kind = entity.get("kind", "entity")
        name = _catalog_entity_name(entity, entities_by_id=catalog_entity_by_id,
                                    documents_by_id=catalog_documents_by_id)
        purpose = _catalog_entity_purpose(entity, entities_by_id=catalog_entity_by_id,
                                          documents_by_id=catalog_documents_by_id)
        normalized = entity.get("normalized") or {}
        path = normalized.get("source_path") or normalized.get("canonical_path") or normalized.get("path") or _catalog_entity_technical(entity)
        return ('<div class="process-entity-line entity-kind--%s" data-entity-kind="%s">'
                '<div class="process-entity-line__head"><span class="process-kind-tag">%s</span><a href="%s">%s</a>%s</div>'
                '<p class="process-entity-line__purpose">%s</p>'
                '<div class="process-entity-line__meta"><code>%s</code>%s%s</div>%s</div>' % (
                    html.escape(_slug(kind)), html.escape(kind, quote=True),
                    html.escape(_ru_kind(kind).capitalize()), catalog_href(entity), html.escape(name),
                    _status_pill(entity.get("status", "unknown")), html.escape(purpose),
                    html.escape(str(path)),
                    '<div class="process-entity-line__links">%s</div>' % links if links else "",
                    '<a class="process-open-entity" href="%s">Открыть сущность</a>' % catalog_href(entity),
                    details))

    def process_step_inspector(step, flow_steps, flow_context, type_ids, agent_ids, role_ids, skill_ids):
        normalized = step.get("normalized") or {}
        type_resource_ids = {"markdown": set(), "schema": set(), "template": set(), "skill": set()}
        for type_id in type_ids:
            for target_kind in type_resource_ids:
                type_resource_ids[target_kind].update(
                    relation_targets(type_id, relation_kinds={"uses", "documents"}, target_kind=target_kind))
        resources = {
            "markdown": sorted(set(flow_context.get("document_ids", [])) | type_resource_ids["markdown"]),
            "schema": sorted(set(flow_context.get("schema_ids", [])) | type_resource_ids["schema"]),
            "template": sorted(set(flow_context.get("template_ids", [])) | type_resource_ids["template"]),
            "skill": sorted(set(flow_context.get("skill_ids", [])) | type_resource_ids["skill"] | set(skill_ids)),
        }
        executor = normalized.get("executor") if isinstance(normalized.get("executor"), dict) else {}
        facts = "".join([
            process_fact("Канонический файл", normalized.get("source_path"), css_class="fact-path"),
            process_fact("Вид задачи", None, links=type_ids, css_class="fact-type"),
            process_fact("Executor", {"mode": executor.get("mode"), "tier": executor.get("tier")}, css_class="fact-agent"),
            process_fact("Agent profile", None, links=agent_ids, css_class="fact-agent"),
            process_fact("Роль", None, links=role_ids, css_class="fact-role"),
            process_fact("Вход", normalized.get("input_from"), css_class="fact-input"),
            process_fact("Выход", normalized.get("output"), css_class="fact-output"),
            process_fact("Gate выхода", normalized.get("gate_out"), css_class="fact-gate"),
            process_fact("Параллельность", normalized.get("parallel"), css_class="fact-control"),
            process_fact("Опциональность", normalized.get("optional"), css_class="fact-control"),
        ])
        resource_groups = []
        for kind, label in (("markdown", "Документы"), ("schema", "Schemas"),
                            ("template", "Templates"), ("skill", "Skills")):
            ids = resources[kind]
            if not ids:
                continue
            resource_groups.append('<div class="process-resource-group process-resource-group--%s">%s</div>' % (
                html.escape(_slug(kind)), process_resource_summary(kind, label, ids)))
        related = ([(item, None, "Вид задачи") for item in type_ids] +
                   [(item, None, "Профиль агента") for item in agent_ids] +
                   [(item, None, "Роль исполнения") for item in role_ids] +
                   [(item, None, "Skill-маршрутизатор") for item in skill_ids])
        return ('<div class="process-step-inspector"><dl class="process-facts">%s</dl>%s%s%s%s%s</div>' % (
            facts,
            process_decision_tree(step, flow_steps),
            '<div class="process-resource-groups">%s</div>' % "".join(resource_groups) if resource_groups else "",
            unified_relations(related),
            process_provenance(step),
            _tech_details("JSON шага процесса", normalized)))

    def unified_step_node(step, *, flow_context=None, flow_steps=None):
        flow_context = flow_context or {}
        flow_steps = flow_steps or [step]
        normalized = step.get("normalized") or {}
        step_id = step.get("entity_id")
        type_ids = relation_targets(step_id, relation_kinds={"implements"}, target_kind="type")
        if not type_ids and normalized.get("type"):
            fallback = "type:%s" % normalized.get("type")
            if fallback in catalog_entity_by_id:
                type_ids = [fallback]
        agent_ids = relation_targets(step_id, relation_kinds={"uses"}, target_kind="agent")
        role_ids = relation_targets(step_id, relation_kinds={"uses"}, target_kind="role")
        skill_ids = relation_targets(step_id, relation_kinds={"uses"}, target_kind="skill")
        type_name = _catalog_entity_name(catalog_entity_by_id[type_ids[0]],
                                         entities_by_id=catalog_entity_by_id,
                                         documents_by_id=catalog_documents_by_id) if type_ids else "тип не указан"
        name = _catalog_entity_name(step, entities_by_id=catalog_entity_by_id,
                                    documents_by_id=catalog_documents_by_id)
        purpose = _catalog_entity_purpose(step, entities_by_id=catalog_entity_by_id,
                                          documents_by_id=catalog_documents_by_id)
        process_id = str(normalized.get("flow_ref") or "")
        step_search = "%s %s %s %s %s" % (name, purpose, type_name, _human_value(normalized), " ".join(
            _catalog_entity_name(catalog_entity_by_id[item], entities_by_id=catalog_entity_by_id,
                                 documents_by_id=catalog_documents_by_id)
            for item in type_ids + agent_ids + role_ids + skill_ids if item in catalog_entity_by_id))
        relation_chips = unified_relations(
            [(item, None, "Вид задачи") for item in type_ids] +
            [(item, None, "Профиль агента") for item in agent_ids] +
            [(item, None, "Роль исполнения") for item in role_ids])
        inspector = process_step_inspector(step, flow_steps, flow_context,
                                           type_ids, agent_ids, role_ids, skill_ids)
        return ('<details class="unified-step process-step" id="step-%s" data-process-id="%s" data-type-ids="%s" data-role-ids="%s" data-search-text="%s" data-search-item>'
                '<summary><span class="process-step-number">%s</span><span class="unified-step__title"><strong>%s</strong>'
                '<small>%s · вид задачи: %s</small></span><span class="unified-step__kind">Шаг потока</span></summary>'
                '<div class="unified-step__body"><div class="process-step-brief">%s</div>%s%s%s</div></details>' % (
                    html.escape(_slug(step.get("entity_id"))),
                    html.escape(process_id, quote=True),
                    html.escape(",".join(type_ids), quote=True),
                    html.escape(",".join(role_ids), quote=True),
                    html.escape(step_search, quote=True),
                    html.escape(str((normalized.get("position") or 0) + 1)),
                    html.escape(name), html.escape(purpose), html.escape(type_name),
                    process_entity_line(step, details=""), relation_chips, inspector, ""))

    unified_flow_nodes = []
    sorted_flows = sorted(catalog_entities_by_kind.get("flow", []),
                          key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower())
    for flow_index, flow in enumerate(sorted_flows):
        flow_id = flow.get("entity_id")
        normalized = flow.get("normalized") or {}
        step_entities = [item for item in catalog_entities_by_kind.get("flow_step", [])
                         if (item.get("normalized") or {}).get("flow_ref") == flow_id]
        step_entities.sort(key=lambda item: ((item.get("normalized") or {}).get("position", 999),
                                             _catalog_entity_name(item, entities_by_id=catalog_entity_by_id)))
        flow_skill_ids = relation_targets(flow_id, relation_kinds={"uses"}, target_kind="skill")
        flow_doc_ids = relation_targets(flow_id, relation_kinds={"documents"}, target_kind="markdown")
        flow_schema_ids = relation_targets(flow_id, relation_kinds={"uses"}, target_kind="schema")
        flow_template_ids = relation_targets(flow_id, relation_kinds={"uses"}, target_kind="template")
        flow_links = [catalog_chip("%d шагов" % len(step_entities))]
        for doc_id in flow_doc_ids:
            doc_entity = catalog_entity_by_id.get(doc_id)
            if doc_entity:
                flow_links.append(catalog_chip("Инструкция →", catalog_href(doc_entity)))
        flow_links.append(process_resource_summary("schema", "Schemas", flow_schema_ids))
        flow_links.append(process_resource_summary("template", "Templates", flow_template_ids))
        flow_links.append(process_resource_summary("skill", "Skills", flow_skill_ids))
        type_ids = []
        for step in step_entities:
            type_ids.extend(relation_targets(step.get("entity_id"), relation_kinds={"implements"}, target_kind="type"))
        type_ids = sorted(set(type_ids))
        flow_related = [(item, None, "Вид задачи потока") for item in type_ids]
        role_ids = sorted(set(role_id for step in step_entities
                              for role_id in relation_targets(step.get("entity_id"), relation_kinds={"uses"}, target_kind="role")))
        flow_related += [(item, None, "Роль исполнения") for item in role_ids]
        flow_search_ids = type_ids + role_ids + flow_skill_ids + flow_doc_ids + flow_schema_ids + flow_template_ids
        flow_search_names = [
            _catalog_entity_name(flow, entities_by_id=catalog_entity_by_id, documents_by_id=catalog_documents_by_id)
        ] + [
            _catalog_entity_name(catalog_entity_by_id[item], entities_by_id=catalog_entity_by_id,
                                 documents_by_id=catalog_documents_by_id)
            for item in flow_search_ids if item in catalog_entity_by_id
        ]
        flow_context = {"document_ids": flow_doc_ids, "schema_ids": flow_schema_ids,
                        "template_ids": flow_template_ids, "skill_ids": flow_skill_ids}
        step_nodes = "".join(unified_step_node(step, flow_context=flow_context, flow_steps=step_entities)
                              for step in step_entities)
        flow_name = _catalog_entity_name(flow, entities_by_id=catalog_entity_by_id,
                                         documents_by_id=catalog_documents_by_id)
        flow_purpose = _catalog_entity_purpose(flow, entities_by_id=catalog_entity_by_id,
                                               documents_by_id=catalog_documents_by_id)
        last_output = ((step_entities[-1].get("normalized") or {}).get("output") or ["результат"]) if step_entities else ["результат"]
        flow_summary = "%s · вход: %s · результат: %s" % (
            flow_purpose, _human_value(normalized.get("entry") or "старт"), _human_value(last_output))
        unified_flow_nodes.append(
            '<details class="unified-flow process-flow" id="process-%s"%s data-process-id="%s" data-type-ids="%s" data-role-ids="%s" data-search-text="%s" data-search-item><summary><span class="process-flow-number">%02d</span><span class="unified-branch__title"><span class="process-kind-tag">Процесс</span><strong>%s</strong><small>%s</small></span><span class="entity-count">%d шагов</span></summary>'
            '<div class="unified-flow__body"><div class="process-flow-intro">%s</div>%s%s<div class="unified-flow__steps"><div class="unified-relationship-note">Дерево исполнения: шаги идут сверху вниз; раскройте узел, чтобы увидеть контракт, решение и provenance.</div>%s</div></div></details>' % (
                html.escape(_slug(flow_id)), " open" if flow_index == 0 else "", html.escape(str(flow_id), quote=True),
                html.escape(",".join(type_ids), quote=True), html.escape(",".join(role_ids), quote=True),
                html.escape(" ".join(flow_search_names) + " " + flow_summary, quote=True),
                flow_index + 1, html.escape(flow_name), html.escape(flow_summary), len(step_entities),
                html.escape(flow_summary),
                process_entity_line(flow, links="".join(flow_links), details=catalog_inline_details(flow)),
                unified_relations(flow_related), step_nodes or '<p class="entity-empty">Шаги не обнаружены.</p>'))

    skill_root = catalog_entity_by_id.get("skill:root")
    skill_child_cards = "".join(catalog_card(item) for item in sorted(
        skills_by_parent.get("skill:root", []),
        key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower()))
    skill_common = ('<details class="unified-common" open><summary><span class="unified-branch__title"><strong>Skill-маршрутизатор</strong><small>Общий вход для потоков и видов задач; внутри — дочерние процедурные skills.</small></span><span class="entity-count">%d процедур</span></summary><div class="unified-common__body">%s<div class="unified-common__items">%s</div></div></details>' % (
        len(skills_by_parent.get("skill:root", [])), catalog_card(skill_root) if skill_root else "", skill_child_cards))
    type_common = ('<details class="unified-common"><summary><span class="unified-branch__title"><strong>Виды задач и исполнители</strong><small>Шаг потока выбирает вид задачи; вид задачи приводит к agent profile и роли.</small></span><span class="entity-count">%d профилей</span></summary><div class="unified-common__body"><div class="unified-common__items">%s</div></div></details>' % (
        len(catalog_entities_by_kind.get("type", [])), type_content))
    contract_common = ('<details class="unified-common"><summary><span class="unified-branch__title"><strong>Runtime-контракты</strong><small>Схемы проверяют данные flow/type/agent; подробные поля доступны в каталоге контрактов.</small></span><span class="entity-count">%d схем</span></summary><div class="unified-common__body"><div class="unified-common__items">%s</div></div></details>' % (
        len(catalog_entities_by_kind.get("schema", [])), schema_content))
    unified_tree = (
        '<div class="unified-map"><div class="unified-explainer"><strong>Как работает связка</strong><p>Поток выбирает и упорядочивает шаги. Каждый шаг реализует конкретный вид задачи, получает executor/agent и роль, а flow и type используют общий skill-маршрутизатор. Инструкция, schemas и исходный JSON остаются доступны в раскрывающихся блоках.</p><p>Связи ниже построены из declared paths и relations bundle; если связь не объявлена, она не дорисовывается.</p></div>'
        '<div class="unified-root"><div class="unified-root__head"><div><div class="unified-root__title">Проект Todone</div><div class="unified-root__purpose">Единое operational tree: от входного потока до конкретного исполнителя и канонического файла.</div></div><span class="entity-count">%d сущностей</span></div><div class="unified-branches">'
        '<details class="unified-branch" open><summary><span class="unified-branch__title"><strong>Потоки исполнения</strong><small>Flow → шаг → вид задачи → agent → роль</small></span><span class="entity-count">%d потока</span></summary><div class="unified-branch__body">%s</div></details>'
        '<details class="unified-branch" open><summary><span class="unified-branch__title"><strong>Общие конфигурации</strong><small>Skill router, task types, agents и runtime contracts</small></span><span class="entity-count">3 уровня</span></summary><div class="unified-branch__body"><div class="unified-common-grid">%s%s%s</div></div></details>'
        '</div></div></div>' % (len(bundle.get("entities") or []), len(sorted_flows), "".join(unified_flow_nodes), skill_common, type_common, contract_common))

    kind_order = ["workspace", "flow", "flow_step", "type", "skill", "schema", "template", "role", "agent", "markdown", "source_file"]
    kind_stats = "".join('<div class="entity-kind-stat"><strong>%d</strong><span>%s</span></div>' %
                         (len(catalog_entities_by_kind.get(kind, [])), html.escape(_RU_ENTITY_GROUPS.get(kind, (_ru_kind(kind).capitalize(), ""))[0]))
                         for kind in kind_order if catalog_entities_by_kind.get(kind))
    legend = "".join(catalog_chip(label) for kind, (label, _) in _RU_ENTITY_GROUPS.items()
                      if catalog_entities_by_kind.get(kind))
    entity_tree = (
        catalog_group("workspace", "Проект", _RU_ENTITY_GROUPS["workspace"][1],
                      len(catalog_entities_by_kind.get("workspace", [])),
                      '<div class="entity-children">%s</div>' % "".join(catalog_card(item) for item in catalog_entities_by_kind.get("workspace", [])))
        + catalog_group("flow", "Процессы", _RU_ENTITY_GROUPS["flow"][1],
                        len(catalog_entities_by_kind.get("flow", [])), flow_content)
        + catalog_group("type", "Виды задач", _RU_ENTITY_GROUPS["type"][1],
                        len(catalog_entities_by_kind.get("type", [])), type_content)
        + catalog_group("skill", "Навыки", _RU_ENTITY_GROUPS["skill"][1],
                        len(catalog_entities_by_kind.get("skill", [])), skill_content)
        + catalog_group("schema", "Runtime-контракты", _RU_ENTITY_GROUPS["schema"][1],
                        len(catalog_entities_by_kind.get("schema", [])), schema_content)
        + catalog_group("template", "Стартовые формы", _RU_ENTITY_GROUPS["template"][1],
                        len(catalog_entities_by_kind.get("template", [])), template_content)
        + catalog_group("role", "Роли и профили агентов", "Сначала роль, затем вложенные профили исполнителей и их контракты.",
                        len(catalog_entities_by_kind.get("role", [])) + len(catalog_entities_by_kind.get("agent", [])), roles_content)
        + catalog_group("markdown", "Документы", _RU_ENTITY_GROUPS["markdown"][1],
                        len(catalog_entities_by_kind.get("markdown", [])), markdown_content)
        + catalog_group("source-file", "Канонические файлы", _RU_ENTITY_GROUPS["source_file"][1],
                        len(catalog_entities_by_kind.get("source_file", [])), source_content, open=False)
    )
    catalog_tree = ('<details class="entity-group entity-group--catalog">'
                    '<summary><span class="entity-group__title"><strong>Полный каталог по видам</strong>'
                    '<small>Все сущности, документы и канонические файлы с фильтрацией по уровням.</small></span>'
                    '<span class="entity-count">%d записей</span></summary>'
                    '<div class="entity-group__body"><p>Этот слой нужен для инвентаризации. Для понимания runtime-связей используйте единое дерево выше.</p><div class="entity-tree">%s</div></div></details>' %
                    (len(bundle.get("entities") or []), entity_tree))
    entities_body = (
        '<section class="hero"><div class="eyebrow">КАРТА СУЩНОСТЕЙ</div><h1>Как проект работает целиком</h1>'
        '<p class="lead">Потоки, шаги, виды задач, skills, agents и schemas теперь показаны как одна operational-связка. Не нужно угадывать, где искать продолжение: раскрывайте узел и переходите по фактической relation.</p>'
        '<p class="source-note">Внутри узлов есть раскрывающиеся блоки с полным назначением, executor, входами/выходами, каноническим путём и исходным JSON. Технические идентификаторы оставлены для проверки, но не являются основным интерфейсом.</p></section>'
        '%s<h2>Охват каталога</h2><div class="entity-catalog-intro">%s</div><div class="entity-legend">%s</div>%s' %
        (unified_tree, kind_stats, legend, catalog_tree))

    process_options = "".join('<option value="%s">%s</option>' % (
        html.escape(str(flow.get("entity_id")), quote=True),
        html.escape(_catalog_entity_name(flow, entities_by_id=catalog_entity_by_id,
                                         documents_by_id=catalog_documents_by_id)))
        for flow in sorted_flows)
    process_type_options = "".join('<option value="%s">%s</option>' % (
        html.escape(str(task_type.get("entity_id")), quote=True),
        html.escape(_catalog_entity_name(task_type, entities_by_id=catalog_entity_by_id,
                                         documents_by_id=catalog_documents_by_id)))
        for task_type in sorted(catalog_entities_by_kind.get("type", []),
                                key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower()))
    process_role_options = "".join('<option value="%s">%s</option>' % (
        html.escape(str(role.get("entity_id")), quote=True),
        html.escape(_catalog_entity_name(role, entities_by_id=catalog_entity_by_id,
                                         documents_by_id=catalog_documents_by_id)))
        for role in sorted(roles.values(),
                           key=lambda item: _catalog_entity_name(item, entities_by_id=catalog_entity_by_id).lower()))
    process_step_count = len(catalog_entities_by_kind.get("flow_step", []))
    process_type_count = len(catalog_entities_by_kind.get("type", []))
    process_role_count = len(catalog_entities_by_kind.get("role", []))
    process_metrics = (
        '<div class="process-metrics" aria-label="Сводка процессов">'
        '<div class="process-metric process-metric--flow"><span class="process-metric__value">%d</span><span class="process-metric__label">процесса</span><small>lifecycle-маршрута</small></div>'
        '<div class="process-metric process-metric--flow-step"><span class="process-metric__value">%d</span><span class="process-metric__label">шагов</span><small>вход → решение → результат</small></div>'
        '<div class="process-metric process-metric--type"><span class="process-metric__value">%d</span><span class="process-metric__label">видов задач</span><small>рабочие профили</small></div>'
        '<div class="process-metric process-metric--role"><span class="process-metric__value">%d</span><span class="process-metric__label">ролей</span><small>кто отвечает</small></div>'
        '</div>' % (len(sorted_flows), process_step_count, process_type_count, process_role_count))
    def process_scope_link(entity_id, relation_label):
        target = catalog_entity_by_id.get(entity_id)
        if not target:
            return ""
        if target.get("kind") == "flow":
            return '<a class="unified-link unified-link--flow" href="#process-%s" title="%s"><span>%s</span></a>' % (
                html.escape(_slug(entity_id)), html.escape(relation_label, quote=True),
                html.escape(_catalog_entity_name(target, entities_by_id=catalog_entity_by_id,
                                                documents_by_id=catalog_documents_by_id)))
        return unified_link(entity_id, relation_label=relation_label)

    def process_scope_links(entity_ids, relation_label):
        return "".join(process_scope_link(entity_id, relation_label)
                       for entity_id in sorted(set(entity_ids)) if entity_id in catalog_entity_by_id)

    def process_resource_row(entity, status, consumers=None, relation_label="Используется в"):
        kind = entity.get("kind", "entity")
        entity_id = entity.get("entity_id")
        name = _catalog_entity_name(entity, entities_by_id=catalog_entity_by_id,
                                    documents_by_id=catalog_documents_by_id)
        consumers = consumers or []
        consumer_html = process_scope_links(consumers, relation_label)
        return ('<div class="process-resource-row entity-kind--%s">'
                '<div class="process-resource-row__name"><span class="process-kind-tag">%s</span><a href="%s">%s</a></div>'
                '<div class="process-resource-row__status"><span class="resource-status %s">%s</span>%s</div></div>' % (
                    html.escape(_slug(kind)), html.escape(_ru_kind(kind).capitalize()), catalog_href(entity), html.escape(name),
                    "resource-status--used" if consumers or status.startswith("наслед") else "resource-status--inventory",
                    html.escape(status),
                    '<div class="process-resource-row__consumers">%s</div>' % consumer_html if consumer_html else ""))

    flow_consumer_ids = [entity.get("entity_id") for entity in sorted_flows]
    skill_root_entity = catalog_entity_by_id.get("skill:root")
    skill_root_flow_ids = [relation.get("from") for relation in catalog_relations
                           if relation.get("to") == "skill:root" and relation.get("kind") == "uses"
                           and catalog_entity_by_id.get(relation.get("from"), {}).get("kind") == "flow"]
    skill_root_type_ids = [relation.get("from") for relation in catalog_relations
                           if relation.get("to") == "skill:root" and relation.get("kind") == "uses"
                           and catalog_entity_by_id.get(relation.get("from"), {}).get("kind") == "type"]
    child_skill_entities = sorted(
        [entity for entity in catalog_entities_by_kind.get("skill", []) if entity.get("entity_id") != "skill:root"],
        key=lambda entity: _catalog_entity_name(entity, entities_by_id=catalog_entity_by_id).lower())
    skill_resource_rows = ""
    if skill_root_entity:
        skill_resource_rows += process_resource_row(
            skill_root_entity,
            "подключён к %d процессам и %d видам задач" % (len(set(skill_root_flow_ids)), len(set(skill_root_type_ids))),
            sorted(set(skill_root_flow_ids + skill_root_type_ids)), "Контекст исполнения")
    skill_resource_rows += "".join(process_resource_row(
        entity, "наследуется через skill:root", ["skill:root"], "Общий родитель")
        for entity in child_skill_entities)
    template_resource_rows = ""
    for template in sorted(catalog_entities_by_kind.get("template", []),
                           key=lambda entity: _catalog_entity_name(entity, entities_by_id=catalog_entity_by_id).lower()):
        template_id = template.get("entity_id")
        type_consumers = [relation.get("from") for relation in catalog_relations
                          if relation.get("to") == template_id and relation.get("kind") == "uses"
                          and catalog_entity_by_id.get(relation.get("from"), {}).get("kind") == "type"]
        template_resource_rows += process_resource_row(
            template,
            "подключён к %d видам задач" % len(set(type_consumers)) if type_consumers else "инвентарь · пока не подключён",
            sorted(set(type_consumers)), "Вид задачи")
    process_resource_map = (
        '<details class="unified-branch process-resource-branch" open><summary><span class="unified-branch__title"><strong>Ресурсы, которые участвуют в процессах</strong><small>Skills подключаются через общий router; templates — через виды задач. Неподключённые записи явно помечены как inventory.</small></span><span class="entity-count">%d skills · %d templates</span></summary>'
        '<div class="unified-branch__body"><div class="process-resource-map">'
        '<section class="process-resource-panel process-resource-panel--skill"><div class="process-resource-panel__head"><span class="process-kind-tag">SKILLS</span><h3>Навыки исполнения</h3><p>Общий <code>skill:root</code> используется процессами и типами задач. Child-skills входят в его дерево и не являются отдельными шагами.</p></div><div class="process-resource-list">%s</div></section>'
        '<section class="process-resource-panel process-resource-panel--template"><div class="process-resource-panel__head"><span class="process-kind-tag">TEMPLATES</span><h3>Стартовые формы</h3><p>Template не является шагом процесса: он подключается к конкретному виду задачи. Поэтому ниже видно, что реально используется, а что пока только хранится в каталоге.</p></div><div class="process-resource-list">%s</div></section>'
        '</div></div></details>' % (len(catalog_entities_by_kind.get("skill", [])), len(catalog_entities_by_kind.get("template", [])), skill_resource_rows, template_resource_rows))
    process_legend = (
        '<section class="process-guide" aria-label="Как читать дерево процессов">'
        '<div class="process-guide__title"><span class="eyebrow">КАК ЧИТАТЬ ДЕРЕВО</span><strong>Одна ветка — один runtime-путь</strong></div>'
        '<div class="process-grammar"><span class="kind-key kind-key--flow">Процесс</span><span class="grammar-arrow">содержит</span><span class="kind-key kind-key--flow-step">Шаг потока</span><span class="grammar-arrow">реализует</span><span class="kind-key kind-key--type">Вид задачи</span><span class="grammar-arrow">назначает</span><span class="kind-key kind-key--agent">Agent</span><span class="grammar-arrow">в роли</span><span class="kind-key kind-key--role">Роль</span></div>'
        '<div class="process-legend"><span class="legend-item legend-item--flow"><i></i>процесс</span><span class="legend-item legend-item--flow-step"><i></i>шаг потока</span><span class="legend-item legend-item--type"><i></i>вид задачи</span><span class="legend-item legend-item--agent"><i></i>agent profile</span><span class="legend-item legend-item--role"><i></i>роль</span><span class="legend-item legend-item--skill"><i></i>skill</span><span class="legend-item legend-item--schema"><i></i>schema</span><span class="legend-item legend-item--template"><i></i>template</span><span class="legend-item legend-item--markdown"><i></i>документ</span></div>'
        '<p>Цвет и левая граница показывают тип узла. Заголовок — человеческое имя, строка кода — provenance, раскрытие «Полная информация» — контракт сущности. Цветные линии между уровнями показывают containment, chips — cross-links.</p></section>')
    process_body = (
        '<section class="hero"><div class="eyebrow">ПРОЦЕССЫ ПРОЕКТА</div><h1>Полный жизненный цикл задач</h1>'
        '<p class="lead">Здесь нет разрыва между задачей, потоком и исполнителем. Выберите процесс, вид задачи или роль — дерево оставит только относящиеся шаги и покажет весь путь от входа до результата.</p>'
        '<p class="source-note">Процесс — это главный экран работы. Потоки, типы задач и skills являются его подразделами, а не разрозненными каталогами.</p></section>'
        + process_legend
        + process_metrics
        + '<div class="process-page"><div class="process-filters" data-process-filters>'
        '<div class="process-filter-field"><label for="process-search">Поиск по жизненному циклу</label><input id="process-search" data-process-search type="search" placeholder="Например: тесты, план, документация"></div>'
        '<div class="process-filter-field"><label for="process-select">Процесс</label><select id="process-select" data-process-select><option value="">Все процессы</option>%s</select></div>'
        '<div class="process-filter-field"><label for="type-select">Вид задачи</label><select id="type-select" data-type-select><option value="">Все виды задач</option>%s</select></div>'
        '<div class="process-filter-field"><label for="role-select">Роль</label><select id="role-select" data-role-select><option value="">Все роли</option>%s</select></div>'
        '<button class="process-filter-reset" type="button" data-process-reset>Сбросить</button></div>'
        '<p class="process-filter-status" data-process-status></p>'
        '<div class="process-no-results" data-process-empty>По заданным фильтрам ничего не найдено. Сбросьте фильтры или выберите другой процесс.</div>'
        '<div class="unified-map"><div class="unified-root"><div class="unified-root__head"><div><div class="unified-root__title">Процессы</div><div class="unified-root__purpose">Вход → этапы → виды задач → agents → роли → evidence и документация.</div></div><span class="entity-count">%d процесса</span></div><div class="process-flow-tree">%s</div></div>%s'
        '<details class="unified-branch" open><summary><span class="unified-branch__title"><strong>Общие правила исполнения</strong><small>Skill router, типы, роли и runtime-контракты, используемые процессами</small></span><span class="entity-count">3 уровня</span></summary><div class="unified-branch__body"><div class="unified-common-grid">%s%s%s</div></div></details></div></div>' % (
            process_options, process_type_options, process_role_options, len(sorted_flows),
            "".join(unified_flow_nodes), process_resource_map, skill_common, type_common, contract_common))
    add_page("processes/index.html", "Процессы проекта", process_body)
    add_page("entities/index.html", "Каталог сущностей", entities_body)

    # Dedicated type cards intentionally combine all type-owned material. The
    # generic entity renderer remains a fallback for future adapters, but a
    # profile page must never force a reader to reconstruct instruction,
    # shared stages and agent contracts from separate raw JSON pages.
    entity_by_id = {item.get("entity_id"): item for item in bundle.get("entities") or []}
    document_by_id = {item.get("document_id"): item for item in bundle.get("documents") or []}
    relation_rows = bundle.get("relations") or []

    def linked_ids(entity_id, *, kind=None, incoming=False, relation_kinds=None):
        values = []
        for relation in relation_rows:
            if relation.get("kind") not in (set(relation_kinds) if relation_kinds else set(RELATION_KINDS)):
                continue
            endpoint = relation.get("to") if incoming else relation.get("from")
            if endpoint != entity_id:
                continue
            other = relation.get("from") if incoming else relation.get("to")
            target = entity_by_id.get(other)
            if target and (kind is None or target.get("kind") == kind):
                values.append(other)
        return sorted(set(values))

    def entity_link(entity_id, from_page, label=None, fragment=True):
        target = page_map.get(entity_id, "entities/index.html")
        if not fragment and "#" in target:
            target = target.split("#", 1)[0]
        return '<a href="%s">%s</a>' % (html.escape(_href(from_page, target), quote=True),
                                         html.escape(label or ((entity_by_id.get(entity_id) or {}).get("normalized") or {}).get("name") or
                                                      ((entity_by_id.get(entity_id) or {}).get("normalized") or {}).get("title") or entity_id))

    def document_fragment(document, page, *, include_diagrams=True):
        if not document:
            return "<p class=\"meta\">Документ не найден в каталоге.</p>"
        markdown = document.get("markdown") or {}
        rendered, compatibility = render_markdown(markdown, source_path=document.get("canonical_path", ""),
                                                   page_path=page, page_map=doc_map, image_map=image_map)
        if include_diagrams:
            rendered, _ = _inject_markdown_mermaid_blocks(rendered, diagram_svgs, diagram_specs,
                                                           source_path=document.get("canonical_path", ""))
        target = doc_map.get(document.get("canonical_path"), "docs/index.html")
        document_link = ("<span>встроен в эту карточку</span>" if target == page else
                         '<a href="%s">отдельная страница документа →</a>' %
                         html.escape(_href(page, target), quote=True))
        return '<article class="prose embedded-document"><p class="meta"><code>%s</code> · %s</p>%s</article>' % (
            html.escape(document.get("canonical_path", "")), document_link, rendered)

    for entity in bundle.get("entities") or []:
        if entity.get("kind") != "type":
            continue
        normalized = entity.get("normalized") or {}
        page = page_map[entity["entity_id"]]
        type_id = normalized.get("id") or entity["entity_id"].split(":", 1)[-1]
        instruction = document_by_id.get(normalized.get("instruction_document"))
        if instruction is None:
            instruction = next((item for item in bundle.get("documents") or []
                                if item.get("canonical_path") == normalized.get("instruction_path")), None)
        shared = [document_by_id[doc_id] for doc_id in normalized.get("shared_instruction_documents") or []
                  if doc_id in document_by_id]
        fields = []
        for field in normalized.get("fields") or []:
            if not isinstance(field, dict):
                continue
            fields.append((field.get("name", "поле"), "%s%s%s" % (
                field.get("type", "—"),
                " · обязательно" if field.get("required") else " · необязательно",
                (" · варианты: " + ", ".join(str(item) for item in field.get("enum") or []))
                if field.get("enum") else "")))
        gates = [(key, value) for key, value in sorted((normalized.get("gates") or {}).items())]
        agents = [entity_by_id[item] for item in normalized.get("agent_refs") or [] if item in entity_by_id]
        if not agents:
            agents = [entity_by_id[item] for item in linked_ids(entity["entity_id"], kind="agent") if item in entity_by_id]
        step_ids = linked_ids(entity["entity_id"], kind="flow_step", incoming=True, relation_kinds={"implements"})
        flow_ids = sorted(set((entity_by_id[item].get("normalized") or {}).get("flow_ref")
                              for item in step_ids if item in entity_by_id))
        flow_ids = [item for item in flow_ids if item in entity_by_id]
        schema_ids = linked_ids(entity["entity_id"], kind="schema", relation_kinds={"uses"})
        template_ids = linked_ids(entity["entity_id"], kind="template", relation_kinds={"uses"})
        agent_cards = "".join('<a class="catalog-card" href="%s"><span class="kicker">Профиль агента</span><h3>%s</h3><p>%s · return contract и границы</p></a>' % (
            html.escape(_href(page, page_map.get(agent["entity_id"], "entities/index.html")), quote=True),
            html.escape(str((agent.get("normalized") or {}).get("name") or agent["entity_id"])),
            html.escape(str((agent.get("normalized") or {}).get("role") or "роль не указана"))) for agent in agents)
        flow_rows = "".join('<li>%s — %s</li>' % (
            entity_link(flow_id, page, ((entity_by_id.get(flow_id) or {}).get("normalized") or {}).get("name")),
            html.escape(", ".join((entity_by_id.get(step_id, {}).get("normalized") or {}).get("id", "шаг")
                                  for step_id in step_ids
                                  if (entity_by_id.get(step_id, {}).get("normalized") or {}).get("flow_ref") == flow_id)))
                          for flow_id in flow_ids)
        relation_cards = "".join('<a class="catalog-card" href="%s"><span class="kicker">%s</span><h3>%s</h3><p>Связь из relations · открыть контракт</p></a>' % (
            html.escape(_href(page, page_map.get(item["entity_id"], "entities/index.html")), quote=True),
            html.escape(_ru_kind(item.get("kind"))),
            html.escape(str((item.get("normalized") or {}).get("title") or (item.get("normalized") or {}).get("name") or item["entity_id"])))
            for item in [entity_by_id[item_id] for item_id in schema_ids + template_ids if item_id in entity_by_id])
        source_ref = entity.get("raw_ref") or (entity.get("source_refs") or [None])[0]
        source_href = _href(page, source_assets.get(source_ref, "sources/index.html"))
        body = (
            '<section class="hero"><div class="eyebrow">ПРОФИЛЬ ЗАДАЧИ · %s</div><h1>%s</h1>'
            '<p class="lead">Единая карточка типа: рабочая инструкция, общие этапы, роли, поля, gates, capabilities и связи с процессами.</p>'
            '<div class="doc-meta"><span class="pill">%s</span><code>%s</code><a class="pill good source-link" href="%s">Канонические bytes ↓</a></div></section>' % (
                html.escape(type_id), html.escape(str(normalized.get("name") or type_id)),
                html.escape(_ru_type_class(normalized.get("class", "product"))), html.escape(entity["entity_id"]),
                html.escape(source_href, quote=True))
            + '<div class="grid"><div><h2>Правила приёма</h2>%s</div><div><h2>Исполнитель</h2>%s</div></div>' % (
                _field_table(gates) or '<p>Гейты не объявлены.</p>',
                _field_table([("роль", (normalized.get("executor") or {}).get("role") if isinstance(normalized.get("executor"), dict) else normalized.get("executor")),
                              ("tier", (normalized.get("executor") or {}).get("tier") if isinstance(normalized.get("executor"), dict) else None),
                              ("режим", (normalized.get("executor") or {}).get("mode") if isinstance(normalized.get("executor"), dict) else None),
                              ("редактор", normalized.get("editor"))]) or '<p>Исполнитель выбирается runtime по профилю.</p>')
            + '<h2>Рабочая инструкция</h2>' + document_fragment(instruction, page)
            + '<h2>Общие этапы и бриф</h2><div class="catalog-grid">%s</div>' %
              "".join('<a class="catalog-card" href="%s"><span class="kicker">Общий Markdown</span><h3>%s</h3><p>%s</p></a>' % (
                  html.escape(_href(page, doc_map.get(doc.get("canonical_path"), "docs/index.html")), quote=True),
                  html.escape(_doc_summary(doc)), html.escape(doc.get("canonical_path", ""))) for doc in shared)
            + '<h2>Поля типа</h2>' + (_field_table(fields) if fields else '<p>Дополнительных полей нет.</p>')
            + '<h2>Capabilities и проверки</h2>' + (_field_table([("capabilities", ", ".join(str(item) for item in normalized.get("capabilities") or [])),
                                                                    ("checks", ", ".join(str(item) for item in normalized.get("checks") or []))]) or '<p>Дополнительные capability/checks не объявлены.</p>')
            + '<h2>Роли и agent profiles</h2><div class="catalog-grid">%s</div>' % (agent_cards or '<div class="callout">Для типа нет отдельного agent profile.</div>')
            + '<h2>Связанные flows и lifecycle</h2>%s%s' % (
                '<ul>%s</ul>' % flow_rows if flow_rows else '<p>Пока нет flow-step relation для этого типа.</p>',
                '<p class="source-note">Откройте flow по ссылке: там lifecycle/process map, gates, decisions и handoff показаны на одном экране.</p>')
            + '<h2>Связанные templates и schemas</h2><div class="catalog-grid">%s</div>' %
              (relation_cards or '<p>Связанные стартовые формы и контракты не обнаружены.</p>')
            + _tech_details("Технический type.json", normalized)
            + _tech_details("Relations этой карточки", [item for item in relation_rows
                                                        if item.get("from") == entity["entity_id"] or item.get("to") == entity["entity_id"]])
        )
        add_page(page, str(normalized.get("name") or type_id), body, entity["entity_id"])

    # Generic entity pages cover workspaces, queues, elements, roles, schemas and
    # any future adapter entity without changing the HTML contract.
    for entity in bundle.get("entities") or []:
        # Dedicated renderers below own these paths; do not emit a generic page
        # first and then silently replace it (that would duplicate manifest rows).
        if entity.get("kind") in {"task", "document", "markdown", "flow", "type", "flow_step", "skill", "agent", "schema", "template", "source_file", "role"}:
            continue
        page = page_map.get(entity["entity_id"])
        if not page or page == "entities/index.html":
            continue
        normalized = entity.get("normalized") or {}
        entity_kind = entity.get("kind", "entity")
        entity_title = normalized.get("title") or normalized.get("name") or entity["entity_id"]
        human_fields = []
        for key, value in sorted(normalized.items()):
            if key in {"task", "raw", "provenance", "title", "description",
                       "description_source"} or value in (None, "", [], {}):
                continue
            human_fields.append((key, value))
        description = str(normalized.get("description") or "").strip()
        if description:
            purpose = '<div class="schema-purpose"><strong>Назначение</strong><p>%s</p><p class="meta">Описание из <code>%s</code>.</p></div>' % (
                html.escape(description),
                html.escape(str(normalized.get("description_source") or "канонического источника")))
        else:
            purpose = '<div class="schema-purpose"><strong>Назначение</strong><p>Описание не добавлено в канонический каталог; ниже показаны фактические технические поля.</p></div>'
        body = (
            '<section class="hero"><div class="eyebrow">%s</div><h1>%s</h1><p class="lead">%s · %s</p></section>' %
            (html.escape(_ru_kind(entity_kind)), html.escape(str(entity_title)),
             html.escape(description or "Технический контракт без человекочитаемого описания"),
             html.escape(entity["entity_id"]))
            + purpose
            + '<h2>Коротко</h2>' + (_field_table(human_fields) or '<p>Для этой сущности нет дополнительных полей.</p>')
            + '<h2>Источник и происхождение</h2><p class="source-note">Сущность собрана адаптером из канонического источника; исходные bytes доступны на странице источников.</p>'
            + _tech_details("Технические данные (для проверки)", normalized)
            + _tech_details("Provenance", entity.get("provenance") or [])
        )
        add_page(page, str(entity_title), body, entity["entity_id"])

    # Contracts have their own human view. Registry metadata and file-backed
    # JSON Schema records with the same logical identity share one page; the
    # page contains both the human purpose and the technical contract.
    schema_groups = defaultdict(list)
    for schema_entity in bundle.get("entities") or []:
        if schema_entity.get("kind") != "schema":
            continue
        schema_normalized = schema_entity.get("normalized") or {}
        schema_identity = _schema_identity(schema_normalized.get("schema_id") or
                                           schema_normalized.get("name") or
                                           schema_entity.get("entity_id"))
        schema_groups[schema_identity].append(schema_entity)
    schema_primary_ids = set()
    schema_counterparts = {}
    for schema_identity, group in schema_groups.items():
        primary = sorted(group, key=lambda item: (
            0 if str(item.get("entity_id", "")).startswith("schema:registry:") else 1,
            str(item.get("entity_id", ""))))[0]
        schema_primary_ids.add(primary.get("entity_id"))
        schema_counterparts[primary.get("entity_id")] = [item for item in group if item is not primary]

    for entity in bundle.get("entities") or []:
        if entity.get("kind") not in {"schema", "template"}:
            continue
        if entity.get("kind") == "schema" and entity.get("entity_id") not in schema_primary_ids:
            continue
        normalized = entity.get("normalized") or {}
        page = page_map[entity["entity_id"]]
        schema_counterpart = (schema_counterparts.get(entity.get("entity_id")) or [None])[0] if entity.get("kind") == "schema" else None
        source_entity_for_link = schema_counterpart or entity
        source_ref = source_entity_for_link.get("raw_ref") or (source_entity_for_link.get("source_refs") or [None])[0]
        source_href = _href(page, source_assets.get(source_ref, "sources/index.html"))
        counterpart_normalized = (schema_counterpart or {}).get("normalized") or {}
        payload = (counterpart_normalized.get("payload") if isinstance(counterpart_normalized.get("payload"), dict) else
                   normalized.get("payload") if isinstance(normalized.get("payload"), dict) else {})
        related = []
        related_entity_ids = {entity["entity_id"]}
        if schema_counterpart:
            related_entity_ids.add(schema_counterpart.get("entity_id"))
        for relation in relation_rows:
            other = None
            if relation.get("from") in related_entity_ids:
                other = relation.get("to")
            elif relation.get("to") in related_entity_ids:
                other = relation.get("from")
            if other in entity_by_id:
                related.append(entity_by_id[other])
        related_cards = "".join('<a class="catalog-card" href="%s"><span class="kicker">%s</span><h3>%s</h3><p>Связь из AUTODOC-RELATION-1</p></a>' % (
            html.escape(_href(page, page_map.get(item["entity_id"], "entities/index.html")), quote=True),
            html.escape(_ru_kind(item.get("kind"))),
            html.escape(str((item.get("normalized") or {}).get("title") or (item.get("normalized") or {}).get("name") or item["entity_id"])))
            for item in sorted(related, key=lambda item: item.get("entity_id", "")))
        if entity.get("kind") == "schema":
            contract_view = counterpart_normalized or normalized
            properties = payload.get("properties") if isinstance(payload.get("properties"), dict) else {}
            property_rows = []
            for name, definition in sorted(properties.items()):
                if isinstance(definition, dict):
                    value = definition.get("type") or definition.get("const") or definition.get("enum") or "объект"
                    description = definition.get("description") or ""
                else:
                    value, description = _human_value(definition), ""
                marker = "обязательно" if name in (contract_view.get("required_fields") or []) else "необязательно"
                property_rows.append((name, "%s · %s%s" % (value, marker, (" · " + description) if description else "")))
            purpose = "Каталог контрактов проекта. Runtime-валидаторы читают эти JSON Schema, а autodoc показывает их назначение и связи; generated output сюда не записывается."
            body = (
                '<section class="hero"><div class="eyebrow">КАТАЛОГ КОНТРАКТОВ · SCHEMA</div><h1>%s</h1>'
                '<p class="lead">%s</p><div class="doc-meta"><span class="pill">version %s</span><code>%s</code><a class="pill good source-link" href="%s">Канонический schema JSON ↓</a></div></section>' % (
                    html.escape(str(normalized.get("title") or contract_view.get("title") or normalized.get("schema_id") or entity["entity_id"])),
                    html.escape(purpose), html.escape(str(contract_view.get("contract_version") or normalized.get("schema_id"))),
                    html.escape(str(normalized.get("schema_id") or contract_view.get("schema_id") or entity["entity_id"])), html.escape(source_href, quote=True))
                + ('<a class="pill good source-link" href="%s">Registry source ↓</a>' % html.escape(_href(page, source_assets.get(entity.get("raw_ref"), "sources/index.html")), quote=True)
                   if schema_counterpart else '')
                + '<div class="schema-purpose"><strong>Назначение</strong><p>%s</p><p class="meta">Кто читает: %s · что проверяет: %s · source path: <code>%s</code></p></div>' % (
                    html.escape(str(normalized.get("description") or contract_view.get("description") or "Назначение описано в каталоге schema.")),
                    html.escape(", ".join(str(item) for item in contract_view.get("readers") or [])),
                    html.escape(", ".join(str(item) for item in contract_view.get("validators") or [])),
                    html.escape(str(contract_view.get("source_path") or normalized.get("source_path") or "—")))
                + '<h2>Поля контракта</h2>' + (_field_table(property_rows) if property_rows else _field_table([("ключи", contract_view.get("field_names") or contract_view.get("keys") or [])]))
                + '<h2>Связанные сущности</h2><div class="catalog-grid">%s</div>' % (related_cards or '<p>Явных relations пока нет.</p>')
                + _tech_details("Технический JSON Schema", contract_view)
                + (_tech_details("Registry metadata", normalized) if schema_counterpart else '')
                + _tech_details("Provenance", (entity.get("provenance") or []) + ((schema_counterpart or {}).get("provenance") or []))
            )
            add_page(page, str(normalized.get("title") or normalized.get("schema_id")), body, entity["entity_id"])
        else:
            payload_fields = [(key, ("%s · %s" % (type(value).__name__, _human_value(value))))
                              for key, value in sorted(payload.items())]
            schema_links = "".join(entity_link(item["entity_id"], page,
                                                (item.get("normalized") or {}).get("title") or item["entity_id"])
                                   for item in related if item.get("kind") == "schema")
            body = (
                '<section class="hero"><div class="eyebrow">СТАРТОВАЯ ФОРМА · TEMPLATE</div><h1>%s</h1>'
                '<p class="lead">%s</p><div class="doc-meta"><code>%s</code><a class="pill good source-link" href="%s">Канонический template JSON ↓</a></div></section>' % (
                    html.escape(str(normalized.get("title") or normalized.get("path") or entity["entity_id"])),
                    html.escape(str(normalized.get("purpose") or "Стартовая форма данных для CLI и проектных writers.")),
                    html.escape(str(normalized.get("path") or entity["entity_id"])), html.escape(source_href, quote=True))
                + '<div class="schema-purpose"><strong>Назначение</strong><p>Template — не runtime-факт, а безопасная стартовая форма. Его поля помогают создать запись, flow, type, роль, инструмент или отчёт; итоговые данные валидируются соответствующим schema/validator.</p><p class="meta">Schema usage: %s · validator usage: %s</p></div>' % (
                    html.escape(", ".join(str(item) for item in normalized.get("schema_usage") or []) or "не объявлено"),
                    html.escape(", ".join(str(item) for item in normalized.get("validator_usage") or [])))
                + '<h2>Поля стартовой формы</h2>' + (_field_table(payload_fields) or '<p>Пустая стартовая форма.</p>')
                + '<h2>Связанные schemas</h2><p>%s</p>' % (schema_links or "Схема связи не заявлена; validator usage остаётся в карточке." )
                + '<h2>Кто использует template</h2><div class="catalog-grid">%s</div>' % (related_cards or '<p>Связи использования пока не обнаружены.</p>')
                + _tech_details("Технический template payload", normalized)
                + _tech_details("Provenance", entity.get("provenance") or [])
            )
            add_page(page, str(normalized.get("title") or normalized.get("path")), body, entity["entity_id"])
    templates_index_cards = "".join('<a class="catalog-card" data-search-item href="%s"><span class="kicker">Шаблон</span><h3>%s</h3><p><code>%s</code> · %d полей · first-class starter payload</p></a>' % (
        html.escape(_href("templates/index.html", page_map[item["entity_id"]]), quote=True),
        html.escape(str((item.get("normalized") or {}).get("title") or item["entity_id"])),
        html.escape(str((item.get("normalized") or {}).get("path") or item["entity_id"])),
        len(((item.get("normalized") or {}).get("payload") or {}).keys()) if isinstance((item.get("normalized") or {}).get("payload"), dict) else 0)
        for item in bundle.get("entities") or [] if item.get("kind") == "template")
    add_page("templates/index.html", "Шаблоны", '<section class="hero"><div class="eyebrow">FIRST-CLASS TEMPLATES</div><h1>Шаблоны проекта</h1><p class="lead">Стартовые payload-формы с разобранными полями, назначением, schema/validator usage и кликабельными связями с типами, flows и контрактами. Канонический каталог templates/ остаётся только источником истины.</p></section><div class="catalog-grid">%s</div>' % (templates_index_cards or '<div class="callout">Шаблоны не обнаружены.</div>'))

    # Skills and sealed agent profiles are first-class operational entities too.
    skill_cards = "".join('<a class="catalog-card" id="skill-%s" data-search-item href="%s"><span class="kicker">Навык</span><h3>%s</h3><p><code>%s</code> · основной текст в документации</p></a>' % (
        html.escape(_slug(item["entity_id"].split(":", 1)[-1]), quote=True),
        html.escape(_href("skills/index.html", page_map[item["entity_id"]]), quote=True),
        html.escape(str((item.get("normalized") or {}).get("name") or item["entity_id"])),
        html.escape(str((item.get("normalized") or {}).get("path") or "")))
        for item in bundle.get("entities") or [] if item.get("kind") == "skill")
    add_page("skills/index.html", "Навыки", '<section class="hero"><div class="eyebrow">SKILLS</div><h1>Навыки и процедурные знания</h1><p class="lead">SKILL.md и child-skills индексируются как связанные сущности. Главный skill — маршрутизатор; дочерние документы — исполняемые процедуры с provenance.</p></section><div class="catalog-grid">%s</div>' % (skill_cards or '<div class="callout">Skills не обнаружены.</div>'))

    agent_cards = "".join('<a class="catalog-card" data-search-item href="%s"><span class="kicker">Agent profile</span><h3>%s</h3><p>role: %s · sealed return contract</p></a>' % (
        html.escape(_href("agents/index.html", page_map[item["entity_id"]]), quote=True),
        html.escape(str((item.get("normalized") or {}).get("name") or item["entity_id"])),
        html.escape(str((item.get("normalized") or {}).get("role") or "—")))
        for item in bundle.get("entities") or [] if item.get("kind") == "agent")
    for agent in bundle.get("entities") or []:
        if agent.get("kind") != "agent":
            continue
        normalized = agent.get("normalized") or {}
        page = page_map[agent["entity_id"]]
        profile = normalized.get("profile") if isinstance(normalized.get("profile"), dict) else {}
        used_by = []
        for relation in relation_rows:
            other = None
            if relation.get("from") == agent["entity_id"]:
                other = relation.get("to")
            elif relation.get("to") == agent["entity_id"]:
                other = relation.get("from")
            if other in entity_by_id:
                used_by.append(entity_by_id[other])
        used_cards = "".join('<a class="catalog-card" href="%s"><span class="kicker">Использует</span><h3>%s</h3><p>%s</p></a>' % (
            html.escape(_href(page, page_map.get(item["entity_id"], "entities/index.html")), quote=True),
            html.escape(str((item.get("normalized") or {}).get("name") or item["entity_id"])),
            html.escape(_ru_kind(item.get("kind")))) for item in sorted(used_by, key=lambda item: item.get("entity_id", "")))
        role_id = "role:%s" % normalized.get("role") if normalized.get("role") else None
        role_link = entity_link(role_id, page, normalized.get("role"), fragment=False) if role_id in entity_by_id else html.escape(str(normalized.get("role") or "—"))
        body = ('<section class="hero"><div class="eyebrow">AGENT PROFILE</div><h1>%s</h1><p class="lead">Запечатанный профиль исполнителя: инструменты, границы, формат возврата и место сохранения evidence.</p><div class="doc-meta"><span class="pill">role: %s</span><code>%s</code></div></section>' % (
            html.escape(str(normalized.get("name") or agent["entity_id"])), role_link, html.escape(str(normalized.get("source_path") or "")))
            + '<h2>Профиль и contract</h2>' + _field_table([(key, value) for key, value in sorted(profile.items()) if key != "name"])
            + '<h2>Кто использует профиль</h2><div class="catalog-grid">%s</div>' % (used_cards or '<p>Прямые relations использования не обнаружены.</p>')
            + _tech_details("Технический agents/*.json", profile)
            + _tech_details("Provenance", agent.get("provenance") or []))
        add_page(page, str(normalized.get("name") or agent["entity_id"]), body, agent["entity_id"])
    role_sections = []
    for role_entity in sorted((item for item in bundle.get("entities") or [] if item.get("kind") == "role"),
                              key=lambda item: str((item.get("normalized") or {}).get("role") or item["entity_id"]).lower()):
        role_normalized = role_entity.get("normalized") or {}
        role_name = role_normalized.get("role") or role_normalized.get("name") or role_entity["entity_id"].split(":", 1)[-1]
        role_agents = [item for item in bundle.get("entities") or []
                       if item.get("kind") == "agent" and
                       str((item.get("normalized") or {}).get("role") or "") == str(role_name)]
        role_agent_links = " ".join(
            '<a class="entity-chip" href="%s">%s</a>' % (
                html.escape(_href("agents/index.html", page_map.get(item["entity_id"], "agents/index.html")), quote=True),
                html.escape(str((item.get("normalized") or {}).get("name") or item["entity_id"])))
            for item in sorted(role_agents, key=lambda item: item.get("entity_id", "")))
        role_sections.append(
            '<section id="role-%s" class="callout"><div class="kicker">РОЛЬ</div><h2>%s</h2><p>%s</p><p class="meta">Agent profiles: %s</p></section>' % (
                html.escape(_slug(role_name), quote=True),
                html.escape(_RU_ROLE_NAMES.get(str(role_name), str(role_name))),
                html.escape(_RU_ROLE_PURPOSES.get(str(role_name), "Разрешённая роль исполнения в runtime.")),
                role_agent_links or "не заявлены"))
    add_page("agents/index.html", "Профили агентов", '<section class="hero"><div class="eyebrow">AGENTS AND ROLES</div><h1>Роли и профили агентов</h1><p class="lead">Каждый agents/*.json разобран как sealed profile и связан с типом, ролью, flow-step и return contract. Роль и agent profile находятся на одной вторичной странице.</p></section><div class="catalog-grid">%s</div>%s' % (agent_cards or '<div class="callout">Профили агентов не обнаружены.</div>', "".join(role_sections)))

    # Tasks have a more useful dedicated view.
    for entity in bundle.get("entities") or []:
        if entity.get("kind") != "task":
            continue
        page = page_map[entity["entity_id"]]
        task = (entity.get("normalized") or {}).get("task") or {}
        source_ref = entity.get("raw_ref")
        source_link = _href(page, source_assets.get(source_ref, "sources/index.html"))
        blocks = []
        field_titles = {"problem": "Проблема", "goals": "Цели", "acceptance": "Критерии приёмки",
                        "verify": "Проверка", "steps": "Шаги", "open_questions": "Открытые вопросы",
                        "comments": "Комментарии", "refs": "Связи", "artifacts": "Артефакты", "notes": "Заметки"}
        for key in ("problem", "goals", "acceptance", "verify", "steps", "open_questions", "comments", "refs", "artifacts", "notes"):
            values = task.get(key)
            if not values:
                continue
            raw_values = values if isinstance(values, list) else [values]
            rows = []
            for value in raw_values:
                if isinstance(value, dict):
                    text = value.get("text") or value.get("title") or value.get("note") or _human_value(value)
                    suffix = _status_pill(value.get("status")) if value.get("status") else ""
                    rows.append("<li>%s %s</li>" % (html.escape(str(text)), suffix))
                else:
                    rows.append("<li>%s</li>" % html.escape(str(value)))
            blocks.append('<section><h3>%s</h3><ul>%s</ul></section>' % (field_titles.get(key, key), "".join(rows)))
        meta_fields = [(key, task.get(key)) for key in ("status", "priority", "phase", "owner", "release", "due", "estimate_h", "kind")]
        body = (
            '<section class="hero"><div class="eyebrow">ЗАДАЧА</div><h1>%s</h1><p class="lead">%s · <code>%s</code></p><p><a class="pill good source-link" href="%s">Скачать канонический task source ↓</a></p></section>' %
            (html.escape(task.get("title") or entity["entity_id"]), _status_pill(task.get("status", entity.get("status", "unknown"))),
             html.escape(entity["entity_id"]), html.escape(source_link, quote=True))
            + '<h2>Основные поля</h2>' + _field_table(meta_fields)
            + "".join(blocks)
            + _tech_details("Технические поля task.json", task)
        )
        _write_text(os.path.join(html_root, page), _page_shell(task.get("title") or entity["entity_id"], body, page_path=page, bundle=bundle))
        pages.append({"path": page, "title": task.get("title") or entity["entity_id"],
                      "entity_id": entity["entity_id"], "sha256": sha256_file(os.path.join(html_root, page))})
    task_cards = "".join(
        '<a class="catalog-card" data-search-item href="%s"><span class="kicker">Задача</span><h3>%s</h3><p>%s · %s</p></a>' %
        (html.escape(_href("tasks/index.html", page_map[e["entity_id"]]), quote=True),
         html.escape(((e.get("normalized") or {}).get("task") or {}).get("title") or e["entity_id"]),
         html.escape(e["entity_id"]), _ru_status(((e.get("normalized") or {}).get("task") or {}).get("status", e.get("status", "unknown"))))
        for e in bundle.get("entities") or [] if e.get("kind") == "task")
    task_index = '<section class="hero"><div class="eyebrow">РАБОТА</div><h1>Задачи</h1><p class="lead">Канонические task-записи с понятными целями, критериями приёмки, проверками и доказательствами.</p></section><div class="catalog-grid">%s</div>' % (task_cards or '<div class="callout">В текущем workspace задач не обнаружено.</div>')
    if task_cards:
        add_page("tasks/index.html", "Задачи", task_index)
    # Markdown/docs pages. Type instructions are already embedded in their
    # richer type profile; keep the document in the bundle and source assets,
    # but do not publish a second page for the same instruction.
    for document in bundle.get("documents") or []:
        page = doc_map.get(document.get("canonical_path")) or "docs/%s.html" % _slug(document.get("document_id"))
        if page.startswith("types/"):
            continue
        markdown = document.get("markdown") or {}
        rendered, compatibility = render_markdown(markdown, source_path=document.get("canonical_path", ""),
                                                   page_path=page, page_map=doc_map,
                                                   image_map=image_map)
        rendered, mermaid_issues = _inject_markdown_mermaid_blocks(
            rendered, diagram_svgs, diagram_specs,
            source_path=document.get("canonical_path", ""))
        compatibility = list(compatibility) + list(mermaid_issues)
        headings = markdown.get("headings") or []
        toc = "<ul>%s</ul>" % "".join('<li><a href="#%s">%s</a></li>' %
                                        (html.escape(item.get("anchor", ""), quote=True),
                                         html.escape(item.get("text", ""))) for item in headings)
        source_link = _href(page, source_assets.get(document.get("source_ref"), "sources/index.html"))
        compat_labels = {"unsafe_html": "небезопасный HTML", "unsafe_url": "небезопасная ссылка",
                         "missing_image": "отсутствует изображение", "broken_link": "битая локальная ссылка",
                         "unclosed_fence": "незакрытый блок кода"}
        compat = "".join("<li><strong>%s</strong> — %s</li>" %
                         (html.escape(compat_labels.get(item.get("kind"), item.get("kind", "неизвестная конструкция"))),
                          html.escape(item.get("message", "Проверить исходник")))
                         for item in compatibility) or "<li>Совместимость без замечаний.</li>"
        toc_html = '<div class="toc"><strong>Содержание документа</strong>%s</div>' % toc if headings else ""
        body = (
            '<section class="hero"><div class="eyebrow">ДОКУМЕНТАЦИЯ</div><h1>%s</h1><p class="lead">%s</p><div class="doc-meta"><span class="pill">revision %s</span><code>%s</code><a class="pill good source-link" href="%s">Скачать оригинальный Markdown ↓</a></div></section>' %
            (html.escape(_doc_summary(document)), html.escape(document.get("doc_key", document.get("document_id", "Документ"))),
             html.escape(str(document.get("revision", 1))), html.escape(document.get("canonical_path", "")),
             html.escape(source_link, quote=True))
            + toc_html
            + '<article class="prose">%s</article>' % rendered
            + '<details class="compat"%s><summary>Отчёт совместимости Markdown · замечаний: %d</summary><ul>%s</ul></details>' % (" open" if compatibility else "", len(compatibility), compat)
            + '<details class="raw-details"><summary>Технические данные и неподдержанные конструкции</summary><pre>%s</pre></details>' %
            html.escape(_json_dumps(markdown.get("raw_unknown") or [], pretty=True))
        )
        add_page(page, document.get("doc_key", document.get("document_id", "Docs")), body, document.get("document_id"))
    doc_groups = defaultdict(list)
    for document in bundle.get("documents") or []:
        path = document.get("canonical_path", "")
        group = path.split("/", 1)[0] if "/" in path else "Корень"
        doc_groups[group].append(document)
    group_titles = {"docs": "Каноническая документация", "flows": "Инструкции потоков",
                    "references": "Справочники", "types": "Инструкции типов", "Корень": "Корневые документы"}
    grouped_html = ""
    for group, documents in sorted(doc_groups.items(), key=lambda item: (group_titles.get(item[0], item[0]), item[0])):
        cards = "".join(
            '<a class="catalog-card" data-search-item href="%s"><span class="kicker">%s</span><h3>%s</h3><p><code>%s</code> · %d заголовков</p></a>' %
            (html.escape(_href("docs/index.html", doc_map.get(d.get("canonical_path"), "docs/index.html")), quote=True),
             html.escape(group_titles.get(group, group)), html.escape(_doc_summary(d)),
             html.escape(d.get("canonical_path", "")), len((d.get("markdown") or {}).get("headings") or []))
            for d in sorted(documents, key=lambda item: item.get("canonical_path", "")))
        grouped_html += '<section><div class="section-head"><div><div class="kicker">%s</div><h2>%s</h2></div><span class="meta">%d документов</span></div><div class="catalog-grid">%s</div></section>' % (
            html.escape(group), html.escape(group_titles.get(group, group)), len(documents), cards)
    docs_index = (
        '<section class="hero"><div class="eyebrow">КАТАЛОГ</div><h1>Вся документация</h1><p class="lead">Каждый Markdown-файл показан как читаемый документ: содержание, заголовки, таблицы, списки, цитаты, код и ссылка на исходные bytes.</p><p class="source-note">Используйте поиск слева, чтобы быстро найти раздел на этой странице.</p></section>'
        '<p id="search-empty" class="warning" hidden>Ничего не найдено на этой странице.</p>' + grouped_html)
    add_page("docs/index.html", "Каталог документации", docs_index)
    # Flow pages with complete textual state and diagram links.
    # A provenance/architecture diagram references many entities. Flow pages
    # must select their exact flow projection, never the last broad diagram that
    # happens to list the same entity as provenance.
    diagram_by_entity = {ref: spec for spec in bundle.get("diagrams") or []
                         if spec.get("kind") == "flow"
                         for ref in spec.get("source_entity_refs", [])}
    for entity in bundle.get("entities") or []:
        if entity.get("kind") != "flow":
            continue
        normalized = entity.get("normalized") or {}
        spec = diagram_by_entity.get(entity["entity_id"])
        page = page_map[entity["entity_id"]]
        svg_link = _href(page, spec.get("asset_path")) if spec else ""
        steps = normalized.get("steps") or []
        step_cards = []
        for number, step in enumerate(steps, 1):
            inputs = step.get("input_from") or []
            route_text = ["%s → %s" % (key, value)
                          for key, value in _declared_routes(step)]
            flags = []
            if step.get("optional"): flags.append("необязательный")
            if step.get("parallel"): flags.append("параллельный")
            if step.get("fan_out"): flags.append("fan-out: %s" % _human_value(step.get("fan_out")))
            if step.get("gate_out"): flags.append("gate: %s" % _human_value(step.get("gate_out")))
            control_html = ""
            tree = step.get("decision_tree")
            if isinstance(tree, dict):
                control_html += '<p class="route">Decision tree: %s · узел входа: %s</p>' % (
                    html.escape(str(tree.get("id", "без имени"))),
                    html.escape(str(tree.get("root", "—"))))
            step_type_id = "type:%s" % step.get("type") if step.get("type") else None
            step_type_html = entity_link(step_type_id, page, step.get("type"), fragment=False) if step_type_id in entity_by_id else html.escape(str(step.get("type", "—")))
            executor = step.get("executor") or {}
            if isinstance(executor, dict) and executor.get("role"):
                role_id = "role:%s" % executor.get("role")
                role_html = entity_link(role_id, page, str(executor.get("role")), fragment=False) if role_id in entity_by_id else html.escape(str(executor.get("role")))
                control_html += '<p class="meta">Роль: %s · tier: %s · режим: %s</p>' % (role_html,
                    html.escape(str(executor.get("tier", "—"))), html.escape(str(executor.get("mode", "—"))))
            documentation = step.get("documentation")
            if isinstance(documentation, dict):
                question = documentation.get("question") or {}
                choices = question.get("choices") or []
                choice_labels = []
                for choice in choices:
                    if isinstance(choice, dict):
                        choice_labels.append(str(choice.get("label") or choice.get("id")))
                    else:
                        choice_labels.append(str(choice))
                requirement = "обязательная" if documentation.get("required") else "необязательная"
                question_text = question.get("text") or "вопрос не задан"
                control_html += '<p class="route">Документация: %s · вопрос: %s%s</p>' % (
                    requirement, html.escape(str(question_text)),
                    (' · варианты: ' + html.escape(", ".join(choice_labels))) if choice_labels else "")
            step_cards.append(
                '<article id="step-%s" class="step-card"><span class="step-no">%02d</span><div><h3>%s</h3>%s<p class="meta">Тип: <strong>%s</strong></p>%s%s%s%s</div></article>' %
                (_slug("%s:%s" % (normalized.get("id") or entity["entity_id"], step.get("id", "step"))),
                 number, html.escape(str(step.get("title") or step.get("name") or step.get("id", "шаг"))),
                 '<p>%s</p>' % html.escape(str(step.get("brief"))) if step.get("brief") else "",
                 step_type_html,
                 '<p>Вход после: %s</p>' % html.escape(", ".join(str(value) for value in inputs)) if inputs else "<p>Стартовый шаг потока.</p>",
                 '<p class="route">Переходы: %s</p>' % html.escape(" · ".join(route_text)) if route_text else "",
                 '<p class="meta">%s</p>' % html.escape(" · ".join(flags)) if flags else "",
                 control_html))
        persisted = (normalized.get("persisted_state_refs") or (spec or {}).get("persisted_state") or [])
        problems = (spec or {}).get("problems") or []
        problem_html = "".join('<li><strong>%s</strong>%s</li>' %
                                  (html.escape(_finding_title(item.get("code", "Проблема"))),
                                   (" — " + html.escape(item.get("message"))) if item.get("message") else "")
                              for item in problems) or "<li>Проблемных узлов не обнаружено.</li>"
        state_html = '<div class="state-grid"><div class="state-card"><h4>Сохранённое состояние</h4><p>%s</p></div><div class="state-card"><h4>Проблемные узлы</h4><p>%d</p></div><div class="state-card"><h4>Диаграмма</h4><p><a href="%s">Скачать SVG ↓</a></p></div></div>' % (
            html.escape(_human_value(persisted) if persisted else "В текущем workspace строк состояния нет; схема готова к отображению.") ,
            len(problems), html.escape(svg_link, quote=True))
        diagram_html = diagram_panel(spec.get("diagram_id"), "Карта процесса: шаги, переходы, gates и проблемные узлы.") if spec else '<div class="callout">Для потока не удалось построить Mermaid SVG.</div>'
        flow_instruction = document_by_id.get(normalized.get("instruction_document"))
        if flow_instruction is None:
            flow_instruction = next((item for item in bundle.get("documents") or []
                                     if item.get("canonical_path") == normalized.get("instruction_path")), None)
        flow_types = sorted(set("type:%s" % step.get("type") for step in steps if step.get("type") and
                                "type:%s" % step.get("type") in entity_by_id))
        flow_agents = sorted(set(agent_id for step_id in normalized.get("step_refs") or []
                                 for agent_id in linked_ids(step_id, kind="agent", relation_kinds={"uses"})))
        flow_schema_ids = linked_ids(entity["entity_id"], kind="schema", relation_kinds={"uses"})
        request_rows = []
        for step in steps:
            request_rows.append((step.get("id"), ", ".join(str(item) for item in step.get("input_from") or []) or "старт",
                                 ", ".join(str(item) for item in step.get("output") or []) or "—",
                                 "необязательный" if step.get("optional") else "обязательный"))
        flow_request_table = '<table class="data-table"><thead><tr><th>Шаг</th><th>Запрос после</th><th>Handoff / artifacts</th><th>Политика</th></tr></thead><tbody>%s</tbody></table>' % "".join(
            '<tr><th>%s</th><td>%s</td><td>%s</td><td>%s</td></tr>' % tuple(html.escape(str(value)) for value in row)
            for row in request_rows)
        related_type_cards = "".join('<a class="catalog-card" href="%s"><span class="kicker">Task type</span><h3>%s</h3><p>Тип шага потока · открыть профиль</p></a>' % (
            html.escape(_href(page, page_map.get(type_id, "types/index.html")), quote=True),
            html.escape(str((entity_by_id.get(type_id, {}).get("normalized") or {}).get("name") or type_id)))
            for type_id in flow_types)
        related_agent_cards = "".join('<a class="catalog-card" href="%s"><span class="kicker">Agent</span><h3>%s</h3><p>Роль исполнителя шага</p></a>' % (
            html.escape(_href(page, page_map.get(agent_id, "agents/index.html")), quote=True),
            html.escape(str((entity_by_id.get(agent_id, {}).get("normalized") or {}).get("name") or agent_id)))
            for agent_id in flow_agents)
        related_schema_cards = "".join('<a class="catalog-card" href="%s"><span class="kicker">Контракт</span><h3>%s</h3><p>Схема, которую читает или валидирует flow</p></a>' % (
            html.escape(_href(page, page_map.get(schema_id, "schemas/index.html")), quote=True),
            html.escape(str((entity_by_id.get(schema_id, {}).get("normalized") or {}).get("title") or schema_id)))
            for schema_id in flow_schema_ids)
        body = (
            '<section class="hero"><div class="eyebrow">ПРОЦЕСС</div><h1>%s</h1><p class="lead">Пошаговый маршрут полного жизненного цикла с переходами, условиями, исполнителями и сохранённым состоянием.</p><div class="doc-meta"><span class="pill">FLOW-2 · revision %s</span><code>%s</code></div></section>' %
            (html.escape(str(normalized.get("name") or normalized.get("id") or entity["entity_id"])),
             html.escape(str(normalized.get("version", 1))), html.escape(entity["entity_id"]))
            + '<div class="flow-layout"><div><h2>Карта процесса и lifecycle</h2>%s</div><div><h2>Состояние потока</h2>%s<h3>Проблемы и контроль</h3><ul>%s</ul></div></div>' % (diagram_html, state_html, problem_html)
            + '<h2>Цель и инструкция потока</h2>' + document_fragment(flow_instruction, page, include_diagrams=False)
            + '<h2>Запросы, handoff, gates и artifacts</h2>' + flow_request_table
            + '<h2>Шаги маршрута</h2><div class="step-list">%s</div>' % "".join(step_cards)
            + '<h2>Виды задач внутри процесса</h2><div class="catalog-grid">%s</div>' % (related_type_cards or '<p>Виды задач шагов не разрешились как entities.</p>')
            + '<h2>Роли и агенты</h2><div class="catalog-grid">%s</div>' % (related_agent_cards or '<p>Профили агентов для шагов не объявлены.</p>')
            + '<h2>Контракты процесса</h2><div class="catalog-grid">%s</div>' % (related_schema_cards or '<p>Связанные схемы не обнаружены.</p>')
            + _tech_details("Техническое описание flow.json", normalized)
            + _tech_details("Relations этого flow", [item for item in relation_rows
                                                      if item.get("from") == entity["entity_id"] or item.get("to") == entity["entity_id"]])
        )
        add_page(page, "Поток " + str(normalized.get("name") or normalized.get("id")), body, entity["entity_id"])
    flow_index_cards = "".join(
        '<a class="catalog-card" data-search-item href="%s"><span class="kicker">Процесс</span><h3>%s</h3><p>%d шагов · %d переходов · SVG включён</p></a>' %
        (html.escape(_href("flows/index.html", page_map[e["entity_id"]]), quote=True),
         html.escape((e.get("normalized") or {}).get("name") or e["entity_id"]),
         len((e.get("normalized") or {}).get("steps") or []),
         len((diagram_by_entity.get(e["entity_id"]) or {}).get("edges") or []))
        for e in bundle.get("entities") or [] if e.get("kind") == "flow")
    add_page("flows/index.html", "Совместимость: процессы", '<section class="hero"><div class="eyebrow">СОВМЕСТИМОСТЬ</div><h1>Старый адрес каталога процессов</h1><p class="lead">Основной экран теперь находится в разделе <a href="../processes/index.html">Процессы</a>. Эта страница сохранена как совместимый инвентаризационный слой.</p></section><div class="catalog-grid">%s</div>' % flow_index_cards)
    type_entities = sorted(
        [e for e in bundle.get("entities") or [] if e.get("kind") == "type"],
        key=lambda e: str((e.get("normalized") or {}).get("name") or e["entity_id"].split(":", 1)[-1]).casefold())
    type_index_cards = "".join(
        '<a class="catalog-card" data-search-item href="%s"><span class="kicker">Вид задачи</span><h3>%s</h3><p>%s · профиль полей, проверок и исполнителя</p></a>' %
        (html.escape(_href("types/index.html", page_map[e["entity_id"]]), quote=True),
         html.escape((e.get("normalized") or {}).get("name") or e["entity_id"].split(":", 1)[-1]),
         html.escape(_ru_type_class((e.get("normalized") or {}).get("class", "профиль"))))
        for e in type_entities)
    add_page("types/index.html", "Совместимость: виды задач", '<section class="hero"><div class="eyebrow">СОВМЕСТИМОСТЬ</div><h1>Виды задач внутри процессов</h1><p class="lead">Основной контекст вида задачи находится на странице <a href="../processes/index.html">Процессы</a>. Эта страница сохранена как вторичный инвентаризационный слой.</p></section><div class="catalog-grid">%s</div>' % type_index_cards)
    schema_index_cards = "".join(
        '<a class="catalog-card" data-search-item href="%s"><span class="kicker">%s</span><h3>%s</h3><p class="schema-code">%s</p><p>%s</p></a>' %
        (html.escape(_href("schemas/index.html", page_map[e["entity_id"]]), quote=True),
         html.escape("Схема" if e.get("kind") == "schema" else "Шаблон"),
         html.escape((e.get("normalized") or {}).get("title") or e["entity_id"].split(":", 2)[-1]),
         html.escape((e.get("normalized") or {}).get("schema_id") or e["entity_id"].split(":", 2)[-1]),
         html.escape((e.get("normalized") or {}).get("description") or
                     ("Ключей: %s" % len((e.get("normalized") or {}).get("keys") or [])
                      if e.get("kind") == "schema" else "Стартовая форма данных")))
        for e in bundle.get("entities") or []
        if e.get("kind") in ("schema", "template") and
        (e.get("kind") != "schema" or e.get("entity_id") in schema_primary_ids))
    add_page("schemas/index.html", "Схемы и шаблоны", '<section class="hero"><div class="eyebrow">КОНТРАКТЫ ДАННЫХ</div><h1>Схемы и шаблоны</h1><p class="lead">Сначала человеческое назначение и группа, затем технический идентификатор и ключи. Описания берутся из канонического каталога Markdown, а фактическая структура — из JSON Schema и runtime-реестра.</p></section><div class="catalog-grid">%s</div>' % schema_index_cards)
    # Legacy preza has a dedicated command section; keep its target page even
    # though current CLI facts come from the live bundle/command classes.
    legacy_commands = ((bundle.get("legacy_parity") or {}).get("inventory") or {}).get("commands") or []
    command_cards = "".join(
        '<article class="catalog-card" data-search-item id="%s"><span class="kicker">%s</span><h3><code>%s</code></h3><p>%s</p><p class="meta">Подкоманды: %s</p></article>' %
        (_slug(item.get("id")), html.escape((item.get("value") or {}).get("entry", "Команда")),
         html.escape(item.get("id", "")), html.escape((item.get("value") or {}).get("summary", "Без описания")),
         html.escape(", ".join((item.get("value") or {}).get("nested") or []) or "нет"))
        for item in legacy_commands)
    if command_cards:
        add_page("commands/index.html", "Команды", '<section class="hero"><div class="eyebrow">CLI</div><h1>Команды</h1><p class="lead">Человекочитаемый каталог точек входа, команд и подкоманд. Формальные флаги остаются внутри исходной документации и технических контрактов.</p></section><div class="catalog-grid">%s</div>' % command_cards)
    # Relations/graph projection is JSON, while the SVG is local and labelled.
    graph = {"schema": "AUTODOC-GRAPH-1", "bundle_id": bundle.get("bundle_id"),
             "nodes": [{"id": item["entity_id"], "kind": item.get("kind")} for item in bundle.get("entities") or []],
             "edges": [{"id": item["relation_id"], "from": item["from"], "to": item["to"], "kind": item["kind"], "resolution": item.get("resolution")} for item in bundle.get("relations") or []]}
    _write_json(os.path.join(html_root, "graph.json"), graph)
    audit = bundle.get("audit_input") or {}
    findings = audit.get("findings") or []
    finding_cards = "".join(
        '<article class="callout %s"><div class="kicker">%s · %s</div><h3>%s</h3><p>%s</p><p class="meta">Что сделать: %s</p><details class="json-details"><summary>Показать техническую привязку</summary><p class="meta">Код: <code>%s</code> · finding: <code>%s</code></p></details></article>' %
        ("error" if item.get("severity") in {"error", "blocker"} else "warning",
         "Ошибка" if item.get("severity") in {"error", "blocker"} else "Предупреждение",
         html.escape(str(item.get("severity", "warning"))), html.escape(_finding_title(item.get("code"))),
         html.escape(item.get("message", "Проверить источник.")), html.escape(item.get("suggested_action", "Открыть источник и повторить сборку.")),
         html.escape(item.get("code", "")), html.escape(item.get("finding_id", "")))
        for item in findings)
    if not finding_cards:
        finding_cards = '<div class="ok"><strong>Проблем не найдено.</strong> Bundle и локальный HTML можно читать и проверять.</div>'
    audit_body = (
        '<section class="hero"><div class="eyebrow">КОНТРОЛЬ</div><h1>Аудит и совместимость</h1><p class="lead">Здесь объясняется, что требует внимания, почему это важно и где находится исходный материал. Технические коды скрыты внутри раскрывающихся блоков.</p><p>%s · замечаний: %d</p></section>' %
        (_status_pill(audit.get("verdict", "not_run")), len(findings))
        + '<h2>Карта проверок</h2>' + diagram_panel("audit-map", "Gates, предупреждения и проблемные узлы")
        + '<h2>Что требует внимания</h2><div class="entity-list">%s</div>' % finding_cards)
    legacy = bundle.get("legacy_parity") or {}
    legacy_sections = legacy.get("sections") or []
    legacy_inventory = legacy.get("inventory") or {}
    legacy_rows = "".join("<tr><td><strong>%s</strong></td><td>%s</td><td>%s</td><td><span class=\"meta\">%s</span></td></tr>" %
                          (html.escape(item.get("id", "")), _status_pill(item.get("status", "unknown")),
                           html.escape(item.get("target_page", "")), html.escape(str(item.get("content_digest", ""))[:24] + "…"))
                          for item in legacy_sections)
    inventory_counts = "".join('<div class="stat"><span class="metric">%d</span><span class="label">%s</span></div>' %
                                (len(value) if isinstance(value, list) else 0, html.escape(_ru_kind(key)))
                                for key, value in sorted(legacy_inventory.items()))
    parity_inventory = ((legacy.get("parity") or {}).get("inventory") or legacy_inventory)
    inventory_rows = "".join(
        "<tr data-search-item><td><strong>%s</strong></td><td>%s</td><td>%s</td><td><span class=\"meta\">%s</span></td></tr>" %
        (html.escape(category), html.escape(str(item.get("id", ""))), _status_pill(item.get("status", "unknown")),
         html.escape(str(item.get("target_page", ""))))
        for category, values in sorted(parity_inventory.items()) if isinstance(values, list)
        for item in values)
    if legacy_sections:
        audit_body += '<h2 id="legacy-facts">PREZA-PARITY-1: что перенесено</h2><p class="lead">Каждый legacy-раздел и каждый item имеет статус, назначение и ссылку на цель. <code>facts-v07.json</code> остаётся evidence, а не источником истины.</p><div class="stats">%s</div><div class="prose"><table class="data-table"><thead><tr><th>Раздел</th><th>Состояние</th><th>Где читать</th><th>Digest</th></tr></thead><tbody>%s</tbody></table></div><h3>Полный inventory parity</h3><div class="prose"><table class="data-table"><thead><tr><th>Семейство</th><th>Элемент</th><th>Состояние</th><th>Где читать</th></tr></thead><tbody>%s</tbody></table></div>' % (inventory_counts, legacy_rows, inventory_rows)
    add_page("audit/index.html", "Аудит и совместимость", audit_body)
    source_entity_by_path = {
        (item.get("normalized") or {}).get("path"): item
        for item in bundle.get("entities") or [] if item.get("kind") == "source_file"
    }

    def source_raw_preview(source):
        raw = source.get("raw")
        if raw is None:
            return "[Оригинальные bytes недоступны по политике хранения.]"
        if source.get("raw_encoding") == "base64":
            return "[Бинарный source; используйте локальную ссылку «Скачать».]"
        text = str(raw)
        if source.get("media_type") == "application/json":
            try:
                return _json_dumps(json.loads(text), pretty=True)
            except (TypeError, ValueError):
                pass
        return text

    def source_row(source):
        path = source.get("canonical_path", "")
        source_entity = source_entity_by_path.get(path) or {}
        normalized = source_entity.get("normalized") or {}
        page_target = page_map.get("source_file:%s" % path, "sources/index.html#source-%s" % _slug(path))
        source_href = _href("sources/index.html", page_target)
        adapter_links = []
        for entity_id in normalized.get("adapted_entity_refs") or []:
            target = page_map.get(entity_id)
            if target:
                adapter = entity_by_id.get(entity_id) or {}
                adapter_name = ((adapter.get("normalized") or {}).get("title") or
                                (adapter.get("normalized") or {}).get("name") or entity_id)
                adapter_links.append('<a class="entity-chip" href="%s">%s</a>' % (
                    html.escape(_href("sources/index.html", target), quote=True), html.escape(str(adapter_name))))
        adapters = " ".join(adapter_links) or '<span class="meta">только raw source</span>'
        raw_preview = source_raw_preview(source)
        details = (
            '<details class="raw-details"><summary>Полная запись, provenance и raw bytes</summary>'
            '<p class="meta">source id: <code>%s</code> · SHA-256: <code>%s</code></p>'
            '<p>Адаптеры: %s</p>'
            '<pre class="source-code">%s</pre>'
            '<details class="json-details"><summary>Provenance source record</summary><pre>%s</pre></details>'
            '</details>' % (
                html.escape(str(source.get("source_id", ""))),
                html.escape(str(source.get("sha256", ""))),
                adapters,
                html.escape(raw_preview),
                html.escape(_json_dumps(source.get("provenance") or [], pretty=True))))
        original = ('<a class="pill good" href="%s">Скачать ↓</a>' %
                    html.escape(_href("sources/index.html", source_assets[source["source_id"]]), quote=True)) if source.get("source_id") in source_assets else '<span class="meta">недоступно</span>'
        return (
            '<tr id="source-%s" data-search-item><td><strong><a href="%s">%s</a></strong><br><span class="meta">%s</span>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' %
            (html.escape(_slug(path), quote=True), html.escape(source_href, quote=True),
             html.escape(path), html.escape(source.get("source_domain", "")), details,
             html.escape(source.get("media_type", "")), html.escape(_human_value(source.get("byte_size"))),
             _status_pill("preserved" if source.get("source_of_truth") else "transformed"), original))

    source_rows = "".join(source_row(source) for source in bundle.get("sources") or [])
    source_body = '<section class="hero"><div class="eyebrow">PROVENANCE</div><h1>Источники и provenance</h1><p class="lead">Один технический каталог вместо отдельных fallback-страниц. Раскройте запись, чтобы увидеть канонические bytes, provenance, SHA-256, адаптеры и локальную ссылку на оригинал.</p></section><h2>Лента происхождения</h2>' + diagram_panel("provenance-timeline", "Связь источников, адаптеров и сущностей") + '<div class="prose"><table id="source-table" class="data-table"><thead><tr><th>Источник</th><th>Формат</th><th>Размер</th><th>Роль</th><th>Оригинал</th></tr></thead><tbody>%s</tbody></table></div>' % source_rows
    add_page("sources/index.html", "Источники и provenance", source_body)
    reconstruction = bundle.get("reconstruction") or {}
    recon_body = (
        '<section class="hero"><div class="eyebrow">ВОССТАНОВЛЕНИЕ</div><h1>Безопасное восстановление</h1><p class="lead">Восстановление возвращает только разрешённые канонические bytes. Скрипты не запускаются, generated HTML и индексы не принимаются за источник истины.</p></section>'
        '<div class="stats"><div class="stat"><span class="metric">%d</span><span class="label">можно восстановить</span></div><div class="stat"><span class="metric">%d</span><span class="label">пропущено</span></div><div class="stat"><span class="metric">%d</span><span class="label">нужно решение человека</span></div></div>' %
        (len(reconstruction.get("source_refs") or []), len(reconstruction.get("skipped") or []), len(reconstruction.get("requires_human") or []))
        + '<div class="callout"><strong>Правило:</strong> абсолютные пути, traversal, duplicate targets и symlink escape отклоняются до публикации target.</div>'
        + _tech_details("Технический reconstruction contract", reconstruction)
    )
    add_page("reconstruction/index.html", "Безопасное восстановление", recon_body)
    # Search is deterministic and does not execute JavaScript or fetch anything.
    _write_json(os.path.join(html_root, "search.json"), sorted(search, key=lambda item: (item.get("title", ""), item.get("path", ""))))
    manifest = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                "schema": AUTODOC_HTML_SCHEMA, "html_id": "html:" + bundle.get("canonical_digest", "").split(":", 1)[-1],
                "bundle_id": bundle.get("bundle_id"), "bundle_digest": bundle.get("canonical_digest"),
                "generator": bundle.get("generator"), "output_path": ".",
                "pages": sorted(pages, key=lambda item: item["path"]),
                "assets": [], "diagrams": [], "source_links": source_assets,
                "redactions": [s for s in bundle.get("sources") or [] if s.get("redaction", {}).get("status") != "none"],
                "audit": {"verdict": (bundle.get("audit_input") or {}).get("verdict", "not_run"),
                          "finding_count": len((bundle.get("audit_input") or {}).get("findings") or [])}}
    for current, dirs, files in os.walk(html_root):
        for name in sorted(files):
            rel = _rel(html_root, os.path.join(current, name)).replace(os.sep, "/")
            if rel in {"manifest.json"}:
                continue
            manifest["assets"].append({"path": rel, "sha256": sha256_file(os.path.join(current, name)),
                                       "kind": "page" if rel.endswith(".html") and not rel.startswith("assets/") else "asset"})
    for spec in bundle.get("diagrams") or []:
        manifest["diagrams"].append({"diagram_id": spec.get("diagram_id"),
                                      "path": spec.get("asset_path"),
                                      "spec_digest": spec.get("spec_digest"),
                                      "svg_digest": sha256_file(os.path.join(html_root, spec.get("asset_path"))),
                                      "renderer": spec.get("renderer", MERMAID_RENDERER),
                                      "renderer_version": spec.get("renderer_version", MERMAID_VERSION),
                                      "mermaid_source_digest": spec.get("mermaid_source_digest")})
    manifest["assets"].sort(key=lambda item: item["path"])
    manifest["diagrams"].sort(key=lambda item: item["diagram_id"])
    _write_json(os.path.join(html_root, "manifest.json"), manifest)
    return manifest


def _write_bytes(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def render_bundle(bundle_or_path, html=None):
    bundle = _read_json(bundle_or_path) if isinstance(bundle_or_path, (str, os.PathLike)) else bundle_or_path
    issues = validate_autodoc_contract(bundle, "bundle")
    if any(item.is_error for item in issues):
        raise SkillError("AUTODOC_BUNDLE_INVALID", issues[0].message, issues[0].where)
    if not html:
        raise SkillError("AUTODOC_HTML_REQUIRED", "для render нужен --html", "autodoc render")
    manifest = _render_bundle_files(bundle, os.path.abspath(html))
    return manifest


# ---------------------------------------------------------------------------
# Audit and verification


def _finding(code, severity, message, *, entities=None, relations=None, sources=None,
             algorithm="semantic", impact=None, action=None):
    return {"finding_id": "pending", "severity": severity, "code": code,
            "verdict_impact": impact or ("blocked" if severity == "blocker" else "changes_required" if severity == "error" else "none"),
            "entity_refs": sorted(set(entities or [])), "relation_refs": sorted(set(relations or [])),
            "source_refs": sorted(set(sources or [])), "algorithm": algorithm,
            "message": message, "suggested_action": action or "review the source and rerun autodoc",
            "provenance": []}


def _tarjan(nodes, edges):
    adjacency = defaultdict(list)
    for source, target in edges:
        adjacency[source].append(target)
    for key in adjacency:
        adjacency[key] = sorted(set(adjacency[key]))
    index = 0
    stack = []
    on_stack = set()
    indices = {}
    low = {}
    components = []

    def visit(node):
        nonlocal index
        indices[node] = index; low[node] = index; index += 1
        stack.append(node); on_stack.add(node)
        for target in adjacency.get(node, []):
            if target not in indices:
                visit(target); low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], indices[target])
        if low[node] == indices[node]:
            component = []
            while True:
                item = stack.pop(); on_stack.remove(item); component.append(item)
                if item == node: break
            components.append(sorted(component))
    for node in sorted(nodes):
        if node not in indices:
            visit(node)
    return sorted(components, key=lambda item: item[0] if item else "")


def audit_payload(bundle, *, include_quality=True):
    issues = validate_autodoc_contract(bundle, "bundle")
    findings = []
    for issue in issues:
        findings.append(_finding("AUTODOC_SCHEMA_INVALID", "error", issue.message,
                                 algorithm="schema", impact="blocked", action="fix bundle schema"))
    if any(item.is_error for item in issues):
        return _finish_audit(bundle, findings)
    entities = bundle.get("entities") or []
    entity_ids = [item.get("entity_id") for item in entities]
    entity_set = set(entity_ids)
    duplicate_ids = sorted({ident for ident in entity_ids if entity_ids.count(ident) > 1})
    for ident in duplicate_ids:
        findings.append(_finding("AUTODOC_DUPLICATE_ENTITY", "error", "duplicate entity id %s" % ident,
                                 entities=[ident], algorithm="identity"))
    source_ids = [item.get("source_id") for item in bundle.get("sources") or []]
    # Source IDs are content-addressed (source:<sha256>), so equal IDs across
    # paths are expected and retain their separate provenance records.
    relation_ids = [item.get("relation_id") for item in bundle.get("relations") or []]
    for ident in sorted({x for x in relation_ids if relation_ids.count(x) > 1}):
        findings.append(_finding("AUTODOC_DUPLICATE_RELATION", "error", "duplicate relation id %s" % ident,
                                 relations=[ident], algorithm="identity"))
    source_set = set(source_ids)
    for entity in entities:
        missing = [ref for ref in entity.get("source_refs") or [] if ref not in source_set]
        if missing:
            findings.append(_finding("AUTODOC_SOURCE_MISSING", "error",
                                     "%s references missing source %s" % (entity.get("entity_id"), missing[0]),
                                     entities=[entity.get("entity_id")], sources=missing,
                                     algorithm="source_integrity"))
    for relation in bundle.get("relations") or []:
        if relation.get("from") not in entity_set or relation.get("to") not in entity_set:
            severity = "error" if relation.get("resolution") == "resolved" else "warning"
            findings.append(_finding("AUTODOC_BROKEN_RELATION", severity,
                                     "relation endpoint is not present: %s -> %s" % (relation.get("from"), relation.get("to")),
                                     relations=[relation.get("relation_id")], algorithm="ref_resolution"))
        elif relation.get("resolution") not in RESOLUTIONS:
            findings.append(_finding("AUTODOC_RELATION_INVALID", "error", "unknown relation resolution",
                                     relations=[relation.get("relation_id")], algorithm="schema"))
        elif relation.get("resolution") in ("unresolved", "ambiguous"):
            findings.append(_finding("AUTODOC_UNRESOLVED_RELATION", "warning",
                                     "relation is %s: %s" % (relation.get("resolution"), relation.get("relation_id")),
                                     relations=[relation.get("relation_id")], algorithm="ref_resolution"))
    dependency_edges = [(item.get("from"), item.get("to")) for item in bundle.get("relations") or []
                        if item.get("kind") == "depends_on" and item.get("from") in entity_set and item.get("to") in entity_set]
    for component in _tarjan(entity_set, dependency_edges):
        if len(component) > 1 or (component and (component[0], component[0]) in dependency_edges):
            findings.append(_finding("AUTODOC_TASK_DEPENDENCY_CYCLE", "error",
                                     "dependency cycle: %s" % ", ".join(component),
                                     entities=component, algorithm="scc"))
    # Flow graph checks include every declared route and prerequisite.
    for entity in entities:
        if entity.get("kind") != "flow":
            continue
        normalized = entity.get("normalized") or {}
        flow_id = normalized.get("id") or entity.get("entity_id")
        steps = normalized.get("steps") or []
        step_ids = {step.get("id") for step in steps if step.get("id")}
        flow_edges = []
        for step in steps:
            current = step.get("id")
            for source in step.get("input_from") or []:
                flow_edges.append((source, current))
            for route, target in _declared_routes(step):
                target_step = target[:-9] if target.endswith(".revision") else target
                flow_edges.append((current, target_step))
                if target_step not in step_ids and target not in _FLOW_TERMINAL_TARGETS:
                    findings.append(_finding("AUTODOC_FLOW_ROUTE_TARGET_MISSING", "error",
                                             "flow %s route points to missing step %s" % (flow_id, target),
                                             entities=[entity.get("entity_id")], algorithm="ref_resolution"))
        # Unreachable: roots are entry-less steps; if all nodes have incoming,
        # the first declared step is the deterministic seed for diagnostics.
        incoming = defaultdict(int)
        for source, target in flow_edges:
            if target in step_ids and source in step_ids:
                incoming[target] += 1
        roots = sorted(step_ids - set(incoming)) or sorted(step_ids)[:1]
        reachable = set(roots); queue = deque(roots)
        adjacency = defaultdict(list)
        for source, target in flow_edges:
            if source in step_ids and target in step_ids:
                adjacency[source].append(target)
        while queue:
            current = queue.popleft()
            for target in sorted(adjacency[current]):
                if target not in reachable:
                    reachable.add(target); queue.append(target)
        for step_id in sorted(step_ids - reachable):
            findings.append(_finding("AUTODOC_FLOW_UNREACHABLE", "error",
                                     "flow %s step %s is unreachable" % (flow_id, step_id),
                                     entities=[entity.get("entity_id")], algorithm="reachability"))
        terminals = {step.get("id") for step in steps if step.get("id") and not adjacency.get(step.get("id"))}
        if not terminals and step_ids:
            findings.append(_finding("AUTODOC_FLOW_DEAD_END", "error",
                                     "flow %s has no terminal route" % flow_id,
                                     entities=[entity.get("entity_id")], algorithm="terminal_analysis"))
        for component in _tarjan(step_ids, flow_edges):
            if len(component) > 1:
                findings.append(_finding("AUTODOC_FLOW_CYCLE", "warning",
                                         "flow %s contains cycle %s" % (flow_id, ",".join(component)),
                                         entities=[entity.get("entity_id")], algorithm="scc"))
    for document in bundle.get("documents") or []:
        markdown = document.get("markdown") or {}
        source_ref = document.get("source_ref")
        for item in markdown.get("compatibility") or []:
            code = {"unsafe_html": "AUTODOC_MARKDOWN_UNSAFE_HTML",
                    "unsafe_url": "AUTODOC_MARKDOWN_UNSAFE_URL",
                    "missing_image": "AUTODOC_MARKDOWN_MISSING_IMAGE",
                    "broken_link": "AUTODOC_MARKDOWN_BROKEN_LINK",
                    "unclosed_fence": "AUTODOC_MARKDOWN_UNCLOSED_FENCE"}.get(item.get("kind"), "AUTODOC_MARKDOWN_UNKNOWN")
            findings.append(_finding(code, "warning", item.get("message", "Markdown compatibility issue"),
                                     entities=[document.get("document_id")], sources=[source_ref],
                                     algorithm="markdown_contract"))
    coverage = (bundle.get("completeness") or {}).get("coverage") or {}
    for path in coverage.get("raw_json_only_paths") or []:
        findings.append(_finding("AUTODOC_SOURCE_RAW_JSON_ONLY", "warning",
                                 "canonical JSON source %s имеет только fallback-представление; добавьте domain adapter и human page" % path,
                                 algorithm="coverage", action="добавить source adapter/renderer и повторить autodoc"))
    for item in bundle.get("unknowns") or []:
        findings.append(_finding("AUTODOC_UNKNOWN_SOURCE", "warning",
                                 "%s: %s" % (item.get("kind", "unknown"), item.get("reason", item.get("status", "unknown"))),
                                 algorithm="provenance"))
    if bundle.get("legacy_parity"):
        for item in bundle["legacy_parity"].get("sections") or []:
            if item.get("status") == "unknown":
                findings.append(_finding("AUTODOC_PREZA_PARITY_UNKNOWN", "warning",
                                         "legacy section %s has no source or target" % item.get("id"),
                                         algorithm="legacy_parity"))
    if include_quality:
        for entity in entities:
            if entity.get("kind") != "task":
                continue
            task = (entity.get("normalized") or {}).get("task") or {}
            if task.get("status") in ("ready", "in_progress") and not task.get("verify"):
                findings.append(_finding("AUTODOC_TASK_VERIFY_MISSING", "warning",
                                         "task %s has no verify field" % entity.get("entity_id"),
                                         entities=[entity.get("entity_id")], algorithm="task_quality"))
    return _finish_audit(bundle, findings)


def _finish_audit(bundle, findings):
    findings.sort(key=lambda item: (item.get("severity", ""), item.get("code", ""),
                                    _json_dumps(item.get("entity_refs", [])), item.get("message", "")))
    for index, finding in enumerate(findings, 1):
        seed = {key: value for key, value in finding.items() if key != "finding_id"}
        finding["finding_id"] = "F-%04d-%s" % (index, hashlib.sha256(canonical_bytes(seed)).hexdigest()[:10])
    blocking = any(item.get("severity") in ("error", "blocker") for item in findings)
    completeness = bundle.get("completeness", {}).get("status")
    verdict = "blocked" if completeness == "blocked" else "changes_required" if blocking or completeness in ("partial", "blocked") else "approved"
    return {"$schema": AUTODOC_AUDIT_SCHEMA, "schema": AUTODOC_AUDIT_SCHEMA,
            "audit_id": "audit:" + hashlib.sha256(canonical_bytes(findings)).hexdigest()[:24],
            "bundle_id": bundle.get("bundle_id"), "bundle_digest": bundle.get("canonical_digest"),
            "algorithm_version": "audit-local-1", "verdict": verdict,
            "findings": findings, "remaining_risks": [], "unknowns": bundle.get("unknowns") or [],
            "provenance": [{"bundle_id": bundle.get("bundle_id"), "digest": bundle.get("canonical_digest")}],
            "created_at": _now()}


def _audit_input(audit):
    return {"algorithm_version": audit.get("algorithm_version"),
            "verdict": audit.get("verdict"),
            "findings": audit.get("findings") or []}


def audit_bundle(bundle_or_path, output=None):
    bundle_path = bundle_or_path if isinstance(bundle_or_path, (str, os.PathLike)) else None
    bundle = _read_json(bundle_or_path) if bundle_path else bundle_or_path
    audit = audit_payload(bundle)
    if output:
        _write_json(os.path.abspath(output), audit)
    return audit


def _safe_local_href(root, href):
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc:
        return False
    try:
        safe_relative_path(href.split("#", 1)[0] or "index.html")
        return True
    except SkillError:
        return False


def verify_bundle(bundle_or_path, html=None, *, audit=None):
    bundle = _read_json(bundle_or_path) if isinstance(bundle_or_path, (str, os.PathLike)) else bundle_or_path
    findings = []
    issues = validate_autodoc_contract(bundle, "bundle")
    for issue in issues:
        findings.append(_finding("AUTODOC_SCHEMA_INVALID", "error", issue.message, algorithm="schema", impact="blocked"))
    if not issues:
        expected = bundle.get("canonical_digest")
        actual = canonical_digest(bundle)
        if expected != actual:
            findings.append(_finding("AUTODOC_DIGEST_MISMATCH", "error",
                                     "canonical digest mismatch: expected %s actual %s" % (expected, actual),
                                     algorithm="fingerprint", impact="blocked"))
        source_ids = {item.get("source_id") for item in bundle.get("sources") or []}
        for source in bundle.get("sources") or []:
            raw = source.get("raw")
            if raw is None or source.get("raw_encoding") != "utf-8":
                continue
            if sha256_bytes(raw.encode("utf-8")) != source.get("sha256"):
                findings.append(_finding("AUTODOC_SOURCE_DIGEST_MISMATCH", "error",
                                         "source digest mismatch %s" % source.get("canonical_path"),
                                         sources=[source.get("source_id")], algorithm="fingerprint"))
        for document in bundle.get("documents") or []:
            source = next((item for item in bundle.get("sources") or [] if item.get("source_id") == document.get("source_ref")), None)
            if not source:
                findings.append(_finding("AUTODOC_DOCUMENT_SOURCE_MISSING", "error", "document source is missing",
                                         entities=[document.get("document_id")], algorithm="source_integrity"))
            elif source.get("sha256") != (document.get("markdown") or {}).get("source_digest"):
                findings.append(_finding("AUTODOC_MARKDOWN_DIGEST_MISMATCH", "error", "Markdown source digest mismatch",
                                         entities=[document.get("document_id")], sources=[source.get("source_id")], algorithm="fingerprint"))
    if html:
        html = os.path.abspath(html)
        manifest_path = os.path.join(html, "manifest.json")
        if not os.path.isfile(manifest_path):
            findings.append(_finding("AUTODOC_HTML_MANIFEST_MISSING", "error", "HTML manifest is missing", algorithm="html_manifest"))
        else:
            try:
                manifest = _read_json(manifest_path)
            except SkillError as exc:
                findings.append(_finding("AUTODOC_HTML_MANIFEST_INVALID", "error", exc.message, algorithm="schema"))
                manifest = {}
            if manifest.get("bundle_digest") != bundle.get("canonical_digest"):
                findings.append(_finding("AUTODOC_HTML_BUNDLE_MISMATCH", "error", "HTML points to another bundle", algorithm="html_manifest"))
            for page in manifest.get("pages") or []:
                path = page.get("path")
                if not path or not _within(html, os.path.join(html, path)) or not os.path.isfile(os.path.join(html, path)):
                    findings.append(_finding("AUTODOC_HTML_PAGE_MISSING", "error", "HTML page missing %s" % path, algorithm="html_manifest"))
                    continue
                if sha256_file(os.path.join(html, path)) != page.get("sha256"):
                    findings.append(_finding("AUTODOC_HTML_PAGE_DIGEST_MISMATCH", "error", "HTML page digest mismatch %s" % path, algorithm="fingerprint"))
            for current, dirs, files in os.walk(html):
                dirs[:] = sorted(dirs)
                for name in sorted(files):
                    path = os.path.join(current, name)
                    if name.endswith((".html", ".svg")):
                        try:
                            text = Path(path).read_text(encoding="utf-8")
                        except (OSError, UnicodeDecodeError):
                            continue
                        if re.search(r"<(?:script|iframe|object|embed)\b", text, re.I) and not name.endswith(".html"):
                            findings.append(_finding("AUTODOC_HTML_UNSAFE_MARKUP", "error", "unsafe SVG markup %s" % _rel(html, path), algorithm="safety"))
                        # Resolve every local href/src from its owning page.  A
                        # missing local target is a deterministic finding rather
                        # than a browser-time 404.
                        if name.endswith(".html"):
                            current_rel = _rel(html, path).replace(os.sep, "/")
                            for attribute, target in re.findall(r"\\b(href|src)=[\\\"']([^\\\"']+)[\\\"']", text, re.I):
                                parsed = urlparse(target)
                                if parsed.scheme or parsed.netloc or target.startswith("#"):
                                    continue
                                target_path = parsed.path.split("#", 1)[0] or current_rel
                                if target_path.startswith("/"):
                                    findings.append(_finding("AUTODOC_HTML_UNSAFE_LINK", "error", "absolute HTML link %s" % target, algorithm="path_safety"))
                                    continue
                                resolved = os.path.abspath(os.path.join(os.path.dirname(path), target_path))
                                if not _within(html, resolved) or not os.path.isfile(resolved):
                                    findings.append(_finding("AUTODOC_HTML_BROKEN_LINK", "error", "%s points to missing %s" % (current_rel, target), algorithm="link_resolution"))
                        if re.search(r"<(?:link|script|img)[^>]+(?:https?:)?//", text, re.I):
                            findings.append(_finding("AUTODOC_HTML_EXTERNAL_ASSET", "error", "external asset in %s" % _rel(html, path), algorithm="offline"))
    # Audit findings are a separate deterministic report.  ``verify`` checks
    # bundle/source/HTML integrity and must not turn a known, reviewable flow
    # finding into a digest or link failure.  Callers inspect ``audit.json`` for
    # the process verdict.
    findings.sort(key=lambda item: (item.get("severity", ""), item.get("code", ""), item.get("message", "")))
    return {"valid": not any(item.get("severity") in ("error", "blocker") for item in findings),
            "bundle_digest": bundle.get("canonical_digest"), "findings": findings,
            "checked": {"sources": len(bundle.get("sources") or []),
                        "entities": len(bundle.get("entities") or []),
                        "relations": len(bundle.get("relations") or [])}}


# ---------------------------------------------------------------------------
# Reconstruction and Markdown augmentation


def reconstruct_bundle(bundle_or_path, target, *, force=False):
    bundle = _read_json(bundle_or_path) if isinstance(bundle_or_path, (str, os.PathLike)) else bundle_or_path
    issues = validate_autodoc_contract(bundle, "bundle")
    if any(item.is_error for item in issues):
        raise SkillError("AUTODOC_BUNDLE_INVALID", issues[0].message, issues[0].where)
    if canonical_digest(bundle) != bundle.get("canonical_digest"):
        raise SkillError("AUTODOC_DIGEST_MISMATCH", "bundle digest не совпадает", "bundle")
    target = os.path.abspath(target)
    if os.path.islink(target):
        raise SkillError("AUTODOC_PATH_UNSAFE", "reconstruction target не может быть symlink", target)
    if os.path.exists(target):
        if not os.path.isdir(target):
            if not force:
                raise SkillError("AUTODOC_RECONSTRUCTION_TARGET_NOT_EMPTY",
                                 "target уже является файлом; explicit --force нужен для замены", target)
        elif os.listdir(target) and not force:
            raise SkillError("AUTODOC_RECONSTRUCTION_TARGET_NOT_EMPTY",
                             "target не пуст; explicit --force нужен для замены", target)
    parent = os.path.dirname(target) or os.getcwd()
    os.makedirs(parent, exist_ok=True)
    temporary = tempfile.mkdtemp(prefix=".autodoc-reconstruct-", dir=parent)
    restored, skipped, redacted = [], [], []
    try:
        seen = set()
        sources = {item.get("source_id"): item for item in bundle.get("sources") or []}
        for source_ref in bundle.get("reconstruction", {}).get("source_refs") or []:
            source = sources.get(source_ref)
            if not source:
                skipped.append({"source_ref": source_ref, "reason": "source_missing"}); continue
            rel = source.get("canonical_path")
            try:
                safe_relative_path(rel)
            except SkillError:
                raise
            if rel in seen:
                raise SkillError("AUTODOC_RECONSTRUCTION_DUPLICATE", "duplicate target path %s" % rel, rel)
            seen.add(rel)
            if source.get("external") or source.get("generated") or not source.get("source_of_truth"):
                skipped.append({"source_ref": source_ref, "path": rel, "reason": "external_or_derived"}); continue
            raw = source.get("raw")
            if raw is None:
                redacted.append({"source_ref": source_ref, "path": rel,
                                 "reason": source.get("redaction", {}).get("reason", "raw_unavailable")}); continue
            data = base64.b64decode(raw) if source.get("raw_encoding") == "base64" else raw.encode("utf-8")
            if sha256_bytes(data) != source.get("sha256"):
                raise SkillError("AUTODOC_SOURCE_DIGEST_MISMATCH", "source digest mismatch %s" % rel, rel)
            destination = os.path.join(temporary, *rel.split("/"))
            if not _within(temporary, destination) or os.path.islink(os.path.dirname(destination)):
                raise SkillError("AUTODOC_PATH_UNSAFE", "symlink/traversal escape for %s" % rel, rel)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            _write_bytes(destination, data)
            restored.append({"source_ref": source_ref, "path": rel, "sha256": source.get("sha256")})
        report = {"$schema": AUTODOC_RECONSTRUCTION_SCHEMA,
                  "schema": AUTODOC_RECONSTRUCTION_SCHEMA,
                  "bundle_id": bundle.get("bundle_id"), "bundle_digest": bundle.get("canonical_digest"),
                  "target": ".", "restored": sorted(restored, key=lambda item: item["path"]),
                  "skipped": sorted(skipped, key=lambda item: item.get("path", "")),
                  "redacted": sorted(redacted, key=lambda item: item.get("path", "")),
                  "status": "complete" if not skipped and not redacted else "partial"}
        if os.path.exists(target):
            if force:
                if os.path.isdir(target):
                    shutil.rmtree(target)
                else:
                    os.unlink(target)
            else:
                raise SkillError("AUTODOC_RECONSTRUCTION_TARGET_NOT_EMPTY", "target стал занят", target)
        os.replace(temporary, target)
        temporary = None
        return report
    finally:
        if temporary and os.path.isdir(temporary):
            shutil.rmtree(temporary, ignore_errors=True)


_AUTODOC_DIAGRAM_BLOCK_RE = re.compile(
    r"<!--\s*AUTODOC:BEGIN diagram=([^\s>]+)[^>]*-->.*?"
    r"<!--\s*AUTODOC:END diagram=\1\s*-->", re.I | re.S)


def _without_autodoc_diagram_blocks(text):
    result = _AUTODOC_DIAGRAM_BLOCK_RE.sub("", str(text or ""))
    # augment_markdown appends an owned block after a blank-line separator;
    # remove that separator when reconstructing the source digest.
    if _AUTODOC_DIAGRAM_BLOCK_RE.search(str(text or "")):
        result = re.sub(r"\n{2,}$", "\n", result)
    return result


def _autodoc_block_digest(text):
    return sha256_bytes(_without_autodoc_diagram_blocks(text).encode("utf-8"))


def augment_markdown(root, bundle, *, backup=True):
    """Idempotently put Mermaid source blocks into flow instruction Markdown.

    Blocks are owned by AUTODOC markers. The digest is calculated after removing
    all owned blocks, so a second generation remains idempotent even though the
    generated Mermaid source itself is part of the Markdown bytes. Mermaid source
    edits are accepted as canonical Markdown; malformed or unclosed owned
    wrappers are reported as conflicts instead of being overwritten.
    """
    changed = []
    conflicts = []
    root = os.path.abspath(root)
    specs = [spec for spec in bundle.get("diagrams") or [] if spec.get("kind") == "flow"]
    documents = bundle.get("documents") or []
    sources = {item.get("canonical_path"): item for item in bundle.get("sources") or []}
    for spec in specs:
        diagram_id = spec.get("diagram_id")
        flow_id = str(diagram_id).split(":", 1)[-1]
        for document in documents:
            path = document.get("canonical_path", "")
            if not path.endswith((".md", ".markdown")) or not _within(root, os.path.join(root, path)):
                continue
            if not path.startswith("flows/%s/" % flow_id):
                continue
            file_path = os.path.join(root, *path.split("/"))
            source = sources.get(path)
            if not source or source.get("raw") is None or not os.path.isfile(file_path):
                continue
            current = Path(file_path).read_text(encoding="utf-8")
            source_digest = _autodoc_block_digest(current)
            marker = "AUTODOC:BEGIN diagram=%s" % diagram_id
            end_marker = "AUTODOC:END diagram=%s" % diagram_id
            # A manually authored Mermaid block in the flow instruction has
            # already become the canonical Markdown source. Do not append a
            # second generated block beside it; provenance is recorded by the
            # Markdown diagram spec itself.
            if spec.get("source_mode") == "markdown" and marker not in current:
                continue
            block_re = re.compile(
                r"<!--\s*AUTODOC:BEGIN diagram=%s[^>]*-->.*?"
                r"<!--\s*AUTODOC:END diagram=%s\s*-->" %
                (re.escape(str(diagram_id)), re.escape(str(diagram_id))), re.I | re.S)
            existing_match = block_re.search(current)
            source_for_block = str(spec.get("mermaid_source", ""))
            if existing_match:
                metadata = _autodoc_begin_metadata(existing_match.group(0))
                if (metadata and metadata.get("projection_digest") and
                        metadata.get("projection_digest") != spec.get("projection_digest")):
                    source_for_block = str(spec.get("projection_source") or source_for_block)
                elif metadata and not metadata.get("projection_digest"):
                    old_code = re.search(r"```mermaid\s*\n(.*?)\n```",
                                         existing_match.group(0), re.S | re.I)
                    old_source = (_mermaid_source_without_marker(old_code.group(1))[0]
                                  if old_code else "")
                    if old_source == str(spec.get("projection_source") or "").strip():
                        source_for_block = str(spec.get("projection_source") or source_for_block)
            source_for_block = source_for_block.strip()
            spec_for_block = spec
            if source_for_block != str(spec.get("mermaid_source", "")).strip():
                spec_for_block = copy.deepcopy(spec)
                spec_for_block["mermaid_source"] = source_for_block
                spec_for_block["source_block_digest"] = sha256_bytes(source_for_block.encode("utf-8"))
                _prepare_diagram_spec(spec_for_block)
            block = (
                "<!-- %s source_digest=%s projection_digest=%s spec_digest=%s -->\n"
                "```mermaid\n"
                "%%%% AUTODOC-DIAGRAM: %s\n"
                "%s\n"
                "```\n"
                "<!-- %s -->" %
                (marker, source_digest, spec.get("projection_digest", "unknown"),
                 spec_for_block.get("spec_digest", "unknown"), diagram_id,
                 source_for_block.rstrip(), end_marker))
            if marker in current and end_marker not in current:
                conflicts.append({"path": path, "diagram_id": diagram_id,
                                  "reason": "unclosed_generated_block"})
                continue
            if marker in current:
                block_re = re.compile(
                    r"<!--\s*AUTODOC:BEGIN diagram=%s[^>]*-->.*?"
                    r"<!--\s*AUTODOC:END diagram=%s\s*-->" %
                    (re.escape(str(diagram_id)), re.escape(str(diagram_id))), re.I | re.S)
                match = block_re.search(current)
                if not match:
                    conflicts.append({"path": path, "diagram_id": diagram_id,
                                      "reason": "generated_block_parse_error"})
                    continue
                existing = match.group(0)
                # The Markdown fence is the selected source of truth. A human
                # may edit its Mermaid body; generation keeps that body because
                # build_bundle has already adopted it into the diagram spec.
                # Only the owned wrapper metadata is refreshed here.
                if not _autodoc_begin_metadata(existing):
                    conflicts.append({"path": path, "diagram_id": diagram_id,
                                      "reason": "generated_block_parse_error"})
                    continue
                new = current[:match.start()] + block + current[match.end():]
            else:
                new = current.rstrip() + "\n\n" + block + "\n"
            if new == current:
                continue
            if backup:
                backup_path = file_path + ".autodoc.bak"
                if not os.path.exists(backup_path):
                    _write_text(backup_path, current)
            _write_text(file_path, new)
            changed.append(path)
    return {"changed": sorted(set(changed)),
            "conflicts": sorted(conflicts, key=lambda item: (item["path"], item.get("diagram_id", "")))}


# ---------------------------------------------------------------------------
# Contract validators used by tcheck schema and fixture tests


def _contract_issue(where, message, code="AUTODOC_CONTRACT_INVALID"):
    return Issue("error", where, message, code)


_CONTRACT_REQUIRED = {
    AUTODOC_BUNDLE_SCHEMA: ("schema", "bundle_id", "bundle_revision", "generator", "root",
                            "canonical_digest", "completeness", "inventory", "entities",
                            "relations", "sources", "documents", "diagrams", "audit_input",
                            "reconstruction"),
    AUTODOC_ENTITY_SCHEMA: ("entity_id", "kind", "namespace", "status", "source_refs", "provenance", "normalized"),
    AUTODOC_RELATION_SCHEMA: ("relation_id", "from", "to", "kind", "resolution", "source_refs", "provenance"),
    AUTODOC_SOURCE_SCHEMA: ("source_id", "canonical_path", "source_domain", "media_type", "byte_size", "sha256", "mode_policy", "redaction", "classification", "source_of_truth", "generated", "provenance"),
    AUTODOC_DIAGRAM_SCHEMA: ("diagram_id", "kind", "title", "nodes", "edges", "legend", "source_entity_refs", "layout"),
    AUTODOC_AUDIT_SCHEMA: ("audit_id", "bundle_id", "bundle_digest", "algorithm_version", "verdict", "findings", "remaining_risks", "unknowns", "provenance"),
    AUTODOC_HTML_SCHEMA: ("html_id", "bundle_id", "bundle_digest", "generator", "output_path", "pages", "assets", "diagrams"),
    AUTODOC_RECONSTRUCTION_SCHEMA: ("bundle_id", "bundle_digest", "target", "restored", "skipped", "redacted", "status"),
    AUTODOC_PACKET_SCHEMA: ("packet_id", "bundle_id", "purpose", "selected_entity_refs", "selected_relation_refs", "findings", "unknowns", "limits", "truncation", "return_contract"),
    AUTODOC_MARKDOWN_SCHEMA: ("document_id", "doc_key", "revision", "canonical_path", "source_ref", "markdown", "provenance"),
    AUTODOC_PREZA_SCHEMA: ("legacy_root", "legacy_output", "sections", "assets", "inventory", "parity", "facts_baseline"),
    PREZA_PARITY_SCHEMA: ("legacy_root", "legacy_output", "sections", "assets", "inventory"),
}

# Every wire envelope carries its discriminator in ``schema``.  The bundle
# declaration above already lists it explicitly; add it to the compact nested
# records here so fixtures and runtime entities use the same contract.
_CONTRACT_REQUIRED = {
    key: value if "schema" in value else ("schema",) + tuple(value)
    for key, value in _CONTRACT_REQUIRED.items()
}

_CONTRACT_ALLOWED = {
    AUTODOC_BUNDLE_SCHEMA: set(_CONTRACT_REQUIRED[AUTODOC_BUNDLE_SCHEMA]) | {"$schema", "created_at", "generator", "outputs", "warnings", "unknowns", "legacy_parity"},
    AUTODOC_ENTITY_SCHEMA: set(_CONTRACT_REQUIRED[AUTODOC_ENTITY_SCHEMA]) | {"$schema", "raw_ref", "revision"},
    AUTODOC_RELATION_SCHEMA: set(_CONTRACT_REQUIRED[AUTODOC_RELATION_SCHEMA]) | {"$schema"},
    AUTODOC_SOURCE_SCHEMA: set(_CONTRACT_REQUIRED[AUTODOC_SOURCE_SCHEMA]) | {"$schema", "raw", "raw_encoding", "raw_available", "text_encoding", "external"},
    AUTODOC_DIAGRAM_SCHEMA: set(_CONTRACT_REQUIRED[AUTODOC_DIAGRAM_SCHEMA]) | {"$schema", "spec_digest", "asset_path", "asset_digest", "persisted_state", "problems", "problem_nodes", "renderer", "renderer_version", "renderer_adapter", "renderer_runtime", "renderer_offline", "mermaid_source", "mermaid_source_digest", "mermaid_render_source", "source_mode", "source_document_path", "source_line", "source_block_digest", "source_file_digest", "projection_source", "projection_digest"},
    AUTODOC_AUDIT_SCHEMA: set(_CONTRACT_REQUIRED[AUTODOC_AUDIT_SCHEMA]) | {"$schema", "created_at"},
    AUTODOC_HTML_SCHEMA: set(_CONTRACT_REQUIRED[AUTODOC_HTML_SCHEMA]) | {"$schema", "schema", "pages", "source_links", "redactions", "audit"},
    AUTODOC_RECONSTRUCTION_SCHEMA: set(_CONTRACT_REQUIRED[AUTODOC_RECONSTRUCTION_SCHEMA]) | {"$schema", "mode", "source_refs", "requires_human"},
    AUTODOC_PACKET_SCHEMA: set(_CONTRACT_REQUIRED[AUTODOC_PACKET_SCHEMA]) | {"$schema", "created_at"},
    AUTODOC_MARKDOWN_SCHEMA: set(_CONTRACT_REQUIRED[AUTODOC_MARKDOWN_SCHEMA]) | {"$schema", "encoding", "frontmatter", "headings", "tokens", "links", "images", "raw_unknown", "compatibility", "source_digest", "rendered_html"},
    AUTODOC_PREZA_SCHEMA: set(_CONTRACT_REQUIRED[AUTODOC_PREZA_SCHEMA]) | {"$schema", "inventory", "parity"},
    PREZA_PARITY_SCHEMA: set(_CONTRACT_REQUIRED[PREZA_PARITY_SCHEMA]) | {"$schema"},
}

_PREZA_REQUIRED_SECTIONS = (
    "start", "architecture", "entities", "lifecycle", "commands", "types",
    "flows", "schemas", "templates", "file-catalog", "checks", "faq",
    "live-facts", "footer",
)
_PREZA_ITEM_REQUIRED = ("id", "source", "content_digest", "target_page", "status", "source_refs")
_PREZA_ASSET_REQUIRED = ("id", "digest", "target", "status", "source_refs")


def _validate_preza_item(item, where):
    issues = []
    if not isinstance(item, dict):
        return [_contract_issue(where, "PREZA inventory item должен быть object")]
    for key in _PREZA_ITEM_REQUIRED:
        if key not in item:
            issues.append(_contract_issue(where, "нет обязательного поля %s" % key))
    if item.get("status") not in PREZA_PARITY_STATUSES:
        issues.append(_contract_issue(where, "status должен быть одним из %s" % ", ".join(PREZA_PARITY_STATUSES)))
    if not isinstance(item.get("source_refs"), list) or not all(isinstance(ref, str) for ref in item.get("source_refs") or []):
        issues.append(_contract_issue(where, "source_refs должен быть массивом строк"))
    if not isinstance(item.get("source"), str) or not item.get("source"):
        issues.append(_contract_issue(where, "source должен быть непустой строкой"))
    if not isinstance(item.get("target_page"), str) or not item.get("target_page"):
        issues.append(_contract_issue(where, "target_page должен быть непустой строкой"))
    if item.get("content_digest") is not None and not isinstance(item.get("content_digest"), str):
        issues.append(_contract_issue(where, "content_digest должен быть строкой или null"))
    return issues


def _validate_preza_parity(payload, where):
    issues = []
    if payload.get("schema") != PREZA_PARITY_SCHEMA:
        issues.append(_contract_issue(where, "schema должен быть PREZA-PARITY-1"))
    sections = payload.get("sections")
    if not isinstance(sections, list):
        issues.append(_contract_issue(where, "sections должен быть array"))
    else:
        for index, item in enumerate(sections):
            issues.extend(_validate_preza_item(item, "%s.sections[%d]" % (where, index)))
        ids = [item.get("id") for item in sections if isinstance(item, dict)]
        missing = sorted(set(_PREZA_REQUIRED_SECTIONS) - set(ids))
        if missing:
            issues.append(_contract_issue(where, "missing PREZA sections: %s" % ", ".join(missing)))
        if len(ids) != len(set(ids)):
            issues.append(_contract_issue(where, "PREZA section ids must be unique"))
    assets = payload.get("assets")
    if not isinstance(assets, list):
        issues.append(_contract_issue(where, "assets должен быть array"))
    else:
        for index, item in enumerate(assets):
            item_where = "%s.assets[%d]" % (where, index)
            if not isinstance(item, dict):
                issues.append(_contract_issue(item_where, "PREZA asset должен быть object"))
                continue
            for key in _PREZA_ASSET_REQUIRED:
                if key not in item:
                    issues.append(_contract_issue(item_where, "нет обязательного поля %s" % key))
            if item.get("status") not in PREZA_PARITY_STATUSES:
                issues.append(_contract_issue(item_where, "asset status не поддержан"))
            if not isinstance(item.get("source_refs"), list):
                issues.append(_contract_issue(item_where, "asset source_refs должен быть array"))
    inventory = payload.get("inventory")
    if not isinstance(inventory, dict):
        issues.append(_contract_issue(where, "inventory должен быть object"))
    else:
        missing_categories = sorted(set(PREZA_PARITY_CATEGORIES) - set(inventory))
        extra_categories = sorted(set(inventory) - set(PREZA_PARITY_CATEGORIES))
        if missing_categories:
            issues.append(_contract_issue(where, "missing PREZA inventory categories: %s" % ", ".join(missing_categories)))
        if extra_categories:
            issues.append(_contract_issue(where, "unknown PREZA inventory categories: %s" % ", ".join(extra_categories)))
        for category in PREZA_PARITY_CATEGORIES:
            values = inventory.get(category)
            if not isinstance(values, list):
                issues.append(_contract_issue("%s.inventory.%s" % (where, category), "category must be array"))
                continue
            if not values:
                issues.append(_contract_issue("%s.inventory.%s" % (where, category), "category must contain an explicit item or unknown row"))
            for index, item in enumerate(values):
                issues.extend(_validate_preza_item(item, "%s.inventory.%s[%d]" % (where, category, index)))
    if isinstance(assets, list) and not assets:
        issues.append(_contract_issue("%s.assets" % where, "assets must contain an explicit asset or unknown row"))
    return issues
    return issues


def validate_autodoc_contract(payload, where="autodoc"):
    issues = []
    if not isinstance(payload, dict):
        return [_contract_issue(where, "payload должен быть object")]
    schema_id = payload.get("schema")
    if schema_id not in _CONTRACT_REQUIRED:
        return [_contract_issue(where, "неизвестная autodoc schema %s" % schema_id, "AUTODOC_CONTRACT_UNKNOWN")]
    for key in payload:
        if key not in _CONTRACT_ALLOWED[schema_id]:
            issues.append(_contract_issue("%s.%s" % (where, key), "ключ не объявлен контрактом"))
    for key in _CONTRACT_REQUIRED[schema_id]:
        if key not in payload:
            issues.append(_contract_issue(where, "нет обязательного поля %s" % key))
    if schema_id == AUTODOC_BUNDLE_SCHEMA and payload.get("schema") != AUTODOC_BUNDLE_SCHEMA:
        issues.append(_contract_issue(where, "schema должен быть AUTODOC-BUNDLE-1"))
    if schema_id == AUTODOC_RELATION_SCHEMA and payload.get("kind") not in RELATION_KINDS:
        issues.append(_contract_issue(where, "relation kind не поддержан"))
    if schema_id == AUTODOC_RELATION_SCHEMA and payload.get("resolution") not in RESOLUTIONS:
        issues.append(_contract_issue(where, "relation resolution не поддержан"))
    if schema_id == AUTODOC_AUDIT_SCHEMA and payload.get("verdict") not in {"approved", "changes_required", "blocked", "not_run"}:
        issues.append(_contract_issue(where, "audit verdict не поддержан"))
    if schema_id == PREZA_PARITY_SCHEMA:
        issues.extend(_validate_preza_parity(payload, where))
    if schema_id == AUTODOC_PREZA_SCHEMA:
        parity = payload.get("parity")
        if isinstance(parity, dict):
            issues.extend(validate_autodoc_contract(parity, "%s.parity" % where))
    if schema_id == AUTODOC_SOURCE_SCHEMA:
        path = payload.get("canonical_path")
        if path:
            try:
                safe_relative_path(path) if not payload.get("external") else None
            except SkillError as exc:
                issues.append(_contract_issue(where, exc.message, "AUTODOC_PATH_UNSAFE"))
    if schema_id == AUTODOC_BUNDLE_SCHEMA:
        if not isinstance(payload.get("entities"), list) or not isinstance(payload.get("sources"), list):
            issues.append(_contract_issue(where, "entities и sources должны быть arrays"))
        if payload.get("canonical_digest") and payload.get("canonical_digest") != "sha256:pending":
            # Do not recurse into source/content semantics here; verify performs
            # the expensive digest and link checks.
            if not isinstance(payload.get("canonical_digest"), str) or not payload["canonical_digest"].startswith("sha256:"):
                issues.append(_contract_issue(where, "canonical_digest должен быть sha256:*"))
        legacy = payload.get("legacy_parity")
        if isinstance(legacy, dict):
            issues.extend(validate_autodoc_contract(legacy, "%s.legacy_parity" % where))
    return issues


def schema_contract_payload(name):
    """Return a compact key contract for ``tcheck schema AUTODOC_*``."""
    mapping = {
        "AUTODOC_BUNDLE": AUTODOC_BUNDLE_SCHEMA, "AUTODOC_ENTITY": AUTODOC_ENTITY_SCHEMA,
        "AUTODOC_RELATION": AUTODOC_RELATION_SCHEMA, "AUTODOC_SOURCE": AUTODOC_SOURCE_SCHEMA,
        "AUTODOC_DIAGRAM": AUTODOC_DIAGRAM_SCHEMA, "AUTODOC_AUDIT": AUTODOC_AUDIT_SCHEMA,
        "AUTODOC_HTML": AUTODOC_HTML_SCHEMA, "AUTODOC_RECONSTRUCTION": AUTODOC_RECONSTRUCTION_SCHEMA,
        "AUTODOC_AUDIT_PACKET": AUTODOC_PACKET_SCHEMA, "AUTODOC_MARKDOWN": AUTODOC_MARKDOWN_SCHEMA,
        "AUTODOC_PREZA_MIGRATION": AUTODOC_PREZA_SCHEMA, "PREZA_PARITY": PREZA_PARITY_SCHEMA,
    }
    schema_id = mapping.get(name, name)
    if schema_id not in _CONTRACT_REQUIRED:
        return None
    return {"schema": schema_id, "required": list(_CONTRACT_REQUIRED[schema_id]),
            "keys": sorted(_CONTRACT_ALLOWED[schema_id])}


def _make_packet(bundle, audit, *, limit=12, chars=24000):
    findings = (audit.get("findings") or [])[:max(0, int(limit))]
    selected = []
    for finding in findings:
        selected.extend(finding.get("entity_refs") or [])
    selected = sorted(set(selected))[:max(0, int(limit))]
    entity_set = set(selected)
    relations = [item for item in bundle.get("relations") or []
                 if item.get("from") in entity_set or item.get("to") in entity_set]
    packet = {"$schema": AUTODOC_PACKET_SCHEMA, "schema": AUTODOC_PACKET_SCHEMA,
              "packet_id": "packet:" + hashlib.sha256(canonical_bytes(findings)).hexdigest()[:20],
              "bundle_id": bundle.get("bundle_id"), "purpose": "bounded autodoc audit review",
              "selected_entity_refs": selected,
              "selected_relation_refs": [item.get("relation_id") for item in relations],
              "findings": findings, "unknowns": bundle.get("unknowns") or [],
              "limits": {"entities": limit, "chars": chars}, "truncation": False,
              "return_contract": {"fields": ["findings", "confidence", "evidence_refs", "unresolved_questions", "next_checks"]}}
    text = _json_dumps(packet)
    if len(text) > chars:
        packet["findings"] = findings[:max(1, int(limit) // 2)]
        packet["truncation"] = True
    return packet


def write_bundle_atomic(path, bundle):
    _write_json(os.path.abspath(path), bundle)


def load_bundle(path):
    bundle = _read_json(path)
    issues = validate_autodoc_contract(bundle, path)
    if any(item.is_error for item in issues):
        raise SkillError("AUTODOC_BUNDLE_INVALID", issues[0].message, issues[0].where)
    return bundle


__all__ = [
    "AUTODOC_BUNDLE_SCHEMA", "AUTODOC_ENTITY_SCHEMA", "AUTODOC_RELATION_SCHEMA",
    "AUTODOC_SOURCE_SCHEMA", "AUTODOC_DIAGRAM_SCHEMA", "AUTODOC_AUDIT_SCHEMA",
    "AUTODOC_HTML_SCHEMA", "AUTODOC_RECONSTRUCTION_SCHEMA", "AUTODOC_PACKET_SCHEMA",
    "AUTODOC_MARKDOWN_SCHEMA", "AUTODOC_PREZA_SCHEMA", "PREZA_PARITY_SCHEMA", "DiscoveryReport", "AutodocBuilder",
    "discover_workspace", "build_bundle", "render_bundle", "audit_bundle", "verify_bundle",
    "reconstruct_bundle", "augment_markdown", "canonical_digest", "validate_autodoc_contract",
    "schema_contract_payload", "write_bundle_atomic", "load_bundle", "audit_payload",
]
