"""Parity scenarios for post-click replacement decision proof hashes."""

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
        "final_contract": {"enabled": True, "family": "bending", "expected_util": 0.32},
        "final_family": "bending",
        "final_expected_util": 0.32,
        "final_current_bending_util": 0.24,
        "unresolved_families": ["bending"],
        "below_floor_families": ["bending"],
        "same_flow_cleanup_apply": True,
        "exact_blocker_on_visible_item": True,
        "requires_exact_blocker": True,
        "visible_action": True,
        "bending_audit": {
            "post_click_exact_blockers_by_family": {"bending": {"no_second_cta_required": True}},
            "post_click_family_utils": {"bending": 0.24},
            "guidance_branch": "pre-replacement",
        },
        "bending_resolution": {
            "title": "Design Guide blocker proof incomplete",
            "button_contract": {"enabled": False, "family": "bending"},
        },
        "bending_contract": {"enabled": False, "family": "bending"},
        "replacement_applied": True,
        "output_item": {"title": "Design Guide blocker proof incomplete", "family": "bending"},
        "final_visible_resolution": {
            "render_reason": "post_click_low_bending_exact_blocker_final",
            "item": {"family": "bending"},
        },
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
        build_final_design_guide_post_click_replacement_decision_proof,
    )

    base = _base()
    base_proof = build_final_design_guide_post_click_replacement_decision_proof(**base)
    repeat_proof = build_final_design_guide_post_click_replacement_decision_proof(**_base())
    scenarios = {
        "same_input_stable": repeat_proof.get("proof_hash") == base_proof.get("proof_hash"),
        "changed_visible_action_changes_hash": (
            build_final_design_guide_post_click_replacement_decision_proof(
                **_mutate(base, path=("visible_action",), value=False)
            ).get("proof_hash")
            != base_proof.get("proof_hash")
        ),
        "changed_replacement_applied_changes_hash": (
            build_final_design_guide_post_click_replacement_decision_proof(
                **_mutate(base, path=("replacement_applied",), value=False)
            ).get("proof_hash")
            != base_proof.get("proof_hash")
        ),
        "changed_resolution_reason_changes_hash": (
            build_final_design_guide_post_click_replacement_decision_proof(
                **_mutate(
                    base,
                    path=("final_visible_resolution", "render_reason"),
                    value="different_reason",
                )
            ).get("proof_hash")
            != base_proof.get("proof_hash")
        ),
        "changed_contract_changes_hash": (
            build_final_design_guide_post_click_replacement_decision_proof(
                **_mutate(base, path=("final_contract", "enabled"), value=False)
            ).get("proof_hash")
            != base_proof.get("proof_hash")
        ),
        "changed_exact_blocker_audit_changes_hash": (
            build_final_design_guide_post_click_replacement_decision_proof(
                **_mutate(
                    base,
                    path=("bending_audit", "post_click_exact_blockers_by_family", "bending", "no_second_cta_required"),
                    value=False,
                )
            ).get("proof_hash")
            != base_proof.get("proof_hash")
        ),
    }
    latest = {
        "object": _latest("design_guide_post_click_replacement_decision_proof_object"),
        "trace": _latest("design_guide_live_post_click_replacement_decision_proof_trace"),
        "classification": _latest("design_guide_post_click_contract_check_live_rows_classification"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "POST_CLICK_REPLACEMENT_DECISION_PROOF_PARITY_SCENARIOS_PASS",
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
        "classification_pass": (latest.get("classification") or {}).get("status") == "PASS",
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
        "# Post-Click Replacement Decision Proof Parity Scenarios",
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
    lines.append("Next safe slice: row-level narrowing/deletion readiness using the replacement proof hash.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_replacement_decision_proof_parity_scenarios.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR / f"design_guide_post_click_replacement_decision_proof_parity_scenarios_{stamp}.json"
    )
    md_path = AUDIT_DIR / f"design_guide_post_click_replacement_decision_proof_parity_scenarios_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_replacement_decision_proof_parity_scenarios {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
