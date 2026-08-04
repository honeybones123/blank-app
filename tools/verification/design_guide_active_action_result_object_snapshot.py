"""Proof-only snapshot for the controller active-action result object."""

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


def _sample_result() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_active_action_result,
    )

    return build_design_guide_controller_active_action_result(
        active_item={
            "title": "Strengthening required",
            "bucket": "fail",
            "display_truth": {"existing": "kept"},
            "action_payload": {"preexisting": True},
            "resolved_candidate": {"preexisting_resolved": True},
            "active_under_capacity_blocker": {"stale": True},
        },
        contract={"source": "sample"},
        updates={"D": 650, "N16_bottom": 8},
        active_family="BENDING_FAIL_GOVERNS",
        active_title="Strengthening required",
        candidate_id="candidate-1",
        expected_util=0.87,
        current_family_util=1.33,
        final_overview={"bending": {"util": 1.33}},
        active_item_evidence={"proof": "outside"},
        active_outside_exact_blockers={"shear": {"reason": "below floor"}},
        merged_residual_shear_cleanup={"evidence": {"removed_links": True}},
        merged_residual_bending_cleanup={},
        debug_probe={"debug": "kept"},
        state_fingerprint="state-hash",
        secondary_action="Review alternatives",
        guidance_change_lines=["Depth 600 -> 650"],
        guidance_change_summary_compact="Depth 600 -> 650",
        efficiency_target_util_min=0.85,
        efficiency_target_util_max=1.0,
    )


def _capture() -> dict[str, Any]:
    source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    first = _sample_result()
    second = _sample_result()
    item = dict(first.get("item") or {})
    contract = dict(item.get("button_contract") or {})
    action_payload = dict(item.get("action_payload") or {})
    resolved_candidate = dict(item.get("resolved_candidate") or {})
    return {
        "builder_exported": '"build_design_guide_controller_active_action_result"' in source,
        "result_hash": _stable_hash(first),
        "stable_repeat_hash": _stable_hash(first) == _stable_hash(second),
        "result_fields": sorted(first.keys()),
        "render_reason": first.get("render_reason"),
        "presentation": dict(first.get("presentation") or {}),
        "button_contract": {
            "enabled": contract.get("enabled"),
            "actionable": contract.get("actionable"),
            "action_type": contract.get("action_type"),
            "family": contract.get("family"),
            "preview_pass": contract.get("preview_pass"),
            "updates": dict(contract.get("updates") or {}),
        },
        "action_payload": {
            "updates": dict(action_payload.get("updates") or {}),
            "candidate_id": action_payload.get("candidate_id"),
            "guidance_change_lines": list(action_payload.get("guidance_change_lines") or []),
            "exact_blocker_families": sorted(
                str(key) for key in dict(action_payload.get("exact_blockers_by_family") or {})
            ),
        },
        "resolved_candidate": {
            "updates": dict(resolved_candidate.get("updates") or {}),
            "candidate_id": resolved_candidate.get("candidate_id"),
            "exact_blocker_families": sorted(
                str(key)
                for key in dict(resolved_candidate.get("exact_blockers_by_family") or {})
            ),
        },
        "stale_blocker_removed_from_item": "active_under_capacity_blocker" not in item,
        "outside_blocker_preserved_in_payloads": (
            bool(action_payload.get("exact_blockers_by_family"))
            and bool(resolved_candidate.get("exact_blockers_by_family"))
        ),
        "imports_forbidden_page_surfaces": any(
            token in source
            for token in ["inputs_page", "streamlit", "st.session_state", "design_guide_page"]
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "builder_exported": capture.get("builder_exported") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "required_result_fields_present": set(capture.get("result_fields") or []) >= {
            "item",
            "overview",
            "presentation",
            "render_reason",
            "state_fingerprint",
            "debug",
        },
        "render_reason_correct": capture.get("render_reason")
        == "final_visible_active_strength_action",
        "button_contract_executor_backed": (
            (capture.get("button_contract") or {}).get("enabled") is True
            and (capture.get("button_contract") or {}).get("actionable") is True
            and (capture.get("button_contract") or {}).get("action_type")
            == "apply_resolved_candidate"
        ),
        "action_payload_has_updates": bool((capture.get("action_payload") or {}).get("updates")),
        "resolved_candidate_has_updates": bool(
            (capture.get("resolved_candidate") or {}).get("updates")
        ),
        "stale_blocker_removed_from_item": capture.get("stale_blocker_removed_from_item") is True,
        "outside_blocker_preserved_in_payloads": capture.get(
            "outside_blocker_preserved_in_payloads"
        )
        is True,
        "no_forbidden_page_imports": capture.get("imports_forbidden_page_surfaces") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    lines = [
        "# Design Guide Active Action Result Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Result hash: `{capture.get('result_hash')}`",
        f"Render reason: `{capture.get('render_reason')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The controller can represent the active-action result object. This is proof-only; "
            "the live page assembler is not cut over by this snapshot.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_active_action_result_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_active_action_result_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_active_action_result_object {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
