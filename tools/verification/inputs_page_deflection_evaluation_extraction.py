"""Verify typed application ownership of both deflection evaluator paths."""

from __future__ import annotations

import ast
import contextlib
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_application" / "deflection_evaluation.py"
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
    full_body = ast.get_source_segment(
        bridge_source,
        _function(
            bridge_source,
            "_evaluate_deflection_with_state_for_app_bridge",
        ),
    ) or ""
    fast_body = ast.get_source_segment(
        bridge_source,
        _function(bridge_source, "_evaluate_deflection_with_state"),
    ) or ""
    checks = {
        "runtime_is_frozen_dataclass": (
            "@dataclass(frozen=True)" in module_source
            and "class DeflectionEvaluationRuntime" in module_source
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
            and "bind_deflection_evaluation_dependencies" not in module_source
        ),
        "both_bridge_paths_construct_explicit_runtime": all(
            "runtime=DeflectionEvaluationRuntime(" in body
            for body in (full_body, fast_body)
        ),
        "old_kernel_deleted": not (
            ROOT
            / "inputs_page_modules"
            / "app_bridge"
            / "deflection_evaluation.py"
        ).exists(),
    }
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge

        original_full = (
            bridge._evaluate_deflection_with_state_for_app_bridge_extracted
        )
        original_fast = bridge._evaluate_deflection_with_state_extracted
        records = {}

        def fake_full(state, *, bottom_updates=None, runtime):
            records["full"] = (dict(state), bottom_updates, runtime)
            return {"path": "full"}

        def fake_fast(state, *, bottom_updates=None, runtime):
            records["fast"] = (dict(state), bottom_updates, runtime)
            return {"path": "fast"}

        try:
            bridge._evaluate_deflection_with_state_for_app_bridge_extracted = (
                fake_full
            )
            bridge._evaluate_deflection_with_state_extracted = fake_fast
            full_result = bridge._evaluate_deflection_with_state_for_app_bridge(
                {"D": 600}
            )
            fast_result = bridge._evaluate_deflection_with_state({"D": 600})
        finally:
            bridge._evaluate_deflection_with_state_for_app_bridge_extracted = (
                original_full
            )
            bridge._evaluate_deflection_with_state_extracted = original_fast
    full_runtime = records.get("full", (None, None, None))[2]
    fast_runtime = records.get("fast", (None, None, None))[2]
    checks["both_bridge_paths_supply_typed_ports"] = bool(
        full_result == {"path": "full"}
        and fast_result == {"path": "fast"}
        and full_runtime is not None
        and fast_runtime is not None
        and full_runtime.design_width
        is bridge._design_width_value_for_app_bridge
        and fast_runtime.design_width is bridge._design_width_value
    )
    result = {
        "contract_version": "inputs_deflection_evaluation_typed_runtime.v1",
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
