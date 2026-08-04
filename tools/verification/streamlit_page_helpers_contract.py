from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _AttrDict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key, value):
        self[key] = value


def test_helper_modules_import_without_app_execution() -> None:
    for module_name in (
        "bending_tabs",
        "shear_layout",
        "shear_steps",
        "step_ui",
        "ui.inputs_page_style",
        "ui_seamless_steps",
    ):
        assert importlib.import_module(module_name)


def test_expected_helper_api_surfaces_exist() -> None:
    bending_tabs = importlib.import_module("bending_tabs")
    shear_steps = importlib.import_module("shear_steps")
    inputs_style = importlib.import_module("ui.inputs_page_style")
    ui_seamless_steps = importlib.import_module("ui_seamless_steps")

    assert callable(bending_tabs.render_uls_tab)
    assert callable(bending_tabs.render_min_strength_tab)
    assert callable(bending_tabs.render_sls_tab)
    assert callable(shear_steps.render_step_1)
    assert callable(shear_steps.render_step_7)
    assert callable(inputs_style.apply_inputs_page_css)
    assert callable(ui_seamless_steps.inject_seamless_steps_css)
    assert callable(ui_seamless_steps.bind_summary_clicks)
    assert callable(ui_seamless_steps.step_card)


def test_step_ui_state_key_contract() -> None:
    step_ui = importlib.import_module("step_ui")
    original_session_state = step_ui.st.session_state
    try:
        step_ui.st.session_state = _AttrDict()
        step_ui.init_step_ui_state("bending")
        assert step_ui.is_expanded("bending", "uls_1") is False
        step_ui.toggle_step("bending", "uls_1")
        assert step_ui.st.session_state["step_open_uls_1"] is True
        assert step_ui.is_expanded("bending", "uls_1") is True
        step_ui.toggle_step("bending", "uls_1")
        assert step_ui.st.session_state["step_open_uls_1"] is False
    finally:
        step_ui.st.session_state = original_session_state


def main() -> int:
    test_helper_modules_import_without_app_execution()
    test_expected_helper_api_surfaces_exist()
    test_step_ui_state_key_contract()
    print("streamlit_page_helpers_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
