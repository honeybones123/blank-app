"""Compatibility façade for callers that still import :mod:`creep`.

The application registry renders :mod:`creep_page`; this module keeps report,
batch and legacy imports stable while the Creep page is modularised.
"""

from __future__ import annotations

from creep_page import (
    compute_creep_results,
    render_creep,
    render_creep_page,
)


__all__ = [
    "compute_creep_results",
    "render_creep",
    "render_creep_page",
]
