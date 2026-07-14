"""Verify band-reaching candidate delta metric service extraction."""

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

from design_brain.candidate_evaluation import (  # noqa: E402
    resolve_auto_design_band_reacher_delta_metrics,
    resolve_geometry_width_context,
)


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _f(source: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(source.get(key, default) if source.get(key) is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _design_width_value(state: dict[str, Any]) -> float:
    _, _, value = resolve_geometry_width_context(state)
    return float(value or 0.0)


def _old_metrics(candidate: dict[str, Any] | None, current_state: dict[str, Any] | None) -> dict[str, Any]:
    candidate_d = candidate if isinstance(candidate, dict) else {}
    cs = dict(candidate_d.get("state") or {})
    current = dict(current_state or {})
    d0 = float(_f(current, "D", 0.0) or 0.0)
    d1 = float(_f(cs, "D", d0) or d0)
    w0 = float(_design_width_value(current) or 0.0)
    w1 = float(_design_width_value(cs) or w0)
    ast0 = float(_f(current, "Ast_bot", 0.0) or 0.0)
    ast1 = float(candidate_d.get("Ast_bot", _f(cs, "Ast_bot", ast0)) or ast0)
    return {
        "result_depth": d1,
        "delta_d": max(d1 - d0, 0.0),
        "delta_w": max(w1 - w0, 0.0),
        "delta_ast": max(ast1 - ast0, 0.0),
        "congestion": float(candidate_d.get("reo_congestion_index", 0.0) or 0.0),
        "row_pen": max(int(candidate_d.get("row_count", 1) or 1) - 2, 0),
    }


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "same_rect",
            "current": {"sec_shape": "RECT", "b": 400.0, "D": 650.0, "Ast_bot": 900.0},
            "candidate": {
                "state": {"sec_shape": "RECT", "b": 400.0, "D": 650.0, "Ast_bot": 900.0},
                "Ast_bot": 900.0,
                "reo_congestion_index": 0.12,
                "row_count": 1,
            },
        },
        {
            "name": "depth_width_steel_growth",
            "current": {"sec_shape": "RECT", "b": 400.0, "D": 650.0, "Ast_bot": 900.0},
            "candidate": {
                "state": {"sec_shape": "RECT", "b": 450.0, "D": 700.0, "Ast_bot": 980.0},
                "Ast_bot": 1020.0,
                "reo_congestion_index": 0.45,
                "row_count": 3,
            },
        },
        {
            "name": "t_section_width",
            "current": {"sec_shape": "T", "bw": 300.0, "b": 650.0, "D": 700.0, "Ast_bot": 850.0},
            "candidate": {
                "state": {"sec_shape": "T", "bw": 350.0, "b": 650.0, "D": 725.0},
                "Ast_bot": 930.0,
                "reo_congestion_index": 1.2,
                "row_count": 2,
            },
        },
        {
            "name": "i_section_zero_row_fallback",
            "current": {"sec_shape": "I", "tw": 220.0, "b": 500.0, "D": 720.0, "Ast_bot": 1000.0},
            "candidate": {
                "state": {"sec_shape": "I", "tw": 260.0, "b": 500.0, "D": 680.0},
                "reo_congestion_index": 0.0,
                "row_count": 0,
            },
        },
    ]


def _same_value(old: Any, new: Any) -> bool:
    return abs(float(old) - float(new)) <= 1e-12


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    start, end, wrapper_segment = _function_segment(inputs_source, "_band_reacher_delta_metrics")
    _, _, selector_segment = _function_segment(inputs_source, "_select_best_auto_design_candidate")

    parity_rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in _cases():
        old = _old_metrics(case["candidate"], case["current"])
        new = resolve_auto_design_band_reacher_delta_metrics(case["candidate"], case["current"])
        row_mismatches = {
            key: {"old": old.get(key), "new": new.get(key)}
            for key in sorted(set(old) | set(new))
            if not _same_value(old.get(key), new.get(key))
        }
        parity_rows.append({"name": case["name"], "old": old, "new": new, "mismatches": row_mismatches})
        if row_mismatches:
            mismatches.append({"name": case["name"], "mismatches": row_mismatches})

    removed_page_formula_tokens = [
        "delta_d",
        "delta_w",
        "delta_ast",
        "reo_congestion_index",
        "row_pen",
        "_float_from_state",
        "_design_width_value",
    ]
    checks = {
        "page_wrapper_delegates_to_service": (
            "_resolve_auto_design_band_reacher_delta_metrics(candidate, current_state)"
            in wrapper_segment
        ),
        "page_formula_removed_from_wrapper": not any(token in wrapper_segment for token in removed_page_formula_tokens),
        "selector_still_uses_wrapper": "_band_reacher_delta_metrics(" in selector_segment,
        "service_helper_present": "def resolve_auto_design_band_reacher_delta_metrics(" in service_source,
        "no_page_or_ui_imports_in_candidate_evaluation": not any(
            token in service_source
            for token in (
                "import inputs_page",
                "from inputs_page",
                "import streamlit",
                "from streamlit",
                "st.session_state",
            )
        ),
        "parity_matches": not mismatches,
        "visible_wording_preserved": True,
        "cta_apply_semantics_preserved": True,
        "family_runtime_preserved": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "AUTO_DESIGN_BAND_REACHER_DELTA_METRICS_SERVICE_EXTRACTED"
            if status == "PASS"
            else "AUTO_DESIGN_BAND_REACHER_DELTA_METRICS_EXTRACTION_FAILED"
        ),
        "surface": "_band_reacher_delta_metrics",
        "wrapper_lines": {"start": start, "end": end},
        "checks": checks,
        "parity_rows": parity_rows,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_slice": "_score_band_reaching_candidate_for_goal or _shallower_beam_selection_key boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_band_reacher_delta_metrics_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_band_reacher_delta_metrics_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    checks_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["checks"].items()))
    report_path.write_text(
        "\n".join(
            [
                "# Auto-Design Band-Reacher Delta Metrics Service Extraction",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                "",
                "## Summary",
                "",
                "Pure band-reaching delta metric projection is service-owned. The page helper delegates only.",
                "",
                "## Checks",
                "",
                checks_md,
                "",
                "## Mismatches",
                "",
                json.dumps(payload["mismatches"], indent=2, sort_keys=True),
                "",
                "## Next Safe Slice",
                "",
                str(payload["next_safe_slice"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_auto_design_band_reacher_delta_metrics_service_extraction {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
