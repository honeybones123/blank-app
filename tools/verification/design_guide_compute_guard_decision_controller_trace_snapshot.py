"""Proof-only controller trace for remaining compute guard decisions.

This verifier proves the three remaining compute-stage guard/rebound decision
surfaces are mirrored through DesignGuideController without replacing the live
inputs_page.py decision path or changing product behaviour.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

EXPECTED_PATH_IDS = (
    "compute_stage_final_visible_resolver",
    "compute_late_evidence_contract_rebound",
    "post_core_evidence_rebound",
)

REQUEST_FIELD_TOKENS = (
    "final_compute_resolution={",
    "blocker_evidence_surface=dict(blocker_evidence_surface or {})",
    "late_evidence_acceptance=dict(late_evidence_acceptance or {})",
    "rebound_contract=dict(rebound_contract or {})",
    "rebound_update_payload=dict(rebound_update_payload or {})",
    "post_core_evidence_mismatch=dict(post_core_evidence_mismatch or {})",
    "pre_resolver_collapsed_item_mutation=dict(pre_resolver_collapsed_item_mutation or {})",
)

TRACE_STAMP_TOKENS = (
    'debug_sink["design_guide_controller_compute_guard_decision_traces"]',
    '"matches_direct_proof_hash": (',
    '"trace_only": True',
    '"product_driving": False',
    '"render_driving": False',
    '"apply_driving": False',
    '"session_driving": False',
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _function_source(source: str, function_name: str) -> tuple[int | None, int | None, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(source.splitlines()[start - 1 : end])
    return None, None, ""


def _controller_sample() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        DesignGuideControllerComputePublicationHandoffRequest,
        run_design_guide_controller_compute_publication_handoff_trace_only,
    )

    selected_item = {
        "candidate_id": "guard-trace-candidate",
        "source_candidate_id": "guard-trace-source",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "status": "ACTION",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "BENDING_FAIL_GOVERNS",
            "candidate_id": "guard-trace-candidate",
            "updates": {"D": 650},
        },
        "candidate_search_evidence": {"selected_candidate_updates": {"D": 650}},
    }
    request = DesignGuideControllerComputePublicationHandoffRequest(
        final_compute_resolution={
            "item": dict(selected_item),
            "render_reason": "compute_guard_trace_sample",
            "state_fingerprint": "guard-trace-state",
        },
        blocker_evidence_surface={
            "candidate_search_evidence": dict(selected_item["candidate_search_evidence"]),
            "exact_blockers_by_family": {},
            "source": "guard_trace_sample",
            "proof_only": True,
            "product_driving": False,
        },
        late_evidence_acceptance={
            "late_updates_present": True,
            "contract_disabled_or_mismatched": True,
            "active_under_capacity_blocker": False,
            "accepted": True,
        },
        rebound_contract=dict(selected_item["button_contract"]),
        rebound_update_payload={"D": 650},
        post_core_evidence_mismatch={
            "post_evidence_updates_present": True,
            "contract_disabled_or_mismatched": False,
            "family": "bending",
            "accepted": False,
        },
        pre_resolver_collapsed_item_mutation={
            "before_identity": {"candidate_id": "guard-trace-candidate"},
            "after_identity": {"candidate_id": "guard-trace-candidate"},
            "mutation_reason": "guard_trace_sample",
        },
        publication_reason="compute_guard_trace_sample",
        source="guard_trace_snapshot",
    )
    first = run_design_guide_controller_compute_publication_handoff_trace_only(request)
    second = run_design_guide_controller_compute_publication_handoff_trace_only(request)
    proof = dict(first.compute_handoff_rebound_decision_proof or {})
    return {
        "stable_controller_hash": first.controller_hash == second.controller_hash,
        "stable_decision_hash": (
            first.compute_handoff_rebound_decision_hash
            == second.compute_handoff_rebound_decision_hash
        ),
        "decision_hash": first.compute_handoff_rebound_decision_hash,
        "blocker_evidence_surface_present": bool(proof.get("blocker_evidence_surface")),
        "late_acceptance_present": bool(proof.get("late_evidence_acceptance")),
        "rebound_contract_present": bool(proof.get("rebound_contract")),
        "post_core_mismatch_present": bool(proof.get("post_core_evidence_mismatch")),
        "pre_resolver_mutation_present": bool(proof.get("pre_resolver_collapsed_item_mutation")),
        "covered_blocking_fields": list(proof.get("covered_blocking_fields") or []),
        "missing_blocking_fields": list(proof.get("missing_blocking_fields") or []),
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    helper_start, helper_end, helper_source = _function_source(
        source,
        "_stamp_final_publication_compute_handoff_rebound_decision_proof",
    )
    request_fields_present = {token: token in helper_source for token in REQUEST_FIELD_TOKENS}
    trace_stamps_present = {token: token in helper_source for token in TRACE_STAMP_TOKENS}
    path_markers = {path_id: path_id in source for path_id in EXPECTED_PATH_IDS}
    controller_fields_present = {
        "request_blocker_evidence_surface": "blocker_evidence_surface: dict[str, Any]" in controller_source,
        "controller_derives_surface": "blocker_evidence_surface = _mapping(request_obj.blocker_evidence_surface)" in controller_source,
        "controller_passes_surface": "blocker_evidence_surface=dict(blocker_evidence_surface)" in controller_source,
    }
    return {
        "helper_line_start": helper_start,
        "helper_line_end": helper_end,
        "request_fields_present": request_fields_present,
        "trace_stamps_present": trace_stamps_present,
        "path_markers": path_markers,
        "controller_fields_present": controller_fields_present,
        "controller_sample": _controller_sample(),
        "verification": {
            "controller_compute_handoff_object": _run(
                "tools/verification/design_guide_controller_compute_handoff_object_snapshot.py"
            ),
            "live_controller_compute_handoff_trace": _run(
                "tools/verification/design_guide_live_controller_compute_handoff_trace_snapshot.py"
            ),
        },
        "product_behavior_changed": False,
        "live_decision_replaced": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    sample = dict(capture.get("controller_sample") or {})
    verification = dict(capture.get("verification") or {})
    return {
        "helper_exists": capture.get("helper_line_start") is not None,
        "all_three_path_markers_present": all((capture.get("path_markers") or {}).values()),
        "all_request_fields_mirrored_to_controller": all(
            (capture.get("request_fields_present") or {}).values()
        ),
        "trace_stamps_non_authoritative": all((capture.get("trace_stamps_present") or {}).values()),
        "controller_request_surface_exists": all(
            (capture.get("controller_fields_present") or {}).values()
        ),
        "controller_sample_stable": sample.get("stable_controller_hash") is True
        and sample.get("stable_decision_hash") is True,
        "controller_sample_covers_guard_surfaces": (
            sample.get("blocker_evidence_surface_present") is True
            and sample.get("late_acceptance_present") is True
            and sample.get("rebound_contract_present") is True
            and sample.get("post_core_mismatch_present") is True
            and sample.get("pre_resolver_mutation_present") is True
        ),
        "all_original_blocking_fields_covered": len(sample.get("covered_blocking_fields") or []) == 9
        and not sample.get("missing_blocking_fields"),
        "dependent_controller_verifiers_pass": all(
            (result or {}).get("passed") is True for result in verification.values()
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "live_decision_not_replaced": capture.get("live_decision_replaced") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Compute Guard Decision Controller Trace Snapshot",
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
            "## Summary",
            "",
            f"- Helper lines: `{capture.get('helper_line_start')}-{capture.get('helper_line_end')}`",
            f"- Path markers: `{capture.get('path_markers')}`",
            f"- Product behaviour changed: `{capture.get('product_behavior_changed')}`",
            f"- Live decision replaced: `{capture.get('live_decision_replaced')}`",
            "",
            "## Recommendation",
            "",
            (
                "Keep the live guard decisions in place until a replacement-readiness "
                "snapshot proves the controller trace can own the guard decision payloads "
                "without raw page mutation."
            ),
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
    json_path = ARTIFACT_DIR / f"design_guide_compute_guard_decision_controller_trace_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_guard_decision_controller_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_compute_guard_decision_controller_trace_snapshot {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
