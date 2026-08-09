"""Lock supported Streamlit API usage and iframe compatibility semantics."""

from __future__ import annotations

import ast
from pathlib import Path

from ui.streamlit_iframe import render_trusted_iframe


ROOT = Path(__file__).resolve().parents[2]


class _FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def iframe(self, body: str, **kwargs):
        self.calls.append((body, kwargs))
        return "iframe"


def verify_iframe_contract() -> None:
    fake = _FakeStreamlit()
    assert render_trusted_iframe(
        fake,
        "<script>window.parent;</script>",
        height=0,
        width=0,
        scrolling=False,
    ) == "iframe"
    body, kwargs = fake.calls[-1]
    assert "overflow:hidden" in body
    assert kwargs == {"width": 1, "height": 1}

    render_trusted_iframe(fake, "<p>diagram</p>", height=500, scrolling=True)
    body, kwargs = fake.calls[-1]
    assert "overflow:hidden" not in body
    assert kwargs == {"width": "stretch", "height": 500}


def verify_no_deprecated_calls() -> None:
    python_files = tuple(
        path
        for path in ROOT.rglob("*.py")
        if ".venv" not in path.parts
        and "build" not in path.parts
        and "__pycache__" not in path.parts
    )
    offenders: list[str] = []
    for path in python_files:
        source = path.read_text(encoding="utf-8")
        if (
            "use_container" + "_width" in source
            or "components." + "html(" in source
            or "experimental" + "_" in source
        ):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"deprecated Streamlit calls remain: {offenders}"


def verify_session_owned_number_rows_have_one_initial_value_authority() -> None:
    """A pre-seeded keyed widget must not also receive an explicit default."""

    offenders: list[str] = []
    for relative_path in (
        "design_page_runtime.py",
        "engineering_page_sections/design_inputs.py",
    ):
        path = ROOT / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        helpers = (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "render_inline_number_row"
        )
        for helper in helpers:
            for node in ast.walk(helper):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute) or node.func.attr != "number_input":
                    continue
                if any(keyword.arg == "value" for keyword in node.keywords):
                    offenders.append(relative_path)
    assert not offenders, (
        "session-owned inline number rows also pass an explicit widget default: "
        f"{offenders}"
    )


def verify_session_owned_selectors_have_one_initial_value_authority() -> None:
    session_owned_keys = {
        "beam_manager_active_selector",
        "crack_exposure_class",
        "inputs_use_calculated_actions",
    }
    offenders: list[str] = []
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv", "build", "__pycache__"} for part in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr not in {"selectbox", "toggle"}:
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            key_node = keywords.get("key")
            key_value = (
                key_node.value
                if isinstance(key_node, ast.Constant)
                else "beam_manager_active_selector"
                if isinstance(key_node, ast.Name) and key_node.id == "ACTIVE_BEAM_SELECTOR_KEY"
                else None
            )
            if key_value not in session_owned_keys:
                continue
            default_keyword = "index" if node.func.attr == "selectbox" else "value"
            if default_keyword in keywords:
                offenders.append(f"{path.relative_to(ROOT)}:{key_value}")
    assert not offenders, (
        "session-owned selectors also pass an explicit widget default: "
        f"{offenders}"
    )


def verify_session_owned_sliders_have_one_initial_value_authority() -> None:
    """Pre-seeded slider state is the default; the widget must not compete."""

    session_owned_keys = {"design_section_x_slider"}
    offenders: list[str] = []
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv", "build", "__pycache__"} for part in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "slider":
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            key_node = keywords.get("key")
            key_value = key_node.value if isinstance(key_node, ast.Constant) else None
            if key_value in session_owned_keys and "value" in keywords:
                offenders.append(f"{path.relative_to(ROOT)}:{key_value}")
    assert not offenders, (
        "session-owned sliders also pass an explicit widget default: "
        f"{offenders}"
    )


def main() -> None:
    verify_iframe_contract()
    verify_no_deprecated_calls()
    verify_session_owned_number_rows_have_one_initial_value_authority()
    verify_session_owned_selectors_have_one_initial_value_authority()
    verify_session_owned_sliders_have_one_initial_value_authority()
    print("streamlit compatibility contract: PASS")


if __name__ == "__main__":
    main()
