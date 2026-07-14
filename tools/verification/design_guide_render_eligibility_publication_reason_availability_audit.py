"""Audit why render eligibility can lack Design Brain publication reason.

Audit-only. Proves whether the Design Guide slot eligibility adapter exists and
whether it receives selected-family/blocker/final-publication truth early
enough at the page gate.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

REQUIRED_ARTIFACTS = {
    "render_eligibility_adapter_implementation": (
        "design_guide_render_eligibility_adapter_implementation"
    ),
    "render_eligibility_trace": "design_guide_render_eligibility_trace",
    "rerun_render_cause_profile": "design_guide_rerun_render_cause_profile",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
}

ORDER_PATTERNS = {
    "debug_bundle_key": r"DESIGN_GUIDE_DEBUG_BUNDLE_KEY\s*=\s*",
    "slot_adapter_function": r"def should_render_design_guide_slot_from_publication_eligibility\(",
    "pre_slot_probe_function": r"def _design_guide_pre_slot_publication_eligibility_probe\(",
    "pre_slot_probe_call": r"_dg_pre_slot_publication_probe\s*=\s*_design_guide_pre_slot_publication_eligibility_probe\(",
    "slot_adapter_call": r"_dg_render_gate_decision\s*=\s*should_render_design_guide_slot_from_publication_eligibility\(",
    "slot_decision": r"show_design_guide_for_current_inputs\s*=\s*bool\(",
    "slot_created": r"design_guide_slot\s*=\s*st\.empty\(\)",
    "render_trace_written": r"_dg_render_gate_bundle\[\"design_guide_render_eligibility_trace\"\]",
    "pre_slot_probe_trace": r"\"pre_slot_publication_eligibility_probe\"",
    "summary_guidance_compute": r"summary_guidance_payload\s*=\s*_compute_design_guidance_items\(",
    "fresh_design_guide_skip_gate": r"if not show_design_guide_for_current_inputs or design_guide_slot is None:",
    "fresh_design_guide_render_panel": r"design_guide_page\.render_final_panel\(",
    "final_publication_verifier_payload_write": r"debug_sink\[\"final_publication_verifier_payload\"\]\s*=\s*dict\(payload\)",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def _first_line(source: str, pattern: str) -> int | None:
    compiled = re.compile(pattern)
    for line_no, line in enumerate(source.splitlines(), start=1):
        if compiled.search(line):
            return line_no
    return None


def _order_map(source: str) -> dict[str, dict[str, Any]]:
    return {
        name: {"line": _first_line(source, pattern), "pattern": pattern}
        for name, pattern in ORDER_PATTERNS.items()
    }


def _classify(order: dict[str, dict[str, Any]], artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    lines = {key: value.get("line") for key, value in order.items()}
    trace = dict(artifacts["render_eligibility_trace"].get("payload") or {})
    runtime = dict(trace.get("runtime_trace_projection") or {})
    cause = dict(artifacts["rerun_render_cause_profile"].get("payload") or {})
    cause_classification = dict(cause.get("classification") or {})

    adapter_before_slot = bool(
        lines.get("slot_adapter_call")
        and lines.get("slot_decision")
        and int(lines["slot_adapter_call"]) < int(lines["slot_decision"])
    )
    pre_slot_probe_before_adapter = bool(
        lines.get("pre_slot_probe_call")
        and lines.get("slot_adapter_call")
        and int(lines["pre_slot_probe_call"]) < int(lines["slot_adapter_call"])
    )
    pre_slot_probe_before_slot = bool(
        lines.get("pre_slot_probe_call")
        and lines.get("slot_decision")
        and int(lines["pre_slot_probe_call"]) < int(lines["slot_decision"])
    )
    summary_compute_after_slot_decision = bool(
        lines.get("summary_guidance_compute")
        and lines.get("slot_decision")
        and int(lines["summary_guidance_compute"]) > int(lines["slot_decision"])
    )
    skip_gate_after_slot_decision = bool(
        lines.get("fresh_design_guide_skip_gate")
        and lines.get("slot_decision")
        and int(lines["fresh_design_guide_skip_gate"]) > int(lines["slot_decision"])
    )
    final_publication_payload_written_before_gate = bool(
        lines.get("final_publication_verifier_payload_write")
        and lines.get("slot_decision")
        and int(lines["final_publication_verifier_payload_write"]) < int(lines["slot_decision"])
    )
    runtime_has_publication_reason = bool(
        runtime.get("selected_family_id")
        or runtime.get("active_failures")
        or runtime.get("invalid_input_state")
        or runtime.get("blocker_state")
        or runtime.get("final_publication_outcome_state")
        or runtime.get("final_publication_publication_hash")
    )

    if pre_slot_probe_before_adapter and pre_slot_probe_before_slot and adapter_before_slot:
        root = "PRE_SLOT_PUBLICATION_REASON_PROBE_BEFORE_SLOT_DECISION"
    elif not adapter_before_slot:
        root = "ADAPTER_NOT_BEFORE_SLOT_DECISION"
    elif runtime_has_publication_reason:
        root = "PUBLICATION_REASON_AVAILABLE_AT_GATE"
    elif summary_compute_after_slot_decision and skip_gate_after_slot_decision:
        root = "PUBLICATION_REASON_COMPUTED_AFTER_SLOT_DECISION"
    else:
        root = "PUBLICATION_REASON_NOT_AVAILABLE_AT_GATE"

    return {
        "root_cause": root,
        "adapter_before_slot_decision": adapter_before_slot,
        "pre_slot_probe_before_adapter": pre_slot_probe_before_adapter,
        "pre_slot_probe_before_slot_decision": pre_slot_probe_before_slot,
        "summary_compute_after_slot_decision": summary_compute_after_slot_decision,
        "fresh_panel_skip_gate_after_slot_decision": skip_gate_after_slot_decision,
        "final_publication_payload_written_before_gate": final_publication_payload_written_before_gate,
        "runtime_has_publication_reason_at_gate": runtime_has_publication_reason,
        "runtime_trace_classification": runtime.get("render_eligibility_classification"),
        "runtime_trace_reason": runtime.get("render_eligibility_reason"),
        "rerun_render_primary_cause": cause_classification.get("likely_primary_cause"),
        "smallest_next_slice": (
            "Add a pre-slot publication eligibility reason probe that is cheap and trace-only first, "
            "then allow the existing slot eligibility adapter to consume that probe. Do not move CTA, "
            "publication rendering, apply routing, family runtimes, formulas, or visible wording."
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Render Eligibility Publication Reason Availability Audit",
        "",
        f"- Status: `{payload['status']}`",
        f"- Root cause: `{payload['classification']['root_cause']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Classification",
        "",
        "```json",
        json.dumps(payload["classification"], indent=2, sort_keys=True),
        "```",
        "",
        "## Order Map",
        "",
        "| Marker | Line |",
        "|---|---:|",
    ]
    for key, row in payload["order_map"].items():
        lines.append(f"| `{_escape_md(key)}` | `{row.get('line')}` |")
    lines.extend(["", "## Supporting Artifacts", "", "| Artifact | Status | Path |", "|---|---|---|"])
    for key, row in payload["supporting_artifacts"].items():
        lines.append(f"| {_escape_md(key)} | {_escape_md(row.get('status'))} | {_escape_md(row.get('path'))} |")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Safe Slice", "", payload["classification"]["smallest_next_slice"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    order = _order_map(source)
    artifacts = {key: _latest(prefix) for key, prefix in REQUIRED_ARTIFACTS.items()}
    classification = _classify(order, artifacts)
    failures = [
        f"{key}_not_passed"
        for key, row in artifacts.items()
        if row.get("status") != "PASS"
    ]
    for key in ("slot_adapter_function", "slot_adapter_call", "slot_decision", "fresh_design_guide_skip_gate"):
        if order.get(key, {}).get("line") is None:
            failures.append(f"missing_order_marker::{key}")
    for key in ("pre_slot_probe_function", "pre_slot_probe_call", "pre_slot_probe_trace"):
        if order.get(key, {}).get("line") is None:
            failures.append(f"missing_pre_slot_probe_marker::{key}")
    if classification["root_cause"] == "ADAPTER_NOT_BEFORE_SLOT_DECISION":
        failures.append("adapter_not_before_slot_decision")

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "schema": "design_guide_render_eligibility_publication_reason_availability_audit.v1",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "classification": classification,
        "order_map": order,
        "supporting_artifacts": {
            key: {"found": row.get("found"), "status": row.get("status"), "path": row.get("path")}
            for key, row in artifacts.items()
        },
        "failures": failures,
        "snapshot_hash": _stable_hash(
            {
                "classification": classification,
                "order": order,
                "artifacts": {key: row.get("path") for key, row in artifacts.items()},
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_render_eligibility_publication_reason_availability_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_eligibility_publication_reason_availability_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_render_eligibility_publication_reason_availability_audit {payload['status']}")
    print(f"root_cause={classification['root_cause']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print(f"failures={json.dumps(failures, sort_keys=True)}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
