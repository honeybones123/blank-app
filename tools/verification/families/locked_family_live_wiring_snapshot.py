"""Live wiring snapshot for locked Design Brain governing families.

This verifier proves that each locked family runtime is reachable through the
app-facing family gateway and that shared CTA/publication/apply/UI ownership
still remains outside the family runtimes.
"""

from __future__ import annotations

import ast
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.registry import (  # noqa: E402
    GOVERNING_FAMILY_REGISTRY,
    family_strategy_for,
)


FORBIDDEN_RUNTIME_TERMS = (
    "inputs_page",
    "streamlit",
    "st.session_state",
    "session_state",
    "button_contract",
    "build_design_guide_apply_button_contract",
    "record_design_guide_publication_snapshot",
    "publication",
    "published_item",
    "apply_routing",
    "one_click",
    "visible_wording",
    "rendered_html",
)


@dataclass(frozen=True)
class LockedFamily:
    family_id: str
    method_name: str
    runtime_path: str
    runtime_authority: str
    app_recognition_paths: tuple[str, ...]
    direct_inputs_anchor: str | None = None


LOCKED_FAMILIES: tuple[LockedFamily, ...] = (
    LockedFamily(
        family_id="BENDING_FAIL_GOVERNS",
        method_name="contracted_repair_ladder_specs",
        runtime_path="design_brain/families/bending_fail_governs/runtime.py",
        runtime_authority="run_bending_fail_governs_ladder_runtime",
        direct_inputs_anchor='family_strategy_for("BENDING_FAIL_GOVERNS")',
        app_recognition_paths=("inputs_page.py", "design_brain/family_chooser.py", "design_brain/governing_state.py"),
    ),
    LockedFamily(
        family_id="SHEAR_FAIL_GOVERNS",
        method_name="contracted_repair_ladder_specs",
        runtime_path="design_brain/families/shear_fail_governs/runtime.py",
        runtime_authority="run_shear_fail_governs_ladder_runtime",
        direct_inputs_anchor='family_strategy_for("SHEAR_FAIL_GOVERNS")',
        app_recognition_paths=("inputs_page.py", "design_brain/family_chooser.py", "design_brain/governing_state.py"),
    ),
    LockedFamily(
        family_id="COMBINED_BENDING_SHEAR_FAIL",
        method_name="contracted_repair_ladder_specs",
        runtime_path="design_brain/families/bending_and_shear_fail_govern/runtime.py",
        runtime_authority="run_combined_bending_shear_fail_runtime",
        direct_inputs_anchor='family_strategy_for("COMBINED_BENDING_SHEAR_FAIL")',
        app_recognition_paths=("inputs_page.py", "design_brain/family_chooser.py", "design_brain/publication.py"),
    ),
    LockedFamily(
        family_id="BENDING_OVERDESIGN_GOVERNS",
        method_name="contracted_optimisation_ladder_specs",
        runtime_path="design_brain/families/bending_overdesign_governs/runtime.py",
        runtime_authority="run_bending_overdesign_governs_runtime",
        app_recognition_paths=(
            "design_brain/family_classification_runtime.py",
            "design_brain/family_chooser.py",
            "design_brain/governing_state.py",
            "design_brain/publication.py",
        ),
    ),
    LockedFamily(
        family_id="SHEAR_OVERDESIGN_GOVERNS",
        method_name="contracted_optimisation_ladder_specs",
        runtime_path="design_brain/families/shear_overdesign_governs/runtime.py",
        runtime_authority="run_shear_overdesign_governs_runtime",
        app_recognition_paths=(
            "design_brain/family_classification_runtime.py",
            "design_brain/family_chooser.py",
            "design_brain/governing_state.py",
            "design_brain/publication.py",
        ),
    ),
    LockedFamily(
        family_id="COMBINED_OVERDESIGN",
        method_name="contracted_optimisation_ladder_specs",
        runtime_path="design_brain/families/bending_and_shear_overdesign_govern/runtime.py",
        runtime_authority="run_combined_overdesign_governs_runtime",
        app_recognition_paths=(
            "design_brain/family_classification_runtime.py",
            "design_brain/family_chooser.py",
            "design_brain/governing_state.py",
            "design_brain/publication.py",
        ),
    ),
    LockedFamily(
        family_id="BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        method_name="contracted_mixed_ladder_result",
        runtime_path="design_brain/families/bending_fail_shear_overdesign_governs/runtime.py",
        runtime_authority="run_bending_fail_shear_overdesign_runtime",
        app_recognition_paths=(
            "design_brain/family_chooser.py",
            "design_brain/family_classification_runtime.py",
            "design_brain/families/registry.py",
        ),
    ),
    LockedFamily(
        family_id="SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        method_name="contracted_mixed_ladder_result",
        runtime_path="design_brain/families/shear_fail_bending_overdesign_governs/runtime.py",
        runtime_authority="run_shear_fail_bending_overdesign_runtime",
        app_recognition_paths=(
            "design_brain/family_chooser.py",
            "design_brain/family_classification_runtime.py",
            "design_brain/families/registry.py",
        ),
    ),
    LockedFamily(
        family_id="SERVICEABILITY_GOVERNS",
        method_name="contracted_serviceability_ladder_result",
        runtime_path="design_brain/families/serviceability_governs/runtime.py",
        runtime_authority="run_serviceability_governs_ladder_runtime",
        app_recognition_paths=(
            "design_brain/family_classification_runtime.py",
            "design_brain/family_chooser.py",
            "design_brain/governing_state.py",
            "design_brain/families/registry.py",
        ),
    ),
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _module_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 500.0,
        "Mstar": 220.0,
        "Vstar": 180.0,
        "phiMu": 330.0,
        "phiVu": 260.0,
        "bending_utilisation": 0.67,
        "shear_utilisation": 0.42,
        "As": 2260.0,
        "As_min": 950.0,
        "bot1_count": 5,
        "db_bot_1": 24,
        "bot_row_count": 1,
        "lig_d": 12,
        "lig_legs": 2,
        "s_lig": 150,
        "minimum_shear_reinforcement_required": True,
    }


