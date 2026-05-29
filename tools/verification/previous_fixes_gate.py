"""Hard gate for previously fixed Design Guide replay regressions.

This runner is intentionally product-logic neutral. It compiles the key Python
files, then replays every fixed Design Guide case that must remain green before
broader fuzz, launch, freeze, or super verification can be meaningful.
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

from tools.verification.source_fingerprint import compute_source_fingerprint
from tools.verification.artifact_contract import (
    build_run_metadata,
    timing_budget_warnings,
    validate_replay_artifact,
)


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "verification"

COMPILE_FILES = [
    "app.py",
    "inputs_page.py",
    "design_guidance_engine.py",
    "state_and_helpers.py",
    "tools/browser_live_design_guide_fuzz_verifier.py",
    "tools/verification/helpers/browser_helpers.py",
    "tools/verification/source_fingerprint.py",
    "tools/verification/golden_matrix_runner.py",
    "tools/run_design_guide_golden_matrix.py",
]


@dataclass(frozen=True)
class FixedReplay:
    group: str
    name: str
    path: str
    original_failure_classification: str
    expected_pass_condition: str
    never_regress: str
    page_cycle_mode: str = "inputs_design_inputs"
    required: bool = True
    reason: str = ""


FIXED_REPLAYS: list[FixedReplay] = [
    FixedReplay(
        "Group 1 - stale payload / stale summary / card recompute",
        "f005_stale_payload",
        "artifacts/verification/live_fuzz/overnight_failure_exports_2026-05-08T23-25-14/f005/failure_case.json",
        "stale payload or stale summary/results",
        "Replay exits 0 and the visible card, summary, button contract, and payload are recomputed from the current state.",
        "Manual edits must not leave an old Design Guide card, stale payload, or stale summary visible.",
    ),
    FixedReplay(
        "Group 1 - stale payload / stale summary / card recompute",
        "f016_card_not_recomputed",
        "artifacts/verification/live_fuzz/overnight_failure_exports_2026-05-08T23-25-14/f016/failure_case.json",
        "card_not_recomputed_after_edit",
        "Replay exits 0 with the Design Guide publication fingerprint matching the edited inputs.",
        "A changed summary/result state must force a fresh card and button contract publication.",
    ),
    FixedReplay(
        "Group 1 - stale payload / stale summary / card recompute",
        "2026-05-10_20case_stale_recompute",
        "artifacts/verification/live_fuzz/2026-05-10T07-30-33/failure_case.json",
        "card_not_recomputed_after_edit",
        "Replay exits 0 after the 20-case stale recompute regression path.",
        "The 20-case manual edit path must not preserve a stale pre-edit card or payload.",
        reason="Added after stale recompute regression report confirmed this replay now passes.",
    ),
    FixedReplay(
        "Group 2 - over-design cleanup completeness",
        "f003_overdesign_cleanup",
        "artifacts/verification/live_fuzz/overnight_failure_exports_2026-05-08T23-25-14/f003/failure_case.json",
        "over-design cleanup completeness",
        "Replay exits 0 and low-util cleanup is either actionable or backed by exact blocker proof.",
        "Low-util bending or shear must not publish terminal guidance without cleanup action or complete blocker evidence.",
    ),
    FixedReplay(
        "Group 2 - over-design cleanup completeness",
        "2026-05-09_06-07-04_overdesign_cleanup",
        "artifacts/verification/live_fuzz/replay_2026-05-09T06-07-04/failure_case.json",
        "optimisation_outside_target_without_blocker",
        "Replay exits 0 and any below-band action/terminal state carries exact no-further-cleanup proof.",
        "A partial cleanup below 0.85 must not be accepted without exhaustive accepted-band blocker evidence.",
    ),
    FixedReplay(
        "Group 2 - over-design cleanup completeness",
        "f025_overdesign_cleanup",
        "artifacts/verification/live_fuzz/overnight_failure_exports_2026-05-08T23-25-14/f025/failure_case.json",
        "low_util_no_cleanup_or_blocker",
        "Replay exits 0 with a safe cleanup CTA or exact low-util blocker evidence.",
        "Low utilisation must not leave the user with neither a CTA nor blocker proof.",
    ),
    FixedReplay(
        "Group 2 - over-design cleanup completeness",
        "f009_overdesign_cleanup",
        "artifacts/verification/live_fuzz/overnight_failure_exports_2026-05-08T23-25-14/f009/failure_case.json",
        "overdesign_blocker_false_cleanup_candidate_exists",
        "Replay exits 0 and blocker publication loses to any safe executor-backed cleanup candidate.",
        "The app must not publish an over-design blocker while a safe improving cleanup candidate exists.",
    ),
    FixedReplay(
        "Group 2 - over-design cleanup completeness",
        "f023_overdesign_cleanup",
        "artifacts/verification/live_fuzz/overnight_failure_exports_2026-05-08T23-25-14/f023/failure_case.json",
        "green_terminal_secondary_blocker_false_candidate_exists",
        "Replay exits 0 and secondary low-util families are resolved by action or exact proof.",
        "A green terminal state must not hide an unresolved low-util family with an available cleanup candidate.",
    ),
    FixedReplay(
        "Group 2 - post-click terminalisation",
        "2026-05-09_17-44-58_post_click_terminal",
        "artifacts/verification/live_fuzz/2026-05-09T17-44-58/failure_case.json",
        "post_click_not_green_or_exact_engineering_blocker",
        "Replay exits 0 and one-click ends on green accepted or exact blocker terminal, not a second ordinary ACTION.",
        "A one-click cleanup must not merely reveal another blue action as the final post-click state.",
    ),
    FixedReplay(
        "Group 2 - false blocker candidate exists",
        "case3_overdesign_blocker_truth",
        "artifacts/verification/live_fuzz/2026-05-09T19-05-48/case3_blocker_reason_failure_case.json",
        "overdesign_blocker_false_cleanup_candidate_exists",
        "Replay exits 0 and independent-probe-equivalent cleanup candidates are published instead of blockers.",
        "Over-design blocker truth must not regress when a safe executor-backed candidate exists.",
    ),
    FixedReplay(
        "Group 2 - low-util publication evidence/action",
        "2026-05-10_08-10-58_low_util_publication",
        "artifacts/verification/live_fuzz/replay_2026-05-10T08-10-58/failure_case.json",
        "low_util_no_cleanup_or_blocker",
        "Replay exits 0 and all below-0.85 strength families have an action or complete exact blocker proof.",
        "Green efficient/no-CTA states must not be published with unresolved low-util strength families.",
        reason="Added after group2_low_util_publication_fix_report confirmed this replay now passes.",
    ),
    FixedReplay(
        "Group 2 - low-util publication evidence/action",
        "2026-05-10_08-25-31_20case_publication",
        "artifacts/verification/live_fuzz/2026-05-10T08-25-31/failure_case.json",
        "green_card_with_unresolved_family / optimisation_wrong_family / optimisation_outside_target_without_blocker",
        "Replay exits 0 with known family/type publication and exact action/blocker evidence.",
        "Unknown-family cards and below-band optimisation previews without blocker proof must not return.",
        reason="Added after group2_low_util_publication_fix_report confirmed the 20-case artifact replay now passes.",
    ),
    FixedReplay(
        "Group 3 - under-design repair evidence",
        "case2_strength_blocker_combined_repair",
        "artifacts/verification/live_fuzz/2026-05-09T16-04-21/case2_strength_blocker_failure_case.json",
        "strength_blocker_missing_combined_repair_attempts",
        "Replay exits 0 and combined active-fail blockers include structured bending, shear, and combined route proof.",
        "Combined bending/shear under-design must not be blocked without exhaustive combined repair evidence.",
    ),
    FixedReplay(
        "Layout/card contract",
        "case2_layout_contract",
        "artifacts/verification/live_fuzz/2026-05-09T19-05-48/case2_layout_failure_case.json",
        "design_guide_layout_contract_failed",
        "Replay exits 0 with compact rows populated and expanded body hidden until expansion.",
        "Collapsed Design Guide cards must not leak expanded body content or render empty current rows.",
        page_cycle_mode="full",
    ),
    FixedReplay(
        "Layout/card contract",
        "case4_layout_contract",
        "artifacts/verification/live_fuzz/2026-05-09T19-05-48/case4_layout_failure_case.json",
        "design_guide_layout_contract_failed",
        "Replay exits 0 with layout contract intact for the case4 card state.",
        "Design Guide card structure must remain single-card, compact when collapsed, and evidence-rich when expanded.",
        page_cycle_mode="full",
    ),
    FixedReplay(
        "Layout/card contract",
        "2026-05-10_expanded_content_layout",
        "artifacts/verification/live_fuzz/2026-05-10T13-50-22/failure_case.json",
        "design_guide_expanded_content_missing",
        "Replay exits 0 and blocked combined under-design details are reachable through a stable expand control.",
        "Red combined under-design blocker cards must keep a reliable expand/collapse interaction.",
        page_cycle_mode="full",
        reason="Added after expanded_content_layout_contract_fix_report confirmed this replay now passes.",
    ),
    FixedReplay(
        "Design Guide visible-output hard invariants",
        "failed_underdesign_unlocked_must_repair",
        "artifacts/verification/focused_replays/2026-05-17/failed_underdesign_unlocked_must_repair.json",
        "failed_design_terminal_without_locked_constraints / failed_shear_with_no_links_terminal / design_guide_debug_text_leaked_to_user",
        "Replay exits 0 because failed unlocked designs publish an executor-backed repair action or exact lock/constraint blocker.",
        "A failed unlocked design cannot terminal-block, frame missing shear links as acceptable, or expose raw solver/debug text.",
        reason="Focused regression added after manual impossible failed/blocked Design Guide state.",
    ),
    FixedReplay(
        "Design Guide visible-output hard invariants",
        "card_button_colour_mismatch",
        "artifacts/verification/focused_replays/2026-05-17/card_button_colour_mismatch.json",
        "design_guide_card_button_colour_mismatch",
        "Replay exits 0 and any visible Design Guide CTA uses the same semantic state as the visible card.",
        "Design Guide CTA colour must match the visible card semantic state.",
        reason="Focused regression for card/button visual state mismatch.",
    ),
    FixedReplay(
        "Design Guide visible-output hard invariants",
        "active_fail_dominates_cleanup_evidence",
        "artifacts/verification/live_fuzz/2026-05-21T21-35-41/failure_case.json",
        "ladder_stop_calc_box_evidence_missing",
        "Replay exits 0 because active-fail repair/blocker evidence has priority over secondary low-util cleanup evidence.",
        "A visible active-fail repair-blocked card must not be forced to prove cleanup-ladder evidence only because another family is low-util.",
        reason="Focused regression for sequence-only active-fail plus low-util evidence priority.",
    ),
]

UNCAPTURED_BEHAVIOUR_NOTES = [
    "No separate stable replay was found for every named Stage 5 behaviour beyond the fixed artifacts listed here.",
    "Capture any newly confirmed behaviour as a replay JSON before treating it as protected by this gate.",
]
SCREENSHOT_FIELD_KEYS = (
    "full_page_screenshot",
    "viewport_screenshot",
    "design_guide_screenshot",
    "summary_cards_screenshot",
    "debug_or_probe_screenshot",
    "screenshot_capture_status",
    "missing_crop_targets",
)


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
    product_verifier_unknown: str = ""
    visible_contradiction: str = ""
    recommended_next_fix: str = ""
    screenshots: dict[str, Any] | None = None


def _now_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H-%M-%S")


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _tail(text: str, *, lines: int = 160) -> str:
    return "\n".join(str(text or "").splitlines()[-lines:])


def _latest_artifact_for_replay(replay_path: Path, *, started_after: float | None = None) -> Path | None:
    root = REPO / "artifacts" / "verification" / "live_fuzz"
    if not root.exists():
        return None
    expected = str(replay_path).replace("/", "\\")
    candidates: list[tuple[float, Path]] = []
    for run_summary in root.glob("replay_*/run_summary.json"):
        try:
            if started_after is not None and run_summary.stat().st_mtime < started_after - 5:
                continue
            payload = json.loads(run_summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        replay_source = str(payload.get("replay_source") or "").replace("/", "\\")
        if replay_source and (replay_source == expected or replay_source.endswith(expected) or expected.endswith(replay_source)):
            candidates.append((run_summary.stat().st_mtime, run_summary.parent))
    if not candidates:
        return None
    return sorted(candidates, reverse=True)[0][1]


def _run_command(name: str, command: list[str], *, timeout_sec: int) -> CommandResult:
    started = time.perf_counter()
    started_wall = time.time()
    try:
        proc = subprocess.run(  # noqa: S603
            command,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        result = CommandResult(
            name=name,
            command=command,
            returncode=proc.returncode,
            status="PASS" if proc.returncode == 0 else "FAIL",
            elapsed_sec=round(time.perf_counter() - started, 3),
            stdout_tail=_tail(proc.stdout or ""),
            stderr_tail=_tail(proc.stderr or ""),
        )
        if len(command) >= 4 and "browser_live_design_guide_fuzz_verifier.py" in " ".join(command):
            artifact = _latest_artifact_for_replay(Path(command[3]), started_after=started_wall)
            if artifact is not None:
                summary_path = artifact / "run_summary.json"
                try:
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                    result.screenshots = result.screenshots or {}
                    result.screenshots["artifact_dir"] = str(artifact)
                    result.screenshots["artifact_contract"] = validate_replay_artifact(artifact)
                    result.screenshots["timing_budget_warnings"] = timing_budget_warnings(
                        summary.get("stage_timing_summary"),
                        artifact_dir=artifact,
                    )
                    result.screenshots["stage_timing_summary"] = summary.get("stage_timing_summary") or {}
                except Exception:
                    pass
        if proc.returncode != 0:
            _attach_failure_details(result, (proc.stdout or "") + "\n" + (proc.stderr or ""))
        return result
    except subprocess.TimeoutExpired as exc:
        result = CommandResult(
            name=name,
            command=command,
            returncode=None,
            status="TIMEOUT",
            elapsed_sec=round(time.perf_counter() - started, 3),
            stdout_tail=_tail(exc.stdout or "" if isinstance(exc.stdout, str) else ""),
            stderr_tail=_tail(exc.stderr or "" if isinstance(exc.stderr, str) else ""),
            failure_classification="timeout",
            product_verifier_unknown="unknown/infrastructure",
            visible_contradiction=f"{name} timed out after {timeout_sec}s",
            recommended_next_fix="Inspect runner readiness and replay artifact before patching product code.",
        )
        return result


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


def _classify_product_verifier(diagnosis: dict[str, Any], failure: dict[str, Any]) -> str:
    if diagnosis.get("product_bug_likely") is True:
        return "product bug"
    if diagnosis.get("verifier_bug_likely") is True:
        return "verifier-only issue"
    value = failure.get("product_verifier_unknown") or failure.get("classification_kind")
    return str(value or "unknown/infrastructure")


def _attach_failure_details(result: CommandResult, output: str) -> None:
    for payload in reversed(_json_objects(output)):
        failure = _first_failure(payload)
        if not failure:
            continue
        diagnosis = failure.get("diagnosis") if isinstance(failure.get("diagnosis"), dict) else {}
        result.failure_classification = str(
            failure.get("failure_classification")
            or failure.get("classification")
            or diagnosis.get("classification")
            or payload.get("verdict")
            or "replay_failed"
        )
        result.product_verifier_unknown = _classify_product_verifier(diagnosis, failure)
        result.visible_contradiction = str(
            diagnosis.get("exact_contradiction")
            or failure.get("failure_message")
            or failure.get("message")
            or payload.get("error")
            or "Fixed replay failed without a parsed contradiction."
        )
        result.recommended_next_fix = (
            "Fix this previous-fixed-groups regression before running 5-case, 20-case, overnight, launch, or super verification."
        )
        result.screenshots = _screenshot_fields(failure) or _screenshot_fields(payload)
        return
    result.failure_classification = result.failure_classification or "runner_failed"
    result.product_verifier_unknown = result.product_verifier_unknown or "unknown/infrastructure"
    result.visible_contradiction = result.visible_contradiction or "Runner exited non-zero; no structured failure payload parsed."
    result.recommended_next_fix = (
        "Inspect the replay stdout/stderr, then fix the previous-fixed-groups regression before broader verification."
    )


def _compile_command() -> list[str]:
    return [sys.executable, "-m", "py_compile", *COMPILE_FILES]


def _replay_command(replay_path: Path, port: int, *, page_cycle_mode: str = "full") -> list[str]:
    return [
        sys.executable,
        "tools/browser_live_design_guide_fuzz_verifier.py",
        "--replay-case",
        str(replay_path),
        "--port",
        str(port),
        "--page-cycle-mode",
        str(page_cycle_mode or "full"),
    ]


def _clear_replay_port(port: int) -> None:
    """Best-effort isolation so one fixed replay cannot leak Streamlit state into the next."""
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


def _write_artifacts(
    *,
    timestamp: str,
    compile_result: CommandResult,
    replay_results: list[dict[str, Any]],
    missing_results: list[dict[str, Any]],
    port: int,
) -> tuple[Path, Path, dict[str, Any]]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    executed = [item for item in replay_results if item.get("status") not in {"MISSING", "SKIPPED"}]
    failed = [item for item in replay_results if item.get("status") not in {"PASS", "SKIPPED"}]
    skipped_missing = list(missing_results)
    passed_count = sum(1 for item in replay_results if item.get("status") == "PASS")
    total_fixed_replays = len(FIXED_REPLAYS)
    pass_rate = round((passed_count / total_fixed_replays) * 100.0, 2) if total_fixed_replays else 0.0
    gate_status = "PASS" if compile_result.status == "PASS" and not failed and not skipped_missing else "FAIL"
    source_fingerprint = compute_source_fingerprint(repo=REPO)
    gate_timing_warnings = []
    for item in replay_results:
        screenshots = dict(item.get("screenshots") or {})
        for warning in list(screenshots.get("timing_budget_warnings") or []):
            gate_timing_warnings.append({**warning, "replay": item.get("name"), "path": item.get("path")})
    metadata = build_run_metadata(
        artifact_dir=ARTIFACT_DIR,
        command_line=f"python tools/run_design_guide_previous_fixes_gate.py --port {int(port)}",
        port=int(port),
        started_at=timestamp,
        finished_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )
    payload = {
        "generated_at": timestamp,
        "finished_at": metadata.get("finished_at"),
        "status": gate_status,
        "blocked_by_previous_fixed_groups_regression": gate_status != "PASS",
        "source_fingerprint": source_fingerprint,
        "correctness_fingerprint": source_fingerprint.get("correctness_fingerprint"),
        "diagnostic_fingerprint": source_fingerprint.get("diagnostic_fingerprint"),
        "verifier_runtime_fingerprint": source_fingerprint.get("verifier_runtime_fingerprint"),
        "verifier_metadata": metadata,
        "command_line": f"python tools/run_design_guide_previous_fixes_gate.py --port {int(port)}",
        "python_version": sys.version.replace("\n", " "),
        "environment": metadata.get("environment"),
        "invalidation_reason": None,
        "full_gate_required": True,
        "compile": asdict(compile_result),
        "total_fixed_replays": total_fixed_replays,
        "executed_replays": len(executed),
        "passed_count": passed_count,
        "failed_count": len(failed),
        "skipped_missing_count": len(skipped_missing),
        "pass_rate_percent": pass_rate,
        "results": replay_results,
        "missing_or_skipped": skipped_missing,
        "uncaptured_behaviour_notes": UNCAPTURED_BEHAVIOUR_NOTES,
        "fresh_server_per_replay": True,
        "timing_budget_warning_thresholds_ms": {
            "replay_apply_ms": 180000,
            "post_apply_settle_ms": 120000,
            "page_cycle_check_ms": 120000,
            "design_guide_build_ms": 60000,
        },
        "timing_budget_warnings": gate_timing_warnings,
    }
    json_path = ARTIFACT_DIR / f"previous_fixes_gate_{timestamp}.json"
    md_path = ARTIFACT_DIR / f"previous_fixes_gate_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Previous Fixed Groups Gate",
        "",
        f"- Generated: `{timestamp}`",
        f"- Status: **{gate_status}**",
        f"- Total fixed replays: `{total_fixed_replays}`",
        f"- Passed: `{passed_count}`",
        f"- Failed: `{len(failed)}`",
        f"- Skipped/missing: `{len(skipped_missing)}`",
        f"- Pass rate: `{pass_rate}%`",
        f"- Compile: `{compile_result.status}`",
        f"- Timing warnings: `{len(gate_timing_warnings)}`",
        "",
    ]
    if gate_status != "PASS":
        lines.append("**blocked by previous-fixed-groups regression.**")
        lines.append("")
    lines.extend(
        [
            "## Replay Results",
            "",
            "| Group | Replay | Status | Original classification | Failure classification | Never regress | Replay command |",
            "|---|---|---:|---|---|---|---|",
        ]
    )
    for item in replay_results:
        screenshots = dict(item.get("screenshots") or {})
        stage_timing = screenshots.get("stage_timing_summary") or {}
        timing_note = ", ".join(
            f"{key}={stage_timing.get(key)}"
            for key in ("replay_apply_ms", "post_apply_settle_ms", "page_cycle_check_ms")
            if key in stage_timing
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("group") or ""),
                    str(item.get("path") or ""),
                    str(item.get("status") or ""),
                    str(item.get("original_failure_classification") or ""),
                    str(item.get("failure_classification") or ""),
                    str(item.get("never_regress") or ""),
                    f"`{item.get('replay_command') or ''}`" + (f"<br>{timing_note}" if timing_note else ""),
                ]
            )
            + " |"
        )
    if gate_timing_warnings:
        lines.extend(["", "## Non-Failing Timing Warnings", ""])
        for warning in gate_timing_warnings:
            lines.append(
                f"- `{warning.get('replay')}` `{warning.get('phase')}`: "
                f"{warning.get('observed_ms')} ms > {warning.get('threshold_ms')} ms"
            )
    if failed:
        lines.extend(["", "## Failed Fixed Replays", ""])
        for item in failed:
            lines.extend(
                [
                    f"### {item.get('group')} / {item.get('name')}",
                    f"- Failed replay path: `{item.get('path')}`",
                    f"- Replay command: `{item.get('replay_command')}`",
                    f"- Failure classification: `{item.get('failure_classification') or ''}`",
                    f"- Product/verifier/unknown: `{item.get('product_verifier_unknown') or ''}`",
                    f"- Visible contradiction: {item.get('visible_contradiction') or ''}",
                    f"- Recommended next scoped fix: {item.get('recommended_next_fix') or ''}",
                    *_screenshots_md(item),
                    "",
                ]
            )
    if skipped_missing:
        lines.extend(["", "## Missing Or Skipped Replay Files", ""])
        for item in skipped_missing:
            lines.append(f"- `{item.get('path')}` ({item.get('group')}; required={item.get('required')})")
    lines.extend(["", "## Uncaptured Stable Behaviours", ""])
    lines.extend(f"- {note}" for note in UNCAPTURED_BEHAVIOUR_NOTES)
    lines.extend(
        [
            "",
            "## Mandatory Workflow",
            "",
            "0. Compile",
            "1. Exact replay for the current fix",
            "2. Previous fixed groups gate",
            "3. Golden matrix gate",
            "4. 5-case smoke fuzz",
            "5. 20-case focused fuzz",
            "6. Overnight fuzz only if 20-case passes",
            "",
            "5-case and 20-case fuzz do not replace this gate. Fuzz does not replace the golden matrix gate.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    return json_path, md_path, payload


def run_gate(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    timestamp = _now_stamp()
    compile_result = _run_command("py_compile", _compile_command(), timeout_sec=300)
    replay_results: list[dict[str, Any]] = []
    missing_results: list[dict[str, Any]] = []
    if compile_result.status == "PASS":
        for replay in FIXED_REPLAYS:
            replay_path = (REPO / replay.path).resolve()
            replay_command = _replay_command(replay_path, int(args.port), page_cycle_mode=replay.page_cycle_mode)
            base = {
                "group": replay.group,
                "name": replay.name,
                "path": replay.path,
                "page_cycle_mode": replay.page_cycle_mode,
                "page_cycle_reduced": replay.page_cycle_mode != "full",
                "required": replay.required,
                "reason": replay.reason,
                "original_failure_classification": replay.original_failure_classification,
                "expected_pass_condition": replay.expected_pass_condition,
                "never_regress": replay.never_regress,
                "replay_command": " ".join(replay_command),
            }
            if not replay_path.exists():
                item = {
                    **base,
                    "status": "MISSING",
                    "failure_classification": "missing_fixed_replay",
                    "product_verifier_unknown": "unknown/infrastructure",
                    "visible_contradiction": "Fixed replay file is missing, so the regression cannot be proven fixed.",
                    "recommended_next_fix": "Restore or recapture this fixed replay before wider verification.",
                }
                replay_results.append(item)
                if replay.required:
                    missing_results.append(item)
                continue
            _clear_replay_port(int(args.port))
            result = _run_command(replay.name, replay_command, timeout_sec=int(args.timeout_sec))
            _clear_replay_port(int(args.port))
            replay_results.append(
                {
                    **base,
                    "status": result.status,
                    "returncode": result.returncode,
                    "elapsed_sec": result.elapsed_sec,
                    "failure_classification": result.failure_classification,
                    "product_verifier_unknown": result.product_verifier_unknown,
                    "visible_contradiction": result.visible_contradiction,
                    "recommended_next_fix": result.recommended_next_fix,
                    "screenshots": result.screenshots or {},
                    "stdout_tail": result.stdout_tail,
                    "stderr_tail": result.stderr_tail,
                }
            )
    json_path, md_path, payload = _write_artifacts(
        timestamp=timestamp,
        compile_result=compile_result,
        replay_results=replay_results,
        missing_results=missing_results,
        port=int(args.port),
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "blocked_by_previous_fixed_groups_regression": payload[
                    "blocked_by_previous_fixed_groups_regression"
                ],
                "json_path": str(json_path),
                "markdown_path": str(md_path),
                "passed_count": payload["passed_count"],
                "failed_count": payload["failed_count"],
                "skipped_missing_count": payload["skipped_missing_count"],
            },
            indent=2,
        )
    )
    if compile_result.status != "PASS":
        return 2, payload
    return (0 if payload["status"] == "PASS" else 1), payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the previous fixed Design Guide replay gate.")
    parser.add_argument("--port", type=int, default=9301)
    parser.add_argument("--timeout-sec", type=int, default=1200)
    args = parser.parse_args(argv)
    code, _ = run_gate(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
