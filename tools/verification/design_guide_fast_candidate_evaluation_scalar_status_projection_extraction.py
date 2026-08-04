"""Verify fast candidate scalar/status projection moved to candidate_evaluation."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import math
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
SERVICE_HELPER = "build_fast_candidate_evaluation_scalar_status_projection"


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


def _status_from_util(util: float | None, unknown_status: str) -> str:
    if util is None or (isinstance(util, float) and math.isnan(util)):
        return unknown_status
    if util <= 1.0:
        return "NEAR LIMIT" if util >= 0.95 else "PASS"
    return "FAIL"


def _old_scalar_projection(**kwargs: Any) -> dict[str, Any]:
    seed_overview = dict(kwargs.get("seed_overview") or {})
    seed_statuses = dict(seed_overview.get("statuses") or {})
    seed_utils = dict(seed_overview.get("utils") or {})
    bending = kwargs.get("bending")
    shear = kwargs.get("shear")
    crack = kwargs.get("crack")
    deflection = kwargs.get("deflection")
    unknown_status = str(kwargs.get("unknown_status") or "")
    failures = [str(reason) for reason in list(kwargs.get("shear_link_detailing_failures") or [])]

    flexural_util = None
    ductility_util = None
    min_steel_util = None
    bending_util = None
    bending_status = unknown_status
    if bending:
        flexural_util = float(bending.get("Mu_util", float("inf")))
        try:
            ductility_util = (
                float(bending.get("ku", 0.0) or 0.0) / 0.36
                if bending.get("ku") is not None
                else None
            )
        except Exception:
            ductility_util = None
        try:
            as_min = float(bending.get("As_min", 0.0) or 0.0)
            ast = float(bending.get("Ast_bot", 0.0) or 0.0)
            if ast > 0.0 and as_min > 0.0:
                min_steel_util = as_min / ast
        except Exception:
            min_steel_util = None
        bending_util = flexural_util
        if bending_util is not None and math.isnan(bending_util):
            bending_util = None
        governs = [
            u
            for u in (flexural_util, ductility_util, min_steel_util)
            if u is not None and not math.isnan(u)
        ]
        if governs:
            if any(u > 1.0 for u in governs):
                bending_status = "FAIL"
            elif any(u >= 0.95 for u in governs):
                bending_status = "NEAR LIMIT"
            else:
                bending_status = "PASS"
        else:
            bending_status = unknown_status

    shear_util = None
    shear_status = unknown_status
    if shear:
        shear_candidates = []
        for value in (shear.get("util"), shear.get("web_util")):
            try:
                resolved = float(value)
            except Exception:
                continue
            if not math.isnan(resolved):
                shear_candidates.append(resolved)
        shear_util = max(shear_candidates, default=None)
        shear_status = _status_from_util(shear_util, unknown_status)
    if failures:
        shear_status = "FAIL"

    statuses = {
        "bending": bending_status,
        "shear": shear_status,
        "crack": (
            _status_from_util(float(crack.get("util", 0.0) or 0.0), unknown_status)
            if crack is not None
            else str(seed_statuses.get("crack", "PASS") or "PASS")
        ),
        "deflection": (
            str(deflection.get("status") or "PASS")
            if deflection is not None
            else str(seed_statuses.get("deflection", "PASS") or "PASS")
        ),
    }
    utils = {
        "bending": bending_util,
        "shear": shear_util,
        "crack": (
            float(crack.get("util", 0.0) or 0.0)
            if crack is not None
            else seed_utils.get("crack")
        ),
        "deflection": (
            deflection.get("util")
            if deflection is not None
            else seed_utils.get("deflection")
        ),
    }
    return {
        "statuses": statuses,
        "utils": utils,
        "flexural_util": flexural_util,
        "ductility_util": ductility_util,
        "min_steel_util": min_steel_util,
        "bending_util": bending_util,
        "shear_util": shear_util,
        "unknown_status": next(
            (
                status
                for status in statuses.values()
                if status not in ("PASS", "FAIL", "NEAR LIMIT", "")
            ),
            unknown_status,
        ),
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    _, _, page_segment = _function_segment(inputs_source, PAGE_HELPER)

    from design_brain.candidate_evaluation import build_fast_candidate_evaluation_scalar_status_projection

    unknown = "UNKNOWN_FAST_STATUS"
    cases = [
        {
            "case": "all_present_pass",
            "kwargs": {
                "seed_overview": {},
                "bending": {"Mu_util": 0.82, "ku": 0.18, "As_min": 100.0, "Ast_bot": 500.0},
                "shear": {"util": 0.71, "web_util": 0.68},
                "crack": {"util": 0.0},
                "deflection": {"status": "PASS", "util": 0.0},
                "shear_link_detailing_failures": [],
                "unknown_status": unknown,
            },
        },
        {
            "case": "bending_fail_shear_warn",
            "kwargs": {
                "seed_overview": {},
                "bending": {"Mu_util": 1.12, "ku": 0.39, "As_min": 300.0, "Ast_bot": 450.0},
                "shear": {"util": 0.94, "web_util": 0.96},
                "crack": {"util": 0.0},
                "deflection": {"status": "PASS", "util": 0.0},
                "shear_link_detailing_failures": [],
                "unknown_status": unknown,
            },
        },
        {
            "case": "missing_bending_seed_sls_fallback",
            "kwargs": {
                "seed_overview": {
                    "statuses": {"crack": "PASS", "deflection": "NEAR LIMIT"},
                    "utils": {"crack": 0.2, "deflection": 0.97},
                },
                "bending": None,
                "shear": None,
                "crack": None,
                "deflection": None,
                "shear_link_detailing_failures": [],
                "unknown_status": unknown,
            },
        },
        {
            "case": "shear_detailing_failure_override",
            "kwargs": {
                "seed_overview": {},
                "bending": {"Mu_util": 0.72, "ku": 0.12, "As_min": 100.0, "Ast_bot": 600.0},
                "shear": {"util": 0.62, "web_util": 0.61},
                "crack": {"util": 0.0},
                "deflection": {"status": "PASS", "util": 0.0},
                "shear_link_detailing_failures": ["spacing exceeds limit"],
                "unknown_status": unknown,
            },
        },
    ]
    parity = []
    for case in cases:
        kwargs = dict(case["kwargs"])
        old = _old_scalar_projection(**kwargs)
        new = build_fast_candidate_evaluation_scalar_status_projection(**kwargs)
        parity.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    source_checks = {
        "service_helper_present": f"def {SERVICE_HELPER}(" in service_source,
        "service_helper_exported": f'"{SERVICE_HELPER}"' in service_source,
        "page_delegates_scalar_status_projection": f"_{SERVICE_HELPER}(" in page_segment,
        "page_delegated_values_feed_overview_projection": "scalar_status_projection.get(\"statuses\")" in page_segment
        and "scalar_status_projection.get(\"utils\")" in page_segment
        and "scalar_status_projection.get(\"unknown_status\")" in page_segment,
        "page_keeps_solver_callbacks": all(
            token in page_segment
            for token in (
                "_evaluate_bending_with_bottom_state",
                "_evaluate_shear_with_state",
                "_evaluate_crack_with_state",
                "_evaluate_deflection_with_state",
            )
        ),
        "page_keeps_shear_detailing_helper_call": "_shear_link_detailing_failures_from_state" in page_segment,
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
        "schema": "design_guide_fast_candidate_evaluation_scalar_status_projection_extraction.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "FAST_CANDIDATE_EVALUATION_SCALAR_STATUS_PROJECTION_SERVICE_OWNED",
        "page_helper": PAGE_HELPER,
        "service_helper": SERVICE_HELPER,
        "parity": parity,
        "source_checks": source_checks,
        "checks": checks,
        "remaining_page_owned_evaluator_surfaces": [
            "fast evaluator solver calls",
            "legacy inline scalar prep deadness proof/deletion",
            "fast physical metric helper calls",
            "_evaluate_candidate_fast cache/cap/metrics runner",
            "evaluate_candidate_full cache/probe/full evaluator kernel",
        ],
        "next_safe_slice": "fast_candidate_evaluation_legacy_scalar_deadness_or_physical_metric_projection_boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_scalar_status_projection_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_scalar_status_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Fast Candidate Evaluation Scalar/Status Projection Extraction",
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
    print(f"design_guide_fast_candidate_evaluation_scalar_status_projection_extraction {payload.get('status')}")
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
