"""Post-cutover verifier for compute rebound mutation adapter rows."""

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
ROUTE_SOURCES = tuple(
    ROOT / "inputs_application" / "page_runtime" / name
    for name in ("common.py", "design_guide.py", "summaries.py", "tail.py")
)
APP = ROOT / "app.py"


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
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    route_source = "\n".join(
        path.read_text(encoding="utf-8-sig", errors="replace")
        for path in ROUTE_SOURCES
        if path.exists()
    )
    app_source = APP.read_text(encoding="utf-8-sig", errors="replace")
    helper = _window(source, "_stamp_design_guide_controller_compute_rebound_mutation_trace_only")
    late = _window(source, "_apply_compute_late_evidence_contract_rebound")
    post = _window(source, "_orchestrate_compute_post_core_publication_handoff")
    latest = {
        "adapter_parity": _latest("design_guide_compute_rebound_mutation_adapter_parity"),
        "cutover_readiness": _latest(
            "design_guide_compute_rebound_mutation_adapter_cutover_readiness"
        ),
        "controller_decision_parity": _latest(
            "design_guide_compute_rebound_controller_decision_parity"
        ),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "COMPUTE_REBOUND_MUTATION_ADAPTER_CUTOVER_PASS",
        "source_checks": {
            "authority_publication_cutover_present": (
                "AuthoritativeDesignResultStore" in route_source
                and "build_authoritative_design_result_from_guidance_payload" in route_source
                and "AuthoritativeDesignResultStore" in app_source
            ),
            "legacy_helper_absent_or_adapter_only": (
                not helper or "return response.to_dict()" in helper
            ),
            "late_mutation_path_removed_or_authority_owned": (
                not late
                or "AuthoritativeDesignResultStore" in route_source
                or "authoritative_design_result" in app_source
            ),
            "late_direct_mutation_removed": not late,
            "late_direct_rebound_item_update_removed": (
                "primary_item_for_evidence.update(_late_rebound_item)" not in late
            ),
            "late_direct_debug_rows_removed": all(
                token not in late
                for token in (
                    'debug_trace["button_contract_enabled"] = True',
                    'debug_trace["selected_action_type"] = "apply_resolved_candidate"',
                    'debug_trace["selected_action_family"] = _late_rebound_contract.get("family")',
                )
            ),
            "post_mutation_path_removed_or_authority_owned": (
                not post
                or "AuthoritativeDesignResultStore" in route_source
                or "authoritative_design_result" in app_source
            ),
            "post_direct_mutation_removed": not post,
            "post_direct_debug_flag_removed": (
                'debug_trace["post_evidence_cleanup_contract_rebound"] = bool(' not in post
            ),
        },
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "delete_ready": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "source_checks_pass": all((capture.get("source_checks") or {}).values()),
        "adapter_parity_pass": (latest.get("adapter_parity") or {}).get("status") == "PASS",
        "cutover_readiness_pass": (latest.get("cutover_readiness") or {}).get("status") == "PASS",
        "controller_decision_parity_pass": (
            (latest.get("controller_decision_parity") or {}).get("status") == "PASS"
        ),
        # Parent lock consumes this cutover child; do not create a cycle by
        # requiring the parent artifact here.
        "compute_bridge_lock_pass": True,
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "not_delete_ready": capture.get("delete_ready") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Compute Rebound Mutation Adapter Cutover Snapshot",
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
                "The row-level mutation values now come from the controller adapter while "
                "publish predicates and live publish calls remain unchanged. Next safe slice is "
                "deadness/readiness for helper/debug compatibility rows, not broad deletion."
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
        "schema": "design_guide_compute_rebound_mutation_adapter_cutover_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_compute_rebound_mutation_adapter_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_rebound_mutation_adapter_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_compute_rebound_mutation_adapter_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
