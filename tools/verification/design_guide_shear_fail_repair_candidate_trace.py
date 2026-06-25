"""Proof-only trace that SHEAR_FAIL_GOVERNS candidates are evaluated by the app path.

The purpose is to catch the blocked-card failure mode where shear-only repair
is incorrectly published as blocked even though the locked family ladder can
provide executor-backed candidates.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _state(
    vstar: float,
    *,
    b: float = 300.0,
    d: float = 600.0,
    mstar: float = 90.0,
    lig_d: int = 10,
    lig_legs: int = 2,
    s_lig: float = 200.0,
) -> dict[str, Any]:
    return {
        "b": float(b),
        "D": float(d),
        "L": 6000.0,
        "fc": 40.0,
        "fsy": 500.0,
        "uls_Mstar": float(mstar),
        "uls_Vstar": float(vstar),
        "Vu_star": float(vstar),
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": int(lig_d),
        "lig_legs": int(lig_legs),
        "s_lig": float(s_lig),
    }


def _overview(vstar: float) -> dict[str, Any]:
    shear_util = max(float(vstar) / 100.0, 1.01)
    return {
        "statuses": {"bending": "PASS", "shear": "FAIL", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.82, "shear": shear_util, "crack": 0.42, "deflection": 0.39},
        "any_fail": True,
        "all_key_pass": False,
        "worst_util": shear_util,
        "governing_util": shear_util,
    }


def _summarise_item(item: dict[str, Any] | None, *, vstar: float) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"vstar": vstar, "item_returned": False}
    evidence = dict(item.get("candidate_search_evidence") or {})
    rows = [
        dict(row)
        for row in list(evidence.get("active_fail_repair_candidate_rows") or evidence.get("candidate_rows") or [])
        if isinstance(row, dict)
    ]
    safe_rows = [
        row
        for row in rows
        if bool(row.get("safe_executor_backed") or row.get("preview_pass") or row.get("is_executable"))
    ]
    return {
        "vstar": vstar,
        "item_returned": True,
        "title": item.get("title_main") or item.get("title"),
        "action_type": item.get("action_type"),
        "updates": dict(item.get("updates") or {}),
        "selected_family_id": item.get("selected_family_id"),
        "governing_family": evidence.get("governing_family"),
        "shear_fail_contract_ladder_attempted": bool(evidence.get("shear_fail_contract_ladder_attempted")),
        "shear_fail_contract_ladder_used": bool(evidence.get("shear_fail_contract_ladder_used")),
        "shear_fail_contract_ladder_candidate_count": evidence.get("shear_fail_contract_ladder_candidate_count"),
        "total_candidates_considered": evidence.get("total_candidates_considered"),
        "safe_candidate_count": evidence.get("safe_candidate_count"),
        "safe_executor_backed_candidates_count": evidence.get("safe_executor_backed_candidates_count"),
        "target_band_candidate_count": evidence.get("target_band_candidate_count"),
        "selected_candidate_id": evidence.get("selected_candidate_id"),
        "selected_candidate_updates": dict(evidence.get("selected_candidate_updates") or {}),
        "outside_target_band_allowed": evidence.get("outside_target_band_allowed"),
        "outside_target_band_allowed_reason": evidence.get("outside_target_band_allowed_reason"),
        "active_under_capacity_blocker": bool(evidence.get("active_under_capacity_blocker")),
        "active_under_capacity_blocker_reason": evidence.get("active_under_capacity_blocker_reason"),
        "safe_row_count": len(safe_rows),
        "safe_row_samples": [
            {
                "candidate_id": row.get("candidate_id"),
                "updates": dict(row.get("updates") or row.get("proposed_updates") or {}),
                "preview_util": row.get("preview_util"),
                "safe_executor_backed": row.get("safe_executor_backed"),
                "preview_pass": row.get("preview_pass"),
            }
            for row in safe_rows[:5]
        ],
    }


def _run_cases() -> list[dict[str, Any]]:
    import importlib

    inputs_page = importlib.import_module("inputs_page")
    inputs_page.get_rerun_pure_cache = lambda *args, **kwargs: None
    inputs_page.set_rerun_pure_cache = lambda *args, **kwargs: None
    rows: list[dict[str, Any]] = []
    cases = [
        {"vstar": 100.0},
        {"vstar": 220.0},
        {"vstar": 600.0},
        {
            "vstar": 700.0,
            "b": 400.0,
            "d": 700.0,
            "mstar": 110.0,
            "lig_d": 12,
            "lig_legs": 2,
            "s_lig": 200.0,
        },
        {"vstar": 1000.0},
    ]
    for case in cases:
        vstar = float(case["vstar"])
        state_kwargs = {key: value for key, value in case.items() if key != "vstar"}
        item = inputs_page._active_fail_near_current_repair_item(
            _state(vstar, **state_kwargs),
            _overview(vstar),
            {"shear"},
        )
        summary = _summarise_item(item, vstar=vstar)
        summary["state_case"] = dict(case)
        rows.append(summary)
    return rows


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# SHEAR_FAIL_GOVERNS Repair Candidate Trace",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Cases",
        "",
        "| Vstar | Title | Action | Updates | Safe Rows | Blocker |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["cases"]:
        lines.append(
            "| {vstar} | {title} | {action} | `{updates}` | {safe} | {blocker} |".format(
                vstar=row.get("vstar"),
                title=row.get("title"),
                action=row.get("action_type"),
                updates=row.get("updates"),
                safe=row.get("safe_row_count"),
                blocker=row.get("active_under_capacity_blocker"),
            )
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            payload["conclusion"],
            "",
            "## Output",
            "",
            f"- `{payload['artifact']}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_guide_shear_fail_repair_candidate_trace_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_fail_repair_candidate_trace_{stamp}.md"
    cases = _run_cases()
    all_attempted_family_ladder = all(row.get("shear_fail_contract_ladder_attempted") for row in cases)
    all_have_actions = all(row.get("action_type") == "apply_resolved_candidate" for row in cases)
    no_blockers = all(not row.get("active_under_capacity_blocker") for row in cases)
    all_have_updates = all(bool(row.get("updates")) for row in cases)
    status = "PASS" if all_attempted_family_ladder and all_have_actions and no_blockers and all_have_updates else "FAIL"
    payload = {
        "schema": "design_guide_shear_fail_repair_candidate_trace.v1",
        "status": status,
        "checks": {
            "all_attempted_family_ladder": all_attempted_family_ladder,
            "all_have_executor_backed_actions": all_have_actions,
            "no_case_published_active_under_capacity_blocker": no_blockers,
            "all_have_updates": all_have_updates,
        },
        "cases": cases,
        "conclusion": (
            "The shear-only app path reaches the locked SHEAR_FAIL_GOVERNS ladder and finds executor-backed "
            "repair candidates for the covered shear-fail fixtures. A blocked shear card in this path should "
            "therefore be investigated as a publication/blocker-materialization regression or as a different "
            "post-click/final-threshold state, not as absence of shear family candidates."
            if status == "PASS"
            else "At least one covered shear-fail fixture did not produce an executor-backed family-ladder repair."
        ),
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
