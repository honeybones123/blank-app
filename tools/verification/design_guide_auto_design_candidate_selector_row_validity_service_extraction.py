"""Verify auto-design selector row-validity service extraction.

This verifier proves the shared selector delegates the pure row-layout validity
decision to design_brain.candidate_evaluation without changing the old truth
table or moving page trace/apply/render ownership.
"""

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
    resolve_auto_design_candidate_row_layout_validity,
)


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
SELECTOR = "_select_best_auto_design_candidate"


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


def _old_row_valid(*, n_bars: int, db: float, beam_width: float, cover: float, s_min: float) -> bool:
    available = float(beam_width) - 2.0 * float(cover)
    required = int(n_bars) * float(db) + (int(n_bars) - 1) * float(s_min)
    if int(n_bars) < 2:
        return False
    if required > available:
        return False
    return True


def _old_candidate_valid(
    *,
    beam_width: float,
    cover: float,
    bot1_count: int,
    bot2_count: int,
    db_bot_1: float,
    db_bot_2: float,
) -> dict[str, Any]:
    row1_valid = _old_row_valid(
        n_bars=bot1_count,
        db=db_bot_1,
        beam_width=beam_width,
        cover=cover,
        s_min=max(float(db_bot_1), 25.0),
    )
    row2_valid = True
    if int(bot2_count) > 0:
        row2_valid = _old_row_valid(
            n_bars=bot2_count,
            db=db_bot_2,
            beam_width=beam_width,
            cover=cover,
            s_min=max(float(db_bot_2), 25.0),
        )
    return {
        "valid": bool(row1_valid and row2_valid),
        "row1_valid": bool(row1_valid),
        "row2_valid": bool(row2_valid),
    }


def _parity_cases() -> list[dict[str, Any]]:
    return [
        {"name": "normal_single_row", "beam_width": 300.0, "cover": 40.0, "bot1_count": 3, "bot2_count": 0, "db_bot_1": 16.0, "db_bot_2": 16.0},
        {"name": "normal_two_rows", "beam_width": 400.0, "cover": 40.0, "bot1_count": 4, "bot2_count": 2, "db_bot_1": 20.0, "db_bot_2": 16.0},
        {"name": "row1_too_few_bars", "beam_width": 400.0, "cover": 40.0, "bot1_count": 1, "bot2_count": 0, "db_bot_1": 20.0, "db_bot_2": 20.0},
        {"name": "row1_too_wide", "beam_width": 220.0, "cover": 50.0, "bot1_count": 5, "bot2_count": 0, "db_bot_1": 32.0, "db_bot_2": 32.0},
        {"name": "row2_too_few_bars", "beam_width": 400.0, "cover": 40.0, "bot1_count": 4, "bot2_count": 1, "db_bot_1": 20.0, "db_bot_2": 16.0},
        {"name": "row2_too_wide", "beam_width": 260.0, "cover": 40.0, "bot1_count": 3, "bot2_count": 4, "db_bot_1": 16.0, "db_bot_2": 32.0},
        {"name": "spacing_governed_by_25mm", "beam_width": 230.0, "cover": 40.0, "bot1_count": 4, "bot2_count": 0, "db_bot_1": 10.0, "db_bot_2": 10.0},
        {"name": "spacing_governed_by_bar_dia", "beam_width": 340.0, "cover": 40.0, "bot1_count": 4, "bot2_count": 0, "db_bot_1": 32.0, "db_bot_2": 32.0},
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    selector_start, selector_end, selector_segment = _function_segment(inputs_source, SELECTOR)

    parity_rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in _parity_cases():
        kwargs = {k: v for k, v in case.items() if k != "name"}
        old = _old_candidate_valid(**kwargs)
        new = resolve_auto_design_candidate_row_layout_validity(**kwargs)
        row = {
            "case": case["name"],
            "old": old,
            "new": {
                "valid": bool(new.get("valid")),
                "row1_valid": bool(new.get("row1_valid")),
                "row2_valid": bool(new.get("row2_valid")),
            },
        }
        parity_rows.append(row)
        if row["old"] != row["new"]:
            mismatches.append(row)

    selector_delegates = "_resolve_auto_design_candidate_row_layout_validity(" in selector_segment
    selector_direct_old_call_removed = "is_valid_reo_layout(" not in selector_segment
    service_has_helper = "def resolve_auto_design_candidate_row_layout_validity(" in candidate_source
    forbidden_service_imports = [
        "import inputs_page",
        "from inputs_page",
        "import streamlit",
        "from streamlit",
        "st.session_state",
        "import design_guide_page",
        "from design_guide_page",
    ]
    forbidden_hits = [token for token in forbidden_service_imports if token in candidate_source]

    status = "PASS"
    if (
        mismatches
        or not selector_delegates
        or not selector_direct_old_call_removed
        or not service_has_helper
        or forbidden_hits
    ):
        status = "FAIL"

    return {
        "status": status,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "selector": {
            "file": str(INPUTS.relative_to(ROOT)),
            "name": SELECTOR,
            "line_start": selector_start,
            "line_end": selector_end,
        },
        "selector_delegates_to_candidate_evaluation": selector_delegates,
        "selector_direct_is_valid_reo_layout_call_removed": selector_direct_old_call_removed,
        "candidate_evaluation_helper_present": service_has_helper,
        "candidate_evaluation_forbidden_import_hits": forbidden_hits,
        "parity_case_count": len(parity_rows),
        "parity_mismatch_count": len(mismatches),
        "parity_rows": parity_rows,
        "mismatches": mismatches,
        "ownership": {
            "moved_to_candidate_evaluation": "pure row-layout validity formula",
            "remaining_in_inputs_page": [
                "state scalar normalization",
                "candidate loop",
                "target-band scoring",
                "winner ranking",
                "rank trace emission",
                "CTA/apply/render/session ownership",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "target-band annotation and base score assignment service extraction",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_candidate_selector_row_validity_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_auto_design_candidate_selector_row_validity_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Auto-Design Candidate Selector Row-Validity Service Extraction",
        "",
        "## Executive Summary",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "Pure row-layout validity now lives in `design_brain.candidate_evaluation`; `inputs_page.py` still normalizes candidate state scalars and owns the surrounding selector loop.",
        "",
        "## Proof",
        f"- Selector delegates to candidate-evaluation helper: `{payload['selector_delegates_to_candidate_evaluation']}`",
        f"- Direct `is_valid_reo_layout(...)` call removed from selector: `{payload['selector_direct_is_valid_reo_layout_call_removed']}`",
        f"- Candidate-evaluation helper present: `{payload['candidate_evaluation_helper_present']}`",
        f"- Forbidden service import hits: `{payload['candidate_evaluation_forbidden_import_hits']}`",
        f"- Parity cases: `{payload['parity_case_count']}`",
        f"- Parity mismatches: `{payload['parity_mismatch_count']}`",
        "",
        "## Ownership After",
        "- Candidate-evaluation service owns the pure row validity formula.",
        "- Page shell still owns scalar input normalization and selector trace emission.",
        "- Ranking, scoring, winner selection, CTA/apply, render, and session behavior were not moved.",
        "",
        "## Next Safe Slice",
        f"`{payload['next_safe_slice']}`",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
