from __future__ import annotations

import ast
from pathlib import Path

from engineering_page_sections.shear_page_shell import ShearPageShell


ROOT = Path(__file__).resolve().parents[1]


class _FakeContainer:
    def __init__(self, events: list[tuple[str, object]], name: str):
        self._events = events
        self._name = name

    def __enter__(self):
        self._events.append(("enter", self._name))
        return self

    def __exit__(self, *_args):
        self._events.append(("exit", self._name))


class _FakePlaceholder:
    def __init__(self, events: list[tuple[str, object]], name: str):
        self._events = events
        self._name = name

    def container(self):
        self._events.append(("container", self._name))
        return _FakeContainer(self._events, self._name)


class _FakeStreamlit:
    def __init__(self):
        self.events: list[tuple[str, object]] = []

    def empty(self):
        self.events.append(("empty", "visualisation"))
        return _FakePlaceholder(self.events, "visualisation")


def test_shell_preserves_the_existing_summary_input_and_visualisation_order() -> None:
    fake = _FakeStreamlit()
    fake.events.append(("summary", "rendered"))
    shell = ShearPageShell.reserve_after_summary(
        fake,
        before_first_divider=lambda: fake.events.append(("timing", "visualisation")),
        render_first_divider=lambda: fake.events.append(("divider", "inputs")),
    )
    fake.events.append(("inputs", "rendered"))

    result = shell.render_visualisation(
        lambda: fake.events.append(("visualisation", "rendered")) or "diagram"
    )

    assert result == "diagram"
    assert fake.events == [
        ("summary", "rendered"),
        ("empty", "visualisation"),
        ("timing", "visualisation"),
        ("divider", "inputs"),
        ("inputs", "rendered"),
        ("container", "visualisation"),
        ("enter", "visualisation"),
        ("visualisation", "rendered"),
        ("exit", "visualisation"),
    ]


def test_shell_module_has_no_engineering_or_session_state_dependency() -> None:
    source = (
        ROOT / "engineering_page_sections" / "shear_page_shell.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        str(node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )

    assert "streamlit" not in imported_roots
    assert "shear_core" not in imported_roots
    assert "calculations" not in imported_roots
    assert "session_state" not in source


def test_runtime_uses_shell_for_deferred_visualisation_position() -> None:
    source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")

    reserve = source.index("shear_page_shell = ShearPageShell.reserve_after_summary(")
    inputs = source.index('render_timing_mark("shear_page.runtime.inputs.start")')
    visualisation = source.index("shear_page_shell.render_visualisation(")
    checks = source.index('render_timing_mark("shear_page.runtime.checks.start")')

    assert reserve < inputs < visualisation < checks
    assert "visualisation_placeholder = st.empty()" not in source
    assert "with visualisation_placeholder.container():" not in source
