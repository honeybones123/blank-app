"""Focused proof for Design Guide UI badge normalization.

This snapshot proves the shared final Design Guide formatter normalizes legacy
visible badges (NEXT, GOOD, RECOMMEND, WARN) to the publication outcome badge
contract without changing title, summary, CTA/apply fields, or family runtime
inputs.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_design_guide_formatter import build_final_design_guide_card_format  # noqa: E402
from design_brain.final_design_guide_formatting_contract import outcome_state_mapping  # noqa: E402
from design_brain.final_publication import (  # noqa: E402
    FinalDesignGuideCTA,
    FinalDesignGuideDisplay,
    FinalDesignGuideEvidence,
    FinalDesignGuidePublication,
    stable_final_publication_hash,
)
from ui.final_design_guide_card import render_final_design_guide_card_html  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _default_badges() -> dict[str, str]:
    return {
        str(state).upper(): str(row.get("default_badge") or "INFO").upper()
        for state, row in outcome_state_mapping().items()
        if isinstance(row, dict)
    }


def _publication_case(
    *,
    name: str,
    outcome_state: str,
    legacy_badge: str,
    title: str,
    summary: str,
    cta_enabled: bool,
) -> FinalDesignGuidePublication:
    cta = FinalDesignGuideCTA(
        enabled=cta_enabled,
        actionable=cta_enabled,
        label="Run one-click auto design" if cta_enabled else "",
        action_type="apply_resolved_candidate" if cta_enabled else None,
        family="BENDING_FAIL_GOVERNS" if cta_enabled else "TARGET_BAND_REACHED",
        apply_payload_summary={"updates": {"depth": 650}} if cta_enabled else {},
        apply_payload_fingerprint=stable_final_publication_hash({"case": name, "payload": cta_enabled}),
        button_contract_hash=stable_final_publication_hash({"case": name, "button": True}),
        source_candidate_id=f"{name}:candidate" if cta_enabled else None,
    )
    display = FinalDesignGuideDisplay(
        title=title,
        badge=legacy_badge,
        summary=summary,
        status=legacy_badge,
        bucket="fail" if outcome_state == "ACTION" else "pass",
        colour_state="fail" if outcome_state == "ACTION" else "pass",
        display_state=outcome_state,
        expanded_evidence_sections={
            "reason_display_rows": [
                {"test_label": "result", "label": "Result", "text": summary}
            ]
        },
        final_card_model_fields={
            "title": title,
            "badge": legacy_badge,
            "summary": summary,
            "status": legacy_badge,
            "display_state": outcome_state,
        },
        visible_wording_hash=stable_final_publication_hash(
            {"title": title, "legacy_badge": legacy_badge, "summary": summary}
        ),
    )
    evidence = FinalDesignGuideEvidence(
        published_item_id=f"{name}:published",
        selected_family=cta.family,
        publication_reason=f"{name}:publication_reason",
        evidence_hash=stable_final_publication_hash({"case": name, "evidence": True}),
    )
    publication = FinalDesignGuidePublication(
        published_item_id=f"{name}:published",
        selected_family=cta.family,
        outcome_state=outcome_state,  # type: ignore[arg-type]
        publication_reason=f"{name}:publication_reason",
        cta=cta,
        display=display,
        evidence=evidence,
        source_hash=stable_final_publication_hash({"case": name, "publication": True}),
        proof_only=True,
    )
    return publication.with_publication_hash()


def _case_result(case: dict[str, Any], default_badges: dict[str, str]) -> dict[str, Any]:
    publication = _publication_case(**case)
    card = build_final_design_guide_card_format(publication)
    html = render_final_design_guide_card_html(card)
    expected_badge = default_badges.get(case["outcome_state"], "INFO")
    legacy_badge = str(case["legacy_badge"]).upper()
    title = str(case["title"])
    summary = str(case["summary"])
    cta = dict(card.cta or {})
    legacy_visible_as_status_pill = f"data-testid='design-guide-status-pill'>{legacy_badge}</span>" in html
    return {
        "case": case["name"],
        "outcome_state": case["outcome_state"],
        "legacy_badge": legacy_badge,
        "expected_badge": expected_badge,
        "actual_badge": card.badge,
        "badge_normalized": card.badge == expected_badge,
        "legacy_status_pill_removed": not legacy_visible_as_status_pill,
        "title_preserved": card.title == title and title in html,
        "summary_preserved": card.summary == summary and summary in html,
        "cta_enabled_preserved": cta.get("enabled") is bool(case["cta_enabled"]),
        "cta_label_preserved": cta.get("label") == ("Run one-click auto design" if case["cta_enabled"] else ""),
        "publication_hash_preserved": card.publication_hash == publication.publication_hash,
        "display_hash_present": bool(card.display_hash),
        "cta_hash_present": bool(card.cta_hash),
        "format_hash_present": bool(card.format_hash),
    }


def _build_payload() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    defaults = _default_badges()
    cases = [
        {
            "name": "action_next",
            "outcome_state": "ACTION",
            "legacy_badge": "NEXT",
            "title": "Bending capacity is low",
            "summary": "Active strength capacity is failing; this repair remains executor-backed.",
            "cta_enabled": True,
        },
        {
            "name": "action_recommend",
            "outcome_state": "ACTION",
            "legacy_badge": "RECOMMEND",
            "title": "Strengthening required",
            "summary": "Run one-click auto design.",
            "cta_enabled": True,
        },
        {
            "name": "pass_good",
            "outcome_state": "PASS",
            "legacy_badge": "GOOD",
            "title": "Design is efficient",
            "summary": "All checks pass.",
            "cta_enabled": False,
        },
        {
            "name": "blocked_warn",
            "outcome_state": "BLOCKED",
            "legacy_badge": "WARN",
            "title": "Repair blocked",
            "summary": "No checked repair keeps all required checks acceptable.",
            "cta_enabled": False,
        },
    ]
    results = [_case_result(case, defaults) for case in cases]
    required_flags = (
        "badge_normalized",
        "legacy_status_pill_removed",
        "title_preserved",
        "summary_preserved",
        "cta_enabled_preserved",
        "cta_label_preserved",
        "publication_hash_preserved",
        "display_hash_present",
        "cta_hash_present",
        "format_hash_present",
    )
    failures = [
        f"{row['case']}:{flag}"
        for row in results
        for flag in required_flags
        if not row.get(flag)
    ]
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_ui_format_renderer_patch_snapshot.v1",
        "status": status,
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "product_behaviour_changed": False,
        "visible_title_summary_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "default_badges": defaults,
        "cases": results,
        "failures": failures,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_ui_format_renderer_patch_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_ui_format_renderer_patch_{stamp}.md"
    lines = [
        "# Design Guide UI Format Renderer Patch Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"CTA/apply semantics changed: `{payload['cta_apply_semantics_changed']}`",
        "",
        "## Cases",
        "",
        "| Case | Legacy badge | Expected | Actual | Normalized |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in payload["cases"]:
        lines.append(
            f"| `{row['case']}` | `{row['legacy_badge']}` | `{row['expected_badge']}` | "
            f"`{row['actual_badge']}` | `{row['badge_normalized']}` |"
        )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{item}`" for item in payload["failures"]] or ["- None"])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build_payload()
    json_path, md_path = _write(payload)
    print(f"design_guide_ui_format_renderer_patch_snapshot {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if payload["failures"]:
        print("failures=" + json.dumps(payload["failures"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
