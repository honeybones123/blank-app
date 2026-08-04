from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
MODULE_ROOT = ROOT / "inputs_page_modules" / "widgets"
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


TRACE_HASH_KEYS: dict[str, tuple[str, ...]] = {
    "top_level_design_mode": ("top_level_widget_metadata_hash",),
    "design_actions_mode": ("design_actions_mode_widget_metadata_hash",),
    "design_action_numbers": ("design_action_numbers_widget_metadata_hash",),
    "geometry_basic": ("geometry_widget_metadata_hash",),
    "materials_basic": ("materials_widget_metadata_hash",),
    "shear_reinforcement_basic": ("shear_widget_metadata_hash",),
    "bottom_longitudinal_reinforcement": ("bot_longitudinal_widget_metadata_hash",),
    "top_longitudinal_reinforcement": ("top_longitudinal_widget_metadata_hash",),
    "serviceability_environment_basic": ("serviceability_environment_basic_widget_metadata_hash",),
    "support_deflection_basic": ("support_deflection_basic_widget_metadata_hash",),
    "shear_section_parameters_basic": ("shear_section_parameters_basic_widget_metadata_hash",),
    "time_dependent_basic": ("time_dependent_basic_widget_metadata_hash",),
    "ducts_prestress_voids_basic": ("ducts_prestress_voids_basic_widget_metadata_hash",),
    "crack_control_inputs_basic": ("crack_control_inputs_basic_widget_metadata_hash",),
    "flange_reinforcement_basic": ("flange_reinforcement_basic_widget_metadata_hash",),
    "flange_transverse_basic": ("flange_transverse_basic_widget_metadata_hash",),
}

GENERIC_DETAILED_TRACE_GROUPS: set[str] = {
    "serviceability_environment_basic",
    "support_deflection_basic",
    "shear_section_parameters_basic",
}

MIXED_TOP_LEVEL_TRACE_GROUPS: set[str] = {
    "top_level_design_mode",
    "design_actions_mode",
}

