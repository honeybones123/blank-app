"""Verify post-active shear cleanup blocked projection extraction."""

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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_segment(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : int(node.end_lineno or node.lineno)])
    raise RuntimeError(f"Function not found: {name}")


def _controller_guidance_item(
    check_key: str,
    title: str,
    primary_action: str,
    secondary_action: str | None,
    reasoning: str,
    levers: str,
    action_type: str | None,
    action_payload: dict | None,
    *,
    status: str,
    util: float | None,
) -> dict[str, Any]:
    if status == "FAIL":
        bucket = "fail"
    elif status == "EFFICIENCY":
        bucket = "efficiency"
    elif status == "START":
        bucket = "start"
    elif status == "PASS":
        bucket = "pass"
    else:
        bucket = "neutral"
    util_score = float(util) if util is not None else 0.0
    if bucket == "start":
        priority = 50.0
    elif bucket == "fail":
        priority = 300.0 + util_score
    elif bucket == "warn":
        priority = 200.0 + util_score
    elif bucket == "efficiency":
        priority = 150.0 + util_score
    else:
        priority = 100.0 - util_score
    return {
        "check_key": check_key,
        "title_main": title,
        "title_util": f"(utilisation = {util:.2f})" if util is not None else None,
        "title": f"{title} (utilisation = {util:.2f})" if util is not None else title,
        "primary_action": primary_action,
        "secondary_action": secondary_action,
        "reasoning": reasoning,
        "levers": levers,
        "status": status,
        "bucket": bucket,
        "util": util,
        "priority": priority,
        "action_type": action_type,
        "action_payload": action_payload or {},
    }


