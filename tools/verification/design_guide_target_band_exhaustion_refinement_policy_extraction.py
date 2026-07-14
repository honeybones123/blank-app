"""Verify target-band exhaustion refinement policy extraction."""

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

from design_brain.candidate_evaluation import (  # noqa: E402
    resolve_candidate_required_domain_progress,
    resolve_candidate_step_improves,
    resolve_candidate_target_domains_for_band,
    resolve_target_band_exhaustion_refinement_allowed,
)


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


def _candidate(
    *,
    target_domains: list[str] | None,
    bending: float,
    shear: float,
    all_key_pass: bool = True,
    statuses: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "target_domains_for_band": list(target_domains or []),
        "overview": {
            "all_key_pass": bool(all_key_pass),
            "statuses": dict(statuses or {"bending": "PASS", "shear": "PASS"}),
            "utils": {"bending": bending, "shear": shear},
            "packs": {"bending": {"summary_Mu_star_kNm": bending * 100.0, "summary_phiMu_kNm": 100.0}},
        },
        "state": {"design_optimisation_goal": "balanced"},
    }


def _progress(eval_obj: dict[str, Any], mode_config: dict[str, Any]) -> dict[str, Any]:
    return resolve_candidate_required_domain_progress(
        eval_obj,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        optimisation_goal_resolver=_goal_from_state,
    )


def _old_allowed(current_eval: dict[str, Any] | None, next_hop_payload: dict[str, Any] | None, mode_config: dict[str, Any]) -> bool:
    if not isinstance(current_eval, dict) or not isinstance(next_hop_payload, dict):
        return False
    if not bool((current_eval.get("overview") or {}).get("all_key_pass")):
        return False
    current_domains = list(resolve_candidate_target_domains_for_band(current_eval) or [])
    if len(current_domains) < 2:
        return False
    current_progress = _progress(current_eval, mode_config)
    if int(current_progress.get("required_fail_count", 0) or 0) != 0:
        return False
    if int(current_progress.get("required_unsatisfied_count", 0) or 0) <= 1:
        return False
    candidate_eval = next_hop_payload.get("eval")
    if not isinstance(candidate_eval, dict):
        return False
    if not bool((candidate_eval.get("overview") or {}).get("all_key_pass")):
        return False
    candidate_progress = _progress(candidate_eval, mode_config)
    if int(candidate_progress.get("required_fail_count", 0) or 0) != 0:
        return False
    if int(candidate_progress.get("required_unsatisfied_count", 0) or 0) > int(
        current_progress.get("required_unsatisfied_count", 0) or 0
    ):
        return False
    current_max = float(current_progress.get("domain_max_distance", float("inf")))
    candidate_max = float(candidate_progress.get("domain_max_distance", float("inf")))
    current_total = float(current_progress.get("domain_total_distance", float("inf")))
    candidate_total = float(candidate_progress.get("domain_total_distance", float("inf")))
    if not (
        math.isfinite(current_max)
        and math.isfinite(candidate_max)
        and math.isfinite(current_total)
        and math.isfinite(candidate_total)
    ):
        return False
    if candidate_max > current_max + 1e-6:
        return False
    if candidate_total >= current_total - 1e-6:
        return False
    return resolve_candidate_step_improves(
        candidate_eval,
        current_eval,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        optimisation_goal_resolver=_goal_from_state,
    )


