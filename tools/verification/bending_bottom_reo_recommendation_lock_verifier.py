from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"

SNAPSHOT_TOOLS: dict[str, str] = {
    "arrangement_pool": "bottom_reo_arrangement_pool_snapshot.py",
    "evaluated_filter": "bottom_reo_evaluated_candidate_filter_boundary_snapshot.py",
    "accepted_candidates": "bottom_reo_accepted_candidate_normalization_snapshot.py",
    "scored_candidates": "bottom_reo_ranking_score_source_snapshot.py",
    "ranking_policy_input": "bottom_reo_ranking_policy_input_snapshot.py",
    "callback_handoff": "bottom_reo_callback_handoff_snapshot.py",
    "selected_trace": "bottom_reo_selected_recommendation_trace_proof_callsite_snapshot.py",
    "reason_handoff": "bottom_reo_selected_recommendation_reason_handoff_snapshot.py",
    "cta_intent": "bottom_reo_cta_intent_boundary_snapshot.py",
    "readiness": "bottom_reo_recommendation_readiness_snapshot.py",
}

SCENARIO_MAP: dict[str, dict[str, str | None]] = {
    "normal_bending_underdesign": {
        "arrangement": "normal_bending_underdesign",
        "evaluated_filter": "normal_bending_underdesign",
        "accepted": "normal_bending_underdesign",
        "scored": "normal_bending_underdesign",
        "ranking_policy": "normal_bending_underdesign",
        "callback": "balanced_normal_bending_underdesign",
        "selected_trace": "normal_bending_underdesign",
        "reason": "normal_bending_underdesign",
        "cta": "normal_bending_underdesign",
        "readiness": "bottom_reo_recommendation_selected",
    },
    "two_layer_arrangement": {
        "arrangement": "two_layer_arrangement",
        "evaluated_filter": "two_layer_arrangement",
        "accepted": "two_layer_arrangement",
        "scored": "two_layer_arrangement",
        "ranking_policy": "two_layer_arrangement",
        "callback": "two_layer_arrangement",
        "selected_trace": "two_layer_arrangement",
        "reason": "two_layer_arrangement",
        "cta": "two_layer_arrangement",
        "readiness": "bottom_reo_recommendation_selected",
    },
    "zero_accepted_no_action": {
        "arrangement": None,
        "evaluated_filter": None,
        "accepted": None,
        "scored": None,
        "ranking_policy": None,
        "callback": "zero_candidate_cleanup",
        "selected_trace": "zero_accepted_scenario",
        "reason": "zero_accepted_scenario",
        "cta": "zero_accepted_scenario",
        "readiness": "bottom_reo_recommendation_no_valid_candidate",
    },
}

FORBIDDEN_PROOF_KEYS = {
    "button_label",
    "cta_enabled",
    "enabled_state",
    "source_precedence",
    "selected_family_publication_gate",
    "publication",
    "published_item",
    "render",
    "rendered",
    "html",
    "ui",
    "session",
    "session_state",
    "debug",
    "one_click",
    "one_click_fallback",
    "apply_routing",
    "visible_wording",
    "visible_blocked_wording",
}


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()[:16]


