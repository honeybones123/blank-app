"""Family-exhaustive Design Guide render-model formatting snapshot.

Proof-only verifier. It builds one synthetic Design Guide render-model fixture
for every contract-allowed governing family using the live inputs_page wrapper
and UI HTML renderer. It does not render Streamlit, change product state,
change wording, change CTA/apply semantics, or execute family runtimes.
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


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.display_formatting_contract import status_colour_contract  # noqa: E402
from design_brain.family_classification import allowed_family_ids  # noqa: E402
from design_brain.output_formatting_contract import (  # noqa: E402
    allowed_reason_why_rows,
    allowed_title_status_formats,
    cta_display_wording_expectations,
    required_html_model_hash_fields,
    required_render_model_fields,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TRACE_DIR = ROOT / "artifacts" / "traces"


def _stable_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _colour_family_map() -> dict[str, str]:
    families: dict[str, str] = {}
    for colour, config in status_colour_contract().items():
        for family_id in dict(config).get("families") or ():
            families[str(family_id)] = str(colour).upper()
    return families


def _status_for_family(family_id: str, colour: str | None) -> tuple[str, str, str, str, bool]:
    if colour in {"RED", "BLUE"}:
        title = "Strengthening required" if colour == "RED" else "Optimisation available"
        return "action", "ACTION", "action", title, True
    if colour == "GREEN":
        return "pass", "PASS", "pass", "Design is efficient", False
    return "blocked", "BLOCKED", "blocked", "Design Guide blocker proof incomplete", False


def _contract(
    *,
    enabled: bool,
    family_id: str,
    candidate_id: str,
    blocking_reason: str,
) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "actionable": bool(enabled),
        "action_type": "apply_resolved_candidate" if enabled else None,
        "family": family_id,
        "updates": {"width": 400, "depth": 650} if enabled else {},
        "preview_pass": bool(enabled),
        "blocking_reason": None if enabled else blocking_reason,
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
    }


def _reasons(status: str, family_id: str, colour: str | None) -> list[dict[str, str]]:
    if status == "pass":
        return [
            {"label": "Result", "text": "All required checks pass and the design is accepted.", "tone": "green"},
            {"label": "Serviceability", "text": "Crack and deflection checks remain within limits.", "tone": "green"},
        ]
    if status == "blocked":
        return [
            {
                "label": "Blocker evidence",
                "text": f"{family_id} has no executable action in this synthetic formatting case.",
                "tone": "amber",
            },
            {"label": "Next step", "text": "Review the recorded failed route evidence.", "tone": "info"},
        ]
    if colour == "BLUE":
        return [
            {
                "label": "Why",
                "text": f"{family_id} has an optimisation candidate in this synthetic formatting case.",
                "tone": "info",
            },
            {"label": "Expected result", "text": "The proposed change remains within accepted checks.", "tone": "green"},
        ]
    return [
        {
            "label": "Problem",
            "text": f"{family_id} requires a repair action in this synthetic formatting case.",
            "tone": "red",
        },
        {"label": "Fix", "text": "Run one-click auto design.", "tone": "green"},
    ]


def _vm_for_family(family_id: str, colour: str | None) -> tuple[dict[str, Any], str]:
    status, pill, tone, title, enabled = _status_for_family(family_id, colour)
    candidate_id = f"{family_id}:family_render_model_formatting_candidate"
    blocking_reason = f"{family_id} synthetic blocker evidence for render-model formatting."
    contract = _contract(
        enabled=enabled,
        family_id=family_id,
        candidate_id=candidate_id,
        blocking_reason=blocking_reason,
    )
    reasons = _reasons(status, family_id, colour)
    cta_label = "Run one-click auto design" if enabled else ""
    cta = {
        "enabled": bool(enabled),
        "label": cta_label,
        "payload_id": candidate_id if enabled else "",
        "reason": "" if enabled else blocking_reason,
    }
    render_gate_probe = {
        "render_button_condition": bool(enabled),
        "pres_show_apply": bool(enabled),
        "effective_render_action_type": "apply_resolved_candidate" if enabled else "",
        "terminal_exact_accepted": status == "pass",
        "button_contract_enabled": bool(enabled),
        "final_view_cta_enabled": bool(enabled),
    }
    exact_rows = {}
    if status == "blocked":
        exact_rows = {
            "family": {
                "reason": blocking_reason,
                "failed_check_name": family_id,
                "owner": family_id,
            }
        }
    details = {
        "button_contract": contract,
        "render_gate_probe": render_gate_probe,
        "candidate_search_evidence": {
            "selected_family_id": family_id,
            "candidate_id": candidate_id,
            "expected_colour": colour,
        },
        "selected_family_id": family_id,
        "selected_family": family_id,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "apply_payload_family_id": family_id if enabled else "",
        "candidate_family_id": family_id,
        "card_family_id": family_id,
        "family_route_owner": "synthetic_family_render_model_formatting_snapshot",
        "exact_blockers_by_family": exact_rows,
        "blocking_reason": blocking_reason if status == "blocked" else "",
    }
    vm = {
        "status": status,
        "pill": pill,
        "title": title,
        "tone": tone,
        "summary_line": "All checks pass." if status == "pass" else "Synthetic formatting case.",
        "section_title": "Status" if status == "pass" else ("Why action is required" if status == "action" else "Why repair is blocked"),
        "reasons": reasons,
        "cta": cta,
        "selected_family_id": family_id,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "apply_payload_family_id": family_id if enabled else "",
        "candidate_family_id": family_id,
        "card_family_id": family_id,
        "governing_label": "Governing utilisation 0.67" if status != "blocked" else family_id,
        "current": [
            {"label": "Bending", "value": "0.67", "status": "PASS"},
            {"label": "Shear", "value": "0.67", "status": "PASS"},
        ],
        "preview": {
            "bending": {"before": "0.67", "after": "0.67", "status": "PASS"},
            "shear": {"before": "0.67", "after": "0.67", "status": "PASS"},
        },
        "details": details,
    }
    card_class = f"fast-guidance-item {status}"
    if status == "pass":
        card_class += " guidance-success"
    return vm, card_class


def _validate_render_model(
    *,
    family_id: str,
    colour: str | None,
    render_model: dict[str, Any],
    html: str,
    reference_keys: tuple[str, ...],
) -> list[str]:
    failures: list[str] = []
    status_formats = allowed_title_status_formats()
    allowed_statuses = {str(value) for value in status_formats.get("statuses") or []}
    allowed_pills = {str(value) for value in status_formats.get("pill_labels") or []}
    reason_contract = allowed_reason_why_rows()
    required_reason_fields = {str(value) for value in reason_contract.get("required_row_fields") or []}
    allowed_reason_tones = {str(value) for value in reason_contract.get("allowed_tones") or []}

    keys = tuple(sorted(render_model.keys()))
    if keys != reference_keys:
        failures.append(f"{family_id}:render_model_key_signature_drift")
    for field in required_render_model_fields():
        if field not in render_model:
            failures.append(f"{family_id}:missing_render_model_field:{field}")

    status = str(render_model.get("status") or "")
    pill = str(render_model.get("pill") or "")
    if status not in allowed_statuses:
        failures.append(f"{family_id}:status_not_allowed:{status}")
    if pill not in allowed_pills:
        failures.append(f"{family_id}:pill_not_allowed:{pill}")

    if str(render_model.get("family") or "") != family_id:
        failures.append(f"{family_id}:family_field_mismatch")
    if str(render_model.get("family_label") or "") != family_id:
        failures.append(f"{family_id}:family_label_mismatch")
    data_attributes = dict(render_model.get("data_attributes") or {})
    verifier_fields = dict(render_model.get("verifier_fields") or {})
    for field in ("selected_family_id", "published_family_id", "cta_family_id", "card_family_id"):
        if str(data_attributes.get(field) or "") != family_id:
            failures.append(f"{family_id}:data_attribute_mismatch:{field}")
    if str(verifier_fields.get("selected_family_id") or "") != family_id:
        failures.append(f"{family_id}:verifier_selected_family_mismatch")

    final_reasons = list(render_model.get("final_reasons") or [])
    if not final_reasons:
        failures.append(f"{family_id}:final_reasons_empty")
    for index, row in enumerate(final_reasons):
        if not isinstance(row, dict):
            failures.append(f"{family_id}:final_reason_row_not_dict:{index}")
            continue
        for field in required_reason_fields:
            if field not in row:
                failures.append(f"{family_id}:final_reason_row_missing_field:{index}:{field}")
        tone = str(row.get("tone") or "")
        if tone and tone not in allowed_reason_tones:
            failures.append(f"{family_id}:final_reason_row_tone_not_allowed:{index}:{tone}")

    display_rows = list(render_model.get("reason_display_rows") or [])
    if not display_rows:
        failures.append(f"{family_id}:reason_display_rows_empty")
    for index, row in enumerate(display_rows):
        if not isinstance(row, dict):
            failures.append(f"{family_id}:reason_display_row_not_dict:{index}")
            continue
        for field in ("label", "text"):
            if field not in row:
                failures.append(f"{family_id}:reason_display_row_missing_field:{index}:{field}")

    button_attrs = dict(render_model.get("button_contract_attributes") or {})
    cta_enabled = bool(render_model.get("cta_enabled"))
    expected_enabled = colour in {"RED", "BLUE"}
    if cta_enabled != expected_enabled:
        failures.append(f"{family_id}:cta_enabled_mismatch")
    if cta_enabled:
        expected_label = str(cta_display_wording_expectations().get("enabled_label") or "")
        if expected_label and str(render_model.get("cta_label") or "") != expected_label:
            failures.append(f"{family_id}:cta_label_mismatch")
        if str(button_attrs.get("action_type") or "") != "apply_resolved_candidate":
            failures.append(f"{family_id}:button_action_type_mismatch")
    if not html.strip():
        failures.append(f"{family_id}:empty_rendered_html")
    return failures


def _snapshot_rows() -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    import inputs_page as module

    colour_map = _colour_family_map()
    family_ids = list(allowed_family_ids())
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    reference_keys: tuple[str, ...] | None = None
    for family_id in family_ids:
        colour = colour_map.get(family_id)
        vm, card_class = _vm_for_family(family_id, colour)
        render_model = module._build_design_guide_card_render_model(vm, card_class=card_class)
        html = module._design_guide_dashboard_card_html_from_render_model(render_model)
        render_dict = render_model.to_dict()
        if reference_keys is None:
            reference_keys = tuple(sorted(render_dict.keys()))
        family_failures = _validate_render_model(
            family_id=family_id,
            colour=colour,
            render_model=render_dict,
            html=html,
            reference_keys=reference_keys,
        )
        failures.extend(family_failures)
        rows.append(
            {
                "family_id": family_id,
                "expected_colour": colour,
                "status": render_dict.get("status"),
                "pill": render_dict.get("pill"),
                "card_tone": render_dict.get("card_tone"),
                "card_class": render_dict.get("card_class"),
                "cta_enabled": render_dict.get("cta_enabled"),
                "cta_label": render_dict.get("cta_label"),
                "section_title": render_dict.get("section_title"),
                "reason_display_row_count": len(render_dict.get("reason_display_rows") or []),
                "render_model_key_signature": sorted(render_dict.keys()),
                "render_model_hash": _stable_hash(render_dict),
                "rendered_html_hash": _stable_hash(html),
                "failures": family_failures,
            }
        )
    meta = {
        "allowed_family_count": len(family_ids),
        "families_with_render_model_cases": len(rows),
        "reference_key_signature": list(reference_keys or ()),
        "missing_colour_contract_families": [family_id for family_id in family_ids if family_id not in colour_map],
    }
    return rows, failures, meta


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_family_render_model_formatting_snapshot_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_family_render_model_formatting_snapshot_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    status = payload.get("status")
    meta = dict(payload.get("meta") or {})
    lines = [
        "# Design Guide Family Render-Model Formatting Snapshot",
        "",
        f"Status: `{status}`",
        "",
        "## Executive Summary",
        "",
        "- Proof-only family-exhaustive render-model snapshot.",
        "- Builds one synthetic render-model fixture for every contract-allowed family id.",
        "- Uses the live `inputs_page._build_design_guide_card_render_model(...)` wrapper and UI HTML renderer.",
        "- No product behaviour, visible wording, CTA/apply semantics, family runtime, or renderer ownership changed.",
        "",
        "## Coverage",
        "",
        f"- Allowed families: `{meta.get('allowed_family_count')}`",
        f"- Render-model family cases: `{meta.get('families_with_render_model_cases')}`",
        f"- Required render-model fields: `{len(required_render_model_fields())}`",
        f"- Missing colour-contract families: `{', '.join(meta.get('missing_colour_contract_families') or []) or '-'}`",
        "",
        "## Family Rows",
        "",
        "| Family | Colour | Status | Pill | CTA | Reason rows | Model hash | HTML hash | Failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload.get("rows") or []:
        lines.append(
            "| `{family}` | `{colour}` | `{status}` | `{pill}` | `{cta}` | `{reasons}` | `{model}` | `{html}` | {failures} |".format(
                family=row.get("family_id"),
                colour=row.get("expected_colour"),
                status=row.get("status"),
                pill=row.get("pill"),
                cta=row.get("cta_enabled"),
                reasons=row.get("reason_display_row_count"),
                model=row.get("render_model_hash"),
                html=row.get("rendered_html_hash"),
                failures=", ".join(f"`{failure}`" for failure in (row.get("failures") or [])) or "-",
            )
        )
    lines.extend(
        [
            "",
            "## Failures",
            "",
            *([f"- `{failure}`" for failure in payload.get("failures") or []] or ["- none"]),
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["DESIGN_GUIDE_CARD_RENDER_MODEL_SNAPSHOT_PATH"] = str(
        TRACE_DIR / f"design_guide_family_render_model_formatting_{timestamp}.jsonl"
    )

    rows, failures, meta = _snapshot_rows()
    missing_colour = list(meta.get("missing_colour_contract_families") or [])
    status = "FAIL" if failures else ("PARTIAL" if missing_colour else "PASS")
    payload = {
        "schema": "design_guide_family_render_model_formatting_snapshot.v1",
        "status": status,
        "failures": failures,
        "coverage_gaps": ["families_missing_status_colour_contract"] if missing_colour else [],
        "meta": meta,
        "allowed_family_ids": list(allowed_family_ids()),
        "required_render_model_fields": list(required_render_model_fields()),
        "required_html_model_hash_fields": list(required_html_model_hash_fields()),
        "rows": rows,
        "product_behaviour_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    json_path, report_path = _write(payload)
    print(f"design_guide_family_render_model_formatting_snapshot {status}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    if status == "FAIL":
        print(json.dumps({"failures": failures}, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
