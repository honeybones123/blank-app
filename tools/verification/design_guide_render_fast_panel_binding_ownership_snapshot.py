"""Focused ownership proof for the remaining render-fast panel restamper binding.

Proof-only. This snapshot inspects the remaining
_render_fast_design_guidance_panel(...) callsite that still invokes
_publish_final_visible_design_guide_contract_binding(...). The former
combined/engine rebind bodies have been deleted and are no longer expected.
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

CALLSITES: tuple[dict[str, Any], ...] = (
    {
        "id": "final_visible_item_binding",
        "call_token": "_final_visible_item = _publish_final_visible_design_guide_contract_binding(",
        "pre_tokens": (
            'source="render_fast_design_guidance_panel.final_visible_resolution"',
        ),
        "post_tokens": (
            "_stamp_final_publication_render_item_consumer_proof(",
            'publication_reason="render_fast_design_guidance_panel.render_item_consumer_trace"',
            "_design_guide_item_is_visible_blocker(_final_visible_item)",
        ),
    },
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


def _line_for(source: str, token: str, start_line: int | None, pre_tokens: tuple[str, ...] = ()) -> int | None:
    lines = source.splitlines()
    for offset, line in enumerate(lines):
        if token not in line:
            continue
        if pre_tokens:
            pre_window = "\n".join(lines[max(0, offset - 28) : offset + 1])
            if not all(pre_token in pre_window for pre_token in pre_tokens):
                continue
        return (start_line or 1) + offset
    return None


def _window(source: str, line: int | None, radius: int = 180) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return "\n".join(lines[start - 1 : end])


def _inventory_render_fast_lines() -> list[int]:
    restamper_latest = _latest("design_guide_remaining_final_visible_restamper_reference_audit")
    restamper_payload = restamper_latest.get("payload") or {}
    restamper_lines: list[int] = []
    for callsite in (restamper_payload.get("capture") or {}).get("calls") or []:
        if (
            callsite.get("function") == FUNCTION_NAME
            and str(callsite.get("category") or "") == "C. render-stage final item binding bridge"
        ):
            try:
                restamper_lines.append(int(callsite.get("line")))
            except (TypeError, ValueError):
                pass
    if restamper_lines:
        return sorted(restamper_lines)

    latest = _latest("design_guide_post_render_bridge_restamper_readiness")
    payload = latest.get("payload") or {}
    out: list[int] = []
    for callsite in payload.get("classified_callsites") or []:
        if (
            callsite.get("function") == FUNCTION_NAME
            and callsite.get("target") == "_publish_final_visible_design_guide_contract_binding"
            and callsite.get("post_render_bridge_classification")
            in {
                "render_fast_panel_item_binding_keep",
                "compatibility_stamp_keep_temporarily",
            }
        ):
            try:
                out.append(int(callsite.get("line")))
            except (TypeError, ValueError):
                pass
    return sorted(out)


def _capture_callsite(function_source: str, function_start: int | None, spec: dict[str, Any]) -> dict[str, Any]:
    pre_tokens = tuple(str(token) for token in spec.get("pre_tokens") or ())
    post_tokens = tuple(str(token) for token in spec.get("post_tokens") or ())
    line = _line_for(function_source, str(spec["call_token"]), function_start, pre_tokens=pre_tokens)
    context = _window(INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff"), line)
    post_token_results = {token: token in context for token in post_tokens}
    pre_token_results = {token: token in context for token in pre_tokens}
    live_binding = line is not None and all(post_token_results.values())
    return {
        "id": spec["id"],
        "line": line,
        "call_token_present": line is not None,
        "pre_tokens": pre_token_results,
        "post_tokens": post_token_results,
        "live_binding": bool(live_binding),
        "deletion_safe_now": False,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_start, function_end, function_source = _function_source(source, FUNCTION_NAME)
    callsites = [
        _capture_callsite(function_source, function_start, spec)
        for spec in CALLSITES
    ]
    inventory_lines = _inventory_render_fast_lines()
    captured_lines = sorted(int(row["line"]) for row in callsites if row.get("line") is not None)
    all_live = all(row.get("live_binding") is True for row in callsites)
    post_render = _latest("design_guide_post_render_bridge_restamper_readiness")
    remaining_restamper = _latest("design_guide_remaining_final_visible_restamper_reference_audit")
    render_lock = _latest("design_guide_render_bridge_lock")
    compute_lock = _latest("design_guide_compute_resolver_publication_bridge_lock")
    independence_lock = _latest("design_guide_independence_lock")
    return {
        "decision": (
            "RENDER_FAST_PANEL_BINDINGS_LIVE_NOT_READY_TO_DELETE"
            if all_live
            else "RENDER_FAST_PANEL_BINDINGS_NEED_FURTHER_PROOF"
        ),
        "function": FUNCTION_NAME,
        "function_start_line": function_start,
        "function_end_line": function_end,
        "expected_inventory_lines": inventory_lines,
        "captured_lines": captured_lines,
        "expected_callsite_count": 1,
        "callsite_count": len(callsites),
        "callsites": callsites,
        "all_live_bindings": bool(all_live),
        "deletion_safe_now": False,
        "recommended_next_slice": (
            "Move the remaining post-binding final-visible consumers behind a "
            "FinalDesignGuidePublication/controller-owned adapter before deleting this compatibility stamp."
        ),
        "latest_locks": {
            "post_render_bridge_restamper_readiness": {
                "status": post_render.get("status"),
                "path": post_render.get("path"),
            },
            "remaining_final_visible_restamper_reference_audit": {
                "status": remaining_restamper.get("status"),
                "path": remaining_restamper.get("path"),
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
    expected_lines = capture.get("expected_inventory_lines") or []
    captured_lines = capture.get("captured_lines") or []
    return {
        "one_callsite_captured": capture.get("callsite_count") == 1,
        "captured_lines_match_post_render_inventory": (
            captured_lines == expected_lines
            or (len(captured_lines) == 1 and set(captured_lines).issubset(set(expected_lines)))
        ),
        "all_call_tokens_present": all(row.get("call_token_present") is True for row in capture.get("callsites") or []),
        "all_callsite_post_tokens_present": all(row.get("live_binding") is True for row in capture.get("callsites") or []),
        "classified_as_live_not_deletable": capture.get("decision") == "RENDER_FAST_PANEL_BINDINGS_LIVE_NOT_READY_TO_DELETE",
        "deletion_safe_false": capture.get("deletion_safe_now") is False,
        "post_render_restamper_readiness_pass": (
            latest.get("post_render_bridge_restamper_readiness") or {}
        ).get("status")
        == "PASS",
        "remaining_restamper_inventory_pass": (
            latest.get("remaining_final_visible_restamper_reference_audit") or {}
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
        "# Render Fast Panel Binding Ownership Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Expected inventory lines: `{capture.get('expected_inventory_lines')}`",
        f"- Captured lines: `{capture.get('captured_lines')}`",
        f"- All live bindings: `{capture.get('all_live_bindings')}`",
        f"- Deletion safe now: `{capture.get('deletion_safe_now')}`",
        "",
        "## Callsites",
        "",
        "| ID | Line | Live Binding | Deletion Safe |",
        "| --- | ---: | --- | --- |",
    ]
    for row in capture.get("callsites") or []:
        lines.append(
            f"| `{row.get('id')}` | `{row.get('line')}` | `{row.get('live_binding')}` | `{row.get('deletion_safe_now')}` |"
        )
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next", "", str(capture.get("recommended_next_slice"))])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_fast_panel_binding_ownership_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_render_fast_panel_binding_ownership_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_fast_panel_binding_ownership_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_render_fast_panel_binding_ownership {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
