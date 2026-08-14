"""One registry for calculation-page loading and non-blocking warm-up.

The application shell remains the only route selector.  This module provides
neutral import/render facts so individual pages do not grow their own loading
or preloading paths.
"""

from __future__ import annotations

import importlib
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PageModuleSpec:
    module_name: str
    renderer_name: str


CALCULATION_PAGE_MODULES: dict[str, PageModuleSpec] = {
    "bending": PageModuleSpec("bending_page", "render_bending"),
    "shear": PageModuleSpec("shear_page", "render_shear"),
    "creep": PageModuleSpec("creep", "render_creep"),
    "shrinkage": PageModuleSpec("shrinkage", "render_shrinkage"),
    "crack": PageModuleSpec("crack_page", "render_crack_control"),
    "deflection": PageModuleSpec("deflection", "render_deflection"),
}

_warm_lock = threading.Lock()
_warm_started = False
_warm_finished = False
_warm_timings_ms: dict[str, float] = {}
_warm_errors: dict[str, str] = {}


def render_module_page(module_name: str, renderer_name: str) -> Any:
    """Import and render one registered page, with one hot-reload recovery."""

    module = importlib.import_module(module_name)
    renderer = getattr(module, renderer_name, None)
    if callable(renderer):
        return renderer()
    refreshed = importlib.reload(module)
    renderer = getattr(refreshed, renderer_name, None)
    if callable(renderer):
        return renderer()
    raise AttributeError(
        f"module {module_name!r} has no callable {renderer_name!r}"
    )


def render_calculation_page(page_slug: str) -> Any:
    """Render a calculation page from the single authoritative registry."""

    slug = str(page_slug or "").strip().lower()
    try:
        spec = CALCULATION_PAGE_MODULES[slug]
    except KeyError as exc:
        raise ValueError(f"unknown calculation page: {page_slug!r}") from exc
    return render_module_page(spec.module_name, spec.renderer_name)


def _warm_modules(specs: Iterable[PageModuleSpec]) -> None:
    global _warm_finished
    try:
        for spec in specs:
            started = time.perf_counter()
            try:
                importlib.import_module(spec.module_name)
            except Exception as exc:  # warm-up cannot own product error handling
                _warm_errors[spec.module_name] = (
                    f"{type(exc).__name__}: {exc}"
                )
            finally:
                _warm_timings_ms[spec.module_name] = round(
                    (time.perf_counter() - started) * 1000.0,
                    3,
                )
    finally:
        _warm_finished = True


def warm_calculation_pages_in_background() -> bool:
    """Start one process-wide, non-blocking import warm-up.

    Returns ``True`` only for the caller that starts the daemon worker.  The
    worker imports modules but never reads or writes Streamlit session state.
    """

    global _warm_started
    with _warm_lock:
        if _warm_started:
            return False
        _warm_started = True
        worker = threading.Thread(
            target=_warm_modules,
            args=(tuple(CALCULATION_PAGE_MODULES.values()),),
            name="calculation-page-module-warmup",
            daemon=True,
        )
        worker.start()
        return True


def calculation_page_warmup_status() -> dict[str, Any]:
    """Return immutable diagnostic evidence for tests and timing reports."""

    with _warm_lock:
        return {
            "started": bool(_warm_started),
            "finished": bool(_warm_finished),
            "timings_ms": dict(_warm_timings_ms),
            "errors": dict(_warm_errors),
        }


__all__ = [
    "CALCULATION_PAGE_MODULES",
    "PageModuleSpec",
    "calculation_page_warmup_status",
    "render_calculation_page",
    "render_module_page",
    "warm_calculation_pages_in_background",
]
