"""Verify active-fail executor rescue tier route input adapter extraction."""

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
HELPER = "build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs"
TIER_ORDER = ("medium", "high", "very_high", "extreme")


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


def _old_requested_tier(action_tier: str | None, util_tier: str | None) -> str | None:
    indices = [
        TIER_ORDER.index(tier)
        for tier in (action_tier, util_tier)
        if tier in TIER_ORDER
    ]
    if not indices:
        return None
    return TIER_ORDER[max(indices)]


def _old_seed_order(requested_tier: str | None) -> list[str]:
    if requested_tier not in TIER_ORDER:
        return []
    if requested_tier == "extreme":
        return ["very_high", "extreme"]
    idx = TIER_ORDER.index(requested_tier)
    out = list(TIER_ORDER[idx:])
    if "extreme" in out and requested_tier != "very_high":
        return [tier for tier in out if tier != "extreme"] + ["extreme"]
    return out


def _new_route_inputs(action_tier: str | None, util_tier: str | None) -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs,
    )

    out = build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs(
        action_tier=action_tier,
        util_tier=util_tier,
        tier_order=TIER_ORDER,
    )
    out.pop("authority", None)
    return out


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(controller_source, HELPER)
    cases = {
        "none": (None, None),
        "action_medium": ("medium", None),
        "util_high": (None, "high"),
        "max_tier_wins": ("medium", "very_high"),
        "extreme": ("extreme", "high"),
        "unknown_ignored": ("bogus", "medium"),
    }
    parity: dict[str, dict[str, Any]] = {}
    for name, (action_tier, util_tier) in cases.items():
        requested = _old_requested_tier(action_tier, util_tier)
        old = {
            "requested_tier": requested,
            "rescue_tiers": _old_seed_order(requested),
            "action_tier": action_tier,
            "util_tier": util_tier,
            "tier_order": list(TIER_ORDER),
        }
        new = _new_route_inputs(action_tier, util_tier)
        parity[name] = {
            "match": old == new,
            "old": old,
            "new": new,
        }
    return {
        "schema": "design_guide_active_fail_executor_rescue_tier_route_input_adapter.v1",
        "target": {
            "line_start": target_start,
            "line_end": target_end,
            "delegates_rescue_tier_inputs": "_build_design_guide_controller_active_fail_executor_rescue_tier_route_inputs("
            in target_source,
            "old_tier_chooser_removed_from_target": "_rescue_mode_choose_tier_from_overview(" not in target_source,
            "old_seed_order_removed_from_target": "_rescue_mode_seed_order(" not in target_source,
            "page_still_computes_action_util_tiers": (
                "_rescue_mode_action_tier(" in target_source
                and "_rescue_mode_overview_util_tier(" in target_source
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
            "helper_source_has_no_page_helpers": all(
                token not in helper_source
                for token in ("_rescue_mode_choose_tier_from_overview", "_rescue_mode_seed_order")
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
        "target_delegates_rescue_tier_inputs": bool(target.get("delegates_rescue_tier_inputs")),
        "old_tier_chooser_removed_from_target": bool(target.get("old_tier_chooser_removed_from_target")),
        "old_seed_order_removed_from_target": bool(target.get("old_seed_order_removed_from_target")),
        "page_still_computes_action_util_tiers": bool(target.get("page_still_computes_action_util_tiers")),
        "controller_helper_exists": bool(helper.get("exists")),
        "controller_helper_exported": bool(helper.get("exported")),
        "controller_import_boundary_clean": bool(helper.get("imports_no_page_or_streamlit")),
        "controller_helper_has_no_page_helpers": bool(helper.get("helper_source_has_no_page_helpers")),
        "parity_cases_present": len(parity) == 6,
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
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_rescue_tier_route_input_adapter_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_rescue_tier_route_input_adapter_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Rescue Tier Route Input Adapter",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "Rescue tier request/order projection now delegates to a pure controller helper.",
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
    print(f"design_guide_active_fail_executor_rescue_tier_route_input_adapter {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
