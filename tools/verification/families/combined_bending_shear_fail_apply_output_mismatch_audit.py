"""Audit live apply-output mismatch for COMBINED_BENDING_SHEAR_FAIL.

This verifier is intentionally diagnostic. It consumes the latest browser/live
10-fuzz artifact for the combined bending/shear fail family and classifies
whether the failure is in publication/CTA/apply binding or in the family
candidate preview/evaluation contract.
"""

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
REPORT_DIR = ROOT / "artifacts" / "reports" / "family_fuzz"
FAMILY_ID = "COMBINED_BENDING_SHEAR_FAIL"
KNOWN_ERRORS_PATH = ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "known_errors.json"


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    if number is None:
        return None
    try:
        return int(round(number))
    except (TypeError, ValueError):
        return None


def _expected_bottom_from_updates(updates: dict[str, Any]) -> dict[str, Any]:
    count_1 = _as_int(updates.get("bot_row_1_bars"))
    dia_1 = _as_int(updates.get("bot_row_1_dia"))
    count_2 = _as_int(updates.get("bot_row_2_bars")) or 0
    dia_2 = _as_int(updates.get("bot_row_2_dia")) or dia_1
    authority = "canonical"
    if count_1 is None or dia_1 is None:
        count_1 = _as_int(updates.get("bot1_count"))
        dia_1 = _as_int(updates.get("db_bot_1"))
        count_2 = _as_int(updates.get("bot2_count")) or 0
        dia_2 = _as_int(updates.get("db_bot_2")) or dia_1
        authority = "legacy"
    if count_1 is None or dia_1 is None:
        return {}
    ast = float(count_1) * 3.141592653589793 * float(dia_1) ** 2 / 4.0
    if count_2 and dia_2:
        ast += float(count_2) * 3.141592653589793 * float(dia_2) ** 2 / 4.0
    label = f"{int(count_1)}N{int(dia_1)}"
    if count_2:
        label += f" + {int(count_2)}N{int(dia_2 or dia_1)}"
    return {
        "authority": authority,
        "expected_bottom_label": label,
        "expected_Ast_bot": round(ast, 6),
    }


