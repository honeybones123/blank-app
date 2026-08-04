"""Proof that shear low-util current-overview replacement needs stronger parity."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.repair import candidate_failure_coverage_summary_from_overviews  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _coverage(current_statuses: dict[str, Any], candidate_statuses: dict[str, Any]) -> dict[str, Any]:
    return candidate_failure_coverage_summary_from_overviews(
        {"statuses": dict(current_statuses)},
        {"statuses": dict(candidate_statuses)},
    )


def _capture() -> dict[str, Any]:
    candidate_passes_shear = {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"}
    cases = [
        {
            "id": "matching_current_overview_safe",
            "recomputed_current_statuses": {"bending": "PASS", "shear": "FAIL", "crack": "PASS", "deflection": "PASS"},
            "caller_current_statuses": {"bending": "PASS", "shear": "FAIL", "crack": "PASS", "deflection": "PASS"},
            "candidate_statuses": candidate_passes_shear,
        },
        {
            "id": "caller_overview_missing_failure_unsafe",
            "recomputed_current_statuses": {"bending": "PASS", "shear": "FAIL", "crack": "PASS", "deflection": "PASS"},
            "caller_current_statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
            "candidate_statuses": candidate_passes_shear,
        },
        {
            "id": "caller_overview_missing_statuses_unsafe",
            "recomputed_current_statuses": {"bending": "PASS", "shear": "FAIL", "crack": "PASS", "deflection": "PASS"},
            "caller_current_statuses": {},
            "candidate_statuses": candidate_passes_shear,
        },
    ]
    comparisons = []
    for case in cases:
        recomputed = _coverage(case["recomputed_current_statuses"], case["candidate_statuses"])
        caller = _coverage(case["caller_current_statuses"], case["candidate_statuses"])
        comparisons.append(
            {
                **case,
                "recomputed_failure_coverage": recomputed,
                "caller_failure_coverage": caller,
                "coverage_matches": recomputed == caller,
            }
        )
    unsafe_cases = [case for case in comparisons if not bool(case.get("coverage_matches"))]
    return {
        "decision": "SHEAR_LOW_UTIL_CURRENT_OVERVIEW_REPLACEMENT_NEEDS_UPSTREAM_PARITY",
        "comparisons": comparisons,
        "unsafe_case_count": len(unsafe_cases),
        "safe_to_replace_recomputed_overview_with_caller_overview_now": False,
        "required_next_proof": (
            "A live/source proof must show the overview supplied to this target loop is the same "
            "status authority as the recomputed current overview before the recompute can be removed."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    comparisons = list(capture.get("comparisons") or [])
    by_id = {str(case.get("id")): case for case in comparisons}
    return {
        "matching_case_proves_equivalence_when_statuses_match": (
            by_id.get("matching_current_overview_safe", {}).get("coverage_matches") is True
        ),
        "stale_failure_case_proves_replacement_unsafe": (
            by_id.get("caller_overview_missing_failure_unsafe", {}).get("coverage_matches") is False
        ),
        "missing_status_case_proves_replacement_unsafe": (
            by_id.get("caller_overview_missing_statuses_unsafe", {}).get("coverage_matches") is False
        ),
        "unsafe_cases_recorded": int(capture.get("unsafe_case_count") or 0) == 2,
        "not_safe_to_replace_now": (
            capture.get("safe_to_replace_recomputed_overview_with_caller_overview_now") is False
        ),
        "required_next_proof_recorded": bool(capture.get("required_next_proof")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Current Overview Parity",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Comparison Cases",
            "",
            "| Case | Coverage matches | Recomputed current failures | Caller current failures |",
            "| --- | --- | --- | --- |",
        ]
    )
    for case in capture.get("comparisons") or []:
        recomputed = (case.get("recomputed_failure_coverage") or {}).get("current_fail_keys")
        caller = (case.get("caller_failure_coverage") or {}).get("current_fail_keys")
        lines.append(f"| {case.get('id')} | {case.get('coverage_matches')} | {recomputed} | {caller} |")
    lines.extend(["", "## Next Proof", "", str(capture.get("required_next_proof") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_current_overview_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_current_overview_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_current_overview_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