LONGITUDINAL_TRACE_GROUPS: set[str] = {
    "bottom_longitudinal_reinforcement",
    "top_longitudinal_reinforcement",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_number(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


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
    if not matches:
        return None
    return sorted(matches, key=lambda item: item.stat().st_mtime)[-1]


def _classify_groups(page: str, contract: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    generic_detailed_hash_trace_present = (
        "for _group_id, _payloads in _detailed_widget_groups.items():" in page
        and '_detailed_widget_metadata_trace[f"{_group_id}_widget_metadata_hash"]' in page
        and "_previous_group_hashes[_group_id] = _group_vm.display_hash" in page
    )
    mixed_top_level_hash_trace_present = (
        '"inputs_widget_metadata_hash"' in page
        and "_top_level_widget_group_vm.display_hash" in page
        and "build_top_level_design_mode_widget_payloads(" in page
    )
    longitudinal_hash_trace_present = (
        "build_longitudinal_reinforcement_widget_payloads(" in page
        and 'f"{section_norm}_longitudinal_widget_metadata_hash"' in page
        and 'f"{section_norm}_longitudinal_widget_metadata_count"' in page
        and 'f"{section_norm}_longitudinal_widget_keys"' in page
    )
    for group in EXPECTED_GROUPS:
        hash_keys = TRACE_HASH_KEYS[group]
        contract_present = f'"{group}"' in contract
        group_present = f'"{group}"' in page
        if group in MIXED_TOP_LEVEL_TRACE_GROUPS:
            group_present = group_present or "build_top_level_design_mode_widget_payloads(" in page
        if group in LONGITUDINAL_TRACE_GROUPS:
            group_present = group_present or "build_longitudinal_reinforcement_widget_payloads(" in page
        hash_present = any(f'"{key}"' in page or key in page for key in hash_keys)
        if group in GENERIC_DETAILED_TRACE_GROUPS:
            hash_present = hash_present or (
                group_present and generic_detailed_hash_trace_present
            )
        if group in MIXED_TOP_LEVEL_TRACE_GROUPS:
            hash_present = hash_present or (
                group_present and mixed_top_level_hash_trace_present
            )
        if group in LONGITUDINAL_TRACE_GROUPS:
            hash_present = hash_present or (
                group_present and longitudinal_hash_trace_present
            )
        ready = contract_present and group_present and hash_present
        rows.append(
            {
                "group_id": group,
                "current_owner": "inputs_page.py trace wrapper plus inputs_page_modules.widgets typed builder",
                "target_owner": "inputs_page_modules.widgets metadata builder",
                "classification": "READY_FOR_METADATA_BUILDER_DELEGATION"
                if ready
                else "KEEP_PAGE_WRAPPER_PENDING_HASHED_TRACE",
                "page_rendering_owner": "inputs_page.py",
                "callbacks_owner": "inputs_page.py",
                "session_hydration_owner": "inputs_page.py",
                "contract_present": contract_present,
                "group_token_present": group_present,
                "hash_trace_present": hash_present,
                "line_number": _line_number(page, group),
                "delete_ready": False,
                "live_renderer_cutover_allowed": False,
            }
        )
    return rows


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Delegation Readiness Audit",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This is audit-only. It does not change widget rendering, widget keys, callbacks, session state, engineering values, or visible wording.",
        "",
        "## Boundary Decision",
        "",
        "- Ready boundary: metadata source/view-model builder delegation for groups with per-group hash traces.",
        "- Not moved: Streamlit widget rendering, widget keys, callbacks, session hydration, Apply routing, and page layout.",
        "- Deletion is not allowed in this slice; page wrappers remain until a later cutover/deadness verifier.",
        "",
        "## Live Coverage",
        "",
    ]
    for name, value in payload["live_artifacts"].items():
        lines.append(f"- `{name}`: `{value or 'MISSING'}`")
    lines.extend(
        [
            "",
            "## Group Readiness",
            "",
            "| Group | Classification | Contract | Page token | Hash trace | Line |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in payload["groups"]:
        lines.append(
            "| `{group_id}` | `{classification}` | `{contract_present}` | `{group_token_present}` | `{hash_trace_present}` | `{line_number}` |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            "Move only reusable widget metadata payload construction into `inputs_page_modules/widgets` for a small stable group, starting with `materials_basic` or `geometry_basic`. Keep the live renderer and callbacks in `inputs_page.py`; page code should pass explicit plain payload inputs to the module and continue rendering the existing widgets.",
            "",
            "## Stop Conditions",
            "",
            "- Any widget key changes.",
            "- Any visible label/help/default/options change.",
            "- Any Streamlit/session import enters `inputs_page_modules.widgets`.",
            "- Any callback or session hydration moves out of `inputs_page.py`.",
            "- Any live trace mode loses parity.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    module_sources = {
        path.name: _read(path)
        for path in MODULE_ROOT.glob("*.py")
    }
    module_combined = "\n".join(module_sources.values())
    executable_module_combined = "\n".join(
        source for name, source in module_sources.items() if name != "contracts.py"
    )
    contract = module_sources.get("contracts.py", "")
    groups = _classify_groups(page, contract)

    fast_artifact = _latest_live_artifact(design_mode="fast")
    detailed_artifact = _latest_live_artifact(design_mode="detailed")
    t_artifact = _latest_live_artifact(design_mode="detailed", section_shape="T")
    checks = {
        "inputs_page_present": INPUTS_PAGE.exists(),
        "widgets_module_present": MODULE_ROOT.exists(),
        "models_file_present": "models.py" in module_sources,
        "builders_file_present": "builders.py" in module_sources,
        "contracts_file_present": "contracts.py" in module_sources,
        "builder_available": "def build_inputs_widget_group_view_model(" in module_sources.get("builders.py", ""),
        "page_imports_builder": (
            "from inputs_page_modules.widgets import" in page
            and "build_inputs_widget_group_view_model" in page
        ),
        "all_expected_groups_contract_present": all(row["contract_present"] for row in groups),
        "at_least_one_group_ready_for_metadata_delegation": any(
            row["classification"] == "READY_FOR_METADATA_BUILDER_DELEGATION" for row in groups
        ),
        "module_does_not_import_streamlit": "import streamlit" not in module_combined and "from streamlit" not in module_combined,
        "module_does_not_import_inputs_page": "inputs_page" not in module_combined,
        "module_does_not_mutate_session_state": "st.session_state" not in module_combined and ".session_state" not in module_combined,
        "module_does_not_route_apply": "route_apply" not in executable_module_combined and "apply_payload" not in executable_module_combined,
        "live_fast_default_pass_artifact_present": fast_artifact is not None,
        "live_detailed_default_pass_artifact_present": detailed_artifact is not None,
        "live_detailed_t_section_pass_artifact_present": t_artifact is not None,
        "live_renderer_not_cut_over": '"live_widget_renderer_cutover": False' in page,
    }
    failures = [key for key, value in checks.items() if not value]
    readiness_gaps = [
        row["group_id"]
        for row in groups
        if row["classification"] != "READY_FOR_METADATA_BUILDER_DELEGATION"
    ]
    decision = "READY_FOR_WIDGET_METADATA_BUILDER_DELEGATION" if not failures else "WIDGET_DELEGATION_READINESS_GAPS_REMAIN"
    payload = {
        "audit": "inputs_widgets_delegation_readiness_audit",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "defer_groups_until_hashed_trace": readiness_gaps,
        "groups": groups,
        "live_artifacts": {
            "fast_default": str(fast_artifact) if fast_artifact else "",
            "detailed_default": str(detailed_artifact) if detailed_artifact else "",
            "detailed_t_section": str(t_artifact) if t_artifact else "",
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
        "live_renderer_switched": False,
        "next_safe_slice": "extract metadata payload construction for a small stable widget group while retaining page rendering",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_widgets_delegation_readiness_audit_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_delegation_readiness_audit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_widgets_delegation_readiness_audit", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
