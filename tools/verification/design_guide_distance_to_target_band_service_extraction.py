"""Verify distance-to-target-band service extraction."""

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

from design_brain.candidate_evaluation import resolve_distance_to_target_band  # noqa: E402


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


def _old_distance(util: Any, target_min: Any, target_max: Any) -> float:
    try:
        u = float(util)
        lo = float(target_min)
        hi = float(target_max)
    except (TypeError, ValueError):
        return float("inf")
    if lo <= u <= hi:
        return 0.0
    if u < lo:
        return lo - u
    return u - hi


def _same(a: float, b: float) -> bool:
    if math.isinf(a) and math.isinf(b):
        return True
    return a == b


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, wrapper = _function_segment(inputs_source, "_distance_to_target_band")
    cases = [
        ("inside_band", 0.88, 0.85, 1.0),
        ("at_low", 0.85, 0.85, 1.0),
        ("at_high", 1.0, 0.85, 1.0),
        ("below_band", 0.72, 0.85, 1.0),
        ("above_band", 1.12, 0.85, 1.0),
        ("numeric_strings", "0.72", "0.85", "1.0"),
        ("invalid_util", "bad", 0.85, 1.0),
        ("invalid_low", 0.9, "bad", 1.0),
        ("none_high", 0.9, 0.85, None),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, util, lo, hi in cases:
        old = _old_distance(util, lo, hi)
        new = resolve_distance_to_target_band(util, lo, hi)
        row = {
            "case": name,
            "old": "inf" if math.isinf(old) else old,
            "new": "inf" if math.isinf(new) else new,
            "matches": _same(old, new),
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_thin = (
        "_resolve_distance_to_target_band(util, target_min, target_max)" in wrapper
        and "float(util)" not in wrapper
    )
    service_present = "def resolve_distance_to_target_band(" in candidate_source
    forbidden_hits = [
        token
        for token in (
            "import inputs_page",
            "from inputs_page",
            "import streamlit",
            "from streamlit",
            "st.session_state",
        )
        if token in candidate_source
    ]
    status = "PASS"
    if mismatches or not wrapper_thin or not service_present or forbidden_hits:
        status = "FAIL"
    return {
        "status": status,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "wrapper_thin": wrapper_thin,
        "service_present": service_present,
        "forbidden_service_import_hits": forbidden_hits,
        "case_count": len(rows),
        "mismatch_count": len(mismatches),
        "rows": rows,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "next_safe_slice": "target-band metric annotation service extraction",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_distance_to_target_band_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_distance_to_target_band_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Distance To Target Band Service Extraction",
        "",
        "## Executive Summary",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Proof",
        f"- Thin page wrapper: `{payload['wrapper_thin']}`",
        f"- Service helper present: `{payload['service_present']}`",
        f"- Forbidden service import hits: `{payload['forbidden_service_import_hits']}`",
        f"- Cases: `{payload['case_count']}`",
        f"- Mismatches: `{payload['mismatch_count']}`",
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
