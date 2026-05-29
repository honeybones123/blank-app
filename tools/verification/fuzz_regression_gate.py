"""Deterministic replay gate for promoted Design Guide fuzz regressions.

This gate is intentionally verification-only. It replays stable browser fuzz
failure cases that were promoted from the 2026-05-14 investigation, records a
per-case report, and fails if any promoted replay is missing or still red.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "verification"
REPLAY_DIR = REPO / "artifacts" / "verification" / "fuzz_regressions" / "2026-05-14"
SCREENSHOT_FIELD_KEYS = (
    "full_page_screenshot",
    "viewport_screenshot",
    "design_guide_screenshot",
    "summary_cards_screenshot",
    "debug_or_probe_screenshot",
    "screenshot_capture_status",
    "missing_crop_targets",
)

COMPILE_FILES = [
    "app.py",
    "inputs_page.py",
    "design_guidance_engine.py",
    "state_and_helpers.py",
    "tools/browser_live_design_guide_fuzz_verifier.py",
    "tools/run_design_guide_previous_fixes_gate.py",
    "tools/run_design_guide_golden_matrix.py",
    "tools/run_design_guide_fuzz_regression_gate.py",
    "tools/verification/fuzz_regression_gate.py",
]


@dataclass(frozen=True)
class FuzzRegressionReplay:
    name: str
    path: str
    root_group: str
    original_failure_classification: str
    expected_pass_condition: str
    never_regress: str


FUZZ_REGRESSION_REPLAYS: list[FuzzRegressionReplay] = [
    FuzzRegressionReplay(
        "fuzz_2026_05_14_case0_low_util_no_cleanup_or_blocker",
        "artifacts/verification/fuzz_regressions/2026-05-14/fuzz_2026_05_14_case0_low_util_no_cleanup_or_blocker.json",
        "low-util cleanup/blocker publication completeness",
        "low_util_no_cleanup_or_blocker",
        "Replay exits 0 with every low-util family covered by an executor-backed action or exact blocker proof.",
        "Low-util families must not leave the user with neither a cleanup action nor exhaustive blocker evidence.",
    ),
    FuzzRegressionReplay(
        "fuzz_2026_05_14_case1_multi_family_blocker_vague_reason",
        "artifacts/verification/fuzz_regressions/2026-05-14/fuzz_2026_05_14_case1_multi_family_blocker_vague_reason.json",
        "low-util cleanup/blocker publication completeness",
        "multi_family_blocker_vague_reason",
        "Replay exits 0 with combined low-util blockers publishing separate bending and shear blocker reasons.",
        "Combined blocker cards must not hide family-specific low-util reasons behind vague combined evidence.",
    ),
    FuzzRegressionReplay(
        "fuzz_2026_05_14_case2_card_not_recomputed_after_edit",
        "artifacts/verification/fuzz_regressions/2026-05-14/fuzz_2026_05_14_case2_card_not_recomputed_after_edit.json",
        "stale Design Guide recompute after edit",
        "card_not_recomputed_after_edit",
        "Replay exits 0 with the summary, card, payload, and debug fingerprints recomputed after the edit.",
        "Manual edits must not leave stale Design Guide cards or payloads after summary truth changes.",
    ),
    FuzzRegressionReplay(
        "fuzz_2026_05_14_case3_optimisation_outside_target_without_blocker",
        "artifacts/verification/fuzz_regressions/2026-05-14/fuzz_2026_05_14_case3_optimisation_outside_target_without_blocker.json",
        "low-util cleanup/blocker publication completeness",
        "optimisation_outside_target_without_blocker",
        "Replay exits 0 with below/outside-band actions backed by exact blocker proof for unavailable accepted-band cleanup.",
        "The app must not publish an ordinary optimisation action outside the accepted range without exact blocker evidence.",
    ),
    FuzzRegressionReplay(
        "fuzz_2026_05_14_case4_design_guide_collapsed_body_leaking",
        "artifacts/verification/fuzz_regressions/2026-05-14/fuzz_2026_05_14_case4_design_guide_collapsed_body_leaking.json",
        "collapsed Design Guide body layout leak",
        "design_guide_collapsed_body_leaking",
        "Replay exits 0 with exactly one Design Guide card, collapsed body hidden, and expanded evidence available.",
        "Collapsed Design Guide cards must not leak expanded body content or lose expanded evidence.",
    ),
    FuzzRegressionReplay(
        "fuzz_2026_05_14_case5_overdesign_blocker_false_cleanup_candidate_exists",
        "artifacts/verification/fuzz_regressions/2026-05-14/fuzz_2026_05_14_case5_overdesign_blocker_false_cleanup_candidate_exists.json",
        "low-util cleanup/blocker publication completeness",
        "overdesign_blocker_false_cleanup_candidate_exists",
        "Replay exits 0 because any safe executor-backed cleanup candidate is published instead of a blocker.",
        "The app must not publish an overdesign blocker while a safe improving executor-backed candidate exists.",
    ),
]


@dataclass
class CommandResult:
    name: str
    command: list[str]
    returncode: int | None
    status: str
    elapsed_sec: float
    stdout_tail: str = ""
    stderr_tail: str = ""
    failure_classification: str = ""
    visible_contradiction: str = ""
    replay_artifact_path: str = ""
    paste_ready_report_path: str = ""
    product_verifier_unknown: str = ""
    recommended_next_fix: str = ""
    screenshots: dict[str, Any] | None = None


def _now_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H-%M-%S")


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _tail(text: str, *, lines: int = 140) -> str:
    return "\n".join(str(text or "").splitlines()[-lines:])


def _compile_command() -> list[str]:
    return [sys.executable, "-m", "py_compile", *COMPILE_FILES]


def _json_objects(text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    objects: list[Any] = []
    for match in re.finditer(r"{", text or ""):
        try:
            obj, _ = decoder.raw_decode(text[match.start() :])
        except Exception:
            continue
        objects.append(obj)
    return objects


def _first_failure(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    failures = payload.get("failures")
    if isinstance(failures, list) and failures:
        first = failures[0]
        return first if isinstance(first, dict) else {}
    return payload if payload.get("failure_classification") or payload.get("classification") else {}


def _screenshot_fields(payload: dict[str, Any]) -> dict[str, Any]:
    screenshots = dict(payload.get("screenshots") or payload.get("first_failure_screenshots") or {})
    for key in SCREENSHOT_FIELD_KEYS:
        if key in payload and key not in screenshots:
            screenshots[key] = payload.get(key)
    result = {key: screenshots.get(key) for key in SCREENSHOT_FIELD_KEYS}
    return result if any(value not in (None, "", []) for value in result.values()) else {}


def _screenshots_md(item: dict[str, Any]) -> list[str]:
    screenshots = dict(item.get("screenshots") or {})
    return [
        "- Screenshots:",
        f"  - Full page: `{screenshots.get('full_page_screenshot') or 'missing'}`",
        f"  - Viewport: `{screenshots.get('viewport_screenshot') or 'missing'}`",
        f"  - Design Guide: `{screenshots.get('design_guide_screenshot') or 'missing'}`",
        f"  - Summary cards: `{screenshots.get('summary_cards_screenshot') or 'missing'}`",
        f"  - Debug/probe: `{screenshots.get('debug_or_probe_screenshot') or 'missing'}`",
        f"  - Capture status: `{screenshots.get('screenshot_capture_status') or 'missing'}`",
        f"  - Missing crop targets: `{screenshots.get('missing_crop_targets') or []}`",
    ]


def _classify_product_verifier(diagnosis: dict[str, Any]) -> str:
    if diagnosis.get("product_bug_likely") is True:
        return "product bug"
    if diagnosis.get("verifier_bug_likely") is True:
        return "verifier-only issue"
    return "unknown/infrastructure"


def _summary_from_artifact(artifact_dir: Path) -> dict[str, Any]:
    summary_path = artifact_dir / "run_summary.json"
    if not summary_path.exists():
        return {}
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _failure_details_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    failure = _first_failure(summary)
    diagnosis = failure.get("diagnosis") if isinstance(failure.get("diagnosis"), dict) else {}
    return {
        "failure_classification": str(
            failure.get("failure_classification")
            or diagnosis.get("failure_classification")
            or summary.get("verdict")
            or ""
        ),
        "visible_contradiction": str(diagnosis.get("exact_contradiction") or failure.get("failure_message") or ""),
        "product_verifier_unknown": _classify_product_verifier(diagnosis),
        "recommended_next_fix": str(
            diagnosis.get("recommended_next_action")
            or "Inspect the replay artifact before patching product code."
        ),
        "paste_ready_report_path": str(summary.get("paste_ready_report_path") or ""),
        "screenshots": _screenshot_fields(failure) or _screenshot_fields(summary),
    }


def _run_command(name: str, command: list[str], *, timeout_sec: int, artifact_dir: Path | None = None) -> CommandResult:
    started = time.perf_counter()
    try:
        proc = subprocess.run(  # noqa: S603
            command,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        status = "PASS" if proc.returncode == 0 else "FAIL"
        result = CommandResult(
            name=name,
            command=command,
            returncode=proc.returncode,
            status=status,
            elapsed_sec=round(time.perf_counter() - started, 3),
            stdout_tail=_tail(proc.stdout or ""),
            stderr_tail=_tail(proc.stderr or ""),
            replay_artifact_path=str(artifact_dir or ""),
        )
        summary = _summary_from_artifact(artifact_dir) if artifact_dir else {}
        details = _failure_details_from_summary(summary)
        result.failure_classification = details["failure_classification"] if status != "PASS" else ""
        result.visible_contradiction = details["visible_contradiction"] if status != "PASS" else ""
        result.product_verifier_unknown = details["product_verifier_unknown"] if status != "PASS" else ""
        result.recommended_next_fix = details["recommended_next_fix"] if status != "PASS" else ""
        result.screenshots = details.get("screenshots") if status != "PASS" else {}
        result.paste_ready_report_path = details["paste_ready_report_path"]
        if status != "PASS" and not result.failure_classification:
            for payload in reversed(_json_objects((proc.stdout or "") + "\n" + (proc.stderr or ""))):
                details = _failure_details_from_summary(payload if isinstance(payload, dict) else {})
                if details["failure_classification"]:
                    result.failure_classification = details["failure_classification"]
                    result.visible_contradiction = details["visible_contradiction"]
                    result.product_verifier_unknown = details["product_verifier_unknown"]
                    result.recommended_next_fix = details["recommended_next_fix"]
                    result.screenshots = details.get("screenshots")
                    break
        return result
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            name=name,
            command=command,
            returncode=None,
            status="TIMEOUT",
            elapsed_sec=round(time.perf_counter() - started, 3),
            stdout_tail=_tail(exc.stdout if isinstance(exc.stdout, str) else ""),
            stderr_tail=_tail(exc.stderr if isinstance(exc.stderr, str) else ""),
            failure_classification="timeout",
            visible_contradiction=f"{name} timed out after {timeout_sec}s",
            replay_artifact_path=str(artifact_dir or ""),
            product_verifier_unknown="unknown/infrastructure",
            recommended_next_fix="Inspect runner readiness and replay artifact before patching product code.",
        )


def _clear_replay_port(port: int) -> None:
    if not sys.platform.startswith("win"):
        return
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$conns = Get-NetTCPConnection -LocalPort {int(port)}
$owners = $conns | Where-Object {{ $_.OwningProcess -ne 0 }} | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($ownerPid in $owners) {{ Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue }}
Start-Sleep -Seconds 2
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:
        pass


def _case_artifact_dir(timestamp: str, case_name: str) -> Path:
    return ARTIFACT_DIR / "fuzz_regression_gate" / timestamp / case_name


def _replay_command(replay_path: Path, port: int, artifact_dir: Path) -> list[str]:
    return [
        sys.executable,
        "tools/browser_live_design_guide_fuzz_verifier.py",
        "--replay-case",
        str(replay_path),
        "--port",
        str(port),
        "--artifact-dir",
        str(artifact_dir),
    ]


def _selected_replays(case_filters: list[str]) -> tuple[list[FuzzRegressionReplay], list[str]]:
    if not case_filters:
        return list(FUZZ_REGRESSION_REPLAYS), []
    selected: list[FuzzRegressionReplay] = []
    unmatched: list[str] = []
    for case_filter in case_filters:
        matches = [
            replay
            for replay in FUZZ_REGRESSION_REPLAYS
            if replay.name == case_filter or case_filter in replay.name
        ]
        if not matches:
            unmatched.append(case_filter)
            continue
        for replay in matches:
            if replay not in selected:
                selected.append(replay)
    return selected, unmatched


def _write_artifacts(
    *,
    timestamp: str,
    compile_result: CommandResult,
    replay_results: list[dict[str, Any]],
    unmatched_filters: list[str],
    filtered: bool,
) -> tuple[Path, Path, dict[str, Any]]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    failed = [item for item in replay_results if item.get("status") != "PASS"]
    missing = [item for item in replay_results if item.get("status") == "MISSING"]
    passed_count = sum(1 for item in replay_results if item.get("status") == "PASS")
    total = len(replay_results)
    gate_status = (
        "PASS"
        if compile_result.status == "PASS" and not failed and not missing and not unmatched_filters and total > 0
        else "FAIL"
    )
    payload = {
        "generated_at": timestamp,
        "status": gate_status,
        "gate": "design_guide_fuzz_regression_gate",
        "source_fuzz_run": "artifacts/verification/live_fuzz/2026-05-14T06-48-22",
        "stable_replay_dir": _repo_rel(REPLAY_DIR),
        "filtered": filtered,
        "unmatched_case_filters": unmatched_filters,
        "compile": asdict(compile_result),
        "total_replays": total,
        "passed_count": passed_count,
        "failed_count": len(failed),
        "missing_count": len(missing),
        "results": replay_results,
        "fresh_server_per_replay": True,
    }
    json_path = ARTIFACT_DIR / f"fuzz_regression_gate_{timestamp}.json"
    md_path = ARTIFACT_DIR / f"fuzz_regression_gate_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Design Guide Fuzz Regression Gate",
        "",
        f"- Generated: `{timestamp}`",
        f"- Status: **{gate_status}**",
        f"- Source fuzz run: `{payload['source_fuzz_run']}`",
        f"- Stable replay dir: `{payload['stable_replay_dir']}`",
        f"- Total replays: `{total}`",
        f"- Passed: `{passed_count}`",
        f"- Failed: `{len(failed)}`",
        f"- Missing: `{len(missing)}`",
        f"- Compile: `{compile_result.status}`",
        "",
        "## Replay Results",
        "",
        "| Order | Replay | Status | Root group | Original classification | Current failure classification | Replay artifact |",
        "|---:|---|---:|---|---|---|---|",
    ]
    for item in replay_results:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("order") or ""),
                    str(item.get("name") or ""),
                    str(item.get("status") or ""),
                    str(item.get("root_group") or ""),
                    str(item.get("original_failure_classification") or ""),
                    str(item.get("failure_classification") or ""),
                    f"`{item.get('replay_artifact_path') or ''}`",
                ]
            )
            + " |"
        )
    if unmatched_filters:
        lines.extend(["", "## Unmatched Case Filters", ""])
        lines.extend(f"- `{case_filter}`" for case_filter in unmatched_filters)
    if failed or missing:
        lines.extend(["", "## Failed Or Missing Replays", ""])
        for item in failed:
            lines.extend(
                [
                    f"### {item.get('name')}",
                    f"- Replay path: `{item.get('path')}`",
                    f"- Status: `{item.get('status')}`",
                    f"- Current failure classification: `{item.get('failure_classification') or ''}`",
                    f"- Visible contradiction: {item.get('visible_contradiction') or ''}",
                    f"- Replay artifact path: `{item.get('replay_artifact_path') or ''}`",
                    f"- Paste-ready report: `{item.get('paste_ready_report_path') or ''}`",
                    f"- Recommended next scoped fix: {item.get('recommended_next_fix') or ''}",
                    *_screenshots_md(item),
                    "",
                ]
            )
    lines.extend(
        [
            "## Gate Intent",
            "",
            "- This gate promotes the six representative failures from the 2026-05-14 real-browser fuzz investigation.",
            "- It does not replace previous-fixed-groups or the golden matrix.",
            "- Any red replay should be investigated from its fresh replay artifact before product code is changed.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    return json_path, md_path, payload


def run_gate(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    timestamp = _now_stamp()
    selected, unmatched = _selected_replays(list(args.case or []))
    compile_result = _run_command("py_compile", _compile_command(), timeout_sec=300)
    replay_results: list[dict[str, Any]] = []
    if compile_result.status == "PASS":
        for index, replay in enumerate(selected, start=1):
            replay_path = (REPO / replay.path).resolve()
            artifact_dir = _case_artifact_dir(timestamp, replay.name)
            command = _replay_command(replay_path, int(args.port), artifact_dir)
            base = {
                "order": index,
                "name": replay.name,
                "path": replay.path,
                "root_group": replay.root_group,
                "original_failure_classification": replay.original_failure_classification,
                "expected_pass_condition": replay.expected_pass_condition,
                "never_regress": replay.never_regress,
                "replay_command": " ".join(command),
                "replay_artifact_path": _repo_rel(artifact_dir),
            }
            if not replay_path.exists():
                replay_results.append(
                    {
                        **base,
                        "status": "MISSING",
                        "failure_classification": "missing_fuzz_regression_replay",
                        "visible_contradiction": "Promoted fuzz regression replay file is missing.",
                        "product_verifier_unknown": "unknown/infrastructure",
                        "recommended_next_fix": "Restore or recapture this promoted replay before accepting fuzz coverage.",
                    }
                )
                continue
            _clear_replay_port(int(args.port))
            result = _run_command(replay.name, command, timeout_sec=int(args.timeout_sec), artifact_dir=artifact_dir)
            _clear_replay_port(int(args.port))
            replay_results.append(
                {
                    **base,
                    "status": result.status,
                    "returncode": result.returncode,
                    "elapsed_sec": result.elapsed_sec,
                    "failure_classification": result.failure_classification,
                    "visible_contradiction": result.visible_contradiction,
                    "product_verifier_unknown": result.product_verifier_unknown,
                    "recommended_next_fix": result.recommended_next_fix,
                    "paste_ready_report_path": result.paste_ready_report_path,
                    "screenshots": result.screenshots or {},
                    "stdout_tail": result.stdout_tail,
                    "stderr_tail": result.stderr_tail,
                }
            )
    json_path, md_path, payload = _write_artifacts(
        timestamp=timestamp,
        compile_result=compile_result,
        replay_results=replay_results,
        unmatched_filters=unmatched,
        filtered=bool(args.case),
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "json_path": str(json_path),
                "markdown_path": str(md_path),
                "total_replays": payload["total_replays"],
                "passed_count": payload["passed_count"],
                "failed_count": payload["failed_count"],
                "missing_count": payload["missing_count"],
                "unmatched_case_filters": payload["unmatched_case_filters"],
            },
            indent=2,
        )
    )
    if compile_result.status != "PASS":
        return 2, payload
    return (0 if payload["status"] == "PASS" else 1), payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run promoted Design Guide fuzz regression replays.")
    parser.add_argument("--port", type=int, default=9301)
    parser.add_argument("--timeout-sec", type=int, default=1200)
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Optional promoted case name or unique substring. May be supplied more than once.",
    )
    args = parser.parse_args(argv)
    code, _ = run_gate(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
