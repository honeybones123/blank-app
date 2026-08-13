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
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    reconcile = "_INPUTS_PAGE_RUNTIME.reconcile_design_actions"
    apply = "_INPUTS_PAGE_RUNTIME.handle_pending_apply"
    reconcile_calls = [
        node for node in calls if ast.unparse(node.func) == reconcile
    ]
    apply_calls = [node for node in calls if ast.unparse(node.func) == apply]
    assert reconcile_calls
    assert len(apply_calls) == 1

    # Reconciliation now occurs both in the source-toggle callback and in the
    # manual-owner branch, rather than as one unconditional top-level call.
    # Line ordering is the durable transaction invariant: pending Apply must
    # be consumed before either path can be defined or executed.
    apply_line = apply_calls[0].lineno
    assert all(apply_line < node.lineno for node in reconcile_calls), (
        "the immutable revision-bound Apply command must be consumed before "
        "action projection or reconciliation can advance its source revision"
    )


def main() -> None:
    verify_pending_apply_is_consumed_before_projection_can_advance()
    print("inputs apply preserves actions contract: PASS")


if __name__ == "__main__":
    main()
