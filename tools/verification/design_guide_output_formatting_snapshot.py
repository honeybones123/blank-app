"""Focused snapshot for Design Guide output-formatting display fields.

Coverage-only verifier. It snapshots the pure decision-display field packer
before moving it out of ``inputs_page.py``. It does not drive product output or
change wording.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from design_brain.output_formatting_contract import (  # noqa: E402
    CONTRACT_PATH,
    allowed_reason_why_rows,
    allowed_title_status_formats,
    blocker_wording_categories,
    cleanup_no_repair_wording,
    cta_display_wording_expectations,
    exact_blocker_fallback_wording,
    ladder_stop_evidence_wording,
    load_design_guide_output_wording_contract,
    required_html_model_hash_fields,
    required_output_wording_gates,
    required_render_model_fields,
    required_snapshot_cases,
)

ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"


def _stable_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _contract(
    *,
    enabled: bool,
    family: str,
    updates: dict[str, Any] | None = None,
    action_type: str | None = "apply_resolved_candidate",
    blocking_reason: str | None = None,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "actionable": bool(enabled),
        "action_type": action_type if enabled else None,
        "family": family,
        "updates": dict(updates or {}),
        "preview_pass": bool(enabled),
        "blocking_reason": None if enabled else blocking_reason,
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
    }


def _case_specs(module: Any) -> list[dict[str, Any]]:
    scalars_type = module.DesignGuideCardResolvedScalars
    cases: list[dict[str, Any]] = []

    action_contract = _contract(
        enabled=True,
        family="SHEAR_FAIL_GOVERNS",
        updates={"s_lig": 150},
        candidate_id="synthetic_shear_action_candidate",
    )
    action_scalars = scalars_type(
        family="SHEAR_FAIL_GOVERNS",
        selected_family_name_attr="SHEAR_FAIL_GOVERNS",
        apply_identity="SHEAR_FAIL_GOVERNS",
        contract_enabled_attr="True",
        cta_enabled_attr="True",
        contract_action_type_attr="apply_resolved_candidate",
        contract_update_count_attr="1",
        cta_payload_id_attr="synthetic_shear_action_candidate",
        render_gate_condition_attr="True",
        render_gate_pres_show_attr="True",
        render_gate_effective_action_attr="apply_resolved_candidate",
        render_gate_button_enabled_attr="True",
        render_gate_vm_cta_attr="True",
    )
    action_reasons = [
        {"label": "Problem", "text": "Shear utilisation is outside the allowed range.", "tone": "red"},
        {"label": "Fix", "text": "Run one-click auto design.", "tone": "green"},
    ]
    cases.append(
        {
            "name": "action_enabled_shear",
            "input": {
                "status": "action",
                "title": "Shear capacity is low",
                "pill": "ACTION",
                "reasons": action_reasons,
                "reason_texts": [row["text"] for row in action_reasons],
                "summary_line": "Run one-click auto design.",
                "card_class": "fast-guidance-item action",
                "vm_d": {
                    "tone": "action",
                    "selected_family_id": "SHEAR_FAIL_GOVERNS",
                    "published_family_id": "SHEAR_FAIL_GOVERNS",
                    "cta_family_id": "SHEAR_FAIL_GOVERNS",
                },
                "cta": {"enabled": True, "label": "Run one-click auto design", "payload_id": "synthetic_shear_action_candidate"},
                "contract": action_contract,
                "card_scalars": action_scalars,
                "disabled_action_with_blocker": False,
                "section_title_override": "",
                "exact_rows": {},
                "blocker_rows": {},
                "blocker_reason": "",
            },
            "vm": {
                "status": "action",
                "pill": "ACTION",
                "title": "Shear capacity is low",
                "tone": "action",
                "summary_line": "Run one-click auto design.",
                "section_title": "Why action is required",
                "reasons": action_reasons,
                "cta": {"enabled": True, "label": "Run one-click auto design", "payload_id": "synthetic_shear_action_candidate"},
                "selected_family_id": "SHEAR_FAIL_GOVERNS",
                "published_family_id": "SHEAR_FAIL_GOVERNS",
                "cta_family_id": "SHEAR_FAIL_GOVERNS",
                "apply_payload_family_id": "SHEAR_FAIL_GOVERNS",
                "details": {
                    "button_contract": action_contract,
                    "candidate_search_evidence": {"selected_family_id": "SHEAR_FAIL_GOVERNS"},
                    "render_gate_probe": {
                        "render_button_condition": True,
                        "pres_show_apply": True,
                        "effective_render_action_type": "apply_resolved_candidate",
                        "button_contract_enabled": True,
                        "final_view_cta_enabled": True,
                    },
                },
            },
            "card_class": "fast-guidance-item action",
        }
    )

    blocked_contract = _contract(
        enabled=False,
        family="SHEAR_FAIL_GOVERNS",
        updates={},
        blocking_reason="Synthetic exact blocker proof remains active.",
    )
    blocked_scalars = scalars_type(
        family="SHEAR_FAIL_GOVERNS",
        selected_family_name_attr="SHEAR_FAIL_GOVERNS",
        apply_identity="SHEAR_FAIL_GOVERNS",
        contract_enabled_attr="False",
        cta_enabled_attr="False",
        contract_action_type_attr="",
        contract_update_count_attr="0",
        contract_blocking_reason_attr="Synthetic exact blocker proof remains active.",
        render_gate_condition_attr="False",
        render_gate_pres_show_attr="False",
        render_gate_effective_action_attr="",
        render_gate_terminal_exact_attr="False",
        render_gate_button_enabled_attr="False",
        render_gate_vm_cta_attr="False",
    )
    blocked_reasons = [
        {"label": "Blocker evidence", "text": "Synthetic exact blocker proof remains active.", "tone": "amber"},
        {"label": "Next step", "text": "Review the recorded failed route evidence.", "tone": "info"},
    ]
    blocked_exact = {"shear": {"reason": "Synthetic exact blocker proof remains active.", "failed_check_name": "shear detailing"}}
    cases.append(
        {
            "name": "blocked_exact_shear",
            "input": {
                "status": "blocked",
                "title": "Shear cleanup blocked",
                "pill": "BLOCKED",
                "reasons": blocked_reasons,
                "reason_texts": [row["text"] for row in blocked_reasons],
                "summary_line": "Open for engineering detail.",
                "card_class": "fast-guidance-item blocked",
                "vm_d": {"tone": "blocked", "selected_family_id": "SHEAR_FAIL_GOVERNS"},
                "cta": {"enabled": False, "label": "", "reason": "Synthetic exact blocker proof remains active."},
                "contract": blocked_contract,
                "card_scalars": blocked_scalars,
                "disabled_action_with_blocker": True,
                "section_title_override": "Why no further cleanup?",
                "exact_rows": blocked_exact,
                "blocker_rows": blocked_exact,
                "blocker_reason": "Synthetic exact blocker proof remains active.",
            },
            "vm": {
                "status": "blocked",
                "pill": "BLOCKED",
                "title": "Shear cleanup blocked",
                "tone": "blocked",
                "summary_line": "Open for engineering detail.",
                "section_title": "Why no further cleanup?",
                "reasons": blocked_reasons,
                "cta": {"enabled": False, "label": "", "reason": "Synthetic exact blocker proof remains active."},
                "selected_family_id": "SHEAR_FAIL_GOVERNS",
                "published_family_id": "SHEAR_FAIL_GOVERNS",
                "cta_family_id": "SHEAR_FAIL_GOVERNS",
                "details": {
                    "button_contract": blocked_contract,
                    "exact_blockers_by_family": blocked_exact,
                    "candidate_search_evidence": {"exact_blockers_by_family": blocked_exact},
                    "render_gate_probe": {
                        "render_button_condition": False,
                        "pres_show_apply": False,
                        "effective_render_action_type": "",
                        "button_contract_enabled": False,
                        "final_view_cta_enabled": False,
                    },
                },
            },
            "card_class": "fast-guidance-item blocked",
        }
    )

    pass_contract = _contract(enabled=False, family="TARGET_BAND_REACHED", updates={}, blocking_reason=None)
    pass_scalars = scalars_type(
        family="TARGET_BAND_REACHED",
        selected_family_name_attr="TARGET_BAND_REACHED",
        apply_identity="",
        contract_enabled_attr="False",
        cta_enabled_attr="False",
        contract_action_type_attr="",
        contract_update_count_attr="0",
        render_gate_condition_attr="False",
        render_gate_terminal_exact_attr="True",
        render_gate_button_enabled_attr="False",
        render_gate_vm_cta_attr="False",
    )
    pass_reasons = [
        {"label": "Result", "text": "All required checks pass and the design is accepted.", "tone": "green"},
        {"label": "Serviceability", "text": "Crack and deflection checks remain within limits.", "tone": "green"},
    ]
    cases.append(
        {
            "name": "pass_terminal",
            "input": {
                "status": "pass",
                "title": "Design is efficient",
                "pill": "PASS",
                "reasons": pass_reasons,
                "reason_texts": [row["text"] for row in pass_reasons],
                "summary_line": "All checks pass.",
                "card_class": "fast-guidance-item pass guidance-success",
                "vm_d": {"tone": "pass", "selected_family_id": "TARGET_BAND_REACHED"},
                "cta": {"enabled": False, "label": ""},
                "contract": pass_contract,
                "card_scalars": pass_scalars,
                "disabled_action_with_blocker": False,
                "section_title_override": "",
                "exact_rows": {},
                "blocker_rows": {},
                "blocker_reason": "",
            },
            "vm": {
                "status": "pass",
                "pill": "PASS",
                "title": "Design is efficient",
                "tone": "pass",
                "summary_line": "All checks pass.",
                "section_title": "Status",
                "reasons": pass_reasons,
                "cta": {"enabled": False, "label": ""},
                "selected_family_id": "TARGET_BAND_REACHED",
                "published_family_id": "TARGET_BAND_REACHED",
                "cta_family_id": "TARGET_BAND_REACHED",
                "details": {
                    "button_contract": pass_contract,
                    "candidate_search_evidence": {"selected_family_id": "TARGET_BAND_REACHED"},
                    "render_gate_probe": {
                        "render_button_condition": False,
                        "terminal_exact_accepted": True,
                        "button_contract_enabled": False,
                        "final_view_cta_enabled": False,
                    },
                },
            },
            "card_class": "fast-guidance-item pass guidance-success",
        }
    )
    return cases


def _summarise_input(case_input: dict[str, Any]) -> dict[str, Any]:
    cta = dict(case_input.get("cta") or {})
    contract = dict(case_input.get("contract") or {})
    reasons = [dict(row) for row in list(case_input.get("reasons") or []) if isinstance(row, dict)]
    return {
        "status": case_input.get("status"),
        "title": case_input.get("title"),
        "pill": case_input.get("pill"),
        "summary_line": case_input.get("summary_line"),
        "card_class": case_input.get("card_class"),
        "reason_count": len(reasons),
        "reasons_hash": _stable_hash(reasons),
        "reason_texts": list(case_input.get("reason_texts") or []),
        "cta": {
            "enabled": bool(cta.get("enabled")),
            "label": cta.get("label"),
            "reason": cta.get("reason") or cta.get("blocking_reason"),
        },
        "contract": {
            "enabled": bool(contract.get("enabled")),
            "action_type": contract.get("action_type"),
            "family": contract.get("family"),
            "update_keys": sorted(dict(contract.get("updates") or {})),
            "blocking_reason": contract.get("blocking_reason"),
        },
        "disabled_action_with_blocker": bool(case_input.get("disabled_action_with_blocker")),
        "section_title_override": case_input.get("section_title_override"),
        "blocker_reason": case_input.get("blocker_reason"),
    }


def _contract_case_coverage(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    case_names = {str(case.get("name") or "") for case in cases}
    coverage: dict[str, dict[str, Any]] = {}
    for category, config in required_snapshot_cases().items():
        names = [str(value) for value in config.get("case_names") or []]
        matched = [name for name in names if name in case_names]
        required = bool(config.get("required"))
        status = "covered" if matched else ("missing" if required else "not_available")
        coverage[category] = {
            "status": status,
            "required": required,
            "case_names": names,
            "matched_case_names": matched,
            "coverage_note": config.get("coverage_note"),
        }
    return coverage


def _validate_case_against_contract(row: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    name = str(row.get("name") or "unknown")
    formats = allowed_title_status_formats()
    allowed_statuses = {str(value) for value in formats.get("statuses") or []}
    allowed_pills = {str(value) for value in formats.get("pill_labels") or []}
    decision = dict(row.get("decision_display_fields") or {})
    status = str(decision.get("final_status") or "")
    pill = str(decision.get("final_pill_label") or "")
    if status not in allowed_statuses:
        failures.append(f"{name}:status_not_allowed_by_contract:{status}")
    if pill not in allowed_pills:
        failures.append(f"{name}:pill_not_allowed_by_contract:{pill}")

    row_contract = allowed_reason_why_rows()
    required_row_fields = {str(value) for value in row_contract.get("required_row_fields") or []}
    allowed_tones = {str(value) for value in row_contract.get("allowed_tones") or []}
    for index, reason in enumerate(list(decision.get("final_reasons") or [])):
        if not isinstance(reason, dict):
            failures.append(f"{name}:reason_row_not_dict:{index}")
            continue
        for field in required_row_fields:
            if field not in reason:
                failures.append(f"{name}:reason_row_missing_field:{index}:{field}")
        tone = str(reason.get("tone") or "")
        if tone and tone not in allowed_tones:
            failures.append(f"{name}:reason_row_tone_not_allowed:{index}:{tone}")

    cta_expectations = cta_display_wording_expectations()
    cta_fields = dict(row.get("cta_display_fields") or {})
    if bool(cta_fields.get("cta_enabled")):
        expected_label = str(cta_expectations.get("enabled_label") or "")
        if expected_label and str(cta_fields.get("cta_label") or "") != expected_label:
            failures.append(f"{name}:enabled_cta_label_mismatch")

    full_model = dict(row.get("final_card_model_full") or {})
    for field in required_render_model_fields():
        if field not in full_model:
            failures.append(f"{name}:render_model_field_missing:{field}")
    for field in required_html_model_hash_fields():
        if field not in row:
            failures.append(f"{name}:hash_field_missing:{field}")
    return failures


def _snapshot_case(module: Any, case: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    fields = module._build_design_guide_card_decision_display_fields(**dict(case["input"]))
    fields_dict = asdict(fields)
    render_model = module._build_design_guide_card_render_model(
        dict(case["vm"]),
        card_class=str(case.get("card_class") or ""),
    )
    module._record_design_guide_card_render_model(
        render_model,
        source=f"design_guide_output_formatting_snapshot.{case['name']}",
    )
    render_dict = render_model.to_dict()
    html = module._design_guide_dashboard_card_html_from_render_model(render_model)

    expected = {
        "final_title": str(case["input"].get("title") or "").strip(),
        "final_status": str(case["input"].get("status") or "").strip(),
        "final_pill_label": str(case["input"].get("pill") or "").strip(),
        "cta_enabled": bool(dict(case["input"].get("cta") or {}).get("enabled")),
        "cta_label": str(dict(case["input"].get("cta") or {}).get("label") or "").strip(),
    }
    for key, value in expected.items():
        if fields_dict.get(key) != value:
            failures.append(f"{case['name']}:{key}_changed")

    if render_dict.get("title") != fields_dict.get("final_title"):
        failures.append(f"{case['name']}:render_title_mismatch")
    if render_dict.get("status") != fields_dict.get("final_status"):
        failures.append(f"{case['name']}:render_status_mismatch")
    if render_dict.get("cta_enabled") != fields_dict.get("cta_enabled"):
        failures.append(f"{case['name']}:render_cta_enabled_mismatch")

    return (
        {
            "name": case["name"],
            "input": _summarise_input(dict(case["input"])),
            "decision_display_fields": fields_dict,
            "decision_display_fields_hash": _stable_hash(fields_dict),
            "title_display": fields_dict.get("final_title"),
            "status_display": fields_dict.get("final_status"),
            "reason_why_display_fields": {
                "final_reasons": fields_dict.get("final_reasons"),
                "final_why_body": fields_dict.get("final_why_body"),
                "final_main_text": fields_dict.get("final_main_text"),
            },
            "cta_display_fields": {
                "cta_label": fields_dict.get("cta_label"),
                "cta_enabled": fields_dict.get("cta_enabled"),
                "cta_reason": fields_dict.get("cta_reason"),
            },
            "disabled_apply_display_fields": {
                "button_contract_attributes": fields_dict.get("button_contract_attributes"),
                "blocked_display_state": fields_dict.get("blocked_display_state"),
                "action_state": fields_dict.get("action_state"),
            },
            "final_card_model_fields": {
                "family": render_dict.get("family"),
                "family_label": render_dict.get("family_label"),
                "title": render_dict.get("title"),
                "status": render_dict.get("status"),
                "pill": render_dict.get("pill"),
                "main_text": render_dict.get("main_text"),
                "cta_label": render_dict.get("cta_label"),
                "cta_enabled": render_dict.get("cta_enabled"),
                "cta_reason": render_dict.get("cta_reason"),
                "button_contract_attributes": render_dict.get("button_contract_attributes"),
                "blocker_reason": render_dict.get("blocker_reason"),
                "data_attributes": render_dict.get("data_attributes"),
            },
            "final_card_model_full": render_dict,
            "final_card_model_hash": _stable_hash(render_dict),
            "rendered_html_hash": _stable_hash(html),
        },
        failures,
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def main() -> int:
    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    decision_record_path = TRACE_DIR / f"design_guide_output_formatting_decision_display_{timestamp}.jsonl"
    render_record_path = TRACE_DIR / f"design_guide_output_formatting_render_model_{timestamp}.jsonl"
    for path in (decision_record_path, render_record_path):
        if path.exists():
            path.unlink()
    os.environ["DESIGN_GUIDE_CARD_DECISION_DISPLAY_SNAPSHOT_PATH"] = str(decision_record_path)
    os.environ["DESIGN_GUIDE_CARD_RENDER_MODEL_SNAPSHOT_PATH"] = str(render_record_path)

    import inputs_page as module

    failures: list[str] = []
    cases: list[dict[str, Any]] = []
    for case in _case_specs(module):
        row, case_failures = _snapshot_case(module, case)
        cases.append(row)
        failures.extend(case_failures)
        failures.extend(_validate_case_against_contract(row))

    contract_case_coverage = _contract_case_coverage(cases)
    for category, row in contract_case_coverage.items():
        if row.get("required") and row.get("status") != "covered":
            failures.append(f"required_contract_case_not_covered:{category}")

    decision_records = _read_jsonl(decision_record_path)
    render_records = _read_jsonl(render_record_path)
    if len(decision_records) < len(cases) * 2:
        failures.append("decision_display_recorder_rows_missing")
    if len(render_records) < len(cases):
        failures.append("render_model_recorder_rows_missing")

    aggregate = {
        "decision_display_hashes": {case["name"]: case["decision_display_fields_hash"] for case in cases},
        "final_card_model_hashes": {case["name"]: case["final_card_model_hash"] for case in cases},
        "rendered_html_hashes": {case["name"]: case["rendered_html_hash"] for case in cases},
    }
    status = "PASS" if not failures else "FAIL"
    snapshot_path = ARTIFACT_DIR / f"design_guide_output_formatting_snapshot_{timestamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_output_formatting_snapshot_{timestamp}.md"
    output = {
        "schema": "design_guide_output_formatting_snapshot.v1",
        "status": status,
        "failures": failures,
        "contract_path": str(CONTRACT_PATH),
        "contract_identity": dict(load_design_guide_output_wording_contract().get("contract_identity") or {}),
        "contract_allowed_title_status_formats": allowed_title_status_formats(),
        "contract_allowed_reason_why_rows": allowed_reason_why_rows(),
        "blocker_wording_categories": list(blocker_wording_categories()),
        "cleanup_no_repair_wording": cleanup_no_repair_wording(),
        "exact_blocker_fallback_wording": exact_blocker_fallback_wording(),
        "ladder_stop_evidence_wording": ladder_stop_evidence_wording(),
        "cta_display_wording_expectations": cta_display_wording_expectations(),
        "required_render_model_fields": list(required_render_model_fields()),
        "required_hash_fields": list(required_html_model_hash_fields()),
        "required_snapshot_cases": required_snapshot_cases(),
        "contract_case_coverage": contract_case_coverage,
        "required_gates": list(required_output_wording_gates()),
        "snapshot_path": str(snapshot_path),
        "audit_path": str(audit_path),
        "decision_display_record_path": str(decision_record_path),
        "render_model_record_path": str(render_record_path),
        "decision_display_record_count": len(decision_records),
        "render_model_record_count": len(render_records),
        "aggregate": aggregate,
        "cases": cases,
        "proven": status == "PASS",
    }
    snapshot_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    failure_lines = [f"- {failure}" for failure in failures] if failures else ["- none"]
    audit_path.write_text(
        "\n".join(
            [
                "# Design Guide Output Formatting Snapshot",
                "",
                f"Status: {status}",
                "",
                f"Snapshot: `{snapshot_path}`",
                f"Decision display record: `{decision_record_path}`",
                f"Render model record: `{render_record_path}`",
                f"Contract: `{CONTRACT_PATH}`",
                "",
                "## Contract Case Coverage",
                *[
                    f"- {category}: {row.get('status')} ({', '.join(row.get('matched_case_names') or []) or 'none'})"
                    for category, row in contract_case_coverage.items()
                ],
                "",
                "## Cases",
                *[
                    f"- {case['name']}: decision `{case['decision_display_fields_hash']}`, "
                    f"model `{case['final_card_model_hash']}`, html `{case['rendered_html_hash']}`"
                    for case in cases
                ],
                "",
                "## Failures",
                *failure_lines,
                "",
                "## Decision",
                (
                    "PROVEN: `_build_design_guide_card_decision_display_fields(...)` has a stable "
                    "snapshot boundary and can be extracted page-neutrally next."
                    if status == "PASS"
                    else "NOT_PROVEN: do not extract until failures are resolved."
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{status}: {snapshot_path}")
    print(f"REPORT: {audit_path}")
    if failures:
        for failure in failures:
            print(f"- {failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
