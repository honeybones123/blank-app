"""Keep Runtime and its bundled Inputs V2 package on one source revision.

The application owns the compatible ``inputs_v2`` source under ``packages``.
An older editable installation must never take precedence because that can
silently apply a different domain contract to every engineering family.
"""

from __future__ import annotations

from pathlib import Path
import sys


RUNTIME_ROOT = Path(__file__).resolve().parent
LOCAL_INPUTS_V2_SRC = RUNTIME_ROOT / "packages" / "beamapp-inputs-v2" / "src"


def prefer_runtime_checkout_sources() -> None:
    """Put this checkout and its matching Inputs V2 source first on ``sys.path``."""

    ordered = (str(LOCAL_INPUTS_V2_SRC), str(RUNTIME_ROOT))
    for path in ordered:
        while path in sys.path:
            sys.path.remove(path)
    # Insert in reverse because every insertion occurs at index zero.
    for path in reversed(ordered):
        sys.path.insert(0, path)


__all__ = [
    "LOCAL_INPUTS_V2_SRC",
    "RUNTIME_ROOT",
    "prefer_runtime_checkout_sources",
]
