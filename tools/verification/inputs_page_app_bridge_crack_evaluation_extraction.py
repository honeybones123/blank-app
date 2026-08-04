"""Verify typed application ownership of candidate crack evaluation."""

from __future__ import annotations

import ast
import contextlib
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_application" / "crack_evaluation.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function(source: str, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    node = _function(
        bridge_source,
        "_evaluate_crack_with_state_for_app_bridge",
    )
    body = ast.get_source_segment(bridge_source, node) or ""
    checks = {
        "runtime_is_frozen_dataclass": (
            "@dataclass(frozen=True)" in module_source
            and "class CrackEvaluationRuntime" in module_source
        ),
        "kernel_has_no_legacy_or_streamlit_import": all(
            token not in module_source
            for token in (
                "inputs_page_app_contract_bridge",
                "inputs_page_route_coordinators",
                "import streamlit",
            )
        ),
        "kernel_has_no_global_binder": (
            "globals().update" not in module_source
            and "bind_crack_evaluation_dependencies" not in module_source
        ),
        "bridge_constructs_explicit_runtime": (
            "runtime=CrackEvaluationRuntime(" in body
        ),
        "old_kernel_deleted": not (
            ROOT / "inputs_page_modules" / "app_bridge" / "crack_evaluation.py"
        ).exists(),
    }
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge

        original = bridge._evaluate_crack_with_state_for_app_bridge_extracted
        record = {}

        def fake(state, *, bottom_updates=None, runtime):
            record.update(
                state=dict(state),
                bottom_updates=bottom_updates,
                runtime=runtime,
            )
            return {"util": 0.5}

        try:
            bridge._evaluate_crack_with_state_for_app_bridge_extracted = fake
            returned = bridge._evaluate_crack_with_state_for_app_bridge(
                {"D": 600},
                bottom_updates={"bot1_count": 3},
            )
        finally:
            bridge._evaluate_crack_with_state_for_app_bridge_extracted = original
    runtime = record.get("runtime")
    checks["bridge_supplies_typed_ports"] = bool(
        returned == {"util": 0.5}
        and record.get("state") == {"D": 600}
        and runtime is not None
        and runtime.design_width is bridge._design_width_value_for_app_bridge
        and runtime.effective_bottom
        is bridge._effective_bottom_design_state_for_app_bridge
    )
    result = {
        "contract_version": "inputs_crack_evaluation_typed_runtime.v1",
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