def _new_allowed(current_eval: dict[str, Any] | None, next_hop_payload: dict[str, Any] | None, mode_config: dict[str, Any]) -> bool:
    return resolve_target_band_exhaustion_refinement_allowed(
        current_eval,
        next_hop_payload,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        optimisation_goal_resolver=_goal_from_state,
    )


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    wrapper_start, wrapper_end, wrapper = _function_segment(inputs_source, "_one_click_exhaustion_next_hop_allowed")
    solve_start, solve_end, solve = _function_segment(inputs_source, "_solve_one_click_to_target")
    mode_config = {"target_util_min": DEFAULT_MIN, "target_util_max": DEFAULT_MAX}
    current = _candidate(target_domains=["bending", "shear"], bending=0.7, shear=0.75)
    better = _candidate(target_domains=["bending", "shear"], bending=0.8, shear=0.82)
    worse_total = _candidate(target_domains=["bending", "shear"], bending=0.7, shear=0.74)
    cases = [
        ("allowed_refinement", current, {"eval": better}, mode_config),
        ("missing_payload", current, None, mode_config),
        ("current_not_pass", _candidate(target_domains=["bending", "shear"], bending=0.7, shear=0.75, all_key_pass=False), {"eval": better}, mode_config),
        ("single_domain_current", _candidate(target_domains=["bending"], bending=0.7, shear=0.75), {"eval": better}, mode_config),
        ("candidate_not_pass", current, {"eval": _candidate(target_domains=["bending", "shear"], bending=0.8, shear=0.82, all_key_pass=False)}, mode_config),
        ("candidate_not_better_total", current, {"eval": worse_total}, mode_config),
        ("missing_candidate_eval", current, {"updates": {"D": 700}}, mode_config),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, cur, payload, cfg in cases:
        old = _old_allowed(cur, payload, cfg)
        new = _new_allowed(cur, payload, cfg)
        row = {"case": name, "old": old, "new": new, "matches": old == new}
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_delegates = "_resolve_target_band_exhaustion_refinement_allowed(" in wrapper
    wrapper_old_policy_removed = all(
        token not in wrapper
        for token in (
            "current_progress =",
            "candidate_progress =",
            "candidate_total >=",
            "required_unsatisfied_count",
            "_one_click_step_improves(",
        )
    )
    fallback_search_remains_page_owned = "_one_click_best_next_hop_improving_candidate(cur_eval, mode_config)" in solve
    fallback_injection_remains_page_owned = '"Fallback multi-domain cleanup"' in solve and '"fallback_next_hop_cleanup"' in solve
    service_present = "def resolve_target_band_exhaustion_refinement_allowed(" in candidate_source
    forbidden_service_hits = [
        token
        for token in (
            "one_click",
            "import inputs_page",
            "from inputs_page",
            "import streamlit",
            "from streamlit",
            "st.session_state",
        )
        if token in candidate_source
    ]
    status = "PASS"
    if (
        mismatches
        or not wrapper_delegates
        or not wrapper_old_policy_removed
        or not fallback_search_remains_page_owned
        or not fallback_injection_remains_page_owned
        or not service_present
        or forbidden_service_hits
    ):
        status = "FAIL"
    return {
        "status": status,
        "surface": "target_band_exhaustion_refinement_policy",
        "wrapper_segment": {"function": "_one_click_exhaustion_next_hop_allowed", "start_line": wrapper_start, "end_line": wrapper_end},
        "solve_segment": {"function": "_solve_one_click_to_target", "start_line": solve_start, "end_line": solve_end},
        "case_count": len(cases),
        "mismatches": mismatches,
        "parity_rows": rows,
        "static_checks": {
            "service_present": service_present,
            "wrapper_delegates": wrapper_delegates,
            "wrapper_old_policy_removed": wrapper_old_policy_removed,
            "fallback_search_remains_page_owned": fallback_search_remains_page_owned,
            "fallback_injection_remains_page_owned": fallback_injection_remains_page_owned,
            "forbidden_service_hits": forbidden_service_hits,
        },
        "ownership": {
            "moved_to_candidate_evaluation": ["exhaustion fallback refinement allow/deny policy"],
            "remains_page_owned": [
                "next-hop candidate generation and evaluation",
                "fallback scored-row materialisation",
                "fallback label/action_type/trace fields",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "audit fallback scored-row materialisation or next-hop candidate generation boundary separately",
    }


def write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_exhaustion_refinement_policy_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_exhaustion_refinement_policy_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Exhaustion Refinement Policy Extraction",
        "",
        f"## Summary: {payload['status']}",
        "",
        "Moved only the pure allow/deny policy for exhaustion refinement fallback into `design_brain.candidate_evaluation`.",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Parity", f"- Cases checked: `{payload['case_count']}`", f"- Mismatches: `{len(payload['mismatches'])}`", ""])
    lines.extend(["## Remaining Page-Owned Logic"])
    for item in payload["ownership"]["remains_page_owned"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"]), "", f"JSON artifact: `{json_path}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
