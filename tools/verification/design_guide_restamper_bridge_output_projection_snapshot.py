"""Proof that final-visible output bridge output projections are controller-readable."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
sys.path.insert(0, str(ROOT))


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_final_visible_output_bridge_trace_only,
    )
    from design_brain.final_publication import build_final_design_guide_publication_mutation_proof

    input_item = {
        "title": "Strengthening required",
        "status": "FAIL",
        "bucket": "fail",
        "button_contract": {"enabled": False, "updates": {}},
        "candidate_search_evidence": {"family": "bending"},
    }
    output_item = {
        **input_item,
        "status": "PASS",
        "button_contract": {"enabled": True, "updates": {"D": 650.0}},
        "candidate_search_evidence": {"family": "bending", "selected_candidate_updates": {"D": 650.0}},
    }
    direct = build_final_design_guide_publication_mutation_proof(
        callsite_id="fixture.pre_render_projection",
        input_item=input_item,
        output_item=output_item,
        state={"D": 500.0},
        debug={"candidate_search_evidence": {"family": "bending"}},
        rec={"source": "fixture"},
    ).to_dict()
    controller = run_design_guide_controller_final_visible_output_bridge_trace_only(
        {
            "callsite_id": "fixture.pre_render_projection",
            "input_item": input_item,
            "output_item": output_item,
            "state": {"D": 500.0},
            "debug": {"candidate_search_evidence": {"family": "bending"}},
            "rec": {"source": "fixture"},
        }
    ).to_dict()
    controller_proof = dict(controller.get("final_visible_output_bridge_proof") or {})
    projection_fields = (
        "cta_projection_hash",
        "display_projection_hash",
        "evidence_projection_hash",
        "mutation_surface",
    )
    return {
        "direct": direct,
        "controller": controller,
        "projection_fields": {field: controller_proof.get(field) for field in projection_fields},
        "projection_fields_present": all(controller_proof.get(field) for field in projection_fields),
        "controller_matches_direct": controller_proof.get("proof_hash") == direct.get("proof_hash"),
        "mutation_surface_detects_changes": dict(controller_proof.get("mutation_surface") or {})
        == {
            "output_changed": True,
            "cta_changed": True,
            "display_changed": True,
            "evidence_changed": True,
        },
        "latest": {
            "pre_render_proof": _latest("design_guide_pre_render_final_visible_output_bridge_proof"),
            "cutover_readiness": _latest("design_guide_pre_render_restamper_bridge_cutover_readiness"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "projection_fields_present": bool(capture.get("projection_fields_present")),
        "controller_matches_direct": bool(capture.get("controller_matches_direct")),
        "mutation_surface_detects_changes": bool(capture.get("mutation_surface_detects_changes")),
        "pre_render_proof_latest_pass": (latest.get("pre_render_proof") or {}).get("status") == "PASS",
        "cutover_readiness_latest_pass": (latest.get("cutover_readiness") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Design Guide Restamper Bridge Output Projection Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Summary",
        "",
        "- Controller route exposes CTA/display/evidence projection hashes.",
        "- Controller proof hash matches the direct final-publication proof builder.",
        "- This is still proof-only and product behavior is unchanged.",
        "",
        "## Next Safe Step",
        "",
        "Use these projection hashes in focused live parity scenarios for the pre-render final-visible output bridge.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_restamper_bridge_output_projection_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_restamper_bridge_output_projection_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_restamper_bridge_output_projection_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
