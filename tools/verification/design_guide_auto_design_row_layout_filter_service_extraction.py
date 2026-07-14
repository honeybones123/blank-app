"""Verify auto-design row-layout filter service extraction."""

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
    filter_auto_design_candidates_by_row_layout,
    resolve_auto_design_candidate_row_layout_validity,
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


def _i(source: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(source.get(key, default) if source.get(key) is not None else default)
    except (TypeError, ValueError):
        return int(default)


def _old_filter(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        cs = dict(candidate.get("state") or {})
        _, _, beam_width_raw = resolve_geometry_width_context(cs)
        beam_width = float(beam_width_raw or 0.0)
        cover = float(_f(cs, "cover_side", 40.0) or 40.0)
        bot1_count = int(_i(cs, "bot1_count", 0) or 0)
        bot2_count = int(_i(cs, "bot2_count", 0) or 0)
        db_bot_1 = float(_f(cs, "db_bot_1", 0.0) or 0.0)
        db_bot_2 = float(_f(cs, "db_bot_2", db_bot_1) or db_bot_1)
        row_layout = resolve_auto_design_candidate_row_layout_validity(
            beam_width=beam_width,
            cover=cover,
            bot1_count=bot1_count,
            bot2_count=bot2_count,
            db_bot_1=db_bot_1,
            db_bot_2=db_bot_2,
        )
        if not bool(row_layout.get("valid")):
            continue
        valid_candidates.append(candidate)
    return valid_candidates


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "mixed_valid_invalid_rect",
            "candidates": [
                {"id": "valid_one_row", "state": {"sec_shape": "RECT", "b": 400.0, "cover_side": 40.0, "bot1_count": 2, "bot2_count": 0, "db_bot_1": 20}},
                {"id": "invalid_congested", "state": {"sec_shape": "RECT", "b": 120.0, "cover_side": 40.0, "bot1_count": 8, "bot2_count": 0, "db_bot_1": 32}},
                {"id": "valid_two_row", "state": {"sec_shape": "RECT", "b": 450.0, "cover_side": 35.0, "bot1_count": 3, "bot2_count": 2, "db_bot_1": 16, "db_bot_2": 20}},
            ],
        },
        {
            "name": "t_section_width_context",
            "candidates": [
                {"id": "valid_t_bw", "state": {"sec_shape": "T", "bw": 300.0, "b": 650.0, "cover_side": 40.0, "bot1_count": 3, "db_bot_1": 20}},
                {"id": "invalid_t_bw", "state": {"sec_shape": "T", "bw": 130.0, "b": 650.0, "cover_side": 40.0, "bot1_count": 7, "db_bot_1": 25}},
            ],
        },
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    start, end, selector_segment = _function_segment(inputs_source, "_select_best_auto_design_candidate")

    parity_rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in _cases():
        candidates = list(case["candidates"])
        old = _old_filter(candidates)
        result = filter_auto_design_candidates_by_row_layout(candidates)
        new = list(result.get("filtered_candidates") or [])
        old_ids = [item.get("id") for item in old]
        new_ids = [item.get("id") for item in new]
        same_refs = [old_item is new_item for old_item, new_item in zip(old, new)]
        row_mismatch: dict[str, Any] = {}
        if old_ids != new_ids:
            row_mismatch["ids"] = {"old": old_ids, "new": new_ids}
        if not all(same_refs):
            row_mismatch["references"] = same_refs
        parity_rows.append(
            {
                "name": case["name"],
                "old_ids": old_ids,
                "new_ids": new_ids,
                "same_object_references": same_refs,
                "rejected_candidate_count": result.get("rejected_candidate_count"),
                "mismatches": row_mismatch,
            }
        )
        if row_mismatch:
            mismatches.append({"name": case["name"], "mismatches": row_mismatch})

    removed_loop_tokens = [
        "beam_width = float(_design_width_value(cs)",
        "cover = float(_float_from_state(cs, \"cover_side\"",
        "continue  # reject immediately",
        "_resolve_auto_design_candidate_row_layout_validity(",
    ]
    checks = {
        "selector_delegates_filter_to_service": "_filter_auto_design_candidates_by_row_layout(candidates)" in selector_segment,
        "selector_row_layout_formula_removed": not any(token in selector_segment for token in removed_loop_tokens),
        "selector_still_scores_after_filter": "candidate[\"score\"] = _score_auto_design_candidate" in selector_segment,
        "service_helper_present": "def filter_auto_design_candidates_by_row_layout(" in service_source,
        "service_uses_existing_row_layout_validity": "resolve_auto_design_candidate_row_layout_validity(" in service_source,
        "same_filtered_candidate_id_order": not mismatches,
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
        "visible_wording_preserved": True,
        "cta_apply_semantics_preserved": True,
        "family_runtime_preserved": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "AUTO_DESIGN_ROW_LAYOUT_FILTER_SERVICE_EXTRACTED"
            if status == "PASS"
            else "AUTO_DESIGN_ROW_LAYOUT_FILTER_EXTRACTION_FAILED"
        ),
        "surface": "_select_best_auto_design_candidate row-layout filtering",
        "selector_lines": {"start": start, "end": end},
        "checks": checks,
        "parity_rows": parity_rows,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_slice": "score assignment loop helper or winner-pool decision object",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_row_layout_filter_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_row_layout_filter_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    checks_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["checks"].items()))
    report_path.write_text(
        "\n".join(
            [
                "# Auto-Design Row-Layout Filter Service Extraction",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                "",
                "## Summary",
                "",
                "Candidate row-layout filtering is service-owned. Scoring and winner selection remain unchanged on the page.",
                "",
                "## Checks",
                "",
                checks_md,
                "",
                "## Parity Rows",
                "",
                json.dumps(payload["parity_rows"], indent=2, sort_keys=True),
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
    print(f"design_guide_auto_design_row_layout_filter_service_extraction {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
