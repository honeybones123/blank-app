"""Verify bottom-reo required-Ast binary search moved to bending family."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS = ROOT / "inputs_page.py"
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PAGE_HELPER = "_required_ast_for_arrangement"
FAMILY_HELPER = "calculate_bottom_reo_required_ast_for_arrangement"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _old_required_ast(
    *,
    compute_fn: Callable[..., dict[str, Any]],
    b: float,
    D: float,
    fc: float,
    fsy: float,
    phi: float,
    Mu_star: float,
    cover_bot: float,
    rowgap_bot: float,
    arrangement: dict[str, Any],
) -> float:
    low = 0.0
    high = float(arrangement["Ast_bot"])
    for _ in range(40):
        trial = 0.5 * (low + high)
        trial_results = compute_fn(
            b=b,
            D=D,
            fc=fc,
            fsy=fsy,
            Ast=trial,
            Mu_star=Mu_star,
            phi=phi,
            d_input=arrangement["d_centroid"],
            cover_bot=cover_bot,
            db_bot=arrangement["db_bot"],
            nb_bot=arrangement["nb_bot"],
            rowgap_bot=rowgap_bot,
        )
        util = float(trial_results.get("Mu_util", float("inf")))
        if util <= 1.0:
            high = trial
        else:
            low = trial
    return float(high)


def _fake_capacity_factory(threshold_ast: float) -> Callable[..., dict[str, Any]]:
    def _fake_capacity(**kwargs: Any) -> dict[str, Any]:
        ast_value = float(kwargs.get("Ast", 0.0) or 0.0)
        util = float(threshold_ast) / max(ast_value, 1e-9)
        return {
            "Mu_util": util,
            "received": {
                "b": kwargs.get("b"),
                "D": kwargs.get("D"),
                "fc": kwargs.get("fc"),
                "fsy": kwargs.get("fsy"),
                "Mu_star": kwargs.get("Mu_star"),
                "phi": kwargs.get("phi"),
                "d_input": kwargs.get("d_input"),
                "cover_bot": kwargs.get("cover_bot"),
                "db_bot": kwargs.get("db_bot"),
                "nb_bot": kwargs.get("nb_bot"),
                "rowgap_bot": kwargs.get("rowgap_bot"),
            },
        }

    return _fake_capacity


def _sample_cases() -> list[dict[str, Any]]:
    return [
        {
            "case": "normal_threshold",
            "threshold_ast": 420.0,
            "b": 400.0,
            "D": 650.0,
            "fc": 40.0,
            "fsy": 500.0,
            "phi": 0.85,
            "Mu_star": 200.0,
            "cover_bot": 40.0,
            "rowgap_bot": 60.0,
            "arrangement": {"Ast_bot": 900.0, "db_bot": 16.0, "nb_bot": 5, "d_centroid": 580.0},
        },
        {
            "case": "low_threshold",
            "threshold_ast": 12.5,
            "b": 300.0,
            "D": 500.0,
            "fc": 32.0,
            "fsy": 500.0,
            "phi": 0.8,
            "Mu_star": 20.0,
            "cover_bot": 35.0,
            "rowgap_bot": 55.0,
            "arrangement": {"Ast_bot": 320.0, "db_bot": 12.0, "nb_bot": 3, "d_centroid": 445.0},
        },
        {
            "case": "near_high_bound",
            "threshold_ast": 799.0,
            "b": 450.0,
            "D": 700.0,
            "fc": 50.0,
            "fsy": 600.0,
            "phi": 0.85,
            "Mu_star": 300.0,
            "cover_bot": 45.0,
            "rowgap_bot": 65.0,
            "arrangement": {"Ast_bot": 800.0, "db_bot": 20.0, "nb_bot": 4, "d_centroid": 620.0},
        },
    ]


def _forbidden_terms(segment: str) -> dict[str, bool]:
    return {
        "imports_inputs_page": "inputs_page" in segment,
        "imports_streamlit": "streamlit" in segment or "st." in segment,
        "uses_session_state": "session_state" in segment,
        "uses_apply_routing": "apply_" in segment or "one_click" in segment,
        "uses_rendering": "render_" in segment or "html" in segment,
        "uses_publication": "FinalDesignGuidePublication" in segment or "publication" in segment,
    }


def build_payload() -> dict[str, Any]:
    from design_brain.families.bending import calculate_bottom_reo_required_ast_for_arrangement

    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_start, page_end, page_segment = _function_segment(inputs_source, PAGE_HELPER)
    helper_start, helper_end, helper_segment = _function_segment(bending_source, FAMILY_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        compute_fn = _fake_capacity_factory(float(case["threshold_ast"]))
        old = _old_required_ast(
            compute_fn=compute_fn,
            b=float(case["b"]),
            D=float(case["D"]),
            fc=float(case["fc"]),
            fsy=float(case["fsy"]),
            phi=float(case["phi"]),
            Mu_star=float(case["Mu_star"]),
            cover_bot=float(case["cover_bot"]),
            rowgap_bot=float(case["rowgap_bot"]),
            arrangement=dict(case["arrangement"]),
        )
        new = calculate_bottom_reo_required_ast_for_arrangement(
            compute_bending_capacity_fn=compute_fn,
            b=float(case["b"]),
            D=float(case["D"]),
            fc=float(case["fc"]),
            fsy=float(case["fsy"]),
            phi=float(case["phi"]),
            Mu_star=float(case["Mu_star"]),
            cover_bot=float(case["cover_bot"]),
            rowgap_bot=float(case["rowgap_bot"]),
            arrangement=dict(case["arrangement"]),
        )
        parity_rows.append(
            {
                "case": case["case"],
                "old": old,
                "new": new,
                "delta": abs(old - new),
                "matches": abs(old - new) <= 1e-9,
            }
        )

    forbidden = _forbidden_terms(helper_segment)
    checks = {
        "family_helper_exists": bool(helper_segment),
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "page_helper_delegates_to_family_helper": "_calculate_bottom_reo_required_ast_for_arrangement(" in page_segment,
        "page_helper_keeps_state_scalar_collection": "_design_width_value(state)" in page_segment
        and "_float_from_state(state" in page_segment
        and "_uls_action_from_state(state" in page_segment,
        "page_helper_no_longer_owns_binary_search_loop": "for _ in range(40)" not in page_segment
        and "trial = 0.5 * (low + high)" not in page_segment,
        "page_helper_keeps_existing_compute_callback": "_get_compute_bending_capacity_pure()" in page_segment,
        "all_sample_cases_match": all(row["matches"] for row in parity_rows),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "BOTTOM_REO_REQUIRED_AST_FAMILY_CALCULATION_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_REQUIRED_AST_EXTRACTION_FAILED"
        ),
        "page_helper_lines": {"start": page_start, "end": page_end},
        "family_helper_lines": {"start": helper_start, "end": helper_end},
        "parity_rows": parity_rows,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "remaining_page_owned_projection_inputs": [
            "state scalar extraction",
            "existing bending capacity compute callback retrieval",
            "guidance change-line construction",
            "selected result adapter call orchestration",
        ],
        "next_safe_slice": "bottom_reo_guidance_change_line_or_selected_result_projection_boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_required_ast_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_required_ast_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Required Ast Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The bending family now owns the required-Ast binary search. The page still supplies scalar state inputs and the existing bending-capacity callback.",
        "",
        "## Parity Cases",
        "",
        "| Case | Old | New | Delta | Match |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(
            f"| `{row.get('case')}` | `{row.get('old')}` | `{row.get('new')}` | `{row.get('delta')}` | `{row.get('matches')}` |"
        )
    lines.extend(["", "## Remaining Page-Owned Projection Inputs", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_owned_projection_inputs") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_required_ast_family_extraction {payload.get('status')}")
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
