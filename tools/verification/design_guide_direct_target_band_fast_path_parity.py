"""Live parity gate for the direct target-band fast path.

The fast path is intentionally feature-gated. This verifier proves whether it
is safe to make that gate default-on by comparing a normal live run against a
live run with active shear blocker proof deferred for broad-search candidates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROFILE_SCRIPT = ROOT / "tools" / "verification" / "design_guide_browser_live_smoothness_profile.py"
FAST_GATE_ENV = "DESIGN_GUIDE_DIRECT_TARGET_BAND_DEFER_ACTIVE_SHEAR_BLOCKER"


def _stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_json(path: Path | str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_load_error": f"{type(exc).__name__}: {exc}"}


def _json_path_from_stdout(stdout: str) -> str | None:
    for line in str(stdout or "").splitlines():
        if line.startswith("json="):
            return line.split("=", 1)[1].strip()
    return None


def _run_profile(*, port: int, recipe: str, timeout_s: int, fast_gate: bool) -> dict[str, Any]:
    env = os.environ.copy()
    if fast_gate:
        env[FAST_GATE_ENV] = "1"
    else:
        env[FAST_GATE_ENV] = "0"
    started_at = time.time()
    proc = subprocess.run(
        [
            sys.executable,
            str(PROFILE_SCRIPT),
            "--port",
            str(port),
            "--recipe",
            recipe,
            "--timeout-s",
            str(timeout_s),
        ],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=max(120, int(timeout_s) + 90),
    )
    json_path = _json_path_from_stdout(proc.stdout)
    payload = _load_json(json_path)
    return {
        "fast_gate": bool(fast_gate),
        "port": int(port),
        "recipe": recipe,
        "started_at": started_at,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "json_path": json_path,
        "payload": payload,
    }


def _first_scenario(run: dict[str, Any]) -> dict[str, Any]:
    payload = dict(run.get("payload") or {})
    scenarios = list(payload.get("scenarios") or [])
    return dict(scenarios[0] or {}) if scenarios else {}


def _counter(run: dict[str, Any], key: str) -> Any:
    scenario = _first_scenario(run)
    counters = dict(scenario.get("counters") or {})
    return counters.get(key)


def _speed_row(run: dict[str, Any], name: str) -> dict[str, Any]:
    scenario = _first_scenario(run)
    counters = dict(scenario.get("counters") or {})
    rows = list(counters.get("speed_profile_last_run_top") or [])
    for row in rows:
        if str((row or {}).get("name") or "") == name:
            return dict(row)
    return {}


def _scenario_summary(run: dict[str, Any]) -> dict[str, Any]:
    scenario = _first_scenario(run)
    return {
        "status": (run.get("payload") or {}).get("status"),
        "elapsed_ms": scenario.get("elapsed_ms"),
        "snapshot_hash": scenario.get("snapshot_hash"),
        "publication_hash": _counter(run, "final_publication_hash"),
        "display_hash": _counter(run, "final_publication_display_hash"),
        "cta_hash": _counter(run, "button_contract_hash"),
        "apply_payload_hash": _counter(run, "apply_payload_hash"),
        "render": _speed_row(run, "ui_render.inputs_page.render_inputs"),
        "candidate_eval": _speed_row(run, "candidate_preview_evaluation.evaluate_candidate_full"),
        "active_shear_blocker_probe": _speed_row(
            run,
            "candidate_preview_evaluation.evaluate_candidate_full.source.accepted_green_shear_low_util_blocker_probe",
        ),
        "summary_overview_build": _speed_row(run, "inputs_page.summary_overview_build"),
        "direct_target_band_search": _speed_row(
            run,
            "candidate_preview_evaluation.evaluate_candidate_full.source.design_guide_direct_target_band_search",
        ),
    }


def _count(row: dict[str, Any]) -> int:
    try:
        return int(row.get("count") or 0)
    except Exception:
        return 0


def _ms(row: dict[str, Any]) -> float:
    try:
        return float(row.get("total_ms") or 0.0)
    except Exception:
        return 0.0


def _markdown(payload: dict[str, Any]) -> str:
    comparison = dict(payload.get("comparison") or {})
    base = dict(comparison.get("default") or {})
    base_repeat = dict(comparison.get("default_repeat") or {})
    fast = dict(comparison.get("fast_gate") or {})
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Direct Target-Band Fast Path Parity",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Recipe: `{payload.get('recipe')}`",
        f"- Default artifact: `{payload.get('default_artifact')}`",
        f"- Default repeat artifact: `{payload.get('default_repeat_artifact')}`",
        f"- Fast-gate artifact: `{payload.get('fast_gate_artifact')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in checks.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Timing",
            "",
            f"- Default elapsed: `{base.get('elapsed_ms')}` ms",
            f"- Default repeat elapsed: `{base_repeat.get('elapsed_ms')}` ms",
            f"- Fast-gate elapsed: `{fast.get('elapsed_ms')}` ms",
            f"- Default render: `{_ms(dict(base.get('render') or {}))}` ms",
            f"- Default repeat render: `{_ms(dict(base_repeat.get('render') or {}))}` ms",
            f"- Fast-gate render: `{_ms(dict(fast.get('render') or {}))}` ms",
            f"- Default candidate evals: `{_count(dict(base.get('candidate_eval') or {}))}`",
            f"- Default repeat candidate evals: `{_count(dict(base_repeat.get('candidate_eval') or {}))}`",
            f"- Fast-gate candidate evals: `{_count(dict(fast.get('candidate_eval') or {}))}`",
            f"- Default active blocker evals: `{_count(dict(base.get('active_shear_blocker_probe') or {}))}`",
            f"- Default repeat active blocker evals: `{_count(dict(base_repeat.get('active_shear_blocker_probe') or {}))}`",
            f"- Fast-gate active blocker evals: `{_count(dict(fast.get('active_shear_blocker_probe') or {}))}`",
            "",
            "## Decision",
            "",
            str(payload.get("decision") or ""),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", default="R3A_M300_V400")
    parser.add_argument("--port", type=int, default=8624)
    parser.add_argument("--timeout-s", type=int, default=75)
    args = parser.parse_args()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    default_run = _run_profile(
        port=int(args.port),
        recipe=str(args.recipe),
        timeout_s=int(args.timeout_s),
        fast_gate=False,
    )
    default_repeat_run = _run_profile(
        port=int(args.port) + 1,
        recipe=str(args.recipe),
        timeout_s=int(args.timeout_s),
        fast_gate=False,
    )
    fast_run = _run_profile(
        port=int(args.port) + 2,
        recipe=str(args.recipe),
        timeout_s=int(args.timeout_s),
        fast_gate=True,
    )
    default_summary = _scenario_summary(default_run)
    default_repeat_summary = _scenario_summary(default_repeat_run)
    fast_summary = _scenario_summary(fast_run)

    checks = {
        "default_profile_pass": default_summary.get("status") == "PASS",
        "default_repeat_profile_pass": default_repeat_summary.get("status") == "PASS",
        "fast_profile_pass": fast_summary.get("status") == "PASS",
        "default_publication_hash_stable": (
            default_summary.get("publication_hash") == default_repeat_summary.get("publication_hash")
        ),
        "default_display_hash_stable": (
            default_summary.get("display_hash") == default_repeat_summary.get("display_hash")
        ),
        "default_cta_hash_stable": default_summary.get("cta_hash") == default_repeat_summary.get("cta_hash"),
        "default_apply_payload_hash_stable": (
            default_summary.get("apply_payload_hash") == default_repeat_summary.get("apply_payload_hash")
        ),
        "publication_hash_equal": default_summary.get("publication_hash") == fast_summary.get("publication_hash"),
        "display_hash_equal": default_summary.get("display_hash") == fast_summary.get("display_hash"),
        "cta_hash_equal": default_summary.get("cta_hash") == fast_summary.get("cta_hash"),
        "apply_payload_hash_equal": (
            default_summary.get("apply_payload_hash") == fast_summary.get("apply_payload_hash")
        ),
        "candidate_eval_count_reduced": (
            _count(dict(fast_summary.get("candidate_eval") or {}))
            < _count(dict(default_summary.get("candidate_eval") or {}))
        ),
        "render_time_reduced": (
            _ms(dict(fast_summary.get("render") or {}))
            < _ms(dict(default_summary.get("render") or {}))
        ),
    }
    cutover_ready = all(
        bool(checks[key])
        for key in (
            "default_profile_pass",
            "default_repeat_profile_pass",
            "default_publication_hash_stable",
            "default_display_hash_stable",
            "default_cta_hash_stable",
            "default_apply_payload_hash_stable",
            "fast_profile_pass",
            "publication_hash_equal",
            "display_hash_equal",
            "cta_hash_equal",
            "apply_payload_hash_equal",
            "candidate_eval_count_reduced",
            "render_time_reduced",
        )
    )
    status = "PASS" if cutover_ready else "FAIL"
    if cutover_ready:
        decision = "Fast path is parity-clean and eligible for default-on cutover."
    elif not checks["default_publication_hash_stable"]:
        decision = (
            "Fast path is not eligible for default-on cutover yet because the default publication hash "
            "is not stable across repeated live default runs. Stabilize or re-scope publication hashing before "
            "using it as a cutover gate."
        )
    elif not checks["publication_hash_equal"]:
        decision = (
            "Fast path is not safe for default-on cutover yet: visible display, CTA, and Apply may match, "
            "but final publication hash parity is not proven."
        )
    else:
        decision = "Fast path is not safe for default-on cutover yet; inspect failing checks."

    payload = {
        "schema": "design_guide_direct_target_band_fast_path_parity.v1",
        "status": status,
        "created_at": _stamp(),
        "recipe": str(args.recipe),
        "default_artifact": default_run.get("json_path"),
        "default_repeat_artifact": default_repeat_run.get("json_path"),
        "fast_gate_artifact": fast_run.get("json_path"),
        "comparison": {
            "default": default_summary,
            "default_repeat": default_repeat_summary,
            "fast_gate": fast_summary,
        },
        "checks": checks,
        "decision": decision,
        "fast_gate_env": FAST_GATE_ENV,
        "cutover_ready": bool(cutover_ready),
        "proof_hash": _stable_hash(
            {
                "recipe": str(args.recipe),
                "comparison": {
                    "default": default_summary,
                    "default_repeat": default_repeat_summary,
                    "fast_gate": fast_summary,
                },
                "checks": checks,
                "decision": decision,
            }
        ),
    }
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_band_fast_path_parity_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_direct_target_band_fast_path_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_direct_target_band_fast_path_parity {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(f"decision={decision}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
