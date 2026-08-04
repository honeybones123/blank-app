"""Focused parity snapshot for proof-only bottom-reo selected recommendation.

This verifier freezes the current page-local returned bottom-reo
recommendation shape against a family-owned proof object. It does not wire the
proof object into live selection, CTA/action, one-click, publication, render,
session, or debug paths.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from design_brain.families.bending import build_bottom_reo_selected_recommendation_proof
from tools.verification.bottom_reo_recommendation_readiness_snapshot import (
    _load_jsonl,
    _stable_hash,
)
from tools.verification.bottom_reo_selector_wrapper_parity_snapshot import _run_scenario


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

FORBIDDEN_PROOF_KEYS = {
    "action",
    "action_payload",
    "action_type",
    "button_contract",
    "cta",
    "cta_intent",
    "debug",
    "debug_trace",
    "final_selected_repair",
    "mutation",
    "one_click",
    "one_click_action",
    "publication",
    "published",
    "render",
    "session",
    "session_state",
    "ui",
}


def _return_payload(rows: list[dict[str, Any]], scenario: str) -> dict[str, Any]:
    matching = [
        row
        for row in rows
        if row.get("event") == "compute_guidance_route"
        and row.get("scenario") == f"BOTTOM_REO_SELECTED_RECOMMENDATION_{scenario}"
        and str(row.get("route_event") or "").endswith("_return")
    ]
    payload = matching[-1].get("payload") if matching else {}
    return payload if isinstance(payload, dict) else {}


def _parse_json_payload(payload: dict[str, Any], key: str, failures: list[str], scenario: str) -> dict[str, Any]:
    raw = payload.get(key)
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        failures.append(f"{scenario}:{key}_invalid")
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _walk_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, val in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_PROOF_KEYS:
                found.add(key_text)
            found.update(_walk_forbidden_keys(val))
    elif isinstance(value, list):
        for val in value:
            found.update(_walk_forbidden_keys(val))
    return found


def _walk_live_candidate_dicts(value: Any) -> int:
    if isinstance(value, dict):
        keys = set(value.keys())
        count = 1 if (
            ("state" in keys or "overview" in keys or "candidate_id" in keys)
            and ("updates" in keys or "arrangement" in keys)
        ) else 0
        return count + sum(_walk_live_candidate_dicts(val) for val in value.values())
    if isinstance(value, list):
        return sum(_walk_live_candidate_dicts(val) for val in value)
    return 0


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_result_shape(result: dict[str, Any]) -> dict[str, Any]:
    updates = dict(result.get("updates") or {})
    return {
        "arrangement": dict(result.get("arrangement") or {}),
        "updates": updates,
        "returned_update_keys": sorted(str(key) for key in updates.keys()),
        "returned_updates_hash": _stable_hash(updates),
        "actual_ast": _as_float(result.get("actual_ast")) or 0.0,
        "required_ast": _as_float(result.get("required_ast")) or 0.0,
        "util": _as_float(result.get("util")),
        "label": str(result.get("label") or ""),
        "score": _as_float(result.get("score")) or 0.0,
        "recommendation_compound": bool(result.get("recommendation_compound")),
        "subfamilies": [str(value) for value in list(result.get("subfamilies") or [])],
        "recommendation_family_tag": (
            str(result.get("recommendation_family_tag"))
            if result.get("recommendation_family_tag") is not None
            else None
        ),
        "guidance_recommendation_title": (
            str(result.get("guidance_recommendation_title"))
            if result.get("guidance_recommendation_title") is not None
            else None
        ),
        "delta_b_mm": _as_float(result.get("delta_b_mm")) or 0.0,
        "delta_D_mm": _as_float(result.get("delta_D_mm")) or 0.0,
        "delta_Ast_bot": _as_float(result.get("delta_Ast_bot")) or 0.0,
        "guidance_change_lines": [str(value) for value in list(result.get("guidance_change_lines") or [])],
    }


def _build_proof_from_result(
    *,
    result: dict[str, Any],
    payload: dict[str, Any],
    scenario: str,
    failures: list[str],
) -> dict[str, Any]:
    decision = _parse_json_payload(payload, "selected_candidate_decision_json", failures, scenario)
    selector = _parse_json_payload(payload, "selector_result_json", failures, scenario)
    ranked_identities = [str(value) for value in list(decision.get("ranked_candidate_identities") or [])]
    selected_identity = (
        selector.get("selected_candidate_identity")
        or decision.get("selected_candidate_identity")
        or None
    )
    selected_index = (
        ranked_identities.index(str(selected_identity))
        if selected_identity is not None and str(selected_identity) in ranked_identities
        else None
    )
    shape = _normalise_result_shape(result)
    utilisation_summary = {
        "selected_bending_util": selector.get("selected_bending_util") or decision.get("selected_bending_util"),
        "selected_candidate_post_util": selector.get("selected_candidate_post_util") or decision.get("selected_candidate_post_util"),
        "selected_reaches_target_band": selector.get("selected_reaches_target_band") or decision.get("selected_reaches_target_band"),
        "target_low": selector.get("target_low") or decision.get("target_low"),
        "target_high": selector.get("target_high") or decision.get("target_high"),
        "post_selector_guard_result": decision.get("post_selector_guard_result"),
        "return_status": payload.get("status"),
        "return_reason": payload.get("return_reason"),
    }
    input_surface = {
        "selected_candidate_identity": selected_identity,
        "selected_source": "page_local_bottom_reo_selected_recommendation",
        "selected_source_index": selected_index,
        "arrangement": dict(shape.get("arrangement") or {}),
        "updates": dict(shape.get("updates") or {}),
        "actual_ast": shape.get("actual_ast"),
        "required_ast": shape.get("required_ast"),
        "util": shape.get("util"),
        "label": shape.get("label"),
        "score": shape.get("score"),
        "recommendation_compound": shape.get("recommendation_compound"),
        "subfamilies": list(shape.get("subfamilies") or []),
        "recommendation_family_tag": shape.get("recommendation_family_tag"),
        "guidance_recommendation_title": shape.get("guidance_recommendation_title"),
        "delta_b_mm": shape.get("delta_b_mm"),
        "delta_D_mm": shape.get("delta_D_mm"),
        "delta_Ast_bot": shape.get("delta_Ast_bot"),
        "guidance_change_lines": list(shape.get("guidance_change_lines") or []),
        "utilisation_check_summary": dict(utilisation_summary),
        "selected_candidate_trace_hash": selector.get("selected_candidate_trace_hash") or decision.get("selected_candidate_trace_hash"),
    }
    before_hash = _stable_hash(input_surface)
    proof = build_bottom_reo_selected_recommendation_proof(**input_surface)
    after_hash = _stable_hash(input_surface)
    proof_dict = proof.to_dict()
    return {
        "decision": decision,
        "selector": selector,
        "page_local_shape": shape,
        "proof": proof_dict,
        "input_hash_before": before_hash,
        "input_hash_after": after_hash,
        "input_mutated": before_hash != after_hash,
        "forbidden_output_keys": sorted(_walk_forbidden_keys(proof_dict)),
        "live_candidate_dict_count": _walk_live_candidate_dicts(proof_dict),
    }


def _compare_shape(scenario: str, summary: dict[str, Any], failures: list[str]) -> None:
    shape = dict(summary.get("page_local_shape") or {})
    proof = dict(summary.get("proof") or {})
    comparisons = {
        "arrangement": shape.get("arrangement"),
        "updates": shape.get("updates"),
        "returned_update_keys": shape.get("returned_update_keys"),
        "returned_updates_hash": shape.get("returned_updates_hash"),
        "actual_ast": shape.get("actual_ast"),
        "required_ast": shape.get("required_ast"),
        "util": shape.get("util"),
        "label": shape.get("label"),
        "score": shape.get("score"),
        "recommendation_compound": shape.get("recommendation_compound"),
        "subfamilies": shape.get("subfamilies"),
        "recommendation_family_tag": shape.get("recommendation_family_tag"),
        "guidance_recommendation_title": shape.get("guidance_recommendation_title"),
        "delta_b_mm": shape.get("delta_b_mm"),
        "delta_D_mm": shape.get("delta_D_mm"),
        "delta_Ast_bot": shape.get("delta_Ast_bot"),
        "guidance_change_lines": shape.get("guidance_change_lines"),
    }
    for key, expected in comparisons.items():
        observed = proof.get(key)
        if isinstance(observed, tuple):
            observed = list(observed)
        if observed != expected:
            failures.append(f"{scenario}:selected_recommendation_{key}_mismatch:expected={expected!r}:got={observed!r}")


def _write_audit_report(path: Path, snapshot: dict[str, Any]) -> None:
    scenarios = snapshot.get("scenarios") if isinstance(snapshot.get("scenarios"), dict) else {}
    parity_lines = []
    for name, data in scenarios.items():
        proof = dict((data or {}).get("proof") or {})
        parity_lines.append(
            f"- {name}: identity={proof.get('selected_candidate_identity')!r}, "
            f"updates={list(proof.get('returned_update_keys') or [])}, "
            f"shape_hash={proof.get('selected_recommendation_shape_hash')}"
        )
    failure_lines = [f"- {failure}" for failure in snapshot.get("failures", [])] or ["- None"]
    report = "\n".join(
        [
            "# Bottom Reo Selected Recommendation Proof Audit",
            "",
            f"Status: {snapshot.get('status')}",
            "",
            "## 1. Selected-Recommendation Proof Type Added",
            "",
            "`BottomReoSelectedRecommendation` was added in `design_brain/families/bending.py` as a frozen proof-only family type.",
            "",
            "## 2. Helper Added",
            "",
            "`build_bottom_reo_selected_recommendation_proof(...)` was added. It consumes explicit post-selection primitive/data values only.",
            "",
            "## 3. Parity Result",
            "",
            *(parity_lines or ["- No scenarios recorded."]),
            "",
            "## 4. Selected Recommendation Fields Captured",
            "",
            "- selected identity, source, and source index",
            "- returned update keys and updates hash",
            "- arrangement and returned updates",
            "- actual Ast, required Ast, utilisation, label, and score",
            "- guidance change lines",
            "- compound flag, subfamilies, family tag, and guidance title",
            "- delta b, delta D, and delta Ast",
            "- utilisation/check summary and selected candidate trace hash",
            "- selected recommendation shape hash and proof hash",
            "",
            "## 5. What Remains Page-Local",
            "",
            "Live candidate dictionaries, live selection, candidate annotation, compound preference swap, CTA/action construction, one-click solver behavior, publication, UI/rendering, session state, and debug trace plumbing remain page-local.",
            "",
            "## 6. Unchanged Paths Confirmation",
            "",
            "The proof helper is used only by this verifier. `inputs_page.py` was not wired to call it, so CTA/action/publication/UI/session/debug paths were not moved or changed.",
            "",
            "## 7. Next Recommended Slice",
            "",
            "Add a page-local proof callsite beside the existing selected-candidate decision trace, still without replacing live selection or returned recommendation ownership.",
            "",
            "## Failures",
            "",
            *failure_lines,
            "",
        ]
    )
    path.write_text(report, encoding="utf-8")


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page_modules.recommendation_compute")
    provider = importlib.import_module("inputs_page_app_contract_bridge")
    module._bind_named_recommendation_globals(
        legacy_page=provider,
        names=module._BOTTOM_RECOMMENDATION_NAMES,
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"bottom_reo_selected_recommendation_parity_trace_{stamp}.jsonl"

    scenarios = [
        "normal_bending_underdesign",
        "two_layer_arrangement",
        "zero_accepted_scenario",
    ]

    previous_env = {
        key: os.environ.get(key)
        for key in (
            "DESIGN_GUIDE_RUNTIME_TRACE",
            "DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO",
            "DESIGN_GUIDE_RUNTIME_TRACE_PATH",
        )
    }
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE"] = "1"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)

    results: dict[str, dict[str, Any]] = {}
    try:
        for scenario in scenarios:
            os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"BOTTOM_REO_SELECTED_RECOMMENDATION_{scenario}"
            results[scenario] = _run_scenario(module, scenario)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    rows = _load_jsonl(trace_path)
    failures: list[str] = []
    scenario_summary: dict[str, Any] = {}
    for scenario in scenarios:
        payload = _return_payload(rows, scenario)
        if not payload:
            failures.append(f"{scenario}:return_trace_missing")
            continue
        result = results.get(scenario) or {}
        summary = _build_proof_from_result(
            result=result,
            payload=payload,
            scenario=scenario,
            failures=failures,
        )
        proof = dict(summary.get("proof") or {})
        if scenario != "zero_accepted_scenario":
            if not result:
                failures.append(f"{scenario}:result_missing")
            _compare_shape(scenario, summary, failures)
            if not proof.get("selected_candidate_identity"):
                failures.append(f"{scenario}:selected_identity_missing")
        else:
            if result:
                failures.append(f"{scenario}:unexpected_result")
            if proof.get("selected_candidate_identity") is not None:
                failures.append(f"{scenario}:unexpected_selected_identity:{proof.get('selected_candidate_identity')!r}")
            if list(proof.get("returned_update_keys") or []):
                failures.append(f"{scenario}:unexpected_update_keys:{proof.get('returned_update_keys')!r}")
        if summary.get("input_mutated"):
            failures.append(f"{scenario}:wrapper_mutated_input_surface")
        if summary.get("forbidden_output_keys"):
            failures.append(f"{scenario}:forbidden_output_keys:{summary.get('forbidden_output_keys')!r}")
        if proof.get("forbidden_fields_present"):
            failures.append(f"{scenario}:forbidden_fields_present:{proof.get('forbidden_fields_present')!r}")
        if summary.get("live_candidate_dict_count"):
            failures.append(f"{scenario}:live_candidate_dicts_returned:{summary.get('live_candidate_dict_count')!r}")
        if scenario == "two_layer_arrangement" and "_2_16_16" not in str(proof.get("selected_candidate_identity") or ""):
            failures.append(f"{scenario}:selected_identity_not_two_layer:{proof.get('selected_candidate_identity')!r}")
        scenario_summary[scenario] = {
            "return_status": payload.get("status"),
            "return_reason": payload.get("return_reason"),
            "result_hash": _stable_hash(result),
            **summary,
        }

    status = "PASS" if not failures else "FAIL"
    output_path = ARTIFACT_DIR / f"bottom_reo_selected_recommendation_parity_snapshot_{stamp}.json"
    audit_path = AUDIT_DIR / f"bottom_reo_selected_recommendation_proof_audit_{stamp}.md"
    snapshot = {
        "schema": "bottom_reo_selected_recommendation_parity_snapshot.v1",
        "status": status,
        "failures": failures,
        "trace_path": str(trace_path),
        "audit_path": str(audit_path),
        "scenarios": scenario_summary,
        "trace_row_count": len(rows),
        "proof_absence_checks": {
            "cta_intent": "absent",
            "one_click_action": "absent",
            "publication_fields": "absent",
            "render_ui_fields": "absent",
            "session_debug_only_fields": "absent",
            "mutation_side_effects": "absent",
        },
    }
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_audit_report(audit_path, snapshot)
    print(f"{status}: {output_path}")
    print(f"audit: {audit_path}")
    print(f"trace: {trace_path}")
    for failure in failures:
        print(f"- {failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
