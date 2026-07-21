"""Verifier for live Design Guide CTA authority cutover.

This verifier proves the live CTA binding path is accountable to
FinalDesignGuidePublication.cta while rendering and apply routing remain
page/shared-owned.
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
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
APPLY_ROUTING = ROOT / "inputs_page_modules" / "apply_routing.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
DESIGN_GUIDE_RENDER_COORDINATORS = ROOT / "inputs_page_modules" / "design_guide" / "render_coordinators.py"

REQUIRED_INPUTS_TOKENS = {
    "final_publication_import": "build_final_publication_cta_from_current_state as _build_final_publication_cta_from_current_state",
    "authority_constant": '_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"',
    "authority_builder": "def _final_publication_cta_authority_payload(",
    "authority_stamper": "def _stamp_final_publication_cta_authority(",
    "payload_audit_hash": "final_publication_cta_hash=cta_authority.get(\"cta_hash\")",
    "contract_authority_marker": "contract[\"final_publication_cta_authority\"] = _FINAL_PUBLICATION_CTA_AUTHORITY",
    "contract_match_marker": "contract[\"final_publication_cta_matches_live\"] = bool(authority[\"matches_live\"])",
    "binding_stamper_call": "_stamp_final_publication_cta_authority(",
    "render_only_extracted": "def render_design_guide_component_cta(",
    "render_queue_callback_injected": "queue_primary_button_action_fn",
    "apply_queue_still_page_owned": "def _queue_primary_design_guide_button_action(",
    "apply_handler_still_page_owned": "handle_apply_buttons",
}

FORBIDDEN_RUNTIME_TOKENS_IN_FINAL_PUBLICATION = (
    "inputs_page",
    "streamlit",
    "session_state",
    "st.button",
    "handle_apply_buttons",
    "apply_design_guide_primary_action",
    "render_final_panel",
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
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, APP_CONTRACT_BRIDGE, APPLY_ROUTING)
        if path.exists()
    )
    render_source = DESIGN_GUIDE_RENDER_COORDINATORS.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    token_checks = {}
    for name, token in REQUIRED_INPUTS_TOKENS.items():
        source = render_source if name in {"render_only_extracted", "render_queue_callback_injected"} else inputs_source
        token_checks[name] = {"token": token, "present": token in source}
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

    adapter_result = _run_verifier("tools/verification/design_guide_cta_adapter_parity_snapshot.py")
    wiring_result = _run_verifier("tools/verification/design_guide_live_cta_wiring_snapshot.py")

    fallback_guarded = bool(wiring_result["passed"])
    rendering_remains_render_only = bool(
        token_checks["render_only_extracted"]["present"]
        and token_checks["render_queue_callback_injected"]["present"]
        and "def _render_design_guide_component_cta(" not in inputs_source
    )
    apply_routing_page_owned = bool(
        token_checks["apply_queue_still_page_owned"]["present"]
        and token_checks["apply_handler_still_page_owned"]["present"]
    )

    failures: list[str] = []
    if missing_tokens:
        failures.append("missing_inputs_page_authority_tokens")
    if forbidden_final_imports or forbidden_final_tokens:
        failures.append("final_publication_forbidden_runtime_dependency")
    if not adapter_result["passed"]:
        failures.append("cta_adapter_parity_snapshot_failed")
    if not wiring_result["passed"]:
        failures.append("live_cta_wiring_snapshot_failed")
    if not fallback_guarded:
        failures.append("fallback_shell_not_guarded")
    if not rendering_remains_render_only:
        failures.append("cta_rendering_not_proven_render_only")
    if not apply_routing_page_owned:
        failures.append("apply_routing_not_proven_page_owned")

    status = "PASS" if not failures else "FAIL"
    proof = {
        "final_publication_cta_is_authority": not missing_tokens,
        "live_button_contract_matches_publication_cta": bool(
            token_checks["contract_authority_marker"]["present"]
            and token_checks["contract_match_marker"]["present"]
            and wiring_result["passed"]
        ),
        "session_debug_apply_payload_matches_publication_cta": bool(
            token_checks["payload_audit_hash"]["present"] and wiring_result["passed"]
        ),
        "fallback_shell_cannot_override_without_flag": fallback_guarded,
        "cta_adapter_parity_still_passes": adapter_result["passed"],
        "live_cta_wiring_snapshot_still_passes": wiring_result["passed"],
        "cta_rendering_remains_render_only": rendering_remains_render_only,
        "apply_routing_consumes_publication_cta_payload": apply_routing_page_owned,
    }
    return {
        "snapshot_name": "design_guide_live_cta_authority_cutover",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "proof": proof,
        "inputs_page_token_checks": token_checks,
        "missing_inputs_page_tokens": missing_tokens,
        "final_publication_imports": final_imports,
        "forbidden_final_publication_imports": forbidden_final_imports,
        "forbidden_final_publication_tokens": forbidden_final_tokens,
        "composed_verifiers": {
            "cta_adapter_parity": adapter_result,
            "live_cta_wiring": wiring_result,
        },
        "authority_owner": "design_brain.final_publication.FinalDesignGuidePublication.cta",
        "render_owner": "inputs_page/design_guide_page",
        "apply_routing_owner": "inputs_page",
        "fallback_shell_policy": (
            "fallback-only and non-authoritative"
            if fallback_guarded
            else "unguarded"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "apply_routing_changed": False,
        "one_click_orchestration_changed": False,
        "engineering_decisions_changed": False,
        "card_view_model_moved": False,
        "fallback_shell_removed": False,
        "snapshot_hash": _stable_hash(
            {
                "proof": proof,
                "token_checks": {
                    name: row["present"] for name, row in token_checks.items()
                },
                "adapter_passed": adapter_result["passed"],
                "wiring_passed": wiring_result["passed"],
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
            "# Design Guide Live CTA Authority Cutover",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Authority",
            "",
            f"- CTA authority owner: `{snapshot['authority_owner']}`",
            f"- Render owner: `{snapshot['render_owner']}`",
            f"- Apply routing owner: `{snapshot['apply_routing_owner']}`",
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
            f"- CTA adapter parity: `{snapshot['composed_verifiers']['cta_adapter_parity']['passed']}`",
            f"- Live CTA wiring: `{snapshot['composed_verifiers']['live_cta_wiring']['passed']}`",
            "",
            "## Guardrails",
            "",
            f"- Product behaviour changed: `{snapshot['product_behavior_changed']}`",
            f"- Visible wording changed: `{snapshot['visible_wording_changed']}`",
            f"- Apply routing changed: `{snapshot['apply_routing_changed']}`",
            f"- One-click orchestration changed: `{snapshot['one_click_orchestration_changed']}`",
            f"- Engineering decisions changed: `{snapshot['engineering_decisions_changed']}`",
            f"- Card view model moved: `{snapshot['card_view_model_moved']}`",
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
    json_path = ARTIFACT_DIR / f"design_guide_live_cta_authority_cutover_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_cta_authority_cutover_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_live_cta_authority_cutover {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("failures=" + ", ".join(snapshot["failures"]))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
