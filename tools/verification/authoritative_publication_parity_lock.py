"""Verify the application-owned publication handoff before bridge removal."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.engineering_snapshot import build_engineering_input_snapshot_from_resolved_state
from application.guidance_result_adapter import build_authoritative_design_result_from_guidance_payload
from inputs_page_modules.design_guide import current_coordinators as current


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _sample_payload() -> dict:
    updates = {"bot1_count": 5}
    return {
        "guidance_items": [
            {
                "published_item_id": "candidate-a",
                "candidate_id": "candidate-a",
                "family": "BENDING_OVERDESIGN_GOVERNS",
                "status": "ACTION",
                "bucket": "action",
                "title_main": "Reduce bottom reinforcement",
                "summary_line": "The selected reinforcement is above the efficient target band.",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "label": "Apply recommendation",
                    "action_type": "reduce_bottom_reinforcement",
                    "family": "BENDING_OVERDESIGN_GOVERNS",
                    "candidate_id": "candidate-a",
                    "source_candidate_id": "candidate-a",
                    "updates": updates,
                    "preview_pass": True,
                },
                "action_payload": {
                    "candidate_id": "candidate-a",
                    "source_candidate_id": "candidate-a",
                    "family": "BENDING_OVERDESIGN_GOVERNS",
                    "action_type": "reduce_bottom_reinforcement",
                    "updates": updates,
                },
                "resolved_candidate": {
                    "candidate_id": "candidate-a",
                    "source_candidate_id": "candidate-a",
                    "family": "BENDING_OVERDESIGN_GOVERNS",
                    "updates": updates,
                },
            }
        ],
        "debug_trace": {
            "governing_family": "BENDING_OVERDESIGN_GOVERNS",
            "family_contract_version": "v1",
            "guidance_branch": "action",
            "overview": {
                "all_key_pass": True,
                "worst_util": 0.82,
                "utils": {
                    "bending": 0.82,
                    "shear": 0.54,
                    "crack": 0.61,
                    "deflection": 0.73,
                },
            },
            "candidate_acceptance_proof": {"accepted": True},
            "candidate_search_evidence": {"selected_candidate_id": "candidate-a"},
        },
    }


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_engineering_input_snapshot_from_resolved_state(
        {"b": 300, "D": 400, "bot1_count": 4, "Mu_star": 300},
        contract_versions={"design_guide": "v1"},
        calculation_versions={"summary_resolver": "v1"},
    )
    result = build_authoritative_design_result_from_guidance_payload(
        engineering_snapshot=snapshot,
        guidance_payload=_sample_payload(),
    )
    canonical = dict(result.final_publication.get("final_design_guide_publication") or {})

    # The authoritative branch must not call the old render-stage builder.
    current._bind_design_guide_current_globals = lambda: None
    current.build_final_design_guide_publication = lambda **_: (_ for _ in ()).throw(
        AssertionError("legacy render publication builder was called")
    )
    projection = current._final_publication_debug_projection(
        item={"title_main": "compatibility item"},
        debug={
            "authoritative_final_design_guide_publication": canonical,
            "authoritative_final_publication_verifier_payload": dict(
                result.final_publication.get("final_publication_verifier_payload") or {}
            ),
        },
        publication_reason="parity_lock",
    )

    projection_publication = dict(projection.get("final_design_guide_publication") or {})
    projection_cta = dict(projection_publication.get("cta") or {})
    projection_display = dict(projection_publication.get("display") or {})
    canonical_cta = dict(canonical.get("cta") or {})
    canonical_display = dict(canonical.get("display") or {})
    canonical_sections = dict(canonical_display.get("expanded_evidence_sections") or {})
    canonical_current_rows = list(canonical_sections.get("current") or [])
    canonical_preview_rows = list(canonical_sections.get("preview_display_rows") or [])
    canonical_updates = dict(canonical_cta.get("apply_payload_summary") or {}).get("updates") or {}
    checks = {
        "canonical_publication_present": bool(canonical.get("publication_hash")),
        "overview_utils_project_to_four_current_rows": len(canonical_current_rows) == 4,
        "overview_utils_project_to_preview_rows": len(canonical_preview_rows) == 4,
        "result_cta_matches_publication": result.cta_model == canonical_cta,
        "result_display_matches_publication": result.display_model == canonical_display,
        "result_apply_updates_match_cta": dict(result.apply_payload.get("updates") or {}) == dict(canonical_updates),
        "renderer_used_authoritative_branch": projection.get("publication_source") == "authoritative_design_result",
        "renderer_publication_hash_matches": projection_publication.get("publication_hash") == canonical.get("publication_hash"),
        "renderer_cta_matches": projection_cta == canonical_cta,
        "renderer_display_matches": projection_display == canonical_display,
        "legacy_builder_not_called": True,
    }
    status = "LOCKED" if all(checks.values()) else "FAIL"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact = ARTIFACT_DIR / f"authoritative_publication_parity_lock_{stamp}.json"
    report = AUDIT_DIR / f"authoritative_publication_parity_lock_{stamp}.md"
    payload = {
        "schema": "authoritative_publication_parity_lock.v1",
        "status": status,
        "checks": checks,
        "canonical_publication_hash": canonical.get("publication_hash"),
        "projection_publication_hash": projection_publication.get("publication_hash"),
    }
    artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text(
        "\n".join(
            [
                "# Authoritative Publication Parity Lock",
                "",
                f"Status: `{status}`",
                "",
                "The application adapter builds the canonical publication before render. The render projection was tested with the legacy publication builder disabled and had to consume the authoritative publication unchanged.",
                "",
                *[f"- `{key}`: `{value}`" for key, value in checks.items()],
                "",
                f"Canonical publication hash: `{canonical.get('publication_hash')}`",
                f"Projection publication hash: `{projection_publication.get('publication_hash')}`",
                "",
                f"JSON: `{artifact.relative_to(ROOT)}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "artifact": str(artifact), "report": str(report)}, indent=2))
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
