"""Verify candidate step-improvement service extraction."""

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
    resolve_auto_design_candidate_objective_util,
    resolve_candidate_in_target_band,
    resolve_candidate_required_domain_progress,
    resolve_candidate_step_improves,
    resolve_candidate_target_band_distance,
    resolve_candidate_target_band_total_distance,
    resolve_candidate_target_domains_for_band,
)


INPUTS = ROOT / "inputs_page_app_contract_bridge.py"
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
    target_domains: Any = None,
    bending: Any = None,
    shear: Any = None,
    mu: Any = None,
    phi: Any = None,
    statuses: dict[str, Any] | None = None,
    all_key_pass: bool | None = None,
    worst_util: Any = None,
    goal: str | None = None,
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
    if worst_util is not None:
        candidate["worst_util"] = worst_util
    if goal is not None:
        candidate["state"] = {"design_optimisation_goal": goal}
    return candidate


def _progress(candidate: dict[str, Any], mode_config: dict[str, Any]) -> dict[str, Any]:
    return resolve_candidate_required_domain_progress(
        candidate,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        optimisation_goal_resolver=_goal_from_state,
    )


def _in_band(candidate: dict[str, Any], mode_config: dict[str, Any]) -> bool:
    return resolve_candidate_in_target_band(
        candidate,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        optimisation_goal_resolver=_goal_from_state,
    )


def _objective_util(candidate: dict[str, Any]) -> float:
    return resolve_auto_design_candidate_objective_util(
        candidate,
        optimisation_goal_resolver=_goal_from_state,
    )


def _distance(candidate: dict[str, Any], mode_config: dict[str, Any]) -> float:
    return resolve_candidate_target_band_distance(
        candidate,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        optimisation_goal_resolver=_goal_from_state,
    )


def _total_distance(candidate: dict[str, Any], mode_config: dict[str, Any]) -> float:
    return resolve_candidate_target_band_total_distance(
        candidate,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        optimisation_goal_resolver=_goal_from_state,
    )


def _old_step_improves(new_eval: dict[str, Any], old_eval: dict[str, Any], mode_config: dict[str, Any]) -> bool:
    old_pass = bool((old_eval.get("overview") or {}).get("all_key_pass"))
    new_pass = bool((new_eval.get("overview") or {}).get("all_key_pass"))
    old_ib = _in_band(old_eval, mode_config)
    new_ib = _in_band(new_eval, mode_config)
    old_u = _objective_util(old_eval)
    new_u = _objective_util(new_eval)
    old_d = _distance(old_eval, mode_config)
    new_d = _distance(new_eval, mode_config)
    if resolve_candidate_target_domains_for_band(old_eval) or resolve_candidate_target_domains_for_band(new_eval):
        old_progress = _progress(old_eval, mode_config)
        new_progress = _progress(new_eval, mode_config)
        old_fail = int(old_progress.get("required_fail_count", 0) or 0)
        new_fail = int(new_progress.get("required_fail_count", 0) or 0)
        old_unsatisfied = int(old_progress.get("required_unsatisfied_count", 0) or 0)
        new_unsatisfied = int(new_progress.get("required_unsatisfied_count", 0) or 0)
        old_max = float(old_progress.get("domain_max_distance", float("inf")))
        new_max = float(new_progress.get("domain_max_distance", float("inf")))
        old_total = float(old_progress.get("domain_total_distance", float("inf")))
        new_total = float(new_progress.get("domain_total_distance", float("inf")))
        if new_ib and not old_ib and new_pass:
            return True
        if new_fail < old_fail:
            return True
        if new_unsatisfied < old_unsatisfied:
            return True
        if new_pass and not old_pass:
            max_not_worse = math.isfinite(old_max) and math.isfinite(new_max) and new_max <= old_max + 1e-6
            total_improved = math.isfinite(old_total) and math.isfinite(new_total) and new_total < old_total - 1e-6
            return bool(max_not_worse or total_improved)
        if new_max < old_max - 1e-6:
            return True
        if new_max <= old_max + 1e-6 and new_total < old_total - 1e-6:
            return True
        return False
    old_total = _total_distance(old_eval, mode_config)
    new_total = _total_distance(new_eval, mode_config)
    if new_pass and not old_pass:
        return True
    if new_ib and not old_ib and new_pass:
        return True
    if new_d < old_d - 1e-6:
        return True
    if new_d <= old_d + 1e-6 and new_total < old_total - 1e-6:
        return True
    lo = float(mode_config.get("target_util_min", DEFAULT_MIN) or DEFAULT_MIN)
    hi = float(mode_config.get("target_util_max", DEFAULT_MAX) or DEFAULT_MAX)
    if old_u < lo and new_u > old_u + 1e-9 and new_pass == old_pass:
        return True
    if old_u > hi and new_u < old_u - 1e-9 and new_pass == old_pass:
        return True
    return False


