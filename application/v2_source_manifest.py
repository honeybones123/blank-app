"""Deterministic identity for the installed Inputs V2 package."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from importlib import metadata, util
from pathlib import Path


EXPECTED_INPUTS_V2_VERSION = "0.1.2"


def installed_inputs_v2_root() -> Path:
    """Return the installed package root without importing application code."""

    spec = util.find_spec("inputs_v2")
    locations = tuple(spec.submodule_search_locations or ()) if spec else ()
    if len(locations) != 1:
        raise ModuleNotFoundError(
            "beamapp-inputs-v2 is not installed; install the V2 distribution "
            "in the Runtime Python environment"
        )
    return Path(locations[0]).resolve()


@lru_cache(maxsize=4)
def _source_manifest_hash(package_root_text: str, distribution_version: str) -> str:
    """Hash installed V2 Python sources in stable path order."""

    root = Path(package_root_text)
    digest = hashlib.sha256()
    digest.update(distribution_version.encode("utf-8"))
    for path in sorted(path for path in root.rglob("*.py") if path.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def source_manifest_hash() -> str:
    """Return the identity of the installed V2 distribution and its sources."""

    root = installed_inputs_v2_root()
    version = metadata.version("beamapp-inputs-v2")
    if version != EXPECTED_INPUTS_V2_VERSION:
        raise RuntimeError(
            "incompatible beamapp-inputs-v2 distribution: "
            f"expected {EXPECTED_INPUTS_V2_VERSION}, found {version}"
        )
    return _source_manifest_hash(str(root), version)


__all__ = [
    "EXPECTED_INPUTS_V2_VERSION",
    "installed_inputs_v2_root",
    "source_manifest_hash",
]
