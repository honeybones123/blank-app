"""Controlled live-fuzz repair loop for the Design Guide.

This script orchestrates ``browser_live_design_guide_fuzz_verifier.py``.  It is
intentionally conservative: each cycle compiles, runs the configured fuzz
smoke, copies the verifier's paste-ready artifacts, and stops unless the run
passes or a tiny known-safe automatic repair is available.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_FUZZ_DIR = REPO_ROOT / "artifacts" / "verification" / "live_fuzz"
DEFAULT_REPAIR_ROOT = REPO_ROOT / "artifacts" / "verification" / "live_fuzz_repair"

PY_COMPILE_FILES = [
    "inputs_page.py",
    "design_guidance_engine.py",
    "design_brain/engine.py",
    "tools/browser_live_design_guide_fuzz_verifier.py",
    "tools/design_guide_live_fuzz_repair_loop.py",
    "tools/verification/previous_fixes_gate.py",
    "tools/run_design_guide_previous_fixes_gate.py",
    "tools/verification/golden_matrix_runner.py",
    "tools/run_design_guide_golden_matrix.py",
]

WATCHED_FILES = [
    "inputs_page.py",
    "design_guide_page.py",
    "design_guidance_engine.py",
    "design_brain/engine.py",
    "tools/browser_live_design_guide_fuzz_verifier.py",
    "tools/design_guide_live_fuzz_repair_loop.py",
]

AUTO_FIX_CLASSES = {
    "visible_debug_wording_leaked",
    "util_display_mismatch",
    "action_card_disabled",
    "blocker_missing",
    "old_payload_reused_after_edit",
    "stale_after_manual_edit",
}

HUMAN_DECISION_CLASSES = {
    "artifact_inconsistency",
    "browser_state_disagrees_with_visible_summary",
    "verifier_runtime_error",
    "setup_failure",
    "parser_failure",
    "timeout",
}


@dataclass
class CommandResult:
    command: list[str]
    exit_code: int
    elapsed_sec: float
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


@dataclass
class CycleRecord:
    cycle: int
    status: str = "started"
    py_compile: CommandResult | None = None
    previous_fixes_gate: CommandResult | None = None
    golden_matrix_gate: CommandResult | None = None
    fuzz: CommandResult | None = None
    replay: CommandResult | None = None
    verifier_artifact_dir: str | None = None
    failure_classification: str | None = None
    failure_case_id: str | None = None
    recipe: str | None = None
    replay_command: str | None = None
    auto_fix_attempted: bool = False
    auto_fix_applied: bool = False
    human_decision_required: bool = False
    safe_to_continue: bool = True
    changed_files: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _now_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H-%M-%S")


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, CommandResult):
        return value.__dict__
    if isinstance(value, CycleRecord):
        return {
            "cycle": value.cycle,
            "status": value.status,
            "py_compile": value.py_compile,
            "previous_fixes_gate": value.previous_fixes_gate,
            "golden_matrix_gate": value.golden_matrix_gate,
            "fuzz": value.fuzz,
            "replay": value.replay,
            "verifier_artifact_dir": value.verifier_artifact_dir,
            "failure_classification": value.failure_classification,
            "failure_case_id": value.failure_case_id,
            "recipe": value.recipe,
            "replay_command": value.replay_command,
            "auto_fix_attempted": value.auto_fix_attempted,
            "auto_fix_applied": value.auto_fix_applied,
            "human_decision_required": value.human_decision_required,
            "safe_to_continue": value.safe_to_continue,
            "changed_files": value.changed_files,
            "notes": value.notes,
        }
    return str(value)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=_json_default), encoding="utf-8")


def _append_jsonl(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, default=_json_default) + "\n")


def _hash_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_files() -> dict[str, str | None]:
    return {_rel(REPO_ROOT / name): _hash_file(REPO_ROOT / name) for name in WATCHED_FILES}


def _changed_files(before: dict[str, str | None], after: dict[str, str | None]) -> list[str]:
    names = sorted(set(before) | set(after))
    return [name for name in names if before.get(name) != after.get(name)]


def _run_command(command: list[str], *, timeout_sec: int, log_path: Path) -> CommandResult:
    started = time.time()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
        )
        result = CommandResult(
            command=command,
            exit_code=completed.returncode,
            elapsed_sec=round(time.time() - started, 3),
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
    except subprocess.TimeoutExpired as exc:
        result = CommandResult(
            command=command,
            exit_code=124,
            elapsed_sec=round(time.time() - started, 3),
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            timed_out=True,
        )
    log_path.write_text(
        "\n".join(
            [
                "$ " + " ".join(command),
                f"exit_code={result.exit_code}",
                f"elapsed_sec={result.elapsed_sec}",
                f"timed_out={result.timed_out}",
                "",
                "----- STDOUT -----",
                result.stdout,
                "",
                "----- STDERR -----",
                result.stderr,
            ]
        ),
        encoding="utf-8",
    )
    return result


def _extract_last_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    starts = [idx for idx, char in enumerate(text) if char == "{"]
    for idx in reversed(starts):
        try:
            parsed, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and ("artifact_dir" in parsed or "verdict" in parsed):
            return parsed
    return None


def _newest_live_fuzz_artifact() -> Path | None:
    if not LIVE_FUZZ_DIR.exists():
        return None
    dirs = [path for path in LIVE_FUZZ_DIR.iterdir() if path.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda path: path.stat().st_mtime)


def _artifact_from_result(result: CommandResult) -> Path | None:
    parsed = _extract_last_json_object(result.stdout)
    if parsed:
        artifact_dir = parsed.get("artifact_dir")
        if artifact_dir:
            path = Path(str(artifact_dir))
            if not path.is_absolute():
                path = REPO_ROOT / path
            if path.exists():
                return path
    return _newest_live_fuzz_artifact()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def _copy_cycle_artifacts(cycle_dir: Path, artifact_dir: Path) -> dict[str, bool]:
    copied: dict[str, bool] = {}
    mapping = {
        "paste_this_to_chatgpt.md": "paste_this_to_chatgpt.md",
        "failure_case.json": "failure_case.json",
        "failure_visible_summary.json": "failure_visible_summary.json",
        "failure_visible_design_guide.json": "failure_visible_design_guide.json",
        "failure_browser_state.json": "failure_browser_state.json",
        "run_summary.json": "run_summary.json",
        "replay_command.txt": "replay_command.txt",
        "minimal_reproduction.md": "minimal_reproduction.md",
    }
    for source_name, dest_name in mapping.items():
        copied[source_name] = _copy_if_exists(artifact_dir / source_name, cycle_dir / dest_name)
    return copied


def _replay_command_from_artifact(artifact_dir: Path, failure_case: dict[str, Any]) -> str | None:
    replay_file = artifact_dir / "replay_command.txt"
    if replay_file.exists():
        text = replay_file.read_text(encoding="utf-8").strip()
        if text:
            return text
    command = failure_case.get("replay_command")
    return str(command) if command else None


def _split_command(command: str) -> list[str]:
    # The replay commands generated by this repo are simple Python commands.
    # Avoid shell=True so the overnight loop does not execute arbitrary shell
    # syntax copied from artifacts.
    import shlex

    return shlex.split(command, posix=False)


def _diagnosis_from_failure(failure_case: dict[str, Any]) -> dict[str, Any]:
    diagnosis = failure_case.get("diagnosis")
    if isinstance(diagnosis, dict):
        return diagnosis
    return {}


def _safe_auto_fix_allowed(failure_case: dict[str, Any]) -> tuple[bool, str]:
    classification = str(failure_case.get("failure_classification") or "")
    diagnosis = _diagnosis_from_failure(failure_case)
    confidence = str(diagnosis.get("confidence") or "").lower()
    product_bug_likely = bool(diagnosis.get("product_bug_likely"))
    if classification in HUMAN_DECISION_CLASSES:
        return False, f"{classification} requires human decision."
    if classification not in AUTO_FIX_CLASSES:
        return False, f"{classification} is not in the automatic fix allow-list."
    if confidence and confidence != "high":
        return False, f"{classification} diagnosis confidence is {confidence}, not high."
    if not product_bug_likely:
        return False, f"{classification} is not marked product_bug_likely."
    return True, "automatic fix class is allowed by policy"


def _attempt_known_safe_fix(failure_case: dict[str, Any], cycle_dir: Path) -> tuple[bool, str]:
    """Apply only exact, known-safe patches.

    The loop cannot invent broad repairs.  This tiny auto-fix exists solely for
    the already-known visible debug wording leak where an executable optional
    cleanup action is shown with internal proof text.
    """

    classification = str(failure_case.get("failure_classification") or "")
    if classification != "visible_debug_wording_leaked":
        return False, "no hardcoded safe repair exists for this class"

    design_card = failure_case.get("visible_design_guide") or {}
    title = str(design_card.get("title") or "")
    text = str(design_card.get("text") or "")
    if "Closest safe option not selected" not in (title + "\n" + text):
        return False, "visible debug wording pattern was not found in failure artifact"

    # This leak historically came from presentation labels.  Patch exact string
    # literals only if they still exist; do not touch solver/ranking code.
    replacements = [
        (
            "Closest safe option not selected - target band evidence required",
            "Design is safe - cleanup available",
        ),
        (
            "Why target band was blocked: no safe executor-backed candidate was proven for this outside-target preview.",
            "This safe one-click cleanup keeps all required checks passing, but the discrete catalogue does not land inside the preferred target band.",
        ),
    ]
    touched: list[str] = []
    for rel_name in ("inputs_page.py", "design_brain/engine.py", "design_guide_page.py"):
        path = REPO_ROOT / rel_name
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        updated = original
        for old, new in replacements:
            updated = updated.replace(old, new)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            touched.append(rel_name)

    (cycle_dir / "auto_fix_notes.md").write_text(
        "\n".join(
            [
                "# Automatic Fix Notes",
                "",
                "Applied only exact user-visible wording replacements for `visible_debug_wording_leaked`.",
                "No formula, ranking, target-band, or verifier-gate code was intentionally changed.",
                "",
                "Changed files:",
                *(f"- {name}" for name in touched),
            ]
        ),
        encoding="utf-8",
    )
    if not touched:
        return False, "known visible wording strings were not present in the current source"
    return True, "applied exact visible wording replacement"


def _write_cycle_files(cycle_dir: Path, record: CycleRecord, artifact_dir: Path | None = None) -> None:
    cycle_dir.mkdir(parents=True, exist_ok=True)
    (cycle_dir / f"cycle_{record.cycle}_changed_files.txt").write_text(
        "\n".join(record.changed_files) + ("\n" if record.changed_files else ""),
        encoding="utf-8",
    )
    if artifact_dir:
        (cycle_dir / f"cycle_{record.cycle}_verifier_artifact_dir.txt").write_text(str(artifact_dir) + "\n", encoding="utf-8")
    if record.replay_command:
        (cycle_dir / f"cycle_{record.cycle}_replay_command.txt").write_text(record.replay_command + "\n", encoding="utf-8")
    status_lines = [
        f"# Cycle {record.cycle} Status",
        "",
        f"- Status: {record.status}",
        f"- Safe to continue: {record.safe_to_continue}",
        f"- Human decision required: {record.human_decision_required}",
        f"- Failure classification: {record.failure_classification or ''}",
        f"- Recipe: {record.recipe or ''}",
        f"- Artifact: {record.verifier_artifact_dir or ''}",
        f"- Auto fix attempted: {record.auto_fix_attempted}",
        f"- Auto fix applied: {record.auto_fix_applied}",
        "",
        "## Notes",
        *(f"- {note}" for note in record.notes),
    ]
    (cycle_dir / f"cycle_{record.cycle}_status.md").write_text("\n".join(status_lines) + "\n", encoding="utf-8")


def _failure_summary_markdown(failure_case: dict[str, Any], artifact_dir: Path) -> str:
    diagnosis = _diagnosis_from_failure(failure_case)
    summary = failure_case.get("visible_summary") or {}
    card = failure_case.get("visible_design_guide") or {}
    lines = [
        "# Failure Summary",
        "",
        f"- Artifact: `{artifact_dir}`",
        f"- Classification: `{failure_case.get('failure_classification', '')}`",
        f"- Case index: `{failure_case.get('case_index', '')}`",
        f"- Recipe: `{failure_case.get('recipe', '')}`",
        f"- Step: `{failure_case.get('expected_failure_step', '')}`",
        f"- Product bug likely: `{diagnosis.get('product_bug_likely', '')}`",
        f"- Verifier bug likely: `{diagnosis.get('verifier_bug_likely', '')}`",
        f"- Confidence: `{diagnosis.get('confidence', '')}`",
        "",
        "## Visible Summary",
        f"- Bending: util `{summary.get('bending', {}).get('util')}`, status `{summary.get('bending', {}).get('status')}`",
        f"- Shear: util `{summary.get('shear', {}).get('util')}`, status `{summary.get('shear', {}).get('status')}`",
        "",
        "## Visible Design Guide",
        f"- Title: {card.get('title', '')}",
        f"- Family: `{card.get('family', '')}`",
        f"- CTA visible/enabled: `{card.get('cta_visible')}` / `{card.get('cta_enabled')}`",
        f"- Text: {card.get('text', '')}",
        "",
        "## Diagnosis",
        diagnosis.get("exact_contradiction", ""),
        "",
        "## Recommended Next Action",
        diagnosis.get("recommended_next_action", ""),
    ]
    return "\n".join(lines) + "\n"


def _build_py_compile_command() -> list[str]:
    return [sys.executable, "-m", "py_compile", *PY_COMPILE_FILES]


def _build_previous_fixes_gate_command(args: argparse.Namespace) -> list[str]:
    return [sys.executable, "tools/run_design_guide_previous_fixes_gate.py", "--port", str(args.port)]


def _build_golden_matrix_gate_command(args: argparse.Namespace) -> list[str]:
    return [sys.executable, "tools/run_design_guide_golden_matrix.py", "--port", str(args.port)]


def _build_fuzz_command(args: argparse.Namespace) -> list[str]:
    mode = "--headed" if args.headed else "--headless"
    return [
        sys.executable,
        "tools/browser_live_design_guide_fuzz_verifier.py",
        "--port",
        str(args.port),
        "--seed",
        str(args.seed),
        "--max-cases",
        str(args.max_cases),
        "--session-steps",
        str(args.session_steps),
        "--mutations-per-case",
        str(args.mutations_per_case),
        mode,
    ]


def _write_final_report(
    *,
    repair_dir: Path,
    verdict: str,
    safe_to_continue: bool,
    cycles: list[CycleRecord],
    commands_run: list[CommandResult],
    latest_artifact: Path | None,
    next_prompt: str = "",
) -> None:
    changed = sorted({name for cycle in cycles for name in cycle.changed_files})
    passed_5_case = verdict == "PASS"
    lines = [
        "# Design Guide Live Fuzz Repair Loop",
        "",
        f"- Overall verdict: **{verdict}**",
        f"- Safe to continue: `{safe_to_continue}`",
        f"- Cycles attempted: `{len(cycles)}`",
        f"- Latest verifier artifact: `{latest_artifact or ''}`",
        "- Mandatory pre-fuzz gates: `previous fixed groups`, `golden matrix`",
        f"- 5-case fuzz passed: `{passed_5_case}`",
        f"- 20-case fuzz should be run next: `{passed_5_case}`",
        "",
        "## Changed Files",
        *(f"- `{name}`" for name in changed),
        *([] if changed else ["- None recorded by the repair loop."]),
        "",
        "## Cycles",
    ]
    for cycle in cycles:
        lines.extend(
            [
                f"### Cycle {cycle.cycle}",
                f"- Status: `{cycle.status}`",
                f"- Failure classification: `{cycle.failure_classification or ''}`",
                f"- Recipe: `{cycle.recipe or ''}`",
                f"- Artifact: `{cycle.verifier_artifact_dir or ''}`",
                f"- Auto fix attempted/applied: `{cycle.auto_fix_attempted}` / `{cycle.auto_fix_applied}`",
                f"- Human decision required: `{cycle.human_decision_required}`",
                f"- Safe to continue: `{cycle.safe_to_continue}`",
                f"- Replay command: `{cycle.replay_command or ''}`",
            ]
        )
        if cycle.notes:
            lines.append("- Notes: " + " | ".join(cycle.notes))
        lines.append("")
    lines.extend(["## Commands Run"])
    for result in commands_run:
        lines.append(f"- `{ ' '.join(result.command) }` -> exit `{result.exit_code}` ({result.elapsed_sec}s)")
    lines.extend(["", "## Replay Commands"])
    replay_commands = [cycle.replay_command for cycle in cycles if cycle.replay_command]
    if replay_commands:
        lines.extend(f"- `{cmd}`" for cmd in replay_commands)
    else:
        lines.append("- None.")
    if passed_5_case:
        lines.extend(
            [
                "",
                "## Recommended Next Command",
                "`python tools/browser_live_design_guide_fuzz_verifier.py --port 9302 --seed 20260505 --max-cases 20 --session-steps 4 --mutations-per-case 3 --headless`",
            ]
        )
    if next_prompt:
        lines.extend(["", "## Paste-ready Next Codex Prompt", "", next_prompt])
    (repair_dir / "final_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_json(
        repair_dir / "repair_loop_summary.json",
        {
            "verdict": verdict,
            "safe_to_continue": safe_to_continue,
            "cycles_attempted": len(cycles),
            "latest_verifier_artifact": str(latest_artifact) if latest_artifact else None,
            "five_case_fuzz_passed": passed_5_case,
            "twenty_case_fuzz_should_run_next": passed_5_case,
            "changed_files": changed,
            "cycles": cycles,
            "commands_run": commands_run,
            "final_report": str(repair_dir / "final_report.md"),
        },
    )


def _human_prompt(failure_case: dict[str, Any], artifact_dir: Path, replay_command: str | None) -> str:
    diagnosis = _diagnosis_from_failure(failure_case)
    contradiction = diagnosis.get("exact_contradiction") or failure_case.get("message") or ""
    classification = failure_case.get("failure_classification") or ""
    return "\n".join(
        [
            "Investigate this live fuzz failure before patching.",
            "",
            f"Artifact: {artifact_dir}",
            f"Replay: {replay_command or '(missing replay command)'}",
            f"Classification: {classification}",
            f"Visible contradiction: {contradiction}",
            "",
            "Keep the fix narrow. Do not change formulas, solver maths, target-band thresholds, broad ranking, or verifier gates.",
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled overnight live-fuzz repair loop for the Design Guide.")
    parser.add_argument("--port", type=int, default=9301)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--max-cases", type=int, default=5)
    parser.add_argument("--session-steps", type=int, default=3)
    parser.add_argument("--mutations-per-case", type=int, default=2)
    parser.add_argument("--max-repair-cycles", type=int, default=3)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--headed", action="store_true", help="Run browser headed.")
    mode.add_argument("--headless", action="store_true", help="Run browser headless.")
    parser.add_argument("--artifact-dir", type=Path, default=None)
    parser.add_argument("--stop-on-human-decision", dest="stop_on_human_decision", action="store_true", default=True)
    parser.add_argument("--no-stop-on-human-decision", dest="stop_on_human_decision", action="store_false")
    parser.add_argument("--dry-run-diagnosis-only", action="store_true", default=False)
    parser.add_argument("--timeout-per-command-sec", type=int, default=2400)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.headed:
        args.headless = True
    timestamp = _now_stamp()
    repair_dir = args.artifact_dir or (DEFAULT_REPAIR_ROOT / timestamp)
    repair_dir = repair_dir if repair_dir.is_absolute() else REPO_ROOT / repair_dir
    repair_dir.mkdir(parents=True, exist_ok=True)
    cycle_log_path = repair_dir / "cycle_log.jsonl"
    commands_run: list[CommandResult] = []
    cycles: list[CycleRecord] = []
    latest_artifact: Path | None = None
    repeated_failures: dict[str, int] = {}
    next_prompt = ""

    try:
        for cycle_number in range(1, int(args.max_repair_cycles) + 1):
            record = CycleRecord(cycle=cycle_number)
            cycles.append(record)
            cycle_dir = repair_dir / f"cycle_{cycle_number}"
            cycle_dir.mkdir(parents=True, exist_ok=True)
            before_hashes = _snapshot_files()

            compile_result = _run_command(
                _build_py_compile_command(),
                timeout_sec=args.timeout_per_command_sec,
                log_path=cycle_dir / f"cycle_{cycle_number}_py_compile.log",
            )
            commands_run.append(compile_result)
            record.py_compile = compile_result
            if compile_result.exit_code != 0:
                record.status = "py_compile_failed"
                record.safe_to_continue = False
                record.notes.append("py_compile failed; stopping without running fuzz.")
                _write_cycle_files(cycle_dir, record)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="PY_COMPILE_FAILED",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt="py_compile failed. Inspect the cycle log before patching further.",
                )
                return 2

            previous_gate_result = _run_command(
                _build_previous_fixes_gate_command(args),
                timeout_sec=args.timeout_per_command_sec,
                log_path=cycle_dir / f"cycle_{cycle_number}_previous_fixed_groups_gate.log",
            )
            commands_run.append(previous_gate_result)
            record.previous_fixes_gate = previous_gate_result
            if previous_gate_result.exit_code != 0:
                record.status = "previous_fixed_groups_gate_failed"
                record.safe_to_continue = False
                record.human_decision_required = True
                record.notes.append("blocked by previous-fixed-groups regression.")
                _write_cycle_files(cycle_dir, record)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="PREVIOUS_FIXED_GROUPS_REGRESSION",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt="Fix the failed previous-fixed-groups replay before running 5-case, 20-case, overnight, launch, or super verification.",
                )
                return 2

            golden_gate_result = _run_command(
                _build_golden_matrix_gate_command(args),
                timeout_sec=args.timeout_per_command_sec,
                log_path=cycle_dir / f"cycle_{cycle_number}_golden_matrix_gate.log",
            )
            commands_run.append(golden_gate_result)
            record.golden_matrix_gate = golden_gate_result
            if golden_gate_result.exit_code != 0:
                record.status = "golden_matrix_gate_failed"
                record.safe_to_continue = False
                record.human_decision_required = True
                record.notes.append("blocked by golden matrix regression.")
                _write_cycle_files(cycle_dir, record)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="GOLDEN_MATRIX_REGRESSION",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt="Fix the failed golden matrix case before running 5-case, 20-case, overnight, launch, or super verification.",
                )
                return 2

            fuzz_result = _run_command(
                _build_fuzz_command(args),
                timeout_sec=args.timeout_per_command_sec,
                log_path=cycle_dir / f"cycle_{cycle_number}_fuzz.log",
            )
            commands_run.append(fuzz_result)
            record.fuzz = fuzz_result
            latest_artifact = _artifact_from_result(fuzz_result)
            if latest_artifact:
                record.verifier_artifact_dir = str(latest_artifact)
                _copy_cycle_artifacts(cycle_dir, latest_artifact)
                _copy_if_exists(latest_artifact / "paste_this_to_chatgpt.md", cycle_dir / f"cycle_{cycle_number}_paste_this_to_chatgpt.md")
                (cycle_dir / f"cycle_{cycle_number}_verifier_artifact_dir.txt").write_text(str(latest_artifact) + "\n", encoding="utf-8")

            if fuzz_result.timed_out:
                record.status = "fuzz_timeout"
                record.safe_to_continue = False
                record.human_decision_required = True
                record.notes.append("Fuzz command timed out; stopping.")
                _write_cycle_files(cycle_dir, record, latest_artifact)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="TIMEOUT",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt="The live fuzz command timed out. Inspect command logs and app readiness before patching product code.",
                )
                return 2

            if fuzz_result.exit_code == 0:
                record.status = "fuzz_passed"
                record.notes.append("Configured live fuzz smoke exited 0.")
                record.changed_files = _changed_files(before_hashes, _snapshot_files())
                _write_cycle_files(cycle_dir, record, latest_artifact)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="PASS",
                    safe_to_continue=True,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                )
                return 0

            if fuzz_result.exit_code not in (1, 2, 3):
                record.status = "fuzz_unexpected_exit"
                record.safe_to_continue = False
                record.human_decision_required = True
                record.notes.append(f"Fuzz exited with unexpected code {fuzz_result.exit_code}.")
                _write_cycle_files(cycle_dir, record, latest_artifact)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="SETUP_OR_RUNTIME_FAILURE",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt="The verifier returned an unexpected exit code. Inspect the command log before patching app code.",
                )
                return 2

            if not latest_artifact:
                record.status = "missing_artifact"
                record.safe_to_continue = False
                record.human_decision_required = True
                record.notes.append("Could not locate verifier artifact directory.")
                _write_cycle_files(cycle_dir, record)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="MISSING_ARTIFACT",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=None,
                    next_prompt="The repair loop could not locate verifier artifacts. Fix harness/artifact discovery before continuing.",
                )
                return 2

            required = [
                "paste_this_to_chatgpt.md",
                "failure_case.json",
                "failure_visible_summary.json",
                "failure_visible_design_guide.json",
                "failure_browser_state.json",
            ]
            missing = [name for name in required if not (latest_artifact / name).exists()]
            failure_case = _load_json(latest_artifact / "failure_case.json")
            if missing:
                record.status = "missing_required_failure_artifacts"
                record.safe_to_continue = False
                record.human_decision_required = True
                record.notes.append("Missing required failure artifacts: " + ", ".join(missing))
                _write_cycle_files(cycle_dir, record, latest_artifact)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="MISSING_FAILURE_ARTIFACTS",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt="Required failure artifacts are missing. Treat this as verifier/harness setup, not product behavior.",
                )
                return 2

            record.failure_classification = str(failure_case.get("failure_classification") or "")
            record.failure_case_id = str(failure_case.get("case_index") or "")
            record.recipe = str(failure_case.get("recipe") or failure_case.get("initial_inputs", {}).get("recipe") or "")
            replay_command = _replay_command_from_artifact(latest_artifact, failure_case)
            record.replay_command = replay_command
            (cycle_dir / f"cycle_{cycle_number}_failure_summary.md").write_text(
                _failure_summary_markdown(failure_case, latest_artifact),
                encoding="utf-8",
            )

            key = f"{record.failure_classification}:{record.recipe}:{record.failure_case_id}"
            repeated_failures[key] = repeated_failures.get(key, 0) + 1
            if repeated_failures[key] > 1:
                record.status = "same_failure_repeated"
                record.safe_to_continue = False
                record.human_decision_required = True
                record.notes.append("Same failure repeated; stopping.")
                next_prompt = _human_prompt(failure_case, latest_artifact, replay_command)
                _write_cycle_files(cycle_dir, record, latest_artifact)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="REPEATED_FAILURE",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt=next_prompt,
                )
                return 1

            auto_allowed, reason = _safe_auto_fix_allowed(failure_case)
            record.notes.append(reason)
            if args.dry_run_diagnosis_only:
                auto_allowed = False
                record.notes.append("dry-run diagnosis only is enabled.")
            if not auto_allowed:
                record.status = "human_decision_required"
                record.safe_to_continue = False
                record.human_decision_required = True
                next_prompt = _human_prompt(failure_case, latest_artifact, replay_command)
                _write_cycle_files(cycle_dir, record, latest_artifact)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="HUMAN_DECISION_REQUIRED",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt=next_prompt,
                )
                return 1

            record.auto_fix_attempted = True
            applied, fix_note = _attempt_known_safe_fix(failure_case, cycle_dir)
            record.auto_fix_applied = applied
            record.notes.append(fix_note)
            if not applied:
                record.status = "no_safe_auto_patch_available"
                record.safe_to_continue = False
                record.human_decision_required = True
                next_prompt = _human_prompt(failure_case, latest_artifact, replay_command)
                _write_cycle_files(cycle_dir, record, latest_artifact)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="HUMAN_DECISION_REQUIRED",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt=next_prompt,
                )
                return 1

            compile_after_fix = _run_command(
                _build_py_compile_command(),
                timeout_sec=args.timeout_per_command_sec,
                log_path=cycle_dir / f"cycle_{cycle_number}_py_compile_after_fix.log",
            )
            commands_run.append(compile_after_fix)
            if compile_after_fix.exit_code != 0:
                record.status = "py_compile_failed_after_fix"
                record.safe_to_continue = False
                record.notes.append("py_compile failed after automatic fix.")
                record.changed_files = _changed_files(before_hashes, _snapshot_files())
                _write_cycle_files(cycle_dir, record, latest_artifact)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="PY_COMPILE_FAILED",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt="Automatic fix caused py_compile failure. Inspect the changed file and revert/repair narrowly.",
                )
                return 2

            if not replay_command:
                record.status = "missing_replay_command_after_fix"
                record.safe_to_continue = False
                record.human_decision_required = True
                record.notes.append("Cannot replay exact failure because replay command is missing.")
                record.changed_files = _changed_files(before_hashes, _snapshot_files())
                _write_cycle_files(cycle_dir, record, latest_artifact)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="MISSING_REPLAY_COMMAND",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt="Replay command missing after automatic fix. Do not continue without exact replay.",
                )
                return 2

            replay_result = _run_command(
                _split_command(replay_command),
                timeout_sec=args.timeout_per_command_sec,
                log_path=cycle_dir / f"cycle_{cycle_number}_replay_after_fix.log",
            )
            commands_run.append(replay_result)
            record.replay = replay_result
            record.changed_files = _changed_files(before_hashes, _snapshot_files())
            if replay_result.exit_code != 0:
                record.status = "replay_failed_after_fix"
                record.safe_to_continue = False
                record.human_decision_required = True
                record.notes.append("Exact replay failed after automatic fix; stopping.")
                next_prompt = _human_prompt(failure_case, latest_artifact, replay_command)
                _write_cycle_files(cycle_dir, record, latest_artifact)
                _append_jsonl(cycle_log_path, record)
                _write_final_report(
                    repair_dir=repair_dir,
                    verdict="REPLAY_FAILED",
                    safe_to_continue=False,
                    cycles=cycles,
                    commands_run=commands_run,
                    latest_artifact=latest_artifact,
                    next_prompt=next_prompt,
                )
                return 1

            record.status = "replay_passed_after_fix"
            record.notes.append("Exact replay passed; continuing to next fuzz cycle.")
            _write_cycle_files(cycle_dir, record, latest_artifact)
            _append_jsonl(cycle_log_path, record)

        _write_final_report(
            repair_dir=repair_dir,
            verdict="MAX_REPAIR_CYCLES_REACHED",
            safe_to_continue=False,
            cycles=cycles,
            commands_run=commands_run,
            latest_artifact=latest_artifact,
            next_prompt="The repair loop reached the configured repair-cycle budget. Review final_report.md before continuing.",
        )
        return 1
    except Exception as exc:
        _write_final_report(
            repair_dir=repair_dir,
            verdict="REPAIR_LOOP_RUNTIME_ERROR",
            safe_to_continue=False,
            cycles=cycles,
            commands_run=commands_run,
            latest_artifact=latest_artifact,
            next_prompt=f"The repair loop crashed with {type(exc).__name__}: {exc}. Inspect logs before patching product code.",
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
