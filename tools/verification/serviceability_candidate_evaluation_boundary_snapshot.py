"""Proof-only snapshot for the serviceability candidate evaluation boundary."""

from __future__ import annotations

import ast
import json
import sys
import time
from dataclasses import fields
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
MODULE_PATH = ROOT / "design_brain" / "serviceability_candidate_evaluation.py"

FORBIDDEN_IMPORT_ROOTS = {
    "inputs_page",
    "streamlit",
}

FORBIDDEN_SOURCE_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "session_state",
    "button_contract",
    "cta_",
    "cta intent",
    "cta rendering",
    "source_precedence",
    "publication",
    "published_item",
    "apply_routing",
    "one_click",
    "rendered_html",
    "ui_state",
    "ladder_order",
    "strategy_order",
    "bottom_reinforcement_increase",
    "depth_increase_restart",
    "width_increase_restart",
    "combined_geometry_reinforcement",
}

REQUIRED_INPUT_FIELDS = {"base_state"}
REQUIRED_UPDATE_FIELDS = {"updates"}
REQUIRED_EVALUATION_FIELDS = {
    "input_hash",
    "update_hash",
    "candidate_state_hash",
    "serviceability_utilisation",
    "previous_serviceability_utilisation",
    "serviceability_improved",
    "serviceability_compliant",
    "deflection_status",
    "crack_control_status",
    "strength_status",
    "code_compliance_status",
    "constructability_status",
    "geometry_status",
    "reinforcement_status",
    "blocker_status",
    "capacity_summary",
    "failure_flags",
    "engineering_status",
    "evaluation_hash",
}


def _read_module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def _module_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _forbidden_imports(imports: list[str]) -> list[str]:
    blocked: list[str] = []
    for imported in imports:
        root = imported.split(".", 1)[0]
        if root in FORBIDDEN_IMPORT_ROOTS:
            blocked.append(imported)
    return blocked


def _forbidden_source_hits(source: str) -> list[str]:
    lowered = source.lower()
    return sorted(term for term in FORBIDDEN_SOURCE_TERMS if term.lower() in lowered)


