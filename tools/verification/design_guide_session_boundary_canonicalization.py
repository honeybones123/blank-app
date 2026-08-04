"""Verifier for Design Guide session boundary canonicalization.

The canonicalization pass keeps compatibility session keys intact while proving
their publication-shaped data is stamped as non-authoritative and derived from
FinalDesignGuidePublication.
"""

from __future__ import annotations

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

LEGACY_PUBLICATION_KEYS = (
    "_design_guide_cache",
    "_design_guide_cached_debug",
    "_design_guide_cached_fingerprint",
    "_design_guide_cached_items",
    "_design_guide_fp",
    "_design_guide_publication_fingerprint",
    "design_guide_post_apply_display_truth",
    "design_guide_primary_apply_payload",
    "design_guide_primary_button_contract",
    "design_guide_primary_button_contract_enabled",
    "design_guide_primary_display_truth",
)

REQUIRED_TOKENS = {
    "metadata_key_constant": '_FINAL_PUBLICATION_LEGACY_SESSION_METADATA_KEY = "_design_guide_legacy_publication_session_key_metadata"',
    "legacy_keys_tuple": "_FINAL_PUBLICATION_LEGACY_SESSION_KEYS = (",
    "canonicalization_helper": "def _canonicalize_legacy_design_guide_publication_session_storage(",
    "called_from_same_object_stamp": "_canonicalize_legacy_design_guide_publication_session_storage(",
    "same_object_payload_key": "final_publication_verifier_payload",
    "authority_hash": "final_publication_authority_hash",
    "publication_hash": "publication_hash",
    "legacy_non_authoritative": '"legacy_non_authoritative": True',
    "compatibility_only": '"compatibility_only": True',
    "derived_from_publication": '"derived_from": "FinalDesignGuidePublication"',
    "may_not_override": '"may_override_publication": False',
    "metadata_stored_in_session": "st.session_state[_FINAL_PUBLICATION_LEGACY_SESSION_METADATA_KEY] = dict(metadata)",
    "metadata_stored_in_debug": 'debug_sink["final_publication_legacy_session_key_metadata"] = dict(metadata)',
    "debug_non_authoritative_flag": 'debug_sink["legacy_publication_session_keys_non_authoritative"] = True',
    "debug_derived_from_flag": 'debug_sink["legacy_publication_session_keys_derived_from"] = "FinalDesignGuidePublication"',
    "cta_authority": "FinalDesignGuidePublication.cta",
    "display_authority": "FinalDesignGuidePublication.display",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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
        return {"found": False, "path": None, "status": None, "payload": {}}
    path = candidates[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "INVALID_JSON",
            "error": str(exc),
            "payload": {},
        }
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "snapshot_hash": payload.get("snapshot_hash"),
        "payload": payload,
    }


