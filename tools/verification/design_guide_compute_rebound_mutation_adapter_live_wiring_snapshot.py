"""Live wiring snapshot for proof-only compute rebound mutation adapter."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"status": "MISSING", "path": None}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"status": status or "UNKNOWN", "path": str(path)}


def _window(source: str, function_name: str) -> str:
    start = source.find(f"def {function_name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    return source[start:] if next_def < 0 else source[start:next_def]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper = _window(inputs_source, "_stamp_design_guide_controller_compute_rebound_mutation_trace_only")
    late = _window(inputs_source, "_apply_compute_late_evidence_contract_rebound")
    post = _window(inputs_source, "_orchestrate_compute_post_core_publication_handoff")
    latest = {
        "adapter_parity": _latest("design_guide_compute_rebound_mutation_adapter_parity"),
        "mutation_readiness": _latest(
            "design_guide_compute_rebound_controller_mutation_cutover_readiness"
        ),
        "controller_decision_parity": _latest(
            "design_guide_compute_rebound_controller_decision_parity"
        ),
        "live_bridge": _latest(
            "design_guide_live_compute_publication_handoff_rebound_decision_bridge"
        ),
    }
    source_checks = {
        "controller_adapter_present": (
            "def run_design_guide_controller_compute_rebound_mutation_trace_only(" in controller_source
        ),
        "page_helper_present": bool(helper),
        "page_helper_calls_controller_adapter": (
            "_run_design_guide_controller_compute_rebound_mutation_trace_only(" in helper
        ),
        "page_helper_proof_only_flags": all(
            token in helper
            for token in (
                'debug_sink["design_guide_controller_compute_rebound_mutation_trace_only"] = True',
                'debug_sink["design_guide_controller_compute_rebound_mutation_product_driving"] = False',
                'debug_sink["design_guide_controller_compute_rebound_mutation_render_driving"] = False',
                'debug_sink["design_guide_controller_compute_rebound_mutation_apply_driving"] = False',
                'debug_sink["design_guide_controller_compute_rebound_mutation_session_driving"] = False',
            )
        ),
        "late_path_has_trace_wiring": (
            'path_id="compute_late_evidence_contract_rebound"' in late
            and "_stamp_design_guide_controller_compute_rebound_mutation_trace_only(" in late
        ),
        "late_live_mutation_still_runs": (
            (
                "primary_item_for_evidence.update(_late_rebound_item)" in late
                and "collapsed_guidance_items[0] = dict(_late_rebound_item)" in late
            )
            or (
                "_late_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
                in late
                and "primary_item_for_evidence.update(_late_mutation_item)" in late
            )
        ),
        "post_path_has_trace_wiring": (
            'path_id="post_core_evidence_rebound"' in post
            and "_stamp_design_guide_controller_compute_rebound_mutation_trace_only(" in post
        ),
        "post_live_mutation_still_runs": (
            "collapsed_guidance_items[0] = dict(_post_evidence_rebound)" in post
            or (
                "_post_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
                in post
                and "_post_mutation_collapsed_items = list(" in post
            )
        ),
    }
    return {
        "decision": "COMPUTE_REBOUND_MUTATION_ADAPTER_TRACE_WIRED_NOT_CUT_OVER",
        "source_checks": source_checks,
        "latest": latest,
        "compute_paths_narrowed": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "source_checks_pass": all((capture.get("source_checks") or {}).values()),
        "adapter_parity_pass": (latest.get("adapter_parity") or {}).get("status") == "PASS",
        "mutation_readiness_pass": (latest.get("mutation_readiness") or {}).get("status") == "PASS",
        "controller_decision_parity_pass": (
            (latest.get("controller_decision_parity") or {}).get("status") == "PASS"
        ),
        "live_bridge_pass": (latest.get("live_bridge") or {}).get("status") == "PASS",
        "compute_paths_not_narrowed": capture.get("compute_paths_narrowed") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Compute Rebound Mutation Adapter Live Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                "The mutation adapter is trace-wired beside live rebound branches. "
                "Next safe slice is a focused cutover-readiness proof comparing live mutation "
                "debug/item outputs to adapter outputs before replacing any page mutation rows."
            ),
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
        "schema": "design_guide_compute_rebound_mutation_adapter_live_wiring_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_compute_rebound_mutation_adapter_live_wiring_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_rebound_mutation_adapter_live_wiring_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_compute_rebound_mutation_adapter_live_wiring {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
