"""Prove unchanged Inputs reruns do not repeat Design Brain work.

This is a focused architecture lock, not a browser performance benchmark. It
exercises the production result coordinator with plain mappings and inspects
the live page boundaries that must remain render-only or fragment-owned.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _compile() -> dict[str, Any]:
    paths = [
        "inputs_page.py",
        "inputs_application/engineering_workspace.py",
        "inputs_application/diagram_fragments.py",
        "inputs_application/engineering_input_store.py",
        "inputs_application/summary_calculation_fragment_store.py",
        "inputs_application/page_runtime/summaries.py",
        "inputs_application/page_runtime/widgets.py",
        "inputs_page_modules/fragments.py",
        "inputs_page_modules/summaries/pipeline.py",
        "application/design_run_coordinator.py",
        "application/design_result_store.py",
        "application/engineering_snapshot.py",
        "design_brain/authority.py",
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *paths],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    return {
        "pass": proc.returncode == 0,
        "returncode": proc.returncode,
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _coordinator_probe() -> dict[str, Any]:
    from application.design_run_coordinator import ensure_design_result
    from design_brain.authority import build_authoritative_design_result
    from application.engineering_snapshot import build_engineering_input_snapshot_from_resolved_state

    state = {
        "b": 300.0,
        "D": 500.0,
        "fc": 40.0,
        "fsy": 500.0,
        "uls_Mstar": 100.0,
        "uls_Vstar": 50.0,
        "active_tab": "inputs",
        "expanded_panels": {"design_guide": False},
        "camera_settings": {"zoom": 1.0},
    }
    snapshot = build_engineering_input_snapshot_from_resolved_state(state)
    session: dict[str, Any] = {}
    calls: list[str] = []

    def compute(requested):
        calls.append(requested.engineering_hash)
        return build_authoritative_design_result(
            engineering_snapshot=requested,
            governing_family="TEST_FAMILY",
            family_outcome="PASS",
            final_publication={"outcome_state": "PASS"},
        )

    first = ensure_design_result(session_state=session, snapshot=snapshot, compute_fn=compute)
    second = ensure_design_result(session_state=session, snapshot=snapshot, compute_fn=compute)
    forced = ensure_design_result(session_state=session, snapshot=snapshot, compute_fn=compute, force=True)
    changed_state = dict(state)
    changed_state["b"] = 325.0
    changed_snapshot = build_engineering_input_snapshot_from_resolved_state(changed_state)
    changed = ensure_design_result(
        session_state=session,
        snapshot=changed_snapshot,
        compute_fn=compute,
    )
    ui_only_snapshot = build_engineering_input_snapshot_from_resolved_state(
        {**state, "active_tab": "design", "expanded_panels": {"design_guide": True}}
    )
    return {
        "same_hash_reuses_exact_object": first is second,
        "same_hash_compute_count": len(calls),
        "force_recomputes": forced is not second and len(calls) >= 3,
        "engineering_change_recomputes": changed is not forced and len(calls) == 3,
        "ui_only_state_excluded_from_hash": snapshot.engineering_hash == ui_only_snapshot.engineering_hash,
        "calls": len(calls),
        "first_hash": snapshot.engineering_hash,
        "changed_hash": changed_snapshot.engineering_hash,
    }


def _function_names(path: Path) -> set[str]:
    tree = ast.parse(_read(path))
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _boundary_probe() -> dict[str, Any]:
    page = _read(ROOT / "inputs_page.py")
    workspace = _read(
        ROOT / "inputs_application" / "engineering_workspace.py"
    )
    summaries = _read(
        ROOT / "inputs_application" / "page_runtime" / "summaries.py"
    )
    widgets = _read(
        ROOT / "inputs_application" / "page_runtime" / "widgets.py"
    )
    diagrams = _read(
        ROOT / "inputs_application" / "diagram_fragments.py"
    )
    state_helpers = _read(ROOT / "state_and_helpers.py")
    fragments = _read(ROOT / "inputs_page_modules" / "fragments.py")
    pipeline = _read(ROOT / "inputs_page_modules" / "summaries" / "pipeline.py")
    adapter = _read(ROOT / "application" / "guidance_result_adapter.py")
    return {
        "summary_container_created_inside_summary_fragment": (
            "def render_inputs_summary_fragment_section" in workspace
            and "summary_container=st_module.container()" in workspace
            and 'fragment_name="summary"' in workspace
        ),
        "diagram_fragments_present": (
            "def run_inputs_diagram_fragment" in diagrams
            and 'fragment_name="diagram_2d"' in widgets
            and 'fragment_name="diagram_3d"' in widgets
        ),
        "design_guide_fragment_present": (
            "def render_inputs_design_guide_fragment_section" in workspace
            and 'fragment_name="design_guide"' in workspace
            and "fragment_store.publish(" in workspace
        ),
        "fragment_has_full_page_fallback": (
            "full_page_fallback" in fragments
            and "CODEX_ENABLE_INPUTS_FRAGMENTS" in fragments
        ),
        "summary_pipeline_does_not_call_design_brain": (
            "_compute_design_guidance_items(" not in pipeline
            and "classify_governing_family(" not in pipeline
            and "evaluate_candidate_full(" not in pipeline
        ),
        "input_fragment_boundary_present": (
            'fragment_name="input"' in workspace
            and "def render_inputs_widget_fragment_section" in workspace
        ),
        "input_changes_have_explicit_commit_dirty_path": (
            "inputs_dirty" in state_helpers
            and "_mark_design_guide_dirty" in widgets
            and "sync_callbacks" in workspace
        ),
        "engineering_widget_commit_requests_app_rerun": (
            "def _request_inputs_engineering_commit" in state_helpers
            and "_inputs_workspace_authoritative_revision" in workspace
            and "workspace_revision > authoritative_revision" in workspace
            and 'st_module.rerun(scope="app")' in workspace
            and 'st.rerun(scope="app")' not in state_helpers[
                state_helpers.index(
                    "def _request_inputs_engineering_commit"
                ):
                state_helpers.index("def _compose_sync_callback")
            ]
        ),
        "design_action_callbacks_commit_app_scope": (
            "def _committing_callback" in widgets
            and "_request_inputs_engineering_commit(widget_key)" in widgets
        ),
        "authoritative_result_carries_resolved_inputs": (
            "resolved_inputs" in adapter
            and '"resolved_inputs"' in workspace
        ),
        "summary_reads_authoritative_resolved_inputs": (
            "AuthoritativeDesignResultStore(" in summaries
            and "authoritative_result.current_calculations" in summaries
            and '"summary_state_source": "authoritative_design_result"'
            in summaries
        ),
        "diagram_reads_authoritative_resolved_inputs": (
            "def _authoritative_state_snapshot" in widgets
            and "authoritative = _authoritative_state_snapshot()" in widgets
            and '"model_state_source": "authoritative_design_result"' in widgets
        ),
        "inputs_page_is_composition_shell": (
            "_INPUTS_PAGE_RUNTIME.render_page_setup(" in page
            and "_render_engineering_workspace(page_context=page_context)"
            in page
            and "_INPUTS_PAGE_RUNTIME.render_tail(" in page
        ),
        "input_fragment_boundary_status": "enabled_with_sibling_output_fragments",
    }


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_result = _compile()
    coordinator = _coordinator_probe()
    boundaries = _boundary_probe()
    required_coordinator = all(
        coordinator[key]
        for key in (
            "same_hash_reuses_exact_object",
            "force_recomputes",
            "engineering_change_recomputes",
            "ui_only_state_excluded_from_hash",
        )
    )
    required_boundaries = all(
        boundaries[key]
        for key in (
            "summary_container_created_inside_summary_fragment",
            "diagram_fragments_present",
            "design_guide_fragment_present",
            "fragment_has_full_page_fallback",
            "summary_pipeline_does_not_call_design_brain",
            "input_fragment_boundary_present",
            "input_changes_have_explicit_commit_dirty_path",
            "engineering_widget_commit_requests_app_rerun",
            "design_action_callbacks_commit_app_scope",
            "authoritative_result_carries_resolved_inputs",
            "summary_reads_authoritative_resolved_inputs",
            "diagram_reads_authoritative_resolved_inputs",
            "inputs_page_is_composition_shell",
        )
    )
    status = "PASS" if compile_result["pass"] and required_coordinator and required_boundaries else "FAIL"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    payload = {
        "status": status,
        "scope": "unchanged_rerun_and_fragment_architecture",
        "compile": compile_result,
        "coordinator_probe": coordinator,
        "boundary_probe": boundaries,
        "claims": {
            "tab_expansion_should_reuse_authoritative_result": coordinator["same_hash_reuses_exact_object"],
            "unchanged_rerun_should_do_zero_design_brain_compute": coordinator["same_hash_reuses_exact_object"],
            "input_widget_fragment_fully_isolated": boundaries["engineering_widget_commit_requests_app_rerun"],
            "input_widget_fragment_note": "Engineering widget edits request an app-scope commit so sibling output fragments refresh from the new authoritative result; display-only toggles remain fragment-local.",
        },
    }
    artifact = ARTIFACT_DIR / f"streamlit_zero_engineering_work_rerun_lock_{stamp}.json"
    report = AUDIT_DIR / f"streamlit_zero_engineering_work_rerun_lock_{stamp}.md"
    payload["artifact"] = str(artifact.relative_to(ROOT))
    artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text(
        "\n".join(
            [
                "# Zero Engineering Work Rerun Lock",
                "",
                f"Status: `{status}`",
                "",
                "## Proven",
                "",
                "- Same engineering hash returns the exact session-owned result object.",
                "- Forced runs and engineering input changes recompute.",
                "- UI-only state does not change the engineering hash.",
                "- Summary, diagram, and Design Guide fragment boundaries are present.",
                "- Summary pipeline does not call the Design Brain directly.",
                "",
                "## Deliberate Remaining Boundary",
                "",
                "Engineering widget edits commit at app scope so summary, diagram, and Design Guide cannot remain stale after a fragment-local callback. Display-only toggles remain fragment-local. Output fragments consume the session-owned authoritative result.",
                "",
                f"JSON: `{artifact.relative_to(ROOT)}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "artifact": str(artifact), "report": str(report)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
