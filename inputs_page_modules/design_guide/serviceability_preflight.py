"""Compatibility export for the application-owned serviceability preflight."""

from __future__ import annotations

from typing import Any

from inputs_application.guidance_runtime_contracts import ServiceabilityPreflightRuntime
from inputs_application.serviceability_preflight import (
    serviceability_governs_preflight_payload,
)


_SERVICEABILITY_PREFLIGHT_DEPENDENCIES: tuple[str, ...] = (
    "_collect_design_overview",
    "_parse_util_value",
    "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence",
)


def bind_serviceability_preflight_dependencies(namespace: dict[str, Any]) -> None:
    """Retain the historical binder for page callers during cutover."""

    globals().update(
        {
            name: namespace[name]
            for name in _SERVICEABILITY_PREFLIGHT_DEPENDENCIES
            if name in namespace
        }
    )


def _serviceability_governs_preflight_payload(
    state: dict,
    *,
    runtime: ServiceabilityPreflightRuntime | None = None,
) -> dict | None:
    if runtime is None:
        namespace = globals()
        runtime = ServiceabilityPreflightRuntime(
            collect_design_overview=namespace["_collect_design_overview"],
            parse_util_value=namespace["_parse_util_value"],
            build_no_repair_blocker=namespace[
                "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence"
            ],
        )
    return serviceability_governs_preflight_payload(state, runtime=runtime)


__all__ = [
    "ServiceabilityPreflightRuntime",
    "bind_serviceability_preflight_dependencies",
    "_serviceability_governs_preflight_payload",
]
