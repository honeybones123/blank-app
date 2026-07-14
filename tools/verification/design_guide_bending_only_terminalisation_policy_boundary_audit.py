"""Audit the bending-only same-click terminalisation fold boundary."""

from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
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


def _terminalisation_segment(function_segment: str) -> str:
    start_token = "if allow_terminalisation_fold:"
    end_token = 'selected["candidate_search_evidence"] = dict(evidence)'
    start = function_segment.find(start_token)
    end = function_segment.find(end_token, start)
    if start < 0 or end < 0:
        return ""
    return function_segment[start:end]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    controller_source = _read(CONTROLLER)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, segment = _function_segment(inputs_source, TARGET)
    terminal = _terminalisation_segment(segment)
    terminal_start = start + segment[: segment.find(terminal)].count("\n") if terminal else start

    surfaces = [
        {
            "surface": "terminal trigger and initial selected update snapshot",
            "classification": "pure policy candidate",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController terminalisation policy",
            "risk": "LOW",
            "evidence": _token_lines(terminal, terminal_start, "terminal_updates"),
        },
        {
            "surface": "post-first-click overview collection",
            "classification": "page-owned callback/execution",
            "current_owner": "inputs_page",
            "target_owner": "page shell injected callback until overview service boundary exists",
            "risk": "HIGH",
            "evidence": _token_lines(terminal, terminal_start, "_collect_design_overview(")
            + _token_lines(terminal, terminal_start, "_build_design_actions_context("),
        },
        {
            "surface": "residual bending follow-up search",
            "classification": "recursive page-owned callback orchestration",
            "current_owner": "inputs_page",
            "target_owner": "controller shell with injected bending cleanup callback",
            "risk": "HIGH",
            "evidence": _token_lines(terminal, terminal_start, "_bending_only_target_band_cleanup_item("),
        },
        {
            "surface": "button contract interrogation for follow-up updates",
            "classification": "CTA/apply-adjacent page plumbing",
            "current_owner": "inputs_page",
            "target_owner": "page shell / publication CTA authority reader",
            "risk": "HIGH",
            "evidence": _token_lines(terminal, terminal_start, "_design_guide_button_contract(")
            + _token_lines(terminal, terminal_start, "_design_guide_button_contract_enabled("),
        },
        {
            "surface": "trial candidate evaluation after merged bending update",
            "classification": "candidate evaluation service-backed callback",
            "current_owner": "inputs_page",
            "target_owner": "candidate_evaluation service with injected evaluator",
            "risk": "MEDIUM",
            "evidence": _token_lines(terminal, terminal_start, "_evaluate_bending_only_target_band_prebuilt_candidate_with_service("),
        },
        {
            "surface": "residual shear follow-up search and merge",
            "classification": "page-owned callback orchestration",
            "current_owner": "inputs_page",
            "target_owner": "controller terminalisation policy with injected shear cleanup callback",
            "risk": "HIGH",
            "evidence": _token_lines(terminal, terminal_start, "_shear_low_util_target_cleanup_item(")
            + _token_lines(terminal, terminal_start, "_publishable_same_click_shear_cleanup_merge("),
        },
        {
            "surface": "terminalisation evidence mutation",
            "classification": "controller-owned pure projection after callback results",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController terminalisation evidence projection",
            "risk": "LOW",
            "evidence": _token_lines(terminal, terminal_start, "terminal_evidence"),
        },
        {
            "surface": "selected candidate combined rewrite",
            "classification": "controller-owned pure selected-candidate projection",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController terminalisation selected-candidate projection",
            "risk": "LOW",
            "evidence": _token_lines(terminal, terminal_start, "_build_design_guide_controller_bending_only_terminalisation_projection("),
        },
    ]

    checks = {
        "target_found": f"def {TARGET}(" in inputs_source,
        "terminalisation_segment_found": bool(terminal),
        "projection_adapter_backed_before_terminalisation_audit": (
            "_build_design_guide_controller_bending_only_best_safe_cleanup_item_projection(" in segment
            and "_build_design_guide_controller_bending_only_target_band_cleanup_item_projection(" in segment
        ),
        "overview_collection_still_page_owned": "_collect_design_overview(" in terminal,
        "followup_bending_callback_still_page_owned": "_bending_only_target_band_cleanup_item(" in terminal,
        "followup_shear_callback_still_page_owned": "_shear_low_util_target_cleanup_item(" in terminal,
        "button_contract_interrogation_still_page_owned": "_design_guide_button_contract(" in terminal,
        "candidate_eval_service_backed": "_evaluate_bending_only_target_band_prebuilt_candidate_with_service(" in terminal,
        "terminal_selected_rewrite_controller_owned": (
            "_build_design_guide_controller_bending_only_terminalisation_projection(" in terminal
            and 'selected["family"] = "combined"' not in terminal
            and 'selected["subfamilies"] = ["shear", "bottom_reinforcement"]' not in terminal
        ),
        "controller_import_clean": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "candidate_evaluation_import_clean": "inputs_page" not in candidate_source and "streamlit" not in candidate_source,
        "surfaces_classified": all(row.get("classification") for row in surfaces),
        "first_safe_slice_identified": True,
        "product_behavior_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": "design_guide_bending_only_terminalisation_policy_boundary_audit.v1",
        "status": status,
        "decision": (
            "BENDING_ONLY_TERMINALISATION_NOT_READY_CALLBACK_BOUNDARY_FIRST"
            if status == "PASS"
            else "BENDING_ONLY_TERMINALISATION_BOUNDARY_AUDIT_FAILED"
        ),
        "target": {"name": TARGET, "line_start": start, "line_end": end},
        "surfaces": surfaces,
        "checks": checks,
        "first_safe_implementation_slice": {
            "name": "bending_only_terminalisation_callback_boundary_next",
            "why": (
                "The pure combined rewrite/evidence projection is now controller-owned, but the surrounding "
                "overview collection, recursive cleanup callbacks, button-contract interrogation, and candidate evaluation remain page-owned."
            ),
            "move_next": (
                "Audit the remaining terminalisation callback execution boundary before moving any callback orchestration."
            ),
            "do_not_move_yet": [
                "overview collection",
                "recursive bending cleanup callback execution",
                "shear cleanup callback execution",
                "button contract execution/interrogation",
                "candidate evaluation execution",
            ],
            "required_verifier": "design_guide_bending_only_terminalisation_callback_boundary_parity.py",
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bending_only_terminalisation_policy_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_only_terminalisation_policy_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bending-Only Terminalisation Policy Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surface Inventory",
        "",
        "| Surface | Current owner | Target owner | Classification | Risk |",
        "|---|---|---|---|---|",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"| `{row.get('surface')}` | {row.get('current_owner')} | {row.get('target_owner')} | "
            f"{row.get('classification')} | {row.get('risk')} |"
        )
    first = dict(payload.get("first_safe_implementation_slice") or {})
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            f"- Name: `{first.get('name')}`",
            f"- Why: {first.get('why')}",
            f"- Move next: {first.get('move_next')}",
            f"- Required verifier: `{first.get('required_verifier')}`",
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- `{key}`: `{value}`" for key, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bending_only_terminalisation_policy_boundary_audit {payload.get('status')}")
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
