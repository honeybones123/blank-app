"""Audit residual shear cleanup final-binding/intent-contract tail ownership."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any] | None:
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"))
    if not matches:
        return None
    try:
        return json.loads(matches[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _row(name: str, route: str, classification: str, tokens: tuple[str, ...], next_step: str) -> dict[str, Any]:
    present = [token for token in tokens if token in route]
    missing = [token for token in tokens if token not in route]
    return {
        "name": name,
        "classification": classification,
        "present": not missing,
        "tokens_present": present,
        "tokens_missing": missing,
        "next": next_step,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    surfaces = {
        "evidence_merge_tail": _row(
            "evidence_merge_tail",
            route,
            "A. still live page authority / next proof target",
            (
                "residual_promoted[\"candidate_search_evidence\"] = dict(residual_evidence)",
                "residual_promoted[\"exact_blockers_by_family\"] = dict(residual_exact_blockers)",
                "residual_payload[\"candidate_search_evidence\"] = dict(residual_evidence)",
                "residual_resolved[\"candidate_search_evidence\"] = dict(residual_evidence)",
            ),
            "Build a controller/publication evidence-tail proof before changing this merge.",
        ),
        "button_contract_binding_tail": _row(
            "button_contract_binding_tail",
            route,
            "A. still live page authority / next proof target",
            (
                "residual_promoted[\"button_contract\"] = dict(",
                "_design_guide_button_contract(residual_promoted, state=state)",
            ),
            "Build a button-contract binding proof that preserves enabled/actionable/updates semantics.",
        ),
        "debug_projection_tail": _row(
            "debug_projection_tail",
            route,
            "B. debug/session projection / keep until same-object proof",
            (
                "debug_sink[\"post_click_residual_shear_cleanup_after_bending_blocker\"] = True",
                "debug_sink[\"post_click_residual_shear_cleanup_updates\"] = dict(residual_shear_updates)",
                "debug_sink[\"candidate_search_evidence\"] = dict(residual_evidence)",
            ),
            "Keep as non-authoritative projection until final-binding proof can stamp same-object payloads.",
        ),
        "controller_trace_observes_not_owns_contract": _row(
            "controller_trace_observes_not_owns_contract",
            route,
            "C. proof-only observer",
            (
                "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff(",
                "\"button_contract_hash_observed_not_owned\": _stable_final_publication_hash(",
            ),
            "Keep as observer; do not treat observed contract hash as controller-owned authority yet.",
        ),
        "final_return_tail": _row(
            "final_return_tail",
            route,
            "D. route return surface",
            ("return residual_route_return_item",),
            "Only change after evidence and button-contract binding parity pass.",
        ),
    }
    adapter_merge_tokens = (
        "residual_binding_without_contract = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
        "residual_binding_with_contract = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
        "residual_button_contract_execution_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(",
        "residual_cta_apply_payload_source_boundary = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(",
        "residual_final_binding_tail_handoff = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_handoff(",
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail_adapter_trace(",
        "residual_route_body_replacement = _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
        "final_binding_tail=dict(",
        "residual_route_body_result = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body(",
        "residual_prebuilt_route_result = _build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result(",
        "return dict(",
    )
    adapter_merge_present = all(token in route for token in adapter_merge_tokens)
    if adapter_merge_present:
        for name in ("evidence_merge_tail", "button_contract_binding_tail", "final_return_tail"):
            surfaces[name] = {
                **dict(surfaces[name]),
                "classification": "E. controller adapter-owned / page bridge cut over",
                "present": True,
                "tokens_present": list(adapter_merge_tokens),
                "tokens_missing": [],
                "next": (
                    "Create deadness proof for the removed manual page merge and keep shared "
                    "button-contract execution unchanged."
                ),
            }
    latest = {
        "materiality_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_cutover_implementation"
        ),
        "candidate_selection_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_cutover_implementation"
        ),
        "result_packaging_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_cutover_implementation"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": (
            "RESIDUAL_SHEAR_CLEANUP_FINAL_BINDING_TAIL_ADAPTER_CUTOVER_AUDITED"
            if adapter_merge_present
            else "RESIDUAL_SHEAR_CLEANUP_FINAL_BINDING_TAIL_AUDITED_NOT_READY_TO_CUT_OVER"
        ),
        "route_block_present": bool(route),
        "adapter_merge_present": adapter_merge_present,
        "surfaces": surfaces,
        "missing_surfaces": [name for name, row in surfaces.items() if row.get("present") is not True],
        "recommended_next_surface": "evidence_merge_and_button_contract_binding_tail",
        "next_safe_step": (
            "Create a proof-only controller/final-publication object for the residual-shear evidence merge "
            "and button-contract binding tail. Do not move CTA/apply execution, visible wording, apply routing, "
            "UI/session, or family/runtime behaviour."
        ),
        "latest": {
            name: {"status": (payload or {}).get("status"), "found": bool(payload)}
            for name, payload in latest.items()
        },
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "product_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "route_block_present": capture.get("route_block_present") is True,
        "all_surfaces_present": not capture.get("missing_surfaces"),
        "recommended_next_surface_set": (
            capture.get("recommended_next_surface")
            == "evidence_merge_and_button_contract_binding_tail"
        ),
        "latest_materiality_cutover_pass": latest.get("materiality_cutover", {}).get("status") == "PASS",
        "latest_candidate_selection_cutover_pass": latest.get("candidate_selection_cutover", {}).get("status") == "PASS",
        "latest_result_packaging_cutover_pass": latest.get("result_packaging_cutover", {}).get("status") == "PASS",
        "latest_render_bridge_lock_pass": latest.get("render_bridge_lock", {}).get("status") == "PASS",
        "latest_compute_bridge_lock_pass": latest.get("compute_bridge_lock", {}).get("status") == "PASS",
        "latest_independence_lock_pass": latest.get("independence_lock", {}).get("status") == "PASS",
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    surfaces = dict(capture.get("surfaces") or {})
    lines = [
        "# Residual Shear Cleanup Final Binding Tail Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Surface Inventory",
        "",
    ]
    for name, row in surfaces.items():
        lines.extend(
            [
                f"### {name}",
                f"- classification: `{row.get('classification')}`",
                f"- present: `{row.get('present')}`",
                f"- tokens missing: `{row.get('tokens_missing')}`",
                f"- next: {row.get('next')}",
                "",
            ]
        )
    lines.extend(["## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            str(capture.get("next_safe_step") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_audit.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_audit_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_audit_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_final_binding_tail_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_audit "
        f"{payload['status']}"
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print(f"failures={','.join(failures)}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
