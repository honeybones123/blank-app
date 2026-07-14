"""Focused family contract compliance verifier for GEOMETRY_DETAILING_GOVERNS."""

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
    json_path = ARTIFACT_DIR / f"design_brain_family_contract_compliance_geometry_detailing_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_family_contract_compliance_geometry_detailing_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(md_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# GEOMETRY_DETAILING_GOVERNS Family Contract Compliance",
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
    runtime_run = _run("tools/verification/geometry_detailing_governs_repair_runtime_snapshot.py")
    classification_run = _run("tools/verification/family_classification_geometry_detailing_governs_snapshot.py")
    tone_run = _run("tools/verification/design_guide_display_tone_contract_snapshot.py")
    object_run = _run("tools/verification/design_guide_final_publication_object_snapshot.py")
    render_gate_run = _run("tools/verification/design_guide_render_eligibility_trace_snapshot.py")
    proof_chain = [runtime_run, classification_run, tone_run, object_run, render_gate_run]

    runtime_artifact = _latest("geometry_detailing_governs_repair_runtime")
    runtime_payload = _read_json(runtime_artifact)
    classification_artifact = _latest("family_classification_geometry_detailing_governs")
    classification_payload = _read_json(classification_artifact)
    render_artifact = _latest("design_guide_render_eligibility_trace")
    render_payload = _read_json(render_artifact)

    action_case = next(
        (case for case in runtime_payload.get("cases") or [] if case.get("case_id") == "family_result_adapter"),
        {},
    )
    classification_case = next(
        (
            case
            for case in classification_payload.get("cases") or []
            if case.get("case_id") == "geometry_detailing_only"
        ),
        {},
    )
    render_case = next(
        (
            case
            for case in render_payload.get("case_results") or []
            if case.get("case_id") == "invalid_geometry_family_action"
        ),
        {},
    )

    publication = FinalDesignGuidePublication(
        published_item_id="geometry_detailing_case",
        selected_family="GEOMETRY_DETAILING_GOVERNS",
        outcome_state="ACTION",
        post_click_design_guide_state="geometry_detailing_rescue",
        publication_reason="Input geometry or detailing is invalid and a corrective geometry change is available.",
        blocker_reason="",
        exact_stop_proof={},
        target_band_proof={},
        cta=FinalDesignGuideCTA(
            enabled=True,
            actionable=True,
            label="Apply geometry fix",
            action_type="apply_resolved_candidate",
            family="GEOMETRY_DETAILING_GOVERNS",
            disabled_reason="",
            apply_payload_summary={"updates": {"b": 430.0}},
            apply_payload_fingerprint="geometry-detailing-width-rescue",
        ),
        display=FinalDesignGuideDisplay(
            title="Geometry input needs correction",
            badge="ACTION",
            summary="A geometry/detailing correction is available before normal engineering recommendation ladders run.",
            status="ACTION",
            bucket="blocked",
            colour_state="red",
            display_state="ACTION",
            blocker_explanation="",
            expanded_evidence_sections={
                "reason_display_rows": (
                    {
                        "label": "Geometry",
                        "text": "The current depth-to-width ratio is not valid and width rescue is available.",
                    },
                )
            },
        ),
        evidence=FinalDesignGuideEvidence(
            published_item_id="geometry_detailing_case",
            post_click_design_guide_state="geometry_detailing_rescue",
            selected_family="GEOMETRY_DETAILING_GOVERNS",
            publication_reason="Input geometry or detailing is invalid and a corrective geometry change is available.",
            blocker_reason="",
        ),
        verifier_payload=FinalDesignGuideVerifierPayload(
            payload={
                "selected_family": "GEOMETRY_DETAILING_GOVERNS",
                "outcome_state": "ACTION",
            }
        ),
    ).with_publication_hash()
    card = build_final_design_guide_card_format(publication)

    red_families = set((status_colour_contract().get("red") or {}).get("families") or [])
    checks = {
        "geometry_detailing_runtime_snapshot_pass": runtime_run["passed"],
        "geometry_detailing_classification_snapshot_pass": classification_run["passed"],
        "display_tone_contract_snapshot_pass": tone_run["passed"],
        "final_publication_object_snapshot_pass": object_run["passed"],
        "render_eligibility_trace_snapshot_pass": render_gate_run["passed"],
        "contract_classifier_selects_geometry_detailing": classification_case.get("contract_selected_family")
        == "GEOMETRY_DETAILING_GOVERNS"
        and classification_case.get("live_selected_family") == "GEOMETRY_DETAILING_GOVERNS",
        "runtime_returns_applyable_geometry_fix": action_case.get("status") == "ACTION"
        and dict(action_case.get("updates") or {}).get("b") == 430.0,
        "inputs_page_keeps_existing_apply_binding": runtime_payload.get("static_checks", {})
        .get("checks", {})
        .get("inputs_uses_existing_apply_binding")
        is True,
        "render_gate_marks_geometry_case_as_contract_required": render_case.get("classification") == "C"
        and render_case.get("selected_family_id") == "GEOMETRY_DETAILING_GOVERNS"
        and render_case.get("final_publication_outcome_state") == "ACTION",
        "formatting_contract_maps_family_to_red": "GEOMETRY_DETAILING_GOVERNS" in red_families,
        "final_publication_cta_actionable": card.cta.get("enabled") is True and card.cta.get("actionable") is True,
        "final_visible_output_matches_selected_family": (
            card.selected_family == "GEOMETRY_DETAILING_GOVERNS"
            and card.outcome_state == "ACTION"
            and card.badge == "ACTION"
            and card.cta.get("action_type") == "apply_resolved_candidate"
        ),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "design_brain_family_contract_compliance_geometry_detailing.v1",
        "result": "PASS" if not failures else "FAIL",
        "family_id": "GEOMETRY_DETAILING_GOVERNS",
        "checks": checks,
        "failures": failures,
        "proof_chain": proof_chain,
        "runtime_artifact": str(runtime_artifact),
        "classification_artifact": str(classification_artifact),
        "render_eligibility_artifact": str(render_artifact),
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
    print(f"design_brain_family_contract_compliance_geometry_detailing {snapshot['result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
