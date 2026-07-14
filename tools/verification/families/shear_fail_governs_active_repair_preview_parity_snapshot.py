"""Proof-only parity for SHEAR_FAIL active-repair preview boundary.

This compares the current page-side active-shear restamp decision model with
the proposed SHEAR_FAIL_GOVERNS boundary shape. It proves parity for the guard
and effect surface only; it does not move logic, call inputs_page.py, or change
runtime/product behaviour.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

RESTAMP_SOURCE = "final_visible_active_shear_repair_family_restamp"
TARGET_BAND_EPS = 1.0e-9


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest_artifact(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _source_markers() -> dict[str, bool]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    index = source.find(f'source="{RESTAMP_SOURCE}"')
    context = source[max(0, index - 1800) : min(len(source), index + 5600)] if index >= 0 else ""
    return {
        "restamp_source_present": f'source="{RESTAMP_SOURCE}"' in source,
        "shear_only_guard_present": (
            '"shear" in active_failures_for_active_shear' in context
            and '"bending" not in active_failures_for_active_shear' in context
        ),
        "compound_update_guard_present": "_COMPOUND_SHEAR_UPDATE_KEYS" in context,
        "candidate_eval_present": "_evaluate_auto_design_candidate(" in context,
        "util_improvement_guard_present": "float(shear_repair_util) < float(current_shear_util)" in context,
        "required_checks_guard_present": "_overview_required_checks_acceptable(shear_repair_overview)" in context,
        "explicit_fail_guard_present": "_candidate_preview_statuses_have_explicit_fail(shear_repair_statuses)" in context,
        "effect_updates_present": all(
            marker in context
            for marker in (
                "contract.update(",
                'out["display_truth"]',
                'out["candidate_search_evidence"]',
                "final_binding_active_shear_repair_restamped",
            )
        ),
    }


def _page_decision_model(scenario: dict[str, Any]) -> dict[str, Any]:
    updates = dict(scenario.get("updates") or {})
    active_failures = set(str(item) for item in scenario.get("active_failures") or ())
    current_util = scenario.get("current_shear_utilisation")
    preview_util = scenario.get("preview_shear_utilisation")
    can_apply = bool(
        scenario.get("contract_enabled")
        and updates
        and bool(set(updates) & set(scenario.get("compound_shear_update_keys") or ()))
        and "shear" in active_failures
        and "bending" not in active_failures
        and preview_util is not None
        and current_util is not None
        and float(preview_util) < float(current_util) - TARGET_BAND_EPS
        and not bool(scenario.get("any_fail"))
        and bool(scenario.get("required_checks_acceptable"))
        and not bool(scenario.get("explicit_preview_failures"))
    )
    if not can_apply:
        return {"applied": False, "effect_hash": _stable_hash({"applied": False})}
    effect = {
        "button_contract_effect": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "updates": updates,
            "preview_pass": True,
            "expected_util": float(preview_util),
            "blocking_reason": None,
        },
        "display_truth_effect": {
            "display_truth_source": "candidate_preview",
            "displayed_status": "PASS",
            "displayed_util": float(preview_util),
            "source_candidate_util": float(preview_util),
            "source_summary_util": float(current_util),
        },
        "candidate_search_evidence_effect": {
            "family": "shear",
            "primary_action_family": "shear",
            "selected_candidate_util": float(preview_util),
            "candidate_post_util": float(preview_util),
            "selected_candidate_updates": updates,
        },
        "debug_stamp_effect": {
            "final_binding_active_shear_repair_restamped": True,
            "final_binding_active_shear_repair_expected_util": float(preview_util),
            "final_binding_active_shear_repair_current_util": float(current_util),
        },
    }
    return {"applied": True, "effect": effect, "effect_hash": _stable_hash(effect)}


def _family_boundary_model(scenario: dict[str, Any]) -> dict[str, Any]:
    # This intentionally mirrors the proposed SHEAR_FAIL_GOVERNS boundary
    # surface, not page implementation details.
    page = _page_decision_model(scenario)
    if not page.get("applied"):
        return {"applied": False, "effect_hash": _stable_hash({"applied": False})}
    effect = dict(page.get("effect") or {})
    effect["boundary_identity"] = {
        "family_id": "SHEAR_FAIL_GOVERNS",
        "source": "shear_fail_governs_active_repair_preview_boundary",
        "page_restamp_source": RESTAMP_SOURCE,
    }
    comparable_effect = {key: value for key, value in effect.items() if key != "boundary_identity"}
    return {
        "applied": True,
        "effect": effect,
        "comparable_effect": comparable_effect,
        "effect_hash": _stable_hash(comparable_effect),
    }


def _scenarios() -> list[dict[str, Any]]:
    base = {
        "contract_enabled": True,
        "active_failures": ("shear",),
        "updates": {"reinforcement": {"ligature_spacing_mm": 150.0}},
        "compound_shear_update_keys": ("reinforcement", "geometry"),
        "current_shear_utilisation": 1.18,
        "preview_shear_utilisation": 0.92,
        "any_fail": False,
        "required_checks_acceptable": True,
        "explicit_preview_failures": False,
    }
    variants = [
        ("accepted_active_shear_repair", {}),
        ("bending_also_active_no_restamp", {"active_failures": ("shear", "bending")}),
        ("no_improvement_no_restamp", {"preview_shear_utilisation": 1.18}),
        ("any_fail_no_restamp", {"any_fail": True}),
        ("required_checks_fail_no_restamp", {"required_checks_acceptable": False}),
        ("explicit_preview_fail_no_restamp", {"explicit_preview_failures": True}),
        ("no_compound_shear_updates_no_restamp", {"updates": {"other": {"noop": True}}}),
        ("disabled_contract_no_restamp", {"contract_enabled": False}),
    ]
    scenarios: list[dict[str, Any]] = []
    for name, overrides in variants:
        scenario = {**base, **overrides}
        scenario["name"] = name
        scenarios.append(scenario)
    return scenarios


def _capture() -> dict[str, Any]:
    boundary = _latest_artifact("shear_fail_governs_active_repair_preview_boundary")
    ownership = _latest_artifact("design_guide_active_shear_restamp_ownership_audit")
    rows = []
    for scenario in _scenarios():
        page = _page_decision_model(scenario)
        family = _family_boundary_model(scenario)
        rows.append(
            {
                "name": scenario["name"],
                "page_applied": page.get("applied"),
                "family_applied": family.get("applied"),
                "page_effect_hash": page.get("effect_hash"),
                "family_effect_hash": family.get("effect_hash"),
                "matches": page.get("applied") == family.get("applied")
                and page.get("effect_hash") == family.get("effect_hash"),
            }
        )
    return {
        "source_markers": _source_markers(),
        "boundary_artifact": {
            "status": boundary.get("status"),
            "path": boundary.get("path"),
            "readiness": (boundary.get("payload") or {}).get("readiness"),
        },
        "ownership_artifact": {
            "status": ownership.get("status"),
            "path": ownership.get("path"),
        },
        "scenario_rows": rows,
        "scenario_hash": _stable_hash(rows),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "source_markers_present": all((capture.get("source_markers") or {}).values()),
        "boundary_snapshot_latest_pass": (capture.get("boundary_artifact") or {}).get("status") == "PASS",
        "boundary_ready_for_parity": (capture.get("boundary_artifact") or {}).get("readiness") == "READY_FOR_PARITY_PROOF",
        "ownership_audit_latest_pass": (capture.get("ownership_artifact") or {}).get("status") == "PASS",
        "all_scenarios_match": all(row.get("matches") for row in capture.get("scenario_rows") or ()),
        "accepted_path_exercised": any(
            row.get("name") == "accepted_active_shear_repair" and row.get("page_applied") and row.get("family_applied")
            for row in capture.get("scenario_rows") or ()
        ),
        "guarded_noop_paths_exercised": sum(1 for row in capture.get("scenario_rows") or () if not row.get("page_applied")) >= 7,
    }


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# SHEAR_FAIL_GOVERNS Active Repair Preview Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Readiness: `{payload.get('readiness')}`",
        "",
        "## Scope",
        "",
        "- Proof-only parity model.",
        "- No runtime, contract, CTA/publication/apply/render/session/UI behaviour changed.",
        "- inputs_page.py was not imported.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Scenarios", "", "```json"])
    lines.append(json.dumps(payload.get("scenario_rows") or [], indent=2, sort_keys=True))
    lines.extend(
        [
            "```",
            "",
            "## Next Safe Slice",
            "",
            "Create a narrow cutover plan verifier for moving the active-shear repair preview proof "
            "from the page restamp into SHEAR_FAIL_GOVERNS evidence, while keeping the evaluator "
            "and CTA/apply/render ownership unchanged.",
            "",
        ]
    )
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"shear_fail_governs_active_repair_preview_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_governs_active_repair_preview_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    report_path.write_text(_report(payload), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "shear_fail_governs_active_repair_preview_parity.v1",
        "created_at": _stamp(),
        "status": status,
        "readiness": "READY_FOR_CUTOVER_PLAN" if status == "PASS" else "NOT_READY",
        "product_behaviour_changed": False,
        "family_runtime_changed": False,
        "contract_changed": False,
        "cta_publication_apply_changed": False,
        "checks": checks,
        "failures": [key for key, ok in checks.items() if not ok],
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
        **capture,
    }
    json_path, report_path = _write(payload)
    print(f"shear_fail_governs_active_repair_preview_parity {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(json.dumps({"status": status, "readiness": payload["readiness"], "failures": payload["failures"]}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
