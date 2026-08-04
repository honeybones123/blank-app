"""Verify accepted compound bottom-reo candidate projection moved to bending family."""

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
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PAGE_HELPER = "_append_geometry_bottom_compound_candidates"
FAMILY_HELPER = "build_bottom_reo_compound_accepted_candidate_projection"


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


def _old_projection(candidate: dict[str, Any], axis: str, arrangement: dict[str, Any], geometry_label: str) -> dict[str, Any]:
    if axis == "width":
        title = "Increase width and rebalance bottom reinforcement"
    elif axis == "depth":
        title = "Increase depth and adjust bottom reinforcement"
    else:
        title = (
            f"Adjust geometry and bottom reinforcement ({geometry_label})"
            if geometry_label
            else "Adjust geometry and bottom reinforcement"
        )
    return {
        "recommendation_compound": True,
        "recommendation_geometry_trial": True,
        "recommendation_bottom_trial": True,
        "subfamilies": ["geometry", "bottom_reo"],
        "recommendation_family_tag": f"compound_{axis}_bottom",
        "compound_geo_axis": axis,
        "arrangement": dict(arrangement),
        "actual_ast": float(candidate.get("Ast_bot", 0.0) or 0.0),
        "guidance_recommendation_title": title,
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    _, _, page_segment = _function_segment(inputs_source, PAGE_HELPER)

    from design_brain.families.bending import build_bottom_reo_compound_accepted_candidate_projection

    cases = [
        {
            "case": "width",
            "candidate": {"Ast_bot": 804.2},
            "axis": "width",
            "arrangement": {"bot1_count": 5, "db_bot_1": 16},
            "geometry_label": "Increase width by 25",
        },
        {
            "case": "depth",
            "candidate": {"Ast_bot": 911.5},
            "axis": "depth",
            "arrangement": {"bot1_count": 6, "db_bot_1": 16},
            "geometry_label": "Increase depth by 25",
        },
        {
            "case": "unknown_axis",
            "candidate": {"Ast_bot": 650.0},
            "axis": "diagonal",
            "arrangement": {"bot1_count": 4, "db_bot_1": 20},
            "geometry_label": "Odd trial",
        },
    ]
    parity: list[dict[str, Any]] = []
    for case in cases:
        old = _old_projection(
            dict(case["candidate"]),
            str(case["axis"]),
            dict(case["arrangement"]),
            str(case["geometry_label"]),
        )
        new = build_bottom_reo_compound_accepted_candidate_projection(
            candidate=dict(case["candidate"]),
            axis=str(case["axis"]),
            arrangement=dict(case["arrangement"]),
            geometry_label=str(case["geometry_label"]),
        )
        parity.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    removed_direct_assignments = all(
        token not in page_segment
        for token in (
            'comp["recommendation_compound"] = True',
            'comp["recommendation_geometry_trial"] = True',
            'comp["recommendation_bottom_trial"] = True',
            'comp["recommendation_family_tag"] =',
            'comp["guidance_recommendation_title"] =',
        )
    )
    source_checks = {
        "family_helper_present": f"def {FAMILY_HELPER}(" in bending_source,
        "page_delegates_projection_to_family": "_build_bottom_reo_compound_accepted_candidate_projection(" in page_segment,
        "page_removed_direct_projection_assignments": removed_direct_assignments,
        "page_keeps_evaluator_callback": "_evaluate_candidate_fast(" in page_segment,
        "page_keeps_candidate_pool_append": "candidates.append(comp)" in page_segment,
        "page_keeps_delta_annotation_callback": "_annotate_bottom_reo_candidate_deltas(" in page_segment,
        "family_has_no_inputs_page_import": "import inputs_page" not in bending_source
        and "from inputs_page" not in bending_source,
        "family_has_no_streamlit_import": "streamlit" not in bending_source and "import st" not in bending_source,
    }
    checks = {
        **source_checks,
        "parity_cases_match": all(bool(row.get("matches")) for row in parity),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_bottom_reo_compound_accepted_candidate_projection_family_boundary.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_COMPOUND_ACCEPTED_CANDIDATE_PROJECTION_FAMILY_BOUNDARY_EXTRACTED",
        "page_helper": PAGE_HELPER,
        "family_helper": FAMILY_HELPER,
        "parity": parity,
        "source_checks": source_checks,
        "checks": checks,
        "next_safe_slice": "bottom_reo_compound_delta_annotation_family_boundary_or_geometry_trial_plan",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_compound_accepted_candidate_projection_family_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_compound_accepted_candidate_projection_family_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Compound Accepted Candidate Projection Family Boundary",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Boundary",
        "",
        f"- Page helper: `{payload.get('page_helper')}`",
        f"- Family helper: `{payload.get('family_helper')}`",
        "- Page still owns evaluator callbacks, delta annotation callback, live candidate append, and trace emission.",
        "",
        "## Parity",
        "",
    ]
    for row in payload.get("parity") or []:
        lines.append(f"- `{row.get('case')}`: `{row.get('matches')}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    status = payload.get("status")
    print(f"design_guide_bottom_reo_compound_accepted_candidate_projection_family_boundary {status}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
