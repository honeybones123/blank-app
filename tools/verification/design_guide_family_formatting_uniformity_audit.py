"""Audit Design Guide formatting uniformity across governing families.

Audit-only. This does not refactor, delete code, render Streamlit UI, change
wording, change CTA/apply semantics, or change engineering behaviour.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.family_classification import allowed_family_ids  # noqa: E402
from design_brain.display_formatting import build_display_model_from_family_result  # noqa: E402
from design_brain.display_formatting_contract import (  # noqa: E402
    required_sections,
    status_colour_contract,
)
from design_brain.output_formatting_contract import (  # noqa: E402
    required_render_model_fields,
    required_snapshot_cases,
)
from design_brain.shared.schemas import FamilyResult  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _colour_family_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for colour, row in status_colour_contract().items():
        for family in dict(row).get("families") or ():
            out[str(family)] = str(colour).upper()
    return out


def _status_for_colour(colour: str) -> str:
    if colour == "RED":
        return "REPAIR_REQUIRED"
    if colour == "BLUE":
        return "OPTIMISATION_AVAILABLE"
    return "COMPLIANT"


def _synthetic_family_result(family_id: str, colour: str) -> FamilyResult:
    status = _status_for_colour(colour)
    candidate = {
        "candidate_id": f"{family_id}:formatting_uniformity_candidate",
        "updates": {"width": 400, "depth": 650},
        "source": family_id,
        "action_type": "apply_resolved_candidate",
    }
    blockers = [
        {
            "owner": family_id,
            "reason": "Synthetic blocker row for formatting uniformity audit.",
            "type": "formatting_uniformity_probe",
        }
    ]
    evidence = {
        "why_selected": f"{family_id} selected by synthetic formatting audit.",
        "ranking_evidence": {"selected_candidate_id": candidate["candidate_id"], "family_id": family_id},
        "exact_stop_proof": {"allowed": False, "owner": family_id, "reason": "synthetic exact stop"},
        "exhausted_proof": {"allowed": False, "owner": family_id, "reason": "synthetic exhausted proof"},
        "target_band_status": {"bending": "synthetic", "shear": "synthetic"},
    }
    return FamilyResult(
        family_id=family_id,
        is_applicable=True,
        governing_score=1.0 if colour == "RED" else 0.67,
        status=status,
        selected_candidate=candidate,
        updates=dict(candidate["updates"]),
        blockers=blockers,
        evidence=evidence,
        publication={"ignored_by_formatting": True},
        cta_contract={"ignored_by_formatting": True},
        lock_proof={"runtime_authority": family_id, "exact_stop_proof": evidence["exact_stop_proof"]},
    )


def _section_signature(model: Any) -> tuple[str, ...]:
    return tuple(section.title for section in model.sections)


def _item_key_signature(model: Any) -> dict[str, list[list[str]]]:
    out: dict[str, list[list[str]]] = {}
    for section in model.sections:
        rows: list[list[str]] = []
        for item in section.items:
            if isinstance(item, dict):
                rows.append(sorted(str(key) for key in item.keys()))
            else:
                rows.append(["<non-dict>"])
        out[section.title] = rows
    return out


def _audit_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    family_ids = tuple(allowed_family_ids())
    colour_map = _colour_family_map()
    rows: list[dict[str, Any]] = []
    reference_signature: tuple[str, ...] | None = None
    reference_item_keys: dict[str, list[list[str]]] | None = None
    for family_id in family_ids:
        expected_colour = colour_map.get(family_id)
        result = _synthetic_family_result(family_id, expected_colour or "GREEN")
        model = build_display_model_from_family_result(result)
        signature = _section_signature(model)
        item_keys = _item_key_signature(model)
        if reference_signature is None:
            reference_signature = signature
            reference_item_keys = item_keys
        rows.append(
            {
                "family_id": family_id,
                "expected_colour": expected_colour,
                "actual_colour": model.colour,
                "tone": model.tone,
                "icon": model.icon,
                "status": model.status,
                "section_signature": list(signature),
                "section_signature_matches_reference": signature == reference_signature,
                "required_sections_present": set(required_sections()).issubset(set(signature)),
                "item_key_signature_matches_reference": item_keys == reference_item_keys,
                "presentation_hash": model.presentation_hash,
                "source_family_result_hash": model.source_family_result_hash,
                "model": model.to_dict(),
            }
        )
    meta = {
        "reference_family_id": rows[0]["family_id"] if rows else None,
        "reference_section_signature": list(reference_signature or ()),
        "reference_item_key_signature": reference_item_keys or {},
    }
    return rows, meta


def _classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_colour = [row["family_id"] for row in rows if not row.get("expected_colour")]
    wrong_colour = [
        row["family_id"]
        for row in rows
        if row.get("expected_colour") and row.get("expected_colour") != row.get("actual_colour")
    ]
    missing_required_sections = [row["family_id"] for row in rows if not row.get("required_sections_present")]
    section_drift = [row["family_id"] for row in rows if not row.get("section_signature_matches_reference")]
    item_key_drift = [row["family_id"] for row in rows if not row.get("item_key_signature_matches_reference")]
    family_render_snapshot = ROOT / "tools" / "verification" / "design_guide_family_render_model_formatting_snapshot.py"
    render_model_contract = {
        "required_render_model_fields_count": len(required_render_model_fields()),
        "required_snapshot_cases": required_snapshot_cases(),
        "family_specific_render_model_cases_present": family_render_snapshot.exists(),
        "family_specific_render_model_snapshot": str(family_render_snapshot),
        "note": (
            "Existing output-formatting snapshot covers action/blocked/pass states. "
            "The family render-model snapshot covers every selectable family id as a separate "
            "live/render-model fixture."
            if family_render_snapshot.exists()
            else (
                "Existing output-formatting snapshot covers action/blocked/pass states, "
                "not every family id as a separate live/render-model fixture."
            )
        ),
    }
    hard_failures = wrong_colour + missing_required_sections + section_drift + item_key_drift
    coverage_gaps = []
    if missing_colour:
        coverage_gaps.append("families_missing_status_colour_contract")
    if not render_model_contract["family_specific_render_model_cases_present"]:
        coverage_gaps.append("render_model_snapshot_not_family_exhaustive")
    if hard_failures:
        result = "FAIL"
    elif coverage_gaps:
        result = "PARTIAL"
    else:
        result = "PASS"
    return {
        "result": result,
        "hard_failures": hard_failures,
        "coverage_gaps": coverage_gaps,
        "missing_colour_contract_families": missing_colour,
        "wrong_colour_families": wrong_colour,
        "missing_required_sections": missing_required_sections,
        "section_signature_drift_families": section_drift,
        "item_key_signature_drift_families": item_key_drift,
        "render_model_contract": render_model_contract,
        "recommendation": (
            "Add family-exhaustive render-model snapshot cases after this audit, using the same "
            "central render-model contract for every selectable family."
            if coverage_gaps and not hard_failures
            else "Fix formatting drift before adding implementation."
            if hard_failures
            else "Formatting is structurally uniform across audited families."
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_family_formatting_uniformity_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_family_formatting_uniformity_audit_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Family Formatting Uniformity Audit",
        "",
        f"Result: `{cls.get('result')}`",
        "",
        "## Executive Summary",
        "",
        "- Audit-only. No behaviour, wording, CTA/apply, family runtime, or renderer changes were made.",
        "- Display formatting is checked for every contract-allowed family using the same synthetic FamilyResult shape.",
        "- Render-model coverage is checked as contract coverage, not as a live family-by-family fixture.",
        "",
        "## Findings",
        "",
        f"- Hard formatting failures: `{len(cls.get('hard_failures') or [])}`",
        f"- Coverage gaps: `{', '.join(cls.get('coverage_gaps') or []) or '-'}`",
        f"- Missing colour contract families: `{', '.join(cls.get('missing_colour_contract_families') or []) or '-'}`",
        f"- Section signature drift families: `{', '.join(cls.get('section_signature_drift_families') or []) or '-'}`",
        f"- Item key signature drift families: `{', '.join(cls.get('item_key_signature_drift_families') or []) or '-'}`",
        "",
        "## Family Rows",
        "",
        "| Family | Expected colour | Actual colour | Sections match | Required sections | Item keys match |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload.get("rows") or []:
        lines.append(
            "| `{family}` | `{expected}` | `{actual}` | `{sections}` | `{required}` | `{items}` |".format(
                family=row.get("family_id"),
                expected=row.get("expected_colour"),
                actual=row.get("actual_colour"),
                sections=row.get("section_signature_matches_reference"),
                required=row.get("required_sections_present"),
                items=row.get("item_key_signature_matches_reference"),
            )
        )
    lines.extend(
        [
            "",
            "## Render Model Coverage",
            "",
            f"- Required render model fields: `{len(required_render_model_fields())}`",
            "- Existing output-formatting snapshot covers action/blocked/pass states.",
            "- It does not yet prove a family-exhaustive live/render-model fixture for every family id.",
            "",
            "## Recommendation",
            "",
            str(cls.get("recommendation") or ""),
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    rows, meta = _audit_rows()
    classification = _classify(rows)
    payload = {
        "schema": "design_guide_family_formatting_uniformity_audit.v1",
        "classification": classification,
        "row_count": len(rows),
        "required_sections": list(required_sections()),
        "allowed_family_ids": list(allowed_family_ids()),
        "status_colour_contract_families": _colour_family_map(),
        "reference": meta,
        "rows": rows,
        "product_behaviour_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    json_path, report_path = _write(payload)
    result = classification["result"]
    print(f"design_guide_family_formatting_uniformity_audit {result}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    if result == "FAIL":
        print(json.dumps(classification, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
