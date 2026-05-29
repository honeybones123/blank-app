from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "tools"
RUNNERS = TOOLS / "verification" / "runners"

COMPILE_FILES = [
    "app.py",
    "inputs_page.py",
    "design_guidance_engine.py",
    "state_and_helpers.py",
    "tools/browser_live_design_guide_fuzz_verifier.py",
    "tools/verification/helpers/browser_helpers.py",
    "tools/verification/helpers/browser_one_click_regression.py",
    "tools/verification/helpers/overdesign_assertions.py",
    "tools/verification/runners/real_user_design_guide_ladder.py",
    "tools/verification/runners/local_cleanup_apply_effectiveness_ladder.py",
    "tools/verification/runners/recommendation_contract_ladder.py",
    "tools/verification/runners/summary_truth_ladder.py",
    "tools/verification/runners/optimisation_expectation_ladder.py",
    "tools/verification/runners/super_verification.py",
    "tools/verification/previous_fixes_gate.py",
    "tools/run_design_guide_previous_fixes_gate.py",
    "tools/verification/golden_matrix_runner.py",
    "tools/run_design_guide_golden_matrix.py",
    "tools/verification/fuzz_regression_gate.py",
    "tools/run_design_guide_fuzz_regression_gate.py",
    "tools/verification/recipes/one_click_recipe_defs.py",
    "tools/verification/runners/write_super_compact_review.py",
    "tools/verification/runners/write_verification_manifest.py",
    "tools/verification/runners/verification_quick_gate.py",
]

LADDERS: dict[str, dict[str, Any]] = {
    "local_cleanup_apply_effectiveness": {
        "script": "local_cleanup_apply_effectiveness_ladder.py",
        "timeout_s": 3600,
        "default_local_cases": [
            "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP",
            "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
        ],
    },
    "real_user_design_guide": {
        "script": "real_user_design_guide_ladder.py",
        "timeout_s": 3600,
        "default_local_cases": [
            "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP",
            "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
            "GEOMETRY_LOW_REO_OR_SHEAR_IN_TARGET_LOCAL_CLEANUP",
        ],
    },
    "optimisation_expectation": {
        "script": "optimisation_expectation_ladder.py",
        "timeout_s": 3600,
        "default_local_cases": [
            "ALREADY_TARGET",
            "SHEAR_SAFE_OVERDESIGNED",
            "COMBINED_SAFE_OVERDESIGNED",
        ],
    },
    "recommendation_contract": {
        "script": "recommendation_contract_ladder.py",
        "timeout_s": 3600,
        "default_local_cases": [
            "A_BEND_IN_BAND_SHEAR_ZERO",
            "D_PURE_SHEAR_LOW_DEMAND",
            "H_ALREADY_EFFICIENT_BENDING",
        ],
    },
    "summary_truth": {
        "script": "summary_truth_ladder.py",
        "timeout_s": 300,
        "default_local_cases": ["A_M45_V0", "B_M0_V150"],
    },
}

RELATED_CASES: dict[str, list[str]] = {
    "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP": [
        "BENDING_LOW_SHEAR_IN_TARGET_TERMINAL",
        "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
    ],
    "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP": [
        "SHEAR_VISIBLE_CTA_APPLIES_SHEAR_PAYLOAD",
        "BENDING_TARGET_SHEAR_LOW_FINAL_ACCEPTANCE",
    ],
    "ALREADY_TARGET": ["BENDING_LOW_SHEAR_IN_TARGET_TERMINAL"],
    "SHEAR_SAFE_OVERDESIGNED": ["SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP"],
    "COMBINED_SAFE_OVERDESIGNED": ["BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP"],
}


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _run_command(name: str, cmd: list[str], *, timeout_s: int) -> dict[str, Any]:
    started = time.perf_counter()
    ports = _ports_from_cmd(cmd)
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return {
            "name": name,
            "cmd": cmd,
            "returncode": proc.returncode,
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-120:]),
            "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-120:]),
        }
    except subprocess.TimeoutExpired as exc:
        _cleanup_streamlit_ports(ports)
        _cleanup_attached_port_processes(ports)
        return {
            "name": name,
            "cmd": cmd,
            "returncode": None,
            "status": "TIMEOUT",
            "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "stdout_tail": "\n".join((exc.stdout or "").splitlines()[-120:]) if isinstance(exc.stdout, str) else "",
            "stderr_tail": "\n".join((exc.stderr or "").splitlines()[-120:]) if isinstance(exc.stderr, str) else "",
        }


