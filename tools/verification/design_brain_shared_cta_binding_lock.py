from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from dataclasses import fields
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS = ROOT / "inputs_page.py"
APP_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
DESIGN_GUIDE_MODULES = ROOT / "inputs_page_modules" / "design_guide"
APPLY_ROUTING = ROOT / "inputs_page_modules" / "apply_routing.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
PUBLICATION = ROOT / "design_brain" / "publication.py"
CTA_CONTRACTS = ROOT / "design_brain" / "cta_contracts.py"

FOCUSED_VERIFIERS = (
    "cta_button_contract_check.py",
    "design_guide_cta_authority_readiness_snapshot.py",
    "design_guide_cta_adapter_parity_snapshot.py",
    "design_guide_live_cta_wiring_snapshot.py",
    "design_guide_live_cta_authority_cutover.py",
    "design_guide_button_contract_shell_deadness_audit.py",
    "design_brain_shared_final_publication_cta_source_precedence_lock.py",
)

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

REQUIRED_SHELL_TOKENS = {
    "cta_authority_constant": '_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"',
    "cta_authority_builder": "def _final_publication_cta_authority_payload(",
    "cta_authority_stamper": "def _stamp_final_publication_cta_authority(",
    "cta_from_current_state_delegate": "_build_final_publication_cta_from_current_state(",
    "contract_authority_marker": 'contract["final_publication_cta_authority"] = _FINAL_PUBLICATION_CTA_AUTHORITY',
    "apply_queue_page_owned": "def _queue_primary_design_guide_button_action(",
    "apply_handler_page_owned": "def handle_inputs_apply_buttons(",
    "render_panel_page_owned": "design_guide_page.render_final_panel(",
    "fallback_cta_non_authoritative": '"legacy_non_authoritative": True',
}

