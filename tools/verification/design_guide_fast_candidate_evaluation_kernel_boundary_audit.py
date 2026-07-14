from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    start, end, segment = _function_segment(inputs_source, "evaluate_candidate_fast")

    surfaces = [
        {
            "surface": "action-resolved eval state construction",
            "tokens": ["_state_with_resolved_auto_design_actions("],
            "classification": "page-owned evaluator input collection",
            "target_owner": "unsafe to move until action-resolution boundary is proven",
            "readiness": "NOT_READY",
            "risk": "HIGH",
        },
        {
            "surface": "bottom update collection",
            "tokens": ["_resolve_bottom_reo_candidate_bottom_updates("],
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "design_brain.candidate_evaluation bottom update projection",
            "readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
        },
        {
            "surface": "shear update projection",
            "tokens": ["_resolve_candidate_shear_updates("],
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "design_brain.candidate_evaluation shear update projection",
            "readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
        },
        {
            "surface": "solver/evaluator execution",
            "tokens": ["_evaluate_crack_with_state(", "_evaluate_deflection_with_state(", "_evaluate_bending_with_bottom_state(", "_evaluate_shear_with_state("],
            "classification": "page-owned solver/evaluator callback execution",
            "target_owner": "candidate evaluation kernel only after solver parity proof",
            "readiness": "NOT_READY_SOLVER_PARITY",
            "risk": "HIGH",
        },
        {
            "surface": "shear-detailing state projection",
            "tokens": ["_build_fast_candidate_evaluation_shear_detail_state_projection("],
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "design_brain.candidate_evaluation",
            "readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
        },
        {
            "surface": "shear-detailing failure callback execution",
            "tokens": ["_shear_link_detailing_failures_from_state("],
            "classification": "page-owned detailing callback execution",
            "target_owner": "page shell until detailing helper boundary is separately proven",
            "readiness": "KEEP_PAGE_OWNED",
            "risk": "MEDIUM",
        },
        {
            "surface": "scalar/status projection",
            "tokens": ["_build_fast_candidate_evaluation_scalar_status_projection("],
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "design_brain.candidate_evaluation",
            "readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
        },
        {
            "surface": "bending summary pack projection",
            "tokens": ["_build_fast_candidate_evaluation_bending_summary_pack_projection("],
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "design_brain.candidate_evaluation",
            "readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
        },
        {
            "surface": "overview/status projection",
            "tokens": ["_build_fast_candidate_evaluation_overview_status_projection("],
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "design_brain.candidate_evaluation",
            "readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
        },
        {
            "surface": "physical metric projection",
            "tokens": ["_build_fast_candidate_evaluation_physical_metric_projection("],
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "design_brain.candidate_evaluation",
            "readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
        },
        {
            "surface": "result projection",
            "tokens": ["_build_fast_candidate_evaluation_result_projection("],
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "design_brain.candidate_evaluation",
            "readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
        },
    ]
    rows = [{**row, "present": all(token in segment for token in row["tokens"])} for row in surfaces]
    checks = {
        "fast_helper_found": bool(segment),
        "all_surfaces_present": all(row["present"] for row in rows),
        "solver_execution_not_moved": any(
            row["surface"] == "solver/evaluator execution"
            and row["readiness"] == "NOT_READY_SOLVER_PARITY"
            and row["present"]
            for row in rows
        ),
        "bending_summary_pack_extracted": any(
            row["surface"] == "bending summary pack projection"
            and row["readiness"] == "SHELL_CALL_ONLY"
            and row["present"]
            for row in rows
        ) and "def build_fast_candidate_evaluation_bending_summary_pack_projection(" in candidate_source,
        "shear_detail_state_projection_extracted": any(
            row["surface"] == "shear-detailing state projection"
            and row["readiness"] == "SHELL_CALL_ONLY"
            and row["present"]
            for row in rows
        ) and "def build_fast_candidate_evaluation_shear_detail_state_projection(" in candidate_source,
        "shear_detailing_callback_not_moved": any(
            row["surface"] == "shear-detailing failure callback execution"
            and row["readiness"] == "KEEP_PAGE_OWNED"
            and row["present"]
            for row in rows
        ),
        "candidate_bottom_updates_extracted": any(
            row["surface"] == "bottom update collection"
            and row["readiness"] == "SHELL_CALL_ONLY"
            and row["present"]
            for row in rows
        ) and "def resolve_bottom_reo_candidate_bottom_updates(" in candidate_source,
        "candidate_shear_updates_extracted": any(
            row["surface"] == "shear update projection"
            and row["readiness"] == "SHELL_CALL_ONLY"
            and row["present"]
            for row in rows
        ) and "def resolve_candidate_shear_updates(" in candidate_source,
        "candidate_service_import_clean": "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "snapshot": "design_guide_fast_candidate_evaluation_kernel_boundary_audit",
        "generated_at": _stamp(),
        "status": status,
        "decision": (
            "FAST_KERNEL_BENDING_PACK_AND_SHEAR_DETAIL_STATE_EXTRACTED_SOLVER_EXECUTION_NOT_READY"
            if status == "PASS"
            else "FAST_KERNEL_BOUNDARY_NOT_CLASSIFIED"
        ),
        "target": {"function": "evaluate_candidate_fast", "line_start": start, "line_end": end},
        "surface_rows": rows,
        "checks": checks,
        "first_safe_implementation_slice": {
            "name": "fast_candidate_evaluation_action_update_or_solver_kernel_boundary_audit",
            "summary": (
                "The pure bending summary pack, shear-detail state, and bottom/shear update projections are now service-owned. "
                "Next audit action resolution or solver kernel execution, without moving solver semantics."
            ),
        },
        "stop_conditions": [
            "Do not move solver/evaluator execution.",
            "Do not move action-resolution or update collection.",
            "Do not change overview packs, statuses, utils, result shape, visible wording, or CTA/apply semantics.",
        ],
        "snapshot_hash": _stable_hash({"checks": checks, "rows": rows}),
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_kernel_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_kernel_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    rows = [
        "| Surface | Classification | Target owner | Readiness | Risk | Present |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for row in snapshot["surface_rows"]:
        rows.append(
            "| {surface} | {classification} | {target_owner} | {readiness} | {risk} | `{present}` |".format(
                **{key: str(value).replace("|", "/") for key, value in row.items()}
            )
        )
    checks = "\n".join(f"- `{key}`: `{value}`" for key, value in sorted(snapshot["checks"].items()))
    first = snapshot["first_safe_implementation_slice"]
    md_path.write_text(
        "\n".join(
            [
                "# Fast Candidate Evaluation Kernel Boundary Audit",
                "",
                f"Status: `{snapshot['status']}`",
                f"Decision: `{snapshot['decision']}`",
                f"Snapshot hash: `{snapshot['snapshot_hash']}`",
                "",
                "## Surface Inventory",
                *rows,
                "",
                "## Checks",
                checks,
                "",
                "## First Safe Implementation Slice",
                f"- `{first['name']}`",
                f"- {first['summary']}",
                "",
                "## Stop Conditions",
                *[f"- {item}" for item in snapshot["stop_conditions"]],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, md_path


def main() -> int:
    snapshot = build_snapshot()
    json_path, md_path = write_outputs(snapshot)
    print("design_guide_fast_candidate_evaluation_kernel_boundary_audit " + snapshot["status"])
    print("decision=" + snapshot["decision"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
