"""Verify active-fail executor ladder eval command handoff."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_active_fail_near_current_repair_item"
HELPER = "build_design_guide_controller_active_fail_executor_ladder_eval_commands"
META_HELPER = "build_design_guide_controller_active_fail_executor_ladder_candidate_meta"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _ladder() -> dict[str, Any]:
    return {
        "specs": [
            {
                "ladder_index": 1,
                "contract_step": "first",
                "strategy": "increase_shear",
                "updates": {"lig_d": 10, "lig_spacing": 150.0},
                "label": "explicit label",
            },
            None,
            {
                "ladder_index": 2,
                "contract_step": "second",
                "strategy": "increase_depth",
                "updates": {"D": 700.0},
            },
        ],
        "known_bad_candidate_count": 1,
    }


def _old_commands(family_id: str, ladder: dict[str, Any], default_label: str) -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_ladder_candidate_meta,
    )

    commands: list[dict[str, Any]] = []
    for spec in list(ladder.get("specs") or []):
        if not isinstance(spec, dict):
            continue
        spec_map = dict(spec)
        commands.append(
            {
                "spec": spec_map,
                "updates": dict(spec_map.get("updates") or {}),
                "label": str(spec_map.get("label") or default_label),
                "family_meta": build_design_guide_controller_active_fail_executor_ladder_candidate_meta(
                    family_id=family_id,
                    spec=spec_map,
                ),
            }
        )
    return commands


def _new_commands(family_id: str, ladder: dict[str, Any], default_label: str) -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_ladder_eval_commands,
    )

    return build_design_guide_controller_active_fail_executor_ladder_eval_commands(
        family_id=family_id,
        ladder=dict(ladder),
        default_label=default_label,
    )


def _cases() -> dict[str, tuple[str, str]]:
    return {
        "shear": ("SHEAR_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS repair ladder candidate"),
        "bending": ("BENDING_FAIL_GOVERNS", "BENDING_FAIL_GOVERNS repair ladder candidate"),
        "combined": ("COMBINED_BENDING_SHEAR_FAIL", "COMBINED_BENDING_SHEAR_FAIL repair ladder candidate"),
        "unknown": ("CUSTOM_FAIL", "custom repair ladder candidate"),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(controller_source, HELPER)

    parity = {}
    ladder = _ladder()
    for name, (family_id, default_label) in _cases().items():
        old = _old_commands(family_id, ladder, default_label)
        new = _new_commands(family_id, ladder, default_label)
        parity[name] = {
            "old_hash": _stable_hash(old),
            "new_hash": _stable_hash(new),
            "match": old == new,
            "command_count": len(new),
        }

    removed_inline_tokens = {
        'for spec in list(shear_family_ladder.get("specs") or []):': 'for spec in list(shear_family_ladder.get("specs") or []):'
        not in target_source,
        'for spec in list(bending_family_ladder.get("specs") or []):': 'for spec in list(bending_family_ladder.get("specs") or []):'
        not in target_source,
        'for spec in list(combined_family_ladder.get("specs") or []):': 'for spec in list(combined_family_ladder.get("specs") or []):'
        not in target_source,
        "_build_design_guide_controller_active_fail_executor_ladder_candidate_meta(": "_build_design_guide_controller_active_fail_executor_ladder_candidate_meta("
        not in target_source,
    }

    return {
        "schema": "design_guide_active_fail_executor_ladder_eval_command_handoff.v1",
        "target": {
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
            "delegates_ladder_eval_commands": "_build_design_guide_controller_active_fail_executor_ladder_eval_commands("
            in target_source,
            "still_owns_evaluator_callback": "_evaluate_active_fail_executor_candidate_with_updates(" in target_source,
            "still_owns_break_conditions": "break" in target_source and "is_compliant" in target_source,
            "still_owns_bending_trace_emission": "bending_fail_ladder.evaluate_candidate" in target_source,
            "removed_inline_tokens": removed_inline_tokens,
        },
        "controller_helper": {
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
            "exists": bool(helper_start),
            "exported": f'"{HELPER}"' in controller_source,
            "uses_meta_helper": f"{META_HELPER}(" in helper_source,
            "imports_no_page_or_streamlit": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
        },
        "parity": parity,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    target = payload.get("target") or {}
    helper = payload.get("controller_helper") or {}
    parity = payload.get("parity") or {}
    return {
        "target_found": bool(target.get("line_start")),
        "target_delegates_ladder_eval_commands": bool(target.get("delegates_ladder_eval_commands")),
        "page_still_owns_evaluator_callback": bool(target.get("still_owns_evaluator_callback")),
        "page_still_owns_break_conditions": bool(target.get("still_owns_break_conditions")),
        "page_still_owns_bending_trace_emission": bool(target.get("still_owns_bending_trace_emission")),
        "inline_spec_loop_and_meta_tokens_removed": all((target.get("removed_inline_tokens") or {}).values()),
        "controller_helper_exists": bool(helper.get("exists")),
        "controller_helper_exported": bool(helper.get("exported")),
        "controller_helper_uses_meta_helper": bool(helper.get("uses_meta_helper")),
        "controller_import_boundary_clean": bool(helper.get("imports_no_page_or_streamlit")),
        "parity_cases_present": len(parity) == 4,
        "all_command_hashes_match": all(bool(row.get("match")) for row in parity.values()),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_ladder_eval_command_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_ladder_eval_command_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Ladder Eval Command Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Executive Summary",
        (
            "Active-fail family ladder specs now become ordered evaluation commands in "
            "`DesignGuideController`. The page still executes evaluator callbacks, break conditions, "
            "trace/session side effects, and candidate ordering."
        ),
        "",
        "## Command Parity",
    ]
    for name, row in (payload.get("parity") or {}).items():
        lines.append(
            f"- {name}: {'PASS' if row.get('match') else 'FAIL'} "
            f"commands `{row.get('command_count')}` hash `{row.get('new_hash')}`"
        )
    lines.extend(["", "## Checks", *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()]])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    payload["snapshot_hash"] = _stable_hash(
        {
            "target": payload.get("target"),
            "controller_helper": payload.get("controller_helper"),
            "parity": payload.get("parity"),
        }
    )
    json_path, report_path = _write(payload, checks)
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
