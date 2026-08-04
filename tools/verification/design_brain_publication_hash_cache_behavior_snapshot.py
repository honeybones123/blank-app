"""Behavioral proof for session-owned publication hash/cache reuse."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.design_run_coordinator import ensure_design_result
from application.design_result_store import AuthoritativeDesignResultStore
from design_brain.authority import (
    EngineeringInputSnapshot,
    build_authoritative_design_result,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _snapshot(depth: int) -> EngineeringInputSnapshot:
    return EngineeringInputSnapshot(
        geometry={"width": 350.0, "depth": float(depth)},
        materials={"fc": 40.0, "fsy": 500.0},
        reinforcement={"bottom_bars": 4, "bottom_dia": 28},
        design_actions={"moment": 100.0, "shear": 200.0},
        design_settings={"goal": "balanced"},
        contract_versions={"family": "current"},
        calculation_versions={"solver": "current"},
    )


def _compute_factory(calls: list[str]):
    def compute(snapshot: EngineeringInputSnapshot):
        calls.append(snapshot.engineering_hash)
        publication = {
            "engineering_hash": snapshot.engineering_hash,
            "selected_identity": "candidate-cache-proof",
            "updates": {"depth": snapshot.geometry["depth"]},
        }
        return build_authoritative_design_result(
            engineering_snapshot=snapshot,
            current_calculations={"governing_util": 0.92},
            governing_family="BENDING_OVERDESIGN_GOVERNS",
            family_outcome="ACTION",
            selected_candidate={"identity": "candidate-cache-proof"},
            selected_updates=dict(publication["updates"]),
            final_publication=publication,
            display_model={"status": "ACTION"},
            cta_model={"action_type": "apply_resolved_candidate", "updates": dict(publication["updates"])},
            apply_payload={"action_type": "apply_resolved_candidate", "updates": dict(publication["updates"])},
        )

    return compute


def _main() -> tuple[dict[str, Any], int]:
    session: dict[str, Any] = {"active_tab": "Inputs"}
    calls: list[str] = []
    compute = _compute_factory(calls)
    snapshot_a = _snapshot(500)
    snapshot_b = _snapshot(420)
    snapshot_a_before = snapshot_a.to_dict()

    first = ensure_design_result(session_state=session, snapshot=snapshot_a, compute_fn=compute)
    first_calls = len(calls)

    session["active_tab"] = "Calculations"
    reused = ensure_design_result(session_state=session, snapshot=snapshot_a, compute_fn=compute)
    unchanged_input_reused_exact_result = reused is first and len(calls) == first_calls

    changed = ensure_design_result(session_state=session, snapshot=snapshot_b, compute_fn=compute)
    changed_decision = dict(session.get("_authoritative_design_result_last_decision") or {})
    changed_input_invalidated_result = (
        changed is not first
        and changed.engineering_hash != first.engineering_hash
        and changed_decision.get("reason") == "engineering_hash_changed"
        and len(calls) == first_calls + 1
    )
    stale_publication_replaced = (
        changed.final_publication.get("engineering_hash") == snapshot_b.engineering_hash
        and changed.publication_authority_hash != first.publication_authority_hash
        and AuthoritativeDesignResultStore(session).current() is changed
    )
    input_snapshot_unchanged = snapshot_a.to_dict() == snapshot_a_before

    deterministic_peer = _compute_factory([])(snapshot_a)
    publication_hash_deterministic = (
        deterministic_peer.publication_authority_hash == first.publication_authority_hash
    )

    checks = {
        "unchanged_inputs_reuse_exact_result": unchanged_input_reused_exact_result,
        "changed_inputs_force_new_compute": changed_input_invalidated_result,
        "stale_publication_replaced_after_change": stale_publication_replaced,
        "publication_authority_hash_deterministic": publication_hash_deterministic,
        "engineering_snapshot_not_mutated": input_snapshot_unchanged,
        "ui_only_session_change_does_not_invalidate": reused is first,
    }
    failures = [key for key, passed in checks.items() if not passed]
    payload = {
        "schema": "design_brain_publication_hash_cache_behavior_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "compute_call_count": len(calls),
        "engineering_hashes": {
            "unchanged": snapshot_a.engineering_hash,
            "changed": snapshot_b.engineering_hash,
        },
        "publication_authority_hashes": {
            "unchanged": first.publication_authority_hash,
            "changed": changed.publication_authority_hash,
        },
        "product_behaviour_changed": False,
    }
    return payload, 0 if not failures else 1


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload, code = _main()
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_brain_publication_hash_cache_behavior_snapshot_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_publication_hash_cache_behavior_snapshot_{stamp}.md"
    payload["artifact"] = str(artifact_path)
    payload["report"] = str(report_path)
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Publication Hash / Cache Behavior Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in payload["checks"].items())
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    lines.extend(["", f"JSON: `{artifact_path}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"design_brain_publication_hash_cache_behavior_snapshot {payload['status']}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
