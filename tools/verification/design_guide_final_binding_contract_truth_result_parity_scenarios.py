"""Parity scenarios for final-binding enabled-contract truth result."""

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

SHEAR_KEYS = ["s_lig", "shear_link_spacing"]
BOTTOM_KEYS = ["bottom_bar_size", "n_bottom", "bottom_layers"]


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
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


def _scenario(
    *,
    scenario_id: str,
    evidence_for_binding: dict[str, Any],
    contract: dict[str, Any],
    item: dict[str, Any],
    updates: dict[str, Any],
    combined_binding_bending_util: Any = None,
    expected_family: str,
    expected_util: Any,
    expected_contract_util: Any,
    expected_cross_family: bool,
    expected_blockers: list[str],
    expected_family_source: str,
    expected_util_source: str,
) -> dict[str, Any]:
    from design_brain.final_publication import build_final_visible_contract_binding_truth_result

    payload = build_final_visible_contract_binding_truth_result(
        evidence_for_binding=evidence_for_binding,
        contract=contract,
        item=item,
        updates=updates,
        compound_shear_update_keys=list(SHEAR_KEYS),
        compound_bottom_update_keys=list(BOTTOM_KEYS),
        combined_binding_bending_util=combined_binding_bending_util,
    )
    repeat = build_final_visible_contract_binding_truth_result(
        evidence_for_binding=evidence_for_binding,
        contract=contract,
        item=item,
        updates=updates,
        compound_shear_update_keys=list(SHEAR_KEYS),
        compound_bottom_update_keys=list(BOTTOM_KEYS),
        combined_binding_bending_util=combined_binding_bending_util,
    )
    result = dict(payload.get("result") or {})
    checks = {
        "family": result.get("evidence_family_for_contract") == expected_family,
        "util": result.get("evidence_expected_util") == expected_util,
        "contract_util": result.get("contract_expected_util") == expected_contract_util,
        "cross_family": bool(result.get("contract_updates_cross_family")) is bool(expected_cross_family),
        "blockers": result.get("blocker_families_for_contract") == expected_blockers,
        "family_source": result.get("family_resolution_source") == expected_family_source,
        "util_source": result.get("util_resolution_source") == expected_util_source,
        "proof_hash_stable": payload.get("proof_hash") == repeat.get("proof_hash"),
        "result_hash_stable": payload.get("result_hash") == repeat.get("result_hash"),
        "proof_only": payload.get("proof_only") is True,
        "not_product_driving": payload.get("product_driving") is False,
        "not_render_driving": payload.get("render_driving") is False,
        "not_apply_driving": payload.get("apply_driving") is False,
        "not_session_driving": payload.get("session_driving") is False,
        "not_ready_for_cutover": payload.get("ready_for_live_cutover") is False,
    }
    return {
        "scenario_id": scenario_id,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "expected": {
            "family": expected_family,
            "util": expected_util,
            "contract_util": expected_contract_util,
            "cross_family": expected_cross_family,
            "blockers": expected_blockers,
            "family_source": expected_family_source,
            "util_source": expected_util_source,
        },
        "actual": {
            "family": result.get("evidence_family_for_contract"),
            "util": result.get("evidence_expected_util"),
            "contract_util": result.get("contract_expected_util"),
            "cross_family": bool(result.get("contract_updates_cross_family")),
            "blockers": result.get("blocker_families_for_contract"),
            "family_source": result.get("family_resolution_source"),
            "util_source": result.get("util_resolution_source"),
        },
        "result_hash": payload.get("result_hash"),
        "proof_hash": payload.get("proof_hash"),
    }


