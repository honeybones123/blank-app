"""Object snapshot for post-click low-bending resolution request proof."""

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
        build_final_design_guide_post_click_low_bending_resolution_request_proof,
    )

    request = {
        "state": {"b": 300.0, "D": 500.0, "reo": "3N20"},
        "overview": {"utils": {"bending": 0.42, "shear": 0.81}},
        "mode_config": {"goal": "efficiency", "target_band": [0.85, 1.0]},
        "acceptance_audit": {
            "post_click_unresolved_low_util_families": ["bending"],
            "post_click_families_below_final_threshold": ["bending", "shear"],
        },
        "last_apply_route": {
            "apply_used_resolved_candidate_payload": True,
            "applied_updates": {"reo": "2N20"},
            "resolved_candidate_label": "Best safe bending cleanup",
        },
    }
    first = build_final_design_guide_post_click_low_bending_resolution_request_proof(**request)
    second = build_final_design_guide_post_click_low_bending_resolution_request_proof(**request)
    return {"first": first, "second": second}


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    start = source.find("def build_final_design_guide_post_click_low_bending_resolution_request_proof(")
    end = source.find("\ndef ", start + 1)
    function_block = source[start:end] if end > start else ""
    fixture = _fixture()
    first = dict(fixture.get("first") or {})
    second = dict(fixture.get("second") or {})
    summary = dict(first.get("request_summary") or {})
    forbidden_terms = ("inputs_page", "streamlit", "st.session_state", "render_html", "button(")
    return {
        "decision": "POST_CLICK_LOW_BENDING_RESOLUTION_REQUEST_OBJECT_PROVEN",
        "function_present": start >= 0,
        "exported": (
            '"build_final_design_guide_post_click_low_bending_resolution_request_proof"'
            in source
        ),
        "stable_repeat_hash": first.get("proof_hash") == second.get("proof_hash"),
        "represented_live_inputs": list(first.get("represented_live_inputs") or []),
        "hidden_page_dependency_represented": first.get("hidden_page_dependency_represented")
        == "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
        "post_click_apply_context": summary.get("post_click_apply_context") is True,
        "last_apply_label_preserved": summary.get("last_apply_label") == "best safe bending cleanup",
        "audit_family_sets_hash_present": bool(summary.get("audit_family_sets_hash")),
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
        "hidden_page_dependency_represented": (
            capture.get("hidden_page_dependency_represented") is True
        ),
        "post_click_apply_context": capture.get("post_click_apply_context") is True,
        "last_apply_label_preserved": capture.get("last_apply_label_preserved") is True,
        "audit_family_sets_hash_present": capture.get("audit_family_sets_hash_present") is True,
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
        "# Post-Click Low Bending Resolution Request Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Stable repeat hash: `{capture.get('stable_repeat_hash')}`",
        f"- Hidden page dependency represented: `{capture.get('hidden_page_dependency_represented')}`",
        f"- Represented inputs: `{capture.get('represented_live_inputs')}`",
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
            "Wire this request proof trace-only beside `_post_click_low_bending_resolution_item(...)`.",
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
        "schema": "design_guide_post_click_low_bending_resolution_request_object_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_resolution_request_object_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_resolution_request_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_low_bending_resolution_request_object {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
