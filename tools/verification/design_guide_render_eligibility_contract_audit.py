"""Design Guide render eligibility contract audit.

Proof-only. Decides whether invalid-input / blocker / repair-needed states must
render the Design Guide even when inputs_has_design_actions_or_loads() is false.
It does not change product behaviour, family runtimes, contracts,
CTA/publication/apply semantics, visible wording, or final publication authority.
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


ELIGIBILITY_STATIC_PATTERNS: dict[str, str] = {
    "current_page_gate": r"show_design_guide_for_current_inputs\s*=\s*bool\(",
    "actions_loads_predicate": r"def inputs_has_design_actions_or_loads\(",
    "slot_creation_conditional": r"if show_design_guide_for_current_inputs:",
    "design_guide_slot_default_none": r"design_guide_slot\s*=\s*None",
    "fresh_panel_skip_if_no_slot": r"if not show_design_guide_for_current_inputs or design_guide_slot is None:",
    "real_design_guide_heading": r"st\.markdown\(\"### Design Guide\"\)",
}


CONTRACT_CASES: list[dict[str, Any]] = [
    {
        "case_id": "no_actions_no_family_no_blocker",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family": None,
        "active_failures": [],
        "invalid_input_or_blocker_state": False,
        "final_publication_outcome": None,
        "expected_render_eligible": False,
        "reason": "No actions, no family, no blocker, and no final publication means the landing shell can own the page.",
    },
    {
        "case_id": "invalid_geometry_family_action",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family": "GEOMETRY_DETAILING_GOVERNS",
        "active_failures": [],
        "invalid_input_or_blocker_state": True,
        "final_publication_outcome": "ACTION",
        "expected_render_eligible": True,
        "reason": "Invalid geometry is itself a Design Brain family state; the Design Guide must be able to propose the repair.",
    },
    {
        "case_id": "locked_no_repair_blocked",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family": "LOCKED_NO_REPAIR",
        "active_failures": [],
        "invalid_input_or_blocker_state": True,
        "final_publication_outcome": "BLOCKED",
        "expected_render_eligible": True,
        "reason": "A blocker publication is user-facing decision truth and must not be hidden by lack of load actions.",
    },
    {
        "case_id": "repair_needed_active_failure",
        "inputs_has_design_actions_or_loads": True,
        "browser_test_mode": False,
        "selected_family": "BENDING_FAIL_GOVERNS",
        "active_failures": ["bending"],
        "invalid_input_or_blocker_state": False,
        "final_publication_outcome": "ACTION",
        "expected_render_eligible": True,
        "reason": "Classic load-driven repair path remains eligible through the existing action/load predicate.",
    },
    {
        "case_id": "proof_pending_publication",
        "inputs_has_design_actions_or_loads": False,
        "browser_test_mode": False,
        "selected_family": "GEOMETRY_DETAILING_GOVERNS",
        "active_failures": [],
        "invalid_input_or_blocker_state": True,
        "final_publication_outcome": "PROOF_PENDING",
        "expected_render_eligible": True,
        "reason": "Proof-pending publication is still publication state and should render a non-authoritative/proof-pending card.",
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
        match_line = None
        compiled = re.compile(pattern)
        for idx, line in enumerate(lines, start=1):
            if compiled.search(line):
                match_line = idx
                break
        snippet = []
        if match_line is not None:
            for line_no in range(max(1, match_line - 4), min(len(lines), match_line + 7) + 1):
                snippet.append({"line": line_no, "text": lines[line_no - 1]})
        out[key] = {
            "found": match_line is not None,
            "line": match_line,
            "pattern": pattern,
            "snippet": snippet,
        }
    return out


def _evaluate_current_gate_for_case(case: dict[str, Any]) -> dict[str, Any]:
    current_gate = bool(case.get("browser_test_mode") or case.get("inputs_has_design_actions_or_loads"))
    expected = bool(case.get("expected_render_eligible"))
    return {
        "case_id": case.get("case_id"),
        "current_gate_show_design_guide_for_current_inputs": current_gate,
        "expected_contract_render_eligible": expected,
        "current_gate_matches_expected": current_gate == expected,
        "gap": bool(expected and not current_gate),
        "gap_reason": (
            "Current page gate only considers browser test mode or actions/loads; it does not consider "
            "selected family, invalid-input/blocker state, or FinalDesignGuidePublication outcome."
            if expected and not current_gate
            else None
        ),
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


def _current_live_fields(live_gate: dict[str, Any]) -> dict[str, Any]:
    classification = dict(live_gate.get("live_gate_classification") or {})
    live_probe = dict(live_gate.get("live_probe") or {})
    snapshots = list(live_probe.get("snapshots") or [])
    last_snapshot = snapshots[-1] if snapshots else {}
    # Direct session variables are not exposed in the browser DOM. These are
    # conservative inferences from the page-level gate and visible DOM state.
    inputs_has_actions = not bool(classification.get("visible_zero_actions"))
    browser_test_mode_effective = False
    if classification.get("real_design_guide_created"):
        show_dg = True
    elif classification.get("diagnosis") == "page_level_actions_or_loads_gate_prevents_design_guide_slot":
        show_dg = False
    else:
        show_dg = None
    return {
        "show_design_guide_for_current_inputs": {
            "value": show_dg,
            "source": "inferred_from_live_dom_and_static_gate",
        },
        "inputs_has_design_actions_or_loads": {
            "value": inputs_has_actions,
            "source": "inferred_from_visible_zero_actions_and_landing_shell",
        },
        "browser_test_mode_flag": {
            "value": browser_test_mode_effective,
            "source": "effective_inference; browser_recipe query alone did not create the Design Guide slot",
        },
        "selected_family": {
            "value": None,
            "source": "not_browser_exposed_because_final_publication_not_rendered",
        },
        "active_failures": {
            "value": [],
            "source": "not_browser_exposed_because_final_publication_not_rendered",
        },
        "invalid_input_blocker_state": {
            "value": None,
            "source": "not_browser_exposed_in_current_live_state; audited in contract cases",
        },
        "final_design_guide_publication_outcome": {
            "value": None,
            "source": "not_materialized_because_design_guide_slot_not_created",
        },
        "design_guide_slot_exists": {
            "value": bool(classification.get("real_design_guide_created")),
            "source": "inferred from absence/presence of product heading and card candidates",
        },
        "real_card_rendered": {
            "value": bool(classification.get("real_design_guide_created")),
            "source": "live DOM card/headings",
        },
        "landing_shell_rendered_instead": {
            "value": bool(classification.get("start_your_design_visible") or classification.get("stable_rerun_shell_visible")),
            "source": "live DOM gate text",
        },
        "last_live_snapshot_gate_text": dict(last_snapshot.get("gate_text") or {}),
    }


def _decision(case_results: list[dict[str, Any]], live_fields: dict[str, Any]) -> dict[str, Any]:
    gaps = [row for row in case_results if row.get("gap")]
    current_live_blocked_by_page_gate = bool(
        ((live_fields.get("show_design_guide_for_current_inputs") or {}).get("value") is False)
        and ((live_fields.get("landing_shell_rendered_instead") or {}).get("value") is True)
    )
    return {
        "decision": "CONTRACT_GAP" if gaps else "NO_CONTRACT_GAP",
        "expected_policy": (
            "Design Brain publication eligibility should not be blocked purely by the page-level "
            "actions/load gate once a selected family, blocker, invalid-input state, active failure, "
            "or FinalDesignGuidePublication outcome exists."
        ),
        "current_gate_blocks_live_slot": current_live_blocked_by_page_gate,
        "gap_case_count": len(gaps),
        "gap_cases": [row.get("case_id") for row in gaps],
        "recommended_next_slice": (
            "Add a trace-only render eligibility proof beside the page-level gate, then wire an eligibility "
            "adapter that allows invalid-input/blocker/family publication states to create the Design Guide slot "
            "without changing CTA/publication/apply semantics."
            if gaps
            else "No eligibility movement required."
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    decision = payload.get("decision") or {}
    live = payload.get("current_live_fields") or {}
    lines = [
        "# Design Guide Render Eligibility Contract Audit",
        "",
        f"- Result: `{payload.get('status')}`",
        f"- Created: `{payload.get('created_at')}`",
        f"- URL: `{payload.get('url')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Decision",
        "",
        f"- Decision: `{decision.get('decision')}`",
        f"- Expected policy: {decision.get('expected_policy')}",
        f"- Gap cases: `{decision.get('gap_cases')}`",
        f"- Current live slot blocked by page gate: `{decision.get('current_gate_blocks_live_slot')}`",
        "",
        "## Current Live Fields",
        "",
    ]
    for key in (
        "show_design_guide_for_current_inputs",
        "inputs_has_design_actions_or_loads",
        "browser_test_mode_flag",
        "selected_family",
        "active_failures",
        "invalid_input_blocker_state",
        "final_design_guide_publication_outcome",
        "design_guide_slot_exists",
        "real_card_rendered",
        "landing_shell_rendered_instead",
    ):
        row = live.get(key) or {}
        lines.append(f"- `{key}`: `{row.get('value')}` ({row.get('source')})")
    lines.extend(["", "## Eligibility Cases", ""])
    for row in payload.get("case_results") or []:
        lines.append(
            f"- `{row.get('case_id')}`: current gate `{row.get('current_gate_show_design_guide_for_current_inputs')}`, "
            f"expected `{row.get('expected_contract_render_eligible')}`, gap `{row.get('gap')}`"
        )
    lines.extend(["", "## Static Gate Map", ""])
    for key, row in (payload.get("static_eligibility_map") or {}).items():
        lines.append(f"- `{key}`: found `{row.get('found')}`, line `{row.get('line')}`")
    lines.extend(["", "## Next Slice", ""])
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
    live_gate: dict[str, Any] = {}
    try:
        live_gate = _capture_live_gate(args.url, headed=args.headed)
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")

    static_map = _line_map_for_patterns(INPUTS_PAGE, ELIGIBILITY_STATIC_PATTERNS)
    live_fields = _current_live_fields(live_gate) if live_gate else {}
    case_results = [_evaluate_current_gate_for_case(case) for case in CONTRACT_CASES]
    decision = _decision(case_results, live_fields)
    status = "PASS" if not errors else "FAIL"
    payload = {
        "schema": "design_guide_render_eligibility_contract_audit.v1",
        "status": status,
        "created_at": stamp,
        "url": args.url,
        "product_behaviour_changed": False,
        "family_runtimes_changed": False,
        "contracts_changed": False,
        "cta_publication_apply_semantics_changed": False,
        "visible_wording_changed": False,
        "final_publication_authority_changed": False,
        "static_eligibility_map": static_map,
        "current_live_fields": live_fields,
        "contract_cases": CONTRACT_CASES,
        "case_results": case_results,
        "live_gate_evidence": live_gate,
        "decision": decision,
        "errors": errors,
        "audit_hash": _stable_hash(
            {
                "static": static_map,
                "live_fields": live_fields,
                "case_results": case_results,
                "decision": decision,
                "errors": errors,
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_render_eligibility_contract_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_eligibility_contract_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_render_eligibility_contract_audit {status}")
    print(f"decision={decision.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if errors:
        print("errors=" + json.dumps(errors))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
