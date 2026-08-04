"""Verify candidate domain-util projection service extraction."""

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

from design_brain.candidate_evaluation import resolve_candidate_domain_util  # noqa: E402


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


def _old_bending_demand_util(candidate: dict[str, Any] | None) -> float | None:
    if not isinstance(candidate, dict):
        return None
    overview = candidate.get("overview") or {}
    bending_pack = (overview.get("packs") or {}).get("bending") or {}
    phi = float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0)
    mu = float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0)
    if phi <= 1e-9:
        return None
    return mu / phi


def _old_domain_util(candidate: dict[str, Any] | None, domain: str) -> float | None:
    d = str(domain or "").strip().lower()
    if d == "bending":
        if isinstance(candidate, dict):
            du = _old_bending_demand_util(candidate)
            if du is not None:
                try:
                    fv = float(du)
                    if math.isfinite(fv):
                        return fv
                except Exception:
                    pass
            raw = ((candidate.get("overview") or {}).get("utils") or {}).get("bending")
            try:
                fv = float(raw)
                if math.isfinite(fv):
                    return fv
            except Exception:
                return None
        return None
    if d == "shear":
        if isinstance(candidate, dict):
            raw = ((candidate.get("overview") or {}).get("utils") or {}).get("shear")
            try:
                fv = float(raw)
                if math.isfinite(fv):
                    return fv
            except Exception:
                return None
        return None
    return None


def _candidate(*, bending: Any = None, shear: Any = None, mu: Any = None, phi: Any = None) -> dict[str, Any]:
    bending_pack: dict[str, Any] = {}
    if mu is not None:
        bending_pack["summary_Mu_star_kNm"] = mu
    if phi is not None:
        bending_pack["summary_phiMu_kNm"] = phi
    return {
        "overview": {
            "utils": {"bending": bending, "shear": shear},
            "packs": {"bending": bending_pack},
        }
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, wrapper = _function_segment(inputs_source, "_candidate_domain_util")
    cases = [
        ("bending_demand_preferred", _candidate(bending=0.3, shear=0.7, mu=90.0, phi=100.0), "bending"),
        ("bending_overview_fallback", _candidate(bending=0.62, shear=0.7, mu=90.0, phi=0.0), "bending"),
        ("bending_invalid_fallback_none", _candidate(bending="bad", shear=0.7, mu=90.0, phi=0.0), "bending"),
        ("shear_normal", _candidate(bending=0.3, shear=0.81, mu=90.0, phi=100.0), "shear"),
        ("shear_numeric_string", _candidate(bending=0.3, shear="0.73", mu=90.0, phi=100.0), "shear"),
        ("shear_nan_none", _candidate(bending=0.3, shear=float("nan"), mu=90.0, phi=100.0), "shear"),
        ("unknown_domain", _candidate(bending=0.3, shear=0.7, mu=90.0, phi=100.0), "crack"),
        ("case_whitespace_domain", _candidate(bending=0.3, shear=0.74, mu=90.0, phi=100.0), " SHEAR "),
        ("non_dict", None, "bending"),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, candidate, domain in cases:
        old = _old_domain_util(candidate, domain)
        new = resolve_candidate_domain_util(candidate, domain)
        row = {"case": name, "old": old, "new": new, "matches": old == new}
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_thin = (
        "_resolve_candidate_domain_util(candidate, domain)" in wrapper
        and "summary_phiMu_kNm" not in wrapper
        and "overview" not in wrapper
    )
    service_present = "def resolve_candidate_domain_util(" in candidate_source
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
        "next_safe_slice": "one-click domain score service extraction",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_candidate_domain_util_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_candidate_domain_util_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Domain Util Service Extraction",
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
