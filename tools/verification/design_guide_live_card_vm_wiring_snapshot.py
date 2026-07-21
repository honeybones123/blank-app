"""Trace-only live card VM wiring snapshot.

This verifier compares current live card VM/render-model shaped surfaces with
FinalDesignGuidePublication.display. It does not move card VM authority, render
HTML, change visible wording, alter colours/layout, or change CTA authority.
"""

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

from tools.verification.design_guide_card_vm_adapter_parity_snapshot import (  # noqa: E402
    COMPARE_FIELDS,
    REMAINING_LIVE_CARD_VM_PATHS,
    _case_definitions,
    _stable_hash,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

LIVE_CARD_VM_SYMBOLS = [
    ("design_brain/final_publication.py", "def build_final_publication_display_from_current_card_model("),
    ("design_brain/final_publication.py", "class FinalDesignGuideDisplay"),
    ("design_brain/final_design_guide_formatter.py", "def build_final_design_guide_card_format("),
    ("design_brain/final_design_guide_formatter.py", "final_publication_display_hash=display_hash"),
    ("ui/final_design_guide_card.py", "def render_final_design_guide_card_html("),
]


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


def _forbidden_final_publication_imports(imports: list[str]) -> list[str]:
    return sorted(
        {
            name
            for name in imports
            for root in ("inputs_page", "streamlit")
            if name == root or name.startswith(root + ".")
        }
    )


def _text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _symbol_presence() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel_path, token in LIVE_CARD_VM_SYMBOLS:
        source = (ROOT / rel_path).read_text(encoding="utf-8")
        rows.append(
            {
                "owner_file": rel_path,
                "token": token,
                "present": token in source,
            }
        )
    return rows


def _live_card_vm_surface(case: dict[str, Any]) -> dict[str, Any]:
    vm = _mapping(case.get("view_model"))
    model = _mapping(case.get("render_model"))
    shell = _mapping(case.get("fallback_shell_model"))
    reasons = [
        dict(row)
        for row in list(
            model.get("final_reasons")
            or model.get("reason_display_rows")
            or vm.get("reasons")
            or []
        )
        if isinstance(row, dict)
    ]
    final_card_model_fields = {
        "title": _text(model.get("title"), vm.get("title"), vm.get("title_main")),
        "badge": _text(model.get("pill"), vm.get("pill"), vm.get("governing_label"), vm.get("status")),
        "summary": _text(model.get("main_text"), vm.get("summary_line"), vm.get("primary_action")),
        "status": _text(model.get("status"), vm.get("status")),
        "bucket": _text(vm.get("bucket")),
        "colour_state": _text(model.get("card_tone"), vm.get("tone"), vm.get("status"), vm.get("bucket")),
        "card_class": _text(model.get("card_class"), vm.get("card_class"), vm.get("final_card_class")),
        "display_state": _text(
            vm.get("display_state"),
            model.get("status"),
            vm.get("status"),
            vm.get("bucket"),
            "PROOF_PENDING",
        ),
        "blocker_explanation": _text(
            model.get("blocker_reason"),
            vm.get("blocker_explanation"),
            vm.get("blocking_reason"),
            _mapping(model.get("details_payload") or vm.get("details")).get("blocking_reason"),
        ),
    }
    expanded_evidence_sections = {
        "reasons": reasons,
        "reason_display_rows": [
            dict(row)
            for row in list(model.get("reason_display_rows") or [])
            if isinstance(row, dict)
        ],
        "current": [
            dict(row)
            for row in list(model.get("current_rows") or vm.get("current") or [])
            if isinstance(row, dict)
        ],
        "preview": _mapping(model.get("preview_rows") or vm.get("preview")),
        "preview_display_rows": [
            dict(row)
            for row in list(model.get("preview_display_rows") or [])
            if isinstance(row, dict)
        ],
        "details": _mapping(model.get("details_payload") or vm.get("details")),
        "blocker_evidence_display_fields": _mapping(model.get("blocker_evidence_display_fields")),
        "terminal_status": _mapping(model.get("terminal_status")),
    }
    return {
        "title": final_card_model_fields["title"],
        "badge": final_card_model_fields["badge"],
        "summary": final_card_model_fields["summary"],
        "status": final_card_model_fields["status"],
        "bucket": final_card_model_fields["bucket"],
        "colour_state": final_card_model_fields["colour_state"],
        "card_class": final_card_model_fields["card_class"],
        "display_state": final_card_model_fields["display_state"],
        "blocker_explanation": final_card_model_fields["blocker_explanation"],
        "expanded_evidence_sections": expanded_evidence_sections,
        "final_card_model_hash": _stable_hash(final_card_model_fields),
        "render_fallback_shell_hash": _stable_hash(shell),
    }


def _adapter_display_surface(case: dict[str, Any]) -> dict[str, Any]:
    from design_brain.final_publication import build_final_publication_display_from_current_card_model

    display = build_final_publication_display_from_current_card_model(
        view_model=case.get("view_model"),
        render_model=case.get("render_model"),
        fallback_shell_model=case.get("fallback_shell_model"),
    ).to_dict()
    return {field: display.get(field) for field in COMPARE_FIELDS}


def _publication_outcome_state(case: dict[str, Any]) -> str:
    from design_brain.final_publication import build_final_design_guide_publication

    name = str(case.get("name") or "case")
    action_family = (
        "SHEAR_FAIL_GOVERNS"
        if name == "fallback_shell_card"
        else "BENDING_FAIL_GOVERNS"
    )
    is_action = case.get("outcome_state") == "ACTION"
    publication = build_final_design_guide_publication(
        item={
            **_mapping(case.get("view_model")),
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
        verifier_payload={"case": case.get("name")},
    )
    return publication.outcome_state


def _build_snapshot() -> dict[str, Any]:
    final_imports = _module_imports(FINAL_PUBLICATION)
    forbidden_imports = _forbidden_final_publication_imports(final_imports)
    symbol_rows = _symbol_presence()
    missing_symbols = [row for row in symbol_rows if not row["present"]]
    inputs_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, APP_CONTRACT_BRIDGE)
        if path.exists()
    )
    direct_shell_helper_absent = "def _design_guide_direct_action_shell_card_html(" not in inputs_source
    cta_authority_markers = {
        "FinalDesignGuidePublication.cta": "FinalDesignGuidePublication.cta" in inputs_source,
        "_stamp_final_publication_cta_authority": "_stamp_final_publication_cta_authority(" in inputs_source,
        "final_publication_cta_hash": "final_publication_cta_hash" in inputs_source,
    }
    cases: dict[str, Any] = {}
    failures: list[str] = []
    fallback_shell_risks: list[str] = []
    for name, case in _case_definitions().items():
        case = {**case, "name": name}
        live = _live_card_vm_surface(case)
        adapter = _adapter_display_surface(case)
        mismatches = {
            field: {"live": live.get(field), "adapter": adapter.get(field)}
            for field in COMPARE_FIELDS
            if live.get(field) != adapter.get(field)
        }
        publication_outcome_state = _publication_outcome_state(case)
        outcome_alignment = publication_outcome_state == case["outcome_state"]
        if mismatches:
            failures.append(f"{name}:live_card_vm_wiring_mismatch")
        if not outcome_alignment:
            failures.append(f"{name}:outcome_alignment")
        if name == "fallback_shell_card":
            shell = _mapping(case.get("fallback_shell_model"))
            if not (shell.get("fallback_only") and shell.get("non_authoritative")):
                fallback_shell_risks.append("fallback shell card is not fallback-only/non-authoritative")
                failures.append("fallback_shell_authority_risk")
        cases[name] = {
            "parity_status": "PASS" if not mismatches and outcome_alignment else "FAIL",
            "live": live,
            "adapter": adapter,
            "mismatches": mismatches,
            "outcome_state": case["outcome_state"],
            "publication_outcome_state": publication_outcome_state,
            "outcome_state_alignment": outcome_alignment,
            "cta_authority_remains_publication_cta": all(cta_authority_markers.values()),
            "case_hash": _stable_hash(
                {
                    "live": live,
                    "adapter": adapter,
                    "outcome": publication_outcome_state,
                }
            ),
        }

    if forbidden_imports:
        failures.append("final_publication_forbidden_imports")
    if missing_symbols:
        failures.append("missing_live_card_vm_symbols")
    if not direct_shell_helper_absent:
        failures.append("legacy_direct_action_shell_helper_still_present")
    if not all(cta_authority_markers.values()):
        failures.append("cta_authority_marker_missing")

    status = "PASS" if not failures else "FAIL"
    return {
        "snapshot_name": "design_guide_live_card_vm_wiring",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "live_card_vm_wiring_parity": status,
        "status": status,
        "product_behavior_changed": False,
        "card_vm_authority_moved": False,
        "card_rendering_moved": False,
        "visible_wording_changed": False,
        "card_colours_changed": False,
        "badge_title_summary_changed": False,
        "layout_changed": False,
        "cta_authority_changed": False,
        "fallback_shell_removed": False,
        "final_publication_imports": final_imports,
        "forbidden_final_publication_imports": forbidden_imports,
        "live_symbol_presence": symbol_rows,
        "cases": cases,
        "remaining_mismatches": {
            name: case["mismatches"]
            for name, case in cases.items()
            if case["mismatches"]
        },
        "fallback_shell_risks": fallback_shell_risks,
        "direct_shell_helper_absent": direct_shell_helper_absent,
        "cta_authority_markers": cta_authority_markers,
        "object_ready_for_live_card_vm_authority": status == "PASS",
        "object_ready_for_live_card_vm_authority_text": "yes" if status == "PASS" else "no",
        "remaining_live_card_vm_paths": list(REMAINING_LIVE_CARD_VM_PATHS),
        "required_before_live_card_vm_move": (
            [
                "move live card VM authority into FinalDesignGuidePublication.display",
                "keep HTML rendering page-owned",
                "run render-model hash and rendered HTML freeze after cutover",
                "keep fallback shell guarded as fallback-only/non-authoritative",
            ]
            if status == "PASS"
            else ["resolve remaining_mismatches before moving card VM authority"]
        ),
        "snapshot_hash": _stable_hash(
            {
                "case_hashes": {name: case["case_hash"] for name, case in cases.items()},
                "symbols": symbol_rows,
                "cta_authority": cta_authority_markers,
                "ready": status == "PASS",
            }
        ),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = []
    for name, case in snapshot["cases"].items():
        live = case["live"]
        rows.append(
            "| {name} | {status} | {title} | {badge} | {state} | {mismatches} | {outcome} |".format(
                name=name,
                status=case["parity_status"],
                title=str(live.get("title") or ""),
                badge=str(live.get("badge") or ""),
                state=str(live.get("display_state") or ""),
                mismatches=len(case["mismatches"]),
                outcome="yes" if case["outcome_state_alignment"] else "no",
            )
        )
    body = "\n".join(
        [
            "# Design Guide Live Card VM Wiring Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['live_card_vm_wiring_parity']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "This is trace-only. It compares live card VM/render-model shaped data to `FinalDesignGuidePublication.display` and does not move card VM authority.",
            "",
            "## Cases",
            "",
            "| Case | Parity | Title | Badge | Display state | Mismatches | Outcome aligned |",
            "|---|---|---|---|---|---:|---:|",
            *rows,
            "",
            "## Readiness",
            "",
            f"- object_ready_for_live_card_vm_authority: `{snapshot['object_ready_for_live_card_vm_authority_text']}`",
            f"- remaining_mismatches: `{snapshot['remaining_mismatches']}`",
            f"- fallback_shell_risks: `{snapshot['fallback_shell_risks']}`",
            f"- remaining_live_card_vm_paths: `{snapshot['remaining_live_card_vm_paths']}`",
            "",
            "Required before live card VM move:",
            "",
            *[f"- {item}" for item in snapshot["required_before_live_card_vm_move"]],
            "",
            "## Guardrails",
            "",
            f"- Product behaviour changed: `{snapshot['product_behavior_changed']}`",
            f"- Card VM authority moved: `{snapshot['card_vm_authority_moved']}`",
            f"- Card rendering moved: `{snapshot['card_rendering_moved']}`",
            f"- Visible wording changed: `{snapshot['visible_wording_changed']}`",
            f"- Card colours changed: `{snapshot['card_colours_changed']}`",
            f"- Badge/title/summary changed: `{snapshot['badge_title_summary_changed']}`",
            f"- Layout changed: `{snapshot['layout_changed']}`",
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
    json_path = ARTIFACT_DIR / f"design_guide_live_card_vm_wiring_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_card_vm_wiring_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_live_card_vm_wiring_snapshot {snapshot['live_card_vm_wiring_parity']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("failures=" + ", ".join(snapshot["failures"]))
    return 0 if snapshot["live_card_vm_wiring_parity"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
