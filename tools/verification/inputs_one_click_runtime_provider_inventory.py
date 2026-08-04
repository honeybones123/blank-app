"""Track permanent ownership of the one-click transaction provider."""

from __future__ import annotations

import contextlib
import dataclasses
import functools
import io
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _has_bridge_callback(value) -> bool:
    if dataclasses.is_dataclass(value):
        return any(
            _has_bridge_callback(getattr(value, field.name))
            for field in dataclasses.fields(value)
        )
    if isinstance(value, functools.partial):
        return (
            _has_bridge_callback(value.func)
            or any(_has_bridge_callback(item) for item in value.args)
            or any(
                _has_bridge_callback(item)
                for item in (value.keywords or {}).values()
            )
        )
    return bool(
        callable(value)
        and getattr(value, "__module__", "")
        == "inputs_page_app_contract_bridge"
    )


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import streamlit as st

        from inputs_application.guidance_entrypoint import (
            build_guidance_entrypoint_runtime,
        )
        from inputs_application.one_click_runtime_provider import (
            build_partial_one_click_runtime_provider,
            missing_one_click_runtime_dependencies,
        )
        from inputs_page_modules.auto_design_compute import (
            _LEGACY_AUTO_DESIGN_NAMES,
        )

    guidance = build_guidance_entrypoint_runtime(
        st_module=st,
        os_module=os,
        sys_module=sys,
    )
    provider = build_partial_one_click_runtime_provider(
        st_module=st,
        guidance_runtime=guidance,
    )
    missing = missing_one_click_runtime_dependencies(provider)
    owned = len(_LEGACY_AUTO_DESIGN_NAMES) - len(missing)
    assert len(_LEGACY_AUTO_DESIGN_NAMES) == 109
    assert provider.copy.__name__ == "copy"
    assert provider.math.__name__ == "math"
    assert owned == 109, (owned, missing)
    assert not _has_bridge_callback(provider)
    print(
        "PASS: one-click provider has 109/109 bridge-independent permanent "
        f"dependencies; {len(missing)} true migration slots remain"
    )


if __name__ == "__main__":
    main()
