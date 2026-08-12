"""One-shot background warm-up for the installed V2 Runtime contracts.

The first import of the calculation and Design Brain package graph is much
slower than every subsequent engineering run.  Render cold instances expose
that import cost to the first user unless Runtime begins loading the contracts
while the opening page is being rendered.

This module performs imports only.  It does not calculate, classify, search,
publish, mutate session state, or create Apply authority.
"""

from __future__ import annotations

from threading import Event, Lock, Thread


_started = False
_started_lock = Lock()
_ready = Event()
_failure: BaseException | None = None


def _warm() -> None:
    global _failure
    try:
        from inputs_application.new_design_brain_adapter import _v2_api

        _v2_api()
    except BaseException as exc:  # pragma: no cover - surfaced by normal use
        _failure = exc
    finally:
        _ready.set()


def start_v2_runtime_warmup() -> bool:
    """Start the process-owned import warm-up once.

    Returns ``True`` only for the caller that starts the worker.  The worker is
    daemonized so it can never keep a CLI command or deployment process alive.
    """

    global _started
    with _started_lock:
        if _started:
            return False
        _started = True
        Thread(target=_warm, name="inputs-v2-runtime-warmup", daemon=True).start()
        return True


def wait_for_v2_runtime_warmup(timeout: float | None = None) -> bool:
    """Wait for warm-up and raise its import failure, if any."""

    completed = _ready.wait(timeout)
    if completed and _failure is not None:
        raise RuntimeError("Inputs V2 Runtime warm-up failed") from _failure
    return completed


__all__ = ["start_v2_runtime_warmup", "wait_for_v2_runtime_warmup"]
