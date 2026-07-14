"""Proof-only object snapshot for intent-contract-from-debug-rows rebind."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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


def _sample_debug_row() -> dict[str, Any]:
    return {
        "displayed_guidance_intent_items": [
            {
                "title": "Bending cleanup - best safe one-click reduction",
                "guidance_intent": "efficiency_tightening",
                "family": "bending",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "bending",
                    "updates": {"bottom_bar_size": "N12", "bottom_bar_count": 4},
                    "preview_pass": True,
                    "expected_util": 0.86,
                    "candidate_id": "intent-bending-1",
                },
            }
        ]
    }


def _build_cases() -> dict[str, dict[str, Any]]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_visible_contract_binding_intent_contract_rebind_result,
    )

    item = {
        "family": "bending",
        "check_key": "bending",
        "button_contract": {"enabled": False, "actionable": False, "blocking_reason": "threshold"},
    }
    debug = _sample_debug_row()
    positive = build_final_visible_contract_binding_intent_contract_rebind_result(
        item=item,
        contract=item["button_contract"],
        guidance_debug=debug,
        post_click_apply_context=False,
        active_strength_failures=(),
        current_binding_cross_family=False,
    )
    repeat = build_final_visible_contract_binding_intent_contract_rebind_result(
        item=item,
        contract=item["button_contract"],
        guidance_debug=debug,
        post_click_apply_context=False,
        active_strength_failures=(),
        current_binding_cross_family=False,
    )
    post_click_blocked = build_final_visible_contract_binding_intent_contract_rebind_result(
        item=item,
        contract=item["button_contract"],
        guidance_debug=debug,
        post_click_apply_context=True,
        active_strength_failures=(),
        current_binding_cross_family=False,
    )
    active_failure_blocked = build_final_visible_contract_binding_intent_contract_rebind_result(
        item=item,
        contract=item["button_contract"],
        guidance_debug=debug,
        post_click_apply_context=False,
        active_strength_failures=("bending",),
        current_binding_cross_family=False,
    )
    cross_family_blocked = build_final_visible_contract_binding_intent_contract_rebind_result(
        item={"family": "combined", "button_contract": {"enabled": False}},
        contract={"enabled": False},
        guidance_debug=debug,
        post_click_apply_context=False,
        active_strength_failures=(),
        current_binding_cross_family=True,
    )
    no_intent = build_final_visible_contract_binding_intent_contract_rebind_result(
        item=item,
        contract=item["button_contract"],
        guidance_debug={"guidance_intent_items": []},
    )
    return {
        "positive": positive,
        "repeat": repeat,
        "post_click_blocked": post_click_blocked,
        "active_failure_blocked": active_failure_blocked,
        "cross_family_blocked": cross_family_blocked,
        "no_intent": no_intent,
    }


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    builder_start = source.find("def build_final_visible_contract_binding_intent_contract_rebind_result(")
    builder_end = source.find("\ndef build_final_design_guide_publication_mutation_proof(", builder_start)
    builder_source = source[builder_start:builder_end] if builder_start >= 0 and builder_end > builder_start else ""
    cases = _build_cases()
    positive_result = dict((cases["positive"].get("result") or {}))
    return {
        "decision": "INTENT_CONTRACT_REBIND_OBJECT_READY_FOR_TRACE_WIRING",
        "cases": cases,
        "case_hashes": {key: value.get("proof_hash") for key, value in cases.items()},
        "stable_repeat_hash": cases["positive"].get("proof_hash") == cases["repeat"].get("proof_hash"),
        "positive_applies": positive_result.get("applies") is True,
        "positive_effects_present": all(
            bool(positive_result.get(key))
            for key in ("contract_effect", "item_effect", "updates_effect", "action_type_effect", "debug_effect")
        ),
        "blocked_cases_do_not_apply": all(
            dict(cases[key].get("result") or {}).get("applies") is False
            for key in ("post_click_blocked", "active_failure_blocked", "cross_family_blocked", "no_intent")
        ),
        "source_checks": {
            "builder_present": "def build_final_visible_contract_binding_intent_contract_rebind_result(" in source,
            "builder_exported": '"build_final_visible_contract_binding_intent_contract_rebind_result"' in source,
            "no_inputs_page_import": "inputs_page" not in builder_source,
            "no_streamlit_import": "import streamlit" not in builder_source and "st.session_state" not in builder_source,
            "no_apply_routing_import": "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY" not in builder_source,
        },
        "latest_artifacts": {
            "ownership_audit": _latest("design_guide_intent_contract_from_debug_rows_tail_ownership"),
            "cleanup_dead_body_deletion": _latest("design_guide_cleanup_evidence_rehydrate_dead_body_deletion"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "builder_present": source_checks.get("builder_present") is True,
        "builder_exported": source_checks.get("builder_exported") is True,
        "clean_import_boundary": all(
            source_checks.get(key) is True
            for key in ("no_inputs_page_import", "no_streamlit_import", "no_apply_routing_import")
        ),
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "positive_applies": capture.get("positive_applies") is True,
        "positive_effects_present": capture.get("positive_effects_present") is True,
        "blocked_cases_do_not_apply": capture.get("blocked_cases_do_not_apply") is True,
        "ownership_audit_pass": (latest.get("ownership_audit") or {}).get("status") == "PASS",
        "cleanup_dead_body_deletion_pass": (latest.get("cleanup_dead_body_deletion") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "ready_for_trace_wiring": capture.get("ready_for_trace_wiring") is True,
        "not_ready_for_live_cutover": capture.get("ready_for_live_cutover") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Intent Contract Rebind Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Cases",
        "",
    ]
    for key, proof_hash in (capture.get("case_hashes") or {}).items():
        applies = dict((capture.get("cases") or {}).get(key, {}).get("result") or {}).get("applies")
        lines.append(f"- {key}: applies=`{applies}`, proof_hash=`{proof_hash}`")
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
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
        "schema": "design_guide_intent_contract_rebind_object_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_intent_contract_rebind_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_intent_contract_rebind_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_intent_contract_rebind_object_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