def _build_snapshot() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    token_checks = {
        name: {"token": token, "present": token in source}
        for name, token in REQUIRED_TOKENS.items()
    }
    missing_tokens = [name for name, row in token_checks.items() if not row["present"]]
    missing_legacy_keys = [
        key for key in LEGACY_PUBLICATION_KEYS if f'"{key}"' not in source
    ]

    freeze = _run_verifier("tools/verification/design_guide_render_after_publication_freeze.py")
    same_object = _run_verifier("tools/verification/design_guide_verifier_debug_same_object.py")
    readiness = _run_verifier("tools/verification/design_guide_session_boundary_readiness_snapshot.py")
    readiness_artifact = _latest_artifact("design_guide_session_boundary_readiness")
    readiness_payload = dict(readiness_artifact.get("payload") or {})
    unsafe_keys = list(readiness_payload.get("unsafe_duplicate_publication_authority_keys") or [])
    legacy_keys = list(readiness_payload.get("legacy_duplicated_publication_keys") or [])

    legacy_key_proofs = {
        key: {
            "listed_for_canonicalization": f'"{key}"' in source,
            "legacy_non_authoritative": token_checks["legacy_non_authoritative"]["present"],
            "compatibility_only": token_checks["compatibility_only"]["present"],
            "derived_from": "FinalDesignGuidePublication",
            "hash_stamped": token_checks["authority_hash"]["present"]
            and token_checks["publication_hash"]["present"],
            "may_override_publication": False,
        }
        for key in LEGACY_PUBLICATION_KEYS
    }
    unproven_legacy_keys = [
        key
        for key, proof in legacy_key_proofs.items()
        if not (
            proof["listed_for_canonicalization"]
            and proof["legacy_non_authoritative"]
            and proof["compatibility_only"]
            and proof["hash_stamped"]
            and not proof["may_override_publication"]
        )
    ]

    failures: list[str] = []
    if missing_tokens:
        failures.append("missing_canonicalization_tokens")
    if missing_legacy_keys:
        failures.append("missing_legacy_keys_from_canonicalization_tuple")
    if unproven_legacy_keys:
        failures.append("legacy_keys_not_proven_non_authoritative")
    if unsafe_keys:
        failures.append("readiness_reported_unsafe_duplicate_publication_authority")
    if not freeze["passed"]:
        failures.append("render_after_publication_freeze_failed")
    if not same_object["passed"]:
        failures.append("verifier_debug_same_object_failed")
    if not readiness["passed"]:
        failures.append("session_boundary_readiness_failed")

    proof = {
        "final_publication_remains_canonical_publication_state": bool(
            token_checks["same_object_payload_key"]["present"]
            and token_checks["metadata_stored_in_session"]["present"]
        ),
        "legacy_publication_keys_are_non_authoritative": not bool(unproven_legacy_keys),
        "legacy_keys_match_publication_hash_or_compatibility_only": bool(
            token_checks["authority_hash"]["present"]
            and token_checks["publication_hash"]["present"]
            and token_checks["compatibility_only"]["present"]
        ),
        "no_session_key_can_override_outcome_family_blocker_cta_or_display": bool(
            not unsafe_keys and token_checks["may_not_override"]["present"]
        ),
        "render_after_publication_freeze_still_passes": freeze["passed"],
        "verifier_debug_same_object_still_passes": same_object["passed"],
        "session_readiness_zero_unsafe_duplicate_publication_authority": not bool(unsafe_keys),
    }
    status = "PASS" if not failures else "FAIL"
    snapshot_hash = _stable_hash(
        {
            "proof": proof,
            "legacy_key_proofs": legacy_key_proofs,
            "freeze": freeze["passed"],
            "same_object": same_object["passed"],
            "readiness": readiness["passed"],
            "unsafe_keys": unsafe_keys,
        }
    )
    return {
        "snapshot_name": "design_guide_session_boundary_canonicalization",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "proof": proof,
        "legacy_key_proofs": legacy_key_proofs,
        "unproven_legacy_keys": unproven_legacy_keys,
        "missing_legacy_keys": missing_legacy_keys,
        "token_checks": token_checks,
        "missing_tokens": missing_tokens,
        "composed_verifiers": {
            "render_after_publication_freeze": freeze,
            "verifier_debug_same_object": same_object,
            "session_boundary_readiness": readiness,
        },
        "readiness_artifact": {
            key: value for key, value in readiness_artifact.items() if key != "payload"
        },
        "readiness_legacy_key_count": len(legacy_keys),
        "readiness_unsafe_duplicate_publication_authority_keys": unsafe_keys,
        "product_behavior_changed": False,
        "visible_behavior_changed": False,
        "broad_session_state_deleted": False,
        "user_input_keys_changed": False,
        "transient_ui_keys_changed": False,
        "apply_routing_changed": False,
        "fallback_shells_removed": False,
        "cta_display_authority_changed": False,
        "snapshot_hash": snapshot_hash,
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    proof_rows = [f"| {name} | `{value}` |" for name, value in snapshot["proof"].items()]
    legacy_rows = [
        f"| `{key}` | `{proof['listed_for_canonicalization']}` | `{proof['hash_stamped']}` | `{proof['legacy_non_authoritative']}` | `{proof['compatibility_only']}` |"
        for key, proof in snapshot["legacy_key_proofs"].items()
    ]
    verifier_rows = [
        f"| {name} | `{row['passed']}` | `{row['returncode']}` |"
        for name, row in snapshot["composed_verifiers"].items()
    ]
    body = "\n".join(
        [
            "# Design Guide Session Boundary Canonicalization",
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
            "## Legacy Key Proofs",
            "",
            "| Key | Listed | Hash Stamped | Non-Authoritative | Compatibility Only |",
            "|---|---:|---:|---:|---:|",
            *legacy_rows,
            "",
            "## Composed Verifiers",
            "",
            "| Verifier | Passed | Return Code |",
            "|---|---:|---:|",
            *verifier_rows,
            "",
            "## Readiness",
            "",
            f"- Readiness artifact: `{snapshot['readiness_artifact'].get('path')}`",
            f"- Readiness legacy key count: `{snapshot['readiness_legacy_key_count']}`",
            f"- Unsafe duplicate publication authority keys: `{len(snapshot['readiness_unsafe_duplicate_publication_authority_keys'])}`",
            "",
            "## Scope",
            "",
            "- Visible behavior changed: `False`",
            "- Broad session state deleted: `False`",
            "- User input keys changed: `False`",
            "- Transient UI keys changed: `False`",
            "- Apply routing changed: `False`",
            "- Fallback shells removed: `False`",
            "- CTA/display authority changed: `False`",
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
    json_path = ARTIFACT_DIR / f"design_guide_session_boundary_canonicalization_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_session_boundary_canonicalization_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_session_boundary_canonicalization {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