FORBIDDEN_SHARED_IMPORT_ROOTS = {"inputs_page", "streamlit", "design_guide_page", "app"}
FORBIDDEN_SHARED_RUNTIME_TOKENS = {
    "st.session_state",
    "st.button",
    "handle_apply_buttons(",
    "render_final_panel(",
    "_queue_primary_design_guide_button_action(",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _module_import_roots(source: str) -> set[str]:
    tree = ast.parse(source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(str(alias.name).split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(str(node.module).split(".", 1)[0])
    return roots


def _run(script_name: str, timeout: int = 300) -> dict[str, Any]:
    command = [sys.executable, f"tools/verification/{script_name}"]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        "script": script_name,
        "command": " ".join(command),
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def _build_cta_publication_case() -> dict[str, Any]:
    from design_brain.final_publication import build_final_design_guide_publication

    item = {
        "published_item_id": "shared-cta-binding-lock-action",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "published_family_id": "SHEAR_FAIL_GOVERNS",
        "status": "FAIL",
        "bucket": "fail",
        "title_main": "Shear capacity is low",
        "primary_action": "Run one-click auto design",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "label": "Repair preview",
            "action_type": "apply_resolved_candidate",
            "family": "SHEAR_FAIL_GOVERNS",
            "updates": {"N_lig": 2, "s_lig": 250.0},
            "preview_pass": True,
            "candidate_id": "shared-cta-binding-lock-action",
            "source_candidate_id": "shared-cta-binding-lock-action",
        },
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "updates": {"N_lig": 2, "s_lig": 250.0},
            "candidate_id": "shared-cta-binding-lock-action",
            "family": "SHEAR_FAIL_GOVERNS",
        },
    }
    publication = build_final_design_guide_publication(
        item=item,
        debug={"selected_family_id": "SHEAR_FAIL_GOVERNS"},
        design_brain_result={"selected_family_id": "SHEAR_FAIL_GOVERNS"},
        publication_reason="shared_cta_binding_lock_action_case",
    )
    data = publication.to_dict()
    cta = dict(data.get("cta") or {})
    return {
        "selected_family": data.get("selected_family"),
        "publication_hash_present": bool(data.get("publication_hash")),
        "cta_enabled": cta.get("enabled") is True,
        "cta_actionable": cta.get("actionable") is True,
        "cta_family": cta.get("family"),
        "cta_action_type": cta.get("action_type"),
        "cta_payload_updates": dict((cta.get("apply_payload_summary") or {}).get("updates") or {}),
        "cta_payload_fingerprint_present": bool(cta.get("apply_payload_fingerprint")),
        "cta_button_contract_hash_present": bool(cta.get("button_contract_hash")),
        "passed": bool(
            data.get("selected_family") == "SHEAR_FAIL_GOVERNS"
            and data.get("publication_hash")
            and cta.get("enabled") is True
            and cta.get("actionable") is True
            and cta.get("family") == "SHEAR_FAIL_GOVERNS"
            and cta.get("action_type") == "apply_resolved_candidate"
            and (cta.get("apply_payload_summary") or {}).get("updates") == {"N_lig": 2, "s_lig": 250.0}
            and cta.get("apply_payload_fingerprint")
            and cta.get("button_contract_hash")
        ),
    }


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Design Brain Shared CTA Binding Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This lock covers CTA binding truth: `FinalDesignGuidePublication.cta`, CTA source precedence, button-contract source/payload proof, live CTA wiring, and render/apply ownership boundaries.",
        "",
        "## Ownership",
        "",
        "- CTA truth: `FinalDesignGuidePublication.cta`",
        "- CTA source precedence: `design_brain.cta_contracts`",
        "- pure CTA publication helpers: `design_brain.final_publication` / `design_brain.publication`",
        "- render: page/UI render-only",
        "- apply routing and click handling: `inputs_page.py`",
        "",
        "## Checks",
        "",
    ]
    for key, value in snapshot["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Focused Verifiers", ""])
    for key, result in snapshot["focused_verifiers"].items():
        lines.append(f"- `{key}`: `{result['passed']}`")
    lines.extend(["", "## CTA Publication Case", ""])
    for key, value in snapshot["cta_publication_case"].items():
        lines.append(f"- `{key}`: `{value}`")
    if snapshot["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in snapshot["failures"])
    lines.extend(["", "## Next", "", "Proceed to the shared `Apply payload` component if this lock is PASS."])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = "\n".join(
        [
            _read(INPUTS),
            _read(APP_BRIDGE),
            _read(ROUTE_COORDINATORS),
            _read(APPLY_ROUTING),
            _read(FINAL_PUBLICATION),
            *(_read(path) for path in sorted(DESIGN_GUIDE_MODULES.rglob("*.py"))),
        ]
    )
    final_source = _read(FINAL_PUBLICATION)
    publication_source = _read(PUBLICATION)
    cta_source = _read(CTA_CONTRACTS)

    from design_brain.final_publication import FinalDesignGuideCTA

    cta_fields = {field.name for field in fields(FinalDesignGuideCTA)}
    shared_import_roots = {
        "design_brain/final_publication.py": _module_import_roots(final_source),
        "design_brain/publication.py": _module_import_roots(publication_source),
        "design_brain/cta_contracts.py": _module_import_roots(cta_source),
    }
    forbidden_imports = {
        path: sorted(roots & FORBIDDEN_SHARED_IMPORT_ROOTS)
        for path, roots in shared_import_roots.items()
        if roots & FORBIDDEN_SHARED_IMPORT_ROOTS
    }
    forbidden_runtime_tokens = {
        "design_brain/final_publication.py": sorted(
            token for token in FORBIDDEN_SHARED_RUNTIME_TOKENS if token in final_source
        ),
        "design_brain/publication.py": sorted(
            token for token in FORBIDDEN_SHARED_RUNTIME_TOKENS if token in publication_source
        ),
        "design_brain/cta_contracts.py": sorted(
            token for token in FORBIDDEN_SHARED_RUNTIME_TOKENS if token in cta_source
        ),
    }
    forbidden_runtime_tokens = {path: tokens for path, tokens in forbidden_runtime_tokens.items() if tokens}

    shell_token_checks = {
        key: token in shell_source for key, token in REQUIRED_SHELL_TOKENS.items()
    }
    focused = {script: _run(script) for script in FOCUSED_VERIFIERS}
    cta_case = _build_cta_publication_case()

    checks = {
        "focused_verifiers_pass": all(result["passed"] for result in focused.values()),
        "final_publication_cta_required_fields_present": REQUIRED_CTA_FIELDS <= cta_fields,
        "shared_cta_modules_have_no_page_streamlit_imports": not forbidden_imports,
        "shared_cta_modules_have_no_render_or_apply_runtime_tokens": not forbidden_runtime_tokens,
        "inputs_page_declares_final_publication_cta_authority": shell_token_checks["cta_authority_constant"],
        "inputs_page_delegates_cta_construction_to_final_publication": shell_token_checks[
            "cta_from_current_state_delegate"
        ],
        "inputs_page_stamps_cta_authority_but_keeps_apply_routing": bool(
            shell_token_checks["cta_authority_stamper"]
            and shell_token_checks["contract_authority_marker"]
            and shell_token_checks["apply_queue_page_owned"]
            and shell_token_checks["apply_handler_page_owned"]
        ),
        "render_remains_page_owned": shell_token_checks["render_panel_page_owned"],
        "fallback_cta_shell_non_authoritative": shell_token_checks["fallback_cta_non_authoritative"],
        "publication_case_has_executable_final_cta": cta_case["passed"],
    }
    failures: list[str] = []
    for key, value in checks.items():
        if not value:
            failures.append("check_failed:" + key)
    for key, present in shell_token_checks.items():
        if not present:
            failures.append("missing_inputs_token:" + key)
    for script, result in focused.items():
        if not result["passed"]:
            failures.append("focused_verifier_failed:" + script)
    if forbidden_imports:
        failures.append("forbidden_imports:" + json.dumps(forbidden_imports, sort_keys=True))
    if forbidden_runtime_tokens:
        failures.append(
            "forbidden_runtime_tokens:" + json.dumps(forbidden_runtime_tokens, sort_keys=True)
        )

    status = "LOCKED" if not failures else "DEFERRED_WITH_BLOCKER"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_shared_cta_binding_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_cta_binding_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_cta_binding_lock.v1",
        "status": status,
        "lock_status": status,
        "component": "CTA binding",
        "owner": "design_brain.publication + FinalDesignGuidePublication.cta",
        "consumers": ["Apply payload", "render-only CTA"],
        "focused_verifiers": focused,
        "shell_token_checks": shell_token_checks,
        "cta_publication_case": cta_case,
        "forbidden_imports": forbidden_imports,
        "forbidden_runtime_tokens": forbidden_runtime_tokens,
        "checks": checks,
        "failures": failures,
        "artifact": str(json_path),
        "report": str(report_path),
    }
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_shared_cta_binding_lock {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
