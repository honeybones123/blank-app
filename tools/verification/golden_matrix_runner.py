"""Mandatory deterministic Design Guide golden matrix gate.

This runner is product-logic neutral. It writes deterministic replay inputs for
canonical Design Guide states, runs the browser live Design Guide verifier in
replay mode for each case, records the complete pass/fail picture, and exits
non-zero if any case fails.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tools.verification.source_fingerprint import compute_source_fingerprint


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "verification" / "golden_matrix"
SCREENSHOT_FIELD_KEYS = (
    "full_page_screenshot",
    "viewport_screenshot",
    "design_guide_screenshot",
    "summary_cards_screenshot",
    "debug_or_probe_screenshot",
    "screenshot_capture_status",
    "missing_crop_targets",
)


@dataclass(frozen=True)
class GoldenCase:
    case_name: str
    initial_inputs: dict[str, Any]
    expected_initial_failing_families: tuple[str, ...]
    expected_initial_low_util_families: tuple[str, ...]
    expected_first_action_family: str
    required_search_families: tuple[str, ...]
    allowed_final_states: tuple[str, ...]
    blocker_evidence_requirements: tuple[str, ...]
    post_click_ordinary_blue_action_allowed: bool = False


REQUIRED_ACTIVE_BLOCKER_FIELDS = (
    "active_repair_search_ran",
    "active_repair_search_exhaustive",
    "attempted_candidate_count",
    "executable_candidate_count",
    "failed_candidate_id or best_rejected_candidate_id",
    "failed_check_name",
    "failed_check_status",
    "failed_check_util/current_util",
    "failed_check_capacity_or_limit where applicable",
    "route_inventory",
    "reason_names_family",
)

REQUIRED_LOW_UTIL_BLOCKER_FIELDS = (
    "cleanup_search_ran",
    "cleanup_search_exhaustive",
    "attempted_candidate_count",
    "executable_candidate_count",
    "target_band_candidate_count",
    "best_safe_final_util where applicable",
    "failed_candidate_id or best_rejected_candidate_id",
    "failed_check_name",
    "failed_check_status",
    "failed_check_util/current_util",
    "failed_check_capacity_or_limit where applicable",
    "family_specific_reason",
)

COMMON_ACTIVE_CASE = {
    "section_shape": "RECT",
    "geometry_lock": False,
    "span_m": 5.8,
    "b": 300,
    "D": 450,
    "fc": 32,
    "fsy": 500,
    "bottom_bar_count": 2,
    "bottom_bar_dia": 12,
    "top_bar_count": 2,
    "top_bar_dia": 10,
    "lig_d": 10,
    "lig_legs": 2,
    "s_lig": 250,
}

COMMON_HEAVY_REO = {
    "section_shape": "RECT",
    "geometry_lock": False,
    "span_m": 5.8,
    "b": 350,
    "D": 600,
    "fc": 40,
    "fsy": 500,
    "bottom_bar_count": 6,
    "bottom_bar_dia": 24,
    "top_bar_count": 4,
    "top_bar_dia": 12,
    "lig_d": 12,
    "lig_legs": 4,
    "s_lig": 150,
}


def _case(case_name: str, *, mu: float, vu: float, recipe: str, base: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    payload = dict(base)
    payload.update({"mu": mu, "vu": vu, "recipe": recipe})
    payload.update(overrides)
    payload["golden_case_name"] = case_name
    return payload


GOLDEN_CASES: list[GoldenCase] = [
    GoldenCase(
        "bending_under_only",
        _case("bending_under_only", mu=560.0, vu=45.0, recipe="A_bending_under_only", base=COMMON_ACTIVE_CASE),
        ("bending",),
        (),
        "bending",
        ("bar count", "bar diameter", "second row", "depth", "width"),
        ("green accepted", "exact active-fail blocker terminal"),
        REQUIRED_ACTIVE_BLOCKER_FIELDS,
    ),
    GoldenCase(
        "shear_under_only",
        _case("shear_under_only", mu=55.0, vu=610.0, recipe="B_shear_under_only", base=COMMON_ACTIVE_CASE),
        ("shear",),
        (),
        "shear",
        ("links", "spacing", "diameter", "legs", "depth", "width"),
        ("green accepted", "exact active-fail blocker terminal"),
        REQUIRED_ACTIVE_BLOCKER_FIELDS,
    ),
    GoldenCase(
        "bending_and_shear_under",
        _case(
            "bending_and_shear_under",
            mu=520.0,
            vu=610.0,
            recipe="C_combined_underdesign",
            base=COMMON_ACTIVE_CASE,
            b=450,
            D=500,
            fc=40,
            fsy=400,
            bottom_bar_count=3,
            bottom_bar_dia=12,
            top_bar_count=3,
            top_bar_dia=10,
            lig_d=24,
            lig_legs=4,
            s_lig=300,
        ),
        ("bending", "shear"),
        (),
        "combined",
        ("bending", "shear", "combined", "geometry", "bottom reinforcement", "links"),
        ("green accepted", "exact active-fail blocker terminal"),
        REQUIRED_ACTIVE_BLOCKER_FIELDS + ("combined_repair_routes",),
    ),
    GoldenCase(
        "bending_overdesign_only",
        _case("bending_overdesign_only", mu=70.0, vu=95.0, recipe="OPT_EXPECT_BENDING_SAFE_OVERDESIGNED", base=COMMON_HEAVY_REO),
        (),
        ("bending",),
        "bending",
        ("bottom bar count", "bottom bar diameter", "second row", "geometry"),
        ("green accepted", "exact low-util blocker terminal"),
        REQUIRED_LOW_UTIL_BLOCKER_FIELDS,
    ),
    GoldenCase(
        "shear_overdesign_only",
        _case("shear_overdesign_only", mu=115.0, vu=30.0, recipe="SO_BASE_HEAVY_LINKS_CONSERVATIVE", base=COMMON_HEAVY_REO),
        (),
        ("shear",),
        "shear",
        ("links", "spacing", "diameter", "legs", "no links", "geometry"),
        ("green accepted", "exact low-util blocker terminal"),
        REQUIRED_LOW_UTIL_BLOCKER_FIELDS,
    ),
    GoldenCase(
        "bending_in_target_shear_low",
        _case("bending_in_target_shear_low", mu=185.0, vu=18.0, recipe="OPT_EXPECT_SHEAR_SAFE_OVERDESIGNED", base=COMMON_HEAVY_REO, bottom_bar_count=3, bottom_bar_dia=20),
        (),
        ("shear",),
        "shear",
        ("links", "spacing", "diameter", "legs", "no links"),
        ("green accepted", "exact low-util blocker terminal"),
        REQUIRED_LOW_UTIL_BLOCKER_FIELDS,
    ),
    GoldenCase(
        "shear_in_target_bending_low",
        _case("shear_in_target_bending_low", mu=45.0, vu=165.0, recipe="OPT_EXPECT_BENDING_SAFE_OVERDESIGNED", base=COMMON_HEAVY_REO, lig_d=10, lig_legs=2, s_lig=300),
        (),
        ("bending",),
        "bending",
        ("bottom bar count", "bottom bar diameter", "second row"),
        ("green accepted", "exact low-util blocker terminal"),
        REQUIRED_LOW_UTIL_BLOCKER_FIELDS,
    ),
    GoldenCase(
        "all_in_target_terminal",
        _case("all_in_target_terminal", mu=135.0, vu=100.0, recipe="ALREADY_TARGET", base=COMMON_ACTIVE_CASE, b=300, D=500, bottom_bar_count=3, bottom_bar_dia=20, lig_d=10, lig_legs=2, s_lig=250),
        (),
        (),
        "none",
        (),
        ("green accepted",),
        (),
    ),
    GoldenCase(
        "no_links_terminal",
        _case("no_links_terminal", mu=115.0, vu=8.0, recipe="SO_BASE_HEAVY_LINKS_CONSERVATIVE", base=COMMON_HEAVY_REO, lig_d=0, lig_legs=0, s_lig=300),
        (),
        ("shear",),
        "none",
        ("no links", "concrete capacity", "catalogue floor"),
        ("green accepted", "exact low-util blocker terminal"),
        REQUIRED_LOW_UTIL_BLOCKER_FIELDS,
    ),
    GoldenCase(
        "spacing_blocked",
        _case("spacing_blocked", mu=690.0, vu=120.0, recipe="A_bending_under_only", base=COMMON_ACTIVE_CASE, b=250, D=350, bottom_bar_count=6, bottom_bar_dia=28, geometry_lock=True),
        ("bending",),
        (),
        "bending",
        ("bar count", "bar diameter", "second row", "spacing", "cover"),
        ("exact active-fail blocker terminal",),
        REQUIRED_ACTIVE_BLOCKER_FIELDS + ("spacing", "cover"),
    ),
    GoldenCase(
        "serviceability_blocked",
        _case("serviceability_blocked", mu=190.0, vu=90.0, recipe="GOLDEN_SERVICEABILITY_BLOCKED", base=COMMON_ACTIVE_CASE, span_m=9.0, D=300, b=250, geometry_lock=True),
        (),
        (),
        "serviceability",
        ("depth", "width", "deflection", "crack"),
        ("exact blocker terminal", "green accepted"),
        REQUIRED_ACTIVE_BLOCKER_FIELDS,
    ),
    GoldenCase(
        "geometry_blocked",
        _case("geometry_blocked", mu=760.0, vu=780.0, recipe="C_combined_underdesign", base=COMMON_ACTIVE_CASE, b=250, D=300, geometry_lock=True, bottom_bar_count=6, bottom_bar_dia=28, lig_d=24, lig_legs=4, s_lig=100),
        ("bending", "shear"),
        (),
        "combined",
        ("geometry", "depth", "width", "bottom reinforcement", "links"),
        ("exact active-fail blocker terminal",),
        REQUIRED_ACTIVE_BLOCKER_FIELDS + ("geometry", "combined_repair_routes"),
    ),
    GoldenCase(
        "combined_repair_required",
        _case("combined_repair_required", mu=430.0, vu=440.0, recipe="C_combined_underdesign", base=COMMON_ACTIVE_CASE, b=350, D=450, bottom_bar_count=2, bottom_bar_dia=16, lig_d=10, lig_legs=2, s_lig=300),
        ("bending", "shear"),
        (),
        "combined",
        ("combined", "geometry", "bottom reinforcement", "links"),
        ("green accepted", "exact active-fail blocker terminal"),
        REQUIRED_ACTIVE_BLOCKER_FIELDS + ("combined_repair_routes",),
    ),
    GoldenCase(
        "combined_cleanup_required",
        _case("combined_cleanup_required", mu=55.0, vu=20.0, recipe="OPT_EXPECT_COMBINED_SAFE_OVERDESIGNED", base=COMMON_HEAVY_REO),
        (),
        ("bending", "shear"),
        "combined",
        ("combined", "geometry", "bottom reinforcement", "links", "no links"),
        ("green accepted", "exact low-util blocker terminal"),
        REQUIRED_LOW_UTIL_BLOCKER_FIELDS,
    ),
]


@dataclass
class CaseRun:
    case_name: str
    command: list[str]
    replay_path: str
    artifact_dir: str
    status: str
    returncode: int | None
    elapsed_sec: float
    failure_classification: str = ""
    product_verifier_unknown: str = ""
    exact_contract_broken: str = ""
    visible_card_title: str = ""
    visible_card_status: str = ""
    visible_card_colour: str = ""
    summary_utilisation_values: dict[str, Any] | None = None
    active_fail_families: list[str] | None = None
    low_util_families: list[str] | None = None
    clicked_candidate_id: str = ""
    expected_updates: dict[str, Any] | None = None
    actual_changed_keys: list[str] | None = None
    blocker_evidence_by_family: dict[str, Any] | None = None
    screenshots: dict[str, Any] | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""


def _now_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H-%M-%S")


def _tail(text: str, *, lines: int = 120) -> str:
    return "\n".join(str(text or "").splitlines()[-lines:])


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")


def _port_owner_snapshot(port: int) -> dict[str, Any]:
    script = rf"""
    $port = {int(port)}
    $conns = @(Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue)
    $owners = @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
    $items = @()
    foreach($owner in $owners) {{
      if($owner) {{
        try {{
          $proc = Get-Process -Id $owner -ErrorAction Stop
          $items += [pscustomobject]@{{
            pid = $owner
            process_name = $proc.ProcessName
            working_set_mb = [math]::Round($proc.WorkingSet64 / 1MB, 1)
          }}
        }} catch {{
          $items += [pscustomobject]@{{ pid = $owner; process_name = ""; working_set_mb = $null }}
        }}
      }}
    }}
    $related = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {{
      $_.ProcessName -match 'python|chrome|node'
    }} | Measure-Object -Property WorkingSet64 -Sum)
    [pscustomobject]@{{
      port = $port
      owner_pids = $owners
      owners = $items
      related_process_working_set_mb = if($related.Sum) {{ [math]::Round($related.Sum / 1MB, 1) }} else {{ 0 }}
    }} | ConvertTo-Json -Compress -Depth 5
    """
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            return data if isinstance(data, dict) else {"port": port, "owners": data}
        return {"port": port, "error": (proc.stderr or proc.stdout or "").strip()[:500]}
    except Exception as exc:
        return {"port": port, "error": f"{type(exc).__name__}: {exc}"}


def _case_artifact_teardown_summary(case_artifact_dir: Path) -> dict[str, Any]:
    timeline = _read_json(case_artifact_dir / "playwright_lifecycle_timeline.json")
    events = list((timeline or {}).get("events") or []) if isinstance(timeline, dict) else []
    stages = [str(item.get("stage") or "") for item in events if isinstance(item, dict)]
    teardown_done = next((item for item in reversed(events) if isinstance(item, dict) and item.get("stage") == "teardown_done"), {})
    route_gate = _read_json(case_artifact_dir / "inputs_content_ready_gate.json")
    setup_mode = _read_json(case_artifact_dir / "replay_input_setup_mode.json")
    return {
        "artifact_dir": _repo_rel(case_artifact_dir),
        "cleanup_completed": "teardown_done" in stages,
        "teardown_started": "teardown_start" in stages,
        "teardown_done_page_exists": teardown_done.get("page_exists") if isinstance(teardown_done, dict) else None,
        "teardown_done_context_exists": teardown_done.get("context_exists") if isinstance(teardown_done, dict) else None,
        "teardown_done_browser_exists": teardown_done.get("browser_exists") if isinstance(teardown_done, dict) else None,
        "route_mounted_before_setup": bool((route_gate or {}).get("ready")) if isinstance(route_gate, dict) else None,
        "route_gate_reason": (route_gate or {}).get("reason") if isinstance(route_gate, dict) else None,
        "input_setup_final_classification": (setup_mode or {}).get("final_setup_classification") if isinstance(setup_mode, dict) else "",
        "input_setup_locator_recreation_count": (setup_mode or {}).get("locator_recreation_count") if isinstance(setup_mode, dict) else None,
        "input_setup_stale_locator_detection": (setup_mode or {}).get("stale_locator_detection") if isinstance(setup_mode, dict) else None,
    }


def _golden_sequence_state(
    *,
    port: int,
    case_name: str,
    case_index: int,
    phase: str,
    prior_case_name: str,
    prior_case_result: str,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "phase": phase,
        "case_name": case_name,
        "case_index": case_index,
        "prior_case_name": prior_case_name,
        "prior_case_result": prior_case_result,
        "runner_pid": os.getpid(),
        "port_owner": _port_owner_snapshot(port),
        "artifact_dir": _repo_rel(artifact_dir) if artifact_dir else "",
    }


def _write_replay(case: GoldenCase, case_index: int, replay_dir: Path) -> Path:
    replay = {
        "seed": 20260510,
        "case_index": case_index,
        "golden_matrix_case": case.case_name,
        "initial_inputs": {**case.initial_inputs, "case_index": case_index},
        "expected_initial_failing_families": list(case.expected_initial_failing_families),
        "expected_initial_low_util_families": list(case.expected_initial_low_util_families),
        "expected_first_action_family": case.expected_first_action_family,
        "required_search_families": list(case.required_search_families),
        "allowed_final_states": list(case.allowed_final_states),
        "blocker_evidence_requirements": list(case.blocker_evidence_requirements),
        "post_click_ordinary_blue_action_allowed": case.post_click_ordinary_blue_action_allowed,
    }
    replay_dir.mkdir(parents=True, exist_ok=True)
    path = replay_dir / f"{case.case_name}.json"
    path.write_text(json.dumps(replay, indent=2), encoding="utf-8")
    return path


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


def _screenshots_md(run: CaseRun) -> list[str]:
    screenshots = dict(run.screenshots or {})
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


def _latest_step_from_failure(failure: dict[str, Any]) -> dict[str, Any]:
    step = failure.get("expected_failure_step")
    if isinstance(step, dict):
        return step
    step = failure.get("step")
    if isinstance(step, dict):
        return step
    timeline = failure.get("timeline")
    if isinstance(timeline, list):
        for item in reversed(timeline):
            if isinstance(item, dict):
                return item
    return {}


def _family_utils(summary: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for family in ("bending", "shear", "crack", "deflection"):
        row = summary.get(family)
        if isinstance(row, dict):
            out[family] = row.get("util") or row.get("utilisation") or row.get("value")
    return out


def _families_by_status(summary: dict[str, Any], status: str) -> list[str]:
    families: list[str] = []
    for family in ("bending", "shear", "crack", "deflection"):
        row = summary.get(family)
        if isinstance(row, dict) and str(row.get("status") or "").upper() == status:
            families.append(family)
    return families


def _low_util_families(summary: dict[str, Any]) -> list[str]:
    families: list[str] = []
    for family in ("bending", "shear"):
        value = _family_utils(summary).get(family)
        try:
            if value is not None and float(value) < 0.85 and family not in _families_by_status(summary, "FAIL"):
                families.append(family)
        except Exception:
            pass
    return families


def _attach_failure_details(run: CaseRun, output: str) -> None:
    for payload in reversed(_json_objects(output)):
        failure = _first_failure(payload)
        if not failure:
            continue
        diagnosis = failure.get("diagnosis") if isinstance(failure.get("diagnosis"), dict) else {}
        step = _latest_step_from_failure(failure)
        card = dict(step.get("visible_design_guide") or {})
        summary = dict(step.get("visible_summary") or {})
        audit = dict(step.get("one_click_material_change_audit") or {})
        run.failure_classification = str(
            failure.get("failure_classification")
            or failure.get("classification")
            or diagnosis.get("classification")
            or payload.get("verdict")
            or "golden_matrix_case_failed"
        )
        run.product_verifier_unknown = str(
            "product bug"
            if diagnosis.get("product_bug_likely") is True
            else "verifier-only issue"
            if diagnosis.get("verifier_bug_likely") is True
            else failure.get("product_verifier_unknown")
            or failure.get("classification_kind")
            or "unknown/infrastructure"
        )
        run.exact_contract_broken = str(
            diagnosis.get("exact_contradiction")
            or failure.get("failure_message")
            or failure.get("message")
            or payload.get("error")
            or "Golden matrix case failed without a parsed contract message."
        )
        run.visible_card_title = str(card.get("title") or card.get("title_main") or "")
        run.visible_card_status = str(card.get("status") or "")
        run.visible_card_colour = str(card.get("colour") or card.get("color") or "")
        run.summary_utilisation_values = _family_utils(summary)
        run.active_fail_families = _families_by_status(summary, "FAIL")
        run.low_util_families = _low_util_families(summary)
        run.clicked_candidate_id = str(audit.get("clicked_candidate_id") or card.get("candidate_id") or "")
        run.expected_updates = dict(audit.get("expected_updates") or card.get("selected_action_updates") or {})
        run.actual_changed_keys = list(audit.get("changed_keys") or [])
        blockers = card.get("blocker_attempts_by_family") or card.get("exact_blockers_by_family") or {}
        run.blocker_evidence_by_family = dict(blockers) if isinstance(blockers, dict) else {}
        run.screenshots = _screenshot_fields(failure) or _screenshot_fields(payload)
        return
    run.failure_classification = run.failure_classification or "runner_failed"
    run.product_verifier_unknown = run.product_verifier_unknown or "unknown/infrastructure"
    run.exact_contract_broken = run.exact_contract_broken or "Runner exited non-zero; no structured failure payload parsed."


def _run_case(case: GoldenCase, case_index: int, *, port: int, timestamp: str, timeout_sec: int, headed: bool) -> CaseRun:
    replay_dir = ARTIFACT_DIR / timestamp / "replays"
    case_artifact_dir = ARTIFACT_DIR / timestamp / case.case_name
    replay_path = _write_replay(case, case_index, replay_dir)
    cmd = [
        sys.executable,
        "tools/browser_live_design_guide_fuzz_verifier.py",
        "--replay-case",
        str(replay_path),
        "--port",
        str(port),
        "--artifact-dir",
        str(case_artifact_dir),
    ]
    cmd.append("--headed" if headed else "--headless")
    started = time.perf_counter()
    try:
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=timeout_sec)  # noqa: S603
        run = CaseRun(
            case_name=case.case_name,
            command=cmd,
            replay_path=_repo_rel(replay_path),
            artifact_dir=_repo_rel(case_artifact_dir),
            status="PASS" if proc.returncode == 0 else "FAIL",
            returncode=proc.returncode,
            elapsed_sec=round(time.perf_counter() - started, 3),
            stdout_tail=_tail(proc.stdout or ""),
            stderr_tail=_tail(proc.stderr or ""),
        )
        if proc.returncode != 0:
            _attach_failure_details(run, (proc.stdout or "") + "\n" + (proc.stderr or ""))
        return run
    except subprocess.TimeoutExpired as exc:
        return CaseRun(
            case_name=case.case_name,
            command=cmd,
            replay_path=_repo_rel(replay_path),
            artifact_dir=_repo_rel(case_artifact_dir),
            status="TIMEOUT",
            returncode=None,
            elapsed_sec=round(time.perf_counter() - started, 3),
            failure_classification="timeout",
            product_verifier_unknown="unknown/infrastructure",
            exact_contract_broken=f"Golden matrix case timed out after {timeout_sec}s.",
            stdout_tail=_tail(exc.stdout or "" if isinstance(exc.stdout, str) else ""),
            stderr_tail=_tail(exc.stderr or "" if isinstance(exc.stderr, str) else ""),
        )


def _write_report(timestamp: str, runs: list[CaseRun]) -> tuple[Path, Path, dict[str, Any]]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    failed = [run for run in runs if run.status != "PASS"]
    passed = [run for run in runs if run.status == "PASS"]
    first_failed = failed[0] if failed else None
    source_fingerprint = compute_source_fingerprint(repo=REPO)
    payload = {
        "generated_at": timestamp,
        "status": "PASS" if not failed else "FAIL",
        "golden_matrix_required_gate": True,
        "source_fingerprint": source_fingerprint,
        "correctness_fingerprint": source_fingerprint.get("correctness_fingerprint"),
        "diagnostic_fingerprint": source_fingerprint.get("diagnostic_fingerprint"),
        "verifier_runtime_fingerprint": source_fingerprint.get("verifier_runtime_fingerprint"),
        "invalidation_reason": None,
        "full_gate_required": True,
        "total_cases": len(GOLDEN_CASES),
        "passed_cases": len(passed),
        "failed_cases": len(failed),
        "skipped_missing_cases": 0,
        "pass_rate_percent": round((len(passed) / len(GOLDEN_CASES)) * 100.0, 2) if GOLDEN_CASES else 0.0,
        "first_failing_case": first_failed.case_name if first_failed else "",
        "cases_defined": [asdict(case) for case in GOLDEN_CASES],
        "results": [asdict(run) for run in runs],
    }
    json_path = ARTIFACT_DIR / f"golden_matrix_{timestamp}.json"
    md_path = ARTIFACT_DIR / f"golden_matrix_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Design Guide Golden Matrix Gate",
        "",
        f"- Generated: `{timestamp}`",
        f"- Status: **{payload['status']}**",
        f"- Total cases: `{payload['total_cases']}`",
        f"- Passed cases: `{payload['passed_cases']}`",
        f"- Failed cases: `{payload['failed_cases']}`",
        f"- Skipped/missing cases: `{payload['skipped_missing_cases']}`",
        f"- Pass rate: `{payload['pass_rate_percent']}%`",
        f"- First failing case: `{payload['first_failing_case']}`",
        "",
        "## Results",
        "",
        "| Case | Status | Failure classification | Expected result | Actual result | Contract broken | Visible card | Replay command |",
        "|---|---:|---|---|---|---|---|---|",
    ]
    cases_by_name = {case.case_name: case for case in GOLDEN_CASES}
    for run in runs:
        case = cases_by_name[run.case_name]
        lines.append(
            "| "
            + " | ".join(
                [
                    run.case_name,
                    run.status,
                    run.failure_classification,
                    ", ".join(case.allowed_final_states),
                    run.status if run.status == "PASS" else run.failure_classification,
                    run.exact_contract_broken,
                    f"{run.visible_card_title} / {run.visible_card_status} / {run.visible_card_colour}",
                    f"`{' '.join(run.command)}`",
                ]
            )
            + " |"
        )
    if failed:
        lines.extend(["", "## Failed Cases", ""])
        for run in failed:
            case = cases_by_name[run.case_name]
            lines.extend(
                [
                    f"### {run.case_name}",
                    f"- Replay command: `{' '.join(run.command)}`",
                    f"- Expected result: `{', '.join(case.allowed_final_states)}`",
                    f"- Actual result: `{run.failure_classification or run.status}`",
                    f"- Exact contract broken: {run.exact_contract_broken}",
                    f"- Visible card title/status/colour: `{run.visible_card_title}` / `{run.visible_card_status}` / `{run.visible_card_colour}`",
                    f"- Summary utilisation values: `{json.dumps(run.summary_utilisation_values or {}, default=str)}`",
                    f"- Active fail families: `{run.active_fail_families or []}`",
                    f"- Low-util families: `{run.low_util_families or []}`",
                    f"- Clicked candidate id: `{run.clicked_candidate_id}`",
                    f"- Expected updates: `{json.dumps(run.expected_updates or {}, default=str)}`",
                    f"- Actual changed keys: `{run.actual_changed_keys or []}`",
                    f"- Blocker evidence by family: `{json.dumps(run.blocker_evidence_by_family or {}, default=str)}`",
                    f"- Product/verifier/unknown classification: `{run.product_verifier_unknown}`",
                    *_screenshots_md(run),
                    "- Suspected files/functions: `inputs_page.py`, `design_guidance_engine.py`, `tools/browser_live_design_guide_fuzz_verifier.py`",
                    "- Narrow recommended patch boundary: fix only the contract named by the failed replay; do not change formulas, solver maths, target bands, ranking, card colours, or verifier strictness.",
                    "",
                ]
            )
    lines.extend(
        [
            "## Canonical Cases Included",
            "",
            *(
                f"- `{case.case_name}`: expected failures={list(case.expected_initial_failing_families)}, "
                f"low-util={list(case.expected_initial_low_util_families)}, first action={case.expected_first_action_family}, "
                f"multi-step allowed={case.post_click_ordinary_blue_action_allowed}"
                for case in GOLDEN_CASES
            ),
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    return json_path, md_path, payload


def run_gate(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    timestamp = _now_stamp()
    runs: list[CaseRun] = []
    run_dir = ARTIFACT_DIR / timestamp
    trace_path = run_dir / "golden_sequence_state_trace.jsonl"
    reset_audit_path = run_dir / "golden_case_reset_audit.json"
    reset_audit: list[dict[str, Any]] = []
    prior_case_name = ""
    prior_case_result = ""
    for index, case in enumerate(GOLDEN_CASES):
        print(f"[golden_matrix] BEGIN {case.case_name}", flush=True)
        case_artifact_dir = ARTIFACT_DIR / timestamp / case.case_name
        start_state = _golden_sequence_state(
            port=int(args.port),
            case_name=case.case_name,
            case_index=index,
            phase="case_start",
            prior_case_name=prior_case_name,
            prior_case_result=prior_case_result,
            artifact_dir=case_artifact_dir,
        )
        _append_jsonl(trace_path, start_state)
        run = _run_case(case, index, port=int(args.port), timestamp=timestamp, timeout_sec=int(args.timeout_sec), headed=bool(args.headed))
        runs.append(run)
        teardown_summary = _case_artifact_teardown_summary(case_artifact_dir)
        end_state = _golden_sequence_state(
            port=int(args.port),
            case_name=case.case_name,
            case_index=index,
            phase="case_end",
            prior_case_name=prior_case_name,
            prior_case_result=prior_case_result,
            artifact_dir=case_artifact_dir,
        )
        end_state.update(
            {
                "result": run.status,
                "elapsed_sec": run.elapsed_sec,
                "failure_classification": run.failure_classification,
                "replay_artifact_path": run.artifact_dir,
                "cleanup_completed": teardown_summary.get("cleanup_completed"),
                "route_mounted_before_setup": teardown_summary.get("route_mounted_before_setup"),
                "input_setup_final_classification": teardown_summary.get("input_setup_final_classification"),
            }
        )
        _append_jsonl(trace_path, end_state)
        reset_audit.append(
            {
                "case_name": case.case_name,
                "case_index": index,
                "result": run.status,
                "prior_case_name": prior_case_name,
                "prior_case_result": prior_case_result,
                "replay_artifact_path": run.artifact_dir,
                "process_before": start_state.get("port_owner"),
                "process_after": end_state.get("port_owner"),
                **teardown_summary,
            }
        )
        reset_audit_path.parent.mkdir(parents=True, exist_ok=True)
        reset_audit_path.write_text(json.dumps({"cases": reset_audit}, indent=2, default=str), encoding="utf-8")
        prior_case_name = case.case_name
        prior_case_result = run.status
        print(f"[golden_matrix] END {case.case_name} {run.status} {run.elapsed_sec}s", flush=True)
    json_path, md_path, payload = _write_report(timestamp, runs)
    payload["golden_sequence_state_trace_path"] = _repo_rel(trace_path)
    payload["golden_case_reset_audit_path"] = _repo_rel(reset_audit_path)
    try:
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
    print(
        json.dumps(
            {
                "status": payload["status"],
                "json_path": str(json_path),
                "markdown_path": str(md_path),
                "golden_sequence_state_trace_path": str(trace_path),
                "golden_case_reset_audit_path": str(reset_audit_path),
                "total_cases": payload["total_cases"],
                "passed_cases": payload["passed_cases"],
                "failed_cases": payload["failed_cases"],
                "first_failing_case": payload["first_failing_case"],
            },
            indent=2,
        )
    )
    return (0 if payload["status"] == "PASS" else 1), payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the mandatory Design Guide golden matrix gate.")
    parser.add_argument("--port", type=int, default=9301)
    parser.add_argument("--timeout-sec", type=int, default=1200)
    parser.add_argument("--headed", action="store_true", default=False)
    args = parser.parse_args(argv)
    code, _ = run_gate(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
