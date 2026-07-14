from __future__ import annotations

import ast
import json
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FAMILIES_DIR = ROOT / "design_brain" / "families"
SHARED_DIR = ROOT / "design_brain" / "shared"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


REQUIRED_FAMILIES: dict[str, dict[str, str]] = {
    "bending_fail_governs": {
        "family_id": "BENDING_FAIL_GOVERNS",
        "runtime_api": "run_bending_fail_governs_ladder_runtime",
    },
    "shear_fail_governs": {
        "family_id": "SHEAR_FAIL_GOVERNS",
        "runtime_api": "run_shear_fail_governs_ladder_runtime",
    },
    "bending_and_shear_fail_govern": {
        "family_id": "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "runtime_api": "run_combined_bending_shear_fail_runtime",
    },
    "bending_fail_shear_overdesign_governs": {
        "family_id": "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "api": "evaluate_bending_fail_shear_overdesign_governs",
    },
    "shear_fail_bending_overdesign_governs": {
        "family_id": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "api": "evaluate_shear_fail_bending_overdesign_governs",
    },
    "bending_overdesign_governs": {
        "family_id": "BENDING_OVERDESIGN_GOVERNS",
        "api": "evaluate_bending_overdesign_governs",
    },
    "shear_overdesign_governs": {
        "family_id": "SHEAR_OVERDESIGN_GOVERNS",
        "runtime_api": "run_shear_overdesign_governs_runtime",
    },
    "bending_and_shear_overdesign_govern": {
        "family_id": "COMBINED_OVERDESIGN_GOVERNS",
        "api": "evaluate_bending_and_shear_overdesign_govern",
    },
    "serviceability_governs": {
        "family_id": "SERVICEABILITY_GOVERNS",
        "api": "evaluate_serviceability_governs",
    },
    "target_band_reached": {
        "family_id": "TARGET_BAND_REACHED",
        "api": "evaluate_target_band_reached",
    },
    "locked_no_repair": {
        "family_id": "LOCKED_NO_REPAIR",
        "api": "evaluate_locked_no_repair",
    },
    "exact_stop_proven": {
        "family_id": "EXACT_STOP_PROVEN",
        "api": "evaluate_exact_stop_proven",
    },
}

FORBIDDEN_TOP_LEVEL_FAMILY_FOLDERS = {
    "min_bending_reo_governs",
    "min_shear_reo_governs",
    "geometry_detailing_governs",
    "ductility_governs",
    "spacing_governs",
}

FAMILY_SPECIFIC_IDENTIFIERS = [
    "BENDING_FAIL_GOVERNS",
    "SHEAR_FAIL_GOVERNS",
    "BENDING_AND_SHEAR_FAIL_GOVERN",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    "BENDING_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "BENDING_AND_SHEAR_OVERDESIGN_GOVERN",
    "COMBINED_BENDING_SHEAR_FAIL",
    "bending fail",
    "shear fail",
    "overdesign",
    "min_bending",
    "min_shear",
    "ductility",
    "geometry_detailing",
]

LEGACY_FILES_TO_SCAN = [
    ROOT / "design_brain" / "engine.py",
    ROOT / "inputs_page.py",
]

ALLOWED_FAMILY_SUPPORT_MODULES = {"base"}

