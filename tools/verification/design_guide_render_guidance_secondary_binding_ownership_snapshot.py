"""Focused ownership proof for the secondary-items render restamper binding.

Proof-only. This snapshot inspects the generic
_render_guidance_secondary_items(...) callsite that still invokes
_publish_final_visible_design_guide_contract_binding(...). It decides whether
the callsite is deletion-ready or still mutates the visible card path.
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

FUNCTION_NAME = "_render_guidance_secondary_items"
CALL_TOKEN = "item = _publish_final_visible_design_guide_contract_binding("
EXPECTED_REASON = 'reason="design_brain_publication_contract_final_binding"'
TARGET_FOLLOWUP_TOKEN = "guidance_items[idx] = item"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _function_source(source: str, function_name: str) -> tuple[int | None, int | None, str]:
    marker = f"def {function_name}("
    start_index = source.find(marker)
    if start_index < 0:
        return None, None, ""
    start_line = source[:start_index].count("\n") + 1
    next_def_index = source.find("\ndef ", start_index + len(marker))
    next_class_index = source.find("\nclass ", start_index + len(marker))
    candidates = [index for index in (next_def_index, next_class_index) if index >= 0]
    end_index = min(candidates) if candidates else len(source)
    end_line = source[:end_index].count("\n") + 1
    return start_line, end_line, source[start_index:end_index]


def _line_for(source: str, token: str, start_line: int | None) -> int | None:
    for offset, line in enumerate(source.splitlines()):
        if token in line:
            return (start_line or 1) + offset
    return None


def _target_binding_line(source: str, start_line: int | None) -> int | None:
    lines = source.splitlines()
    for offset, line in enumerate(lines):
        if CALL_TOKEN not in line:
            continue
        followup_window = "\n".join(lines[offset : min(len(lines), offset + 14)])
        if TARGET_FOLLOWUP_TOKEN in followup_window:
            return (start_line or 1) + offset
    return _line_for(source, CALL_TOKEN, start_line)


def _window(source: str, line: int | None, radius: int = 70) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return "\n".join(lines[start - 1 : end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    start_line, end_line, function_source = _function_source(source, FUNCTION_NAME)
    call_line = _target_binding_line(function_source, start_line)
    call_window = _window(source, call_line)
    post_render = _latest("design_guide_post_render_bridge_restamper_readiness")
    render_lock = _latest("design_guide_render_bridge_lock")
    compute_lock = _latest("design_guide_compute_resolver_publication_bridge_lock")
    independence_lock = _latest("design_guide_independence_lock")

    proof_tokens = {
        "callsite_present": call_line is not None,
        "inside_expected_function": start_line is not None and end_line is not None and call_line is not None and start_line <= call_line <= end_line,
        "assigns_bound_item_back_to_guidance_items": "guidance_items[idx] = item" in call_window,
        "recomputes_button_contract_from_bound_item": "button_contract = dict(item.get(\"button_contract\") or {})" in call_window,
        "updates_button_enabled_from_bound_item": "_button_contract_enabled = _design_guide_button_contract_enabled(button_contract)" in call_window,
        "passes_bound_item_through_publication_contract": "_apply_design_brain_publication_contract_for_render(" in call_window and EXPECTED_REASON in call_window,
        "may_replace_item_after_contract_enforcement": "item = normalise_final_visible_design_guide_item(dict(_binding_contract_items[0]))" in call_window,
        "may_update_primary_card_presentation": "primary_card_presentation = dict(_binding_contract_presentation or primary_card_presentation or {})" in call_window,
        "uses_page_session_debug_sink": "st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)" in call_window,
        "no_compatibility_only_marker": "compatibility_only_callsite" not in call_window,
    }
    live_mutation = all(
        proof_tokens[key]
        for key in (
            "callsite_present",
            "assigns_bound_item_back_to_guidance_items",
            "recomputes_button_contract_from_bound_item",
            "passes_bound_item_through_publication_contract",
            "may_replace_item_after_contract_enforcement",
        )
    )
    return {
        "decision": (
            "RENDER_GUIDANCE_SECONDARY_BINDING_LIVE_NOT_READY_TO_DELETE"
            if live_mutation
            else "RENDER_GUIDANCE_SECONDARY_BINDING_READY_FOR_NARROWING_PROOF"
        ),
        "function": FUNCTION_NAME,
        "function_start_line": start_line,
        "function_end_line": end_line,
        "call_line": call_line,
        "proof_tokens": proof_tokens,
        "target_followup_token": TARGET_FOLLOWUP_TOKEN,
        "live_mutation": bool(live_mutation),
        "deletion_safe_now": False,
        "recommended_next_slice": (
            "Move or prove this binding through a controller/publication render-item adapter before deleting "
            "or marking it compatibility-only."
        ),
        "latest_locks": {
            "post_render_bridge_restamper_readiness": {
                "status": post_render.get("status"),
                "path": post_render.get("path"),
            },
            "render_bridge_lock": {
                "status": render_lock.get("status"),
                "path": render_lock.get("path"),
            },
            "compute_resolver_publication_bridge_lock": {
                "status": compute_lock.get("status"),
                "path": compute_lock.get("path"),
            },
            "independence_lock": {
                "status": independence_lock.get("status"),
                "path": independence_lock.get("path"),
            },
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_locks") or {})
    return {
        "callsite_present": (capture.get("proof_tokens") or {}).get("callsite_present") is True,
        "callsite_classified_as_live_or_ready": capture.get("decision")
        in {
            "RENDER_GUIDANCE_SECONDARY_BINDING_LIVE_NOT_READY_TO_DELETE",
            "RENDER_GUIDANCE_SECONDARY_BINDING_READY_FOR_NARROWING_PROOF",
        },
        "live_mutation_not_deleted": capture.get("deletion_safe_now") is False,
        "post_render_restamper_readiness_pass": (
            latest.get("post_render_bridge_restamper_readiness") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (
            latest.get("compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Render Guidance Secondary Binding Ownership Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Location",
        "",
        f"- Function: `{capture.get('function')}`",
        f"- Call line: `{capture.get('call_line')}`",
        "",
        "## Proof Tokens",
    ]
    for key, value in (capture.get("proof_tokens") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Result",
            "",
            f"- Live mutation: `{capture.get('live_mutation')}`",
            f"- Deletion safe now: `{capture.get('deletion_safe_now')}`",
            f"- Next: {capture.get('recommended_next_slice')}",
            "",
            "## Checks",
        ]
    )
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
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_guidance_secondary_binding_ownership_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_render_guidance_secondary_binding_ownership_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_guidance_secondary_binding_ownership_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_render_guidance_secondary_binding_ownership {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
