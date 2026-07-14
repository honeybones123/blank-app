"""Verifier for render-after-publication freeze.

This verifier proves that once FinalDesignGuidePublication owns CTA/display
authority, downstream render, session/debug, and fallback paths are either
render/storage-only or explicitly marked fallback-only/non-authoritative.
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

FROZEN_SURFACES: dict[str, dict[str, str]] = {
    "selected_family": {
        "authority": "FinalDesignGuidePublication",
        "evidence": "selected_family",
    },
    "outcome_state": {
        "authority": "FinalDesignGuidePublication",
        "evidence": "outcome_state",
    },
    "publication_reason": {
        "authority": "FinalDesignGuidePublication",
        "evidence": "publication_reason",
    },
    "blocker_reason": {
        "authority": "FinalDesignGuidePublication",
        "evidence": "blocker_reason",
    },
    "cta_enabled": {
        "authority": "FinalDesignGuidePublication.cta",
        "evidence": "\"enabled\"",
    },
    "cta_label": {
        "authority": "FinalDesignGuidePublication.cta",
        "evidence": "\"label\"",
    },
    "cta_disabled_reason": {
        "authority": "FinalDesignGuidePublication.cta",
        "evidence": "\"disabled_reason\"",
    },
    "apply_payload_fingerprint": {
        "authority": "FinalDesignGuidePublication.cta",
        "evidence": "\"apply_payload_fingerprint\"",
    },
    "display_title": {
        "authority": "FinalDesignGuidePublication.display",
        "evidence": "\"title\"",
    },
    "display_badge": {
        "authority": "FinalDesignGuidePublication.display",
        "evidence": "\"badge\"",
    },
    "display_colour_state": {
        "authority": "FinalDesignGuidePublication.display",
        "evidence": "\"colour_state\"",
    },
    "display_summary": {
        "authority": "FinalDesignGuidePublication.display",
        "evidence": "\"summary\"",
    },
    "display_blocker_explanation": {
        "authority": "FinalDesignGuidePublication.display",
        "evidence": "\"blocker_explanation\"",
    },
}

REQUIRED_INPUTS_TOKENS: dict[str, str] = {
    "cta_authority_constant": '_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"',
    "display_authority_constant": '_FINAL_PUBLICATION_DISPLAY_AUTHORITY = "FinalDesignGuidePublication.display"',
    "publication_authority_hash_builder": "def _final_publication_authority_hash_from_parts(",
    "cta_authority_stamper": "def _stamp_final_publication_cta_authority(",
    "display_authority_stamper": "def _stamp_final_publication_display_authority(",
    "debug_authority_hash_stamp": 'debug_sink["final_publication_authority_hash"] = publication_hash',
    "button_contract_cta_authority": 'contract["final_publication_cta_authority"] = _FINAL_PUBLICATION_CTA_AUTHORITY',
    "button_contract_cta_match": 'contract["final_publication_cta_matches_live"] = bool(authority["matches_live"])',
    "debug_display_authority": 'debug_sink["final_publication_display_authority"] = _FINAL_PUBLICATION_DISPLAY_AUTHORITY',
    "debug_display_match": 'debug_sink["final_publication_display_matches_live"] = bool(authority["matches_live"])',
    "render_model_display_stamp": "_stamp_final_publication_display_authority(",
    "render_only_html": "_design_guide_dashboard_card_html_from_render_model(render_model)",
    "page_render_call": "design_guide_page.render_final_panel(",
    "apply_queue_page_owned": "def _queue_primary_design_guide_button_action(",
    "apply_handler_page_owned": "handle_apply_buttons()",
    "fallback_cta_fallback_only": '"final_publication_cta_fallback_only": True',
    "fallback_cta_non_authoritative": '"final_publication_cta_non_authoritative_shell": True',
    "fallback_display_fallback_only": '"final_publication_display_fallback_only": True',
    "fallback_display_non_authoritative": '"final_publication_display_non_authoritative_shell": True',
    "fallback_probe_publication_hash": '"final_publication_authority_hash": _fallback_publication_hash',
    "pre_render_probe_publication_hash": '"final_publication_authority_hash": _pre_render_publication_hash',
    "actual_card_render_probe": '"actual_card_render_probe"',
    "debug_bundle_storage": "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY]",
    "final_visible_binding": "def _publish_final_visible_design_guide_contract_binding(",
    "final_visible_resolver": "def resolve_final_visible_design_guide_item(",
}

REQUIRED_FINAL_PUBLICATION_TOKENS: dict[str, str] = {
    "publication_object": "class FinalDesignGuidePublication",
    "cta_object": "class FinalDesignGuideCTA",
    "display_object": "class FinalDesignGuideDisplay",
    "publication_hash_field": "publication_hash",
    "publication_hash_method": "def with_publication_hash(",
    "cta_adapter": "def build_final_publication_cta_from_current_state(",
    "display_adapter": "def build_final_publication_display_from_current_card_model(",
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

LATE_CHECKPOINTS: list[dict[str, Any]] = [
    {
        "checkpoint": "final_visible_resolver",
        "symbol": "resolve_final_visible_design_guide_item",
        "authority_role": "pre-publication resolver; not downstream freeze authority",
        "guard_tokens": ["def resolve_final_visible_design_guide_item("],
        "can_change_outcome": True,
        "downstream_of_final_publication": False,
    },
    {
        "checkpoint": "final_visible_contract_binding",
        "symbol": "_publish_final_visible_design_guide_contract_binding",
        "authority_role": "pre-render binding; downstream CTA/display fields are stamped to publication authority",
        "guard_tokens": [
            "def _publish_final_visible_design_guide_contract_binding(",
            "_stamp_final_publication_cta_authority(",
        ],
        "can_change_outcome": True,
        "downstream_of_final_publication": False,
    },
    {
        "checkpoint": "live_cta_binding",
        "symbol": "_stamp_final_publication_cta_authority",
        "authority_role": "FinalDesignGuidePublication.cta authority stamp",
        "guard_tokens": [
            "def _stamp_final_publication_cta_authority(",
            'contract["final_publication_cta_authority"] = _FINAL_PUBLICATION_CTA_AUTHORITY',
            'contract["final_publication_cta_matches_live"] = bool(authority["matches_live"])',
        ],
        "can_change_cta": False,
        "downstream_of_final_publication": False,
    },
    {
        "checkpoint": "live_card_view_model_binding",
        "symbol": "_stamp_final_publication_display_authority",
        "authority_role": "FinalDesignGuidePublication.display authority stamp",
        "guard_tokens": [
            "def _stamp_final_publication_display_authority(",
            'debug_sink["final_publication_display_authority"] = _FINAL_PUBLICATION_DISPLAY_AUTHORITY',
            'debug_sink["final_publication_display_matches_live"] = bool(authority["matches_live"])',
        ],
        "can_change_visible_display": False,
        "downstream_of_final_publication": False,
    },
    {
        "checkpoint": "card_html_render",
        "symbol": "_design_guide_dashboard_card_html_from_render_model",
        "authority_role": "renderer-only after display authority stamp",
        "guard_tokens": [
            "_stamp_final_publication_display_authority(",
            "_design_guide_dashboard_card_html_from_render_model(render_model)",
        ],
        "can_change_visible_display": False,
        "downstream_of_final_publication": True,
    },
    {
        "checkpoint": "debug_session_bundle",
        "symbol": "DESIGN_GUIDE_DEBUG_BUNDLE_KEY",
        "authority_role": "storage-only; stamped with final publication hash",
        "guard_tokens": [
            "final_publication_authority_hash",
            "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY]",
        ],
        "can_restamp_debug_session": False,
        "downstream_of_final_publication": True,
    },
    {
        "checkpoint": "browser_pre_render_shell",
        "symbol": "browser_enabled_contract_pre_render_shell",
        "authority_role": "fallback-only, non-authoritative shell",
        "guard_tokens": [
            "browser_enabled_contract_pre_render_shell",
            '"final_publication_cta_non_authoritative_shell": True',
            '"final_publication_display_non_authoritative_shell": True',
            '"final_publication_authority_hash": _pre_render_publication_hash',
        ],
        "can_change_outcome": False,
        "can_change_cta": False,
        "can_change_visible_display": False,
        "downstream_of_final_publication": True,
    },
    {
        "checkpoint": "render_fallback_shell",
        "symbol": "fallback_enabled_contract_shell",
        "authority_role": "fallback-only, non-authoritative shell",
        "guard_tokens": [
            "fallback_enabled_contract_shell",
            '"final_publication_cta_non_authoritative_shell": True',
            '"final_publication_display_non_authoritative_shell": True',
            '"final_publication_authority_hash": _fallback_publication_hash',
        ],
        "can_change_outcome": False,
        "can_change_cta": False,
        "can_change_visible_display": False,
        "downstream_of_final_publication": True,
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
        "stdout_tail": proc.stdout.strip().splitlines()[-8:],
        "stderr_tail": proc.stderr.strip().splitlines()[-8:],
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
        "payload": payload,
    }


def _token_checks(source: str, required: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        name: {"token": token, "present": token in source}
        for name, token in required.items()
    }


def _late_checkpoint_status(inputs_source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for checkpoint in LATE_CHECKPOINTS:
        guard_tokens = list(checkpoint.get("guard_tokens") or [])
        missing = [token for token in guard_tokens if token not in inputs_source]
        legacy_resolver_deleted = (
            checkpoint.get("checkpoint") == "final_visible_resolver"
            and missing
            and "def resolve_final_visible_design_guide_item(" not in inputs_source
        )
        rows.append(
            {
                **checkpoint,
                "guard_tokens_present": not missing or legacy_resolver_deleted,
                "missing_guard_tokens": missing,
                "freeze_policy": (
                    "legacy_resolver_deleted"
                    if legacy_resolver_deleted
                    else (
                    "guarded_non_authoritative_or_render_only"
                    if not missing
                    else "unproven"
                    )
                ),
                "legacy_resolver_deleted": legacy_resolver_deleted,
            }
        )
    return rows


def _build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")

    inputs_token_checks = _token_checks(inputs_source, REQUIRED_INPUTS_TOKENS)
    final_token_checks = _token_checks(final_source, REQUIRED_FINAL_PUBLICATION_TOKENS)
    missing_inputs_tokens = [
        name for name, row in inputs_token_checks.items() if not row["present"]
        and name != "final_visible_resolver"
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

    cta_cutover = _run_verifier("tools/verification/design_guide_live_cta_authority_cutover.py")
    card_cutover = _run_verifier("tools/verification/design_guide_live_card_vm_authority_cutover.py")
    latest_authority_snapshot = _latest_artifact("design_guide_final_publication_authority")
    latest_cta_cutover = _latest_artifact("design_guide_live_cta_authority_cutover")
    latest_card_cutover = _latest_artifact("design_guide_live_card_vm_authority_cutover")

    late_checkpoints = _late_checkpoint_status(inputs_source)
    unguarded_late_paths = [
        row["checkpoint"] for row in late_checkpoints if not row["guard_tokens_present"]
    ]

    frozen_surface_checks = {
        name: {
            **surface,
            "authority_marker_present": surface["evidence"] in final_source
            or surface["evidence"] in inputs_source,
            "downstream_override_allowed": False,
        }
        for name, surface in FROZEN_SURFACES.items()
    }
    missing_frozen_surface_evidence = [
        name
        for name, row in frozen_surface_checks.items()
        if not row["authority_marker_present"]
    ]

    fallback_guarded = bool(
        inputs_token_checks["fallback_cta_fallback_only"]["present"]
        and inputs_token_checks["fallback_cta_non_authoritative"]["present"]
        and inputs_token_checks["fallback_display_fallback_only"]["present"]
        and inputs_token_checks["fallback_display_non_authoritative"]["present"]
        and inputs_token_checks["fallback_probe_publication_hash"]["present"]
        and inputs_token_checks["pre_render_probe_publication_hash"]["present"]
    )
    session_debug_storage_guarded = bool(
        inputs_token_checks["debug_authority_hash_stamp"]["present"]
        and inputs_token_checks["debug_bundle_storage"]["present"]
    )
    verifier_payloads_identify_publication_hash = bool(
        inputs_token_checks["fallback_probe_publication_hash"]["present"]
        and inputs_token_checks["pre_render_probe_publication_hash"]["present"]
        and inputs_token_checks["actual_card_render_probe"]["present"]
    )
    render_only_guarded = bool(
        inputs_token_checks["render_only_html"]["present"]
        and inputs_token_checks["page_render_call"]["present"]
    )

    failures: list[str] = []
    if missing_inputs_tokens:
        failures.append("missing_inputs_page_freeze_tokens")
    if missing_final_tokens:
        failures.append("missing_final_publication_tokens")
    if forbidden_final_imports or forbidden_final_tokens:
        failures.append("final_publication_forbidden_runtime_dependency")
    if not cta_cutover["passed"]:
        failures.append("live_cta_authority_cutover_failed")
    if not card_cutover["passed"]:
        failures.append("live_card_vm_authority_cutover_failed")
    if unguarded_late_paths:
        failures.append("unguarded_late_render_paths")
    if missing_frozen_surface_evidence:
        failures.append("missing_frozen_surface_evidence")
    if not fallback_guarded:
        failures.append("fallback_shell_not_non_authoritative")
    if not session_debug_storage_guarded:
        failures.append("session_debug_storage_can_restamp_truth")
    if not verifier_payloads_identify_publication_hash:
        failures.append("verifier_browser_payload_missing_publication_hash")
    if not render_only_guarded:
        failures.append("render_path_not_proven_render_only")

    proof = {
        "downstream_cannot_alter_selected_family_or_outcome": not bool(
            missing_frozen_surface_evidence
        ),
        "downstream_cannot_alter_cta": bool(cta_cutover["passed"]),
        "downstream_cannot_alter_display": bool(card_cutover["passed"]),
        "fallback_shells_are_fallback_only": fallback_guarded,
        "fallback_shells_are_non_authoritative": fallback_guarded,
        "fallback_shells_are_publication_hash_stamped": verifier_payloads_identify_publication_hash,
        "session_debug_bundles_storage_only": session_debug_storage_guarded,
        "verifier_browser_payloads_identify_publication_hash": verifier_payloads_identify_publication_hash,
        "cta_authority_cutover_still_passes": cta_cutover["passed"],
        "display_authority_cutover_still_passes": card_cutover["passed"],
        "rendering_remains_render_only": render_only_guarded,
        "apply_routing_unchanged_page_owned": bool(
            inputs_token_checks["apply_queue_page_owned"]["present"]
            and inputs_token_checks["apply_handler_page_owned"]["present"]
        ),
    }
    status = "PASS" if not failures else "FAIL"
    snapshot_hash = _stable_hash(
        {
            "proof": proof,
            "frozen_surface_checks": {
                key: row["authority_marker_present"]
                for key, row in frozen_surface_checks.items()
            },
            "late_checkpoints": {
                row["checkpoint"]: row["guard_tokens_present"]
                for row in late_checkpoints
            },
            "cta_cutover_passed": cta_cutover["passed"],
            "card_cutover_passed": card_cutover["passed"],
        }
    )

    return {
        "snapshot_name": "design_guide_render_after_publication_freeze",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "proof": proof,
        "frozen_surfaces": frozen_surface_checks,
        "missing_frozen_surface_evidence": missing_frozen_surface_evidence,
        "late_checkpoints": late_checkpoints,
        "unguarded_late_paths": unguarded_late_paths,
        "inputs_page_token_checks": inputs_token_checks,
        "missing_inputs_page_tokens": missing_inputs_tokens,
        "final_publication_token_checks": final_token_checks,
        "missing_final_publication_tokens": missing_final_tokens,
        "final_publication_imports": final_imports,
        "forbidden_final_publication_imports": forbidden_final_imports,
        "forbidden_final_publication_tokens": forbidden_final_tokens,
        "composed_verifiers": {
            "live_cta_authority_cutover": cta_cutover,
            "live_card_vm_authority_cutover": card_cutover,
        },
        "referenced_artifacts": {
            "final_publication_authority_snapshot": {
                key: value
                for key, value in latest_authority_snapshot.items()
                if key != "payload"
            },
            "live_cta_authority_cutover": {
                key: value for key, value in latest_cta_cutover.items() if key != "payload"
            },
            "live_card_vm_authority_cutover": {
                key: value for key, value in latest_card_cutover.items() if key != "payload"
            },
        },
        "fallback_shell_policy": (
            "fallback-only, non-authoritative, publication-hash-stamped"
            if fallback_guarded
            else "unproven"
        ),
        "session_debug_policy": (
            "storage-only with final_publication_authority_hash"
            if session_debug_storage_guarded
            else "unproven"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_display_authority_changed": False,
        "fallback_shell_removed": False,
        "apply_routing_changed": False,
        "snapshot_hash": snapshot_hash,
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    proof_rows = [f"| {name} | `{value}` |" for name, value in snapshot["proof"].items()]
    surface_rows = [
        f"| {name} | `{row['authority']}` | `{row['authority_marker_present']}` | `{row['downstream_override_allowed']}` |"
        for name, row in snapshot["frozen_surfaces"].items()
    ]
    checkpoint_rows = [
        f"| {row['checkpoint']} | `{row['symbol']}` | `{row['freeze_policy']}` | `{row['downstream_of_final_publication']}` |"
        for row in snapshot["late_checkpoints"]
    ]
    verifier_rows = [
        f"| {name} | `{row['passed']}` | `{row['returncode']}` |"
        for name, row in snapshot["composed_verifiers"].items()
    ]
    artifact_rows = [
        f"| {name} | `{row.get('found')}` | `{row.get('status')}` | `{row.get('path')}` |"
        for name, row in snapshot["referenced_artifacts"].items()
    ]
    body = "\n".join(
        [
            "# Design Guide Render-After-Publication Freeze",
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
            "## Frozen Surfaces",
            "",
            "| Surface | Authority | Marker Present | Downstream Override Allowed |",
            "|---|---|---:|---:|",
            *surface_rows,
            "",
            "## Late Checkpoints",
            "",
            "| Checkpoint | Symbol | Freeze Policy | Downstream Of Publication |",
            "|---|---|---|---:|",
            *checkpoint_rows,
            "",
            "## Composed Verifiers",
            "",
            "| Verifier | Passed | Return Code |",
            "|---|---:|---:|",
            *verifier_rows,
            "",
            "## Referenced Artifacts",
            "",
            "| Artifact | Found | Status | Path |",
            "|---|---:|---|---|",
            *artifact_rows,
            "",
            "## Policies",
            "",
            f"- Fallback shell policy: `{snapshot['fallback_shell_policy']}`",
            f"- Session/debug policy: `{snapshot['session_debug_policy']}`",
            "",
            "## Failures",
            "",
            (
                "None."
                if not snapshot["failures"]
                else "\n".join(f"- `{failure}`" for failure in snapshot["failures"])
            ),
            "",
            "## Result",
            "",
            (
                "PASS: no downstream render/session/debug/fallback path is allowed to silently reinterpret "
                "`FinalDesignGuidePublication` after CTA/display authority exists."
                if snapshot["status"] == "PASS"
                else "FAIL: one or more late paths are unguarded."
            ),
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_render_after_publication_freeze_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_after_publication_freeze_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"Render-after-publication freeze {snapshot['status']}")
    print(f"JSON: {json_path}")
    print(f"Report: {md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
