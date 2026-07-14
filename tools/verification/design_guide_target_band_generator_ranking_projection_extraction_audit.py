from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

HELPERS = [
    "_zero_bending_demand_cleanup_item",
    "_probe_equivalent_bending_cleanup_action_item",
    "_bending_only_target_band_cleanup_item",
    "_shear_low_util_target_cleanup_item",
    "_direct_target_band_guidance_item",
]

CLASSIFICATION_TOKENS = {
    "candidate_generation": [
        "for ",
        "while ",
        "width_trials",
        "depth_trials",
        "raw_updates",
        "update_trials",
        "rows.append(",
        "candidates.append(",
        "generate_less_shear_reo_variants(",
        "_generate_local_bottom_arrangements(",
        "_generate_escalated_shear_states(",
    ],
    "candidate_evaluation_service": [
        "_evaluate_shear_low_util_candidate_with_service(",
        "_evaluate_probe_equivalent_bending_candidate_with_service(",
        "_evaluate_zero_bending_demand_candidate_with_service(",
        "_evaluate_bending_only_target_band_candidate_with_service(",
        "_evaluate_bending_only_target_band_prebuilt_candidate_with_service(",
        "_evaluate_direct_target_band_candidate_with_service(",
    ],
    "page_evaluation_shim": [
        "_evaluate_auto_design_candidate(",
        "evaluate_candidate_full(",
    ],
    "ranking_selection": [
        "selected = min(",
        "selected = max(",
        "safe_candidates",
        "target_candidates",
        "fallback_pool",
        "_direct_candidate_final_cleanup_key(",
        "_select_direct_target_item(",
    ],
    "blocker_fallback_policy": [
        "_bounded_proof_blocker_item(",
        "_active_failure_no_target_blocker_item(",
        "return None",
        "rejection_reason",
        "blocked",
        "proof_exhausted",
    ],
    "publication_projection": [
        "_guidance_item_from_resolved_candidate(",
        "item[\"action_payload\"]",
        "item[\"resolved_candidate\"]",
        "candidate_search_evidence",
        "primary_action",
        "title=",
        "reasoning=",
    ],
    "debug_proof": [
        "debug_sink",
        "candidate_search_evidence",
        "trace",
        "proof",
        "audit",
    ],
    "page_session_or_cache": [
        "st.session_state",
        "get_rerun_pure_cache(",
        "set_rerun_pure_cache(",
        "_inputs_pre_widget_trace(",
    ],
    "controller_service_already_used": [
        "_resolve_design_guide_controller_",
        "_build_design_guide_controller_",
        "_evaluate_design_guide_",
    ],
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node.lineno, int(node.end_lineno or node.lineno), "\n".join(lines[node.lineno - 1 : int(node.end_lineno or node.lineno)])
    return 0, 0, ""


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _classify(segment: str, start_line: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, tokens in CLASSIFICATION_TOKENS.items():
        matches = []
        for token in tokens:
            count = segment.count(token)
            if count:
                matches.append({"token": token, "count": count, "lines": _line_numbers(segment, start_line, token)[:16]})
        out[name] = {"present": bool(matches), "matches": matches}
    return out


def _helper_target_owner(name: str) -> str:
    if name == "_shear_low_util_target_cleanup_item":
        return "DesignGuideController plus shear cleanup candidate-generation service"
    if name in {"_zero_bending_demand_cleanup_item", "_probe_equivalent_bending_cleanup_action_item", "_bending_only_target_band_cleanup_item"}:
        return "DesignGuideController plus bending/target-band cleanup candidate-generation service"
    if name == "_direct_target_band_guidance_item":
        return "DesignGuideController route plus family/runtime candidate generators and publication adapters"
    return "DesignGuideController"


def _capture() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    helpers = []
    for name in HELPERS:
        start, end, segment = _function_source(source, name)
        classifications = _classify(segment, start)
        helpers.append(
            {
                "helper": name,
                "line_start": start,
                "line_end": end,
                "line_count": max(0, end - start + 1),
                "target_owner": _helper_target_owner(name),
                "candidate_evaluation_service_backed": classifications["candidate_evaluation_service"]["present"],
                "zero_bending_update_trial_generation_service_backed": (
                    name == "_zero_bending_demand_cleanup_item"
                    and "_build_zero_bending_demand_cleanup_update_trials(" in segment
                    and "def _material_proxy" not in segment
                    and "for width in width_trials" not in segment
                ),
                "probe_equivalent_candidate_generation_service_backed": (
                    name == "_probe_equivalent_bending_cleanup_action_item"
                    and "_build_probe_equivalent_bending_cleanup_candidate_inputs(" in segment
                    and "rows.append(" not in segment
                    and "current_area_key" not in segment
                ),
                "bending_only_update_trial_generation_service_backed": (
                    name == "_bending_only_target_band_cleanup_item"
                    and "_build_bending_only_target_band_cleanup_update_trials(" in segment
                    and "def _append_update" not in segment
                    and "def _append_geometry_bottom_update" not in segment
                    and "for trial_width in width_trials" not in segment
                ),
                "direct_target_ladder_generation_service_backed": (
                    name == "_direct_target_band_guidance_item"
                    and "_build_direct_target_band_ladder_stage_update_attempts(" in segment
                    and '_service_stage_updates("strengthen_shear_nearby")' in segment
                    and '_service_stage_updates("cleanup_geometry_nearby")' in segment
                    and "shear_updates.append((f\"reduce link spacing" not in segment
                    and "geometry_updates.append((f\"reduce depth" not in segment
                ),
                "page_evaluation_shim_present": classifications["page_evaluation_shim"]["present"],
                "candidate_generation_present": classifications["candidate_generation"]["present"],
                "ranking_selection_present": classifications["ranking_selection"]["present"],
                "blocker_fallback_policy_present": classifications["blocker_fallback_policy"]["present"],
                "publication_projection_present": classifications["publication_projection"]["present"],
                "debug_proof_present": classifications["debug_proof"]["present"],
                "page_session_or_cache_present": classifications["page_session_or_cache"]["present"],
                "controller_service_already_used": classifications["controller_service_already_used"]["present"],
                "classifications": classifications,
                "extraction_difficulty": (
                    "LOW"
                    if name == "_probe_equivalent_bending_cleanup_action_item"
                    else "MEDIUM"
                    if name in {"_zero_bending_demand_cleanup_item", "_shear_low_util_target_cleanup_item"}
                    else "HIGH"
                    if name == "_bending_only_target_band_cleanup_item"
                    else "VERY_HIGH"
                ),
                "deletion_readiness": "NOT_READY",
            }
        )

    zero_trial_generation_service_backed = any(
        bool(helper.get("zero_bending_update_trial_generation_service_backed")) for helper in helpers
    )
    probe_candidate_generation_service_backed = any(
        bool(helper.get("probe_equivalent_candidate_generation_service_backed")) for helper in helpers
    )
    bending_only_generation_service_backed = any(
        bool(helper.get("bending_only_update_trial_generation_service_backed")) for helper in helpers
    )
    direct_ladder_generation_service_backed = any(
        bool(helper.get("direct_target_ladder_generation_service_backed")) for helper in helpers
    )
    if (
        zero_trial_generation_service_backed
        and probe_candidate_generation_service_backed
        and bending_only_generation_service_backed
        and direct_ladder_generation_service_backed
    ):
        first_safe_slice = {
            "name": "direct_target_band_broad_search_generation_or_ranking_policy_audit",
            "target_helper": "_direct_target_band_guidance_item",
            "why": (
                "All smaller target-band generation slices are now service-backed. The remaining direct target-band "
                "surface is the broad search/ranking/projection route, which needs a focused audit before extraction."
            ),
            "move": (
                "Audit the broad direct target-band width/depth/bottom/shear search and final ranking policy. Do not "
                "move route orchestration, debug/session diagnostics, item projection, CTA/apply payload, or visible "
                "wording without a separate parity verifier."
            ),
            "do_not_move": [
                "route orchestration",
                "item/action payload projection",
                "debug_sink writes",
                "CTA/apply payload",
                "visible wording",
            ],
            "required_verifier": "design_guide_direct_target_band_broad_search_boundary_audit.py",
        }
    elif zero_trial_generation_service_backed and probe_candidate_generation_service_backed and bending_only_generation_service_backed:
        first_safe_slice = {
            "name": "direct_target_band_candidate_generation_service_boundary",
            "target_helper": "_direct_target_band_guidance_item",
            "why": (
                "Zero-bending, probe-equivalent, and bending-only target-band generation are now service-backed. "
                "The remaining largest generator/search surface is the direct target-band route."
            ),
            "move": (
                "Audit and move only the smallest pure direct-target candidate generation/search preparation surface. "
                "Keep route orchestration, ranking/selection, item projection, debug sink writes, CTA/apply payload, "
                "and visible wording in the page until separate parity exists."
            ),
            "do_not_move": [
                "route orchestration",
                "candidate evaluation service calls",
                "ranking/selection",
                "item/action payload projection",
                "debug_sink writes",
                "CTA/apply payload",
            ],
            "required_verifier": "design_guide_direct_target_band_candidate_generation_boundary.py",
        }
    elif zero_trial_generation_service_backed and probe_candidate_generation_service_backed:
        first_safe_slice = {
            "name": "bending_only_target_band_generation_service_boundary",
            "target_helper": "_bending_only_target_band_cleanup_item",
            "why": (
                "Zero-bending and probe-equivalent candidate generation are now service-backed. The next remaining "
                "bending cleanup generator surface is the bending-only target-band candidate construction/search route."
            ),
            "move": (
                "Move only pure bending-only target-band candidate generation/search preparation into a Design Brain "
                "service helper. Keep evaluation, ranking/selection, item projection, debug sink writes, CTA/apply "
                "payload, and visible wording in the page until separate parity exists."
            ),
            "do_not_move": [
                "candidate evaluation service calls",
                "ranking/selection",
                "item/action payload projection",
                "debug_sink writes",
                "CTA/apply payload",
                "_direct_target_band_guidance_item(...)",
            ],
            "required_verifier": "design_guide_bending_only_target_band_generation_boundary.py",
        }
    elif zero_trial_generation_service_backed:
        first_safe_slice = {
            "name": "probe_equivalent_bending_candidate_generation_service_boundary",
            "target_helper": "_probe_equivalent_bending_cleanup_action_item",
            "why": (
                "Zero-bending update-trial generation is now service-backed. The next smallest remaining "
                "target-band generator surface is the probe-equivalent bending cleanup candidate construction, "
                "which is narrower than the bending-only and direct target-band routes."
            ),
            "move": (
                "Move only pure probe-equivalent bending candidate generation/search preparation into a Design Brain "
                "service helper. Keep candidate evaluation, item projection, debug sink writes, CTA/apply payload, "
                "and visible wording in the page until separate parity exists."
            ),
            "do_not_move": [
                "candidate evaluation service calls",
                "item/action payload projection",
                "debug_sink writes",
                "CTA/apply payload",
                "_direct_target_band_guidance_item(...)",
            ],
            "required_verifier": "design_guide_probe_equivalent_bending_candidate_generation_boundary.py",
        }
    else:
        first_safe_slice = {
            "name": "zero_bending_demand_update_trial_generation_service_boundary",
            "target_helper": "_zero_bending_demand_cleanup_item",
            "why": (
                "Candidate evaluation is already service-backed. The smallest remaining generator/search surface is "
                "the zero-bending-demand update trial construction because it has a compact width/depth/bar/dia "
                "trial loop and no nested recursion or direct route orchestration."
            ),
            "move": (
                "Move only update-trial construction/material-proxy screening into a Design Brain target-band cleanup "
                "candidate-generation helper that accepts plain base state, scalar constants, and geometry-lock results. "
                "Keep item projection, debug sink writes, CTA/apply payload, and selected-candidate packaging in the page "
                "until separate parity exists."
            ),
            "do_not_move": [
                "candidate evaluation service calls",
                "item/action payload projection",
                "debug_sink writes",
                "ranking beyond trial material-proxy screening",
                "_direct_target_band_guidance_item(...)",
            ],
            "required_verifier": "design_guide_zero_bending_demand_update_trial_generation_boundary.py",
        }

    return {
        "schema": "design_guide_target_band_generator_ranking_projection_extraction_audit.v1",
        "helpers": helpers,
        "summary": {
            "helper_count": len(helpers),
            "page_evaluation_shim_helpers": [h["helper"] for h in helpers if h["page_evaluation_shim_present"]],
            "candidate_evaluation_service_backed_helpers": [h["helper"] for h in helpers if h["candidate_evaluation_service_backed"]],
            "candidate_generation_helpers": [h["helper"] for h in helpers if h["candidate_generation_present"]],
            "ranking_selection_helpers": [h["helper"] for h in helpers if h["ranking_selection_present"]],
            "publication_projection_helpers": [h["helper"] for h in helpers if h["publication_projection_present"]],
            "page_session_or_cache_helpers": [h["helper"] for h in helpers if h["page_session_or_cache_present"]],
            "zero_bending_update_trial_generation_service_backed": zero_trial_generation_service_backed,
            "probe_equivalent_candidate_generation_service_backed": probe_candidate_generation_service_backed,
            "bending_only_update_trial_generation_service_backed": bending_only_generation_service_backed,
            "total_target_helper_lines": sum(int(h["line_count"]) for h in helpers),
        },
        "decision": "CANDIDATE_EVALUATION_HANDOFF_COMPLETE_GENERATOR_RANKING_PROJECTION_REMAINS",
        "first_safe_implementation_slice": first_safe_slice,
        "stop_conditions": [
            "generated update trial order changes",
            "selected candidate changes",
            "item/action payload changes",
            "visible wording changes",
            "debug/proof fields change",
            "CTA/apply semantics change",
            "family runtime behavior changes",
            "any composed lock fails",
        ],
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    summary = dict(capture.get("summary") or {})
    return {
        "target_band_page_evaluation_shims_removed": not bool(summary.get("page_evaluation_shim_helpers")),
        "direct_service_backed_helpers_recorded": len(summary.get("candidate_evaluation_service_backed_helpers") or []) >= 4,
        "page_evaluation_shim_count_zero": not bool(summary.get("page_evaluation_shim_helpers")),
        "remaining_generation_surfaces_identified": bool(summary.get("candidate_generation_helpers")),
        "remaining_ranking_surfaces_identified": bool(summary.get("ranking_selection_helpers")),
        "remaining_projection_surfaces_identified": bool(summary.get("publication_projection_helpers")),
        "first_safe_slice_identified": bool((capture.get("first_safe_implementation_slice") or {}).get("name")),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    summary = dict(capture.get("summary") or {})
    first_slice = dict(capture.get("first_safe_implementation_slice") or {})
    lines = [
        "# Target-Band Generator/Ranking/Projection Extraction Audit",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Decision: `{capture.get('decision')}`",
        f"- Page evaluation shim helpers: `{summary.get('page_evaluation_shim_helpers')}`",
        f"- Candidate-evaluation service-backed helpers: `{summary.get('candidate_evaluation_service_backed_helpers')}`",
        f"- Remaining candidate-generation helpers: `{summary.get('candidate_generation_helpers')}`",
        f"- Remaining ranking/selection helpers: `{summary.get('ranking_selection_helpers')}`",
        f"- Remaining publication projection helpers: `{summary.get('publication_projection_helpers')}`",
        "",
        "## Helper Inventory",
        "| Helper | Lines | Target owner | Difficulty | Deletion readiness |",
        "|---|---:|---|---|---|",
    ]
    for helper in list(capture.get("helpers") or []):
        lines.append(
            f"| `{helper.get('helper')}` | {helper.get('line_count')} | {helper.get('target_owner')} | "
            f"{helper.get('extraction_difficulty')} | {helper.get('deletion_readiness')} |"
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Target helper: `{first_slice.get('target_helper')}`",
            f"- Move: {first_slice.get('move')}",
            f"- Required verifier: `{first_slice.get('required_verifier')}`",
            "",
            "## Do Not Move Yet",
        ]
    )
    for item in list(first_slice.get("do_not_move") or []):
        lines.append(f"- {item}")
    lines.extend(["", "## Checks"])
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = PROGRESS_PATH.read_text(encoding="utf-8").rstrip() if PROGRESS_PATH.exists() else ""
    lines = [existing, ""] if existing else []
    lines.extend(
        [
            f"## {payload.get('created_at')} - Target-band generator/ranking/projection extraction audit",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Decision: `{(payload.get('capture') or {}).get('decision')}`",
            f"- Report: [{report_path.name}](../audits/{report_path.name})",
            "",
        ]
    )
    PROGRESS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = _timestamp()
    capture = _capture()
    checks = _checks(capture)
    passed = all(checks.values())
    payload = {
        "schema": "design_guide_target_band_generator_ranking_projection_extraction_audit.v1",
        "created_at": created_at,
        "status": "PASS" if passed else "FAIL",
        "capture": capture,
        "checks": checks,
    }
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_generator_ranking_projection_extraction_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_target_band_generator_ranking_projection_extraction_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_target_band_generator_ranking_projection_extraction_audit {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not passed:
        print("failing_checks=" + json.dumps([name for name, ok in checks.items() if not ok]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
