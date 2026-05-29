"""Replay the Design Guide one-click solver against a frozen dual-domain fixture.

Usage:
    python tools/replay_one_click_dual_domain.py tests/fixtures/dual_bending_shear_fail_snapshot.json

The harness is intentionally safety-first:
- PASS_SOLVED means the solver found final updates and both bending/shear are in band.
- PASS_NO_COMMIT means the solver refused to commit a partial or overdone design.
- FAIL_PARTIAL_COMMIT means final updates exist while either required domain is outside the target band.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import logging
import math
import os
from pathlib import Path
import sys
from typing import Any


REQUIRED_DOMAINS = ("bending", "shear")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return None
    try:
        import numpy as np  # type: ignore

        if isinstance(value, np.generic):
            return _json_safe(value.item())
    except Exception:
        pass
    return value


def _load_fixture(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and isinstance(data.get("shared"), dict):
        return dict(data["shared"])
    if isinstance(data, dict):
        return dict(data)
    raise TypeError(f"Fixture must contain a JSON object: {path}")


def _import_inputs_page():
    os.environ.setdefault("STREAMLIT_LOG_LEVEL", "error")
    logging.getLogger("streamlit").setLevel(logging.ERROR)
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        return importlib.import_module("inputs_page")


def _domain_scores(result: dict[str, Any]) -> dict[str, Any]:
    debug = dict(result.get("one_click_solver_debug") or {})
    trace = dict(debug.get("final_eval_band_trace") or {})
    scores = trace.get("domain_scores")
    return dict(scores or {})


def _target_domains(result: dict[str, Any]) -> list[str]:
    debug = dict(result.get("one_click_solver_debug") or {})
    domains = debug.get("final_target_domains_eval") or debug.get("target_domains_for_band") or []
    if not isinstance(domains, list):
        return []
    out: list[str] = []
    for raw in domains:
        d = str(raw or "").strip().lower()
        if d in REQUIRED_DOMAINS and d not in out:
            out.append(d)
    return out


def _score_in_band(scores: dict[str, Any], domain: str) -> bool:
    score = scores.get(domain)
    return bool(isinstance(score, dict) and score.get("in_band") is True)


def _score_util(scores: dict[str, Any], domain: str) -> float | None:
    score = scores.get(domain)
    if not isinstance(score, dict):
        return None
    raw = score.get("util")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def replay(fixture: Path, *, max_steps: int) -> tuple[int, dict[str, Any]]:
    inputs_page = _import_inputs_page()
    state = _load_fixture(fixture)

    result = inputs_page._solve_one_click_to_target(  # noqa: SLF001 - intentional regression harness
        state,
        max_steps=max_steps,
        debug_enabled=False,
        trace_run_id=None,
        trace_source="one_click_replay",
    )

    debug = dict(result.get("one_click_solver_debug") or {})
    scores = _domain_scores(result)
    domains = _target_domains(result)
    final_updates = dict(result.get("final_updates") or {})

    missing_domains = [d for d in REQUIRED_DOMAINS if d not in domains]
    both_domains_in_band = all(_score_in_band(scores, d) for d in REQUIRED_DOMAINS)

    if missing_domains:
        verdict = "FAIL_MISSING_TARGET_DOMAINS"
        exit_code = 1
    elif final_updates and both_domains_in_band and bool(result.get("all_key_pass")):
        verdict = "PASS_SOLVED"
        exit_code = 0
    elif final_updates:
        verdict = "FAIL_PARTIAL_COMMIT"
        exit_code = 1
    else:
        verdict = "PASS_NO_COMMIT"
        exit_code = 0

    output = {
        "verdict": verdict,
        "status": result.get("status"),
        "stop_reason": result.get("stop_reason"),
        "step_count": result.get("step_count"),
        "reached_target_band": result.get("reached_target_band"),
        "all_key_pass": result.get("all_key_pass"),
        "final_updates_present": bool(final_updates),
        "final_updates": final_updates,
        "target_domains": domains,
        "missing_target_domains": missing_domains,
        "domain_scores": scores,
        "domain_utils": {d: _score_util(scores, d) for d in REQUIRED_DOMAINS},
        "final_target_domains_eval": debug.get("final_target_domains_eval"),
        "final_eval_band_trace": debug.get("final_eval_band_trace"),
    }
    return exit_code, _json_safe(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="Path to shared_snapshot-style JSON fixture.")
    parser.add_argument("--max-steps", type=int, default=6)
    args = parser.parse_args(argv)

    exit_code, output = replay(args.fixture, max_steps=args.max_steps)
    print(json.dumps(output, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
