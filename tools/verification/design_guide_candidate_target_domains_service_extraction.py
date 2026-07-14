"""Verify candidate target-domain normalization service extraction."""

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

from design_brain.candidate_evaluation import resolve_candidate_target_domains_for_band  # noqa: E402


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


def _old_domains(candidate: dict[str, Any] | None) -> list[str]:
    if not isinstance(candidate, dict):
        return []
    raw = candidate.get("target_domains_for_band")
    if not isinstance(raw, list) or not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        d = str(item or "").strip().lower()
        if d in ("flexure", "ductility", "bottom", "bottom_reo"):
            d = "bending"
        if d not in ("bending", "shear"):
            continue
        if d not in seen:
            out.append(d)
            seen.add(d)
    return out


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, wrapper = _function_segment(inputs_source, "_candidate_target_domains_for_band")
    cases = [
        ("normal_bending_shear", {"target_domains_for_band": ["bending", "shear"]}),
        ("alias_flexure", {"target_domains_for_band": ["flexure"]}),
        ("alias_ductility_bottom", {"target_domains_for_band": ["ductility", "bottom", "bottom_reo"]}),
        ("dedupe_preserves_order", {"target_domains_for_band": ["shear", "bending", "shear", "flexure"]}),
        ("case_and_whitespace", {"target_domains_for_band": ["  SHEAR ", " Bottom_Reo "]}),
        ("invalid_filtered", {"target_domains_for_band": ["crack", "", None, "deflection"]}),
        ("mixed_invalid_valid", {"target_domains_for_band": ["crack", "shear", "bottom"]}),
        ("empty_list", {"target_domains_for_band": []}),
        ("non_list", {"target_domains_for_band": "bending"}),
        ("missing", {}),
        ("non_dict", None),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, candidate in cases:
        old = _old_domains(candidate)
        new = resolve_candidate_target_domains_for_band(candidate)
        row = {"case": name, "old": old, "new": new, "matches": old == new}
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_thin = (
        "_resolve_candidate_target_domains_for_band(candidate)" in wrapper
        and "seen: set" not in wrapper
        and "bottom_reo" not in wrapper
        and "for item in raw" not in wrapper
    )
    service_present = "def resolve_candidate_target_domains_for_band(" in candidate_source
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
        "next_safe_slice": "candidate domain-util projection service extraction",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_candidate_target_domains_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_candidate_target_domains_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Target Domains Service Extraction",
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
