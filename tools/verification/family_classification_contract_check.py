from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTRACT_MODULE_PATH = ROOT / "design_brain" / "contracts" / "family_classification_contract.py"
FACADE_MODULE_PATH = ROOT / "design_brain" / "family_classification.py"

EXPECTED_ALLOWED_FAMILY_IDS = (
    "EXACT_STOP_PROVEN",
    "LOCKED_NO_REPAIR",
    "GEOMETRY_DETAILING_GOVERNS",
    "BENDING_AND_SHEAR_FAIL_GOVERN",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS",
    "BENDING_FAIL_GOVERNS",
    "SHEAR_FAIL_GOVERNS",
    "SERVICEABILITY_GOVERNS",
    "COMBINED_OVERDESIGN",
    "BENDING_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "TARGET_BAND_REACHED",
)

EXPECTED_PRIORITY_ORDER = EXPECTED_ALLOWED_FAMILY_IDS

EXPECTED_STATE_INPUTS = {
    "bending_utilisation",
    "shear_utilisation",
    "bending_state",
    "shear_state",
    "serviceability_state",
    "geometry_detailing_state",
    "minimum_bending_reo_state",
    "minimum_shear_reo_state",
    "geometry_locked",
    "reo_locked",
    "can_strengthen_bending",
    "can_strengthen_shear",
    "can_optimise_bending_without_hurting_shear",
    "can_optimise_shear_without_hurting_bending",
    "exact_stop_available",
    "no_valid_repair_available",
}

EXPECTED_UTILISATION_BANDS = {
    "FAIL": {"operator": ">", "threshold": 1.0},
    "TARGET": {
        "lower_operator": ">=",
        "lower_threshold": 0.85,
        "upper_operator": "<=",
        "upper_threshold": 1.0,
    },
    "OVERDESIGNED": {"operator": "<", "threshold": 0.85},
    "SEVERELY_OVERDESIGNED": {"operator": "<", "threshold": 0.7},
}

REQUIRED_GLOBAL_PROTECTION_RULE_FRAGMENTS = {
    "Never optimise an overdesigned check",
    "Never reduce shared geometry",
    "Never allow inactive-family recommendations to publish",
    "Mixed strengthen-and-optimise families",
    "Classification selects the governing family only",
}

REQUIRED_TOP_LEVEL_KEYS = {
    "schema",
    "contract_identity",
    "utilisation_bands",
    "allowed_family_ids",
    "classification_priority_order",
    "required_state_inputs",
    "required_utilisation_status_fields",
    "global_protection_rules",
    "classification_rules",
    "selected_family_output_schema",
    "inactive_family_evidence_schema",
    "shared_page_owned_exclusions",
    "movement_rules",
    "required_gates",
}

REQUIRED_SELECTED_OUTPUT_FIELDS = {
    "selected_family_id",
    "classification_reason",
    "classification_priority",
    "bending_state",
    "shear_state",
    "governing_checks",
    "inactive_family_evidence",
    "terminal_status",
    "blocked_reason",
    "contract_version",
    "classification_hash",
}

REQUIRED_INACTIVE_FIELDS = {
    "family_id",
    "evaluated",
    "eligible",
    "rejection_reason",
    "evidence",
    "priority_rank",
}

REQUIRED_EXCLUSIONS = {
    "family strategy ladders",
    "repair candidate generation",
    "CTA rendering",
    "CTA source precedence",
    "publication rendering",
    "apply routing",
    "one-click orchestration",
    "visible wording",
    "UI/session/debug behaviour",
}

FORBIDDEN_TOP_LEVEL_KEYS = {
    "strategy_ladder",
    "repair_ladder",
    "candidate_generation",
    "cta_rendering",
    "publication_rendering",
    "apply_routing",
    "visible_wording",
    "ui_session_debug",
}


