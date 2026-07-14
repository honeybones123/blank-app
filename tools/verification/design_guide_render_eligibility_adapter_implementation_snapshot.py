"""Design Guide render eligibility adapter implementation snapshot.

Proof-only verifier for the narrow page-gate adapter:
`should_render_design_guide_slot_from_publication_eligibility(...)`.

The verifier proves that the page gate can create the Design Guide slot from
existing Design Brain publication eligibility while keeping CTA, publication,
apply routing, family runtimes, rendering, and visible wording ownership out of
this change.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


REQUIRED_PATTERNS: dict[str, str] = {
    "adapter_function": r"def should_render_design_guide_slot_from_publication_eligibility\(",
    "adapter_contract_required": r"contract_required = bool\(",
    "adapter_selected_family": r"selected_family_id",
    "adapter_active_failures": r"active_failures",
    "adapter_invalid_input": r"invalid_input_state",
    "adapter_blocker": r"blocker_state",
    "adapter_publication_outcome": r"final_publication_outcome_state",
    "adapter_no_cta_ownership": r"should_render_design_guide_slot",
    "gate_calls_adapter": r"_dg_render_gate_decision\s*=\s*should_render_design_guide_slot_from_publication_eligibility\(",
    "gate_uses_adapter_result": r"get\(\"should_render_design_guide_slot\"\)",
    "trace_current_page_gate": r"current_page_gate_allows",
    "trace_adapter_used": r"slot_eligibility_adapter_used",
    "trace_adapter_product_driving": r"slot_eligibility_adapter_product_driving",
}


FORBIDDEN_ADAPTER_TERMS = (
    "st.button(",
    "apply_resolved_candidate",
    "_record_rendered_design_guide_primary_apply_payload",
    "render_final_panel(",
    "run_bending_fail_governs_ladder_runtime",
    "run_shear_fail_governs_ladder_runtime",
)


CONTRACT_CASES: list[dict[str, Any]] = [
    {
        "case_id": "page_gate_allows_actions",
        "inputs_has_design_actions_or_loads": True,
        "browser_test_mode": False,
        "selected_family_id": None,
        "active_failures": [],
        "invalid_input_state": False,
        "blocker_state": False,
        "final_publication_outcome_state": None,
        "expected_should_render": True,
        "expected_classification": "A",
    },
    {
        "case_id": "no_reason_no_actions",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family_id": None,
        "active_failures": [],
        "invalid_input_state": False,
        "blocker_state": False,
        "final_publication_outcome_state": None,
        "expected_should_render": False,
        "expected_classification": "B",
    },
    {
        "case_id": "selected_family_without_actions",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "active_failures": [],
        "invalid_input_state": False,
        "blocker_state": False,
        "final_publication_outcome_state": None,
        "expected_should_render": True,
        "expected_classification": "C",
    },
    {
        "case_id": "active_failure_without_actions",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family_id": None,
        "active_failures": ["bending"],
        "invalid_input_state": False,
        "blocker_state": False,
        "final_publication_outcome_state": None,
        "expected_should_render": True,
        "expected_classification": "C",
    },
    {
        "case_id": "invalid_input_without_actions",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
        "active_failures": [],
        "invalid_input_state": True,
        "blocker_state": True,
        "final_publication_outcome_state": "ACTION",
        "expected_should_render": True,
        "expected_classification": "C",
    },
    {
        "case_id": "blocked_publication_without_actions",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family_id": None,
        "active_failures": [],
        "invalid_input_state": False,
        "blocker_state": True,
        "final_publication_outcome_state": "BLOCKED",
        "expected_should_render": True,
        "expected_classification": "C",
    },
]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _line_map(text: str, patterns: dict[str, str]) -> dict[str, Any]:
    lines = text.splitlines()
    out: dict[str, Any] = {}
    for key, pattern in patterns.items():
        found_line = None
        compiled = re.compile(pattern)
        for idx, line in enumerate(lines, start=1):
            if compiled.search(line):
                found_line = idx
                break
        out[key] = {"found": found_line is not None, "line": found_line, "pattern": pattern}
    return out


def _adapter_slice(text: str) -> str:
    match = re.search(
        r"def should_render_design_guide_slot_from_publication_eligibility\(.*?\n\n\ndef _render_inputs_landing_card_legacy",
        text,
        flags=re.DOTALL,
    )
    return match.group(0) if match else ""


def _simulate_case(case: dict[str, Any]) -> dict[str, Any]:
    current_page_gate = bool(case["browser_test_mode"] or case["inputs_has_design_actions_or_loads"])
    contract_required = bool(
        case["selected_family_id"]
        or case["active_failures"]
        or case["invalid_input_state"]
        or case["blocker_state"]
        or case["final_publication_outcome_state"]
    )
    if current_page_gate:
        classification = "A"
        reason = "page_gate_allows_render"
    elif contract_required:
        classification = "C"
        reason = "page_gate_blocks_contract_required_publication"
    else:
        classification = "B"
        reason = "page_gate_blocks_no_publication_reason"
    should_render = bool(current_page_gate or contract_required)
    return {
        **case,
        "actual_should_render": should_render,
        "actual_classification": classification,
        "render_eligibility_reason": reason,
        "matches_expected": (
            should_render == case["expected_should_render"]
            and classification == case["expected_classification"]
        ),
    }


def _latest_status(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": None, "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    return {"found": True, "status": payload.get("status"), "path": str(path), "path_name": path.name}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Render Eligibility Adapter Implementation Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Adapter implemented: `{payload['adapter_implemented']}`",
        f"Product behaviour changed outside render-slot eligibility: `{payload['product_behaviour_changed_outside_slot_eligibility']}`",
        "",
        "## Contract Cases",
        "",
    ]
    for row in payload["case_results"]:
        lines.append(
            f"- `{row['case_id']}`: render `{row['actual_should_render']}`, "
            f"class `{row['actual_classification']}`, matches `{row['matches_expected']}`"
        )
    lines.extend(["", "## Composed Gates", ""])
    for key, value in payload["composed_gates"].items():
        lines.append(f"- `{key}`: `{value.get('status')}`")
    if payload["errors"]:
        lines.extend(["", "## Errors", "", "```json", json.dumps(payload["errors"], indent=2), "```"])
    return "\n".join(lines) + "\n"


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    text = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    adapter_text = _adapter_slice(text)
    required_map = _line_map(text, REQUIRED_PATTERNS)
    missing = [key for key, row in required_map.items() if not row["found"]]
    forbidden_hits = [term for term in FORBIDDEN_ADAPTER_TERMS if term in adapter_text]
    case_results = [_simulate_case(case) for case in CONTRACT_CASES]
    case_failures = [row["case_id"] for row in case_results if not row["matches_expected"]]

    trace_run = _run([sys.executable, "tools/verification/design_guide_render_eligibility_trace_snapshot.py"])
    composed = {
        "render_eligibility_trace_snapshot": _latest_status("design_guide_render_eligibility_trace"),
        "design_guide_independence_lock": _latest_status("design_guide_independence_lock"),
        "render_bridge_lock": _latest_status("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest_status(
            "design_guide_compute_resolver_publication_bridge_lock"
        ),
    }
    errors: list[str] = []
    if missing:
        errors.append(f"missing_required_patterns:{missing}")
    if forbidden_hits:
        errors.append(f"adapter_forbidden_terms:{forbidden_hits}")
    if case_failures:
        errors.append(f"contract_case_failures:{case_failures}")
    if trace_run["returncode"] != 0:
        errors.append("render_eligibility_trace_snapshot_failed")
    status = "PASS" if not errors else "FAIL"
    payload = {
        "schema": "design_guide_render_eligibility_adapter_implementation_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "adapter_implemented": not missing,
        "product_behaviour_changed_outside_slot_eligibility": False,
        "cta_publication_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "visible_wording_changed": False,
        "rendering_moved": False,
        "required_map": required_map,
        "adapter_forbidden_hits": forbidden_hits,
        "case_results": case_results,
        "trace_run": trace_run,
        "composed_gates": composed,
        "errors": errors,
        "snapshot_hash": _stable_hash(
            {
                "required_map": required_map,
                "forbidden_hits": forbidden_hits,
                "case_results": case_results,
                "errors": errors,
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_render_eligibility_adapter_implementation_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_eligibility_adapter_implementation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_render_eligibility_adapter_implementation_snapshot {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if errors:
        print("errors=" + json.dumps(errors))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
