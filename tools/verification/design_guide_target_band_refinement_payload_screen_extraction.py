"""Verify target-band refinement payload screening extraction."""

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
    build_target_band_refinement_payload_if_valid,
    resolve_candidate_step_improves,
    resolve_candidate_target_band_distance,
)


INPUTS = ROOT / "inputs_page_app_contract_bridge.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET_MIN = 0.85
TARGET_MAX = 1.0
FAIL_STATUS = "FAIL"
MODE_CONFIG = {"target_util_min": TARGET_MIN, "target_util_max": TARGET_MAX}


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


def _goal_resolver(state: dict[str, Any]) -> str:
    return str((state or {}).get("design_optimisation_goal") or "balanced")


def _eval(util: Any, *, all_pass: bool = True) -> dict[str, Any]:
    status = "PASS" if all_pass else "FAIL"
    return {
        "state": {"design_optimisation_goal": "balanced"},
        "overview": {
            "all_key_pass": bool(all_pass),
            "worst_util": util,
            "governing_util": util,
            "utils": {"shear": util},
            "statuses": {"bending": status, "shear": status, "crack": "PASS", "deflection": "PASS"},
        },
        "worst_util": util,
    }


def _old_screen(
    *,
    candidate_state: dict[str, Any] | None,
    candidate_eval: dict[str, Any] | None,
    candidate_updates: dict[str, Any] | None,
    current_eval: dict[str, Any] | None,
    current_distance: Any,
    spacing_envelope_fail: bool,
) -> dict[str, Any] | None:
    if candidate_eval is None:
        return None
    candidate_overview = dict((candidate_eval.get("overview") or {}))
    if not bool(candidate_overview.get("all_key_pass")):
        return None
    if spacing_envelope_fail:
        return None
    candidate_distance = resolve_candidate_target_band_distance(
        candidate_eval,
        MODE_CONFIG,
        default_target_min=TARGET_MIN,
        default_target_max=TARGET_MAX,
        fail_status=FAIL_STATUS,
        optimisation_goal_resolver=_goal_resolver,
    )
    if candidate_distance is None or not math.isfinite(float(candidate_distance)):
        return None
    if float(candidate_distance) + 1e-9 >= float(current_distance):
        return None
    if not resolve_candidate_step_improves(
        candidate_eval,
        current_eval,
        MODE_CONFIG,
        default_target_min=TARGET_MIN,
        default_target_max=TARGET_MAX,
        fail_status=FAIL_STATUS,
        optimisation_goal_resolver=_goal_resolver,
    ):
        return None
    return {
        "state": dict(candidate_state or {}),
        "eval": candidate_eval,
        "distance": float(candidate_distance),
        "updates": dict(candidate_updates or {}),
    }


def _new_screen(**kwargs: Any) -> dict[str, Any] | None:
    return build_target_band_refinement_payload_if_valid(
        **kwargs,
        mode_config=MODE_CONFIG,
        default_target_min=TARGET_MIN,
        default_target_max=TARGET_MAX,
        fail_status=FAIL_STATUS,
        optimisation_goal_resolver=_goal_resolver,
    )


