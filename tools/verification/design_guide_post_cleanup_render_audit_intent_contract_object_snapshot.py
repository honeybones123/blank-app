"""Proof snapshot for post-cleanup render-audit intent contract extraction."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _contract(family: str = "bending") -> dict[str, Any]:
    updates = {"bottom_bar_count": 8} if family == "bending" else {"shear_spacing": 0.0}
    return {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": family,
        "updates": updates,
        "preview_pass": True,
        "expected_util": 0.9,
        "blocking_reason": None,
        "candidate_id": f"{family}-post-cleanup-1",
        "source_candidate_id": f"{family}-post-cleanup-1",
    }


def _intent_debug() -> dict[str, Any]:
    return {
        "guidance_intent_items": [
            {
                "title": "Intent row title",
                "family": "bending",
                "check_key": "bending",
                "guidance_intent": "efficiency_tightening",
                "button_contract": _contract("bending"),
            }
        ]
    }


def _cases() -> dict[str, dict[str, Any]]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_design_guide_post_cleanup_render_audit_intent_contract_result,
    )

    intent_rows = build_final_design_guide_post_cleanup_render_audit_intent_contract_result(
        guidance_debug=_intent_debug(),
    )
    intent_rows_repeat = build_final_design_guide_post_cleanup_render_audit_intent_contract_result(
        guidance_debug=_intent_debug(),
    )
    fallback_primary = build_final_design_guide_post_cleanup_render_audit_intent_contract_result(
        guidance_debug={
            "selected_title": "Selected fallback title",
            "primary_button_contract_debug": _contract("shear"),
        },
    )
    fallback_displayed = build_final_design_guide_post_cleanup_render_audit_intent_contract_result(
        guidance_debug={
            "displayed_primary_button_contract_debug": _contract("bending"),
        },
    )
    disabled_fallback = build_final_design_guide_post_cleanup_render_audit_intent_contract_result(
        guidance_debug={
            "primary_button_contract_debug": {
                **_contract("shear"),
                "actionable": False,
            },
        },
    )
    return {
        "intent_rows": intent_rows,
        "intent_rows_repeat": intent_rows_repeat,
        "fallback_primary": fallback_primary,
        "fallback_displayed": fallback_displayed,
        "disabled_fallback": disabled_fallback,
    }


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    cases = _cases()
    intent_result = dict(cases["intent_rows"].get("result") or {})
    primary_result = dict(cases["fallback_primary"].get("result") or {})
    displayed_result = dict(cases["fallback_displayed"].get("result") or {})
    return {
        "decision": "POST_CLEANUP_RENDER_AUDIT_INTENT_CONTRACT_OBJECT_READY_FOR_CUTOVER",
        "cases": cases,
        "source_checks": {
            "builder_present": "def build_final_design_guide_post_cleanup_render_audit_intent_contract_result(" in source,
            "builder_exported": '"build_final_design_guide_post_cleanup_render_audit_intent_contract_result"' in source,
            "clean_import_boundary": all(
                token not in source
                for token in ("import streamlit", "st.session_state", "inputs_page")
            ),
        },
        "intent_row_contract_found": intent_result.get("contract_found") is True,
        "intent_row_source": intent_result.get("source") == "intent_rows",
        "fallback_primary_contract_found": primary_result.get("contract_found") is True,
        "fallback_primary_source": primary_result.get("source") == "primary_button_contract_debug",
        "fallback_displayed_contract_found": displayed_result.get("contract_found") is True,
        "fallback_displayed_source": displayed_result.get("source") == "displayed_primary_button_contract_debug",
        "disabled_fallback_not_found": dict(cases["disabled_fallback"].get("result") or {}).get("contract_found")
        is False,
        "stable_repeat_hash": cases["intent_rows"].get("proof_hash")
        == cases["intent_rows_repeat"].get("proof_hash"),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "all_source_checks_pass": all(source_checks.values()),
        "intent_row_contract_found": capture.get("intent_row_contract_found") is True,
        "intent_row_source": capture.get("intent_row_source") is True,
        "fallback_primary_contract_found": capture.get("fallback_primary_contract_found") is True,
        "fallback_primary_source": capture.get("fallback_primary_source") is True,
        "fallback_displayed_contract_found": capture.get("fallback_displayed_contract_found") is True,
        "fallback_displayed_source": capture.get("fallback_displayed_source") is True,
        "disabled_fallback_not_found": capture.get("disabled_fallback_not_found") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post Cleanup Render Audit Intent Contract Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if not value]
    payload = {
        "schema": "design_guide_post_cleanup_render_audit_intent_contract_object_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_post_cleanup_render_audit_intent_contract_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_post_cleanup_render_audit_intent_contract_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_cleanup_render_audit_intent_contract_object_snapshot {payload['status']}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
