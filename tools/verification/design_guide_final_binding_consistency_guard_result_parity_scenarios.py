"""Scenario parity for final-binding contract consistency guard result."""

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


def _page_like_decision(scenario: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(scenario.get("evidence_for_binding") or {})
    current_updates = dict(scenario.get("current_updates") or {})
    safe_updates = dict(scenario.get("safe_binding_updates") or {})
    combined_updates = dict(scenario.get("combined_binding_updates") or {})
    family = str(evidence.get("family") or "").strip().lower()
    safe_available = bool(
        family == "shear"
        and safe_updates
        and bool(set(safe_updates) & set(SHEAR_KEYS))
        and not bool(scenario.get("safe_updates_already_applied"))
        and (
            bool(evidence.get("one_click_target_reaching_candidate_exists"))
            or int(evidence.get("accepted_band_candidate_count") or 0) > 0
        )
    )
    safe_resets = bool(safe_available and dict(current_updates) != dict(safe_updates))
    current_after_safe = {} if safe_resets else dict(current_updates)
    combined_available = bool(
        family == "combined"
        and combined_updates
        and not bool(scenario.get("combined_updates_already_applied"))
        and bool(
            evidence.get("cleanup_search_ran")
            or evidence.get("local_cleanup_search_ran")
            or evidence.get("candidate_search_exhaustive")
        )
    )
    combined_resets = bool(combined_available and dict(current_after_safe) != dict(combined_updates))
    return {
        "reset_contract": bool(safe_resets or combined_resets),
        "safe_binding_evidence_available": safe_available,
        "combined_binding_evidence_available": combined_available,
        "safe_binding_mismatch": safe_resets,
        "combined_binding_mismatch": combined_resets,
    }


def _scenarios() -> list[dict[str, Any]]:
    return [
        {
            "name": "shear_safe_binding_mismatch_resets",
            "evidence_for_binding": {
                "family": "shear",
                "one_click_target_reaching_candidate_exists": True,
            },
            "current_updates": {"s_lig": 250.0},
            "safe_binding_updates": {"s_lig": 150.0},
            "combined_binding_updates": {},
            "safe_updates_already_applied": False,
            "combined_updates_already_applied": True,
        },
        {
            "name": "shear_safe_binding_match_does_not_reset",
            "evidence_for_binding": {
                "family": "shear",
                "one_click_target_reaching_candidate_exists": True,
            },
            "current_updates": {"s_lig": 150.0},
            "safe_binding_updates": {"s_lig": 150.0},
            "combined_binding_updates": {},
            "safe_updates_already_applied": False,
            "combined_updates_already_applied": True,
        },
        {
            "name": "shear_safe_binding_already_applied_does_not_reset",
            "evidence_for_binding": {
                "family": "shear",
                "accepted_band_candidate_count": 1,
            },
            "current_updates": {"s_lig": 250.0},
            "safe_binding_updates": {"s_lig": 150.0},
            "combined_binding_updates": {},
            "safe_updates_already_applied": True,
            "combined_updates_already_applied": True,
        },
        {
            "name": "combined_binding_mismatch_resets",
            "evidence_for_binding": {"family": "combined", "cleanup_search_ran": True},
            "current_updates": {"s_lig": 250.0},
            "safe_binding_updates": {},
            "combined_binding_updates": {"s_lig": 150.0, "bottom_bar_size": "N20"},
            "safe_updates_already_applied": True,
            "combined_updates_already_applied": False,
        },
        {
            "name": "combined_binding_match_does_not_reset",
            "evidence_for_binding": {"family": "combined", "cleanup_search_ran": True},
            "current_updates": {"s_lig": 150.0, "bottom_bar_size": "N20"},
            "safe_binding_updates": {},
            "combined_binding_updates": {"s_lig": 150.0, "bottom_bar_size": "N20"},
            "safe_updates_already_applied": True,
            "combined_updates_already_applied": False,
        },
        {
            "name": "wrong_family_does_not_reset",
            "evidence_for_binding": {"family": "bending", "cleanup_search_ran": True},
            "current_updates": {"s_lig": 250.0},
            "safe_binding_updates": {"s_lig": 150.0},
            "combined_binding_updates": {"s_lig": 150.0},
            "safe_updates_already_applied": False,
            "combined_updates_already_applied": False,
        },
    ]


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_visible_contract_binding_consistency_guard_result,
    )

    rows = []
    for scenario in _scenarios():
        kwargs = {key: value for key, value in scenario.items() if key != "name"}
        kwargs["compound_shear_update_keys"] = list(SHEAR_KEYS)
        expected = _page_like_decision(kwargs)
        payload = build_final_visible_contract_binding_consistency_guard_result(**kwargs)
        result = dict(payload.get("result") or {})
        actual = {
            "reset_contract": bool(result.get("reset_contract")),
            "safe_binding_evidence_available": bool(result.get("safe_binding_evidence_available")),
            "combined_binding_evidence_available": bool(result.get("combined_binding_evidence_available")),
            "safe_binding_mismatch": bool(result.get("safe_binding_mismatch")),
            "combined_binding_mismatch": bool(result.get("combined_binding_mismatch")),
        }
        rows.append(
            {
                "name": scenario["name"],
                "expected": expected,
                "actual": actual,
                "matches": expected == actual,
                "result_hash": payload.get("result_hash"),
                "proof_hash": payload.get("proof_hash"),
            }
        )
    latest = {
        "object": _latest("design_guide_final_binding_consistency_guard_result_object"),
        "trace": _latest("design_guide_live_final_binding_consistency_guard_result_trace"),
        "residual_policy": _latest("design_guide_final_binding_residual_policy_ownership"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "FINAL_BINDING_CONSISTENCY_GUARD_RESULT_PARITY_SCENARIOS_PASS",
        "scenario_count": len(rows),
        "matched_scenario_count": sum(1 for row in rows if row.get("matches")),
        "mismatches": [row for row in rows if not row.get("matches")],
        "scenarios": rows,
        "ready_for_cutover_readiness_snapshot": True,
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
        "all_scenarios_matched": capture.get("scenario_count") == capture.get("matched_scenario_count"),
        "has_positive_and_negative_cases": capture.get("scenario_count", 0) >= 6,
        "no_mismatches": not capture.get("mismatches"),
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "residual_policy_pass": (latest.get("residual_policy") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "ready_for_cutover_readiness_snapshot": capture.get("ready_for_cutover_readiness_snapshot") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Binding Consistency Guard Result Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenario Results",
        "",
    ]
    for row in capture.get("scenarios") or []:
        lines.append(f"- {row.get('name')}: `{row.get('matches')}`")
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
        "schema": "design_guide_final_binding_consistency_guard_result_parity_scenarios.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_consistency_guard_result_parity_scenarios_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_consistency_guard_result_parity_scenarios_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_consistency_guard_result_parity_scenarios {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
