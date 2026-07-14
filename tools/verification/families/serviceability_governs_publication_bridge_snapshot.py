"""Focused publication bridge proof for SERVICEABILITY_GOVERNS."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.publication import enforce_family_selection_publication_contract  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _serviceability_result() -> dict[str, Any]:
    return {
        "selected_family_id": "SERVICEABILITY_GOVERNS",
        "status": "EXHAUSTED",
        "evidence": {
            "runtime_result": {
                "status": "EXHAUSTED",
                "selected_strategy_lane": "EXHAUSTED",
                "selected_recommendation": None,
                "exhausted_reason": "geometry limits reached",
                "exact_stop_proof": {"allowed": False},
                "exhausted_proof": {
                    "allowed": True,
                    "all_ladder_branches_attempted": True,
                    "no_valid_compliant_repair_exists": True,
                    "specific_blockers": ["geometry limits reached"],
                },
                "evidence": {
                    "selection_boundary": {
                        "selected_family_id": "SERVICEABILITY_GOVERNS",
                        "runtime_performs_family_selection": False,
                    },
                    "serviceability_governing_proof": {
                        "family_id": "SERVICEABILITY_GOVERNS",
                    },
                },
            }
        },
    }


def _mismatched_payload() -> dict[str, Any]:
    return {
        "guidance_items": [
            {
                "title_main": "Bending repair blocked by reinforcement/detailing limits",
                "title": "Bending repair blocked by reinforcement/detailing limits",
                "headline": "Bending repair blocked by reinforcement/detailing limits",
                "summary_line": "stale bending blocker",
                "family": "bending",
                "check_key": "bending",
                "selected_family_id": "SERVICEABILITY_GOVERNS",
                "published_family_id": "BENDING_FAIL_GOVERNS",
                "cta_family_id": "BENDING_FAIL_GOVERNS",
                "status": "FAIL",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "family": "bending",
                    "updates": {},
                },
            }
        ],
        "debug_trace": {
            "active_failures": ["serviceability"],
            "selected_family_id": "SERVICEABILITY_GOVERNS",
            "published_family_id": "BENDING_FAIL_GOVERNS",
            "cta_family_id": "BENDING_FAIL_GOVERNS",
            "serviceability_status": "FAIL",
            "design_brain_result": _serviceability_result(),
        },
        "design_brain_result": _serviceability_result(),
        "overview": {
            "any_fail": True,
            "all_key_pass": False,
            "serviceability_state": "FAIL",
            "serviceability_status": "FAIL",
            "bending_state": "TARGET",
            "shear_state": "TARGET",
        },
    }


def run() -> dict[str, Any]:
    result = enforce_family_selection_publication_contract(_mismatched_payload())
    item = dict((result.get("guidance_items") or [{}])[0] or {})
    debug = dict(result.get("debug_trace") or {})
    contract = dict(item.get("button_contract") or {})
    checks = {
        "serviceability_selected": item.get("selected_family_id") == "SERVICEABILITY_GOVERNS",
        "serviceability_published": item.get("published_family_id") == "SERVICEABILITY_GOVERNS",
        "serviceability_cta": item.get("cta_family_id") == "SERVICEABILITY_GOVERNS",
        "wrong_family_error_not_published": item.get("title_main") != "Design Guide family contract violation",
        "old_bending_blocker_not_published": "Bending repair blocked" not in str(item.get("title_main") or ""),
        "terminal_publication_marker_present": bool(item.get("serviceability_governs_terminal_publication")),
        "known_outcome_status": str(item.get("status") or "").upper() in {"BLOCKED", "PASS"},
        "cta_disabled_without_family_owned_apply": not bool(contract.get("enabled") or contract.get("actionable")),
        "debug_records_serviceability_route": bool(
            debug.get("family_guard_recovered_to_serviceability_terminal_publication")
            or debug.get("family_guard_routed_to_serviceability_terminal_publication")
        ),
    }
    passed = all(checks.values())
    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "schema": "serviceability_governs_publication_bridge_snapshot.v1",
        "result": "PASS" if passed else "FAIL",
        "checks": checks,
        "item": item,
        "button_contract": contract,
    }
    json_path = ARTIFACT_DIR / f"serviceability_governs_publication_bridge_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_governs_publication_bridge_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SERVICEABILITY_GOVERNS Publication Bridge",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                *[f"- `{key}`: `{value}`" for key, value in checks.items()],
                "",
            ]
        ),
        encoding="utf-8",
    )
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    return snapshot


def main() -> int:
    snapshot = run()
    print(f"SERVICEABILITY_GOVERNS publication bridge {snapshot['result']}")
    print(f"JSON: {snapshot['artifact']}")
    print(f"Report: {snapshot['report']}")
    return 0 if snapshot["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
