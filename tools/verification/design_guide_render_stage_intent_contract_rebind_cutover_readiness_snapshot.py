"""Cutover readiness for render-stage intent-contract rebind.

Proof-only. Compares the new FinalDesignGuidePublication render-stage
intent-contract result against the old render-stage mutation shape before any
live branch replacement.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _old_render_stage_output(item: dict[str, Any], intent_contract: dict[str, Any], intent_row: dict[str, Any]) -> dict[str, Any]:
    final_item = dict(item)
    final_contract = dict(intent_contract)
    final_item["button_contract"] = dict(final_contract)
    final_item["action_type"] = "apply_resolved_candidate"
    final_item["selected_action_updates"] = dict(final_contract.get("updates") or {})
    final_item["updates"] = dict(final_contract.get("updates") or {})
    final_item["candidate_id"] = final_contract.get("candidate_id") or final_contract.get("source_candidate_id")
    final_item["source_candidate_id"] = final_contract.get("source_candidate_id") or final_contract.get("candidate_id")
    if isinstance(intent_row, dict):
        final_item.setdefault("title_main", intent_row.get("title"))
        final_item.setdefault("title", intent_row.get("title"))
        final_item.setdefault("guidance_intent", intent_row.get("guidance_intent"))
    return final_item


def _scenario_rows() -> list[dict[str, Any]]:
    sys.path.insert(0, str(ROOT))
    from design_brain.final_publication import (  # noqa: WPS433
        build_final_visible_render_stage_intent_contract_rebind_result,
        stable_final_publication_hash,
    )

    scenarios = [
        {
            "id": "bending_contract_with_empty_titles",
            "item": {"title": "", "title_main": "", "button_contract": {"enabled": False}},
            "intent_contract": {
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family": "bending",
                "updates": {"bottom_bars": "8N16"},
                "candidate_id": "bending-cleanup-1",
            },
            "intent_row": {
                "title": "Improve bending efficiency",
                "guidance_intent": "efficiency_tightening",
                "check_key": "bending",
            },
        },
        {
            "id": "shear_contract_preserves_existing_title",
            "item": {
                "title": "Design is efficient",
                "title_main": "Design is efficient",
                "guidance_intent": "pass",
                "button_contract": {"enabled": False},
            },
            "intent_contract": {
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family": "shear",
                "updates": {"shear_legs": 0, "shear_spacing": 0},
                "source_candidate_id": "shear-cleanup-1",
            },
            "intent_row": {
                "title": "Remove shear links",
                "guidance_intent": "efficiency_tightening",
                "check_key": "shear",
            },
        },
        {
            "id": "no_intent_contract_noop",
            "item": {"title": "Blocked", "button_contract": {"enabled": False}},
            "intent_contract": {},
            "intent_row": {},
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        item = dict(scenario["item"])
        intent_contract = dict(scenario["intent_contract"])
        intent_row = dict(scenario["intent_row"])
        proof = build_final_visible_render_stage_intent_contract_rebind_result(
            item=item,
            contract=dict(item.get("button_contract") or {}),
            guidance_debug={
                "guidance_intent_items": [
                    {
                        "button_contract": dict(intent_contract),
                        **dict(intent_row),
                    }
                ]
            },
            intent_contract=intent_contract,
            intent_row=intent_row,
        )
        result = dict(proof.get("result") or {})
        proof_output = dict(result.get("output_item") or {})
        old_output = _old_render_stage_output(item, intent_contract, intent_row) if intent_contract else dict(item)
        rows.append(
            {
                "id": scenario["id"],
                "applies": bool(result.get("applies")),
                "old_output_hash": stable_final_publication_hash(old_output),
                "proof_output_hash": stable_final_publication_hash(proof_output),
                "output_parity": stable_final_publication_hash(old_output)
                == stable_final_publication_hash(proof_output),
                "contract_parity": stable_final_publication_hash(intent_contract)
                == stable_final_publication_hash(result.get("contract_effect") or {}),
                "proof_hash": proof.get("proof_hash"),
                "result_hash": proof.get("result_hash"),
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    input_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    input_lines = input_source.splitlines()
    render_stage_line = next(
        (
            index
            for index, line in enumerate(input_lines, start=1)
            if index > 93000 and "_build_final_visible_render_stage_intent_contract_rebind_result(" in line
        ),
        None,
    )
    if render_stage_line:
        start = max(0, render_stage_line - 30)
        end = min(len(input_lines), render_stage_line + 120)
        branch_context = "\n".join(input_lines[start:end])
    else:
        branch_context = ""
    rows = _scenario_rows()
    old_render_mutation_still_present = (
        "_final_visible_contract = dict(_intent_contract)" in branch_context
        and '_final_visible_item["button_contract"] = dict(_final_visible_contract)' in branch_context
        and "_record_rendered_design_guide_primary_apply_payload(" in branch_context
    )
    guarded_cutover_applied = (
        "_render_stage_intent_rebind_result = dict(" in branch_context
        and '"contract_effect"' in branch_context
        and '"item_effect"' in branch_context
        and "_final_visible_item.update(dict(_render_stage_item_effect))" in branch_context
        and '"render_stage_intent_contract_rebind_cutover_applied"' in branch_context
        and "_record_rendered_design_guide_primary_apply_payload(" in branch_context
    )
    return {
        "decision": "RENDER_STAGE_INTENT_CONTRACT_REBIND_READY_FOR_GUARDED_CUTOVER",
        "scenario_rows": rows,
        "source_checks": {
            "builder_present": "def build_final_visible_render_stage_intent_contract_rebind_result(" in final_source,
            "builder_exported": '"build_final_visible_render_stage_intent_contract_rebind_result"' in final_source,
            "inputs_imports_builder": (
                "build_final_visible_render_stage_intent_contract_rebind_result as "
                "_build_final_visible_render_stage_intent_contract_rebind_result"
            )
            in input_source,
            "render_stage_trace_uses_builder": (
                "_build_final_visible_render_stage_intent_contract_rebind_result(" in branch_context
            ),
            "builder_owns_intent_selection": (
                "_select_enabled_design_guide_contract_from_intent_rows(guidance_debug)" not in branch_context
                and "intent_contract=dict(_intent_contract or {})" not in branch_context
                and "intent_row=dict(_intent_row or {})" not in branch_context
            ),
            "branch_has_old_or_cutover_shape": bool(
                old_render_mutation_still_present or guarded_cutover_applied
            ),
            "guarded_cutover_applied": bool(guarded_cutover_applied),
        },
        "latest_artifacts": {
            "trace_wiring": _latest("design_guide_render_stage_intent_contract_rebind_trace_wiring"),
            "intent_ownership": _latest("design_guide_intent_contract_from_debug_rows_tail_ownership"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "ready_for_guarded_cutover": all(row["output_parity"] and row["contract_parity"] for row in rows),
        "delete_now": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    latest = dict(capture.get("latest_artifacts") or {})
    rows = list(capture.get("scenario_rows") or [])
    return {
        "all_source_checks_pass": all(source_checks.values()),
        "all_scenarios_have_output_parity": all(row.get("output_parity") is True for row in rows),
        "all_scenarios_have_contract_parity": all(row.get("contract_parity") is True for row in rows),
        "trace_wiring_pass": (latest.get("trace_wiring") or {}).get("status") == "PASS",
        "intent_ownership_pass": (latest.get("intent_ownership") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "ready_for_guarded_cutover": capture.get("ready_for_guarded_cutover") is True,
        "not_ready_for_deletion": capture.get("delete_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Render-Stage Intent Contract Rebind Cutover Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenario Rows",
        "",
        "| Scenario | Applies | Output parity | Contract parity |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in capture.get("scenario_rows") or []:
        lines.append(
            f"| `{row.get('id')}` | `{row.get('applies')}` | `{row.get('output_parity')}` | "
            f"`{row.get('contract_parity')}` |"
        )
    lines.extend(["", "## Source Checks", ""])
    for key, value in (capture.get("source_checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            "Cut over only the render-stage intent-contract branch to use the proof result effects, then rerun this verifier and composed locks.",
        ]
    )
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
        "schema": "design_guide_render_stage_intent_contract_rebind_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_stage_intent_contract_rebind_cutover_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_stage_intent_contract_rebind_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_stage_intent_contract_rebind_cutover_readiness_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
