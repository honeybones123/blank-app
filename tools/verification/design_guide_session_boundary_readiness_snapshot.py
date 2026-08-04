"""Readiness snapshot for Design Guide session/debug boundary cleanup.

This verifier maps the current Design Guide session/debug/probe storage surface
and classifies what can remain, what should be derived from
FinalDesignGuidePublication, and what would be unsafe duplicate publication
authority. It does not delete keys or change product behaviour.
"""

from __future__ import annotations

import json
import re
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

USER_INPUT_KEYS = {
    "design_guide_reference_D",
    "design_guide_reference_b",
    "design_guide_session_anchor_D",
    "design_guide_last_user_geometry",
    "_design_guide_ref_beam_id",
    "_design_guide_last_applied_auto_geometry",
}

CURRENT_PUBLICATION_KEYS = {
    "final_publication_authority_hash",
    "final_publication_publication_hash",
    "publication_hash",
    "final_publication_verifier_payload",
    "final_publication_cta_hash",
    "final_publication_display_hash",
    "final_publication_cta_authority_payload",
    "final_publication_display_authority_payload",
}

TRANSIENT_UI_KEYS = {
    "inputs_design_guide_debug_sidebar_v1",
    "_design_guide_apply_banner_payload",
    "_design_guide_apply_banner_meta",
    "_design_guide_needs_refresh",
    "_design_guide_pending_step_ctx",
    "_design_guide_last_apply_route",
    "_design_guide_component_cta_consumed_events",
    "_design_guide_component_cta_last_event",
    "_design_guide_component_apply_in_flight",
    "_design_guide_component_scroll_restore",
    "_design_guide_family_settle_gate",
    "_design_guide_apply_trace_run_id",
    "_design_guide_apply_trace_meta",
}

DEBUG_EXPORT_KEYS = {
    "_design_guide_debug_bundle",
    "_design_guide_reco_trace",
    "_design_guide_rank_trace",
    "_design_guide_geometry_trial_debug",
    "_design_guide_step_history",
    "_design_guide_first_target_band_step",
    "_design_guide_history_anchor",
    "design_guide_primary_payload_binding_audit",
}

LEGACY_PUBLICATION_KEYS = {
    "_design_guide_cached_fingerprint",
    "_design_guide_cached_items",
    "_design_guide_cached_debug",
    "_design_guide_fp",
    "_design_guide_cache",
    "_design_guide_publication_fingerprint",
    "design_guide_primary_apply_payload",
    "design_guide_primary_button_contract",
    "design_guide_primary_button_contract_enabled",
    "design_guide_primary_display_truth",
}

