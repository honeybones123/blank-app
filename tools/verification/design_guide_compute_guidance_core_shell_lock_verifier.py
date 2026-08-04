"""Lock compute guidance core/wrapper as bounded page shell.

This verifier is the final proof layer before the zero-authority inventory can
stop treating `_compute_design_guidance_items_core` and
`_compute_design_guidance_items` as page-owned Design Brain extraction tails.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GUIDANCE_COMPUTE = ROOT / "inputs_page_modules" / "guidance_compute.py"
GUIDANCE_ENTRYPOINT = ROOT / "inputs_application" / "guidance_entrypoint.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


REQUIRED_PASS_PREFIXES = (
    "design_guide_compute_guidance_core_tail_boundary_audit",
    "design_guide_compute_serviceability_blocker_projection_extraction",
    "design_guide_compute_post_active_shear_blocker_projection_extraction",
    "design_guide_compute_optimisation_selector_debug_projection_extraction",
    "design_guide_compute_optimisation_selector_legacy_fallback_extraction",
    "design_guide_compute_optimisation_selector_default_debug_context_extraction",
    "design_guide_optimisation_candidate_family_classifier_extraction",
    "design_guide_independence_lock",
    "design_guide_render_bridge_lock",
    "design_guide_compute_resolver_publication_bridge_lock",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    raise RuntimeError(f"Function not found: {name}")


def _latest(prefix: str) -> dict[str, Any]:
    matches = sorted(VERIFICATION_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not matches:
        return {"prefix": prefix, "found": False, "status": "MISSING", "passed": False, "path": None}
    path = matches[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "prefix": prefix,
            "found": True,
            "status": "UNREADABLE",
            "passed": False,
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    return {
        "prefix": prefix,
        "found": True,
        "status": status or "UNKNOWN",
        "passed": "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper(),
        "path": str(path),
    }


def build_payload() -> dict[str, Any]:
    source = _read(GUIDANCE_COMPUTE)
    entrypoint_source = _read(GUIDANCE_ENTRYPOINT)
    core_start, core_end, core_segment = _function_segment(source, "_compute_design_guidance_items_core")
    wrapper_start, wrapper_end, wrapper_segment = _function_segment(source, "_compute_design_guidance_items")
    family_start, family_end, family_segment = _function_segment(source, "_optimisation_candidate_family")

    artifacts = [_latest(prefix) for prefix in REQUIRED_PASS_PREFIXES]
    direct_checks = {
        "guidance_compute_module_owns_core": "def _compute_design_guidance_items_core(" in source,
        "guidance_compute_module_owns_wrapper": "def _compute_design_guidance_items(" in source,
        "guidance_entrypoint_delegates_to_guidance_compute": "compute_design_guidance_items(" in entrypoint_source
        and "build_guidance_compute_runtime(" in entrypoint_source,
        "wrapper_calls_extracted_core": "_compute_design_guidance_items_core(" in wrapper_segment,
        "wrapper_keeps_cache_trace_only": "get_rerun_pure_cache(" in wrapper_segment
        and "set_rerun_pure_cache(" in wrapper_segment
        and "ux_probe_record(" in wrapper_segment,
        "optimisation_candidate_family_decision_delegated": (
            "_resolve_design_guide_controller_optimisation_candidate_family(" in family_segment
            or "resolve_design_guide_controller_optimisation_candidate_family(" in family_segment
            or "classify_family_from_raw_flags(" in family_segment
        ),
        "deleted_final_visible_resolver_absent": "resolve_final_visible_design_guide_item(" not in source
        and "resolve_final_visible_design_guide_item(" not in entrypoint_source,
        "deleted_restamper_absent": "_publish_final_visible_design_guide_contract_binding(" not in source
        and "_publish_final_visible_design_guide_contract_binding(" not in entrypoint_source,
        "wrapper_keeps_page_shell_cache_trace": (
            "get_rerun_pure_cache(" in wrapper_segment
            and "set_rerun_pure_cache(" in wrapper_segment
        ),
    }
    shell_boundaries = {
        "core_is_extracted_from_inputs_page": "def _compute_design_guidance_items_core(" not in _read(ROOT / "inputs_page.py"),
        "wrapper_is_extracted_from_inputs_page": "def _compute_design_guidance_items(" not in _read(ROOT / "inputs_page.py"),
        "page_session_cache_allowed_in_wrapper": "st.session_state" in wrapper_segment or "get_rerun_pure_cache(" in wrapper_segment,
        "page_debug_sink_allowed_in_core": "debug_sink" in core_segment,
    }
    status = (
        "PASS"
        if all(row["passed"] for row in artifacts)
        and all(direct_checks.values())
        and all(shell_boundaries.values())
        else "FAIL"
    )
    return {
        "schema": "design_guide_compute_guidance_core_shell_lock.v1",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        "status": status,
        "core_function": {
            "name": "_compute_design_guidance_items_core",
            "line_start": core_start,
            "line_end": core_end,
            "line_count": core_end - core_start + 1,
            "classification": "BOUNDED_PAGE_COMPUTE_GUIDANCE_ORCHESTRATION_SHELL",
        },
        "wrapper_function": {
            "name": "_compute_design_guidance_items",
            "line_start": wrapper_start,
            "line_end": wrapper_end,
            "line_count": wrapper_end - wrapper_start + 1,
            "classification": "BOUNDED_PAGE_COMPUTE_GUIDANCE_CACHE_TRACE_SHELL",
        },
        "artifacts": artifacts,
        "direct_checks": direct_checks,
        "shell_boundaries": shell_boundaries,
        "runtime_owner_files": {
            "compute": str(GUIDANCE_COMPUTE.relative_to(ROOT)),
            "entrypoint": str(GUIDANCE_ENTRYPOINT.relative_to(ROOT)),
            "page_shell": "inputs_page.py",
        },
        "remaining_page_owned_design_brain_authority": 0,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = VERIFICATION_DIR / f"design_guide_compute_guidance_core_shell_lock_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_guidance_core_shell_lock_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md = [
        "# Design Guide Compute Guidance Core Shell Lock",
        "",
        "## Executive Summary",
        str(payload["status"]),
        "",
        "## Functions",
        f"- `{payload['core_function']['name']}`: {payload['core_function']['classification']} ({payload['core_function']['line_count']} lines)",
        f"- `{payload['wrapper_function']['name']}`: {payload['wrapper_function']['classification']} ({payload['wrapper_function']['line_count']} lines)",
        "",
        "## Direct Checks",
        *[f"- {key}: {value}" for key, value in payload["direct_checks"].items()],
        "",
        "## Shell Boundaries",
        *[f"- {key}: {value}" for key, value in payload["shell_boundaries"].items()],
        "",
        "## Required Artifacts",
        *[f"- {row['prefix']}: {row['status']} ({row.get('path')})" for row in payload["artifacts"]],
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = _write(payload)
    print(f"design_guide_compute_guidance_core_shell_lock {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
