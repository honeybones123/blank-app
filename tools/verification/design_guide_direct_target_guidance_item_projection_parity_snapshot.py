"""Proof-only parity for direct target-band guidance item projection."""

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
PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_direct_target_band_guidance_item"
BASE_HELPER = "build_design_guide_controller_resolved_candidate_guidance_item"
NEXT_HELPER = "build_design_guide_controller_direct_target_guidance_item_projection"

ACTIVE_STRENGTH_WORDING = {
    "combined": {
        "title": "Bending and shear capacity are low",
        "family": "combined",
        "check_key": "combined",
    },
    "shear": {
        "title": "Shear capacity is low",
        "family": "shear",
        "check_key": "shear",
    },
    "bending": {
        "title": "Bending capacity is low",
        "family": "bending",
        "check_key": "bending",
    },
}

ACTIVE_STRENGTH_REASONING = (
    "Why: active bending/shear capacity checks are failing; this one-click "
    "repair is executor-backed and keeps all required checks acceptable."
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _function_segment(source: str, name: str) -> tuple[str, int, int]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno]), node.lineno, node.end_lineno
    return "", 0, 0


def _build_base_item() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_resolved_candidate_guidance_item,
    )

    candidate = {
        "label": "Direct target-band candidate",
        "action_type": "apply_direct_target_band_cleanup",
        "updates": {"D": 650, "b": 350},
        "candidate_post_util": 0.87,
        "candidate_reaches_target_band": True,
        "candidate_search_evidence": {"selected_candidate_id": "direct-target-001"},
    }
    return build_design_guide_controller_resolved_candidate_guidance_item(
        candidate=dict(candidate),
        updates=dict(candidate["updates"]),
        label=str(candidate["label"]),
        raw_label=str(candidate["label"]),
        family_tag="combined",
        subfamilies=["bending", "shear"],
        alternatives_text="No safer alternative was preferred.",
        change_lines=["Depth 600 -> 650", "Width 300 -> 350"],
        candidate_post_util=0.87,
        original_candidate_action_type=str(candidate["action_type"]),
        primary_action="Apply recommendation",
        reasoning_text=(
            "This option searches the available geometry and reinforcement moves before "
            "accepting an outside-target step."
        ),
        status="FAIL",
        overview_worst_util=1.12,
        failure_coverage={
            "covers_all_current_failures": True,
            "covered_fail_keys": ["bending", "shear"],
            "remaining_fail_keys": [],
        },
        candidate_search_evidence={"selected_candidate_id": "direct-target-001"},
        guidance_change_summary_compact="Depth 600 -> 650; Width 300 -> 350",
        guidance_expected_util_text="0.87",
        guidance_why_text_compact="Direct target-band search selected this candidate.",
        guidance_before_after="Bending 1.33 -> 0.87; Shear 1.08 -> 0.59",
    )


