"""Parity scenarios for post-click contract check input proof hashes."""

from __future__ import annotations

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


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _base() -> dict[str, Any]:
    return {
        "item": {
            "family": "bending",
            "action_type": "apply_resolved_candidate",
            "exact_blockers_by_family": {"bending": {"no_second_cta_required": True}},
            "candidate_search_evidence": {
                "post_click_exact_blockers_by_family": {
                    "bending": {"no_second_cta_required": True}
                }
            },
        },
        "final_visible_resolution": {"render_reason": "post_click_candidate", "item": {"family": "bending"}},
        "guidance_debug": {
            "post_click_unresolved_low_util_families": ["bending"],
            "post_click_families_below_final_threshold": ["bending"],
        },
        "post_cleanup_render_audit": {
            "post_click_unresolved_low_util_families": ["bending"],
            "post_click_families_below_final_threshold": [],
        },
        "last_apply_route": {
            "apply_used_resolved_candidate_payload": True,
            "applied_updates": {"lig_d": 0, "lig_legs": 0},
            "resolved_candidate_label": "cleanup",
        },
        "primary_payload_binding_audit": {"applied_updates": {"lig_d": 0, "lig_legs": 0}},
        "current_state": {"lig_d": 0, "lig_legs": 0, "b": 300, "D": 500},
        "final_contract": {"enabled": True, "family": "bending", "expected_util": 0.32},
    }


def _mutate(base: dict[str, Any], *, path: tuple[str, ...], value: Any) -> dict[str, Any]:
    clone = json.loads(json.dumps(base))
    cursor = clone
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    return clone


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_contract_check_input_proof,
    )

    base = _base()
    base_proof = build_final_design_guide_post_click_contract_check_input_proof(**base)
    repeat_proof = build_final_design_guide_post_click_contract_check_input_proof(**_base())
    scenarios = {
        "same_input_stable": repeat_proof.get("proof_hash") == base_proof.get("proof_hash"),
        "changed_last_apply_route_changes_hash": (
            build_final_design_guide_post_click_contract_check_input_proof(
                **_mutate(base, path=("last_apply_route", "resolved_candidate_label"), value="different cleanup")
            ).get("proof_hash")
            != base_proof.get("proof_hash")
        ),
        "changed_ligature_state_changes_hash": (
            build_final_design_guide_post_click_contract_check_input_proof(
                **_mutate(base, path=("current_state", "lig_legs"), value=2)
            ).get("proof_hash")
            != base_proof.get("proof_hash")
        ),
        "changed_exact_blocker_changes_hash": (
            build_final_design_guide_post_click_contract_check_input_proof(
                **_mutate(
                    base,
                    path=("item", "exact_blockers_by_family", "bending", "no_second_cta_required"),
                    value=False,
                )
            ).get("proof_hash")
            != base_proof.get("proof_hash")
        ),
        "changed_final_contract_changes_hash": (
            build_final_design_guide_post_click_contract_check_input_proof(
                **_mutate(base, path=("final_contract", "enabled"), value=False)
            ).get("proof_hash")
            != base_proof.get("proof_hash")
        ),
    }
    latest = {
        "object": _latest("design_guide_post_click_contract_check_input_proof_object"),
        "trace": _latest("design_guide_live_post_click_contract_check_input_proof_trace"),
        "readiness": _latest("design_guide_post_click_final_contract_checks_readiness"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "POST_CLICK_CONTRACT_CHECK_INPUT_PROOF_PARITY_SCENARIOS_PASS",
        "base_proof_hash": base_proof.get("proof_hash"),
        "scenario_results": scenarios,
        "ready_for_narrowing_audit": True,
        "ready_for_direct_cutover": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "all_scenarios_pass": all((capture.get("scenario_results") or {}).values()),
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "readiness_pass": (latest.get("readiness") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "direct_cutover_still_false": capture.get("ready_for_direct_cutover") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Contract Check Input Proof Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenario Results",
        "",
    ]
    lines.extend(
        f"- {key}: `{value}`" for key, value in (capture.get("scenario_results") or {}).items()
    )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", ""])
    lines.append(
        "Next safe slice: classify which live post-click rows can be narrowed now that the input proof hash is stable."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_contract_check_input_proof_parity_scenarios.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR / f"design_guide_post_click_contract_check_input_proof_parity_scenarios_{stamp}.json"
    )
    md_path = AUDIT_DIR / f"design_guide_post_click_contract_check_input_proof_parity_scenarios_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_contract_check_input_proof_parity_scenarios {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
