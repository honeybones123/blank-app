"""Lock the fragment-fresh browser Apply projection to typed authority."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.authority import (  # noqa: E402
    EngineeringInputSnapshot,
    build_authoritative_design_result,
)
from inputs_application.engineering_workspace import (  # noqa: E402
    _authoritative_apply_browser_projection,
)


def main() -> int:
    updates = {"b": 375.0, "lig_d": 0, "lig_legs": 0, "s_lig": 0}
    candidate_id = "candidate_002"
    family = "SHEAR_OVERDESIGN_GOVERNS"
    apply_payload = {
        "action_type": "apply_resolved_candidate",
        "resolved_candidate_action_type": "apply_resolved_candidate",
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "family": family,
        "updates": dict(updates),
        "resolved_candidate_updates": dict(updates),
        "state_fingerprint": "state-1",
        "render_fingerprint": "render-1",
    }
    cta_model = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": family,
        "source_candidate_id": candidate_id,
        "updates": dict(updates),
    }
    result = build_authoritative_design_result(
        engineering_snapshot=EngineeringInputSnapshot(
            geometry={"b": 400.0, "D": 450.0}
        ),
        governing_family=family,
        selected_candidate={
            "candidate_id": candidate_id,
            "family": family,
            "updates": dict(updates),
        },
        selected_updates=dict(updates),
        cta_model=cta_model,
        apply_payload=apply_payload,
    )
    projection = _authoritative_apply_browser_projection(result)
    payload = dict(
        projection.get("design_guide_primary_apply_payload") or {}
    )
    audit = dict(
        projection.get("design_guide_primary_payload_binding_audit") or {}
    )
    checks = {
        "selected_updates_preserved": (
            projection.get("selected_action_updates") == updates
        ),
        "apply_payload_preserved": payload == result.apply_payload,
        "payload_updates_match": payload.get("updates") == updates,
        "candidate_identity_matches": (
            payload.get("candidate_id") == candidate_id
            and audit.get("visible_primary_candidate_id") == candidate_id
            and audit.get("button_contract_candidate_id") == candidate_id
        ),
        "family_identity_matches": (
            projection.get("selected_action_family") == family
        ),
        "action_type_matches": (
            projection.get("selected_action_type")
            == "apply_resolved_candidate"
        ),
        "binding_is_canonical": (
            audit.get("payload_binding_match") is True
            and audit.get("payload_update_match") is True
            and audit.get("canonical_primary_payload_exists") is True
            and audit.get("legacy_fallback_used") is False
        ),
        "authority_hash_bound": (
            audit.get("authoritative_publication_hash")
            == result.publication_authority_hash
        ),
        "empty_result_is_non_actionable": not any(
            _authoritative_apply_browser_projection(None).values()
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    artifact_dir = ROOT / "artifacts" / "verification"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / (
        "inputs_fragment_authoritative_apply_projection_contract_"
        f"{time.strftime('%Y-%m-%dT%H-%M-%S')}.json"
    )
    artifact.write_text(
        json.dumps(
            {
                "schema": (
                    "inputs_fragment_authoritative_apply_projection_contract.v1"
                ),
                "status": status,
                "checks": checks,
                "projection": projection,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"status": status, "artifact": str(artifact), "checks": checks},
            indent=2,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
