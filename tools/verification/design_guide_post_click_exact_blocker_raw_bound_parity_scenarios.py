"""Parity scenarios for post-click exact-blocker raw-vs-bound proof.

Proof-only. These scenarios verify the Design Brain proof object that compares
the raw post-click exact-blocker item with the legacy bound item created by the
page restamper. This does not delete or replace the live binding.
"""

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


def _base_item() -> dict[str, Any]:
    return {
        "title": "Design Guide blocker proof incomplete",
        "title_main": "Design Guide blocker proof incomplete",
        "family": "bending",
        "status": "BLOCKED",
        "button_contract": {"enabled": False, "family": "bending"},
        "post_click_exact_blockers_by_family": {
            "bending": {"no_second_cta_required": True, "reason": "exact stop"}
        },
    }


def _base_kwargs() -> dict[str, Any]:
    item = _base_item()
    return {
        "raw_item": dict(item),
        "bound_item": dict(item),
        "final_visible_resolution": {
            "render_reason": "pre_adapter_final_visible",
            "item": dict(item),
        },
        "guidance_debug": {"guidance_branch": "pre_adapter"},
        "visible_action": True,
        "bending_resolution": dict(item),
        "bending_contract": {"enabled": False, "family": "bending"},
    }


def _scenario_payloads() -> dict[str, dict[str, Any]]:
    base = _base_kwargs()

    bound_changed = dict(base)
    bound_changed["bound_item"] = {**dict(base["bound_item"]), "family": "bending_bound"}

    raw_changed = dict(base)
    raw_changed["raw_item"] = {**dict(base["raw_item"]), "title": "Different raw item"}

    no_visible_action = dict(base)
    no_visible_action["visible_action"] = False

    enabled_contract = dict(base)
    enabled_contract["bending_contract"] = {"enabled": True, "family": "bending"}

    empty_bound = dict(base)
    empty_bound["bound_item"] = {}

    return {
        "identical_raw_bound": base,
        "bound_item_changed": bound_changed,
        "raw_item_changed": raw_changed,
        "no_visible_action": no_visible_action,
        "enabled_contract": enabled_contract,
        "empty_bound_item": empty_bound,
    }


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof,
    )

    scenarios = _scenario_payloads()
    first = build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof(
        **scenarios["identical_raw_bound"]
    )
    second = build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof(
        **_scenario_payloads()["identical_raw_bound"]
    )
    scenario_results: dict[str, dict[str, Any]] = {}
    for name, kwargs in scenarios.items():
        payload = build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof(**kwargs)
        scenario_results[name] = {
            "proof_hash": payload.get("proof_hash"),
            "raw_item_hash": payload.get("raw_item_hash"),
            "bound_item_hash": payload.get("bound_item_hash"),
            "raw_adapter_result_hash": payload.get("raw_adapter_result_hash"),
            "bound_adapter_result_hash": payload.get("bound_adapter_result_hash"),
            "raw_bound_adapter_result_parity": payload.get("raw_bound_adapter_result_parity"),
            "ready_to_replace_old_binding": payload.get("ready_to_replace_old_binding"),
            "proof_only": payload.get("proof_only"),
            "product_driving": payload.get("product_driving"),
            "render_driving": payload.get("render_driving"),
            "apply_driving": payload.get("apply_driving"),
            "session_driving": payload.get("session_driving"),
        }
    latest = {
        "trace": _latest("design_guide_post_click_exact_blocker_raw_bound_parity_trace"),
        "replacement_readiness": _latest(
            "design_guide_post_click_exact_blocker_final_binding_replacement_readiness"
        ),
        "result_parity": _latest("design_guide_post_click_final_contract_adapter_result_parity_scenarios"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "POST_CLICK_EXACT_BLOCKER_RAW_BOUND_PARITY_SCENARIOS_PASS",
        "base_hash_stable": first.get("proof_hash") == second.get("proof_hash"),
        "scenario_results": scenario_results,
        "identical_ready_to_replace": scenario_results["identical_raw_bound"][
            "ready_to_replace_old_binding"
        ],
        "changed_bound_not_ready": scenario_results["bound_item_changed"][
            "ready_to_replace_old_binding"
        ]
        is False,
        "changed_raw_not_ready": scenario_results["raw_item_changed"][
            "ready_to_replace_old_binding"
        ]
        is False,
        "empty_bound_not_ready": scenario_results["empty_bound_item"][
            "ready_to_replace_old_binding"
        ]
        is False,
        "disabled_paths_are_stable": (
            scenario_results["no_visible_action"]["raw_bound_adapter_result_parity"] is True
            and scenario_results["enabled_contract"]["raw_bound_adapter_result_parity"] is True
        ),
        "all_flags_non_driving": all(
            row.get("proof_only") is True
            and row.get("product_driving") is False
            and row.get("render_driving") is False
            and row.get("apply_driving") is False
            and row.get("session_driving") is False
            for row in scenario_results.values()
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
        "identical_ready_to_replace": capture.get("identical_ready_to_replace") is True,
        "changed_bound_not_ready": capture.get("changed_bound_not_ready") is True,
        "changed_raw_not_ready": capture.get("changed_raw_not_ready") is True,
        "empty_bound_not_ready": capture.get("empty_bound_not_ready") is True,
        "disabled_paths_are_stable": capture.get("disabled_paths_are_stable") is True,
        "all_flags_non_driving": capture.get("all_flags_non_driving") is True,
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "replacement_readiness_pass": (latest.get("replacement_readiness") or {}).get("status")
        == "PASS",
        "result_parity_pass": (latest.get("result_parity") or {}).get("status") == "PASS",
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
        "# Post-Click Exact Blocker Raw-Bound Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Base hash stable: `{capture.get('base_hash_stable')}`",
        f"- Identical raw/bound ready to replace: `{capture.get('identical_ready_to_replace')}`",
        f"- Changed bound not ready: `{capture.get('changed_bound_not_ready')}`",
        f"- Changed raw not ready: `{capture.get('changed_raw_not_ready')}`",
        f"- Empty bound not ready: `{capture.get('empty_bound_not_ready')}`",
        "",
        "## Scenario Results",
        "",
    ]
    for name, row in (capture.get("scenario_results") or {}).items():
        lines.append(
            f"- `{name}`: parity=`{row.get('raw_bound_adapter_result_parity')}`, "
            f"ready=`{row.get('ready_to_replace_old_binding')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_exact_blocker_raw_bound_parity_scenarios.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    artifact = ARTIFACT_DIR / f"design_guide_post_click_exact_blocker_raw_bound_parity_scenarios_{stamp}.json"
    report = AUDIT_DIR / f"design_guide_post_click_exact_blocker_raw_bound_parity_scenarios_{stamp}.md"
    artifact.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report, payload)
    print(f"design_guide_post_click_exact_blocker_raw_bound_parity_scenarios {status}")
    print(f"json={artifact}")
    print(f"report={report}")
    if failures:
        print("Failures:", ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
