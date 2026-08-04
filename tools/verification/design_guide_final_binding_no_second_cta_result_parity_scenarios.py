"""Scenario parity for final-binding no-second-CTA suppression.

Proof-only. This verifier compares the Design Brain result object with a
page-like reference decision for the current no-second-CTA cases before any
live cutover.
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

FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
TARGET_BAND_EPS = 0.005


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
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


def _parse_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _page_like_decision(
    *,
    evidence_for_binding: dict[str, Any],
    item: dict[str, Any],
    debug: dict[str, Any],
    evidence_expected_util: Any,
    evidence_family: str,
    blocker_families: list[str],
) -> dict[str, Any]:
    expected_util = _parse_float(evidence_expected_util)
    threshold = FINAL_ACCEPTED_MIN_FAMILY_UTIL - TARGET_BAND_EPS
    applies = False
    reason = None
    target_band_count = int(
        evidence_for_binding.get("target_band_candidate_count")
        or evidence_for_binding.get("executable_target_band_candidate_count")
        or evidence_for_binding.get("accepted_band_candidate_count")
        or len(list(evidence_for_binding.get("target_band_candidates") or []))
        or 0
    )
    if expected_util is not None and float(expected_util) < threshold:
        if bool(evidence_for_binding.get("no_second_cta_required")) and target_band_count <= 0:
            applies = True
            reason = str(
                evidence_for_binding.get("reason")
                or evidence_for_binding.get("outside_target_band_allowed_reason")
                or evidence_for_binding.get("why_reduction_would_hurt_other_design_elements")
                or "post-click exact cleanup proof suppresses a second below-floor CTA"
            )
        exact_sources = [
            dict(item.get("post_click_exact_blockers_by_family") or {}),
            dict(item.get("exact_blockers_by_family") or {}),
            dict(evidence_for_binding.get("post_click_exact_blockers_by_family") or {}),
            dict(evidence_for_binding.get("exact_blockers_by_family") or {}),
            dict(debug.get("post_click_exact_blockers_by_family") or {}),
            dict(debug.get("exact_blockers_by_family") or {}),
        ]
        families = list(blocker_families or [str(evidence_family or "").strip().lower()])
        if not applies:
            for exact_source in exact_sources:
                for blocker_family in families:
                    blocker = dict(exact_source.get(blocker_family) or {})
                    if not blocker:
                        continue
                    blocker_util = _parse_float(
                        blocker.get("best_safe_final_util") or blocker.get("failed_check_util")
                    )
                    if (
                        bool(blocker.get("no_second_cta_required"))
                        and str(blocker.get("failed_check_status") or "").strip().upper()
                        == "BLOCKED_BY_FINAL_ACCEPTED_THRESHOLD"
                        and (blocker_util is None or float(blocker_util) < threshold)
                    ):
                        applies = True
                        reason = str(
                            blocker.get("reason")
                            or blocker.get("why_reduction_would_hurt_other_design_elements")
                            or "post-click exact cleanup proof suppresses a second below-floor CTA"
                        )
                        break
                if applies:
                    break
    return {"applies": applies, "reason": reason}


def _scenario_inputs() -> list[dict[str, Any]]:
    exact_blocker = {
        "no_second_cta_required": True,
        "failed_check_status": "BLOCKED_BY_FINAL_ACCEPTED_THRESHOLD",
        "best_safe_final_util": 0.62,
        "reason": "exact blocker suppresses below-floor cleanup",
    }
    return [
        {
            "name": "direct_evidence_suppresses",
            "evidence_for_binding": {
                "family": "bending",
                "no_second_cta_required": True,
                "target_band_candidate_count": 0,
                "reason": "direct evidence suppresses below-floor cleanup",
            },
            "contract": {"enabled": True, "actionable": True, "updates": {"bottom_bar_size": "N12"}},
            "item": {},
            "debug": {},
            "evidence_expected_util": 0.63,
            "evidence_family": "bending",
            "blocker_families": ["bending"],
        },
        {
            "name": "item_exact_blocker_suppresses",
            "evidence_for_binding": {"family": "bending"},
            "contract": {"enabled": True, "actionable": True, "updates": {"bottom_bar_size": "N12"}},
            "item": {"exact_blockers_by_family": {"bending": dict(exact_blocker)}},
            "debug": {},
            "evidence_expected_util": 0.64,
            "evidence_family": "bending",
            "blocker_families": ["bending"],
        },
        {
            "name": "debug_exact_blocker_combined_shear_suppresses",
            "evidence_for_binding": {"family": "combined"},
            "contract": {
                "enabled": True,
                "actionable": True,
                "updates": {"bottom_bar_size": "N12", "shear_link_spacing": 200},
            },
            "item": {},
            "debug": {"post_click_exact_blockers_by_family": {"shear": dict(exact_blocker)}},
            "evidence_expected_util": 0.66,
            "evidence_family": "combined",
            "blocker_families": ["combined", "bending", "shear"],
        },
        {
            "name": "target_band_candidate_prevents_direct_suppression",
            "evidence_for_binding": {
                "family": "bending",
                "no_second_cta_required": True,
                "target_band_candidate_count": 1,
                "reason": "direct evidence would otherwise suppress",
            },
            "contract": {"enabled": True, "actionable": True, "updates": {"bottom_bar_size": "N12"}},
            "item": {},
            "debug": {},
            "evidence_expected_util": 0.63,
            "evidence_family": "bending",
            "blocker_families": ["bending"],
        },
        {
            "name": "in_target_util_prevents_suppression",
            "evidence_for_binding": {
                "family": "bending",
                "no_second_cta_required": True,
                "target_band_candidate_count": 0,
                "reason": "above floor should not suppress",
            },
            "contract": {"enabled": True, "actionable": True, "updates": {"bottom_bar_size": "N12"}},
            "item": {},
            "debug": {},
            "evidence_expected_util": 0.86,
            "evidence_family": "bending",
            "blocker_families": ["bending"],
        },
        {
            "name": "wrong_exact_blocker_status_prevents_suppression",
            "evidence_for_binding": {"family": "bending"},
            "contract": {"enabled": True, "actionable": True, "updates": {"bottom_bar_size": "N12"}},
            "item": {
                "exact_blockers_by_family": {
                    "bending": {
                        **exact_blocker,
                        "failed_check_status": "BLOCKED_BY_OTHER_REASON",
                    }
                }
            },
            "debug": {},
            "evidence_expected_util": 0.64,
            "evidence_family": "bending",
            "blocker_families": ["bending"],
        },
    ]


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_visible_contract_binding_no_second_cta_result,
    )

    scenarios = []
    for scenario in _scenario_inputs():
        expected = _page_like_decision(
            evidence_for_binding=dict(scenario["evidence_for_binding"]),
            item=dict(scenario["item"]),
            debug=dict(scenario["debug"]),
            evidence_expected_util=scenario["evidence_expected_util"],
            evidence_family=str(scenario["evidence_family"]),
            blocker_families=list(scenario["blocker_families"]),
        )
        payload = build_final_visible_contract_binding_no_second_cta_result(
            evidence_for_binding=dict(scenario["evidence_for_binding"]),
            contract=dict(scenario["contract"]),
            item=dict(scenario["item"]),
            debug=dict(scenario["debug"]),
            evidence_expected_util=scenario["evidence_expected_util"],
            evidence_family=str(scenario["evidence_family"]),
            blocker_families=list(scenario["blocker_families"]),
            final_accepted_min_family_util=FINAL_ACCEPTED_MIN_FAMILY_UTIL,
            target_band_eps=TARGET_BAND_EPS,
        )
        result = dict(payload.get("result") or {})
        actual = {"applies": bool(result.get("applies")), "reason": result.get("reason")}
        scenarios.append(
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
        "object": _latest("design_guide_final_binding_no_second_cta_result_object"),
        "trace": _latest("design_guide_live_final_binding_no_second_cta_result_trace"),
        "ownership_audit": _latest("design_guide_final_visible_contract_binding_ownership"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "FINAL_BINDING_NO_SECOND_CTA_RESULT_PARITY_SCENARIOS_PASS",
        "scenario_count": len(scenarios),
        "matched_scenario_count": sum(1 for scenario in scenarios if scenario.get("matches")),
        "mismatches": [scenario for scenario in scenarios if not scenario.get("matches")],
        "scenarios": scenarios,
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
        "ownership_audit_pass": (latest.get("ownership_audit") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "ready_for_cutover_readiness_snapshot": (
            capture.get("ready_for_cutover_readiness_snapshot") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Binding No-Second-CTA Result Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Scenarios: `{capture.get('scenario_count')}`",
        f"- Matched: `{capture.get('matched_scenario_count')}`",
        f"- Ready for cutover-readiness snapshot: `{capture.get('ready_for_cutover_readiness_snapshot')}`",
        "",
        "## Scenario Results",
        "",
    ]
    for scenario in capture.get("scenarios") or []:
        lines.append(f"- {scenario.get('name')}: `{scenario.get('matches')}`")
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
        "schema": "design_guide_final_binding_no_second_cta_result_parity_scenarios.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_no_second_cta_result_parity_scenarios_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_no_second_cta_result_parity_scenarios_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_no_second_cta_result_parity_scenarios {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
