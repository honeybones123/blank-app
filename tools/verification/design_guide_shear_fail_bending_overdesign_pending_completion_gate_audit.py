"""Audit post-click pending-shell completion for SHEAR_FAIL_BENDING_OVERDESIGN.

Proof-only. This verifier targets the case where Apply changes the engineering
outputs but the final Design Guide card never replaces the pending shell.

It enables existing server-side trace hooks, performs the same browser/live
post-click replay as the readiness snapshot, then classifies the completion gate:

* final panel did not re-enter after Apply,
* settle gate returned a waiting shell,
* guidance compute did not complete,
* post-processing/render handoff did not complete,
* final render completed but the DOM/card readiness marker was missing, or
* trace evidence was insufficient.

It does not change family runtimes, contracts, CTA rendering, publication
semantics, apply routing, visible wording, or product behaviour.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification import design_guide_product_path_gate as product_gate  # noqa: E402
from tools.verification.design_guide_partial_family_browser_apply_noop_replay import (  # noqa: E402
    ReplayAttempt,
    _click_first_enabled_action,
    _enabled_action_buttons,
    _family_matches,
    _family_selection,
    _goto_recipe,
    _output_fingerprint,
    _selected_family_ids,
    _stable_hash,
)
from tools.verification.design_guide_shear_fail_bending_overdesign_post_click_card_readiness_snapshot import (  # noqa: E402
    _classify as _classify_readiness,
    _compact_text,
    _sample,
)
from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PERF_DIR = ROOT / "artifacts" / "performance"

FAMILY_ID = "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
ATTEMPT = ReplayAttempt(
    name="shear_fail_bending_overdesign_pending_completion_gate",
    family_id=FAMILY_ID,
    recipe="B_shear_under_only",
)


def _trace_files() -> dict[str, float]:
    if not PERF_DIR.exists():
        return {}
    return {
        str(path): path.stat().st_mtime
        for path in PERF_DIR.glob("inputs_pre_widget_trace_*.jsonl")
        if path.is_file()
    }


def _created_or_modified_trace_files(before: dict[str, float], *, started_at: float) -> list[Path]:
    files: list[Path] = []
    for raw, mtime in _trace_files().items():
        previous = before.get(raw)
        if previous is None or mtime > previous or mtime >= started_at - 1.0:
            files.append(Path(raw))
    return sorted(files, key=lambda path: path.stat().st_mtime)


def _parse_trace_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        try:
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    row = dict(json.loads(line))
                except json.JSONDecodeError:
                    row = {"trace_parse_error": "json_decode_error", "line_no": line_no, "raw": line[:400]}
                row.setdefault("trace_file", str(path))
                row.setdefault("line_no", line_no)
                rows.append(row)
        except OSError as exc:
            rows.append({"trace_parse_error": f"{type(exc).__name__}: {exc}", "trace_file": str(path)})
    return rows


def _row_time(row: dict[str, Any]) -> datetime | None:
    raw = str(row.get("timestamp") or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _filter_after(rows: list[dict[str, Any]], *, after: datetime | None) -> list[dict[str, Any]]:
    if after is None:
        return rows
    filtered: list[dict[str, Any]] = []
    for row in rows:
        row_time = _row_time(row)
        if row_time is not None and row_time >= after:
            filtered.append(row)
    return filtered


def _stage_name(block: str) -> str:
    prefix = "_render_fast_design_guidance_panel.stage."
    return block[len(prefix) :] if block.startswith(prefix) else block


def _trace_summary(rows: list[dict[str, Any]], *, click_wall_time: datetime | None) -> dict[str, Any]:
    recipe_rows = [
        row
        for row in rows
        if not row.get("recipe") or str(row.get("recipe")) == ATTEMPT.recipe
    ]
    post_click_rows = _filter_after(recipe_rows, after=click_wall_time)
    stage_rows = [
        row
        for row in post_click_rows
        if str(row.get("block") or "").startswith("_render_fast_design_guidance_panel.stage.")
    ]
    blocks = [str(row.get("block") or "") for row in post_click_rows]
    stages = [_stage_name(str(row.get("block") or "")) for row in stage_rows]
    final_render_rows = [
        row
        for row in post_click_rows
        if str(row.get("block") or "") == "render_inputs.render_fast_design_guidance_panel"
    ]
    compute_rows = [
        row
        for row in post_click_rows
        if str(row.get("block") or "") == "_compute_design_guidance_items.for_design_guide"
    ]
    enter_rows = [
        row
        for row in post_click_rows
        if str(row.get("block") or "") == "_render_fast_design_guidance_panel.enter"
    ]

    block_counts: dict[str, int] = {}
    for block in blocks:
        block_counts[block] = block_counts.get(block, 0) + 1

    last_rows = [
        {
            "timestamp": row.get("timestamp"),
            "block": row.get("block"),
            "elapsed_ms": row.get("elapsed_ms"),
            "duration_ms": row.get("duration_ms"),
            "call_count": row.get("call_count"),
            "trace_file": row.get("trace_file"),
            "line_no": row.get("line_no"),
        }
        for row in post_click_rows[-18:]
    ]

    return {
        "trace_files": sorted({str(row.get("trace_file") or "") for row in rows if row.get("trace_file")}),
        "total_rows": len(rows),
        "recipe_rows": len(recipe_rows),
        "post_click_rows": len(post_click_rows),
        "post_click_block_counts": block_counts,
        "post_click_stage_sequence": stages,
        "last_stage": stages[-1] if stages else "",
        "final_panel_enter_count": len(enter_rows),
        "compute_guidance_count": len(compute_rows),
        "final_render_panel_complete_count": len(final_render_rows),
        "compute_guidance_durations_ms": [
            row.get("duration_ms") for row in compute_rows if row.get("duration_ms") is not None
        ],
        "final_render_durations_ms": [
            row.get("duration_ms") for row in final_render_rows if row.get("duration_ms") is not None
        ],
        "last_post_click_rows": last_rows,
    }


def _classify_completion_gate(readiness: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    stages = list(trace.get("post_click_stage_sequence") or [])
    blocks = dict(trace.get("post_click_block_counts") or {})
    final_enter_count = int(trace.get("final_panel_enter_count") or 0)
    final_complete_count = int(trace.get("final_render_panel_complete_count") or 0)
    before_compute = "before_compute_guidance" in stages
    after_compute = "after_compute_guidance" in stages
    before_postprocess = "before_guidance_postprocess" in stages
    stuck_pending = bool(readiness.get("stuck_pending_shell"))
    output_changed = bool(readiness.get("apply_output_changed"))

    if not output_changed:
        gate = "APPLY_DID_NOT_CHANGE_OUTPUT"
        reason = "The browser proof did not observe an output change after Apply."
    elif final_enter_count == 0:
        gate = "FINAL_PANEL_NOT_REENTERED_AFTER_APPLY"
        reason = "Apply changed outputs, but the final Design Guide panel did not re-enter after the rerun."
    elif "settle_gate_waiting" in stages:
        gate = "SETTLE_GATE_RETURNED_WAITING_SHELL"
        reason = "The final panel re-entered, then returned through the settle-gate waiting shell."
    elif before_compute and not after_compute:
        gate = "COMPUTE_GUIDANCE_DID_NOT_COMPLETE"
        reason = "The final panel reached guidance compute but did not emit the after-compute stage."
    elif after_compute and not before_postprocess:
        gate = "COMPUTE_TO_POSTPROCESS_HANDOFF_MISSING"
        reason = "Guidance compute completed, but post-processing did not begin."
    elif before_postprocess and final_complete_count == 0:
        gate = "POSTPROCESS_OR_RENDER_DID_NOT_COMPLETE"
        reason = "The final panel entered post-processing but did not emit the final render completion trace."
    elif final_complete_count > 0 and stuck_pending:
        gate = "FINAL_RENDER_COMPLETED_BUT_PENDING_SHELL_REMAINED"
        reason = "The final render trace completed, but the browser still saw pending shell and no card."
    elif final_complete_count > 0 and not bool(readiness.get("post_click_card_ready")):
        gate = "FINAL_RENDER_COMPLETED_BUT_CARD_NOT_READY"
        reason = "The final render trace completed, but the browser did not see a refreshed verifier-ready card."
    elif blocks:
        gate = "COMPLETION_GATE_UNCLASSIFIED_WITH_TRACE"
        reason = "Trace rows exist, but they do not match a known completion-gate failure."
    else:
        gate = "NO_POST_CLICK_TRACE_ROWS"
        reason = "No post-click trace rows were captured for the recipe."

    return {
        "completion_gate": gate,
        "reason": reason,
        "apply_output_changed": output_changed,
        "post_click_card_ready": bool(readiness.get("post_click_card_ready")),
        "stuck_pending_shell": stuck_pending,
        "final_panel_enter_count": final_enter_count,
        "final_render_panel_complete_count": final_complete_count,
        "last_stage": trace.get("last_stage"),
        "stage_count": len(stages),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    readiness = dict(payload.get("readiness_classification") or {})
    completion = dict(payload.get("completion_gate_classification") or {})
    trace = dict(payload.get("trace_summary") or {})
    lines = [
        "# SHEAR_FAIL_BENDING_OVERDESIGN Pending-Shell Completion Gate Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Readiness classification: `{readiness.get('classification')}`",
        f"Completion gate: `{completion.get('completion_gate')}`",
        f"Reason: {completion.get('reason')}",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Findings",
        "",
        f"- Apply output changed: `{completion.get('apply_output_changed')}`",
        f"- Post-click card ready: `{completion.get('post_click_card_ready')}`",
        f"- Stuck pending shell: `{completion.get('stuck_pending_shell')}`",
        f"- Final panel re-enter count: `{completion.get('final_panel_enter_count')}`",
        f"- Final render complete count: `{completion.get('final_render_panel_complete_count')}`",
        f"- Last traced stage: `{completion.get('last_stage')}`",
        "",
        "## Trace Files",
        "",
    ]
    for trace_file in trace.get("trace_files") or []:
        lines.append(f"- `{trace_file}`")
    lines.extend(
        [
            "",
            "## Post-Click Stage Sequence",
            "",
        ]
    )
    stages = list(trace.get("post_click_stage_sequence") or [])
    if stages:
        for index, stage in enumerate(stages, start=1):
            lines.append(f"{index}. `{stage}`")
    else:
        lines.append("No post-click stage rows captured.")
    lines.extend(
        [
            "",
            "## Last Post-Click Trace Rows",
            "",
            "| Timestamp | Block | Elapsed ms | Duration ms |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for row in trace.get("last_post_click_rows") or []:
        lines.append(
            "| `{timestamp}` | `{block}` | `{elapsed}` | `{duration}` |".format(
                timestamp=row.get("timestamp"),
                block=row.get("block"),
                elapsed=row.get("elapsed_ms"),
                duration=row.get("duration_ms"),
            )
        )
    lines.extend(
        [
            "",
            "## Samples",
            "",
            "| Label | Elapsed s | Card Count | Pending Text | Output Changed | Card Text |",
            "| --- | ---: | ---: | --- | --- | --- |",
        ]
    )
    for sample in payload.get("samples") or []:
        dom = dict(sample.get("dom") or {})
        lines.append(
            "| `{label}` | `{elapsed}` | `{count}` | `{pending}` | `{changed}` | {text} |".format(
                label=sample.get("label"),
                elapsed=sample.get("elapsed_seconds"),
                count=sample.get("snapshot_card_count"),
                pending=dom.get("contains_pending_text"),
                changed=sample.get("output_changed_from_before"),
                text=_compact_text(sample.get("snapshot_first_card_text"), 180).replace("|", "\\|"),
            )
        )
    lines.extend(["", "## Next Safe Step", "", str(payload.get("next_safe_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8573)
    parser.add_argument("--reuse-existing-server", action="store_true", default=False)
    parser.add_argument("--headed", action="store_true", default=False)
    parser.add_argument("--sample-window-sec", type=float, default=95.0)
    parser.add_argument("--sample-interval-sec", type=float, default=5.0)
    parser.add_argument("--ready-timeout-sec", type=float, default=75.0)
    parser.add_argument("--card-timeout-sec", type=float, default=75.0)
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    PERF_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = ARTIFACT_DIR / f"design_guide_shear_fail_bending_overdesign_pending_completion_gate_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{args.port}"

    previous_perf_trace = os.environ.get("PERF_TRACE_INPUTS")
    previous_stage_debug = os.environ.get("CODEX_DG_STAGE_DEBUG")
    os.environ["PERF_TRACE_INPUTS"] = "1"
    os.environ["CODEX_DG_STAGE_DEBUG"] = "1"
    trace_before = _trace_files()
    process = None
    started_at = time.time()
    if not args.reuse_existing_server:
        process = _start_streamlit(args.port)
    else:
        _wait_for_http(base_url, timeout_s=45.0)

    payload: dict[str, Any] = {
        "schema": "design_guide_shear_fail_bending_overdesign_pending_completion_gate_audit.v1",
        "status": "PASS",
        "created_at": stamp,
        "family_id": FAMILY_ID,
        "attempt": {
            "name": ATTEMPT.name,
            "recipe": ATTEMPT.recipe,
        },
        "product_behaviour_changed": False,
        "browser_test_mode": True,
        "trace_enabled": True,
        "samples": [],
        "screenshots": {},
        "failures": [],
    }

    click_wall_time: datetime | None = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(viewport={"width": 1600, "height": 1000})
            page = context.new_page()
            try:
                _goto_recipe(
                    page,
                    base_url,
                    ATTEMPT.recipe,
                    ready_timeout_ms=int(max(args.ready_timeout_sec, 5.0) * 1000),
                    card_timeout_ms=int(max(args.card_timeout_sec, 5.0) * 1000),
                )
                before_state = _load_browser_state(page, timeout_s=45.0)
                before_snapshot = product_gate._snapshot(page)
                if before_state.get("browser_recipe") != ATTEMPT.recipe:
                    payload["failures"].append(
                        f"requested_browser_recipe_mismatch:requested={ATTEMPT.recipe}:applied={before_state.get('browser_recipe')}"
                    )
                if before_state.get("browser_recipe_error"):
                    payload["failures"].append(f"browser_recipe_error:{before_state.get('browser_recipe_error')}")
                if not _family_matches(FAMILY_ID, before_snapshot, before_state):
                    payload["failures"].append(f"target_family_not_selected:{FAMILY_ID}")
                before_hash = _stable_hash(_output_fingerprint(before_snapshot, before_state))
                before_card_text_hash = _stable_hash(before_snapshot.get("first_card_text") or "")
                payload["before"] = {
                    "output_hash": before_hash,
                    "family_ids": _selected_family_ids(before_snapshot, before_state),
                    "family_selection": _family_selection(before_snapshot),
                    "visible_cta_buttons": _enabled_action_buttons(before_snapshot),
                    "card_text_sample": _compact_text(before_snapshot.get("first_card_text"), 620),
                }
                payload["screenshots"]["before"] = product_gate._save_screenshot(page, run_dir, ATTEMPT.name, "before")
                payload["samples"].append(_sample(page, label="before_click", elapsed_s=0.0, before_hash=before_hash))

                click_wall_time = datetime.now()
                click = _click_first_enabled_action(page)
                payload["click"] = click
                if not click.get("clicked"):
                    payload["status"] = "PARTIAL"
                    payload["failures"].append("enabled_cta_detected_but_click_failed")
                    readiness = {
                        "classification": "CLICK_NOT_PERFORMED",
                        "reason": "No enabled Apply/one-click CTA was clicked.",
                        "post_click_card_ready": False,
                        "apply_output_changed": False,
                    }
                else:
                    start = time.monotonic()
                    page.wait_for_timeout(1000)
                    next_sample = 0.0
                    while True:
                        elapsed = time.monotonic() - start
                        if elapsed >= next_sample:
                            payload["samples"].append(
                                _sample(
                                    page,
                                    label=f"post_click_{len(payload['samples'])}",
                                    elapsed_s=elapsed,
                                    before_hash=before_hash,
                                )
                            )
                            next_sample += max(args.sample_interval_sec, 1.0)
                        latest = payload["samples"][-1]
                        if (
                            latest["label"].startswith("post_click")
                            and int(latest.get("snapshot_card_count") or 0) > 0
                            and str(latest.get("snapshot_first_card_text") or "").strip()
                            and bool(latest.get("output_changed_from_before"))
                            and elapsed >= max(args.sample_interval_sec, 1.0)
                            and _stable_hash(latest.get("snapshot_first_card_text") or "") != before_card_text_hash
                        ):
                            break
                        if elapsed >= max(args.sample_window_sec, 5.0):
                            break
                        page.wait_for_timeout(500)
                    payload["screenshots"]["after_sampling"] = product_gate._save_screenshot(
                        page,
                        run_dir,
                        ATTEMPT.name,
                        "after_sampling",
                    )
                    readiness = _classify_readiness(
                        payload["samples"],
                        before_hash=before_hash,
                        before_card_text_hash=before_card_text_hash,
                        min_ready_elapsed_s=max(args.sample_interval_sec, 1.0),
                    )

                payload["readiness_classification"] = readiness
            except PlaywrightTimeoutError as exc:
                payload["status"] = "PARTIAL"
                payload["failures"].append(f"initial_ready_or_card_timeout:{type(exc).__name__}: {exc}")
                payload["readiness_classification"] = {
                    "classification": "INITIAL_CARD_NOT_READY",
                    "reason": "The initial recipe did not reach a verifier-ready Design Guide card.",
                    "post_click_card_ready": False,
                    "apply_output_changed": False,
                }
                try:
                    payload["samples"].append(_sample(page, label="initial_timeout", elapsed_s=0.0))
                    payload["screenshots"]["initial_timeout"] = product_gate._save_screenshot(
                        page,
                        run_dir,
                        ATTEMPT.name,
                        "initial_timeout",
                    )
                except Exception as nested:
                    payload["failures"].append(f"initial_timeout_snapshot_failed:{type(nested).__name__}: {nested}")
            finally:
                context.close()
                browser.close()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()
        if previous_perf_trace is None:
            os.environ.pop("PERF_TRACE_INPUTS", None)
        else:
            os.environ["PERF_TRACE_INPUTS"] = previous_perf_trace
        if previous_stage_debug is None:
            os.environ.pop("CODEX_DG_STAGE_DEBUG", None)
        else:
            os.environ["CODEX_DG_STAGE_DEBUG"] = previous_stage_debug

    trace_paths = _created_or_modified_trace_files(trace_before, started_at=started_at)
    trace_rows = _parse_trace_rows(trace_paths)
    trace_summary = _trace_summary(trace_rows, click_wall_time=click_wall_time)
    payload["trace_summary"] = trace_summary
    payload["completion_gate_classification"] = _classify_completion_gate(
        dict(payload.get("readiness_classification") or {}),
        trace_summary,
    )
    payload["next_safe_step"] = (
        "Inspect the classified completion gate and add a focused proof/fix at that gate only; "
        "do not change family runtime, contracts, CTA rendering, publication semantics, apply routing, "
        "or visible wording."
    )

    artifact_path = ARTIFACT_DIR / f"design_guide_shear_fail_bending_overdesign_pending_completion_gate_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_fail_bending_overdesign_pending_completion_gate_audit_{stamp}.md"
    payload["artifact"] = str(artifact_path)
    payload["report"] = str(report_path)
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "readiness_classification": (payload.get("readiness_classification") or {}).get("classification"),
                "completion_gate": (payload.get("completion_gate_classification") or {}).get("completion_gate"),
                "artifact": str(artifact_path),
                "report": str(report_path),
                "failures": payload.get("failures"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
