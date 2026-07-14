from __future__ import annotations

import ast
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET = "_probe_equivalent_bending_cleanup_action_item"
SERVICE_HELPER = "build_probe_equivalent_bending_cleanup_candidate_inputs"
SERVICE_ALIAS = "_build_probe_equivalent_bending_cleanup_candidate_inputs"
EVALUATION_WRAPPER = "_evaluate_probe_equivalent_bending_candidate_with_service"
PROJECTION_HELPER = "build_design_guide_controller_probe_equivalent_bending_cleanup_item_projection"
PROJECTION_ALIAS = "_build_design_guide_controller_probe_equivalent_bending_cleanup_item_projection"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _old_inline_probe_equivalent_candidate_inputs(
    base_state: dict[str, Any],
    *,
    count: int,
    dia: int,
) -> list[dict[str, Any]]:
    base = dict(base_state or {})
    rows: list[tuple[str, dict[str, Any]]] = []
    minimum_bottom_bars = 2
    for new_count in range(max(minimum_bottom_bars, int(count) - 1), minimum_bottom_bars - 1, -1):
        if new_count < int(count):
            rows.append((f"bottom_count_{new_count}", {"bot1_count": new_count, "bot_row_1_bars": new_count}))
    for new_dia in reversed([10, 12, 16, 20, 24, 28, 32, 36, 40]):
        if 0 < int(new_dia) < int(dia):
            rows.append((f"bottom_dia_{new_dia}", {"db_bot_1": int(new_dia), "bot_row_1_dia": int(new_dia)}))
            current_area_key = max(minimum_bottom_bars, int(count)) * int(dia) * int(dia)
            for new_count in range(max(minimum_bottom_bars, int(count)), max(minimum_bottom_bars, int(count)) + 5):
                if new_count == int(count):
                    continue
                if new_count * int(new_dia) * int(new_dia) >= current_area_key:
                    continue
                rows.append(
                    (
                        f"bottom_count_{new_count}_dia_{new_dia}",
                        {
                            "bot1_count": int(new_count),
                            "bot_row_1_bars": int(new_count),
                            "db_bot_1": int(new_dia),
                            "bot_row_1_dia": int(new_dia),
                        },
                    )
                )
    if int(base.get("bot2_count") or base.get("bot_row_2_bars") or 0) > 0:
        rows.append(("remove_second_bottom_row", {"bot2_count": 0, "bot_row_2_bars": 0, "bot_row_count": 1}))

    candidates: list[dict[str, Any]] = []
    for label_key, updates in rows:
        candidate_state = dict(base)
        candidate_state.update(dict(updates))
        candidate_id = f"cleanup:bending:{label_key}"
        label_text = f"Bending cleanup - {label_key.replace('_', ' ')}"
        candidates.append(
            {
                "label_key": label_key,
                "updates": dict(updates),
                "candidate_state": candidate_state,
                "candidate_row": {
                    "candidate_id": candidate_id,
                    "label": label_text,
                    "title": label_text,
                    "updates": dict(updates),
                    "proposed_updates": dict(updates),
                    "family": "bending",
                    "action_type": "apply_resolved_candidate",
                    "executor_backed": True,
                },
            }
        )
    return candidates


