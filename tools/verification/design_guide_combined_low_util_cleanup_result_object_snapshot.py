"""Verify controller object for already-selected combined low-util cleanup result."""

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

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_combined_low_util_cleanup_result,
    )

    source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    item = {
        "title_main": "Combined cleanup",
        "title": "Combined cleanup",
        "primary_action": "Apply combined cleanup",
        "guidance_intent": "efficiency_tightening",
        "bucket": "pass",
        "candidate_id": "combined-cleanup-sample",
    }
    contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "combined",
        "updates": {"b": 300, "lig_legs": 0},
        "candidate_id": "combined-cleanup-sample",
    }
    updates = {"b": 300, "lig_legs": 0}
    first = build_design_guide_controller_combined_low_util_cleanup_result(
        cleanup_item=dict(item),
        cleanup_contract=dict(contract),
        cleanup_updates=dict(updates),
        final_overview={"utils": {"bending": 0.42, "shear": 0.38}},
        state_fingerprint="sample-state-fingerprint",
        current_bending_util=0.42,
        current_shear_util=0.38,
        shear_seed_updates={"lig_legs": 0},
    )
    second = build_design_guide_controller_combined_low_util_cleanup_result(
        cleanup_item=dict(item),
        cleanup_contract=dict(contract),
        cleanup_updates=dict(updates),
        final_overview={"utils": {"bending": 0.42, "shear": 0.38}},
        state_fingerprint="sample-state-fingerprint",
        current_bending_util=0.42,
        current_shear_util=0.38,
        shear_seed_updates={"lig_legs": 0},
    )
    forbidden_tokens = {
        "inputs_page": "inputs_page" in source,
        "streamlit": "streamlit" in source,
        "st_session_state": "st.session_state" in source,
        "render_panel": "render_final_panel" in source,
        "apply_routing": "handle_apply_buttons" in source,
    }
    return {
        "result_hash_stable": _stable_hash(first) == _stable_hash(second),
        "result": first,
        "result_shape": {
            "has_item": isinstance(first.get("item"), dict),
            "has_overview": isinstance(first.get("overview"), dict),
            "has_presentation": isinstance(first.get("presentation"), dict),
            "has_debug": isinstance(first.get("debug"), dict),
            "has_state_fingerprint": bool(first.get("state_fingerprint")),
            "controller_authority": first.get("controller_authority"),
            "render_reason": first.get("render_reason"),
        },
        "item_shape": {
            "primary_card_actionable": (first.get("item") or {}).get("primary_card_actionable"),
            "updates": dict((first.get("item") or {}).get("updates") or {}),
            "selected_action_updates": dict(
                (first.get("item") or {}).get("selected_action_updates") or {}
            ),
            "button_contract": dict((first.get("item") or {}).get("button_contract") or {}),
            "final_visible_design_guide_item": (first.get("item") or {}).get(
                "final_visible_design_guide_item"
            ),
            "final_visible_resolver_reason": (first.get("item") or {}).get(
                "final_visible_resolver_reason"
            ),
        },
        "forbidden_tokens_present": forbidden_tokens,
        "decision": "COMBINED_LOW_UTIL_CLEANUP_RESULT_OBJECT_READY",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    shape = dict(capture.get("result_shape") or {})
    item = dict(capture.get("item_shape") or {})
    return {
        "result_hash_stable": capture.get("result_hash_stable") is True,
        "required_result_shape_present": all(
            bool(shape.get(key))
            for key in (
                "has_item",
                "has_overview",
                "has_presentation",
                "has_debug",
                "has_state_fingerprint",
            )
        )
        and shape.get("controller_authority")
        == "DesignGuideController.combined_low_util_cleanup_result"
        and shape.get("render_reason") == "final_visible_combined_low_util_safe_cleanup",
        "required_item_shape_present": item.get("primary_card_actionable") is True
        and bool(item.get("updates"))
        and item.get("updates") == item.get("selected_action_updates")
        and bool(item.get("button_contract"))
        and item.get("final_visible_design_guide_item") is True
        and item.get("final_visible_resolver_reason")
        == "final_visible_combined_low_util_safe_cleanup",
        "no_page_ui_session_apply_imports": not any(
            (capture.get("forbidden_tokens_present") or {}).values()
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Cleanup Result Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "This proof object represents an already-selected combined cleanup result. It does not generate candidates, search cleanup options, render UI, or route Apply.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_cleanup_result_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_cleanup_result_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_cleanup_result_object_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
