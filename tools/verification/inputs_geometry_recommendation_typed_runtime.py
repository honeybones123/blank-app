"""Freeze the explicit geometry recommendation runtime boundary."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPUTE_PATH = ROOT / "inputs_page_modules" / "recommendation_compute.py"
BRIDGE_PATH = ROOT / "inputs_page_app_contract_bridge.py"


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function: {name}")


def main() -> None:
    compute_tree = ast.parse(COMPUTE_PATH.read_text(encoding="utf-8"))
    bridge_tree = ast.parse(BRIDGE_PATH.read_text(encoding="utf-8"))
    compute = _function(compute_tree, "compute_geometry_recommendation")
    bridge = _function(bridge_tree, "_compute_geometry_recommendation")

    compute_args = [arg.arg for arg in compute.args.args]
    assert compute_args == ["runtime", "state"], compute_args
    compute_source = ast.unparse(compute)
    assert "legacy_page" not in compute_source
    assert "GeometryCandidateRuntime(" not in compute_source

    bridge_source = ast.unparse(bridge)
    assert "_BRIDGE_PROVIDER" not in bridge_source
    assert "GeometryCandidateRuntime(" in bridge_source
    for field in (
        "evaluate_full=",
        "evaluate_fast=",
        "rank=",
        "max_stage_candidates=",
    ):
        assert field in bridge_source, field

    print("PASS: geometry recommendation uses an explicit four-port runtime")


if __name__ == "__main__":
    main()
