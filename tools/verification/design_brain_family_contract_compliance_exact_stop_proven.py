"""Focused family contract compliance verifier for EXACT_STOP_PROVEN."""

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
    json_path = ARTIFACT_DIR / f"design_brain_family_contract_compliance_exact_stop_proven_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_family_contract_compliance_exact_stop_proven_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(md_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# EXACT_STOP_PROVEN Family Contract Compliance",
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
    object_run = _run("tools/verification/design_guide_final_publication_object_snapshot.py")
    tone_run = _run("tools/verification/design_guide_display_tone_contract_snapshot.py")
    proof_chain = [classification_run, object_run, tone_run]

    classification_artifact = _latest("family_classification_lock_verifier")
    classification_payload = _read_json(classification_artifact)
    exact_stop_case = next(
        (
            case
            for case in classification_payload.get("cases") or []
            if case.get("case_id") == "exact_stop_priority"
        ),
        {},
    )

    publication = FinalDesignGuidePublication(
        published_item_id="exact_stop_proven_case",
        selected_family="EXACT_STOP_PROVEN",
        outcome_state="PASS",
        post_click_design_guide_state="exact_stop_proven",
        publication_reason="Exact-stop proof shows no further optimisation is required.",
        blocker_reason=None,
        exact_stop_proof={
            "status": "EXACT_STOP_PROVEN",
            "proof": "Exhaustive exact-stop proof accepted",
        },
        target_band_proof={},
        cta=FinalDesignGuideCTA(
            enabled=False,
            actionable=False,
            label="Re-evaluate",
            action_type=None,
            family="EXACT_STOP_PROVEN",
            disabled_reason="No action is required because exact stop has already been proven.",
            apply_payload_summary={},
            apply_payload_fingerprint=None,
        ),
        display=FinalDesignGuideDisplay(
            title="Design is efficient",
            badge="PASS",
            summary="No further change is required.",
            status="PASS",
            bucket="pass",
            colour_state="green",
            display_state="PASS",
            expanded_evidence_sections={
                "current": [
                    {
                        "family": "combined",
                        "label": "Overall status",
                        "value": "Exact stop proven",
                        "status": "PASS",
                    }
                ],
                "reason_display_rows": [
                    {
                        "label": "Result",
                        "text": "Exact-stop proof confirms there is no further compliant optimisation to apply.",
                    }
                ],
            },
        ),
        evidence=FinalDesignGuideEvidence(
            published_item_id="exact_stop_proven_case",
            post_click_design_guide_state="exact_stop_proven",
            selected_family="EXACT_STOP_PROVEN",
            publication_reason="Exact-stop proof shows no further optimisation is required.",
            blocker_reason=None,
            exact_stop_proof={
                "status": "EXACT_STOP_PROVEN",
                "proof": "Exhaustive exact-stop proof accepted",
            },
            target_band_proof={},
        ),
        verifier_payload=FinalDesignGuideVerifierPayload(
            payload={
                "selected_family": "EXACT_STOP_PROVEN",
                "outcome_state": "PASS",
            }
        ),
    ).with_publication_hash()
    card = build_final_design_guide_card_format(publication)

    green_families = set((status_colour_contract().get("green") or {}).get("families") or [])
    checks = {
        "family_classification_lock_verifier_pass": classification_run["passed"],
        "final_publication_object_snapshot_pass": object_run["passed"],
        "display_tone_contract_snapshot_pass": tone_run["passed"],
        "classifier_selects_exact_stop_proven": exact_stop_case.get("contract_selected_family") == "EXACT_STOP_PROVEN"
        or exact_stop_case.get("legacy_selected_family") == "EXACT_STOP_PROVEN"
        or exact_stop_case.get("selected_family_id") == "EXACT_STOP_PROVEN",
        "formatting_contract_maps_family_to_green": "EXACT_STOP_PROVEN" in green_families,
        "final_publication_cta_disabled": card.cta.get("enabled") is False and card.cta.get("actionable") is False,
        "final_publication_tone_green": card.tone == "green",
        "final_visible_output_matches_selected_family": card.selected_family == "EXACT_STOP_PROVEN"
        and card.outcome_state == "PASS"
        and card.badge == "PASS"
        and bool(card.summary),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "design_brain_family_contract_compliance_exact_stop_proven.v1",
        "result": "PASS" if not failures else "FAIL",
        "family_id": "EXACT_STOP_PROVEN",
        "checks": checks,
        "failures": failures,
        "proof_chain": proof_chain,
        "classification_artifact": str(classification_artifact),
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
    print(f"design_brain_family_contract_compliance_exact_stop_proven {snapshot['result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
