"""Permanent Runtime architecture gate for the dual-design cutover."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _imports(path: str) -> set[str]:
    tree = ast.parse(_source(path), filename=path)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def main() -> int:
    failures: list[str] = []
    if (ROOT / "inputs_application" / "guidance_entrypoint.py").exists():
        failures.append("legacy guidance_entrypoint.py still exists")

    pure_modules = (
        "application/contracts/design_branch.py",
        "application/contracts/load_analysis.py",
        "inputs_application/branch_workspace.py",
        "inputs_application/workspace_application_service.py",
    )
    for path in pure_modules:
        imports = _imports(path)
        forbidden = sorted(
            name
            for name in imports
            if name == "streamlit"
            or name.startswith("streamlit.")
            or name.endswith("_page")
            or ".page_" in name
        )
        if forbidden:
            failures.append(f"{path} imports presentation modules: {forbidden}")

    page_sources = {
        path: _source(path)
        for path in (
            "app.py",
            "inputs_page.py",
            "design_page_runtime.py",
            "inputs_application/page_runtime/setup.py",
        )
    }
    for path, source in page_sources.items():
        if "build_design_brain_service(" in source:
            failures.append(f"{path} directly composes the Design Brain")
        if "calculate_v2_authoritative_result(" in source:
            failures.append(f"{path} directly executes the V2 calculator")
        if "ensure_design_result(" in source:
            failures.append(f"{path} retains a page-local result execution path")

    load_analysis_page = page_sources["design_page_runtime.py"]
    if "include_design_brain=False" not in load_analysis_page:
        failures.append("Load Analysis is not bound to calculation-only execution")
    for forbidden in (
        "render_v2_design_guide_card",
        "execute_typed_apply",
        "compare_design_brain_actions",
    ):
        if forbidden in load_analysis_page:
            failures.append(
                f"Load Analysis retains Design Brain UI authority: {forbidden}"
            )
    if "_queued_design_brain_apply_result" in _source(
        "inputs_application/v2_design_guide_renderer.py"
    ):
        failures.append("renderer retains a cross-page Design Brain Apply handover")

    retired_mirrors = {
        "inputs_application/engineering_input_store.py": (
            "_inputs_engineering_input_snapshot_by_beam_v2",
            "_inputs_committed_engineering_state_by_beam_v1",
        ),
        "inputs_application/page_runtime/setup.py": (
            "_inputs_authoritative_design_result_by_beam_v1",
            "_inputs_authoritative_result_revision_by_beam_v1",
        ),
    }
    for path, tokens in retired_mirrors.items():
        source = _source(path)
        for token in tokens:
            if token in source:
                failures.append(f"{path} retains duplicate authority {token}")

    worker = _source("inputs_application/design_brain_job_worker.py")
    for forbidden in ("adapter_name=\"legacy\"", "selected_adapter == \"legacy\""):
        if forbidden in worker:
            failures.append(f"worker retains legacy branch: {forbidden}")

    job_service = _source("inputs_application/design_brain_job_service.py")
    if "design_branch" not in job_service or "record.process.terminate()" not in job_service:
        failures.append("async jobs are not branch-keyed and supersedable")

    required_tokens = {
        "inputs_application/design_branch_store.py": (
            "expected_branch_revision",
            "expected_selection_revision",
        ),
        "inputs_application/load_analysis_store.py": ("expected_revision",),
        "inputs_application/branch_apply_identity.py": (
            "publication_authority_hash",
            "candidate_id",
            "selection_revision",
        ),
    }
    for path, tokens in required_tokens.items():
        source = _source(path)
        for token in tokens:
            if token not in source:
                failures.append(f"{path} is missing {token}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: dual-design branch architecture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
