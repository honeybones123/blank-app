"""Object snapshot for post-click low-bending resolution result projection proof."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _fixture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_low_bending_resolution_result_projection_proof,
    )

    request = {
        "result_item": {
            "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
            "status": "ACTION",
            "bucket": "action",
            "title_main": "Strengthening required",
            "guidance_intent": "efficiency_tightening",
            "local_cleanup_candidate": True,
            "post_click_low_family_cleanup_action": False,
            "terminal_state_blocked_by_local_cleanup": False,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "no_second_cta_required": False,
            "candidate_id": "bending_cleanup_fixture",
            "candidate_search_evidence": {
                "selected_candidate_id": "bending_cleanup_fixture",
                "selected_candidate_util": 0.87,
                "post_click_exact_blockers_by_family": {
                    "bending": {
                        "blocker_type": "final_threshold",
                        "no_second_cta_required": True,
                    }
                },
            },
            "button_contract": {
                "family": "bending",
                "action_type": "apply_resolved_candidate",
                "enabled": True,
            },
        },
        "acceptance_audit": {
            "post_click_exact_blockers_by_family": {
                "bending": {
                    "blocker_type": "final_threshold",
                    "no_second_cta_required": True,
                }
            }
        },
        "final_visible_resolution": {"reason": "fixture"},
    }
    first = build_final_design_guide_post_click_low_bending_resolution_result_projection_proof(**request)
    second = build_final_design_guide_post_click_low_bending_resolution_result_projection_proof(**request)
    return {"first": first, "second": second}


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    start = source.find(
        "def build_final_design_guide_post_click_low_bending_resolution_result_projection_proof("
    )
    end = source.find("\ndef ", start + 1)
    function_block = source[start:end] if end > start else ""
    fixture = _fixture()
    first = dict(fixture.get("first") or {})
    second = dict(fixture.get("second") or {})
    projection = dict(first.get("result_projection") or {})
    forbidden_terms = (
        "inputs_page",
        "streamlit",
        "st.session_state",
        "render_html",
        "button(",
        "one_click",
    )
    return {
        "decision": "POST_CLICK_LOW_BENDING_RESULT_PROJECTION_OBJECT_PROVEN",
        "function_present": start >= 0,
        "exported": (
            '"build_final_design_guide_post_click_low_bending_resolution_result_projection_proof"'
            in source
        ),
        "stable_repeat_hash": first.get("proof_hash") == second.get("proof_hash"),
        "represented_result_surfaces": list(first.get("represented_result_surfaces") or []),
        "excluded_live_surfaces": list(first.get("excluded_live_surfaces") or []),
        "has_result_identity": bool(projection.get("result_identity")),
        "has_cleanup_flags": bool(projection.get("cleanup_flags")),
        "has_evidence_projection": bool(projection.get("evidence_projection")),
        "result_projection_hash_present": bool(first.get("result_projection_hash")),
        "forbidden_page_terms_absent": not any(
            term.lower() in function_block.lower() for term in forbidden_terms
        ),
        "proof_only": first.get("proof_only") is True,
        "product_driving": first.get("product_driving") is True,
        "render_driving": first.get("render_driving") is True,
        "apply_driving": first.get("apply_driving") is True,
        "session_driving": first.get("session_driving") is True,
        "raw_payload": first,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    represented = set(capture.get("represented_result_surfaces") or [])
    excluded = set(capture.get("excluded_live_surfaces") or [])
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "represented_a_class_surfaces": {
            "early_cleanup_action_item",
            "best_safe_partial_or_incremental_item",
            "exact_blocker_evidence",
        }.issubset(represented),
        "excluded_live_surfaces_preserved": {
            "cta_contract_fallback",
            "residual_shear_cleanup_probe",
            "visible_wording",
            "search_and_evaluation_dependencies",
        }.issubset(excluded),
        "has_result_identity": capture.get("has_result_identity") is True,
        "has_cleanup_flags": capture.get("has_cleanup_flags") is True,
        "has_evidence_projection": capture.get("has_evidence_projection") is True,
        "result_projection_hash_present": capture.get("result_projection_hash_present") is True,
        "forbidden_page_terms_absent": capture.get("forbidden_page_terms_absent") is True,
        "proof_only": capture.get("proof_only") is True,
        "not_product_driving": capture.get("product_driving") is False,
        "not_render_driving": capture.get("render_driving") is False,
        "not_apply_driving": capture.get("apply_driving") is False,
        "not_session_driving": capture.get("session_driving") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Low-Bending Resolution Result Projection Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Stable repeat hash: `{capture.get('stable_repeat_hash')}`",
        f"- Represented result surfaces: `{capture.get('represented_result_surfaces')}`",
        f"- Excluded live surfaces: `{capture.get('excluded_live_surfaces')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Add trace-only wiring beside `_post_click_low_bending_resolution_item(...)` output before any branch cutover.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_resolution_result_projection_object_snapshot.v1",
        "generated_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_resolution_result_projection_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_resolution_result_projection_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_resolution_result_projection_object {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
