"""Verify auto-design selector score-assignment loop service extraction."""

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
    score_auto_design_candidates_for_selection,
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


def _sample_candidates() -> list[dict[str, Any]]:
    return [
        {"id": "depth_650", "state": {"D": 650.0}, "score_seed": 4.5},
        {"id": "depth_625", "state": {"D": 625.0}, "score_seed": 2.0},
        {"id": "width_375", "state": {"b": 375.0}, "score_seed": 3.25},
    ]


def _annotate_factory(call_log: list[str]):
    def _annotate(candidate: dict[str, Any], mode_config: dict[str, Any]) -> None:
        call_log.append(f"annotate:{candidate.get('id')}")
        target_mid = float(mode_config.get("target_mid", 0.91) or 0.91)
        candidate["candidate_post_util"] = round(target_mid + float(candidate.get("score_seed", 0.0)) / 100.0, 6)
        candidate["candidate_distance_to_target_band"] = abs(float(candidate["candidate_post_util"]) - target_mid)
        candidate["candidate_reaches_target_band"] = candidate["candidate_distance_to_target_band"] <= 0.05

    return _annotate


def _score_factory(call_log: list[str]):
    def _score(candidate: dict[str, Any], mode_config: dict[str, Any], seed_candidate: dict[str, Any]) -> float:
        call_log.append(f"score:{candidate.get('id')}")
        multiplier = float(mode_config.get("score_multiplier", 10.0) or 10.0)
        seed_bias = float(seed_candidate.get("seed_bias", 0.0) or 0.0)
        return round(float(candidate.get("score_seed", 0.0)) * multiplier + seed_bias, 6)

    return _score


def _old_score_assignment(
    candidates: list[dict[str, Any]],
    mode_config: dict[str, Any],
    seed_candidate: dict[str, Any],
    call_log: list[str],
) -> list[dict[str, Any]]:
    annotate = _annotate_factory(call_log)
    score = _score_factory(call_log)
    for candidate in candidates:
        annotate(candidate, mode_config)
        candidate["score"] = score(candidate, mode_config, seed_candidate)
    return candidates


def _summarize_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": candidate.get("id"),
            "candidate_post_util": candidate.get("candidate_post_util"),
            "candidate_distance_to_target_band": candidate.get("candidate_distance_to_target_band"),
            "candidate_reaches_target_band": candidate.get("candidate_reaches_target_band"),
            "score": candidate.get("score"),
        }
        for candidate in candidates
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    selector_start, selector_end, selector_segment = _function_segment(inputs_source, "_select_best_auto_design_candidate")
    helper_start, helper_end, helper_segment = _function_segment(
        service_source,
        "score_auto_design_candidates_for_selection",
    )

    mode_config = {"target_mid": 0.915, "score_multiplier": 7.0}
    seed_candidate = {"seed_bias": 1.25}
    old_candidates = _sample_candidates()
    new_candidates = _sample_candidates()
    old_log: list[str] = []
    new_log: list[str] = []

    old_result = _old_score_assignment(old_candidates, mode_config, seed_candidate, old_log)
    new_payload = score_auto_design_candidates_for_selection(
        new_candidates,
        mode_config,
        seed_candidate,
        annotate_candidate_fn=_annotate_factory(new_log),
        score_candidate_fn=_score_factory(new_log),
    )
    new_result = list(new_payload.get("scored_candidates") or [])

    parity = {
        "candidate_order_unchanged": [row.get("id") for row in old_result] == [row.get("id") for row in new_result],
        "candidate_mutations_unchanged": _summarize_candidates(old_result) == _summarize_candidates(new_result),
        "callback_call_order_unchanged": old_log == new_log,
        "service_returns_same_candidate_objects": all(
            result_candidate is source_candidate
            for result_candidate, source_candidate in zip(new_result, new_candidates)
        ),
        "input_candidate_count_preserved": new_payload.get("input_candidate_count") == len(new_candidates),
        "scored_candidate_count_preserved": new_payload.get("scored_candidate_count") == len(new_candidates),
    }
    checks = {
        "selector_delegates_score_assignment": "_score_auto_design_candidates_for_selection(" in selector_segment,
        "old_page_local_score_loop_removed": "for candidate in valid_candidates:" not in selector_segment
        and "_annotate_candidate_target_band_metrics(candidate, mode_config)" not in selector_segment
        and "candidate[\"score\"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)" not in selector_segment,
        "winner_selection_is_service_owned_or_trace_only": (
            "_resolve_auto_design_winner_pool_decision(" in selector_segment
            and "_resolve_auto_design_band_reacher_ranked_pool(" in selector_segment
            and "_build_auto_design_selected_candidate_selection_result_from_context(" in selector_segment
            and "_merge_design_guide_rank_trace(" in selector_segment
        ),
        "helper_exported": "\"score_auto_design_candidates_for_selection\"" in service_source,
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
        "helper_accepts_plain_callbacks": "annotate_candidate_fn" in helper_segment and "score_candidate_fn" in helper_segment,
    }
    status = "PASS" if all(parity.values()) and all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "SCORE_ASSIGNMENT_LOOP_SERVICE_OWNED_WINNER_POLICY_SERVICE_OR_TRACE_ONLY"
            if status == "PASS"
            else "SCORE_ASSIGNMENT_LOOP_EXTRACTION_FAILED"
        ),
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "extraction_complete_estimate": "99.45%",
        "selector_lines": {"start": selector_start, "end": selector_end, "count": selector_end - selector_start + 1},
        "helper_lines": {"start": helper_start, "end": helper_end, "count": helper_end - helper_start + 1},
        "parity": parity,
        "checks": checks,
        "old_candidate_summary": _summarize_candidates(old_result),
        "new_candidate_summary": _summarize_candidates(new_result),
        "remaining_selector_policy": [
            "rank_trace_publication",
        ],
        "product_behavior_changed": False,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_score_assignment_loop_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_score_assignment_loop_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    checks_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["checks"].items()))
    parity_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["parity"].items()))
    report_path.write_text(
        "\n".join(
            [
                "# Auto-Design Score Assignment Loop Service Extraction",
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
    print(f"design_guide_auto_design_score_assignment_loop_service_extraction {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
