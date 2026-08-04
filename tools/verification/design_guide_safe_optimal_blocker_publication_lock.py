"""Verify safe optimal blockers publish green, not red blocked.

This lock proves the Design Brain publication layer distinguishes:

* safe designs outside the ideal target band with family-owned exact-stop
  blockers, which publish as green optimal/no-action cards, and
* unsafe/failing states, which must not be hidden as optimal.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.family_optimal_blockers import family_optimal_blocker_contract  # noqa: E402
from design_brain.final_publication import build_final_design_guide_publication  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _case_safe_bending_ast_min() -> dict[str, Any]:
    item = {
        "title": "Design is efficient - no further safe cleanup available",
        "summary_line": "All checks pass; bending remains below target because minimum reinforcement governs.",
        "status": "PASS",
        "badge": "PASS",
        "bucket": "pass",
        "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
        "candidate_search_evidence": {
            "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "outside_target_band_allowed_reason": (
                "As_min governs after bottom-reinforcement reduction, width/depth relief, "
                "and restarted reo arrangement search were exhausted."
            ),
            "blocker_reasons_by_family": {
                "BENDING_OVERDESIGN_GOVERNS": "As_min governs; no smaller safe reo or geometry relief remains."
            },
            "all_checks_pass": True,
        },
        "exact_stop_proof": {
            "exact_stop_proven": True,
            "target_band_search_exhaustive": True,
            "family_id": "BENDING_OVERDESIGN_GOVERNS",
        },
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "disabled_reason": "exact_stop_proven",
        },
    }
    publication = build_final_design_guide_publication(item=item)
    proof = publication.evidence.optimal_blocker_proof
    return {
        "case": "safe_bending_ast_min_exact_stop",
        "publication": publication.to_dict(),
        "passed": (
            publication.outcome_state == "PASS"
            and publication.display.status == "PASS"
            and publication.display.colour_state == "pass"
            and publication.cta.enabled is False
            and bool(proof.get("safe_optimal_no_action"))
            and "AST_MIN_GOVERNS" in set(proof.get("family_blocker_codes") or [])
            and bool(publication.display.blocker_explanation)
        ),
    }


def _case_safe_bending_ku() -> dict[str, Any]:
    item = {
        "title": "Design is optimal",
        "summary_line": "All checks pass; ductility limits prevent further safe cleanup.",
        "status": "GOOD",
        "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
        "candidate_search_evidence": {
            "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
            "cleanup_search_exhaustive": True,
            "outside_target_band_allowed_reason": (
                "k_u / ductility governs after reo reduction and geometry rescue were exhausted."
            ),
            "all_checks_pass": True,
        },
        "exact_stop_proof": {
            "exact_stop_proven": True,
            "search_exhaustive": True,
        },
        "button_contract": {"enabled": False, "actionable": False},
    }
    publication = build_final_design_guide_publication(item=item)
    proof = publication.evidence.optimal_blocker_proof
    return {
        "case": "safe_bending_ku_exact_stop",
        "publication": publication.to_dict(),
        "passed": (
            publication.outcome_state == "PASS"
            and publication.display.status == "PASS"
            and "KU_GOVERNS_AFTER_REO_AND_GEOMETRY_EXHAUSTED"
            in set(proof.get("family_blocker_codes") or [])
        ),
    }


def _case_unsafe_bending_failure_not_promoted() -> dict[str, Any]:
    item = {
        "title": "Bending capacity is low",
        "summary_line": "Active strength capacity is failing.",
        "status": "FAIL",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "candidate_search_evidence": {
            "selected_family_id": "BENDING_FAIL_GOVERNS",
            "active_under_capacity_blocker_reason": "Geometry locked and bending repair is still failing.",
            "active_failures": ["bending"],
        },
        "button_contract": {"enabled": False, "actionable": False, "disabled_reason": "locked_geometry"},
    }
    publication = build_final_design_guide_publication(item=item)
    proof = publication.evidence.optimal_blocker_proof
    return {
        "case": "unsafe_bending_failure_not_promoted",
        "publication": publication.to_dict(),
        "passed": (
            publication.outcome_state != "PASS"
            and not bool(proof.get("safe_optimal_no_action"))
        ),
    }


def _case_target_band_reached() -> dict[str, Any]:
    item = {
        "title": "Design accepted - target band achieved",
        "summary_line": "The current design is accepted.",
        "status": "PASS",
        "selected_family_id": "TARGET_BAND_REACHED",
        "candidate_search_evidence": {
            "selected_family_id": "TARGET_BAND_REACHED",
            "all_checks_pass": True,
        },
        "target_band_proof": {"target_band_reached": True, "utilisation": 0.91},
        "button_contract": {"enabled": False, "actionable": False},
    }
    publication = build_final_design_guide_publication(item=item)
    proof = publication.evidence.optimal_blocker_proof
    return {
        "case": "target_band_reached_no_button",
        "publication": publication.to_dict(),
        "passed": (
            publication.outcome_state == "PASS"
            and publication.display.status == "PASS"
            and bool(proof.get("safe_optimal_no_action"))
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Safe Optimal Blocker Publication Lock",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Cases",
        "",
        "| Case | Passed | Outcome | Display | Safe optimal proof |",
        "| --- | ---: | --- | --- | ---: |",
    ]
    for row in payload["cases"]:
        publication = row["publication"]
        proof = (((publication.get("evidence") or {}).get("optimal_blocker_proof")) or {})
        lines.append(
            "| `{case}` | `{passed}` | `{outcome}` | `{display}` | `{safe}` |".format(
                case=row["case"],
                passed=row["passed"],
                outcome=publication.get("outcome_state"),
                display=(publication.get("display") or {}).get("status"),
                safe=proof.get("safe_optimal_no_action"),
            )
        )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in payload["failures"]] or ["- none"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    cases = [
        _case_safe_bending_ast_min(),
        _case_safe_bending_ku(),
        _case_unsafe_bending_failure_not_promoted(),
        _case_target_band_reached(),
    ]
    contract = family_optimal_blocker_contract()
    failures = [row["case"] for row in cases if not row["passed"]]
    for family in ("BENDING_OVERDESIGN_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS", "COMBINED_OVERDESIGN_GOVERNS"):
        if family not in contract["families"]:
            failures.append(f"missing_family_optimal_blocker_taxonomy:{family}")
    payload = {
        "schema": "design_guide.safe_optimal_blocker_publication_lock.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "contract": contract,
        "cases": cases,
        "failures": failures,
        "product_behaviour_changed": True,
        "behaviour_change": (
            "Safe exact-stop/no-action states with family-owned blocker evidence publish green optimal "
            "instead of red blocked."
        ),
    }
    stamp = _stamp()
    artifact = ARTIFACT_DIR / f"design_guide_safe_optimal_blocker_publication_lock_{stamp}.json"
    report = AUDIT_DIR / f"design_guide_safe_optimal_blocker_publication_lock_{stamp}.md"
    payload["artifact"] = str(artifact)
    payload["report"] = str(report)
    artifact.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report)
    print(f"design_guide_safe_optimal_blocker_publication_lock {payload['status']}")
    print(f"artifact={artifact}")
    print(f"report={report}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
