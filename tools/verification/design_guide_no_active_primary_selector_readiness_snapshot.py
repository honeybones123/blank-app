"""Focused readiness proof for replacing the no-active primary resolver route.

This snapshot compares the controller compute selector against the legacy
no-active primary route shape. It intentionally imports the legacy
inputs_page.py fingerprint function to prove whether that page-owned truth still
blocks replacement.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "passed": proc.returncode == 0,
    }


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        DesignGuideControllerComputeSelectionRequest,
        run_design_guide_controller_compute_selection_trace_only,
    )
    import inputs_page

    state = {
        "b": 300,
        "D": 600,
        "fc": 40,
        "fsy": 500,
        "bot1_count": 3,
        "db_bot_1": 16,
        "lig_legs": 0,
        "lig_d": 0,
        "s_lig": 200,
    }
    overview = {
        "statuses": {
            "bending": "PASS",
            "shear": "PASS",
            "crack": "PASS",
            "deflection": "PASS",
        },
        "utils": {"bending": 0.72, "shear": 0.31},
        "worst_util": 0.72,
    }
    primary_item = {
        "candidate_id": "no-active-primary-candidate",
        "source_candidate_id": "no-active-primary-candidate",
        "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
        "family": "bending",
        "action_type": "none",
        "publication_reason": "final_visible_no_active_strength_fail",
        "title": "Design is efficient",
        "button_contract": {"enabled": False, "updates": {}},
    }
    request = DesignGuideControllerComputeSelectionRequest(
        current_state=dict(state),
        overview=dict(overview),
        collapsed_guidance_items=[dict(primary_item)],
        publication_context={
            "source": "no_active_primary_readiness",
            "guidance_state_snapshot": inputs_page._guidance_state_snapshot(dict(state)),
        },
        publication_dependencies={"source": "no_active_primary_readiness"},
        session_controls={},
        design_actions_signature=tuple(
            inputs_page._resolve_design_actions_from_state(
                inputs_page._guidance_state_snapshot(dict(state))
            ).get("signature", ())
        ),
        optimisation_goal=str(inputs_page._design_optimisation_goal(dict(state))),
        publication_reason="final_visible_no_active_strength_fail",
        source="no_active_primary_selector_readiness",
    )
    first = run_design_guide_controller_compute_selection_trace_only(request)
    second = run_design_guide_controller_compute_selection_trace_only(request)
    legacy_state_fingerprint = inputs_page._design_guide_primary_apply_state_fingerprint(state)
    legacy_selected_item_hash = _stable_hash(primary_item)
    controller_matches = {
        "selected_item_identity": first.selected_item_hash == legacy_selected_item_hash,
        "render_reason": first.render_reason == "final_visible_no_active_strength_fail",
        "state_fingerprint": first.state_fingerprint == legacy_state_fingerprint,
    }
    replacement_ready = all(controller_matches.values())
    blockers = [
        key for key, value in controller_matches.items() if value is not True
    ]
    return {
        "scenario": "no_active_primary_collapsed_item",
        "selection_policy": first.selection_policy,
        "stable_selection_hash": first.selection_hash == second.selection_hash,
        "stable_request_hash": first.request_hash == second.request_hash,
        "trace_flags": {
            "trace_only": first.trace_only,
            "product_driving": first.product_driving,
            "render_driving": first.render_driving,
            "apply_driving": first.apply_driving,
            "session_driving": first.session_driving,
        },
        "controller_hashes": {
            "request_hash": first.request_hash,
            "selection_hash": first.selection_hash,
            "selected_item_hash": first.selected_item_hash,
            "state_fingerprint": first.state_fingerprint,
        },
        "legacy_hashes": {
            "selected_item_hash": legacy_selected_item_hash,
            "state_fingerprint_hash": _stable_hash(legacy_state_fingerprint),
        },
        "legacy_state_fingerprint_type": type(legacy_state_fingerprint).__name__,
        "controller_matches": controller_matches,
        "replacement_ready": replacement_ready,
        "replacement_blockers": blockers,
        "decision": (
            "READY_TO_REPLACE_NO_ACTIVE_PRIMARY"
            if replacement_ready
            else "NOT_READY_SELECTOR_PARITY_GAP"
        ),
        "composed": {
            "live_controller_compute_selection_trace": _run(
                "tools/verification/design_guide_live_controller_compute_selection_trace_snapshot.py"
            ),
            "selector_legacy_route_parity": _run(
                "tools/verification/design_guide_controller_compute_selector_legacy_route_parity_snapshot.py"
            ),
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    flags = dict(capture.get("trace_flags") or {})
    composed = dict(capture.get("composed") or {})
    matches = dict(capture.get("controller_matches") or {})
    return {
        "scenario_is_no_active_primary": capture.get("scenario")
        == "no_active_primary_collapsed_item",
        "stable_hashes": capture.get("stable_selection_hash") is True
        and capture.get("stable_request_hash") is True,
        "selector_trace_only": flags.get("trace_only") is True
        and flags.get("product_driving") is False
        and flags.get("render_driving") is False
        and flags.get("apply_driving") is False
        and flags.get("session_driving") is False,
        "identity_and_reason_match": matches.get("selected_item_identity") is True
        and matches.get("render_reason") is True,
        "state_fingerprint_matches": matches.get("state_fingerprint") is True,
        "composed_trace_and_route_parity_pass": all(
            (result or {}).get("passed") is True for result in composed.values()
        ),
        "route_replacement_ready": capture.get("replacement_ready") is True
        and capture.get("decision") == "READY_TO_REPLACE_NO_ACTIVE_PRIMARY",
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide No-Active Primary Selector Readiness Snapshot",
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
            "## Match Result",
            "",
            f"- Selected item identity matches: `{(capture.get('controller_matches') or {}).get('selected_item_identity')}`",
            f"- Render reason matches: `{(capture.get('controller_matches') or {}).get('render_reason')}`",
            f"- State fingerprint matches: `{(capture.get('controller_matches') or {}).get('state_fingerprint')}`",
            f"- Replacement ready: `{capture.get('replacement_ready')}`",
            f"- Replacement blockers: `{', '.join(capture.get('replacement_blockers') or [])}`",
            "",
            "## Next Step",
            "",
            "If not already cut over, replace only the no-active primary branch with the controller selector output, then rerun this snapshot and the composed locks.",
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
    json_path = ARTIFACT_DIR / f"design_guide_no_active_primary_selector_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_no_active_primary_selector_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_primary_selector_readiness_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
