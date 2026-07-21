"""Verify candidate-search evidence alignment extraction."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "candidate_search_evidence.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    bridge_node = _function_node(bridge_source, "_align_guidance_items_to_candidate_search_evidence")
    module_node = _function_node(module_source, "_align_guidance_items_to_candidate_search_evidence")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.design_guide import candidate_search_evidence as extracted

    extracted.bind_candidate_search_evidence_dependencies(
        {
            "EFFICIENCY_TARGET_UTIL_MIN": 0.85,
            "EFFICIENCY_TARGET_UTIL_MAX": 0.95,
        }
    )

    direct_case = extracted._align_guidance_items_to_candidate_search_evidence(
        [
            {
                "title_main": "Direct",
                "action_payload": {},
                "candidate_search_evidence": {
                    "selected_candidate_id": "c1",
                    "selected_candidate_title": "Candidate 1",
                    "selected_candidate_util": 0.90,
                    "selected_candidate_updates": {"D": 650},
                    "target_low": 0.85,
                    "target_high": 0.95,
                },
            }
        ]
    )[0]
    fallback_case = extracted._align_guidance_items_to_candidate_search_evidence(
        [
            {
                "title_main": "Fallback",
                "action_payload": {
                    "candidate_search_evidence": {
                        "selected_candidate_id": "c2",
                        "selected_candidate_title": "Candidate 2",
                        "selected_candidate_util": 1.02,
                        "target_band_candidates": [
                            {"candidate_id": "c2", "proposed_updates": {"b": 350}},
                        ],
                        "target_low": 0.85,
                        "target_high": 0.95,
                    }
                },
            }
        ]
    )[0]
    noop_input = {"title_main": "Noop", "action_payload": {"updates": {"D": 600}}}
    noop_case = extracted._align_guidance_items_to_candidate_search_evidence([noop_input])[0]

    original = bridge._align_guidance_items_to_candidate_search_evidence_extracted
    delegate_call: dict[str, Any] = {}

    def _fake_extracted(guidance_items: list[dict] | None) -> list[dict]:
        delegate_call.update(
            {
                "guidance_items": list(guidance_items or []),
                "module_owner": extracted._align_guidance_items_to_candidate_search_evidence is original,
                "target_min_bound": getattr(extracted, "EFFICIENCY_TARGET_UTIL_MIN", None)
                == bridge.EFFICIENCY_TARGET_UTIL_MIN,
                "target_max_bound": getattr(extracted, "EFFICIENCY_TARGET_UTIL_MAX", None)
                == bridge.EFFICIENCY_TARGET_UTIL_MAX,
            }
        )
        return [{"aligned": True}]

    try:
        bridge._align_guidance_items_to_candidate_search_evidence_extracted = _fake_extracted
        wrapped = bridge._align_guidance_items_to_candidate_search_evidence([{"seed": True}])
    finally:
        bridge._align_guidance_items_to_candidate_search_evidence_extracted = original

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 5,
        "bridge_binds_dependencies": "_bind_candidate_search_evidence_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_align_guidance_items_to_candidate_search_evidence_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 65,
        "direct_updates_aligned": direct_case["action_payload"]["updates"] == {"D": 650}
        and direct_case["resolved_candidate_updates"] == {"D": 650}
        and direct_case["resolved_candidate"]["updates"] == {"D": 650},
        "direct_identity_aligned": direct_case["candidate_id"] == "c1"
        and direct_case["source_candidate_id"] == "c1"
        and direct_case["action_payload"]["source_candidate_id"] == "c1"
        and direct_case["resolved_candidate"]["candidate_id"] == "c1",
        "direct_target_band_flag": direct_case["action_payload"]["resolved_candidate_reaches_target_band"] is True
        and direct_case["resolved_candidate"]["candidate_reaches_target_band"] is True,
        "fallback_row_updates_aligned": fallback_case["action_payload"]["updates"] == {"b": 350}
        and fallback_case["resolved_candidate_updates"] == {"b": 350},
        "fallback_outside_target_flag": fallback_case["action_payload"]["resolved_candidate_reaches_target_band"] is False,
        "no_evidence_noop": noop_case == noop_input,
        "bridge_runtime_delegates": wrapped == [{"aligned": True}]
        and delegate_call.get("guidance_items") == [{"seed": True}],
        "bridge_runtime_preserves_module_owner": delegate_call.get("module_owner") is True,
        "bridge_runtime_binds_target_constants": delegate_call.get("target_min_bound") is True
        and delegate_call.get("target_max_bound") is True,
    }

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_candidate_search_evidence_alignment_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_candidate_search_evidence_alignment_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Candidate Search Evidence Alignment Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {check}: {'PASS' if passed else 'FAIL'}" for check, passed in checks.items()],
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
