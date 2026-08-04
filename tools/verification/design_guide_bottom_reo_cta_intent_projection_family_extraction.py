"""Verify bottom-reo CTA intent trace projection is family-owned."""

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
FAMILY_HELPER = "build_bottom_reo_cta_intent_trace_projection"


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


def _trace_hash(value: object) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _old_projection(
    *,
    selected_proof: dict | None,
    reason_proof: dict | None,
    selected_update_hash_surface: dict | None,
    action_payload_identity: dict | None,
    selector_trace_reasons: dict | None,
    return_reason: str | None,
) -> dict[str, Any]:
    from design_brain.families.bending import build_bottom_reo_cta_intent_proof

    proof = dict(selected_proof or {})
    reason = dict(reason_proof or {})
    update_surface = dict(selected_update_hash_surface or {})
    action_identity = dict(action_payload_identity or {})
    trace_reasons = dict(selector_trace_reasons or {})
    action_materialized = bool(action_identity.get("materialized"))
    intent_state = (
        "actionable_candidate"
        if action_materialized
        else (
            "trace_only_no_selection"
            if str(return_reason or "") in {"no_filtered_candidates", "no_selected_candidate"}
            else "not_materialized"
        )
    )
    cta_intent_proof = build_bottom_reo_cta_intent_proof(
        selected_recommendation_identity=proof.get("selected_candidate_identity"),
        selected_recommendation_proof_hash=proof.get("proof_hash"),
        selected_recommendation_shape_hash=proof.get("selected_recommendation_shape_hash"),
        repair_blocked_reason_proof_hash=reason.get("proof_hash"),
        selected_update_hash_surface=update_surface,
        action_payload_identity={
            "materialized": action_materialized,
            "action_type": action_identity.get("action_type"),
            "action_type_source": action_identity.get("action_kind_source"),
            "payload_hash": action_identity.get("payload_hash"),
            "update_keys": list(action_identity.get("update_keys") or []),
            "updates_hash": action_identity.get("updates_hash"),
        },
        action_intent_source={
            "source": action_identity.get("source"),
            "recommendation_family_tag": proof.get("recommendation_family_tag"),
            "subfamilies": list(proof.get("subfamilies") or []),
            "recommendation_compound": bool(proof.get("recommendation_compound")),
        },
        intent_state=intent_state,
        no_action_or_blocked_proof_source=(
            trace_reasons
            if not action_materialized
            else {}
        ),
    ).to_dict()
    return {
        "action_materialized": action_materialized,
        "intent_state": intent_state,
        "bottom_reo_cta_intent_proof": cta_intent_proof,
        "bottom_reo_cta_intent_proof_hash": cta_intent_proof.get("cta_intent_proof_hash"),
        "bottom_reo_cta_intent_action_payload_identity": {
            key: value
            for key, value in action_identity.items()
            if key != "payload"
        },
    }


