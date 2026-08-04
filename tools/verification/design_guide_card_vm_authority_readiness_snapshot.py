"""Readiness snapshot for Design Guide card view-model authority.

This verifier maps the current page-owned card VM/render-model authority into
FinalDesignGuidePublication.display. It does not move rendering, change visible
wording, change colours, change layout, or alter CTA authority.
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
FINAL_FORMATTER = ROOT / "design_brain" / "final_design_guide_formatter.py"
OUTPUT_FORMATTING = ROOT / "design_brain" / "output_formatting.py"
CURRENT_DISPLAY_FILES = (
    ROOT / "inputs_application" / "page_runtime" / "design_guide.py",
    ROOT / "inputs_page_modules" / "design_guide" / "panel_orchestration.py",
    ROOT / "inputs_page_modules" / "design_guide" / "render_coordinators.py",
    ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py",
    ROOT / "ui" / "final_design_guide_card.py",
)

REQUIRED_DISPLAY_FIELDS = {
    "title",
    "badge",
    "summary",
    "status",
    "bucket",
    "colour_state",
    "card_class",
    "display_state",
    "expanded_evidence_sections",
    "blocker_explanation",
    "final_card_model_fields",
    "final_card_model_hash",
    "render_fallback_shell_model",
    "render_fallback_shell_hash",
    "visible_wording_hash",
    "renderer_driving",
}

CARD_VM_PATHS = [
    {
        "owner_file": "design_brain/final_publication.py",
        "function_or_symbol": "build_final_publication_display_from_current_card_model",
        "tokens": [
            "def build_final_publication_display_from_current_card_model(",
            "return FinalDesignGuideDisplay(",
            "renderer_driving=False",
        ],
        "authority_role": "adapts current display-shaped data into FinalDesignGuidePublication.display proof without page imports",
        "matching_display_fields": [
            "title",
            "badge",
            "summary",
            "status",
            "colour_state",
            "expanded_evidence_sections",
            "blocker_explanation",
            "display_state",
        ],
        "can_be_moved_now": "yes",
        "reason_if_no": "",
        "required_parity_proof": "card VM adapter parity snapshot",
    },
    {
        "owner_file": "design_brain/final_design_guide_formatter.py",
        "function_or_symbol": "build_final_design_guide_card_format",
        "tokens": [
            "def build_final_design_guide_card_format(",
            "display_hash = stable_final_publication_hash(display.to_dict())",
            "final_publication_display_hash=display_hash",
        ],
        "authority_role": "builds renderer-only card format from FinalDesignGuidePublication.display",
        "matching_display_fields": [
            "final_card_model_fields",
            "final_card_model_hash",
            "expanded_evidence_sections",
            "blocker_explanation",
            "card_class",
        ],
        "can_be_moved_now": "yes",
        "reason_if_no": "",
        "required_parity_proof": "card render-model adapter parity snapshot",
    },
    {
        "owner_file": "design_brain/output_formatting.py",
        "function_or_symbol": "build_design_guide_card_render_model_fields",
        "tokens": [
            "def build_design_guide_card_render_model_fields(",
            "return DesignGuideCardRenderModel(",
            "card_class=decision_display.final_card_class",
        ],
        "authority_role": "pure render-model field packer already Design Brain-owned",
        "matching_display_fields": ["final_card_model_fields", "final_card_model_hash"],
        "can_be_moved_now": "yes",
        "reason_if_no": "",
        "required_parity_proof": "existing output-formatting snapshot plus future adapter parity",
    },
    {
        "owner_file": "ui/final_design_guide_card.py",
        "function_or_symbol": "render_final_design_guide_card_html_clean_path",
        "tokens": [
            "def render_final_design_guide_card_html(",
            "FinalDesignGuideCardFormat",
        ],
        "authority_role": "renders clean FinalDesignGuidePublication formatter HTML without display ownership",
        "matching_display_fields": ["final_card_model_hash"],
        "can_be_moved_now": "yes",
        "reason_if_no": "",
        "required_parity_proof": "render-freeze snapshot after card VM authority move",
    },
    {
        "owner_file": "ui/final_design_guide_card.py",
        "function_or_symbol": "render_final_design_guide_card_html",
        "tokens": [
            "def render_final_design_guide_card_html(",
            "FinalDesignGuideCardFormat",
            "fdg-card",
        ],
        "authority_role": "clean formatter renderer-only HTML emission",
        "matching_display_fields": [],
        "can_be_moved_now": "yes",
        "reason_if_no": "",
        "required_parity_proof": "clean formatter live cutover snapshot",
    },
]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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
    forbidden = {"inputs_page", "streamlit"}
    return sorted(
        {
            name
            for name in imports
            for root in forbidden
            if name == root or name.startswith(root + ".")
        }
    )


def _path_rows() -> list[dict[str, Any]]:
    source_by_file = {
        "inputs_page.py": "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in (INPUTS_PAGE, ROUTE_COORDINATORS, *CURRENT_DISPLAY_FILES)
            if path.exists()
        ),
        "design_brain/final_publication.py": FINAL_PUBLICATION.read_text(encoding="utf-8"),
        "design_brain/final_design_guide_formatter.py": FINAL_FORMATTER.read_text(encoding="utf-8"),
        "design_brain/output_formatting.py": OUTPUT_FORMATTING.read_text(encoding="utf-8"),
        "ui/final_design_guide_card.py": (ROOT / "ui" / "final_design_guide_card.py").read_text(
            encoding="utf-8"
        ),
    }
    rows: list[dict[str, Any]] = []
    for path in CARD_VM_PATHS:
        source = source_by_file[path["owner_file"]]
        missing_tokens = [token for token in path["tokens"] if token not in source]
        rows.append(
            {
                "owner_file": path["owner_file"],
                "function_or_symbol": path["function_or_symbol"],
                "current_authority_role": path["authority_role"],
                "matching_final_publication_display_fields": list(path["matching_display_fields"]),
                "can_be_moved_now": path["can_be_moved_now"],
                "reason_if_no": path["reason_if_no"],
                "required_parity_proof": path["required_parity_proof"],
                "tokens_present": not bool(missing_tokens),
                "missing_tokens": missing_tokens,
            }
        )
    return rows


def _display_case_payloads() -> dict[str, dict[str, Any]]:
    return {
        "pass": {
            "status": "pass",
            "bucket": "pass",
            "tone": "pass",
            "title_main": "Design accepted",
            "pill": "PASS",
            "summary_line": "All checks pass.",
            "card_class": "fast-guidance-item pass guidance-success",
        },
        "action": {
            "status": "action",
            "bucket": "warn",
            "tone": "action",
            "title_main": "Bending capacity is low",
            "pill": "ACTION",
            "summary_line": "Run one-click auto design.",
            "card_class": "fast-guidance-item warn dg-card--action",
            "reasons": [{"label": "Bending", "text": "Bending utilisation is above 1.00.", "tone": "amber"}],
            "details": {"candidate_search_evidence": {"candidate_count": 4}},
        },
        "blocked": {
            "status": "blocked",
            "bucket": "fail",
            "tone": "blocked",
            "title_main": "Shear repair blocked",
            "pill": "BLOCKED",
            "summary_line": "Open for engineering detail.",
            "card_class": "fast-guidance-item fail dg-card--blocked",
            "blocking_reason": "no_valid_shear_repair",
            "button_contract": {"enabled": False, "blocking_reason": "no_valid_shear_repair"},
            "exact_blockers_by_family": {"shear": {"reason": "spacing/detailing limit"}},
        },
        "error": {
            "status": "error",
            "bucket": "error",
            "tone": "error",
            "title_main": "Design Guide family contract violation",
            "pill": "ERROR",
            "summary_line": "Publication blocked.",
            "card_class": "fast-guidance-item error",
            "blocker_explanation": "family_selection_contract_mismatch",
        },
        "proof_pending": {
            "status": "info",
            "bucket": "info",
            "tone": "info",
            "title_main": "Design guidance",
            "pill": "INFO",
            "summary_line": "Proof pending.",
            "display_state": "PROOF_PENDING",
            "card_class": "fast-guidance-item info",
            "render_fallback_shell": True,
        },
    }


def _build_snapshot() -> dict[str, Any]:
    from design_brain.final_publication import (
        FinalDesignGuideDisplay,
        build_final_design_guide_display,
    )

    final_imports = _module_imports(FINAL_PUBLICATION)
    forbidden_imports = _forbidden_final_publication_imports(final_imports)
    display_fields = {field.name for field in fields(FinalDesignGuideDisplay)}
    missing_display_fields = sorted(REQUIRED_DISPLAY_FIELDS - display_fields)
    path_rows = _path_rows()

    display_cases: dict[str, Any] = {}
    for name, payload in _display_case_payloads().items():
        first = build_final_design_guide_display(item=payload).to_dict()
        second = build_final_design_guide_display(item=payload).to_dict()
        required_values_present = {
            field: field in first for field in REQUIRED_DISPLAY_FIELDS
        }
        display_cases[name] = {
            "display": first,
            "display_hash": _stable_hash(first),
            "stable_hash": _stable_hash(first) == _stable_hash(second),
            "required_values_present": required_values_present,
            "missing_required_values": [
                field for field, present in required_values_present.items() if not present
            ],
        }

    final_publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    inputs_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, *CURRENT_DISPLAY_FILES)
        if path.exists()
    )
    cta_authority_markers = {
        "final_publication_cta_authority_constant": "FinalDesignGuidePublication.cta" in inputs_source or "FinalDesignGuidePublication.cta" in final_publication_source,
        "final_publication_cta_stamper": "_final_publication_cta_authority_payload(" in inputs_source,
        "display_not_cta_authority": "FinalDesignGuideCTA" in final_publication_source,
    }

    failures: list[str] = []
    if missing_display_fields:
        failures.append("missing_final_publication_display_fields")
    if forbidden_imports:
        failures.append("final_publication_forbidden_imports")
    for row in path_rows:
        if not row["tokens_present"]:
            failures.append(f"missing_path_tokens:{row['function_or_symbol']}")
    for name, case in display_cases.items():
        if not case["stable_hash"]:
            failures.append(f"unstable_display_hash:{name}")
        if case["missing_required_values"]:
            failures.append(f"missing_display_case_values:{name}")
    if not all(cta_authority_markers.values()):
        failures.append("cta_authority_not_proven")

    status = "PASS" if not failures else "FAIL"
    return {
        "snapshot_name": "design_guide_card_vm_authority_readiness",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "final_publication_display_fields": sorted(display_fields),
        "required_display_fields": sorted(REQUIRED_DISPLAY_FIELDS),
        "missing_display_fields": missing_display_fields,
        "final_publication_imports": final_imports,
        "forbidden_final_publication_imports": forbidden_imports,
        "card_vm_authority_paths": path_rows,
        "display_cases": display_cases,
        "cta_authority_remains_final_publication_cta": all(cta_authority_markers.values()),
        "cta_authority_markers": cta_authority_markers,
        "rendering_remains_page_owned": True,
        "card_rendering_moved": False,
        "visible_wording_changed": False,
        "card_colours_changed": False,
        "badge_title_summary_changed": False,
        "layout_moved": False,
        "cta_authority_changed": False,
        "object_ready_for_card_vm_adapter": status == "PASS",
        "object_ready_for_card_vm_authority": False,
        "recommended_next_step": (
            "proof-only card VM adapter parity"
            if status == "PASS"
            else "resolve missing display/path fields before adapter parity"
        ),
        "required_before_live_card_vm_move": [
            "proof-only card VM adapter parity snapshot",
            "render-model hash parity snapshot",
            "fallback shell display parity snapshot",
            "rendered HTML freeze after card VM authority moves",
        ],
        "snapshot_hash": _stable_hash(
            {
                "display_fields": sorted(display_fields),
                "path_rows": path_rows,
                "case_hashes": {
                    name: case["display_hash"] for name, case in display_cases.items()
                },
                "cta_markers": cta_authority_markers,
            }
        ),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    path_rows = [
        "| {owner} | {symbol} | {role} | {fields} | {move} | {reason} | {proof} |".format(
            owner=row["owner_file"],
            symbol=row["function_or_symbol"],
            role=row["current_authority_role"],
            fields=", ".join(row["matching_final_publication_display_fields"]) or "-",
            move=row["can_be_moved_now"],
            reason=row["reason_if_no"] or "-",
            proof=row["required_parity_proof"],
        )
        for row in snapshot["card_vm_authority_paths"]
    ]
    case_rows = [
        "| {name} | {stable} | {title} | {state} | {card_hash} |".format(
            name=name,
            stable="yes" if case["stable_hash"] else "no",
            title=str(case["display"].get("title") or ""),
            state=str(case["display"].get("display_state") or ""),
            card_hash=str(case["display"].get("final_card_model_hash") or ""),
        )
        for name, case in snapshot["display_cases"].items()
    ]
    body = "\n".join(
        [
            "# Design Guide Card VM Authority Readiness Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Readiness",
            "",
            f"- FinalDesignGuidePublication.display fields complete: `{not bool(snapshot['missing_display_fields'])}`",
            f"- CTA authority remains FinalDesignGuidePublication.cta: `{snapshot['cta_authority_remains_final_publication_cta']}`",
            f"- Rendering remains page-owned: `{snapshot['rendering_remains_page_owned']}`",
            f"- Object ready for card VM adapter: `{snapshot['object_ready_for_card_vm_adapter']}`",
            f"- Object ready for live card VM authority: `{snapshot['object_ready_for_card_vm_authority']}`",
            f"- Recommended next step: `{snapshot['recommended_next_step']}`",
            "",
            "## Authority Paths",
            "",
            "| Owner | Function/symbol | Role | Display fields | Can move now | Reason if no | Required parity proof |",
            "|---|---|---|---|---|---|---|",
            *path_rows,
            "",
            "## Display Cases",
            "",
            "| Case | Stable | Title | Display state | Card model hash |",
            "|---|---:|---|---|---|",
            *case_rows,
            "",
            "## Guardrails",
            "",
            f"- Card rendering moved: `{snapshot['card_rendering_moved']}`",
            f"- Visible wording changed: `{snapshot['visible_wording_changed']}`",
            f"- Card colours changed: `{snapshot['card_colours_changed']}`",
            f"- Badge/title/summary changed: `{snapshot['badge_title_summary_changed']}`",
            f"- Layout moved: `{snapshot['layout_moved']}`",
            f"- CTA authority changed: `{snapshot['cta_authority_changed']}`",
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
    json_path = ARTIFACT_DIR / f"design_guide_card_vm_authority_readiness_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_card_vm_authority_readiness_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_card_vm_authority_readiness_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("failures=" + ", ".join(snapshot["failures"]))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
