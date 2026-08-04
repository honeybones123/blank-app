from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.final_publication import build_final_design_guide_publication  # noqa: E402
from design_brain.publication import enforce_underdesign_repair_publication_boundary  # noqa: E402


FAMILY_ID = "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"
BLOCKER = "underdesign_repair_invariant_requires_repair_or_no_repair_proof"


def _repair_contract() -> dict[str, Any]:
    return {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "preview_pass": True,
        "candidate_id": "candidate_000",
        "source_candidate_id": "candidate_000",
        "expected_util": 0.21,
        "blocking_reason": None,
        "updates": {
            "b": 600.0,
            "D": 950.0,
            "db_bot_1": 40,
            "bot2_count": 3,
            "db_bot_2": 40,
            "bot_row_count": 2,
            "bot_row_1_spacing": 0.0,
            "bot_row_1_dia": 40,
            "bot_row_2_bars": 3,
            "bot_row_2_spacing": 0.0,
            "bot_row_2_dia": 40,
        },
    }


def _payload() -> dict[str, Any]:
    stale_disabled_shell = {
        "enabled": False,
        "actionable": False,
        "family": "bending",
        "action_type": None,
        "updates": {},
        "blocking_reason": BLOCKER,
    }
    return {
        "active_failures": ["bending"],
        "overview": {
            "statuses": {"bending": "FAIL", "shear": "PASS"},
            "utils": {"bending": 5.47, "shear": 0.52},
            "worst_util": 5.47,
        },
        "design_brain_result": {
            "selected_family_id": FAMILY_ID,
            "published_family_id": FAMILY_ID,
            "active_failures": ["bending"],
        },
        "debug_trace": {
            "selected_family_id": FAMILY_ID,
            "published_family_id": FAMILY_ID,
            "cta_family_id": FAMILY_ID,
            "button_contract": _repair_contract(),
            "selected_action_updates": dict(_repair_contract()["updates"]),
            "selected_action_type": "apply_resolved_candidate",
            "selected_candidate_id": "candidate_000",
            "primary_card_actionable": True,
        },
        "guidance_items": [
            {
                "title_main": "Bending capacity is low",
                "title": "Bending capacity is low",
                "family": "bending",
                "check_key": "bending",
                "selected_family_id": FAMILY_ID,
                "published_family_id": FAMILY_ID,
                "cta_family_id": FAMILY_ID,
                "guidance_intent": "required_fix",
                "status": "FAIL",
                "button_contract": stale_disabled_shell,
                "candidate_search_evidence": {
                    "selected_family_id": FAMILY_ID,
                    "published_family_id": FAMILY_ID,
                    "cta_family_id": FAMILY_ID,
                    "family_route_owner": (
                        "design_brain.families.bending_fail_shear_overdesign."
                        "BendingFailShearOverdesignFamily"
                    ),
                },
            }
        ],
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_shear_overdesign_governs_publication_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_shear_overdesign_governs_publication_regression_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_SHEAR_OVERDESIGN Publication Regression",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    result = enforce_underdesign_repair_publication_boundary(_payload())
    item = dict((result.get("guidance_items") or [{}])[0])
    debug = dict(result.get("debug_trace") or {})
    evidence = dict(item.get("candidate_search_evidence") or {})
    contract = dict(item.get("button_contract") or {})
    updates = dict(contract.get("updates") or {})
    plain_bending_publication = build_final_design_guide_publication(
        item={
            "title_main": "Bending capacity is low",
            "title": "Bending capacity is low",
            "family": "bending",
            "check_key": "bending",
            "action_type": "apply_resolved_candidate",
            "button_contract": _repair_contract(),
        },
        debug={
            "selected_family_id": "bending",
            "published_family_id": "bending",
            "cta_family_id": "bending",
            "exact_blockers_by_family": {
                "shear": {
                    "current_util": 0.52,
                    "attempted_updates": {
                        "lig_d": 0,
                        "lig_legs": 0,
                        "s_lig": 200.0,
                    },
                    "reason": "shear overdesign cleanup considered during active bending repair",
                }
            },
        },
        publication_reason="bending_fail_shear_overdesign_identity_regression",
    )
    checks = {
        "boundary_checked": debug.get("contract_boundary_checked") is True,
        "boundary_passed": debug.get("contract_boundary_passed") is True,
        "allowed_repair_action": evidence.get("allowed_outcome") == "repair_ACTION",
        "stale_disabled_shell_replaced": contract.get("enabled") is True and contract.get("actionable") is True,
        "updates_preserved": updates == _repair_contract()["updates"],
        "preview_pass_preserved": contract.get("preview_pass") is True,
        "blocking_reason_cleared": not contract.get("blocking_reason"),
        "mixed_family_preserved": item.get("selected_family_id") == FAMILY_ID
        and item.get("published_family_id") == FAMILY_ID
        and item.get("cta_family_id") == FAMILY_ID,
        "plain_bending_with_shear_overdesign_blocker_canonicalises_to_mixed_family": (
            plain_bending_publication.selected_family == FAMILY_ID
        ),
        "plain_bending_mixed_publication_keeps_executor_cta_enabled": (
            plain_bending_publication.cta.enabled is True
            and plain_bending_publication.cta.action_type == "apply_resolved_candidate"
            and bool(plain_bending_publication.cta.updates)
        ),
        "no_invariant_error_published": BLOCKER not in json.dumps(item, sort_keys=True),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "bending_fail_shear_overdesign_governs_publication_regression.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "published_item": item,
        "debug": debug,
        "plain_bending_publication": plain_bending_publication.to_dict(),
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("BENDING_FAIL_SHEAR_OVERDESIGN publication regression FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("BENDING_FAIL_SHEAR_OVERDESIGN publication regression PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
