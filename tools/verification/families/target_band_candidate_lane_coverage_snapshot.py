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
CONTRACT_ROOT = ROOT / "design_brain" / "families"


def _flatten_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str).lower()


def _family_id(contract: dict[str, Any]) -> str:
    identity = contract.get("family_identity") or {}
    return str(identity.get("family_id") or contract.get("family_id") or "")


def _has_target_band_language(contract: dict[str, Any]) -> bool:
    target = contract.get("target_band")
    return isinstance(target, dict) and bool(target)


def _has_explicit_target_candidate_lane(contract: dict[str, Any]) -> bool:
    target = contract.get("target_band") or {}
    source = contract.get("candidate_source_contract") or {}
    policies = contract.get("lane_proof_policies") or {}
    text = _flatten_text(contract)
    return bool(
        (isinstance(target, dict) and target.get("candidate_lane"))
        or (isinstance(source, dict) and source.get("target_band_refinement_lane"))
        or (isinstance(policies, dict) and policies.get("target_band_refinement"))
        or "target-band refinement" in text
    )


def _has_candidate_generation_surface(contract: dict[str, Any]) -> bool:
    text = _flatten_text(contract)
    return bool(
        contract.get("strategy_ladder")
        or contract.get("repair_ladder")
        or contract.get("candidate_source_contract")
        or "candidate generation" in text
        or "candidate repairs" in text
        or "candidate_repairs" in text
    )


def _has_fallback_proof_language(contract: dict[str, Any]) -> bool:
    text = _flatten_text(contract)
    return "fallback" in text and ("specific blocker" in text or "specific reason" in text or "blocker evidence" in text)


def _classify(contract_path: Path) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    family_id = _family_id(contract)
    has_target = _has_target_band_language(contract)
    has_explicit_lane = _has_explicit_target_candidate_lane(contract)
    has_candidate_surface = _has_candidate_generation_surface(contract)
    has_fallback_proof = _has_fallback_proof_language(contract)
    source = contract.get("candidate_source_contract") or {}
    merge_family = isinstance(source, dict) and source.get("must_not_duplicate_ladders") is True
    review_needed = bool(has_target and merge_family and not has_explicit_lane)
    if not has_target:
        classification = "NO_TARGET_BAND_CONTRACT"
    elif has_explicit_lane:
        classification = "EXPLICIT_TARGET_BAND_CANDIDATE_LANE_PRESENT"
    elif has_candidate_surface and has_fallback_proof:
        classification = "TARGET_BAND_RANKING_WITH_FALLBACK_PROOF_REVIEW"
    elif has_candidate_surface:
        classification = "TARGET_BAND_CANDIDATE_SURFACE_REVIEW"
    else:
        classification = "TARGET_BAND_NO_CANDIDATE_SURFACE_REVIEW"
    return {
        "family_id": family_id,
        "contract": str(contract_path.relative_to(ROOT)),
        "has_target_band_contract": has_target,
        "has_explicit_target_candidate_lane": has_explicit_lane,
        "has_candidate_generation_surface": has_candidate_surface,
        "has_fallback_proof_language": has_fallback_proof,
        "merge_family_without_ladder_duplication": merge_family,
        "review_needed": review_needed,
        "classification": classification,
        "target_band": contract.get("target_band") if isinstance(contract.get("target_band"), dict) else None,
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    rows = payload.get("families") or []
    lines = [
        "# Target-Band Candidate Lane Coverage Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Summary",
        "",
        f"- contracts scanned: `{payload.get('contracts_scanned')}`",
        f"- explicit target-band lanes: `{payload.get('explicit_lane_count')}`",
        f"- review-needed families: `{payload.get('review_needed_count')}`",
        "",
        "## Family Coverage",
        "",
        "| Family | Classification | Explicit lane | Review needed |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {family} | {classification} | {lane} | {review} |".format(
                family=row.get("family_id"),
                classification=row.get("classification"),
                lane=row.get("has_explicit_target_candidate_lane"),
                review=row.get("review_needed"),
            )
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This is an audit snapshot only; it does not alter product behavior.",
            "- A review-needed result means the contract has target-band/fallback language on a merge family but no explicit target-band candidate/refinement lane yet.",
            "",
            f"Output: `{payload.get('artifact')}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    rows = sorted((_classify(path) for path in CONTRACT_ROOT.rglob("contract.json")), key=lambda row: row["family_id"])
    review_rows = [row for row in rows if row.get("review_needed")]
    explicit_rows = [row for row in rows if row.get("has_explicit_target_candidate_lane")]
    status = "PASS_WITH_REVIEW" if review_rows else "PASS"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"target_band_candidate_lane_coverage_{stamp}.json"
    report_path = AUDIT_DIR / f"target_band_candidate_lane_coverage_{stamp}.md"
    payload = {
        "schema": "target_band_candidate_lane_coverage_snapshot.v1",
        "status": status,
        "contracts_scanned": len(rows),
        "explicit_lane_count": len(explicit_rows),
        "review_needed_count": len(review_rows),
        "review_needed_families": [row["family_id"] for row in review_rows],
        "families": rows,
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
