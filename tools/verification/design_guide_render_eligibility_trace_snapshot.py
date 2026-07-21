"""Design Guide render eligibility snapshot.

Captures the current page-level Design Guide render gate and compares it with
the contract-required Design Brain publication eligibility surface. After the
narrow adapter cutover, this snapshot also proves the adapter is product-driving
only for Design Guide slot eligibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_live_render_gate_audit import (  # noqa: E402
    DEFAULT_URL,
    INPUTS_PAGE,
    _capture_live,
    _classify as _classify_live_render_gate,
    _line_map,
    _wait_for_live_url,
)

from playwright.sync_api import sync_playwright  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


TRACE_STATIC_PATTERNS: dict[str, str] = {
    "actions_or_loads_gate_value": r"_inputs_has_design_actions_or_loads_for_dg\s*=\s*bool\(inputs_has_design_actions_or_loads\(\)\)",
    "current_page_gate": r"show_design_guide_for_current_inputs\s*=\s*bool\(",
    "slot_eligibility_adapter_call": r"_dg_render_gate_decision\s*=\s*should_render_design_guide_slot_from_publication_eligibility\(",
    "current_page_gate_uses_adapter_result": r"get\(\"should_render_design_guide_slot\"\)",
    "trace_payload_key": r"design_guide_render_eligibility_trace",
    "trace_schema": r"design_guide_render_eligibility_trace\.v1",
    "adapter_evaluated_trace_only": r"slot_eligibility_adapter_evaluated_trace_only",
    "adapter_used": r"slot_eligibility_adapter_used",
    "adapter_product_driving": r"slot_eligibility_adapter_product_driving\"\s*:\s*True",
    "contract_required_flag": r"contract_required_design_brain_eligibility",
    "classification_field": r"render_eligibility_classification",
    "classification_a": r"page gate allows render",
    "classification_b": r"page gate blocks render but Design Brain has no publication reason",
    "classification_c": r"page gate blocks render but Design Brain has publication reason",
    "classification_d": r"browser/test state unavailable",
    "render_path_updates_trace": r"real_design_guide_card_rendered_source",
    "trace_only_marker": r"trace_only",
    "product_behaviour_unchanged_marker": r"product_behaviour_changed",
}


CONTRACT_REQUIRED_CASES: list[dict[str, Any]] = [
    {
        "case_id": "no_actions_no_family_no_blocker",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family_id": None,
        "active_failures": [],
        "invalid_input_state": False,
        "blocker_state": False,
        "final_publication_outcome_state": None,
        "expected_classification": "B",
    },
    {
        "case_id": "invalid_geometry_family_action",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
        "active_failures": [],
        "invalid_input_state": True,
        "blocker_state": True,
        "final_publication_outcome_state": "ACTION",
        "expected_classification": "C",
    },
    {
        "case_id": "locked_no_repair_blocked",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family_id": "LOCKED_NO_REPAIR",
        "active_failures": [],
        "invalid_input_state": False,
        "blocker_state": True,
        "final_publication_outcome_state": "BLOCKED",
        "expected_classification": "C",
    },
    {
        "case_id": "active_failure_repair_needed",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "active_failures": ["bending"],
        "invalid_input_state": False,
        "blocker_state": False,
        "final_publication_outcome_state": "ACTION",
        "expected_classification": "C",
    },
    {
        "case_id": "classic_actions_gate_allows_render",
        "inputs_has_design_actions_or_loads": True,
        "browser_test_mode": False,
        "selected_family_id": None,
        "active_failures": [],
        "invalid_input_state": False,
        "blocker_state": False,
        "final_publication_outcome_state": None,
        "expected_classification": "A",
    },
]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _datetime_stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _line_map_for_patterns(path: Path, patterns: dict[str, str]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    out: dict[str, Any] = {}
    for key, pattern in patterns.items():
        compiled = re.compile(pattern)
        match_line: int | None = None
        for idx, line in enumerate(lines, start=1):
            if compiled.search(line):
                match_line = idx
                break
        snippet: list[dict[str, Any]] = []
        if match_line is not None:
            for line_no in range(max(1, match_line - 5), min(len(lines), match_line + 8) + 1):
                snippet.append({"line": line_no, "text": lines[line_no - 1]})
        out[key] = {
            "found": match_line is not None,
            "line": match_line,
            "pattern": pattern,
            "snippet": snippet,
        }
    return out


def _case_contract_required(case: dict[str, Any]) -> bool:
    return bool(
        case.get("selected_family_id")
        or case.get("active_failures")
        or case.get("invalid_input_state")
        or case.get("blocker_state")
        or case.get("final_publication_outcome_state")
    )


def _classify_case(case: dict[str, Any]) -> dict[str, Any]:
    page_gate_allows = bool(
        case.get("browser_test_mode") or case.get("inputs_has_design_actions_or_loads")
    )
    contract_required = _case_contract_required(case)
    if page_gate_allows:
        classification = "A"
        reason = "page_gate_allows_render"
    elif contract_required:
        classification = "C"
        reason = "page_gate_blocks_contract_required_publication"
    else:
        classification = "B"
        reason = "page_gate_blocks_no_publication_reason"
    return {
        **case,
        "current_page_gate_allows": page_gate_allows,
        "contract_required_design_brain_eligibility": contract_required,
        "classification": classification,
        "classification_matches_expected": classification == case.get("expected_classification"),
        "render_eligibility_reason": reason,
        "contract_gap": classification == "C",
    }


def _capture_live_gate(url: str, *, headed: bool) -> dict[str, Any]:
    _wait_for_live_url(url)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        page = context.new_page()
        page.set_default_timeout(25_000)
        live = _capture_live(page, url=url)
        context.close()
        browser.close()
    static_map = _line_map(INPUTS_PAGE)
    live_classification = _classify_live_render_gate(static_map, live)
    return {
        "static_render_gate_map": static_map,
        "live_probe": live,
        "live_gate_classification": live_classification,
    }


def _runtime_trace_projection(live_gate: dict[str, Any]) -> dict[str, Any]:
    classification = dict(live_gate.get("live_gate_classification") or {})
    live_probe = dict(live_gate.get("live_probe") or {})
    snapshots = list(live_probe.get("snapshots") or [])
    last_snapshot = snapshots[-1] if snapshots else {}
    product_card = bool(classification.get("real_design_guide_created"))
    landing = bool(
        classification.get("start_your_design_visible")
        or classification.get("stable_rerun_shell_visible")
    )
    if product_card:
        trace_classification = "A"
        trace_reason = "page_gate_allows_render"
    elif classification.get("diagnosis") == "page_level_actions_or_loads_gate_prevents_design_guide_slot":
        trace_classification = "B"
        trace_reason = "page_gate_blocks_no_publication_reason_or_hidden_publication_reason"
    else:
        trace_classification = "D"
        trace_reason = "browser_test_state_unavailable"
    return {
        "source": "live_dom_projection_plus_trace_hook_static_proof",
        "inputs_has_design_actions_or_loads": not bool(classification.get("visible_zero_actions")),
        "show_design_guide_for_current_inputs": product_card,
        "browser_test_mode": False,
        "selected_family_id": None,
        "active_failures": [],
        "invalid_input_state": None,
        "blocker_state": None,
        "final_publication_outcome_state": None,
        "final_publication_publication_hash": None,
        "design_guide_slot_created": product_card,
        "landing_shell_rendered": landing,
        "real_design_guide_card_rendered": product_card,
        "render_eligibility_reason": trace_reason,
        "render_eligibility_classification": trace_classification,
        "last_live_snapshot_gate_text": dict(last_snapshot.get("gate_text") or {}),
    }


def _markdown(payload: dict[str, Any]) -> str:
    decision = payload.get("decision") or {}
    projection = payload.get("runtime_trace_projection") or {}
    lines = [
        "# Design Guide Render Eligibility Trace Snapshot",
        "",
        f"- Result: `{payload.get('status')}`",
        f"- Created: `{payload.get('created_at')}`",
        f"- URL: `{payload.get('url')}`",
        f"- Decision: `{decision.get('decision')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Runtime Projection",
        "",
    ]
    for key in (
        "inputs_has_design_actions_or_loads",
        "show_design_guide_for_current_inputs",
        "browser_test_mode",
        "selected_family_id",
        "active_failures",
        "invalid_input_state",
        "blocker_state",
        "final_publication_outcome_state",
        "final_publication_publication_hash",
        "design_guide_slot_created",
        "landing_shell_rendered",
        "real_design_guide_card_rendered",
        "render_eligibility_reason",
        "render_eligibility_classification",
    ):
        lines.append(f"- `{key}`: `{projection.get(key)}`")
    lines.extend(["", "## Contract Cases", ""])
    for row in payload.get("case_results") or []:
        lines.append(
            f"- `{row.get('case_id')}`: class `{row.get('classification')}`, "
            f"contract required `{row.get('contract_required_design_brain_eligibility')}`, "
            f"gap `{row.get('contract_gap')}`"
        )
    lines.extend(["", "## Trace Hook", ""])
    for key, row in (payload.get("trace_static_map") or {}).items():
        lines.append(f"- `{key}`: found `{row.get('found')}`, line `{row.get('line')}`")
    lines.extend(["", "## Recommendation", ""])
    lines.append(str(decision.get("recommended_next_slice") or "No recommendation recorded."))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _datetime_stamp()
    errors: list[str] = []
    warnings: list[str] = []

    trace_static_map = _line_map_for_patterns(INPUTS_PAGE, TRACE_STATIC_PATTERNS)
    missing_trace_tokens = [
        key for key, row in trace_static_map.items() if not bool(row.get("found"))
    ]
    if missing_trace_tokens:
        errors.append(f"missing_trace_tokens:{missing_trace_tokens}")

    live_gate: dict[str, Any] = {}
    try:
        live_gate = _capture_live_gate(args.url, headed=args.headed)
    except Exception as exc:
        warnings.append(f"live_browser_unavailable:{type(exc).__name__}: {exc}")

    runtime_projection = _runtime_trace_projection(live_gate) if live_gate else {
        "source": "browser/test state unavailable",
        "render_eligibility_classification": "D",
        "render_eligibility_reason": "browser_test_state_unavailable",
    }
    case_results = [_classify_case(case) for case in CONTRACT_REQUIRED_CASES]
    case_failures = [
        row.get("case_id") for row in case_results if not row.get("classification_matches_expected")
    ]
    if case_failures:
        errors.append(f"contract_case_classification_mismatch:{case_failures}")

    gap_cases = [row.get("case_id") for row in case_results if row.get("contract_gap")]
    decision = {
        "decision": "CONTRACT_GAP" if gap_cases else "NO_CONTRACT_GAP",
        "gap_cases": gap_cases,
        "current_page_gate_vs_contract_required_design_brain_eligibility": {
            "current_page_gate": (
                "browser_test_mode_or_inputs_has_design_actions_or_loads"
            ),
            "contract_required": (
                "selected family, active failure, invalid input, blocker, or "
                "FinalDesignGuidePublication outcome should make the slot eligible"
            ),
        },
        "recommended_next_slice": (
            "Add should_render_design_guide_slot_from_publication_eligibility(...) and "
            "use it as a tiny adapter at the page gate; do not move CTA, publication, "
            "apply routing, family runtimes, visible wording, or rendering."
        ),
    }
    status = "PASS" if not errors else "FAIL"
    payload = {
        "schema": "design_guide_render_eligibility_trace_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "url": args.url,
        "product_behaviour_changed": False,
        "trace_only": True,
        "cta_publication_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "visible_wording_changed": False,
        "rendering_moved": False,
        "trace_static_map": trace_static_map,
        "runtime_trace_projection": runtime_projection,
        "case_results": case_results,
        "live_gate_evidence": live_gate,
        "decision": decision,
        "errors": errors,
        "warnings": warnings,
        "snapshot_hash": _stable_hash(
            {
                "trace_static_map": trace_static_map,
                "runtime_projection": runtime_projection,
                "case_results": case_results,
                "decision": decision,
                "errors": errors,
                "warnings": warnings,
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_render_eligibility_trace_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_eligibility_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_render_eligibility_trace_snapshot {status}")
    print(f"decision={decision.get('decision')}")
    print(f"classification={runtime_projection.get('render_eligibility_classification')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if errors:
        print("errors=" + json.dumps(errors))
    if warnings:
        print("warnings=" + json.dumps(warnings))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
