"""Object snapshot for residual shear cleanup route proof."""

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


EXPECTED_SURFACES = {
    "route_entry_guard",
    "primary_shear_tightening_search",
    "fallback_variant_search",
    "materiality_and_safety_screen",
    "promoted_item_packaging",
    "blocker_evidence_merge",
    "target_band_reason_text",
    "cta_contract_bridge",
    "debug_session_projection",
}

EXPECTED_EXCLUSIONS = {
    "candidate_generation_execution",
    "candidate_evaluation_execution",
    "cta_contract_execution",
    "visible_wording_authoring",
    "session_debug_mutation",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _fixture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof,
    )

    request = {
        "state": {"b": 400.0, "D": 650.0, "lig_legs": 2, "s_lig": 200},
        "overview": {"utils": {"bending": 0.24, "shear": 0.69}},
        "mode_config": {"target_band": [0.85, 1.0], "goal": "efficiency"},
        "bending_blocker": {
            "family": "bending",
            "exact_blocker": True,
            "no_second_cta_required": True,
        },
        "exact_blockers_by_family": {
            "bending": {
                "family": "bending",
                "exact_blocker": True,
                "no_second_cta_required": True,
            }
        },
        "residual_shear_tightening": {
            "updates": {"lig_legs": 0, "s_lig": 0},
            "candidate_search_evidence": {
                "starting_util": 0.69,
                "best_safe_final_util": 0.91,
                "selected_candidate_id": "shear_cleanup_fixture",
                "safe_candidate_count": 1,
                "executable_candidate_count": 1,
            },
        },
        "residual_result_item": {
            "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
            "family": "shear",
            "guidance_intent": "efficiency_tightening",
            "action_type": "apply_resolved_candidate",
            "candidate_id": "shear_cleanup_fixture",
            "no_second_cta_required": True,
            "button_contract": {
                "family": "shear",
                "enabled": True,
                "action_type": "apply_resolved_candidate",
                "updates": {"lig_legs": 0, "s_lig": 0},
            },
            "candidate_search_evidence": {
                "post_click_bending_blocker_preserved": True,
                "post_click_residual_shear_cleanup_after_bending_blocker": True,
                "no_second_cta_required": True,
                "starting_util": 0.69,
                "best_safe_final_util": 0.91,
                "selected_candidate_id": "shear_cleanup_fixture",
                "exact_blockers_by_family": {
                    "bending": {
                        "family": "bending",
                        "exact_blocker": True,
                        "no_second_cta_required": True,
                    }
                },
            },
        },
        "residual_detail": {"source": "fixture"},
        "route_debug": {
            "post_click_bending_blocker_preserved": True,
            "post_click_residual_shear_cleanup_after_bending_blocker": True,
        },
        "route_flags": {"starting_shear_util": 0.69},
    }
    first = build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof(
        **request
    )
    second = build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof(
        **request
    )
    return {"first": first, "second": second}


def _function_block(source: str) -> str:
    start = source.find(
        "def build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof("
    )
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    block = _function_block(source)
    fixture = _fixture()
    first = dict(fixture.get("first") or {})
    second = dict(fixture.get("second") or {})
    projection = dict(first.get("route_projection") or {})
    forbidden_terms = (
        "inputs_page",
        "streamlit",
        "st.session_state",
        "render_html",
        "st.button",
    )
    return {
        "decision": "POST_CLICK_LOW_BENDING_RESIDUAL_SHEAR_CLEANUP_ROUTE_OBJECT_PROVEN",
        "function_present": bool(block),
        "exported": (
            '"build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof"'
            in source
        ),
        "stable_repeat_hash": first.get("proof_hash") == second.get("proof_hash"),
        "represented_route_surfaces": list(first.get("represented_route_surfaces") or []),
        "excluded_live_surfaces": list(first.get("excluded_live_surfaces") or []),
        "has_route_request": bool(projection.get("route_request")),
        "has_search_projection": bool(projection.get("search_projection")),
        "has_blocker_projection": bool(projection.get("blocker_projection")),
        "has_result_projection": bool(projection.get("result_projection")),
        "route_projection_hash_present": bool(first.get("route_projection_hash")),
        "forbidden_page_terms_absent": not any(
            term.lower() in block.lower() for term in forbidden_terms
        ),
        "proof_only": first.get("proof_only") is True,
        "product_driving": first.get("product_driving") is True,
        "render_driving": first.get("render_driving") is True,
        "apply_driving": first.get("apply_driving") is True,
        "session_driving": first.get("session_driving") is True,
        "raw_payload": first,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    represented = set(capture.get("represented_route_surfaces") or [])
    excluded = set(capture.get("excluded_live_surfaces") or [])
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "all_route_surfaces_represented": EXPECTED_SURFACES.issubset(represented),
        "live_execution_surfaces_excluded": EXPECTED_EXCLUSIONS.issubset(excluded),
        "has_route_request": capture.get("has_route_request") is True,
        "has_search_projection": capture.get("has_search_projection") is True,
        "has_blocker_projection": capture.get("has_blocker_projection") is True,
        "has_result_projection": capture.get("has_result_projection") is True,
        "route_projection_hash_present": capture.get("route_projection_hash_present") is True,
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
        "# Post-Click Low-Bending Residual Shear Cleanup Route Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Stable repeat hash: `{capture.get('stable_repeat_hash')}`",
        f"- Represented route surfaces: `{capture.get('represented_route_surfaces')}`",
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
            "Wire this object trace-only beside the residual shear cleanup branch before any route cutover.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_object_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_residual_shear_cleanup_route_object {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
