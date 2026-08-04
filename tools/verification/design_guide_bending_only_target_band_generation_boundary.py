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
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET = "_bending_only_target_band_cleanup_item"
SERVICE_HELPER = "build_bending_only_target_band_cleanup_update_trials"
SERVICE_ALIAS = "_build_bending_only_target_band_cleanup_update_trials"
EVALUATION_WRAPPER = "_evaluate_bending_only_target_band_candidate_with_service"


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


def _old_inline_bending_only_update_trials(
    base_state: dict[str, Any],
    *,
    width_key: str,
    current_width: float,
    current_depth: float,
    row_count: int,
    row1_bars: int,
    row2_bars: int,
    row1_dia: int,
    row2_dia: int,
    geometry_locked: bool,
    min_width: float,
    min_depth: float,
    compound_shear_update_keys: set[str],
) -> dict[str, Any]:
    del row_count
    base = dict(base_state or {})
    common_dias = [10, 12, 16, 20, 24, 28, 32, 36, 40]
    dia_trials = [d for d in common_dias if d <= max(int(row1_dia), 10)]
    if int(row1_dia) not in dia_trials:
        dia_trials.append(int(row1_dia))
    dia_trials = sorted(set(int(d) for d in dia_trials), reverse=True)

    raw_updates: list[dict[str, Any]] = []

    def _append_update(next_row1: int, next_row2: int, next_dia1: int, next_dia2: int | None = None) -> None:
        next_row1 = max(1, int(next_row1))
        next_row2 = max(0, int(next_row2))
        next_dia1 = int(next_dia1)
        next_dia2 = int(next_dia2 if next_dia2 is not None else next_dia1)
        next_row_count = 2 if next_row2 > 0 else 1
        updates = {
            "bot_row_count": next_row_count,
            "bot_row_1_bars": next_row1,
            "bot_row_1_dia": next_dia1,
            "bot1_count": next_row1,
            "db_bot_1": next_dia1,
            "nb_bot": next_row1 + next_row2,
            "bot_entry": float(next_row1 + next_row2),
            "bot_row_2_bars": next_row2,
            "bot2_count": next_row2,
            "bot_row_2_dia": next_dia2,
            "db_bot_2": next_dia2,
        }
        changed = {key: value for key, value in updates.items() if str(base.get(key)) != str(value)}
        if changed and not (set(changed) & compound_shear_update_keys):
            raw_updates.append(updates)

    def _append_geometry_bottom_update(
        next_width: float,
        next_depth: float,
        next_row1: int,
        next_dia1: int,
    ) -> None:
        next_row1 = max(1, int(next_row1))
        next_dia1 = int(next_dia1)
        next_width = float(next_width)
        next_depth = float(next_depth)
        updates = {
            str(width_key): next_width,
            "D": next_depth,
            "bot_row_count": 1,
            "bot_row_1_bars": next_row1,
            "bot_row_1_dia": next_dia1,
            "bot1_count": next_row1,
            "db_bot_1": next_dia1,
            "nb_bot": next_row1,
            "bot_entry": float(next_row1),
            "bot_row_2_bars": 0,
            "bot2_count": 0,
            "bot_row_2_dia": next_dia1,
            "db_bot_2": next_dia1,
        }
        if str(width_key) != "b":
            updates["b"] = next_width
        if str(width_key) != "bw":
            updates["bw"] = next_width
        changed = {key: value for key, value in updates.items() if str(base.get(key)) != str(value)}
        if changed and not (set(changed) & compound_shear_update_keys):
            raw_updates.append(updates)

    if int(row2_bars) > 0:
        for bars2 in range(int(row2_bars) - 1, -1, -1):
            _append_update(int(row1_bars), bars2, int(row1_dia), int(row2_dia))
        for bars1 in range(int(row1_bars) - 1, 0, -1):
            _append_update(bars1, 0, int(row1_dia), int(row2_dia))
    else:
        for bars1 in range(int(row1_bars) - 1, 0, -1):
            _append_update(bars1, 0, int(row1_dia), int(row2_dia))

    for dia in dia_trials:
        if dia >= int(row1_dia):
            continue
        _append_update(int(row1_bars), int(row2_bars), dia, min(int(row2_dia), dia))
        current_area_key = max(1, int(row1_bars + row2_bars)) * int(row1_dia) * int(row1_dia)
        for bars1 in range(int(row1_bars) + 1, int(row1_bars) + 5):
            if bars1 * int(dia) * int(dia) >= current_area_key:
                continue
            _append_update(bars1, 0, dia, dia)
        for bars1 in range(int(row1_bars) - 1, 0, -1):
            _append_update(bars1, 0, dia, dia)

    if not bool(geometry_locked):
        width_trials = sorted(
            {
                float(value)
                for value in (
                    float(current_width) - 50.0,
                    float(current_width) - 100.0,
                    450.0,
                    400.0,
                    350.0,
                    300.0,
                    float(min_width),
                )
                if float(min_width) <= float(value) < float(current_width) - 1e-9
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
                    float(current_depth) - 200.0,
                    float(min_depth),
                )
                if float(min_depth) <= float(value) <= float(current_depth) + 1e-9
            },
            reverse=True,
        )
        practical_bottom_trials = {
            (int(row1_bars), int(row1_dia)),
            (2, 12),
            (3, 12),
            (4, 12),
            (5, 12),
            (6, 12),
            (2, 16),
            (3, 16),
            (4, 16),
            (2, 20),
        }
        practical_bottom_trials.update((bars1, int(row1_dia)) for bars1 in range(int(row1_bars) - 1, 0, -1))
        for trial_width in width_trials:
            for trial_depth in depth_trials:
                for trial_bars, trial_dia in sorted(practical_bottom_trials):
                    _append_geometry_bottom_update(trial_width, trial_depth, trial_bars, trial_dia)

    seen: set[tuple[tuple[str, str], ...]] = set()
    update_trials: list[dict[str, Any]] = []
    for updates in raw_updates:
        fingerprint = tuple(sorted((str(k), repr(v)) for k, v in updates.items()))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        update_trials.append(dict(updates))

    return {
        "raw_updates": [dict(updates) for updates in raw_updates],
        "update_trials": update_trials,
    }


