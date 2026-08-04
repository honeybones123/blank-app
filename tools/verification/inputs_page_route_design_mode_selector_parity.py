from __future__ import annotations

import copy
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

    def columns(self, spec, *, gap=None, vertical_alignment=None):
        spec_list = list(spec) if isinstance(spec, (list, tuple)) else [spec]
        self._calls.append(("columns", spec_list, gap, vertical_alignment))
        return [
            _FakeContext(self._calls, f"column:{len(self._calls)}:{idx}")
            for idx, _ in enumerate(spec_list)
        ]

    def caption(self, text):
        self._calls.append(("caption", str(text)))

    def toggle(self, label, *, key=None, help=None, on_change=None):
        self._calls.append(("toggle", str(label), key, help, bool(callable(on_change))))
        return bool(self.session_state.get(str(key), False))


def _run_case(module, seed: dict[str, Any]) -> dict[str, Any]:
    calls: list[tuple[str, Any]] = []
    session_state = copy.deepcopy(seed)
    fake_st = _FakeStreamlit(session_state, calls)

    original_st = module.st
    original_seed = module.seed_widget_from_shared
    original_radio = module.v2_radio
    original_info = module.info_i_button
    original_select = module.select_row
    original_register = module._register_rendered_key

    def _seed_widget_from_shared(widget_key: str, shared_key: str, fallback_default):
        calls.append(("seed_widget_from_shared", widget_key, shared_key, fallback_default))
        if widget_key not in session_state:
            session_state[widget_key] = session_state.get(shared_key, fallback_default)

    def _v2_radio(**kwargs):
        calls.append(
            (
                "v2_radio",
                kwargs.get("label"),
                kwargs.get("key"),
                list(kwargs.get("options") or []),
                kwargs.get("default_index"),
                kwargs.get("horizontal"),
                kwargs.get("help"),
                bool(callable(kwargs.get("on_change"))),
            )
        )
        options = list(kwargs.get("options") or [])
        if "_radio_return" in session_state:
            return session_state["_radio_return"]
        default_index = int(kwargs.get("default_index") or 0)
        return options[default_index]

    def _info_i_button(*, content=None, help_text=None, key=None, use_container_width=False):
        calls.append(("info_i_button", content, help_text, key, bool(use_container_width)))
        return _FakeContext(calls, "info_i_button")

    def _select_row(label, key, options, default=None, sync_callbacks=None, help_text=None, *args, **kwargs):
        option_keys = list(options.keys()) if isinstance(options, dict) else list(options or [])
        calls.append(
            (
                "select_row",
                label,
                key,
                option_keys,
                default,
                help_text,
                bool(sync_callbacks and sync_callbacks.get(key)),
            )
        )

    def _register_rendered_key(key: str):
        calls.append(("register_rendered_key", str(key)))
        rendered = session_state.get("_rendered_widget_keys")
        if not isinstance(rendered, set):
            rendered = set()
            session_state["_rendered_widget_keys"] = rendered
        rendered.add(str(key))

    try:
        module.st = fake_st
        module.seed_widget_from_shared = _seed_widget_from_shared
        module.v2_radio = _v2_radio
        module.info_i_button = _info_i_button
        module.select_row = _select_row
        module._register_rendered_key = _register_rendered_key
        result = module.render_inputs_design_mode_selector_coordinator(
            sync_callbacks={
                "inputs_detailed_mode_toggle": lambda: None,
                "inputs_design_optimisation_goal": lambda: None,
                "inputs_optimisation_lock_geometry": lambda: None,
            }
        )
    finally:
        module.st = original_st
        module.seed_widget_from_shared = original_seed
        module.v2_radio = original_radio
        module.info_i_button = original_info
        module.select_row = original_select
        module._register_rendered_key = original_register

    rendered_keys = sorted(session_state.get("_rendered_widget_keys") or [])
    return {
        "result": bool(result),
        "calls": calls,
        "session": {
            "inputs_detailed_mode_toggle": session_state.get("inputs_detailed_mode_toggle"),
            "inputs_optimisation_lock_geometry": session_state.get("inputs_optimisation_lock_geometry"),
            "_rendered_widget_keys": rendered_keys,
        },
    }


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    import inputs_page as legacy_inputs_page
    import inputs_page_route_coordinators as route

    cases = {
        "fast_balanced": {
            "inputs_detailed_mode": False,
            "design_optimisation_goal": "balanced",
            "optimisation_lock_geometry": False,
        },
        "detailed_less_shear_locked": {
            "inputs_detailed_mode": True,
            "design_optimisation_goal": "less_shear_reinforcement",
            "optimisation_lock_geometry": True,
            "_radio_return": True,
        },
        "invalid_goal_defaults_balanced": {
            "inputs_detailed_mode": False,
            "design_optimisation_goal": "not-a-real-goal",
            "optimisation_lock_geometry": False,
        },
    }

    results = {
        name: {
            "legacy": _run_case(legacy_inputs_page, seed),
            "route": _run_case(route, seed),
        }
        for name, seed in cases.items()
    }

    checks = {
        "all_results_match_legacy": all(case["legacy"]["result"] == case["route"]["result"] for case in results.values()),
        "all_call_sequences_match_legacy": all(case["legacy"]["calls"] == case["route"]["calls"] for case in results.values()),
        "all_session_effects_match_legacy": all(case["legacy"]["session"] == case["route"]["session"] for case in results.values()),
    }
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8")
    checks["route_no_longer_delegates_design_mode_selector"] = (
        "_legacy_inputs_page.render_inputs_design_mode_selector_coordinator" not in route_source
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
    json_path = ARTIFACT_DIR / f"inputs_page_route_design_mode_selector_parity_{timestamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_route_design_mode_selector_parity_{timestamp}.md"
    json_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Design Mode Selector Parity",
                "",
                f"Status: {status}",
                "",
                "## Checks",
                *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
                "",
                "## Scope",
                "- Compares the old design-mode selector coordinator to the route-local coordinator using fake Streamlit widgets.",
                "- Verifies widget keys, option/default wiring, help text, callback wiring, captions, rendered-key registration, and return value.",
                "- Uses locked Design Brain config for optimisation goal labels instead of old page constants.",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "artifact": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
