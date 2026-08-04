"""Proof-only snapshot for the Design Brain candidate evaluation boundary.

This proves the boundary shape only. It does not prove ladder decisions,
runtime parity, or the BENDING_FAIL_GOVERNS lock.
"""

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
MODULE_PATH = ROOT / "design_brain" / "candidate_evaluation.py"

FORBIDDEN_IMPORT_ROOTS = {
    "inputs_page",
    "streamlit",
}

FORBIDDEN_SOURCE_TERMS = {
    "st.session_state",
    "button_contract",
    "cta_rendering",
    "source_precedence",
    "publication",
    "published_item",
    "apply_routing",
    "one_click",
    "session_state",
    "rendered_html",
    "ui_state",
    "ladder_order",
    "strategy_order",
}

REQUIRED_INPUT_FIELDS = {"base_state"}
REQUIRED_UPDATE_FIELDS = {"updates"}
REQUIRED_EVALUATION_FIELDS = {
    "input_hash",
    "candidate_state_hash",
    "update_hash",
    "bending_utilisation",
    "shear_utilisation",
    "serviceability_status",
    "geometry_status",
    "detailing_status",
    "spacing_status",
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
    json_path = ARTIFACT_DIR / f"candidate_evaluation_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"candidate_evaluation_boundary_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Candidate Evaluation Boundary Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "This proves the boundary shape only.",
                "It does not prove ladder decisions.",
                "It does not prove runtime parity.",
                "It does not prove BENDING_FAIL_GOVERNS lock.",
                "",
                "## Checks",
                "",
                f"- imports cleanly: `{snapshot['checks']['imports_cleanly']}`",
                f"- forbidden imports absent: `{snapshot['checks']['forbidden_imports_absent']}`",
                f"- forbidden source terms absent: `{snapshot['checks']['forbidden_source_terms_absent']}`",
                f"- required fields present: `{snapshot['checks']['required_fields_present']}`",
                f"- stable hashes: `{snapshot['checks']['stable_hashes']}`",
                f"- realistic result normalized: `{snapshot['checks']['realistic_result_normalized']}`",
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
    from design_brain.candidate_evaluation import (  # noqa: WPS433
        BeamCandidateEvaluation,
        BeamCandidateInput,
        BeamCandidateUpdate,
        build_candidate_state_hash,
        stable_candidate_evaluation_hash,
    )

    modules_after = set(sys.modules)
    imported_during_check = sorted(modules_after - modules_before)
    forbidden_runtime_imports = [
        name
        for name in imported_during_check
        if name.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS
    ]

    base_state = {
        "beam": {"depth_mm": 600.0, "width_mm": 300.0, "span_mm": 6000.0},
        "materials": {"fc_mpa": 40.0, "fsy_mpa": 500.0},
        "actions": {"m_star_knm": 820.0, "v_star_kn": 140.0},
        "reinforcement": {
            "bottom_bar_count": 4,
            "bottom_bar_diameter_mm": 20,
            "ligature_spacing_mm": 200,
        },
    }
    candidate_update = {
        "beam": {"depth_mm": 625.0},
        "reinforcement": {"bottom_bar_count": 5},
    }

    boundary_input = BeamCandidateInput(base_state=base_state)
    boundary_update = BeamCandidateUpdate(updates=candidate_update)
    candidate_state_hash = build_candidate_state_hash(
        boundary_input.base_state,
        boundary_update.updates,
    )

    realistic_result = {
        "bending_utilisation": 0.91,
        "shear_utilisation": 0.74,
        "serviceability_status": {"deflection": "PASS", "crack": "PASS"},
        "geometry_status": {"depth_width_ratio": 2.0833, "status": "CHECKED"},
        "detailing_status": {"anchorage": "PASS", "cover": "PASS"},
        "spacing_status": {"bottom_clear_spacing_mm": 112.0, "status": "PASS"},
        "capacity_summary": {
            "phi_mu_knm": 901.0,
            "phi_vu_kn": 189.0,
            "neutral_axis_depth_mm": 148.0,
        },
        "failure_flags": {
            "bending_fail": False,
            "shear_fail": False,
            "serviceability_fail": False,
        },
        "engineering_status": {"overall": "PASS", "governing_check": "bending"},
    }
    evaluation = BeamCandidateEvaluation(
        input_hash=boundary_input.state_hash,
        candidate_state_hash=candidate_state_hash,
        update_hash=boundary_update.update_hash,
        **realistic_result,
    ).with_evaluation_hash()
    repeated_evaluation = BeamCandidateEvaluation(
        input_hash=boundary_input.state_hash,
        candidate_state_hash=candidate_state_hash,
        update_hash=boundary_update.update_hash,
        **realistic_result,
    ).with_evaluation_hash()

    input_fields = {field.name for field in fields(BeamCandidateInput)}
    update_fields = {field.name for field in fields(BeamCandidateUpdate)}
    evaluation_fields = {field.name for field in fields(BeamCandidateEvaluation)}
    missing_fields = {
        "BeamCandidateInput": sorted(REQUIRED_INPUT_FIELDS - input_fields),
        "BeamCandidateUpdate": sorted(REQUIRED_UPDATE_FIELDS - update_fields),
        "BeamCandidateEvaluation": sorted(REQUIRED_EVALUATION_FIELDS - evaluation_fields),
    }

    evaluation_payload = evaluation.to_dict()
    stable_hashes = (
        boundary_input.state_hash == stable_candidate_evaluation_hash(base_state)
        and boundary_update.update_hash == stable_candidate_evaluation_hash(candidate_update)
        and candidate_state_hash == build_candidate_state_hash(base_state, candidate_update)
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
    }

    snapshot = {
        "result": "PASS" if all(checks.values()) else "FAIL",
        "purpose": (
            "Prove the Candidate Evaluation API can represent real evaluated beam "
            "candidates without importing page/UI/session/CTA/publication logic "
            "into Design Brain."
        ),
        "scope_limits": {
            "proves_boundary_shape_only": True,
            "proves_ladder_decisions": False,
            "proves_runtime_parity": False,
            "proves_bending_fail_governs_lock": False,
        },
        "module": str(MODULE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "imports": imports,
        "forbidden_imports": forbidden_imports,
        "forbidden_runtime_imports": forbidden_runtime_imports,
        "forbidden_source_hits": forbidden_source_hits,
        "missing_required_fields": missing_fields,
        "checks": checks,
        "hashes": {
            "input_hash": boundary_input.state_hash,
            "update_hash": boundary_update.update_hash,
            "candidate_state_hash": candidate_state_hash,
            "evaluation_hash": evaluation.evaluation_hash,
            "repeat_evaluation_hash": repeated_evaluation.evaluation_hash,
        },
        "realistic_evaluator_shaped_result": evaluation_payload,
    }
    json_path, report_path = _write_artifacts(snapshot)

    if snapshot["result"] != "PASS":
        print("candidate evaluation boundary FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1

    print("candidate evaluation boundary PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