def _sample_parity() -> list[dict[str, Any]]:
    from design_brain.candidate_evaluation import (  # noqa: WPS433
        build_bending_only_target_band_cleanup_update_trials,
    )

    cases = [
        {
            "name": "unlocked_geometry_and_two_rows",
            "base_state": {
                "b": 450.0,
                "bw": 450.0,
                "D": 700.0,
                "bot_row_count": 2,
                "bot_row_1_bars": 6,
                "bot1_count": 6,
                "bot_row_1_dia": 24,
                "db_bot_1": 24,
                "bot_row_2_bars": 2,
                "bot2_count": 2,
                "bot_row_2_dia": 20,
                "db_bot_2": 20,
            },
            "width_key": "b",
            "geometry_locked": False,
        },
        {
            "name": "locked_reinforcement_only",
            "base_state": {
                "b": 400.0,
                "bw": 400.0,
                "D": 650.0,
                "bot_row_count": 1,
                "bot_row_1_bars": 5,
                "bot1_count": 5,
                "bot_row_1_dia": 20,
                "db_bot_1": 20,
                "bot_row_2_bars": 0,
                "bot2_count": 0,
                "bot_row_2_dia": 16,
                "db_bot_2": 16,
            },
            "width_key": "b",
            "geometry_locked": True,
        },
        {
            "name": "bw_width_context",
            "base_state": {
                "b": 500.0,
                "bw": 500.0,
                "D": 750.0,
                "bot_row_count": 1,
                "bot_row_1_bars": 4,
                "bot1_count": 4,
                "bot_row_1_dia": 16,
                "db_bot_1": 16,
                "bot_row_2_bars": 0,
                "bot2_count": 0,
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
            "row_count": int(base_state.get("bot_row_count") or 1),
            "row1_bars": int(base_state.get("bot_row_1_bars") or base_state.get("bot1_count") or 0),
            "row2_bars": int(base_state.get("bot_row_2_bars") or base_state.get("bot2_count") or 0),
            "row1_dia": int(base_state.get("bot_row_1_dia") or base_state.get("db_bot_1") or 16),
            "row2_dia": int(base_state.get("bot_row_2_dia") or base_state.get("db_bot_2") or base_state.get("bot_row_1_dia") or 16),
            "geometry_locked": bool(case["geometry_locked"]),
            "min_width": 200.0,
            "min_depth": 250.0,
            "compound_shear_update_keys": {"shear_link_spacing", "shear_legs", "link_dia"},
        }
        old_result = _old_inline_bending_only_update_trials(base_state, **kwargs)
        new_result = build_bending_only_target_band_cleanup_update_trials(base_state, **kwargs)
        out.append(
            {
                "case": case["name"],
                "match": old_result == new_result,
                "old_hash": _stable_hash(old_result),
                "new_hash": _stable_hash(new_result),
                "old_raw_count": len(old_result.get("raw_updates") or []),
                "new_raw_count": len(new_result.get("raw_updates") or []),
                "old_deduped_count": len(old_result.get("update_trials") or []),
                "new_deduped_count": len(new_result.get("update_trials") or []),
                "first_update_hashes": {
                    "old": _stable_hash((old_result.get("update_trials") or [])[:8]),
                    "new": _stable_hash((new_result.get("update_trials") or [])[:8]),
                },
            }
        )
    return out


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(candidate_source, SERVICE_HELPER)
    parity = _sample_parity()
    return {
        "schema": "design_guide_bending_only_target_band_generation_boundary.v1",
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
            "target_local_append_helpers_removed": "def _append_update" not in target_source and "def _append_geometry_bottom_update" not in target_source,
            "target_local_width_depth_trial_loops_removed": "for trial_width in width_trials" not in target_source,
            "target_local_dedupe_removed": "seen: set" not in target_source,
            "target_ranking_selection_service_backed": (
                "_select_bending_only_best_safe_partial_cleanup_candidate(" in target_source
                and "_select_bending_only_target_band_cleanup_candidate(" in target_source
                and "def select_bending_only_best_safe_partial_cleanup_candidate(" in candidate_source
                and "def select_bending_only_target_band_cleanup_candidate(" in candidate_source
            ),
            "target_projection_adapter_service_backed": "_guidance_item_from_resolved_candidate(" in target_source
            and "_build_design_guide_controller_bending_only_best_safe_cleanup_item_projection(" in target_source
            and "_build_design_guide_controller_bending_only_target_band_cleanup_item_projection(" in target_source,
            "target_inline_action_payload_projection_removed": 'item["action_payload"]' not in target_source,
            "target_keeps_debug_sink": 'debug_sink["bending_only_cleanup_generated_count"]' in target_source,
            "candidate_evaluation_has_no_page_import": "inputs_page" not in candidate_source,
            "candidate_evaluation_has_no_streamlit_import": "streamlit" not in candidate_source and "import st" not in candidate_source,
            "candidate_evaluation_has_no_session_import": "session_state" not in candidate_source,
            "service_helper_has_generation": "def _append_update" in helper_source and "update_trials" in helper_source,
        },
        "parity_cases": parity,
        "parity_summary": {
            "case_count": len(parity),
            "mismatches": [case for case in parity if not bool(case.get("match"))],
        },
        "behaviour_preserved": {
            "raw_update_order": all(bool(case.get("match")) for case in parity),
            "selected_candidate_id": "unchanged_by_this_slice_candidate_numbering_stays_page_owned",
            "updates": "unchanged_service_update_trials_match_old_inline_trials",
            "button_contract": "unchanged_not_touched",
            "action_payload": "unchanged_not_touched",
            "debug_proof_fields": "unchanged_counts_keep_raw_and_deduped_lists",
            "visible_wording": "unchanged_not_touched",
            "family_runtime_behaviour": "unchanged_not_touched",
        },
        "remaining_page_owned_surfaces": [
            "cache/fingerprint shell",
            "candidate evaluation loop",
            "terminalisation fold",
            "item/action payload projection adapter shell call",
            "debug_sink writes",
        ],
        "next_safe_slice": "bending_only_terminalisation_boundary_audit_or_item_projection_boundary_audit",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    parity_summary = dict(capture.get("parity_summary") or {})
    return {
        "service_helper_exported": bool((capture.get("service_helper") or {}).get("exported")),
        "inputs_imports_service_helper": bool(source_checks.get("inputs_imports_service_helper")),
        "target_calls_service_helper": bool(source_checks.get("target_calls_service_helper")),
        "target_uses_candidate_eval_service_wrapper": bool(source_checks.get("target_uses_candidate_eval_service_wrapper")),
        "target_local_append_helpers_removed": bool(source_checks.get("target_local_append_helpers_removed")),
        "target_local_width_depth_trial_loops_removed": bool(source_checks.get("target_local_width_depth_trial_loops_removed")),
        "target_local_dedupe_removed": bool(source_checks.get("target_local_dedupe_removed")),
        "target_ranking_selection_service_backed": bool(source_checks.get("target_ranking_selection_service_backed")),
        "target_projection_adapter_service_backed": bool(source_checks.get("target_projection_adapter_service_backed")),
        "target_inline_action_payload_projection_removed": bool(source_checks.get("target_inline_action_payload_projection_removed")),
        "target_keeps_debug_sink": bool(source_checks.get("target_keeps_debug_sink")),
        "candidate_evaluation_boundary_clean": bool(source_checks.get("candidate_evaluation_has_no_page_import"))
        and bool(source_checks.get("candidate_evaluation_has_no_streamlit_import"))
        and bool(source_checks.get("candidate_evaluation_has_no_session_import")),
        "service_helper_has_generation": bool(source_checks.get("service_helper_has_generation")),
        "candidate_generation_parity_passed": not bool(parity_summary.get("mismatches")),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    target = dict(capture.get("target") or {})
    helper = dict(capture.get("service_helper") or {})
    lines = [
        "# Bending-Only Target-Band Generation Boundary",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        f"- Target: `{target.get('name')}` lines `{target.get('line_start')}-{target.get('line_end')}`",
        f"- Service helper: `{helper.get('name')}` lines `{helper.get('line_start')}-{helper.get('line_end')}`",
        "",
        "## Behaviour Preserved",
        "- Raw update-trial generation and dedupe moved behind candidate_evaluation service.",
        "- Candidate evaluation, terminalisation, CTA/apply payload semantics, debug sink writes, and visible wording remain unchanged in this slice.",
        "- Ranking and item projection are service/controller-backed.",
        "",
        "## Update-Trial Parity",
    ]
    for case in capture.get("parity_cases") or []:
        lines.append(
            f"- `{case.get('case')}`: match=`{case.get('match')}`, "
            f"raw `{case.get('old_raw_count')}->{case.get('new_raw_count')}`, "
            f"deduped `{case.get('old_deduped_count')}->{case.get('new_deduped_count')}`"
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
            f"\n- `{payload.get('timestamp')}` bending-only target-band generation boundary: "
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
    artifact_path = ARTIFACT_DIR / f"design_guide_bending_only_target_band_generation_boundary_{ts.replace(':', '-')}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_only_target_band_generation_boundary_{ts.replace(':', '-')}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_bending_only_target_band_generation_boundary {status}")
    print(f"artifact: {artifact_path}")
    print(f"report: {report_path}")
    if status != "PASS":
        print(json.dumps(checks, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
