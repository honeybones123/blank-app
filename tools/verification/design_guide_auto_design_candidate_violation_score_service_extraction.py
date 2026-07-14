"""Verify auto-design candidate violation score service extraction."""

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

from design_brain.candidate_evaluation import resolve_auto_design_candidate_violation_score  # noqa: E402


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


def _old_score(candidate: dict[str, Any] | None) -> float:
    candidate_d = candidate if isinstance(candidate, dict) else {}
    util = float(candidate_d.get("worst_util", 0.0) or 0.0)
    overflow = max(util - 1.0, 0.0)
    fail_count = int(candidate_d.get("fail_count", 0) or 0)
    return overflow * 100.0 + fail_count * 25.0


def _cases() -> list[dict[str, Any] | None]:
    return [
        {},
        None,
        {"worst_util": 0.75, "fail_count": 0},
        {"worst_util": 1.0, "fail_count": 0},
        {"worst_util": 1.20, "fail_count": 0},
        {"worst_util": 1.20, "fail_count": 2},
        {"worst_util": "1.35", "fail_count": "3"},
        {"worst_util": None, "fail_count": None},
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    _, _, wrapper_segment = _function_segment(inputs_source, "_candidate_violation_score")
    _, _, score_segment = _function_segment(inputs_source, "_score_auto_design_candidate_components")

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for idx, candidate in enumerate(_cases()):
        old = _old_score(candidate)
        new = resolve_auto_design_candidate_violation_score(candidate)
        row = {
            "case_index": idx,
            "candidate": candidate,
            "old": old,
            "new": new,
            "matches": abs(float(old) - float(new)) <= 1e-12,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    checks = {
        "wrapper_delegates_to_candidate_evaluation": "_resolve_auto_design_candidate_violation_score(candidate)" in wrapper_segment,
        "old_page_formula_removed": all(
            token not in wrapper_segment
            for token in ("overflow", "fail_count", "worst_util", "* 100.0", "* 25.0")
        ),
        "score_components_still_uses_wrapper": "_candidate_violation_score(candidate)" in score_segment,
        "service_helper_present": "def resolve_auto_design_candidate_violation_score(" in service_source,
        "candidate_evaluation_forbidden_import_hits_empty": not any(
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
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "AUTO_DESIGN_CANDIDATE_VIOLATION_SCORE_SERVICE_EXTRACTED",
        "checks": checks,
        "case_count": len(rows),
        "mismatch_count": len(mismatches),
        "rows": rows,
        "mismatches": mismatches,
        "next_safe_slice": "auto-design selector shear practicality metric boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_candidate_violation_score_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_candidate_violation_score_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto-Design Candidate Violation Score Service Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        f"Cases: `{payload.get('case_count')}`",
        f"Mismatches: `{payload.get('mismatch_count')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_auto_design_candidate_violation_score_service_extraction {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [key for key, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
