"""Verify required-domain progress service extraction."""

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

from design_brain.candidate_evaluation import resolve_candidate_required_domain_progress  # noqa: E402


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


def _goal_from_state(state: dict[str, Any]) -> str:
    return str((state or {}).get("design_optimisation_goal") or "balanced")


def _old_target_domains(candidate: dict[str, Any] | None) -> list[str]:
    if not isinstance(candidate, dict):
        return []
    raw = candidate.get("target_domains_for_band")
    if not isinstance(raw, (list, tuple, set)):
        return []
    normalized: list[str] = []
    for value in raw:
        domain = str(value or "").strip().lower()
        if domain in ("bending", "flexure", "bottom", "bottom_reo"):
            domain = "bending"
        elif domain in ("shear", "links", "ligatures"):
            domain = "shear"
        else:
            continue
        if domain not in normalized:
            normalized.append(domain)
    return normalized


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


def _old_objective_util(candidate: dict[str, Any] | None) -> float:
    candidate_d = candidate if isinstance(candidate, dict) else {}
    state = candidate_d.get("state") if isinstance(candidate_d.get("state"), dict) else {}
    goal = _goal_from_state(dict(state or {}))
    overview = candidate_d.get("overview") if isinstance(candidate_d.get("overview"), dict) else {}
    utils = overview.get("utils") if isinstance(overview.get("utils"), dict) else {}
    target_domain = str(candidate_d.get("target_domain_for_band") or "").strip().lower()
    bending_demand_util = _old_bending_demand_util(candidate_d)

    if target_domain == "shear" or goal == "less_shear_reinforcement":
        objective_values = [utils.get("shear")]
    else:
        objective_values = [bending_demand_util, utils.get("shear")]

    resolved_values: list[float] = []
    for value in objective_values:
        if value is None:
            continue
        try:
            resolved = float(value)
        except Exception:
            continue
        if not math.isnan(resolved):
            resolved_values.append(resolved)
    if resolved_values:
        return max(resolved_values)
    return float(candidate_d.get("worst_util", 0.0) or 0.0)


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


def _old_scores(eval_obj: dict[str, Any] | None, mode_config: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        domain: _old_score(eval_obj, domain, mode_config)
        for domain in _old_target_domains(eval_obj or {})
    }


def _old_progress(eval_obj: dict[str, Any] | None, mode_config: dict[str, Any] | None) -> dict[str, Any]:
    scores = _old_scores(eval_obj, mode_config)
    try:
        target_min = float((mode_config or {}).get("target_util_min", DEFAULT_MIN) or DEFAULT_MIN)
        target_max = float((mode_config or {}).get("target_util_max", DEFAULT_MAX) or DEFAULT_MAX)
    except (TypeError, ValueError, KeyError):
        target_min = float(DEFAULT_MIN)
        target_max = float(DEFAULT_MAX)

    if not scores:
        util = _old_objective_util(eval_obj or {})
        try:
            util = float(util)
        except (TypeError, ValueError):
            util = None
        overview = dict((eval_obj or {}).get("overview") or {})
        statuses = dict(overview.get("statuses") or {})
        all_key_pass = bool(overview.get("all_key_pass"))
        any_fail = any(
            status == FAIL or str(status or "").strip().upper() == "FAIL"
            for status in statuses.values()
        )
        ok_status = bool(all_key_pass and not any_fail)
        in_band = bool(util is not None and math.isfinite(float(util)) and target_min <= float(util) <= target_max and ok_status)
        distance = (
            float("inf")
            if util is None or not math.isfinite(float(util))
            else _old_distance(float(util), target_min, target_max)
        )
        return {
            "scores": {},
            "required_domain_count": 0,
            "required_fail_count": 0 if ok_status else 1,
            "required_unsatisfied_count": 0 if in_band else 1,
            "required_satisfied_count": 1 if in_band else 0,
            "required_fail_domains": [] if ok_status else ["objective"],
            "required_unsatisfied_domains": [] if in_band else ["objective"],
            "required_satisfied_domains": ["objective"] if in_band else [],
            "domain_total_distance": float(distance),
            "domain_max_distance": float(distance),
        }

    fail_domains: list[str] = []
    unsatisfied_domains: list[str] = []
    satisfied_domains: list[str] = []
    total = 0.0
    max_distance = float("-inf")
    for domain, score in scores.items():
        if not bool(score.get("pass")):
            fail_domains.append(domain)
        if bool(score.get("pass")) and bool(score.get("in_band")):
            satisfied_domains.append(domain)
        else:
            unsatisfied_domains.append(domain)
        dist = score.get("distance")
        if dist is None or not math.isfinite(float(dist)):
            total = float("inf")
            max_distance = float("inf")
            continue
        fd = float(dist)
        if not math.isfinite(total):
            continue
        total += fd
        max_distance = max(max_distance, fd)
    if max_distance == float("-inf"):
        max_distance = float("inf")
    return {
        "scores": scores,
        "required_domain_count": len(scores),
        "required_fail_count": len(fail_domains),
        "required_unsatisfied_count": len(unsatisfied_domains),
        "required_satisfied_count": len(satisfied_domains),
        "required_fail_domains": fail_domains,
        "required_unsatisfied_domains": unsatisfied_domains,
        "required_satisfied_domains": satisfied_domains,
        "domain_total_distance": float(total),
        "domain_max_distance": float(max_distance),
    }


