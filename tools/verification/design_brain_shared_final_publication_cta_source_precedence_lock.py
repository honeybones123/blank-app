from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTRACT_PATH = ROOT / "design_brain" / "contracts" / "final_publication_cta_source_precedence_contract.json"
FINAL_PUBLICATION_PATH = ROOT / "design_brain" / "final_publication.py"
CTA_CONTRACTS_PATH = ROOT / "design_brain" / "cta_contracts.py"
INPUTS_PAGE_PATH = ROOT / "inputs_page.py"
CURRENT_COORDINATORS_PATH = ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py"
CURRENT_RUNTIME_SUPPORT_PATH = ROOT / "inputs_application" / "page_runtime" / "design_guide_runtime_support.py"
CURRENT_PRIMARY_QUEUE_PATH = ROOT / "inputs_page_modules" / "design_guide" / "primary_button_queue.py"
CURRENT_RUNTIME_COMMON_PATH = ROOT / "inputs_application" / "page_runtime" / "common.py"

FORBIDDEN_IMPORT_ROOTS = {
    "inputs_page",
    "streamlit",
    "design_brain.families",
    "design_brain.families.registry",
}

FORBIDDEN_DECISION_TERMS = {
    "family_strategy_for(",
    "contracted_repair_ladder_specs",
    "repair_ladder",
    "optimisation_ladder",
    "run_selected_family_ladder",
    "render_button(",
    "st.session_state",
}

REQUIRED_PUBLICATION_FIELDS = {
    "published_item_id",
    "selected_family",
    "outcome_state",
    "publication_reason",
    "blocker_reason",
    "cta",
    "display",
    "evidence",
    "verifier_payload",
    "source_hash",
    "publication_hash",
}

REQUIRED_CTA_FIELDS = {
    "enabled",
    "actionable",
    "label",
    "disabled_reason",
    "action_type",
    "family",
    "apply_payload_summary",
    "apply_payload_fingerprint",
    "button_contract_hash",
    "source_precedence_proof",
}

REQUIRED_SOURCE_PRECEDENCE_FIELDS = {
    "winning_button_contract",
    "winning_button_contract_source",
    "winning_update_payload",
    "winning_update_payload_source",
    "winning_action_type",
    "winning_action_type_source",
    "winning_candidate",
    "winning_candidate_source",
    "apply_enabled",
    "apply_actionable",
    "disabled_reason",
    "final_cta_action_payload_summary",
    "final_published_item_hash",
    "source_candidates",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _module_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(set(imports))


def _forbidden_imports(imports: list[str]) -> list[str]:
    hits: list[str] = []
    for name in imports:
        for forbidden in FORBIDDEN_IMPORT_ROOTS:
            if name == forbidden or name.startswith(forbidden + "."):
                hits.append(name)
    return sorted(set(hits))


def _forbidden_terms(source: str) -> list[str]:
    return sorted(term for term in FORBIDDEN_DECISION_TERMS if term in source)


def _run(command: list[str], timeout: int = 180) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        "command": " ".join(command),
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _action_publication_case() -> dict[str, Any]:
    from design_brain.final_publication import build_final_design_guide_publication

    item = {
        "published_item_id": "bending-action-1",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "published_family_id": "BENDING_FAIL_GOVERNS",
        "cta_family_id": "BENDING_FAIL_GOVERNS",
        "status": "FAIL",
        "bucket": "fail",
        "title_main": "Bending capacity is low",
        "primary_action": "Run one-click auto design",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "label": "Repair preview",
            "action_type": "apply_resolved_candidate",
            "family": "BENDING_FAIL_GOVERNS",
            "updates": {"bot_dia": 20},
            "preview_pass": True,
            "candidate_id": "bending-action-1",
            "source_candidate_id": "bending-action-1",
        },
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "updates": {"bot_dia": 20},
            "candidate_id": "bending-action-1",
            "family": "BENDING_FAIL_GOVERNS",
        },
    }
    publication = build_final_design_guide_publication(
        item=item,
        debug={"selected_family_id": "BENDING_FAIL_GOVERNS"},
        design_brain_result={"selected_family_id": "BENDING_FAIL_GOVERNS"},
        publication_reason="shared_lock_action_case",
    )
    data = publication.to_dict()
    cta = dict(data.get("cta") or {})
    return {
        "selected_family": data.get("selected_family"),
        "publication_hash_present": bool(data.get("publication_hash")),
        "source_hash_present": bool(data.get("source_hash")),
        "cta_enabled": bool(cta.get("enabled")),
        "cta_actionable": bool(cta.get("actionable")),
        "cta_family": cta.get("family"),
        "cta_action_type": cta.get("action_type"),
        "cta_payload_fingerprint_present": bool(cta.get("apply_payload_fingerprint")),
        "cta_button_contract_hash_present": bool(cta.get("button_contract_hash")),
        "pass": bool(
            data.get("selected_family") == "BENDING_FAIL_GOVERNS"
            and data.get("publication_hash")
            and data.get("source_hash")
            and cta.get("enabled") is True
            and cta.get("actionable") is True
            and cta.get("family") == "BENDING_FAIL_GOVERNS"
            and cta.get("action_type") == "apply_resolved_candidate"
            and cta.get("apply_payload_fingerprint")
            and cta.get("button_contract_hash")
        ),
    }


