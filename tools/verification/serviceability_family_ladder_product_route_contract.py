"""Focused product-route proof for the SERVICEABILITY_GOVERNS ladder."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules import guidance_compute as subject  # noqa: E402


def main() -> int:
    evaluations: list[dict] = []

    def evaluate(state, *, updates=None, source, label=None, action_type=None):
        evaluations.append(
            {
                "state": dict(state),
                "updates": dict(updates or {}),
                "source": source,
                "label": label,
                "action_type": action_type,
            }
        )
        return {
            "overview": {
                "all_key_pass": True,
                "any_fail": False,
                "statuses": {
                    "bending": "PASS",
                    "shear": "PASS",
                    "crack": "PASS",
                    "deflection": "PASS",
                },
                "utils": {
                    "bending": 0.91,
                    "shear": 0.88,
                    "crack": 0.82,
                    "deflection": 0.94,
                },
            },
            "updates": dict(updates or {}),
            "state": dict(state),
        }

    original_evaluate = subject._evaluate_auto_design_candidate
    original_screen = subject._evaluate_serviceability_ladder_screen_candidate
    original_item_builder = subject._guidance_item_from_resolved_candidate
    subject._evaluate_auto_design_candidate = evaluate
    subject._evaluate_serviceability_ladder_screen_candidate = (
        lambda state, *, reference_overview, updates=None, source, label=None, action_type=None: evaluate(
            state,
            updates=updates,
            source=source,
            label=label,
            action_type=action_type,
        )
    )
    subject._guidance_item_from_resolved_candidate = (
        lambda candidate, **kwargs: {
            "title_main": kwargs.get("title"),
            "action_type": "apply_resolved_candidate",
            "action_payload": {},
            "button_contract": {},
            "resolved_candidate": dict(candidate),
        }
    )
    try:
        debug: dict = {}
        item = subject._serviceability_contract_ladder_guidance_item(
            {
                "b": 300.0,
                "D": 500.0,
                "bot1_count": 3,
                "db_bot_1": 20,
            },
            {
                "any_fail": True,
                "statuses": {
                    "bending": "PASS",
                    "shear": "PASS",
                    "crack": "FAIL",
                    "deflection": "FAIL",
                },
                "utils": {
                    "bending": 0.70,
                    "shear": 0.65,
                    "crack": 1.15,
                    "deflection": 1.20,
                },
            },
            debug_sink=debug,
        )
    finally:
        subject._evaluate_auto_design_candidate = original_evaluate
        subject._evaluate_serviceability_ladder_screen_candidate = original_screen
        subject._guidance_item_from_resolved_candidate = original_item_builder

    contract = dict((item or {}).get("button_contract") or {})
    updates = dict(contract.get("updates") or {})
    def reject_full(state, *, updates=None, source, label=None, action_type=None):
        result = evaluate(
            state,
            updates=updates,
            source=source,
            label=label,
            action_type=action_type,
        )
        result["overview"].update(
            {
                "all_key_pass": False,
                "any_fail": True,
                "statuses": {
                    **dict(result["overview"].get("statuses") or {}),
                    "deflection": "FAIL",
                },
            }
        )
        return result

    subject._evaluate_auto_design_candidate = reject_full
    subject._evaluate_serviceability_ladder_screen_candidate = original_screen
    subject._evaluate_serviceability_ladder_screen_candidate = (
        lambda state, *, reference_overview, updates=None, source, label=None, action_type=None: evaluate(
            state,
            updates=updates,
            source=source,
            label=label,
            action_type=action_type,
        )
    )
    disagreement_debug: dict = {}
    try:
        disagreement_item = subject._serviceability_contract_ladder_guidance_item(
            {
                "b": 300.0,
                "D": 500.0,
                "bot1_count": 3,
                "db_bot_1": 20,
            },
            {
                "any_fail": True,
                "statuses": {
                    "bending": "PASS",
                    "shear": "PASS",
                    "crack": "FAIL",
                    "deflection": "FAIL",
                },
                "utils": {
                    "bending": 0.70,
                    "shear": 0.65,
                    "crack": 1.15,
                    "deflection": 1.20,
                },
            },
            debug_sink=disagreement_debug,
        )
    finally:
        subject._evaluate_auto_design_candidate = original_evaluate
        subject._evaluate_serviceability_ladder_screen_candidate = original_screen

    checks = {
        "route_returns_actionable_item": isinstance(item, dict),
        "family_identity_preserved": contract.get("family") == "SERVICEABILITY_GOVERNS",
        "nested_contract_update_translated": updates.get("bot1_count") == 4,
        "no_nested_updates_leak_to_apply": not {"geometry", "reinforcement"}.intersection(updates),
        "screen_and_full_evaluators_used": len(evaluations) >= 2
        and all(row.get("source") for row in evaluations)
        and evaluations[-1].get("source") == "SERVICEABILITY_GOVERNS.contract_ladder",
        "full_confirmation_recorded": (
            debug.get("serviceability_family_ladder_full_confirmation_passed") is True
        ),
        "fast_full_disagreement_rejected": disagreement_item is None,
        "fast_full_disagreement_recorded": (
            disagreement_debug.get(
                "serviceability_family_ladder_fast_full_disagreement"
            )
            is True
        ),
        "family_ladder_selected": debug.get("serviceability_family_ladder_found_safe") is True,
    }
    if not all(checks.values()):
        print({"checks": checks, "debug": debug, "updates": updates, "evaluations": evaluations})
        return 1
    print("serviceability_family_ladder_product_route_contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
