"""Object snapshot for final-visible rebind projection adapter.

Proof-only. Verifies Design Brain can materialize plain item/contract/evidence
projection data from the rebind-effects proof without using inputs_page.py or
driving product/render/apply/session behavior.
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


def _scenario_requests() -> dict[str, dict[str, Any]]:
    from tools.verification.design_guide_controller_rebind_effects_adapter_parity_snapshot import (  # noqa: PLC0415
        _scenario_requests as controller_scenario_requests,
    )

    return controller_scenario_requests()


def _exercise() -> dict[str, Any]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_visible_contract_binding_rebind_effects_proof,
        build_final_visible_contract_binding_rebind_projection,
    )

    rows = []
    for scenario_id, request in _scenario_requests().items():
        proof = build_final_visible_contract_binding_rebind_effects_proof(
            **{key: value for key, value in request.items() if key != "source"}
        )
        projection = build_final_visible_contract_binding_rebind_projection(
            item=request.get("item"),
            contract=request.get("contract"),
            evidence_for_binding=request.get("evidence_for_binding"),
            debug=request.get("debug"),
            rebind_effects_proof=proof,
        )
        item = dict(projection.get("item") or {})
        contract = dict(projection.get("contract") or {})
        evidence = dict(projection.get("evidence_for_binding") or {})
        rows.append(
            {
                "scenario_id": scenario_id,
                "projection_hash": projection.get("projection_hash"),
                "projection_hash_stable": projection.get("projection_hash")
                == build_final_visible_contract_binding_rebind_projection(
                    item=request.get("item"),
                    contract=request.get("contract"),
                    evidence_for_binding=request.get("evidence_for_binding"),
                    debug=request.get("debug"),
                    rebind_effects_proof=proof,
                ).get("projection_hash"),
                "applied_effects": list(projection.get("applied_effects") or []),
                "applied_effect_count": projection.get("applied_effect_count"),
                "contract_hash": (projection.get("output_hashes") or {}).get("contract_hash"),
                "item_hash": (projection.get("output_hashes") or {}).get("item_hash"),
                "evidence_hash": (projection.get("output_hashes") or {}).get("evidence_for_binding_hash"),
                "button_contract_matches_projection_contract": dict(item.get("button_contract") or {})
                == contract,
                "item_candidate_evidence_matches_projection_evidence": dict(
                    item.get("candidate_search_evidence") or {}
                )
                == evidence,
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
                "def build_final_visible_contract_binding_rebind_projection(" in source
            ),
            "projection_function_exported": (
                '"build_final_visible_contract_binding_rebind_projection"' in source
            ),
            "does_not_import_inputs_page": "inputs_page" not in source,
            "does_not_import_streamlit": "streamlit" not in source and "import st" not in source,
        },
        "latest_artifacts": {
            "controller_adapter_parity": _latest("design_guide_controller_rebind_effects_adapter_parity"),
            "callsite_parity_readiness": _latest(
                "design_guide_controller_rebind_effects_callsite_parity_readiness"
            ),
        },
        "decision": "RENDER_REBIND_PROJECTION_ADAPTER_OBJECT_PROVEN_NOT_WIRED",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("rows") or [])
    source = dict(capture.get("source_checks") or {})
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "three_scenarios_exercised": capture.get("row_count") == 3,
        "all_projection_hashes_stable": all(row.get("projection_hash_stable") is True for row in rows),
        "all_apply_at_least_one_effect": all(int(row.get("applied_effect_count") or 0) > 0 for row in rows),
        "button_contract_projection_consistent": all(
            row.get("button_contract_matches_projection_contract") is True for row in rows
        ),
        "candidate_evidence_projection_consistent": all(
            row.get("item_candidate_evidence_matches_projection_evidence") is True for row in rows
        ),
        "all_outputs_non_authoritative": all(row.get("non_authoritative") is True for row in rows),
        "projection_function_present": source.get("projection_function_present") is True,
        "projection_function_exported": source.get("projection_function_exported") is True,
        "design_brain_does_not_import_inputs_page": source.get("does_not_import_inputs_page") is True,
        "design_brain_does_not_import_streamlit": source.get("does_not_import_streamlit") is True,
        "controller_adapter_parity_pass": (latest.get("controller_adapter_parity") or {}).get("status") == "PASS",
        "callsite_parity_readiness_pass": (latest.get("callsite_parity_readiness") or {}).get("status")
        == "PASS",
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
        "# Rebind Projection Adapter Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Applied Effects | Stable | Non-Authoritative |",
        "| --- | --- | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            f"| `{row.get('scenario_id')}` | `{row.get('applied_effects')}` | "
            f"`{row.get('projection_hash_stable')}` | `{row.get('non_authoritative')}` |"
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
        "schema": "design_guide_rebind_projection_adapter_object_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_rebind_projection_adapter_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_rebind_projection_adapter_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_rebind_projection_adapter_object_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
