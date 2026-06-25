"""Post render-bridge restamper cleanup readiness snapshot.

This verifier retargets duplicate restamper cleanup after the render bridge lock.
It consumes the latest reachability snapshot and render bridge lock, then
separates:

- compatibility/debug stamps,
- fallback shell support,
- compute-stage authority bridges that must stay for now,
- render-stage resolver paths covered by the render bridge lock.

It is proof-only: no deletion and no product behaviour change.
"""

from __future__ import annotations

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
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    if not matches:
        return {"path": None, "snapshot": {}, "found": False, "passed": False}
    path = matches[-1]
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "snapshot": snapshot,
        "found": True,
        "passed": snapshot.get("status") == "PASS",
    }


def _lock_summary(lock_snapshot: dict[str, Any]) -> dict[str, Any]:
    summary = dict(lock_snapshot.get("final_narrowing_summary") or {})
    if not summary:
        summary = dict(lock_snapshot.get("summary") or {})
    return {
        "remaining_live_resolver_rows": summary.get("remaining_live_resolver_rows"),
        "render_bridge_fully_narrowed": summary.get("render_bridge_fully_narrowed"),
        "product_behavior_changed": summary.get("product_behavior_changed"),
    }


def _classify(row: dict[str, Any], *, render_bridge_locked: bool) -> dict[str, Any]:
    function = str(row.get("function") or "")
    target = str(row.get("target") or "")
    reachability = str(row.get("classification") or "")
    line = int(row.get("line") or 0)

    if reachability == "compatibility stamp":
        cls = "compatibility_stamp_keep_temporarily"
        deletion_safe_now = False
        next_step = "consumer-proof before deleting compatibility/debug stamp"
        rationale = "Reachability proves this is compatibility-only, but consumers still need one-by-one deletion proof."
    elif reachability == "fallback shell support":
        cls = "fallback_shell_keep"
        deletion_safe_now = False
        next_step = "fallback-shell deletion proof only after browser/pre-render safety is separately covered"
        rationale = "Fallback shells are non-authoritative but still browser/render resilience paths."
    elif (
        render_bridge_locked
        and function == "_render_fast_design_guidance_panel"
        and target == "resolve_final_visible_design_guide_item"
    ):
        cls = "render_stage_resolver_covered_by_lock"
        deletion_safe_now = False
        next_step = "create focused render-stage resolver deletion proof"
        rationale = (
            "Render bridge lock proves render-stage selected-item mutation truth is compatibility/proof-only; "
            "delete only after a direct callsite-removal verifier."
        )
    elif function in {
        "_resolve_compute_design_guidance_publication_handoff",
        "_apply_compute_late_evidence_contract_rebound",
        "_orchestrate_compute_post_core_publication_handoff",
    }:
        cls = "compute_stage_authority_keep"
        deletion_safe_now = False
        next_step = "compute publication handoff same-object proof"
        rationale = (
            "Compute-stage handoff/rebound still selects or repairs the item before final render authority; "
            "this is not covered by the render-stage bridge lock."
        )
    else:
        cls = "unknown_keep"
        deletion_safe_now = False
        next_step = "manual proof required"
        rationale = "No current lock proves this callsite duplicate-only."

    return {
        "file": row.get("file"),
        "line": line,
        "function": function,
        "target": target,
        "reachability_classification": reachability,
        "post_render_bridge_classification": cls,
        "deletion_safe_now": deletion_safe_now,
        "recommended_next_step": next_step,
        "rationale": rationale,
        "context_hash": row.get("context_hash"),
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Post Render-Bridge Restamper Readiness",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Render bridge locked: `{payload['render_bridge_locked']}`",
        f"- Restamper callsites: `{payload['restamper_callsite_count']}`",
        f"- Deletion candidates now: `{len(payload['deletion_candidates_now'])}`",
        f"- Next safe step: `{payload['next_safe_step']}`",
        "",
        "## Classification Counts",
        "",
    ]
    for key, value in sorted(payload["classification_counts"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Callsites", "", "| Line | Function | Target | Classification | Next |", "| --- | --- | --- | --- | --- |"])
    for row in payload["classified_callsites"]:
        lines.append(
            "| {line} | `{function}` | `{target}` | `{classification}` | {next_step} |".format(
                line=row["line"],
                function=row["function"],
                target=row["target"],
                classification=row["post_render_bridge_classification"],
                next_step=str(row["recommended_next_step"]).replace("|", "\\|"),
            )
        )
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    reachability_run = _run("tools/verification/design_guide_duplicate_restamper_reachability_snapshot.py")
    render_bridge_run = _run("tools/verification/design_guide_render_bridge_lock_verifier.py")
    reachability = _latest("design_guide_duplicate_restamper_reachability")
    render_lock = _latest("design_guide_render_bridge_lock")

    reachability_snapshot = dict(reachability.get("snapshot") or {})
    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    render_resolver_replaced = bool(
        "_final_visible_resolution = _final_visible_resolution_from_final_publication_authority(" in input_source
        and "_final_visible_resolution = resolve_final_visible_design_guide_item(" not in input_source
    )
    lock = _lock_summary(dict(render_lock.get("snapshot") or {}))
    render_bridge_locked = bool(
        render_bridge_run["passed"]
        and render_lock["passed"]
        and lock.get("render_bridge_fully_narrowed") is True
        and int(lock.get("remaining_live_resolver_rows") or 0) == 0
    )
    callsites = [dict(row) for row in list(reachability_snapshot.get("callsites") or []) if isinstance(row, dict)]
    classified = [_classify(row, render_bridge_locked=render_bridge_locked) for row in callsites]
    counts: dict[str, int] = {}
    for row in classified:
        key = str(row["post_render_bridge_classification"])
        counts[key] = counts.get(key, 0) + 1
    deletion_candidates = [row for row in classified if row["deletion_safe_now"]]
    compute_stage_keep = [row for row in classified if row["post_render_bridge_classification"] == "compute_stage_authority_keep"]
    render_stage_candidate = [
        row for row in classified if row["post_render_bridge_classification"] == "render_stage_resolver_covered_by_lock"
    ]

    failures: list[str] = []
    if not reachability_run["passed"] or not reachability["passed"]:
        failures.append("duplicate_restamper_reachability_failed")
    if not render_bridge_locked:
        failures.append("render_bridge_lock_not_current_or_not_fully_narrowed")
    expected_callsite_count = 11 if render_resolver_replaced else 12
    if len(callsites) != expected_callsite_count:
        failures.append(f"expected_{expected_callsite_count}_restamper_callsites_found_{len(callsites)}")
    if len(compute_stage_keep) != 3:
        failures.append(f"expected_3_compute_stage_authority_kept_found_{len(compute_stage_keep)}")
    expected_render_stage_candidates = 0 if render_resolver_replaced else 1
    if len(render_stage_candidate) != expected_render_stage_candidates:
        failures.append(
            f"expected_{expected_render_stage_candidates}_render_stage_lock_covered_candidate_found_{len(render_stage_candidate)}"
        )

    payload = {
        "schema": "design_guide_post_render_bridge_restamper_readiness.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "reachability_run": reachability_run,
        "render_bridge_run": render_bridge_run,
        "source_reachability_artifact": reachability.get("path"),
        "source_render_bridge_lock_artifact": render_lock.get("path"),
        "render_bridge_lock_summary": lock,
        "render_bridge_locked": render_bridge_locked,
        "render_resolver_replaced_by_publication_authority_adapter": render_resolver_replaced,
        "restamper_callsite_count": len(callsites),
        "classification_counts": counts,
        "classified_callsites": classified,
        "deletion_candidates_now": deletion_candidates,
        "compute_stage_authority_kept": compute_stage_keep,
        "render_stage_lock_covered_candidates": render_stage_candidate,
        "next_safe_step": (
            "delete first safe candidate"
            if deletion_candidates
            else (
                "focused render-stage resolver deletion proof"
                if render_stage_candidate
                else "compute publication handoff same-object proof"
            )
        ),
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(
            {
                "render_bridge_locked": render_bridge_locked,
                "counts": counts,
                "classified": classified,
            }
        ),
    }
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_guide_post_render_bridge_restamper_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_post_render_bridge_restamper_readiness_{stamp}.md"
    payload["artifact"] = str(artifact_path)
    payload["report"] = str(report_path)
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"{payload['status']}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
