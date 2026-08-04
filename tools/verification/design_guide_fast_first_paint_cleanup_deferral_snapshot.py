"""Proof snapshot for Fast Design Guide first-paint cleanup proof deferral.

This verifier is proof-only. It confirms that expensive exact cleanup probes are
deferred only during Fast first paint, that the deferral is source-guarded at
the approved callsites, and that the latest live loading-shell profile still
settles to a real final Design Guide card with browser-state proof.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

APPROVED_PROBES = {
    "accepted_green_shear_low_util_blocker_probe": "_shear_low_util_active_links_exact_blocker",
    "post_active_strength_repair_residual_shear_target_band_probe": "_post_active_repair_residual_shear_exact_blocker",
    "design_guide_bending_only_cleanup_search": "_bending_only_target_band_cleanup_item",
}


def _latest_json(prefix: str) -> dict[str, Any]:
    matches = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        return {}
    try:
        return json.loads(matches[0].read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_trace_counts() -> dict[str, Any]:
    trace_dir = ROOT / "artifacts" / "performance"
    matches = sorted(
        trace_dir.glob("inputs_pre_widget_trace_*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        return {"path": None, "deferred_probe_count": 0, "probe_names": {}}
    latest = matches[0]
    names: Counter[str] = Counter()
    total = 0
    with latest.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("block") != "design_guide.fast_first_paint_deferred_cleanup_probe":
                continue
            total += 1
            name = str(row.get("probe_name") or "").strip()
            if name:
                names[name] += 1
    return {
        "path": str(latest),
        "deferred_probe_count": total,
        "probe_names": dict(sorted(names.items())),
    }


def _function_body(source: str, function_name: str) -> str:
    start = source.find(f"def {function_name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    return source[start:] if next_def < 0 else source[start:next_def]


def _source_checks() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="ignore")
    helper_present = "def _defer_expensive_cleanup_exact_proof_for_fast_render()" in source
    fast_flag_present = '"_design_guide_fast_first_paint_render_active"' in source
    checks: dict[str, Any] = {}
    for probe_name, function_name in APPROVED_PROBES.items():
        body = _function_body(source, function_name)
        checks[function_name] = {
            "function_found": bool(body),
            "uses_fast_first_paint_deferral": "_defer_expensive_cleanup_exact_proof_for_fast_render()" in body,
            "emits_deferred_probe_trace": "design_guide.fast_first_paint_deferred_cleanup_probe" in body,
            "emits_expected_probe_name": probe_name in body,
            "returns_none_on_defer": "return None" in body,
        }
    return {
        "helper_present": helper_present,
        "fast_first_paint_flag_present": fast_flag_present,
        "approved_probe_checks": checks,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Fast First-Paint Cleanup Deferral Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Summary",
        "",
        f"- Source guards complete: `{payload['summary']['source_guards_complete']}`",
        f"- Live deferred probes seen: `{payload['summary']['live_deferred_probes_seen']}`",
        f"- Loading-shell profile PASS: `{payload['summary']['loading_shell_profile_pass']}`",
        f"- Final card seen: `{payload['summary']['final_card_seen']}`",
        f"- Browser-state seen: `{payload['summary']['browser_state_seen']}`",
        "",
        "## Probe Counts",
        "",
    ]
    for name, count in dict(payload.get("trace_counts", {}).get("probe_names") or {}).items():
        lines.append(f"- `{name}`: `{count}`")
    lines.extend(["", "## Failures", ""])
    failures = list(payload.get("failures") or [])
    lines.append("None" if not failures else "\n".join(f"- `{failure}`" for failure in failures))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source_checks = _source_checks()
    trace_counts = _latest_trace_counts()
    profile = _latest_json("design_guide_loading_shell_completion_profile")
    classification = dict(profile.get("classification") or {})

    approved_checks = dict(source_checks.get("approved_probe_checks") or {})
    source_guards_complete = bool(
        source_checks.get("helper_present")
        and source_checks.get("fast_first_paint_flag_present")
        and approved_checks
        and all(all(check.values()) for check in approved_checks.values())
    )
    live_probe_names = set(dict(trace_counts.get("probe_names") or {}).keys())
    live_deferred_probes_seen = bool(live_probe_names.intersection(APPROVED_PROBES.keys()))
    loading_shell_profile_pass = bool(profile.get("status") == "PASS")
    final_card_seen = bool(classification.get("final_card_seen"))
    browser_state_seen = bool(classification.get("browser_state_seen"))
    loading_shell_last = bool(classification.get("loading_shell_last"))

    failures: list[str] = []
    if not source_guards_complete:
        failures.append("source_guards_incomplete")
    if not live_deferred_probes_seen:
        failures.append("live_deferred_probes_not_seen")
    if not loading_shell_profile_pass:
        failures.append("latest_loading_shell_profile_not_pass")
    if not final_card_seen:
        failures.append("latest_loading_shell_profile_missing_final_card")
    if not browser_state_seen:
        failures.append("latest_loading_shell_profile_missing_browser_state")
    if loading_shell_last:
        failures.append("latest_loading_shell_profile_still_in_loading_shell")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_fast_first_paint_cleanup_deferral_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "product_behaviour_changed": False,
        "summary": {
            "source_guards_complete": source_guards_complete,
            "live_deferred_probes_seen": live_deferred_probes_seen,
            "loading_shell_profile_pass": loading_shell_profile_pass,
            "final_card_seen": final_card_seen,
            "browser_state_seen": browser_state_seen,
            "loading_shell_last": loading_shell_last,
        },
        "source_checks": source_checks,
        "trace_counts": trace_counts,
        "latest_loading_shell_profile": {
            "status": profile.get("status"),
            "created_at": profile.get("created_at"),
            "target_url": profile.get("target_url"),
            "classification": classification,
        },
        "approved_probes": dict(APPROVED_PROBES),
        "failures": failures,
    }
    artifact_path = ARTIFACT_DIR / f"design_guide_fast_first_paint_cleanup_deferral_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_fast_first_paint_cleanup_deferral_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": status,
                "artifact": str(artifact_path),
                "report": str(report_path),
                "failures": failures,
            },
            indent=2,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
