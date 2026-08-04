"""Run the corrected legacy family fuzz verifier in isolated batches.

Each family receives its own Streamlit port and subprocess. A timeout is
recorded for that family and its process tree is stopped, allowing the rest of
the universal suite to continue without reusing stale browser state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
BATCH_DIR = ARTIFACT_DIR / "universal_fuzz_batches"
RUNNER = ROOT / "tools" / "verification" / "run_family_10_fuzz_audit.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.run_family_10_fuzz_audit import FAMILIES  # noqa: E402


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "UNREADABLE", "error": str(exc)}
    return value if isinstance(value, dict) else {}


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if sys.platform.startswith("win"):
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
    else:
        process.kill()


def _artifact_from_output(output: str, started_at: float) -> Path | None:
    for line in reversed(output.splitlines()):
        text = line.strip()
        if text.startswith("JSON:"):
            candidate = Path(text.split(":", 1)[1].strip())
            if candidate.is_file():
                return candidate
    candidates = sorted(
        ARTIFACT_DIR.glob("family_10_fuzz_audit_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    fresh = [path for path in candidates if path.stat().st_mtime >= started_at - 1.0]
    return fresh[-1] if fresh else None


def _run_family(
    family: str,
    *,
    index: int,
    start_port: int,
    seed: int,
    timeout_s: float,
    card_timeout_s: float,
    apply_timeout_s: float,
    stamp: str,
) -> dict[str, Any]:
    port = start_port + index
    log_path = BATCH_DIR / f"{stamp}_{family}.log"
    command = [
        sys.executable,
        str(RUNNER),
        "--family",
        family,
        "--visuals",
        "--seed",
        str(seed),
        "--port",
        str(port),
        "--live-card-timeout-s",
        str(card_timeout_s),
        "--live-apply-timeout-s",
        str(apply_timeout_s),
    ]
    started_at = time.time()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    timed_out = False
    output = ""
    returncode: int | None = None
    try:
        output, _ = process.communicate(timeout=max(30.0, timeout_s))
        returncode = process.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        partial = exc.output or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        output = str(partial)
        _kill_process_tree(process)
        tail, _ = process.communicate(timeout=20)
        output += str(tail or "")
        returncode = process.returncode

    log_path.write_text(output[-20000:] + "\n", encoding="utf-8")
    artifact_path = _artifact_from_output(output, started_at)
    payload = _read_json(artifact_path)
    result = str(payload.get("result") or payload.get("status") or "MISSING").upper()
    if timed_out:
        status = "TIMEOUT"
    elif result == "LIVE_EXECUTION_PASS":
        status = "PASS"
    elif result in {"LIVE_EXECUTION_FAIL", "STRUCTURAL_NOT_READY", "FAIL", "NOT_LOCKED_FAIL"}:
        status = "FAIL"
    else:
        status = "NOT_PROVEN"
    return {
        "family": family,
        "status": status,
        "runner_result": result,
        "returncode": returncode,
        "timed_out": timed_out,
        "runtime_seconds": round(time.time() - started_at, 2),
        "port": port,
        "command": command,
        "artifact": str(artifact_path) if artifact_path else None,
        "artifact_summary": payload.get("summary") if isinstance(payload.get("summary"), dict) else {},
        "report": next(
            (line.split(":", 1)[1].strip() for line in output.splitlines() if line.strip().startswith("Global report:")),
            None,
        ),
        "log": str(log_path),
        "stdout_tail": output[-4000:],
    }


def _markdown(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Universal Fuzz Family Batch Audit",
        "",
        f"Generated: `{snapshot['generated_at']}`",
        "",
        f"Status: **`{snapshot['status']}`**",
        "",
        "Each family was executed in its own verifier subprocess and Streamlit port. A timeout is not treated as a pass or silently omitted.",
        "",
        "| Family | Status | Runner result | Runtime seconds | Artifact |",
        "|---|---|---|---:|---|",
    ]
    for row in snapshot["families"]:
        lines.append(
            f"| `{row['family']}` | `{row['status']}` | `{row['runner_result']}` | {row['runtime_seconds']} | `{row['artifact'] or 'none'}` |"
        )
    lines.extend(["", "## Failure Summary", ""])
    for row in snapshot["families"]:
        summary = row.get("artifact_summary") or {}
        lines.append(
            f"- `{row['family']}`: live failed `{summary.get('families_live_failed', 'n/a')}`, action failures `{summary.get('button_action_failures', 'n/a')}`, publication mismatches `{summary.get('publication_mismatches', 'n/a')}`, log `{row['log']}`"
        )
    lines.extend(
        [
            "",
            "## Acceptance Rule",
            "",
            "Universal fuzz is green only when every requested family is `PASS`, every runner result is `LIVE_EXECUTION_PASS`, and no family batch timed out.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", action="append", default=[], help="Run only this family; repeat for a subset.")
    parser.add_argument("--start-port", type=int, default=9470)
    parser.add_argument("--seed", type=int, default=1007)
    parser.add_argument("--family-timeout-s", type=float, default=600.0)
    parser.add_argument("--live-card-timeout-s", type=float, default=20.0)
    parser.add_argument("--live-apply-timeout-s", type=float, default=12.0)
    args = parser.parse_args(argv)

    requested = [str(item).strip().upper() for item in args.family if str(item).strip()]
    unknown = sorted(set(requested) - set(FAMILIES))
    if unknown:
        raise SystemExit(f"Unknown family filter(s): {', '.join(unknown)}")
    families = requested or list(FAMILIES)
    stamp = _stamp()
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for index, family in enumerate(families):
        print(f"[batch] starting {family} on port {args.start_port + index}", flush=True)
        row = _run_family(
            family,
            index=index,
            start_port=args.start_port,
            seed=args.seed,
            timeout_s=args.family_timeout_s,
            card_timeout_s=args.live_card_timeout_s,
            apply_timeout_s=args.live_apply_timeout_s,
            stamp=stamp,
        )
        rows.append(row)
        print(
            f"[batch] {family} {row['status']} result={row['runner_result']} runtime={row['runtime_seconds']}s",
            flush=True,
        )

    status = "PASS" if all(row["status"] == "PASS" for row in rows) else "NOT_PROVEN"
    snapshot = {
        "schema": "design_brain.universal_fuzz_family_batches.v1",
        "generated_at": stamp,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "families_requested": families,
        "family_timeout_seconds": args.family_timeout_s,
        "seed": args.seed,
        "families": rows,
        "pass_count": sum(1 for row in rows if row["status"] == "PASS"),
        "fail_count": sum(1 for row in rows if row["status"] == "FAIL"),
        "timeout_count": sum(1 for row in rows if row["status"] == "TIMEOUT"),
        "not_proven_count": sum(1 for row in rows if row["status"] == "NOT_PROVEN"),
        "product_behaviour_changed": False,
    }
    json_path = ARTIFACT_DIR / f"design_brain_universal_fuzz_family_batches_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_universal_fuzz_family_batches_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(_markdown(snapshot), encoding="utf-8")
    print(f"Universal fuzz family batches: {status}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
