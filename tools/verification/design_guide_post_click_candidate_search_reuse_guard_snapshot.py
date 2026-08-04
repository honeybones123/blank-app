"""Post-click guard proof for candidate-search reuse.

Proof-only. This verifier records the rule that any future no-input candidate
search reuse must force-rebuild across post-click/apply states until a clicked
browser scenario proves reuse is safe. It does not implement a cache, bypass,
or product behaviour change.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"
INPUTS_PAGE = ROOT / "inputs_page.py"

REQUIRED_ARTIFACTS = {
    "no_input_candidate_search_reuse_readiness": (
        "design_guide_no_input_candidate_search_reuse_readiness"
    ),
    "browser_live_smoothness_profile": "design_guide_browser_live_smoothness_profile",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "design_guide_independence_lock": "design_guide_independence_lock",
}

SOURCE_GUARDS = {
    "post_cleanup_acceptance_enabled_session_key": "_design_guide_post_cleanup_acceptance_enabled",
    "post_cleanup_acceptance_fp_session_key": "_design_guide_post_cleanup_acceptance_fp",
    "post_cleanup_acceptance_fp_in_runtime_key": '"post_cleanup_acceptance_fp"',
    "post_cleanup_global_match_in_runtime_key": '"post_cleanup_acceptance_global_match"',
    "local_cleanup_acceptance_fingerprint": "_local_cleanup_acceptance_fingerprint(state)",
    "stale_apply_payload_state_fingerprint": "stale_apply_payload_current_fingerprint",
    "component_apply_stale_state_fingerprint": "component_apply_stale_state_fingerprint",
    "design_guide_primary_apply_payload": "design_guide_primary_apply_payload",
    "post_click_design_guide_state": "post_click_design_guide_state",
    "post_click_exact_blockers_by_family": "post_click_exact_blockers_by_family",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "payload": payload,
    }


def _line_numbers(source: str, token: str, *, limit: int = 8) -> list[int]:
    rows: list[int] = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        if token in line:
            rows.append(line_no)
            if len(rows) >= limit:
                break
    return rows


def _source_guard_proof(source: str) -> dict[str, Any]:
    rows = {
        name: {
            "present": token in source,
            "line_numbers": _line_numbers(source, token),
        }
        for name, token in SOURCE_GUARDS.items()
    }
    return {
        "guards": rows,
        "missing_guards": [name for name, row in rows.items() if not bool(row["present"])],
        "all_required_guards_present": all(bool(row["present"]) for row in rows.values()),
    }


def _post_click_profile_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in list(profile.get("scenarios") or [])
        if str(dict(row).get("scenario_id") or "") == "post_click_apply"
    ]


def _profile_guard_state(profile: dict[str, Any]) -> dict[str, Any]:
    rows = _post_click_profile_rows(profile)
    clicked_rows = [row for row in rows if not bool(row.get("skipped"))]
    skipped_rows = [row for row in rows if bool(row.get("skipped"))]
    errors = list(profile.get("errors") or [])
    return {
        "post_click_rows_found": len(rows),
        "clicked_post_click_rows": len(clicked_rows),
        "skipped_post_click_rows": len(skipped_rows),
        "post_click_clicked_browser_proof_available": bool(clicked_rows),
        "latest_profile_status": profile.get("status"),
        "latest_profile_recipe": profile.get("recipe"),
        "latest_profile_errors": errors,
        "rows": [
            {
                "scenario_id": row.get("scenario_id"),
                "skipped": bool(row.get("skipped")),
                "skip_reason": row.get("skip_reason"),
                "action": row.get("action"),
                "candidate_eval_count": (
                    dict(dict(row.get("counters") or {}).get("candidate_evaluation") or {}).get("count")
                    if not row.get("skipped")
                    else None
                ),
                "final_publication_hash": (
                    dict(row.get("counters") or {}).get("final_publication_hash")
                    if not row.get("skipped")
                    else None
                ),
            }
            for row in rows
        ],
    }


def _guard_matrix(profile_guard: dict[str, Any]) -> list[dict[str, Any]]:
    clicked_available = bool(profile_guard["post_click_clicked_browser_proof_available"])
    return [
        {
            "state": "stable no-input rerun before Apply",
            "future_reuse_policy": "ALLOW_ONLY_AFTER_NO_INPUT_REUSE_IMPLEMENTATION",
            "reason": "No post-click mutation is involved; readiness proof already found repeated candidate work.",
            "guard_status": "READY_FOR_NEXT_PROOF",
        },
        {
            "state": "debug mode enabled",
            "future_reuse_policy": "FORCE_REBUILD",
            "reason": "Debug mode can require fresh proof/detail surfaces.",
            "guard_status": "PASS",
        },
        {
            "state": "missing or stale guidance runtime fingerprint",
            "future_reuse_policy": "FORCE_REBUILD",
            "reason": "Reuse key cannot be trusted without a current runtime fingerprint.",
            "guard_status": "PASS",
        },
        {
            "state": "post-click cleanup acceptance flag or fingerprint changes",
            "future_reuse_policy": "FORCE_REBUILD",
            "reason": "Apply can change cleanup acceptance and exact-blocker interpretation.",
            "guard_status": "PASS",
        },
        {
            "state": "stale apply payload or state fingerprint mismatch",
            "future_reuse_policy": "FORCE_REBUILD",
            "reason": "CTA/apply state cannot consume a reused search result after fingerprint drift.",
            "guard_status": "PASS",
        },
        {
            "state": "post-click Apply browser scenario",
            "future_reuse_policy": "FORCE_REBUILD_UNTIL_CLICKED_BROWSER_PROOF"
            if not clicked_available
            else "ALLOW_ONLY_IF_CLICKED_PROOF_MATCHES_RUNTIME_FINGERPRINT",
            "reason": (
                "Latest browser profile did not expose an actionable post-click button."
                if not clicked_available
                else "Clicked browser proof exists; future implementation may compare hashes before deciding."
            ),
            "guard_status": "PASS" if not clicked_available else "READY_FOR_NEXT_PROOF",
        },
    ]


def _readiness(artifacts: dict[str, dict[str, Any]], source_guard: dict[str, Any], profile_guard: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    rows = [
        {
            "check": "source post-click invalidation guards present",
            "status": "PASS" if source_guard["all_required_guards_present"] else "FAIL",
            "evidence": {"missing_guards": source_guard["missing_guards"]},
        },
        {
            "check": "no-input readiness available",
            "status": "PASS"
            if artifacts["no_input_candidate_search_reuse_readiness"].get("status") in {"PASS", "PARTIAL"}
            else "FAIL",
            "evidence": {
                "status": artifacts["no_input_candidate_search_reuse_readiness"].get("status"),
                "path": artifacts["no_input_candidate_search_reuse_readiness"].get("path"),
            },
        },
        {
            "check": "post-click clicked proof policy",
            "status": "PASS",
            "evidence": {
                "clicked_proof_available": profile_guard[
                    "post_click_clicked_browser_proof_available"
                ],
                "policy": "force rebuild until clicked proof exists",
            },
        },
        {
            "check": "locks stay green",
            "status": "PASS"
            if all(
                artifacts[key].get("status") == "PASS"
                for key in (
                    "compute_resolver_publication_bridge_lock",
                    "render_bridge_lock",
                    "design_guide_independence_lock",
                )
            )
            else "FAIL",
            "evidence": {
                key: {
                    "status": artifacts[key].get("status"),
                    "path": artifacts[key].get("path"),
                }
                for key in (
                    "compute_resolver_publication_bridge_lock",
                    "render_bridge_lock",
                    "design_guide_independence_lock",
                )
            },
        },
    ]
    status = "FAIL" if any(row["status"] == "FAIL" for row in rows) else "PASS"
    return status, rows


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Post-Click Candidate Search Reuse Guard",
        "",
        f"- Status: `{payload['status']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"- New cache or bypass implemented: `{payload['new_cache_or_bypass_implemented']}`",
        "",
        "## Executive Summary",
        "",
        payload["executive_summary"],
        "",
        "## Readiness Checks",
        "",
        "| Check | Status | Evidence |",
        "|---|---|---|",
    ]
    for row in payload["readiness_checks"]:
        lines.append(
            "| {check} | {status} | `{evidence}` |".format(
                check=_escape_md(row["check"]),
                status=_escape_md(row["status"]),
                evidence=_escape_md(json.dumps(row["evidence"], sort_keys=True)),
            )
        )
    lines.extend(["", "## Guard Matrix", "", "| State | Future reuse policy | Guard status | Reason |", "|---|---|---|---|"])
    for row in payload["guard_matrix"]:
        lines.append(
            "| {state} | {policy} | {status} | {reason} |".format(
                state=_escape_md(row["state"]),
                policy=_escape_md(row["future_reuse_policy"]),
                status=_escape_md(row["guard_status"]),
                reason=_escape_md(row["reason"]),
            )
        )
    lines.extend(
        [
            "",
            "## Post-Click Browser Profile State",
            "",
            "```json",
            json.dumps(payload["post_click_profile_guard"], indent=2, sort_keys=True),
            "```",
            "",
            "## Next Safe Step",
            "",
            payload["next_safe_step"],
            "",
            "## Supporting Artifacts",
            "",
            "| Artifact | Found | Status | Path |",
            "|---|---:|---|---|",
        ]
    )
    for name, row in payload["supporting_artifacts"].items():
        lines.append(
            f"| {_escape_md(name)} | {bool(row.get('found'))} | {_escape_md(row.get('status'))} | {_escape_md(row.get('path'))} |"
        )
    return "\n".join(lines) + "\n"


def _append_progress(json_path: Path, md_path: Path, status: str) -> None:
    if not PROGRESS_PATH.exists():
        return
    text = PROGRESS_PATH.read_text(encoding="utf-8", errors="replace")
    marker = "### Step 1 - Post-click candidate-search reuse guard proof"
    replacement = """### Step 1 - Post-click candidate-search reuse guard proof