def _case_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current_eval = _eval(0.40)
    current_distance = resolve_candidate_target_band_distance(
        current_eval,
        MODE_CONFIG,
        default_target_min=TARGET_MIN,
        default_target_max=TARGET_MAX,
        fail_status=FAIL_STATUS,
        optimisation_goal_resolver=_goal_resolver,
    )
    cases = [
        ("valid_improving_candidate", {"b": 400}, _eval(0.80), {"b": 400}, False),
        ("missing_candidate_eval", {"b": 400}, None, {"b": 400}, False),
        ("candidate_not_all_pass", {"b": 400}, _eval(0.80, all_pass=False), {"b": 400}, False),
        ("spacing_envelope_fail", {"b": 400}, _eval(0.80), {"b": 400}, True),
        ("candidate_not_better", {"b": 400}, _eval(0.40), {"b": 400}, False),
        ("candidate_non_finite", {"b": 400}, _eval("nan"), {"b": 400}, False),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, candidate_state, candidate_eval, candidate_updates, spacing_fail in cases:
        old = _old_screen(
            candidate_state=candidate_state,
            candidate_eval=candidate_eval,
            candidate_updates=candidate_updates,
            current_eval=current_eval,
            current_distance=current_distance,
            spacing_envelope_fail=spacing_fail,
        )
        new = _new_screen(
            candidate_state=candidate_state,
            candidate_eval=candidate_eval,
            candidate_updates=candidate_updates,
            current_eval=current_eval,
            current_distance=current_distance,
            spacing_envelope_fail=spacing_fail,
        )
        row = {
            "case": name,
            "old_present": isinstance(old, dict),
            "new_present": isinstance(new, dict),
            "old_distance": old.get("distance") if isinstance(old, dict) else None,
            "new_distance": new.get("distance") if isinstance(new, dict) else None,
            "matches": old == new,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append({"case": name, "old": old, "new": new})
    return rows, mismatches


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, helper = _function_segment(inputs_source, "_one_click_best_next_hop_improving_candidate")
    rows, mismatches = _case_rows()

    static_checks = {
        "service_present": "def build_target_band_refinement_payload_if_valid(" in candidate_source,
        "page_delegates_payload_screen": (
            "_build_target_band_refinement_payload_if_valid(" in helper
            or "_select_best_target_band_refinement_candidate(" in helper
        ),
        "old_inline_all_pass_screen_removed": 'candidate_overview.get("all_key_pass")' not in helper,
        "old_inline_distance_screen_removed": "_candidate_target_band_distance(candidate_eval, mode_config)" not in helper,
        "old_inline_step_improves_removed": "_one_click_step_improves(candidate_eval, current_eval, mode_config)" not in helper,
        "generator_and_evaluator_retained": all(
            token in helper
            for token in (
                "_build_auto_design_context(",
                "generate_compliant_refinement_candidates(",
                "evaluator_fn=evaluate_candidate_full",
                "state_pack_fn=_build_canonical_design_state_pack",
                "target_domain_attachment_fn=_one_click_attach_eval_target_domains",
                "spacing_envelope_fail_fn=_one_click_has_unresolved_spacing_envelope_fail",
            )
        ),
    }
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
    static_checks["forbidden_service_hits"] = forbidden_service_hits

    status = "PASS"
    if mismatches or not all(value is True for key, value in static_checks.items() if key != "forbidden_service_hits") or forbidden_service_hits:
        status = "FAIL"
    return {
        "status": status,
        "surface": "target_band_refinement_payload_screen",
        "inputs_segment": {
            "function": "_one_click_best_next_hop_improving_candidate",
            "start_line": start,
            "end_line": end,
        },
        "case_count": len(rows),
        "parity_rows": rows,
        "mismatches": mismatches,
        "static_checks": static_checks,
        "ownership": {
            "moved_to_candidate_evaluation": [
                "post-evaluation all-pass screen",
                "spacing-envelope rejection input handling",
                "target-band distance improvement screen",
                "step-improvement screen",
                "next-hop payload construction",
            ],
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
        "next_safe_slice": "extract or bound auto-design context construction and refinement candidate generation",
    }


def write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_refinement_payload_screen_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_refinement_payload_screen_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Refinement Payload Screen Extraction",
        "",
        f"## Summary: {payload['status']}",
        "",
        "Moved post-evaluation refinement payload screening into `design_brain.candidate_evaluation.build_target_band_refinement_payload_if_valid(...)`.",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Parity",
            f"- Cases checked: `{payload['case_count']}`",
            f"- Mismatches: `{len(payload['mismatches'])}`",
            "",
            "## Remaining Page-Owned Logic",
        ]
    )
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