def _find_latest_family_audit() -> tuple[Path | None, dict[str, Any]]:
    candidates = sorted(
        ARTIFACT_DIR.glob("family_10_fuzz_audit_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for family in _safe_list(payload.get("families")):
            family_row = _safe_dict(family)
            if family_row.get("family") == FAMILY_ID:
                return path, family_row
    return None, {}


def _row_summary(row: dict[str, Any]) -> dict[str, Any]:
    run_data = _safe_dict(_safe_dict(row.get("run_end_event")).get("data"))
    binding = _safe_dict(run_data.get("primary_payload_binding_audit"))
    route = _safe_dict(run_data.get("last_apply_route"))
    compare = _safe_dict(run_data.get("compare"))
    compact = _safe_dict(run_data.get("current_shared_compact"))
    final_util = _as_float(run_data.get("final_live_worst_util"))
    expected_util = _as_float(route.get("expected_post_util"))
    applied_updates = _safe_dict(binding.get("applied_updates"))
    expected_bottom = _expected_bottom_from_updates(applied_updates)
    compact_ast = _as_float(compact.get("Ast_bot"))
    expected_ast = _as_float(expected_bottom.get("expected_Ast_bot"))
    compact_label = str(compact.get("bottom_label") or "")
    expected_label = str(expected_bottom.get("expected_bottom_label") or "")
    bottom_update_present = bool(expected_bottom)
    bottom_reflected = bool(
        bottom_update_present
        and expected_label
        and compact_label == expected_label
        and compact_ast is not None
        and expected_ast is not None
        and abs(float(compact_ast) - float(expected_ast)) <= 1.0
    )
    return {
        "scenario_id": row.get("scenario_id"),
        "failures": _safe_list(row.get("failures")),
        "button_clicked": bool(_safe_dict(row.get("click_result")).get("clicked")),
        "button_text": _safe_dict(row.get("click_result")).get("button_text"),
        "run_status": run_data.get("status"),
        "stop_reason": run_data.get("stop_reason"),
        "all_key_pass": run_data.get("all_key_pass"),
        "post_commit_live_statuses": _safe_dict(run_data.get("post_commit_live_statuses")),
        "final_live_worst_util": final_util,
        "expected_post_util": expected_util,
        "expected_actual_gap": (
            round(final_util - expected_util, 6)
            if final_util is not None and expected_util is not None
            else None
        ),
        "resolved_candidate_label": route.get("resolved_candidate_label"),
        "resolved_candidate_action_type": route.get("resolved_candidate_action_type"),
        "apply_used_resolved_candidate_payload": route.get("apply_used_resolved_candidate_payload"),
        "apply_fell_back_to_generic_solver": route.get("apply_fell_back_to_generic_solver"),
        "payload_binding_match": binding.get("payload_binding_match"),
        "payload_update_match": binding.get("payload_update_match"),
        "queued_apply_updates": _safe_dict(binding.get("queued_apply_updates")),
        "applied_updates": applied_updates,
        "applied_changed_keys": _safe_list(binding.get("applied_changed_keys")),
        "actual_changed_updates": _safe_dict(binding.get("actual_changed_updates")),
        "current_shared_compact": compact,
        "bottom_reo_update_present": bottom_update_present,
        "expected_bottom_after_update": expected_bottom,
        "expected_bottom_authority": expected_bottom.get("authority"),
        "final_bottom_label": compact_label,
        "final_Ast_bot": compact_ast,
        "bottom_reo_update_reflected_in_final_compact": bottom_reflected,
        "compare_starting_worst_util": compare.get("starting_worst_util"),
        "compare_ending_worst_util": compare.get("ending_worst_util"),
    }


def _classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    failed = [row for row in rows if row.get("failures")]
    clicked = all(row.get("button_clicked") for row in rows) if rows else False
    payload_binding_ok = all(row.get("payload_binding_match") is True for row in rows) if rows else False
    payload_update_ok = all(row.get("payload_update_match") is True for row in rows) if rows else False
    direct_payload_used = all(row.get("apply_used_resolved_candidate_payload") is True for row in rows) if rows else False
    generic_solver_not_used = all(row.get("apply_fell_back_to_generic_solver") is False for row in rows) if rows else False
    expected_safe = all(
        (row.get("expected_post_util") is not None and float(row["expected_post_util"]) <= 1.0)
        for row in rows
    ) if rows else False
    actual_safe = all(
        row.get("all_key_pass") is True
        and row.get("final_live_worst_util") is not None
        and float(row["final_live_worst_util"]) <= 1.0
        for row in rows
    ) if rows else False
    bending_still_fails = all(
        _safe_dict(row.get("post_commit_live_statuses")).get("bending") == "FAIL"
        for row in rows
    ) if rows else False
    shear_repaired = all(
        _safe_dict(row.get("post_commit_live_statuses")).get("shear") == "PASS"
        for row in rows
    ) if rows else False
    same_updates = all(row.get("queued_apply_updates") == row.get("applied_updates") for row in rows) if rows else False
    bottom_update_present = all(row.get("bottom_reo_update_present") for row in rows) if rows else False
    bottom_update_reflected = all(
        row.get("bottom_reo_update_reflected_in_final_compact") is True
        for row in rows
    ) if rows else False

    if failed and clicked and payload_binding_ok and payload_update_ok and direct_payload_used and bottom_update_present and not bottom_update_reflected:
        root = "APPLY_DERIVED_BOTTOM_REO_PROPAGATION_MISMATCH"
    elif failed and clicked and payload_binding_ok and payload_update_ok and direct_payload_used:
        root = "FAMILY_PREVIEW_OR_CANDIDATE_VALIDATION_MISMATCH"
    elif failed and not clicked:
        root = "CTA_NOT_CLICKABLE_OR_MISSING"
    elif failed and not payload_binding_ok:
        root = "CTA_PAYLOAD_BINDING_MISMATCH"
    elif failed and not payload_update_ok:
        root = "APPLY_UPDATE_MISMATCH"
    else:
        root = "NO_LIVE_APPLY_FAILURE_FOUND" if actual_safe else "UNCLASSIFIED"

    blockers = []
    if failed:
        blockers.append("combined family live apply is not lockable")
    if expected_safe and not actual_safe:
        blockers.append("family expected post-utilisation does not match real post-Apply recompute")
    if bending_still_fails and shear_repaired:
        blockers.append("combined repair fixes shear but leaves bending failing")
    if bottom_update_present and not bottom_update_reflected:
        blockers.append("bending reinforcement update is queued/applied but final compact bottom reinforcement does not reflect it")

    return {
        "scenario_count": total,
        "failed_count": len(failed),
        "clicked_all": clicked,
        "payload_binding_match_all": payload_binding_ok,
        "payload_update_match_all": payload_update_ok,
        "direct_resolved_payload_used_all": direct_payload_used,
        "generic_solver_not_used_all": generic_solver_not_used,
        "queued_updates_equal_applied_updates_all": same_updates,
        "bottom_reo_update_present_all": bottom_update_present,
        "bottom_reo_update_reflected_in_final_compact_all": bottom_update_reflected,
        "expected_safe_all": expected_safe,
        "actual_safe_all": actual_safe,
        "bending_still_fails_all": bending_still_fails,
        "shear_repaired_all": shear_repaired,
        "root_classification": root,
        "blocking_defects": blockers,
        "family_lock_status": "NOT_LOCKED_FAIL" if blockers else "LIVE_LOCK_READY",
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_bending_shear_fail_apply_output_mismatch_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_fail_apply_output_mismatch_audit_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cls = snapshot["classification"]
    sample = snapshot.get("sample_failure") or {}
    report_lines = [
        "# COMBINED_BENDING_SHEAR_FAIL Apply Output Mismatch Audit",
        "",
        f"Audit result: `{snapshot['result']}`",
        f"Family lock status: `{cls['family_lock_status']}`",
        "",
        "## Source Artifact",
        "",
        f"- `{snapshot.get('source_artifact')}`",
        "",
        "## Classification",
        "",
        f"- root: `{cls['root_classification']}`",
        f"- scenarios checked: `{cls['scenario_count']}`",
        f"- failed scenarios: `{cls['failed_count']}`",
        f"- clicked all: `{cls['clicked_all']}`",
        f"- payload binding match all: `{cls['payload_binding_match_all']}`",
        f"- payload update match all: `{cls['payload_update_match_all']}`",
        f"- expected safe all: `{cls['expected_safe_all']}`",
        f"- actual safe all: `{cls['actual_safe_all']}`",
        f"- bottom reo update present all: `{cls['bottom_reo_update_present_all']}`",
        f"- bottom reo update reflected all: `{cls['bottom_reo_update_reflected_in_final_compact_all']}`",
        f"- bending still fails all: `{cls['bending_still_fails_all']}`",
        f"- shear repaired all: `{cls['shear_repaired_all']}`",
        "",
        "## Blocking Defects",
        "",
        *([f"- {defect}" for defect in cls["blocking_defects"]] or ["- none"]),
        "",
        "## Known Error Register",
        "",
        f"- `CBSF-001` recorded: `{snapshot.get('known_error_recorded')}`",
        f"- register: `{KNOWN_ERRORS_PATH}`",
        "",
        "## Sample Failure",
        "",
        f"- scenario: `{sample.get('scenario_id')}`",
        f"- button: `{sample.get('button_text')}`",
        f"- resolved candidate: `{sample.get('resolved_candidate_label')}`",
        f"- expected post-utilisation: `{sample.get('expected_post_util')}`",
        f"- final live worst utilisation: `{sample.get('final_live_worst_util')}`",
        f"- expected/actual gap: `{sample.get('expected_actual_gap')}`",
        f"- final statuses: `{sample.get('post_commit_live_statuses')}`",
        f"- expected bottom after update: `{sample.get('expected_bottom_after_update')}`",
        f"- expected bottom authority: `{sample.get('expected_bottom_authority')}`",
        f"- final compact bottom label: `{sample.get('final_bottom_label')}`",
        f"- final compact Ast_bot: `{sample.get('final_Ast_bot')}`",
        "",
        "## Next Safe Target",
        "",
        (
            "Add/fix family regression `CBSF-001` around resolved bottom-reinforcement update propagation: "
            "the combined family candidate must either publish calculation-consumed bottom reinforcement keys "
            "or the Apply boundary must canonicalize them before recompute. Then rerun live 10-fuzz."
        ),
        "",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    source_path, family = _find_latest_family_audit()
    rows = [_row_summary(_safe_dict(row)) for row in _safe_list(_safe_dict(family.get("live_execution")).get("rows"))]
    classification = _classify(rows)
    known_errors = _safe_dict(json.loads(KNOWN_ERRORS_PATH.read_text(encoding="utf-8"))) if KNOWN_ERRORS_PATH.exists() else {}
    known_error_recorded = any(
        _safe_dict(entry).get("id") == "CBSF-001"
        and _safe_dict(entry).get("status") == "open"
        and _safe_dict(entry).get("locked") is False
        for entry in _safe_list(known_errors.get("entries"))
    )
    snapshot = {
        "schema": "combined_bending_shear_fail_apply_output_mismatch_audit.v1",
        "result": "PASS" if source_path and rows else "FAIL",
        "source_artifact": str(source_path) if source_path else None,
        "family": FAMILY_ID,
        "classification": classification,
        "known_error_recorded": known_error_recorded,
        "known_errors_path": str(KNOWN_ERRORS_PATH),
        "sample_failure": next((row for row in rows if row.get("failures")), rows[0] if rows else {}),
        "rows": rows,
        "checks": {
            "latest_family_audit_found": source_path is not None,
            "live_rows_found": bool(rows),
            "audit_identifies_combined_family_blocker": classification["family_lock_status"] == "NOT_LOCKED_FAIL",
            "classification_is_specific": classification["root_classification"]
            in {
                "FAMILY_PREVIEW_OR_CANDIDATE_VALIDATION_MISMATCH",
                "APPLY_DERIVED_BOTTOM_REO_PROPAGATION_MISMATCH",
            },
            "known_error_cbsf_001_recorded_open": known_error_recorded,
        },
    }
    json_path, report_path = _write(snapshot)
    if snapshot["result"] != "PASS":
        print("COMBINED_BENDING_SHEAR_FAIL apply output mismatch audit FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        return 1
    print("COMBINED_BENDING_SHEAR_FAIL apply output mismatch audit PASS")
    print(f"family_lock_status={classification['family_lock_status']}")
    print(f"root_classification={classification['root_classification']}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
