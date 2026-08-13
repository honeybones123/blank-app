from __future__ import annotations

import pytest

from application.result_page_workspace import resolve_result_page_workspace


@pytest.mark.parametrize(
    "state, expected_reason",
    [
        ({"inputs_dirty": True}, "engineering_inputs_dirty"),
        ({"_inputs_dirty": True}, "engineering_inputs_dirty"),
        ({"results": {}}, "calculation_cache_missing"),
        ({"_cached_compute_results": {}}, "result_projection_missing"),
    ],
)
def test_result_page_refreshes_only_for_missing_or_dirty_engineering_state(
    state: dict[str, object], expected_reason: str
) -> None:
    decision = resolve_result_page_workspace("shear", state)
    assert decision.requires_calculation is True
    assert decision.reason == expected_reason


def test_display_only_result_page_rerun_reuses_current_projection() -> None:
    decision = resolve_result_page_workspace(
        "shear",
        {
            "inputs_dirty": False,
            "_inputs_dirty": False,
            "_cached_compute_results": {},
            "results": {},
            "shear_show_cracks": False,
        },
    )
    assert decision.requires_calculation is False
    assert decision.reason == "current_projection_reusable"


def test_result_page_slug_is_required() -> None:
    with pytest.raises(ValueError, match="page_slug"):
        resolve_result_page_workspace("", {})
