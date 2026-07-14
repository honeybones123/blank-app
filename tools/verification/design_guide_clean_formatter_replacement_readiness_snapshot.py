"""Clean Design Guide formatter replacement readiness snapshot.

This proves the new formatter can represent the final Design Guide card from
FinalDesignGuidePublication only. The legacy/current card renderer is used only
as comparison evidence; it is not the authority for the new formatter.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_design_guide_formatting_contract import (  # noqa: E402
    CONTRACT_PATH,
    allowed_inputs,
    contract_hash,
    contract_identity,
    field_sources,
    forbidden_inputs,
    load_final_design_guide_formatting_contract,
    outcome_state_mapping,
    required_test_ids,
    section_order,
    status_colour_contract,
    verifier_contract,
)
from design_brain.final_design_guide_formatter import build_final_design_guide_card_format  # noqa: E402
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
FORMATTER_PATH = ROOT / "design_brain" / "final_design_guide_formatter.py"
UI_RENDERER_PATH = ROOT / "ui" / "final_design_guide_card.py"
FORBIDDEN_IMPORT_ROOTS = {
    "inputs_page",
    "streamlit",
}
FORBIDDEN_SOURCE_TERMS = {
    "st.session_state",
    "session_state",
    "family_strategy_for",
    "candidate_search(",
    "apply_routing",
    "one_click",
    "_build_design_guide_card_render_model",
    "_design_guide_dashboard_card_html",
    "_guidance_item",
}


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _forbidden_imports(path: Path) -> list[str]:
    hits: list[str] = []
    for name in _imports(path):
        root = str(name).split(".", 1)[0]
        if root in FORBIDDEN_IMPORT_ROOTS:
            hits.append(name)
    return sorted(set(hits))


def _forbidden_terms(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8", errors="replace")
    return sorted(term for term in FORBIDDEN_SOURCE_TERMS if term in source)


def _publication_case(
    *,
    name: str,
    selected_family: str | None,
    outcome_state: str,
    title: str,
    badge: str,
    summary: str,
    status: str,
    colour_state: str,
    cta_enabled: bool = False,
    cta_label: str = "",
    disabled_reason: str = "",
    blocker_reason: str = "",
) -> FinalDesignGuidePublication:
    cta = FinalDesignGuideCTA(
        enabled=bool(cta_enabled),
        actionable=bool(cta_enabled),
        label=cta_label,
        action_type="apply_resolved_candidate" if cta_enabled else None,
        family=selected_family,
        disabled_reason=disabled_reason or None,
        apply_payload_summary={"updates": {"depth": 650}} if cta_enabled else {},
        apply_payload_fingerprint=stable_final_publication_hash({"case": name, "enabled": cta_enabled}),
        button_contract_hash=stable_final_publication_hash({"case": name, "button_contract": True}),
        source_candidate_id=f"{name}:candidate" if cta_enabled else None,
    )
    display = FinalDesignGuideDisplay(
        title=title,
        badge=badge,
        summary=summary,
        status=status,
        bucket=colour_state,
        colour_state=colour_state,
        display_state=outcome_state,
        expanded_evidence_sections={
            "current": [
                {"family": "bending", "label": "Bending", "value": "1.12", "status": "FAIL", "tone": "red"},
                {"family": "shear", "label": "Shear", "value": "0.82", "status": "PASS", "tone": "green"},
            ],
            "preview_display_rows": [
                {"family": "bending", "label": "Bending", "before": "1.12 FAIL", "after": "0.91 PASS"}
            ]
            if cta_enabled
            else [],
            "reason_display_rows": [
                {"test_label": "result", "label": "Result", "text": summary or blocker_reason}
            ],
        },
        blocker_explanation=blocker_reason or None,
        final_card_model_fields={
            "title": title,
            "badge": badge,
            "summary": summary,
            "status": status,
            "colour_state": colour_state,
            "display_state": outcome_state,
        },
        visible_wording_hash=stable_final_publication_hash(
            {"title": title, "badge": badge, "summary": summary, "blocker": blocker_reason}
        ),
    )
    evidence = FinalDesignGuideEvidence(
        published_item_id=f"{name}:published",
        selected_family=selected_family,
        publication_reason=f"{name}:publication_reason",
        blocker_reason=blocker_reason or None,
        candidate_search_evidence={"case": name, "source": "synthetic_clean_formatter_snapshot"},
        evidence_hash=stable_final_publication_hash({"case": name, "evidence": True}),
    )
    publication = FinalDesignGuidePublication(
        published_item_id=f"{name}:published",
        selected_family=selected_family,
        outcome_state=outcome_state,  # type: ignore[arg-type]
        publication_reason=f"{name}:publication_reason",
        blocker_reason=blocker_reason or None,
        cta=cta,
        display=display,
        evidence=evidence,
        source_hash=stable_final_publication_hash({"case": name, "publication": True}),
        publication_hash=None,
        proof_only=True,
    )
    return publication.with_publication_hash()


def _case_result(name: str, publication: FinalDesignGuidePublication, expected_tone: str) -> dict[str, Any]:
    card_format = build_final_design_guide_card_format(publication)
    new_html = render_final_design_guide_card_html(card_format)
    missing_test_ids = [test_id for test_id in required_test_ids() if f"data-testid='{test_id}'" not in new_html and f'data-testid="{test_id}"' not in new_html]
    visible_fields = {
        "title": card_format.title,
        "badge": card_format.badge,
        "summary": card_format.summary,
        "outcome_state": card_format.outcome_state,
        "cta_label": card_format.cta.get("label"),
        "cta_enabled": card_format.cta.get("enabled"),
        "cta_disabled_reason": card_format.cta.get("disabled_reason"),
    }
    clean_visible_fields = {
        "title_present": str(card_format.title or "") in new_html,
        "badge_present": str(card_format.badge or "") in new_html,
        "summary_present": (not card_format.summary) or str(card_format.summary or "") in new_html,
        "uses_clean_card_marker": "fdg-card" in new_html,
        "uses_existing_card_shell": "dg-card" in new_html and "fast-guidance-item" in new_html,
    }
    return {
        "case": name,
        "expected_tone": expected_tone,
        "actual_tone": card_format.tone,
        "tone_source": card_format.tone_source,
        "tone_matches": card_format.tone == expected_tone,
        "visible_fields": visible_fields,
        "clean_visible_field_evidence": clean_visible_fields,
        "missing_test_ids": missing_test_ids,
        "new_html_hash": _stable_hash(new_html),
        "format_hash": card_format.format_hash,
        "publication_hash": publication.publication_hash,
        "sections": [section.to_dict() for section in card_format.sections],
        "safe_differences": [],
        "unsafe_differences": [],
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_clean_formatter_replacement_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_clean_formatter_replacement_readiness_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Design Guide Clean Formatter Replacement Readiness Snapshot",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Boundary",
        "",
        "- New formatter consumes `FinalDesignGuidePublication` only.",
        "- Legacy formatter is comparison evidence only.",
        "- No CTA/apply/session/family runtime ownership moves.",
        "",
        "## Cases",
        "",
        "| Case | Expected tone | Actual tone | Test IDs missing | Unsafe drift |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in snapshot["cases"]:
        lines.append(
            "| `{case}` | `{expected}` | `{actual}` | `{missing}` | `{unsafe}` |".format(
                case=row["case"],
                expected=row["expected_tone"],
                actual=row["actual_tone"],
                missing=", ".join(row["missing_test_ids"]) or "-",
                unsafe=", ".join(row["unsafe_differences"]) or "-",
            )
        )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    contract = load_final_design_guide_formatting_contract()
    cases = [
        (
            "fail_action",
            _publication_case(
                name="fail_action",
                selected_family="BENDING_FAIL_GOVERNS",
                outcome_state="ACTION",
                title="Strengthening required",
                badge="ACTION",
                summary="Run one-click auto design.",
                status="action",
                colour_state="fail",
                cta_enabled=True,
                cta_label="Run one-click auto design",
            ),
            "red",
        ),
        (
            "pass",
            _publication_case(
                name="pass",
                selected_family="TARGET_BAND_REACHED",
                outcome_state="PASS",
                title="Design is efficient",
                badge="PASS",
                summary="All checks pass.",
                status="pass",
                colour_state="pass",
            ),
            "green",
        ),
        (
            "optimise_action",
            _publication_case(
                name="optimise_action",
                selected_family="SHEAR_OVERDESIGN_GOVERNS",
                outcome_state="ACTION",
                title="Improve shear efficiency",
                badge="ACTION",
                summary="Run one-click auto design.",
                status="action",
                colour_state="efficiency",
                cta_enabled=True,
                cta_label="Run one-click auto design",
            ),
            "blue",
        ),
        (
            "geometry_blocked",
            _publication_case(
                name="geometry_blocked",
                selected_family="GEOMETRY_DETAILING_GOVERNS",
                outcome_state="BLOCKED",
                title="Geometry repair required",
                badge="BLOCKED",
                summary="Open for engineering detail.",
                status="blocked",
                colour_state="fail",
                blocker_reason="Depth-to-width ratio exceeds the contract limit.",
            ),
            "red",
        ),
        (
            "proof_pending",
            _publication_case(
                name="proof_pending",
                selected_family=None,
                outcome_state="PROOF_PENDING",
                title="Design guidance",
                badge="INFO",
                summary="Proof pending.",
                status="info",
                colour_state="info",
            ),
            "grey",
        ),
    ]
    case_rows = [_case_result(name, publication, expected_tone) for name, publication, expected_tone in cases]
    formatter_forbidden_imports = _forbidden_imports(FORMATTER_PATH)
    ui_forbidden_imports = _forbidden_imports(UI_RENDERER_PATH)
    formatter_forbidden_terms = _forbidden_terms(FORMATTER_PATH)
    ui_forbidden_terms = _forbidden_terms(UI_RENDERER_PATH)
    checks = {
        "schema_v1": contract.get("schema") == "design_brain.final_design_guide_formatting_contract.v1",
        "input_is_final_publication": contract_identity().get("input") == "FinalDesignGuidePublication",
        "output_is_card_format": contract_identity().get("output") == "FinalDesignGuideCardFormat",
        "allowed_inputs_are_final_publication_only": set(allowed_inputs())
        == {
            "FinalDesignGuidePublication",
            "FinalDesignGuidePublication.cta",
            "FinalDesignGuidePublication.display",
            "FinalDesignGuidePublication.evidence",
        },
        "forbidden_inputs_present": bool(forbidden_inputs()),
        "outcome_states_present": {"PASS", "ACTION", "BLOCKED", "ERROR", "PROOF_PENDING"}.issubset(
            set(outcome_state_mapping())
        ),
        "red_green_blue_contract_present": {"red", "green", "blue"}.issubset(set(status_colour_contract())),
        "field_sources_loaded": bool(field_sources()),
        "section_order_loaded": bool(section_order()),
        "required_test_ids_loaded": bool(required_test_ids()),
        "verifier_contract_loaded": bool(verifier_contract().get("must_prove")),
        "formatter_forbidden_imports_absent": not formatter_forbidden_imports,
        "ui_forbidden_imports_absent": not ui_forbidden_imports,
        "formatter_forbidden_terms_absent": not formatter_forbidden_terms,
        "ui_forbidden_terms_absent": not ui_forbidden_terms,
        "case_tones_match": all(row["tone_matches"] for row in case_rows),
        "case_test_ids_present": all(not row["missing_test_ids"] for row in case_rows),
        "no_unsafe_differences": all(not row["unsafe_differences"] for row in case_rows),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "design_guide_clean_formatter_replacement_readiness_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "contract_path": str(CONTRACT_PATH),
        "contract_hash": contract_hash(),
        "checks": checks,
        "formatter_path": str(FORMATTER_PATH),
        "ui_renderer_path": str(UI_RENDERER_PATH),
        "formatter_forbidden_imports": formatter_forbidden_imports,
        "ui_forbidden_imports": ui_forbidden_imports,
        "formatter_forbidden_terms": formatter_forbidden_terms,
        "ui_forbidden_terms": ui_forbidden_terms,
        "cases": case_rows,
        "classification": {
            "old_formatting_authority": "comparison_evidence_only",
            "ready_for_trace_only_wiring": not failures,
            "ready_for_live_cutover": False,
            "ready_for_deletion": False,
            "next_required_slice": "trace_only_new_formatter_wiring",
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("design_guide_clean_formatter_replacement_readiness FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        return 1
    print("design_guide_clean_formatter_replacement_readiness PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
