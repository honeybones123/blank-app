"""Focused proof for the shared post-Apply truth and verifier root fixes."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.guidance_result_adapter import (
    build_authoritative_design_result_from_guidance_payload,
)
from design_brain.authority import EngineeringInputSnapshot
from tools.verification.run_family_10_fuzz_audit import (
    _post_apply_green_pass_visual_contract,
    _summary_domain_utils,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"


def main() -> int:
    terminal_result = build_authoritative_design_result_from_guidance_payload(
        engineering_snapshot=EngineeringInputSnapshot(
            geometry={"b": 450.0, "D": 850.0}
        ),
        family_override="SHEAR_FAIL_GOVERNS",
        guidance_payload={
            "guidance_items": [
                {
                    "family": "SHEAR_FAIL_GOVERNS",
                    "selected_family_id": "SHEAR_FAIL_GOVERNS",
                    "status": "PASS",
                    "display_state": "PASS",
                    "button_contract": {
                        "enabled": False,
                        "actionable": False,
                        "updates": {},
                    },
                }
            ],
            "debug_trace": {
                "design_guide_terminal_state": "target_band_reached",
                "target_band_with_eps_passed": True,
                "overview": {
                    "statuses": {"bending": "PASS", "shear": "PASS"},
                    "utils": {"bending": 0.59374, "shear": 0.916894},
                },
            },
        },
    )

    summary_utils = _summary_domain_utils(
        {
            "browser_state": {
                "summary_overview_probe": {
                    "utils": {"bending": 0.59374, "shear": 0.916894}
                }
            },
            "summary_cards": {
                "bending": {"utilisation_text": "0.59"},
                "shear": {"utilisation_text": "0.59"},
            },
        }
    )
    contaminated_green = _post_apply_green_pass_visual_contract(
        {
            "design_guide": {
                "text_sample": (
                    "PASSDesign accepted - target band achieved "
                    "Preview utilisation 0.95 PREVIEW_BLOCKED"
                )
            },
            "checks": {"design_guide_statuses": ["PASS"]},
        }
    )
    clean_green = _post_apply_green_pass_visual_contract(
        {
            "design_guide": {
                "text_sample": (
                    "PASSDesign accepted - target band achieved "
                    "Preview utilisation 0.92"
                )
            },
            "checks": {"design_guide_statuses": ["PASS"]},
        }
    )

    checks = {
        "terminal_current_evidence_outranks_pre_apply_family_pin": (
            terminal_result.governing_family == "TARGET_BAND_REACHED"
        ),
        "authoritative_summary_bending_preserved": (
            summary_utils.get("bending") == 0.59374
        ),
        "authoritative_summary_shear_preserved": (
            summary_utils.get("shear") == 0.916894
        ),
        "stale_preview_blocked_contamination_rejected": (
            contaminated_green.get("blocked_visible") is True
            and contaminated_green.get("passes_contract") is False
        ),
        "concatenated_accepted_pass_card_recognised": (
            clean_green.get("pass_visible") is True
            and clean_green.get("passes_contract") is True
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_brain.post_apply_truth_root_cause_contract.v1",
        "status": status,
        "checks": checks,
        "terminal_governing_family": terminal_result.governing_family,
        "summary_utils": summary_utils,
        "contaminated_green_contract": contaminated_green,
        "clean_green_contract": clean_green,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifact = (
        ARTIFACT_DIR
        / f"design_brain_post_apply_truth_root_cause_contract_{stamp}.json"
    )
    artifact.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(status)
    print(f"artifact={artifact}")
    if status != "PASS":
        print(
            "failures="
            + ",".join(name for name, passed in checks.items() if not passed)
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
