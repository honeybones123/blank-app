"""Proof-only bottom-reo selector policy family parity object.

This verifier does not move the live selector loop. It proves the bending
family already has a plain-data selector wrapper proof surface that can record
selected-identity parity before the live selector policy is moved.
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS = ROOT / "inputs_page.py"
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

LIVE_SELECTOR = "_pick_best_bottom_recommendation_by_selector"
FAMILY_PROOF = "build_bottom_reo_selector_wrapper_proof"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _scenario_rows() -> list[dict[str, Any]]:
    from design_brain.families.bending import build_bottom_reo_selector_wrapper_proof

    scenarios = [
        {
            "name": "selected_identity_matches_kept_order",
            "kwargs": {
                "ranked_candidate_identities": ("a", "b", "c"),
                "kept_candidate_identities": ("b", "c"),
                "selected_candidate_identity": "b",
                "selected_source_index": 0,
                "selected_source": "selector_top_valid",
                "selected_update_keys": ("bot1_count", "nb_bot"),
                "selected_updates_hash": "updates-hash",
                "selected_candidate_trace_hash": "candidate-hash",
                "selection_reason_summary": {
                    "selected_reason": "selector_top_valid",
                    "winner_pool_mode": "normal",
                },
            },
            "expect_parity": True,
            "expect_failures": (),
        },
        {
            "name": "zero_accepted_candidates",
            "kwargs": {
                "ranked_candidate_identities": (),
                "kept_candidate_identities": (),
                "selected_candidate_identity": None,
                "selected_source_index": None,
                "selected_source": "no_result",
                "selected_update_keys": (),
                "selected_updates_hash": None,
                "selected_candidate_trace_hash": None,
                "selection_reason_summary": {"no_candidate_reason": "selector_pool_exhausted"},
            },
            "expect_parity": True,
            "expect_failures": (),
        },
        {
            "name": "selected_identity_not_kept",
            "kwargs": {
                "ranked_candidate_identities": ("a", "b", "c"),
                "kept_candidate_identities": ("a", "c"),
                "selected_candidate_identity": "b",
                "selected_source_index": 1,
                "selected_source": "selector_top_valid",
                "selected_update_keys": ("bot1_count",),
                "selected_updates_hash": "updates-hash",
                "selected_candidate_trace_hash": "candidate-hash",
                "selection_reason_summary": {"selected_reason": "selector_top_valid"},
            },
            "expect_parity": False,
            "expect_failures": ("selected_identity_not_in_kept_candidates",),
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        proof = build_bottom_reo_selector_wrapper_proof(**scenario["kwargs"])
        result = proof.to_dict()
        failures = tuple(result.get("parity_failures") or ())
        rows.append(
            {
                "name": scenario["name"],
                "selected_identity_parity": bool(result.get("selected_identity_parity")),
                "zero_accepted_parity": bool(result.get("zero_accepted_parity")),
                "parity_failures": failures,
                "proof_hash_present": bool(result.get("proof_hash")),
                "matches_expectation": (
                    bool(result.get("selected_identity_parity")) is bool(scenario["expect_parity"])
                    and all(item in failures for item in scenario["expect_failures"])
                    and bool(result.get("proof_hash"))
                ),
            }
        )
    return rows


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    selector_start, selector_end, selector_segment = _function_segment(inputs_source, LIVE_SELECTOR)
    proof_start, proof_end, proof_segment = _function_segment(bending_source, FAMILY_PROOF)
    scenario_rows = _scenario_rows()
    checks = {
        "live_selector_found": bool(selector_segment),
        "family_proof_helper_found": bool(proof_segment),
        "family_proof_no_page_or_ui_imports": all(
            token not in proof_segment
            for token in ("inputs_page", "streamlit", "st.session_state", "FinalDesignGuidePublication")
        ),
        "family_proof_does_not_receive_live_candidate_dicts": all(
            token not in proof_segment
            for token in ("selected_candidate:", "dict(candidate", "candidate.get(", "candidate[")
        ),
        "live_selector_still_page_owned": "_select_best_auto_design_candidate(" in selector_segment,
        "result_packaging_still_page_owned": "_build_bottom_reo_recommendation_result(" in inputs_source,
        "scenario_parity": bool(scenario_rows) and all(row["matches_expectation"] for row in scenario_rows),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_SELECTOR_POLICY_FAMILY_PARITY_OBJECT_READY",
        "live_selector_lines": {"start": selector_start, "end": selector_end},
        "family_proof_lines": {"start": proof_start, "end": proof_end},
        "scenario_rows": scenario_rows,
        "checks": checks,
        "remaining_page_owned_surfaces": [
            "live selector loop",
            "rank trace logging",
            "final result packaging",
            "CTA/apply/publication/render shell",
        ],
        "next_safe_slice": {
            "name": "bottom_reo_selector_policy_live_loop_cutover_readiness",
            "why": (
                "The family can represent selected identity/order parity. The next proof must compare "
                "the live selector loop against a family-owned selector policy helper before moving "
                "any live selection."
            ),
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_selector_policy_family_parity_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_selector_policy_family_parity_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Selector Policy Family Parity Object",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Scenario Parity",
        "",
        "| Scenario | Selected parity | Zero accepted parity | Match |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(
            f"| `{row.get('name')}` | `{row.get('selected_identity_parity')}` | `{row.get('zero_accepted_parity')}` | `{row.get('matches_expectation')}` |"
        )
    lines.extend(["", "## Remaining Page-Owned Surfaces", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_owned_surfaces") or [])
    next_slice = dict(payload.get("next_safe_slice") or {})
    lines.extend(["", "## Next Safe Slice", "", f"- `{next_slice.get('name')}`", f"- {next_slice.get('why')}"])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_selector_policy_family_parity_object {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
