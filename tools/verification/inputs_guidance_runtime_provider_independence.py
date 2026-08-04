"""Lock bridge-independent construction of the Inputs guidance runtime."""

from __future__ import annotations

import builtins
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "inputs_page_app_contract_bridge" or name.startswith(
            "inputs_page_app_contract_bridge."
        ):
            raise AssertionError(f"legacy bridge import attempted: {name}")
        return original_import(name, *args, **kwargs)

    builtins.__import__ = guarded_import
    try:
        import streamlit as st

        from inputs_application.guidance_runtime_provider import (
            build_guidance_runtime_provider,
        )
        from inputs_page_modules.guidance_compute import (
            GuidanceComputeRuntime,
            build_guidance_compute_runtime,
        )

        runtime = build_guidance_compute_runtime(
            build_guidance_runtime_provider(st)
        )
    finally:
        builtins.__import__ = original_import

    assert isinstance(runtime, GuidanceComputeRuntime)
    assert "inputs_page_app_contract_bridge" not in sys.modules
    print(
        "PASS: guidance runtime constructs without importing the legacy "
        "app-contract bridge"
    )


if __name__ == "__main__":
    main()
