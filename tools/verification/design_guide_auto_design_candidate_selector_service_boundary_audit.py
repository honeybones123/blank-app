"""Audit the shared auto-design candidate selector service boundary.

This is proof-only. It does not move selection/ranking policy, candidate
evaluation, visible wording, CTA/apply semantics, family runtimes, or page
trace emission.
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

SELECTOR = "_select_best_auto_design_candidate"


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


def _line_number(source: str, needle: str) -> int | None:
    for idx, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return idx
    return None


def _callsites(source: str, name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, line in enumerate(source.splitlines(), start=1):
        if f"{name}(" not in line:
            continue
        if line.lstrip().startswith("def "):
            continue
        out.append({"line": idx, "text": line.strip()})
    return out


def _tokens(segment: str, names: list[str]) -> dict[str, bool]:
    return {name: name in segment for name in names}


def _surface(
    *,
    name: str,
    classification: str,
    current_owner: str,
    target_owner: str,
    deletion_readiness: str,
    risk: str,
    tokens: list[str],
    segment: str,
    required_before_move: str,
    first_safe_slice: str,
) -> dict[str, Any]:
    token_presence = _tokens(segment, tokens)
    return {
        "surface": name,
        "classification": classification,
        "current_owner": current_owner,
        "target_owner": target_owner,
        "deletion_readiness": deletion_readiness,
        "risk": risk,
        "tokens": token_presence,
        "present": all(token_presence.values()),
        "required_verifier_before_moving": required_before_move,
        "first_safe_implementation_slice": first_safe_slice,
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_eval_source = _read(CANDIDATE_EVALUATION)
    selector_start, selector_end, selector_segment = _function_segment(inputs_source, SELECTOR)
    callsites = _callsites(inputs_source, SELECTOR)

    surfaces = [
        _surface(
            name="candidate row layout validity screen",
            classification="SERVICE_CANDIDATE_WITH_PAGE_HELPER_DEPENDENCIES",
            current_owner="inputs_page.py",
            target_owner="design_brain.candidate_evaluation with plain layout/geometry inputs",
            deletion_readiness="NOT_READY",
            risk="MEDIUM",
            tokens=[
                "is_valid_reo_layout(",
                "_design_width_value(",
                "_float_from_state(",
                "_int_from_state(",
            ],
            segment=selector_segment,
            required_before_move="design_guide_auto_design_candidate_selector_row_validity_service_extraction.py",
            first_safe_slice=(
                "extract a plain-data row-layout validity adapter into candidate_evaluation; "
                "keep page helpers as input normalization until geometry accessors are service-owned"
            ),
        ),
        _surface(
            name="target-band annotation and base scoring",
            classification="PAGE_OWNED_DESIGN_BRAIN_RANKING_POLICY",
            current_owner="inputs_page.py",
            target_owner="design_brain.candidate_evaluation",
            deletion_readiness="NOT_READY",
            risk="HIGH",
            tokens=[
                "_annotate_candidate_target_band_metrics(",
                "_score_auto_design_candidate(",
                "candidate[\"score\"]",
            ],
            segment=selector_segment,
            required_before_move="design_guide_auto_design_candidate_selector_scoring_service_extraction.py",
            first_safe_slice=(
                "move target-band annotation and score assignment behind a service helper "
                "after row-validity parity is proven"
            ),
        ),
        _surface(
            name="winner-pool selection and band-reacher policy",
            classification="PAGE_OWNED_DESIGN_BRAIN_SELECTION_POLICY",
            current_owner="inputs_page.py",
            target_owner="design_brain.candidate_evaluation",
            deletion_readiness="NOT_READY",
            risk="HIGH",
            tokens=[
                "band_reachers",
                "force_band_reacher_pool",
                "winner_pool_mode",
                "_candidate_in_target_band(",
                "_candidate_violation_score(",
            ],
            segment=selector_segment,
            required_before_move="design_guide_auto_design_candidate_selector_winner_policy_extraction.py",
            first_safe_slice=(
                "move winner-pool selection only after row-validity and score annotation "
                "are service-owned"
            ),
        ),
        _surface(
            name="goal tie-break ranking for band reachers",
            classification="PAGE_OWNED_DESIGN_BRAIN_GOAL_TIE_BREAK_POLICY",
            current_owner="inputs_page.py",
            target_owner="design_brain.candidate_evaluation or family-owned ranking policy",
            deletion_readiness="NOT_READY",
            risk="HIGH",
            tokens=[
                "_design_optimisation_goal(",
                "_score_band_reaching_candidate_for_goal(",
                "_band_reacher_delta_metrics(",
                "candidate_goal_tie_break_reason",
            ],
            segment=selector_segment,
            required_before_move="design_guide_auto_design_candidate_selector_goal_tie_break_extraction.py",
            first_safe_slice=(
                "extract as a pure ranking policy only after confirming whether the goal "
                "preference is shared candidate policy or family-owned policy"
            ),
        ),
        _surface(
            name="winner metadata/result packaging",
            classification="SERVICE_CANDIDATE_RESULT_PACKAGING",
            current_owner="inputs_page.py with design_brain.ranking result object",
            target_owner="design_brain.candidate_evaluation plus design_brain.ranking",
            deletion_readiness="NOT_READY",
            risk="MEDIUM",
            tokens=[
                "winning_candidate_post_util",
                "canonical_winner_label",
                "_build_selected_auto_design_candidate_selection_result(",
                "_auto_design_candidate_identity(",
            ],
            segment=selector_segment,
            required_before_move="design_guide_auto_design_candidate_selector_result_packaging_extraction.py",
            first_safe_slice=(
                "move pure winner metadata/result packaging after selection policy parity is green"
            ),
        ),
        _surface(
            name="rank trace emission",
            classification="PAGE_SHELL_TRACE_EMISSION",
            current_owner="inputs_page.py",
            target_owner="inputs_page.py shell; service may return trace payload only",
            deletion_readiness="SHELL_ONLY_KEEP",
            risk="LOW",
            tokens=[
                "_ACTIVE_GUIDANCE_RANK_TRACE",
                "_merge_design_guide_rank_trace(",
                "auto_design_convergence_selection",
                "auto_design_final_selector",
            ],
            segment=selector_segment,
            required_before_move="design_guide_auto_design_candidate_selector_trace_payload_extraction.py",
            first_safe_slice=(
                "keep actual trace emission page-owned; optional service output can expose plain trace rows"
            ),
        ),
    ]

    unresolved = [
        surface["surface"]
        for surface in surfaces
        if surface["classification"].startswith("PAGE_OWNED_DESIGN_BRAIN")
        or surface["classification"].startswith("SERVICE_CANDIDATE")
    ]
    decision = "NOT_READY_TO_MOVE_WHOLE_SELECTOR_FIRST_SAFE_SLICE_IDENTIFIED"
    if not unresolved:
        decision = "READY_TO_EXTRACT_WHOLE_SELECTOR"

    return {
        "status": "PASS",
        "decision": decision,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "selector": {
            "file": str(INPUTS.relative_to(ROOT)),
            "name": SELECTOR,
            "line_start": selector_start,
            "line_end": selector_end,
            "line_count": selector_end - selector_start + 1,
        },
        "callsite_count": len(callsites),
        "callsites": callsites,
        "service_existing_state": {
            "candidate_evaluation_file": str(CANDIDATE_EVALUATION.relative_to(ROOT)),
            "has_auto_selector_service": "select_best_auto_design_candidate" in candidate_eval_source,
            "has_generic_update_evaluation_boundary": "evaluate_design_candidate_with_updates" in candidate_eval_source,
            "has_shear_low_util_boundary": "evaluate_shear_low_util_candidate_with_updates" in candidate_eval_source,
        },
        "surfaces": surfaces,
        "first_safe_implementation_slice": {
            "name": "auto_design_candidate_selector_row_validity_service_extraction",
            "target": "candidate row layout validity screen",
            "owner_after": "design_brain.candidate_evaluation owns plain-data row validity projection; inputs_page.py normalizes page geometry inputs",
            "why_first": (
                "It is the earliest selector filter and can be proven without moving "
                "winner ranking, goal tie-breaks, trace emission, CTA/apply, or family runtimes."
            ),
            "required_verifier": "tools/verification/design_guide_auto_design_candidate_selector_row_validity_service_extraction.py",
        },
        "stop_conditions": [
            "row-validity acceptance changes",
            "candidate order changes",
            "selected candidate changes",
            "winner metadata changes",
            "rank trace emission moves into Design Brain",
            "visible wording changes",
            "CTA/apply semantics change",
            "any composed lock fails",
        ],
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_candidate_selector_service_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_auto_design_candidate_selector_service_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    selector = payload["selector"]
    lines = [
        "# Auto-Design Candidate Selector Service Boundary Audit",
        "",
        "## Executive Summary",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "The shared selector is not safe to move as one piece. It still owns row-layout filtering, target-band scoring, winner-pool policy, goal tie-break ranking, and winner metadata mutation. Page-owned rank trace emission must remain shell-owned.",
        "",
        "## Selector",
        f"- File: `{selector['file']}`",
        f"- Function: `{selector['name']}`",
        f"- Lines: `{selector['line_start']}-{selector['line_end']}`",
        f"- Line count: `{selector['line_count']}`",
        f"- Callsites: `{payload['callsite_count']}`",
        "",
        "## Callsites",
    ]
    for callsite in payload["callsites"]:
        lines.append(f"- `inputs_page.py:{callsite['line']}` - `{callsite['text']}`")

    lines.extend(
        [
            "",
            "## Surface Inventory",
            "| Surface | Classification | Current owner | Target owner | Readiness | Risk |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for surface in payload["surfaces"]:
        lines.append(
            "| {surface} | {classification} | {current_owner} | {target_owner} | {readiness} | {risk} |".format(
                surface=surface["surface"],
                classification=surface["classification"],
                current_owner=surface["current_owner"],
                target_owner=surface["target_owner"],
                readiness=surface["deletion_readiness"],
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

    lines.extend(
        [
            "",
            "## Notes",
            "- No product behaviour was changed.",
            "- No selector policy was moved.",
            "- This audit exists to prevent replacing shared ranking with a callback-heavy pseudo-extraction.",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