def _missing_family_case() -> dict[str, Any]:
    from design_brain.final_publication import build_final_design_guide_publication

    item = {
        "status": "FAIL",
        "bucket": "fail",
        "title_main": "Repair required",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "updates": {"D": 700},
        },
        "action_payload": {"action_type": "apply_resolved_candidate", "updates": {"D": 700}},
    }
    publication = build_final_design_guide_publication(
        item=item,
        debug={},
        design_brain_result={},
        publication_reason="shared_lock_missing_family_case",
    )
    data = publication.to_dict()
    cta = dict(data.get("cta") or {})
    invalid_action_without_family = bool(cta.get("enabled") and not data.get("selected_family"))
    return {
        "selected_family": data.get("selected_family"),
        "cta_enabled": bool(cta.get("enabled")),
        "invalid_action_without_family": invalid_action_without_family,
        "pass": not invalid_action_without_family,
    }


def _source_precedence_case() -> dict[str, Any]:
    from design_brain.cta_contracts import select_design_guide_button_contract_source_precedence

    final_contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "SHEAR_FAIL_GOVERNS",
        "updates": {"N_lig": 2, "s_lig": 250.0},
        "candidate_id": "shear-action-1",
        "source_candidate_id": "shear-action-1",
        "expected_util": 0.92,
    }
    records = SimpleNamespace(
        displayed_primary_item={
            "identity_hash": "final-item-hash",
            "button_contract": dict(final_contract),
            "action_payload": {
                "action_type": "apply_resolved_candidate",
                "updates": {"N_lig": 2, "s_lig": 250.0},
                "candidate_id": "shear-action-1",
                "family": "SHEAR_FAIL_GOVERNS",
            },
        },
        primary_item={},
        debug_displayed_primary_button_contract={},
        debug_primary_button_contract={},
        debug_button_contract={},
        source_candidates={
            "evidence_rehydration_source": {
                "present": True,
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family": "SHEAR_FAIL_GOVERNS",
                "updates": {"N_lig": 2, "s_lig": 250.0},
                "candidate_id": "shear-action-1",
                "source_candidate_id": "shear-action-1",
                "expected_util": 0.92,
            }
        },
    )
    result = select_design_guide_button_contract_source_precedence(
        source_records=records,
        button_contract_source_precedence_order=("primary.button_contract",),
        payload_source_precedence_order={},
        candidate_source_keys=("evidence_rehydration_source",),
        source_payload_labels={
            "evidence_rehydration_source": {
                "update_payload": "candidate_search_evidence.best_safe_candidate_updates",
                "action_type": "rebuilt_late_evidence_contract",
                "candidate": "candidate_search_evidence.selected_candidate_id",
            }
        },
    )
    return {
        "winning_button_contract_source": result.get("winning_button_contract_source"),
        "winning_update_payload_source": result.get("winning_update_payload_source"),
        "winning_action_type": result.get("winning_action_type"),
        "winning_candidate": result.get("winning_candidate"),
        "required_fields_present": REQUIRED_SOURCE_PRECEDENCE_FIELDS <= set(result),
        "pass": bool(
            result.get("winning_button_contract_source") == "evidence_rehydration_source"
            and result.get("winning_update_payload_source")
            == "candidate_search_evidence.best_safe_candidate_updates"
            and result.get("winning_action_type") == "apply_resolved_candidate"
            and REQUIRED_SOURCE_PRECEDENCE_FIELDS <= set(result)
        ),
    }


