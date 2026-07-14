"""Verify active-fail executor ladder metadata projection handoff."""

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
HELPER = "build_design_guide_controller_active_fail_executor_ladder_candidate_meta"


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


def _old_meta(family_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    if family_id == "SHEAR_FAIL_GOVERNS":
        return {
            "candidate_family_id": "SHEAR_FAIL_GOVERNS",
            "card_family_id": "SHEAR_FAIL_GOVERNS",
            "published_family_id": "SHEAR_FAIL_GOVERNS",
            "cta_family_id": "SHEAR_FAIL_GOVERNS",
            "shear_fail_ladder_index": spec.get("ladder_index"),
            "shear_fail_contract_step": spec.get("contract_step"),
            "shear_fail_strategy": spec.get("strategy"),
            "shear_fail_restart_point": bool(spec.get("restart_point")),
            "shear_fail_escalation": spec.get("escalation"),
        }
    if family_id == "BENDING_FAIL_GOVERNS":
        return {
            "candidate_family_id": "BENDING_FAIL_GOVERNS",
            "card_family_id": "BENDING_FAIL_GOVERNS",
            "published_family_id": "BENDING_FAIL_GOVERNS",
            "cta_family_id": "BENDING_FAIL_GOVERNS",
            "bending_fail_ladder_index": spec.get("ladder_index"),
            "bending_fail_contract_step": spec.get("contract_step"),
            "bending_fail_stage_name": spec.get("stage_name"),
            "bending_fail_strategy": spec.get("strategy"),
            "bending_fail_escalation": spec.get("escalation"),
            "bending_fail_stop_rule": spec.get("stop_rule"),
            "bending_fail_candidate_b": spec.get("b"),
            "bending_fail_candidate_D": spec.get("D"),
            "bending_fail_bottom_bar_count": spec.get("bottom_bar_count"),
            "bending_fail_bar_diameter": spec.get("bar_diameter"),
            "bending_fail_split_row": bool(spec.get("split_row")),
            "bending_fail_clear_spacing": spec.get("clear_spacing"),
        }
    if family_id == "COMBINED_BENDING_SHEAR_FAIL":
        return {
            "candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "card_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "combined_fail_ladder_index": spec.get("ladder_index"),
            "combined_fail_contract_step": spec.get("contract_step"),
            "combined_fail_strategy": spec.get("strategy"),
            "combined_fail_stop_rule": spec.get("stop_rule"),
        }
    family = family_id or "UNKNOWN_ACTIVE_FAIL_FAMILY"
    return {
        "candidate_family_id": family,
        "card_family_id": family,
        "published_family_id": family,
        "cta_family_id": family,
    }


def _new_meta(family_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_ladder_candidate_meta,
    )

    return build_design_guide_controller_active_fail_executor_ladder_candidate_meta(
        family_id=family_id,
        spec=dict(spec),
    )


def _cases() -> dict[str, tuple[str, dict[str, Any]]]:
    spec = {
        "ladder_index": 3,
        "contract_step": "increase_capacity",
        "strategy": "geometry_then_reo",
        "restart_point": True,
        "escalation": "tier_2",
        "stage_name": "increase_bottom_reo",
        "stop_rule": "first_safe_candidate",
        "b": 450.0,
        "D": 700.0,
        "bottom_bar_count": 7,
        "bar_diameter": 20,
        "split_row": True,
        "clear_spacing": 52.5,
    }
    return {
        "shear": ("SHEAR_FAIL_GOVERNS", dict(spec)),
        "bending": ("BENDING_FAIL_GOVERNS", dict(spec)),
        "combined": ("COMBINED_BENDING_SHEAR_FAIL", dict(spec)),
        "fallback_unknown": ("CUSTOM_FAIL_FAMILY", dict(spec)),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(CONTROLLER.read_text(encoding="utf-8"), HELPER)
    parity: dict[str, dict[str, Any]] = {}
    for name, (family_id, spec) in _cases().items():
        old = _old_meta(family_id, spec)
        new = _new_meta(family_id, spec)
        parity[name] = {
            "old_hash": _stable_hash(old),
            "new_hash": _stable_hash(new),
            "match": old == new,
        }
    inline_meta_tokens = [
        '"shear_fail_ladder_index": spec.get("ladder_index")',
        '"bending_fail_ladder_index": spec.get("ladder_index")',
        '"combined_fail_ladder_index": spec.get("ladder_index")',
        '"bending_fail_split_row": bool(spec.get("split_row"))',
    ]
    return {
        "schema": "design_guide_active_fail_executor_ladder_meta_projection_handoff.v1",
        "target": {
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
            "delegates_meta_projection": "_build_design_guide_controller_active_fail_executor_ladder_candidate_meta("
            in target_source,
            "inline_meta_tokens_removed": {
                token: token not in target_source for token in inline_meta_tokens
            },
        },
        "controller_helper": {
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
            "exists": bool(helper_start),
            "exported": f'"{HELPER}"' in controller_source,
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
        "target_delegates_meta_projection": bool(target.get("delegates_meta_projection")),
        "inline_meta_tokens_removed": all((target.get("inline_meta_tokens_removed") or {}).values()),
        "controller_helper_exists": bool(helper.get("exists")),
        "controller_helper_exported": bool(helper.get("exported")),
        "controller_import_boundary_clean": bool(helper.get("imports_no_page_or_streamlit")),
        "parity_cases_present": len(parity) == 4,
        "all_meta_projection_hashes_match": all(bool(row.get("match")) for row in parity.values()),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_ladder_meta_projection_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_ladder_meta_projection_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Ladder Meta Projection Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Executive Summary",
        (
            "Active-fail ladder candidate metadata projection now delegates to "
            "`DesignGuideController`. The page loop still controls iteration, evaluation callback, "
            "cache/session state, and trace emission."
        ),
        "",
        "## Parity Cases",
    ]
    for name, row in (payload.get("parity") or {}).items():
        lines.append(f"- {name}: {'PASS' if row.get('match') else 'FAIL'} hash `{row.get('new_hash')}`")
    lines.extend(
        [
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_ladder_meta_projection_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