def _new_step_improves(new_eval: dict[str, Any], old_eval: dict[str, Any], mode_config: dict[str, Any]) -> bool:
    return resolve_candidate_step_improves(
        new_eval,
        old_eval,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        optimisation_goal_resolver=_goal_from_state,
    )


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, wrapper = _function_segment(inputs_source, "_one_click_step_improves")
    cases = [
        (
            "target_domain_new_in_band",
            _candidate(target_domains=["bending"], mu=60.0, phi=100.0, statuses={"bending": "PASS"}, all_key_pass=True),
            _candidate(target_domains=["bending"], mu=90.0, phi=100.0, statuses={"bending": "PASS"}, all_key_pass=True),
            {},
        ),
        (
            "target_domain_fail_count_improves",
            _candidate(target_domains=["shear"], shear=0.9, statuses={"shear": "FAIL"}, all_key_pass=False),
            _candidate(target_domains=["shear"], shear=0.9, statuses={"shear": "PASS"}, all_key_pass=True),
            {},
        ),
        (
            "target_domain_distance_improves",
            _candidate(target_domains=["bending", "shear"], mu=60.0, phi=100.0, shear=1.2, statuses={"bending": "PASS", "shear": "PASS"}, all_key_pass=True),
            _candidate(target_domains=["bending", "shear"], mu=80.0, phi=100.0, shear=1.05, statuses={"bending": "PASS", "shear": "PASS"}, all_key_pass=True),
            {},
        ),
        (
            "target_domain_no_improvement",
            _candidate(target_domains=["bending"], mu=90.0, phi=100.0, statuses={"bending": "PASS"}, all_key_pass=True),
            _candidate(target_domains=["bending"], mu=70.0, phi=100.0, statuses={"bending": "PASS"}, all_key_pass=True),
            {},
        ),
        (
            "objective_pass_improves",
            _candidate(bending=1.1, shear=1.1, statuses={"bending": "FAIL"}, all_key_pass=False, worst_util=1.1),
            _candidate(bending=0.95, shear=0.95, statuses={"bending": "PASS"}, all_key_pass=True, worst_util=0.95),
            {},
        ),
        (
            "objective_under_moves_up",
            _candidate(bending=0.6, shear=0.6, statuses={"bending": "PASS"}, all_key_pass=True, worst_util=0.6),
            _candidate(bending=0.7, shear=0.7, statuses={"bending": "PASS"}, all_key_pass=True, worst_util=0.7),
            {},
        ),
        (
            "objective_over_moves_down",
            _candidate(bending=1.2, shear=1.2, statuses={"bending": "PASS"}, all_key_pass=True, worst_util=1.2),
            _candidate(bending=1.1, shear=1.1, statuses={"bending": "PASS"}, all_key_pass=True, worst_util=1.1),
            {},
        ),
        (
            "objective_no_improvement",
            _candidate(bending=0.9, shear=0.9, statuses={"bending": "PASS"}, all_key_pass=True, worst_util=0.9),
            _candidate(bending=1.1, shear=1.1, statuses={"bending": "PASS"}, all_key_pass=True, worst_util=1.1),
            {},
        ),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, old_eval, new_eval, mode_config in cases:
        old = _old_step_improves(new_eval, old_eval, mode_config)
        new = _new_step_improves(new_eval, old_eval, mode_config)
        row = {"case": name, "old": old, "new": new, "matches": old == new}
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_thin = (
        "_resolve_candidate_step_improves(" in wrapper
        and "required_fail_count" not in wrapper
        and "_candidate_target_band_distance(" not in wrapper
        and "_candidate_objective_util(" not in wrapper
    )
    service_present = "def resolve_candidate_step_improves(" in candidate_source
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
        "next_safe_slice": "mixed-direction ranking overlay boundary audit",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_candidate_step_improves_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_candidate_step_improves_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Step Improves Service Extraction",
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
