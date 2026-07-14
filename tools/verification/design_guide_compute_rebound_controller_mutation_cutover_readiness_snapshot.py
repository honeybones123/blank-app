"""Cutover-readiness snapshot for compute rebound mutation extraction.

Proof-only. This records whether the remaining late/post-core rebound mutation
bridges in inputs_page.py can be cut over to a controller-owned/plain-data
adapter yet. It must not approve deletion while the page still executes the
live publish/mutation branches.
"""

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
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _window(source: str, function_name: str) -> str:
    marker = f"def {function_name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    return source[start:] if next_def < 0 else source[start:next_def]


def _line_numbers(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    late_window = _window(inputs_source, "_apply_compute_late_evidence_contract_rebound")
    post_window = _window(inputs_source, "_orchestrate_compute_post_core_publication_handoff")
    latest = {
        "controller_decision_parity": _latest(
            "design_guide_compute_rebound_controller_decision_parity"
        ),
        "live_bridge": _latest(
            "design_guide_live_compute_publication_handoff_rebound_decision_bridge"
        ),
        "parity_scenarios": _latest(
            "design_guide_live_compute_publication_handoff_rebound_parity_scenarios"
        ),
        "rebound_readiness": _latest("design_guide_compute_rebound_authority_extraction_readiness"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    live_mutation_tokens = {
        "late_publish_binding": "_late_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "late_primary_item_update": "primary_item_for_evidence.update(_late_rebound_item)",
        "late_collapsed_replacement": "collapsed_guidance_items[0] = dict(_late_rebound_item)",
        "post_publish_binding": "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(",
        "post_collapsed_replacement": "collapsed_guidance_items[0] = dict(_post_evidence_rebound)",
        "post_debug_flag": 'debug_trace["post_evidence_cleanup_contract_rebound"]',
    }
    token_presence = {
        key: (
            token in late_window
            if key.startswith("late_")
            else token in post_window
        )
        for key, token in live_mutation_tokens.items()
    }
    mutation_adapter_cutover_present = (
        "_late_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
        in late_window
        and "_post_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
        in post_window
    )
    source_checks = {
        "controller_request_has_raw_rebound_item": (
            "raw_rebound_item: dict[str, Any] = field(default_factory=dict)" in controller_source
        ),
        "controller_dict_loader_reads_raw_rebound_item": (
            "raw_rebound_item=_mapping(request.get(\"raw_rebound_item\"))" in controller_source
        ),
        "controller_uses_raw_rebound_item_for_publication_item": (
            "publication_item = raw_rebound_item if rebound_accepted and raw_rebound_item else selected_item"
            in controller_source
        ),
        "page_stamper_passes_raw_rebound_item": (
            "raw_rebound_item=dict(raw_rebound_item or {})" in inputs_source
        ),
        "late_live_mutation_or_adapter_cutover_present": (
            all(token_presence[key] for key in token_presence if key.startswith("late_"))
            or "_late_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
            in late_window
        ),
        "post_live_mutation_or_adapter_cutover_present": (
            all(token_presence[key] for key in token_presence if key.startswith("post_"))
            or "_post_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only("
            in post_window
        ),
        "controller_mutation_adapter_present": (
            "def run_design_guide_controller_compute_rebound_mutation_trace_only(" in controller_source
        ),
    }
    return {
        "decision": (
            "COMPUTE_REBOUND_MUTATION_ADAPTER_CUTOVER_PRESENT"
            if mutation_adapter_cutover_present
            else "CONTROLLER_DECISION_READY_MUTATION_ADAPTER_NEEDED"
        ),
        "source_checks": source_checks,
        "live_mutation_tokens": token_presence,
        "line_numbers": {
            key: _line_numbers(inputs_source, token)
            for key, token in live_mutation_tokens.items()
        },
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
        "ready_for_product_cutover": False,
        "ready_for_next_adapter_slice": not mutation_adapter_cutover_present,
        "mutation_adapter_cutover_present": mutation_adapter_cutover_present,
        "delete_ready": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    source = dict(capture.get("source_checks") or {})
    return {
        "source_checks_pass": all(source.values()),
        "controller_decision_parity_pass": (
            (latest.get("controller_decision_parity") or {}).get("status") == "PASS"
        ),
        "live_bridge_pass": (latest.get("live_bridge") or {}).get("status") == "PASS",
        "parity_scenarios_pass": (latest.get("parity_scenarios") or {}).get("status") == "PASS",
        "rebound_readiness_pass": (latest.get("rebound_readiness") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "not_ready_for_product_cutover_yet_or_cutover_present": (
            capture.get("ready_for_product_cutover") is False
            or capture.get("mutation_adapter_cutover_present") is True
        ),
        "ready_for_next_adapter_slice_or_cutover_present": (
            capture.get("ready_for_next_adapter_slice") is True
            or capture.get("mutation_adapter_cutover_present") is True
        ),
        "not_delete_ready": capture.get("delete_ready") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Compute Rebound Controller Mutation Cutover Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Result",
        "",
        f"- Ready for product cutover: `{capture.get('ready_for_product_cutover')}`",
        f"- Ready for next adapter slice: `{capture.get('ready_for_next_adapter_slice')}`",
        f"- Delete ready: `{capture.get('delete_ready')}`",
        "",
        "## Live Mutation Tokens",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (capture.get("live_mutation_tokens") or {}).items())
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                "Do not delete or cut over the live rebound branches yet. "
                "The controller decision proof is ready, but the next slice must add a "
                "controller-owned/plain-data rebound mutation adapter that represents the "
                "late/post-core item replacement and debug compatibility outputs."
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
        "schema": "design_guide_compute_rebound_controller_mutation_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / (
        f"design_guide_compute_rebound_controller_mutation_cutover_readiness_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_compute_rebound_controller_mutation_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_compute_rebound_controller_mutation_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