def _ports_from_cmd(cmd: list[str]) -> list[int]:
    ports: list[int] = []
    for idx, part in enumerate(cmd):
        text = str(part)
        if text == "--port" and idx + 1 < len(cmd):
            try:
                ports.append(int(cmd[idx + 1]))
            except Exception:
                pass
        elif text.startswith("--server.port"):
            pieces = text.split("=", 1)
            if len(pieces) == 2:
                try:
                    ports.append(int(pieces[1]))
                except Exception:
                    pass
    return ports


def _cleanup_streamlit_ports(ports: list[int]) -> None:
    if not ports:
        return
    port_patterns = "|".join(re.escape(str(port)) for port in sorted(set(ports)))
    script = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -match 'streamlit' -and $_.CommandLine -match '({port_patterns})' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        pass


def _cleanup_attached_port_processes(ports: list[int]) -> None:
    if not ports:
        return
    port_list = ",".join(str(int(port)) for port in sorted(set(ports)))
    script = (
        f"$ports=@({port_list}); "
        "$pids = Get-NetTCPConnection -ErrorAction SilentlyContinue | "
        "Where-Object { $ports -contains $_.LocalPort -and $_.OwningProcess -ne 0 } | "
        "Select-Object -ExpandProperty OwningProcess -Unique; "
        "foreach ($targetPid in $pids) { "
        "  Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue "
        "}"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        pass


def _case_args(case_ids: list[str]) -> list[str]:
    args: list[str] = []
    for case_id in case_ids:
        args.extend(["--case", case_id])
    return args


def _list_ladder_cases(script: str) -> list[str]:
    cmd = [sys.executable, str(RUNNERS / script), "--list-cases"]
    proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=60)  # noqa: S603
    if proc.returncode != 0:
        return []
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def _case_catalog() -> dict[str, list[str]]:
    return {name: _list_ladder_cases(str(meta["script"])) for name, meta in LADDERS.items()}


