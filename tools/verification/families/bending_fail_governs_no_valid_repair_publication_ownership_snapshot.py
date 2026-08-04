"""Proof-only BENDING_FAIL_GOVERNS no-valid-repair publication ownership snapshot.

The live no-button bug should resolve to a family-owned blocked/exhausted
publication, not a family-selection violation. This verifier proves the locked
BENDING_FAIL_GOVERNS runtime can produce the needed proof shape without an
executor-backed Apply CTA.
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

from design_brain.candidate_evaluation import (  # noqa: E402
    BeamCandidateEvaluation,
    BeamCandidateInput,
    BeamCandidateUpdate,
    build_candidate_state_hash,
)
from design_brain.families.bending_fail_governs.contract import (  # noqa: E402
    load_bending_fail_governs_contract,
)
from design_brain.families.bending_fail_governs.runtime import (  # noqa: E402
    NON_TERMINAL_LANES,
    bending_fail_governs_contract_lane_order,
    run_bending_fail_governs_ladder_runtime,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _evaluation(
    base_input: BeamCandidateInput,
    update: BeamCandidateUpdate,
) -> BeamCandidateEvaluation:
    lane_hint = str(update.updates.get("lane_hint") or "")
    if lane_hint == "NO_VALID_STRATEGY":
        status = {
            "terminal_status": "NO_VALID_STRATEGY",
            "blocked_reason": "all contract-permitted BENDING_FAIL_GOVERNS repair strategies exhausted with explicit terminal evidence",
            "accepted": True,
            "contract_strategy_exhaustion_proven": True,
            "contract_strategies_checked": list(NON_TERMINAL_LANES),
            "contract_strategies_blocked": [],
            "hard_blocker_proven": False,
            "internal_cap_only": False,
        }
    else:
        status = {
            "lane_result": "REJECTED",
            "accepted": False,
            "contract_strategies_checked": [lane_hint],
            "internal_cap_only": False,
        }
    return BeamCandidateEvaluation(
        input_hash=base_input.state_hash,
        candidate_state_hash=build_candidate_state_hash(base_input.base_state, update.updates),
        update_hash=update.update_hash,
        bending_utilisation=1.42,
        shear_utilisation=0.82,
        serviceability_status={"deflection": "PASS", "crack": "PASS"},
        geometry_status={"status": "PASS"},
        detailing_status={"status": "PASS"},
        spacing_status={"status": "PASS"},
        capacity_summary={"bending_status": "FAIL", "shear_status": "PASS"},
        failure_flags={"bending": True, "shear": False},
        engineering_status=status,
    ).with_evaluation_hash()


def _lane_updates() -> dict[str, dict[str, Any]]:
    return {lane_id: {"lane_hint": lane_id} for lane_id in bending_fail_governs_contract_lane_order()}


def _contract_publication_requirements() -> dict[str, Any]:
    contract = load_bending_fail_governs_contract()
    publication = dict(contract.get("publication") or {})
    blockers = dict(contract.get("blockers") or {})
    return {
        "publication_required_fields": list(publication.get("required_fields") or []),
        "publication_allowed_cta_states": list(publication.get("allowed_cta_states") or []),
        "valid_repair_blocked_proof": list(blockers.get("valid_repair_blocked_proof") or []),
        "implementation_cap_only_not_terminal": list(blockers.get("implementation_cap_only_not_terminal") or []),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    checks = payload["checks"]
    result = payload["runtime_result"]
    lines = [
        "# BENDING_FAIL_GOVERNS No-Valid-Repair Publication Ownership Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Executive Summary",
        "",
        f"- Family selected by runtime: `BENDING_FAIL_GOVERNS`",
        f"- Selected terminal lane: `{result.get('selected_strategy_lane')}`",
        f"- Repair blocked: `{result.get('repair_blocked')}`",
        f"- Blocked reason source: `{result.get('blocked_reason_source')}`",
        f"- Selected recommendation: `{result.get('selected_recommendation')}`",
        f"- CTA proof product-driving: `{dict(result.get('cta_intent_proof') or {}).get('product_driving')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- `{name}`: `{value}`" for name, value in checks.items())
    lines.extend(
        [
            "",
            "## Publication Interpretation",
            "",
            "This is the contract-backed shape the live card should publish when bending repair is exhausted: "
            "`BENDING_FAIL_GOVERNS`, blocked/exhausted evidence, and no executor-backed Apply CTA. "
            "It must not fall through to `family_selection_contract_mismatch`.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    runtime = run_bending_fail_governs_ladder_runtime(
        base_state={"family_id": "BENDING_FAIL_GOVERNS", "bending_utilisation": 1.42, "shear_utilisation": 0.82},
        evaluate_candidate=_evaluation,
        lane_candidate_updates=_lane_updates(),
    )
    result = runtime.to_dict()
    contract_publication = _contract_publication_requirements()
    blocked_proof = dict((result.get("repair_reason_proof") or {}).get("blocked_ownership_proof") or {})
    cta = dict(result.get("cta_intent_proof") or {})
    checks = {
        "selected_terminal_lane_no_valid_strategy": result.get("selected_strategy_lane") == "NO_VALID_STRATEGY",
        "selected_recommendation_absent": result.get("selected_recommendation") is None,
        "repair_blocked_true": result.get("repair_blocked") is True,
        "terminal_status_repair_blocked": result.get("terminal_status") == "REPAIR_BLOCKED",
        "blocked_reason_source_family_contract": result.get("blocked_reason_source") == "family_contract_blocker_proof",
        "contract_strategy_exhaustion_proven": result.get("contract_strategy_exhaustion_proven") is True,
        "no_internal_cap_only": result.get("internal_cap_only") is False,
        "all_non_terminal_lanes_checked": tuple(result.get("contract_strategies_checked") or ()) == tuple(NON_TERMINAL_LANES),
        "no_remaining_strategy_lanes": list(result.get("contract_strategies_remaining") or []) == [],
        "blocked_ownership_proof_present": bool(blocked_proof),
        "cta_intent_is_proof_only": cta.get("proof_only") is True and cta.get("product_driving") is False,
        "publication_allows_no_apply_locked": "no_apply_locked" in contract_publication["publication_allowed_cta_states"],
        "contract_blocked_proof_mentions_strategy_exhaustion": any(
            "all contract-permitted BENDING_FAIL_GOVERNS repair strategies exhausted" in str(item)
            for item in contract_publication["valid_repair_blocked_proof"]
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "schema": "bending_fail_governs_no_valid_repair_publication_ownership_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "runtime_result": result,
        "contract_publication": contract_publication,
        "checks": checks,
        "failures": failures,
        "next_safe_slice": (
            "Wire final publication fallback for active BENDING_FAIL_GOVERNS no-valid-repair evidence so it "
            "publishes blocked/no-apply proof instead of family_selection_contract_mismatch."
            if not failures
            else "Fix runtime/contract proof before any publication behavior change."
        ),
    }
    json_path = ARTIFACT_DIR / f"bending_fail_governs_no_valid_repair_publication_ownership_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_no_valid_repair_publication_ownership_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "artifact": str(json_path),
                "report": str(report_path),
                "next_safe_slice": payload["next_safe_slice"],
            },
            indent=2,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
