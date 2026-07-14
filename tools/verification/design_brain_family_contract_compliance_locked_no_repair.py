"""Focused family contract compliance verifier for LOCKED_NO_REPAIR."""

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
    json_path = ARTIFACT_DIR / f"design_brain_family_contract_compliance_locked_no_repair_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_family_contract_compliance_locked_no_repair_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(md_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# LOCKED_NO_REPAIR Family Contract Compliance",
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
    classification_run = _run("tools/verification/family_classification_lock_verifier.py")
    render_gate_run = _run("tools/verification/design_guide_render_eligibility_trace_snapshot.py")
    tone_run = _run("tools/verification/design_guide_display_tone_contract_snapshot.py")
    object_run = _run("tools/verification/design_guide_final_publication_object_snapshot.py")
    proof_chain = [classification_run, render_gate_run, tone_run, object_run]

    classification_artifact = _latest("family_classification_lock_verifier")
    classification_payload = _read_json(classification_artifact)
    locked_case = next(
        (
            case
            for case in classification_payload.get("cases") or []
            if case.get("case_id") == "locked_priority"
        ),
        {},
    )

    render_artifact = _latest("design_guide_render_eligibility_trace")
    render_payload = _read_json(render_artifact)
    render_case = next(
        (
            case
            for case in render_payload.get("case_results") or []
            if case.get("case_id") == "locked_no_repair_blocked"
        ),
        {},
    )

    publication = FinalDesignGuidePublication(
        published_item_id="locked_no_repair_case",
        selected_family="LOCKED_NO_REPAIR",
        outcome_state="BLOCKED",
        post_click_design_guide_state="locked_no_repair",
        publication_reason="Repair variables are locked or no valid repair exists.",
        blocker_reason="Locked inputs or no valid repair path prevent a legal change.",
        exact_stop_proof={},
        target_band_proof={},
        cta=FinalDesignGuideCTA(
            enabled=False,
            actionable=False,
            label="Re-evaluate",
            action_type=None,
            family="LOCKED_NO_REPAIR",
            disabled_reason="No legal repair can be applied from the current locked state.",
            apply_payload_summary={},
            apply_payload_fingerprint=None,
        ),
        display=FinalDesignGuideDisplay(
            title="No legal repair is available",
            badge="BLOCKED",
            summary="Locked inputs or no valid repair path prevent a legal change.",
            status="BLOCKED",
            bucket="blocked",
            colour_state="red",
            display_state="BLOCKED",
            blocker_explanation="Locked inputs or no valid repair path prevent a legal change.",
            expanded_evidence_sections={
                "reason_display_rows": [
                    {
                        "label": "Blocker",
                        "text": "Locked inputs or no valid repair path prevent a legal change.",
                    }
                ]
            },
        ),
        evidence=FinalDesignGuideEvidence(
            published_item_id="locked_no_repair_case",
            post_click_design_guide_state="locked_no_repair",
            selected_family="LOCKED_NO_REPAIR",
            publication_reason="Repair variables are locked or no valid repair exists.",
            blocker_reason="Locked inputs or no valid repair path prevent a legal change.",
        ),
        verifier_payload=FinalDesignGuideVerifierPayload(
            payload={
                "selected_family": "LOCKED_NO_REPAIR",
                "outcome_state": "BLOCKED",
            }
        ),
    ).with_publication_hash()
    card = build_final_design_guide_card_format(publication)

    red_families = set((status_colour_contract().get("red") or {}).get("families") or [])
    checks = {
        "family_classification_lock_verifier_pass": classification_run["passed"],
        "render_eligibility_trace_snapshot_pass": render_gate_run["passed"],
        "display_tone_contract_snapshot_pass": tone_run["passed"],
        "final_publication_object_snapshot_pass": object_run["passed"],
        "classifier_selects_locked_no_repair": locked_case.get("contract_selected_family") == "LOCKED_NO_REPAIR"
        or locked_case.get("legacy_selected_family") == "LOCKED_NO_REPAIR",
        "render_gate_records_locked_no_repair_blocked_state": render_case.get("selected_family_id") == "LOCKED_NO_REPAIR"
        and render_case.get("final_publication_outcome_state") == "BLOCKED",
        "formatting_contract_maps_family_to_red": "LOCKED_NO_REPAIR" in red_families,
        "final_publication_cta_disabled": card.cta.get("enabled") is False and card.cta.get("actionable") is False,
        "final_publication_tone_red": card.tone == "red",
        "final_visible_output_matches_selected_family": card.selected_family == "LOCKED_NO_REPAIR"
        and card.outcome_state == "BLOCKED"
        and card.badge == "BLOCKED"
        and bool(card.blocker_explanation),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "design_brain_family_contract_compliance_locked_no_repair.v1",
        "result": "PASS" if not failures else "FAIL",
        "family_id": "LOCKED_NO_REPAIR",
        "checks": checks,
        "failures": failures,
        "proof_chain": proof_chain,
        "classification_artifact": str(classification_artifact),
        "render_eligibility_artifact": str(render_artifact),
        "formatter_artifact": {
            "publication_hash": publication.publication_hash,
            "format_hash": card.format_hash,
            "tone": card.tone,
            "badge": card.badge,
            "summary": card.summary,
            "blocker_explanation": card.blocker_explanation,
            "cta": card.cta,
        },
        "product_behaviour_changed": False,
    }
    json_path, md_path = _write(snapshot)
    print(f"design_brain_family_contract_compliance_locked_no_repair {snapshot['result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
