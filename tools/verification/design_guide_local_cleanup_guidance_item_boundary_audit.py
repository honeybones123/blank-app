from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_evaluate_local_cleanup_guidance_item"


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return 0, 0, ""
    start_line = source[:start].count("\n") + 1
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    end_line = source[:next_start].count("\n") + 1
    return start_line, end_line, source[start:next_start]


def _capture() -> dict:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    start, end, segment = _function_segment(source, TARGET)
    required_tokens = {
        "page_shell_inputs": [
            "_resolve_recommendation_updates",
            "_updates_match_state",
            "_evaluate_auto_design_candidate",
            "_promote_guidance_item_to_resolved_candidate",
            "_guidance_executor_actionability_contract",
        ],
        "already_extracted_policy_helpers": [
            "_local_cleanup_family_for_updates",
            "_local_cleanup_material_proxy",
            "_local_cleanup_materially_reduces",
        ],
        "pre_preview_policy": [
            "invalid_candidate",
            "candidate_not_actionable",
            "cleanup_no_material_update",
            "cleanup_no_net_material_efficiency",
            "cleanup_increases_geometry_without_section_reduction",
            "cleanup_not_material",
            "active_failure_needs_strengthening",
            "shear_not_below_target",
        ],
        "post_preview_policy": [
            "cleanup_preview_failed",
            "cleanup_preview_not_all_pass",
            "cleanup_preview_has_fail_status",
            "shear_cleanup_does_not_improve_utilisation",
            "cleanup_does_not_move_governing_utilisation_toward_target",
            "cleanup_not_executor_backed",
            "cleanup_not_executable",
        ],
    }
    token_presence = {
        group: {token: token in segment for token in tokens}
        for group, tokens in required_tokens.items()
    }
    classifications = [
        {
            "surface": "detail_default_shape",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController",
            "classification": "controller_owned_pre_preview_policy",
            "difficulty": "LOW",
            "first_safe_slice": "move default detail and pre-preview blocked reason shaping into controller helper",
        },
        {
            "surface": "item/action/update/state-match gate",
            "current_owner": "inputs_page",
            "target_owner": "mixed",
            "classification": "page_collects_inputs_controller_decides_gate",
            "difficulty": "MEDIUM",
            "first_safe_slice": "keep update resolution/state-match callbacks in page; pass booleans and updates to controller gate",
        },
        {
            "surface": "material proxy/materiality gate",
            "current_owner": "mixed",
            "target_owner": "DesignGuideController",
            "classification": "partially_extracted_controller_policy",
            "difficulty": "LOW",
            "first_safe_slice": "reuse extracted proxy/materiality helpers and let controller assemble blocked detail",
        },
        {
            "surface": "candidate evaluation execution",
            "current_owner": "inputs_page",
            "target_owner": "candidate evaluation service later",
            "classification": "unsafe_to_move_yet",
            "difficulty": "HIGH",
            "first_safe_slice": "do not move before candidate evaluation service boundary",
        },
        {
            "surface": "promotion/executor actionability",
            "current_owner": "inputs_page",
            "target_owner": "post-click/apply service later",
            "classification": "page_callback_execution_keep_for_now",
            "difficulty": "HIGH",
            "first_safe_slice": "do not move in local cleanup pre-preview slice",
        },
        {
            "surface": "post-preview acceptance policy",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController",
            "classification": "controller_owned_post_preview_policy_later",
            "difficulty": "MEDIUM",
            "first_safe_slice": "move only after pre-preview gate is extracted and locked",
        },
    ]
    return {
        "schema": "design_guide_local_cleanup_guidance_item_boundary_audit.v1",
        "target": TARGET,
        "line_range": {"start": start, "end": end, "line_count": max(end - start + 1, 0)},
        "token_presence": token_presence,
        "classifications": classifications,
        "decision": "PARTIAL_READY",
        "first_safe_implementation_slice": "extract pre-preview local cleanup gate/detail shaping into DesignGuideController; keep candidate evaluation, promotion, executor actionability, update resolution, and page callbacks in inputs_page.py",
        "stop_conditions": [
            "candidate evaluation output changes",
            "blocked_reason strings change",
            "detail shape changes",
            "CTA/apply semantics change",
            "visible wording changes",
            "family runtime changes",
        ],
    }


def _write_report(path: Path, payload: dict) -> None:
    capture = payload["capture"]
    lines = [
        "# Local Cleanup Guidance Item Boundary Audit",
        "",
        "## Executive Summary",
        capture["decision"],
        "",
        "## Current Helper Responsibilities",
        f"- Target: `{capture['target']}`",
        f"- Line range: `{capture['line_range']['start']}-{capture['line_range']['end']}`",
        f"- Line count: `{capture['line_range']['line_count']}`",
        "",
        "## Page-Owned Design Brain Logic Still Present",
    ]
    for row in capture["classifications"]:
        if row["current_owner"] == "inputs_page" or row["classification"].startswith("controller_owned"):
            lines.append(
                f"- `{row['surface']}`: current=`{row['current_owner']}`, target=`{row['target_owner']}`, class=`{row['classification']}`"
            )
    lines.extend(
        [
            "",
            "## Inputs That Must Stay Page-Shell-Owned",
            "- `_resolve_recommendation_updates(...)` callback execution",
            "- `_updates_match_state(...)` callback execution",
            "- `_evaluate_auto_design_candidate(...)` until candidate evaluation service boundary",
            "- `_promote_guidance_item_to_resolved_candidate(...)` until post-click/apply extraction",
            "- `_guidance_executor_actionability_contract(...)` until apply/actionability extraction",
            "",
            "## Logic That Should Move To DesignGuideController",
            "- default detail shape",
            "- pre-preview blocked reason/detail shaping",
            "- post-preview acceptance policy in a later slice",
            "",
            "## Required Controller Request/Result Shape",
            "- Plain request: item validity, action type, updates, updates-match-state, family, candidate id, proxy values, materiality booleans, overview acceptable, shear cleanup need, current shear util.",
            "- Plain result: `accepted_for_preview`, `blocked_reason`, `detail`, and normalized candidate-state metadata.",
            "",
            "## Parity Verifier Needed",
            "`design_guide_local_cleanup_pre_preview_gate_extraction.py` should prove blocked reasons and detail fields match for invalid item, no action, no updates, no net material efficiency, geometry increase, no material reduction, active failure, shear not below target, and accepted pre-preview cases.",
            "",
            "## First Safe Implementation Slice",
            capture["first_safe_implementation_slice"],
            "",
            "## Stop Conditions",
        ]
    )
    for item in capture["stop_conditions"]:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().replace(microsecond=0).isoformat().replace(":", "-")
    capture = _capture()
    status = "PASS" if capture["decision"] in {"READY", "PARTIAL_READY"} else "FAIL"
    payload = {
        "schema": "design_guide_local_cleanup_guidance_item_boundary_audit.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
    }
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_guidance_item_boundary_audit_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_local_cleanup_guidance_item_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    print(f"design_guide_local_cleanup_guidance_item_boundary_audit {status}")
    print(f"json={json_path}")
    print(f"report={audit_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
