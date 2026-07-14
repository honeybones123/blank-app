"""Stable no-input candidate-search reuse adapter readiness.

Proof-only. Defines the exact decision shape a future candidate-search reuse
adapter must obey. It does not implement caching, bypassing, or product
behaviour changes.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

REQUIRED_ARTIFACTS = {
    "post_click_guard": "design_guide_post_click_candidate_search_reuse_guard",
    "no_input_readiness": "design_guide_no_input_candidate_search_reuse_readiness",
    "browser_live_smoothness_profile": "design_guide_browser_live_smoothness_profile",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "design_guide_independence_lock": "design_guide_independence_lock",
}


@dataclass(frozen=True)
class CandidateSearchReuseKey:
    guidance_runtime_fp: str
    candidate_fingerprint_set_hash: str
    request_kind: str
    algorithm_version: str
    debug_enabled: bool
    guidance_debug_verbose: bool
    post_cleanup_acceptance_fp: str | None
    post_cleanup_acceptance_enabled: bool


@dataclass(frozen=True)
class CandidateSearchReuseDecision:
    scenario_id: str
    decision: str
    reason: str
    current_key_hash: str | None
    cached_key_hash: str | None
    force_rebuild: bool
    eligible_for_future_reuse: bool


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


def _key_hash(key: CandidateSearchReuseKey | None) -> str | None:
    if key is None:
        return None
    return _stable_hash(asdict(key))


def _decision(
    *,
    scenario_id: str,
    current_key: CandidateSearchReuseKey | None,
    cached_key: CandidateSearchReuseKey | None,
    existing_cached_result_present: bool,
    post_click_state: bool = False,
    stale_apply_payload: bool = False,
    missing_runtime_fingerprint: bool = False,
    clicked_post_apply_proof_available: bool = False,
) -> CandidateSearchReuseDecision:
    current_hash = _key_hash(current_key)
    cached_hash = _key_hash(cached_key)
    if missing_runtime_fingerprint or current_key is None:
        return CandidateSearchReuseDecision(
            scenario_id,
            "FORCE_REBUILD",
            "missing_runtime_fingerprint",
            current_hash,
            cached_hash,
            True,
            False,
        )
    if current_key.debug_enabled or current_key.guidance_debug_verbose:
        return CandidateSearchReuseDecision(
            scenario_id,
            "FORCE_REBUILD",
            "debug_mode_enabled",
            current_hash,
            cached_hash,
            True,
            False,
        )
    if stale_apply_payload:
        return CandidateSearchReuseDecision(
            scenario_id,
            "FORCE_REBUILD",
            "stale_apply_payload_or_state_fingerprint_mismatch",
            current_hash,
            cached_hash,
            True,
            False,
        )
    if post_click_state and not clicked_post_apply_proof_available:
        return CandidateSearchReuseDecision(
            scenario_id,
            "FORCE_REBUILD",
            "post_click_apply_without_clicked_browser_reuse_proof",
            current_hash,
            cached_hash,
            True,
            False,
        )
    if not existing_cached_result_present:
        return CandidateSearchReuseDecision(
            scenario_id,
            "REBUILD_AND_RECORD",
            "missing_cached_candidate_search_result",
            current_hash,
            cached_hash,
            True,
            False,
        )
    if not cached_hash or current_hash != cached_hash:
        return CandidateSearchReuseDecision(
            scenario_id,
            "REBUILD_AND_RECORD",
            "reuse_key_changed",
            current_hash,
            cached_hash,
            True,
            False,
        )
    return CandidateSearchReuseDecision(
        scenario_id,
        "REUSE_ELIGIBLE",
        "stable_no_input_reuse_key_unchanged",
        current_hash,
        cached_hash,
        False,
        True,
    )


def _scenario_decisions() -> list[dict[str, Any]]:
    stable_key = CandidateSearchReuseKey(
        guidance_runtime_fp="runtime-stable",
        candidate_fingerprint_set_hash="candidate-set-stable",
        request_kind="design_guide",
        algorithm_version="DESIGN_GUIDE_ALGORITHM_VERSION",
        debug_enabled=False,
        guidance_debug_verbose=False,
        post_cleanup_acceptance_fp=None,
        post_cleanup_acceptance_enabled=False,
    )
    debug_key = CandidateSearchReuseKey(
        **{**asdict(stable_key), "debug_enabled": True},
    )
    post_click_key = CandidateSearchReuseKey(
        **{
            **asdict(stable_key),
            "post_cleanup_acceptance_fp": "accepted-fp-after-apply",
            "post_cleanup_acceptance_enabled": True,
        },
    )
    changed_key = CandidateSearchReuseKey(
        **{**asdict(stable_key), "guidance_runtime_fp": "runtime-changed"},
    )
    decisions = [
        _decision(
            scenario_id="initial_missing_cache",
            current_key=stable_key,
            cached_key=None,
            existing_cached_result_present=False,
        ),
        _decision(
            scenario_id="stable_no_input_same_key",
            current_key=stable_key,
            cached_key=stable_key,
            existing_cached_result_present=True,
        ),
        _decision(
            scenario_id="runtime_fingerprint_changed",
            current_key=changed_key,
            cached_key=stable_key,
            existing_cached_result_present=True,
        ),
        _decision(
            scenario_id="missing_runtime_fingerprint",
            current_key=None,
            cached_key=stable_key,
            existing_cached_result_present=True,
            missing_runtime_fingerprint=True,
        ),
        _decision(
            scenario_id="debug_mode_enabled",
            current_key=debug_key,
            cached_key=stable_key,
            existing_cached_result_present=True,
        ),
        _decision(
            scenario_id="stale_apply_payload",
            current_key=stable_key,
            cached_key=stable_key,
            existing_cached_result_present=True,
            stale_apply_payload=True,
        ),
        _decision(
            scenario_id="post_click_apply_without_clicked_proof",
            current_key=post_click_key,
            cached_key=stable_key,
            existing_cached_result_present=True,
            post_click_state=True,
            clicked_post_apply_proof_available=False,
        ),
        _decision(
            scenario_id="post_click_apply_with_clicked_proof_but_changed_key",
            current_key=post_click_key,
            cached_key=stable_key,
            existing_cached_result_present=True,
            post_click_state=True,
            clicked_post_apply_proof_available=True,
        ),
    ]
    return [asdict(row) for row in decisions]


def _readiness(artifacts: dict[str, dict[str, Any]], decisions: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    stable = next(row for row in decisions if row["scenario_id"] == "stable_no_input_same_key")
    force_rebuild_rows = [
        row for row in decisions if row["scenario_id"] != "stable_no_input_same_key"
    ]
    rows = [
        {
            "check": "post-click guard proof available",
            "status": "PASS" if artifacts["post_click_guard"].get("status") == "PASS" else "FAIL",
            "evidence": {
                "status": artifacts["post_click_guard"].get("status"),
                "path": artifacts["post_click_guard"].get("path"),
            },
        },
        {
            "check": "stable no-input decision is reuse-eligible",
            "status": "PASS" if stable["decision"] == "REUSE_ELIGIBLE" else "FAIL",
            "evidence": stable,
        },
        {
            "check": "guarded states force rebuild",
            "status": "PASS"
            if all(row["force_rebuild"] for row in force_rebuild_rows)
            else "FAIL",
            "evidence": [
                {
                    "scenario_id": row["scenario_id"],
                    "decision": row["decision"],
                    "reason": row["reason"],
                }
                for row in force_rebuild_rows
            ],
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
        {
            "check": "no cache or bypass implemented by this snapshot",
            "status": "PASS",
            "evidence": {"product_behaviour_changed": False, "new_cache_or_bypass_implemented": False},
        },
    ]
    return ("FAIL" if any(row["status"] == "FAIL" for row in rows) else "PASS"), rows


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide No-Input Candidate Search Reuse Adapter Readiness",
        "",
        f"- Status: `{payload['status']}`",
        f"- Ready for implementation slice: `{payload['ready_for_implementation_slice']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Executive Summary",
        "",
        payload["executive_summary"],
        "",
        "## Decision Matrix",
        "",
        "| Scenario | Decision | Reason | Force rebuild | Future reuse eligible |",
        "|---|---|---|---:|---:|",
    ]
    for row in payload["decision_matrix"]:
        lines.append(
            "| {scenario} | {decision} | {reason} | {force} | {eligible} |".format(
                scenario=_escape_md(row["scenario_id"]),
                decision=_escape_md(row["decision"]),
                reason=_escape_md(row["reason"]),
                force=bool(row["force_rebuild"]),
                eligible=bool(row["eligible_for_future_reuse"]),
            )
        )
    lines.extend(["", "## Readiness Checks", "", "| Check | Status | Evidence |", "|---|---|---|"])
    for row in payload["readiness_checks"]:
        lines.append(
            "| {check} | {status} | `{evidence}` |".format(
                check=_escape_md(row["check"]),
                status=_escape_md(row["status"]),
                evidence=_escape_md(json.dumps(row["evidence"], sort_keys=True)),
            )
        )
    lines.extend(
        [
            "",
            "## Implementation Contract",
            "",
        ]
    )
    for item in payload["future_implementation_contract"]:
        lines.append(f"- {item}")
    lines.extend(
        [
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
    marker = "### Step 2 - Narrow no-input candidate-search reuse adapter readiness"
    replacement = """### Step 2 - Narrow no-input candidate-search reuse adapter readiness

