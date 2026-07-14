"""Verify renderer-only cleanup of duplicate expanded Design Guide Status rows.

The patch is intentionally narrow: duplicate expanded Status rows may be omitted
only when their text is already visible in the card title/summary/blocker
surface. Unique Status evidence must still render.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_design_guide_formatter import (  # noqa: E402
    FinalDesignGuideCardFormat,
    FinalDesignGuideFormatSection,
)
from ui.final_design_guide_card import render_final_design_guide_card_html  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
RENDERER_PATH = ROOT / "ui" / "final_design_guide_card.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _base_model(*, status_rows: tuple[dict, ...], summary: str, title: str = "Bending cleanup blocked") -> FinalDesignGuideCardFormat:
    return FinalDesignGuideCardFormat(
        selected_family="BENDING_CLEANUP_GOVERNS",
        outcome_state="BLOCKED",
        tone="blue",
        tone_source="test",
        title=title,
        badge="INFO",
        summary=summary,
        blocker_explanation=summary,
        governing_label="utilisation = 0.41",
        cta={
            "enabled": False,
            "label": "",
            "disabled_reason": "blocked",
            "action_type": "",
            "apply_payload_fingerprint": "",
        },
        sections=(
            FinalDesignGuideFormatSection(
                title="Status",
                rows=status_rows,
                visible=True,
            ),
        ),
        required_test_ids=(),
        publication_hash="publication-hash",
        display_hash="display-hash",
        cta_hash="cta-hash",
        evidence_hash="evidence-hash",
        contract_hash="contract-hash",
        format_hash="format-hash",
    )


def _build_payload() -> dict:
    duplicate_summary = (
        "Trial bottom-reinforcement reductions were exhausted and none preserved bending, "
        "shear, crack/deflection serviceability, spacing and ductility checks."
    )
    duplicate_model = _base_model(
        summary=duplicate_summary,
        status_rows=(
            {
                "label": "Bending cleanup blocked",
                "text": duplicate_summary,
            },
        ),
    )
    title_prefixed_duplicate_model = _base_model(
        summary=duplicate_summary,
        status_rows=(
            {
                "label": "",
                "text": f"Bending cleanup blocked: {duplicate_summary}",
            },
        ),
    )
    unique_model = _base_model(
        summary="Cleanup is blocked by the accepted family outcome.",
        status_rows=(
            {
                "label": "Blocker evidence",
                "text": "No checked route can preserve shear reserve while reducing reinforcement.",
            },
        ),
    )
    empty_model = _base_model(summary="All checks pass.", title="Design is efficient", status_rows=())

    duplicate_html = render_final_design_guide_card_html(duplicate_model)
    title_prefixed_duplicate_html = render_final_design_guide_card_html(title_prefixed_duplicate_model)
    unique_html = render_final_design_guide_card_html(unique_model)
    empty_html = render_final_design_guide_card_html(empty_model)

    checks = {
        "duplicate_status_section_omitted": "data-testid='design-guide-main-explanation'" not in duplicate_html,
        "title_prefixed_duplicate_status_section_omitted": (
            "data-testid='design-guide-main-explanation'" not in title_prefixed_duplicate_html
        ),
        "duplicate_title_still_visible": "Bending cleanup blocked" in duplicate_html,
        "duplicate_summary_still_visible": "Trial bottom-reinforcement reductions were exhausted" in duplicate_html,
        "duplicate_cta_attributes_preserved": (
            "data-publication-hash='publication-hash'" in duplicate_html
            and "data-display-hash='display-hash'" in duplicate_html
            and "data-cta-hash='cta-hash'" in duplicate_html
            and "data-cta-disabled-reason='blocked'" in duplicate_html
            and "data-apply-payload-fingerprint=''" in duplicate_html
        ),
        "unique_status_section_still_rendered": "data-testid='design-guide-main-explanation'" in unique_html,
        "unique_status_text_still_rendered": "No checked route can preserve shear reserve" in unique_html,
        "empty_status_section_not_rendered": "data-testid='design-guide-main-explanation'" not in empty_html,
        "renderer_only_surface": "render_final_design_guide_card_html" in RENDERER_PATH.read_text(encoding="utf-8"),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "schema": "design_guide_expanded_status_section_readability_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "created_at": _stamp(),
        "product_behaviour_changed": False,
        "visible_engineering_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "design_brain_authority_changed": False,
        "renderer_path": str(RENDERER_PATH),
        "checks": checks,
        "failures": failures,
        "duplicate_html_sample": duplicate_html[:900],
        "title_prefixed_duplicate_html_sample": title_prefixed_duplicate_html[:900],
        "unique_html_sample": unique_html[:900],
        "result": (
            "Duplicate expanded Status rows are omitted only when already represented by collapsed card text; "
            "unique status evidence remains visible."
        ),
    }


def _write(payload: dict) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_expanded_status_section_readability_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_expanded_status_section_readability_{stamp}.md"
    lines = [
        "# Design Guide Expanded Status Section Readability Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Result: {payload['result']}",
        "",
        "## Behaviour Guarantees",
        "",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"- Visible engineering wording changed: `{payload['visible_engineering_wording_changed']}`",
        f"- CTA/apply semantics changed: `{payload['cta_apply_semantics_changed']}`",
        f"- Family runtimes changed: `{payload['family_runtimes_changed']}`",
        f"- Design Brain authority changed: `{payload['design_brain_authority_changed']}`",
        "",
        "## Checks",
        "",
        "```json",
        json.dumps(payload["checks"], indent=2, sort_keys=True),
        "```",
        "",
        "## Failures",
        "",
        "```json",
        json.dumps(payload["failures"], indent=2, sort_keys=True),
        "```",
        "",
    ]
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build_payload()
    json_path, md_path = _write(payload)
    print(f"design_guide_expanded_status_section_readability {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print("failures=" + json.dumps(payload["failures"], sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
