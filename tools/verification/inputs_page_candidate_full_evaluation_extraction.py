"""Verify the typed, application-owned full candidate evaluator boundary."""

from __future__ import annotations

import ast
import contextlib
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_application" / "candidate_full_evaluation.py"
ADAPTER = ROOT / "inputs_page_modules" / "recommendation_candidate_adapter.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    adapter_source = ADAPTER.read_text(encoding="utf-8")
    bridge_node = _function_node(
        bridge_source,
        "evaluate_candidate_full_for_app_bridge",
    )
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    checks = {
        "runtime_is_frozen_dataclass": (
            "@dataclass(frozen=True)" in module_source
            and "class FullCandidateEvaluationRuntime" in module_source
        ),
        "application_kernel_has_no_legacy_import": (
            "inputs_page_app_contract_bridge" not in module_source
            and "inputs_page_route_coordinators" not in module_source
        ),
        "application_kernel_has_no_global_binder": (
            "globals().update" not in module_source
            and "bind_candidate_full_evaluation_dependencies" not in module_source
        ),
        "application_kernel_has_no_streamlit_import": (
            "import streamlit" not in module_source
        ),
        "bridge_constructs_explicit_runtime": (
            "FullCandidateEvaluationRuntime(" in adapter_source
            and "inputs_page_app_contract_bridge" not in adapter_source
        ),
        "bridge_delegates_to_application_kernel": (
            "evaluate_full_candidate_owned(" in bridge_body
            and "evaluate_candidate_full_for_app_bridge(" in adapter_source
        ),
        "old_app_bridge_kernel_is_deleted": not (
            ROOT
            / "inputs_page_modules"
            / "app_bridge"
            / "candidate_full_evaluation.py"
        ).exists(),
    }

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        original = bridge.evaluate_full_candidate_owned
        record = {}

        def fake_kernel(candidate_state, **kwargs):
            record.update(candidate_state=dict(candidate_state), **kwargs)
            return {"source": "typed_full_fake"}

        try:
            bridge.evaluate_full_candidate_owned = fake_kernel
            returned = bridge.evaluate_candidate_full_for_app_bridge(
                {"D": 600},
                source="proof",
                updates={"D": 600},
            )
        finally:
            bridge.evaluate_full_candidate_owned = original

    checks["bridge_supplies_expected_typed_ports"] = bool(
        returned == {"source": "typed_full_fake"}
        and record.get("candidate_state") == {"D": 600}
        and record.get("source") == "proof"
        and record.get("updates") == {"D": 600}
        and record.get("session_state") is bridge.st.session_state
        and "collect_overview=lambda state" in adapter_source
        and "evaluate_bending=evaluate_bending_with_bottom_state" in adapter_source
        and "evaluate_shear=evaluate_shear_with_state" in adapter_source
        and "build_projection=build_full_candidate_evaluation_result_projection" in adapter_source
        and "candidate_bottom_updates=candidate_bottom_updates" in adapter_source
        and "candidate_shear_updates=candidate_shear_updates" in adapter_source
        and "reo_congestion=reo_congestion_index" in adapter_source
        and "status_from_util=status_from_candidate_util" in adapter_source
    )

    result = {
        "contract_version": "inputs_full_candidate_evaluator_typed_runtime.v1",
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
