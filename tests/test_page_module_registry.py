from __future__ import annotations

import time

from application.page_module_registry import (
    CALCULATION_PAGE_MODULES,
    calculation_page_render_status,
    calculation_page_warmup_status,
    render_module_page,
    warm_calculation_pages_in_background,
)


def test_registry_covers_every_general_calculation_page_once() -> None:
    assert tuple(CALCULATION_PAGE_MODULES) == (
        "bending",
        "shear",
        "creep",
        "shrinkage",
        "crack",
        "deflection",
    )
    modules = [spec.module_name for spec in CALCULATION_PAGE_MODULES.values()]
    assert len(modules) == len(set(modules))


def test_background_warmup_is_process_singleton_and_has_no_errors() -> None:
    first = warm_calculation_pages_in_background()
    second = warm_calculation_pages_in_background()
    assert first is True
    assert second is False
    deadline = time.monotonic() + 10.0
    status = calculation_page_warmup_status()
    while not status["finished"] and time.monotonic() < deadline:
        time.sleep(0.01)
        status = calculation_page_warmup_status()
    assert status["finished"] is True
    assert status["errors"] == {}
    assert set(status["timings_ms"]) == {
        spec.module_name for spec in CALCULATION_PAGE_MODULES.values()
    }


def test_background_warmup_can_be_disabled_for_true_cold_benchmarks(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CODEX_DISABLE_CALC_PAGE_WARMUP", "1")
    assert warm_calculation_pages_in_background() is False


def test_render_timing_is_factual_and_does_not_change_renderer_output(
    monkeypatch,
) -> None:
    class _Module:
        @staticmethod
        def render_bending():
            return {"unchanged": True}

    monkeypatch.setattr(
        "application.page_module_registry.importlib.import_module",
        lambda _name: _Module,
    )
    result = render_module_page("bending_page", "render_bending")
    timing = calculation_page_render_status("bending")

    assert result == {"unchanged": True}
    assert timing["import_ms"] >= 0.0
    assert timing["render_ms"] >= 0.0
    assert isinstance(timing["module_was_loaded"], bool)
