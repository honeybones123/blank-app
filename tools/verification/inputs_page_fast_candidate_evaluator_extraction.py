"""Verify the typed, application-owned fast candidate evaluator boundary."""

from __future__ import annotations

import ast
import contextlib
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "inputs_application" / "fast_candidate_evaluator.py"
ADAPTER = ROOT / "inputs_page_modules" / "recommendation_candidate_adapter.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def main() -> int:
    module_source = MODULE.read_text(encoding="utf-8")
    adapter_source = ADAPTER.read_text(encoding="utf-8")
    module_node = _function_node(module_source, "evaluate_candidate_fast")
    adapter_node = _function_node(adapter_source, "evaluate_fast_candidate")
    adapter_body = ast.get_source_segment(adapter_source, adapter_node) or ""

    checks = {
        "runtime_is_frozen_dataclass": (
            "@dataclass(frozen=True)" in module_source
            and "class FastCandidateEvaluationRuntime" in module_source
        ),
        "application_kernel_has_no_legacy_import": (
            "inputs_page_app_contract_bridge" not in module_source
            and "inputs_page_route_coordinators" not in module_source
        ),
        "application_kernel_has_no_global_binder": (
            "globals().update" not in module_source
            and "bind_fast_candidate_evaluator_dependencies" not in module_source
        ),
        "application_kernel_has_no_streamlit_import": (
            "import streamlit" not in module_source
        ),
        "adapter_constructs_explicit_runtime": (
            "FastCandidateEvaluationRuntime(" in adapter_source
            and "inputs_page_app_contract_bridge" not in adapter_source
        ),
        "adapter_delegates_to_application_kernel": (
            "evaluate_candidate_fast(" in adapter_body
        ),
        "old_app_bridge_kernel_is_deleted": not (
            ROOT
            / "inputs_page_modules"
            / "app_bridge"
            / "fast_candidate_evaluator.py"
        ).exists(),
        "kernel_keeps_candidate_contract": all(
            token in module_source
            for token in (
                "fast_eval",
                "Fast Eval",
                "bending_components",
                "reo_congestion_index",
                "shear_density",
                "fail_count",
                "all_key_pass",
                "worst_util",
            )
        ),
    }

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_modules.recommendation_candidate_adapter as adapter
        original = adapter.evaluate_candidate_fast
        call_record = {}

        def fake_kernel(candidate_state, context, *, runtime):
            call_record.update(
                candidate_state=dict(candidate_state),
                context=dict(context),
                runtime=runtime,
            )
            return {"source": "typed_fake"}

        try:
            adapter.evaluate_candidate_fast = fake_kernel
            session_state = {"test": True}
            returned = adapter.evaluate_fast_candidate(
                {"D": 600},
                {"actions": {"M": 10}},
                session_state=session_state,
            )
        finally:
            adapter.evaluate_candidate_fast = original

    runtime = call_record.get("runtime")
    checks["adapter_supplies_expected_typed_ports"] = bool(
        returned == {"source": "typed_fake"}
        and call_record.get("candidate_state") == {"D": 600}
        and call_record.get("context") == {"actions": {"M": 10}}
        and runtime is not None
        and callable(runtime.candidate_bottom_updates)
        and callable(runtime.candidate_shear_updates)
        and callable(runtime.evaluate_bending)
        and callable(runtime.evaluate_shear)
        and callable(runtime.status_from_util)
        and "candidate_bottom_updates=candidate_bottom_updates" in adapter_source
        and "candidate_shear_updates=candidate_shear_updates" in adapter_source
        and "evaluate_bending=evaluate_bending_with_bottom_state" in adapter_source
        and "evaluate_shear=evaluate_shear_with_state" in adapter_source
        and "status_from_util=status_from_candidate_util" in adapter_source
    )

    result = {
        "contract_version": "inputs_fast_candidate_evaluator_typed_runtime.v1",
        "checks": checks,
        "adapter_wrapper_lines": (
            (adapter_node.end_lineno or adapter_node.lineno)
            - adapter_node.lineno
            + 1
        ),
        "kernel_lines": (
            (module_node.end_lineno or module_node.lineno)
            - module_node.lineno
            + 1
        ),
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