def _load_contract_module() -> Any:
    spec = importlib.util.spec_from_file_location("family_classification_contract_file", CONTRACT_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load contract module: {CONTRACT_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_for(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _validate_contract_shape(module: Any, contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(contract.keys()))
    failures.extend(f"missing_top_level_key:{key}" for key in missing)
    forbidden = sorted(FORBIDDEN_TOP_LEVEL_KEYS & set(contract.keys()))
    failures.extend(f"forbidden_top_level_key:{key}" for key in forbidden)

    if contract.get("schema") != "design_brain.family_classification_contract.v1":
        failures.append("schema_mismatch")

    identity = contract.get("contract_identity") or {}
    if identity.get("contract_id") != "DESIGN_BRAIN_FAMILY_CLASSIFICATION":
        failures.append("contract_id_mismatch")
    if bool(identity.get("product_driving")):
        failures.append("contract_must_not_be_product_driving")

    allowed = tuple(module.allowed_family_ids())
    if allowed != EXPECTED_ALLOWED_FAMILY_IDS:
        failures.append("allowed_family_ids_mismatch")

    priority = tuple(module.classification_priority_order())
    if priority != EXPECTED_PRIORITY_ORDER:
        failures.append("classification_priority_order_mismatch")
    if set(priority) != set(allowed):
        failures.append("priority_order_does_not_cover_allowed_families")
    if len(priority) != len(set(priority)):
        failures.append("priority_order_contains_duplicates")
    expected_priority_numbers = list(range(1, len(priority) + 1))

    rules = module.classification_rules()
    if set(rules) != set(allowed):
        failures.append("classification_rules_do_not_match_allowed_families")
    seen_priorities: set[int] = set()
    actual_priority_numbers: list[int] = []
    for family_id in allowed:
        rule = dict(rules.get(family_id) or {})
        if rule.get("family_id") != family_id:
            failures.append(f"{family_id}:family_id_mismatch")
        if "priority" not in rule:
            failures.append(f"{family_id}:missing_priority")
        else:
            try:
                priority_number = int(rule.get("priority"))
            except (TypeError, ValueError):
                failures.append(f"{family_id}:invalid_priority")
            else:
                if priority_number in seen_priorities:
                    failures.append(f"{family_id}:duplicate_priority:{priority_number}")
                seen_priorities.add(priority_number)
                actual_priority_numbers.append(priority_number)
        for field in (
            "rule_type",
            "condition_summary",
            "select_when",
            "must_not_select_when",
            "required_evidence",
            "output_requirements",
        ):
            if field not in rule:
                failures.append(f"{family_id}:missing_rule_field:{field}")
        if not isinstance(rule.get("select_when"), list) or not rule.get("select_when"):
            failures.append(f"{family_id}:select_when_empty")
        if not isinstance(rule.get("required_evidence"), list) or not rule.get("required_evidence"):
            failures.append(f"{family_id}:required_evidence_empty")
        if not isinstance(rule.get("output_requirements"), list) or not rule.get("output_requirements"):
            failures.append(f"{family_id}:output_requirements_empty")
        if not str(rule.get("condition_summary") or "").strip():
            failures.append(f"{family_id}:condition_summary_empty")

    if sorted(actual_priority_numbers) != expected_priority_numbers:
        failures.append("priority_numbers_not_unique_ordered_sequence")

    bands = module.utilisation_bands()
    if set(bands) != set(EXPECTED_UTILISATION_BANDS):
        failures.append("utilisation_bands_keys_mismatch")
    for band_name, expected in EXPECTED_UTILISATION_BANDS.items():
        actual = bands.get(band_name) or {}
        for field, expected_value in expected.items():
            actual_value = actual.get(field)
            if isinstance(expected_value, float):
                try:
                    actual_numeric = float(actual_value)
                except (TypeError, ValueError):
                    failures.append(f"utilisation_band:{band_name}:{field}_invalid")
                    continue
                if actual_numeric != expected_value:
                    failures.append(f"utilisation_band:{band_name}:{field}_mismatch")
            elif actual_value != expected_value:
                failures.append(f"utilisation_band:{band_name}:{field}_mismatch")

    state_inputs = set(module.required_state_inputs())
    missing_state_inputs = sorted(EXPECTED_STATE_INPUTS - state_inputs)
    failures.extend(f"required_state_inputs_missing:{field}" for field in missing_state_inputs)

    selected_fields = set(module.selected_family_output_required_fields())
    missing_selected = sorted(REQUIRED_SELECTED_OUTPUT_FIELDS - selected_fields)
    failures.extend(f"selected_output_missing_field:{field}" for field in missing_selected)

    inactive_fields = set(module.inactive_family_evidence_required_fields())
    missing_inactive = sorted(REQUIRED_INACTIVE_FIELDS - inactive_fields)
    failures.extend(f"inactive_evidence_missing_field:{field}" for field in missing_inactive)

    exclusions = set(module.shared_page_owned_exclusions())
    missing_exclusions = sorted(REQUIRED_EXCLUSIONS - exclusions)
    failures.extend(f"missing_shared_page_owned_exclusion:{field}" for field in missing_exclusions)

    protection_rules = tuple(module.global_protection_rules())
    for fragment in REQUIRED_GLOBAL_PROTECTION_RULE_FRAGMENTS:
        if not any(fragment in rule for rule in protection_rules):
            failures.append(f"missing_global_protection_rule:{fragment}")

    movement = contract.get("movement_rules") or {}
    must_not_import = set(str(value) for value in movement.get("must_not_import") or ())
    if not {"inputs_page", "streamlit"} <= must_not_import:
        failures.append("movement_rules_missing_inputs_page_streamlit_import_ban")
    if not bool(movement.get("classification_only")):
        failures.append("movement_rules_classification_only_not_true")

    if not module.required_state_inputs():
        failures.append("required_state_inputs_empty")
    if not module.required_utilisation_status_fields():
        failures.append("required_utilisation_status_fields_empty")
    if not module.required_family_classification_gates():
        failures.append("required_gates_empty")
    return failures


def _validate_import_boundaries(module: Any) -> list[str]:
    failures: list[str] = []
    for path in (CONTRACT_MODULE_PATH, FACADE_MODULE_PATH):
        source = _source_for(path)
        if "inputs_page" in source:
            failures.append(f"{path.name}:imports_or_mentions_inputs_page")
        if "streamlit" in source or "import st" in source:
            failures.append(f"{path.name}:imports_or_mentions_streamlit")

    before_inputs_page = "inputs_page" in sys.modules
    before_streamlit = "streamlit" in sys.modules
    facade = importlib.import_module("design_brain.family_classification")
    if not facade.allowed_family_ids():
        failures.append("family_classification_facade_allowed_family_ids_empty")
    if "inputs_page" in sys.modules and not before_inputs_page:
        failures.append("facade_import_loaded_inputs_page")
    if "streamlit" in sys.modules and not before_streamlit:
        failures.append("facade_import_loaded_streamlit")
    if set(facade.allowed_family_ids()) != set(module.allowed_family_ids()):
        failures.append("facade_allowed_family_ids_mismatch")
    return failures


def _write_human_contract(contract: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Brain Family Classification Contract",
        "",
        "Status: active scaffold",
        "",
        "## Purpose",
        "",
        "This contract defines how Design Brain will choose one active governing family before that family runs its own internal strategy ladder.",
        "",
        "It is classification-only. It does not own repair strategy ladders, candidate generation, CTA rendering, CTA source precedence, publication rendering, apply routing, one-click orchestration, visible wording, or UI/session/debug behaviour.",
        "",
        "## Allowed Families",
        "",
    ]
    for family_id in contract.get("allowed_family_ids") or []:
        lines.append(f"- `{family_id}`")
    lines.extend(["", "## Utilisation Bands", ""])
    for band_name, band in (contract.get("utilisation_bands") or {}).items():
        lines.append(f"- `{band_name}`: {band.get('summary')}")
    lines.extend(["", "## Required Whole-Beam State Inputs", ""])
    for field in contract.get("required_state_inputs") or []:
        lines.append(f"- `{field}`")
    lines.extend(["", "## Priority Order", ""])
    for index, family_id in enumerate(contract.get("classification_priority_order") or [], start=1):
        rule = (contract.get("classification_rules") or {}).get(family_id) or {}
        summary = rule.get("condition_summary") or ""
        lines.append(f"{index}. `{family_id}` - {summary}")
    lines.extend(["", "## Global Protection Rules", ""])
    for rule in contract.get("global_protection_rules") or []:
        lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "## Required Output",
            "",
            "A normalized classification result must contain:",
            "",
        ]
    )
    for field in ((contract.get("selected_family_output_schema") or {}).get("required_fields") or []):
        lines.append(f"- `{field}`")
    lines.extend(
        [
            "",
            "## Inactive Family Evidence",
            "",
            "Inactive families may carry diagnostic evidence, but they must not publish final CTA, summary, target-band guidance, fallback output, one-click action, or selected repair output.",
            "",
            "## Shared/Page-Owned Exclusions",
            "",
        ]
    )
    for exclusion in contract.get("shared_page_owned_exclusions") or []:
        lines.append(f"- {exclusion}")
    lines.extend(
        [
            "",
            "## Movement Rule",
            "",
            "This contract is not product-driving yet. Moving live classification out of `inputs_page.py` requires focused classification snapshots, selected-family publication gate proof, inactive-family leakage proof, and C1/C2/C3 product gates.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(output: dict[str, Any], path: Path) -> None:
    lines = [
        "# Family Classification Contract Check",
        "",
        f"Status: {output.get('status')}",
        "",
        "## Contract",
        "",
        f"- JSON: `{output.get('contract_path')}`",
        f"- Loader: `{output.get('contract_module_path')}`",
        f"- Facade: `{output.get('facade_module_path')}`",
        f"- Human contract: `{output.get('human_contract_path')}`",
        "",
        "## Checks",
        "",
        "- contract JSON loads through the Design Brain loader",
        "- every allowed family has a classification rule",
        "- priority order is explicit and complete",
        "- priority numbers are unique and ordered",
        "- utilisation bands match FAIL/TARGET/OVERDESIGNED/SEVERELY_OVERDESIGNED thresholds",
        "- required whole-beam state inputs are present",
        "- global protection rules are present",
        "- selected-family output schema includes required fields",
        "- inactive-family evidence schema includes required fields",
        "- shared/page-owned exclusions are present",
        "- loader/facade do not import `inputs_page.py` or Streamlit",
        "",
        "## Failures",
        "",
    ]
    lines.extend([f"- {failure}" for failure in output.get("failures") or []] or ["- none"])
    lines.extend(["", "## Output", "", f"- `{output.get('artifact')}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    module = _load_contract_module()
    contract = module.load_family_classification_contract()
    human_path = AUDIT_DIR / "family_classification_contract.md"
    _write_human_contract(contract, human_path)

    failures = _validate_contract_shape(module, contract) + _validate_import_boundaries(module)
    status = "PASS" if not failures else "FAIL"
    artifact_path = ARTIFACT_DIR / f"family_classification_contract_check_{stamp}.json"
    report_path = AUDIT_DIR / f"family_classification_contract_check_{stamp}.md"
    output = {
        "schema": "family_classification_contract_check.v1",
        "status": status,
        "generated_at": stamp,
        "artifact": str(artifact_path),
        "report": str(report_path),
        "contract_path": str(module.CONTRACT_PATH),
        "contract_module_path": str(CONTRACT_MODULE_PATH),
        "facade_module_path": str(FACADE_MODULE_PATH),
        "human_contract_path": str(human_path),
        "allowed_family_ids": list(module.allowed_family_ids()),
        "classification_priority_order": list(module.classification_priority_order()),
        "utilisation_bands": module.utilisation_bands(),
        "required_state_inputs": list(module.required_state_inputs()),
        "global_protection_rules": list(module.global_protection_rules()),
        "selected_family_output_required_fields": list(module.selected_family_output_required_fields()),
        "inactive_family_evidence_required_fields": list(module.inactive_family_evidence_required_fields()),
        "shared_page_owned_exclusions": list(module.shared_page_owned_exclusions()),
        "terminal_family_ids": list(module.terminal_family_ids()),
        "failures": failures,
    }
    artifact_path.write_text(json.dumps(output, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(output, report_path)
    print(
        json.dumps(
            {
                "status": status,
                "artifact": str(artifact_path),
                "report": str(report_path),
                "human_contract": str(human_path),
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
