"""Focused family contract compliance verifier for COMBINED_OVERDESIGN."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.final_design_guide_formatter import build_final_design_guide_card_format  # noqa: E402
from design_brain.final_design_guide_formatting_contract import status_colour_contract  # noqa: E402
from design_brain.final_publication import (  # noqa: E402
    FinalDesignGuideCTA,
    FinalDesignGuideDisplay,
    FinalDesignGuideEvidence,
    FinalDesignGuidePublication,
    FinalDesignGuideVerifierPayload,
)


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest(prefix: str) -> Path:
    candidates = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(prefix)
    return candidates[0]


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    json_path = ARTIFACT_DIR / f"design_brain_family_contract_compliance_combined_overdesign_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_family_contract_compliance_combined_overdesign_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(md_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# COMBINED_OVERDESIGN Family Contract Compliance",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in snapshot["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    lock_run = _run("tools/verification/families/combined_overdesign_governs_lock_verifier.py")
    publication_run = _run("tools/verification/design_guide_combined_zero_shear_cleanup_publication_snapshot.py")
    tone_run = _run("tools/verification/design_guide_display_tone_contract_snapshot.py")
    object_run = _run("tools/verification/design_guide_final_publication_object_snapshot.py")
    proof_chain = [lock_run, publication_run, tone_run, object_run]

    lock_artifact = _latest("combined_overdesign_governs_lock_verifier")
    lock_payload = _read_json(lock_artifact)
    publication_artifact = _latest("design_guide_combined_zero_shear_cleanup_publication")
    publication_payload = _read_json(publication_artifact)

    publication = FinalDesignGuidePublication(
        published_item_id="combined_overdesign_case",
        selected_family="COMBINED_OVERDESIGN",
        outcome_state="ACTION",
        post_click_design_guide_state="combined_overdesign_cleanup",
        publication_reason="The design is safe and a combined cleanup candidate can reduce unnecessary reinforcement.",
        blocker_reason="",
        exact_stop_proof={},
        target_band_proof={"target_band": "0.85-1.00"},
        cta=FinalDesignGuideCTA(
            enabled=True,
            actionable=True,
            label="Apply cleanup",
            action_type="apply_resolved_candidate",
            family="COMBINED_OVERDESIGN",
            disabled_reason="",
            apply_payload_summary={"updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0}},
            apply_payload_fingerprint="combined-overdesign-cleanup",
        ),
        display=FinalDesignGuideDisplay(
            title="Design is safe - optional combined cleanup available",
            badge="ACTION",
            summary="Remove unnecessary reinforcement while keeping the design inside the accepted band.",
            status="ACTION",
            bucket="optimise",
            colour_state="blue",
            display_state="ACTION",
            blocker_explanation="",
            expanded_evidence_sections={
                "reason_display_rows": (
                    {
                        "label": "Optimisation",
                        "text": "A combined cleanup candidate is available without reintroducing a failure state.",
                    },
                )
            },
        ),
        evidence=FinalDesignGuideEvidence(
            published_item_id="combined_overdesign_case",
            post_click_design_guide_state="combined_overdesign_cleanup",
            selected_family="COMBINED_OVERDESIGN",
            publication_reason="The design is safe and a combined cleanup candidate can reduce unnecessary reinforcement.",
            blocker_reason="",
        ),
        verifier_payload=FinalDesignGuideVerifierPayload(
            payload={
                "selected_family": "COMBINED_OVERDESIGN",
                "outcome_state": "ACTION",
            }
        ),
    ).with_publication_hash()
    card = build_final_design_guide_card_format(publication)

    blue_families = set((status_colour_contract().get("blue") or {}).get("families") or [])
    stale_recovery = dict(publication_payload.get("capture", {}).get("stale_contract_shell_recovery") or {})
    checks = {
        "combined_overdesign_lock_verifier_pass": lock_run["passed"],
        "combined_zero_shear_cleanup_publication_snapshot_pass": publication_run["passed"],
        "display_tone_contract_snapshot_pass": tone_run["passed"],
        "final_publication_object_snapshot_pass": object_run["passed"],
        "lock_identifies_runtime_driven_contract_authority": (
            lock_payload.get("checks", {}).get("family_shell_runtime_driven") is True
            and lock_payload.get("checks", {}).get("api_identifies_runtime_authority") is True
        ),
        "published_cleanup_uses_canonical_combined_family": (
            publication_payload.get("checks", {}).get("combined_canonical_family_is_preserved") is True
            and publication_payload.get("checks", {}).get("combined_owner_shear_cleanup_cta_maps_to_combined") is True
            and stale_recovery.get("selected_family_id") == "COMBINED_OVERDESIGN"
            and stale_recovery.get("published_family_id") == "COMBINED_OVERDESIGN"
            and stale_recovery.get("cta_family_id") == "COMBINED_OVERDESIGN"
        ),
        "formatting_contract_maps_family_to_blue": "COMBINED_OVERDESIGN" in blue_families,
        "final_publication_cta_actionable": card.cta.get("enabled") is True and card.cta.get("actionable") is True,
        "final_publication_tone_blue": card.tone == "blue",
        "final_visible_output_matches_selected_family": (
            card.selected_family == "COMBINED_OVERDESIGN"
            and card.outcome_state == "ACTION"
            and card.badge == "ACTION"
            and card.cta.get("action_type") == "apply_resolved_candidate"
        ),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "design_brain_family_contract_compliance_combined_overdesign.v1",
        "result": "PASS" if not failures else "FAIL",
        "family_id": "COMBINED_OVERDESIGN",
        "checks": checks,
        "failures": failures,
        "proof_chain": proof_chain,
        "lock_artifact": str(lock_artifact),
        "publication_artifact": str(publication_artifact),
        "formatter_artifact": {
            "publication_hash": publication.publication_hash,
            "format_hash": card.format_hash,
            "tone": card.tone,
            "badge": card.badge,
            "summary": card.summary,
            "cta": card.cta,
        },
        "product_behaviour_changed": False,
    }
    json_path, md_path = _write(snapshot)
    print(f"design_brain_family_contract_compliance_combined_overdesign {snapshot['result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
