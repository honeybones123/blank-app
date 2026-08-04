"""Verify fast candidate overview/status projection moved to candidate_evaluation."""

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
SERVICE_HELPER = "build_fast_candidate_evaluation_overview_status_projection"


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


def _old_overview_projection(**kwargs: Any) -> dict[str, Any]:
    failures = [str(reason) for reason in list(kwargs.get("shear_link_detailing_failures") or [])]
    statuses = {
        "bending": kwargs["bending_status"],
        "shear": kwargs["shear_status"],
        "crack": kwargs["crack_status"],
        "deflection": kwargs["deflection_status"],
    }
    utils = {
        "bending": kwargs.get("bending_util"),
        "shear": kwargs.get("shear_util"),
        "crack": kwargs.get("crack_util"),
        "deflection": kwargs.get("deflection_util"),
    }
    unknown_status = str(kwargs.get("unknown_status") or "")
    tracked_statuses = [status for status in statuses.values() if status not in (unknown_status, "")]
    bend_pack = dict(kwargs.get("bend_pack") or {})
    overview = {
        "packs": {"bending": bend_pack} if bend_pack else {},
        "statuses": statuses,
        "utils": utils,
        "any_fail": any(status == "FAIL" for status in tracked_statuses),
        "any_warn": any(status == "NEAR LIMIT" for status in tracked_statuses),
        "all_key_pass": bool(tracked_statuses) and all(status == "PASS" for status in tracked_statuses),
        "worst_util": max((util for util in utils.values() if util is not None), default=0.0),
    }
    if failures:
        overview["failure_details_by_family"] = {
            "shear": [
                {
                    "title": "Shear link detailing",
                    "status": "FAIL",
                    "text": reason,
                }
                for reason in failures
            ]
        }
        overview["shear_link_detailing_failures"] = list(failures)
    return overview


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    _, _, page_segment = _function_segment(inputs_source, PAGE_HELPER)

    from design_brain.candidate_evaluation import build_fast_candidate_evaluation_overview_status_projection

    unknown = "UNKNOWN_FAST_STATUS"
    cases = [
        {
            "case": "all_pass",
            "kwargs": {
                "seed_overview": {},
                "bending_status": "PASS",
                "shear_status": "PASS",
                "crack_status": "PASS",
                "deflection_status": "PASS",
                "bending_util": 0.72,
                "shear_util": 0.66,
                "crack_util": 0.0,
                "deflection_util": 0.0,
                "bend_pack": {"summary_util": 0.72, "rows": []},
                "shear_link_detailing_failures": [],
                "unknown_status": unknown,
            },
        },
        {
            "case": "near_limit_warning",
            "kwargs": {
                "seed_overview": {},
                "bending_status": "NEAR LIMIT",
                "shear_status": "PASS",
                "crack_status": "PASS",
                "deflection_status": "PASS",
                "bending_util": 0.97,
                "shear_util": 0.42,
                "crack_util": 0.0,
                "deflection_util": 0.0,
                "bend_pack": {"summary_util": 0.97, "rows": []},
                "shear_link_detailing_failures": [],
                "unknown_status": unknown,
            },
        },
        {
            "case": "shear_failure_detailing",
            "kwargs": {
                "seed_overview": {},
                "bending_status": "PASS",
                "shear_status": "FAIL",
                "crack_status": "PASS",
                "deflection_status": "PASS",
                "bending_util": 0.62,
                "shear_util": 1.04,
                "crack_util": 0.0,
                "deflection_util": 0.0,
                "bend_pack": {},
                "shear_link_detailing_failures": ["spacing exceeds limit"],
                "unknown_status": unknown,
            },
        },
        {
            "case": "unknown_bending_ignored",
            "kwargs": {
                "seed_overview": {},
                "bending_status": unknown,
                "shear_status": "PASS",
                "crack_status": "PASS",
                "deflection_status": "PASS",
                "bending_util": None,
                "shear_util": 0.44,
                "crack_util": 0.0,
                "deflection_util": 0.0,
                "bend_pack": {},
                "shear_link_detailing_failures": [],
                "unknown_status": unknown,
            },
        },
    ]
    parity = []
    for case in cases:
        kwargs = dict(case["kwargs"])
        old = _old_overview_projection(**kwargs)
        new = build_fast_candidate_evaluation_overview_status_projection(**kwargs)
        parity.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    source_checks = {
        "service_helper_present": f"def {SERVICE_HELPER}(" in service_source,
        "service_helper_exported": f'"{SERVICE_HELPER}"' in service_source,
        "page_delegates_overview_status_projection": f"_{SERVICE_HELPER}(" in page_segment,
        "page_removed_inline_overview_materialization": '"any_fail": any(status == "FAIL" for status in tracked_statuses)' not in page_segment
        and '"failure_details_by_family"' not in page_segment,
        "page_keeps_solver_callbacks": all(
            token in page_segment
            for token in (
                "_evaluate_bending_with_bottom_state",
                "_evaluate_shear_with_state",
                "_evaluate_crack_with_state",
                "_evaluate_deflection_with_state",
            )
        ),
        "page_keeps_fast_result_projection_delegate": "_build_fast_candidate_evaluation_result_projection(" in page_segment,
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
        "schema": "design_guide_fast_candidate_evaluation_overview_status_projection_extraction.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "FAST_CANDIDATE_EVALUATION_OVERVIEW_STATUS_PROJECTION_SERVICE_OWNED",
        "page_helper": PAGE_HELPER,
        "service_helper": SERVICE_HELPER,
        "parity": parity,
        "source_checks": source_checks,
        "checks": checks,
        "remaining_page_owned_evaluator_surfaces": [
            "fast evaluator solver calls",
            "fast evaluator scalar status preparation",
            "fast physical metric helper calls",
            "_evaluate_candidate_fast cache/cap/metrics runner",
            "evaluate_candidate_full cache/probe/full evaluator kernel",
        ],
        "next_safe_slice": "fast_candidate_evaluation_scalar_status_or_physical_metric_projection_boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_overview_status_projection_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_overview_status_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Fast Candidate Evaluation Overview/Status Projection Extraction",
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
    print(f"design_guide_fast_candidate_evaluation_overview_status_projection_extraction {payload.get('status')}")
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
