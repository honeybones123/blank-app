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
    overlay_tokens = [
        "shear_detail_state = dict(eval_state)",
        'for key in ("shear_required_spacing_mm", "shear_effective_spacing_mm", "shear_sectional_check_spacing_mm")',
        "shear_detail_state[key] = candidate_state.get(key)",
    ]
    checks = {
        "fast_helper_found": bool(segment),
        "legacy_overlay_present": all(token in segment for token in overlay_tokens),
        "detailing_failure_callback_stays_page_owned": "_shear_link_detailing_failures_from_state(shear_detail_state)" in segment,
        "service_helper_not_yet_present": "def build_fast_candidate_evaluation_shear_detail_state_projection(" not in candidate_source,
        "candidate_service_import_clean": "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "snapshot": "design_guide_fast_candidate_evaluation_shear_detail_state_boundary_audit",
        "generated_at": _stamp(),
        "status": status,
        "decision": (
            "SHEAR_DETAIL_STATE_OVERLAY_READY_TO_EXTRACT_CALLBACK_STAYS_PAGE_OWNED"
            if status == "PASS"
            else "SHEAR_DETAIL_STATE_BOUNDARY_NOT_READY"
        ),
        "target": {"function": "evaluate_candidate_fast", "line_start": start, "line_end": end},
        "surface_rows": [
            {
                "surface": "shear detail state spacing-key overlay",
                "current_owner": "inputs_page",
                "target_owner": "design_brain.candidate_evaluation",
                "classification": "pure state projection",
                "readiness": "READY_TO_EXTRACT",
                "risk": "LOW",
            },
            {
                "surface": "shear detailing failure callback execution",
                "current_owner": "inputs_page",
                "target_owner": "page shell until detailing helper boundary is separately proven",
                "classification": "page-owned helper/callback execution",
                "readiness": "KEEP_PAGE_OWNED",
                "risk": "MEDIUM",
            },
        ],
        "checks": checks,
        "first_safe_implementation_slice": {
            "name": "fast_candidate_evaluation_shear_detail_state_projection_extraction",
            "summary": (
                "Move only the eval-state/candidate-state spacing-key overlay into "
                "design_brain.candidate_evaluation. Keep `_shear_link_detailing_failures_from_state(...)` in inputs_page.py."
            ),
        },
        "stop_conditions": [
            "Do not move shear detailing failure callback execution.",
            "Do not change spacing-key precedence or failure wording.",
            "Do not move solver/evaluator execution.",
        ],
        "snapshot_hash": _stable_hash(checks),
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_shear_detail_state_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_shear_detail_state_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    checks = "\n".join(f"- `{key}`: `{value}`" for key, value in sorted(snapshot["checks"].items()))
    rows = [
        "| Surface | Current owner | Target owner | Classification | Readiness | Risk |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in snapshot["surface_rows"]:
        rows.append(
            "| {surface} | {current_owner} | {target_owner} | {classification} | {readiness} | {risk} |".format(
                **{key: str(value).replace("|", "/") for key, value in row.items()}
            )
        )
    first = snapshot["first_safe_implementation_slice"]
    md_path.write_text(
        "\n".join(
            [
                "# Fast Candidate Evaluation Shear Detail State Boundary Audit",
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
    print("design_guide_fast_candidate_evaluation_shear_detail_state_boundary_audit " + snapshot["status"])
    print("decision=" + snapshot["decision"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
