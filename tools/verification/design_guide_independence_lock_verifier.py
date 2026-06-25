"""Final Design Guide independence lock verifier.

This verifier composes the full publication-independence proof chain. It proves
FinalDesignGuidePublication is the final CTA/display authority while
inputs_page.py remains allowed to render, route apply actions, and store debug
payloads without reinterpreting final publication truth.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

COMPOSED_GATES: list[dict[str, str]] = [
    {
        "id": "final_publication_authority_snapshot",
        "script": "tools/verification/design_guide_final_publication_authority_snapshot.py",
        "label": "Final publication authority snapshot",
    },
    {
        "id": "final_publication_object_snapshot",
        "script": "tools/verification/design_guide_final_publication_object_snapshot.py",
        "label": "FinalDesignGuidePublication object snapshot",
    },
    {
        "id": "final_publication_boundary_snapshot",
        "script": "tools/verification/design_guide_final_publication_boundary_snapshot.py",
        "label": "Final publication boundary snapshot",
    },
    {
        "id": "cta_authority_readiness",
        "script": "tools/verification/design_guide_cta_authority_readiness_snapshot.py",
        "label": "CTA readiness",
    },
    {
        "id": "cta_adapter_parity",
        "script": "tools/verification/design_guide_cta_adapter_parity_snapshot.py",
        "label": "CTA adapter parity",
    },
    {
        "id": "live_cta_wiring",
        "script": "tools/verification/design_guide_live_cta_wiring_snapshot.py",
        "label": "Live CTA wiring",
    },
    {
        "id": "live_cta_authority_cutover",
        "script": "tools/verification/design_guide_live_cta_authority_cutover.py",
        "label": "Live CTA authority cutover",
    },
    {
        "id": "card_vm_authority_readiness",
        "script": "tools/verification/design_guide_card_vm_authority_readiness_snapshot.py",
        "label": "Card VM readiness",
    },
    {
        "id": "card_vm_adapter_parity",
        "script": "tools/verification/design_guide_card_vm_adapter_parity_snapshot.py",
        "label": "Card VM adapter parity",
    },
    {
        "id": "live_card_vm_wiring",
        "script": "tools/verification/design_guide_live_card_vm_wiring_snapshot.py",
        "label": "Live card VM wiring",
    },
    {
        "id": "live_card_vm_authority_cutover",
        "script": "tools/verification/design_guide_live_card_vm_authority_cutover.py",
        "label": "Live card VM authority cutover",
    },
    {
        "id": "render_after_publication_freeze",
        "script": "tools/verification/design_guide_render_after_publication_freeze.py",
        "label": "Render-after-publication freeze",
    },
    {
        "id": "verifier_debug_same_object",
        "script": "tools/verification/design_guide_verifier_debug_same_object.py",
        "label": "Verifier/debug same-object proof",
    },
    {
        "id": "session_boundary_readiness",
        "script": "tools/verification/design_guide_session_boundary_readiness_snapshot.py",
        "label": "Session boundary readiness",
    },
    {
        "id": "session_boundary_canonicalization",
        "script": "tools/verification/design_guide_session_boundary_canonicalization.py",
        "label": "Session boundary canonicalization",
    },
    {
        "id": "design_brain_inputs_page_independence_audit",
        "script": "tools/verification/design_brain_inputs_page_independence_audit.py",
        "label": "Design Brain inputs_page independence audit",
    },
    {
        "id": "locked_family_live_wiring_snapshot",
        "script": "tools/verification/families/locked_family_live_wiring_snapshot.py",
        "label": "Locked family live wiring snapshot",
    },
]

REQUIRED_INPUTS_TOKENS = {
    "cta_authority": '_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"',
    "display_authority": '_FINAL_PUBLICATION_DISPLAY_AUTHORITY = "FinalDesignGuidePublication.display"',
    "same_object_payload": "final_publication_verifier_payload",
    "publication_authority_hash": "final_publication_authority_hash",
    "publication_hash": "publication_hash",
    "cta_hash": "final_publication_cta_hash",
    "display_hash": "final_publication_display_hash",
    "fallback_cta_non_authoritative": '"final_publication_cta_non_authoritative_shell": True',
    "fallback_display_non_authoritative": '"final_publication_display_non_authoritative_shell": True',
    "fallback_cta_fallback_only": '"final_publication_cta_fallback_only": True',
    "fallback_display_fallback_only": '"final_publication_display_fallback_only": True',
    "legacy_session_metadata_key": "_FINAL_PUBLICATION_LEGACY_SESSION_METADATA_KEY",
    "legacy_session_non_authoritative": '"legacy_non_authoritative": True',
    "legacy_session_compatibility": '"compatibility_only": True',
    "legacy_session_derived": '"derived_from": "FinalDesignGuidePublication"',
    "legacy_session_no_override": '"may_override_publication": False',
    "apply_queue_page_owned": "def _queue_primary_design_guide_button_action(",
    "apply_handler_page_owned": "handle_apply_buttons()",
    "render_final_panel": "design_guide_page.render_final_panel(",
    "render_html_only": "_design_guide_dashboard_card_html_from_render_model(render_model)",
}

REQUIRED_FINAL_PUBLICATION_TOKENS = {
    "publication_object": "class FinalDesignGuidePublication",
    "cta_object": "class FinalDesignGuideCTA",
    "display_object": "class FinalDesignGuideDisplay",
    "verifier_payload_object": "class FinalDesignGuideVerifierPayload",
    "stable_hash": "def stable_final_publication_hash(",
    "cta_adapter": "def build_final_publication_cta_from_current_state(",
    "display_adapter": "def build_final_publication_display_from_current_card_model(",
    "publication_builder": "def build_final_design_guide_publication(",
}

FORBIDDEN_FINAL_PUBLICATION_TOKENS = (
    "inputs_page",
    "streamlit",
    "session_state",
    "st.button",
    "st.markdown",
    "unsafe_allow_html",
    "render_final_panel",
    "handle_apply_buttons",
    "apply_design_guide_primary_action",
)


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


def _run_gate(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _latest_artifact(prefix: str) -> dict[str, Any]:
    candidates = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {"found": False, "path": None, "status": None}
    path = candidates[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "status": "INVALID_JSON", "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "snapshot_hash": payload.get("snapshot_hash"),
        "failures": payload.get("failures"),
    }


def _authority_audit_status() -> dict[str, Any]:
    candidates = sorted(
        AUDIT_DIR.glob("design_guide_final_publication_authority_audit_*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {"found": False, "path": None}
    path = candidates[0]
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "found": True,
        "path": str(path),
        "contains_final_authority": "Final" in text and "publication" in text.lower(),
    }


def _token_checks(source: str, tokens: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        name: {"token": token, "present": token in source}
        for name, token in tokens.items()
    }


def _build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    authority_audit = _authority_audit_status()

    gate_results: dict[str, dict[str, Any]] = {}
    for gate in COMPOSED_GATES:
        result = _run_gate(gate["script"])
        gate_results[gate["id"]] = {
            **gate,
            **result,
        }

    inputs_token_checks = _token_checks(inputs_source, REQUIRED_INPUTS_TOKENS)
    final_token_checks = _token_checks(final_source, REQUIRED_FINAL_PUBLICATION_TOKENS)
    missing_inputs_tokens = [
        name for name, row in inputs_token_checks.items() if not row["present"]
    ]
    missing_final_tokens = [
        name for name, row in final_token_checks.items() if not row["present"]
    ]
    final_imports = _module_imports(FINAL_PUBLICATION)
    forbidden_final_imports = [
        name
        for name in final_imports
        if name == "inputs_page" or name.startswith("inputs_page.") or name == "streamlit"
    ]
    forbidden_final_tokens = [
        token for token in FORBIDDEN_FINAL_PUBLICATION_TOKENS if token in final_source
    ]

    gate_failures = [
        gate_id for gate_id, row in gate_results.items() if not row["passed"]
    ]
    failures: list[str] = []
    if not authority_audit["found"]:
        failures.append("final_publication_authority_audit_missing")
    if gate_failures:
        failures.append("composed_gate_failed")
    if missing_inputs_tokens:
        failures.append("missing_inputs_page_authority_tokens")
    if missing_final_tokens:
        failures.append("missing_final_publication_tokens")
    if forbidden_final_imports or forbidden_final_tokens:
        failures.append("final_publication_forbidden_runtime_dependency")

    cta_authority = bool(
        inputs_token_checks["cta_authority"]["present"]
        and gate_results["live_cta_authority_cutover"]["passed"]
    )
    display_authority = bool(
        inputs_token_checks["display_authority"]["present"]
        and gate_results["live_card_vm_authority_cutover"]["passed"]
    )
    same_object = bool(
        inputs_token_checks["same_object_payload"]["present"]
        and gate_results["verifier_debug_same_object"]["passed"]
    )
    render_session_fallback_non_authoritative = bool(
        gate_results["render_after_publication_freeze"]["passed"]
        and inputs_token_checks["fallback_cta_non_authoritative"]["present"]
        and inputs_token_checks["fallback_display_non_authoritative"]["present"]
    )
    legacy_compatibility = bool(
        gate_results["session_boundary_canonicalization"]["passed"]
        and inputs_token_checks["legacy_session_non_authoritative"]["present"]
        and inputs_token_checks["legacy_session_compatibility"]["present"]
        and inputs_token_checks["legacy_session_no_override"]["present"]
    )
    page_render_route_store_only = bool(
        inputs_token_checks["apply_queue_page_owned"]["present"]
        and inputs_token_checks["apply_handler_page_owned"]["present"]
        and inputs_token_checks["render_final_panel"]["present"]
        and inputs_token_checks["render_html_only"]["present"]
        and render_session_fallback_non_authoritative
        and gate_results["design_brain_inputs_page_independence_audit"]["passed"]
    )
    apply_routing_shared_page_owned = bool(
        inputs_token_checks["apply_queue_page_owned"]["present"]
        and inputs_token_checks["apply_handler_page_owned"]["present"]
        and cta_authority
    )
    fallback_shells_fallback_only = bool(
        inputs_token_checks["fallback_cta_fallback_only"]["present"]
        and inputs_token_checks["fallback_display_fallback_only"]["present"]
        and render_session_fallback_non_authoritative
    )

    direct_proof = {
        "final_publication_authority_audit_exists": bool(authority_audit["found"]),
        "final_design_guide_publication_is_cta_authority": cta_authority,
        "final_design_guide_publication_is_display_card_vm_authority": display_authority,
        "verifier_debug_browser_payloads_hash_stamped_from_same_object": same_object,
        "render_session_fallback_paths_non_authoritative_after_publication": render_session_fallback_non_authoritative,
        "legacy_duplicated_publication_keys_compatibility_only": legacy_compatibility,
        "inputs_page_may_render_route_store_but_cannot_reinterpret_publication_truth": page_render_route_store_only,
        "apply_routing_remains_shared_page_owned_and_consumes_publication_cta": apply_routing_shared_page_owned,
        "fallback_shells_are_fallback_only_and_non_authoritative": fallback_shells_fallback_only,
        "final_publication_has_no_page_ui_runtime_imports": not bool(
            forbidden_final_imports or forbidden_final_tokens
        ),
    }
    failed_direct_proof = [
        name for name, passed in direct_proof.items() if not passed
    ]
    if failed_direct_proof:
        failures.append("direct_independence_proof_failed")

    status = "PASS" if not failures else "FAIL"
    latest_artifacts = {
        "final_publication_authority_snapshot": _latest_artifact("design_guide_final_publication_authority"),
        "final_publication_object_snapshot": _latest_artifact("design_guide_final_publication_object"),
        "final_publication_boundary_snapshot": _latest_artifact("design_guide_final_publication_boundary"),
        "cta_authority_readiness": _latest_artifact("design_guide_cta_authority_readiness"),
        "cta_adapter_parity": _latest_artifact("design_guide_cta_adapter_parity"),
        "live_cta_wiring": _latest_artifact("design_guide_live_cta_wiring"),
        "live_cta_authority_cutover": _latest_artifact("design_guide_live_cta_authority_cutover"),
        "card_vm_authority_readiness": _latest_artifact("design_guide_card_vm_authority_readiness"),
        "card_vm_adapter_parity": _latest_artifact("design_guide_card_vm_adapter_parity"),
        "live_card_vm_wiring": _latest_artifact("design_guide_live_card_vm_wiring"),
        "live_card_vm_authority_cutover": _latest_artifact("design_guide_live_card_vm_authority_cutover"),
        "render_after_publication_freeze": _latest_artifact("design_guide_render_after_publication_freeze"),
        "verifier_debug_same_object": _latest_artifact("design_guide_verifier_debug_same_object"),
        "session_boundary_readiness": _latest_artifact("design_guide_session_boundary_readiness"),
        "session_boundary_canonicalization": _latest_artifact("design_guide_session_boundary_canonicalization"),
        "design_brain_inputs_page_independence_audit": _latest_artifact("design_brain_inputs_page_independence_audit"),
        "locked_family_live_wiring_snapshot": _latest_artifact("locked_family_live_wiring"),
    }
    snapshot_hash = _stable_hash(
        {
            "direct_proof": direct_proof,
            "gate_results": {
                gate_id: row["passed"] for gate_id, row in gate_results.items()
            },
            "authority_audit": authority_audit,
            "missing_inputs_tokens": missing_inputs_tokens,
            "missing_final_tokens": missing_final_tokens,
            "failed_direct_proof": failed_direct_proof,
        }
    )
    return {
        "snapshot_name": "design_guide_independence_lock",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "direct_proof": direct_proof,
        "failed_direct_proof": failed_direct_proof,
        "authority_audit": authority_audit,
        "composed_gates": gate_results,
        "gate_failures": gate_failures,
        "latest_artifacts": latest_artifacts,
        "inputs_page_token_checks": inputs_token_checks,
        "missing_inputs_page_tokens": missing_inputs_tokens,
        "final_publication_token_checks": final_token_checks,
        "missing_final_publication_tokens": missing_final_tokens,
        "final_publication_imports": final_imports,
        "forbidden_final_publication_imports": forbidden_final_imports,
        "forbidden_final_publication_tokens": forbidden_final_tokens,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_display_authority_changed": False,
        "fallback_shells_removed": False,
        "legacy_session_keys_deleted": False,
        "apply_routing_changed": False,
        "lock_status": (
            "Design Guide independence lock complete"
            if status == "PASS"
            else "Design Guide independence lock blocked"
        ),
        "snapshot_hash": snapshot_hash,
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    proof_rows = [
        f"| {name} | `{value}` |"
        for name, value in snapshot["direct_proof"].items()
    ]
    gate_rows = [
        f"| {row['label']} | `{row['passed']}` | `{row['returncode']}` | `{row['script']}` |"
        for row in snapshot["composed_gates"].values()
    ]
    artifact_rows = [
        f"| {name} | `{row.get('found')}` | `{row.get('status')}` | `{row.get('path')}` |"
        for name, row in snapshot["latest_artifacts"].items()
    ]
    body = "\n".join(
        [
            "# Design Guide Independence Lock Verifier",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Lock status: `{snapshot['lock_status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Direct Proof",
            "",
            "| Check | Value |",
            "|---|---:|",
            *proof_rows,
            "",
            "## Composed Gates",
            "",
            "| Gate | Passed | Return Code | Script |",
            "|---|---:|---:|---|",
            *gate_rows,
            "",
            "## Latest Artifacts",
            "",
            "| Artifact | Found | Status | Path |",
            "|---|---:|---|---|",
            *artifact_rows,
            "",
            "## Authority Audit",
            "",
            f"- Found: `{snapshot['authority_audit'].get('found')}`",
            f"- Path: `{snapshot['authority_audit'].get('path')}`",
            "",
            "## Scope",
            "",
            "- Product behavior changed: `False`",
            "- Visible wording changed: `False`",
            "- CTA/display authority changed: `False`",
            "- Fallback shells removed: `False`",
            "- Legacy session keys deleted: `False`",
            "- Apply routing changed: `False`",
            "",
            "## Failures",
            "",
            (
                "None."
                if not snapshot["failures"]
                else "\n".join(f"- `{failure}`" for failure in snapshot["failures"])
            ),
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_independence_lock_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_independence_lock_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_independence_lock {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
        if snapshot["gate_failures"]:
            print("Gate failures:")
            for gate in snapshot["gate_failures"]:
                print(f"- {gate}")
        if snapshot["failed_direct_proof"]:
            print("Direct proof failures:")
            for proof in snapshot["failed_direct_proof"]:
                print(f"- {proof}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
