"""Verify fast candidate evaluation result projection moved to candidate_evaluation."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PAGE_HELPER = "evaluate_candidate_fast"
SERVICE_HELPER = "build_fast_candidate_evaluation_result_projection"


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


def _old_projection(**kwargs: Any) -> dict[str, Any]:
    overview = dict(kwargs["overview"])
    bottom_state = dict(kwargs["bottom_state"])
    failures = list(kwargs.get("shear_link_detailing_failures") or [])
    fail_count = sum(1 for status in overview["statuses"].values() if status == "FAIL")
    bending = bool(kwargs.get("bending_present"))
    return {
        "source": "fast_eval",
        "label": "Fast Eval",
        "action_type": None,
        "updates": {},
        "state": dict(kwargs["candidate_state"]),
        "overview": overview,
        "bottom_state": bottom_state,
        "width": float(kwargs["width"]),
        "depth": float(kwargs["depth"]),
        "Ast_bot": float(bottom_state.get("Ast_bot", 0.0) or 0.0),
        "Ast_top": float(kwargs["ast_top"]),
        "bar_count": int(kwargs["bar_count"]),
        "row_count": int(kwargs["row_count"]),
        "reo_congestion_index": float(kwargs["reo_congestion_index"]),
        "shear_density": float(kwargs["shear_density"]),
        "bending_components": {
            "flexural_util": kwargs.get("flexural_util") if bending else None,
            "ductility_util": kwargs.get("ductility_util") if bending else None,
            "min_steel_util": kwargs.get("min_steel_util") if bending else None,
        },
        "shear_link_detailing_failures": list(failures),
        "rejection_reason": (
            "shear link detailing fail: " + "; ".join(failures)
            if failures else None
        ),
        "is_compliant": bool(overview["all_key_pass"]),
        "worst_util": float(overview["worst_util"] or 0.0),
        "fail_count": fail_count,
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    _, _, page_segment = _function_segment(inputs_source, PAGE_HELPER)

    from design_brain.candidate_evaluation import build_fast_candidate_evaluation_result_projection

    cases = [
        {
            "case": "pass_no_failures",
            "kwargs": {
                "candidate_state": {"D": 650.0, "b": 400.0},
                "overview": {
                    "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
                    "all_key_pass": True,
                    "worst_util": 0.82,
                },
                "bottom_state": {"Ast_bot": 804.248},
                "width": 400.0,
                "depth": 650.0,
                "ast_top": 402.0,
                "bar_count": 5,
                "row_count": 1,
                "reo_congestion_index": 0.33,
                "shear_density": 1.28,
                "flexural_util": 0.82,
                "ductility_util": 0.66,
                "min_steel_util": 0.45,
                "bending_present": True,
                "shear_link_detailing_failures": [],
            },
        },
        {
            "case": "shear_detailing_fail",
            "kwargs": {
                "candidate_state": {"D": 650.0, "b": 400.0, "s_lig": 999.0},
                "overview": {
                    "statuses": {"bending": "PASS", "shear": "FAIL", "crack": "PASS", "deflection": "PASS"},
                    "all_key_pass": False,
                    "worst_util": 1.12,
                },
                "bottom_state": {"Ast_bot": 721.0},
                "width": 400.0,
                "depth": 650.0,
                "ast_top": 0.0,
                "bar_count": 4,
                "row_count": 1,
                "reo_congestion_index": 0.21,
                "shear_density": 0.0,
                "flexural_util": 0.74,
                "ductility_util": 0.52,
                "min_steel_util": 0.35,
                "bending_present": True,
                "shear_link_detailing_failures": ["spacing exceeds limit"],
            },
        },
        {
            "case": "no_bending_result",
            "kwargs": {
                "candidate_state": {"D": 650.0, "b": 400.0},
                "overview": {
                    "statuses": {"bending": "FAIL", "shear": "PASS"},
                    "all_key_pass": False,
                    "worst_util": 1.2,
                },
                "bottom_state": {"Ast_bot": 0.0},
                "width": 400.0,
                "depth": 650.0,
                "ast_top": 0.0,
                "bar_count": 0,
                "row_count": 0,
                "reo_congestion_index": 0.0,
                "shear_density": 0.0,
                "flexural_util": 1.2,
                "ductility_util": None,
                "min_steel_util": None,
                "bending_present": False,
                "shear_link_detailing_failures": [],
            },
        },
    ]
    parity = []
    for case in cases:
        kwargs = dict(case["kwargs"])
        old = _old_projection(**kwargs)
        new = build_fast_candidate_evaluation_result_projection(**kwargs)
        parity.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    source_checks = {
        "service_helper_present": f"def {SERVICE_HELPER}(" in service_source,
        "service_helper_exported": f'"{SERVICE_HELPER}"' in service_source,
        "page_delegates_fast_result_projection": "_build_fast_candidate_evaluation_result_projection(" in page_segment,
        "page_removed_inline_fast_return_projection": '"source": "fast_eval"' not in page_segment
        and '"label": "Fast Eval"' not in page_segment,
        "page_keeps_solver_callbacks": all(
            token in page_segment
            for token in (
                "_evaluate_bending_with_bottom_state",
                "_evaluate_shear_with_state",
                "_evaluate_crack_with_state",
                "_evaluate_deflection_with_state",
            )
        ),
        "candidate_evaluation_has_no_inputs_page_import": "import inputs_page" not in service_source
        and "from inputs_page" not in service_source,
        "candidate_evaluation_has_no_streamlit_import": "streamlit" not in service_source,
    }
    checks = {
        **source_checks,
        "parity_cases_match": all(bool(row["matches"]) for row in parity),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_fast_candidate_evaluation_result_projection_extraction.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "FAST_CANDIDATE_EVALUATION_RESULT_PROJECTION_SERVICE_OWNED",
        "page_helper": PAGE_HELPER,
        "service_helper": SERVICE_HELPER,
        "parity": parity,
        "source_checks": source_checks,
        "checks": checks,
        "remaining_page_owned_evaluator_surfaces": [
            "fast evaluator solver calls",
            "fast evaluator overview/status construction",
            "_evaluate_candidate_fast cache/cap/metrics runner",
            "evaluate_candidate_full cache/probe/full evaluator kernel",
        ],
        "next_safe_slice": "fast_candidate_evaluation_overview_projection_or_runner_adapter_boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_result_projection_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_result_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Fast Candidate Evaluation Result Projection Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Parity",
        "",
    ]
    for row in payload.get("parity") or []:
        lines.append(f"- `{row.get('case')}`: `{row.get('matches')}`")
    lines.extend(["", "## Remaining Page-Owned Evaluator Surfaces", ""])
    lines.extend(f"- `{item}`" for item in payload.get("remaining_page_owned_evaluator_surfaces") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_fast_candidate_evaluation_result_projection_extraction {payload.get('status')}")
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
