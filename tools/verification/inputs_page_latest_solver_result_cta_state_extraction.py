"""Verify latest solver-result CTA state extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "presentation_state.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


class _FakeSessionState(dict):
    pass


class _FakeStreamlit:
    def __init__(self, state: dict | None = None) -> None:
        self.session_state = _FakeSessionState(state or {})


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    bridge_node = _function_node(bridge_source, "_latest_solver_result_cta_state")
    module_node = _function_node(module_source, "_latest_solver_result_cta_state")
    module_builder_node = _function_node(module_source, "_build_design_guide_presentation_state")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    module_body = ast.get_source_segment(module_source, module_node) or ""
    module_builder_body = ast.get_source_segment(module_source, module_builder_node) or ""
    dependency_tuple_source = module_source.split("_PRESENTATION_STATE_DEPENDENCIES", 1)[1].split(")", 1)[0]

    checks: dict[str, bool] = {
        "bridge_wrapper_is_tiny": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 3,
        "bridge_binds_presentation_dependencies": "_bind_presentation_state_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_latest_solver_result_cta_state_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 60,
        "module_builder_calls_owned_helper": "_latest_solver_result_cta_state(ov)" in module_builder_body,
        "module_has_dependency_binder": "def bind_presentation_state_dependencies" in module_source,
        "module_binds_solver_cta_dependencies": all(
            token in module_source
            for token in (
                '"st"',
                '"_current_design_guide_fail_fingerprint"',
                '"_design_guide_fail_fingerprints_equivalent"',
                '"_ONE_CLICK_CTA_BLOCKING_REASONS"',
            )
        ),
        "module_does_not_dependency_inject_owned_helper": '"_latest_solver_result_cta_state"' not in dependency_tuple_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_keeps_cta_contract_surface": all(
            token in module_body
            for token in (
                "_solver_result",
                "auto_design_status",
                "recommendation_envelope",
                "commit_eligible",
                "_ONE_CLICK_CTA_BLOCKING_REASONS",
                "_current_design_guide_fail_fingerprint",
                "_design_guide_fail_fingerprints_equivalent",
                "status",
                "reason",
                "matches_current_state",
                "current_fail_fingerprint",
                "result_fail_fingerprint",
            )
        ),
    }

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import presentation_state as extracted

    original = bridge._latest_solver_result_cta_state_extracted
    call_record: dict = {}

    def _fake_extracted(overview: dict | None) -> dict:
        call_record.update(
            {
                "overview": dict(overview or {}),
                "bound_st": getattr(extracted, "st", None) is bridge.st,
                "bound_blocking_reasons": getattr(extracted, "_ONE_CLICK_CTA_BLOCKING_REASONS", None)
                is bridge._ONE_CLICK_CTA_BLOCKING_REASONS,
                "bound_current_fingerprint": getattr(extracted, "_current_design_guide_fail_fingerprint", None)
                is bridge._current_design_guide_fail_fingerprint,
                "bound_equivalent": getattr(extracted, "_design_guide_fail_fingerprints_equivalent", None)
                is bridge._design_guide_fail_fingerprints_equivalent,
            }
        )
        return {"matches_current_state": True, "delegated": True}

    try:
        bridge._latest_solver_result_cta_state_extracted = _fake_extracted
        returned = bridge._latest_solver_result_cta_state({"statuses": {"bending": "FAIL"}})
    finally:
        bridge._latest_solver_result_cta_state_extracted = original

    checks["bridge_runtime_delegates_with_arguments"] = (
        returned == {"matches_current_state": True, "delegated": True}
        and call_record.get("overview") == {"statuses": {"bending": "FAIL"}}
        and call_record.get("bound_st") is True
        and call_record.get("bound_blocking_reasons") is True
        and call_record.get("bound_current_fingerprint") is True
        and call_record.get("bound_equivalent") is True
    )

    extracted.bind_presentation_state_dependencies(
        {
            "st": _FakeStreamlit(),
            "_ONE_CLICK_CTA_BLOCKING_REASONS": frozenset({"blocked_reason"}),
            "_current_design_guide_fail_fingerprint": lambda overview: {"bending": "FAIL"},
            "_design_guide_fail_fingerprints_equivalent": lambda a, b: False,
        }
    )
    no_result = extracted._latest_solver_result_cta_state({"statuses": {"bending": "FAIL"}})
    extracted.bind_presentation_state_dependencies(
        {
            "st": _FakeStreamlit(
                {
                    "_solver_result": {
                        "status": "blocked",
                        "recommendation_envelope": {
                            "blocked_reason": "blocked_reason",
                            "commit_eligible": True,
                        },
                    }
                }
            ),
            "_ONE_CLICK_CTA_BLOCKING_REASONS": frozenset({"blocked_reason"}),
            "_current_design_guide_fail_fingerprint": lambda overview: {"bending": "FAIL"},
            "_design_guide_fail_fingerprints_equivalent": lambda a, b: False,
        }
    )
    commit_eligible = extracted._latest_solver_result_cta_state({"statuses": {"bending": "FAIL"}})
    extracted.bind_presentation_state_dependencies(
        {
            "st": _FakeStreamlit(
                {
                    "_solver_result": {
                        "status": "blocked",
                        "recommendation_envelope": {"blocked_reason": "blocked_reason"},
                        "one_click_solver_debug": {"current_fail_fingerprint": {"bending": "FAIL"}},
                    }
                }
            ),
            "_ONE_CLICK_CTA_BLOCKING_REASONS": frozenset({"blocked_reason"}),
            "_current_design_guide_fail_fingerprint": lambda overview: {"bending": "FAIL"},
            "_design_guide_fail_fingerprints_equivalent": lambda a, b: False,
        }
    )
    matching = extracted._latest_solver_result_cta_state({"statuses": {"bending": "FAIL"}})
    extracted.bind_presentation_state_dependencies(
        {
            "st": _FakeStreamlit(
                {
                    "_solver_result": {
                        "status": "blocked",
                        "recommendation_envelope": {"blocked_reason": "blocked_reason"},
                        "one_click_solver_debug": {"current_fail_fingerprint": {"bending": "OLD"}},
                    }
                }
            ),
            "_ONE_CLICK_CTA_BLOCKING_REASONS": frozenset({"blocked_reason"}),
            "_current_design_guide_fail_fingerprint": lambda overview: {"bending": "FAIL"},
            "_design_guide_fail_fingerprints_equivalent": lambda a, b: True,
        }
    )
    equivalent = extracted._latest_solver_result_cta_state({"statuses": {"bending": "FAIL"}})

    checks["module_runtime_cases"] = (
        no_result
        == {
            "status": "",
            "reason": "",
            "matches_current_state": False,
            "current_fail_fingerprint": {},
            "result_fail_fingerprint": {},
        }
        and commit_eligible.get("matches_current_state") is False
        and commit_eligible.get("reason") == "blocked_reason"
        and matching.get("matches_current_state") is True
        and matching.get("current_fail_fingerprint") == {"bending": "FAIL"}
        and matching.get("result_fail_fingerprint") == {"bending": "FAIL"}
        and equivalent.get("matches_current_state") is True
        and equivalent.get("current_fail_fingerprint") == {"bending": "FAIL"}
        and equivalent.get("result_fail_fingerprint") == {"bending": "OLD"}
    )

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
        "module_builder_lines": (
            module_builder_node.end_lineno or module_builder_node.lineno
        ) - module_builder_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_latest_solver_result_cta_state_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_latest_solver_result_cta_state_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Latest Solver Result CTA State Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                f"- Presentation builder lines: {result['module_builder_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(result["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
