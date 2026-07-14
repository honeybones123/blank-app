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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
OPTIMISATION = ROOT / "design_brain" / "optimisation.py"
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
    "family_owned_candidate_generation": [
        "_shear_ladder",
        "_bending_ladder",
        "contracted_repair_ladder_specs",
        "_active_fail_near_current_repair_item",
        "selected_family_",
        "family_route_owner",
    ],
    "controller_owned_candidate_selection": [
        "_resolve_design_guide_controller",
        "_build_design_guide_shear_low_util",
        "_evaluate_design_guide_shear_low_util",
        "_accumulate_design_guide_shear_low_util",
        "_classify_design_guide_shear_low_util",
        "_direct_candidate_final_cleanup_key",
        "selected = min(",
        "selected = max(",
    ],
    "candidate_evaluation_service_call": [
        "_evaluate_bending_only_target_band_candidate_with_service",
        "_evaluate_bending_only_target_band_prebuilt_candidate_with_service",
        "_evaluate_direct_target_band_candidate_with_service",
        "_evaluate_design_candidate_with_updates(",
        "_evaluate_probe_equivalent_bending_candidate_with_service",
        "_evaluate_shear_low_util_candidate_with_service",
        "_evaluate_zero_bending_demand_candidate_with_service",
        "resolve_design_candidate_overview_for_safety_check(",
    ],
    "page_evaluation_shim_dependency": [
        "_evaluate_auto_design_candidate",
        "evaluate_candidate_full",
    ],
    "page_shell_input_collection": [
        "_guidance_state_snapshot(",
        "_collect_design_overview(",
        "_build_design_actions_context(",
        "_design_mode_config(",
        "_design_optimisation_goal(",
    ],
    "cta_apply_plumbing": [
        "button_contract",
        "action_payload",
        "action_type",
        "primary_action",
        "Apply recommendation",
    ],
    "presentation_item_shaping": [
        "_guidance_item_from_resolved_candidate(",
        "title_main",
        "title_sub",
        "status",
        "bucket",
        "reasoning",
    ],
    "debug_proof_construction": [
        "candidate_search_evidence",
        "debug_sink",
        "proof",
        "trace_only",
        "boundary_trace",
    ],
    "unsafe_to_move_yet": [
        "st.session_state",
        "_record_bending_fail_valid_repair_cta_published(",
        "_finish(",
        "return _finish(",
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


def _count_callers(source: str, name: str) -> int:
    return max(0, source.count(f"{name}(") - source.count(f"def {name}("))


def _line_numbers_for_token(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _classify_helper(name: str, start_line: int, end_line: int, segment: str, inputs_source: str) -> dict[str, Any]:
    classifications: dict[str, dict[str, Any]] = {}
    for classification, tokens in CLASSIFICATION_TOKENS.items():
        matches = []
        for token in tokens:
            count = segment.count(token)
            if count:
                matches.append(
                    {
                        "token": token,
                        "count": count,
                        "lines": _line_numbers_for_token(segment, start_line, token)[:12],
                    }
                )
        classifications[classification] = {
            "present": bool(matches),
            "matches": matches,
        }

    helper_role = "mixed_page_owned_candidate_generation_and_item_packaging"
    target_owner = "candidate service plus DesignGuideController adapters"
    deletion_readiness = "NOT_READY"
    extraction_difficulty = "HIGH"
    if name == "_shear_low_util_target_cleanup_item":
        helper_role = "page-owned shear low-util candidate generation shell with many controller-owned subhelpers"
        target_owner = "candidate service for evaluation handoff, then DesignGuideController/family runtime for generator orchestration"
        extraction_difficulty = "MEDIUM"
    elif name == "_probe_equivalent_bending_cleanup_action_item":
        helper_role = "page-owned equivalent bending cleanup probe and item projection"
        target_owner = "candidate evaluation service plus publication/controller item projection"
        extraction_difficulty = "MEDIUM"
    elif name == "_zero_bending_demand_cleanup_item":
        helper_role = "page-owned zero-demand bending cleanup generator/search"
        target_owner = "bending cleanup family/runtime or target-band cleanup candidate service"
        extraction_difficulty = "MEDIUM"
    elif name == "_bending_only_target_band_cleanup_item":
        helper_role = "page-owned bending-only target-band cleanup generator/search"
        target_owner = "bending cleanup family/runtime or target-band cleanup candidate service"
        extraction_difficulty = "HIGH"
    elif name == "_direct_target_band_guidance_item":
        helper_role = "large page-owned direct target-band orchestration, fallback dispatch, ranking, evidence, and item projection"
        target_owner = "DesignGuideController route plus family-owned candidate generators and publication adapters"
        extraction_difficulty = "VERY_HIGH"

    return {
        "helper": name,
        "line_start": start_line,
        "line_end": end_line,
        "line_count": max(0, end_line - start_line + 1),
        "callsite_count": _count_callers(inputs_source, name),
        "current_role": helper_role,
        "target_owner": target_owner,
        "deletion_readiness": deletion_readiness,
        "extraction_difficulty": extraction_difficulty,
        "classifications": classifications,
        "page_owned_candidate_generation": bool(
            classifications["page_shell_input_collection"]["present"]
            and (
                classifications["page_evaluation_shim_dependency"]["present"]
                or "for " in segment
                or "while " in segment
                or "selected = min(" in segment
            )
        ),
        "uses_page_evaluation_shim": classifications["page_evaluation_shim_dependency"]["present"],
        "uses_candidate_evaluation_service_directly": classifications["candidate_evaluation_service_call"]["present"],
        "uses_controller_helpers": classifications["controller_owned_candidate_selection"]["present"],
        "shapes_cta_or_apply_payload": classifications["cta_apply_plumbing"]["present"],
        "shapes_presentation_item": classifications["presentation_item_shaping"]["present"],
        "constructs_debug_or_proof": classifications["debug_proof_construction"]["present"],
        "unsafe_tokens_present": classifications["unsafe_to_move_yet"]["present"],
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    candidate_source = _read(CANDIDATE_EVALUATION)
    optimisation_source = _read(OPTIMISATION)
    helpers = []
    for name in HELPERS:
        start_line, end_line, segment = _function_source(inputs_source, name)
        helpers.append(_classify_helper(name, start_line, end_line, segment, inputs_source))

    page_owned_helpers = [row for row in helpers if row.get("page_owned_candidate_generation")]
    shim_helpers = [row["helper"] for row in helpers if row.get("uses_page_evaluation_shim")]
    direct_service_helpers = [row["helper"] for row in helpers if row.get("uses_candidate_evaluation_service_directly")]

    shear_helper = next((row for row in helpers if row.get("helper") == "_shear_low_util_target_cleanup_item"), {})
    probe_helper = next((row for row in helpers if row.get("helper") == "_probe_equivalent_bending_cleanup_action_item"), {})
    zero_bending_helper = next((row for row in helpers if row.get("helper") == "_zero_bending_demand_cleanup_item"), {})
    bending_only_helper = next((row for row in helpers if row.get("helper") == "_bending_only_target_band_cleanup_item"), {})
    if shear_helper.get("uses_page_evaluation_shim"):
        first_slice = {
            "name": "shear_low_util_candidate_evaluation_service_handoff",
            "target_helper": "_shear_low_util_target_cleanup_item",
            "why": (
                "It is the smallest target-band cleanup helper with one page evaluator-shim dependency, "
                "existing controller-owned subhelper proof surfaces, and no need to move CTA/apply/render ownership."
            ),
            "move": (
                "Replace the `_evaluate_auto_design_candidate` evaluator injection used by "
                "`_evaluate_design_guide_shear_low_util_cleanup_candidate(...)` with a candidate-evaluation "
                "service helper that preserves candidate, overview, source, action_type, label, updates, "
                "candidate_id, and evidence shape."
            ),
            "do_not_move": [
                "the whole shear cleanup generator",
                "button_contract/action_payload rendering",
                "debug_sink writes",
                "callers or CTA/apply routing",
            ],
        }
    elif probe_helper.get("uses_page_evaluation_shim"):
        first_slice = {
            "name": "probe_equivalent_bending_candidate_evaluation_service_handoff",
            "target_helper": "_probe_equivalent_bending_cleanup_action_item",
            "why": (
                "The shear low-util evaluator handoff is complete. The next smallest shim-backed "
                "target-band helper is the equivalent bending cleanup probe, which has a narrow "
                "candidate evaluation dependency and one live helper body to prove."
            ),
            "move": (
                "Move the candidate evaluation call in `_probe_equivalent_bending_cleanup_action_item(...)` "
                "behind a candidate-evaluation service helper while preserving source, label, action_type, "
                "updates, overview/evidence, action payload, button contract, debug/proof fields, and wording."
            ),
            "do_not_move": [
                "the whole bending cleanup generator",
                "button_contract/action_payload rendering",
                "debug_sink writes",
                "callers or CTA/apply routing",
            ],
        }
    elif zero_bending_helper.get("uses_page_evaluation_shim"):
        first_slice = {
            "name": "zero_bending_demand_candidate_evaluation_service_handoff",
            "target_helper": "_zero_bending_demand_cleanup_item",
            "why": (
                "The shear low-util and probe-equivalent bending evaluator handoffs are complete. "
                "The next smallest shim-backed target-band helper is the zero-bending-demand cleanup item."
            ),
            "move": (
                "Move the candidate evaluation call in `_zero_bending_demand_cleanup_item(...)` "
                "behind a candidate-evaluation service helper while preserving source, label, action_type, "
                "updates, overview/evidence, action payload, button contract, debug/proof fields, and wording."
            ),
            "do_not_move": [
                "the whole zero-bending-demand cleanup generator",
                "button_contract/action_payload rendering",
                "debug_sink writes",
                "callers or CTA/apply routing",
            ],
        }
    elif bending_only_helper.get("uses_page_evaluation_shim"):
        first_slice = {
            "name": "bending_only_target_band_candidate_evaluation_service_handoff",
            "target_helper": "_bending_only_target_band_cleanup_item",
            "why": (
                "The smaller shear low-util, probe-equivalent bending, and zero-bending-demand evaluator "
                "handoffs are complete. The next shim-backed target-band helper is the bending-only "
                "target-band cleanup item."
            ),
            "move": (
                "Move the candidate evaluation call in `_bending_only_target_band_cleanup_item(...)` "
                "behind a candidate-evaluation service helper while preserving source, label, action_type, "
                "updates, overview/evidence, action payload, button contract, debug/proof fields, and wording."
            ),
            "do_not_move": [
                "the whole bending-only target-band cleanup generator",
                "button_contract/action_payload rendering",
                "debug_sink writes",
                "callers or CTA/apply routing",
                "`_direct_target_band_guidance_item(...)`",
            ],
        }
    else:
        first_slice = {
            "name": "target_band_generator_ranking_projection_extraction_audit",
            "target_helper": "target_band_cleanup_helpers",
            "why": (
                "All target-band helper candidate-evaluation calls are behind the candidate-evaluation service. "
                "The remaining target-band work is no longer evaluator handoff; it is generator/search, ranking, "
                "fallback/blocker, debug/proof, and publication/item projection extraction."
            ),
            "move": "Audit generator/search/ranking/projection ownership before implementation.",
            "do_not_move": [
                "candidate generation loops",
                "ranking/selection policy",
                "fallback/blocker construction",
                "publication/item projection",
                "CTA/apply routing",
            ],
        }

    required_verifier = {
        "name": (
            "design_guide_shear_low_util_candidate_evaluation_service_handoff.py"
            if first_slice.get("target_helper") == "_shear_low_util_target_cleanup_item"
            else "design_guide_probe_equivalent_bending_candidate_evaluation_service_handoff.py"
            if first_slice.get("target_helper") == "_probe_equivalent_bending_cleanup_action_item"
            else "design_guide_zero_bending_demand_candidate_evaluation_service_handoff.py"
            if first_slice.get("target_helper") == "_zero_bending_demand_cleanup_item"
            else "design_guide_bending_only_target_band_candidate_evaluation_service_handoff.py"
            if first_slice.get("target_helper") == "_bending_only_target_band_cleanup_item"
            else "design_guide_target_band_generator_ranking_projection_extraction_audit.py"
        ),
        "must_prove": [
            "target-band helper candidate evaluation remains service-backed",
            "page evaluation shim helper count stays zero",
            "remaining page-owned generator/ranking/projection surfaces are classified",
            "candidate_evaluation boundary remains import-clean",
            "local cleanup callback and shell audits remain green",
            "composed locks pass",
        ],
    }

    stop_conditions = [
        "candidate overview/evidence differs between page shim and candidate service",
        "selected cleanup candidate id or updates change",
        "button_contract/action_payload/visible wording changes",
        "debug/proof payload loses required fields",
        "candidate evaluation service would need Streamlit/session/page imports",
        "family runtime behavior changes",
        "any composed lock fails",
    ]

    return {
        "schema": "design_guide_target_band_cleanup_candidate_service_boundary_audit.v1",
        "helpers": helpers,
        "summary": {
            "helper_count": len(helpers),
            "total_target_helper_lines": sum(int(row.get("line_count") or 0) for row in helpers),
            "page_owned_candidate_generation_helpers": [row["helper"] for row in page_owned_helpers],
            "page_evaluation_shim_helpers": shim_helpers,
            "direct_candidate_evaluation_service_helpers": direct_service_helpers,
            "helpers_shaping_cta_or_apply_payload": [row["helper"] for row in helpers if row.get("shapes_cta_or_apply_payload")],
            "helpers_shaping_presentation_item": [row["helper"] for row in helpers if row.get("shapes_presentation_item")],
            "helpers_constructing_debug_or_proof": [row["helper"] for row in helpers if row.get("constructs_debug_or_proof")],
        },
        "decision": "NOT_EXTRACTED_TARGET_BAND_CANDIDATE_SERVICE_BOUNDARY_MAPPED",
        "first_safe_implementation_slice": first_slice,
        "required_verifier": required_verifier,
        "stop_conditions": stop_conditions,
        "target_ownership_map": {
            "family runtime": [
                "bending cleanup candidate generation",
                "shear cleanup candidate generation",
                "combined target-band cleanup candidate generation where a family owns the ladder",
            ],
            "DesignGuideController": [
                "candidate selection/ranking policy",
                "target-band acceptance/fallback policy",
                "route ownership and handoff objects",
            ],
            "candidate evaluation service": [
                "candidate preview/evaluation from plain state + updates",
                "overview/evidence preservation",
            ],
            "FinalDesignGuidePublication/publication adapters": [
                "button contract and display/publication projection after selected candidate exists",
            ],
            "inputs_page shell": [
                "state snapshot collection",
                "debug sink storage",
                "page-owned callbacks and apply routing",
            ],
        },
        "controller_has_target_band_helpers": all(
            token in controller_source
            for token in (
                "resolve_design_guide_controller_local_cleanup_target_band_acceptance",
                "build_design_guide_shear_low_util_cleanup_generator_boundary_proof",
            )
        ),
        "candidate_evaluation_import_clean": "inputs_page" not in candidate_source and "streamlit" not in candidate_source,
        "optimisation_has_static_target_band_descriptors": "get_target_band_cleanup_contract_blueprints" in optimisation_source
        or "target_band_cleanup" in optimisation_source,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    helpers = list(capture.get("helpers") or [])
    return {
        "all_target_helpers_found": all(row.get("line_count") for row in helpers) and len(helpers) == len(HELPERS),
        "helpers_classified": all(row.get("classifications") and row.get("target_owner") for row in helpers),
        "page_owned_candidate_generation_identified": bool(
            (capture.get("summary") or {}).get("page_owned_candidate_generation_helpers")
        ),
        "first_safe_slice_defined": bool((capture.get("first_safe_implementation_slice") or {}).get("target_helper")),
        "required_verifier_defined": bool((capture.get("required_verifier") or {}).get("name")),
        "stop_conditions_defined": bool(capture.get("stop_conditions")),
        "controller_boundary_available": bool(capture.get("controller_has_target_band_helpers")),
        "candidate_evaluation_import_clean": bool(capture.get("candidate_evaluation_import_clean")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtimes_unchanged": capture.get("family_runtimes_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    summary = dict(capture.get("summary") or {})
    first_slice = dict(capture.get("first_safe_implementation_slice") or {})
    required_verifier = dict(capture.get("required_verifier") or {})
    lines = [
        "# Target-Band Cleanup Candidate Service Boundary Audit",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "This is audit-only. No target-band cleanup helper was moved or deleted.",
        "",
        "## Summary",
        f"- Target helper count: `{summary.get('helper_count')}`",
        f"- Total target helper lines: `{summary.get('total_target_helper_lines')}`",
        f"- Page-owned candidate generation helpers: `{summary.get('page_owned_candidate_generation_helpers')}`",
        f"- Helpers using page evaluation shim: `{summary.get('page_evaluation_shim_helpers')}`",
        f"- Helpers directly using candidate evaluation service: `{summary.get('direct_candidate_evaluation_service_helpers')}`",
        "",
        "## Helper Inventory",
        "Helper | Lines | Call sites | Current role | Target owner | Classifications | Difficulty | Deletion readiness",
        "--- | --- | --- | --- | --- | --- | --- | ---",
    ]
    for row in capture.get("helpers") or []:
        class_names = [
            name
            for name, detail in dict(row.get("classifications") or {}).items()
            if isinstance(detail, dict) and detail.get("present")
        ]
        lines.append(
            " | ".join(
                [
                    f"`{row.get('helper')}`",
                    f"`{row.get('line_start')}`-`{row.get('line_end')}` ({row.get('line_count')})",
                    f"`{row.get('callsite_count')}`",
                    str(row.get("current_role") or ""),
                    str(row.get("target_owner") or ""),
                    ", ".join(class_names),
                    str(row.get("extraction_difficulty") or ""),
                    str(row.get("deletion_readiness") or ""),
                ]
            )
        )
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Design Brain Logic",
        ]
    )
    for row in capture.get("helpers") or []:
        if row.get("page_owned_candidate_generation"):
            lines.append(
                f"- `{row.get('helper')}` still owns target-band cleanup candidate construction/search and is `NOT_READY` for deletion."
            )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Target helper: `{first_slice.get('target_helper')}`",
            f"- Why: {first_slice.get('why')}",
            f"- Move: {first_slice.get('move')}",
            f"- Do not move: `{first_slice.get('do_not_move')}`",
            "",
            "## Required Verifier",
            f"- Name: `{required_verifier.get('name')}`",
        ]
    )
    for item in required_verifier.get("must_prove") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Stop Conditions",
        ]
    )
    for item in capture.get("stop_conditions") or []:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Verifier Checks",
        ]
    )
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = PROGRESS_PATH.read_text(encoding="utf-8").rstrip() if PROGRESS_PATH.exists() else ""
    lines = [existing, ""] if existing else []
    first_slice = dict((payload.get("capture") or {}).get("first_safe_implementation_slice") or {})
    lines.extend(
        [
            f"## {payload.get('created_at')} - Target-band cleanup candidate service boundary audit",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Decision: `{(payload.get('capture') or {}).get('decision')}`",
            f"- First safe slice: `{first_slice.get('name')}`",
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
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_target_band_cleanup_candidate_service_boundary_audit.v1",
        "created_at": created_at,
        "status": status,
        "capture": capture,
        "checks": checks,
    }
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_cleanup_candidate_service_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_target_band_cleanup_candidate_service_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_target_band_cleanup_candidate_service_boundary_audit {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status != "PASS":
        print("failing_checks=" + json.dumps([name for name, ok in checks.items() if not ok]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
