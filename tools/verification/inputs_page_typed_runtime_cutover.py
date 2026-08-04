"""Prove the Inputs page owns a complete typed, concern-split application runtime."""

from __future__ import annotations

import ast
import contextlib
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PAGE = ROOT / "inputs_page.py"
RUNTIME = ROOT / "inputs_application/page_runtime"
LEGACY_FILES = (
    ROOT / "inputs_page_app_contract_bridge.py",
    ROOT / "inputs_page_route_coordinators.py",
)
EXPECTED_OWNER_MODULES = {
    "inputs_application.page_runtime.common",
    "inputs_application.page_runtime.setup",
    "inputs_application.page_runtime.batch",
    "inputs_application.page_runtime.calculations",
    "inputs_application.page_runtime.design_guide",
    "inputs_application.page_runtime.mode",
    "inputs_application.page_runtime.divider",
    "inputs_application.page_runtime.summaries",
    "inputs_application.page_runtime.tail",
    "inputs_application.page_runtime.widgets",
}


def main() -> None:
    for path in LEGACY_FILES:
        assert not path.exists(), f"legacy file still exists: {path.name}"

    page_source = PAGE.read_text(encoding="utf-8")
    page_tree = ast.parse(page_source)
    assert "inputs_page_route_coordinators" not in page_source
    assert "inputs_page_app_contract_bridge" not in page_source
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "inputs_application.page_runtime"
        and any(
            alias.name == "build_inputs_page_runtime"
            for alias in node.names
        )
        for node in ast.walk(page_tree)
    )

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page

    runtime = inputs_page._INPUTS_PAGE_RUNTIME
    owners = {value.__module__ for value in vars(runtime).values()}
    assert owners.issubset(EXPECTED_OWNER_MODULES), owners
    assert len(vars(runtime)) == 13
    assert not (RUNTIME / "_split_manifest.py").exists()

    production_sources = [
        PAGE,
        ROOT / "inputs_application/one_click_entrypoint.py",
        *sorted(RUNTIME.glob("*.py")),
    ]
    for path in production_sources:
        source = path.read_text(encoding="utf-8")
        assert "inputs_page_app_contract_bridge" not in source, path
        assert "inputs_page_route_coordinators" not in source, path

    print(
        "PASS: Inputs page uses a typed 13-callable runtime across 10 permanent "
        "concern modules; the obsolete extraction manifest and legacy bridges "
        "are absent"
    )


if __name__ == "__main__":
    main()
