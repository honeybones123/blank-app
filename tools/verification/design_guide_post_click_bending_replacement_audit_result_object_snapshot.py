"""Object snapshot for post-click bending replacement audit/result proof."""

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
        build_final_design_guide_post_click_bending_replacement_audit_result_proof,
    )

    guidance_debug = {
        "guidance_branch": "post_click_low_bending_exact_blocker_final",
        "post_click_unresolved_low_util_families": ["bending"],
        "exact_blockers_by_family": {"bending": {"reason": "below_floor"}},
    }
    audit_sources = [
        {
            "candidate_search_evidence": {"ignored": True},
            "post_click_exact_blockers_by_family": {"bending": {"reason": "exact_stop"}},
            "cleanup_evidence_by_family": {"bending": {"cleanup": "failed"}},
            "post_click_families_below_final_threshold": ["bending", "shear"],
            "post_click_family_utils": {"bending": 0.42},
        },
        {
            "post_click_cleanup_evidence_by_family": {"bending": {"post": "cleanup"}},
            "low_util_families": ["bending"],
            "materially_overprovided_families": ["shear"],
        },
    ]
    bending_resolution = {
        "title": "Design Guide blocker proof incomplete",
        "button_contract": {"enabled": False, "blocking_reason": "exact_stop"},
    }
    bending_contract = {"enabled": False, "blocking_reason": "exact_stop"}
    output_item = {"family": "bending", "status": "BLOCKED"}
    final_visible_resolution = {
        "render_reason": "post_click_low_bending_exact_blocker_final",
        "item": dict(output_item),
    }
    first = build_final_design_guide_post_click_bending_replacement_audit_result_proof(
        guidance_debug=guidance_debug,
        audit_sources=audit_sources,
        bending_resolution=bending_resolution,
        bending_contract=bending_contract,
        output_item=output_item,
        final_visible_resolution=final_visible_resolution,
    )
    second = build_final_design_guide_post_click_bending_replacement_audit_result_proof(
        guidance_debug=guidance_debug,
        audit_sources=audit_sources,
        bending_resolution=bending_resolution,
        bending_contract=bending_contract,
        output_item=output_item,
        final_visible_resolution=final_visible_resolution,
    )
    return {"first": first, "second": second}


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    fixture = _fixture()
    first = dict(fixture.get("first") or {})
    second = dict(fixture.get("second") or {})
    audit_projection = dict(first.get("audit_projection") or {})
    resolution_result = dict(first.get("resolution_result") or {})
    forbidden_terms = (
        "inputs_page",
        "streamlit",
        "st.session_state",
        "render_html",
        "button(",
        "apply routing",
    )
    function_block_start = source.find(
        "def build_final_design_guide_post_click_bending_replacement_audit_result_proof("
    )
    function_block_end = source.find("\ndef ", function_block_start + 1)
    function_block = source[function_block_start:function_block_end]
    return {
        "decision": "POST_CLICK_BENDING_REPLACEMENT_AUDIT_RESULT_OBJECT_PROVEN",
        "function_present": function_block_start >= 0,
        "exported": (
            '"build_final_design_guide_post_click_bending_replacement_audit_result_proof"'
            in source
        ),
        "stable_repeat_hash": first.get("proof_hash") == second.get("proof_hash"),
        "bending_exact_blocker_projected": (
            dict(audit_projection.get("post_click_exact_blockers_by_family") or {})
            .get("bending", {})
            .get("reason")
            == "exact_stop"
        ),
        "cleanup_evidence_projected": bool(
            dict(audit_projection.get("cleanup_evidence_by_family") or {}).get("bending")
        ),
        "family_lists_projected": all(
            key in audit_projection
            for key in (
                "post_click_families_below_final_threshold",
                "low_util_families",
                "materially_overprovided_families",
            )
        ),
        "resolution_hashes_present": bool(
            resolution_result.get("bending_resolution_hash")
            and resolution_result.get("bending_contract_hash")
            and resolution_result.get("final_visible_resolution_hash")
        ),
        "represented_live_rows": list(first.get("represented_live_rows") or []),
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
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "bending_exact_blocker_projected": (
            capture.get("bending_exact_blocker_projected") is True
        ),
        "cleanup_evidence_projected": capture.get("cleanup_evidence_projected") is True,
        "family_lists_projected": capture.get("family_lists_projected") is True,
        "resolution_hashes_present": capture.get("resolution_hashes_present") is True,
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
        "# Post-Click Bending Replacement Audit/Result Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Stable repeat hash: `{capture.get('stable_repeat_hash')}`",
        f"- Forbidden page terms absent: `{capture.get('forbidden_page_terms_absent')}`",
        f"- Represented rows: `{capture.get('represented_live_rows')}`",
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
            "Wire this object trace-only beside the live post-click bending replacement body.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_bending_replacement_audit_result_object_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_bending_replacement_audit_result_object_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_bending_replacement_audit_result_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_bending_replacement_audit_result_object {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
