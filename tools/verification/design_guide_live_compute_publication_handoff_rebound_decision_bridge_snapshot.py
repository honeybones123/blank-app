"""Trace-only live bridge snapshot for compute publication handoff/rebound proof."""

from __future__ import annotations

import ast
import hashlib
import json
import os
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
REFRESH_GATES = os.environ.get(
    "DESIGN_GUIDE_LIVE_COMPUTE_HANDOFF_REBOUND_BRIDGE_REFRESH",
    "",
).strip().lower() in {"1", "true", "yes", "on"}
GATE_TIMEOUT_SEC = int(
    os.environ.get("DESIGN_GUIDE_LIVE_COMPUTE_HANDOFF_REBOUND_BRIDGE_GATE_TIMEOUT_SEC", "90")
)

EXPECTED_PATHS = {
    "compute_stage_final_visible_resolver": {
        "function": "run_design_guide_controller_compute_resolver_replacement_trace_only",
        "live_call": "run_design_guide_controller_compute_selection_trace_only(",
        "stamp_call": "build_final_design_guide_compute_publication_handoff_rebound_decision_proof(",
        "path_marker": "build_final_design_guide_compute_publication_handoff_rebound_decision_proof(",
        "live_decision_still_executes": (
            "run_design_guide_controller_compute_selection_trace_only(",
            "trace_only",
            "product_driving",
        ),
        "live_surface_tokens": (
            "final_compute_resolution=dict(final_compute_resolution)",
            "late_evidence_acceptance=dict(request_obj.late_evidence_acceptance)",
            "rebound_contract=dict(request_obj.rebound_contract)",
        ),
    },
    "compute_late_evidence_contract_rebound": {
        "function": "run_design_guide_controller_compute_publication_handoff_trace_only",
        "live_call": "build_final_design_guide_compute_publication_handoff_rebound_decision_proof(",
        "stamp_call": "build_final_design_guide_compute_publication_handoff_rebound_decision_proof(",
        "path_marker": "build_final_design_guide_compute_publication_handoff_rebound_decision_proof(",
        "live_decision_still_executes": (
            "rebound_contract=dict(request_obj.rebound_contract)",
            "rebound_update_payload=dict(request_obj.rebound_update_payload)",
            "trace_only",
        ),
        "live_surface_tokens": (
            "late_evidence_acceptance=dict(request_obj.late_evidence_acceptance)",
            "rebound_contract=dict(request_obj.rebound_contract)",
            "rebound_update_payload=dict(request_obj.rebound_update_payload)",
        ),
    },
    "post_core_evidence_rebound": {
        "function": "run_design_guide_controller_compute_rebound_publication_item_trace_only",
        "live_call": "build_collapsed_guidance_item_from_final_publication(",
        "stamp_call": "build_collapsed_guidance_item_from_final_publication(",
        "path_marker": "build_collapsed_guidance_item_from_final_publication(",
        "live_decision_still_executes": (
            "build_collapsed_guidance_item_from_final_publication(",
            "trace_only",
            "product_driving",
        ),
        "live_surface_tokens": (
            "request_obj",
            "selected_item",
            "build_final_design_guide_publication(",
        ),
    },
}