def _stable_payload(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"serviceability_candidate_evaluation_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_candidate_evaluation_boundary_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Serviceability Candidate Evaluation Boundary Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "This proves the boundary shape only.",
                "It does not prove lane decisions.",
                "It does not prove runtime parity.",
                "It does not prove SERVICEABILITY_GOVERNS lock.",
                "",
                "## Checks",
                "",
                f"- imports cleanly: `{snapshot['checks']['imports_cleanly']}`",
                f"- forbidden imports absent: `{snapshot['checks']['forbidden_imports_absent']}`",
                f"- forbidden source terms absent: `{snapshot['checks']['forbidden_source_terms_absent']}`",
                f"- required fields present: `{snapshot['checks']['required_fields_present']}`",
                f"- stable hashes: `{snapshot['checks']['stable_hashes']}`",
                f"- realistic result normalized: `{snapshot['checks']['realistic_result_normalized']}`",
                f"- ownership/lane policy absent: `{snapshot['checks']['ownership_and_lane_policy_absent']}`",
                "",
                "## Boundary Hashes",
                "",
                f"- input hash: `{snapshot['hashes']['input_hash']}`",
                f"- update hash: `{snapshot['hashes']['update_hash']}`",
                f"- candidate state hash: `{snapshot['hashes']['candidate_state_hash']}`",
                f"- evaluation hash: `{snapshot['hashes']['evaluation_hash']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    source = _read_module_source()
    imports = _module_imports(source)
    forbidden_imports = _forbidden_imports(imports)
    forbidden_source_hits = _forbidden_source_hits(source)

    modules_before = set(sys.modules)
    from design_brain.serviceability_candidate_evaluation import (  # noqa: WPS433
        ServiceabilityCandidateEvaluation,
        ServiceabilityCandidateInput,
        ServiceabilityCandidateUpdate,
        build_serviceability_candidate_state_hash,
        stable_serviceability_candidate_hash,
    )

    modules_after = set(sys.modules)
    imported_during_check = sorted(modules_after - modules_before)
    forbidden_runtime_imports = [
        name
        for name in imported_during_check
        if name.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS
    ]

    base_state = {
        "geometry": {
            "beam_width_mm": 300.0,
            "beam_depth_mm": 500.0,
            "span_mm": 6500.0,
        },
        "reinforcement": {
            "bottom_bar_count": 3,
            "bottom_bar_diameter_mm": 20,
        },
        "materials": {
            "concrete_strength_mpa": 32.0,
            "steel_strength_mpa": 500.0,
        },
        "actions": {
            "service_moment_knm": 260.0,
            "sustained_load_knm": 180.0,
        },
        "constraints": {
            "maximum_depth_mm": 650.0,
            "maximum_width_mm": 450.0,
            "geometry_locked": False,
        },
    }
    candidate_update = {
        "reinforcement": {
            "bottom_bar_count": 4,
        }
    }

    boundary_input = ServiceabilityCandidateInput(base_state=base_state)
    boundary_update = ServiceabilityCandidateUpdate(updates=candidate_update)
    candidate_state_hash = build_serviceability_candidate_state_hash(
        boundary_input.base_state,
        boundary_update.updates,
    )

    realistic_result = {
        "serviceability_utilisation": 0.96,
        "previous_serviceability_utilisation": 1.14,
        "serviceability_improved": True,
        "serviceability_compliant": True,
        "deflection_status": {
            "status": "PASS",
            "utilisation": 0.96,
            "limit": "ALLOWABLE",
        },
        "crack_control_status": {
            "status": "PASS",
            "utilisation": 0.88,
        },
        "strength_status": {
            "overall": "PASS",
            "bending": "PASS",
            "shear": "PASS",
        },
        "code_compliance_status": {
            "overall": "PASS",
        },
        "constructability_status": {
            "overall": "PASS",
            "congestion": "ACCEPTABLE",
        },
        "geometry_status": {
            "depth_mm": 500.0,
            "width_mm": 300.0,
            "status": "UNCHANGED",
        },
        "reinforcement_status": {
            "bottom_bar_count": 4,
            "increase": 1,
            "status": "INCREASED",
        },
        "blocker_status": {
            "blocked": False,
            "reasons": [],
        },
        "capacity_summary": {
            "deflection_utilisation": 0.96,
            "crack_utilisation": 0.88,
            "bending_strength_ratio": 1.18,
            "shear_strength_ratio": 1.42,
        },
        "failure_flags": {
            "serviceability_fail": False,
            "bending_fail": False,
            "shear_fail": False,
            "constructability_fail": False,
        },
        "engineering_status": {
            "overall": "PASS",
            "governing_check": "serviceability",
            "target_band_status": "TARGET",
        },
    }
    evaluation = ServiceabilityCandidateEvaluation(
        input_hash=boundary_input.input_hash,
        update_hash=boundary_update.update_hash,
        candidate_state_hash=candidate_state_hash,
        **realistic_result,
    ).with_evaluation_hash()
    repeated_evaluation = ServiceabilityCandidateEvaluation(
        input_hash=boundary_input.input_hash,
        update_hash=boundary_update.update_hash,
        candidate_state_hash=candidate_state_hash,
        **realistic_result,
    ).with_evaluation_hash()

    input_fields = {field.name for field in fields(ServiceabilityCandidateInput)}
    update_fields = {field.name for field in fields(ServiceabilityCandidateUpdate)}
    evaluation_fields = {field.name for field in fields(ServiceabilityCandidateEvaluation)}
    missing_fields = {
        "ServiceabilityCandidateInput": sorted(REQUIRED_INPUT_FIELDS - input_fields),
        "ServiceabilityCandidateUpdate": sorted(REQUIRED_UPDATE_FIELDS - update_fields),
        "ServiceabilityCandidateEvaluation": sorted(REQUIRED_EVALUATION_FIELDS - evaluation_fields),
    }

    evaluation_payload = evaluation.to_dict()
    stable_hashes = (
        boundary_input.input_hash == stable_serviceability_candidate_hash(base_state)
        and boundary_update.update_hash == stable_serviceability_candidate_hash(candidate_update)
        and candidate_state_hash == build_serviceability_candidate_state_hash(base_state, candidate_update)
        and evaluation.evaluation_hash == repeated_evaluation.evaluation_hash
        and _stable_payload(evaluation_payload) == _stable_payload(repeated_evaluation.to_dict())
    )
    realistic_result_normalized = all(
        evaluation_payload.get(key) == value for key, value in realistic_result.items()
    )

    checks = {
        "imports_cleanly": True,
        "forbidden_imports_absent": not forbidden_imports and not forbidden_runtime_imports,
        "forbidden_source_terms_absent": not forbidden_source_hits,
        "required_fields_present": not any(missing_fields.values()),
        "stable_hashes": stable_hashes,
        "realistic_result_normalized": realistic_result_normalized,
        "ownership_and_lane_policy_absent": not forbidden_source_hits,
    }

    snapshot = {
        "schema": "serviceability_candidate_evaluation_boundary_snapshot.v1",
        "result": "PASS" if all(checks.values()) else "FAIL",
        "purpose": (
            "Prove the permanent serviceability candidate evaluation boundary can "
            "represent evaluated deflection/crack candidates without importing "
            "page-owned logic."
        ),
        "scope_limits": {
            "proves_boundary_shape_only": True,
            "proves_lane_decisions": False,
            "proves_runtime_parity": False,
            "proves_serviceability_governs_lock": False,
        },
        "module": str(MODULE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "imports": imports,
        "forbidden_imports": forbidden_imports,
        "forbidden_runtime_imports": forbidden_runtime_imports,
        "forbidden_source_hits": forbidden_source_hits,
        "missing_required_fields": missing_fields,
        "checks": checks,
        "hashes": {
            "input_hash": boundary_input.input_hash,
            "update_hash": boundary_update.update_hash,
            "candidate_state_hash": candidate_state_hash,
            "evaluation_hash": evaluation.evaluation_hash,
            "repeat_evaluation_hash": repeated_evaluation.evaluation_hash,
        },
        "realistic_evaluator_shaped_result": evaluation_payload,
    }
    json_path, report_path = _write_artifacts(snapshot)

    if snapshot["result"] != "PASS":
        print("serviceability candidate evaluation boundary FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1

    print("serviceability candidate evaluation boundary PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
