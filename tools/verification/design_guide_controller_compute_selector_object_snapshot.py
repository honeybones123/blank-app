"""Verify proof-only controller compute selector object."""

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
        DesignGuideControllerComputeSelectionRequest,
        DesignGuideControllerComputeSelectionResponse,
        run_design_guide_controller_compute_selection_trace_only,
    )

    source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    item = {
        "candidate_id": "selector-sample",
        "source_candidate_id": "selector-sample",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "family": "bending",
        "action_type": "increase_depth",
        "publication_reason": "sample_selection",
    }
    request = DesignGuideControllerComputeSelectionRequest(
        current_state={"D": 600},
        overview={"worst_util": 1.2},
        collapsed_guidance_items=[dict(item)],
        publication_context={"source": "sample"},
        publication_dependencies={"source": "sample"},
        publication_reason="sample_selection",
        source="selector_object_snapshot",
    )
    first = run_design_guide_controller_compute_selection_trace_only(request)
    second = run_design_guide_controller_compute_selection_trace_only(request)
    forbidden_source_tokens = {
        "inputs_page_import": "inputs_page" in source,
        "streamlit_import": "streamlit" in source,
        "session_state": "st.session_state" in source,
        "render_panel": "render_final_panel" in source,
        "apply_routing": "_record_rendered_design_guide_primary_apply_payload" in source,
    }
    return {
        "request_class": DesignGuideControllerComputeSelectionRequest.__name__,
        "response_class": DesignGuideControllerComputeSelectionResponse.__name__,
        "stable_request_hash": first.request_hash == second.request_hash,
        "stable_selection_hash": first.selection_hash == second.selection_hash,
        "stable_selected_item_hash": first.selected_item_hash == second.selected_item_hash,
        "selected_item_hash_matches_input": first.selected_item_hash == _stable_hash(item),
        "selection_policy": first.selection_policy,
        "selected_item_index": first.selected_item_index,
        "render_reason": first.render_reason,
        "state_fingerprint_present": bool(first.state_fingerprint),
        "product_flags": {
            "trace_only": first.trace_only,
            "product_driving": first.product_driving,
            "render_driving": first.render_driving,
            "apply_driving": first.apply_driving,
            "session_driving": first.session_driving,
        },
        "forbidden_source_tokens_present": forbidden_source_tokens,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    flags = dict(capture.get("product_flags") or {})
    return {
        "request_response_classes_exist": bool(capture.get("request_class"))
        and bool(capture.get("response_class")),
        "stable_hashes": (
            capture.get("stable_request_hash") is True
            and capture.get("stable_selection_hash") is True
            and capture.get("stable_selected_item_hash") is True
        ),
        "selected_primary_item_policy_explicit": (
            capture.get("selection_policy") == "primary_collapsed_guidance_item_trace_only_v1"
            and capture.get("selected_item_index") == 0
        ),
        "selected_item_hash_matches_input": capture.get("selected_item_hash_matches_input") is True,
        "render_reason_and_fingerprint_present": bool(capture.get("render_reason"))
        and capture.get("state_fingerprint_present") is True,
        "trace_only_not_product_driving": (
            flags.get("trace_only") is True
            and flags.get("product_driving") is False
            and flags.get("render_driving") is False
            and flags.get("apply_driving") is False
            and flags.get("session_driving") is False
        ),
        "no_page_ui_session_apply_imports": not any(
            (capture.get("forbidden_source_tokens_present") or {}).values()
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Controller Compute Selector Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Selector",
            "",
            f"- Policy: `{capture.get('selection_policy')}`",
            f"- Selected item index: `{capture.get('selected_item_index')}`",
            f"- Render reason: `{capture.get('render_reason')}`",
            "",
            "This selector is proof-only and is not ready to replace the legacy resolver until scenario/live parity proves the policy covers active-failure, blocker, post-click, and cleanup routes.",
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
    json_path = ARTIFACT_DIR / f"design_guide_controller_compute_selector_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_controller_compute_selector_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_controller_compute_selector_object_snapshot {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