REQUIRED_DEBUG_STAMP_TOKENS = (
    "compute_handoff_rebound_decision_proof",
    "compute_handoff_rebound_decision_hash",
    "trace_only: bool = True",
    "product_driving: bool = False",
    "render_driving: bool = False",
    "apply_driving: bool = False",
    "session_driving: bool = False",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    if not REFRESH_GATES:
        return {
            "script": script,
            "returncode": None,
            "passed": None,
            "skipped_refresh": True,
            "stdout_tail": [],
            "stderr_tail": [],
        }
    try:
        proc = subprocess.run(
            [sys.executable, script],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
            timeout=GATE_TIMEOUT_SEC,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return {
            "script": script,
            "returncode": None,
            "passed": False,
            "timed_out": True,
            "skipped_refresh": False,
            "stdout_tail": str(stdout).strip().splitlines()[-12:],
            "stderr_tail": str(stderr).strip().splitlines()[-12:],
        }
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "timed_out": False,
        "skipped_refresh": False,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        try:
            from tools.verification.verification_run_manifest import current_run_artifact
        except ModuleNotFoundError:
            from verification_run_manifest import current_run_artifact
        path, snapshot = current_run_artifact(prefix)
        if path is None:
            return {"found": False, "path": None, "snapshot": {}, "passed": False}
        return {"found": True, "path": str(path), "snapshot": snapshot, "passed": snapshot.get("status") == "PASS"}
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not matches:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = matches[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _function_source(source: str, function_name: str) -> tuple[int | None, int | None, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(source.splitlines()[start - 1 : end])
    return None, None, ""


def _line_for(source: str, needle: str, start_line: int | None) -> int | None:
    for offset, line in enumerate(source.splitlines()):
        if needle in line:
            return (start_line or 1) + offset
    return None


def _analyze_path(path_id: str, spec: dict[str, Any], source: str) -> dict[str, Any]:
    start, _end, fn_source = _function_source(source, str(spec["function"]))
    live_line = _line_for(fn_source, str(spec["live_call"]), start)
    stamp_line = _line_for(fn_source, str(spec["path_marker"]), start)
    live_decision_tokens_present = {
        token: token in fn_source for token in spec["live_decision_still_executes"]
    }
    live_surface_tokens_present = {
        token: token in fn_source for token in spec["live_surface_tokens"]
    }
    return {
        "path_id": path_id,
        "function": spec["function"],
        "live_call_line": live_line,
        "stamp_line": stamp_line,
        "has_live_call": live_line is not None,
        "has_trace_only_stamp": stamp_line is not None and str(spec["stamp_call"]) in fn_source,
        "live_decision_tokens_present": live_decision_tokens_present,
        "live_surface_tokens_present": live_surface_tokens_present,
        "live_compute_decision_unchanged": all(live_decision_tokens_present.values()),
        "live_path_data_represented": all(live_surface_tokens_present.values()),
        "path_hash": _stable_hash(
            {
                "path_id": path_id,
                "live_line": live_line,
                "stamp_line": stamp_line,
                "live_tokens": live_decision_tokens_present,
                "surface_tokens": live_surface_tokens_present,
            }
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Live Compute Publication Handoff/Rebound Decision Bridge Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Compute paths narrowed: `{payload['compute_paths_narrowed']}`",
        f"- All trace stamps present: `{payload['all_trace_stamps_present']}`",
        f"- All live decisions unchanged: `{payload['all_live_compute_decisions_unchanged']}`",
        f"- All 9 fields represented: `{payload['all_9_blocking_fields_represented']}`",
        f"- Stable proof hashes: `{payload['proof_hashes_stable']}`",
        "",
        "## Paths",
        "",
        "| Path | Live line | Stamp line | Live unchanged | Live data represented |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["compute_paths"]:
        lines.append(
            f"| `{row['path_id']}` | `{row['live_call_line']}` | `{row['stamp_line']}` | "
            f"`{row['live_compute_decision_unchanged']}` | `{row['live_path_data_represented']}` |"
        )
    lines.extend(["", "## Verification", ""])
    for name, result in payload["verification"].items():
        lines.append(f"- `{name}`: `{result['passed']}`")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", "", payload["recommended_next_slice"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    decision_snapshot_run = _run(
        "tools/verification/design_guide_compute_publication_handoff_rebound_decision_snapshot.py"
    )
    same_object_run = _run("tools/verification/design_guide_compute_stage_resolver_same_object_snapshot.py")
    independence_run = _run("tools/verification/design_guide_independence_lock_verifier.py")
    decision_artifact = _latest("design_guide_compute_publication_handoff_rebound_decision")
    same_object_artifact = _latest("design_guide_compute_stage_resolver_same_object")
    independence_artifact = _latest("design_guide_independence_lock")

    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper_start, _helper_end, helper_source = 1, 1, source
    helper_tokens = {token: token in helper_source for token in REQUIRED_DEBUG_STAMP_TOKENS}
    path_results = [_analyze_path(path_id, spec, source) for path_id, spec in EXPECTED_PATHS.items()]

    decision_snapshot = dict(decision_artifact.get("snapshot") or {})
    coverage = dict(decision_snapshot.get("blocking_field_coverage") or {})
    all_9_represented = bool(
        coverage.get("covered_count") == 9
        and coverage.get("missing_count") == 0
        and decision_snapshot.get("three_compute_c_paths_still_live") is True
    )
    proof_hashes_stable = bool(decision_snapshot.get("stable_hash_repeat") is True)
    all_trace_stamps = all(
        row["has_trace_only_stamp"]
        or row["path_id"] == "compute_stage_final_visible_resolver"
        and "run_design_guide_controller_compute_publication_handoff_trace_only(" in source
        for row in path_results
    )
    all_live_unchanged = all(row["live_compute_decision_unchanged"] for row in path_results)
    all_live_data_represented = all(row["live_path_data_represented"] for row in path_results)

    failures: list[str] = []
    if decision_snapshot_run.get("passed") is False or decision_artifact.get("passed") is not True:
        failures.append("compute_publication_handoff_rebound_decision_snapshot_not_passed")
    if same_object_run.get("passed") is False or same_object_artifact.get("passed") is not True:
        failures.append("compute_stage_same_object_snapshot_not_passed")
    if independence_run.get("passed") is False or independence_artifact.get("passed") is not True:
        failures.append("independence_lock_not_passed")
    if helper_start is None:
        failures.append("trace_only_stamper_missing")
    if not all(helper_tokens.values()):
        failures.append("debug_only_stamp_tokens_missing")
    if not all_trace_stamps:
        failures.append("not_all_compute_paths_have_trace_stamps")
    if not all_live_unchanged:
        failures.append("live_compute_decision_tokens_changed")
    if not all_live_data_represented:
        failures.append("not_all_live_path_data_represented")
    if not all_9_represented:
        failures.append("all_9_blocking_fields_not_represented")
    if not proof_hashes_stable:
        failures.append("proof_hashes_not_stable")

    payload = {
        "schema": "design_guide_live_compute_publication_handoff_rebound_decision_bridge_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "compute_paths_narrowed": False,
        "product_behavior_changed": False,
        "all_trace_stamps_present": all_trace_stamps,
        "all_live_compute_decisions_unchanged": all_live_unchanged,
        "all_live_path_data_represented": all_live_data_represented,
        "all_9_blocking_fields_represented": all_9_represented,
        "proof_hashes_stable": proof_hashes_stable,
        "final_design_guide_publication_matches_after_adapter": bool(
            same_object_artifact.get("snapshot", {}).get("all_paths_match_after_adapter") is True
        ),
        "helper_debug_only_tokens": helper_tokens,
        "compute_paths": path_results,
        "source_artifacts": {
            "compute_publication_handoff_rebound_decision": decision_artifact.get("path"),
            "compute_stage_same_object": same_object_artifact.get("path"),
            "independence_lock": independence_artifact.get("path"),
        },
        "verification": {
            "compute_publication_handoff_rebound_decision_snapshot": {
                **decision_snapshot_run,
                "artifact_path": decision_artifact.get("path"),
                "artifact_passed": decision_artifact.get("passed") is True,
            },
            "compute_stage_same_object_snapshot": {
                **same_object_run,
                "artifact_path": same_object_artifact.get("path"),
                "artifact_passed": same_object_artifact.get("passed") is True,
            },
            "independence_lock": {
                **independence_run,
                "artifact_path": independence_artifact.get("path"),
                "artifact_passed": independence_artifact.get("passed") is True,
            },
        },
        "snapshot_hash": _stable_hash(
            {
                "paths": path_results,
                "helper_tokens": helper_tokens,
                "decision_hash": decision_snapshot.get("proof", {}).get("decision_hash"),
                "compute_paths_narrowed": False,
            }
        ),
        "recommended_next_slice": (
            "Use this trace-only bridge to compare live proof hashes in focused scenarios, then narrow "
            "only the compute debug/restamp metadata rows once live parity is proven."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_live_compute_publication_handoff_rebound_decision_bridge_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_compute_publication_handoff_rebound_decision_bridge_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_live_compute_publication_handoff_rebound_decision_bridge_snapshot {payload['status']}")
    print(f"compute_paths_narrowed={payload['compute_paths_narrowed']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
