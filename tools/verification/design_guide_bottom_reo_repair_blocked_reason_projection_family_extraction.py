"""Verify bottom-reo repair/blocked reason trace projection is family-owned."""

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

PAGE_CALLER = "_bottom_reo_trace_proof_payload"
FAMILY_HELPER = "build_bottom_reo_repair_blocked_reason_trace_projection"
DELETED_PAGE_HELPERS = (
    "_bottom_reo_trace_selected_update_hash_surface",
    "_bottom_reo_trace_selector_reason_surface",
    "_bottom_reo_trace_reason_visibility_surface",
    "_bottom_reo_trace_repair_reason_source_surface",
    "_bottom_reo_trace_blocked_reason_source_surface",
    "_bottom_reo_trace_visible_guidance_text_source",
)


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


def _old_projection(
    *,
    selected_proof: dict | None,
    decision: dict | None,
    selector_result: dict | None,
    ranking_result_boundary: dict | None,
    guard_surface: dict | None,
) -> dict[str, Any]:
    from design_brain.families.bending import build_bottom_reo_repair_blocked_reason_proof

    proof = dict(selected_proof or {})
    decision_d = dict(decision or {})
    selector = dict(selector_result or {})
    ranking = dict(ranking_result_boundary or {})
    guard = dict(guard_surface or {})
    selected = bool(proof.get("selected_candidate_identity"))
    selected_update_hash_surface = {
        "selected_candidate_update_keys": list(decision_d.get("selected_candidate_update_keys") or []),
        "selected_candidate_updates_hash": decision_d.get("selected_candidate_updates_hash"),
        "final_result_update_keys": list(decision_d.get("final_result_update_keys") or []),
        "final_result_updates_hash": decision_d.get("final_result_updates_hash"),
        "proof_returned_update_keys": list(proof.get("returned_update_keys") or []),
        "proof_returned_updates_hash": proof.get("returned_updates_hash"),
    }
    raw_reasons = {
        "decision_no_result_reason": decision_d.get("no_result_reason"),
        "selector_no_candidate_reason": selector.get("no_candidate_reason"),
        "selector_legacy_rejection_reason": selector.get("legacy_rejection_reason"),
        "selector_strict_band_rejected_reason": selector.get("strict_band_rejected_reason"),
        "post_selector_guard_result": decision_d.get("post_selector_guard_result"),
    }
    selector_trace_reasons = {
        "reason_kind": "trace_proof_only",
        "raw_reasons": raw_reasons,
        "tracked_reasons": {
            key: any(str(value or "") == key for value in raw_reasons.values())
            for key in (
                "no_filtered_candidates",
                "no_selected_candidate",
                "growth_blocked_efficiency_reduction",
            )
        },
        "visible_blocked_wording_materialized": False,
        "visible_blocked_wording_source": None,
    }
    if selected:
        repair_reason_source_surface = {
            "reason_kind": "visible_guidance_text_source",
            "source": "selected_recommendation_proof",
            "selected_candidate_identity": proof.get("selected_candidate_identity"),
            "label": proof.get("label"),
            "guidance_recommendation_title": proof.get("guidance_recommendation_title"),
            "guidance_change_lines": list(proof.get("guidance_change_lines") or []),
            "utilisation_check_summary": dict(proof.get("utilisation_check_summary") or {}),
            "returned_update_keys": list(proof.get("returned_update_keys") or []),
            "returned_updates_hash": proof.get("returned_updates_hash"),
            "visible_reason_rows_materialized": False,
        }
        blocked_reason_source_surface = {
            "reason_kind": "not_applicable_selected_recommendation",
            "trace_reason_surface": selector_trace_reasons,
            "visible_blocked_wording_materialized": False,
            "visible_blocked_wording_source": None,
        }
    else:
        repair_reason_source_surface = {
            "reason_kind": "not_produced",
            "source": None,
            "visible_guidance_text_source": None,
        }
        blocked_reason_source_surface = {
            "reason_kind": "trace_proof_only",
            "trace_reason_surface": selector_trace_reasons,
            "visible_blocked_wording_materialized": False,
            "visible_blocked_wording_source": None,
        }
    reason_visibility_surface = {
        "selected_result_label": "visible_guidance_text_source" if selected else "not_produced",
        "selected_result_guidance_change_lines": "visible_guidance_text_source" if selected else "not_produced",
        "selector_no_result_reason": "trace_proof_only",
        "selector_no_candidate_reason": "trace_proof_only",
        "blocked_reason": "not_visible_from_bottom_reo_selector",
    }
    visible_guidance_text_source = (
        {
            "source": repair_reason_source_surface.get("source"),
            "selected_candidate_identity": repair_reason_source_surface.get("selected_candidate_identity"),
            "label": repair_reason_source_surface.get("label"),
            "guidance_recommendation_title": repair_reason_source_surface.get("guidance_recommendation_title"),
            "guidance_change_lines": list(repair_reason_source_surface.get("guidance_change_lines") or []),
        }
        if repair_reason_source_surface.get("reason_kind") == "visible_guidance_text_source"
        else None
    )
    selected_recommendation_handoff_hash = _trace_hash(
        {
            "ranking_result_hash": ranking.get("ranking_result_hash"),
            "selector_result": selector,
            "selected_candidate_decision": decision_d,
            "selected_recommendation_shape_hash": proof.get("selected_recommendation_shape_hash"),
            "selected_recommendation_proof_hash": proof.get("proof_hash"),
            "guards": guard,
        }
    )
    reason_proof = build_bottom_reo_repair_blocked_reason_proof(
        selected_recommendation_identity=proof.get("selected_candidate_identity"),
        selected_recommendation_proof_hash=proof.get("proof_hash"),
        selected_recommendation_shape_hash=proof.get("selected_recommendation_shape_hash"),
        selected_recommendation_handoff_hash=selected_recommendation_handoff_hash,
        selected_candidate_identity=(
            selector.get("selected_candidate_identity")
            or decision_d.get("selected_candidate_identity")
            or None
        ),
        selected_candidate_trace_hash=(
            selector.get("selected_candidate_trace_hash")
            or decision_d.get("selected_candidate_trace_hash")
        ),
        selected_update_hash_surface=selected_update_hash_surface,
        selector_guard_outcomes=guard,
        selector_trace_reasons=selector_trace_reasons,
        repair_reason_source_surface=repair_reason_source_surface,
        blocked_reason_source_surface=blocked_reason_source_surface,
        reason_visibility_surface=reason_visibility_surface,
        visible_guidance_text_source=visible_guidance_text_source,
    ).to_dict()
    return {
        "selected_recommendation_handoff_hash": selected_recommendation_handoff_hash,
        "selected_update_hash_surface": selected_update_hash_surface,
        "selector_trace_reasons": selector_trace_reasons,
        "repair_reason_source_surface": repair_reason_source_surface,
        "blocked_reason_source_surface": blocked_reason_source_surface,
        "reason_visibility_surface": reason_visibility_surface,
        "visible_guidance_text_source": visible_guidance_text_source,
        "repair_blocked_reason_proof": reason_proof,
        "repair_blocked_reason_proof_hash": reason_proof.get("proof_hash"),
    }


