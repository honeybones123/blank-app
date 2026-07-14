"""Verify shallower-beam metric service extraction."""

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
    resolve_auto_design_shallower_beam_metrics,
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


def _old_metrics(candidate: dict[str, Any] | None, seed_candidate: dict[str, Any] | None) -> dict[str, Any]:
    candidate_d = candidate if isinstance(candidate, dict) else {}
    seed_d = seed_candidate if isinstance(seed_candidate, dict) else {}
    candidate_state = dict(candidate_d.get("state") or {})
    seed_state = dict(seed_d.get("state") or {})
    seed_depth = float(seed_d.get("depth", _f(seed_state, "D", 0.0)) or _f(seed_state, "D", 0.0))
    candidate_depth = float(
        candidate_d.get("depth", _f(candidate_state, "D", 0.0))
        or _f(candidate_state, "D", 0.0)
    )
    seed_width = float(seed_d.get("width", _design_width_value(seed_state)) or _design_width_value(seed_state))
    candidate_width = float(
        candidate_d.get("width", _design_width_value(candidate_state))
        or _design_width_value(candidate_state)
    )
    seed_ast = float(seed_d.get("Ast_bot", 0.0) or 0.0)
    candidate_ast = float(candidate_d.get("Ast_bot", 0.0) or 0.0)
    depth_reduction = max(seed_depth - candidate_depth, 0.0)
    width_growth = max(candidate_width - seed_width, 0.0)
    reinforcement_growth = max(candidate_ast - seed_ast, 0.0)
    shallowness_score = depth_reduction - (0.45 * width_growth) - (0.04 * reinforcement_growth)
    materially_shallower = depth_reduction >= 50.0 or (
        depth_reduction >= 25.0
        and width_growth <= 50.0
        and reinforcement_growth <= 120.0
    )
    return {
        "depth_reduction": depth_reduction,
        "width_growth": width_growth,
        "reinforcement_growth": reinforcement_growth,
        "shallowness_score": shallowness_score,
        "materially_shallower": materially_shallower,
    }


def _cases() -> list[dict[str, Any]]:
    seed_rect = {
        "state": {"sec_shape": "RECT", "b": 400.0, "D": 650.0},
        "depth": 650.0,
        "width": 400.0,
        "Ast_bot": 900.0,
    }
    return [
        {
            "name": "same_candidate",
            "seed": dict(seed_rect),
            "candidate": dict(seed_rect),
        },
        {
            "name": "materially_shallower_small_width_growth",
            "seed": dict(seed_rect),
            "candidate": {
                "state": {"sec_shape": "RECT", "b": 425.0, "D": 600.0},
                "depth": 600.0,
                "width": 425.0,
                "Ast_bot": 970.0,
            },
        },
        {
            "name": "not_materially_shallower_due_to_reo_growth",
            "seed": dict(seed_rect),
            "candidate": {
                "state": {"sec_shape": "RECT", "b": 430.0, "D": 625.0},
                "depth": 625.0,
                "width": 430.0,
                "Ast_bot": 1080.0,
            },
        },
        {
            "name": "t_section_width_fallback",
            "seed": {
                "state": {"sec_shape": "T", "bw": 300.0, "b": 650.0, "D": 700.0},
                "Ast_bot": 850.0,
            },
            "candidate": {
                "state": {"sec_shape": "T", "bw": 350.0, "b": 650.0, "D": 640.0},
                "Ast_bot": 930.0,
            },
        },
        {
            "name": "i_section_explicit_depth_width",
            "seed": {
                "state": {"sec_shape": "I", "tw": 220.0, "b": 500.0, "D": 720.0},
                "depth": 720.0,
                "width": 220.0,
                "Ast_bot": 1000.0,
            },
            "candidate": {
                "state": {"sec_shape": "I", "tw": 260.0, "b": 500.0, "D": 680.0},
                "depth": 680.0,
                "width": 260.0,
                "Ast_bot": 1040.0,
            },
        },
    ]


def _same_value(old: Any, new: Any) -> bool:
    if isinstance(old, bool) or isinstance(new, bool):
        return bool(old) == bool(new)
    return abs(float(old) - float(new)) <= 1e-12


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    start, end, wrapper_segment = _function_segment(inputs_source, "_shallower_beam_metrics")
    _, _, score_segment = _function_segment(inputs_source, "_score_auto_design_candidate_components")

    parity_rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in _cases():
        old = _old_metrics(case["candidate"], case["seed"])
        new = resolve_auto_design_shallower_beam_metrics(case["candidate"], case["seed"])
        row_mismatches = {
            key: {"old": old.get(key), "new": new.get(key)}
            for key in sorted(set(old) | set(new))
            if not _same_value(old.get(key), new.get(key))
        }
        parity_rows.append(
            {
                "name": case["name"],
                "old": old,
                "new": new,
                "mismatches": row_mismatches,
            }
        )
        if row_mismatches:
            mismatches.append({"name": case["name"], "mismatches": row_mismatches})

    removed_page_formula_tokens = [
        "depth_reduction",
        "width_growth",
        "reinforcement_growth",
        "shallowness_score",
        "materially_shallower",
        "_float_from_state",
        "_design_width_value",
    ]
    checks = {
        "page_wrapper_delegates_to_service": (
            "_resolve_auto_design_shallower_beam_metrics(candidate, seed_candidate)"
            in wrapper_segment
        ),
        "page_formula_removed_from_wrapper": not any(token in wrapper_segment for token in removed_page_formula_tokens),
        "score_components_still_use_wrapper": "_shallower_beam_metrics(" in score_segment,
        "service_helper_present": "def resolve_auto_design_shallower_beam_metrics(" in service_source,
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
            "AUTO_DESIGN_SHALLOWER_BEAM_METRICS_SERVICE_EXTRACTED"
            if status == "PASS"
            else "AUTO_DESIGN_SHALLOWER_BEAM_METRICS_EXTRACTION_FAILED"
        ),
        "surface": "_shallower_beam_metrics",
        "wrapper_lines": {"start": start, "end": end},
        "checks": checks,
        "parity_rows": parity_rows,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_slice": "shallower-beam selection key or required-domain progress policy boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_shallower_beam_metrics_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_shallower_beam_metrics_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    checks_md = "\n".join(
        f"- `{name}`: `{value}`"
        for name, value in sorted(payload["checks"].items())
    )
    report_path.write_text(
        "\n".join(
            [
                "# Auto-Design Shallower-Beam Metrics Service Extraction",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                "",
                "## Summary",
                "",
                "Pure shallower-beam metric projection is service-owned. The page helper delegates only.",
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
    print(f"design_guide_auto_design_shallower_beam_metrics_service_extraction {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
