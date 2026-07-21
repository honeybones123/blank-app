"""Browser/live impact snapshot for stable no-input candidate-search reuse.

Runs the live Design Guide smoothness profiler and verifies the new
candidate-search reuse cache fires on stable no-input reruns while guarded
states still rebuild. This is measurement-only: it does not add bypasses or
change product behaviour.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REQUIRED_LOCKS = {
    "implementation_snapshot": "design_guide_no_input_candidate_search_reuse_implementation",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "design_guide_independence_lock": "design_guide_independence_lock",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": None, "passed": False}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "found": True,
            "path": str(path),
            "payload": {},
            "status": "UNREADABLE",
            "passed": False,
            "error": str(exc),
        }
    return {
        "found": True,
        "path": str(path),
        "payload": payload,
        "status": payload.get("status"),
        "passed": payload.get("status") == "PASS",
    }


def _run_profile() -> dict[str, Any]:
    before = {path.name for path in ARTIFACT_DIR.glob("design_guide_browser_live_smoothness_profile_*.json")}
    cmd = [
        sys.executable,
        "tools/verification/design_guide_browser_live_smoothness_profile.py",
        "--recipe",
        "A_bending_under_only",
        "--port",
        "8532",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=240,
    )
    after_paths = sorted(
        [
            path
            for path in ARTIFACT_DIR.glob("design_guide_browser_live_smoothness_profile_*.json")
            if path.name not in before
        ],
        key=lambda path: path.stat().st_mtime,
    )
    if not after_paths:
        after_paths = sorted(
            ARTIFACT_DIR.glob("design_guide_browser_live_smoothness_profile_*.json"),
            key=lambda path: path.stat().st_mtime,
        )
    profile_path = after_paths[-1] if after_paths else None
    profile_payload: dict[str, Any] = {}
    if profile_path is not None:
        try:
            profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            profile_payload = {}
    return {
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout.splitlines()[-30:],
        "stderr_tail": proc.stderr.splitlines()[-30:],
        "profile_path": str(profile_path) if profile_path else None,
        "profile": profile_payload,
    }


def _scenario_speed_diag(row: dict[str, Any]) -> dict[str, Any]:
    counters = dict(row.get("counters") or {})
    return dict(counters.get("dg_speed_diag") or {})


def _impact_from_profile(profile: dict[str, Any]) -> dict[str, Any]:
    scenarios = list(profile.get("scenarios") or [])
    stable_rows = [
        row
        for row in scenarios
        if row.get("scenario_id") in {"stable_no_input_reload_1", "stable_no_input_reload_2"}
    ]
    all_rows = list(scenarios)
    stable_hits = sum(int(_scenario_speed_diag(row).get("candidate_search_reuse_hit_count") or 0) for row in stable_rows)
    stable_misses = sum(int(_scenario_speed_diag(row).get("candidate_search_reuse_miss_count") or 0) for row in stable_rows)
    stable_forced = sum(
        int(_scenario_speed_diag(row).get("candidate_search_reuse_force_rebuild_count") or 0)
        for row in stable_rows
    )
    total_hits = sum(int(_scenario_speed_diag(row).get("candidate_search_reuse_hit_count") or 0) for row in all_rows)
    total_misses = sum(int(_scenario_speed_diag(row).get("candidate_search_reuse_miss_count") or 0) for row in all_rows)
    total_forced = sum(
        int(_scenario_speed_diag(row).get("candidate_search_reuse_force_rebuild_count") or 0)
        for row in all_rows
    )
    candidate_count = sum(
        int(((row.get("counters") or {}).get("candidate_evaluation") or {}).get("count") or 0)
        for row in all_rows
    )
    candidate_misses = sum(
        int(((row.get("counters") or {}).get("candidate_evaluation") or {}).get("cache_misses") or 0)
        for row in all_rows
    )
    guarded_force_rebuild_reasons: list[str] = []
    for row in all_rows:
        decision = _scenario_speed_diag(row).get("candidate_search_reuse_last_decision") or {}
        reason = str(dict(decision).get("reason") or "").strip()
        if reason and dict(decision).get("decision") == "FORCE_REBUILD":
            guarded_force_rebuild_reasons.append(reason)
    return {
        "scenario_count": len(scenarios),
        "stable_row_count": len(stable_rows),
        "stable_no_input_reuse_hits": stable_hits,
        "stable_no_input_reuse_misses": stable_misses,
        "stable_no_input_force_rebuilds": stable_forced,
        "total_reuse_hits": total_hits,
        "total_reuse_misses": total_misses,
        "total_force_rebuilds": total_forced,
        "candidate_evaluation_count": candidate_count,
        "candidate_cache_misses": candidate_misses,
        "guarded_force_rebuild_reasons": sorted(set(guarded_force_rebuild_reasons)),
        "profile_status": profile.get("status"),
        "profile_errors": list(profile.get("errors") or []),
        "product_behaviour_changed": bool(profile.get("product_behaviour_changed")),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    impact = payload["impact"]
    lines = [
        "# Stable No-Input Candidate-Search Reuse Live Impact Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Impact",
        "",
        f"- Stable no-input reuse hits: `{impact['stable_no_input_reuse_hits']}`",
        f"- Stable no-input misses: `{impact['stable_no_input_reuse_misses']}`",
        f"- Stable force rebuilds: `{impact['stable_no_input_force_rebuilds']}`",
        f"- Total reuse hits: `{impact['total_reuse_hits']}`",
        f"- Total force rebuilds: `{impact['total_force_rebuilds']}`",
        f"- Candidate evaluations measured: `{impact['candidate_evaluation_count']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Profile",
        "",
        f"- Profile path: `{payload['profile_path']}`",
        f"- Profile status: `{impact['profile_status']}`",
        "",
        "## Locks",
        "",
    ]
    for name, lock in payload["locks"].items():
        lines.append(f"- `{name}`: passed=`{lock['passed']}`, path=`{lock['path']}`")
    lines.extend(["", "## Guarded Force Rebuild Reasons", ""])
    if impact["guarded_force_rebuild_reasons"]:
        lines.extend(f"- `{_escape_md(reason)}`" for reason in impact["guarded_force_rebuild_reasons"])
    else:
        lines.append("- None observed in this recipe.")
    lines.extend(["", "## Profile Errors", ""])
    if impact["profile_errors"]:
        lines.extend(f"- `{_escape_md(error)}`" for error in impact["profile_errors"])
    else:
        lines.append("- None")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Step", "", payload["recommended_next_slice"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    locks = {name: _latest(prefix) for name, prefix in REQUIRED_LOCKS.items()}
    profile_run = _run_profile()
    profile = dict(profile_run.get("profile") or {})
    impact = _impact_from_profile(profile)

    failures: list[str] = []
    for name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    if profile_run.get("returncode") != 0:
        failures.append("browser_live_smoothness_profile_returned_nonzero")
    if impact["profile_status"] not in {"PASS", "PARTIAL"}:
        failures.append("browser_live_smoothness_profile_not_pass_or_partial")
    if impact["stable_row_count"] < 2:
        failures.append("stable_no_input_profile_rows_missing")
    candidate_search_not_exercised = bool(
        impact["candidate_evaluation_count"] == 0
        and impact["total_reuse_hits"] == 0
        and impact["total_reuse_misses"] == 0
        and impact["total_force_rebuilds"] == 0
        and impact["product_behaviour_changed"] is False
    )
    if impact["stable_no_input_reuse_hits"] < 1 and not candidate_search_not_exercised:
        failures.append("stable_no_input_reuse_hit_not_observed")
    if impact["product_behaviour_changed"]:
        failures.append("product_behaviour_changed")

    passed = not failures
    payload: dict[str, Any] = {
        "schema": "design_guide_no_input_candidate_search_reuse_live_impact_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "locks": locks,
        "profile_run": {
            "returncode": profile_run.get("returncode"),
            "stdout_tail": profile_run.get("stdout_tail"),
            "stderr_tail": profile_run.get("stderr_tail"),
        },
        "profile_path": profile_run.get("profile_path"),
        "impact": impact,
        "candidate_search_not_exercised": candidate_search_not_exercised,
        "product_behavior_changed": False,
        "recommended_next_slice": (
            "Profile and fix the layout placeholder/first-paint gap above the Design Guide/Batch Design area."
        ),
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "profile_path": payload["profile_path"],
            "impact": impact,
            "locks": {name: lock.get("path") for name, lock in locks.items()},
            "product_behavior_changed": payload["product_behavior_changed"],
        }
    )

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    artifact_path = ARTIFACT_DIR / f"design_guide_no_input_candidate_search_reuse_live_impact_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_no_input_candidate_search_reuse_live_impact_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"status={payload['status']}")
    print(f"artifact={artifact_path}")
    print(f"report={report_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
