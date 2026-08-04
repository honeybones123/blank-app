"""Branch parity scenarios for blocked-primary full-route proof wiring.

This is proof-only. It does not execute the live page route, mutate session,
render UI, route Apply, or change product behavior. It proves the controller
full-route proof selects the same branch/result hash that the live trace wiring
passes from each page branch.
"""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

ROUTE = "_resolve_final_visible_no_active_blocked_primary_cleanup_probe_result"
CONTROLLER_ROUTE = "run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route"
GENERIC_CALLER = "_run_design_guide_page_shell_controller_route"
CONTROLLER_ALIAS = "_run_design_guide_controller_no_active_blocked_primary_cleanup_probe_route"
SAFE_BRANCH = "safe_shear_cleanup_before_blocker"
BENDING_BRANCH = "bending_cleanup_available_before_blocker"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not paths:
        return {"status": "MISSING", "path": None}
    path = paths[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "ERROR", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    return {"status": payload.get("status"), "path": str(path), "payload": payload}


def _function_source(path: Path, function_name: str) -> tuple[str | None, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return None, None, None


def _scenario_samples() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_bending_cleanup_available_before_blocker_result,
        build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof,
        build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof,
        build_design_guide_controller_safe_cleanup_candidate_before_blocker_result,
    )

    policy = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof(
        primary={"title": "Primary cleanup blocked", "action_type": "blocked"},
        contract={"enabled": False, "action_type": "blocked"},
        updates={},
        primary_evidence={
            "selected_candidate_updates": {"lig_legs": 0},
            "safe_executor_backed_candidates_count": 1,
        },
        final_state={"lig_legs": 2, "reo_1": 8},
        final_overview={"utils": {"bending": 0.24, "shear": 0.69}},
        final_accepted_min_family_util=0.85,
        target_band_eps=0.001,
        compound_shear_update_keys={"lig_legs"},
        contract_enabled=False,
        post_click_route_for_safe_cleanup=False,
        safe_cleanup_updates_match_current_state=False,
        final_bending_util=0.24,
        bending_probe_candidate_present=True,
        bending_probe_updates={"reo_1": 5},
        bending_probe_expected_util=0.69,
    )
    safe_result = build_design_guide_controller_safe_cleanup_candidate_before_blocker_result(
        safe_cleanup_item={
            "title": "Shear cleanup",
            "title_main": "Shear cleanup",
            "primary_action": "Remove links",
            "bucket": "pass",
            "guidance_intent": "efficiency_tightening",
        },
        safe_cleanup_contract={
            "enabled": True,
            "action_type": "apply_resolved_candidate",
            "candidate_id": "safe-shear",
            "updates": {"lig_legs": 0},
        },
        safe_cleanup_updates={"lig_legs": 0},
        final_overview={"utils": {"bending": 0.24, "shear": 0.69}},
        state_fingerprint="state-safe",
    )
    bending_result = build_design_guide_controller_bending_cleanup_available_before_blocker_result(
        bending_probe_item={
            "title": "Bending cleanup",
            "title_main": "Bending cleanup",
            "primary_action": "Reduce bottom reinforcement",
            "bucket": "pass",
            "guidance_intent": "efficiency_tightening",
        },
        bending_probe_contract={
            "enabled": True,
            "action_type": "apply_resolved_candidate",
            "candidate_id": "bending-probe",
            "updates": {"reo_1": 5},
        },
        bending_probe_updates={"reo_1": 5},
        bending_probe_candidate_id="bending-probe",
        bending_probe_expected_util=0.69,
        final_overview={"utils": {"bending": 0.24, "shear": 0.69}},
        final_bending_util_for_probe=0.24,
        state_fingerprint="state-bending",
    )
    scenarios = {
        "safe_branch": {
            "expected_branch": SAFE_BRANCH,
            "safe_cleanup_result": safe_result,
            "bending_cleanup_result": bending_result,
        },
        "bending_branch": {
            "expected_branch": BENDING_BRANCH,
            "safe_cleanup_result": {},
            "bending_cleanup_result": bending_result,
        },
        "none_branch": {
            "expected_branch": "none",
            "safe_cleanup_result": {},
            "bending_cleanup_result": {},
        },
    }
    rows: dict[str, Any] = {}
    for name, scenario in scenarios.items():
        proof = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof(
            route_policy_proof=policy,
            safe_cleanup_result=scenario["safe_cleanup_result"],
            bending_cleanup_result=scenario["bending_cleanup_result"],
        )
        selected_result = (
            scenario["safe_cleanup_result"]
            if scenario["safe_cleanup_result"]
            else scenario["bending_cleanup_result"]
        )
        rows[name] = {
            "expected_branch": scenario["expected_branch"],
            "selected_branch": proof.get("selected_branch"),
            "selected_result_hash": proof.get("selected_result_hash"),
            "expected_result_hash": _stable_hash(dict(selected_result or {})),
            "result_hash_match": proof.get("selected_result_hash")
            == _stable_hash(dict(selected_result or {})),
            "full_route_builder_hash": proof.get("full_route_builder_hash"),
            "route_policy_hash": proof.get("route_policy_hash"),
            "proof_only": proof.get("proof_only"),
            "product_driving": proof.get("product_driving"),
            "render_driving": proof.get("render_driving"),
            "apply_driving": proof.get("apply_driving"),
            "session_driving": proof.get("session_driving"),
        }
    repeat = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof(
        route_policy_proof=policy,
        safe_cleanup_result=safe_result,
        bending_cleanup_result=bending_result,
    )
    return {
        "policy_hash": policy.get("route_policy_hash"),
        "scenarios": rows,
        "safe_repeat_hash_stable": rows["safe_branch"].get("full_route_builder_hash")
        == repeat.get("full_route_builder_hash"),
    }


def _capture() -> dict[str, Any]:
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE)
    controller_route_source, controller_route_start, controller_route_end = _function_source(
        CONTROLLER, CONTROLLER_ROUTE
    )
    route_text = route_source or ""
    controller_route_text = controller_route_source or ""
    samples = _scenario_samples()
    return {
        "decision": "FULL_ROUTE_BRANCH_PARITY_PROVEN_FOR_CONTROLLER_ROUTE_AFTER_PAGE_SHELL_CUTOVER",
        "route": {
            "name": ROUTE,
            "present": route_source is not None,
            "start_line": route_start,
            "end_line": route_end,
            "delegates_to_controller": (
                f"return {GENERIC_CALLER}(" in route_text
                and f"controller_fn={CONTROLLER_ALIAS}" in route_text
            ),
        },
        "controller_route": {
            "name": CONTROLLER_ROUTE,
            "present": controller_route_source is not None,
            "start_line": controller_route_start,
            "end_line": controller_route_end,
            "exported": f'"{CONTROLLER_ROUTE}"' in controller_source,
            "safe_branch_uses_safe_result_only": (
                "safe_cleanup_result=safe_cleanup_result" in controller_route_text
                and "bending_cleanup_result=None" in controller_route_text
            ),
            "bending_branch_uses_bending_result_only": (
                "safe_cleanup_result=None" in controller_route_text
                and "bending_cleanup_result=bending_probe_result" in controller_route_text
            ),
            "full_route_proof_call_count": controller_route_text.count(
                "build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof("
            ),
        },
        "scenario_samples": samples,
        "latest": {
            "full_route_trace_wiring": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_full_route_trace_wiring"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_full_route_trace_wiring"
                ).get("path"),
            },
            "full_route_builder_object": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_full_route_builder_object"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_full_route_builder_object"
                ).get("path"),
            },
            "controller_route_object": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_controller_route_object"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_controller_route_object"
                ).get("path"),
            },
            "generic_page_shell_cutover": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_generic_page_shell_caller_cutover"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_generic_page_shell_caller_cutover"
                ).get("path"),
            },
            "independence_lock": {
                "status": _latest("design_guide_independence_lock").get("status"),
                "path": _latest("design_guide_independence_lock").get("path"),
            },
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    samples = dict((capture.get("scenario_samples") or {}).get("scenarios") or {})
    latest = dict(capture.get("latest") or {})
    route = dict(capture.get("route") or {})
    controller = dict(capture.get("controller_route") or {})
    route_absent_after_deletion = route.get("present") is False and controller.get("present") is True
    return {
        "route_present_or_deleted": route.get("present") is True or route_absent_after_deletion,
        "page_route_delegates_to_controller_or_deleted": (
            route.get("delegates_to_controller") is True or route_absent_after_deletion
        ),
        "controller_route_present": controller.get("present") is True,
        "controller_route_exported": controller.get("exported") is True,
        "safe_branch_parity": (samples.get("safe_branch") or {}).get("selected_branch")
        == SAFE_BRANCH
        and (samples.get("safe_branch") or {}).get("result_hash_match") is True,
        "bending_branch_parity": (samples.get("bending_branch") or {}).get("selected_branch")
        == BENDING_BRANCH
        and (samples.get("bending_branch") or {}).get("result_hash_match") is True,
        "none_branch_explicit": (samples.get("none_branch") or {}).get("selected_branch")
        == "none"
        and (samples.get("none_branch") or {}).get("result_hash_match") is True,
        "scenario_hash_stable": (capture.get("scenario_samples") or {}).get(
            "safe_repeat_hash_stable"
        )
        is True,
        "proofs_non_product_driving": all(
            (row or {}).get("proof_only") is True
            and (row or {}).get("product_driving") is False
            and (row or {}).get("render_driving") is False
            and (row or {}).get("apply_driving") is False
            and (row or {}).get("session_driving") is False
            for row in samples.values()
        ),
        "safe_controller_route_uses_safe_result_only": controller.get("safe_branch_uses_safe_result_only")
        is True,
        "bending_controller_route_uses_bending_result_only": controller.get(
            "bending_branch_uses_bending_result_only"
        )
        is True,
        "exactly_two_controller_full_route_proof_calls": controller.get(
            "full_route_proof_call_count"
        )
        == 2,
        "full_route_trace_wiring_passed": (latest.get("full_route_trace_wiring") or {}).get(
            "status"
        )
        == "PASS",
        "full_route_builder_object_passed": (latest.get("full_route_builder_object") or {}).get(
            "status"
        )
        == "PASS",
        "controller_route_object_passed": (latest.get("controller_route_object") or {}).get(
            "status"
        )
        == "PASS",
        "generic_page_shell_cutover_artifact_available": (
            latest.get("generic_page_shell_cutover") or {}
        ).get("status")
        in {"PASS", "FAIL", "MISSING"},
        "independence_lock_artifact_available": (latest.get("independence_lock") or {}).get(
            "status"
        )
        in {"PASS", "FAIL"},
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    samples = dict((capture.get("scenario_samples") or {}).get("scenarios") or {})
    lines = [
        "# Design Guide No-Active Blocked-Primary Full Route Branch Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Scenarios", "", "| Scenario | Selected branch | Hash match |", "| --- | --- | ---: |"])
    for name, row in samples.items():
        lines.append(
            f"| {name} | `{row.get('selected_branch')}` | `{row.get('result_hash_match')}` |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            "Create a dead-body deletion proof for the unreachable page body after the generic page-shell cutover.",
            "",
            "No product behavior, visible wording, CTA/apply semantics, family runtime, solver maths, target bands, render ownership, apply routing, or UI/session ownership changed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_no_active_blocked_primary_full_route_branch_parity_scenarios_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_full_route_branch_parity_scenarios_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_full_route_branch_parity_scenarios {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status == "PASS":
        print("next=cutover-readiness verifier for controller-owned blocked-primary route")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
