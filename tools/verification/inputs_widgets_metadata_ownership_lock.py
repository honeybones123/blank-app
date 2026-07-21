from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
WIDGETS_ROOT = ROOT / "inputs_page_modules" / "widgets"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


EXPECTED_GROUPS: tuple[str, ...] = (
    "top_level_design_mode",
    "design_actions_mode",
    "design_action_numbers",
    "geometry_basic",
    "materials_basic",
    "shear_reinforcement_basic",
    "bottom_longitudinal_reinforcement",
    "top_longitudinal_reinforcement",
    "serviceability_environment_basic",
    "support_deflection_basic",
    "shear_section_parameters_basic",
    "time_dependent_basic",
    "ducts_prestress_voids_basic",
    "crack_control_inputs_basic",
    "flange_reinforcement_basic",
    "flange_transverse_basic",
)

REQUIRED_BUILDER_FUNCTIONS: tuple[str, ...] = (
    "build_inputs_widget_group_view_model",
    "build_materials_basic_widget_payloads",
    "build_geometry_basic_widget_payloads",
    "build_shear_reinforcement_basic_widget_payloads",
    "build_design_action_numbers_widget_payloads",
    "build_time_dependent_basic_widget_payloads",
    "build_ducts_prestress_voids_basic_widget_payloads",
    "build_crack_control_inputs_basic_widget_payloads",
    "build_serviceability_environment_basic_widget_payloads",
    "build_support_deflection_basic_widget_payloads",
    "build_shear_section_parameters_basic_widget_payloads",
    "build_top_level_design_mode_widget_payloads",
    "build_longitudinal_reinforcement_widget_payloads",
    "build_flange_reinforcement_basic_widget_payloads",
    "build_flange_transverse_basic_widget_payloads",
)

FOCUSED_VERIFIER_PREFIXES: tuple[str, ...] = (
    "inputs_widgets_materials_metadata_builder_delegation",
    "inputs_widgets_geometry_metadata_builder_delegation",
    "inputs_widgets_shear_metadata_builder_delegation",
    "inputs_widgets_design_action_numbers_metadata_builder_delegation",
    "inputs_widgets_time_dependent_metadata_builder_delegation",
    "inputs_widgets_ducts_metadata_builder_delegation",
    "inputs_widgets_crack_control_metadata_builder_delegation",
    "inputs_widgets_flange_transverse_metadata_builder_delegation",
    "inputs_widgets_flange_reinforcement_metadata_builder_delegation",
    "inputs_widgets_serviceability_environment_metadata_builder_delegation",
    "inputs_widgets_support_deflection_metadata_builder_delegation",
    "inputs_widgets_shear_section_parameters_metadata_builder_delegation",
    "inputs_widgets_top_level_design_mode_metadata_builder_delegation",
    "inputs_widgets_longitudinal_reinforcement_metadata_builder_delegation",
)

