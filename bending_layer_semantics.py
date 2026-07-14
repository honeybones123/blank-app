"""
Compatibility imports for sagging vs hogging layer semantics.

The pure calculation ownership lives in calculations.bending. Existing diagram,
page, and verification imports keep using this module without changing behavior.
"""

from __future__ import annotations

from calculations.bending import (
    resolve_bending_faces,
    resolve_bending_layer_geometry,
)

__all__ = [
    "resolve_bending_faces",
    "resolve_bending_layer_geometry",
]
