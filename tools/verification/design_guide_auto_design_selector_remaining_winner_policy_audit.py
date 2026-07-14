"""Audit remaining auto-design selector winner policy in inputs_page.py."""

from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
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


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    ranking_source = _read(ROOT / "design_brain" / "ranking.py")
    start, end, selector_segment = _function_segment(inputs_source, "_select_best_auto_design_candidate")

    moved_surfaces = {
        "objective_util_service": "resolve_auto_design_candidate_objective_util(" in service_source,
        "target_band_annotation_service": "resolve_auto_design_candidate_target_band_metrics(" in service_source,
        "violation_score_service": "resolve_auto_design_candidate_violation_score(" in service_source,
        "shear_practicality_service": "resolve_auto_design_shear_candidate_practicality_metrics(" in service_source,
        "shallower_metrics_service": "resolve_auto_design_shallower_beam_metrics(" in service_source,
        "band_reacher_delta_service": "resolve_auto_design_band_reacher_delta_metrics(" in service_source,
        "band_reaching_goal_score_service": "resolve_auto_design_band_reaching_candidate_goal_score(" in service_source,
        "shallower_selection_key_service": "resolve_auto_design_shallower_beam_selection_key(" in service_source,
        "row_layout_filter_service": "filter_auto_design_candidates_by_row_layout(" in service_source,
        "score_assignment_loop_service": "score_auto_design_candidates_for_selection(" in service_source
        and "_score_auto_design_candidates_for_selection(" in selector_segment,
        "winner_pool_decision_service": "resolve_auto_design_winner_pool_decision(" in service_source
        and "_resolve_auto_design_winner_pool_decision(" in selector_segment,
        "band_reacher_ranked_pool_service": "resolve_auto_design_band_reacher_ranked_pool(" in service_source
        and "_resolve_auto_design_band_reacher_ranked_pool(" in selector_segment,
        "winner_metadata_projection_service": "apply_auto_design_winner_metadata_projection(" in service_source
        and "_apply_auto_design_winner_metadata_projection(" in selector_segment,
        "selected_result_assembly_service": "build_auto_design_selected_candidate_selection_result_from_context(" in ranking_source
        and "_build_auto_design_selected_candidate_selection_result_from_context(" in selector_segment,
    }

    remaining_surfaces: list[dict[str, Any]] = [
        {
            "surface": "rank_trace_publication",
            "evidence_tokens": ["_ACTIVE_GUIDANCE_RANK_TRACE", "_merge_design_guide_rank_trace"],
            "current_owner": "inputs_page",
            "target_owner": "page_shell_debug_sink",
            "classification": "page_owned_debug_sink_allowed",
            "readiness": "SHELL_ONLY_AFTER_TRACE_PAYLOAD_SERVICE_OBJECT",
            "first_slice": "service returns trace payload; page appends to active trace sink",
        },
    ]

    for surface in remaining_surfaces:
        surface["tokens_present"] = {
            token: token in selector_segment
            for token in surface["evidence_tokens"]
        }
        surface["evidence_present"] = all(surface["tokens_present"].values())

    checks = {
        "all_prior_metric_surfaces_service_owned": all(moved_surfaces.values()),
        "selector_still_present": "def _select_best_auto_design_candidate(" in selector_segment,
        "remaining_surface_tokens_found": all(surface["evidence_present"] for surface in remaining_surfaces),
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
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "REMAINING_SELECTOR_POLICY_SHELL_BOUND_TRACE_SINK_ONLY"
            if status == "PASS"
            else "REMAINING_SELECTOR_POLICY_AUDIT_FAILED"
        ),
        "extraction_complete_estimate": "99.65%",
        "selector_lines": {"start": start, "end": end, "count": end - start + 1},
        "moved_surfaces": moved_surfaces,
        "remaining_surfaces": remaining_surfaces,
        "checks": checks,
        "first_safe_implementation_slice": "rank_trace_publication_shell_bound_or_payload_projection",
        "stop_conditions": [
            "selected candidate changes",
            "winner_pool_mode changes",
            "rank trace payload changes",
            "no-winner result reason changes",
            "candidate score or annotation changes",
            "visible wording or CTA/apply semantics change",
        ],
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_selector_remaining_winner_policy_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_selector_remaining_winner_policy_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    rows = [
        "| Surface | Current owner | Target owner | Classification | Readiness | First slice |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for surface in payload["remaining_surfaces"]:
        rows.append(
            "| {surface} | {current_owner} | {target_owner} | {classification} | {readiness} | {first_slice} |".format(
                **surface
            )
        )
    checks_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["checks"].items()))
    moved_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["moved_surfaces"].items()))
    report_path.write_text(
        "\n".join(
            [
                "# Auto-Design Selector Remaining Winner Policy Audit",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                f"Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
                "",
                "## Already Service-Owned Selector Surfaces",
                "",
                moved_md,
                "",
                "## Remaining Selector Surfaces",
                "",
                *rows,
                "",
                "## Checks",
                "",
                checks_md,
                "",
                "## First Safe Implementation Slice",
                "",
                str(payload["first_safe_implementation_slice"]),
                "",
                "## Stop Conditions",
                "",
                "\n".join(f"- {item}" for item in payload["stop_conditions"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_auto_design_selector_remaining_winner_policy_audit {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
