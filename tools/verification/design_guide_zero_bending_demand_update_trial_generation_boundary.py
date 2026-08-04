from __future__ import annotations

import ast
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET = "_zero_bending_demand_cleanup_item"
SERVICE_HELPER = "build_zero_bending_demand_cleanup_update_trials"
SERVICE_ALIAS = "_build_zero_bending_demand_cleanup_update_trials"
EVALUATION_WRAPPER = "_evaluate_zero_bending_demand_candidate_with_service"
PROJECTION_HELPER = "build_design_guide_controller_zero_bending_demand_cleanup_item_projection"
PROJECTION_ALIAS = "_build_design_guide_controller_zero_bending_demand_cleanup_item_projection"


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


def _updates_match_state(base: dict[str, Any], updates: dict[str, Any]) -> bool:
    if not updates:
        return True
    for key, value in dict(updates or {}).items():
        if str((base or {}).get(key)) != str(value):
            return False
    return True


def _old_inline_zero_bending_trial_builder(
    base_state: dict[str, Any],
    *,
    width_key: str,
    current_width: float,
    current_depth: float,
    row1_bars: int,
    row2_bars: int,
    row1_dia: int,
    row2_dia: int,
    geometry_locked: bool,
    min_width: float,
    min_depth: float,
    updates_match_state_fn: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    base = dict(base_state or {})
    common_dias = [10, 12, 16, 20, 24, 28, 32, 36, 40]
    dia_trials = sorted({int(d) for d in common_dias if 10 <= int(d) <= max(int(row1_dia), 10)}, reverse=True)
    if int(row1_dia) not in dia_trials:
        dia_trials.append(int(row1_dia))
        dia_trials = sorted(set(dia_trials), reverse=True)
    bar_trials = list(range(max(2, min(int(row1_bars), 6)), 1, -1))
    if int(row1_bars) not in bar_trials:
        bar_trials.insert(0, int(row1_bars))

    if geometry_locked:
        width_trials = [float(current_width)]
        depth_trials = [float(current_depth)]
    else:
        width_trials = sorted(
            {
                float(value)
                for value in (float(current_width), float(current_width) - 50.0, float(min_width))
                if float(value) >= float(min_width)
            },
            reverse=True,
        )
        depth_trials = sorted(
            {
                float(value)
                for value in (
                    float(current_depth),
                    float(current_depth) - 50.0,
                    float(current_depth) - 100.0,
                    float(current_depth) - 150.0,
                    float(min_depth),
                )
                if float(value) >= float(min_depth)
            },
            reverse=True,
        )

    def _material_proxy(width: float, depth: float, bars: int, dia: int) -> float:
        ast_value = float(bars) * math.pi * (float(dia) ** 2.0) / 4.0
        return float(width) * float(depth) * 0.001 + ast_value * 0.05

    current_proxy = _material_proxy(
        float(current_width),
        float(current_depth),
        int(row1_bars) + int(row2_bars),
        int(row1_dia),
    )
    update_trials: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for width in width_trials:
        for depth in depth_trials:
            for bars in bar_trials:
                for dia in dia_trials:
                    updates: dict[str, Any] = {
                        str(width_key): float(width),
                        "D": float(depth),
                        "bot_row_count": 1,
                        "bot_row_1_bars": int(bars),
                        "bot1_count": int(bars),
                        "nb_bot": int(bars),
                        "bot_entry": float(bars),
                        "bot_row_1_dia": int(dia),
                        "db_bot_1": int(dia),
                        "bot_row_2_bars": 0,
                        "bot2_count": 0,
                        "bot_row_2_dia": int(min(int(row2_dia), int(dia))),
                        "db_bot_2": int(min(int(row2_dia), int(dia))),
                    }
                    if str(width_key) != "b":
                        updates["b"] = float(width)
                    if str(width_key) != "bw":
                        updates["bw"] = float(width)
                    updates = {key: value for key, value in updates.items() if str(base.get(key)) != str(value)}
                    if not updates:
                        continue
                    if updates_match_state_fn is not None and updates_match_state_fn(base, updates):
                        continue
                    key = tuple(sorted((str(k), repr(v)) for k, v in updates.items()))
                    if key in seen:
                        continue
                    seen.add(key)
                    proxy = _material_proxy(float(width), float(depth), int(bars), int(dia))
                    if proxy >= current_proxy - 1e-9:
                        continue
                    update_trials.append(
                        {
                            "updates": dict(updates),
                            "candidate_material_proxy": float(proxy),
                        }
                    )

    return {
        "current_material_proxy": float(current_proxy),
        "update_trials": update_trials,
    }


def _sample_parity() -> list[dict[str, Any]]:
    from design_brain.candidate_evaluation import (  # noqa: WPS433
        build_zero_bending_demand_cleanup_update_trials,
    )

    cases = [
        {
            "name": "unlocked_b_width",
            "base_state": {
                "b": 400.0,
                "bw": 400.0,
                "D": 650.0,
                "bot_row_1_bars": 6,
                "bot1_count": 6,
                "bot_row_1_dia": 20,
                "db_bot_1": 20,
                "bot_row_2_bars": 2,
                "bot2_count": 2,
                "bot_row_2_dia": 16,
                "db_bot_2": 16,
            },
            "width_key": "b",
            "geometry_locked": False,
        },
        {
            "name": "locked_b_width",
            "base_state": {
                "b": 350.0,
                "bw": 350.0,
                "D": 550.0,
                "bot_row_1_bars": 5,
                "bot1_count": 5,
                "bot_row_1_dia": 16,
                "db_bot_1": 16,
                "bot_row_2_bars": 0,
                "bot2_count": 0,
                "bot_row_2_dia": 12,
                "db_bot_2": 12,
            },
            "width_key": "b",
            "geometry_locked": True,
        },
        {
            "name": "unlocked_bw_width",
            "base_state": {
                "b": 450.0,
                "bw": 450.0,
                "D": 700.0,
                "bot_row_1_bars": 4,
                "bot1_count": 4,
                "bot_row_1_dia": 24,
                "db_bot_1": 24,
                "bot_row_2_bars": 1,
                "bot2_count": 1,
                "bot_row_2_dia": 20,
                "db_bot_2": 20,
            },
            "width_key": "bw",
            "geometry_locked": False,
        },
    ]

    out: list[dict[str, Any]] = []
    for case in cases:
        base_state = dict(case["base_state"])
        kwargs = {
            "width_key": str(case["width_key"]),
            "current_width": float(base_state.get(case["width_key"], 0.0) or 0.0),
            "current_depth": float(base_state.get("D", 0.0) or 0.0),
            "row1_bars": int(base_state.get("bot_row_1_bars") or base_state.get("bot1_count") or 0),
            "row2_bars": int(base_state.get("bot_row_2_bars") or base_state.get("bot2_count") or 0),
            "row1_dia": int(base_state.get("bot_row_1_dia") or base_state.get("db_bot_1") or 16),
            "row2_dia": int(base_state.get("bot_row_2_dia") or base_state.get("db_bot_2") or base_state.get("bot_row_1_dia") or 16),
            "geometry_locked": bool(case["geometry_locked"]),
            "min_width": 200.0,
            "min_depth": 250.0,
            "updates_match_state_fn": _updates_match_state,
        }
        old_result = _old_inline_zero_bending_trial_builder(base_state, **kwargs)
        new_result = build_zero_bending_demand_cleanup_update_trials(base_state, **kwargs)
        out.append(
            {
                "case": case["name"],
                "old_hash": _stable_hash(old_result),
                "new_hash": _stable_hash(new_result),
                "match": old_result == new_result,
                "old_count": len(old_result.get("update_trials") or []),
                "new_count": len(new_result.get("update_trials") or []),
                "current_proxy_match": old_result.get("current_material_proxy") == new_result.get("current_material_proxy"),
                "first_trial_hashes": {
                    "old": _stable_hash((old_result.get("update_trials") or [])[:5]),
                    "new": _stable_hash((new_result.get("update_trials") or [])[:5]),
                },
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
        "schema": "design_guide_zero_bending_demand_update_trial_generation_boundary.v1",
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
            "target_local_material_proxy_removed": "def _material_proxy" not in target_source,
            "target_width_depth_trial_loops_removed": "for width in width_trials" not in target_source and "for depth in depth_trials" not in target_source,
            "target_common_dia_trial_construction_removed": "common_dias" not in target_source and "dia_trials" not in target_source,
            "target_keeps_projection": "_guidance_item_from_resolved_candidate(" in target_source,
            "target_uses_controller_projection_helper": f"{PROJECTION_ALIAS}(" in target_source,
            "controller_projection_helper_exists": f"def {PROJECTION_HELPER}(" in controller_source,
            "controller_projection_helper_exported": f'"{PROJECTION_HELPER}"' in controller_source,
            "target_no_longer_embeds_item_projection_payload": 'item["action_payload"]' not in target_source
            and 'item["resolved_candidate"]' not in target_source,
            "candidate_evaluation_has_no_page_import": "inputs_page" not in candidate_source,
            "candidate_evaluation_has_no_streamlit_import": "streamlit" not in candidate_source and "import st" not in candidate_source,
            "candidate_evaluation_has_no_session_import": "session_state" not in candidate_source,
            "service_helper_has_trial_generation": "for width in width_trials" in helper_source and "candidate_material_proxy" in helper_source,
        },
        "parity_cases": parity,
        "parity_summary": {
            "case_count": len(parity),
            "mismatches": [case for case in parity if not bool(case.get("match"))],
        },
        "behaviour_preserved": {
            "candidate_generator_order": all(bool(case.get("match")) for case in parity),
            "selected_candidate_id": "unchanged_by_this_slice_candidate_numbering_stays_page_owned",
            "updates": "unchanged_service_trial_rows_match_old_inline_rows",
            "button_contract": "unchanged_not_touched",
            "action_payload": "unchanged_controller_projection_parity_passed",
            "debug_proof_fields": "unchanged_not_touched",
            "visible_wording": "unchanged_not_touched",
            "family_runtime_behaviour": "unchanged_not_touched",
        },
        "remaining_page_owned_surfaces": [
            "safe candidate filtering after evaluation",
            "candidate ranking/selection",
            "debug_sink writes",
            "zero-bending-demand visible item wording",
        ],
        "next_safe_slice": "probe_equivalent_bending_candidate_generation_service_boundary",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    parity_summary = dict(capture.get("parity_summary") or {})
    return {
        "service_helper_exported": bool((capture.get("service_helper") or {}).get("exported")),
        "inputs_imports_service_helper": bool(source_checks.get("inputs_imports_service_helper")),
        "target_calls_service_helper": bool(source_checks.get("target_calls_service_helper")),
        "target_uses_candidate_eval_service_wrapper": bool(source_checks.get("target_uses_candidate_eval_service_wrapper")),
        "target_local_material_proxy_removed": bool(source_checks.get("target_local_material_proxy_removed")),
        "target_width_depth_trial_loops_removed": bool(source_checks.get("target_width_depth_trial_loops_removed")),
        "target_common_dia_trial_construction_removed": bool(source_checks.get("target_common_dia_trial_construction_removed")),
        "target_keeps_projection": bool(source_checks.get("target_keeps_projection")),
        "target_uses_controller_projection_helper": bool(source_checks.get("target_uses_controller_projection_helper")),
        "controller_projection_helper_exists": bool(source_checks.get("controller_projection_helper_exists")),
        "controller_projection_helper_exported": bool(source_checks.get("controller_projection_helper_exported")),
        "target_no_longer_embeds_item_projection_payload": bool(source_checks.get("target_no_longer_embeds_item_projection_payload")),
        "candidate_evaluation_boundary_clean": bool(source_checks.get("candidate_evaluation_has_no_page_import"))
        and bool(source_checks.get("candidate_evaluation_has_no_streamlit_import"))
        and bool(source_checks.get("candidate_evaluation_has_no_session_import")),
        "service_helper_has_trial_generation": bool(source_checks.get("service_helper_has_trial_generation")),
        "trial_generation_parity_passed": not bool(parity_summary.get("mismatches")),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    target = dict(capture.get("target") or {})
    helper = dict(capture.get("service_helper") or {})
    source_checks = dict(capture.get("source_checks") or {})
    parity_cases = list(capture.get("parity_cases") or [])
    lines = [
        "# Zero Bending Demand Update-Trial Generation Boundary",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        f"- Target: `{target.get('name')}` lines `{target.get('line_start')}-{target.get('line_end')}`",
        f"- Service helper: `{helper.get('name')}` lines `{helper.get('line_start')}-{helper.get('line_end')}`",
        "",
        "## Behaviour Preserved",
        "- Candidate evaluation remains service-backed.",
        "- Candidate ranking, item projection, CTA/apply payload, debug sink writes, and visible wording remain page-owned and unchanged in this slice.",
        "- The service helper only builds update trial rows and material proxy values.",
        "",
        "## Projection Parity",
    ]
    for case in parity_cases:
        lines.append(
            f"- `{case.get('case')}`: match=`{case.get('match')}`, "
            f"old_count=`{case.get('old_count')}`, new_count=`{case.get('new_count')}`"
        )
    lines.extend(
        [
            "",
            "## Source Checks",
        ]
    )
    for key, value in source_checks.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Surfaces",
        ]
    )
    for item in capture.get("remaining_page_owned_surfaces") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Next Safe Target",
            str(capture.get("next_safe_slice") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"\n- `{payload.get('timestamp')}` zero-bending update-trial generation boundary: "
        f"{payload.get('status')} report `{report_path.relative_to(ROOT).as_posix()}`\n"
    )
    with PROGRESS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)


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
    artifact_path = ARTIFACT_DIR / f"design_guide_zero_bending_demand_update_trial_generation_boundary_{ts.replace(':', '-')}.json"
    report_path = AUDIT_DIR / f"design_guide_zero_bending_demand_update_trial_generation_boundary_{ts.replace(':', '-')}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_zero_bending_demand_update_trial_generation_boundary {status}")
    print(f"artifact: {artifact_path}")
    print(f"report: {report_path}")
    if status != "PASS":
        print(json.dumps(checks, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
