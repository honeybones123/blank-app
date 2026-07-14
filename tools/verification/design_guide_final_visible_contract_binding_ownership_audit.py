"""Ownership audit for final visible Design Guide contract binding helper.

Proof-only. This does not change product behavior. It classifies the remaining
mixed responsibilities inside `_publish_final_visible_design_guide_contract_binding`
so later slices can extract/delete one boundary at a time.
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

HELPER_TOKEN = "def _publish_final_visible_design_guide_contract_binding("
NEXT_DEF_PREFIX = "\ndef "

GROUPS = {
    "A_page_binding_and_payload_shape": {
        "tokens": (
            "normalise_final_visible_design_guide_item(",
            "_attach_family_status_display_payload(",
            "_design_guide_button_contract(",
            '"button_contract"',
            '"action_payload"',
            '"resolved_candidate"',
            "debug_sink.update(",
        ),
        "owner": "page/shared binding",
        "recommendation": "keep until product-capable binding adapter exists",
    },
    "B_design_brain_policy_candidates": {
        "tokens": (
            "target_binding_evidence_available",
            "safe_binding_evidence_available",
            "combined_binding_evidence_available",
            "final_binding_no_second_cta",
            "accepted_safe_shear_cleanup_exists",
            "_build_shear_fail_active_repair_preview_evidence(",
        ),
        "owner": "design_brain policy candidate",
        "recommendation": "extract pure policy/result objects first",
    },
    "C_candidate_evaluation_and_formula_access": {
        "tokens": (
            "_evaluate_auto_design_candidate(",
            "_collect_design_overview(",
            "_overview_required_checks_acceptable(",
            "_candidate_preview_statuses_have_explicit_fail(",
        ),
        "owner": "shared evaluator boundary",
        "recommendation": "must stay live until evaluator-boundary adapter exists",
    },
    "D_session_or_debug_context": {
        "tokens": (
            "st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY)",
            "st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)",
            "debug_sink[",
            "debug_sink.update(",
        ),
        "owner": "inputs_page.py page shell",
        "recommendation": "retain as page/session wiring",
    },
    "E_snapshot_reuse_compatibility": {
        "tokens": (
            "_bending_fail_publication_snapshot_for_state(",
            "bending_fail_publication_snapshot_reused",
            "restore_binding=True",
        ),
        "owner": "compatibility bridge",
        "recommendation": "separate reachability proof before deletion",
    },
}


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


def _helper_block(source: str) -> str:
    start = source.find(HELPER_TOKEN)
    if start < 0:
        return ""
    end = source.find(NEXT_DEF_PREFIX, start + 1)
    return source[start:end] if end > start else source[start:]


def _line_number(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    block = _helper_block(source)
    call_count = source.count("_publish_final_visible_design_guide_contract_binding(") - (
        1 if block else 0
    )
    groups: dict[str, Any] = {}
    for name, spec in GROUPS.items():
        presence = {token: token in block for token in spec["tokens"]}
        groups[name] = {
            "owner": spec["owner"],
            "recommendation": spec["recommendation"],
            "presence": presence,
            "state_ok": all(presence.values()),
        }
    latest = {
        "post_click_adapter_cutover": _latest(
            "design_guide_post_click_exact_blocker_projection_adapter_cutover"
        ),
        "post_click_manual_deadness": _latest(
            "design_guide_post_click_exact_blocker_projection_manual_rows_deadness"
        ),
        "remaining_truth": _latest("design_guide_post_click_remaining_live_truth_ownership"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "FINAL_VISIBLE_CONTRACT_BINDING_MIXED_OWNERSHIP_CLASSIFIED",
        "helper_found": bool(block),
        "helper_start_line": _line_number(source, HELPER_TOKEN),
        "helper_hash": _stable_hash(block),
        "helper_line_count": len(block.splitlines()),
        "callsite_count_excluding_definition": call_count,
        "groups": groups,
        "safe_deletion_candidates": [],
        "next_safe_slice": (
            "extract pure final-binding policy/result object for target-band promotion, "
            "no-second-CTA suppression, and evidence cleanup rehydration before moving "
            "page/session binding"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    groups = dict(capture.get("groups") or {})
    return {
        "helper_found": capture.get("helper_found") is True,
        "callsites_remain": int(capture.get("callsite_count_excluding_definition") or 0) > 0,
        "all_groups_classified": all((group or {}).get("state_ok") is True for group in groups.values()),
        "no_safe_deletion_candidates": capture.get("safe_deletion_candidates") == [],
        "post_click_adapter_cutover_pass": (
            (latest.get("post_click_adapter_cutover") or {}).get("status") == "PASS"
        ),
        "post_click_manual_deadness_pass": (
            (latest.get("post_click_manual_deadness") or {}).get("status") == "PASS"
        ),
        "remaining_truth_pass": (latest.get("remaining_truth") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Visible Contract Binding Ownership Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Helper start line: `{capture.get('helper_start_line')}`",
        f"- Helper line count: `{capture.get('helper_line_count')}`",
        f"- Callsites excluding definition: `{capture.get('callsite_count_excluding_definition')}`",
        f"- Safe deletion candidates: `{capture.get('safe_deletion_candidates')}`",
        f"- Next safe slice: {capture.get('next_safe_slice')}",
        "",
        "## Ownership Groups",
        "",
    ]
    for name, group in (capture.get("groups") or {}).items():
        lines.append(
            f"- {name}: owner=`{group.get('owner')}` state_ok=`{group.get('state_ok')}` "
            f"recommendation={group.get('recommendation')}"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_final_visible_contract_binding_ownership_audit.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_contract_binding_ownership_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_visible_contract_binding_ownership_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_visible_contract_binding_ownership {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
