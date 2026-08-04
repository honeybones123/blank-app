"""Verify direct shell family identity projection is final-publication owned."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_publication import (  # noqa: E402
    build_final_design_guide_direct_shell_identity_projection,
    stable_final_publication_hash,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    start = source.find(f"def {name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    if next_def < 0:
        return source[start:]
    return source[start:next_def]


def _expected(
    *,
    family_identity: dict[str, Any],
    title: str,
    governing_label: str | None,
    summary_line: str,
    reason_text: str,
) -> dict[str, Any]:
    identity = dict(family_identity or {})
    selected = str(identity.get("selected_family_id") or "").strip()
    published = str(identity.get("published_family_id") or "").strip()
    cta = str(identity.get("cta_family_id") or "").strip()
    apply = str(identity.get("apply_payload_family_id") or "").strip()
    evidence = dict(identity.get("selection_evidence") or {})
    if selected and not identity.get("matched_family_ids"):
        matches = evidence.get("matched_family_ids")
        identity["matched_family_ids"] = list(matches) if isinstance(matches, list) and matches else [selected]
    if selected and not identity.get("raw_state_flags"):
        flags = evidence.get("raw_state_flags")
        if isinstance(flags, dict) and flags:
            identity["raw_state_flags"] = dict(flags)
    title_text = str(title or "").strip()
    governing_label_text = str(governing_label or "").strip() or None
    summary_line_text = str(summary_line or "Run one-click auto design.").strip()
    reason_text_value = str(reason_text or "Run one-click auto design.").strip()
    if selected and published == selected and cta == selected and (not apply or apply == selected):
        identity["apply_payload_family_id"] = selected
        identity["family_match_passed"] = True
        identity["family_match_violation_reason"] = None
        stale_text = " ".join(
            str(part or "")
            for part in (title_text, governing_label_text, summary_line_text, reason_text_value)
        ).lower()
        if "family mismatch blocked" in stale_text or "publication blocked by family contract" in stale_text:
            if selected == "COMBINED_BENDING_SHEAR_FAIL":
                title_text = "Strengthening required for bending and shear"
                governing_label_text = "Combined bending and shear repair"
                summary_line_text = "Run one-click auto design."
                reason_text_value = "Run one-click auto design."
            elif selected == "SHEAR_FAIL_GOVERNS":
                governing_label_text = "Shear repair"
                summary_line_text = "Run one-click auto design."
                reason_text_value = "Run one-click auto design."
    payload = {
        "identity": identity,
        "title": title_text,
        "governing_label": governing_label_text,
        "summary_line": summary_line_text,
        "reason_text": reason_text_value,
    }
    return {
        **payload,
        "projection_hash": stable_final_publication_hash(payload),
        "proof_only": True,
    }


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        {
            "name": "matched_family_ids_filled_from_selected",
            "family_identity": {
                "selected_family_id": "BENDING_FAIL_GOVERNS",
                "published_family_id": "BENDING_FAIL_GOVERNS",
                "cta_family_id": "BENDING_FAIL_GOVERNS",
                "updates": {"D": 650},
            },
            "title": "Strengthening required",
            "governing_label": "Repair preview",
            "summary_line": "Run one-click auto design.",
            "reason_text": "Run one-click auto design.",
        },
        {
            "name": "selection_evidence_fields_preserved",
            "family_identity": {
                "selected_family_id": "SHEAR_FAIL_GOVERNS",
                "published_family_id": "SHEAR_FAIL_GOVERNS",
                "cta_family_id": "SHEAR_FAIL_GOVERNS",
                "selection_evidence": {
                    "matched_family_ids": ["SHEAR_FAIL_GOVERNS"],
                    "raw_state_flags": {"shear_fail": True},
                },
            },
            "title": "Shear capacity is low",
            "governing_label": "Repair preview",
            "summary_line": "Run one-click auto design.",
            "reason_text": "Run one-click auto design.",
        },
        {
            "name": "stale_shear_mismatch_text_repaired",
            "family_identity": {
                "selected_family_id": "SHEAR_FAIL_GOVERNS",
                "published_family_id": "SHEAR_FAIL_GOVERNS",
                "cta_family_id": "SHEAR_FAIL_GOVERNS",
            },
            "title": "Publication blocked by family contract",
            "governing_label": "Family mismatch blocked",
            "summary_line": "Family mismatch blocked",
            "reason_text": "Family mismatch blocked",
        },
        {
            "name": "stale_combined_mismatch_text_repaired",
            "family_identity": {
                "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "published_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "cta_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            },
            "title": "Publication blocked by family contract",
            "governing_label": "Family mismatch blocked",
            "summary_line": "Family mismatch blocked",
            "reason_text": "Family mismatch blocked",
        },
    ]
    rows = []
    for scenario in scenarios:
        projection = build_final_design_guide_direct_shell_identity_projection(
            family_identity=dict(scenario["family_identity"]),
            title=scenario["title"],
            governing_label=scenario["governing_label"],
            summary_line=scenario["summary_line"],
            reason_text=scenario["reason_text"],
        ).to_dict()
        expected = _expected(
            family_identity=dict(scenario["family_identity"]),
            title=scenario["title"],
            governing_label=scenario["governing_label"],
            summary_line=scenario["summary_line"],
            reason_text=scenario["reason_text"],
        )
        rows.append(
            {
                "name": scenario["name"],
                "matches_expected": projection == expected,
                "projection_hash": projection.get("projection_hash"),
                "expected_hash": expected.get("projection_hash"),
                "title": projection.get("title"),
                "governing_label": projection.get("governing_label"),
                "family_match_passed": dict(projection.get("identity") or {}).get("family_match_passed"),
            }
        )
    return rows


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    final_source = _read(FINAL_PUBLICATION)
    helper = _function_body(inputs_source, "_design_guide_direct_action_shell_card_html")
    rows = _scenario_rows()
    source_checks = {
        "adapter_exported": '"build_final_design_guide_direct_shell_identity_projection"' in final_source,
        "adapter_imported": (
            "build_final_design_guide_direct_shell_identity_projection as _build_final_design_guide_direct_shell_identity_projection"
            in inputs_source
        ),
        "helper_uses_adapter": "_build_final_design_guide_direct_shell_identity_projection(" in helper,
        "helper_no_selection_evidence_normalization": "selection_evidence_for_identity" not in helper,
        "helper_no_matched_family_fill": "matched_family_ids" not in helper[: helper.find("vm = {")],
        "helper_no_stale_match_text_repair": "stale_match_text" not in helper,
        "final_publication_no_streamlit_import": "import streamlit" not in final_source.lower()
        and "from streamlit" not in final_source.lower(),
        "final_publication_no_inputs_page_import": "inputs_page" not in final_source,
    }
    failures = []
    for row in rows:
        if not row["matches_expected"]:
            failures.append(f"scenario:{row['name']}")
    for key, value in source_checks.items():
        if value is not True:
            failures.append(f"source:{key}")
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_direct_shell_identity_projection_cutover.v1",
        "status": status,
        "surface": "direct action shell identity projection",
        "projection_scenarios": rows,
        "source_checks": source_checks,
        "failures": failures,
        "ownership_after": {
            "family_identity_projection": "FinalDesignGuidePublication",
            "card_html_rendering": "inputs_page.py",
            "apply_routing": "inputs_page.py",
        },
        "product_behavior_changed": False,
        "next_safe_target": "Audit current/preview row shaping in the direct shell renderer.",
    }


def _write(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_direct_shell_identity_projection_cutover_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_direct_shell_identity_projection_cutover_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_direct_shell_identity_projection_{stamp}.md"
    payload["artifact_paths"] = {
        "json": str(json_path),
        "audit": str(audit_path),
        "report": str(report_path),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        payload["status"],
        "",
        "## Surface Targeted",
        payload["surface"],
        "",
        "## Ownership Before",
        "inputs_page.py normalized direct shell family identity and stale family-mismatch text inside the renderer.",
        "",
        "## Ownership After",
        "FinalDesignGuidePublication projects direct shell family identity; inputs_page.py renders the returned view data.",
        "",
        "## Behaviour Preserved",
        f"Product behavior changed: `{payload['product_behavior_changed']}`.",
        "",
        "## Adapter / Default Rebuild Proof",
        json.dumps(payload["projection_scenarios"], indent=2, sort_keys=True),
        "",
        "## Cutover Proof",
        json.dumps(payload["source_checks"], indent=2, sort_keys=True),
        "",
        "## Deadness / Deletion Proof",
        "The renderer no longer contains the selected-family identity normalization block or stale mismatch text repair block.",
        "",
        "## Lines Removed / Added",
        "Focused identity projection cutover; line-ending churn is not normalized.",
        "",
        "## Files Changed",
        "- inputs_page.py",
        "- design_brain/final_publication.py",
        "- tools/verification/design_guide_direct_shell_identity_projection_cutover.py",
        "",
        "## Verifier Results",
        payload["status"],
        "",
        "## Remaining Page-Owned Authority",
        "Current/preview row shaping and HTML rendering remain page-owned.",
        "",
        "## Next Safe Target",
        payload["next_safe_target"],
        "",
    ]
    audit_path.write_text("\n".join(lines), encoding="utf-8")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    _write(payload)
    print(f"design_guide_direct_shell_identity_projection_cutover {payload['status']}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
