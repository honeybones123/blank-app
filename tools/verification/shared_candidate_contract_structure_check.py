from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_CONTRACT = Path("artifacts/contracts/shared_candidate_contract.json")
DEFAULT_ALIAS_MAP = Path("artifacts/contracts/shared_candidate_alias_map.json")

REQUIRED_ALIAS_MAP_TOP_LEVEL_KEYS = {
    "metadata",
    "coverage_summary",
    "mappings",
    "mismatch_inventory",
    "phase_5_5_recommendation",
}

REQUIRED_MAPPING_KEYS = {
    "canonical_field",
    "product_fields",
    "verifier_fields",
    "status",
    "drift_risk",
    "notes",
}

DEFAULT_ALLOWED_STATUS_VALUES = {
    "exact match",
    "alias required",
    "missing in product",
    "missing in verifier",
    "ambiguous",
}

DEFAULT_ALLOWED_DRIFT_RISK_VALUES = {
    "low",
    "medium",
    "high",
}

REQUIRED_IDENTITY_FIELDS = {
    "candidate_id",
    "source_candidate_id",
    "family",
    "candidate_type",
}

REQUIRED_SEARCH_EVIDENCE_FIELDS = {
    "candidate_search_exhaustive",
    "search_scope",
    "target_low",
    "target_high",
    "candidate_rows",
}


def _load_json(path: Path, errors: list[str], label: str) -> Any:
    if not path.exists():
        errors.append(f"{label}_missing:{path}")
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        errors.append(f"{label}_json_parse_failed:{path}:{exc}")
        return None


def _as_string_set(value: Any, fallback: set[str]) -> set[str]:
    if not isinstance(value, list):
        return set(fallback)
    out = {str(item) for item in value if str(item)}
    return out or set(fallback)


def _required_candidate_fields(contract: dict[str, Any]) -> set[str]:
    candidate_schema = contract.get("candidate_schema")
    if not isinstance(candidate_schema, dict):
        return set()
    fields = candidate_schema.get("required_fields")
    if not isinstance(fields, list):
        return set()
    return {str(field) for field in fields if str(field)}


def _validate_contract(contract: Any, errors: list[str]) -> set[str]:
    if not isinstance(contract, dict):
        errors.append("contract_root_not_object")
        return set()
    for key in ("contract_metadata", "candidate_schema", "evaluation_schema", "shared_evidence_schema"):
        if key not in contract:
            errors.append(f"contract_missing_top_level_key:{key}")
    required = _required_candidate_fields(contract)
    if not required:
        errors.append("contract_candidate_schema_required_fields_missing_or_empty")
    fields_obj = (contract.get("candidate_schema") or {}).get("fields") if isinstance(contract.get("candidate_schema"), dict) else None
    if not isinstance(fields_obj, dict):
        errors.append("contract_candidate_schema_fields_not_object")
    else:
        for field in sorted(required):
            if field not in fields_obj:
                errors.append(f"contract_required_candidate_field_missing_definition:{field}")
    return required


def _validate_alias_map(alias_map: Any, required_candidate_fields: set[str], errors: list[str]) -> None:
    if not isinstance(alias_map, dict):
        errors.append("alias_map_root_not_object")
        return

    for key in sorted(REQUIRED_ALIAS_MAP_TOP_LEVEL_KEYS):
        if key not in alias_map:
            errors.append(f"alias_map_missing_top_level_key:{key}")

    allowed_status = _as_string_set(alias_map.get("allowed_status_values"), DEFAULT_ALLOWED_STATUS_VALUES)
    allowed_risk = _as_string_set(alias_map.get("allowed_drift_risk_values"), DEFAULT_ALLOWED_DRIFT_RISK_VALUES)

    mappings = alias_map.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        errors.append("alias_map_mappings_missing_or_empty")
        return

    fields_seen: set[str] = set()
    for index, row in enumerate(mappings):
        if not isinstance(row, dict):
            errors.append(f"alias_map_mapping_row_not_object:index={index}")
            continue
        for key in sorted(REQUIRED_MAPPING_KEYS):
            if key not in row:
                errors.append(f"alias_map_mapping_missing_key:index={index}:key={key}")
        canonical = str(row.get("canonical_field") or "").strip()
        if not canonical:
            errors.append(f"alias_map_mapping_empty_canonical_field:index={index}")
        elif canonical in fields_seen:
            errors.append(f"alias_map_duplicate_canonical_field:{canonical}")
        else:
            fields_seen.add(canonical)

        product_fields = row.get("product_fields")
        verifier_fields = row.get("verifier_fields")
        if not isinstance(product_fields, list):
            errors.append(f"alias_map_product_fields_not_list:{canonical or index}")
        if not isinstance(verifier_fields, list):
            errors.append(f"alias_map_verifier_fields_not_list:{canonical or index}")

        status = str(row.get("status") or "").strip()
        if status not in allowed_status:
            errors.append(f"alias_map_invalid_status:{canonical or index}:{status}")

        risk = str(row.get("drift_risk") or "").strip()
        if risk not in allowed_risk:
            errors.append(f"alias_map_invalid_drift_risk:{canonical or index}:{risk}")

    for field in sorted(required_candidate_fields):
        if field not in fields_seen:
            errors.append(f"required_contract_candidate_field_missing_alias_mapping:{field}")

    for field in sorted(REQUIRED_IDENTITY_FIELDS):
        if field not in fields_seen:
            errors.append(f"required_identity_family_type_mapping_missing:{field}")

    for field in sorted(REQUIRED_SEARCH_EVIDENCE_FIELDS):
        if field not in fields_seen:
            errors.append(f"required_search_evidence_mapping_missing:{field}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Failing structural check for shared candidate contract and alias-map JSON. "
            "Does not inspect saved artifacts or enforce coverage gaps."
        )
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--alias-map", type=Path, default=DEFAULT_ALIAS_MAP)
    parser.add_argument("--json", action="store_true", help="Print machine-readable result JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or sys.argv[1:]))
    errors: list[str] = []
    contract = _load_json(args.contract, errors, "contract")
    alias_map = _load_json(args.alias_map, errors, "alias_map")

    required_candidate_fields: set[str] = set()
    if contract is not None:
        required_candidate_fields = _validate_contract(contract, errors)
    if alias_map is not None:
        _validate_alias_map(alias_map, required_candidate_fields, errors)

    result = {
        "check_id": "design_brain.shared_candidate_contract_structure_check",
        "contract_path": str(args.contract),
        "alias_map_path": str(args.alias_map),
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "non_runtime": True,
        "artifact_coverage_checked": False,
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif errors:
        print("Shared candidate contract structural check FAILED")
        for error in errors:
            print(f"- {error}")
    else:
        print("Shared candidate contract structural check PASS")
        print(f"- contract: {args.contract}")
        print(f"- alias map: {args.alias_map}")
        print(f"- required candidate fields mapped: {len(required_candidate_fields)}")
        print("- artifact coverage gaps: not checked by this structural checker")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
