from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
SESSION_ROOT = ROOT / "inputs_page_modules" / "session"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


SESSION_TOKENS: tuple[str, ...] = (
    "st.session_state",
    "session_state",
    "seed_widget_from_shared",
    "hydrate_active_page_widgets_from_shared",
    "persist_state_snapshot",
    "get_sync_callbacks",
    "sync_callbacks",
    "_shared_state_snapshot",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _session_module_sources() -> tuple[str, str]:
    if not SESSION_ROOT.exists():
        return "", ""
    all_sources = "\n".join(_read(path) for path in sorted(SESSION_ROOT.glob("*.py")))
    executable_sources = "\n".join(
        _read(path)
        for path in sorted(SESSION_ROOT.glob("*.py"))
        if path.name != "contracts.py"
    )
    return all_sources, executable_sources


def _session_module_has_apply_routing(source: str) -> bool:
    """Detect executable Apply routing, not diagnostic or payload field text."""
    routing_patterns = (
        r"\bdef\s+(?:route|execute|dispatch|apply)_.*apply",
        r"\b(?:route|execute|dispatch)_apply\s*\(",
        r"\bapply_guidance_action\s*\(",
        r"\b_apply_resolved_candidate_payload\s*\(",
    )
    return any(re.search(pattern, source) for pattern in routing_patterns)


def _node_source(source: str, node: ast.AST) -> str:
    lines = source.splitlines()
    start = int(getattr(node, "lineno", 1))
    end = int(getattr(node, "end_lineno", start))
    return "\n".join(lines[start - 1 : end])


def _session_write_count(text: str) -> int:
    return len(re.findall(r"st\.session_state\[[^\]]+\]\s*=", text)) + len(
        re.findall(r"\.pop\(", text)
    ) + len(re.findall(r"\.setdefault\(", text))


def _session_read_count(text: str) -> int:
    return len(re.findall(r"st\.session_state\.get\(", text)) + len(
        re.findall(r"st\.session_state\[[^\]]+\]", text)
    )


def _classify_function(name: str, body: str) -> tuple[str, str, str]:
    name_l = name.lower()
    body_l = body.lower()
    if "snapshot" in name_l or "_shared_state_snapshot" in body:
        return (
            "snapshot_building",
            "inputs_page_modules.session",
            "read-only snapshot/source shaping candidate",
        )
    if any(token in name_l for token in ("hydrate", "seed", "reseed", "mirror")):
        return (
            "hydration",
            "inputs_page_modules.session",
            "state hydration/update API candidate",
        )
    if "sync" in name_l or "callback" in name_l:
        return (
            "callback_sync",
            "page shell",
            "callbacks stay page-owned; pure state-normalisation may move later",
        )
    if any(token in name_l for token in ("invalidate", "dirty", "cache", "settle_gate")) or any(
        token in body_l for token in ("needs_refresh", "cached_", ".pop(")
    ):
        return (
            "invalidation_cache",
            "inputs_page_modules.session or domain owner",
            "requires focused parity because stale-state behaviour is sensitive",
        )
    if any(token in name_l for token in ("apply", "pending", "route")):
        return (
            "apply_orchestration",
            "page shell",
            "apply/session orchestration remains page-owned unless a later slice proves a pure adapter",
        )
    if "design_guide" in name_l or "dg_" in name_l or "debug" in name_l or "trace" in name_l:
        return (
            "debug_trace_session",
            "page shell or debug/proof service",
            "non-authoritative trace/debug storage; extract only after consumer proof",
        )
    if "render" in name_l:
        return (
            "render_session_boundary",
            "page shell",
            "render/layout state stays page-owned",
        )
    if "auto_design" in name_l:
        return (
            "auto_design_session",
            "page shell or auto-design controller",
            "high-risk orchestration; audit separately before extraction",
        )
    return (
        "general_session_surface",
        "needs classification",
        "not ready to move without a focused boundary audit",
    )


def _scan_functions(source: str) -> list[dict[str, Any]]:
    tree = ast.parse(source)
    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = _node_source(source, node)
        if not any(token in body for token in SESSION_TOKENS):
            continue
        classification, target_owner, note = _classify_function(node.name, body)
        rows.append(
            {
                "function": node.name,
                "line_start": int(node.lineno),
                "line_end": int(getattr(node, "end_lineno", node.lineno)),
                "classification": classification,
                "target_owner": target_owner,
                "session_read_count": _session_read_count(body),
                "session_write_count": _session_write_count(body),
                "uses_shared_snapshot": "_shared_state_snapshot" in body,
                "uses_hydration_api": "hydrate_active_page_widgets_from_shared" in body
                or "seed_widget_from_shared" in body,
                "uses_sync_callbacks": "sync_callbacks" in body or "get_sync_callbacks" in body,
                "note": note,
            }
        )
    return sorted(rows, key=lambda row: (row["line_start"], row["function"]))


def _summary_by_classification(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        key = str(row.get("classification") or "unknown")
        summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session State Phase 0 Ownership Audit",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "Audit-only. No session behaviour, widget keys, callbacks, Streamlit rendering, Apply routing, engineering values, or visible wording changed.",
        "",
        "## Current State",
        "",
        f"- Session-touching functions found: `{payload['session_function_count']}`",
        f"- Total session reads in scanned functions: `{payload['total_session_reads']}`",
        f"- Total session writes/pops/defaults in scanned functions: `{payload['total_session_writes']}`",
        "",
        "## Classification Counts",
        "",
    ]
    for key, value in payload["classification_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            payload["first_safe_slice"],
            "",
            "## Stop Conditions",
            "",
        ]
    )
    for condition in payload["stop_conditions"]:
        lines.append(f"- {condition}")
    lines.extend(
        [
            "",
            "## Session Surface Inventory",
            "",
            "| Function | Lines | Classification | Target owner | Reads | Writes | Note |",
            "|---|---:|---|---|---:|---:|---|",
        ]
    )
    for row in payload["surfaces"]:
        lines.append(
            "| `{function}` | `{line_start}-{line_end}` | `{classification}` | `{target_owner}` | `{session_read_count}` | `{session_write_count}` | {note} |".format(
                **row
            )
        )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    session_module_source, session_module_executable_source = _session_module_sources()
    surfaces = _scan_functions(source)
    classification_counts = _summary_by_classification(surfaces)
    checks = {
        "inputs_page_present": INPUTS_PAGE.exists(),
        "session_surfaces_found": bool(surfaces),
        "snapshot_surfaces_found": classification_counts.get("snapshot_building", 0) > 0,
        "hydration_surfaces_found": classification_counts.get("hydration", 0) > 0,
        "callback_sync_surfaces_found": classification_counts.get("callback_sync", 0) > 0,
        "apply_orchestration_remains_page_shell": classification_counts.get("apply_orchestration", 0) > 0,
        "session_module_if_present_is_pure": "import streamlit" not in session_module_source
        and "from streamlit" not in session_module_source
        and "st.session_state" not in session_module_executable_source
        and ".session_state" not in session_module_executable_source
        and not _session_module_has_apply_routing(session_module_executable_source),
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "READY_FOR_SESSION_STATE_TYPED_MODELS" if not failures else "SESSION_STATE_OWNERSHIP_AUDIT_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_state_phase0_ownership_audit",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "session_function_count": len(surfaces),
        "total_session_reads": sum(int(row["session_read_count"]) for row in surfaces),
        "total_session_writes": sum(int(row["session_write_count"]) for row in surfaces),
        "classification_counts": classification_counts,
        "surfaces": surfaces,
        "first_safe_slice": (
            "Create `inputs_page_modules/session/` typed models for read-only source snapshots first. "
            "Start with pure snapshot/source shaping around `_inputs_audit_snapshot_state`, `_session_overlay_state`, "
            "`_summary_base_state`, and `_summary_state`; do not move hydration, callbacks, Apply routing, cache invalidation, "
            "or render-trigger writes until parity proves the snapshot boundary."
        ),
        "stop_conditions": (
            "Any widget key or session key changes.",
            "Any Streamlit import enters the new session module.",
            "Any Apply routing/click handling moves out of `inputs_page.py`.",
            "Any cache invalidation or stale-state behaviour changes without a focused verifier.",
            "Any summary/widget/Design Guide parity verifier fails.",
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_state_phase0_ownership_audit_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_state_phase0_ownership_audit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_state_phase0_ownership_audit", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