ALLOWED_COMPATIBILITY_IMPORTS = {
    ("bending_fail_governs", "design_brain.families.bending_fail"),
    ("shear_fail_governs", "design_brain.families.shear_fail"),
    ("bending_and_shear_fail_govern", "design_brain.families.combined_bending_shear_fail"),
    ("bending_and_shear_overdesign_govern", "design_brain.families.combined_cleanup"),
    ("bending_overdesign_governs", "design_brain.families.bending_cleanup"),
    ("shear_overdesign_governs", "design_brain.families.shear_cleanup"),
}


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _functions_in(path: Path) -> set[str]:
    tree = _parse(path)
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def _assignments_in(path: Path) -> dict[str, Any]:
    tree = _parse(path)
    values: dict[str, Any] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        values[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass
    return values


def _family_internal_imports(path: Path, current_family: str) -> tuple[list[str], list[str]]:
    imports: list[str] = []
    compatibility_imports: list[str] = []
    tree = _parse(path)
    for node in ast.walk(tree):
        module = ""
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("design_brain.families."):
                parts = module.split(".")
                if len(parts) >= 3 and parts[2] in ALLOWED_FAMILY_SUPPORT_MODULES:
                    continue
                if (current_family, module) in ALLOWED_COMPATIBILITY_IMPORTS:
                    compatibility_imports.append(module)
                    continue
                if len(parts) >= 3 and parts[2] != current_family:
                    imports.append(module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if module.startswith("design_brain.families."):
                    parts = module.split(".")
                    if len(parts) >= 3 and parts[2] in ALLOWED_FAMILY_SUPPORT_MODULES:
                        continue
                    if (current_family, module) in ALLOWED_COMPATIBILITY_IMPORTS:
                        compatibility_imports.append(module)
                        continue
                    if len(parts) >= 3 and parts[2] != current_family:
                        imports.append(module)
    return imports, compatibility_imports


def _line_hits(path: Path, patterns: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    hits: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for idx, line in enumerate(text.splitlines(), 1):
        for pattern in patterns:
            if re.search(re.escape(pattern), line, re.IGNORECASE):
                hits.append({"line": idx, "pattern": pattern, "text": line.strip()[:240]})
                break
    return hits


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []
    family_results: dict[str, Any] = {}

    for folder_name, spec in REQUIRED_FAMILIES.items():
        folder = FAMILIES_DIR / folder_name
        init_file = folder / "__init__.py"
        result: dict[str, Any] = {
            "folder": str(folder.relative_to(ROOT)),
            "exists": folder.is_dir(),
            "init_exists": init_file.exists(),
            "required_api": spec.get("api"),
            "required_runtime_api": spec.get("runtime_api"),
            "required_family_id": spec["family_id"],
        }
        if not folder.is_dir():
            failures.append(f"missing_family_package:{folder_name}")
            family_results[folder_name] = result
            continue
        if not init_file.exists():
            failures.append(f"missing_family_init:{folder_name}")
            family_results[folder_name] = result
            continue
        funcs = _functions_in(init_file)
        assignments = _assignments_in(init_file)
        required_api = spec.get("api")
        required_runtime_api = spec.get("runtime_api")
        result["api_exists"] = required_api in funcs if required_api else None
        result["runtime_api_exported"] = (
            required_runtime_api in init_file.read_text(encoding="utf-8", errors="replace")
            if required_runtime_api
            else None
        )
        result["family_id_matches"] = assignments.get("FAMILY_ID") == spec["family_id"]
        cross_family_imports, compatibility_imports = _family_internal_imports(init_file, folder_name)
        result["cross_family_imports"] = cross_family_imports
        result["compatibility_imports"] = compatibility_imports
        if required_api and not result["api_exists"]:
            failures.append(f"missing_public_api:{folder_name}:{required_api}")
        if required_runtime_api and not result["runtime_api_exported"]:
            failures.append(f"missing_runtime_api:{folder_name}:{required_runtime_api}")
        if not result["family_id_matches"]:
            failures.append(f"family_id_mismatch:{folder_name}")
        for imported in result["cross_family_imports"]:
            failures.append(f"cross_family_import:{folder_name}:{imported}")
        family_results[folder_name] = result

    existing_forbidden = [
        path.name for path in FAMILIES_DIR.iterdir() if path.is_dir() and path.name in FORBIDDEN_TOP_LEVEL_FAMILY_FOLDERS
    ]
    for folder_name in existing_forbidden:
        failures.append(f"forbidden_top_level_family_folder:{folder_name}")

    shared_hits: dict[str, list[dict[str, Any]]] = {}
    if SHARED_DIR.exists():
        for path in SHARED_DIR.glob("*.py"):
            if path.name == "schemas.py":
                # The shared schema intentionally mentions generic field names only.
                pass
            hits = _line_hits(path, FAMILY_SPECIFIC_IDENTIFIERS)
            if hits:
                shared_hits[str(path.relative_to(ROOT))] = hits
                failures.append(f"family_specific_identifier_in_shared_module:{path.relative_to(ROOT)}")

    legacy_findings: dict[str, Any] = {}
    for path in LEGACY_FILES_TO_SCAN:
        hits = _line_hits(path, FAMILY_SPECIFIC_IDENTIFIERS)
        legacy_findings[str(path.relative_to(ROOT))] = {
            "hit_count": len(hits),
            "sample_hits": hits[:30],
            "status": "migration_backlog_nonfatal",
        }
        if hits:
            warnings.append(f"legacy_family_policy_backlog:{path.relative_to(ROOT)}:{len(hits)}")

    existing_flat_family_modules = sorted(
        path.name
        for path in FAMILIES_DIR.glob("*.py")
        if path.name
        not in {
            "__init__.py",
            "base.py",
            "registry.py",
        }
    )

    status = "PASS" if not failures else "FAIL"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    result = {
        "schema": "design_brain_governing_family_architecture_check.v1",
        "status": status,
        "required_family_count": len(REQUIRED_FAMILIES),
        "family_results": family_results,
        "forbidden_top_level_family_folders": existing_forbidden,
        "shared_module_hits": shared_hits,
        "legacy_findings": legacy_findings,
        "existing_flat_family_modules": existing_flat_family_modules,
        "failures": failures,
        "warnings": warnings,
    }
    output_path = ARTIFACT_DIR / f"design_brain_governing_family_architecture_check_{stamp}.json"
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    report_path = AUDIT_DIR / f"design_brain_governing_family_architecture_check_{stamp}.md"
    report_lines = [
        "# Design Brain Governing-Family Architecture Check",
        "",
        f"Status: {status}",
        "",
        "## Hard Failures",
        "",
    ]
    report_lines.extend([f"- {failure}" for failure in failures] or ["- none"])
    report_lines.extend(
        [
            "",
            "## Nonfatal Legacy Backlog",
            "",
        ]
    )
    report_lines.extend([f"- {warning}" for warning in warnings] or ["- none"])
    report_lines.extend(
        [
            "",
            "## Existing Legacy Flat Family Modules",
            "",
        ]
    )
    report_lines.extend([f"- `{name}`" for name in existing_flat_family_modules] or ["- none"])
    report_lines.extend(
        [
            "",
            "## Output",
            "",
            f"- `{output_path}`",
        ]
    )
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"{status}: {output_path}")
    print(f"REPORT: {report_path}")
    if warnings:
        print(f"WARNINGS: {len(warnings)} legacy migration findings")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
