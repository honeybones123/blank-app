"""Audit no-input reload publication/display hash drift.

Proof-only. This verifier explains why candidate-search reuse is not yet safe
even though the controller memo is live: the browser smoothness profile still
observes publication/display hash drift across no-input reloads.
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

REQUIRED_ARTIFACTS = {
    "browser_live_smoothness_profile": "design_guide_browser_live_smoothness_profile",
    "controller_request_key_live_stability": "design_guide_controller_request_key_live_stability",
    "final_publication_memo_implementation": "design_guide_final_publication_memo_implementation",
    "no_input_candidate_search_reuse_readiness": "design_guide_no_input_candidate_search_reuse_readiness",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
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
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def _stable_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in list(profile.get("scenarios") or []):
        if not isinstance(row, dict):
            continue
        if str(row.get("scenario_id") or "").startswith("stable_no_input_reload"):
            counters = dict(row.get("counters") or {})
            candidate = dict(counters.get("candidate_evaluation") or {})
            out.append(
                {
                    "scenario_id": row.get("scenario_id"),
                    "rerun_seq": row.get("rerun_seq"),
                    "final_publication_hash": counters.get("final_publication_hash"),
                    "final_publication_display_hash": counters.get("final_publication_display_hash"),
                    "button_contract_hash": counters.get("button_contract_hash"),
                    "apply_payload_hash": counters.get("apply_payload_hash"),
                    "candidate_eval_count": int(candidate.get("count") or 0),
                    "candidate_eval_cache_hits": int(candidate.get("cache_hits") or 0),
                    "candidate_eval_cache_misses": int(candidate.get("cache_misses") or 0),
                    "candidate_eval_total_ms": round(float(candidate.get("total_ms") or 0.0), 3),
                }
            )
    return out


def _controller_stability(controller: dict[str, Any]) -> dict[str, Any]:
    browser = dict(controller.get("browser_live") or {})
    stable = dict(browser.get("stable") or {})
    stable_rerun = dict(browser.get("stable_rerun") or {})
    latest = dict(stable.get("latest") or {})
    return {
        "status": controller.get("status"),
        "stable_request_hash": stable.get("stable_request_hash"),
        "stable_publication_hash": stable.get("stable_publication_hash"),
        "stable_controller_hash": stable.get("stable_controller_hash"),
        "stable_rerun_memo_cache_hits": int(stable_rerun.get("memo_cache_hits") or 0),
        "latest_controller_request_hash": latest.get("controller_request_hash"),
        "latest_publication_hash": latest.get("publication_hash"),
        "latest_controller_hash": latest.get("controller_hash"),
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide No-Input Reload Publication Hash Drift Audit",
        "",
        f"- Status: `{payload['status']}`",
        f"- Classification: `{payload['classification']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Summary",
        "",
        payload["summary"],
        "",
        "## Stable Reload Rows",
        "",
        "| Scenario | Publication hash | Display hash | Candidate evals | Misses | Hits |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in payload["stable_reload_rows"]:
        lines.append(
            "| {scenario} | `{pub}` | `{display}` | {count} | {misses} | {hits} |".format(
                scenario=_escape_md(row.get("scenario_id")),
                pub=_escape_md(row.get("final_publication_hash")),
                display=_escape_md(row.get("final_publication_display_hash")),
                count=row.get("candidate_eval_count"),
                misses=row.get("candidate_eval_cache_misses"),
                hits=row.get("candidate_eval_cache_hits"),
            )
        )
    lines.extend(
        [
            "",
            "## Controller Stability",
            "",
            "```json",
            json.dumps(payload["controller_stability"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision",
            "",
            f"- Candidate-search reuse implementation allowed now: `{payload['candidate_search_reuse_allowed_now']}`",
            f"- Required next proof: `{payload['required_next_proof']}`",
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


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifacts = {key: _latest(prefix) for key, prefix in REQUIRED_ARTIFACTS.items()}
    profile = dict(artifacts["browser_live_smoothness_profile"].get("payload") or {})
    controller = dict(artifacts["controller_request_key_live_stability"].get("payload") or {})
    stable_rows = _stable_rows(profile)
    publication_hashes = {row.get("final_publication_hash") for row in stable_rows if row.get("final_publication_hash")}
    display_hashes = {
        row.get("final_publication_display_hash")
        for row in stable_rows
        if row.get("final_publication_display_hash")
    }
    candidate_misses = sum(int(row.get("candidate_eval_cache_misses") or 0) for row in stable_rows)
    candidate_count = sum(int(row.get("candidate_eval_count") or 0) for row in stable_rows)
    controller_stability = _controller_stability(controller)
    locks_ok = all(
        artifacts[name].get("status") == "PASS"
        for name in (
            "final_publication_memo_implementation",
            "controller_request_key_live_stability",
            "design_guide_independence_lock",
            "render_bridge_lock",
            "compute_resolver_publication_bridge_lock",
        )
    )
    profile_drift = len(publication_hashes) > 1 or len(display_hashes) > 1
    classification = (
        "SMOOTHNESS_PROFILE_RELOAD_HASH_DRIFT_WITH_CONTROLLER_STABILITY_PROVEN"
        if profile_drift and controller_stability.get("stable_publication_hash") is True
        else "NO_RELOAD_HASH_DRIFT"
        if not profile_drift
        else "RELOAD_HASH_DRIFT_NEEDS_CONTROLLER_STABILITY"
    )
    status = "PASS" if stable_rows and locks_ok else "FAIL"
    payload = {
        "status": status,
        "schema": "design_guide_no_input_reload_publication_hash_drift_audit.v1",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "classification": classification,
        "summary": (
            "Browser smoothness profiling still sees publication/display hash drift across no-input reloads, "
            "while the controller request-key proof separately shows stable controller publication hashes and "
            "memo hits. Candidate-search reuse should wait for a focused bridge proving the smoothness counters "
            "consume the same FinalDesignGuidePublication authority object as the controller path."
        )
        if profile_drift
        else "No publication/display hash drift was observed across stable no-input reloads.",
        "stable_reload_rows": stable_rows,
        "publication_hashes_unique_count": len(publication_hashes),
        "display_hashes_unique_count": len(display_hashes),
        "candidate_eval_count": candidate_count,
        "candidate_eval_cache_misses": candidate_misses,
        "controller_stability": controller_stability,
        "candidate_search_reuse_allowed_now": False if profile_drift else bool(candidate_misses),
        "required_next_proof": (
            "smoothness_profile_final_publication_same_object_bridge"
            if profile_drift
            else "candidate_search_reuse_implementation_readiness"
        ),
        "supporting_artifacts": {
            key: {"found": value.get("found"), "status": value.get("status"), "path": value.get("path")}
            for key, value in artifacts.items()
        },
        "snapshot_hash": _stable_hash(
            {
                "stable_rows": stable_rows,
                "controller_stability": controller_stability,
                "classification": classification,
                "candidate_count": candidate_count,
                "candidate_misses": candidate_misses,
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_no_input_reload_publication_hash_drift_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_no_input_reload_publication_hash_drift_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_no_input_reload_publication_hash_drift_audit {status}")
    print(f"classification={classification}")
    print(f"candidate_search_reuse_allowed_now={payload['candidate_search_reuse_allowed_now']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
