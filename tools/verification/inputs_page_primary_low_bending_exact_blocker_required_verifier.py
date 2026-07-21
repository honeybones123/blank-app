from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_primary_low_bending_exact_blocker_required_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_primary_low_bending_exact_blocker_required_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_family = inputs_page._design_guide_candidate_family
    original_visible = inputs_page._design_guide_item_is_visible_blocker
    original_best_safe = inputs_page._guidance_item_best_safe_partial_cleanup
    original_incremental = inputs_page._guidance_item_safe_incremental_cleanup_below_threshold
    original_exact = inputs_page._guidance_item_has_low_util_exact_blocker

    def family(item):
        calls.append({"event": "family", "item": dict(item or {})})
        return str((item or {}).get("family") or "")

    def visible(item):
        calls.append({"event": "visible", "item": dict(item or {})})
        return bool((item or {}).get("visible_blocker"))

    def best_safe(item):
        calls.append({"event": "best_safe", "item": dict(item or {})})
        return bool((item or {}).get("best_safe"))

    def incremental(item):
        calls.append({"event": "incremental", "item": dict(item or {})})
        return bool((item or {}).get("incremental"))

    def has_exact(item, family_name):
        calls.append({"event": "has_exact", "item": dict(item or {}), "family": family_name})
        return family_name in dict((item or {}).get("exact_blockers_by_family") or {})

    try:
        inputs_page._design_guide_candidate_family = family
        inputs_page._design_guide_item_is_visible_blocker = visible
        inputs_page._guidance_item_best_safe_partial_cleanup = best_safe
        inputs_page._guidance_item_safe_incremental_cleanup_below_threshold = incremental
        inputs_page._guidance_item_has_low_util_exact_blocker = has_exact

        contract_enabled_true = inputs_page.render_design_guide_primary_low_bending_exact_blocker_required(
            primary_post_click_item={
                "family": "bending",
                "title_main": "Bending best safe cleanup",
                "best_safe": True,
            },
            primary_post_click_contract={"expected_util": 0.72},
            primary_post_click_contract_enabled=True,
            primary_post_click_expected_util=0.72,
        )
        blocking_reason_true = inputs_page.render_design_guide_primary_low_bending_exact_blocker_required(
            primary_post_click_item={
                "family": "bending",
                "title_main": "Bending cleanup",
                "exact_blockers_by_family": {"bending": {"reason": "low"}},
            },
            primary_post_click_contract={
                "blocking_reason": "candidate_final_accepted_state_unresolved_low_family",
            },
            primary_post_click_contract_enabled=False,
            primary_post_click_expected_util=0.7,
        )
        action_type_true = inputs_page.render_design_guide_primary_low_bending_exact_blocker_required(
            primary_post_click_item={
                "family": "bending",
                "action_type": "apply_resolved_candidate",
                "title_main": "Best safe action",
            },
            primary_post_click_contract={},
            primary_post_click_contract_enabled=False,
            primary_post_click_expected_util=0.8,
        )
        false_family = inputs_page.render_design_guide_primary_low_bending_exact_blocker_required(
            primary_post_click_item={
                "family": "shear",
                "title_main": "Shear best safe cleanup",
                "best_safe": True,
            },
            primary_post_click_contract={"expected_util": 0.72},
            primary_post_click_contract_enabled=True,
            primary_post_click_expected_util=0.72,
        )
        false_util = inputs_page.render_design_guide_primary_low_bending_exact_blocker_required(
            primary_post_click_item={
                "family": "bending",
                "title_main": "Bending best safe cleanup",
                "best_safe": True,
            },
            primary_post_click_contract={"expected_util": 0.9},
            primary_post_click_contract_enabled=True,
            primary_post_click_expected_util=0.9,
        )
        false_visible = inputs_page.render_design_guide_primary_low_bending_exact_blocker_required(
            primary_post_click_item={
                "family": "bending",
                "action_type": "apply_resolved_candidate",
                "visible_blocker": True,
                "title_main": "Best safe action",
            },
            primary_post_click_contract={},
            primary_post_click_contract_enabled=False,
            primary_post_click_expected_util=0.7,
        )
    finally:
        inputs_page._design_guide_candidate_family = original_family
        inputs_page._design_guide_item_is_visible_blocker = original_visible
        inputs_page._guidance_item_best_safe_partial_cleanup = original_best_safe
        inputs_page._guidance_item_safe_incremental_cleanup_below_threshold = original_incremental
        inputs_page._guidance_item_has_low_util_exact_blocker = original_exact

    expect(
        "true_paths",
        contract_enabled_true is True
        and blocking_reason_true is True
        and action_type_true is True,
        (
            f"contract={contract_enabled_true} blocking={blocking_reason_true} "
            f"action_type={action_type_true}"
        ),
    )
    expect(
        "false_paths",
        false_family is False
        and false_util is False
        and false_visible is False,
        f"family={false_family} util={false_util} visible={false_visible}",
    )
    expect(
        "call_coverage",
        any(call["event"] == "visible" for call in calls)
        and any(call["event"] == "best_safe" for call in calls)
        and any(call["event"] == "has_exact" for call in calls),
        f"calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "contract_enabled_true": contract_enabled_true,
        "blocking_reason_true": blocking_reason_true,
        "action_type_true": action_type_true,
        "false_family": false_family,
        "false_util": false_util,
        "false_visible": false_visible,
        "calls": calls,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Low Bending Exact Blocker Required Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(failures or ["None."]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
