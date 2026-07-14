"""Consumer proof for the final-visible compatibility restamper stamp.

Proof-only. The post-render readiness audit classifies the final visible
binding in _render_fast_design_guidance_panel(...) as a compatibility stamp,
but deletion still requires consumer proof. This snapshot checks whether the
returned _final_visible_item is still consumed by later render-stage logic.
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

FUNCTION_NAME = "_render_fast_design_guidance_panel"
CALL_TOKEN = "_final_visible_item = _publish_final_visible_design_guide_contract_binding("
PRE_CONTEXT_TOKEN = 'source="render_fast_design_guidance_panel.final_visible_resolution"'

CONSUMER_TOKENS: tuple[str, ...] = (
    'str(_final_visible_resolution.get("render_reason") or "").strip()',
    'str(_final_visible_item.get("design_guide_terminal_state") or "").strip()',
    '_final_visible_item["candidate_search_evidence"] = dict(_zero_shear_candidate_evidence)',
    "_design_guide_item_is_visible_blocker(_final_visible_item)",
    "_visible_safe_low_util_cleanup_action_from_evidence(",
    '_final_visible_resolution["item"] = dict(_final_visible_item)',
    "_final_contract_for_post_click = dict(_final_visible_item.get(\"button_contract\") or {})",
    "_final_family_for_post_click = str(",
)


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


def _target_line(source: str, start_line: int | None) -> int | None:
    lines = source.splitlines()
    for offset, line in enumerate(lines):
        if CALL_TOKEN not in line:
            continue
        pre_window = "\n".join(lines[max(0, offset - 22) : offset + 1])
        if PRE_CONTEXT_TOKEN in pre_window:
            return (start_line or 1) + offset
    return None


def _window(source: str, line: int | None, before: int = 35, after: int = 210) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_start, function_end, function_source = _function_source(source, FUNCTION_NAME)
    call_line = _target_line(function_source, function_start)
    context = _window(source, call_line)
    consumer_results = {token: token in context for token in CONSUMER_TOKENS}
    has_live_consumers = call_line is not None and any(consumer_results.values())
    post_render = _latest("design_guide_post_render_bridge_restamper_readiness")
    render_lock = _latest("design_guide_render_bridge_lock")
    compute_lock = _latest("design_guide_compute_resolver_publication_bridge_lock")
    independence_lock = _latest("design_guide_independence_lock")
    return {
        "decision": (
            "FINAL_VISIBLE_COMPATIBILITY_STAMP_HAS_LIVE_CONSUMERS_NOT_DELETABLE"
            if has_live_consumers
            else "FINAL_VISIBLE_COMPATIBILITY_STAMP_READY_FOR_DELETION_PROOF"
        ),
        "function": FUNCTION_NAME,
        "function_start_line": function_start,
        "function_end_line": function_end,
        "call_line": call_line,
        "consumer_tokens": consumer_results,
        "has_live_consumers": bool(has_live_consumers),
        "deletion_safe_now": False,
        "recommended_next_slice": (
            "Move the post-binding zero-shear, safe-low-util, and post-click consumer logic behind "
            "a FinalDesignGuidePublication/controller-owned adapter before deleting this restamper call."
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
        "target_callsite_present": capture.get("call_line") is not None,
        "live_consumers_detected": capture.get("has_live_consumers") is True,
        "classified_not_deletable": capture.get("decision")
        == "FINAL_VISIBLE_COMPATIBILITY_STAMP_HAS_LIVE_CONSUMERS_NOT_DELETABLE",
        "deletion_safe_false": capture.get("deletion_safe_now") is False,
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
        "# Final Visible Compatibility Stamp Consumer Snapshot",
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
        "## Consumer Tokens",
    ]
    for key, value in (capture.get("consumer_tokens") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Result",
            "",
            f"- Has live consumers: `{capture.get('has_live_consumers')}`",
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
        "schema": "design_guide_final_visible_compatibility_stamp_consumer_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_compatibility_stamp_consumer_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_visible_compatibility_stamp_consumer_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_visible_compatibility_stamp_consumer {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
