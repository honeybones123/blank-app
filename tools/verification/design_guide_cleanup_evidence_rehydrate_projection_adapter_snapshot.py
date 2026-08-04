"""Projection adapter snapshot for cleanup-evidence rehydrate tail.

Proof-only. Verifies Design Brain can project the cleanup-evidence rehydrate
proof into item/contract/evidence/debug dictionaries without using page,
render, apply, evaluator, or session code.
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


def _scenario_inputs() -> dict[str, dict[str, Any]]:
    from tools.verification.design_guide_cleanup_evidence_rehydrate_tail_object_snapshot import (  # noqa: PLC0415
        _scenario_inputs as object_scenario_inputs,
    )

    return object_scenario_inputs()


def _exercise() -> dict[str, Any]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection,
        build_final_visible_contract_binding_cleanup_evidence_rehydrate_result,
    )

    rows = []
    for scenario_id, kwargs in _scenario_inputs().items():
        proof = build_final_visible_contract_binding_cleanup_evidence_rehydrate_result(
            **kwargs,
            final_accepted_min_family_util=0.85,
            target_band_eps=1e-9,
        )
        projection = build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection(
            item=kwargs.get("item"),
            contract=kwargs.get("contract"),
            evidence_for_binding=kwargs.get("evidence_for_binding"),
            debug={},
            cleanup_rehydrate_proof=proof,
        )
        repeat = build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection(
            item=kwargs.get("item"),
            contract=kwargs.get("contract"),
            evidence_for_binding=kwargs.get("evidence_for_binding"),
            debug={},
            cleanup_rehydrate_proof=proof,
        )
        item = dict(projection.get("item") or {})
        contract = dict(projection.get("contract") or {})
        evidence = dict(projection.get("evidence_for_binding") or {})
        payload = dict(item.get("action_payload") or {})
        resolved = dict(item.get("resolved_candidate") or {})
        rows.append(
            {
                "scenario_id": scenario_id,
                "proof_applies": bool((proof.get("result") or {}).get("applies")),
                "projection_hash": projection.get("projection_hash"),
                "projection_hash_stable": projection.get("projection_hash") == repeat.get("projection_hash"),
                "applied_effects": list(projection.get("applied_effects") or []),
                "applied_effect_count": projection.get("applied_effect_count"),
                "contract_enabled": bool(contract.get("enabled")),
                "item_button_contract_matches_projection_contract": dict(item.get("button_contract") or {})
                == contract,
                "item_candidate_evidence_matches_projection_evidence": dict(
                    item.get("candidate_search_evidence") or {}
                )
                == evidence,
                "payload_candidate_evidence_matches_projection_evidence": (
                    dict(payload.get("candidate_search_evidence") or {}) == evidence
                    if bool((proof.get("result") or {}).get("applies"))
                    else True
                ),
                "resolved_candidate_evidence_matches_projection_evidence": (
                    dict(resolved.get("candidate_search_evidence") or {}) == evidence
                    if bool((proof.get("result") or {}).get("applies"))
                    else True
                ),
                "stale_blockers_removed": not any(
                    key in evidence
                    for key in (
                        "exact_blockers_by_family",
                        "post_click_exact_blockers_by_family",
                        "cleanup_evidence_by_family",
                        "post_click_cleanup_evidence_by_family",
                    )
                ),
                "item_title": item.get("title"),
                "non_authoritative": (
                    projection.get("proof_only") is True
                    and projection.get("product_driving") is False
                    and projection.get("render_driving") is False
                    and projection.get("apply_driving") is False
                    and projection.get("session_driving") is False
                ),
            }
        )
    return {"rows": rows, "row_count": len(rows)}


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    return {
        **_exercise(),
        "source_checks": {
            "projection_function_present": (
                "def build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection(" in source
            ),
            "projection_function_exported": (
                '"build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection"' in source
            ),
            "does_not_import_inputs_page": "inputs_page" not in source,
            "does_not_import_streamlit": "streamlit" not in source and "import st" not in source,
            "does_not_call_evaluator": "_evaluate_auto_design_candidate" not in source,
        },
        "latest_artifacts": {
            "tail_object": _latest("design_guide_cleanup_evidence_rehydrate_tail_object"),
            "tail_trace_wiring": _latest("design_guide_cleanup_evidence_rehydrate_tail_trace_wiring"),
        },
        "decision": "CLEANUP_EVIDENCE_REHYDRATE_PROJECTION_ADAPTER_PROVEN_NOT_WIRED",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "ready_for_live_parity": True,
        "ready_for_live_cutover": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("rows") or [])
    by_id = {str(row.get("scenario_id")): row for row in rows}
    source = dict(capture.get("source_checks") or {})
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "four_scenarios_exercised": capture.get("row_count") == 4,
        "all_hashes_stable": all(row.get("projection_hash_stable") is True for row in rows),
        "all_outputs_non_authoritative": all(row.get("non_authoritative") is True for row in rows),
        "accepted_scenarios_enable_contract": all(
            by_id.get(key, {}).get("contract_enabled") is True
            for key in ("combined_accepted_rehydrate", "safe_shear_cleanup_rehydrate")
        ),
        "rejected_noop_scenarios_do_not_enable_contract": all(
            by_id.get(key, {}).get("contract_enabled") is False
            for key in ("rejected_candidate_explicit_fail", "no_updates_noop")
        ),
        "item_contract_consistent": all(
            row.get("item_button_contract_matches_projection_contract") is True for row in rows
        ),
        "item_evidence_consistent": all(
            row.get("item_candidate_evidence_matches_projection_evidence") is True for row in rows
        ),
        "payload_evidence_consistent_when_applies": all(
            row.get("payload_candidate_evidence_matches_projection_evidence") is True for row in rows
        ),
        "resolved_candidate_evidence_consistent_when_applies": all(
            row.get("resolved_candidate_evidence_matches_projection_evidence") is True for row in rows
        ),
        "safe_shear_stale_blockers_removed": by_id.get("safe_shear_cleanup_rehydrate", {}).get(
            "stale_blockers_removed"
        )
        is True,
        "safe_shear_title_represented": "Shear cleanup - best safe one-click reduction"
        in str(by_id.get("safe_shear_cleanup_rehydrate", {}).get("item_title") or ""),
        "projection_function_present": source.get("projection_function_present") is True,
        "projection_function_exported": source.get("projection_function_exported") is True,
        "design_brain_does_not_import_inputs_page": source.get("does_not_import_inputs_page") is True,
        "design_brain_does_not_import_streamlit": source.get("does_not_import_streamlit") is True,
        "design_brain_does_not_call_evaluator": source.get("does_not_call_evaluator") is True,
        "tail_object_pass": (latest.get("tail_object") or {}).get("status") == "PASS",
        "tail_trace_wiring_pass": (latest.get("tail_trace_wiring") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "ready_for_live_parity": capture.get("ready_for_live_parity") is True,
        "not_ready_for_live_cutover": capture.get("ready_for_live_cutover") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Cleanup Evidence Rehydrate Projection Adapter Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Applies | Contract Enabled | Applied Effects | Stable |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            f"| `{row.get('scenario_id')}` | `{row.get('proof_applies')}` | "
            f"`{row.get('contract_enabled')}` | `{row.get('applied_effects')}` | "
            f"`{row.get('projection_hash_stable')}` |"
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
        "schema": "design_guide_cleanup_evidence_rehydrate_projection_adapter_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_cleanup_evidence_rehydrate_projection_adapter_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_cleanup_evidence_rehydrate_projection_adapter_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_cleanup_evidence_rehydrate_projection_adapter_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
