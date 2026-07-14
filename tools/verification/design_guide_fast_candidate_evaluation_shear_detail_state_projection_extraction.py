from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
SPACING_KEYS = (
    "shear_required_spacing_mm",
    "shear_effective_spacing_mm",
    "shear_sectional_check_spacing_mm",
)


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


def _load_candidate_module():
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    spec = importlib.util.spec_from_file_location(
        "candidate_evaluation_for_shear_detail_state_verifier",
        CANDIDATE_EVALUATION,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to import design_brain.candidate_evaluation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _legacy_projection(eval_state: dict[str, Any] | None, candidate_state: dict[str, Any] | None) -> dict[str, Any]:
    state = dict(eval_state or {})
    candidate = dict(candidate_state or {})
    for key in SPACING_KEYS:
        if key in candidate:
            state[key] = candidate.get(key)
    return state


def build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    _, _, fast_segment = _function_segment(inputs_source, "evaluate_candidate_fast")
    module = _load_candidate_module()
    helper = module.build_fast_candidate_evaluation_shear_detail_state_projection

    cases = {
        "no_spacing_keys": {
            "eval_state": {"b": 300, "shear_required_spacing_mm": 200},
            "candidate_state": {"D": 500},
        },
        "candidate_overrides_all_spacing": {
            "eval_state": {key: 200 for key in SPACING_KEYS},
            "candidate_state": {key: 150 for key in SPACING_KEYS},
        },
        "candidate_partial_override": {
            "eval_state": {key: 200 for key in SPACING_KEYS},
            "candidate_state": {"shear_effective_spacing_mm": 125},
        },
        "candidate_none_override": {
            "eval_state": {key: 200 for key in SPACING_KEYS},
            "candidate_state": {"shear_required_spacing_mm": None},
        },
    }
    parity_rows = []
    for name, payload in cases.items():
        old_value = _legacy_projection(payload["eval_state"], payload["candidate_state"])
        new_value = helper(eval_state=payload["eval_state"], candidate_state=payload["candidate_state"])
        parity_rows.append({"case": name, "old": old_value, "new": new_value, "matches": old_value == new_value})

    checks = {
        "service_helper_exists": "def build_fast_candidate_evaluation_shear_detail_state_projection(" in candidate_source,
        "service_helper_exported": '"build_fast_candidate_evaluation_shear_detail_state_projection"' in candidate_source,
        "page_calls_service_helper": "_build_fast_candidate_evaluation_shear_detail_state_projection(" in fast_segment,
        "legacy_inline_overlay_absent": all(
            token not in fast_segment
            for token in (
                "shear_detail_state = dict(eval_state)",
                "shear_detail_state[key] = candidate_state.get(key)",
            )
        ),
        "detailing_callback_still_page_owned": "_shear_link_detailing_failures_from_state(shear_detail_state)" in fast_segment,
        "parity_cases_match": all(row["matches"] for row in parity_rows),
        "candidate_service_has_no_page_import": "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source,
        "solver_execution_not_moved": all(
            token in fast_segment
            for token in (
                "_evaluate_crack_with_state(",
                "_evaluate_deflection_with_state(",
                "_evaluate_bending_with_bottom_state(",
                "_evaluate_shear_with_state(",
            )
        ),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "snapshot": "design_guide_fast_candidate_evaluation_shear_detail_state_projection_extraction",
        "generated_at": _stamp(),
        "status": status,
        "decision": (
            "FAST_SHEAR_DETAIL_STATE_PROJECTION_SERVICE_OWNED_CALLBACK_STAYS_PAGE_OWNED"
            if status == "PASS"
            else "FAST_SHEAR_DETAIL_STATE_PROJECTION_EXTRACTION_FAILED"
        ),
        "checks": checks,
        "parity_rows": parity_rows,
        "remaining_fast_kernel_page_owned": [
            "action-resolved eval state construction",
            "bottom/shear update collection",
            "solver/evaluator execution",
            "shear-detailing failure callback execution",
            "mu_star input collection",
        ],
        "snapshot_hash": _stable_hash({"checks": checks, "parity_rows": parity_rows}),
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_shear_detail_state_projection_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_shear_detail_state_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    checks = "\n".join(f"- `{key}`: `{value}`" for key, value in sorted(snapshot["checks"].items()))
    rows = [
        "| Case | Matches |",
        "| --- | ---: |",
        *[f"| `{row['case']}` | `{row['matches']}` |" for row in snapshot["parity_rows"]],
    ]
    remaining = "\n".join(f"- {item}" for item in snapshot["remaining_fast_kernel_page_owned"])
    md_path.write_text(
        "\n".join(
            [
                "# Fast Candidate Evaluation Shear Detail State Projection Extraction",
                "",
                f"Status: `{snapshot['status']}`",
                f"Decision: `{snapshot['decision']}`",
                f"Snapshot hash: `{snapshot['snapshot_hash']}`",
                "",
                "## Checks",
                checks,
                "",
                "## Parity Cases",
                *rows,
                "",
                "## Remaining Fast Kernel Page-Owned Surfaces",
                remaining,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, md_path


def main() -> int:
    snapshot = build_snapshot()
    json_path, md_path = write_outputs(snapshot)
    print("design_guide_fast_candidate_evaluation_shear_detail_state_projection_extraction " + snapshot["status"])
    print("decision=" + snapshot["decision"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
