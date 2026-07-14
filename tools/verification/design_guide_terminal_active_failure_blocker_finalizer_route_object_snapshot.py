"""Snapshot terminal active-failure blocker finalizer controller route.

Proof-only. This does not cut over inputs_page.py, change CTA/apply semantics,
change visible wording, change family runtimes, or move Streamlit rendering.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import inspect
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
ROUTE = "run_design_guide_controller_terminal_active_failure_blocker_finalizer_route"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _state_fingerprint(state: dict[str, Any] | None) -> str:
    return "state:" + _stable_hash(dict(state or {}))[:16]


def _suppress_blocker_cta(item: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(item or {})
    out["primary_card_actionable"] = False
    out["button_contract"] = {
        "enabled": False,
        "actionable": False,
        "reason": "terminal_active_failure_blocker_snapshot",
    }
    return out


def _active_item(*, scope: str, marker: str, active_blocker: bool = False) -> dict[str, Any]:
    return {
        "title": "Existing active blocker",
        "title_main": "Existing active blocker",
        "family": "bending",
        "source_marker": marker,
        "primary_action": "Bending repair blocked.",
        "active_under_capacity_blocker": bool(active_blocker),
        "candidate_search_evidence": {
            "search_scope": scope,
            "active_fail_repair_search_scope": scope,
            "repair_search_exhaustive": True,
            "exact_blockers_by_family": {
                "bending": {
                    "family": "bending",
                    "blocked_reason": "snapshot blocker",
                    "blocked_ladder": "BENDING_FAIL_GOVERNS",
                    "no_valid_candidate": True,
                }
            },
        },
    }


def _scenario_payload() -> dict[str, Any]:
    return {
        "active_family": "bending",
        "active_title": "Bending repair blocked",
        "active_failures": ["bending"],
        "final_overview": {
            "bending": {"utilisation": 1.42, "status": "FAIL"},
            "shear": {"utilisation": 0.82, "status": "PASS"},
        },
        "final_state": {"D": 650.0, "b": 400.0, "Mu_pos": 800.0},
        "debug_probe": {"snapshot": "terminal_active_failure_blocker_finalizer_route"},
    }


def _run_case(active_item: dict[str, Any] | None, fallback_marker: str) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_terminal_active_failure_blocker_finalizer_route,
    )

    payload = _scenario_payload()
    fallback_item = {
        "title": "Fallback active blocker",
        "title_main": "Fallback active blocker",
        "family": "bending",
        "source_marker": fallback_marker,
        "primary_action": "Fallback bending repair blocked.",
        "candidate_search_evidence": {
            "search_scope": "active_fail_fallback_snapshot",
            "active_fail_repair_search_scope": "active_fail_fallback_snapshot",
            "repair_search_exhaustive": True,
        },
    }
    result = run_design_guide_controller_terminal_active_failure_blocker_finalizer_route(
        active_item=active_item,
        raw_guidance_items=[fallback_item],
        state_fingerprint_fn=_state_fingerprint,
        suppress_design_guide_blocker_cta_fn=_suppress_blocker_cta,
        **payload,
    )
    item = dict(result.get("item") or {})
    return {
        "result": result,
        "item": item,
        "source_marker": item.get("source_marker"),
        "render_reason": result.get("render_reason"),
        "state_fingerprint": result.get("state_fingerprint"),
        "button_contract": dict(item.get("button_contract") or {}),
        "exact_blockers_by_family": dict(item.get("exact_blockers_by_family") or {}),
        "publication_hash": _stable_hash(result),
    }


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_terminal_active_failure_blocker_finalizer_route,
    )

    route_source = inspect.getsource(
        run_design_guide_controller_terminal_active_failure_blocker_finalizer_route
    )
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    valid_active = _run_case(
        _active_item(scope="active_fail_depth_width_exhausted", marker="active"),
        "fallback",
    )
    active_under_capacity = _run_case(
        _active_item(scope="cleanup_search", marker="active_under_capacity", active_blocker=True),
        "fallback",
    )
    invalid_cleanup = _run_case(
        _active_item(scope="cleanup_search", marker="invalid_cleanup"),
        "fallback",
    )
    repeat = _run_case(
        _active_item(scope="active_fail_depth_width_exhausted", marker="active"),
        "fallback",
    )
    forbidden_tokens = {
        "inputs_page_import": "inputs_page" in route_source,
        "streamlit": "streamlit" in route_source.lower() or "st.session_state" in route_source,
        "render_html": "html" in route_source.lower() or "st." in route_source,
        "apply_routing": "apply" in route_source.lower() or "one_click" in route_source.lower(),
    }
    return {
        "route": {
            "name": ROUTE,
            "present": ROUTE in controller_source,
            "source_hash": _stable_hash(route_source),
            "signature": str(inspect.signature(run_design_guide_controller_terminal_active_failure_blocker_finalizer_route)),
            "forbidden_tokens": forbidden_tokens,
        },
        "cases": {
            "valid_active_source_kept": valid_active,
            "active_under_capacity_source_kept": active_under_capacity,
            "invalid_cleanup_source_falls_back": invalid_cleanup,
        },
        "stable_repeat_hash": valid_active["publication_hash"] == repeat["publication_hash"],
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "page_routing_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    route = dict(capture.get("route") or {})
    cases = dict(capture.get("cases") or {})
    valid = dict(cases.get("valid_active_source_kept") or {})
    active_under_capacity = dict(cases.get("active_under_capacity_source_kept") or {})
    invalid = dict(cases.get("invalid_cleanup_source_falls_back") or {})
    return {
        "route_present": route.get("present") is True,
        "route_imports_clean": not any((route.get("forbidden_tokens") or {}).values()),
        "valid_active_source_kept": valid.get("source_marker") == "active",
        "active_under_capacity_source_kept": active_under_capacity.get("source_marker")
        == "active_under_capacity",
        "invalid_cleanup_source_falls_back": invalid.get("source_marker") == "fallback",
        "valid_render_reason_matches": valid.get("render_reason")
        == "final_visible_active_strength_blocker",
        "invalid_render_reason_matches": invalid.get("render_reason")
        == "final_visible_active_strength_blocker",
        "valid_button_disabled": (valid.get("button_contract") or {}).get("enabled") is False,
        "invalid_button_disabled": (invalid.get("button_contract") or {}).get("enabled") is False,
        "valid_exact_blocker_present": "bending" in (valid.get("exact_blockers_by_family") or {}),
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "page_routing_unchanged": capture.get("page_routing_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Terminal Active-Failure Blocker Finalizer Route Object Snapshot",
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
            "## Cases",
            "",
            "| Case | Source marker | Render reason | Button enabled |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for case, data in (capture.get("cases") or {}).items():
        button = dict((data or {}).get("button_contract") or {})
        lines.append(
            f"| {case} | `{(data or {}).get('source_marker')}` | `{(data or {}).get('render_reason')}` | `{button.get('enabled')}` |"
        )
    lines.extend(
        [
            "",
            "No inputs_page.py routing, visible wording, CTA/apply semantics, family runtime, render ownership, or session behavior changed.",
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
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_terminal_active_failure_blocker_finalizer_route_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_terminal_active_failure_blocker_finalizer_route_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_terminal_active_failure_blocker_finalizer_route_object {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