def _expected_old_projection(
    *,
    reason: str,
    util: float | None,
    mode_config: dict[str, Any],
    blocker: dict[str, Any],
) -> dict[str, Any]:
    item = _controller_guidance_item(
        "shear",
        "Shear cleanup blocked by final efficiency threshold",
        "No second one-click cleanup is enabled after the capacity repair.",
        None,
        f"Why: {reason}",
        "Key checks: shear utilisation threshold, bending, serviceability, detailing",
        None,
        None,
        status="EFFICIENCY",
        util=util,
    )
    contract = {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": "shear",
        "updates": {},
        "preview_pass": False,
        "blocking_reason": reason,
        "source_candidate_id": None,
        "candidate_id": None,
    }
    truth = {
        "display_truth_source": "post_commit_truth",
        "displayed_util": util,
        "displayed_status": "BLOCKED",
        "target_low": mode_config.get("target_low"),
        "target_high": mode_config.get("target_high"),
        "displayed_within_target_band": False,
        "source_summary_util": util,
        "source_candidate_util": None,
        "source_post_commit_util": util,
    }
    item.update(
        {
            "guidance_intent": "specific_blocker",
            "button_contract": dict(contract),
            "display_truth": dict(truth),
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "safe_local_cleanup_count": 0,
            "executable_safe_cleanup_count": 0,
            "terminal_state_blocked_by_local_cleanup": True,
            "local_cleanup_blocked_reasons": [reason],
            "local_cleanup_blocked_reasons_by_family": {"shear": [reason]},
            "exact_blockers_by_family": {"shear": dict(blocker)},
            "post_click_exact_blockers_by_family": {"shear": dict(blocker)},
            "cleanup_evidence_by_family": {"shear": dict(blocker)},
            "post_click_cleanup_evidence_by_family": {"shear": dict(blocker)},
            "candidate_search_evidence": {
                "candidate_search_exhaustive": True,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": True,
                "safe_local_cleanup_count": 0,
                "executable_safe_cleanup_count": 0,
                "safe_shear_cleanup_count": 0,
                "executable_shear_cleanup_count": 0,
                "exact_blockers_by_family": {"shear": dict(blocker)},
                "local_cleanup_blocked_reasons": [reason],
                "local_cleanup_blocked_reasons_by_family": {"shear": [reason]},
                "no_second_cta_required": True,
            },
        }
    )
    debug = {
        "guidance_branch": "post_active_repair_shear_cleanup_blocked",
        "selected_action_type": None,
        "selected_title": item.get("title_main"),
        "selected_action_family": "shear",
        "post_click_accepted_green": False,
        "post_click_accepted_green_valid": True,
        "post_click_design_guide_state": "exact_blocker",
        "post_click_safe_local_cleanup_count": 0,
        "post_click_executable_safe_cleanup_count": 0,
        "post_click_unresolved_low_util_families": [],
        "post_click_unresolved_overprovided_families": [],
        "post_click_exact_blockers_by_family": {"shear": dict(blocker)},
        "exact_blockers_by_family": {"shear": dict(blocker)},
        "cleanup_evidence_by_family": {"shear": dict(blocker)},
        "post_click_cleanup_evidence_by_family": {"shear": dict(blocker)},
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "safe_local_cleanup_count": 0,
        "executable_safe_cleanup_count": 0,
        "terminal_state_blocked_by_local_cleanup": True,
        "terminal_state_reason": reason,
        "primary_button_contract": dict(contract),
        "primary_display_truth": dict(truth),
        "primary_card_title": item.get("title_main"),
        "primary_card_intent": "specific_blocker",
        "primary_guidance_intent": "specific_blocker",
    }
    return {
        "item": dict(item),
        "button_contract": dict(contract),
        "display_truth": dict(truth),
        "debug_updates": dict(debug),
    }


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def build_payload() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_post_active_shear_cleanup_blocked_projection,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    core_segment = _function_segment(inputs_source, "_compute_design_guidance_items_core")
    helper_segment = _function_segment(
        controller_source,
        "build_design_guide_controller_post_active_shear_cleanup_blocked_projection",
    )
    case = {
        "reason": "checked shear cleanup route exhausted",
        "util": 0.42,
        "mode_config": {"target_low": 0.85, "target_high": 1.0},
        "blocker": {"reason": "checked shear cleanup route exhausted", "family": "shear"},
    }
    expected = _expected_old_projection(**case)
    actual = build_design_guide_controller_post_active_shear_cleanup_blocked_projection(
        shear_blocker_reason=case["reason"],
        shear_blocker_util=case["util"],
        mode_config=dict(case["mode_config"]),
        shear_blocker=dict(case["blocker"]),
    )
    source_checks = {
        "page_delegates_to_controller": "_build_design_guide_controller_post_active_shear_cleanup_blocked_projection(" in core_segment,
        "page_no_longer_embeds_blocker_item_literal": "blocker_item = _guidance_item(" not in core_segment,
        "page_no_longer_embeds_blocker_contract_literal": "blocker_contract = {" not in core_segment,
        "page_no_longer_embeds_blocker_truth_literal": "blocker_truth = {" not in core_segment,
        "controller_helper_exists": "def build_design_guide_controller_post_active_shear_cleanup_blocked_projection(" in controller_source,
        "controller_helper_exported": '"build_design_guide_controller_post_active_shear_cleanup_blocked_projection"' in controller_source,
        "controller_no_streamlit_import": "import streamlit" not in controller_source and "from streamlit" not in controller_source,
        "helper_no_session_reads": "st.session_state" not in helper_segment,
    }
    status = "PASS" if _stable(expected) == _stable(actual) and all(source_checks.values()) else "FAIL"
    return {
        "schema": "design_guide_compute_post_active_shear_blocker_projection_extraction.v1",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        "status": status,
        "parity": {
            "matches": _stable(expected) == _stable(actual),
            "expected": expected,
            "actual": actual,
        },
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_target": "optimisation_selector_debug_and_legacy_fallback_packaging",
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_compute_post_active_shear_blocker_projection_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_post_active_shear_blocker_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md = [
        "# Design Guide Compute Post-Active Shear Blocker Projection Extraction",
        "",
        "## Executive Summary",
        str(payload["status"]),
        "",
        f"- Parity: {payload['parity']['matches']}",
        "",
        "## Source Checks",
        *[f"- {key}: {value}" for key, value in payload["source_checks"].items()],
        "",
        "## Next Safe Target",
        str(payload["next_safe_target"]),
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = _write(payload)
    print(f"design_guide_compute_post_active_shear_blocker_projection_extraction {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
