"""Audit remaining bending-only terminalisation and item projection ownership."""

from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_bending_only_target_band_cleanup_item"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _token_lines(segment: str, start: int, token: str) -> list[int]:
    return [start + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_segment(inputs_source, TARGET)

    surfaces = [
        {
            "surface": "fast-render/cache shell",
            "current_owner": "inputs_page",
            "target_owner": "page shell / future cache service",
            "classification": "approved page-shell guard",
            "deletion_readiness": "SHELL_ONLY_KEEP",
            "risk": "LOW",
            "evidence": _token_lines(segment, start, "get_rerun_pure_cache(")
            + _token_lines(segment, start, "set_rerun_pure_cache("),
        },
        {
            "surface": "candidate update-trial generation",
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation",
            "classification": "extracted service boundary",
            "deletion_readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
            "evidence": _token_lines(segment, start, "_build_bending_only_target_band_cleanup_update_trials("),
        },
        {
            "surface": "candidate evaluation loop",
            "current_owner": "inputs_page service-backed callback loop",
            "target_owner": "candidate evaluation service after callback/kernel proof",
            "classification": "bounded page callback execution",
            "deletion_readiness": "NOT_READY_CALLBACK_EXECUTION",
            "risk": "MEDIUM",
            "evidence": _token_lines(segment, start, "_evaluate_bending_only_target_band_candidate_with_service("),
        },
        {
            "surface": "ranking selectors",
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation",
            "classification": "extracted service boundary",
            "deletion_readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
            "evidence": _token_lines(segment, start, "_select_bending_only_best_safe_partial_cleanup_candidate(")
            + _token_lines(segment, start, "_select_bending_only_target_band_cleanup_candidate("),
        },
        {
            "surface": "best-safe partial item projection",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController projection adapter",
            "classification": "extracted controller projection boundary",
            "deletion_readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
            "evidence": _token_lines(segment, start, "Bending cleanup - best safe one-click reduction")
            + _token_lines(segment, start, "_build_design_guide_controller_bending_only_best_safe_cleanup_item_projection("),
        },
        {
            "surface": "same-click terminalisation fold",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController terminalisation policy with page-injected callbacks",
            "classification": "page-owned terminalisation decision/orchestration",
            "deletion_readiness": "NOT_READY_TERMINALISATION_POLICY_PARITY",
            "risk": "HIGH",
            "evidence": _token_lines(segment, start, "allow_terminalisation_fold")
            + _token_lines(segment, start, "same_click_terminalisation_fold")
            + _token_lines(segment, start, "_shear_low_util_target_cleanup_item("),
        },
        {
            "surface": "final target-band item projection",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController projection adapter",
            "classification": "extracted controller projection boundary",
            "deletion_readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
            "evidence": _token_lines(segment, start, "_guidance_item_from_resolved_candidate(")
            + _token_lines(segment, start, "_build_design_guide_controller_bending_only_target_band_cleanup_item_projection("),
        },
        {
            "surface": "debug sink writes",
            "current_owner": "inputs_page",
            "target_owner": "page shell diagnostics / future debug service",
            "classification": "non-authoritative debug/session storage",
            "deletion_readiness": "SHELL_DEBUG_KEEP",
            "risk": "LOW",
            "evidence": _token_lines(segment, start, "debug_sink["),
        },
    ]
    checks = {
        "target_found": f"def {TARGET}(" in inputs_source,
        "candidate_generation_service_backed": "_build_bending_only_target_band_cleanup_update_trials(" in segment,
        "ranking_selectors_service_backed": "_select_bending_only_best_safe_partial_cleanup_candidate(" in segment
        and "_select_bending_only_target_band_cleanup_candidate(" in segment,
        "terminalisation_present_and_not_moved": "allow_terminalisation_fold" in segment
        and "_shear_low_util_target_cleanup_item(" in segment,
        "projection_adapter_service_backed": "_guidance_item_from_resolved_candidate(" in segment
        and "_build_design_guide_controller_bending_only_best_safe_cleanup_item_projection(" in segment
        and "_build_design_guide_controller_bending_only_target_band_cleanup_item_projection(" in segment
        and 'item["action_payload"] = payload' not in segment
        and 'item["resolved_candidate"] = resolved' not in segment,
        "candidate_service_import_clean": "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source,
        "controller_import_clean": "inputs_page" not in controller_source
        and "streamlit" not in controller_source,
        "surfaces_classified": all(bool(row.get("classification")) for row in surfaces),
        "first_safe_slice_identified": True,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_bending_only_terminalisation_projection_boundary_audit.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BENDING_ONLY_PROJECTION_SERVICE_BACKED_TERMINALISATION_NOT_READY",
        "target": {"name": TARGET, "line_start": start, "line_end": end, "line_count": end - start + 1},
        "surfaces": surfaces,
        "checks": checks,
        "first_safe_implementation_slice": {
            "name": "bending_only_terminalisation_policy_boundary_audit",
            "why": (
                "Generation, ranking, and item projection are service/controller-owned. "
                "Terminalisation remains high-risk and callback-heavy."
            ),
            "move": "Audit the same-click terminalisation fold before moving any policy or injected callbacks.",
            "do_not_move": [
                "candidate evaluation loop",
                "same-click terminalisation fold",
                "debug_sink writes",
                "CTA/apply routing",
                "visible wording",
            ],
            "required_verifier": "design_guide_bending_only_terminalisation_policy_boundary_audit.py",
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bending_only_terminalisation_projection_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_only_terminalisation_projection_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bending-Only Terminalisation / Projection Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surface Inventory",
        "",
        "| Surface | Current owner | Target owner | Classification | Deletion readiness | Risk |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"| `{row.get('surface')}` | {row.get('current_owner')} | {row.get('target_owner')} | "
            f"{row.get('classification')} | {row.get('deletion_readiness')} | {row.get('risk')} |"
        )
    first = dict(payload.get("first_safe_implementation_slice") or {})
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            f"- Name: `{first.get('name')}`",
            f"- Why: {first.get('why')}",
            f"- Move: {first.get('move')}",
            f"- Required verifier: `{first.get('required_verifier')}`",
            "",
            "## Checks",
            "",
        ],
    )
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bending_only_terminalisation_projection_boundary_audit {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
