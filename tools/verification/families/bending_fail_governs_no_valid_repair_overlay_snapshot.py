"""Snapshot for BENDING_FAIL_GOVERNS no-valid-repair overlay proof.

This verifies that once page evaluation has checked the family-generated
contract ladder and found zero safe candidates, the family overlay emits
family-owned blocked/exhausted evidence instead of diagnostic-only exhaustion.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.families.bending_fail_governs.runtime import NON_TERMINAL_LANES  # noqa: E402
from design_brain.families.registry import family_strategy_for  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _sample_ladder() -> dict[str, Any]:
    specs = [
        {"label": f"candidate {idx}", "updates": {"D": 400 + idx}, "ladder_index": idx}
        for idx in range(1, 4)
    ]
    return {
        "specs": specs,
        "ranking_rule": "Evaluate contract runtime lane order and stop immediately on the first fully compliant executor-backed pure bending repair.",
        "known_bad_candidate_count": 0,
        "terminal_status": "DIAGNOSTIC_INCOMPLETE_NO_REPAIR_PROOF",
        "repair_blocked": False,
        "blocked_reason": None,
        "blocked_reason_source": "diagnostic_internal_cap_only",
        "internal_cap_only": True,
        "hard_blocker_proven": False,
        "contract_strategy_exhaustion_proven": False,
        "contract_strategies_checked": list(NON_TERMINAL_LANES),
        "contract_strategies_blocked": [],
        "contract_strategies_remaining": [],
        "implementation_caps_hit": [],
        "repair_reason_proof": {
            "proof_only": True,
            "blocked_ownership_proof": {
                "family_id": "BENDING_FAIL_GOVERNS",
                "terminal_status": "DIAGNOSTIC_INCOMPLETE_NO_REPAIR_PROOF",
                "repair_blocked": False,
                "internal_cap_only": True,
                "contract_strategy_exhaustion_proven": False,
                "contract_strategies_checked": list(NON_TERMINAL_LANES),
            },
        },
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    overlay = payload["overlay"]
    checks = payload["checks"]
    lines = [
        "# BENDING_FAIL_GOVERNS No-Valid-Repair Overlay Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Summary",
        "",
        f"- Repair blocked: `{overlay.get('bending_fail_repair_blocked')}`",
        f"- Blocked reason source: `{overlay.get('bending_fail_blocked_reason_source')}`",
        f"- Strategy exhaustion proven: `{overlay.get('bending_fail_contract_strategy_exhaustion_proven')}`",
        f"- Internal cap only: `{overlay.get('bending_fail_internal_cap_only')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- `{name}`: `{value}`" for name, value in checks.items())
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    strategy = family_strategy_for("BENDING_FAIL_GOVERNS")
    ladder = _sample_ladder()
    selected_result = {
        "selected": None,
        "selection_reason": "no_compliant_candidate_in_contract_ladder",
        "candidate_count": len(ladder["specs"]),
        "safe_candidate_count": 0,
    }
    overlay = strategy.repair_ladder_evidence_overlay(ladder=ladder, selected_result=selected_result)
    proof = dict(overlay.get("bending_fail_blocked_ownership_proof") or {})
    checks = {
        "overlay_marks_repair_blocked": overlay.get("bending_fail_repair_blocked") is True,
        "overlay_uses_family_contract_source": overlay.get("bending_fail_blocked_reason_source") == "family_contract_blocker_proof",
        "overlay_proves_strategy_exhaustion": overlay.get("bending_fail_contract_strategy_exhaustion_proven") is True,
        "overlay_not_internal_cap_only": overlay.get("bending_fail_internal_cap_only") is False,
        "proof_family_id": proof.get("family_id") == "BENDING_FAIL_GOVERNS",
        "proof_terminal_status": proof.get("terminal_status") == "REPAIR_BLOCKED",
        "proof_contains_evaluated_candidate_count": proof.get("evaluated_candidate_count") == len(ladder["specs"]),
        "proof_remaining_lanes_empty": list(proof.get("contract_strategies_remaining") or []) == [],
        "repair_reason_proof_surface_present": bool(overlay.get("repair_reason_proof")),
    }
    failures = [name for name, value in checks.items() if not value]
    payload = {
        "schema": "bending_fail_governs_no_valid_repair_overlay_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "sample_selected_result": selected_result,
        "overlay": overlay,
        "checks": checks,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"bending_fail_governs_no_valid_repair_overlay_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_no_valid_repair_overlay_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(json.dumps({"status": payload["status"], "artifact": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
