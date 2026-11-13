"""Tag dictionary loading and alias resolution (J05)."""

import json
from pathlib import Path

from .contract import validate_tags_dictionary, ContractError


class TagError(ValueError):
    def __init__(self, code, message=None):
        super().__init__(f"{code}" + (f": {message}" if message else ""))
        self.code = code


_CACHE = {}


def dictionary_path(docs):
    return docs / "skil_data" / "task-doc" / "state" / "tags.json"


def load_dictionary(docs, refresh=False):
    path = dictionary_path(docs)
    key = str(path)
    if not refresh and key in _CACHE:
        return _CACHE[key]
    if not path.is_file():
        raise TagError("tags_dictionary_missing", str(path))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TagError("tags_dictionary_invalid", str(exc)) from None
    errors = validate_tags_dictionary(data)
    if errors:
        raise TagError("tags_dictionary_invalid", errors[0].get("code"))
    _CACHE[key] = data
    return data


def resolve_tag(docs, reference):
    """Resolve canonical tag id from id or alias; raise on unknown/ambiguous."""
    data = load_dictionary(docs)
    norm = str(reference).casefold()
    matches = []
    for tag in data["tags"]:
        if tag["id"].casefold() == norm:
            matches = [tag["id"]]
            break
        if norm in {alias.casefold() for alias in tag["aliases"]}:
            matches.append(tag["id"])
    unique = sorted(set(matches))
    if len(unique) == 1:
        if unique[0] != reference:
            return unique[0]
        return unique[0]
    if not unique:
        raise TagError("unknown_tag", reference)
    raise TagError("ambiguous_alias", reference)


def resolve_tags(docs, reference):
    """Compatibility shim used by search; raises on unknown tags."""
    return resolve_tag(docs, reference)
