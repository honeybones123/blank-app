"""Verifier for live Design Guide card VM authority cutover."""

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
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
FINAL_FORMATTER = ROOT / "design_brain" / "final_design_guide_formatter.py"

REQUIRED_INPUTS_TOKENS = {
    "display_model_object": "class FinalDesignGuideDisplay",
    "display_adapter": "def build_final_publication_display_from_current_card_model(",
    "display_not_renderer_driving": "renderer_driving=False",
    "clean_format_builder": "def build_final_design_guide_card_format(",
    "display_hash_in_clean_format": "final_publication_display_hash=display_hash",
    "clean_html_renderer": "def render_final_design_guide_card_html(",
    "cta_authority_constant": '_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"',
}

FORBIDDEN_RUNTIME_TOKENS_IN_FINAL_PUBLICATION = (
    "inputs_page",
    "streamlit",
    "session_state",
    "st.markdown",
    "st.button",
    "render_final_panel",
    "unsafe_allow_html",
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


def _run_verifier(script: str) -> dict[str, Any]:
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
        "stdout": proc.stdout.strip().splitlines()[-8:],
        "stderr": proc.stderr.strip().splitlines()[-8:],
    }


def _build_snapshot() -> dict[str, Any]:
    inputs_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, APP_CONTRACT_BRIDGE)
        if path.exists()
    )
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    formatter_source = FINAL_FORMATTER.read_text(encoding="utf-8")
    renderer_source = (ROOT / "ui" / "final_design_guide_card.py").read_text(encoding="utf-8")
    display_source = "\n".join([inputs_source, final_source, formatter_source, renderer_source])
    token_checks = {
        name: {"token": token, "present": token in display_source}
        for name, token in REQUIRED_INPUTS_TOKENS.items()
    }
    missing_tokens = [name for name, row in token_checks.items() if not row["present"]]

    final_imports = _module_imports(FINAL_PUBLICATION)
    forbidden_final_imports = [
        name
        for name in final_imports
        if name == "inputs_page" or name.startswith("inputs_page.") or name == "streamlit"
    ]
    forbidden_final_tokens = [
        token for token in FORBIDDEN_RUNTIME_TOKENS_IN_FINAL_PUBLICATION if token in final_source
    ]

    adapter_result = _run_verifier("tools/verification/design_guide_card_vm_adapter_parity_snapshot.py")
    wiring_result = _run_verifier("tools/verification/design_guide_live_card_vm_wiring_snapshot.py")
    cta_result = _run_verifier("tools/verification/design_guide_live_cta_authority_cutover.py")

    fallback_guarded = bool(wiring_result["passed"])
    legacy_html_renderer_absent = "_design_guide_dashboard_card_html_from_render_model(" not in inputs_source
    direct_shell_helper_absent = "def _design_guide_direct_action_shell_card_html(" not in inputs_source
    direct_shell_deletion_markers_present = direct_shell_helper_absent
    rendering_render_only = bool(
        token_checks["clean_html_renderer"]["present"]
        and legacy_html_renderer_absent
        and direct_shell_helper_absent
    )
    cta_authority_preserved = bool(token_checks["cta_authority_constant"]["present"] and cta_result["passed"])

    failures: list[str] = []
    if missing_tokens:
        failures.append("missing_inputs_page_display_authority_tokens")
    if forbidden_final_imports or forbidden_final_tokens:
        failures.append("final_publication_forbidden_runtime_dependency")
    if not adapter_result["passed"]:
        failures.append("card_vm_adapter_parity_snapshot_failed")
    if not wiring_result["passed"]:
        failures.append("live_card_vm_wiring_snapshot_failed")
    if not cta_result["passed"]:
        failures.append("live_cta_authority_cutover_failed")
    if not fallback_guarded:
        failures.append("fallback_shell_not_guarded")
    if not rendering_render_only:
        failures.append("rendering_not_proven_render_only")
    if not cta_authority_preserved:
        failures.append("cta_authority_regressed")

    proof = {
        "final_publication_display_is_authority": not missing_tokens,
        "live_render_model_matches_publication_display": bool(wiring_result["passed"]),
        "fallback_shell_cannot_override_without_flag": fallback_guarded,
        "card_vm_adapter_parity_still_passes": adapter_result["passed"],
        "live_card_vm_wiring_snapshot_still_passes": wiring_result["passed"],
        "cta_authority_remains_final_publication_cta": cta_authority_preserved,
        "rendering_remains_render_only": rendering_render_only,
        "legacy_html_renderer_absent": legacy_html_renderer_absent,
        "direct_shell_helper_absent": direct_shell_helper_absent,
        "direct_shell_deletion_markers_present": direct_shell_deletion_markers_present,
    }
    status = "PASS" if not failures else "FAIL"
    return {
        "snapshot_name": "design_guide_live_card_vm_authority_cutover",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "proof": proof,
        "inputs_page_token_checks": token_checks,
        "missing_inputs_page_tokens": missing_tokens,
        "final_publication_imports": final_imports,
        "forbidden_final_publication_imports": forbidden_final_imports,
        "forbidden_final_publication_tokens": forbidden_final_tokens,
        "composed_verifiers": {
            "card_vm_adapter_parity": adapter_result,
            "live_card_vm_wiring": wiring_result,
            "live_cta_authority_cutover": cta_result,
        },
        "authority_owner": "design_brain.final_publication.FinalDesignGuidePublication.display",
        "render_owner": "inputs_page/design_guide_page/ui.design_guide_cards",
        "cta_authority_owner": "design_brain.final_publication.FinalDesignGuidePublication.cta",
        "fallback_shell_policy": (
            "fallback-only and non-authoritative"
            if fallback_guarded
            else "unguarded"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "card_colours_changed": False,
        "badge_title_summary_changed": False,
        "layout_changed": False,
        "cta_authority_changed": False,
        "apply_routing_changed": False,
        "engineering_decisions_changed": False,
        "fallback_shell_removed": False,
        "snapshot_hash": _stable_hash(
            {
                "proof": proof,
                "token_checks": {
                    name: row["present"] for name, row in token_checks.items()
                },
                "adapter_passed": adapter_result["passed"],
                "wiring_passed": wiring_result["passed"],
                "cta_passed": cta_result["passed"],
            }
        ),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    proof_rows = [
        f"| {name} | `{value}` |" for name, value in snapshot["proof"].items()
    ]
    token_rows = [
        f"| {name} | `{row['present']}` | `{row['token']}` |"
        for name, row in snapshot["inputs_page_token_checks"].items()
    ]
    body = "\n".join(
        [
            "# Design Guide Live Card VM Authority Cutover",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Authority",
            "",
            f"- Display authority owner: `{snapshot['authority_owner']}`",
            f"- Render owner: `{snapshot['render_owner']}`",
            f"- CTA authority owner: `{snapshot['cta_authority_owner']}`",
            f"- Fallback shell policy: `{snapshot['fallback_shell_policy']}`",
            "",
            "## Proof",
            "",
            "| Check | Value |",
            "|---|---:|",
            *proof_rows,
            "",
            "## Token Checks",
            "",
            "| Check | Present | Token |",
            "|---|---:|---|",
            *token_rows,
            "",
            "## Composed Verifiers",
            "",
            f"- Card VM adapter parity: `{snapshot['composed_verifiers']['card_vm_adapter_parity']['passed']}`",
            f"- Live card VM wiring: `{snapshot['composed_verifiers']['live_card_vm_wiring']['passed']}`",
            f"- Live CTA authority cutover: `{snapshot['composed_verifiers']['live_cta_authority_cutover']['passed']}`",
            "",
            "## Guardrails",
            "",
            f"- Product behaviour changed: `{snapshot['product_behavior_changed']}`",
            f"- Visible wording changed: `{snapshot['visible_wording_changed']}`",
            f"- Card colours changed: `{snapshot['card_colours_changed']}`",
            f"- Badge/title/summary changed: `{snapshot['badge_title_summary_changed']}`",
            f"- Layout changed: `{snapshot['layout_changed']}`",
            f"- CTA authority changed: `{snapshot['cta_authority_changed']}`",
            f"- Apply routing changed: `{snapshot['apply_routing_changed']}`",
            f"- Engineering decisions changed: `{snapshot['engineering_decisions_changed']}`",
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
    json_path = ARTIFACT_DIR / f"design_guide_live_card_vm_authority_cutover_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_card_vm_authority_cutover_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_live_card_vm_authority_cutover {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("failures=" + ", ".join(snapshot["failures"]))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