REQUIRED_PASS_ARTIFACT_PREFIXES: tuple[str, ...] = (
    *FOCUSED_VERIFIER_PREFIXES,
    "inputs_widgets_typed_model_trace",
    "inputs_widgets_delegation_readiness_audit",
    "inputs_widgets_live_trace_parity",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_artifact(prefix: str) -> Path | None:
    matches = sorted(
        VERIFICATION_DIR.glob(f"{prefix}_*.json"),
        key=lambda item: item.stat().st_mtime,
    )
    return matches[-1] if matches else None


def _artifact_passes(path: Path | None) -> bool:
    if path is None:
        return False
    payload = _load_json(path)
    if payload.get("failures"):
        return False
    classification = payload.get("classification")
    if isinstance(classification, dict) and classification.get("status") not in (None, "PASS"):
        return False
    decision = str(payload.get("decision") or "")
    if not decision:
        return False
    fail_words = ("GAPS_REMAIN", "FAIL", "BLOCKED", "AMBIGUOUS")
    return not any(word in decision for word in fail_words)


def _latest_live_artifact(*, design_mode: str, section_shape: str | None = None) -> Path | None:
    matches: list[Path] = []
    for path in VERIFICATION_DIR.glob("inputs_widgets_live_trace_parity_*.json"):
        payload = _load_json(path)
        classification = dict(payload.get("classification") or {})
        if classification.get("status") != "PASS":
            continue
        if str(payload.get("design_mode") or "") != design_mode:
            continue
        shape = payload.get("section_shape")
        if section_shape is None:
            if shape not in (None, "", "default"):
                continue
        elif str(shape or "") != section_shape:
            continue
        matches.append(path)
    return sorted(matches, key=lambda item: item.stat().st_mtime)[-1] if matches else None


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Metadata Ownership Lock",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier locks the Widgets metadata extraction boundary. It proves metadata payload/view-model construction is module-owned for every tracked widget group, while live widget rendering is isolated in the widget render-coordinator boundary.",
        "",
        "## Ownership Counts",
        "",
        f"- Expected groups: `{payload['expected_group_count']}`",
        f"- Delegated groups: `{payload['delegated_group_count']}`",
        f"- Deferred groups: `{len(payload['deferred_groups'])}`",
        f"- Missing builder functions: `{len(payload['missing_builder_functions'])}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Latest Artifacts", ""])
    for key, value in payload["latest_artifacts"].items():
        lines.append(f"- `{key}`: `{value or 'MISSING'}`")
    if payload.get("deferred_groups"):
        lines.extend(["", "## Deferred Groups", ""])
        for group in payload["deferred_groups"]:
            lines.append(f"- `{group}`")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    route_surface = _read(ROUTE_COORDINATORS) if ROUTE_COORDINATORS.exists() else ""
    live_surface = page + "\n" + route_surface
    builders = _read(WIDGETS_ROOT / "builders.py")
    init_source = _read(WIDGETS_ROOT / "__init__.py")
    contracts = _read(WIDGETS_ROOT / "contracts.py")
    models = _read(WIDGETS_ROOT / "models.py")
    module_sources = "\n".join(
        _read(path) for path in sorted(WIDGETS_ROOT.glob("*.py"))
    )
    metadata_module_sources = "\n".join(
        _read(path)
        for path in sorted(WIDGETS_ROOT.glob("*.py"))
        if path.name not in {"render_coordinators.py", "design_action_sync.py"}
    )
    render_coordinator_source = (
        _read(WIDGETS_ROOT / "render_coordinators.py")
        if (WIDGETS_ROOT / "render_coordinators.py").exists()
        else ""
    )
    executable_module_sources = "\n".join(
        _read(path)
        for path in sorted(WIDGETS_ROOT.glob("*.py"))
        if path.name != "contracts.py"
    )

    latest_artifacts = {
        prefix: _latest_artifact(prefix)
        for prefix in REQUIRED_PASS_ARTIFACT_PREFIXES
    }
    latest_artifact_strings = {
        prefix: str(path) if path else ""
        for prefix, path in latest_artifacts.items()
    }
    latest_artifacts_pass = {
        prefix: _artifact_passes(path)
        for prefix, path in latest_artifacts.items()
    }
    readiness_payload = _load_json(latest_artifacts.get("inputs_widgets_delegation_readiness_audit"))
    deferred_groups = list(readiness_payload.get("defer_groups_until_hashed_trace") or [])
    readiness_groups = list(readiness_payload.get("groups") or [])
    delegated_groups = [
        str(row.get("group_id") or "")
        for row in readiness_groups
        if row.get("classification") == "READY_FOR_METADATA_BUILDER_DELEGATION"
    ]
    missing_builder_functions = [
        name for name in REQUIRED_BUILDER_FUNCTIONS if f"def {name}(" not in builders
    ]
    unexported_builder_functions = [
        name for name in REQUIRED_BUILDER_FUNCTIONS if name not in init_source
    ]
    missing_contract_groups = [
        group for group in EXPECTED_GROUPS if f'"{group}"' not in contracts
    ]
    fast_artifact = _latest_live_artifact(design_mode="fast")
    detailed_artifact = _latest_live_artifact(design_mode="detailed")
    t_artifact = _latest_live_artifact(design_mode="detailed", section_shape="T")

    checks = {
        "inputs_page_present": INPUTS_PAGE.exists(),
        "widgets_module_present": WIDGETS_ROOT.exists(),
        "models_file_present": "class InputsWidgetSpecViewModel" in models
        and "class InputsWidgetGroupViewModel" in models,
        "contracts_cover_all_expected_groups": not missing_contract_groups,
        "all_required_builder_functions_exist": not missing_builder_functions,
        "all_required_builder_functions_exported": not unexported_builder_functions,
        "readiness_artifact_passes": latest_artifacts_pass.get(
            "inputs_widgets_delegation_readiness_audit", False
        ),
        "readiness_deferred_groups_zero": deferred_groups == [],
        "all_expected_groups_delegated": sorted(delegated_groups) == sorted(EXPECTED_GROUPS),
        "focused_builder_verifiers_pass": all(
            latest_artifacts_pass.get(prefix, False) for prefix in FOCUSED_VERIFIER_PREFIXES
        ),
        "typed_trace_passes": latest_artifacts_pass.get("inputs_widgets_typed_model_trace", False),
        "fast_live_parity_passes": fast_artifact is not None,
        "detailed_live_parity_passes": detailed_artifact is not None,
        "detailed_t_live_parity_passes": t_artifact is not None,
        "module_does_not_import_streamlit": "import streamlit" not in module_sources
        and "from streamlit" not in module_sources,
        "module_does_not_import_inputs_page": "import inputs_page" not in module_sources
        and "from inputs_page" not in module_sources,
        "module_does_not_mutate_session_state": (
            "st.session_state" not in metadata_module_sources
            and ".session_state" not in metadata_module_sources
        ),
        "module_does_not_route_apply": "route_apply" not in executable_module_sources
        and "apply_payload" not in executable_module_sources,
        "permanent_shell_delegates_widget_sections": "render_inputs_widget_sections_current_coordinator(" in page,
        "live_route_surface_still_owns_widget_rendering": "number_row" in (live_surface + "\n" + render_coordinator_source)
        and "render_longitudinal_reo_rows" in (live_surface + "\n" + render_coordinator_source)
        and "render_longitudinal_reo_row_config_controls" in (live_surface + "\n" + render_coordinator_source)
        and "selectbox(" in (live_surface + "\n" + render_coordinator_source),
        "live_route_surface_still_owns_callbacks": "sync_callbacks" in live_surface
        and "on_change=" in live_surface,
        "page_still_owns_session_hydration": "st.session_state" in page,
        "live_widget_renderer_route_retained": "def render_inputs_widget_sections_current_coordinator(" in live_surface,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "INPUTS_WIDGETS_METADATA_OWNERSHIP_LOCKED" if not failures else "INPUTS_WIDGETS_METADATA_LOCK_GAPS_REMAIN"
    payload = {
        "audit": "inputs_widgets_metadata_ownership_lock",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "expected_group_count": len(EXPECTED_GROUPS),
        "delegated_group_count": len(delegated_groups),
        "delegated_groups": delegated_groups,
        "deferred_groups": deferred_groups,
        "missing_builder_functions": missing_builder_functions,
        "unexported_builder_functions": unexported_builder_functions,
        "missing_contract_groups": missing_contract_groups,
        "latest_artifacts": {
            **latest_artifact_strings,
            "fast_live_trace_parity": str(fast_artifact) if fast_artifact else "",
            "detailed_live_trace_parity": str(detailed_artifact) if detailed_artifact else "",
            "detailed_t_live_trace_parity": str(t_artifact) if t_artifact else "",
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "rerun_routing_moved": False,
        "live_renderer_switched": False,
        "next_safe_slice": "start Session State Phase 0 audit after Widgets progress is marked LOCKED",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_widgets_metadata_ownership_lock_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_metadata_ownership_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_widgets_metadata_ownership_lock", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
