"""Pure runtime contracts for canonical state bridge operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, MutableMapping


@dataclass(frozen=True)
class CanonicalDesignStatePackRuntime:
    guidance_state_snapshot: Callable[[dict], dict]


@dataclass(frozen=True)
class CanonicalConvenienceResyncRuntime:
    agent_debug_log: Callable[..., Any]
    build_canonical_design_state_pack: Callable[[dict], dict]
    convenience_scalar_differs: Callable[[Any, Any], bool]
    guidance_state_snapshot: Callable[[dict], dict]
    session_state: MutableMapping[str, Any]
    set_shared: Callable[..., Any]
    shared_state_snapshot: Callable[[], dict]


__all__ = [
    "CanonicalConvenienceResyncRuntime",
    "CanonicalDesignStatePackRuntime",
]