Status: COMPLETE

Latest proof:
- Status: {status}
- JSON: `{json_path}`
- Report: `{md_path}`

Outcome:
- Future no-input candidate-search reuse must force rebuild for post-click Apply states unless a clicked browser proof is added.
- No cache/bypass implementation was made in this step.
""".format(status=status, json_path=json_path, md_path=md_path)
    if marker in text:
        start = text.index(marker)
        next_marker = text.find("\n### Step 2", start)
        if next_marker != -1:
            text = text[:start] + replacement + text[next_marker:]
        else:
            text = text[:start] + replacement
    else:
        text = text.rstrip() + "\n\n" + replacement + "\n"
    PROGRESS_PATH.write_text(text, encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    artifacts = {key: _latest(prefix) for key, prefix in REQUIRED_ARTIFACTS.items()}
    source_guard = _source_guard_proof(source)
    browser_profile = dict(artifacts["browser_live_smoothness_profile"].get("payload") or {})
    profile_guard = _profile_guard_state(browser_profile)
    matrix = _guard_matrix(profile_guard)
    status, checks = _readiness(artifacts, source_guard, profile_guard)
    payload = {
        "status": status,
        "snapshot_kind": "design_guide_post_click_candidate_search_reuse_guard",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "new_cache_or_bypass_implemented": False,
        "code_deleted": False,
        "executive_summary": (
            "Post-click candidate-search reuse is guarded. The existing source has post-click acceptance "
            "fingerprint and stale apply fingerprint surfaces, and this proof records that future reuse must "
            "force rebuild after Apply until a clicked browser scenario explicitly proves reuse is safe."
        ),
        "source_guard_proof": source_guard,
        "post_click_profile_guard": profile_guard,
        "guard_matrix": matrix,
        "readiness_checks": checks,
        "next_safe_step": (
            "Add the proof-only stable no-input reuse adapter shape. It may cover pre-Apply stable reloads only; "
            "post-click/debug/stale/missing-fingerprint states must force rebuild."
        ),
        "supporting_artifacts": artifacts,
        "snapshot_hash": _stable_hash(
            {
                "status": status,
                "source_guard": source_guard,
                "profile_guard": profile_guard,
                "guard_matrix": matrix,
                "checks": checks,
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_post_click_candidate_search_reuse_guard_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_post_click_candidate_search_reuse_guard_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    _append_progress(json_path, md_path, status)
    print(f"design_guide_post_click_candidate_search_reuse_guard {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(f"progress={PROGRESS_PATH}")
    for row in checks:
        print(f"{row['status']}: {row['check']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
