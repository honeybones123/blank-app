"""Verify the Design overview collector has an explicit typed boundary."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    owner = (
        ROOT / "inputs_page_modules" / "app_bridge" / "design_overview_collector.py"
    ).read_text(encoding="utf-8")
    bridge = (ROOT / "inputs_page_app_contract_bridge.py").read_text(encoding="utf-8")
    assert "@dataclass(frozen=True)" in owner
    assert "class DesignOverviewRuntime" in owner
    assert "globals().update" not in owner
    assert "bind_design_overview_collector_dependencies" not in owner
    assert "runtime: DesignOverviewRuntime" in owner
    assert "runtime=DesignOverviewRuntime(" in bridge
    print("PASS: Design overview collector uses a frozen explicit runtime")


if __name__ == "__main__":
    main()
