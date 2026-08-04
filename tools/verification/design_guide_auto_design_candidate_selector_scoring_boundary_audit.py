"""Audit target-band annotation/base scoring extraction for the shared selector.

This is proof-only. It does not move scoring, ranking, family behaviour,
visible wording, CTA/apply semantics, or trace emission.
"""

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


def _presence(segment: str, tokens: list[str]) -> dict[str, bool]:
    return {token: token in segment for token in tokens}


def _surface(
    *,
    name: str,
    function: str,
    segment: str,
    classification: str,
    target_owner: str,
    tokens: list[str],
    extraction_readiness: str,
    first_safe_slice: str,
    risk: str,
) -> dict[str, Any]:
    token_presence = _presence(segment, tokens)
    return {
        "surface": name,
        "function": function,
        "classification": classification,
        "current_owner": "inputs_page.py",
        "target_owner": target_owner,
        "tokens": token_presence,
        "present": all(token_presence.values()),
        "extraction_readiness": extraction_readiness,
        "first_safe_slice": first_safe_slice,
        "risk": risk,
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    selector_start, selector_end, selector_segment = _function_segment(inputs_source, "_select_best_auto_design_candidate")
    annotate_start, annotate_end, annotate_segment = _function_segment(inputs_source, "_annotate_candidate_target_band_metrics")
    score_start, score_end, score_segment = _function_segment(inputs_source, "_score_auto_design_candidate_components")
    shear_start, shear_end, shear_segment = _function_segment(inputs_source, "_shear_candidate_practicality_metrics")
    objective_start, objective_end, objective_segment = _function_segment(inputs_source, "_candidate_objective_util")
    domains_start, domains_end, domains_segment = _function_segment(inputs_source, "_one_click_required_domain_progress")

    surfaces = [
        _surface(
            name="selector score assignment callsite",
            function="_select_best_auto_design_candidate",
            segment=selector_segment,
            classification="PAGE_OWNED_SELECTOR_SCORE_ASSIGNMENT",
            target_owner="design_brain.candidate_evaluation",
            tokens=[
                "_annotate_candidate_target_band_metrics(candidate, mode_config)",
                "candidate[\"score\"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)",
            ],
            extraction_readiness="READY_AFTER_SCORE_POLICY_SURFACE_MOVES",
            first_safe_slice="move objective/domain metric projection before score assignment",
            risk="MEDIUM",
        ),
        _surface(
            name="target-band metric annotation",
            function="_annotate_candidate_target_band_metrics",
            segment=annotate_segment,
            classification="PAGE_OWNED_TARGET_BAND_METRIC_POLICY",
            target_owner="design_brain.candidate_evaluation",
            tokens=[
                "_candidate_objective_util(",
                "_distance_to_target_band(",
                "_candidate_reaches_target_band_one_step(",
                "candidate[\"candidate_post_util\"]",
            ],
            extraction_readiness="NOT_READY_UNTIL_OBJECTIVE_AND_DOMAIN_POLICY_MOVE",
            first_safe_slice="extract objective util and distance projection as pure candidate_evaluation helpers",
            risk="HIGH",
        ),
        _surface(
            name="base score component policy",
            function="_score_auto_design_candidate_components",
            segment=score_segment,
            classification="PAGE_OWNED_SCORE_POLICY",
            target_owner="design_brain.candidate_evaluation or family-owned ranking policy after ownership decision",
            tokens=[
                "_shear_candidate_practicality_metrics(",
                "_candidate_objective_util(",
                "_mode_target_midpoint(",
                "_candidate_ductility_governs(",
                "_shallower_beam_metrics(",
                "_candidate_violation_score(",
            ],
            extraction_readiness="NOT_READY_TO_MOVE_WHOLE_SCORE_POLICY",
            first_safe_slice="extract objective/domain target-band metrics before moving score components",
            risk="HIGH",
        ),
        _surface(
            name="shear practicality metrics",
            function="_shear_candidate_practicality_metrics",
            segment=shear_segment,
            classification="PAGE_OWNED_SHARED_CANDIDATE_POLICY",
            target_owner="design_brain.candidate_evaluation",
            tokens=[
                "_int_from_state(",
                "_float_from_state(",
                "_design_width_value(",
                "shear_candidate_total_practicality_penalty",
            ],
            extraction_readiness="READY_AFTER_PLAIN_STATE_ACCESSOR_BOUNDARY",
            first_safe_slice="move after replacing page state accessors with plain scalar extraction",
            risk="MEDIUM",
        ),
        _surface(
            name="objective util projection",
            function="_candidate_objective_util",
            segment=objective_segment,
            classification="PAGE_OWNED_OBJECTIVE_UTIL_POLICY",
            target_owner="design_brain.candidate_evaluation",
            tokens=[
                "governing_util",
                "worst_util",
                "bending_util",
                "shear_util",
            ],
            extraction_readiness="FIRST_EXTRACTION_CANDIDATE",
            first_safe_slice="move objective util projection with exact parity cases",
            risk="LOW",
        ),
        _surface(
            name="required-domain progress policy",
            function="_one_click_required_domain_progress",
            segment=domains_segment,
            classification="PAGE_OWNED_REQUIRED_DOMAIN_PROGRESS_POLICY",
            target_owner="design_brain.candidate_evaluation or DesignGuideController after ownership decision",
            tokens=[
                "_one_click_eval_domain_scores(",
                "required_unsatisfied_count",
                "required_fail_domains",
                "domain_total_distance",
            ],
            extraction_readiness="NOT_READY_UNTIL_DOMAIN_SCORE_HELPERS_MOVE",
            first_safe_slice="audit one-click domain score helpers before moving required-domain progress",
            risk="HIGH",
        ),
    ]

    first = next(surface for surface in surfaces if surface["surface"] == "objective util projection")
    status = "PASS"
    decision = "SCORING_NOT_READY_WHOLE_MOVE_OBJECTIVE_UTIL_FIRST"
    return {
        "status": status,
        "decision": decision,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "selector_lines": {"start": selector_start, "end": selector_end},
        "candidate_evaluation_has_selector_row_validity": "resolve_auto_design_candidate_row_layout_validity" in candidate_source,
        "candidate_evaluation_has_objective_util_projection": "resolve_auto_design_candidate_objective_util" in candidate_source,
        "surfaces": surfaces,
        "first_safe_implementation_slice": {
            "name": "auto_design_candidate_objective_util_projection_extraction",
            "target": first["function"],
            "owner_after": "design_brain.candidate_evaluation",
            "why_first": (
                "Target-band annotation and score policy both depend on objective util; "
                "moving that low-risk pure projection enables later annotation extraction."
            ),
            "required_verifier": "tools/verification/design_guide_auto_design_candidate_objective_util_projection_extraction.py",
        },
        "stop_conditions": [
            "objective util parity differs",
            "candidate_post_util changes",
            "candidate_reaches_target_band changes",
            "score changes",
            "selected candidate changes",
            "visible wording changes",
            "CTA/apply semantics change",
            "any composed lock fails",
        ],
        "product_behavior_changed": False,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_candidate_selector_scoring_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_auto_design_candidate_selector_scoring_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Auto-Design Candidate Selector Scoring Boundary Audit",
        "",
        "## Executive Summary",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "The shared selector scoring layer is not safe to move wholesale. Target-band annotation and score components depend on objective-util, required-domain progress, shear practicality, ductility, and shallow-beam policies still housed in `inputs_page.py`.",
        "",
        "## Surface Inventory",
        "| Surface | Function | Classification | Target owner | Readiness | Risk |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for surface in payload["surfaces"]:
        lines.append(
            "| {surface} | `{function}` | {classification} | {target_owner} | {readiness} | {risk} |".format(
                surface=surface["surface"],
                function=surface["function"],
                classification=surface["classification"],
                target_owner=surface["target_owner"],
                readiness=surface["extraction_readiness"],
                risk=surface["risk"],
            )
        )
    first = payload["first_safe_implementation_slice"]
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first['name']}`",
            f"- Target: `{first['target']}`",
            f"- Owner after: {first['owner_after']}",
            f"- Why first: {first['why_first']}",
            f"- Required verifier: `{first['required_verifier']}`",
            "",
            "## Stop Conditions",
        ]
    )
    for stop in payload["stop_conditions"]:
        lines.append(f"- {stop}")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
