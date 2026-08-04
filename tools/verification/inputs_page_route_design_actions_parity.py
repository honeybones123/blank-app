from __future__ import annotations

import copy
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _load_archived_legacy_inputs_page():
    candidates = sorted((ROOT / "artifacts" / "audits").glob("legacy_inputs_page_removed_*.py"))
    if not candidates:
        raise RuntimeError("No archived legacy inputs_page reference found for parity comparison")
    path = candidates[-1]
    spec = importlib.util.spec_from_file_location("_archived_legacy_inputs_page", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load archived legacy inputs_page reference: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _RerunRequested(Exception):
    pass


class _FakeContext:
    def __init__(self, calls: list[tuple[str, Any]], label: str) -> None:
        self.calls = calls
        self.label = label

    def __enter__(self):
        self.calls.append(("enter", self.label))
        return self

    def __exit__(self, exc_type, exc, tb):
        self.calls.append(("exit", self.label))
        return False


class _FakeStreamlit:
    def __init__(self, session_state: dict[str, Any], calls: list[tuple[str, Any]]) -> None:
        self.session_state = session_state
        self._calls = calls
        self._counter = 0

    def columns(self, spec, *, gap=None, vertical_alignment=None):
        spec_list = list(spec) if isinstance(spec, (list, tuple)) else [spec]
        self._calls.append(("columns", spec_list, gap, vertical_alignment))
        out = []
        for idx, _ in enumerate(spec_list):
            self._counter += 1
            out.append(_FakeContext(self._calls, f"column:{self._counter}:{idx}"))
        return out

    def markdown(self, text, **kwargs):
        self._calls.append(("markdown", str(text), dict(kwargs)))

    def caption(self, text):
        self._calls.append(("caption", str(text)))

    def divider(self):
        self._calls.append(("divider", None))

    def info(self, text):
        self._calls.append(("info", str(text)))

    def toggle(self, label, *, value=False, key=None, on_change=None, help=None):
        self._calls.append(("toggle", str(label), bool(value), key, bool(callable(on_change)), help))
        if key in self.session_state:
            result = bool(self.session_state.get(key))
        else:
            result = bool(value)
            if key is not None:
                self.session_state[key] = result
        return result

    def rerun(self):
        self._calls.append(("rerun", None))
        raise _RerunRequested()


def _session_subset(session_state: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "actions_source",
        "actions_mode",
        "inputs_use_calculated_actions",
        "_inputs_use_calculated_actions_user_intent",
        "loads_edit_mode",
        "_force_design_action_widget_hydrate",
        "inputs_dirty",
        "_inputs_dirty",
    )
    return {key: copy.deepcopy(session_state.get(key)) for key in keys if key in session_state}


def _run_case(module, seed: dict[str, Any], *, detailed: bool, design_controls: bool) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    session_state = copy.deepcopy(seed)
    fake_st = _FakeStreamlit(session_state, calls)
    action_slot = _FakeContext(calls, "actions_slot")
    legacy_bridge = getattr(module, "_legacy_inputs_page", module)

    original_st = module.st
    original_info = module.info_i_button
    original_get_widget_key = module.get_widget_key_for_shared
    original_is_design_governing = module.is_design_governing

    helper_names = (
        "_commit_design_action_widgets_to_shared",
        "_mirror_design_action_proxies_from_shared",
        "_hydrate_design_action_widgets_from_shared",
        "_design_action_widget_specs",
        "_make_design_action_widget_callback",
        "_render_design_action_number_row",
        "_reconcile_design_action_widgets_with_shared",
        "_debug_check_design_action_consistency",
    )
    helper_owners = {
        name: module if hasattr(module, name) else legacy_bridge
        for name in helper_names
    }
    originals = {name: getattr(helper_owners[name], name) for name in helper_names}

    def _info_i_button(*, content=None, help_text=None, key=None, use_container_width=False):
        calls.append(("info_i_button", content, help_text, key, bool(use_container_width)))
        return _FakeContext(calls, "info_i_button")

    def _get_widget_key_for_shared(shared_key, *, prefix=""):
        calls.append(("get_widget_key_for_shared", shared_key, prefix))
        if shared_key == "loads_edit_toggle":
            return "inputs_loads_edit_toggle"
        return None

    def _is_design_governing():
        calls.append(("is_design_governing", None))
        return bool(design_controls)

    def _commit(prefix: str):
        calls.append(("commit_design_action_widgets_to_shared", prefix))

    def _mirror(prefix: str):
        calls.append(("mirror_design_action_proxies_from_shared", prefix))

    def _hydrate(prefix: str, *, force: bool, design_controls: bool):
        calls.append(("hydrate_design_action_widgets_from_shared", prefix, bool(force), bool(design_controls)))

    def _specs(prefix: str):
        calls.append(("design_action_widget_specs", prefix))
        return [
            {
                "label": "Axial force N* (kN)",
                "widget_key": f"inputs_{prefix}_Nstar",
                "shared_key": "P_star",
                "proxy_key": f"load_Nstar_{prefix}_proxy",
                "help_text": "Axial action.",
                "disabled_in_design_mode": True,
            },
            {
                "label": "Negative moment M* (kNm)",
                "widget_key": f"inputs_{prefix}_Mstar_neg",
                "shared_key": f"{prefix}_Mstar_neg_manual",
                "proxy_key": f"load_Mstar_neg_{prefix}_proxy",
                "help_text": "Negative moment.",
                "disabled_in_design_mode": True,
            },
            {
                "label": "Positive moment M* (kNm)",
                "widget_key": f"inputs_{prefix}_Mstar_pos",
                "shared_key": f"{prefix}_Mstar_pos_manual",
                "proxy_key": f"load_Mstar_pos_{prefix}_proxy",
                "help_text": "Positive moment.",
                "disabled_in_design_mode": True,
            },
            {
                "label": "Shear V* (kN)",
                "widget_key": f"inputs_{prefix}_Vstar",
                "shared_key": f"{prefix}_Vstar_manual",
                "proxy_key": f"load_Vstar_{prefix}_proxy",
                "help_text": "Shear.",
                "disabled_in_design_mode": True,
            },
        ]

    def _make_callback(widget_key: str, shared_key: str, proxy_key):
        calls.append(("make_design_action_widget_callback", widget_key, shared_key, proxy_key))
        return lambda: None

    def _render_number_row(**kwargs):
        calls.append(
            (
                "render_design_action_number_row",
                kwargs.get("label"),
                kwargs.get("widget_key"),
                kwargs.get("help_text"),
                bool(callable(kwargs.get("on_change"))),
                bool(kwargs.get("disabled")),
                getattr(kwargs.get("col_label"), "label", None),
                getattr(kwargs.get("col_input"), "label", None),
            )
        )

    def _reconcile(prefix: str):
        calls.append(("reconcile_design_action_widgets_with_shared", prefix))

    def _debug(state: dict):
        calls.append(("debug_check_design_action_consistency", state.get("actions_mode"), state.get("loads_edit_mode")))

    def _sub_mark(label: str):
        calls.append(("sub_mark", str(label)))

    try:
        module.st = fake_st
        module.info_i_button = _info_i_button
        module.get_widget_key_for_shared = _get_widget_key_for_shared
        module.is_design_governing = _is_design_governing
        helper_owners["_commit_design_action_widgets_to_shared"]._commit_design_action_widgets_to_shared = _commit
        helper_owners["_mirror_design_action_proxies_from_shared"]._mirror_design_action_proxies_from_shared = _mirror
        helper_owners["_hydrate_design_action_widgets_from_shared"]._hydrate_design_action_widgets_from_shared = _hydrate
        helper_owners["_design_action_widget_specs"]._design_action_widget_specs = _specs
        helper_owners["_make_design_action_widget_callback"]._make_design_action_widget_callback = _make_callback
        helper_owners["_render_design_action_number_row"]._render_design_action_number_row = _render_number_row
        helper_owners["_reconcile_design_action_widgets_with_shared"]._reconcile_design_action_widgets_with_shared = _reconcile
        helper_owners["_debug_check_design_action_consistency"]._debug_check_design_action_consistency = _debug

        rerun = False
        try:
            module.render_inputs_design_actions_section_current_coordinator(
                actions_slot=action_slot,
                inputs_detailed_mode=detailed,
                sync_callbacks={},
                sub_mark=_sub_mark,
            )
        except _RerunRequested:
            rerun = True
    finally:
        module.st = original_st
        module.info_i_button = original_info
        module.get_widget_key_for_shared = original_get_widget_key
        module.is_design_governing = original_is_design_governing
        for name, value in originals.items():
            setattr(helper_owners[name], name, value)

    return {
        "rerun": rerun,
        "calls": calls,
        "session": _session_subset(session_state),
    }


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    legacy_inputs_page = _load_archived_legacy_inputs_page()
    import inputs_page_route_coordinators as route

    legacy_manual = "Manual design actions (inputs below)"
    legacy_design = "Teaching SFD/BMD page (|M|max, |V|max)"
    cases = {
        "manual_fast_full_render": {
            "seed": {
                "actions_source": legacy_manual,
                "actions_mode": "manual",
                "inputs_use_calculated_actions": False,
                "loads_edit_mode": "ULS",
                "inputs_loads_edit_toggle": False,
            },
            "detailed": False,
            "design_controls": False,
        },
        "align_calculated_toggle_rerun": {
            "seed": {
                "actions_source": legacy_design,
                "actions_mode": "design",
                "inputs_use_calculated_actions": False,
                "loads_edit_mode": "ULS",
                "inputs_loads_edit_toggle": False,
            },
            "detailed": True,
            "design_controls": True,
        },
        "source_mode_change_rerun": {
            "seed": {
                "actions_source": legacy_manual,
                "actions_mode": "manual",
                "inputs_use_calculated_actions": True,
                "loads_edit_mode": "ULS",
                "inputs_loads_edit_toggle": False,
            },
            "detailed": True,
            "design_controls": True,
        },
        "load_mode_change_rerun": {
            "seed": {
                "actions_source": legacy_manual,
                "actions_mode": "manual",
                "inputs_use_calculated_actions": False,
                "loads_edit_mode": "ULS",
                "inputs_loads_edit_toggle": True,
            },
            "detailed": False,
            "design_controls": False,
        },
        "detailed_design_controls_render": {
            "seed": {
                "actions_source": legacy_design,
                "actions_mode": "design",
                "inputs_use_calculated_actions": True,
                "loads_edit_mode": "SLS",
                "inputs_loads_edit_toggle": True,
                "_force_design_action_widget_hydrate": True,
                "_inputs_use_calculated_actions_user_intent": True,
            },
            "detailed": True,
            "design_controls": True,
        },
    }

    results = {}
    for name, config in cases.items():
        results[name] = {
            "legacy": _run_case(
                legacy_inputs_page,
                config["seed"],
                detailed=bool(config["detailed"]),
                design_controls=bool(config["design_controls"]),
            ),
            "route": _run_case(
                route,
                config["seed"],
                detailed=bool(config["detailed"]),
                design_controls=bool(config["design_controls"]),
            ),
        }

    checks = {
        "all_rerun_outcomes_match_legacy": all(case["legacy"]["rerun"] == case["route"]["rerun"] for case in results.values()),
        "all_call_sequences_match_legacy": all(case["legacy"]["calls"] == case["route"]["calls"] for case in results.values()),
        "all_session_effects_match_legacy": all(case["legacy"]["session"] == case["route"]["session"] for case in results.values()),
    }
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8")
    checks["route_no_longer_delegates_design_actions_coordinator"] = (
        "_legacy_inputs_page.render_inputs_design_actions_section_current_coordinator" not in route_source
    )

    status = "PASS" if all(checks.values()) else "FAIL"
    artifact = {
        "status": status,
        "timestamp": timestamp,
        "checks": checks,
        "cases": results,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_route_design_actions_parity_{timestamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_route_design_actions_parity_{timestamp}.md"
    json_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Design Actions Parity",
                "",
                f"Status: {status}",
                "",
                "## Checks",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
                "## Scope",
                "- Compares old and route-local Design Actions coordinator branches using fake Streamlit.",
                "- Verifies toggle alignment rerun, source/mode rerun, ULS/SLS mode rerun, fast hidden fields, detailed rendering, design lock disabled fields, helper call order, and session effects.",
                "- Leaves design-action helper functions as explicit old-page bridges for later focused slices.",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "artifact": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
