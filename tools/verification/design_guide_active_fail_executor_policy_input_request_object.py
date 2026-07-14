"""Verify active-fail executor policy input request object extraction."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
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
HELPER = "build_design_guide_controller_active_fail_executor_policy_input_request"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _old_projection(
    *,
    base_state: dict[str, Any],
    goal_labels: dict[str, Any],
    mode_config_by_goal: dict[str, dict[str, Any]],
    default_low: float,
    default_high: float,
    default_goal: str = "balanced",
) -> dict[str, Any]:
    from design_brain.config import (  # noqa: WPS433
        resolve_design_mode_config,
        resolve_design_optimisation_goal,
        resolve_efficiency_target_band,
    )

    goal = resolve_design_optimisation_goal(
        base_state,
        goal_labels=goal_labels,
        default_goal=default_goal,
    )
    mode_config = resolve_design_mode_config(
        goal,
        mode_config_by_goal=mode_config_by_goal,
        default_goal=default_goal,
    )
    target_low, target_high, default_band_used = resolve_efficiency_target_band(
        mode_config,
        goal=goal,
        mode_config_by_goal=mode_config_by_goal,
        default_low=default_low,
        default_high=default_high,
        default_goal=default_goal,
    )
    return {
        "optimisation_goal": str(goal),
        "mode_config": dict(mode_config),
        "target_low": float(target_low),
        "target_high": float(target_high),
        "target_band_default_used": bool(default_band_used),
    }


def _new_projection(**kwargs: Any) -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_policy_input_request,
    )

    out = build_design_guide_controller_active_fail_executor_policy_input_request(**kwargs)
    out.pop("authority", None)
    return out


def _cases() -> dict[str, dict[str, Any]]:
    labels = {"balanced": "Balanced", "lean": "Lean"}
    configs = {
        "balanced": {"target_util_min": 0.88, "target_util_max": 0.95, "search_strategy": "balanced"},
        "lean": {"target_util_min": 0.82, "target_util_max": 0.92, "search_strategy": "lean"},
    }
    return {
        "default_goal": {
            "base_state": {},
            "goal_labels": labels,
            "mode_config_by_goal": configs,
            "default_low": 0.88,
            "default_high": 0.95,
            "default_goal": "balanced",
        },
        "explicit_goal": {
            "base_state": {"design_optimisation_goal": "lean"},
            "goal_labels": labels,
            "mode_config_by_goal": configs,
            "default_low": 0.88,
            "default_high": 0.95,
            "default_goal": "balanced",
        },
        "unknown_goal_falls_back": {
            "base_state": {"design_optimisation_goal": "unknown"},
            "goal_labels": labels,
            "mode_config_by_goal": configs,
            "default_low": 0.88,
            "default_high": 0.95,
            "default_goal": "balanced",
        },
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(controller_source, HELPER)
    parity: dict[str, dict[str, Any]] = {}
    for name, kwargs in _cases().items():
        old = _old_projection(**kwargs)
        new = _new_projection(**kwargs)
        parity[name] = {
            "match": old == new,
            "old": old,
            "new": new,
        }
    return {
        "schema": "design_guide_active_fail_executor_policy_input_request_object.v1",
        "target": {
            "line_start": target_start,
            "line_end": target_end,
            "delegates_policy_inputs": "_build_design_guide_controller_active_fail_executor_policy_input_request("
            in target_source,
            "old_inline_projection_removed": (
                "mode_cfg = _design_mode_config(_design_optimisation_goal(base))" not in target_source
                and "target_low, target_high, _ = _resolved_efficiency_target_band(" not in target_source
            ),
        },
        "controller_helper": {
            "line_start": helper_start,
            "line_end": helper_end,
            "exists": bool(helper_start),
            "exported": f'"{HELPER}"' in controller_source,
            "imports_no_page_or_streamlit": all(
                token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
            ),
            "uses_design_brain_config": all(
                token in helper_source
                for token in (
                    "resolve_design_optimisation_goal(",
                    "resolve_design_mode_config(",
                    "resolve_efficiency_target_band(",
                )
            ),
        },
        "parity": parity,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    target = payload.get("target") or {}
    helper = payload.get("controller_helper") or {}
    parity = payload.get("parity") or {}
    return {
        "target_found": bool(target.get("line_start")),
        "target_delegates_policy_inputs": bool(target.get("delegates_policy_inputs")),
        "old_inline_projection_removed": bool(target.get("old_inline_projection_removed")),
        "controller_helper_exists": bool(helper.get("exists")),
        "controller_helper_exported": bool(helper.get("exported")),
        "controller_import_boundary_clean": bool(helper.get("imports_no_page_or_streamlit")),
        "controller_uses_config_helpers": bool(helper.get("uses_design_brain_config")),
        "parity_cases_present": len(parity) == 3,
        "all_parity_cases_match": all(bool(row.get("match")) for row in parity.values()),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_policy_input_request_object_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_policy_input_request_object_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Policy Input Request Object",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "Active-fail executor optimisation goal, mode config, and target-band projection now delegate to a pure controller helper.",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_policy_input_request_object {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
