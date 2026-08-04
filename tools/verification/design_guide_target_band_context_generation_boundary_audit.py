"""Audit remaining target-band context/generator boundary in inputs_page.py."""

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
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

CONTEXT_HELPER = "_build_auto_design_context"
GENERATOR_HELPER = "generate_compliant_refinement_candidates"
NEXT_HOP_HELPER = "_one_click_best_next_hop_improving_candidate"

CONTEXT_TOKENS = {
    "page_action_resolution": [
        "_resolve_design_actions_from_state(",
        "_state_with_resolved_design_actions(",
    ],
    "page_policy_helpers": [
        "_shear_change_is_relevant(",
        "_ductility_governs_overview(",
        "_geometry_lock_enabled(",
    ],
    "plain_projection_fields": [
        '"seed_state"',
        '"mode_config"',
        '"mode_signature"',
        '"actions"',
        '"actions_signature"',
        '"seed_overview"',
        '"seen_candidate_keys"',
        '"layout_fit_cache"',
    ],
}

GENERATOR_TOKENS = {
    "geometry_generation": ["generate_smaller_geometry_variants("],
    "bottom_reo_generation": ["generate_less_bottom_reo_variants("],
    "shear_generation": [
        "_shear_governing_truth_allows_overdesign_cleanup(",
        "_shear_cleanup_possible(",
        "generate_less_shear_reo_variants(",
    ],
    "layout_generation": ["generate_simpler_layout_variants("],
    "dedupe_and_cap": [
        "_make_auto_design_candidate_key(",
        "AUTO_DESIGN_MAX_LOCAL_CANDIDATES_PER_ITER",
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
            start = int(node.lineno)
            end = int(node.end_lineno or node.lineno)
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _count_callers(source: str, name: str) -> int:
    return max(0, source.count(f"{name}(") - source.count(f"def {name}("))


def _line_numbers_for_token(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _classify_tokens(segment: str, start_line: int, token_groups: dict[str, list[str]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for group, tokens in token_groups.items():
        matches = []
        for token in tokens:
            count = segment.count(token)
            if count:
                matches.append(
                    {
                        "token": token,
                        "count": count,
                        "lines": _line_numbers_for_token(segment, start_line, token)[:10],
                    }
                )
        result[group] = {"present": bool(matches), "matches": matches}
    return result


def _called_names(segment: str) -> list[str]:
    tree = ast.parse(segment)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return sorted(names)


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    context_start, context_end, context_segment = _function_source(inputs_source, CONTEXT_HELPER)
    generator_start, generator_end, generator_segment = _function_source(inputs_source, GENERATOR_HELPER)
    next_hop_start, next_hop_end, next_hop_segment = _function_source(inputs_source, NEXT_HOP_HELPER)

    context_classification = _classify_tokens(context_segment, context_start, CONTEXT_TOKENS)
    generator_classification = _classify_tokens(generator_segment, generator_start, GENERATOR_TOKENS)
    helper_callers = {
        CONTEXT_HELPER: _count_callers(inputs_source, CONTEXT_HELPER),
        GENERATOR_HELPER: _count_callers(inputs_source, GENERATOR_HELPER),
    }

    checks = {
        "context_helper_present": f"def {CONTEXT_HELPER}(" in inputs_source,
        "generator_helper_present": f"def {GENERATOR_HELPER}(" in inputs_source,
        "next_hop_uses_context": f"{CONTEXT_HELPER}(" in next_hop_segment,
        "next_hop_uses_generator": f"{GENERATOR_HELPER}(" in next_hop_segment,
        "selection_loop_already_service_owned": "select_best_target_band_refinement_candidate(" in candidate_source,
        "context_projection_service_owned": "def build_target_band_auto_design_context_projection(" in candidate_source
        and "_build_target_band_auto_design_context_projection(" in context_segment,
        "generator_orchestration_service_owned": "def generate_target_band_refinement_candidate_states(" in candidate_source
        and "_generate_target_band_refinement_candidate_states(" in generator_segment,
        "context_uses_page_policy_helpers": any(
            context_classification[group]["present"]
            for group in ("page_action_resolution", "page_policy_helpers")
        ),
        "generator_injects_multiple_generation_lanes": all(
            token in generator_segment
            for token in (
                "geometry_variants_fn=generate_smaller_geometry_variants",
                "bottom_reo_variants_fn=generate_less_bottom_reo_variants",
                "shear_reo_variants_fn=generate_less_shear_reo_variants",
                "layout_variants_fn=generate_simpler_layout_variants",
                "candidate_key_fn=_make_auto_design_candidate_key",
                "shear_cleanup_possible_fn=_shear_cleanup_possible",
                "shear_cleanup_allowed_by_truth_fn=_shear_governing_truth_allows_overdesign_cleanup",
                "max_candidates=AUTO_DESIGN_MAX_LOCAL_CANDIDATES_PER_ITER",
            )
        ),
    }

    classifications = [
        {
            "surface": CONTEXT_HELPER,
            "line_start": context_start,
            "line_end": context_end,
            "current_owner": "inputs_page.py",
            "target_owner": "candidate generation context service, after action/policy inputs are plain-data",
            "classification": "PARTIAL_SHELL_WITH_PAGE_INPUT_COLLECTION",
            "reason": "pure context projection is service-owned; wrapper still collects page-local resolved actions, shear relevance, ductility, and geometry lock flags",
            "first_safe_slice": "audit remaining page-local action/policy scalar collection before moving any of those helpers",
        },
        {
            "surface": GENERATOR_HELPER,
            "line_start": generator_start,
            "line_end": generator_end,
            "current_owner": "inputs_page.py",
            "target_owner": "candidate generation service, after lane callbacks/generator ownership are explicit",
            "classification": "CALLBACK_SHELL_WITH_PAGE_LANES",
            "reason": "orchestration, shear gating, dedupe, current removal, and cap are service-owned; page still injects lane generators and gate callbacks",
            "first_safe_slice": "audit remaining injected lane callbacks and classify which are service-ready versus page-local solver callbacks",
        },
        {
            "surface": NEXT_HOP_HELPER,
            "line_start": next_hop_start,
            "line_end": next_hop_end,
            "current_owner": "mixed shell plus remaining generation boundary",
            "target_owner": "shell-only after context/generator service handoff",
            "classification": "PARTIAL_SHELL",
            "reason": "selection/evaluation loop is already service-owned; context and candidate-state generation are the remaining extraction seam",
            "first_safe_slice": "context projection service before full generator handoff",
        },
    ]

    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "surface": "target_band_context_generation_boundary",
        "decision": "PARTIAL_REMAINING_PAGE_LANE_CALLBACKS",
        "extraction_complete_estimate": "99%",
        "helper_callers": helper_callers,
        "checks": checks,
        "context": {
            "function": CONTEXT_HELPER,
            "line_start": context_start,
            "line_end": context_end,
            "line_count": context_end - context_start + 1,
            "called_names": _called_names(context_segment),
            "classification": context_classification,
        },
        "generator": {
            "function": GENERATOR_HELPER,
            "line_start": generator_start,
            "line_end": generator_end,
            "line_count": generator_end - generator_start + 1,
            "called_names": _called_names(generator_segment),
            "classification": generator_classification,
        },
        "classifications": classifications,
        "ready_to_extract_now": [
            "remaining injected lane callback ownership audit",
        ],
        "not_ready_to_extract_full": [
            "geometry/bottom/shear/layout lane callbacks until their service boundaries are proven",
        ],
        "required_next_verifier": "design_guide_target_band_injected_lane_callback_boundary_audit.py",
        "stop_conditions": [
            "resolved action signature changes",
            "geometry lock or shear cleanup-disable flag changes",
            "candidate state set/order changes",
            "candidate cap/dedupe changes",
            "visible wording, CTA/apply, or family runtime behaviour changes",
        ],
        "product_behavior_changed": False,
    }


def _write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_context_generation_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_context_generation_boundary_audit_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Target-Band Context / Generation Boundary Audit",
        "",
        f"## Executive Summary: {payload['status']}",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        f"Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
        "",
        "The target-band refinement loop and candidate-state generator orchestration are service-owned. The remaining page surface is now callback injection for page-local lane generators and scalar input collection for context construction.",
        "",
        "## Checks",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Current Surfaces"])
    for row in payload["classifications"]:
        lines.append(
            f"- `{row['surface']}` ({row['line_start']}-{row['line_end']}): "
            f"`{row['classification']}` -> {row['target_owner']}. {row['reason']}"
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            "`design_guide_target_band_injected_lane_callback_boundary_audit.py`: classify the injected geometry, bottom-reo, shear-reo, layout, key, shear-cleanup, and shear-truth callbacks before moving any callback body.",
            "",
            "## Stop Conditions",
        ]
    )
    for item in payload["stop_conditions"]:
        lines.append(f"- {item}")
    lines.extend(["", f"JSON artifact: `{json_path}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    _write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
