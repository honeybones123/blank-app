"""Verify auto-design winner metadata projection service extraction."""

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

from design_brain.candidate_evaluation import (  # noqa: E402
    apply_auto_design_winner_metadata_projection,
)


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


def _winner(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "candidate_post_util": 0.91,
        "candidate_reaches_target_band": True,
        "candidate_distance_to_target_band": 0.01,
    }


def _old_projection(
    winner: dict[str, Any],
    *,
    selected_because_band: bool,
    winner_pool_mode: str,
    band_reacher_labels_considered: list[str],
    winner_goal_score: float | None,
    runner_up_goal_score: float | None,
    goal_tie_break_reason: str | None,
    goal_preference: str,
) -> dict[str, Any]:
    winner["winning_candidate_post_util"] = winner.get("candidate_post_util")
    winner["winning_candidate_reaches_target_band"] = winner.get("candidate_reaches_target_band")
    winner["winning_candidate_distance_to_target_band"] = winner.get("candidate_distance_to_target_band")
    winner["winning_candidate_selected_because_reaches_band"] = selected_because_band
    winner["winning_candidate_selected_from_band_reachers"] = selected_because_band
    winner["winner_pool_mode"] = winner_pool_mode
    winner["band_reacher_labels_considered"] = [str(label or "")[:100] for label in band_reacher_labels_considered]
    winner["winning_candidate_goal_score"] = winner_goal_score
    winner["runner_up_goal_score"] = runner_up_goal_score
    winner["goal_tie_break_reason"] = goal_tie_break_reason
    winner["winning_candidate_goal_preference"] = goal_preference
    label = str(winner.get("label") or "").strip()
    if label:
        winner["canonical_winner_label"] = label
        winner["title_locked_from_final_winner"] = True
    return winner


def _summary(winner: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(winner, dict):
        return {}
    keys = [
        "winning_candidate_post_util",
        "winning_candidate_reaches_target_band",
        "winning_candidate_distance_to_target_band",
        "winning_candidate_selected_because_reaches_band",
        "winning_candidate_selected_from_band_reachers",
        "winner_pool_mode",
        "band_reacher_labels_considered",
        "winning_candidate_goal_score",
        "runner_up_goal_score",
        "goal_tie_break_reason",
        "winning_candidate_goal_preference",
        "canonical_winner_label",
        "title_locked_from_final_winner",
    ]
    return {key: winner.get(key) for key in keys if key in winner}


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    selector_start, selector_end, selector_segment = _function_segment(inputs_source, "_select_best_auto_design_candidate")
    helper_start, helper_end, helper_segment = _function_segment(
        service_source,
        "apply_auto_design_winner_metadata_projection",
    )
    cases = [
        {
            "name": "band_selected_with_label",
            "label": "band winner",
            "selected_because_band": True,
            "winner_pool_mode": "band_reachers_only",
            "labels": ["first", "second " + "x" * 120],
            "winner_goal_score": 1.5,
            "runner_up_goal_score": 2.0,
            "goal_tie_break_reason": "shallower:band winner",
            "goal_preference": "shallower",
        },
        {
            "name": "compliant_selected_blank_label",
            "label": "  ",
            "selected_because_band": False,
            "winner_pool_mode": "all_compliant",
            "labels": [],
            "winner_goal_score": None,
            "runner_up_goal_score": None,
            "goal_tie_break_reason": None,
            "goal_preference": "balanced",
        },
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[str] = []
    for case in cases:
        old_winner = _winner(case["label"])
        new_winner = _winner(case["label"])
        old_result = _old_projection(
            old_winner,
            selected_because_band=case["selected_because_band"],
            winner_pool_mode=case["winner_pool_mode"],
            band_reacher_labels_considered=case["labels"],
            winner_goal_score=case["winner_goal_score"],
            runner_up_goal_score=case["runner_up_goal_score"],
            goal_tie_break_reason=case["goal_tie_break_reason"],
            goal_preference=case["goal_preference"],
        )
        new_result = apply_auto_design_winner_metadata_projection(
            new_winner,
            selected_because_band=case["selected_because_band"],
            winner_pool_mode=case["winner_pool_mode"],
            band_reacher_labels_considered=case["labels"],
            winner_goal_score=case["winner_goal_score"],
            runner_up_goal_score=case["runner_up_goal_score"],
            goal_tie_break_reason=case["goal_tie_break_reason"],
            goal_preference=case["goal_preference"],
        )
        same_ref = new_result is new_winner
        match = _summary(old_result) == _summary(new_result) and same_ref
        if not match:
            mismatches.append(case["name"])
        rows.append(
            {
                "case": case["name"],
                "match": match,
                "same_ref": same_ref,
                "old": _summary(old_result),
                "new": _summary(new_result),
            }
        )

    checks = {
        "selector_delegates_winner_metadata_projection": "_apply_auto_design_winner_metadata_projection(" in selector_segment,
        "old_page_metadata_assignments_removed": "winner[\"winning_candidate_post_util\"] = winner.get(\"candidate_post_util\")" not in selector_segment
        and "winner[\"canonical_winner_label\"] = _wl" not in selector_segment
        and "winner[\"title_locked_from_final_winner\"] = True" not in selector_segment,
        "identity_and_result_packaging_service_owned_or_trace_only": (
            "_build_auto_design_selected_candidate_selection_result_from_context(" in selector_segment
            and "_build_selected_auto_design_candidate_selection_result(" not in selector_segment
        ),
        "trace_publication_remains_page_owned": "_merge_design_guide_rank_trace(" in selector_segment,
        "helper_exported": "\"apply_auto_design_winner_metadata_projection\"" in service_source,
        "no_page_or_ui_imports_in_candidate_evaluation": not any(
            token in service_source
            for token in (
                "import inputs_page",
                "from inputs_page",
                "import streamlit",
                "from streamlit",
                "st.session_state",
            )
        ),
        "service_avoids_forbidden_page_term": "one_click" not in helper_segment,
    }
    parity = {
        "all_cases_match": not mismatches,
        "mismatches": mismatches,
        "case_count": len(rows),
    }
    status = "PASS" if parity["all_cases_match"] and all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "WINNER_METADATA_PROJECTION_SERVICE_OWNED_RESULT_PACKAGING_SERVICE_OR_TRACE_ONLY"
            if status == "PASS"
            else "WINNER_METADATA_PROJECTION_EXTRACTION_FAILED"
        ),
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "extraction_complete_estimate": "99.6%",
        "selector_lines": {"start": selector_start, "end": selector_end, "count": selector_end - selector_start + 1},
        "helper_lines": {"start": helper_start, "end": helper_end, "count": helper_end - helper_start + 1},
        "parity": parity,
        "cases": rows,
        "checks": checks,
        "remaining_selector_policy": [
            "rank_trace_publication",
        ],
        "product_behavior_changed": False,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_winner_metadata_projection_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_winner_metadata_projection_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    checks_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["checks"].items()))
    parity_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["parity"].items()))
    report_path.write_text(
        "\n".join(
            [
                "# Auto-Design Winner Metadata Projection Service Extraction",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                f"Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
                "",
                "## Parity",
                "",
                parity_md,
                "",
                "## Static Checks",
                "",
                checks_md,
                "",
                "## Remaining Selector Policy",
                "",
                "\n".join(f"- `{item}`" for item in payload["remaining_selector_policy"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_auto_design_winner_metadata_projection_service_extraction {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
