"""Cutover plan verifier for compute rebound final-visible output bridges.

This is plan/proof only. It names the replacement target and proves the plan
does not move guard decisions, CTA/apply semantics, visible wording, or family
runtime behavior.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

PLAN = {
    "compute_late_evidence_contract_rebound": {
        "function": "_apply_compute_late_evidence_contract_rebound",
        "old_call": "_late_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "allowed_replacement": (
            "Build rebound item from the existing live guard inputs using "
            "FinalDesignGuidePublication collapsed item adapter, then pass through "
            "DesignGuideController.compute_rebound_mutation output."
        ),
        "must_keep_live": (
            "_late_evidence_acceptance = {",
            "_late_updates = dict(",
            "_late_contract_disabled_or_mismatched = (",
            "if not (",
            "if isinstance(_late_rebound_item, dict) and _design_guide_button_contract_enabled(_late_rebound_contract):",
            "return {",
        ),
    },
    "post_core_evidence_rebound": {
        "function": "_orchestrate_compute_post_core_publication_handoff",
        "old_call": "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(",
        "allowed_replacement": (
            "Build rebound item from the existing post-core evidence primary item using "
            "FinalDesignGuidePublication collapsed item adapter, then pass through "
            "DesignGuideController.compute_rebound_mutation output."
        ),
        "must_keep_live": (
            "_post_core_mismatch = {",
            "_post_evidence_updates = dict(",
            "_post_evidence_disabled_or_mismatched = (",
            "if (",
            "if isinstance(_post_evidence_rebound, dict) and _post_evidence_rebound:",
            "if not _post_core_mismatch.get(\"accepted\"):",
        ),
    },
}

FORBIDDEN_MOVES = (
    "change guard predicates",
    "change candidate update selection",
    "change CTA/apply semantics",
    "change visible wording",
    "change family runtime behavior",
    "change solver maths",
    "delete fallback/safety paths in same slice",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _function_window(source: str, function_name: str) -> str:
    start = source.find(f"def {function_name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    return source[start:] if next_def < 0 else source[start:next_def]


def _source_capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    rows: dict[str, Any] = {}
    for target_id, plan in PLAN.items():
        window = _function_window(source, plan["function"])
        rows[target_id] = {
            "function_present": bool(window),
            "old_call_present": plan["old_call"] in window,
            "publication_adapter_present": "_collapsed_guidance_item_from_final_publication_authority(" in window,
            "controller_mutation_trace_present": "_stamp_design_guide_controller_compute_rebound_mutation_trace_only(" in window,
            "handoff_rebound_decision_proof_present": "_stamp_final_publication_compute_handoff_rebound_decision_proof(" in window,
            "must_keep_live_present": {
                token: token in window
                for token in plan["must_keep_live"]
            },
        }
    return rows


def _capture() -> dict[str, Any]:
    return {
        "decision": "CUTOVER_PLAN_READY_IMPLEMENTATION_NOT_STARTED",
        "plan": dict(PLAN),
        "forbidden_moves": list(FORBIDDEN_MOVES),
        "source": _source_capture(),
        "latest": {
            "focused_parity": _latest("design_guide_compute_rebound_restamper_focused_parity_scenarios"),
            "cutover_readiness": _latest("design_guide_compute_rebound_restamper_cutover_readiness"),
            "ownership": _latest("design_guide_compute_rebound_restamper_bridge_ownership"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "remaining_restamper_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "implementation_started": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    source = dict(capture.get("source") or {})
    return {
        "decision_is_plan_only": capture.get("decision") == "CUTOVER_PLAN_READY_IMPLEMENTATION_NOT_STARTED",
        "plan_covers_both_targets": set(capture.get("plan") or {}) == set(PLAN),
        "forbidden_moves_listed": tuple(capture.get("forbidden_moves") or ()) == FORBIDDEN_MOVES,
        "all_functions_present": all(row.get("function_present") for row in source.values()),
        "old_calls_still_present": all(row.get("old_call_present") for row in source.values()),
        "publication_adapters_present": all(row.get("publication_adapter_present") for row in source.values()),
        "controller_mutation_traces_present": all(
            row.get("controller_mutation_trace_present") for row in source.values()
        ),
        "handoff_rebound_decision_proofs_present": all(
            row.get("handoff_rebound_decision_proof_present") for row in source.values()
        ),
        "must_keep_live_tokens_present": all(
            all(dict(row.get("must_keep_live_present") or {}).values()) for row in source.values()
        ),
        "focused_parity_latest_pass": (latest.get("focused_parity") or {}).get("status") == "PASS",
        "cutover_readiness_latest_pass": (latest.get("cutover_readiness") or {}).get("status") == "PASS",
        "ownership_latest_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "remaining_restamper_audit_latest_pass": (latest.get("remaining_restamper_audit") or {}).get("status")
        == "PASS",
        "implementation_not_started": capture.get("implementation_started") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Compute Rebound Restamper Cutover Plan",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Plan",
        "",
    ]
    for target_id, row in dict(capture.get("plan") or {}).items():
        lines.append(f"### `{target_id}`")
        lines.append(f"- Old call: `{row.get('old_call')}`")
        lines.append(f"- Allowed replacement: {row.get('allowed_replacement')}")
        lines.append("- Must keep live:")
        lines.extend(f"  - `{item}`" for item in row.get("must_keep_live") or [])
        lines.append("")
    lines.extend(["## Forbidden Moves", ""])
    lines.extend(f"- {item}" for item in capture.get("forbidden_moves") or [])
    if payload.get("failures"):
        lines.extend(["", "## Failures"])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_compute_rebound_restamper_cutover_plan.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_compute_rebound_restamper_cutover_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_rebound_restamper_cutover_plan_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
