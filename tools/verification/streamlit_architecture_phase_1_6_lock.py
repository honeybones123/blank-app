"""Lock the current typed Inputs/Streamlit architecture boundary.

This is a focused structural contract. It does not claim browser parity or
release readiness.
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

INPUTS = ROOT / "inputs_page.py"
WORKSPACE = ROOT / "inputs_application" / "engineering_workspace.py"
RUNTIME = ROOT / "inputs_application" / "page_runtime" / "__init__.py"
SETUP = ROOT / "inputs_application" / "page_runtime" / "setup.py"
INPUT_STORE = ROOT / "inputs_application" / "engineering_input_store.py"
SUMMARY_CALC_STORE = (
    ROOT / "inputs_application" / "summary_calculation_fragment_store.py"
)
DIAGRAM_FRAGMENT_OWNER = (
    ROOT / "inputs_application" / "diagram_fragments.py"
)
FRAGMENT_STORE = (
    ROOT / "inputs_application" / "design_guide_fragment_store.py"
)
SNAPSHOT = ROOT / "design_brain" / "authority.py"
RESULT_STORE = ROOT / "application" / "design_result_store.py"
RUN_COORDINATOR = ROOT / "application" / "design_run_coordinator.py"
APPLY = ROOT / "application" / "apply_command.py"
LIVE_APPLY = ROOT / "inputs_application" / "live_apply.py"
ADAPTER = ROOT / "application" / "guidance_result_adapter.py"

LEGACY_PATHS = (
    ROOT / "inputs_page_route_coordinators.py",
    ROOT / "inputs_page_app_contract_bridge.py",
    ROOT / "design_guidance_engine.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(path: Path, name: str) -> str:
    source = _read(path)
    lines = source.splitlines()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _frozen_dataclass(path: Path, class_name: str) -> bool:
    tree = ast.parse(_read(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            name = getattr(decorator.func, "id", None) or getattr(
                decorator.func,
                "attr",
                None,
            )
            if name != "dataclass":
                continue
            return any(
                keyword.arg == "frozen"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in decorator.keywords
            )
    return False


def _compile() -> dict[str, Any]:
    paths = [
        str(path.relative_to(ROOT))
        for path in (
            INPUTS,
            WORKSPACE,
            RUNTIME,
            SETUP,
            INPUT_STORE,
            SUMMARY_CALC_STORE,
            DIAGRAM_FRAGMENT_OWNER,
            FRAGMENT_STORE,
            SNAPSHOT,
            RESULT_STORE,
            RUN_COORDINATOR,
            APPLY,
            LIVE_APPLY,
            ADAPTER,
            Path(__file__).resolve(),
        )
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


def _checks() -> dict[str, bool]:
    page = _read(INPUTS)
    workspace = _read(WORKSPACE)
    runtime = _read(RUNTIME)
    input_store = _read(INPUT_STORE)
    summary_calc_store = _read(SUMMARY_CALC_STORE)
    diagram_fragment_owner = _read(DIAGRAM_FRAGMENT_OWNER)
    fragment_store = _read(FRAGMENT_STORE)
    result_store = _read(RESULT_STORE)
    coordinator = _read(RUN_COORDINATOR)
    apply = _read(APPLY)
    live_apply = _read(LIVE_APPLY)
    adapter = _read(ADAPTER)
    workspace_render = _function_source(
        WORKSPACE,
        "render_engineering_workspace",
    )
    workspace_transaction = _function_source(
        WORKSPACE,
        "prepare_engineering_workspace_transaction",
    )
    widget_fragment = _function_source(
        WORKSPACE,
        "render_inputs_widget_fragment_section",
    )
    design_guide_fragment = _function_source(
        WORKSPACE,
        "render_inputs_design_guide_fragment_section",
    )
    setup_render = _function_source(
        SETUP,
        "render_inputs_pre_widget_apply_and_render_setup_coordinator",
    )
    return {
        "legacy_bridges_and_wrapper_absent": all(
            not path.exists() for path in LEGACY_PATHS
        ),
        "engineering_snapshot_is_frozen": _frozen_dataclass(
            SNAPSHOT,
            "EngineeringInputSnapshot",
        ),
        "engineering_hash_is_deterministic_property": (
            "def engineering_hash" in _read(SNAPSHOT)
            and "stable_authority_hash(self.to_dict())" in _read(SNAPSHOT)
        ),
        "draft_and_committed_store_is_explicit": all(
            token in input_store
            for token in (
                "DRAFT_STATE_KEY",
                "COMMITTED_STATE_KEY",
                "def capture_draft(",
                "def commit_draft(",
            )
        ),
        "authoritative_result_store_is_streamlit_independent": (
            "import streamlit" not in result_store
            and "from streamlit" not in result_store
        ),
        "calculation_handoff_is_session_owned": (
            "class SummaryCalculationFragmentStore" in summary_calc_store
            and "import streamlit" not in summary_calc_store
            and "SummaryCalculationFragmentStore(st_module.session_state).publish("
            in workspace
            and "SummaryCalculationFragmentStore(" in workspace
            and "summary_state.source" in workspace
        ),
        "coordinator_reuses_by_engineering_hash": all(
            token in coordinator
            for token in (
                "store.can_reuse(snapshot.engineering_hash",
                "result = compute_fn(snapshot)",
                "return store.store(result)",
            )
        ),
        "workspace_has_one_authoritative_transaction": (
            workspace_render.count(
                "prepare_engineering_workspace_transaction("
            )
            == 1
            and workspace_transaction.count(
                "runtime.refresh_authoritative_result()"
            )
            == 1
        ),
        "input_fragment_promotes_stale_revision_outside_callback": (
            "_inputs_workspace_authoritative_revision"
            in workspace_transaction
            and "_inputs_workspace_authoritative_revision"
            in widget_fragment
            and "workspace_revision > authoritative_revision"
            in widget_fragment
            and 'st_module.rerun(scope="app")' in widget_fragment
            and 'st.rerun(scope="app")'
            not in _function_source(
                ROOT / "state_and_helpers.py",
                "_request_inputs_engineering_commit",
            )
        ),
        "page_setup_does_not_compute_authority": (
            "_ensure_authoritative_design_result_current_coordinator("
            not in setup_render
        ),
        "summary_calculation_design_guide_and_input_are_fragments": (
            workspace_render.count("run_inputs_fragment(") == 4
            and all(
                f'fragment_name="{name}"' in workspace_render
                for name in (
                    "summary",
                    "calculation",
                    "design_guide",
                    "input",
                )
            )
        ),
        "diagram_fragments_have_typed_owner_and_preserve_layout": (
            "INPUTS_DIAGRAM_FRAGMENT_NAMES" in diagram_fragment_owner
            and "def run_inputs_diagram_fragment(" in diagram_fragment_owner
            and "run_inputs_fragment(" in diagram_fragment_owner
            and 'fragment_name="diagram_2d"' in _read(
                ROOT / "inputs_application" / "page_runtime" / "widgets.py"
            )
            and 'fragment_name="diagram_3d"' in _read(
                ROOT / "inputs_application" / "page_runtime" / "widgets.py"
            )
            and "run_inputs_fragment(" not in _read(
                ROOT / "inputs_application" / "page_runtime" / "widgets.py"
            )
        ),
        "design_guide_lifecycle_preserves_last_publication": all(
            token in fragment_store
            for token in (
                "def begin_refresh(",
                "active_publication=dict(current.active_publication)",
                "def publish(",
                "def fail_refresh(",
            )
        ),
        "design_guide_fragment_owns_atomic_replacement": (
            ".begin_refresh(" in workspace_transaction
            and ".publish(" not in workspace_transaction
            and "fragment_store.publish(" in design_guide_fragment
            and "fragment_store.clear()" in design_guide_fragment
            and "fragment_state=fragment_state.to_dict()"
            in design_guide_fragment
        ),
        "typed_runtime_has_calculation_and_publication_ports": all(
            token in runtime
            for token in (
                "refresh_authoritative_result: PageCallable",
                "render_calculation: PageCallable",
                "render_design_guide: PageCallable",
            )
        ),
        "atomic_apply_is_application_owned": (
            "def execute_apply_command" in apply
            and "def execute_typed_apply" in live_apply
        ),
        "canonical_publication_is_authoritative_result_owned": (
            "build_final_design_guide_publication" in adapter
            and "final_publication=canonical_payload" in adapter
        ),
        "page_shell_has_no_design_brain_decisions": (
            "_render_engineering_workspace(page_context=page_context)" in page
            and 'fragment_name="engineering_workspace"' not in page
            and "_compute_design_guidance_items(" not in page
            and "resolve_design_guide_decision(" not in page
        ),
        "design_guide_remains_before_widgets": (
            workspace_render.find(
                "render_inputs_design_guide_fragment_section"
            )
            < workspace_render.find(
                "render_inputs_widget_fragment_section"
            )
        ),
    }


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_result = _compile()
    checks = _checks()
    passed = compile_result["pass"] and all(checks.values())
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    status = (
        "STREAMLIT_ARCHITECTURE_CURRENT_LOCKED"
        if passed
        else "STREAMLIT_ARCHITECTURE_CURRENT_FAIL"
    )
    payload = {
        "status": status,
        "scope": "focused_structural_contract_not_browser_or_release_parity",
        "compile": compile_result,
        "checks": checks,
        "failures": [
            name for name, value in checks.items() if not value
        ],
    }
    artifact = ARTIFACT_DIR / f"streamlit_architecture_phase_1_6_lock_{stamp}.json"
    report = AUDIT_DIR / f"streamlit_architecture_phase_1_6_lock_{stamp}.md"
    artifact.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report.write_text(
        "\n".join(
            [
                "# Current Streamlit Architecture Lock",
                "",
                f"Status: `{status}`",
                "",
                "This is a focused structural contract. It does not claim "
                "browser parity or release readiness.",
                "",
                "## Checks",
                "",
                *(
                    f"- `{name}`: `{value}`"
                    for name, value in checks.items()
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": status,
                "artifact": str(artifact),
                "report": str(report),
                "failures": payload["failures"],
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
