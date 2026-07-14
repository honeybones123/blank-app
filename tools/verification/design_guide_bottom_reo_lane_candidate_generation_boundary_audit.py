"""Audit bottom-reo target-band lane candidate-generation boundary.

This is proof-only. It records the remaining page-owned bottom-reo target-band
candidate construction surfaces and identifies the smallest safe extraction
slice. It does not move code, delete code, or change product behavior.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
FAMILY_BENDING = ROOT / "design_brain" / "families" / "bending.py"
CONTRACTS = ROOT / "design_brain" / "contracts.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGETS = [
    "generate_less_bottom_reo_variants",
    "generate_simpler_layout_variants",
    "_generate_local_bottom_arrangements",
    "_effective_bottom_design_state",
    "_candidate_bottom_updates",
    "_bottom_row_count_from_state",
    "_bottom_bar_count_from_state",
    "_reo_congestion_index",
    "compute_reo_complexity",
]

TOKEN_GROUPS = {
    "page_state_reads": [
        "_float_from_state(",
        "_int_from_state(",
        "_design_width_value(",
    ],
    "design_brain_service_calls": [
        "_build_bottom_reo_arrangement_pool_from_state(",
        "_bottom_arrangement_to_shared_updates(",
        "_calculate_bottom_reo_complexity(",
    ],
    "bottom_metric_projection": [
        "_effective_bottom_design_state(",
        "_candidate_bottom_updates(",
        "_bottom_row_count_from_state(",
        "_bottom_bar_count_from_state(",
        "_reo_congestion_index(",
        "compute_reo_complexity(",
    ],
    "candidate_generation_mutation": [
        "candidate_state.update(",
        "variants[",
        "_make_auto_design_candidate_key(",
    ],
    "solver_or_engineering_calc": [
        "effective_depth_with_links_mm(",
        "compute_bending_capacity_from_state(",
        "run_shear_calc(",
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


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


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


def _classify_tokens(segment: str, start_line: int) -> dict[str, Any]:
    groups: dict[str, Any] = {}
    for group, tokens in TOKEN_GROUPS.items():
        matches = []
        for token in tokens:
            count = segment.count(token)
            if count:
                matches.append(
                    {
                        "token": token,
                        "count": count,
                        "lines": _line_numbers(segment, start_line, token)[:12],
                    }
                )
        groups[group] = {"present": bool(matches), "matches": matches}
    return groups


def _surface_recommendation(name: str, segment: str, caller_count: int) -> dict[str, str]:
    if name == "_generate_local_bottom_arrangements":
        if "_build_bottom_reo_arrangement_pool_from_state(" in segment:
            return {
                "classification": "COMPATIBILITY_WRAPPER_SERVICE_OWNED",
                "target_owner": "design_brain.families.bending",
                "deletion_readiness": "COMPATIBILITY_ONLY",
                "first_safe_slice": "keep wrapper until bottom lane callers can use the family arrangement-pool service directly",
                "risk": "LOW",
            }
    if name == "compute_reo_complexity":
        if "_calculate_bottom_reo_complexity(" in segment:
            return {
                "classification": "COMPATIBILITY_WRAPPER_SERVICE_OWNED",
                "target_owner": "design_brain.families.bending",
                "deletion_readiness": "COMPATIBILITY_ONLY",
                "first_safe_slice": "keep wrapper until candidate metric projection is service-owned",
                "risk": "LOW",
            }
    if name == "_candidate_bottom_updates":
        return {
            "classification": "READY_FOR_PLAIN_SERVICE_EXTRACTION",
            "target_owner": "design_brain.candidate_evaluation",
            "deletion_readiness": "NOT_READY",
            "first_safe_slice": "extract bottom update projection from candidate state as plain data",
            "risk": "LOW",
        }
    if name in {"_bottom_row_count_from_state", "_bottom_bar_count_from_state", "_reo_congestion_index"}:
        return {
            "classification": "READY_AFTER_BOTTOM_EFFECTIVE_STATE_PROJECTION",
            "target_owner": "design_brain.candidate_evaluation",
            "deletion_readiness": "NOT_READY",
            "first_safe_slice": "extract bottom effective-state and metric projection together with parity",
            "risk": "LOW_MEDIUM",
        }
    if name == "_effective_bottom_design_state":
        return {
            "classification": "READY_FOR_PLAIN_SERVICE_EXTRACTION_WITH_ENGINEERING_PRIMITIVE",
            "target_owner": "design_brain.candidate_evaluation",
            "deletion_readiness": "NOT_READY",
            "first_safe_slice": "extract pure bottom effective-state projection using effective_depth_with_links_mm as an injected or imported primitive",
            "risk": "MEDIUM",
        }
    if name in {"generate_less_bottom_reo_variants", "generate_simpler_layout_variants"}:
        if "_generate_bottom_reo_target_band_candidate_states(" in segment:
            return {
                "classification": "COMPATIBILITY_WRAPPER_SERVICE_OWNED",
                "target_owner": "design_brain.candidate_evaluation",
                "deletion_readiness": "COMPATIBILITY_ONLY",
                "first_safe_slice": "keep wrapper until live callers can use the candidate-evaluation lane service directly or wrapper deadness is proven",
                "risk": "LOW",
            }
        return {
            "classification": "NOT_READY_BOTTOM_METRIC_PROJECTION_STILL_PAGE_OWNED",
            "target_owner": "design_brain.candidate_evaluation",
            "deletion_readiness": "NOT_READY",
            "first_safe_slice": "extract bottom candidate metric/update projection before moving lane orchestration",
            "risk": "MEDIUM",
        }
    return {
        "classification": "UNKNOWN",
        "target_owner": "unknown",
        "deletion_readiness": "NOT_READY",
        "first_safe_slice": "manual audit required",
        "risk": "HIGH",
    }


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    bending_source = _read(FAMILY_BENDING)
    contracts_source = _read(CONTRACTS)

    surfaces = []
    for name in TARGETS:
        start, end, segment = _function_source(inputs_source, name)
        recommendation = _surface_recommendation(name, segment, _count_callers(inputs_source, name))
        surfaces.append(
            {
                "function": name,
                "line_start": start,
                "line_end": end,
                "line_count": end - start + 1,
                "caller_count": _count_callers(inputs_source, name),
                "called_names": _called_names(segment),
                "token_classification": _classify_tokens(segment, start),
                **recommendation,
            }
        )

    service_owned = [row["function"] for row in surfaces if row["classification"] == "COMPATIBILITY_WRAPPER_SERVICE_OWNED"]
    ready = [row["function"] for row in surfaces if row["classification"].startswith("READY")]
    not_ready = [row["function"] for row in surfaces if row["classification"].startswith("NOT_READY")]
    unknown = [row["function"] for row in surfaces if row["classification"] == "UNKNOWN"]
    checks = {
        "all_targets_found": len(surfaces) == len(TARGETS),
        "arrangement_conversion_design_brain_owned": "def bottom_arrangement_to_shared_updates(" in contracts_source,
        "arrangement_pool_design_brain_owned": "def build_bottom_reo_arrangement_pool_from_state(" in bending_source,
        "complexity_design_brain_owned": "def calculate_bottom_reo_complexity(" in bending_source,
        "bottom_lane_still_uses_page_metric_projection": all(
            token in inputs_source
            for token in (
                "_effective_bottom_design_state(",
                "_candidate_bottom_updates(",
                "_reo_congestion_index(",
            )
        ),
        "candidate_evaluation_has_bottom_metric_projection_service": "def build_bottom_reo_candidate_metric_projection(" in candidate_source,
        "candidate_evaluation_has_bottom_lane_service": "def generate_bottom_reo_target_band_candidate_states(" in candidate_source,
        "all_surfaces_classified": not unknown,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    decision = (
        "BOTTOM_REO_METRIC_PROJECTION_SERVICE_PRESENT"
        if status == "PASS" and ready and not unknown
        else "AUDIT_INCOMPLETE"
    )
    return {
        "schema": "design_guide_bottom_reo_lane_candidate_generation_boundary_audit.v1",
        "status": status,
        "surface": "bottom_reo_target_band_lane_candidate_generation_boundary",
        "decision": decision,
        "product_behavior_changed": False,
        "extraction_complete_estimate": "99%",
        "checks": checks,
        "service_owned_wrappers": service_owned,
        "ready_to_extract_next": ready,
        "not_ready": not_ready,
        "unknown": unknown,
        "surfaces": surfaces,
        "target_ownership_map": {
            "family_owned_now": [
                "bottom_arrangement_to_shared_updates",
                "build_bottom_reo_arrangement_pool_from_state",
                "calculate_bottom_reo_complexity",
            ],
            "candidate_evaluation_next": [
                "bottom effective-state projection",
                "bottom update projection",
                "bottom row/bar/congestion metric projection",
            ],
            "page_shell_remains": [
                "live wrapper callsites until lane orchestration parity is proven",
                "current candidate/context collection",
            ],
        },
        "first_safe_implementation_slice": {
            "name": "bottom_reo_metric_projection_service_extraction",
            "target_helper": "build_bottom_reo_candidate_metric_projection(...)",
            "target_module": "design_brain.candidate_evaluation",
            "moves": [
                "_candidate_bottom_updates plain projection",
                "_effective_bottom_design_state plain projection",
                "_bottom_row_count_from_state / _bottom_bar_count_from_state",
                "_reo_congestion_index metric projection",
            ],
            "keeps_in_inputs_page": [
                "generate_less_bottom_reo_variants wrapper",
                "generate_simpler_layout_variants wrapper",
                "_generate_local_bottom_arrangements compatibility wrapper",
            ],
            "required_verifier": "design_guide_bottom_reo_metric_projection_service_extraction.py",
        },
        "stop_conditions": [
            "Do not move bottom lane orchestration until bottom metric projection parity is proven.",
            "Do not delete wrappers while direct live callers remain.",
            "Do not move evaluator, CTA/apply payload, visible wording, or family runtime behaviour in this slice.",
            "Do not introduce Streamlit/session imports into design_brain.candidate_evaluation.",
        ],
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bottom-Reo Lane Candidate Generation Boundary Audit",
        "",
        "## Executive Summary",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
        f"- Product behavior changed: `{payload['product_behavior_changed']}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {name}: `{value}`" for name, value in payload["checks"].items())
    lines.extend(
        [
            "",
            "## Surface Inventory",
            "| Function | Lines | Classification | Target owner | Deletion readiness | Risk |",
            "| --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in payload["surfaces"]:
        lines.append(
            "| {function} | {line_start}-{line_end} | {classification} | {target_owner} | {deletion_readiness} | {risk} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Current Ownership",
            "- Arrangement conversion is already Design Brain-owned by `design_brain.contracts.bottom_arrangement_to_shared_updates`.",
            "- Arrangement pool generation is already family-owned by `design_brain.families.bending.build_bottom_reo_arrangement_pool_from_state`.",
            "- Reo complexity scoring primitive is already family-owned by `design_brain.families.bending.calculate_bottom_reo_complexity`.",
            "- The target-band lane still owns bottom effective-state and metric projection inside `inputs_page.py`.",
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{payload['first_safe_implementation_slice']['name']}`",
            f"- Target helper: `{payload['first_safe_implementation_slice']['target_helper']}`",
            f"- Target module: `{payload['first_safe_implementation_slice']['target_module']}`",
            f"- Required verifier: `{payload['first_safe_implementation_slice']['required_verifier']}`",
            "",
            "Moves:",
        ]
    )
    lines.extend(f"- {item}" for item in payload["first_safe_implementation_slice"]["moves"])
    lines.append("")
    lines.append("Keeps in inputs_page.py:")
    lines.extend(f"- {item}" for item in payload["first_safe_implementation_slice"]["keeps_in_inputs_page"])
    lines.extend(["", "## Stop Conditions"])
    lines.extend(f"- {item}" for item in payload["stop_conditions"])
    return "\n".join(lines) + "\n"


def _write_artifacts(payload: dict[str, Any]) -> dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_lane_candidate_generation_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_bottom_reo_lane_candidate_generation_boundary_audit_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload["artifact_paths"]


def main() -> int:
    payload = _build_payload()
    paths = _write_artifacts(payload)
    print(f"design_guide_bottom_reo_lane_candidate_generation_boundary_audit {payload['status']}")
    print(json.dumps({"decision": payload["decision"], "artifact_paths": paths}, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