def _capture() -> dict[str, Any]:
    contract = _load_contract()
    final_source = _read(FINAL_PUBLICATION_PATH)
    cta_source = _read(CTA_CONTRACTS_PATH)
    inputs_source = "\n".join(
        _read(path)
        for path in (
            INPUTS_PAGE_PATH,
            CURRENT_COORDINATORS_PATH,
            CURRENT_RUNTIME_SUPPORT_PATH,
            CURRENT_PRIMARY_QUEUE_PATH,
            CURRENT_RUNTIME_COMMON_PATH,
        )
        if path.exists()
    )

    from design_brain.final_publication import FinalDesignGuideCTA, FinalDesignGuidePublication

    publication_fields = {field.name for field in fields(FinalDesignGuidePublication)}
    cta_fields = {field.name for field in fields(FinalDesignGuideCTA)}
    final_imports = _module_imports(final_source)
    cta_imports = _module_imports(cta_source)
    files_functions_audited = {
        "design_brain/final_publication.py": [
            "FinalDesignGuidePublication",
            "FinalDesignGuideCTA",
            "build_final_design_guide_publication",
            "build_final_publication_cta_from_current_state",
            "stable_final_publication_hash",
        ],
        "design_brain/cta_contracts.py": [
            "select_design_guide_button_contract_source_precedence",
            "build_design_guide_button_contract_source_resolution",
            "DesignGuideButtonContractSourceResolution",
        ],
        "composed Inputs surface": [
            "inputs_page.py",
            "inputs_page_modules/design_guide/current_coordinators.py",
            "inputs_page_modules/design_guide/primary_button_queue.py",
            "inputs_application/page_runtime/design_guide_runtime_support.py",
            "inputs_application/page_runtime/common.py",
            "_final_publication_cta_authority_payload",
            "_final_publication_debug_projection",
        ],
    }

    static_checks = {
        "contract_schema_present": contract.get("schema")
        == "design_brain.shared.final_publication_cta_source_precedence.v1",
        "contract_required_sections_present": all(
            key in contract
            for key in (
                "allowed_inputs",
                "required_outputs",
                "invalid_states",
                "ownership_boundary",
                "forbidden_behaviours",
                "required_evidence_fields",
                "regression_expectations",
            )
        ),
        "publication_required_fields_present": REQUIRED_PUBLICATION_FIELDS <= publication_fields,
        "cta_required_fields_present": REQUIRED_CTA_FIELDS <= cta_fields,
        "final_publication_has_no_forbidden_imports": not _forbidden_imports(final_imports),
        "cta_contracts_has_no_forbidden_imports": not _forbidden_imports(cta_imports),
        "final_publication_has_no_ladder_runtime_calls": not _forbidden_terms(final_source),
        "cta_contracts_has_no_ladder_runtime_calls": not _forbidden_terms(cta_source),
        "inputs_uses_final_publication_cta_authority": (
            '_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"' in inputs_source
            or "_final_publication_cta_authority_payload" in inputs_source
        ),
        "inputs_uses_final_publication_display_authority": (
            'authoritative_publication.get("display")' in inputs_source
            and "_final_publication_debug_projection" in inputs_source
        ),
        "inputs_imports_cta_source_precedence_core": "_final_publication_cta_authority_payload" in inputs_source,
    }

    regressions = {
        "normal_valid_action_publication": _action_publication_case(),
        "missing_family_invalid_action": _missing_family_case(),
        "source_precedence_explicit_winner": _source_precedence_case(),
    }

    composed = {
        "final_publication_object": _run(["python", "tools/verification/design_guide_final_publication_object_snapshot.py"]),
        "cta_adapter_parity": _run(["python", "tools/verification/design_guide_cta_adapter_parity_snapshot.py"]),
        "live_cta_authority_cutover": _run(["python", "tools/verification/design_guide_live_cta_authority_cutover.py"]),
        "cta_button_contract": _run(["python", "tools/verification/cta_button_contract_check.py"]),
        "locked_family_live_wiring": _run(["python", "tools/verification/families/locked_family_live_wiring_snapshot.py"]),
    }

    broader_publication_surface = {
        "file": "design_brain/publication.py",
        "lock_scope": "not included in this Priority 1 lock",
        "reason": "broader shared publication helpers still contain legacy recovery/adaptation surfaces and need their own shared-code contract lock",
    }

    checks = {
        **static_checks,
        "normal_valid_action_publication_pass": regressions["normal_valid_action_publication"].get("pass") is True,
        "missing_family_invalid_action_pass": regressions["missing_family_invalid_action"].get("pass") is True,
        "source_precedence_explicit_winner_pass": regressions["source_precedence_explicit_winner"].get("pass") is True,
        "composed_publication_cta_gates_pass": all(item.get("passed") for item in composed.values()),
    }
    locked = all(checks.values())
    return {
        "shared_area_name": "FinalDesignGuidePublication and CTA source precedence",
        "files_functions_audited": files_functions_audited,
        "contract_path": str(CONTRACT_PATH),
        "contract": contract,
        "static_checks": static_checks,
        "regressions": regressions,
        "composed_verifiers": composed,
        "broader_publication_surface_note": broader_publication_surface,
        "bugs_found": [],
        "fixes_made": [],
        "checks": checks,
        "lock_status": "LOCKED" if locked else "NOT_LOCKED",
    }


