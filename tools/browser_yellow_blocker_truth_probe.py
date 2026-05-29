"""Focused truth probe for yellow Design Guide cleanup blockers.

This script is diagnostic-only. It reuses the live fuzz verifier's browser
state capture, then checks whether a yellow "Further cleanup blocked" state is
truthful against current app state, visible card text, diagram evidence, and
direct candidate previews for likely bending cleanup reductions.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.browser_live_design_guide_fuzz_verifier import (  # noqa: E402
    _now_stamp,
    _port_ready,
    apply_initial_case,
    capture_step,
    exact_blockers,
    low_util_families,
    no_link_shear_cleanup_audit,
    wait_for_settle,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
    _start_streamlit,
    _wait_for_http,
)


DEFAULT_SOURCE_ARTIFACT = Path(
    "artifacts/verification/live_fuzz/2026-05-07T14-25-26"
)
DEFAULT_RECIPE = "OPT_EXPECT_BENDING_SAFE_OVERDESIGNED"
MINIMUM_REQUESTED_BENDING_TRIALS = [(5, 24), (4, 24), (6, 20), (5, 20), (4, 20)]


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _first_number(*values: Any) -> float | None:
    for value in values:
        out = _float_or_none(value)
        if out is not None:
            return out
    return None


def _first_int(*values: Any) -> int | None:
    out = _first_number(*values)
    return int(round(out)) if out is not None else None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _case_from_failure_case(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = _load_json(path)
    for source in (data.get("initial_inputs"), data.get("case"), data):
        if isinstance(source, dict) and source.get("recipe"):
            return dict(source)
    case_result = data.get("case_result")
    if isinstance(case_result, dict) and isinstance(case_result.get("initial_inputs"), dict):
        return dict(case_result["initial_inputs"])
    return None


def _case_from_artifact(artifact_dir: Path, recipe: str) -> dict[str, Any]:
    progress = artifact_dir / "cases_progress.jsonl"
    if progress.exists():
        for line in progress.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            case_result = row.get("case")
            initial = dict((case_result or {}).get("initial_inputs") or {})
            if initial.get("recipe") == recipe:
                return initial
            if row.get("recipe") == recipe and initial:
                return initial
    latest = artifact_dir / "latest_case.json"
    if latest.exists():
        data = _load_json(latest)
        initial = dict(data.get("initial_inputs") or {})
        if initial.get("recipe") == recipe:
            return initial
    stable = REPO_ROOT / "tools/replay_cases/design_guide_contract/combined_overdesign_cleanup_blocker_names_bending_and_shear.json"
    fallback = _case_from_failure_case(stable)
    if fallback:
        return fallback
    raise FileNotFoundError(f"No replay case for recipe {recipe!r} found in {artifact_dir}")


def _state_from_browser(browser_state: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for source_name in (
        "browser_recipe_applied_state",
        "browser_shared_probe",
        "summary_state_probe",
        "active_beam_record_probe",
    ):
        source = browser_state.get(source_name)
        if isinstance(source, dict):
            state.update(
                {
                    key: value
                    for key, value in source.items()
                    if value is not None and not str(key).startswith("_")
                }
            )
    return state


def _current_reinforcement_and_links(browser_state: dict[str, Any]) -> dict[str, Any]:
    shared = dict(browser_state.get("browser_shared_probe") or {})
    summary = dict(browser_state.get("summary_state_probe") or {})
    active = dict(browser_state.get("active_beam_record_probe") or {})
    recipe_state = dict(browser_state.get("browser_recipe_applied_state") or {})
    return {
        "lig_d": _first_number(summary.get("lig_d"), shared.get("lig_d"), active.get("lig_d"), recipe_state.get("lig_d")),
        "lig_legs": _first_int(summary.get("lig_legs"), shared.get("lig_legs"), active.get("lig_legs"), recipe_state.get("lig_legs")),
        "s_lig": _first_number(summary.get("s_lig"), shared.get("s_lig"), active.get("s_lig"), recipe_state.get("s_lig")),
        "bottom_bar_count": _first_int(
            summary.get("bot1_count"),
            summary.get("bot_row_1_bars"),
            shared.get("bot1_count"),
            shared.get("bot_row_1_bars"),
            active.get("bot1_count"),
            recipe_state.get("bot1_count"),
        ),
        "bottom_bar_diameter": _first_number(
            summary.get("db_bot_1"),
            summary.get("bot_row_1_dia"),
            shared.get("db_bot_1"),
            shared.get("bot_row_1_dia"),
            active.get("db_bot_1"),
            recipe_state.get("db_bot_1"),
        ),
    }


def _extract_evidence(step: dict[str, Any]) -> dict[str, Any]:
    state = dict(step.get("browser_state") or {})
    guidance = dict(state.get("guidance_compute_probe") or {})
    return {
        "exact_blockers_by_family": exact_blockers(state),
        "candidate_search_evidence": dict(guidance.get("candidate_search_evidence") or {}),
        "no_link_shear_cleanup_audit": no_link_shear_cleanup_audit(state, dict(step.get("visible_design_guide") or {})),
    }


def _diagram_probe(page, artifact_dir: Path) -> dict[str, Any]:
    screenshot_path = artifact_dir / "yellow_blocker_truth_probe_full_page.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    details = page.evaluate(
        """
        () => {
          const txt = (document.body && document.body.innerText) || "";
          const named = [];
          for (const el of document.querySelectorAll("svg *")) {
            const attrs = [
              el.getAttribute("class"),
              el.getAttribute("aria-label"),
              el.getAttribute("data-testid"),
              el.getAttribute("id"),
              el.getAttribute("name"),
              el.textContent,
            ].filter(Boolean).join(" ").toLowerCase();
            if (/lig|link|stirrup|shear/.test(attrs)) {
              named.push({
                tag: el.tagName,
                className: el.getAttribute("class") || "",
                id: el.getAttribute("id") || "",
                text: (el.textContent || "").trim().slice(0, 80),
              });
            }
          }
          return {
            canvas_count: document.querySelectorAll("canvas").length,
            svg_count: document.querySelectorAll("svg").length,
            named_shear_link_svg_element_count: named.length,
            named_shear_link_svg_elements: named.slice(0, 20),
            visible_link_controls_off:
              /Link\\s*Ø\\s*\\(mm\\)\\s*0\\s*\\(off\\)/i.test(txt) &&
              /No\\.\\s*of\\s*legs\\s*0/i.test(txt),
          };
        }
        """
    )
    named_count = int(details.get("named_shear_link_svg_element_count") or 0)
    rendered_links_visible: str | bool = "unknown"
    if named_count > 0:
        rendered_links_visible = True
    elif details.get("visible_link_controls_off"):
        rendered_links_visible = False
    return {
        **details,
        "rendered_links_visible": rendered_links_visible,
        "screenshot_path": str(screenshot_path),
    }


def _candidate_state(base_state: dict[str, Any], count: int, diameter: int) -> dict[str, Any]:
    candidate = dict(base_state)
    candidate.update(
        {
            "bot1_count": int(count),
            "bot_row_1_bars": int(count),
            "nb_bot": int(count),
            "bot_entry": float(count),
            "db_bot_1": float(diameter),
            "bot_row_1_dia": float(diameter),
            "db_bot": float(diameter),
        }
    )
    return candidate


def _bar_area_mm2(count: int | None, diameter: int | None) -> float | None:
    if count is None or diameter is None:
        return None
    try:
        return float(count) * math.pi * (float(diameter) ** 2.0) / 4.0
    except Exception:
        return None


def _failed_subchecks(overview: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    packs = overview.get("packs")
    if not isinstance(packs, dict):
        return failures
    for family, pack in packs.items():
        rows = (pack or {}).get("rows") if isinstance(pack, dict) else None
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "").strip().upper()
            if status != "FAIL":
                continue
            failures.append(
                {
                    "family": family,
                    "uid": row.get("uid") or row.get("key") or row.get("id"),
                    "title": row.get("title") or row.get("label") or row.get("check"),
                    "status": status,
                    "util": _float_or_none(row.get("util") or row.get("utilisation") or row.get("ratio")),
                    "value": row.get("value") or row.get("calculated") or row.get("demand"),
                    "limit": row.get("limit") or row.get("capacity") or row.get("requirement"),
                    "reason": row.get("reason") or row.get("message") or row.get("note"),
                }
            )
    return failures


def _failed_rule_summary(overview: dict[str, Any]) -> str:
    failures = _failed_subchecks(overview)
    if not failures:
        statuses = dict(overview.get("statuses") or {})
        return ", ".join(
            str(family)
            for family, status in statuses.items()
            if str(status).strip().upper() == "FAIL"
        )
    parts: list[str] = []
    for failure in failures[:4]:
        title = failure.get("title") or failure.get("uid") or failure.get("family")
        util = failure.get("util")
        limit = failure.get("limit")
        details: list[str] = []
        if util is not None:
            details.append(f"util {float(util):.3f}")
        if limit not in (None, ""):
            details.append(f"limit {limit}")
        suffix = f" ({', '.join(details)})" if details else ""
        parts.append(f"{failure.get('family')}: {title}{suffix}")
    return "; ".join(parts)


def _bending_trials_for_current(current: dict[str, Any]) -> list[tuple[int, int]]:
    trials: list[tuple[int, int]] = list(MINIMUM_REQUESTED_BENDING_TRIALS)
    count = _first_int(current.get("bottom_bar_count"))
    diameter = _first_int(current.get("bottom_bar_diameter"))
    if count and diameter:
        for c in range(max(1, count - 1), 0, -1):
            trials.append((c, diameter))
        smaller_diameters = [d for d in (28, 24, 20, 16, 12, 10) if d < diameter]
        for d in smaller_diameters:
            trials.append((count, d))
            if count > 1:
                trials.append((count - 1, d))
    unique: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for trial in trials:
        if trial not in seen:
            unique.append(trial)
            seen.add(trial)
    return unique


def _run_bending_candidate_trials(browser_state: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    import inputs_page as app  # Imported lazily so the browser-only path stays light.

    base_state = _state_from_browser(browser_state)
    current_bending = _float_or_none(
        dict(browser_state.get("summary_overview_probe") or {}).get("utils", {}).get("bending")
    )
    current_count = _first_int(current.get("bottom_bar_count"))
    current_dia = _first_int(current.get("bottom_bar_diameter"))
    rows: list[dict[str, Any]] = []
    best_passing_improvement: dict[str, Any] | None = None
    for count, diameter in _bending_trials_for_current(current):
        candidate = _candidate_state(base_state, count, diameter)
        row: dict[str, Any] = {
            "candidate": f"{count}N{diameter}",
            "bottom_bar_count": count,
            "bottom_bar_diameter": diameter,
            "Ast_mm2": _bar_area_mm2(count, diameter),
            "is_reduction_from_current": bool(
                current_count
                and current_dia
                and (diameter < current_dia or (diameter == current_dia and count < current_count))
            ),
        }
        try:
            evaluated = app.evaluate_candidate_full(candidate, source="yellow_blocker_truth_probe")
            overview = dict((evaluated or {}).get("overview") or {})
            utils = dict(overview.get("utils") or {})
            statuses = dict(overview.get("statuses") or {})
            all_pass = bool(overview.get("all_key_pass")) and not bool(overview.get("any_fail"))
            bending_util = _float_or_none(utils.get("bending"))
            improvement = (
                current_bending is not None
                and bending_util is not None
                and bending_util > current_bending + 1e-6
            )
            row.update(
                {
                    "bending_util": bending_util,
                    "shear_util": _float_or_none(utils.get("shear")),
                    "crack_util": _float_or_none(utils.get("crack")),
                    "deflection_util": _float_or_none(utils.get("deflection")),
                    "crack_status": statuses.get("crack"),
                    "deflection_status": statuses.get("deflection"),
                    "statuses": statuses,
                    "all_required_checks_pass": all_pass,
                    "improves_bending_utilisation": bool(improvement),
                    "executor_backed_assumed": True,
                    "failed_check": next(
                        (family for family, status in statuses.items() if str(status).upper() == "FAIL"),
                        None,
                    ),
                    "failed_subchecks": _failed_subchecks(overview),
                    "failed_rule_summary": _failed_rule_summary(overview),
                }
            )
            if all_pass and improvement and row["is_reduction_from_current"]:
                if best_passing_improvement is None or float(bending_util or 0.0) > float(
                    best_passing_improvement.get("bending_util") or 0.0
                ):
                    best_passing_improvement = dict(row)
        except Exception as exc:
            row.update({"error": f"{type(exc).__name__}: {exc}"})
        rows.append(row)
    return {
        "current_bending_util": current_bending,
        "tested_candidates": rows,
        "best_passing_bending_cleanup_candidate": best_passing_improvement,
    }


def _verdict(report: dict[str, Any]) -> tuple[str, list[str], str]:
    failures: list[str] = []
    card_text = str(report.get("visible_card_text") or "")
    current = dict(report.get("current_state") or {})
    links_removed_claimed = "shear links are already removed" in card_text.lower()
    lig_d = _float_or_none(current.get("lig_d"))
    lig_legs = _first_int(current.get("lig_legs"))
    app_state_no_links = bool((lig_d is not None and lig_d <= 0.0) or (lig_legs is not None and lig_legs <= 0))
    if links_removed_claimed and not app_state_no_links:
        failures.append("false_shear_removed_claim_app_state_has_active_links")
    diagram = dict(report.get("diagram_probe") or {})
    if links_removed_claimed and diagram.get("rendered_links_visible") is True:
        failures.append("false_shear_removed_claim_diagram_shows_links")
    title_text = f"{report.get('visible_card_title') or ''} {card_text}".lower()
    cta_enabled = bool(report.get("cta_enabled"))
    visible_low_util_blocker = (not cta_enabled) and (
        "cleanup blocked" in title_text or "further cleanup blocked" in title_text or "blocked" in title_text
    )
    best = dict((report.get("bending_candidate_probe") or {}).get("best_passing_bending_cleanup_candidate") or {})
    if visible_low_util_blocker and best:
        failures.append("safe_bending_cleanup_candidate_found")
    blockers = dict(report.get("exact_blockers_by_family") or {})
    if visible_low_util_blocker:
        if "bending" in report.get("low_util_families", []) and "bending" not in blockers:
            failures.append("missing_bending_exact_blocker")
        if "shear" in report.get("low_util_families", []) and "shear" not in blockers:
            failures.append("missing_shear_exact_blocker")
    if failures:
        if any("diagram" in item for item in failures):
            layer = "stale diagram rendering or stale visual state"
        elif any("bending_cleanup" in item for item in failures):
            layer = "false blocker candidate search"
        elif any("app_state_has_active_links" in item for item in failures):
            layer = "stale state publication or false blocker text"
        else:
            layer = "blocker proof publication"
        return "false blocker", failures, layer
    return "truthful blocker", [], "no issue detected by focused truth probe"


def _markdown_report(report: dict[str, Any]) -> str:
    rows = report.get("bending_candidate_probe", {}).get("tested_candidates", [])
    trial_lines = [
        "| candidate | Ast | reduction | bend util | shear util | crack | deflection | pass | improves | failed rule |",
        "|---|---:|---:|---:|---:|---|---|---|---|---|",
    ]
    for row in rows:
        ast = row.get("Ast_mm2")
        failed = row.get("failed_rule_summary") or row.get("failed_check") or row.get("error") or ""
        trial_lines.append(
            "| {candidate} | {ast} | {reduction} | {bend} | {shear} | {crack} | {deflection} | {passed} | {improves} | {failed} |".format(
                candidate=row.get("candidate"),
                ast="" if ast is None else f"{float(ast):.0f}",
                reduction=row.get("is_reduction_from_current"),
                bend="" if row.get("bending_util") is None else f"{float(row['bending_util']):.3f}",
                shear="" if row.get("shear_util") is None else f"{float(row['shear_util']):.3f}",
                crack=str(row.get("crack_status") or ""),
                deflection=str(row.get("deflection_status") or ""),
                passed=row.get("all_required_checks_pass"),
                improves=row.get("improves_bending_utilisation"),
                failed=str(failed).replace("|", "/"),
            )
        )
    current = dict(report.get("current_state") or {})
    return "\n".join(
        [
            "# Yellow Blocker Truth Probe",
            "",
            f"- Verdict: `{report.get('verdict')}`",
            f"- Likely issue layer: `{report.get('likely_issue_layer')}`",
            f"- Artifact directory: `{report.get('artifact_dir')}`",
            f"- Screenshot: `{report.get('diagram_probe', {}).get('screenshot_path')}`",
            "",
            "## Current Card",
            f"- Title: `{report.get('visible_card_title')}`",
            f"- Colour/status: `{report.get('visible_card_colour')}` / `{report.get('visible_card_status')}`",
            f"- CTA visible/enabled: `{report.get('cta_visible')}` / `{report.get('cta_enabled')}`",
            f"- Text: {report.get('visible_card_text')}",
            "",
            "## Current State",
            f"- Bottom reinforcement: `{current.get('bottom_bar_count')}N{current.get('bottom_bar_diameter')}`",
            f"- Links: `lig_d={current.get('lig_d')}`, `lig_legs={current.get('lig_legs')}`, `s_lig={current.get('s_lig')}`",
            f"- Bending utilisation: `{report.get('bending_util')}`",
            f"- Shear utilisation: `{report.get('shear_util')}`",
            f"- Actual app-state links removed: `{report.get('actual_app_state_links_removed')}`",
            f"- Rendered links visible: `{report.get('diagram_probe', {}).get('rendered_links_visible')}`",
            "",
            "## Bending Candidate Probe",
            *trial_lines,
            "",
            "## Evidence",
            f"- Low-util families: `{report.get('low_util_families')}`",
            f"- Exact blocker families: `{list(dict(report.get('exact_blockers_by_family') or {}).keys())}`",
            f"- No-link audit: `{report.get('no_link_shear_cleanup_audit')}`",
            f"- Failure reasons: `{report.get('failure_reasons')}`",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9301)
    parser.add_argument("--artifact", default=str(DEFAULT_SOURCE_ARTIFACT))
    parser.add_argument("--replay-case", default=None)
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--headed", action="store_true", default=True)
    mode.add_argument("--headless", action="store_true", default=False)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)

    timestamp = _now_stamp()
    artifact_dir = Path(args.output_dir or REPO_ROOT / "artifacts/verification/yellow_blocker_truth_probe" / timestamp).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    source_case: dict[str, Any] | None = None
    replay_path = Path(args.replay_case).resolve() if args.replay_case else None
    if replay_path and replay_path.exists():
        source_case = _case_from_failure_case(replay_path)
    if source_case is None:
        source_case = _case_from_artifact(Path(args.artifact).resolve(), str(args.recipe))
    source_case = dict(source_case)
    source_case.setdefault("case_index", 0)

    base_url = f"http://127.0.0.1:{args.port}"
    process: subprocess.Popen[Any] | None = None
    console_messages: list[str] = []
    report: dict[str, Any] = {
        "artifact_dir": str(artifact_dir),
        "source_case": source_case,
        "source_replay_case": str(replay_path) if replay_path else None,
        "source_artifact": str(Path(args.artifact).resolve()),
    }
    try:
        if not _port_ready(base_url):
            process = _start_streamlit(args.port)
        else:
            _wait_for_http(base_url, timeout_s=10)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=bool(args.headless))
            context = browser.new_context()
            page = context.new_page()
            page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
            apply_initial_case(
                page,
                base_url,
                source_case,
                reload_between_cases=True,
                console_messages=console_messages,
            )
            wait_for_settle(page, base_url=base_url, console_messages=console_messages)
            step = capture_step(
                page,
                artifact_dir=artifact_dir,
                case_index=int(source_case.get("case_index") or 0),
                step_index=0,
                step_type="yellow_blocker_truth_probe",
                inputs={"mu": source_case.get("mu"), "vu": source_case.get("vu"), "recipe": source_case.get("recipe")},
                save_screenshot=True,
            )
            browser_state = dict(step.get("browser_state") or {})
            card = dict(step.get("visible_design_guide") or {})
            summary = dict(step.get("visible_summary") or {})
            current = _current_reinforcement_and_links(browser_state)
            evidence = _extract_evidence(step)
            diagram = _diagram_probe(page, artifact_dir)
            bending_probe = _run_bending_candidate_trials(browser_state, current)
            utils = dict((browser_state.get("summary_overview_probe") or {}).get("utils") or {})
            lig_d = _float_or_none(current.get("lig_d"))
            lig_legs = _first_int(current.get("lig_legs"))
            report.update(
                {
                    "visible_card_title": card.get("title"),
                    "visible_card_colour": card.get("classes"),
                    "visible_card_status": card.get("status_label"),
                    "visible_card_text": card.get("text"),
                    "cta_visible": bool(card.get("cta_visible")),
                    "cta_enabled": bool(card.get("cta_enabled")),
                    "summary": summary,
                    "bending_util": _float_or_none(utils.get("bending")),
                    "shear_util": _float_or_none(utils.get("shear")),
                    "current_state": current,
                    "actual_app_state_links_removed": bool(
                        (lig_d is not None and lig_d <= 0.0)
                        or (lig_legs is not None and lig_legs <= 0)
                    ),
                    "low_util_families": low_util_families(summary),
                    "diagram_probe": diagram,
                    "bending_candidate_probe": bending_probe,
                    **evidence,
                    "console_messages": console_messages[-50:],
                }
            )
            verdict, failures, layer = _verdict(report)
            report["verdict"] = verdict
            report["failure_reasons"] = failures
            report["likely_issue_layer"] = layer
            _write_json(artifact_dir / "yellow_blocker_truth_probe.json", report)
            markdown = _markdown_report(report)
            (artifact_dir / "yellow_blocker_truth_probe.md").write_text(markdown, encoding="utf-8")
            sys.stdout.buffer.write(markdown.encode("utf-8", errors="replace") + b"\n")
            browser.close()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    return 0 if report.get("verdict") == "truthful blocker" else 1


if __name__ == "__main__":
    raise SystemExit(main())