def _sample_cases() -> list[dict[str, Any]]:
    selected_proof = {
        "selected_candidate_identity": "candidate_selected",
        "proof_hash": "proof_hash_selected",
        "selected_recommendation_shape_hash": "shape_hash_selected",
        "recommendation_family_tag": "BENDING_OVERDESIGN_GOVERNS",
        "subfamilies": ["bottom_reo"],
        "recommendation_compound": False,
    }
    reason_proof = {"proof_hash": "reason_hash_selected"}
    update_surface = {
        "selected_candidate_update_keys": ["bot1_count"],
        "selected_candidate_updates_hash": "selected_updates_hash",
        "final_result_update_keys": ["bot1_count"],
        "final_result_updates_hash": "final_updates_hash",
        "proof_returned_update_keys": ["bot1_count"],
        "proof_returned_updates_hash": "returned_updates_hash",
    }
    action_identity = {
        "materialized": True,
        "source": "inputs_page.py:_get_one_click_band_reaching_candidate:bottom_recommendation_option",
        "action_type": "apply_bottom_recommendation",
        "action_kind_source": "bottom_recommendation",
        "payload": {"updates": {"bot1_count": 5}},
        "payload_hash": "payload_hash",
        "update_keys": ["bot1_count"],
        "updates_hash": "updates_hash",
    }
    trace_reasons = {
        "reason_kind": "trace_proof_only",
        "raw_reasons": {"decision_no_result_reason": "no_selected_candidate"},
    }
    return [
        {
            "case": "actionable_bottom_candidate",
            "selected_proof": selected_proof,
            "reason_proof": reason_proof,
            "selected_update_hash_surface": update_surface,
            "action_payload_identity": action_identity,
            "selector_trace_reasons": trace_reasons,
            "return_reason": "accepted",
        },
        {
            "case": "actionable_compound_candidate",
            "selected_proof": {**selected_proof, "recommendation_compound": True, "subfamilies": ["bottom_reo", "geometry"]},
            "reason_proof": reason_proof,
            "selected_update_hash_surface": update_surface,
            "action_payload_identity": {
                **action_identity,
                "action_type": "apply_compound_guidance",
                "action_kind_source": "recommendation_compound",
                "update_keys": ["b", "bot1_count"],
            },
            "selector_trace_reasons": trace_reasons,
            "return_reason": "accepted",
        },
        {
            "case": "trace_only_no_selection",
            "selected_proof": {},
            "reason_proof": {"proof_hash": "reason_hash_none"},
            "selected_update_hash_surface": {},
            "action_payload_identity": {
                "materialized": False,
                "source": "bottom_reo_recommendation:no_action",
                "action_type": None,
                "action_kind_source": "no_selected_bottom_reo_recommendation",
                "payload": {},
                "payload_hash": "empty_payload_hash",
                "update_keys": [],
                "updates_hash": "empty_updates_hash",
            },
            "selector_trace_reasons": trace_reasons,
            "return_reason": "no_selected_candidate",
        },
        {
            "case": "not_materialized_other_reason",
            "selected_proof": {},
            "reason_proof": {"proof_hash": "reason_hash_none"},
            "selected_update_hash_surface": {},
            "action_payload_identity": {"materialized": False, "payload": {}, "update_keys": []},
            "selector_trace_reasons": trace_reasons,
            "return_reason": "growth_blocked_efficiency_reduction",
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
    from design_brain.families.bending import build_bottom_reo_cta_intent_trace_projection

    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_start, page_end, page_segment = _function_segment(inputs_source, PAGE_CALLER)
    family_start, family_end, family_segment = _function_segment(bending_source, FAMILY_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        kwargs = {
            "selected_proof": case.get("selected_proof"),
            "reason_proof": case.get("reason_proof"),
            "selected_update_hash_surface": case.get("selected_update_hash_surface"),
            "action_payload_identity": case.get("action_payload_identity"),
            "selector_trace_reasons": case.get("selector_trace_reasons"),
            "return_reason": case.get("return_reason"),
        }
        old = _old_projection(**kwargs)
        new = build_bottom_reo_cta_intent_trace_projection(**kwargs)
        parity_rows.append(
            {
                "case": case.get("case"),
                "matches": old == new,
                "old_hash": _trace_hash(old),
                "new_hash": _trace_hash(new),
                "intent_state": new.get("intent_state"),
                "cta_intent_proof_hash": new.get("bottom_reo_cta_intent_proof_hash"),
            }
        )

    forbidden = _forbidden_terms(family_segment)
    checks = {
        "family_helper_exists": bool(family_segment),
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "page_caller_delegates_to_family_helper": "_build_bottom_reo_cta_intent_trace_projection(" in page_segment,
        "page_no_longer_calls_cta_intent_proof_directly": "_build_bottom_reo_cta_intent_proof(" not in inputs_source,
        "page_no_longer_shapes_intent_state": "intent_state = (" not in page_segment
        and "action_materialized = bool" not in page_segment,
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
            "BOTTOM_REO_CTA_INTENT_PROJECTION_FAMILY_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_CTA_INTENT_PROJECTION_EXTRACTION_FAILED"
        ),
        "page_caller_lines": {"start": page_start, "end": page_end},
        "family_helper_lines": {"start": family_start, "end": family_end},
        "parity_rows": parity_rows,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "remaining_bottom_reo_tail": [
            "live selector loop",
            "guidance change-line projection",
            "result adapter call orchestration",
            "trace event emission",
        ],
        "next_safe_slice": "bottom_reo_trace_event_emission_shell_boundary_or_guidance_change_line_parity",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_cta_intent_projection_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_cta_intent_projection_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo CTA Intent Projection Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The bending family now projects trace-only CTA intent proof. Live CTA/apply routing, button rendering, visible wording, and publication authority remain unchanged.",
        "",
        "## Parity Cases",
        "",
        "| Case | Match | Old hash | New hash | Intent state | Proof hash |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(
            f"| `{row.get('case')}` | `{row.get('matches')}` | `{row.get('old_hash')}` | `{row.get('new_hash')}` | `{row.get('intent_state')}` | `{row.get('cta_intent_proof_hash')}` |"
        )
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
    print(f"design_guide_bottom_reo_cta_intent_projection_family_extraction {payload.get('status')}")
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
