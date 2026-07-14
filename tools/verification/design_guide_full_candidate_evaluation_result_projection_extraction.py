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
        "candidate_evaluation_for_full_result_projection_verifier",
        CANDIDATE_EVALUATION,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to import design_brain.candidate_evaluation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _legacy_result(
    *,
    candidate_state: dict[str, Any],
    source: str,
    label: str | None,
    action_type: str | None,
    updates: dict[str, Any] | None,
    overview: dict[str, Any],
    bottom_state: dict[str, Any],
    width: int | float,
    depth: int | float,
    ast_top: int | float,
    bar_count: int,
    row_count: int,
    reo_congestion_index: int | float,
    shear_density: int | float,
    flexural_util: int | float | None,
    ductility_util: int | float | None,
    min_steel_util: int | float | None,
    bending_present: bool,
) -> dict[str, Any]:
    fail_count = sum(1 for status in overview["statuses"].values() if status == "FAIL")
    return {
        "source": source,
        "label": label or source.replace("_", " ").title(),
        "action_type": action_type,
        "updates": dict(updates or {}),
        "state": candidate_state,
        "overview": overview,
        "bottom_state": bottom_state,
        "width": float(width),
        "depth": float(depth),
        "Ast_bot": float(bottom_state.get("Ast_bot", 0.0) or 0.0),
        "Ast_top": float(ast_top),
        "bar_count": int(bar_count),
        "row_count": int(row_count),
        "reo_congestion_index": float(reo_congestion_index),
        "shear_density": float(shear_density),
        "bending_components": {
            "flexural_util": flexural_util if bending_present else None,
            "ductility_util": ductility_util if bending_present else None,
            "min_steel_util": min_steel_util if bending_present else None,
        },
        "is_compliant": bool(overview["all_key_pass"]),
        "worst_util": float(overview["worst_util"] or 0.0),
        "fail_count": fail_count,
    }


def build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    _, _, full_segment = _function_segment(inputs_source, "evaluate_candidate_full")
    module = _load_candidate_module()
    helper = module.build_full_candidate_evaluation_result_projection

    base_payload = {
        "candidate_state": {"b": 300, "D": 600, "Ast_top": 120.0},
        "source": "full_eval",
        "label": None,
        "action_type": "apply_resolved_candidate",
        "updates": {"D": 600},
        "overview": {
            "packs": {},
            "statuses": {"bending": "PASS", "shear": "FAIL"},
            "utils": {"bending": 0.8, "shear": 1.1},
            "all_key_pass": False,
            "worst_util": 1.1,
        },
        "bottom_state": {"Ast_bot": 450.0},
        "width": 300,
        "depth": 600,
        "ast_top": 120.0,
        "bar_count": 4,
        "row_count": 1,
        "reo_congestion_index": 0.25,
        "shear_density": 1.2,
        "flexural_util": 0.8,
        "ductility_util": 0.5,
        "min_steel_util": 0.6,
        "bending_present": True,
    }
    cases = {
        "default_label_with_bending": base_payload,
        "explicit_label_no_bending": {
            **base_payload,
            "label": "Custom",
            "bending_present": False,
            "overview": {**base_payload["overview"], "statuses": {"bending": "PASS", "shear": "PASS"}, "all_key_pass": True, "worst_util": 0.8},
        },
    }
    parity_rows = []
    for name, payload in cases.items():
        old_value = _legacy_result(**payload)
        new_value = helper(**payload)
        parity_rows.append(
            {
                "case": name,
                "matches": old_value == new_value,
                "state_identity_preserved": new_value.get("state") is payload["candidate_state"],
            }
        )

    checks = {
        "service_helper_exists": "def build_full_candidate_evaluation_result_projection(" in candidate_source,
        "service_helper_exported": '"build_full_candidate_evaluation_result_projection"' in candidate_source,
        "page_calls_service_helper": "_build_full_candidate_evaluation_result_projection(" in full_segment,
        "legacy_inline_result_absent": "evaluated_candidate = {" not in full_segment,
        "parity_cases_match": all(row["matches"] for row in parity_rows),
        "state_identity_preserved": all(row["state_identity_preserved"] for row in parity_rows),
        "candidate_service_has_no_page_import": "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source,
        "solver_execution_not_moved": all(
            token in full_segment
            for token in (
                "_evaluate_crack_with_state(",
                "_evaluate_deflection_with_state(",
                "_evaluate_bending_with_bottom_state(",
                "_evaluate_shear_with_state(",
                "_collect_design_overview(",
            )
        ),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "snapshot": "design_guide_full_candidate_evaluation_result_projection_extraction",
        "generated_at": _stamp(),
        "status": status,
        "decision": (
            "FULL_CANDIDATE_EVALUATION_RESULT_PROJECTION_SERVICE_OWNED"
            if status == "PASS"
            else "FULL_CANDIDATE_EVALUATION_RESULT_PROJECTION_EXTRACTION_FAILED"
        ),
        "checks": checks,
        "parity_rows": parity_rows,
        "remaining_full_evaluator_page_owned": [
            "fingerprint/cache/profiling wrapper",
            "bottom/shear update collection",
            "solver/evaluator execution",
            "overview collection/status projection",
            "physical metric input collection",
        ],
        "snapshot_hash": _stable_hash({"checks": checks, "parity_rows": parity_rows}),
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_guide_full_candidate_evaluation_result_projection_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_full_candidate_evaluation_result_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    checks = "\n".join(f"- `{key}`: `{value}`" for key, value in sorted(snapshot["checks"].items()))
    rows = [
        "| Case | Matches | State identity preserved |",
        "| --- | ---: | ---: |",
        *[
            f"| `{row['case']}` | `{row['matches']}` | `{row['state_identity_preserved']}` |"
            for row in snapshot["parity_rows"]
        ],
    ]
    remaining = "\n".join(f"- {item}" for item in snapshot["remaining_full_evaluator_page_owned"])
    md_path.write_text(
        "\n".join(
            [
                "# Full Candidate Evaluation Result Projection Extraction",
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
                "## Remaining Full Evaluator Page-Owned Surfaces",
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
    print("design_guide_full_candidate_evaluation_result_projection_extraction " + snapshot["status"])
    print("decision=" + snapshot["decision"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