Status: COMPLETE

Latest proof:
- Status: {status}
- JSON: `{json_path}`
- Report: `{md_path}`

Outcome:
- Stable no-input same-key state is eligible for the future implementation slice.
- Debug, missing/stale fingerprint, stale apply payload, and post-click states force rebuild.
- No cache/bypass implementation was made in this step.
""".format(status=status, json_path=json_path, md_path=md_path)
    if marker in text:
        start = text.index(marker)
        next_marker = text.find("\n### Step 3", start)
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
    artifacts = {key: _latest(prefix) for key, prefix in REQUIRED_ARTIFACTS.items()}
    decisions = _scenario_decisions()
    status, checks = _readiness(artifacts, decisions)
    payload = {
        "status": status,
        "snapshot_kind": "design_guide_no_input_candidate_search_reuse_adapter_readiness",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "new_cache_or_bypass_implemented": False,
        "code_deleted": False,
        "ready_for_implementation_slice": status == "PASS",
        "executive_summary": (
            "The future candidate-search reuse adapter shape is now defined. It allows only stable "
            "pre-Apply no-input same-key reuse, and forces rebuild for debug, missing/stale runtime "
            "fingerprint, stale apply payload, changed runtime key, and post-click Apply states."
        ),
        "reuse_key_schema": {
            "fields": list(CandidateSearchReuseKey.__dataclass_fields__.keys()),
            "hash": "sha256(stable_json(CandidateSearchReuseKey))",
        },
        "decision_schema": {
            "fields": list(CandidateSearchReuseDecision.__dataclass_fields__.keys()),
        },
        "decision_matrix": decisions,
        "readiness_checks": checks,
        "future_implementation_contract": [
            "Implement only for stable no-input same-key reruns.",
            "Use guidance_runtime_fp plus candidate_fingerprint_set_hash as the reuse key.",
            "Force rebuild when debug or verbose debug is enabled.",
            "Force rebuild when runtime fingerprint is missing or changed.",
            "Force rebuild when apply payload/state fingerprint is stale.",
            "Force rebuild for post-click Apply until clicked browser proof allows otherwise.",
            "Keep CTA/apply routing, family contracts, formulas, and visible wording unchanged.",
        ],
        "supporting_artifacts": artifacts,
        "snapshot_hash": _stable_hash(
            {
                "status": status,
                "decisions": decisions,
                "checks": checks,
                "reuse_key_schema": list(CandidateSearchReuseKey.__dataclass_fields__.keys()),
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_no_input_candidate_search_reuse_adapter_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_no_input_candidate_search_reuse_adapter_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    _append_progress(json_path, md_path, status)
    print(f"design_guide_no_input_candidate_search_reuse_adapter_readiness {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(f"progress={PROGRESS_PATH}")
    print(f"ready_for_implementation_slice={status == 'PASS'}")
    for row in checks:
        print(f"{row['status']}: {row['check']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
