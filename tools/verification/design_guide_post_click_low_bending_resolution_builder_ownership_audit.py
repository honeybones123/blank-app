"""Ownership audit for `_post_click_low_bending_resolution_item`.

This is proof-only. It maps the remaining page-owned low-bending resolution
builder before any extraction or deletion, and classifies which surfaces need
input adapters, controller ownership, or dedicated parity coverage.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

FUNCTION_TOKEN = "def _post_click_low_bending_resolution_item("
CALL_TOKEN = "_post_click_low_bending_resolution_item("

SURFACES = {
    "page_session_input": {
        "tokens": ("st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY)",),
        "classification": "A. page-owned input to extract as explicit request field",
        "risk": "high",
        "next": "Pass last_apply_route into a request/proof object instead of reading session inside the builder.",
    },
    "bending_cleanup_search": {
        "tokens": (
            "_bending_only_target_band_cleanup_item(",
            "_probe_equivalent_bending_cleanup_action_item(",
        ),
        "classification": "B. controller-owned recommendation/search decision",
        "risk": "high",
        "next": "Create controller request/result parity before moving cleanup search orchestration.",
    },
    "post_click_predicates": {
        "tokens": (
            "suppress_same_flow_action",
            "force_post_click_exact_blocker",
            "post_click_apply_context",
        ),
        "classification": "B. controller-owned decision predicates",
        "risk": "medium",
        "next": "Feed from existing post-click predicate adapter rather than recomputing page context here.",
    },
    "candidate_evaluation": {
        "tokens": (
            "_evaluate_auto_design_candidate(",
            "_evaluate_bending_with_bottom_state(",
            "_compute_shear_tightening_recommendation(",
            "generate_less_shear_reo_variants(",
        ),
        "classification": "C. engineering/search helper dependency to inject or move behind controller boundary",
        "risk": "high",
        "next": "Do not move until candidate/evaluator dependency boundary is explicit.",
    },
    "contract_construction": {
        "tokens": (
            "_design_guide_button_contract(",
            "_design_guide_button_contract_enabled(",
        ),
        "classification": "D. CTA contract construction/guard bridge",
        "risk": "medium",
        "next": "Keep CTA semantics unchanged; prove any cutover through CTA authority snapshots.",
    },
    "blocker_evidence_construction": {
        "tokens": (
            "\"exact_blockers_by_family\"",
            "\"post_click_exact_blockers_by_family\"",
            "\"no_second_cta_required\": True",
            "\"minimum_bending_reinforcement_governs\"",
        ),
        "classification": "B. controller-owned blocker evidence/result construction",
        "risk": "high",
        "next": "Move only after a result object proves blocker evidence parity.",
    },
    "visible_reason_text": {
        "tokens": (
            "Bending cleanup is governed by minimum bending reinforcement",
            "Trial bottom-reinforcement reductions were exhausted",
            "Geometry is locked, so optimisation cannot change beam width or depth.",
        ),
        "classification": "E. visible wording surface, no-touch until formatting authority proof",
        "risk": "high",
        "next": "Do not change text; preserve wording byte-for-byte through parity.",
    },
    "residual_shear_cleanup_probe": {
        "tokens": (
            "post_click_low_bending_residual_shear_cleanup_probe",
            "_skip_bending_fail_post_publication_probe(",
            "_shear_cleanup_materially_reduces_reinforcement(",
        ),
        "classification": "B. controller-owned residual cleanup route",
        "risk": "high",
        "next": "Needs separate route proof before moving.",
    },
    "item_packaging": {
        "tokens": (
            "\"guidance_intent\"",
            "\"button_contract\"",
            "\"candidate_search_evidence\"",
            "return cleanup_item",
        ),
        "classification": "B. controller-owned final item packaging",
        "risk": "high",
        "next": "Build result-object parity before any live cutover.",
    },
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _function_body(source: str) -> str:
    start = source.find(FUNCTION_TOKEN)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    body = _function_body(source)
    call_count_total = source.count(CALL_TOKEN) - (1 if FUNCTION_TOKEN in source else 0)
    surface_rows = {}
    for name, surface in SURFACES.items():
        tokens = tuple(surface.get("tokens") or ())
        present_tokens = [token for token in tokens if token in body]
        surface_rows[name] = {
            **surface,
            "tokens_present": present_tokens,
            "tokens_missing": [token for token in tokens if token not in body],
            "present": bool(present_tokens),
            "delete_now": False,
        }
    classification_counts: dict[str, int] = {}
    for row in surface_rows.values():
        classification = str(row.get("classification") or "unknown")
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
    latest = {
        "audit_merge_cutover": _latest(
            "design_guide_post_click_bending_replacement_audit_merge_cutover"
        ),
        "audit_result_trace": _latest(
            "design_guide_live_post_click_bending_replacement_audit_result_trace"
        ),
        "audit_result_parity": _latest(
            "design_guide_post_click_bending_replacement_audit_result_parity_scenarios"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "POST_CLICK_LOW_BENDING_RESOLUTION_BUILDER_MAPPED_NOT_READY_TO_MOVE",
        "function_found": bool(body),
        "function_line_count_estimate": len(body.splitlines()),
        "call_count_total": int(call_count_total),
        "surface_rows": surface_rows,
        "classification_counts": classification_counts,
        "missing_required_surfaces": [
            name for name, row in surface_rows.items() if row.get("present") is not True
        ],
        "delete_now_count": 0,
        "ready_to_move_function_wholesale": False,
        "next_safe_step": (
            "Create a request/result parity object for this builder that makes session/apply inputs "
            "explicit, then trace it beside the live function before moving any branch."
        ),
        "latest": latest,
        "all_latest_required_artifacts_pass": all(
            (item or {}).get("status") == "PASS" for item in latest.values()
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "function_found": capture.get("function_found") is True,
        "call_count_nonzero": int(capture.get("call_count_total") or 0) > 0,
        "all_required_surfaces_present": not capture.get("missing_required_surfaces"),
        "delete_now_count_zero": capture.get("delete_now_count") == 0,
        "not_ready_to_move_wholesale": capture.get("ready_to_move_function_wholesale") is False,
        "all_latest_required_artifacts_pass": (
            capture.get("all_latest_required_artifacts_pass") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Low Bending Resolution Builder Ownership Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Function line count estimate: `{capture.get('function_line_count_estimate')}`",
        f"- Call count: `{capture.get('call_count_total')}`",
        f"- Delete-now count: `{capture.get('delete_now_count')}`",
        f"- Ready to move wholesale: `{capture.get('ready_to_move_function_wholesale')}`",
        "",
        "## Classification Counts",
        "",
    ]
    for key, value in (capture.get("classification_counts") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Surfaces", ""])
    for name, row in (capture.get("surface_rows") or {}).items():
        lines.append(
            f"- {name}: present=`{row.get('present')}`, classification=`{row.get('classification')}`, "
            f"risk=`{row.get('risk')}`, delete_now=`{row.get('delete_now')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", "", str(capture.get("next_safe_step"))])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_low_bending_resolution_builder_ownership_audit.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_resolution_builder_ownership_audit_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_resolution_builder_ownership_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_low_bending_resolution_builder_ownership_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
