from __future__ import annotations

import ast
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
MODULE_PATH = ROOT / "design_brain" / "display_formatting.py"

from design_brain.display_formatting import build_display_model_from_family_result  # noqa: E402
from design_brain.display_formatting_contract import (  # noqa: E402
    CONTRACT_PATH,
    contract_hash,
    display_model_contract,
    formatting_must_not_own,
    formatting_owns,
    load_design_guide_formatting_contract,
    required_sections,
    source_contract,
    status_colour_contract,
    verifier_contract,
)
from design_brain.shared.schemas import FamilyResult  # noqa: E402


FORBIDDEN_IMPORT_ROOTS = {"inputs_page", "streamlit"}
FORBIDDEN_RUNTIME_TERMS = {
    "st.session_state",
    "session_state",
    "family_strategy_for",
    "classify_family",
    "candidate_search",
    "repair_ladder",
    "optimisation_ladder",
    "button_contract",
    "build_design_guide_apply_button_contract",
    "record_design_guide_publication_snapshot",
    "apply_routing",
    "one_click",
}
REQUIRED_SECTIONS = {
    "Outcome",
    "Recommendation",
    "Why Selected",
    "Evidence",
    "Blockers",
    "Status",
}


def _imports(source: str) -> list[str]:
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _base_result() -> FamilyResult:
    return FamilyResult(
        family_id="SHEAR_FAIL_GOVERNS",
        is_applicable=True,
        governing_score=1.18,
        status="REPAIR_REQUIRED",
        selected_candidate={
            "candidate_id": "shear_repair_001",
            "updates": {"s_lig": 125},
            "source": "SHEAR_FAIL_GOVERNS",
        },
        updates={"s_lig": 125},
        blockers=[{"reason": "spacing limit reached", "owner": "SHEAR_FAIL_GOVERNS"}],
        evidence={
            "why_selected": "Shear utilisation exceeds capacity.",
            "ranking_evidence": {"selected_candidate_id": "shear_repair_001"},
            "exact_stop_proof": {"allowed": False, "owner": "SHEAR_FAIL_GOVERNS"},
            "exhausted_proof": {"allowed": False, "owner": "SHEAR_FAIL_GOVERNS"},
            "target_band_status": {"shear": "outside"},
        },
        publication={"published": True, "source": "mutated outside formatting"},
        cta_contract={"enabled": True, "action_type": "apply_resolved_candidate"},
        lock_proof={"runtime_authority": "run_shear_fail_governs_ladder_runtime"},
    )


