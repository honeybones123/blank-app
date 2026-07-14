"""Verify candidate objective-util projection extraction.

This proves the objective utilisation and bending demand utilisation projection
now live behind design_brain.candidate_evaluation while preserving the old
plain-data behaviour.
"""

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
    resolve_candidate_bending_demand_util,
)
from design_brain.config import resolve_design_optimisation_goal  # noqa: E402


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
GOAL_LABELS = {
    "balanced": "Balanced",
    "less_reinforcement": "Less reinforcement",
    "less_shear_reinforcement": "Less shear reinforcement",
    "shallower_beam": "Shallower beam",
}


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


def _old_objective_util(candidate: dict[str, Any] | None) -> float:
    candidate_d = candidate if isinstance(candidate, dict) else {}
    state = candidate_d.get("state") if isinstance(candidate_d.get("state"), dict) else {}
    goal = resolve_design_optimisation_goal(dict(state or {}), goal_labels=GOAL_LABELS)
    overview = candidate_d.get("overview") if isinstance(candidate_d.get("overview"), dict) else {}
    utils = overview.get("utils") if isinstance(overview.get("utils"), dict) else {}
    target_domain = str(candidate_d.get("target_domain_for_band") or "").strip().lower()
    bend_du = _old_bending_demand_util(candidate_d)
    if target_domain == "shear" or goal == "less_shear_reinforcement":
        objective_values = [utils.get("shear")]
    else:
        objective_values = [bend_du, utils.get("shear")]
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


def _candidate(*, mu: Any = None, phi: Any = None, shear: Any = None, target_domain: str = "", goal: str = "", worst: Any = 0.0) -> dict[str, Any]:
    state = {"design_optimisation_goal": goal} if goal else {}
    bending_pack: dict[str, Any] = {}
    if mu is not None:
        bending_pack["summary_Mu_star_kNm"] = mu
    if phi is not None:
        bending_pack["summary_phiMu_kNm"] = phi
    return {
        "state": state,
        "overview": {
            "utils": {"shear": shear},
            "packs": {"bending": bending_pack},
        },
        "target_domain_for_band": target_domain,
        "worst_util": worst,
    }


def _cases() -> list[dict[str, Any]]:
    return [
        {"name": "bending_demand_wins", "candidate": _candidate(mu=90.0, phi=100.0, shear=0.6, worst=0.2)},
        {"name": "shear_wins_balanced", "candidate": _candidate(mu=60.0, phi=100.0, shear=0.82, worst=0.2)},
        {"name": "target_domain_shear_uses_shear", "candidate": _candidate(mu=120.0, phi=100.0, shear=0.72, target_domain="shear", worst=0.2)},
        {"name": "less_shear_goal_uses_shear", "candidate": _candidate(mu=120.0, phi=100.0, shear=0.69, goal="less_shear_reinforcement", worst=0.2)},
        {"name": "zero_phi_falls_back_to_shear", "candidate": _candidate(mu=120.0, phi=0.0, shear=0.64, worst=0.2)},
        {"name": "non_numeric_shear_ignored", "candidate": _candidate(mu=80.0, phi=100.0, shear="bad", worst=0.2)},
        {"name": "nan_shear_ignored", "candidate": _candidate(mu=None, phi=None, shear=float("nan"), worst=0.31)},
        {"name": "empty_candidate_falls_back", "candidate": {"worst_util": 0.44}},
        {"name": "non_dict_candidate", "candidate": None},
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, bending_wrapper = _function_segment(inputs_source, "_candidate_bending_demand_util")
    _, _, objective_wrapper = _function_segment(inputs_source, "_candidate_objective_util")

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in _cases():
        cand = case["candidate"]
        old_bend = _old_bending_demand_util(cand)
        new_bend = resolve_candidate_bending_demand_util(cand)
        old_obj = _old_objective_util(cand)
        new_obj = resolve_auto_design_candidate_objective_util(
            cand,
            optimisation_goal_resolver=lambda state: resolve_design_optimisation_goal(
                state,
                goal_labels=GOAL_LABELS,
            ),
        )
        row = {
            "case": case["name"],
            "old_bending_demand_util": old_bend,
            "new_bending_demand_util": new_bend,
            "old_objective_util": old_obj,
            "new_objective_util": new_obj,
            "bending_matches": old_bend == new_bend,
            "objective_matches": old_obj == new_obj,
        }
        rows.append(row)
        if not (row["bending_matches"] and row["objective_matches"]):
            mismatches.append(row)

    wrapper_thin = (
        "_resolve_candidate_bending_demand_util(candidate)" in bending_wrapper
        and "_resolve_auto_design_candidate_objective_util(" in objective_wrapper
        and "optimisation_goal_resolver=_design_optimisation_goal" in objective_wrapper
        and "candidate.get(\"overview\")" not in objective_wrapper
        and "summary_phiMu_kNm" not in bending_wrapper
    )
    service_present = (
        "def resolve_candidate_bending_demand_util(" in candidate_source
        and "def resolve_auto_design_candidate_objective_util(" in candidate_source
    )
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
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_candidate_objective_util_projection_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_auto_design_candidate_objective_util_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto-Design Candidate Objective-Util Projection Extraction",
        "",
        "## Executive Summary",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Proof",
        f"- Thin page wrappers: `{payload['wrapper_thin']}`",
        f"- Service helpers present: `{payload['service_present']}`",
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
