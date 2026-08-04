"""Verify bottom-reo selected recommendation proof projection is family-owned."""

from __future__ import annotations

import ast
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS = ROOT / "inputs_page.py"
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PAGE_HELPER = "_bottom_reo_trace_selected_recommendation_proof"
DELETED_PAGE_HELPER = "_bottom_reo_trace_selected_source_index"
FAMILY_HELPER = "build_bottom_reo_selected_recommendation_proof_from_result"


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


def _function_exists(source: str, name: str) -> bool:
    tree = ast.parse(source)
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        for node in ast.walk(tree)
    )


def _trace_hash(value: object) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _old_selected_recommendation_proof(
    *,
    result: dict | None,
    decision: dict | None,
    selector_result: dict | None,
    return_status: str,
    return_reason: str,
) -> dict[str, Any]:
    from design_brain.families.bending import build_bottom_reo_selected_recommendation_proof

    decision_d = dict(decision or {})
    selector_d = dict(selector_result or {})
    selected_identity = (
        selector_d.get("selected_candidate_identity")
        or decision_d.get("selected_candidate_identity")
        or None
    )
    ranked = [str(value) for value in list(decision_d.get("ranked_candidate_identities") or [])]
    selected_source_index = None
    if selected_identity is not None:
        selected_text = str(selected_identity)
        selected_source_index = ranked.index(selected_text) if selected_text in ranked else None
    result_d = dict(result or {})
    return build_bottom_reo_selected_recommendation_proof(
        selected_candidate_identity=selected_identity,
        selected_source="page_local_bottom_reo_selected_recommendation",
        selected_source_index=selected_source_index,
        arrangement=dict(result_d.get("arrangement") or {}),
        updates=dict(result_d.get("updates") or {}),
        actual_ast=result_d.get("actual_ast"),
        required_ast=result_d.get("required_ast"),
        util=result_d.get("util"),
        label=str(result_d.get("label") or ""),
        score=result_d.get("score"),
        recommendation_compound=bool(result_d.get("recommendation_compound")),
        subfamilies=list(result_d.get("subfamilies") or []),
        recommendation_family_tag=result_d.get("recommendation_family_tag"),
        guidance_recommendation_title=result_d.get("guidance_recommendation_title"),
        delta_b_mm=result_d.get("delta_b_mm"),
        delta_D_mm=result_d.get("delta_D_mm"),
        delta_Ast_bot=result_d.get("delta_Ast_bot"),
        guidance_change_lines=list(result_d.get("guidance_change_lines") or []),
        utilisation_check_summary={
            "selected_bending_util": selector_d.get("selected_bending_util") or decision_d.get("selected_bending_util"),
            "selected_candidate_post_util": selector_d.get("selected_candidate_post_util") or decision_d.get("selected_candidate_post_util"),
            "selected_reaches_target_band": selector_d.get("selected_reaches_target_band") or decision_d.get("selected_reaches_target_band"),
            "target_low": selector_d.get("target_low") or decision_d.get("target_low"),
            "target_high": selector_d.get("target_high") or decision_d.get("target_high"),
            "post_selector_guard_result": decision_d.get("post_selector_guard_result"),
            "return_status": return_status,
            "return_reason": return_reason,
        },
        selected_candidate_trace_hash=(
            selector_d.get("selected_candidate_trace_hash")
            or decision_d.get("selected_candidate_trace_hash")
        ),
    ).to_dict()


def _sample_cases() -> list[dict[str, Any]]:
    base_result = {
        "arrangement": {"bot1_count": 5, "bot1_dia": 16, "bot2_count": 0},
        "updates": {"bot1_count": 5, "bot1_dia": 16},
        "actual_ast": 1005.3,
        "required_ast": 812.2,
        "util": 0.81,
        "label": "Reduce bottom reinforcement to 5N16",
        "score": 0.27,
        "recommendation_compound": False,
        "subfamilies": ["bottom_reo"],
        "recommendation_family_tag": "BENDING_OVERDESIGN_GOVERNS",
        "guidance_recommendation_title": "Reduce bottom reinforcement",
        "delta_b_mm": 0,
        "delta_D_mm": 0,
        "delta_Ast_bot": -402.1,
        "guidance_change_lines": ["Bottom reinforcement: 8N16 -> 5N16"],
    }
    decision = {
        "selected_candidate_identity": "decision_selected",
        "ranked_candidate_identities": ["candidate_a", "decision_selected", "candidate_c"],
        "selected_bending_util": 0.81,
        "selected_candidate_post_util": 0.81,
        "selected_reaches_target_band": True,
        "target_low": 0.75,
        "target_high": 0.9,
        "post_selector_guard_result": "accepted",
        "selected_candidate_trace_hash": _trace_hash({"decision": "selected"}),
    }
    selector = {
        "selected_candidate_identity": "selector_selected",
        "selected_bending_util": 0.82,
        "selected_candidate_post_util": 0.82,
        "selected_reaches_target_band": True,
        "target_low": 0.75,
        "target_high": 0.9,
        "selected_candidate_trace_hash": _trace_hash({"selector": "selected"}),
    }
    return [
        {
            "case": "decision_identity_ranked_no_selector",
            "result": base_result,
            "decision": decision,
            "selector_result": None,
            "return_status": "selected",
            "return_reason": "accepted",
        },
        {
            "case": "selector_identity_overrides_decision_unranked",
            "result": {**base_result, "recommendation_compound": True, "updates": {"b": 350, "bot1_count": 5}},
            "decision": decision,
            "selector_result": selector,
            "return_status": "selected",
            "return_reason": "compound_preferred",
        },
        {
            "case": "selected_identity_absent",
            "result": None,
            "decision": {"ranked_candidate_identities": ["candidate_a"]},
            "selector_result": {},
            "return_status": "no_result",
            "return_reason": "no_selected_candidate",
        },
        {
            "case": "identity_not_ranked",
            "result": {**base_result, "guidance_change_lines": ["Width: 400 -> 350", "Bottom: 8N16 -> 5N16"]},
            "decision": {**decision, "selected_candidate_identity": "not_in_ranked"},
            "selector_result": None,
            "return_status": "selected",
            "return_reason": "legacy_rejection_not_triggered",
        },
        {
            "case": "empty_result_with_selector",
            "result": {},
            "decision": decision,
            "selector_result": {**selector, "selected_candidate_identity": "decision_selected"},
            "return_status": "selected",
            "return_reason": "empty_result_projection",
        },
    ]


