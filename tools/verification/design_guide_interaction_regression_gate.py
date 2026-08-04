"""Focused Design Guide interaction regression gate.

This gate runs permanent browser replay assets for user-visible Design Guide
interaction failures, then applies reusable post-run assertions over the saved
browser evidence. It does not change product runtime behaviour.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.verification.helpers.design_guide_interaction_assertions import (
    AssertionResult,
    run_core_design_guide_assertions,
)


ARTIFACT_ROOT = REPO / "artifacts" / "verification"

COMPILE_FILES = [
    "app.py",
    "inputs_page.py",
    "design_guide_page.py",
    "tools/browser_live_design_guide_fuzz_verifier.py",
    "tools/verification/helpers/design_guide_interaction_assertions.py",
    "tools/verification/design_guide_interaction_regression_gate.py",
]


@dataclass(frozen=True)
class InteractionRegression:
    name: str
    scenario: str
    path: str
    page_cycle_mode: str
    protects: str


REGRESSIONS: tuple[InteractionRegression, ...] = (
    InteractionRegression(
        name="design_guide_duplicate_cta_regression",
        scenario="A/E - bending underdesign plus repeated action stability",
        path="artifacts/verification/live_fuzz/2026-05-31T23-35-44/extracted_failures/case_013_design_guide_collapsed_body_leaking.json",
        page_cycle_mode="inputs_design_inputs",
        protects="No duplicate one-click CTA, no collapsed body leak, no shell-only final state.",
    ),
    InteractionRegression(
        name="shear_underdesign_must_resolve_regression",
        scenario="B - shear/active underdesign must resolve to repair or explicit no-repair evidence",
        path="artifacts/verification/focused_replays/2026-05-17/failed_underdesign_unlocked_must_repair.json",
        page_cycle_mode="inputs_design_inputs",
        protects="Unlocked underdesign cannot freeze, blank, pass, or terminal-block without proof.",
    ),
    InteractionRegression(
        name="stale_blocked_cleanup_regression",
        scenario="C - overdesign cleanup must outrank stale disabled blocker when safe cleanup exists",
        path="artifacts/verification/live_fuzz/2026-06-02T10-15-16/failure_case.json",
        page_cycle_mode="inputs_design_inputs",
        protects="Passing overdesign cannot publish stale BLOCKED cleanup when safe executable cleanup exists.",
    ),
    InteractionRegression(
        name="geometry_change_reo_refresh_regression",
        scenario="D - geometry edit must not leave stale Design Guide or reinforcement evidence",
        path="artifacts/verification/live_fuzz/2026-05-31T23-35-44/extracted_failures/case_047_card_not_recomputed_after_edit.json",
        page_cycle_mode="inputs_design_inputs",
        protects="Geometry/state edits must recompute card, CTA, payload, summary, and diagram/reo evidence.",
    ),
)


def _run(command: list[str], timeout_sec: int) -> tuple[int, float, str, str]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=REPO,
        text=True,
        capture_output=True,
        timeout=timeout_sec,
    )
    elapsed = time.perf_counter() - started
    return completed.returncode, elapsed, completed.stdout, completed.stderr


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_final_diagnostics(summary: dict[str, Any]) -> dict[str, Any]:
    case = summary.get("case") if isinstance(summary.get("case"), dict) else {}
    timeline = list(case.get("timeline") or summary.get("timeline") or [])
    final = dict(timeline[-1] if timeline else {})
    card = dict(final.get("visible_design_guide") or {})
    layout = dict(final.get("design_guide_layout_contract") or {})
    state = dict(final.get("browser_state") or {})
    button = dict(card.get("button_contract") or {})
    screenshots = {
        "full_page": case.get("pass_full_page_screenshot"),
        "viewport": case.get("pass_viewport_screenshot"),
        "design_guide": case.get("pass_design_guide_screenshot"),
        "summary_cards": case.get("pass_summary_cards_screenshot"),
    }
    return {
        "visible_text": card.get("text"),
        "visible_title": card.get("title"),
        "visible_status": card.get("status_label"),
        "visible_card_count": card.get("visible_card_count"),
        "cta_label": card.get("cta_label"),
        "cta_visible": card.get("cta_visible"),
        "cta_enabled": card.get("cta_enabled"),
        "button_contract": button,
        "layout_contract": layout,
        "active_failing_families": final.get("active_failing_families"),
        "low_util_families": final.get("low_util_families"),
        "test_hook_counts": (list(card.get("cards") or [{}])[0] or {}).get("test_hook_counts"),
        "exact_blockers_by_family": card.get("exact_blockers_by_family")
        or dict(state.get("guidance_compute_probe") or {}).get("exact_blockers_by_family"),
        "post_click_final_state": final.get("post_click_final_state"),
        "screenshots": screenshots,
    }


def _write_reports(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path = path.with_suffix(".md")
    lines = [
        "# Design Guide Interaction Regression Gate",
        "",
        f"- Status: **{report['status']}**",
        f"- Pass count: {report['pass_count']}/{report['total_count']}",
        f"- Started: {report['started_at']}",
        f"- Finished: {report['finished_at']}",
        "",
        "## Results",
        "",
    ]
    for result in report["results"]:
        lines.extend(
            [
                f"### {result['name']}",
                "",
                f"- Status: {result['status']}",
                f"- Scenario: {result['scenario']}",
                f"- Replay: `{result['path']}`",
                f"- Artifact: `{result.get('artifact_dir')}`",
                f"- Verifier exit code: {result['verifier_exit_code']}",
                f"- Assertion failures: {len(result['assertion_failures'])}",
                "",
            ]
        )
        if result["assertion_failures"]:
            for failure in result["assertion_failures"]:
                lines.append(f"  - `{failure['name']}`: `{failure['details']}`")
            lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _compile(timeout_sec: int) -> dict[str, Any]:
    command = [sys.executable, "-m", "py_compile", *COMPILE_FILES]
    try:
        code, elapsed, stdout, stderr = _run(command, timeout_sec)
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "exit_code": None,
            "elapsed_sec": timeout_sec,
            "timed_out": True,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    return {
        "command": command,
        "exit_code": code,
        "elapsed_sec": round(elapsed, 3),
        "timed_out": False,
        "stdout": stdout,
        "stderr": stderr,
    }


def _run_regression(regression: InteractionRegression, args: argparse.Namespace, run_dir: Path) -> dict[str, Any]:
    replay_path = REPO / regression.path
    artifact_dir = run_dir / regression.name
    command = [
        sys.executable,
        "tools/browser_live_design_guide_fuzz_verifier.py",
        "--replay-case",
        str(replay_path),
        "--port",
        str(args.port),
        "--page-cycle-mode",
        regression.page_cycle_mode,
        "--artifact-dir",
        str(artifact_dir),
    ]
    result: dict[str, Any] = {
        **asdict(regression),
        "command": command,
        "artifact_dir": str(artifact_dir),
        "verifier_exit_code": None,
        "elapsed_sec": None,
        "timed_out": False,
        "assertions": [],
        "assertion_failures": [],
        "diagnostics": {},
        "status": "FAIL",
        "stdout_tail": "",
        "stderr_tail": "",
    }
    if not replay_path.exists():
        result["assertion_failures"].append(
            {"name": "replay_asset_exists", "passed": False, "details": {"path": str(replay_path)}}
        )
        return result
    try:
        code, elapsed, stdout, stderr = _run(command, args.replay_timeout_sec)
    except subprocess.TimeoutExpired as exc:
        result.update(
            {
                "timed_out": True,
                "elapsed_sec": args.replay_timeout_sec,
                "stdout_tail": str(exc.stdout or "")[-4000:],
                "stderr_tail": str(exc.stderr or "")[-4000:],
            }
        )
        return result
    result.update(
        {
            "verifier_exit_code": code,
            "elapsed_sec": round(elapsed, 3),
            "stdout_tail": stdout[-4000:],
            "stderr_tail": stderr[-4000:],
        }
    )
    summary_path = artifact_dir / "run_summary.json"
    if not summary_path.exists():
        result["assertion_failures"].append(
            {"name": "run_summary_exists", "passed": False, "details": {"path": str(summary_path)}}
        )
        return result
    summary = _load_json(summary_path)
    result["diagnostics"] = _extract_final_diagnostics(summary)
    assertion_results: list[AssertionResult] = run_core_design_guide_assertions(summary)
    result["assertions"] = [asdict(assertion) for assertion in assertion_results]
    result["assertion_failures"] = [asdict(assertion) for assertion in assertion_results if not assertion.passed]
    if code != 0:
        result["assertion_failures"].append(
            {"name": "browser_replay_exit_code", "passed": False, "details": {"exit_code": code}}
        )
    result["status"] = "PASS" if not result["assertion_failures"] else "FAIL"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9301)
    parser.add_argument("--replay-timeout-sec", type=int, default=900)
    parser.add_argument("--compile-timeout-sec", type=int, default=120)
    parser.add_argument("--skip-compile", action="store_true", default=False)
    args = parser.parse_args(argv)

    started_at = time.strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = ARTIFACT_ROOT / "design_guide_interaction_regression" / started_at
    compile_result = {"skipped": True}
    results: list[dict[str, Any]] = []
    if not args.skip_compile:
        compile_result = _compile(args.compile_timeout_sec)
    if compile_result.get("exit_code") not in (0, None) or compile_result.get("timed_out"):
        status = "FAIL"
    else:
        for regression in REGRESSIONS:
            results.append(_run_regression(regression, args, run_dir))
        status = "PASS" if all(result["status"] == "PASS" for result in results) else "FAIL"

    finished_at = time.strftime("%Y-%m-%dT%H-%M-%S")
    report = {
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "compile": compile_result,
        "total_count": len(REGRESSIONS),
        "pass_count": sum(1 for result in results if result.get("status") == "PASS"),
        "fail_count": sum(1 for result in results if result.get("status") != "PASS"),
        "results": results,
    }
    report_path = ARTIFACT_ROOT / f"design_guide_interaction_regression_{started_at}.json"
    _write_reports(report, report_path)
    print(f"Design Guide interaction regression gate: {status}")
    print(f"Report: {report_path}")
    print(f"Markdown: {report_path.with_suffix('.md')}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
