"""Read-only three-way classification for harness update previews.

The caller must establish ownership and validate paths before using this
module. A returned proposal is not permission to write or update a receipt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FileState:
    sha256: str
    mode: int

    def __post_init__(self) -> None:
        if not isinstance(self.sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        if type(self.mode) is not int or not 0 <= self.mode <= 0o7777:
            raise ValueError("mode must be permission bits between 0000 and 7777")


@dataclass(frozen=True)
class Proposal:
    status: str
    action: str
    choices: tuple[str, ...] = ()
    requires_review: bool = False


def classify_update(*, base_known: bool, base: FileState | None,
                    target: FileState | None, incoming: FileState | None,
                    ownership: str = "upstream") -> Proposal:
    """Classify one regular file for update without reading or writing files.

    ``base_known`` means that a receipt establishes the prior state; it must
    not be inferred from a filename match. ``None`` denotes an absent file.
    Type, path, symlink, secret and snapshot validation remain caller gates.
    """
    if type(base_known) is not bool:
        raise ValueError("base_known must be boolean")
    if any(item is not None and not isinstance(item, FileState) for item in (base, target, incoming)):
        raise ValueError("states must be FileState or None")
    if not base_known and base is not None:
        raise ValueError("base cannot be supplied without a known receipt")
    if ownership not in ("upstream", "local", "secret"):
        raise ValueError("unknown ownership")
    if ownership == "secret":
        raise ValueError("secret paths cannot be processed by update")
    if ownership == "local":
        if incoming is not None:
            return Proposal("local_path_collision", "review", ("keep", "rename_incoming", "skip"), True)
        if target is None:
            return Proposal("absent", "none")
        return Proposal("local_custom", "keep")

    if not base_known or base is None:
        if target is not None and incoming is not None:
            return Proposal("same_path_collision", "review", ("keep", "adopt", "rename_incoming", "skip"), True)
        if target is not None:
            return Proposal("unexpected_unclassified", "review", ("keep", "mark_local", "skip"), True)
        if incoming is not None:
            return Proposal("new_from_release", "add", (), True)
        return Proposal("absent", "none")

    if target is None:
        if incoming is None:
            return Proposal("both_deleted", "none")
        if incoming == base:
            return Proposal("locally_deleted", "keep_deleted")
        return Proposal("delete_modify_conflict", "review", ("keep_deleted", "restore_incoming", "skip"), True)
    if incoming is None:
        if target == base:
            return Proposal("deleted_upstream", "propose_delete", ("keep", "delete"), True)
        return Proposal("orphan_local_modified", "keep")
    if target == base and incoming == base:
        return Proposal("unchanged", "none")
    if target == base:
        return Proposal("modified_upstream", "replace", (), True)
    if incoming == base:
        return Proposal("local_modified", "keep")
    if target == incoming:
        return Proposal("already_applied", "none")
    return Proposal("both_modified", "review", ("keep", "replace", "edited", "skip"), True)
