"""Neutral compatibility surface for retired V1 guidance entrypoints.

V2 publishes Design Brain results through ``DesignBrainService``.  The page
shell still imports these names while older coordinator modules are retired,
so they intentionally return an empty compatibility payload and never load a
legacy calculator or family implementation.
"""

from __future__ import annotations

from typing import Any

from inputs_application.guidance_runtime_contracts import GuidanceEntrypointRuntime


def build_guidance_entrypoint_runtime(*, st_module: Any, os_module: Any, sys_module: Any) -> GuidanceEntrypointRuntime:
    del st_module, os_module, sys_module
    return GuidanceEntrypointRuntime(
        compute_runtime=None,
        st_module=None,
        os_module=None,
        sys_module=None,
        serviceability_preflight=lambda _state: None,
        mixed_width_cleanup_promotion=lambda payload, *, state: dict(payload or {}),
    )


def compute_inputs_guidance(runtime: GuidanceEntrypointRuntime, state: dict, **_: Any) -> dict:
    del runtime, state
    return {"guidance_items": [], "source": "inputs_v2_authoritative_design_brain"}


def run_guidance_preflight(runtime: GuidanceEntrypointRuntime, state: dict) -> dict | None:
    return runtime.serviceability_preflight(state)


def run_guidance_compute(runtime: GuidanceEntrypointRuntime, state: dict, **_: Any) -> dict:
    return compute_inputs_guidance(runtime, state)


def run_guidance_postprocess(runtime: GuidanceEntrypointRuntime, payload: dict, state: dict) -> dict:
    return runtime.mixed_width_cleanup_promotion(payload, state=state)


__all__ = [
    "GuidanceEntrypointRuntime",
    "build_guidance_entrypoint_runtime",
    "compute_inputs_guidance",
    "run_guidance_compute",
    "run_guidance_postprocess",
    "run_guidance_preflight",
]