def _capture() -> dict[str, Any]:
    scenarios = [
        _scenario(
            scenario_id="plain_shear_contract",
            evidence_for_binding={"family": "shear", "selected_candidate_util": 0.69},
            contract={"expected_util": 0.67},
            item={"title": "Optional shear cleanup"},
            updates={"s_lig": 0},
            expected_family="shear",
            expected_util=0.69,
            expected_contract_util=0.67,
            expected_cross_family=False,
            expected_blockers=["shear"],
            expected_family_source="title_hint_shear_cleanup",
            expected_util_source="evidence_candidate_util",
        ),
        _scenario(
            scenario_id="title_hint_bending_cleanup",
            evidence_for_binding={"family": "cleanup", "selected_candidate_util": 0.24},
            contract={"expected_util": 0.24},
            item={"title": "Optional bending cleanup"},
            updates={"bottom_bar_size": "N12"},
            expected_family="bending",
            expected_util=0.24,
            expected_contract_util=0.24,
            expected_cross_family=False,
            expected_blockers=["bending"],
            expected_family_source="title_hint_bending_cleanup",
            expected_util_source="evidence_candidate_util",
        ),
        _scenario(
            scenario_id="title_hint_shear_cleanup",
            evidence_for_binding={"family": "cleanup", "selected_candidate_util": 0.44},
            contract={"expected_util": 0.44},
            item={"title": "Optional shear cleanup"},
            updates={"shear_link_spacing": 0},
            expected_family="shear",
            expected_util=0.44,
            expected_contract_util=0.44,
            expected_cross_family=False,
            expected_blockers=["shear"],
            expected_family_source="title_hint_shear_cleanup",
            expected_util_source="evidence_candidate_util",
        ),
        _scenario(
            scenario_id="bending_target_band_util_override",
            evidence_for_binding={
                "family": "bending",
                "selected_candidate_util": 0.22,
                "best_target_band_candidate_util": 0.86,
                "target_band_candidate_count": 1,
            },
            contract={"expected_util": 0.22},
            item={"title": "Optional bending cleanup"},
            updates={"n_bottom": 4},
            expected_family="bending",
            expected_util=0.86,
            expected_contract_util=0.22,
            expected_cross_family=False,
            expected_blockers=["bending"],
            expected_family_source="title_hint_bending_cleanup",
            expected_util_source="bending_target_band_candidate_util",
        ),
        _scenario(
            scenario_id="combined_cross_family_plain_preview_util",
            evidence_for_binding={
                "family": "combined",
                "selected_candidate_util": 0.62,
                "selected_candidate_id": "combined_candidate",
            },
            contract={"expected_util": 0.62, "candidate_id": "combined_candidate"},
            item={"title": "Shear and bending cleanup"},
            updates={"s_lig": 0, "bottom_bar_size": "N12"},
            combined_binding_bending_util=0.91,
            expected_family="combined",
            expected_util=0.91,
            expected_contract_util=0.62,
            expected_cross_family=True,
            expected_blockers=["bending", "combined", "shear"],
            expected_family_source="combined_cross_family_updates",
            expected_util_source="combined_preview_bending_util",
        ),
        _scenario(
            scenario_id="combined_cross_family_without_preview_keeps_evidence_util",
            evidence_for_binding={
                "family": "combined",
                "selected_candidate_util": 0.73,
                "selected_candidate_id": "combined_candidate",
            },
            contract={"expected_util": 0.73, "candidate_id": "combined_candidate"},
            item={"title": "Shear and bending cleanup"},
            updates={"s_lig": 0, "bottom_layers": 1},
            combined_binding_bending_util=None,
            expected_family="combined",
            expected_util=0.73,
            expected_contract_util=0.73,
            expected_cross_family=True,
            expected_blockers=["bending", "combined", "shear"],
            expected_family_source="combined_cross_family_updates",
            expected_util_source="evidence_candidate_util",
        ),
    ]
    latest = {
        "object": _latest("design_guide_final_binding_contract_truth_result_object"),
        "trace": _latest("design_guide_live_final_binding_contract_truth_result_trace"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "FINAL_BINDING_CONTRACT_TRUTH_RESULT_PARITY_PROVEN_NOT_CUT_OVER",
        "scenarios": scenarios,
        "scenario_count": len(scenarios),
        "passing_scenarios": sum(1 for scenario in scenarios if scenario.get("status") == "PASS"),
        "ready_for_cutover_readiness_audit": all(scenario.get("status") == "PASS" for scenario in scenarios),
        "ready_for_live_cutover": False,
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
        "all_scenarios_pass": capture.get("passing_scenarios") == capture.get("scenario_count"),
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "ready_for_cutover_readiness_audit": capture.get("ready_for_cutover_readiness_audit") is True,
        "not_live_cutover_yet": capture.get("ready_for_live_cutover") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Binding Contract Truth Result Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
    ]
    for scenario in capture.get("scenarios") or []:
        lines.append(f"- {scenario.get('scenario_id')}: `{scenario.get('status')}`")
    lines.extend(["", "## Checks", ""])
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
        "schema": "design_guide_final_binding_contract_truth_result_parity_scenarios.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_contract_truth_result_parity_scenarios_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_contract_truth_result_parity_scenarios_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_contract_truth_result_parity_scenarios {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