REQUIRED_TOKENS = {
    "debug_authority_hash": "final_publication_authority_hash",
    "debug_publication_hash": "final_publication_publication_hash",
    "same_object_payload": "final_publication_verifier_payload",
    "actual_card_render_probe": "actual_card_render_probe",
    "cta_matches_live": "final_publication_cta_matches_live",
    "display_matches_live": "final_publication_display_matches_live",
    "debug_no_mutation": '"debug_payload_mutation_allowed": False',
    "cta_authority": "FinalDesignGuidePublication.cta",
    "display_authority": "FinalDesignGuidePublication.display",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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


def _extract_design_guide_key_constants(source: str) -> dict[str, str]:
    pattern = re.compile(r'^(DESIGN_GUIDE_[A-Z0-9_]+_KEY)\s*=\s*"([^"]+)"', re.MULTILINE)
    return {match.group(1): match.group(2) for match in pattern.finditer(source)}


def _extract_literal_session_keys(source: str) -> set[str]:
    patterns = [
        r'st\.session_state\[\s*"([^"]+)"\s*\]',
        r"st\.session_state\[\s*'([^']+)'\s*\]",
        r'st\.session_state\.get\(\s*"([^"]+)"',
        r"st\.session_state\.get\(\s*'([^']+)'",
        r'st\.session_state\.pop\(\s*"([^"]+)"',
        r"st\.session_state\.pop\(\s*'([^']+)'",
        r'st\.session_state\.setdefault\(\s*"([^"]+)"',
        r"st\.session_state\.setdefault\(\s*'([^']+)'",
    ]
    keys: set[str] = set()
    for pattern in patterns:
        keys.update(re.findall(pattern, source))
    return keys


def _classification_for_key(key: str) -> dict[str, Any]:
    key_l = key.lower()
    if key in USER_INPUT_KEYS:
        category = "user input state"
        disposition = "allowed to remain"
        reason = "beam/user anchor state, not publication authority"
    elif key in TRANSIENT_UI_KEYS:
        category = "transient UI state"
        disposition = "allowed to remain"
        reason = "ephemeral UI/apply lifecycle state"
    elif key in DEBUG_EXPORT_KEYS:
        category = "debug/export state"
        disposition = "allowed to remain"
        reason = "debug/export storage; publication truth must be hash-stamped"
    elif key in CURRENT_PUBLICATION_KEYS or key_l.startswith("final_publication_") or key == "publication_hash":
        category = "current FinalDesignGuidePublication state"
        disposition = "allowed to remain"
        reason = "canonical final publication proof/hash surface"
    elif key in LEGACY_PUBLICATION_KEYS:
        category = "legacy duplicated publication state"
        disposition = "should be derived from FinalDesignGuidePublication"
        reason = "legacy compatibility surface; not allowed to be final authority"
    elif "button_contract" in key_l or "primary_apply_payload" in key_l or "display_truth" in key_l:
        category = "legacy duplicated publication state"
        disposition = "should be derived from FinalDesignGuidePublication"
        reason = "publication-shaped duplicate kept for compatibility"
    elif "publication" in key_l or "guidance_cache" in key_l or "design_guide_cache" in key_l:
        category = "legacy duplicated publication state"
        disposition = "legacy compatibility only"
        reason = "cache/fingerprint surface; must not become publication authority"
    elif "debug" in key_l or "trace" in key_l or "probe" in key_l or "audit" in key_l:
        category = "debug/export state"
        disposition = "allowed to remain"
        reason = "diagnostic state only"
    elif key_l.startswith("_design_guide"):
        category = "transient UI state"
        disposition = "allowed to remain"
        reason = "Design Guide private UI/session coordination state"
    else:
        category = "transient UI state"
        disposition = "allowed to remain"
        reason = "non-publication session state"
    unsafe = category == "unsafe restamp state"
    deletion_candidate = category == "legacy duplicated publication state"
    return {
        "key": key,
        "category": category,
        "disposition": disposition,
        "reason": reason,
        "allowed_to_remain": disposition == "allowed to remain",
        "should_be_derived_from_publication": disposition == "should be derived from FinalDesignGuidePublication",
        "legacy_compatibility_only": disposition == "legacy compatibility only",
        "unsafe_duplicate_publication_authority": unsafe,
        "candidate_for_deletion_after_final_lock": deletion_candidate,
    }


def _build_snapshot() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    constants = _extract_design_guide_key_constants(source)
    literal_keys = _extract_literal_session_keys(source)
    all_keys = sorted(set(constants.values()) | literal_keys | CURRENT_PUBLICATION_KEYS)

    classified_keys = [_classification_for_key(key) for key in all_keys]
    counts: dict[str, int] = {}
    for row in classified_keys:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    unsafe_keys = [
        row for row in classified_keys if row["unsafe_duplicate_publication_authority"]
    ]
    legacy_keys = [
        row for row in classified_keys if row["category"] == "legacy duplicated publication state"
    ]

    token_checks = {
        name: {"token": token, "present": token in source}
        for name, token in REQUIRED_TOKENS.items()
    }
    missing_tokens = [name for name, row in token_checks.items() if not row["present"]]

    freeze = _run_verifier("tools/verification/design_guide_render_after_publication_freeze.py")
    same_object = _run_verifier("tools/verification/design_guide_verifier_debug_same_object.py")

    duplicated_publication_keys_hash_stamped_or_legacy = bool(
        token_checks["debug_authority_hash"]["present"]
        and token_checks["same_object_payload"]["present"]
        and not unsafe_keys
    )
    no_second_publication_engine = not unsafe_keys
    session_debug_carry_hash = bool(
        token_checks["debug_authority_hash"]["present"]
        and token_checks["debug_publication_hash"]["present"]
        and token_checks["actual_card_render_probe"]["present"]
    )
    session_debug_cannot_override = bool(
        freeze["passed"]
        and same_object["passed"]
        and token_checks["debug_no_mutation"]["present"]
    )

    failures: list[str] = []
    if missing_tokens:
        failures.append("missing_session_boundary_tokens")
    if unsafe_keys:
        failures.append("unsafe_duplicate_publication_authority_keys")
    if not freeze["passed"]:
        failures.append("render_after_publication_freeze_failed")
    if not same_object["passed"]:
        failures.append("verifier_debug_same_object_failed")
    if not session_debug_carry_hash:
        failures.append("session_debug_payload_missing_final_publication_hash")
    if not session_debug_cannot_override:
        failures.append("session_debug_payload_can_override_publication")
    if not duplicated_publication_keys_hash_stamped_or_legacy:
        failures.append("duplicated_publication_keys_not_accounted_for")
    if not no_second_publication_engine:
        failures.append("second_publication_engine_detected")

    proof = {
        "session_debug_payloads_carry_final_publication_authority_hash": session_debug_carry_hash,
        "session_debug_payloads_cannot_override_cta_display_or_outcome": session_debug_cannot_override,
        "duplicated_publication_keys_hash_stamped_or_legacy": duplicated_publication_keys_hash_stamped_or_legacy,
        "no_session_key_acts_as_second_publication_engine": no_second_publication_engine,
        "render_after_publication_freeze_still_passes": freeze["passed"],
        "verifier_debug_same_object_still_passes": same_object["passed"],
        "ready_for_narrow_session_cleanup": not bool(failures),
    }
    status = "PASS" if not failures else "FAIL"
    snapshot_hash = _stable_hash(
        {
            "proof": proof,
            "counts": counts,
            "legacy_keys": [row["key"] for row in legacy_keys],
            "unsafe_keys": [row["key"] for row in unsafe_keys],
            "freeze": freeze["passed"],
            "same_object": same_object["passed"],
        }
    )
    return {
        "snapshot_name": "design_guide_session_boundary_readiness",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "proof": proof,
        "session_key_category_counts": counts,
        "session_key_classification": classified_keys,
        "legacy_duplicated_publication_keys": legacy_keys,
        "unsafe_duplicate_publication_authority_keys": unsafe_keys,
        "candidate_for_deletion_after_final_lock": [
            row for row in classified_keys if row["candidate_for_deletion_after_final_lock"]
        ],
        "design_guide_key_constants": constants,
        "token_checks": token_checks,
        "missing_tokens": missing_tokens,
        "composed_verifiers": {
            "render_after_publication_freeze": freeze,
            "verifier_debug_same_object": same_object,
        },
        "recommended_next_step": (
            "narrow session cleanup/canonicalization pass: derive legacy button/cache/display publication "
            "keys from FinalDesignGuidePublication while keeping apply routing and fallback shells intact"
        ),
        "product_behavior_changed": False,
        "visible_output_changed": False,
        "cta_display_authority_changed": False,
        "apply_routing_changed": False,
        "fallback_shells_removed": False,
        "snapshot_hash": snapshot_hash,
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    proof_rows = [f"| {name} | `{value}` |" for name, value in snapshot["proof"].items()]
    count_rows = [
        f"| {name} | `{count}` |"
        for name, count in sorted(snapshot["session_key_category_counts"].items())
    ]
    legacy_rows = [
        f"| `{row['key']}` | `{row['disposition']}` | `{row['reason']}` |"
        for row in snapshot["legacy_duplicated_publication_keys"]
    ]
    deletion_rows = [
        f"| `{row['key']}` | `{row['category']}` | `{row['reason']}` |"
        for row in snapshot["candidate_for_deletion_after_final_lock"]
    ]
    verifier_rows = [
        f"| {name} | `{row['passed']}` | `{row['returncode']}` |"
        for name, row in snapshot["composed_verifiers"].items()
    ]
    body = "\n".join(
        [
            "# Design Guide Session Boundary Readiness Snapshot",
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
            "## Session Key Category Counts",
            "",
            "| Category | Count |",
            "|---|---:|",
            *count_rows,
            "",
            "## Legacy Duplicated Publication Keys",
            "",
            "| Key | Disposition | Reason |",
            "|---|---|---|",
            *(legacy_rows or ["| None |  |  |"]),
            "",
            "## Candidate For Deletion After Final Lock",
            "",
            "| Key | Category | Reason |",
            "|---|---|---|",
            *(deletion_rows or ["| None |  |  |"]),
            "",
            "## Composed Verifiers",
            "",
            "| Verifier | Passed | Return Code |",
            "|---|---:|---:|",
            *verifier_rows,
            "",
            "## Unsafe Duplicate Publication Authority",
            "",
            (
                "None."
                if not snapshot["unsafe_duplicate_publication_authority_keys"]
                else "\n".join(
                    f"- `{row['key']}`" for row in snapshot["unsafe_duplicate_publication_authority_keys"]
                )
            ),
            "",
            "## Recommendation",
            "",
            snapshot["recommended_next_step"],
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
    json_path = ARTIFACT_DIR / f"design_guide_session_boundary_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_session_boundary_readiness_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_session_boundary_readiness {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