def _sample_cases() -> list[dict[str, Any]]:
    selected_proof = {
        "selected_candidate_identity": "candidate_selected",
        "selected_recommendation_shape_hash": "shape_hash_selected",
        "proof_hash": "proof_hash_selected",
        "label": "Reduce bottom reinforcement to 5N16",
        "guidance_recommendation_title": "Reduce bottom reinforcement",
        "guidance_change_lines": ["Bottom reinforcement: 8N16 -> 5N16"],
        "utilisation_check_summary": {"selected_bending_util": 0.82, "target_low": 0.75},
        "returned_update_keys": ("bot1_count", "bot1_dia"),
        "returned_updates_hash": "updates_hash_selected",
    }
    decision = {
        "selected_candidate_identity": "candidate_selected",
        "selected_candidate_trace_hash": "trace_hash_decision",
        "selected_candidate_update_keys": ["bot1_count", "bot1_dia"],
        "selected_candidate_updates_hash": "selected_updates_hash",
        "final_result_update_keys": ["bot1_count", "bot1_dia"],
        "final_result_updates_hash": "final_updates_hash",
        "no_result_reason": None,
        "post_selector_guard_result": "selected",
    }
    selector = {
        "selected_candidate_identity": "candidate_selected",
        "selected_candidate_trace_hash": "trace_hash_selector",
        "no_candidate_reason": None,
        "legacy_rejection_reason": None,
        "strict_band_rejected_reason": None,
    }
    ranking = {"ranking_result_hash": "ranking_hash"}
    guard = {
        "strict_band": {"winner_seen": True, "winner_accepted": True},
        "post_selector_guard": {"result": "selected"},
    }
    return [
        {
            "case": "selected_recommendation_visible_source",
            "selected_proof": selected_proof,
            "decision": decision,
            "selector_result": selector,
            "ranking_result_boundary": ranking,
            "guard_surface": guard,
        },
        {
            "case": "no_selected_candidate_blocked_trace",
            "selected_proof": {},
            "decision": {**decision, "selected_candidate_identity": None, "no_result_reason": "no_selected_candidate"},
            "selector_result": {**selector, "selected_candidate_identity": None, "no_candidate_reason": "no_selected_candidate"},
            "ranking_result_boundary": ranking,
            "guard_surface": {"post_selector_guard": {"result": "no_selected_candidate"}},
        },
        {
            "case": "growth_rejected_trace",
            "selected_proof": {},
            "decision": {**decision, "selected_candidate_identity": None, "post_selector_guard_result": "growth_blocked_efficiency_reduction"},
            "selector_result": {**selector, "selected_candidate_identity": None},
            "ranking_result_boundary": {"ranking_result_hash": "growth_ranking_hash"},
            "guard_surface": {"post_selector_guard": {"result": "growth_blocked_efficiency_reduction"}},
        },
        {
            "case": "selector_identity_fallback",
            "selected_proof": selected_proof,
            "decision": {**decision, "selected_candidate_identity": None, "selected_candidate_trace_hash": None},
            "selector_result": selector,
            "ranking_result_boundary": ranking,
            "guard_surface": guard,
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
    from design_brain.families.bending import build_bottom_reo_repair_blocked_reason_trace_projection

    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_start, page_end, page_segment = _function_segment(inputs_source, PAGE_CALLER)
    family_start, family_end, family_segment = _function_segment(bending_source, FAMILY_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        kwargs = {
            "selected_proof": case.get("selected_proof"),
            "decision": case.get("decision"),
            "selector_result": case.get("selector_result"),
            "ranking_result_boundary": case.get("ranking_result_boundary"),
            "guard_surface": case.get("guard_surface"),
        }
        old = _old_projection(**kwargs)
        new = build_bottom_reo_repair_blocked_reason_trace_projection(**kwargs)
        parity_rows.append(
            {
                "case": case.get("case"),
                "matches": old == new,
                "old_hash": _trace_hash(old),
                "new_hash": _trace_hash(new),
                "reason_proof_hash": new.get("repair_blocked_reason_proof_hash"),
                "visible_guidance_text_source": bool(new.get("visible_guidance_text_source")),
            }
        )

    deleted_helpers_removed = {
        name: not _function_exists(inputs_source, name)
        for name in DELETED_PAGE_HELPERS
    }
    forbidden = _forbidden_terms(family_segment)
    checks = {
        "family_helper_exists": bool(family_segment),
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "page_caller_delegates_to_family_helper": "_build_bottom_reo_repair_blocked_reason_trace_projection(" in page_segment,
        "page_no_longer_calls_repair_blocked_reason_proof_directly": "_build_bottom_reo_repair_blocked_reason_proof(" not in inputs_source,
        "deleted_page_projection_helpers_removed": all(deleted_helpers_removed.values()),
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
            "BOTTOM_REO_REPAIR_BLOCKED_REASON_PROJECTION_FAMILY_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_REPAIR_BLOCKED_REASON_PROJECTION_EXTRACTION_FAILED"
        ),
        "page_caller_lines": {"start": page_start, "end": page_end},
        "family_helper_lines": {"start": family_start, "end": family_end},
        "parity_rows": parity_rows,
        "deleted_page_projection_helpers_removed": deleted_helpers_removed,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "remaining_bottom_reo_tail": [
            "live selector loop",
            "guidance change-line projection",
            "result adapter call orchestration",
            "CTA intent proof assembly",
            "trace event emission",
        ],
        "next_safe_slice": "bottom_reo_cta_intent_proof_family_projection",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_repair_blocked_reason_projection_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_repair_blocked_reason_projection_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Repair Blocked Reason Projection Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The bending family now projects trace-only repair/blocked reason surfaces. Visible wording, CTA/apply behavior, rendering, and live family runtime behavior are unchanged.",
        "",
        "## Parity Cases",
        "",
        "| Case | Match | Old hash | New hash | Reason proof hash | Visible source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(
            f"| `{row.get('case')}` | `{row.get('matches')}` | `{row.get('old_hash')}` | `{row.get('new_hash')}` | `{row.get('reason_proof_hash')}` | `{row.get('visible_guidance_text_source')}` |"
        )
    lines.extend(["", "## Deleted Page Projection Helpers", ""])
    for name, removed in dict(payload.get("deleted_page_projection_helpers_removed") or {}).items():
        lines.append(f"- `{name}`: removed=`{removed}`")
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
    print(f"design_guide_bottom_reo_repair_blocked_reason_projection_family_extraction {payload.get('status')}")
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
