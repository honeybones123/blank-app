from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "verification" / "helpers" / "cold_page_benchmark.py"


def _module():
    spec = importlib.util.spec_from_file_location("cold_page_benchmark", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_benchmark_covers_every_general_calculation_page() -> None:
    module = _module()
    assert module.PAGES == (
        "bending",
        "shear",
        "creep",
        "shrinkage",
        "crack",
        "deflection",
    )
    assert set(module.PAGE_TITLES) == set(module.PAGES)
    assert set(module.PAGE_NAV_LABELS) == set(module.PAGES)


def test_acceptance_requires_every_cold_run_below_one_second() -> None:
    module = _module()
    passing = module._summary(
        [{"page_open_ms": 900.0}, {"page_open_ms": 999.9}]
    )
    failing = module._summary(
        [{"page_open_ms": 800.0}, {"page_open_ms": 1000.0}]
    )
    assert passing["all_under_1000_ms"] is True
    assert failing["all_under_1000_ms"] is False


def test_trace_delta_report_ranks_the_slowest_phases_first() -> None:
    module = _module()
    ranked = module._top_trace_deltas(
        [
            {"name": "quick", "delta_ms": 1.0, "elapsed_ms": 1.0},
            {"name": "slow", "delta_ms": 25.0, "elapsed_ms": 26.0},
        ]
    )
    assert [item["name"] for item in ranked] == ["slow", "quick"]


def test_reconnected_or_multiple_transaction_samples_are_not_page_timings() -> None:
    module = _module()
    assert module._measurement_validity({}, [{}]) == (True, None)
    assert module._measurement_validity({"new_session": 1}, [{}]) == (True, None)
    assert module._measurement_validity({}, [{}, {}]) == (
        False,
        "multiple_script_transactions",
    )


def test_cold_benchmark_records_setup_failures_as_invalid_attempts() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"browser_or_server_setup_failed"' in source
    assert '"error_type": type(exc).__name__' in source