def _section_titles(model: Any) -> tuple[str, ...]:
    return tuple(section.title for section in model.sections)


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_formatting_contract_v3_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_formatting_contract_v3_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide Formatting Contract v3 Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Boundary",
                "",
                "- Input: selected `FamilyResult`.",
                "- Output: `DisplayModel`.",
                "- CTA/publication/apply/session ownership stays outside formatting.",
                "",
                "## Hashes",
                "",
                f"- contract_hash: `{snapshot['contract_hash']}`",
                f"- base_display_hash: `{snapshot['hashes']['base_display']}`",
                f"- mutated_shared_hash: `{snapshot['hashes']['mutated_shared']}`",
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    source = MODULE_PATH.read_text(encoding="utf-8", errors="replace")
    imports = _imports(source)
    forbidden_imports = [item for item in imports if item.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS]
    forbidden_terms = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term.lower() in source.lower())

    base = _base_result()
    base_model = build_display_model_from_family_result(base)
    mutated_shared = replace(
        base,
        publication={"published": False, "source": "changed publication outside formatting"},
        cta_contract={"enabled": False, "action_type": "different"},
    )
    mutated_shared_model = build_display_model_from_family_result(mutated_shared)
    mutated_recommendation = replace(base, selected_candidate={"candidate_id": "different", "updates": {"s_lig": 100}})
    mutated_recommendation_model = build_display_model_from_family_result(mutated_recommendation)
    mutated_blocker = replace(base, blockers=[{"reason": "different blocker", "owner": "SHEAR_FAIL_GOVERNS"}])
    mutated_blocker_model = build_display_model_from_family_result(mutated_blocker)
    blue_model = build_display_model_from_family_result(
        replace(base, family_id="BENDING_OVERDESIGN_GOVERNS", status="OPTIMISATION_AVAILABLE")
    )
    green_model = build_display_model_from_family_result(
        replace(base, family_id="TARGET_BAND_REACHED", status="COMPLIANT", selected_candidate=None, blockers=[])
    )

    contract = load_design_guide_formatting_contract()
    display_contract = display_model_contract()
    source_rules = source_contract()
    section_titles = set(_section_titles(base_model))
    checks = {
        "schema_v3": contract.get("schema") == "design_brain.design_guide_formatting_contract.v3",
        "input_is_family_result": display_contract.get("output_type") == "DisplayModel"
        and source_rules.get("input_type") == "FamilyResult",
        "single_engineering_source": source_rules.get("single_engineering_source") == "Selected Family Result",
        "does_not_merge_multiple_families": source_rules.get("must_not_merge_engineering_content_from_multiple_families") is True,
        "required_sections_from_contract": REQUIRED_SECTIONS.issubset(set(required_sections())),
        "required_sections_in_model": REQUIRED_SECTIONS.issubset(section_titles),
        "status_colours_locked": {"RED", "BLUE", "GREEN"}.issubset(set(status_colour_contract())),
        "red_mapping": base_model.colour == "RED",
        "blue_mapping": blue_model.colour == "BLUE",
        "green_mapping": green_model.colour == "GREEN",
        "forbidden_imports_absent": not forbidden_imports,
        "forbidden_runtime_terms_absent": not forbidden_terms,
        "shared_publication_cta_ignored": base_model.presentation_hash == mutated_shared_model.presentation_hash
        and base_model.source_family_result_hash == mutated_shared_model.source_family_result_hash,
        "recommendation_change_changes_display": base_model.presentation_hash != mutated_recommendation_model.presentation_hash,
        "blocker_change_changes_display": base_model.presentation_hash != mutated_blocker_model.presentation_hash,
        "selected_recommendation_preserved": (
            base_model.to_dict()["sections"][1]["items"][0]["candidate_id"]
            == base.selected_candidate["candidate_id"]
        ),
        "blocker_preserved": base_model.to_dict()["sections"][4]["items"][0]["reason"] == base.blockers[0]["reason"],
        "exact_stop_displayed_not_decided": "Exact Stop" in section_titles
        and base_model.to_dict()["sections"][_section_titles(base_model).index("Exact Stop")]["items"][0]["owner"]
        == "SHEAR_FAIL_GOVERNS",
        "exhausted_displayed_not_decided": "Exhausted Reason" in section_titles
        and base_model.to_dict()["sections"][_section_titles(base_model).index("Exhausted Reason")]["items"][0]["owner"]
        == "SHEAR_FAIL_GOVERNS",
        "contract_ownership_lists_present": bool(formatting_owns()) and bool(formatting_must_not_own()),
        "verifier_contract_loaded": bool(verifier_contract().get("must_prove")),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "design_guide_formatting_contract_v3_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "contract_path": str(CONTRACT_PATH),
        "contract_hash": contract_hash(),
        "checks": checks,
        "imports": imports,
        "forbidden_imports": forbidden_imports,
        "forbidden_terms": forbidden_terms,
        "sections": list(_section_titles(base_model)),
        "hashes": {
            "base_display": base_model.presentation_hash,
            "mutated_shared": mutated_shared_model.presentation_hash,
            "mutated_recommendation": mutated_recommendation_model.presentation_hash,
            "mutated_blocker": mutated_blocker_model.presentation_hash,
        },
        "models": {
            "base": base_model.to_dict(),
            "blue": blue_model.to_dict(),
            "green": green_model.to_dict(),
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("Design Guide formatting contract v3 FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("Design Guide formatting contract v3 PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
