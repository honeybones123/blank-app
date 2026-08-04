"""Verify live trace wiring for controller compute resolver replacement.

This proof checks that inputs_page.py now records the controller-owned compute
resolver replacement beside the current live resolver, without replacing the
product-driving resolver path.
"""

from __future__ import annotations

import ast
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


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "payload": {}}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "payload": payload,
    }


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return "\n".join(lines[node.lineno - 1 : int(getattr(node, "end_lineno", node.lineno))])
    return ""


def _build_payload() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    helper_source = _function_source(
        INPUTS_PAGE, "_stamp_design_guide_controller_compute_resolver_replacement_trace_only"
    )
    compute_handoff_source = _function_source(
        INPUTS_PAGE, "_resolve_compute_design_guidance_publication_handoff"
    )
    controller_source = _function_source(
        CONTROLLER, "run_design_guide_controller_compute_resolver_replacement_trace_only"
    )
    controller_trace = _latest("design_guide_compute_resolver_controller_replacement_trace")
    deletion_readiness = _latest("design_guide_compute_stage_resolver_deletion_readiness")
    helper_readiness = _latest("design_guide_remaining_compatibility_helper_deletion_readiness")

    source_guards = {
        "import_alias_present": (
            "run_design_guide_controller_compute_resolver_replacement_trace_only as "
            "_run_design_guide_controller_compute_resolver_replacement_trace_only"
        )
        in inputs_source,
        "helper_exists": bool(helper_source),
        "helper_calls_controller_trace": "_run_design_guide_controller_compute_resolver_replacement_trace_only(" in helper_source,
        "helper_writes_debug_only": "debug_sink[" in helper_source
        and "return response" not in helper_source
        and "return payload" not in helper_source,
        "helper_marks_trace_only": '"trace_only": True' in helper_source,
        "helper_marks_non_product_driving": '"product_driving": False' in helper_source
        and "product_driving\"] = False" in helper_source,
        "helper_marks_non_render_apply_session": all(
            token in helper_source
            for token in (
                '"render_driving": False',
                '"apply_driving": False',
                '"session_driving": False',
            )
        ),
        "live_compute_path_calls_helper": "_stamp_design_guide_controller_compute_resolver_replacement_trace_only(" in compute_handoff_source,
        "live_compute_path_still_calls_old_resolver": "final_compute_resolution = resolve_final_visible_design_guide_item(" in compute_handoff_source,
        "live_compute_path_not_replaced_by_controller": "final_compute_resolution = _run_design_guide_controller_compute_resolver_replacement_trace_only(" not in compute_handoff_source,
        "controller_replacement_function_exists": bool(controller_source),
        "controller_replacement_does_not_call_old_resolver": "resolve_final_visible_design_guide_item(" not in controller_source,
        "controller_replacement_old_resolver_input_not_required": '"old_resolver_input_required": False' in controller_source,
    }
    artifact_guards = {
        "controller_replacement_trace_snapshot_pass": controller_trace.get("status") == "PASS",
        "deletion_readiness_artifact_present": bool(deletion_readiness.get("found")),
        "helper_readiness_artifact_present": bool(helper_readiness.get("found")),
    }
    failures = [
        key
        for key, value in {**source_guards, **artifact_guards}.items()
        if not bool(value)
    ]
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "failures": failures,
        "summary": {
            "live_trace_wired": source_guards["live_compute_path_calls_helper"],
            "product_path_still_old_resolver": source_guards["live_compute_path_still_calls_old_resolver"],
            "product_path_cut_over": False,
            "trace_only_not_product_driving": (
                source_guards["helper_marks_trace_only"]
                and source_guards["helper_marks_non_product_driving"]
                and source_guards["helper_marks_non_render_apply_session"]
            ),
            "ready_to_delete_compute_resolver": False,
            "product_behavior_changed": False,
        },
        "source_guards": source_guards,
        "artifact_guards": artifact_guards,
        "latest_artifacts": {
            "controller_replacement_trace": {
                "path": controller_trace.get("path"),
                "status": controller_trace.get("status"),
            },
            "compute_stage_resolver_deletion_readiness": {
                "path": deletion_readiness.get("path"),
                "status": deletion_readiness.get("status"),
                "decision": (deletion_readiness.get("payload") or {}).get("decision")
                or (deletion_readiness.get("payload") or {}).get("summary", {}).get("decision"),
            },
            "remaining_compatibility_helper_deletion_readiness": {
                "path": helper_readiness.get("path"),
                "status": helper_readiness.get("status"),
            },
        },
        "next_safe_step": (
            "Run browser/live parity against the trace payload. Do not delete the "
            "compute resolver or compute compatibility helpers until the parity proof "
            "covers product-state scenarios."
        ),
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "summary": payload["summary"],
            "source_guards": source_guards,
            "artifact_guards": artifact_guards,
        }
    )
    return payload


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Live Compute Resolver Replacement Trace Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Snapshot hash: `{payload['snapshot_hash']}`",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in payload["summary"].items())
    lines.extend(["", "## Source Guards", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["source_guards"].items())
    lines.extend(["", "## Artifact Guards", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["artifact_guards"].items())
    lines.extend(["", "## Next Safe Step", "", str(payload["next_safe_step"]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    timestamp = payload["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_live_compute_resolver_replacement_trace_{timestamp}.json"
    report_path = AUDIT_DIR / f"design_guide_live_compute_resolver_replacement_trace_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(json.dumps({"status": payload["status"], "json": str(json_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