def _expand_related(case_ids: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for case_id in case_ids:
        for item in [case_id, *RELATED_CASES.get(case_id, [])]:
            if item and item not in seen:
                seen.add(item)
                expanded.append(item)
    return expanded


def _selected_for_ladder(
    ladder_name: str,
    requested: list[str],
    catalog: dict[str, list[str]],
    *,
    tier: str,
) -> list[str]:
    available = set(catalog.get(ladder_name) or [])
    if tier == "freeze":
        return []
    candidates = _expand_related(requested) if requested else list(LADDERS[ladder_name].get("default_local_cases") or [])
    return [case_id for case_id in candidates if case_id in available]


def _artifact_path_from_output(text: str) -> Path | None:
    patterns = [
        r'"output"\s*:\s*"([^"]+\.json)"',
        r"([A-Za-z]:\\[^\r\n]+?\.json)",
        r"((?:\.?/?|artifacts/)?[A-Za-z0-9_./\\ -]+?_ladder_[0-9T:-]+\.json)",
        r"(super_verification_[0-9_-]+\.json)",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text or ""):
            candidate = Path(str(match))
            if not candidate.is_absolute():
                candidate = REPO / candidate
            if candidate.exists():
                return candidate
    return None


def _load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _case_duration_ms(case: dict[str, Any]) -> float | None:
    for key in (
        "total_ms",
        "total_duration_ms",
        "case_duration_ms",
        "duration_ms",
        "elapsed_ms",
    ):
        value = case.get(key)
        try:
            if value is not None:
                return float(value)
        except Exception:
            pass
    meta = case.get("settle_timing") or case.get("pre_settle_meta") or {}
    if isinstance(meta, dict):
        value = meta.get("total_ms") or meta.get("settle_wait_time_ms")
        try:
            if value is not None:
                return float(value)
        except Exception:
            pass
    return None


def _timeout_stage(case: dict[str, Any]) -> str | None:
    for key in ("timeout_stage", "first_timeout_stage", "stage"):
        value = case.get(key)
        if value:
            return str(value)
    reasons = " | ".join(str(item) for item in case.get("fail_reasons") or [])
    if "Browser state" in reasons:
        return "browser_state_wait"
    if "Locator.wait_for" in reasons:
        return "locator_wait"
    return None


def _browser_live_satisfied(artifact: dict[str, Any]) -> bool | None:
    cases = artifact.get("cases")
    if not isinstance(cases, list) or not cases:
        mode = artifact.get("browser_mode") or artifact.get("browser_mode_required")
        return True if mode == "browser_live" else None
    modes = [str(case.get("browser_mode") or "") for case in cases if case.get("browser_mode")]
    if not modes:
        return None
    return all(mode == "browser_live" for mode in modes)


def _summarise_gate(result: dict[str, Any]) -> dict[str, Any]:
    artifact_path = _artifact_path_from_output(
        "\n".join([str(result.get("stdout_tail") or ""), str(result.get("stderr_tail") or "")])
    )
    artifact = _load_json(artifact_path)
    cases = artifact.get("cases") if isinstance(artifact.get("cases"), list) else []
    case_summaries: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_summaries.append(
            {
                "gate": result["name"],
                "case_id": case.get("case_id") or case.get("name"),
                "verdict": case.get("verdict") or case.get("status"),
                "duration_ms": _case_duration_ms(case),
                "timeout_stage": _timeout_stage(case),
                "browser_probe_wait_ms": (case.get("before_settle_meta") or {}).get("settle_wait_time_ms")
                if isinstance(case.get("before_settle_meta"), dict)
                else None,
                "click_to_settle_ms": (case.get("post_click_settle_meta") or {}).get("settle_wait_time_ms")
                if isinstance(case.get("post_click_settle_meta"), dict)
                else None,
            }
        )
    artifact_size = artifact_path.stat().st_size if artifact_path and artifact_path.exists() else None
    return {
        "name": result["name"],
        "status": result["status"],
        "returncode": result.get("returncode"),
        "duration_ms": result.get("duration_ms"),
        "artifact_path": str(artifact_path) if artifact_path else None,
        "artifact_size_bytes": artifact_size,
        "browser_live_satisfied": _browser_live_satisfied(artifact),
        "timeout_stage": artifact.get("summary", {}).get("first_timeout_stage")
        if isinstance(artifact.get("summary"), dict)
        else None,
        "cases": case_summaries,
    }


def _write_timing_summary(
    *,
    timestamp: str,
    tier: str,
    case_ids: list[str],
    gate_results: list[dict[str, Any]],
    catalog: dict[str, list[str]],
) -> Path:
    gate_summaries = [_summarise_gate(result) for result in gate_results]
    all_cases = [case for gate in gate_summaries for case in gate.get("cases", [])]
    slowest_cases = sorted(
        [case for case in all_cases if case.get("duration_ms") is not None],
        key=lambda row: float(row.get("duration_ms") or 0.0),
        reverse=True,
    )[:10]
    payload = {
        "generated_at": timestamp,
        "tier": tier,
        "case_ids": case_ids,
        "overall_status": "PASS" if all(result["status"] == "PASS" for result in gate_results) else "FAIL",
        "freeze_safe_claimed": bool(
            tier == "freeze"
            and gate_results
            and all(result["status"] == "PASS" for result in gate_results)
            and any(result["name"] == "super_verification" for result in gate_results)
        ),
        "streamlit_start_count": sum(
            1
            for result in gate_results
            if any("--base-url" == str(part) for part in result.get("cmd", [])) is False
            and result["name"] != "py_compile"
        ),
        "gate_timings": gate_summaries,
        "total_time_by_gate_ms": {gate["name"]: gate.get("duration_ms") for gate in gate_summaries},
        "total_time_by_case_ms": {
            f"{case.get('gate')}::{case.get('case_id')}": case.get("duration_ms")
            for case in all_cases
            if case.get("case_id")
        },
        "slowest_10_cases": slowest_cases,
        "timeout_stages": [
            {"gate": gate["name"], "timeout_stage": gate.get("timeout_stage")}
            for gate in gate_summaries
            if gate.get("timeout_stage")
        ]
        + [
            {"gate": case.get("gate"), "case_id": case.get("case_id"), "timeout_stage": case.get("timeout_stage")}
            for case in all_cases
            if case.get("timeout_stage")
        ],
        "browser_live_satisfied_by_gate": {
            gate["name"]: gate.get("browser_live_satisfied")
            for gate in gate_summaries
        },
        "artifact_sizes": {
            gate["name"]: gate.get("artifact_size_bytes")
            for gate in gate_summaries
            if gate.get("artifact_size_bytes") is not None
        },
        "known_case_catalog": catalog,
    }
    out = REPO / "artifacts" / "verification" / "latest" / f"verification_timing_summary_{timestamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out


def _compile_step() -> tuple[str, list[str], int]:
    return ("py_compile", [sys.executable, "-m", "py_compile", *COMPILE_FILES], 300)


def _previous_fixes_gate_step(*, port: int) -> tuple[str, list[str], int]:
    return (
        "previous_fixed_groups_gate",
        [sys.executable, "tools/run_design_guide_previous_fixes_gate.py", "--port", str(port)],
        7200,
    )


def _golden_matrix_gate_step(*, port: int) -> tuple[str, list[str], int]:
    return (
        "golden_matrix_gate",
        [sys.executable, "tools/run_design_guide_golden_matrix.py", "--port", str(port)],
        7200,
    )


def _fuzz_regression_gate_step(*, port: int) -> tuple[str, list[str], int]:
    return (
        "fuzz_regression_gate",
        [sys.executable, "tools/run_design_guide_fuzz_regression_gate.py", "--port", str(port)],
        7200,
    )


def _focused_replay_step(*, replay: Path, port: int) -> tuple[str, list[str], int]:
    return (
        "focused_replay",
        [
            sys.executable,
            "tools/browser_live_design_guide_fuzz_verifier.py",
            "--replay-case",
            str(replay),
            "--port",
            str(port),
        ],
        1200,
    )


def _ladder_step(name: str, *, port: int, case_ids: list[str]) -> tuple[str, list[str], int]:
    meta = LADDERS[name]
    cmd = [sys.executable, str(RUNNERS / str(meta["script"])), "--port", str(port)]
    cmd.extend(_case_args(case_ids))
    return (name, cmd, int(meta["timeout_s"]))


def _steps_for_tier(
    tier: str,
    *,
    port: int,
    requested_cases: list[str],
    catalog: dict[str, list[str]],
) -> list[tuple[str, list[str], int]]:
    steps = [_compile_step()]
    if tier == "focused":
        if not requested_cases:
            return steps
        recognised = False
        offset = 0
        for ladder_name in LADDERS:
            selected = _selected_for_ladder(ladder_name, requested_cases, catalog, tier=tier)
            if selected:
                recognised = True
                steps.append(_ladder_step(ladder_name, port=port + offset, case_ids=selected))
                offset += 1
        if not recognised:
            raise SystemExit(f"No selected cases are known to the configured ladders: {', '.join(requested_cases)}")
    elif tier == "local":
        offset = 0
        for ladder_name in LADDERS:
            selected = _selected_for_ladder(ladder_name, requested_cases, catalog, tier=tier)
            if selected or not requested_cases:
                steps.append(_ladder_step(ladder_name, port=port + offset, case_ids=selected))
                offset += 1
    elif tier == "freeze":
        steps.append(_previous_fixes_gate_step(port=port))
        steps.append(_golden_matrix_gate_step(port=port))
        steps.append(_fuzz_regression_gate_step(port=port))
        offset = 0
        for ladder_name in LADDERS:
            steps.append(_ladder_step(ladder_name, port=port + offset, case_ids=[]))
            offset += 1
        steps.append(("super_verification", [sys.executable, str(RUNNERS / "super_verification.py"), "--port", str(port + offset)], 10800))
        steps.append(("compact_review", [sys.executable, str(RUNNERS / "write_super_compact_review.py")], 300))
        steps.append(("manifest", [sys.executable, str(RUNNERS / "write_verification_manifest.py")], 300))
    else:
        raise ValueError(f"Unsupported tier: {tier}")
    return steps


def _print_case_catalog(catalog: dict[str, list[str]]) -> None:
    for gate, cases in catalog.items():
        print(f"[{gate}]")
        for case_id in cases:
            print(case_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run tiered verification gates and emit timing summaries.")
    parser.add_argument(
        "--mode",
        choices=["compile", "focused", "previous-fixed", "golden", "fuzz-regression", "baseline"],
        required=False,
        help="Staged workflow mode. Use --mode focused --replay <path> for the first proof after a change.",
    )
    parser.add_argument("--tier", choices=["focused", "local", "freeze"], required=False)
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--replay", default=None, help="Replay JSON for --mode focused.")
    parser.add_argument("--case", action="append", dest="case_ids", default=None)
    parser.add_argument("--cases", default=None, help="Comma-separated case_id list.")
    parser.add_argument("--list-cases", action="store_true")
    args = parser.parse_args(argv)

    catalog = _case_catalog()
    if args.list_cases:
        _print_case_catalog(catalog)
        return 0
    if args.mode and args.tier:
        parser.error("Use either --mode or --tier, not both.")
    if not args.tier and not args.mode:
        parser.error("--mode or --tier is required unless --list-cases is used")

    case_ids = [str(case_id).strip() for case_id in (args.case_ids or []) if str(case_id).strip()]
    case_ids.extend(str(case_id).strip() for case_id in str(args.cases or "").split(",") if str(case_id).strip())
    timestamp = _now_stamp()
    results: list[dict[str, Any]] = []
    if args.mode:
        if args.mode == "compile":
            steps = [_compile_step()]
        elif args.mode == "focused":
            if not args.replay:
                parser.error("--mode focused requires --replay <path>.")
            replay = Path(str(args.replay))
            if not replay.is_absolute():
                replay = REPO / replay
            if not replay.exists():
                parser.error(f"Replay does not exist: {replay}")
            steps = [_compile_step(), _focused_replay_step(replay=replay, port=int(args.port))]
        elif args.mode == "previous-fixed":
            steps = [_compile_step(), _previous_fixes_gate_step(port=int(args.port))]
        elif args.mode == "golden":
            steps = [_compile_step(), _golden_matrix_gate_step(port=int(args.port))]
        elif args.mode == "fuzz-regression":
            steps = [_compile_step(), _fuzz_regression_gate_step(port=int(args.port))]
        elif args.mode == "baseline":
            steps = [
                _compile_step(),
                _previous_fixes_gate_step(port=int(args.port)),
                _golden_matrix_gate_step(port=int(args.port)),
                _fuzz_regression_gate_step(port=int(args.port)),
            ]
        else:
            raise ValueError(f"Unsupported mode: {args.mode}")
        workflow_label = str(args.mode)
    else:
        steps = _steps_for_tier(str(args.tier), port=args.port, requested_cases=case_ids, catalog=catalog)
        workflow_label = str(args.tier)

    for name, cmd, timeout_s in steps:
        if name == "focused_replay":
            _cleanup_attached_port_processes([int(args.port)])
        print(f"[quick_gate] BEGIN {name}", flush=True)
        result = _run_command(name, cmd, timeout_s=timeout_s)
        results.append(result)
        print(f"[quick_gate] END {name} {result['status']} {result['duration_ms']}ms", flush=True)
        if result["status"] != "PASS":
            break

    timing_path = _write_timing_summary(
        timestamp=timestamp,
        tier=workflow_label,
        case_ids=case_ids,
        gate_results=results,
        catalog=catalog,
    )
    status = "PASS" if all(result["status"] == "PASS" for result in results) else "FAIL"
    payload = {
        "generated_at": timestamp,
        "tier": args.tier,
        "mode": args.mode,
        "case_ids": case_ids,
        "status": status,
        "blocked_by_previous_fixed_groups_regression": any(
            result["name"] == "previous_fixed_groups_gate" and result["status"] != "PASS" for result in results
        ),
        "blocked_by_golden_matrix_regression": any(
            result["name"] == "golden_matrix_gate" and result["status"] != "PASS" for result in results
        ),
        "timing_summary": str(timing_path),
        "results": results,
    }
    out_dir = REPO / "artifacts" / "verification" / "latest" / "verification_quick_gate"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"verification_quick_gate_{workflow_label}_{timestamp}.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"status": status, "output": str(out), "timing_summary": str(timing_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
