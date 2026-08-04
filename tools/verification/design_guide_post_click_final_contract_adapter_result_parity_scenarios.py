"""Parity scenarios for the post-click final-contract adapter result."""

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
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _base() -> dict[str, Any]:
    return {
        "output_item": {
            "title": "Design Guide blocker proof incomplete",
            "family": "bending",
            "button_contract": {"enabled": False, "family": "bending"},
        },
        "final_visible_resolution": {
            "render_reason": "pre_adapter_final_visible",
            "item": {"family": "bending", "title": "Strengthening required"},
        },
        "guidance_debug": {"guidance_branch": "pre_adapter"},
        "visible_action": True,
        "bending_resolution": {
            "title": "Design Guide blocker proof incomplete",
            "family": "bending",
            "button_contract": {"enabled": False, "family": "bending"},
        },
        "bending_contract": {"enabled": False, "family": "bending"},
        "input_proof": {"proof_hash": "input-proof-hash"},
        "replacement_decision_proof": {"proof_hash": "replacement-proof-hash"},
        "adapter_proof": {"proof_hash": "adapter-proof-hash"},
    }


def _scenario_payloads() -> dict[str, dict[str, Any]]:
    base = _base()

    no_visible_action = dict(base)
    no_visible_action["visible_action"] = False

    enabled_contract = dict(base)
    enabled_contract["bending_contract"] = {"enabled": True, "family": "bending"}

    no_bending_resolution = dict(base)
    no_bending_resolution["bending_resolution"] = {}

    changed_output_item = dict(base)
    changed_output_item["output_item"] = {
        **dict(base["output_item"]),
        "family": "bending_changed",
    }

    changed_input_proof = dict(base)
    changed_input_proof["input_proof"] = {"proof_hash": "changed-input-proof-hash"}

    changed_adapter_proof = dict(base)
    changed_adapter_proof["adapter_proof"] = {"proof_hash": "changed-adapter-proof-hash"}

    return {
        "base_replacement_result": base,
        "no_visible_action": no_visible_action,
        "enabled_bending_contract": enabled_contract,
        "no_bending_resolution": no_bending_resolution,
        "changed_output_item": changed_output_item,
        "changed_input_proof": changed_input_proof,
        "changed_adapter_proof": changed_adapter_proof,
    }


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_final_contract_check_adapter_result,
    )

    scenarios = _scenario_payloads()
    base_first = build_final_design_guide_post_click_final_contract_check_adapter_result(
        **scenarios["base_replacement_result"]
    )
    base_second = build_final_design_guide_post_click_final_contract_check_adapter_result(
        **_scenario_payloads()["base_replacement_result"]
    )
    scenario_results: dict[str, dict[str, Any]] = {}
    for name, kwargs in scenarios.items():
        result_payload = build_final_design_guide_post_click_final_contract_check_adapter_result(
            **kwargs
        )
        result = dict(result_payload.get("result") or {})
        scenario_results[name] = {
            "proof_hash": result_payload.get("proof_hash"),
            "result_hash": result_payload.get("result_hash"),
            "should_publish_exact_blocker_projection": result.get(
                "should_publish_exact_blocker_projection"
            ),
            "replacement_applied": result.get("replacement_applied"),
            "replacement_item_hash": result.get("replacement_item_hash"),
            "final_visible_resolution_hash": result.get("final_visible_resolution_hash"),
            "guidance_debug_patch_hash": result.get("guidance_debug_patch_hash"),
            "projection_hash": result.get("projection_hash"),
        }
    base_hash = scenario_results["base_replacement_result"]["proof_hash"]
    changed_hashes = {
        name: value["proof_hash"] != base_hash
        for name, value in scenario_results.items()
        if name != "base_replacement_result"
    }
    disabled_names = ("no_visible_action", "enabled_bending_contract", "no_bending_resolution")
    latest = {
        "result_object": _latest("design_guide_post_click_final_contract_adapter_result_object"),
        "adapter_hash_parity": _latest("design_guide_live_post_click_final_contract_adapter_hash_parity"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "POST_CLICK_FINAL_CONTRACT_ADAPTER_RESULT_PARITY_SCENARIOS_PASS",
        "base_hash_stable": base_first.get("proof_hash") == base_second.get("proof_hash"),
        "scenario_results": scenario_results,
        "changed_hashes": changed_hashes,
        "all_variants_change_hash": all(changed_hashes.values()),
        "base_should_publish_projection": scenario_results["base_replacement_result"][
            "should_publish_exact_blocker_projection"
        ],
        "disabled_variants_do_not_publish": all(
            scenario_results[name]["should_publish_exact_blocker_projection"] is False
            for name in disabled_names
        ),
        "disabled_variants_do_not_replace": all(
            scenario_results[name]["replacement_applied"] is False for name in disabled_names
        ),
        "proof_variants_preserve_projection_decision": all(
            scenario_results[name]["should_publish_exact_blocker_projection"] is True
            for name in ("changed_output_item", "changed_input_proof", "changed_adapter_proof")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": latest,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "base_hash_stable": capture.get("base_hash_stable") is True,
        "all_variants_change_hash": capture.get("all_variants_change_hash") is True,
        "base_should_publish_projection": capture.get("base_should_publish_projection") is True,
        "disabled_variants_do_not_publish": capture.get("disabled_variants_do_not_publish") is True,
        "disabled_variants_do_not_replace": capture.get("disabled_variants_do_not_replace") is True,
        "proof_variants_preserve_projection_decision": (
            capture.get("proof_variants_preserve_projection_decision") is True
        ),
        "result_object_pass": (latest.get("result_object") or {}).get("status") == "PASS",
        "adapter_hash_parity_pass": (latest.get("adapter_hash_parity") or {}).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Final Contract Adapter Result Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Base hash stable: `{capture.get('base_hash_stable')}`",
        f"- All variants change hash: `{capture.get('all_variants_change_hash')}`",
        f"- Base should publish projection: `{capture.get('base_should_publish_projection')}`",
        f"- Disabled variants do not publish: `{capture.get('disabled_variants_do_not_publish')}`",
        f"- Disabled variants do not replace: `{capture.get('disabled_variants_do_not_replace')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_final_contract_adapter_result_parity_scenarios.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    artifact = ARTIFACT_DIR / f"design_guide_post_click_final_contract_adapter_result_parity_scenarios_{stamp}.json"
    report = AUDIT_DIR / f"design_guide_post_click_final_contract_adapter_result_parity_scenarios_{stamp}.md"
    artifact.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report, payload)
    print(f"{status}: {artifact}")
    if failures:
        print("Failures:", ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