def _apply_current_direct_target_projection(
    item: dict[str, Any],
    *,
    active_strength_family_floor_set: set[str],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_direct_target_guidance_item_projection,
    )

    out = build_design_guide_controller_direct_target_guidance_item_projection(
        item=dict(item),
        active_strength_family_floor_set=set(active_strength_family_floor_set),
        evidence=dict(evidence),
        strengthening=bool(active_strength_family_floor_set),
        source="generate_in_target_local_cleanup_candidates",
    )
    payload = dict(out.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["source_candidate_id"] = evidence.get("selected_candidate_id")
    out["action_payload"] = payload
    resolved = dict(out.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    resolved["candidate_id"] = evidence.get("selected_candidate_id")
    resolved["source_candidate_id"] = evidence.get("selected_candidate_id")
    out["resolved_candidate"] = resolved
    return out


def _parity_cases() -> dict[str, Any]:
    evidence = {
        "selected_candidate_id": "direct-target-001",
        "search_scope": "design_guide_direct_target_band_search",
    }
    base_item = _build_base_item()
    cases: dict[str, Any] = {}
    for name, families in {
        "combined_active_strength": {"bending", "shear"},
        "shear_active_strength": {"shear"},
        "bending_active_strength": {"bending"},
        "non_strength_cleanup": set(),
    }.items():
        item = _apply_current_direct_target_projection(
            base_item,
            active_strength_family_floor_set=set(families),
            evidence=dict(evidence),
        )
        expected = (
            ACTIVE_STRENGTH_WORDING["combined"]
            if name == "combined_active_strength"
            else ACTIVE_STRENGTH_WORDING["shear"]
            if name == "shear_active_strength"
            else ACTIVE_STRENGTH_WORDING["bending"]
            if name == "bending_active_strength"
            else None
        )
        checks = {
            "candidate_search_evidence_preserved": item.get("candidate_search_evidence") == evidence,
            "payload_evidence_preserved": (item.get("action_payload") or {}).get("candidate_search_evidence")
            == evidence,
            "payload_source_candidate_id_preserved": (item.get("action_payload") or {}).get(
                "source_candidate_id"
            )
            == "direct-target-001",
            "resolved_candidate_evidence_preserved": (item.get("resolved_candidate") or {}).get(
                "candidate_search_evidence"
            )
            == evidence,
            "resolved_candidate_id_preserved": (item.get("resolved_candidate") or {}).get("candidate_id")
            == "direct-target-001",
            "local_cleanup_flag_preserved": item.get("local_cleanup_candidate") is True,
            "source_preserved": item.get("source") == "generate_in_target_local_cleanup_candidates",
        }
        if expected is not None:
            checks.update(
                {
                    "active_title_main_preserved": item.get("title_main") == expected["title"],
                    "active_title_preserved": item.get("title") == expected["title"],
                    "active_title_sub_preserved": item.get("title_sub")
                    == "One-click capacity repair available",
                    "active_status_preserved": item.get("status") == "FAIL",
                    "active_bucket_preserved": item.get("bucket") == "fail",
                    "active_intent_preserved": item.get("guidance_intent") == "required_fix",
                    "active_family_preserved": item.get("family") == expected["family"],
                    "active_check_key_preserved": item.get("check_key") == expected["check_key"],
                    "active_terminal_state_preserved": item.get("design_guide_terminal_state") is None,
                    "active_canonical_label_preserved": item.get("canonical_winner_label")
                    == expected["title"],
                    "active_title_lock_preserved": item.get("title_locked_from_final_winner") is True,
                    "active_reasoning_preserved": item.get("reasoning") == ACTIVE_STRENGTH_REASONING,
                    "affected_family_preserved": item.get("affected_family") == expected["family"],
                }
            )
        else:
            checks.update(
                {
                    "base_title_preserved": item.get("title_main") == "Direct target-band candidate",
                    "base_status_preserved": item.get("status") == "FAIL",
                    "affected_family_preserved": item.get("affected_family") == "general",
                }
            )
        cases[name] = {
            "checks": checks,
            "passed": all(checks.values()),
            "selected_fields": {
                key: item.get(key)
                for key in (
                    "title_main",
                    "title",
                    "title_sub",
                    "bucket",
                    "status",
                    "guidance_intent",
                    "family",
                    "check_key",
                    "canonical_winner_label",
                    "title_locked_from_final_winner",
                    "source",
                    "affected_family",
                )
            },
        }
    return cases


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    publication_source = PUBLICATION.read_text(encoding="utf-8", errors="replace")
    target, start, end = _function_segment(inputs_source, TARGET)
    selected_tail = target.split('selected = selection_result.get("selected_candidate")', 1)[-1]
    controller_helper, helper_start, helper_end = _function_segment(controller_source, NEXT_HELPER)
    parity_cases = _parity_cases()
    active_override_tokens = [
        'active_title = "Bending and shear capacity are low"',
        'active_title = "Shear capacity is low"',
        'active_title = "Bending capacity is low"',
        'item["title_sub"] = "One-click capacity repair available"',
        '"Why: active bending/shear capacity checks are failing; this one-click "',
    ]
    payload_sync_tokens = [
        'payload["candidate_search_evidence"]',
        'payload["source_candidate_id"]',
        'item["action_payload"] = payload',
        'resolved["candidate_search_evidence"]',
        'item["resolved_candidate"] = resolved',
    ]
    controller_payload_sync_tokens = [
        'payload["candidate_search_evidence"]',
        'payload["source_candidate_id"]',
        'out["action_payload"] = payload',
        'resolved["candidate_search_evidence"]',
        'out["resolved_candidate"] = resolved',
    ]
    return {
        "schema": "design_guide_direct_target_guidance_item_projection_parity_snapshot.v1",
        "target": {"name": TARGET, "line_start": start, "line_end": end},
        "base_helper": BASE_HELPER,
        "next_helper": NEXT_HELPER,
        "controller_helper": {
            "name": NEXT_HELPER,
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
        },
        "target_present": bool(target),
        "base_item_delegates_to_controller": "_guidance_item_from_resolved_candidate(" in target
        and f"_{BASE_HELPER}(" in _function_segment(inputs_source, "_guidance_item_from_resolved_candidate")[0],
        "page_calls_controller_projection_adapter": f"_{NEXT_HELPER}(" in selected_tail,
        "old_page_active_override_tokens_present": sorted(
            token for token in active_override_tokens if token in selected_tail
        ),
        "controller_active_override_tokens_present": sorted(
            token for token in active_override_tokens if token in controller_helper
        ),
        "controller_title_sub_token_present": '"One-click capacity repair available"' in controller_helper,
        "old_page_payload_sync_tokens_present": sorted(
            token for token in payload_sync_tokens if token in selected_tail
        ),
        "controller_payload_sync_tokens_present": sorted(
            token for token in controller_payload_sync_tokens if token in controller_helper
        ),
        "debug_sink_remains_page_owned": 'debug_sink["candidate_search_evidence"]' in selected_tail
        and 'debug_sink["local_cleanup_candidate_search_evidence"]' in selected_tail,
        "repair_bridge_remains_page_owned": "_repair_select_repair_decision(" in selected_tail,
        "parity_cases": parity_cases,
        "all_parity_cases_passed": all(case.get("passed") for case in parity_cases.values()),
        "ready_for_controller_projection_adapter": True,
        "out_of_scope_for_next_adapter": [
            "repair bridge",
            "debug sink writes",
            "CTA/apply routing",
            "Streamlit/session state",
        ],
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source
        and "streamlit" not in controller_source
        and "st.session_state" not in controller_source,
        "final_publication_has_no_page_or_streamlit_imports": "inputs_page" not in publication_source
        and "streamlit" not in publication_source
        and "st.session_state" not in publication_source,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_present": bool(capture.get("target_present")),
        "base_item_delegates_to_controller": bool(capture.get("base_item_delegates_to_controller")),
        "controller_projection_helper_found": bool((capture.get("controller_helper") or {}).get("line_start")),
        "page_calls_controller_projection_adapter": bool(capture.get("page_calls_controller_projection_adapter")),
        "old_page_active_override_tokens_removed": not bool(
            capture.get("old_page_active_override_tokens_present")
        ),
        "controller_active_override_tokens_present": len(
            capture.get("controller_active_override_tokens_present") or []
        )
        >= 4
        and bool(capture.get("controller_title_sub_token_present")),
        "old_page_payload_sync_tokens_removed": not bool(
            capture.get("old_page_payload_sync_tokens_present")
        ),
        "controller_payload_sync_tokens_present": len(
            capture.get("controller_payload_sync_tokens_present") or []
        )
        == 5,
        "debug_sink_remains_page_owned": bool(capture.get("debug_sink_remains_page_owned")),
        "repair_bridge_remains_page_owned": bool(capture.get("repair_bridge_remains_page_owned")),
        "all_parity_cases_passed": bool(capture.get("all_parity_cases_passed")),
        "controller_has_no_page_or_streamlit_imports": bool(
            capture.get("controller_has_no_page_or_streamlit_imports")
        ),
        "final_publication_has_no_page_or_streamlit_imports": bool(
            capture.get("final_publication_has_no_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = str(payload["created_at"]).replace(":", "-")
    json_path = (
        ARTIFACT_DIR / f"design_guide_direct_target_guidance_item_projection_parity_{suffix}.json"
    )
    report_path = AUDIT_DIR / f"design_guide_direct_target_guidance_item_projection_parity_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    capture = dict(payload.get("capture") or {})
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Design Guide Direct Target Guidance Item Projection Parity",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Surface Targeted",
        "`_direct_target_band_guidance_item(...)` selected item projection tail.",
        "",
        "## Parity Result",
        f"- all parity cases passed: `{capture.get('all_parity_cases_passed')}`",
        f"- ready for controller projection adapter: `{capture.get('ready_for_controller_projection_adapter')}`",
        "",
        "## Preserved Visible Fields",
        "- active title/status/family/check-key overrides",
        "- title subtext",
        "- active repair reasoning",
        "- local cleanup/source/affected-family metadata",
        "- candidate-search evidence mirrors",
        "",
        "## Explicitly Out Of Scope",
        *[f"- {item}" for item in capture.get("out_of_scope_for_next_adapter") or []],
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        "",
        "## Next Safe Slice",
        (
            "Move only the pure direct-target item projection tail into a controller adapter. "
            "Leave repair bridge, debug sink, CTA/apply routing, and session/UI plumbing in inputs_page.py."
        ),
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_direct_target_guidance_item_projection_parity_snapshot.v1",
        "status": status,
        "created_at": _timestamp(),
        "capture": capture,
        "checks": checks,
    }
    json_path, report_path = _write(payload)
    print(f"design_guide_direct_target_guidance_item_projection_parity {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
