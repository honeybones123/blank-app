from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_runtime_trace_session_snapshot


INPUTS_PAGE = ROOT / "inputs_page.py"
SESSION_BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
SESSION_MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
SESSION_INIT = ROOT / "inputs_page_modules" / "session" / "__init__.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    window = source.split(marker, 1)[1].split("\ndef ", 1)[0]
    return window.split("\n", 1)[1] if "\n" in window else window


def _old_hash(value: object) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _old_item_summary(item: object) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"type": type(item).__name__}
    contract = dict(item.get("button_contract") or {})
    action_payload = dict(item.get("action_payload") or {})
    resolved_candidate = dict(item.get("resolved_candidate") or {})
    evidence = dict(
        item.get("candidate_search_evidence")
        or action_payload.get("candidate_search_evidence")
        or resolved_candidate.get("candidate_search_evidence")
        or {}
    )
    return {
        "type": "dict",
        "hash": _old_hash(item),
        "keys": sorted(str(k) for k in item.keys())[:40],
        "id": item.get("id") or item.get("candidate_id") or item.get("source_candidate_id"),
        "family": item.get("family") or item.get("check_key"),
        "selected_action_family": item.get("selected_action_family"),
        "status": item.get("status"),
        "terminal_status": item.get("terminal_status"),
        "guidance_intent": item.get("guidance_intent"),
        "action_type": item.get("action_type") or contract.get("action_type"),
        "cta_label": item.get("primary_action") or item.get("cta_label") or contract.get("label"),
        "button_contract_enabled": bool(contract.get("enabled") or contract.get("actionable")),
        "button_contract_reason": contract.get("disabled_reason") or contract.get("blocking_reason"),
        "button_contract_hash": _old_hash(contract) if contract else None,
        "updates_hash": _old_hash(item.get("updates") or contract.get("updates") or {}),
        "action_payload_hash": _old_hash(action_payload) if action_payload else None,
        "resolved_candidate_hash": _old_hash(resolved_candidate) if resolved_candidate else None,
        "candidate_search_evidence_hash": _old_hash(evidence) if evidence else None,
        "candidate_search_evidence_keys": sorted(str(k) for k in evidence.keys())[:40],
    }


def _old_compact(value: object, *, depth: int = 0) -> object:
    if depth > 1:
        return {"type": type(value).__name__, "hash": _old_hash(value)}
    if isinstance(value, dict):
        if any(k in value for k in ("button_contract", "action_payload", "resolved_candidate", "guidance_intent")):
            return _old_item_summary(value)
        return {
            "type": "dict",
            "hash": _old_hash(value),
            "keys": sorted(str(k) for k in value.keys())[:60],
            "family": value.get("family") or value.get("selected_family") or value.get("published_family"),
            "status": value.get("status") or value.get("terminal_status"),
            "render_reason": value.get("render_reason"),
            "action_type": value.get("action_type"),
            "enabled": value.get("enabled"),
            "actionable": value.get("actionable"),
            "blocking_reason": value.get("blocking_reason") or value.get("disabled_reason"),
            "item": _old_item_summary(value.get("item")) if isinstance(value.get("item"), dict) else None,
            "items_count": len(value.get("items") or value.get("guidance_items") or [])
            if isinstance(value.get("items") or value.get("guidance_items"), list)
            else None,
        }
    if isinstance(value, (list, tuple)):
        return {
            "type": type(value).__name__,
            "count": len(value),
            "hash": _old_hash(value),
            "items": [_old_compact(v, depth=depth + 1) for v in list(value)[:3]],
        }
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return {"type": type(value).__name__, "repr": repr(value)[:200]}


def _old_snapshot(entries: dict[Any, Any]) -> dict[str, Any]:
    interesting: dict[str, Any] = {}
    for key in list(entries.keys()):
        key_s = str(key)
        key_l = key_s.lower()
        if (
            "design_guide" not in key_l
            and "_dg_" not in key_l
            and "pending_recommendation" not in key_l
            and "auto_design" not in key_l
        ):
            continue
        interesting[key_s] = _old_compact(entries.get(key))
    return interesting


def _scenarios() -> list[dict[str, Any]]:
    item = {
        "id": "candidate-1",
        "family": "SHEAR_FAIL_GOVERNS",
        "status": "action",
        "guidance_intent": "repair",
        "button_contract": {"enabled": True, "label": "Apply", "updates": {"s_lig": 125}},
        "action_payload": {"candidate_search_evidence": {"route": "shear"}, "updates": {"s_lig": 125}},
        "resolved_candidate": {"candidate_search_evidence": {"route": "resolved"}},
    }
    return [
        {
            "name": "filters_only_trace_keys",
            "entries": {
                "irrelevant": {"ignored": True},
                "_dg_runtime_trace": {"state": "on"},
                "pending_recommendation_applied_id": "candidate-1",
                "auto_design_invoke_pending": True,
            },
        },
        {
            "name": "design_guide_item_shape",
            "entries": {
                "design_guide_item": item,
                "other": "ignored",
            },
        },
        {
            "name": "list_and_depth_shape",
            "entries": {
                "_dg_items": [item, {"nested": {"deeper": item}}, "plain", 4],
            },
        },
        {
            "name": "fallback_repr_shape",
            "entries": {
                "auto_design_object": object(),
                "plain": "ignored",
            },
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Runtime Trace Session Snapshot Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenarios'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- product behavior changed: `{payload['product_behavior_changed']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    helper = _function_window(source, "_dg_runtime_trace_session_snapshot")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_snapshot(row["entries"])
        new = build_inputs_design_guide_runtime_trace_session_snapshot(session_entries=row["entries"])
        match = old == dict(new.snapshot) and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": old,
                "new": dict(new.snapshot),
                "display_hash": new.display_hash,
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": old, "new": dict(new.snapshot)})

    checks = {
        "page_helper_delegates_to_session_builder": "build_inputs_design_guide_runtime_trace_session_snapshot(" in helper,
        "page_helper_keeps_session_source": "st.session_state" in helper,
        "old_filter_policy_removed_from_page_helper": '"design_guide"' not in helper
        and '"_dg_"' not in helper
        and '"pending_recommendation"' not in helper
        and '"auto_design"' not in helper,
        "old_compaction_removed_from_page_helper": "_dg_runtime_trace_compact_value(" not in helper,
        "session_builder_exists": "def build_inputs_design_guide_runtime_trace_session_snapshot(" in builders,
        "session_model_exists": "class InputsDesignGuideRuntimeTraceSessionSnapshot" in models,
        "session_init_exports_builder": "build_inputs_design_guide_runtime_trace_session_snapshot" in init_source,
        "session_init_exports_model": "InputsDesignGuideRuntimeTraceSessionSnapshot" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_RUNTIME_TRACE_SESSION_SNAPSHOT_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_RUNTIME_TRACE_SESSION_SNAPSHOT_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_runtime_trace_session_snapshot_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenarios": scenario_results,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "streamlit_reads_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_runtime_trace_session_snapshot_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_runtime_trace_session_snapshot_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        "inputs_session_design_guide_runtime_trace_session_snapshot_cutover",
        "PASS" if not failures else "FAIL",
    )
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
