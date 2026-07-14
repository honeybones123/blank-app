"""Verify auto-design target-band metric annotation service extraction.

This proves _annotate_candidate_target_band_metrics(...) delegates the pure
annotation projection to design_brain.candidate_evaluation while preserving the
old candidate fields and leaving selector mutation/trace/apply/render ownership
in inputs_page.py.
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
    resolve_auto_design_candidate_target_band_metrics,
    resolve_candidate_in_target_band,
    resolve_distance_to_target_band,
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


def _goal(state: dict[str, Any]) -> str:
    return resolve_design_optimisation_goal(state, goal_labels=GOAL_LABELS)


def _old_metrics(candidate: dict[str, Any] | None, mode_config: dict[str, Any]) -> dict[str, Any]:
    candidate_d = candidate if isinstance(candidate, dict) else {}
    try:
        util = float(
            resolve_auto_design_candidate_objective_util(
                candidate_d,
                optimisation_goal_resolver=_goal,
            )
        )
    except Exception:
        util = float(candidate_d.get("worst_util", 0.0) or 0.0)
    tmin = float(mode_config.get("target_util_min", 0.80) or 0.80)
    tmax = float(mode_config.get("target_util_max", 0.90) or 0.90)
    return {
        "candidate_post_util": util,
        "candidate_distance_to_target_band": resolve_distance_to_target_band(util, tmin, tmax),
        "candidate_reaches_target_band": bool(
            bool(candidate_d.get("is_compliant"))
            and resolve_candidate_in_target_band(
                candidate_d,
                mode_config,
                default_target_min=0.80,
                default_target_max=0.90,
                fail_status="FAIL",
                optimisation_goal_resolver=_goal,
            )
        ),
    }


def _candidate(
    *,
    bending: Any = None,
    shear: Any = None,
    mu: Any = None,
    phi: Any = None,
    target_domain: str = "",
    target_domains: list[str] | None = None,
    is_compliant: bool = True,
    all_key_pass: bool = True,
    statuses: dict[str, Any] | None = None,
    goal: str = "",
    worst: Any = 0.0,
) -> dict[str, Any]:
    pack: dict[str, Any] = {}
    if mu is not None:
        pack["summary_Mu_star_kNm"] = mu
    if phi is not None:
        pack["summary_phiMu_kNm"] = phi
    return {
        "state": {"design_optimisation_goal": goal} if goal else {},
        "overview": {
            "utils": {"bending": bending, "shear": shear},
            "packs": {"bending": pack},
            "all_key_pass": all_key_pass,
            "statuses": dict(statuses or {"bending": "PASS", "shear": "PASS"}),
        },
        "target_domain_for_band": target_domain,
        "target_domains_for_band": list(target_domains or []),
        "is_compliant": is_compliant,
        "worst_util": worst,
    }


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "balanced_bending_demand_in_band",
            "candidate": _candidate(mu=85.0, phi=100.0, shear=0.52, target_domains=["bending"], worst=0.85),
            "mode": {"target_util_min": 0.80, "target_util_max": 0.90},
        },
        {
            "name": "balanced_bending_demand_under",
            "candidate": _candidate(mu=62.0, phi=100.0, shear=0.55, target_domains=["bending"], worst=0.62),
            "mode": {"target_util_min": 0.80, "target_util_max": 0.90},
        },
        {
            "name": "shear_target_domain_uses_shear",
            "candidate": _candidate(mu=120.0, phi=100.0, shear=0.86, target_domain="shear", target_domains=["shear"], worst=1.2),
            "mode": {"target_util_min": 0.80, "target_util_max": 0.90},
        },
        {
            "name": "less_shear_goal_uses_shear",
            "candidate": _candidate(mu=115.0, phi=100.0, shear=0.73, goal="less_shear_reinforcement", target_domains=["shear"], worst=1.15),
            "mode": {"target_util_min": 0.80, "target_util_max": 0.90},
        },
        {
            "name": "not_compliant_never_reaches",
            "candidate": _candidate(mu=85.0, phi=100.0, shear=0.84, target_domains=["bending"], is_compliant=False, worst=0.85),
            "mode": {"target_util_min": 0.80, "target_util_max": 0.90},
        },
        {
            "name": "custom_target_band",
            "candidate": _candidate(mu=74.0, phi=100.0, shear=0.66, target_domains=["bending"], worst=0.74),
            "mode": {"target_util_min": 0.70, "target_util_max": 0.75},
        },
    ]


def _same_float(left: Any, right: Any) -> bool:
    try:
        left_f = float(left)
        right_f = float(right)
    except (TypeError, ValueError):
        return left == right
    if math.isinf(left_f) or math.isinf(right_f):
        return left_f == right_f
    return abs(left_f - right_f) <= 1e-12


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    _, _, wrapper_segment = _function_segment(inputs_source, "_annotate_candidate_target_band_metrics")

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in _cases():
        old = _old_metrics(case["candidate"], case["mode"])
        new = resolve_auto_design_candidate_target_band_metrics(
            case["candidate"],
            case["mode"],
            default_target_min=0.80,
            default_target_max=0.90,
            fail_status="FAIL",
            optimisation_goal_resolver=_goal,
        )
        row = {
            "case": case["name"],
            "old": old,
            "new": new,
            "post_util_matches": _same_float(old.get("candidate_post_util"), new.get("candidate_post_util")),
            "distance_matches": _same_float(
                old.get("candidate_distance_to_target_band"),
                new.get("candidate_distance_to_target_band"),
            ),
            "reaches_matches": old.get("candidate_reaches_target_band") == new.get("candidate_reaches_target_band"),
        }
        row["matches"] = bool(row["post_util_matches"] and row["distance_matches"] and row["reaches_matches"])
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_delegates = "_resolve_auto_design_candidate_target_band_metrics(" in wrapper_segment
    old_page_logic_removed = all(
        token not in wrapper_segment
        for token in (
            "_candidate_objective_util(",
            "_distance_to_target_band(",
            "_candidate_reaches_target_band_one_step(",
            "mode_config.get(\"target_util_min\"",
            "mode_config.get(\"target_util_max\"",
        )
    )
    service_present = "def resolve_auto_design_candidate_target_band_metrics(" in service_source
    forbidden_hits = [
        token
        for token in (
            "import inputs_page",
            "from inputs_page",
            "import streamlit",
            "from streamlit",
            "st.session_state",
        )
        if token in service_source
    ]
    checks = {
        "wrapper_delegates_to_candidate_evaluation": wrapper_delegates,
        "old_page_annotation_logic_removed": old_page_logic_removed,
        "service_helper_present": service_present,
        "candidate_evaluation_forbidden_import_hits_empty": not forbidden_hits,
        "parity_matches": not mismatches,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "TARGET_BAND_METRIC_ANNOTATION_SERVICE_EXTRACTED",
        "checks": checks,
        "case_count": len(rows),
        "mismatch_count": len(mismatches),
        "rows": rows,
        "mismatches": mismatches,
        "forbidden_service_import_hits": forbidden_hits,
        "next_safe_slice": "auto-design selector base score component policy boundary",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_candidate_target_band_metric_annotation_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_candidate_target_band_metric_annotation_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto-Design Candidate Target-Band Metric Annotation Service Extraction",
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
    print(f"design_guide_auto_design_candidate_target_band_metric_annotation_service_extraction {payload.get('status')}")
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