def _candidate(
    *,
    target_domains: Any = None,
    target_domain: Any = None,
    bending: Any = None,
    shear: Any = None,
    mu: Any = None,
    phi: Any = None,
    statuses: dict[str, Any] | None = None,
    all_key_pass: bool | None = None,
    goal: str | None = None,
    worst_util: Any = None,
) -> dict[str, Any]:
    bending_pack: dict[str, Any] = {}
    if mu is not None:
        bending_pack["summary_Mu_star_kNm"] = mu
    if phi is not None:
        bending_pack["summary_phiMu_kNm"] = phi
    overview: dict[str, Any] = {
        "statuses": dict(statuses or {}),
        "utils": {"bending": bending, "shear": shear},
        "packs": {"bending": bending_pack},
    }
    if all_key_pass is not None:
        overview["all_key_pass"] = bool(all_key_pass)
    candidate: dict[str, Any] = {"overview": overview}
    if target_domains is not None:
        candidate["target_domains_for_band"] = target_domains
    if target_domain is not None:
        candidate["target_domain_for_band"] = target_domain
    if goal is not None:
        candidate["state"] = {"design_optimisation_goal": goal}
    if worst_util is not None:
        candidate["worst_util"] = worst_util
    return candidate


def _normalize(value: Any) -> Any:
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    if isinstance(value, dict):
        return {key: _normalize(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_normalize(inner) for inner in value]
    return value


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, wrapper = _function_segment(inputs_source, "_one_click_required_domain_progress")
    cases = [
        (
            "explicit_domains_all_satisfied",
            _candidate(
                target_domains=["bending", "shear"],
                mu=90.0,
                phi=100.0,
                shear=0.9,
                statuses={"bending": "PASS", "shear": "PASS"},
            ),
            {},
        ),
        (
            "explicit_domain_fail_inside_band",
            _candidate(
                target_domains=["shear"],
                shear=0.9,
                statuses={"shear": "FAIL"},
            ),
            {},
        ),
        (
            "explicit_domains_unsatisfied_distance",
            _candidate(
                target_domains=["bending", "shear"],
                mu=60.0,
                phi=100.0,
                shear=1.2,
                statuses={"bending": "PASS", "shear": "PASS"},
            ),
            {},
        ),
        (
            "objective_fallback_satisfied",
            _candidate(
                bending=0.9,
                shear=0.9,
                statuses={"bending": "PASS", "shear": "PASS"},
                all_key_pass=True,
            ),
            {},
        ),
        (
            "objective_fallback_failed_status",
            _candidate(
                bending=0.9,
                shear=0.9,
                statuses={"bending": "FAIL", "shear": "PASS"},
                all_key_pass=False,
            ),
            {},
        ),
        (
            "objective_fallback_less_shear_goal",
            _candidate(
                bending=0.6,
                shear=0.9,
                statuses={"bending": "PASS", "shear": "PASS"},
                all_key_pass=True,
                goal="less_shear_reinforcement",
            ),
            {},
        ),
        (
            "objective_fallback_bad_band",
            _candidate(
                bending="bad",
                shear=float("nan"),
                statuses={},
                all_key_pass=False,
                worst_util=0.0,
            ),
            {"target_util_min": "bad", "target_util_max": None},
        ),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, candidate, mode_config in cases:
        old = _old_progress(candidate, mode_config)
        new = resolve_candidate_required_domain_progress(
            candidate,
            mode_config,
            default_target_min=DEFAULT_MIN,
            default_target_max=DEFAULT_MAX,
            fail_status=FAIL,
            optimisation_goal_resolver=_goal_from_state,
        )
        row = {
            "case": name,
            "old": _normalize(old),
            "new": _normalize(new),
            "matches": _normalize(old) == _normalize(new),
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_thin = (
        "_resolve_candidate_required_domain_progress(" in wrapper
        and "_one_click_eval_domain_scores(" not in wrapper
        and "_candidate_objective_util(" not in wrapper
        and "required_fail_domains" not in wrapper
    )
    service_present = "def resolve_candidate_required_domain_progress(" in candidate_source
    forbidden_service_import_hits = [
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
    if mismatches or not wrapper_thin or not service_present or forbidden_service_import_hits:
        status = "FAIL"
    return {
        "status": status,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "wrapper_thin": wrapper_thin,
        "service_present": service_present,
        "forbidden_service_import_hits": forbidden_service_import_hits,
        "case_count": len(rows),
        "mismatch_count": len(mismatches),
        "rows": rows,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "next_safe_slice": "domain-distance and required-domain satisfied wrappers shell/deadness check",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_required_domain_progress_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_required_domain_progress_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Required-Domain Progress Service Extraction",
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
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