def _write_report(payload: dict[str, Any], json_path: Path, report_path: Path) -> None:
    lines = [
        "# Design Brain Shared Code Lock Report",
        "",
        f"## Shared Area Name",
        payload["shared_area_name"],
        "",
        "## Lock Status",
        f"`{payload['lock_status']}`",
        "",
        "## Files / Functions Audited",
    ]
    for file_name, functions in payload["files_functions_audited"].items():
        lines.append(f"- `{file_name}`: {', '.join(f'`{fn}`' for fn in functions)}")
    lines.extend(
        [
            "",
            "## Contract Added / Updated",
            f"- `{payload['contract_path']}`",
            "",
            "## Static Checks",
        ]
    )
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Regression Pack"])
    for key, value in payload["regressions"].items():
        lines.append(f"- `{key}`: `{value.get('pass')}`")
    lines.extend(["", "## Verifier Results"])
    for key, value in payload["composed_verifiers"].items():
        lines.append(f"- `{key}`: `{value.get('passed')}`")
    lines.extend(
        [
            "",
            "## Bugs Found",
            "- None in this lock scope.",
            "",
            "## Fixes Made",
            "- None. This slice adds a shared lock contract/verifier around the already-green authority surface.",
            "",
            "## Broader Publication Surface",
            f"- `{payload['broader_publication_surface_note']['file']}`: {payload['broader_publication_surface_note']['reason']}",
            "",
            "## Checks",
        ]
    )
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _capture()
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_shared_final_publication_cta_source_precedence_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_final_publication_cta_source_precedence_lock_{stamp}.md"
    _write_report(payload, json_path, report_path)
    print(f"design_brain_shared_final_publication_cta_source_precedence_lock {payload['lock_status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload["lock_status"] != "LOCKED":
        failed = [key for key, value in payload["checks"].items() if not value]
        print(f"failures={failed}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
