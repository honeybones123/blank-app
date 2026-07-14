"""Verify one-click domain score service extraction."""

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

from design_brain.candidate_evaluation import resolve_candidate_domain_score  # noqa: E402


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_MIN = 0.85
DEFAULT_MAX = 1.0
FAIL = "FAIL"


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


def _old_score(eval_obj: dict[str, Any] | None, domain: str, mode_config: dict[str, Any] | None) -> dict[str, Any]:
    d = str(domain or "").strip().lower()
    overview = dict((eval_obj or {}).get("overview") or {})
    statuses = dict(overview.get("statuses") or {})
    status = statuses.get(d)
    util = _old_domain_util(eval_obj or {}, d)
    try:
        lo = float((mode_config or {}).get("target_util_min", DEFAULT_MIN) or DEFAULT_MIN)
        hi = float((mode_config or {}).get("target_util_max", DEFAULT_MAX) or DEFAULT_MAX)
    except Exception:
        lo = float(DEFAULT_MIN)
        hi = float(DEFAULT_MAX)
    fu = None
    if util is not None:
        try:
            fu = float(util)
            if not math.isfinite(fu):
                fu = None
        except Exception:
            fu = None
    fail = bool(status == FAIL or str(status or "").strip().upper() == "FAIL")
    ok_status = not fail
    dist = float("inf") if fu is None else _old_distance(fu, lo, hi)
    return {
        "domain": d,
        "status": status,
        "util": fu,
        "distance": dist,
        "in_band": bool(fu is not None and lo <= fu <= hi and ok_status),
        "pass": bool(ok_status),
        "under": bool(fu is not None and fu < lo),
        "over": bool(fu is not None and fu > hi),
    }


def _candidate(*, bending: Any = None, shear: Any = None, mu: Any = None, phi: Any = None, statuses: dict[str, Any] | None = None) -> dict[str, Any]:
    bending_pack: dict[str, Any] = {}
    if mu is not None:
        bending_pack["summary_Mu_star_kNm"] = mu
    if phi is not None:
        bending_pack["summary_phiMu_kNm"] = phi
    return {
        "overview": {
            "statuses": dict(statuses or {}),
            "utils": {"bending": bending, "shear": shear},
            "packs": {"bending": bending_pack},
        }
    }


def _normalize(value: Any) -> Any:
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    return value


def _normalize_score(score: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalize(value) for key, value in score.items()}


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, wrapper = _function_segment(inputs_source, "_one_click_domain_score")
    cases = [
        ("bending_in_band_pass", _candidate(mu=90.0, phi=100.0, shear=0.7, statuses={"bending": "PASS"}), "bending", {}),
        ("bending_fail_in_band", _candidate(mu=90.0, phi=100.0, shear=0.7, statuses={"bending": "FAIL"}), "bending", {}),
        ("bending_under", _candidate(mu=60.0, phi=100.0, shear=0.7, statuses={"bending": "PASS"}), "bending", {}),
        ("bending_over", _candidate(mu=120.0, phi=100.0, shear=0.7, statuses={"bending": "PASS"}), "bending", {}),
        ("shear_in_band", _candidate(bending=0.7, shear=0.9, statuses={"shear": "PASS"}), "shear", {}),
        ("shear_fail_lowercase_status", _candidate(bending=0.7, shear=0.9, statuses={"shear": "fail"}), "shear", {}),
        ("invalid_util", _candidate(bending="bad", shear=float("nan"), statuses={}), "shear", {}),
        ("custom_band", _candidate(bending=0.7, shear=0.74, statuses={"shear": "PASS"}), "shear", {"target_util_min": 0.7, "target_util_max": 0.8}),
        ("bad_mode_config_defaults", _candidate(bending=0.7, shear=0.9, statuses={"shear": "PASS"}), "shear", {"target_util_min": "bad", "target_util_max": None}),
        ("unknown_domain", _candidate(bending=0.7, shear=0.9, statuses={}), "crack", {}),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, candidate, domain, mode_config in cases:
        old = _old_score(candidate, domain, mode_config)
        new = resolve_candidate_domain_score(
            candidate,
            domain,
            mode_config,
            default_target_min=DEFAULT_MIN,
            default_target_max=DEFAULT_MAX,
            fail_status=FAIL,
        )
        row = {
            "case": name,
            "old": _normalize_score(old),
            "new": _normalize_score(new),
            "matches": _normalize_score(old) == _normalize_score(new),
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_thin = (
        "_resolve_candidate_domain_score(" in wrapper
        and "_candidate_domain_util(" not in wrapper
        and "statuses.get" not in wrapper
        and "_distance_to_target_band(" not in wrapper
    )
    service_present = "def resolve_candidate_domain_score(" in candidate_source
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
        "next_safe_slice": "one-click eval domain scores / required-domain progress service extraction",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_one_click_domain_score_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_one_click_domain_score_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# One-Click Domain Score Service Extraction",
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