def _call_family_method(family: LockedFamily) -> dict[str, Any]:
    strategy = family_strategy_for(family.family_id)
    method: Callable[..., dict[str, Any]] | None = (
        getattr(strategy, family.method_name, None) if strategy is not None else None
    )
    if not callable(method):
        return {
            "called": False,
            "error": f"{family.family_id} does not expose {family.method_name}",
        }
    base = _base_state()
    try:
        if family.family_id == "BENDING_FAIL_GOVERNS":
            result = method(base, geometry_locked=False, bar_diameters=(10, 12, 16, 20, 24, 28, 32))
        elif family.family_id == "SHEAR_FAIL_GOVERNS":
            result = method(
                base,
                width_key="b",
                geometry_locked=False,
                reo_spacings=(300.0, 250.0, 200.0, 175.0, 150.0, 125.0, 100.0),
                lig_diameters=(10, 12, 16),
            )
        elif family.family_id == "COMBINED_BENDING_SHEAR_FAIL":
            result = method(
                {"selected_family_id": "COMBINED_BENDING_SHEAR_FAIL", **base},
                geometry_locked=False,
                bending_fail_candidates=(
                    {
                        "source_family_id": "BENDING_FAIL_GOVERNS",
                        "candidate_id": "live_wiring_bending_source",
                        "updates": {"D": 550.0},
                    },
                ),
                shear_fail_candidates=(
                    {
                        "source_family_id": "SHEAR_FAIL_GOVERNS",
                        "candidate_id": "live_wiring_shear_source",
                        "updates": {"lig_d": 12, "s_lig": 125},
                    },
                ),
            )
        elif family.family_id == "COMBINED_OVERDESIGN":
            result = method(
                base,
                bending_overdesign_candidates=(
                    {
                        "source_family_id": "BENDING_OVERDESIGN_GOVERNS",
                        "candidate_id": "live_wiring_bending_overdesign_source",
                        "updates": {"bot1_count": 4, "db_bot_1": 20},
                    },
                ),
                shear_overdesign_candidates=(
                    {
                        "source_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                        "candidate_id": "live_wiring_shear_overdesign_source",
                        "updates": {"lig_d": 0, "lig_legs": 0},
                    },
                ),
            )
        else:
            result = method(base)
    except Exception as exc:  # pragma: no cover - failure is reported in snapshot
        return {"called": False, "error": f"{type(exc).__name__}: {exc}"}
    if not isinstance(result, dict):
        return {"called": False, "error": f"unexpected result type: {type(result).__name__}"}
    specs = list(result.get("specs") or [])
    authority = result.get("contract_runtime_authority") or result.get("runtime_authority")
    return {
        "called": True,
        "error": "",
        "contract_runtime_driven": result.get("contract_runtime_driven") is True
        or authority == family.runtime_authority,
        "contract_runtime_authority": authority,
        "runtime_authority_matches": authority == family.runtime_authority,
        "spec_count": len(specs),
        "has_runtime_hash": bool(result.get("ladder_hash") or result.get("runtime_hash")),
    }


def _family_source_snapshot(family: LockedFamily) -> dict[str, Any]:
    inputs_source = _read("inputs_page.py")
    recognition_hits = {
        path: family.family_id in _read(path)
        for path in family.app_recognition_paths
    }
    direct_inputs_call = bool(
        family.direct_inputs_anchor
        and family.direct_inputs_anchor in inputs_source
        and f".{family.method_name}(" in inputs_source
    )
    reachability_mode = "direct_inputs_ladder" if direct_inputs_call else "registry_app_gateway"
    return {
        "registered": family.family_id in GOVERNING_FAMILY_REGISTRY,
        "strategy_class": (
            GOVERNING_FAMILY_REGISTRY.get(family.family_id).__name__
            if family.family_id in GOVERNING_FAMILY_REGISTRY
            else ""
        ),
        "app_recognition_hits": recognition_hits,
        "app_recognition_complete": all(recognition_hits.values()),
        "direct_inputs_ladder_call": direct_inputs_call,
        "reachability_mode": reachability_mode,
        "family_strategy_gateway_used_by_app": "family_strategy_for(" in inputs_source
        or "family_strategy_for(" in _read("design_brain/engine.py"),
    }


