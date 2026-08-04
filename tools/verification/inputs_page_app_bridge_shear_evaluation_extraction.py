"""Verify application ownership of candidate shear evaluation."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.recipes.one_click_recipe_defs import (
    build_state,
    find_named_case,
)


EXPECTED = {
    "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02": (0.0, 0.0, 0.0, 0, 0.0),
    "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01": (
        1.345996588135,
        0.516461483502,
        10.0,
        2,
        300.0,
    ),
    "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01": (
        0.054920829956,
        0.094975747812,
        12.0,
        4,
        100.0,
    ),
}


def _projection(result: dict) -> tuple:
    return (
        round(float(result["util"]), 12),
        round(float(result["web_util"]), 12),
        float(result["lig_d"]),
        int(result["lig_legs"]),
        float(result["s_lig"]),
    )


def main() -> int:
    bridge_source = (
        ROOT / "inputs_page_app_contract_bridge.py"
    ).read_text(encoding="utf-8")
    owned_source = (
        ROOT / "inputs_application" / "recommendation_evaluation.py"
    ).read_text(encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.recommendation_evaluation import (
            evaluate_shear_with_state,
        )

        parity = {}
        for recipe, expected in EXPECTED.items():
            state = build_state(find_named_case(recipe)["changes"])
            bridge_result = bridge._evaluate_shear_with_state_for_app_bridge(
                state
            )
            owned_result = evaluate_shear_with_state(state)
            parity[recipe] = {
                "bridge_matches_owned": (
                    _projection(bridge_result) == _projection(owned_result)
                ),
                "owned_matches_frozen_output": (
                    _projection(owned_result) == expected
                ),
            }
    checks = {
        "bridge_delegates_to_owned_shear_evaluator": (
            "return _evaluate_shear_with_state_owned(" in bridge_source
        ),
        "old_app_bridge_kernel_deleted": not (
            ROOT / "inputs_page_modules" / "app_bridge" / "shear_evaluation.py"
        ).exists(),
        "owned_evaluator_has_no_legacy_import": all(
            token not in owned_source
            for token in (
                "inputs_page_app_contract_bridge",
                "inputs_page_route_coordinators",
            )
        ),
        "all_recipe_outputs_match": all(
            all(fields.values()) for fields in parity.values()
        ),
    }
    result = {
        "contract_version": "inputs_shear_evaluation_application_owner.v1",
        "checks": checks,
        "parity": parity,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
