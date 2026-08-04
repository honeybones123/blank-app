"""Pure contracts for guidance-entrypoint preflight stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ServiceabilityPreflightRuntime:
    collect_design_overview: Callable[..., Any]
    parse_util_value: Callable[..., Any]
    build_no_repair_blocker: Callable[..., Any]


@dataclass(frozen=True)
class GuidanceEntrypointRuntime:
    compute_runtime: Any
    st_module: Any
    os_module: Any
    sys_module: Any
    serviceability_preflight: Callable[..., Any]
    mixed_width_cleanup_promotion: Callable[..., Any]


__all__ = ["GuidanceEntrypointRuntime", "ServiceabilityPreflightRuntime"]