def _runtime_boundary_snapshot(family: LockedFamily) -> dict[str, Any]:
    source = _read(family.runtime_path)
    imports = _module_imports(source)
    forbidden_imports = [
        item
        for item in imports
        if item.split(".", 1)[0] in {"inputs_page", "streamlit"}
    ]
    source_lower = source.lower()
    forbidden_terms = sorted(
        term for term in FORBIDDEN_RUNTIME_TERMS if term.lower() in source_lower
    )
    return {
        "runtime_path": family.runtime_path,
        "forbidden_imports": forbidden_imports,
        "forbidden_terms": forbidden_terms,
        "clean_runtime_boundary": not forbidden_imports and not forbidden_terms,
    }


def _shared_ownership_snapshot() -> dict[str, bool]:
    inputs_source = _read("inputs_page.py")
    publication_source = _read("design_brain/publication.py")
    return {
        "candidate_evaluation_loop_in_inputs_page": "def _evaluate(" in inputs_source
        and "_evaluate_auto_design_candidate(" in inputs_source,
        "cta_contracts_imported_by_inputs_page": "from design_brain.cta_contracts import" in inputs_source,
        "publication_imported_by_inputs_page": "from design_brain.publication import" in inputs_source,
        "publication_gate_exists": "record_design_guide_publication_snapshot" in inputs_source,
        "apply_routing_exists": "build_design_guide_apply_button_contract" in inputs_source,
        "one_click_orchestration_exists": "one_click" in inputs_source.lower(),
        "ui_session_debug_exists": "st.session_state" in inputs_source and "debug" in inputs_source.lower(),
        "publication_knows_locked_overdesign_ids": "BENDING_OVERDESIGN_GOVERNS" in publication_source
        and "SHEAR_OVERDESIGN_GOVERNS" in publication_source,
    }


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"locked_family_live_wiring_snapshot_{stamp}.json"
    report_path = AUDIT_DIR / f"locked_family_live_wiring_snapshot_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Locked Family Live Wiring Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Family Wiring",
                "",
                *[
                    "- `{family}`: `{result}` via `{mode}`; authority `{authority}`".format(
                        family=row["family_id"],
                        result=row["result"],
                        mode=row["source"]["reachability_mode"],
                        authority=row["call"].get("contract_runtime_authority"),
                    )
                    for row in snapshot["families"]
                ],
                "",
                "## Shared Ownership",
                "",
                *[
                    f"- `{key}`: `{value}`"
                    for key, value in snapshot["shared_ownership"].items()
                ],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    family_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for family in LOCKED_FAMILIES:
        source = _family_source_snapshot(family)
        call = _call_family_method(family)
        runtime = _runtime_boundary_snapshot(family)
        checks = {
            "registered": bool(source["registered"]),
            "app_recognition_complete": bool(source["app_recognition_complete"]),
            "family_strategy_gateway_used_by_app": bool(source["family_strategy_gateway_used_by_app"]),
            "method_called": bool(call.get("called")),
            "runtime_authority_matches": bool(call.get("runtime_authority_matches")),
            "runtime_boundary_clean": bool(runtime["clean_runtime_boundary"]),
        }
        result = "PASS" if all(checks.values()) else "FAIL"
        if result != "PASS":
            failed = sorted(key for key, value in checks.items() if not value)
            failures.append(f"{family.family_id}:{failed}")
        family_rows.append(
            {
                "family_id": family.family_id,
                "method_name": family.method_name,
                "expected_runtime_authority": family.runtime_authority,
                "result": result,
                "checks": checks,
                "source": source,
                "call": call,
                "runtime_boundary": runtime,
            }
        )
    shared_ownership = _shared_ownership_snapshot()
    if not all(shared_ownership.values()):
        failures.append(
            "shared_ownership:"
            + str(sorted(key for key, value in shared_ownership.items() if not value))
        )
    snapshot = {
        "schema": "locked_family_live_wiring_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "families": family_rows,
        "shared_ownership": shared_ownership,
        "failures": failures,
        "scope": {
            "live_product_behavior_changed": False,
            "cta_publication_apply_ui_moved": False,
            "runtime_formulas_changed": False,
            "overdesign_reachability_mode": "registry_app_gateway",
            "combined_overdesign_reachability_mode": "registry_app_gateway",
            "fail_family_reachability_mode": "direct_inputs_ladder",
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("locked family live wiring snapshot FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("locked family live wiring snapshot PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
