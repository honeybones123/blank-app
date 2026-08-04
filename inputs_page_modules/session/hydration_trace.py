"""Inputs hydration trace compatibility behavior."""

from __future__ import annotations


def inputs_hydration_trace_log(phase: str, **extra: object) -> None:
    """Preserve the live no-op trace contract without a legacy bridge call."""

    _ = phase
    _ = extra


__all__ = ["inputs_hydration_trace_log"]
