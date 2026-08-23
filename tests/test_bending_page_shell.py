from __future__ import annotations

import ast
from pathlib import Path

from engineering_page_sections.bending_page_shell import BendingPageShell


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


class _FakeStreamlit:
    def __init__(self):
        self.events: list[tuple[str, object]] = []
        self._container_index = 0
        self._empty_index = 0

    def container(self, *, key=None):
        self._container_index += 1
        name = key or f"container-{self._container_index}"
        self.events.append(("container", name))
        return _FakeContainer(self.events, name)

    def empty(self):
        self._empty_index += 1
        name = f"empty-{self._empty_index}"
        self.events.append(("empty", name))
        return name


def test_shell_reserves_the_existing_summary_first_section_order() -> None:
    fake = _FakeStreamlit()
    shell = BendingPageShell.create(fake)
    fake.events.append(("summary", "rendered"))
    content = shell.reserve_content(fake)

    assert shell.top is not None
    assert content.diagram_options == "empty-1"
    assert content.diagram_section == "empty-2"
    assert content.inputs == "empty-3"
    assert content.calculations is not None
    assert fake.events == [
        ("container", "container-1"),
        ("summary", "rendered"),
        ("container", "bending_diagram_frame"),
        ("enter", "bending_diagram_frame"),
        ("empty", "empty-1"),
        ("empty", "empty-2"),
        ("exit", "bending_diagram_frame"),
        ("empty", "empty-3"),
        ("container", "container-3"),
    ]


def test_shell_module_has_no_engineering_or_session_state_dependency() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_page_shell.py"
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
    assert "bending_core" not in imported_roots
    assert "calculations" not in imported_roots
    assert "session_state" not in source


def test_runtime_uses_the_shared_shell_for_all_reserved_page_positions() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert "bending_page_shell = BendingPageShell.create(st)" in source
    assert "shell_content = bending_page_shell.reserve_content(st)" in source
    assert "diagram_options_placeholder = shell_content.diagram_options" in source
    assert "diagram_section_placeholder = shell_content.diagram_section" in source
    assert "inputs_placeholder = shell_content.inputs" in source
    assert "calc_blocks_container = shell_content.calculations" in source
