"""Verify target-band next-hop precheck policy extraction."""

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
    resolve_candidate_target_band_distance,
    resolve_target_band_next_hop_precheck,
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
    all_key_pass: bool = True,
    worst_util: float = 0.7,
    statuses: dict[str, str] | None = None,
    state: dict[str, Any] | None = None,
    target_domains: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "target_domains_for_band": list(target_domains or ["bending", "shear"]),
        "overview": {
            "all_key_pass": bool(all_key_pass),
            "worst_util": worst_util,
            "statuses": dict(statuses or {"bending": "PASS", "shear": "PASS"}),
            "utils": {"bending": worst_util, "shear": worst_util},
            "packs": {"bending": {"summary_Mu_star_kNm": worst_util * 100.0, "summary_phiMu_kNm": 100.0}},
        },
        "state": dict(state if state is not None else {"D": 650, "b": 400, "design_optimisation_goal": "balanced"}),
    }


def _strict_ok(overview: dict[str, Any], mode_config: dict[str, Any]) -> bool:
    try:
        lo = float(mode_config.get("target_util_min", DEFAULT_MIN) or DEFAULT_MIN)
        hi = float(mode_config.get("target_util_max", DEFAULT_MAX) or DEFAULT_MAX)
    except Exception:
        lo = DEFAULT_MIN
        hi = DEFAULT_MAX
    try:
        worst = float(overview.get("governing_util", overview.get("worst_util", 0.0)) or 0.0)
    except (TypeError, ValueError):
        return False
    statuses = dict(overview.get("statuses") or {})
    any_fail = any(value == FAIL or str(value or "").strip().upper() == "FAIL" for value in statuses.values())
    return bool(not any_fail and lo <= worst <= hi)


def _distance(eval_obj: dict[str, Any], mode_config: dict[str, Any]) -> float:
    return resolve_candidate_target_band_distance(
        eval_obj,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        optimisation_goal_resolver=_goal_from_state,
    )


def _old_precheck(current_eval: dict[str, Any] | None, mode_config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(current_eval, dict):
        return {"allowed": False, "overview": {}, "current_distance": None, "current_state": {}}
    overview = dict((current_eval.get("overview") or {}))
    if not bool(overview.get("all_key_pass")):
        return {"allowed": False, "overview": overview, "current_distance": None, "current_state": {}}
    if _strict_ok(overview, mode_config):
        return {"allowed": False, "overview": overview, "current_distance": None, "current_state": {}}
    current_distance = _distance(current_eval, mode_config)
    if current_distance is None or not math.isfinite(float(current_distance)):
        return {"allowed": False, "overview": overview, "current_distance": current_distance, "current_state": {}}
    current_state = dict(current_eval.get("state") or {})
    if not current_state:
        return {"allowed": False, "overview": overview, "current_distance": current_distance, "current_state": {}}
    return {
        "allowed": True,
        "overview": overview,
        "current_distance": float(current_distance),
        "current_state": current_state,
    }


def _new_precheck(current_eval: dict[str, Any] | None, mode_config: dict[str, Any]) -> dict[str, Any]:
    result = resolve_target_band_next_hop_precheck(
        current_eval,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        optimisation_goal_resolver=_goal_from_state,
    )
    return {
        "allowed": bool(result.get("allowed")),
        "overview": dict(result.get("overview") or {}),
        "current_distance": result.get("current_distance"),
        "current_state": dict(result.get("current_state") or {}),
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, helper = _function_segment(inputs_source, "_one_click_best_next_hop_improving_candidate")
    mode_config = {"target_util_min": DEFAULT_MIN, "target_util_max": DEFAULT_MAX}
    cases = [
        ("allowed", _candidate(worst_util=0.7)),
        ("missing_eval", None),
        ("not_all_pass", _candidate(all_key_pass=False, worst_util=0.7)),
        ("already_in_band", _candidate(worst_util=0.9)),
        ("already_in_band_but_fail_status", _candidate(worst_util=0.9, statuses={"bending": "FAIL", "shear": "PASS"})),
        ("missing_state", _candidate(worst_util=0.7, state={})),
        ("no_target_domains_nonfinite_distance", _candidate(worst_util=0.7, target_domains=[])),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, candidate in cases:
        old = _old_precheck(candidate, mode_config)
        new = _new_precheck(candidate, mode_config)
        row = {
            "case": name,
            "old_allowed": bool(old.get("allowed")),
            "new_allowed": bool(new.get("allowed")),
            "old_distance": old.get("current_distance"),
            "new_distance": new.get("current_distance"),
            "state_matches": dict(old.get("current_state") or {}) == dict(new.get("current_state") or {}),
        }
        row["matches"] = (
            row["old_allowed"] == row["new_allowed"]
            and row["state_matches"]
            and (
                row["old_distance"] == row["new_distance"]
                or (
                    row["old_distance"] is not None
                    and row["new_distance"] is not None
                    and abs(float(row["old_distance"]) - float(row["new_distance"])) < 1e-9
                )
            )
        )
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    service_present = "def resolve_target_band_next_hop_precheck(" in candidate_source
    page_delegates = "_resolve_target_band_next_hop_precheck(" in helper
    old_inline_precheck_removed = all(
        token not in helper
        for token in (
            "if not isinstance(current_eval, dict):",
            "_one_click_strict_target_band_ok(",
            "current_distance = _candidate_target_band_distance(",
            "if current_distance is None",
            "current_state = dict(current_eval.get(\"state\")",
        )
    )
    generator_loop_retained = all(
        token in helper
        for token in (
            "_build_auto_design_context(",
            "generate_compliant_refinement_candidates(",
            "evaluator_fn=evaluate_candidate_full",
            "_select_best_target_band_refinement_candidate(",
        )
    )
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
        or not service_present
        or not page_delegates
        or not old_inline_precheck_removed
        or not generator_loop_retained
        or forbidden_service_hits
    ):
        status = "FAIL"
    return {
        "status": status,
        "surface": "target_band_next_hop_precheck_policy",
        "inputs_segment": {"function": "_one_click_best_next_hop_improving_candidate", "start_line": start, "end_line": end},
        "case_count": len(cases),
        "mismatches": mismatches,
        "parity_rows": rows,
        "static_checks": {
            "service_present": service_present,
            "page_delegates": page_delegates,
            "old_inline_precheck_removed": old_inline_precheck_removed,
            "generator_loop_retained": generator_loop_retained,
            "forbidden_service_hits": forbidden_service_hits,
        },
        "ownership": {
            "moved_to_candidate_evaluation": ["pure precheck before fallback next-hop generation"],
            "remains_page_owned": [
                "auto-design context construction",
                "refinement candidate generation",
                "canonical state pack callback",
                "full candidate evaluator callback",
                "target-domain attachment callback",
                "spacing-envelope callback",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "audit/evaluate best payload selection by distance after candidate rows exist",
    }


def write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_next_hop_precheck_policy_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_next_hop_precheck_policy_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Next-Hop Precheck Policy Extraction",
        "",
        f"## Summary: {payload['status']}",
        "",
        "Moved only the pure precheck before fallback next-hop generation into `design_brain.candidate_evaluation.resolve_target_band_next_hop_precheck(...)`.",
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