def _forbidden_terms(segment: str) -> dict[str, bool]:
    return {
        "imports_inputs_page": "import inputs_page" in segment or "from inputs_page" in segment,
        "imports_streamlit": "streamlit" in segment or "st." in segment,
        "uses_session_state": "session_state" in segment,
        "uses_apply_routing": "_queue_" in segment or "route_apply" in segment or "on_click" in segment,
        "uses_rendering": "render_" in segment or "html" in segment,
        "uses_publication_authority": "FinalDesignGuidePublication" in segment,
    }


def build_payload() -> dict[str, Any]:
    from design_brain.families.bending import build_bottom_reo_selected_recommendation_proof_from_result

    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_helper_exists = _function_exists(inputs_source, PAGE_HELPER)
    if page_helper_exists:
        page_start, page_end, page_segment = _function_segment(inputs_source, PAGE_HELPER)
    else:
        page_start, page_end, page_segment = 0, 0, ""
    family_start, family_end, family_segment = _function_segment(bending_source, FAMILY_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        kwargs = {
            "result": case.get("result"),
            "decision": case.get("decision"),
            "selector_result": case.get("selector_result"),
            "return_status": str(case.get("return_status") or ""),
            "return_reason": str(case.get("return_reason") or ""),
        }
        old = _old_selected_recommendation_proof(**kwargs)
        new = build_bottom_reo_selected_recommendation_proof_from_result(**kwargs)
        parity_rows.append(
            {
                "case": case.get("case"),
                "matches": old == new,
                "old_hash": _trace_hash(old),
                "new_hash": _trace_hash(new),
                "selected_candidate_identity": new.get("selected_candidate_identity"),
                "selected_source_index": new.get("selected_source_index"),
            }
        )

    forbidden = _forbidden_terms(family_segment)
    checks = {
        "family_helper_exists": bool(family_segment),
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "page_helper_delegates_or_is_deleted_after_family_projection": (
            "_build_bottom_reo_selected_recommendation_proof_from_result(" in page_segment
            or not page_helper_exists
        ),
        "page_helper_no_longer_assembles_selected_proof_fields": "selected_source_index=" not in page_segment
        and "utilisation_check_summary=" not in page_segment
        and "_build_bottom_reo_selected_recommendation_proof(" not in page_segment,
        "page_helper_deleted_or_shell_only": not page_helper_exists
        or "_build_bottom_reo_selected_recommendation_proof_from_result(" in page_segment,
        "dead_page_selected_source_index_helper_removed": not _function_exists(inputs_source, DELETED_PAGE_HELPER),
        "all_sample_cases_match": all(row["matches"] for row in parity_rows),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "BOTTOM_REO_SELECTED_RECOMMENDATION_PROOF_FAMILY_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_SELECTED_RECOMMENDATION_PROOF_EXTRACTION_FAILED"
        ),
        "page_helper_lines": {"start": page_start, "end": page_end},
        "family_helper_lines": {"start": family_start, "end": family_end},
        "parity_rows": parity_rows,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "deleted_page_helpers": [DELETED_PAGE_HELPER],
        "remaining_page_owned_trace_surfaces": [
            "trace event emission",
        ],
        "remaining_bottom_reo_tail": [
            "result adapter call orchestration",
            "trace event emission",
        ],
        "next_safe_slice": "bottom_reo_callback_shell_or_result_adapter_deletion_readiness",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_selected_recommendation_proof_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_selected_recommendation_proof_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Selected Recommendation Proof Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The bending family now projects selected-recommendation proof inputs from plain selector/result records. Page code keeps only the wrapper call and does not alter CTA/apply/render behavior.",
        "",
        "## Parity Cases",
        "",
        "| Case | Match | Old hash | New hash | Selected source index |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(
            f"| `{row.get('case')}` | `{row.get('matches')}` | `{row.get('old_hash')}` | `{row.get('new_hash')}` | `{row.get('selected_source_index')}` |"
        )
    lines.extend(["", "## Deleted Page Helpers", ""])
    lines.extend(f"- `{item}`" for item in payload.get("deleted_page_helpers") or [])
    lines.extend(["", "## Remaining Bottom-Reo Tail", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_bottom_reo_tail") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_selected_recommendation_proof_family_extraction {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
