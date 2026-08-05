"""Deterministic identity for the externally composed Inputs V2 source."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=4)
def _source_manifest_hash(source_root_text: str) -> str:
    """Hash the V2 source files in stable path order without importing V2."""

    root = Path(source_root_text) / "src" / "inputs_v2"
    if not root.is_dir():
        return "missing"
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*.py") if path.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def source_manifest_hash(source_root: Path | str) -> str:
    """Return the process-cached identity of the selected V2 source tree."""

    return _source_manifest_hash(str(Path(source_root).expanduser().resolve()))


__all__ = ["source_manifest_hash"]
