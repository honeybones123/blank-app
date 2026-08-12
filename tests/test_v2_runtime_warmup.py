from __future__ import annotations

from inputs_application.new_design_brain_adapter import _v2_api as design_api
from inputs_application.v2_engineering_calculation_adapter import (
    _v2_api as calculation_api,
)


def test_v2_api_tables_are_process_cached_and_boundaries_stay_separate() -> None:
    calculation_first = calculation_api()
    calculation_second = calculation_api()
    design_first = design_api()
    design_second = design_api()

    assert calculation_first is calculation_second
    assert design_first is design_second
    assert "DesignGuideOrchestrator" not in calculation_first
    assert "DesignGuideOrchestrator" in design_first


def test_background_warmup_is_one_shot() -> None:
    # Import locally so this test proves the public warm-up API without relying
    # on app.py (which also initializes Streamlit rendering state).
    from application.v2_runtime_warmup import (
        start_v2_runtime_warmup,
        wait_for_v2_runtime_warmup,
    )

    first = start_v2_runtime_warmup()
    second = start_v2_runtime_warmup()

    assert first is True
    assert second is False
    assert wait_for_v2_runtime_warmup(timeout=5.0) is True
