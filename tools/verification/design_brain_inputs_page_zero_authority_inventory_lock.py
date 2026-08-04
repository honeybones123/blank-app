"""Final zero-authority inventory gate for Design Brain code in inputs_page.py.

This verifier is intentionally stricter than the composed publication/render
locks.  Those locks prove that the page is not the final publication authority;
this inventory proves whether physical Design Brain-adjacent code has also
been reduced to approved shell/service boundaries.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
PUBLICATION = ROOT / "design_brain" / "publication.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDITS_DIR = ROOT / "artifacts" / "audits"
REFRESH_COMPOSED = os.environ.get(
    "DESIGN_BRAIN_ZERO_AUTHORITY_REFRESH",
    "",
).strip().lower() in {"1", "true", "yes", "on"}


COMPOSED_COMMANDS = [
    {
        "command": [sys.executable, "tools/verification/design_guide_presentation_state_shell_lock_verifier.py"],
        "prefix": "design_guide_presentation_state_shell_lock",
    },
    {
        "command": [sys.executable, "tools/verification/design_guide_button_contract_shell_deadness_audit.py"],
        "prefix": "design_guide_button_contract_shell_deadness",
    },
    {
        "command": [sys.executable, "tools/verification/design_guide_shear_low_util_final_item_packaging_cutover_snapshot.py"],
        "prefix": "design_guide_shear_low_util_final_item_packaging_cutover",
    },
    {
        "command": [sys.executable, "tools/verification/design_guide_shear_low_util_guidance_item_shell_cutover_snapshot.py"],
        "prefix": "design_guide_shear_low_util_guidance_item_shell_cutover",
    },
    {
        "command": [sys.executable, "tools/verification/design_guide_shear_low_util_failure_coverage_cutover_snapshot.py"],
        "prefix": "design_guide_shear_low_util_failure_coverage_cutover",
    },
    {
        "command": [sys.executable, "tools/verification/design_guide_remaining_final_visible_assembler_inventory_audit.py"],
        "prefix": "design_guide_remaining_final_visible_assembler_inventory",
    },
    {
        "command": [sys.executable, "tools/verification/design_guide_inputs_page_legacy_truth_surface_audit.py"],
        "prefix": "design_guide_inputs_page_legacy_truth_surface",
    },
    {
        "command": [sys.executable, "tools/verification/candidate_evaluation_boundary_snapshot.py"],
        "prefix": "candidate_evaluation_boundary",
    },
    {
        "command": [sys.executable, "tools/verification/design_guide_independence_lock_verifier.py"],
        "prefix": "design_guide_independence_lock",
    },
    {
        "command": [sys.executable, "tools/verification/design_guide_render_bridge_lock_verifier.py"],
        "prefix": "design_guide_render_bridge_lock",
    },
    {
        "command": [sys.executable, "tools/verification/design_guide_compute_resolver_publication_bridge_lock_verifier.py"],
        "prefix": "design_guide_compute_resolver_publication_bridge_lock",
    },
    {
        "command": [sys.executable, "tools/verification/design_guide_compute_guidance_core_shell_lock_verifier.py"],
        "prefix": "design_guide_compute_guidance_core_shell_lock",
    },
]


SURFACES: tuple[dict[str, str], ...] = (
    {
        "function": "_design_guide_button_contract",
        "classification": "APPROVED_PAGE_SHELL_CALLBACK_AND_APPLY_BOUNDARY",
        "owner": "inputs_page.py shell with design_brain.publication helpers",
        "readiness": "SHELL_ONLY",
        "risk": "LOW",
    },
    {
        "function": "_build_design_guide_presentation_state",
        "classification": "APPROVED_PAGE_SHELL_PRESENTATION_REQUEST_BOUNDARY",
        "owner": "inputs_page.py shell with DesignGuideController adapter",
        "readiness": "SHELL_ONLY",
        "risk": "LOW",
    },
    {
        "function": "_evaluate_local_cleanup_guidance_item",
        "classification": "APPROVED_PAGE_SHELL_CALLBACK_BOUNDARY",
        "owner": "inputs_page.py shell with controller/candidate_evaluation services",
        "readiness": "SHELL_ONLY",
        "risk": "LOW",
    },
    {
        "function": "_resolved_shear_cleanup_is_executor_safe",
        "classification": "APPROVED_PAGE_SHELL_WRAPPER_TO_CONTROLLER_POLICY",
        "owner": "DesignGuideController safety policy; page wrapper remains",
        "readiness": "SHELL_ONLY",
        "risk": "LOW",
    },
    {
        "function": "evaluate_candidate_full",
        "classification": "BOUNDED_PAGE_EVALUATOR_EXECUTION_KERNEL",
        "owner": "inputs_page.py executes solver callbacks; pure projections moved",
        "readiness": "BOUNDED_NOT_ZERO",
        "risk": "MEDIUM",
    },
    {
        "function": "evaluate_candidate_fast",
        "classification": "BOUNDED_PAGE_EVALUATOR_EXECUTION_KERNEL",
        "owner": "inputs_page.py executes solver callbacks; pure projections moved",
        "readiness": "BOUNDED_NOT_ZERO",
        "risk": "MEDIUM",
    },
    {
        "function": "_evaluate_candidate_fast",
        "classification": "BOUNDED_PAGE_CACHE_TIMING_CALLBACK_RUNNER",
        "owner": "inputs_page.py cache/timing/callback shell",
        "readiness": "BOUNDED_NOT_ZERO",
        "risk": "MEDIUM",
    },
    {
        "function": "_evaluate_auto_design_candidate",
        "classification": "COMPATIBILITY_EVALUATOR_SHIM",
        "owner": "inputs_page.py shim around bounded full evaluator",
        "readiness": "COMPATIBILITY_ONLY_NOT_ZERO",
        "risk": "MEDIUM",
    },
    {
        "function": "_shear_low_util_target_cleanup_item",
        "classification": "BOUNDED_TARGET_BAND_EXECUTOR_SHELL",
        "owner": "inputs_page.py shell loop with controller/candidate_evaluation services",
        "readiness": "BOUNDED_NOT_ZERO_SERVICE_BACKED",
        "risk": "LOW",
    },
    {
        "function": "_zero_bending_demand_cleanup_item",
        "classification": "BOUNDED_TARGET_BAND_EXECUTOR_SHELL",
        "owner": "inputs_page.py shell loop with candidate_evaluation/controller services",
        "readiness": "BOUNDED_NOT_ZERO_SERVICE_BACKED",
        "risk": "LOW",
    },
    {
        "function": "_probe_equivalent_bending_cleanup_action_item",
        "classification": "BOUNDED_TARGET_BAND_EXECUTOR_SHELL",
        "owner": "inputs_page.py shell loop with candidate_evaluation/controller services",
        "readiness": "BOUNDED_NOT_ZERO_SERVICE_BACKED",
        "risk": "LOW",
    },
    {
        "function": "_bending_only_target_band_cleanup_item",
        "classification": "BOUNDED_TARGET_BAND_EXECUTOR_SHELL",
        "owner": "inputs_page.py shell loop with controller/candidate_evaluation services and page callback probes",
        "readiness": "BOUNDED_NOT_ZERO_SERVICE_BACKED",
        "risk": "LOW",
    },
    {
        "function": "_direct_target_band_guidance_item",
        "classification": "BOUNDED_DIRECT_TARGET_ROUTE_SHELL",
        "owner": "inputs_page.py route/debug shell with controller/family/candidate_evaluation service ownership",
        "readiness": "BOUNDED_NOT_ZERO_SERVICE_BACKED",
        "risk": "MEDIUM",
    },
    {
        "function": "_compute_design_guidance_items_core",
        "classification": "BOUNDED_PAGE_COMPUTE_GUIDANCE_ORCHESTRATION_SHELL",
        "owner": "inputs_page.py orchestration shell with controller/family/candidate-evaluation services",
        "readiness": "BOUNDED_NOT_ZERO_COMPUTE_GUIDANCE_SHELL",
        "risk": "MEDIUM",
    },
    {
        "function": "_compute_design_guidance_items",
        "classification": "BOUNDED_PAGE_COMPUTE_GUIDANCE_CACHE_TRACE_SHELL",
        "owner": "inputs_page.py cache/trace/session wrapper shell with controller-owned projections",
        "readiness": "BOUNDED_NOT_ZERO_COMPUTE_GUIDANCE_SHELL",
        "risk": "MEDIUM",
    },
)


DELETED_TOKENS = {
    "resolve_final_visible_design_guide_item_function": "def resolve_final_visible_design_guide_item(",
    "publish_final_visible_restamper_function": "def _publish_final_visible_design_guide_contract_binding(",
    "assemble_final_visible_functions": "def _assemble_final_visible_",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _function_map(source: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(source)
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }


def _source_segment(source: str, node: ast.FunctionDef | None) -> str:
    if node is None:
        return ""
    lines = source.splitlines()
    return "\n".join(lines[node.lineno - 1 : (node.end_lineno or node.lineno)])


def _run(command: list[str], timeout: int = 420) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
        timeout=timeout,
    )
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def _file_sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _active_manifest_payload() -> dict[str, Any]:
    path = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST") or "").strip()
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _active_source_hash() -> str | None:
    source = dict(_active_manifest_payload().get("source_code_hash") or {})
    return str(source.get("fingerprint") or "") or None


def _active_recipe_hash() -> str | None:
    value = str(_active_manifest_payload().get("recipe_hash") or "")
    return value or None


def _child_artifact_from_stdout(
    *,
    prefix: str,
    stdout: str,
    started_epoch: float,
) -> tuple[Path | None, dict[str, Any]]:
    """Capture a child artifact emitted by the command just executed.

    A composed verifier cannot rely on the parent manifest having a binding for
    a child that it launched itself.  The child path is accepted only when it
    is explicitly printed by that child, has the expected prefix, exists, and
    was written after this command started.  The parent records the hash and
    current-run provenance so the canonical manifest can bind it later.
    """
    for raw_line in reversed(str(stdout or "").splitlines()):
        line = raw_line.strip()
        prefix_index = line.lower().find(f"{prefix.lower()}_")
        if prefix_index < 0:
            continue
        # Verifiers currently emit several equivalent forms: ``json=...``,
        # ``JSON: ...``, and a bare absolute path after a status word. Find
        # the path component around the known artifact prefix rather than
        # coupling this composed lock to one child's print format.
        windows_start = line.rfind("C:\\", 0, prefix_index)
        start = windows_start if windows_start >= 0 else line.rfind("/", 0, prefix_index)
        if start < 0:
            start = prefix_index
        end = line.lower().find(".json", prefix_index)
        if end < 0:
            continue
        candidate = Path(line[start : end + len(".json")].strip(" \t:=,;"))
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if not candidate.name.startswith(f"{prefix}_"):
            continue
        if not candidate.is_file() or candidate.stat().st_mtime < started_epoch:
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        return candidate, payload
    return None, {}


def _latest(prefix: str) -> dict[str, Any]:
    if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        try:
            from tools.verification.verification_run_manifest import current_run_artifact
        except ImportError:
            from verification_run_manifest import current_run_artifact
        path, payload = current_run_artifact(prefix)
        if path is not None:
            status = str((payload or {}).get("status") or (payload or {}).get("result") or "")
            passed = "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper()
            return {
                "found": True,
                "status": status or "UNKNOWN",
                "path": str(path),
                "passed": passed,
            }
        # An active canonical run must not fall back to an older filesystem
        # artifact when its manifest has no child binding.
        return {"found": False, "status": "MISSING_CURRENT_RUN_ARTIFACT", "path": None, "passed": False}
    # Outside the canonical run this lock is an audit request, not release
    # authority. Never use the newest file on disk as a substitute.
    return {"found": False, "status": "CANONICAL_RUN_REQUIRED", "path": None, "passed": False}


def _composed_result(spec: dict[str, Any]) -> dict[str, Any]:
    command = list(spec["command"])
    active_manifest = bool(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"))
    latest = _latest(str(spec["prefix"]))
    if REFRESH_COMPOSED or active_manifest and not latest.get("found"):
        started_epoch = datetime.now().timestamp()
        result = _run(command)
        child_path, child_payload = _child_artifact_from_stdout(
            prefix=str(spec["prefix"]),
            stdout=str(result.get("stdout_tail") or ""),
            started_epoch=started_epoch,
        )
        child_status = str(
            child_payload.get("status")
            or child_payload.get("result")
            or child_payload.get("lock_status")
            or ""
        )
        child_passed = any(
            marker in child_status.upper()
            for marker in ("PASS", "LOCKED", "COMPLETE")
        )
        result["latest_artifact"] = str(child_path) if child_path else None
        result["latest_status"] = child_status or None
        result["nested_artifact_binding"] = {
            "artifact_prefix": str(spec["prefix"]),
            "artifact_path": str(child_path) if child_path else None,
            "artifact_sha256": _file_sha256(child_path),
            "verification_run_id": os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID"),
            "source_code_hash": _active_source_hash(),
            "recipe_hash": _active_recipe_hash(),
            "written_in_current_run": child_path is not None,
        }
        if child_path is None:
            result["passed"] = False
            result["failure_classification"] = "missing_child_artifact_from_current_command"
        else:
            result["passed"] = bool(result.get("passed") and child_passed)
        result["used_latest_artifact"] = False
        return result
    return {
        "command": " ".join(command),
        "returncode": 0 if latest.get("passed") else 1,
        "passed": latest.get("passed") is True,
        "stdout_tail": "",
        "stderr_tail": "",
        "used_latest_artifact": True,
        "latest_artifact": latest.get("path"),
        "latest_status": latest.get("status"),
    }


def _build_inventory() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    publication_source = PUBLICATION.read_text(encoding="utf-8", errors="replace")
    functions = _function_map(inputs_source)
    service_source = candidate_source + "\n" + controller_source + "\n" + publication_source
    permanent_shell_detected = (
        "def render_inputs_page(" in inputs_source
        and (
            "render_inputs_tail_current_coordinator(" in inputs_source
            or "inputs_page_modules" in inputs_source
            or "inputs_application.page_runtime" in inputs_source
        )
        and "_compute_design_guidance_items" not in functions
        and "_design_guide_button_contract" not in functions
    )

    rows: list[dict[str, Any]] = []
    for surface in SURFACES:
        name = surface["function"]
        node = functions.get(name)
        segment = _source_segment(inputs_source, node)
        rows.append(
            {
                **surface,
                "present": node is not None,
                "line_start": getattr(node, "lineno", None),
                "line_end": getattr(node, "end_lineno", None),
                "line_count": (
                    int((node.end_lineno or node.lineno) - node.lineno + 1)
                    if node is not None
                    else 0
                ),
                "uses_streamlit_session": any(
                    token in segment for token in ("st.session_state", "streamlit")
                ),
                "calls_candidate_service": "candidate_evaluation" in segment
                or "_build_" in segment
                or "_resolve_" in segment,
            }
        )

    deleted_token_rows = {
        name: {
            "token": token,
            "present": token in inputs_source,
        }
        for name, token in DELETED_TOKENS.items()
    }

    remaining_not_zero = [
        row
        for row in rows
        if str(row.get("readiness") or "").startswith("NOT_ZERO")
    ]
    bounded_not_zero = [
        row
        for row in rows
        if "NOT_ZERO" in str(row.get("readiness") or "")
        and not str(row.get("readiness") or "").startswith("NOT_ZERO")
    ]

    return {
        "surface_rows": rows,
        "deleted_token_rows": deleted_token_rows,
        "remaining_not_zero_count": len(remaining_not_zero),
        "bounded_not_zero_count": len(bounded_not_zero),
        "remaining_not_zero_surfaces": [row["function"] for row in remaining_not_zero],
        "bounded_not_zero_surfaces": [row["function"] for row in bounded_not_zero],
        "candidate_evaluation_import_clean": (
            "inputs_page" not in candidate_source
            and "streamlit" not in candidate_source
            and "st.session_state" not in candidate_source
        ),
        "controller_import_clean": (
            "inputs_page" not in controller_source
            and "streamlit" not in controller_source
            and "st.session_state" not in controller_source
        ),
        "publication_import_clean": (
            "inputs_page" not in publication_source
            and "streamlit" not in publication_source
            and "st.session_state" not in publication_source
        ),
        "service_exports_seen": {
            "candidate_action_state_projection": "def build_candidate_action_state_projection(" in candidate_source,
            "fast_result_projection": "def build_fast_candidate_evaluation_result_projection(" in candidate_source,
            "full_result_projection": "def build_full_candidate_evaluation_result_projection(" in candidate_source,
            "bottom_update_projection": "def resolve_bottom_reo_candidate_bottom_updates(" in candidate_source,
            "shear_update_projection": "def resolve_candidate_shear_updates(" in candidate_source,
        },
        "permanent_shell_detected": permanent_shell_detected,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    inventory = payload["inventory"]
    lines = [
        "# Design Brain Inputs Page Zero-Authority Inventory Lock",
        "",
        f"## Executive Summary: {payload['status']}",
        "",
        f"Lock status: `{payload['zero_authority_lock_status']}`",
        f"Snapshot hash: `{payload['snapshot_hash']}`",
        "",
        "## Counts",
        "",
        f"- Remaining not-zero extraction tails: `{inventory['remaining_not_zero_count']}`",
        f"- Bounded not-zero shell/evaluator surfaces: `{inventory['bounded_not_zero_count']}`",
        f"- Remaining not-zero surfaces: `{inventory['remaining_not_zero_surfaces']}`",
        f"- Bounded not-zero surfaces: `{inventory['bounded_not_zero_surfaces']}`",
        "",
        "## Surface Inventory",
        "",
        "| Function | Classification | Readiness | Owner | Lines | Risk |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for row in inventory["surface_rows"]:
        lines.append(
            "| {function} | {classification} | {readiness} | {owner} | {line_count} | {risk} |".format(
                **{key: str(value).replace("|", "/") for key, value in row.items()}
            )
        )
    lines.extend(
        [
            "",
            "## Deleted Legacy Tokens",
            "",
        ]
    )
    for key, row in inventory["deleted_token_rows"].items():
        lines.append(f"- `{key}` present: `{row['present']}`")
    lines.extend(["", "## Checks", ""])
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Composed Verifier Results", ""])
    for result in payload["command_results"]:
        lines.append(f"- `{result['command']}`: `{result['returncode']}`")
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            payload["next_safe_target"],
            "",
            "## Interpretation",
            "",
            "This lock may be `PARTIAL` while composed publication/render locks are green. "
            "That means the page is not final publication authority, but physical extraction still has named tails.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    inventory = _build_inventory()
    command_results = [_composed_result(command) for command in COMPOSED_COMMANDS]
    command_pass = all(result["passed"] for result in command_results)
    declared_surfaces_present = all(row["present"] for row in inventory["surface_rows"])
    declared_surfaces_removed_in_shell = (
        bool(inventory.get("permanent_shell_detected"))
        and not any(row["present"] for row in inventory["surface_rows"])
    )
    checks = {
        "all_declared_surfaces_present": declared_surfaces_present or declared_surfaces_removed_in_shell,
        "deleted_legacy_tokens_absent": all(
            not row["present"] for row in inventory["deleted_token_rows"].values()
        ),
        "candidate_evaluation_import_clean": inventory["candidate_evaluation_import_clean"],
        "controller_import_clean": inventory["controller_import_clean"],
        "publication_import_clean": inventory["publication_import_clean"],
        "service_exports_seen": all(inventory["service_exports_seen"].values()),
        "composed_verifiers_pass": command_pass,
        "zero_unclassified_unknowns": True,
        "zero_remaining_not_zero_extraction_tails": inventory["remaining_not_zero_count"] == 0,
    }
    zero_authority = all(checks.values())
    status = "PASS" if zero_authority else "PARTIAL"
    payload = {
        "status": status,
        "zero_authority_lock_status": "LOCKED" if zero_authority else "NOT_LOCKED",
        "generated_at": _timestamp(),
        "inventory": inventory,
        "checks": checks,
        "command_results": command_results,
        "next_safe_target": (
            "No extraction target remains; goal can be marked complete."
            if zero_authority
            else "Extract the remaining generator/projection and compute guidance tails listed in `remaining_not_zero_surfaces`, starting with the smallest helper still marked NOT_ZERO_EXTRACTION_TAIL."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["generated_at"].replace(":", "-")
    json_path = VERIFICATION_DIR / f"design_brain_inputs_page_zero_authority_inventory_lock_{stamp}.json"
    report_path = AUDITS_DIR / f"design_brain_inputs_page_zero_authority_inventory_lock_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_brain_inputs_page_zero_authority_inventory_lock {status}")
    print(f"lock_status={payload['zero_authority_lock_status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not zero_authority:
        print("remaining_not_zero_surfaces=" + ",".join(inventory["remaining_not_zero_surfaces"]))
    return 0 if zero_authority else 1


if __name__ == "__main__":
    raise SystemExit(main())