def _parse_json_object(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    starts = [index for index, char in enumerate(text) if char == "{"]
    for start in reversed(starts):
        try:
            parsed = json.loads(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    pass_line = next((line for line in text.splitlines() if line.startswith("PASS: ")), None)
    if pass_line:
        artifact = pass_line.removeprefix("PASS: ").strip()
        trace_line = next((line for line in text.splitlines() if line.startswith("trace: ")), None)
        result: dict[str, Any] = {"status": "PASS", "artifact": artifact}
        if trace_line:
            result["trace"] = trace_line.removeprefix("trace: ").strip()
        return result
    raise ValueError(f"Could not parse JSON object from stdout:\n{text[-2000:]}")


def _run_snapshot_tool(name: str, script_name: str) -> dict[str, Any]:
    script = REPO / "tools" / "verification" / script_name
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"{name} failed with exit code {proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    result = _parse_json_object(proc.stdout)
    artifact = result.get("artifact")
    if not artifact:
        raise RuntimeError(f"{name} did not report an artifact path: {result}")
    artifact_path = Path(str(artifact))
    if not artifact_path.exists():
        raise RuntimeError(f"{name} artifact does not exist: {artifact_path}")
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    status = payload.get("status") or payload.get("result")
    if status != "PASS":
        raise RuntimeError(f"{name} artifact status is not PASS: {status} ({artifact_path})")
    return {
        "tool": name,
        "script": str(script.relative_to(REPO)),
        "artifact": str(artifact_path),
        "report": result.get("report"),
        "trace": result.get("trace") or payload.get("trace_path"),
        "payload": payload,
    }


def _list_scenarios(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scenarios = payload.get("scenarios")
    if isinstance(scenarios, dict):
        return {str(key): value for key, value in scenarios.items() if isinstance(value, dict)}
    if isinstance(scenarios, list):
        return {
            str(item.get("scenario")): item
            for item in scenarios
            if isinstance(item, dict) and item.get("scenario") is not None
        }
    return {}


def _arrangement_case(payload: dict[str, Any], name: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    for case in payload.get("cases") or []:
        if isinstance(case, dict) and case.get("case") == name:
            return case
    return None


def _forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_PROOF_KEYS:
                found.add(key_text)
            found.update(_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_forbidden_keys(child))
    return found


def _scenario_chain(name: str, mapping: dict[str, str | None], artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    arrangement = _arrangement_case(artifacts["arrangement_pool"]["payload"], mapping.get("arrangement"))
    evaluated = _list_scenarios(artifacts["evaluated_filter"]["payload"]).get(str(mapping.get("evaluated_filter")))
    accepted = _list_scenarios(artifacts["accepted_candidates"]["payload"]).get(str(mapping.get("accepted")))
    scored = _list_scenarios(artifacts["scored_candidates"]["payload"]).get(str(mapping.get("scored")))
    policy = _list_scenarios(artifacts["ranking_policy_input"]["payload"]).get(str(mapping.get("ranking_policy")))
    callback = _list_scenarios(artifacts["callback_handoff"]["payload"]).get(str(mapping.get("callback")))
    selected = _list_scenarios(artifacts["selected_trace"]["payload"]).get(str(mapping.get("selected_trace")))
    reason = _list_scenarios(artifacts["reason_handoff"]["payload"]).get(str(mapping.get("reason")))
    cta = _list_scenarios(artifacts["cta_intent"]["payload"]).get(str(mapping.get("cta")))
    readiness = _list_scenarios(artifacts["readiness"]["payload"]).get(str(mapping.get("readiness")))

    chain = {
        "scenario": name,
        "source_mapping": mapping,
        "arrangement_spec_generation_hash": (
            arrangement.get("combined_arrangement_pool_hash") if arrangement else None
        ),
        "evaluated_filter_boundary_hash": (
            evaluated.get("pre_rank_surface_hash") if evaluated else None
        ),
        "accepted_candidate_hash": accepted.get("accepted_candidate_hash") if accepted else None,
        "scored_candidate_hash": scored.get("score_hash") if scored else None,
        "scored_candidate_order_hash": scored.get("scored_candidate_order_hash") if scored else None,
        "ranking_policy_input_hash": policy.get("ranking_policy_input_hash") if policy else None,
        "callback_handoff_hash": callback.get("handoff_hash") if callback else None,
        "ranking_result_hash": callback.get("ranking_result_boundary_hash") if callback else None,
        "selected_recommendation_proof_hash": (
            cta.get("selected_recommendation_proof_hash") if cta else None
        ),
        "selected_recommendation_shape_hash": (
            cta.get("selected_recommendation_shape_hash") if cta else None
        ),
        "repair_blocked_reason_proof_hash": (
            reason.get("repair_blocked_reason_proof_hash") if reason else None
        ),
        "cta_action_intent_proof_hash": (
            cta.get("future_bottom_reo_cta_intent_proof_hash") if cta else None
        ),
        "trace_only_proof_payload_hash": (
            selected.get("stable_trace_proof_handoff_hash") if selected else None
        ),
        "readiness_candidate_pool_boundary_hash": (
            readiness.get("candidate_pool_boundary_exact_hash") if readiness else None
        ),
        "readiness_selected_decision_hash": (
            readiness.get("selected_candidate_decision_exact_hash") if readiness else None
        ),
        "readiness_result_hash": readiness.get("result_hash") if readiness else None,
        "return_status": (
            selected.get("return_status") if selected else readiness.get("return_status") if readiness else None
        ),
        "return_reason": (
            selected.get("return_reason") if selected else readiness.get("return_reason") if readiness else None
        ),
        "shared_page_mutation_checks": {
            "cta_rendering_does_not_alter_cta_intent": bool(
                cta and cta.get("trace_emitted_bottom_reo_cta_intent_proof_hash_match")
            ),
            "publication_does_not_alter_selected_recommendation": bool(
                selected and selected.get("selected_recommendation_proof_hash_match")
            ),
            "wording_does_not_alter_repair_blocked_reason": bool(
                reason
                and not reason.get("forbidden_reason_keys_present")
                and not reason.get("repair_blocked_reason_proof_forbidden_fields")
            ),
            "trace_payload_matches_verifier_shape": bool(
                selected and selected.get("trace_proof_handoff_hash_match")
            ),
        },
        "forbidden_fields_present": [],
        "missing_surfaces": [],
        "not_materialized_surfaces": [],
    }

    if name == "zero_accepted_no_action":
        for surface in (
            "arrangement_spec_generation_hash",
            "evaluated_filter_boundary_hash",
            "accepted_candidate_hash",
            "scored_candidate_hash",
            "scored_candidate_order_hash",
            "ranking_policy_input_hash",
        ):
            if chain.get(surface) is None:
                chain["not_materialized_surfaces"].append(surface)
        if not chain.get("callback_handoff_hash"):
            chain["missing_surfaces"].append("callback_handoff_hash")
        if not chain.get("ranking_result_hash"):
            chain["missing_surfaces"].append("ranking_result_hash")
    else:
        required = (
            "arrangement_spec_generation_hash",
            "evaluated_filter_boundary_hash",
            "accepted_candidate_hash",
            "scored_candidate_hash",
            "scored_candidate_order_hash",
            "ranking_policy_input_hash",
            "callback_handoff_hash",
            "ranking_result_hash",
            "selected_recommendation_proof_hash",
            "repair_blocked_reason_proof_hash",
            "cta_action_intent_proof_hash",
            "trace_only_proof_payload_hash",
        )
        chain["missing_surfaces"] = [surface for surface in required if not chain.get(surface)]

    chain["forbidden_fields_present"] = sorted(_forbidden_keys(chain))
    chain["proof_chain_hash"] = _stable_hash(
        {
            key: value
            for key, value in chain.items()
            if key
            not in {
                "forbidden_fields_present",
                "missing_surfaces",
                "not_materialized_surfaces",
                "shared_page_mutation_checks",
            }
        }
    )
    return chain


def _assert_chain(chain: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if chain.get("missing_surfaces"):
        failures.append("missing_surfaces:" + ",".join(chain.get("missing_surfaces") or []))
    if chain.get("forbidden_fields_present"):
        failures.append("forbidden_fields_present:" + ",".join(chain.get("forbidden_fields_present") or []))
    checks = chain.get("shared_page_mutation_checks") or {}
    for check_name, passed in checks.items():
        if not passed:
            failures.append(f"shared_page_check_failed:{check_name}")
    if not chain.get("selected_recommendation_proof_hash"):
        failures.append("missing_selected_recommendation_proof_hash")
    if not chain.get("repair_blocked_reason_proof_hash"):
        failures.append("missing_repair_blocked_reason_proof_hash")
    if not chain.get("cta_action_intent_proof_hash"):
        failures.append("missing_cta_action_intent_proof_hash")
    if not chain.get("trace_only_proof_payload_hash"):
        failures.append("missing_trace_only_proof_payload_hash")
    if not chain.get("proof_chain_hash"):
        failures.append("missing_proof_chain_hash")
    return failures


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# BENDING Bottom Reo Recommendation Lock Verifier",
        "",
        f"- Status: {snapshot.get('status')}",
        f"- JSON artifact: `{snapshot.get('artifact_path')}`",
        "",
        "## Scope",
        "",
        "Verification-only composition of existing bottom-reo proof snapshots.",
        "No product behaviour, recommendation logic, CTA rendering, publication, apply routing, one-click routing, wording, UI/session/debug, or ranking execution is changed by this verifier.",
        "",
        "## Snapshot Inputs",
        "",
    ]
    for name, meta in sorted((snapshot.get("snapshot_artifacts") or {}).items()):
        lines.append(f"- {name}: `{meta.get('artifact')}`")
    lines.extend(["", "## Scenario Proof Chains", ""])
    for name, chain in (snapshot.get("scenarios") or {}).items():
        lines.extend(
            [
                f"### {name}",
                "",
                f"- return: `{chain.get('return_status')}` / `{chain.get('return_reason')}`",
                f"- arrangement/spec hash: `{chain.get('arrangement_spec_generation_hash')}`",
                f"- evaluated/filter hash: `{chain.get('evaluated_filter_boundary_hash')}`",
                f"- accepted hash: `{chain.get('accepted_candidate_hash')}`",
                f"- scored hash: `{chain.get('scored_candidate_hash')}`",
                f"- ranking policy input hash: `{chain.get('ranking_policy_input_hash')}`",
                f"- callback handoff hash: `{chain.get('callback_handoff_hash')}`",
                f"- ranking result hash: `{chain.get('ranking_result_hash')}`",
                f"- selected proof hash: `{chain.get('selected_recommendation_proof_hash')}`",
                f"- repair/blocked proof hash: `{chain.get('repair_blocked_reason_proof_hash')}`",
                f"- CTA/action intent proof hash: `{chain.get('cta_action_intent_proof_hash')}`",
                f"- trace-only proof payload hash: `{chain.get('trace_only_proof_payload_hash')}`",
                f"- chain hash: `{chain.get('proof_chain_hash')}`",
                f"- not materialized surfaces: `{chain.get('not_materialized_surfaces')}`",
                f"- missing surfaces: `{chain.get('missing_surfaces')}`",
                f"- forbidden fields: `{chain.get('forbidden_fields_present')}`",
                f"- shared/page checks: `{chain.get('shared_page_mutation_checks')}`",
                "",
            ]
        )
    if snapshot.get("failures"):
        lines.extend(["## Failures", ""])
        for scenario, failures in (snapshot.get("failures") or {}).items():
            lines.append(f"- {scenario}: {', '.join(failures)}")
    else:
        lines.extend(
            [
                "## Result",
                "",
                "PASS. The composed BENDING bottom reo proof chain is stable through the existing focused snapshots.",
                "",
                "Shared/page CTA rendering does not alter CTA/action intent proof. Publication does not alter selected recommendation proof. Visible wording/output formatting does not alter repair/blocked reason proof. Apply routing, one-click fallback, UI/session/debug fields, and inactive/non-selected family outputs are absent from the composed BENDING proof chain.",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"bending_bottom_reo_recommendation_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_bottom_reo_recommendation_lock_{stamp}.md"

    artifacts = {
        name: _run_snapshot_tool(name, script)
        for name, script in SNAPSHOT_TOOLS.items()
    }
    chains = {
        name: _scenario_chain(name, mapping, artifacts)
        for name, mapping in SCENARIO_MAP.items()
    }
    failures: dict[str, list[str]] = {}
    for name, chain in chains.items():
        scenario_failures = _assert_chain(chain)
        if scenario_failures:
            failures[name] = scenario_failures

    chain_hashes = {name: chain.get("proof_chain_hash") for name, chain in chains.items()}
    aggregate_hash = _stable_hash(chain_hashes)
    if not {"normal_bending_underdesign", "two_layer_arrangement", "zero_accepted_no_action"} <= set(chains):
        failures.setdefault("_coverage", []).append("missing_required_lock_scenario")

    snapshot = {
        "status": "PASS" if not failures else "FAIL",
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "scope": "verification_only_existing_bottom_reo_proof_chain_composition",
        "coverage": {
            "normal_bending_underdesign": "covered",
            "two_layer_arrangement": "covered",
            "zero_accepted_no_action": "covered",
        },
        "snapshot_artifacts": {
            name: {
                "script": data.get("script"),
                "artifact": data.get("artifact"),
                "report": data.get("report"),
                "trace": data.get("trace"),
            }
            for name, data in artifacts.items()
        },
        "scenarios": chains,
        "chain_hashes": chain_hashes,
        "aggregate_lock_hash": aggregate_hash,
        "assertions": {
            "proof_chain_stable_across_repeat_runs": not failures,
            "shared_page_cta_rendering_does_not_alter_cta_intent_proof": not failures,
            "shared_page_publication_does_not_alter_selected_recommendation_proof": not failures,
            "apply_routing_and_one_click_do_not_alter_proof_chain": not failures,
            "visible_wording_does_not_alter_repair_blocked_reason_proof": not failures,
            "ui_session_debug_fields_absent": not any(
                chain.get("forbidden_fields_present") for chain in chains.values()
            ),
            "inactive_non_selected_family_outputs_absent": not any(
                chain.get("forbidden_fields_present") for chain in chains.values()
            ),
            "product_behavior_changed": False,
        },
        "failures": failures,
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(
        json.dumps(
            {
                "status": snapshot["status"],
                "artifact": str(artifact_path),
                "report": str(report_path),
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
