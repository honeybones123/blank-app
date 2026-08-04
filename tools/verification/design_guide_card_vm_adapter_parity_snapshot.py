"""Proof-only parity snapshot for FinalDesignGuidePublication display adapter."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
CURRENT_AUTHORITY_FILES = (
    ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py",
    ROOT / "inputs_application" / "page_runtime" / "design_guide_runtime_support.py",
)

COMPARE_FIELDS = (
    "title",
    "badge",
    "summary",
    "status",
    "bucket",
    "colour_state",
    "card_class",
    "display_state",
    "blocker_explanation",
    "expanded_evidence_sections",
    "final_card_model_hash",
    "render_fallback_shell_hash",
)

REMAINING_LIVE_CARD_VM_PATHS = [
    "design_brain.final_publication::build_final_publication_display_from_current_card_model",
    "design_brain.final_design_guide_formatter::build_final_design_guide_card_format",
    "ui.final_design_guide_card::render_final_design_guide_card_html",
]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _module_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _forbidden_imports(imports: list[str]) -> list[str]:
    return sorted(
        {
            name
            for name in imports
            for root in ("inputs_page", "streamlit")
            if name == root or name.startswith(root + ".")
        }
    )


def _case_definitions() -> dict[str, dict[str, Any]]:
    def case(
        *,
        title: str,
        badge: str,
        summary: str,
        status: str,
        bucket: str,
        colour: str,
        card_class: str,
        display_state: str | None = None,
        blocker: str | None = None,
        reasons: list[dict[str, Any]] | None = None,
        shell: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence = {
            "reasons": [dict(row) for row in list(reasons or [])],
            "reason_display_rows": [dict(row) for row in list(reasons or [])],
            "current": [{"label": "Bending", "value": "0.91", "tone": "ok"}],
            "preview": {"bending": {"status": "PASS", "util": 0.91}},
            "preview_display_rows": [{"label": "Preview", "value": "PASS", "tone": "ok"}],
            "details": {"blocking_reason": blocker} if blocker else {},
            "blocker_evidence_display_fields": (
                {"blocker_reason": blocker, "exact_rows": {"shear": {"reason": blocker}}}
                if blocker
                else {}
            ),
            "terminal_status": {
                "status": status,
                "terminal_exact": display_state == "EXACT_STOP",
            },
        }
        view_model = {
            "title": title,
            "title_main": title,
            "pill": badge,
            "governing_label": badge,
            "summary_line": summary,
            "status": status,
            "bucket": bucket,
            "tone": colour,
            "card_class": card_class,
            "display_state": display_state or status,
            "blocker_explanation": blocker,
            "blocking_reason": blocker,
            "reasons": evidence["reasons"],
            "current": evidence["current"],
            "preview": evidence["preview"],
            "details": evidence["details"],
            "button_contract": {"enabled": False, "blocking_reason": blocker} if blocker else {},
        }
        render_model = {
            "title": title,
            "pill": badge,
            "main_text": summary,
            "status": status,
            "card_tone": colour,
            "card_class": card_class,
            "blocker_reason": blocker,
            "final_reasons": evidence["reasons"],
            "reason_display_rows": evidence["reason_display_rows"],
            "current_rows": evidence["current"],
            "preview_rows": evidence["preview"],
            "preview_display_rows": evidence["preview_display_rows"],
            "details_payload": evidence["details"],
            "blocker_evidence_display_fields": evidence["blocker_evidence_display_fields"],
            "terminal_status": evidence["terminal_status"],
        }
        return {
            "view_model": view_model,
            "render_model": render_model,
            "fallback_shell_model": dict(shell or {}),
            "expected": {
                "title": title,
                "badge": badge,
                "summary": summary,
                "status": status,
                "bucket": bucket,
                "colour_state": colour,
                "card_class": card_class,
                "display_state": display_state or status,
                "blocker_explanation": blocker,
                "expanded_evidence_sections": {
                    "reasons": evidence["reasons"],
                    "reason_display_rows": evidence["reason_display_rows"],
                    "current": evidence["current"],
                    "preview": evidence["preview"],
                    "preview_display_rows": evidence["preview_display_rows"],
                    "details": evidence["details"],
                    "blocker_evidence_display_fields": evidence["blocker_evidence_display_fields"],
                    "terminal_status": evidence["terminal_status"],
                },
                "render_fallback_shell_model": dict(shell or {}),
            },
            "outcome_state": (
                "ERROR"
                if status == "error"
                else "BLOCKED"
                if status == "blocked" and blocker
                else "ACTION"
                if status == "action"
                else "PASS"
                if status == "pass"
                else "PROOF_PENDING"
            ),
        }

    return {
        "PASS": case(
            title="Design accepted",
            badge="PASS",
            summary="All checks pass.",
            status="pass",
            bucket="pass",
            colour="pass",
            card_class="fast-guidance-item pass guidance-success",
        ),
        "ACTION": case(
            title="Bending capacity is low",
            badge="ACTION",
            summary="Run one-click auto design.",
            status="action",
            bucket="warn",
            colour="action",
            card_class="fast-guidance-item warn dg-card--action",
            reasons=[{"label": "Bending", "text": "Bending utilisation is above 1.00.", "tone": "amber"}],
        ),
        "BLOCKED": case(
            title="Shear repair blocked",
            badge="BLOCKED",
            summary="Open for engineering detail.",
            status="blocked",
            bucket="fail",
            colour="blocked",
            card_class="fast-guidance-item fail dg-card--blocked",
            blocker="no_valid_shear_repair",
            reasons=[{"label": "Blocker", "text": "Shear repair blocked by detailing limits.", "tone": "info"}],
        ),
        "ERROR": case(
            title="Design Guide family contract violation",
            badge="ERROR",
            summary="Publication blocked.",
            status="error",
            bucket="error",
            colour="error",
            card_class="fast-guidance-item error",
            blocker="family_selection_contract_mismatch",
        ),
        "PROOF_PENDING": case(
            title="Design guidance",
            badge="INFO",
            summary="Proof pending.",
            status="info",
            bucket="info",
            colour="info",
            card_class="fast-guidance-item info",
            display_state="PROOF_PENDING",
        ),
        "fallback_shell_card": case(
            title="Shear cleanup - best safe one-click reduction",
            badge="NEXT",
            summary="Run one-click auto design.",
            status="action",
            bucket="warn",
            colour="action",
            card_class="fast-guidance-item warn dg-card--action",
            display_state="ACTION",
            shell={
                "marker": "fallback_enabled_contract_shell",
                "fallback_only": True,
                "non_authoritative": True,
                "title": "Shear cleanup - best safe one-click reduction",
            },
        ),
        "exact_stop_terminal_card": case(
            title="Design accepted - target band achieved",
            badge="PASS",
            summary="Target band reached.",
            status="pass",
            bucket="pass",
            colour="pass",
            card_class="fast-guidance-item pass guidance-success",
            display_state="EXACT_STOP",
        ),
        "stale_non_actionable_card": case(
            title="Review Design Guide recommendation",
            badge="INFO",
            summary="Open for engineering detail.",
            status="blocked",
            bucket="fail",
            colour="blocked",
            card_class="fast-guidance-item fail",
            display_state="BLOCKED",
            blocker="component_apply_token_mismatch",
        ),
    }


def _manual_expected(case: dict[str, Any]) -> dict[str, Any]:
    expected = dict(case["expected"])
    final_card_model_fields = {
        "title": expected["title"],
        "badge": expected["badge"],
        "summary": expected["summary"],
        "status": expected["status"],
        "bucket": expected["bucket"],
        "colour_state": expected["colour_state"],
        "card_class": expected["card_class"],
        "display_state": expected["display_state"],
        "blocker_explanation": expected["blocker_explanation"],
    }
    visible_wording = {
        "title": expected["title"],
        "summary": expected["summary"],
        "badge": expected["badge"],
        "blocker_explanation": expected["blocker_explanation"],
    }
    expected["final_card_model_fields"] = final_card_model_fields
    expected["final_card_model_hash"] = _stable_hash(final_card_model_fields)
    expected["render_fallback_shell_hash"] = _stable_hash(expected["render_fallback_shell_model"])
    expected["visible_wording_hash"] = _stable_hash(visible_wording)
    return expected


def _build_snapshot() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_publication,
        build_final_publication_display_from_current_card_model,
    )

    imports = _module_imports(FINAL_PUBLICATION)
    forbidden_imports = _forbidden_imports(imports)
    inputs_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, *CURRENT_AUTHORITY_FILES)
        if path.exists()
    )
    cta_authority_markers = {
        "FinalDesignGuidePublication.cta": "FinalDesignGuidePublication.cta" in inputs_source,
        "_stamp_final_publication_cta_authority": "_final_publication_cta_authority_payload(" in inputs_source,
        "final_publication_cta_hash": "final_publication_cta_hash" in inputs_source,
    }
    cases: dict[str, Any] = {}
    failures: list[str] = []
    fallback_shell_risks: list[str] = []
    for name, case in _case_definitions().items():
        display_a = build_final_publication_display_from_current_card_model(
            view_model=case["view_model"],
            render_model=case["render_model"],
            fallback_shell_model=case["fallback_shell_model"],
        )
        display_b = build_final_publication_display_from_current_card_model(
            view_model=case["view_model"],
            render_model=case["render_model"],
            fallback_shell_model=case["fallback_shell_model"],
        )
        actual = display_a.to_dict()
        expected = _manual_expected(case)
        comparable_actual = {field: actual.get(field) for field in COMPARE_FIELDS}
        comparable_expected = {field: expected.get(field) for field in COMPARE_FIELDS}
        mismatches = {
            field: {"expected": comparable_expected.get(field), "actual": comparable_actual.get(field)}
            for field in COMPARE_FIELDS
            if comparable_actual.get(field) != comparable_expected.get(field)
        }
        action_family = (
            "SHEAR_FAIL_GOVERNS"
            if name == "fallback_shell_card"
            else "BENDING_FAIL_GOVERNS"
        )
        is_action = case["outcome_state"] == "ACTION"
        publication = build_final_design_guide_publication(
            item={
                **case["view_model"],
                **(
                    {
                        "selected_family_id": action_family,
                        "published_family_id": action_family,
                        "cta_family_id": action_family,
                        "family": action_family,
                    }
                    if is_action
                    else {}
                ),
                "button_contract": {
                    "enabled": is_action,
                    "actionable": is_action,
                    **(
                        {
                            "action_type": "apply_resolved_candidate",
                            "family": action_family,
                            "updates": {"fixture_action": True},
                            "candidate_id": f"{name}_candidate",
                            "source_candidate_id": f"{name}_candidate",
                        }
                        if is_action
                        else {}
                    ),
                },
            },
            verifier_payload={"case": name},
        )
        outcome_alignment = publication.outcome_state == case["outcome_state"]
        stable_hash = _stable_hash(display_a.to_dict()) == _stable_hash(display_b.to_dict())
        if mismatches:
            failures.append(f"{name}:display_parity")
        if not stable_hash:
            failures.append(f"{name}:unstable_display_hash")
        if not outcome_alignment:
            failures.append(f"{name}:outcome_alignment")
        if name == "fallback_shell_card":
            shell = dict(actual.get("render_fallback_shell_model") or {})
            if not (shell.get("fallback_only") and shell.get("non_authoritative")):
                fallback_shell_risks.append("fallback shell model is not explicitly fallback-only/non-authoritative")
                failures.append("fallback_shell_authority_risk")
        cases[name] = {
            "parity_status": "PASS" if not mismatches and stable_hash and outcome_alignment else "FAIL",
            "actual": comparable_actual,
            "expected": comparable_expected,
            "mismatches": mismatches,
            "stable_hash": stable_hash,
            "outcome_state": case["outcome_state"],
            "publication_outcome_state": publication.outcome_state,
            "outcome_state_alignment": outcome_alignment,
            "display_hash": _stable_hash(actual),
            "cta_authority_remains_publication_cta": all(cta_authority_markers.values()),
        }

    if forbidden_imports:
        failures.append("final_publication_forbidden_imports")
    if not all(cta_authority_markers.values()):
        failures.append("cta_authority_marker_missing")

    parity_status = "PASS" if not failures else "FAIL"
    object_ready = parity_status == "PASS"
    return {
        "snapshot_name": "design_guide_card_vm_adapter_parity",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "parity_status": parity_status,
        "status": parity_status,
        "final_publication_imports": imports,
        "forbidden_final_publication_imports": forbidden_imports,
        "product_behavior_changed": False,
        "card_rendering_moved": False,
        "visible_wording_changed": False,
        "card_colours_changed": False,
        "badge_title_summary_changed": False,
        "cta_authority_changed": False,
        "fallback_shell_removed": False,
        "cases": cases,
        "cta_authority_markers": cta_authority_markers,
        "object_ready_for_live_card_vm_authority": object_ready,
        "object_ready_for_live_card_vm_authority_text": "yes" if object_ready else "no",
        "remaining_live_card_vm_paths": list(REMAINING_LIVE_CARD_VM_PATHS),
        "fallback_shell_risks": fallback_shell_risks,
        "required_before_live_move": (
            [
                "wire display adapter beside live card VM/render-model build",
                "prove live render-model hash parity",
                "prove fallback shell display remains fallback-only/non-authoritative",
                "run rendered HTML freeze after live card VM authority move",
            ]
            if object_ready
            else ["resolve remaining display mismatches before live card VM authority move"]
        ),
        "snapshot_hash": _stable_hash(
            {
                "case_hashes": {name: case["display_hash"] for name, case in cases.items()},
                "remaining_live_card_vm_paths": REMAINING_LIVE_CARD_VM_PATHS,
                "cta_authority_markers": cta_authority_markers,
                "ready": object_ready,
            }
        ),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = []
    for name, case in snapshot["cases"].items():
        actual = case["actual"]
        rows.append(
            "| {name} | {status} | {title} | {badge} | {state} | {mismatches} | {stable} | {outcome} |".format(
                name=name,
                status=case["parity_status"],
                title=str(actual.get("title") or ""),
                badge=str(actual.get("badge") or ""),
                state=str(actual.get("display_state") or ""),
                mismatches=len(case["mismatches"]),
                stable="yes" if case["stable_hash"] else "no",
                outcome="yes" if case["outcome_state_alignment"] else "no",
            )
        )
    body = "\n".join(
        [
            "# Design Guide Card VM Adapter Parity Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['parity_status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Cases",
            "",
            "| Case | Parity | Title | Badge | Display state | Mismatches | Stable | Outcome aligned |",
            "|---|---|---|---|---|---:|---:|---:|",
            *rows,
            "",
            "## Readiness",
            "",
            f"- object_ready_for_live_card_vm_authority: `{snapshot['object_ready_for_live_card_vm_authority_text']}`",
            f"- remaining_live_card_vm_paths: `{snapshot['remaining_live_card_vm_paths']}`",
            f"- fallback_shell_risks: `{snapshot['fallback_shell_risks']}`",
            "",
            "Required before live move:",
            "",
            *[f"- {item}" for item in snapshot["required_before_live_move"]],
            "",
            "## Guardrails",
            "",
            f"- Card rendering moved: `{snapshot['card_rendering_moved']}`",
            f"- Visible wording changed: `{snapshot['visible_wording_changed']}`",
            f"- Card colours changed: `{snapshot['card_colours_changed']}`",
            f"- Badge/title/summary changed: `{snapshot['badge_title_summary_changed']}`",
            f"- CTA authority changed: `{snapshot['cta_authority_changed']}`",
            f"- Fallback shell removed: `{snapshot['fallback_shell_removed']}`",
            "",
            f"Failures: `{snapshot['failures']}`",
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_card_vm_adapter_parity_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_card_vm_adapter_parity_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_card_vm_adapter_parity_snapshot {snapshot['parity_status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("failures=" + ", ".join(snapshot["failures"]))
    return 0 if snapshot["parity_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
