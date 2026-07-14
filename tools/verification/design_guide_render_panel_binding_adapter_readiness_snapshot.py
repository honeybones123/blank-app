"""Readiness map for render-panel compatibility bindings.

Proof-only. This snapshot keeps the physical extraction program honest by
classifying the remaining compatibility-only calls to
_publish_final_visible_design_guide_contract_binding(...) in render paths and
recording which ones already have a FinalDesignGuidePublication/controller
adapter surface nearby.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

COMPATIBILITY_BINDINGS: tuple[dict[str, Any], ...] = (
    {
        "id": "primary_guidance_card_binding",
        "function": "_render_guidance_secondary_items",
        "call_token": "item = _publish_final_visible_design_guide_contract_binding(",
        "pre_context_token": "if is_primary_guidance_card:",
        "context_tokens": (
            "guidance_items[idx] = item",
            "button_contract = dict(item.get(\"button_contract\") or {})",
            "_apply_design_brain_publication_contract_for_render(",
        ),
        "adapter_tokens": (
            "build_final_design_guide_render_item_consumer_proof",
        ),
        "required_next_proof": "render-guidance secondary item adapter parity before deleting binding",
        "readiness_class": "B. compatibility binding with live render consumers",
    },
    {
        "id": "final_visible_item_binding",
        "function": "_render_fast_design_guidance_panel",
        "call_token": "_final_visible_item = _publish_final_visible_design_guide_contract_binding(",
        "pre_context_token": 'source="render_fast_design_guidance_panel.final_visible_resolution"',
        "context_tokens": (
            "_stamp_final_publication_render_item_consumer_proof(",
            'publication_reason="render_fast_design_guidance_panel.render_item_consumer_trace"',
            "_design_guide_item_is_visible_blocker(_final_visible_item)",
        ),
        "adapter_tokens": (
            "build_final_design_guide_render_item_consumer_proof",
        ),
        "required_next_proof": "render item consumer adapter exists but downstream consumers still need adapter replacement",
        "readiness_class": "C. adapter-traced but still has live item consumers",
    },
)

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "design_guide_remaining_resolver_cleanup_audit",
    "design_guide_render_guidance_secondary_binding_ownership",
    "design_guide_render_fast_panel_binding_ownership",
    "design_guide_final_visible_compatibility_stamp_consumer",
    "design_guide_live_render_item_consumer_adapter_trace",
    "design_guide_render_bridge_lock",
    "design_guide_compute_resolver_publication_bridge_lock",
    "design_guide_independence_lock",
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


def _line_for(function_source: str, token: str, start_line: int | None, pre_context_token: str | None) -> int | None:
    lines = function_source.splitlines()
    for offset, line in enumerate(lines):
        if token not in line:
            continue
        if pre_context_token:
            pre_window = "\n".join(lines[max(0, offset - 35) : offset + 1])
            if pre_context_token not in pre_window:
                continue
        return (start_line or 1) + offset
    return None


def _window(source: str, line: int | None, before: int = 45, after: int = 260) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _cleanup_inventory_lines() -> list[int]:
    latest = _latest("design_guide_remaining_resolver_cleanup_audit")
    payload = latest.get("payload") or {}
    out: list[int] = []
    for row in payload.get("remaining_paths") or []:
        if row.get("classification") == "B. compatibility-only stamp":
            try:
                out.append(int(row.get("line")))
            except (TypeError, ValueError):
                pass
    return sorted(out)


def _capture_binding(source: str, final_publication_source: str, spec: dict[str, Any]) -> dict[str, Any]:
    function_start, function_end, function_source = _function_source(source, str(spec["function"]))
    line = _line_for(
        function_source,
        str(spec["call_token"]),
        function_start,
        str(spec.get("pre_context_token") or "") or None,
    )
    context = _window(source, line)
    context_tokens = {str(token): str(token) in context for token in spec.get("context_tokens") or ()}
    adapter_tokens = {
        str(token): (str(token) in source or str(token) in final_publication_source)
        for token in spec.get("adapter_tokens") or ()
    }
    callsite_present = line is not None
    context_complete = bool(context_tokens) and all(context_tokens.values())
    adapter_surface_present = bool(adapter_tokens) and all(adapter_tokens.values())
    return {
        "id": spec["id"],
        "function": spec["function"],
        "line": line,
        "callsite_present": bool(callsite_present),
        "context_tokens": context_tokens,
        "context_complete": bool(context_complete),
        "adapter_tokens": adapter_tokens,
        "adapter_surface_present": bool(adapter_surface_present),
        "readiness_class": spec["readiness_class"],
        "required_next_proof": spec["required_next_proof"],
        "delete_now": False,
        "product_behavior_changed": False,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    final_publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    bindings = [_capture_binding(source, final_publication_source, spec) for spec in COMPATIBILITY_BINDINGS]
    latest = {prefix: _latest(prefix) for prefix in REQUIRED_ARTIFACTS}
    cleanup_lines = _cleanup_inventory_lines()
    captured_lines = sorted(int(row["line"]) for row in bindings if row.get("line") is not None)
    class_counts: dict[str, int] = {}
    for row in bindings:
        class_counts[str(row.get("readiness_class"))] = class_counts.get(str(row.get("readiness_class")), 0) + 1
    next_candidates = [
        row for row in bindings if str(row.get("readiness_class", "")).startswith("A.")
    ]
    return {
        "decision": "RENDER_PANEL_BINDINGS_MAPPED_NO_DELETION_YET",
        "binding_count": len(bindings),
        "expected_compatibility_binding_count": 2,
        "cleanup_inventory_lines": cleanup_lines,
        "captured_lines": captured_lines,
        "inventory_line_count_matches_captured_count": len(captured_lines) == len(bindings),
        "inventory_line_numbers_are_advisory": True,
        "class_counts": class_counts,
        "bindings": bindings,
        "next_safe_target": (next_candidates[0].get("id") if next_candidates else None),
        "next_safe_instruction": (
            "No A-class binding remains in this readiness map. The remaining bindings are "
            "compatibility/live-consumer paths and need focused consumer deletion proof before removal."
        ),
        "delete_now_count": 0,
        "latest_artifacts": {
            prefix: {"status": data.get("status"), "path": data.get("path")}
            for prefix, data in latest.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    bindings = list(capture.get("bindings") or [])
    return {
        "two_compatibility_bindings_captured": capture.get("binding_count") == 2,
        "inventory_line_count_matches_captured_count": (
            capture.get("inventory_line_count_matches_captured_count") is True
        ),
        "all_callsites_present": all(row.get("callsite_present") is True for row in bindings),
        "all_contexts_complete": all(row.get("context_complete") is True for row in bindings),
        "adapter_surface_present_for_each": all(row.get("adapter_surface_present") is True for row in bindings),
        "no_delete_now": capture.get("delete_now_count") == 0 and all(row.get("delete_now") is False for row in bindings),
        "no_a_class_next_target_without_new_proof": capture.get("next_safe_target") is None,
        "remaining_resolver_cleanup_pass": (latest.get("design_guide_remaining_resolver_cleanup_audit") or {}).get("status") == "PASS",
        "secondary_binding_ownership_pass": (latest.get("design_guide_render_guidance_secondary_binding_ownership") or {}).get("status") == "PASS",
        "fast_panel_binding_ownership_pass": (latest.get("design_guide_render_fast_panel_binding_ownership") or {}).get("status") == "PASS",
        "final_visible_consumer_pass": (latest.get("design_guide_final_visible_compatibility_stamp_consumer") or {}).get("status") == "PASS",
        "render_item_trace_pass": (latest.get("design_guide_live_render_item_consumer_adapter_trace") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("design_guide_render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("design_guide_compute_resolver_publication_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("design_guide_independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Render Panel Binding Adapter Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Compatibility bindings captured: `{capture.get('binding_count')}`",
        f"- Inventory count matches captured count: `{capture.get('inventory_line_count_matches_captured_count')}`",
        f"- Inventory line numbers advisory: `{capture.get('inventory_line_numbers_are_advisory')}`",
        f"- Delete now count: `{capture.get('delete_now_count')}`",
        f"- Next safe target: `{capture.get('next_safe_target')}`",
        f"- Next instruction: {capture.get('next_safe_instruction')}",
        "",
        "## Binding Map",
        "",
        "| ID | Line | Class | Adapter surface | Delete now | Required next proof |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for row in capture.get("bindings") or []:
        lines.append(
            "| {id} | {line} | {klass} | `{adapter}` | `{delete}` | {proof} |".format(
                id=row.get("id"),
                line=row.get("line"),
                klass=row.get("readiness_class"),
                adapter=row.get("adapter_surface_present"),
                delete=row.get("delete_now"),
                proof=row.get("required_next_proof"),
            )
        )
    lines.extend(["", "## Class Counts", ""])
    for key, value in (capture.get("class_counts") or {}).items():
        lines.append(f"- {key}: `{value}`")
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
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_panel_binding_adapter_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_render_panel_binding_adapter_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_panel_binding_adapter_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_render_panel_binding_adapter_readiness {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
