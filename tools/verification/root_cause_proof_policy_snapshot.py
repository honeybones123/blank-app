"""Verify the root-cause proof rule itself.

This is a policy self-check, not a claim that any product bug is fixed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from root_cause_proof import (
    REQUIRED_ROOT_CAUSE_FIELDS,
    RootCauseProof,
    patch_may_proceed,
    validate_root_cause_proof,
)


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"


def _proof(*, complete: bool) -> RootCauseProof:
    return RootCauseProof(
        issue_id="duplicate_cta",
        reproduction_id="live_recipe_bending_fail_01",
        reproduction_recipe="Apply once, wait for settled publication, inspect visible widgets",
        source_hash="source-sha256",
        verification_run_id="run-root-cause-policy",
        production_path=("page_route", "design_guide_panel", "cta_renderer"),
        exact_callsites=("inputs_application/page_runtime/design_guide.py:438",),
        branch_conditions=("parent_fragment_active=True", "ACTION publication",),
        input_fingerprint="input-fingerprint",
        first_divergence=("cta_renderer_invoked_twice_in_one_render_epoch" if complete else "symptom_only"),
        output_fingerprint_before="one-button",
        output_fingerprint_after=("two-buttons" if complete else "one-button"),
        downstream_effect="duplicate Streamlit widget key / second visible Apply button",
        alternatives_checked=(
            "duplicate publication",
            "duplicate card render",
            "nested fragment invocation",
            "post-Apply stale session payload",
        ),
        confidence=("confirmed" if complete else "suspected"),
        patch_authorized=complete,
    )


def main() -> int:
    incomplete = _proof(complete=False)
    complete = _proof(complete=True)
    incomplete_defects = validate_root_cause_proof(incomplete)
    complete_defects = validate_root_cause_proof(complete)
    status = "PASS" if incomplete_defects and not complete_defects and patch_may_proceed(complete) else "FAIL"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    payload = {
        "schema": "root_cause_proof_policy_snapshot.v1",
        "status": status,
        "rule": "no behavioral patch without complete root-cause proof",
        "incomplete_proof_rejected": bool(incomplete_defects),
        "incomplete_defects": list(incomplete_defects),
        "complete_proof_accepted": not complete_defects and patch_may_proceed(complete),
        "required_fields": list(REQUIRED_ROOT_CAUSE_FIELDS),
        "complete_proof": complete.as_dict(),
    }
    out = ARTIFACTS / "verification" / f"root_cause_proof_policy_snapshot_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    audit = ARTIFACTS / "audits" / f"root_cause_proof_policy_snapshot_{stamp}.md"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(
        "# Root Cause Proof Policy Snapshot\n\n"
        f"Status: **{status}**\n\n"
        "A behavioral patch is permitted only after the same-run proof identifies "
        "the exact production callsite, executed branch, first divergence, state "
        "fingerprints, downstream effect, and checked alternatives.\n",
        encoding="utf-8",
    )
    print(f"root cause proof policy {status}")
    print(f"json={out}")
    print(f"report={audit}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