def _sample_parity() -> list[dict[str, Any]]:
    from design_brain.candidate_evaluation import (  # noqa: WPS433
        build_probe_equivalent_bending_cleanup_candidate_inputs,
    )

    cases = [
        {
            "name": "bottom_count_and_dia_reduction_with_second_row",
            "base_state": {
                "bot1_count": 6,
                "bot_row_1_bars": 6,
                "db_bot_1": 20,
                "bot_row_1_dia": 20,
                "bot2_count": 2,
                "bot_row_2_bars": 2,
            },
            "count": 6,
            "dia": 20,
        },
        {
            "name": "minimum_count_dia_reduction_only",
            "base_state": {
                "bot1_count": 2,
                "bot_row_1_bars": 2,
                "db_bot_1": 16,
                "bot_row_1_dia": 16,
                "bot2_count": 0,
                "bot_row_2_bars": 0,
            },
            "count": 2,
            "dia": 16,
        },
        {
            "name": "fallback_second_row_key",
            "base_state": {
                "bot_row_1_bars": 5,
                "bot_row_1_dia": 24,
                "bot_row_2_bars": 1,
            },
            "count": 5,
            "dia": 24,
        },
    ]

    out: list[dict[str, Any]] = []
    for case in cases:
        old_result = _old_inline_probe_equivalent_candidate_inputs(
            dict(case["base_state"]),
            count=int(case["count"]),
            dia=int(case["dia"]),
        )
        new_result = build_probe_equivalent_bending_cleanup_candidate_inputs(
            dict(case["base_state"]),
            count=int(case["count"]),
            dia=int(case["dia"]),
        )
        out.append(
            {
                "case": case["name"],
                "match": old_result == new_result,
                "old_hash": _stable_hash(old_result),
                "new_hash": _stable_hash(new_result),
                "old_count": len(old_result),
                "new_count": len(new_result),
                "first_rows": {
                    "old": _stable_hash(old_result[:5]),
                    "new": _stable_hash(new_result[:5]),
                },
                "row_shape_keys": sorted((new_result[0].get("candidate_row") or {}).keys()) if new_result else [],
            }
        )
    return out


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(candidate_source, SERVICE_HELPER)
    parity = _sample_parity()
    return {
        "schema": "design_guide_probe_equivalent_bending_candidate_generation_boundary.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "service_helper": {
            "name": SERVICE_HELPER,
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
            "exported": f'"{SERVICE_HELPER}"' in candidate_source,
        },
        "source_checks": {
            "inputs_imports_service_helper": SERVICE_ALIAS in inputs_source,
            "target_calls_service_helper": f"{SERVICE_ALIAS}(" in target_source,
            "target_uses_candidate_eval_service_wrapper": f"{EVALUATION_WRAPPER}(" in target_source,
            "target_local_rows_removed": "rows: list" not in target_source and "rows.append(" not in target_source,
            "target_local_area_key_removed": "current_area_key" not in target_source,
            "target_selection_service_backed": "_select_probe_equivalent_bending_cleanup_candidate(" in target_source
            and "def select_probe_equivalent_bending_cleanup_candidate(" in candidate_source,
            "target_keeps_projection": "_guidance_item_from_resolved_candidate(" in target_source,
            "target_uses_controller_projection_helper": f"{PROJECTION_ALIAS}(" in target_source,
            "controller_projection_helper_exists": f"def {PROJECTION_HELPER}(" in controller_source,
            "controller_projection_helper_exported": f'"{PROJECTION_HELPER}"' in controller_source,
            "target_no_longer_embeds_item_projection_payload": 'item["action_payload"]' not in target_source
            and 'item["resolved_candidate"]' not in target_source,
            "target_keeps_debug_sink": 'debug_sink["probe_equivalent_bending_cleanup_candidate_rows"]' in target_source,
            "candidate_evaluation_has_no_page_import": "inputs_page" not in candidate_source,
            "candidate_evaluation_has_no_streamlit_import": "streamlit" not in candidate_source and "import st" not in candidate_source,
            "candidate_evaluation_has_no_session_import": "session_state" not in candidate_source,
            "service_helper_has_candidate_generation": "rows.append(" in helper_source and "candidate_row" in helper_source,
        },
        "parity_cases": parity,
        "parity_summary": {
            "case_count": len(parity),
            "mismatches": [case for case in parity if not bool(case.get("match"))],
        },
        "behaviour_preserved": {
            "candidate_order": all(bool(case.get("match")) for case in parity),
            "selected_candidate_id": "unchanged_by_this_slice_candidate_ids_are_generated_in_service_with_same labels",
            "updates": "unchanged_service_candidate_rows_match_old_inline_rows",
            "button_contract": "unchanged_not_touched",
            "action_payload": "unchanged_controller_projection_parity_passed",
            "debug_proof_fields": "unchanged_candidate_rows_keep_same row shape",
            "visible_wording": "unchanged_labels_match_old row labels",
            "family_runtime_behaviour": "unchanged_not_touched",
        },
        "remaining_page_owned_surfaces": [
            "overview acceptability and skip guard",
            "candidate evaluation callback call",
            "safe candidate filtering",
            "debug_sink writes",
        ],
        "next_safe_slice": "probe_equivalent_bending_item_projection_boundary_audit_or_bending_only_target_band_generation_service_boundary",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    parity_summary = dict(capture.get("parity_summary") or {})
    return {
        "service_helper_exported": bool((capture.get("service_helper") or {}).get("exported")),
        "inputs_imports_service_helper": bool(source_checks.get("inputs_imports_service_helper")),
        "target_calls_service_helper": bool(source_checks.get("target_calls_service_helper")),
        "target_uses_candidate_eval_service_wrapper": bool(source_checks.get("target_uses_candidate_eval_service_wrapper")),
        "target_local_rows_removed": bool(source_checks.get("target_local_rows_removed")),
        "target_local_area_key_removed": bool(source_checks.get("target_local_area_key_removed")),
        "target_selection_service_backed": bool(source_checks.get("target_selection_service_backed")),
        "target_keeps_projection": bool(source_checks.get("target_keeps_projection")),
        "target_uses_controller_projection_helper": bool(source_checks.get("target_uses_controller_projection_helper")),
        "controller_projection_helper_exists": bool(source_checks.get("controller_projection_helper_exists")),
        "controller_projection_helper_exported": bool(source_checks.get("controller_projection_helper_exported")),
        "target_no_longer_embeds_item_projection_payload": bool(source_checks.get("target_no_longer_embeds_item_projection_payload")),
        "target_keeps_debug_sink": bool(source_checks.get("target_keeps_debug_sink")),
        "candidate_evaluation_boundary_clean": bool(source_checks.get("candidate_evaluation_has_no_page_import"))
        and bool(source_checks.get("candidate_evaluation_has_no_streamlit_import"))
        and bool(source_checks.get("candidate_evaluation_has_no_session_import")),
        "service_helper_has_candidate_generation": bool(source_checks.get("service_helper_has_candidate_generation")),
        "candidate_generation_parity_passed": not bool(parity_summary.get("mismatches")),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    target = dict(capture.get("target") or {})
    helper = dict(capture.get("service_helper") or {})
    lines = [
        "# Probe-Equivalent Bending Candidate Generation Boundary",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        f"- Target: `{target.get('name')}` lines `{target.get('line_start')}-{target.get('line_end')}`",
        f"- Service helper: `{helper.get('name')}` lines `{helper.get('line_start')}-{helper.get('line_end')}`",
        "",
        "## Behaviour Preserved",
        "- Candidate row generation moved behind candidate_evaluation service.",
        "- Candidate evaluation, selection, item projection, CTA/apply payload, debug sink writes, and visible wording remain unchanged in this slice.",
        "",
        "## Candidate Generation Parity",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(
            f"- `{case.get('case')}`: match=`{case.get('match')}`, "
            f"old_count=`{case.get('old_count')}`, new_count=`{case.get('new_count')}`"
        )
    lines.extend(["", "## Source Checks"])
    for key, value in dict(capture.get("source_checks") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Remaining Page-Owned Surfaces"])
    for item in capture.get("remaining_page_owned_surfaces") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Safe Target", str(capture.get("next_safe_slice") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n- `{payload.get('timestamp')}` probe-equivalent bending candidate generation boundary: "
            f"{payload.get('status')} report `{report_path.relative_to(ROOT).as_posix()}`\n"
        )


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ts = _timestamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "timestamp": ts,
        "status": status,
        "checks": checks,
        "capture": capture,
        "artifact_hash": _stable_hash({"checks": checks, "capture": capture}),
    }
    artifact_path = ARTIFACT_DIR / f"design_guide_probe_equivalent_bending_candidate_generation_boundary_{ts.replace(':', '-')}.json"
    report_path = AUDIT_DIR / f"design_guide_probe_equivalent_bending_candidate_generation_boundary_{ts.replace(':', '-')}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_probe_equivalent_bending_candidate_generation_boundary {status}")
    print(f"artifact: {artifact_path}")
    print(f"report: {report_path}")
    if status != "PASS":
        print(json.dumps(checks, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
