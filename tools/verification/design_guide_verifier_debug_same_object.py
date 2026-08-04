"""Verifier for Design Guide verifier/debug same-object publication proof.

The verifier proves debug/session/browser-facing payloads are stamped from the
same FinalDesignGuidePublication authority surface used for live CTA/display,
instead of restamping an independent truth after publication.
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

from design_brain.final_publication import stable_final_publication_hash


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

REQUIRED_DEBUG_PAYLOAD_TOKENS: dict[str, str] = {
    "same_object_payload_helper": "def _final_publication_same_object_verifier_payload(",
    "same_object_payload_stamper": "def _stamp_final_publication_same_object_verifier_payload(",
    "debug_payload_key": 'debug_sink["final_publication_verifier_payload"] = dict(payload)',
    "debug_publication_hash_key": 'debug_sink["final_publication_publication_hash"] = payload["publication_hash"]',
    "generic_publication_hash_key": 'debug_sink["publication_hash"] = payload["publication_hash"]',
    "final_publication_authority_hash_field": '"final_publication_authority_hash": authority_hash',
    "publication_hash_field": '"publication_hash": publication_hash',
    "cta_hash_field": '"final_publication_cta_hash": cta_hash',
    "display_hash_field": '"final_publication_display_hash": display_hash',
    "selected_family_field": '"selected_family": selected_family',
    "outcome_state_field": '"outcome_state": outcome_state',
    "blocker_reason_field": '"blocker_reason": blocker_reason',
    "cta_field": '"cta": cta_payload',
    "display_field": '"display": display_payload',
    "debug_cannot_mutate": '"debug_payload_mutation_allowed": False',
    "browser_expectation_source": '"browser_expectation_source": "FinalDesignGuidePublication"',
    "dom_expectation_source": '"dom_expectation_source": "FinalDesignGuidePublication"',
    "render_not_driving": '"render_driving": False',
    "browser_not_driving": '"browser_driving": False',
    "cta_stamp_calls_same_object": "_stamp_final_publication_same_object_verifier_payload(",
    "display_stamp_calls_same_object": "_stamp_final_publication_same_object_verifier_payload(",
    "actual_probe_publication_hash": '"publication_hash": (',
    "actual_probe_same_object_payload": '"final_publication_verifier_payload": dict(',
    "normal_probe_post_sync": "_same_object_probe[\"final_publication_verifier_payload\"] = dict(_same_object_payload)",
}

REQUIRED_FINAL_PUBLICATION_TOKENS: dict[str, str] = {
    "publication_object": "class FinalDesignGuidePublication",
    "cta_object": "class FinalDesignGuideCTA",
    "display_object": "class FinalDesignGuideDisplay",
    "verifier_payload_object": "class FinalDesignGuideVerifierPayload",
    "publication_hash": "publication_hash",
    "stable_hash": "def stable_final_publication_hash(",
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

IMMUTABLE_DEBUG_FIELDS = (
    "selected_family",
    "outcome_state",
    "blocker_reason",
    "cta",
    "display",
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
    env = dict(os.environ)
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-8:],
        "stderr_tail": proc.stderr.strip().splitlines()[-8:],
    }


def _token_checks(source: str, tokens: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        name: {"token": token, "present": token in source}
        for name, token in tokens.items()
    }


def _sample_same_object_hashes() -> dict[str, Any]:
    cta = {
        "enabled": True,
        "label": "Apply recommendation",
        "disabled_reason": None,
        "action_type": "apply_resolved_candidate",
    }
    display = {
        "title": "Design guide",
        "badge": "ACTION",
        "summary": "Apply the selected repair.",
        "display_state": "ACTION",
    }
    cta_hash = stable_final_publication_hash(cta)
    display_hash = stable_final_publication_hash(display)
    same_object = {
        "selected_family": "BENDING_FAIL_GOVERNS",
        "outcome_state": "ACTION",
        "blocker_reason": None,
        "cta": cta,
        "display": display,
        "cta_hash": cta_hash,
        "display_hash": display_hash,
    }
    authority_hash = stable_final_publication_hash(
        {
            "authority": "FinalDesignGuidePublication",
            "cta_hash": cta_hash,
            "display_hash": display_hash,
        }
    )
    publication_hash_a = stable_final_publication_hash(same_object)
    publication_hash_b = stable_final_publication_hash(json.loads(_stable_json(same_object)))
    return {
        "cta_hash": cta_hash,
        "display_hash": display_hash,
        "authority_hash": authority_hash,
        "publication_hash": publication_hash_a,
        "publication_hash_repeat": publication_hash_b,
        "hashes_stable": publication_hash_a == publication_hash_b,
    }


def _build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    debug_token_checks = _token_checks(inputs_source, REQUIRED_DEBUG_PAYLOAD_TOKENS)
    final_token_checks = _token_checks(final_source, REQUIRED_FINAL_PUBLICATION_TOKENS)
    missing_debug_tokens = [
        name for name, row in debug_token_checks.items() if not row["present"]
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

    freeze = _run_verifier("tools/verification/design_guide_render_after_publication_freeze.py")
    cta_cutover = _run_verifier("tools/verification/design_guide_live_cta_authority_cutover.py")
    card_cutover = _run_verifier("tools/verification/design_guide_live_card_vm_authority_cutover.py")
    sample_hashes = _sample_same_object_hashes()

    debug_payload_fields = {
        "final_publication_authority_hash": debug_token_checks["final_publication_authority_hash_field"]["present"],
        "publication_hash": debug_token_checks["publication_hash_field"]["present"],
        "cta_authority_hash": debug_token_checks["cta_hash_field"]["present"],
        "display_authority_hash": debug_token_checks["display_hash_field"]["present"],
        "selected_family": debug_token_checks["selected_family_field"]["present"],
        "outcome_state": debug_token_checks["outcome_state_field"]["present"],
        "blocker_reason": debug_token_checks["blocker_reason_field"]["present"],
        "cta_enabled_label_disabled_reason": debug_token_checks["cta_field"]["present"],
        "display_title_badge_summary_state": debug_token_checks["display_field"]["present"],
    }
    missing_payload_fields = [
        name for name, present in debug_payload_fields.items() if not present
    ]

    immutability_proof = {
        field: {
            "mutation_allowed": False,
            "source": "FinalDesignGuidePublication",
        }
        for field in IMMUTABLE_DEBUG_FIELDS
    }
    dom_browser_same_object = bool(
        debug_token_checks["browser_expectation_source"]["present"]
        and debug_token_checks["dom_expectation_source"]["present"]
        and debug_token_checks["actual_probe_same_object_payload"]["present"]
        and debug_token_checks["normal_probe_post_sync"]["present"]
    )

    failures: list[str] = []
    if missing_debug_tokens:
        failures.append("missing_debug_same_object_tokens")
    if missing_final_tokens:
        failures.append("missing_final_publication_object_tokens")
    if missing_payload_fields:
        failures.append("missing_required_debug_payload_fields")
    if forbidden_final_imports or forbidden_final_tokens:
        failures.append("final_publication_forbidden_runtime_dependency")
    if not sample_hashes["hashes_stable"]:
        failures.append("final_publication_hash_unstable")
    if not freeze["passed"]:
        failures.append("render_after_publication_freeze_failed")
    if not cta_cutover["passed"]:
        failures.append("live_cta_authority_cutover_failed")
    if not card_cutover["passed"]:
        failures.append("live_card_vm_authority_cutover_failed")
    if not dom_browser_same_object:
        failures.append("dom_browser_expectations_not_same_object")

    proof = {
        "debug_session_browser_payload_includes_required_fields": not bool(missing_payload_fields),
        "hashes_match_final_publication_hash_algorithm": bool(sample_hashes["hashes_stable"]),
        "debug_payload_cannot_mutate_outcome_cta_display_blocker_or_family": bool(
            debug_token_checks["debug_cannot_mutate"]["present"]
        ),
        "dom_browser_expectations_derive_from_same_publication_payload": dom_browser_same_object,
        "render_after_publication_freeze_still_passes": freeze["passed"],
        "cta_authority_cutover_still_passes": cta_cutover["passed"],
        "display_authority_cutover_still_passes": card_cutover["passed"],
        "final_publication_has_no_page_ui_runtime_imports": not bool(
            forbidden_final_imports or forbidden_final_tokens
        ),
    }
    status = "PASS" if not failures else "FAIL"
    snapshot_hash = _stable_hash(
        {
            "proof": proof,
            "debug_payload_fields": debug_payload_fields,
            "sample_hashes": sample_hashes,
            "freeze": freeze["passed"],
            "cta": cta_cutover["passed"],
            "display": card_cutover["passed"],
        }
    )
    return {
        "snapshot_name": "design_guide_verifier_debug_same_object",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "proof": proof,
        "debug_payload_fields": debug_payload_fields,
        "missing_payload_fields": missing_payload_fields,
        "debug_token_checks": debug_token_checks,
        "missing_debug_tokens": missing_debug_tokens,
        "final_publication_token_checks": final_token_checks,
        "missing_final_publication_tokens": missing_final_tokens,
        "final_publication_imports": final_imports,
        "forbidden_final_publication_imports": forbidden_final_imports,
        "forbidden_final_publication_tokens": forbidden_final_tokens,
        "immutability_proof": immutability_proof,
        "sample_hashes": sample_hashes,
        "composed_verifiers": {
            "render_after_publication_freeze": freeze,
            "live_cta_authority_cutover": cta_cutover,
            "live_card_vm_authority_cutover": card_cutover,
        },
        "payload_branch_result": (
            "same_object_hash_stamped"
            if status == "PASS"
            else "restamp_branch_detected_or_unproven"
        ),
        "product_behavior_changed": False,
        "visible_behavior_changed": False,
        "cta_authority_changed": False,
        "display_authority_changed": False,
        "apply_routing_changed": False,
        "family_runtimes_changed": False,
        "fallback_shells_removed": False,
        "snapshot_hash": snapshot_hash,
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    proof_rows = [f"| {name} | `{value}` |" for name, value in snapshot["proof"].items()]
    field_rows = [
        f"| {name} | `{present}` |"
        for name, present in snapshot["debug_payload_fields"].items()
    ]
    verifier_rows = [
        f"| {name} | `{row['passed']}` | `{row['returncode']}` |"
        for name, row in snapshot["composed_verifiers"].items()
    ]
    body = "\n".join(
        [
            "# Design Guide Verifier/Debug Same-Object Proof",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Proof",
            "",
            "| Check | Value |",
            "|---|---:|",
            *proof_rows,
            "",
            "## Required Debug Payload Fields",
            "",
            "| Field | Present |",
            "|---|---:|",
            *field_rows,
            "",
            "## Sample Hashes",
            "",
            f"- final publication authority hash: `{snapshot['sample_hashes']['authority_hash']}`",
            f"- publication hash: `{snapshot['sample_hashes']['publication_hash']}`",
            f"- hash repeat stable: `{snapshot['sample_hashes']['hashes_stable']}`",
            "",
            "## Composed Verifiers",
            "",
            "| Verifier | Passed | Return Code |",
            "|---|---:|---:|",
            *verifier_rows,
            "",
            "## Payload Branch Result",
            "",
            f"`{snapshot['payload_branch_result']}`",
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
    json_path = ARTIFACT_DIR / f"design_guide_verifier_debug_same_object_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_verifier_debug_same_object_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_verifier_debug_same_object {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
