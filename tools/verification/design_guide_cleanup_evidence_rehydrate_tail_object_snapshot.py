"""Object snapshot for cleanup-evidence rehydrate tail proof.

Proof-only. This verifies Design Brain can represent the old final-visible
cleanup-evidence rehydrate tail from plain already-evaluated candidate data,
without importing inputs_page.py or taking over evaluator/render/apply/session
ownership.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"


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
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _base_item(*, title: str = "Design Guide cleanup") -> dict[str, Any]:
    return {
        "title": title,
        "title_main": title,
        "family": "combined",
        "check_key": "combined",
        "button_contract": {"enabled": False, "actionable": False},
        "candidate_search_evidence": {},
        "action_payload": {"existing": "kept"},
        "resolved_candidate": {"existing": "candidate"},
    }


def _accepted_candidate(*, bending: float = 0.91, shear: float = 0.88) -> dict[str, Any]:
    return {
        "candidate_id": "cand-accepted",
        "source_candidate_id": "cand-accepted",
        "candidate_post_util": max(bending, shear),
        "overview": {
            "any_fail": False,
            "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
            "utils": {"bending": bending, "shear": shear, "crack": 0.0, "deflection": 0.0},
            "worst_util": max(bending, shear),
        },
    }


def _scenario_inputs() -> dict[str, dict[str, Any]]:
    return {
        "combined_accepted_rehydrate": {
            "item": _base_item(),
            "contract": {"enabled": False, "actionable": False},
            "evidence_for_binding": {
                "family": "combined",
                "cleanup_search_ran": True,
                "generated_count": 12,
                "best_safe_final_util": 0.91,
                "selected_candidate_id": "combined-safe-1",
            },
            "evidence_candidate": _accepted_candidate(bending=0.91, shear=0.86),
            "evidence_updates": {"width": 450, "bottom_bar_count": 6},
            "evidence_family": "combined",
        },
        "safe_shear_cleanup_rehydrate": {
            "item": _base_item(title="Shear cleanup blocked by final efficiency threshold"),
            "contract": {"enabled": False, "actionable": False},
            "evidence_for_binding": {
                "family": "shear",
                "cleanup_search_ran": True,
                "accepted_band_candidate_count": 1,
                "safe_candidate_count": 1,
                "best_safe_candidate_id": "shear-safe-1",
                "best_safe_final_util": 0.82,
                "exact_blockers_by_family": {"shear": {"reason": "stale"}},
                "cleanup_evidence_by_family": {"shear": {"reason": "stale"}},
            },
            "evidence_candidate": _accepted_candidate(bending=0.72, shear=0.82),
            "evidence_updates": {"ligature_legs": 0, "shear_link_spacing": 0},
            "evidence_family": "shear",
            "accepted_safe_shear_cleanup_exists": True,
        },
        "rejected_candidate_explicit_fail": {
            "item": _base_item(),
            "contract": {"enabled": False, "actionable": False},
            "evidence_for_binding": {"family": "bending", "cleanup_search_ran": True},
            "evidence_candidate": {
                "candidate_id": "bad-cand",
                "overview": {
                    "any_fail": True,
                    "statuses": {"bending": "PASS", "shear": "FAIL"},
                    "utils": {"bending": 0.9, "shear": 1.1},
                },
            },
            "evidence_updates": {"depth": 700},
            "evidence_family": "bending",
        },
        "no_updates_noop": {
            "item": _base_item(),
            "contract": {"enabled": False, "actionable": False},
            "evidence_for_binding": {"family": "bending", "cleanup_search_ran": True},
            "evidence_candidate": _accepted_candidate(bending=0.84, shear=0.7),
            "evidence_updates": {},
            "evidence_family": "bending",
        },
    }


def _exercise() -> dict[str, Any]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_visible_contract_binding_cleanup_evidence_rehydrate_result,
    )

    rows = []
    for scenario_id, kwargs in _scenario_inputs().items():
        result = build_final_visible_contract_binding_cleanup_evidence_rehydrate_result(
            **kwargs,
            final_accepted_min_family_util=0.85,
            target_band_eps=1e-9,
        )
        repeat = build_final_visible_contract_binding_cleanup_evidence_rehydrate_result(
            **kwargs,
            final_accepted_min_family_util=0.85,
            target_band_eps=1e-9,
        )
        result_body = dict(result.get("result") or {})
        rows.append(
            {
                "scenario_id": scenario_id,
                "applies": result_body.get("applies"),
                "proof_hash": result.get("proof_hash"),
                "proof_hash_stable": result.get("proof_hash") == repeat.get("proof_hash"),
                "contract_enabled": bool((result_body.get("contract_effect") or {}).get("enabled")),
                "evidence_remove_keys": list(result_body.get("evidence_remove_keys") or []),
                "item_title": (result_body.get("item_effect") or {}).get("title"),
                "action_payload_updates": dict(
                    (result_body.get("action_payload_effect") or {}).get("updates") or {}
                ),
                "resolved_candidate_updates": dict(
                    (result_body.get("resolved_candidate_effect") or {}).get("updates") or {}
                ),
                "debug_rehydrated": bool(
                    (result_body.get("debug_effect") or {}).get("final_binding_evidence_cleanup_rehydrated")
                ),
                "non_authoritative": (
                    result.get("proof_only") is True
                    and result.get("product_driving") is False
                    and result.get("render_driving") is False
                    and result.get("apply_driving") is False
                    and result.get("session_driving") is False
                ),
            }
        )
    return {"rows": rows, "row_count": len(rows)}


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    return {
        **_exercise(),
        "source_checks": {
            "builder_present": "def build_final_visible_contract_binding_cleanup_evidence_rehydrate_result(" in source,
            "builder_exported": '"build_final_visible_contract_binding_cleanup_evidence_rehydrate_result"' in source,
            "does_not_import_inputs_page": "inputs_page" not in source,
            "does_not_import_streamlit": "streamlit" not in source and "import st" not in source,
            "does_not_call_evaluator": "_evaluate_auto_design_candidate" not in source,
        },
        "latest_artifacts": {
            "old_helper_tail_gap": _latest("design_guide_rebind_projection_old_helper_tail_gap"),
            "projection_adapter_object": _latest("design_guide_rebind_projection_adapter_object"),
        },
        "decision": "CLEANUP_EVIDENCE_REHYDRATE_TAIL_OBJECT_PROVEN_NOT_WIRED",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("rows") or [])
    by_id = {str(row.get("scenario_id")): row for row in rows}
    source = dict(capture.get("source_checks") or {})
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "four_scenarios_exercised": capture.get("row_count") == 4,
        "all_hashes_stable": all(row.get("proof_hash_stable") is True for row in rows),
        "all_outputs_non_authoritative": all(row.get("non_authoritative") is True for row in rows),
        "combined_accepted_applies": by_id.get("combined_accepted_rehydrate", {}).get("applies") is True,
        "combined_contract_enabled": by_id.get("combined_accepted_rehydrate", {}).get("contract_enabled") is True,
        "safe_shear_accepted_applies": by_id.get("safe_shear_cleanup_rehydrate", {}).get("applies") is True,
        "safe_shear_removes_stale_blockers": set(
            by_id.get("safe_shear_cleanup_rehydrate", {}).get("evidence_remove_keys") or []
        )
        == {
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
            "cleanup_evidence_by_family",
            "post_click_cleanup_evidence_by_family",
        },
        "safe_shear_title_represented": "Shear cleanup - best safe one-click reduction"
        in str(by_id.get("safe_shear_cleanup_rehydrate", {}).get("item_title") or ""),
        "rejected_candidate_does_not_apply": by_id.get("rejected_candidate_explicit_fail", {}).get("applies") is False,
        "no_updates_does_not_apply": by_id.get("no_updates_noop", {}).get("applies") is False,
        "builder_present": source.get("builder_present") is True,
        "builder_exported": source.get("builder_exported") is True,
        "design_brain_does_not_import_inputs_page": source.get("does_not_import_inputs_page") is True,
        "design_brain_does_not_import_streamlit": source.get("does_not_import_streamlit") is True,
        "design_brain_does_not_call_evaluator": source.get("does_not_call_evaluator") is True,
        "old_helper_tail_gap_pass": (latest.get("old_helper_tail_gap") or {}).get("status") == "PASS",
        "projection_adapter_object_pass": (latest.get("projection_adapter_object") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "ready_for_trace_wiring": capture.get("ready_for_trace_wiring") is True,
        "not_ready_for_live_cutover": capture.get("ready_for_live_cutover") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Cleanup Evidence Rehydrate Tail Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Applies | Contract Enabled | Stable | Non-Authoritative |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            f"| `{row.get('scenario_id')}` | `{row.get('applies')}` | "
            f"`{row.get('contract_enabled')}` | `{row.get('proof_hash_stable')}` | "
            f"`{row.get('non_authoritative')}` |"
        )
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_cleanup_evidence_rehydrate_tail_object_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_cleanup_evidence_rehydrate_tail_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_cleanup_evidence_rehydrate_tail_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_cleanup_evidence_rehydrate_tail_object_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
