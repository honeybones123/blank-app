"""Regression contract for the Inputs action-to-Apply transaction order."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def verify_pending_apply_is_consumed_before_projection_can_advance() -> None:
    source = (REPO_ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_render_v2_workspace_fragment"
    )
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
    ]
    reconcile = "_INPUTS_PAGE_RUNTIME.reconcile_design_actions"
    apply = "_INPUTS_PAGE_RUNTIME.handle_pending_apply"
    assert reconcile in calls
    assert apply in calls

    body_calls = [
        ast.unparse(statement.value.func)
        for statement in function.body
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
    ]
    assert body_calls.index(apply) < body_calls.index(reconcile), (
        "the immutable revision-bound Apply command must be consumed before "
        "action projection or reconciliation can advance its source revision"
    )


def main() -> None:
    verify_pending_apply_is_consumed_before_projection_can_advance()
    print("inputs apply preserves actions contract: PASS")


if __name__ == "__main__":
    main()
