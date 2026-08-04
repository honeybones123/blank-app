"""Regression snapshot for overdesign post-Apply terminal publication.

This checker reads the latest strict browser/live family lock artifacts and
proves that overdesign families do not publish a second ACTION card after
Apply.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.verification.verification_run_manifest import current_run_artifact
except ModuleNotFoundError:
    from verification_run_manifest import current_run_artifact


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET_FAMILIES = {
    "BENDING_OVERDESIGN_GOVERNS": {
        "artifact_slug": "bending_overdesign_governs",
        "lock_family_id": "BENDING_OVERDESIGN_GOVERNS",
    },
    "COMBINED_OVERDESIGN_GOVERNS": {
        "artifact_slug": "combined_overdesign",
        "lock_family_id": "COMBINED_OVERDESIGN",
    },
}


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _latest_live_lock_artifact(family_id: str) -> Path:
    config = TARGET_FAMILIES[family_id]
    current_path, current_payload = current_run_artifact(
        f"{config['artifact_slug']}_live_fuzz_regression_lock_gate"
    )
    if current_path is None or not current_payload:
        raise AssertionError(
            f"No current-run hash-bound live lock artifact found for {family_id}"
        )
    if current_payload.get("family") != config["lock_family_id"]:
        raise AssertionError(f"Current-run family mismatch for {family_id}")
    return current_path


def _compact_family_result(family_id: str, source_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    family = dict(payload.get("family_10_fuzz_row") or {})
    live_execution = dict(family.get("live_execution") or {})
    rows = list(live_execution.get("rows") or [])
    failing_rows: list[dict[str, Any]] = []
    for row in rows:
        failures = list(row.get("failures") or [])
        green_contract = dict(row.get("post_apply_green_pass_visual_contract") or {})
        publication_after = dict(row.get("publication_probe_after") or {})
        cta = dict(publication_after.get("cta") or {})
        second_action = (
            str(publication_after.get("outcome_state") or "").upper() == "ACTION"
            and bool(cta.get("enabled") or cta.get("actionable"))
        )
        if failures or green_contract.get("passes_contract") is False or second_action:
            post_card = dict(row.get("post_apply_final_card_probe") or {})
            run_data = dict(((row.get("run_end_event") or {}).get("data") or {}))
            failing_rows.append(
                {
                    "scenario_id": row.get("scenario_id"),
                    "failures": failures or ["second_action_cta_after_overdesign_apply"],
                    "post_apply_status_markers": post_card.get("status_markers"),
                    "post_apply_text_sample": str(post_card.get("text_sample") or "")[:800],
                    "final_live_worst_util": run_data.get("final_live_worst_util"),
                    "current_overview": run_data.get("current_overview"),
                    "applied_updates": dict((run_data.get("last_apply_route") or {}).get("applied_updates") or {}),
                    "exact_blocker_families": sorted(
                        str(key)
                        for key in dict((run_data.get("last_apply_route") or {}).get("exact_blockers_by_family") or {}).keys()
                    ),
                    "green_contract": green_contract,
                }
            )
    return {
        "family": family_id,
        "lock_family": payload.get("family"),
        "source_artifact": _repo_rel(source_path),
        "lock_status": payload.get("lock_status"),
        "live_status": live_execution.get("status"),
        "row_count": len(rows),
        "failed_count": len(failing_rows),
        "failing_rows": failing_rows,
    }


def _write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_overdesign_post_apply_green_regression_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_overdesign_post_apply_green_regression_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Overdesign Post-Apply Green Regression",
        "",
        f"Status: **{payload['status']}**",
        "",
        "Source artifacts:",
        "",
    ]
    for source_artifact in payload["source_artifacts"]:
        lines.append(f"- `{source_artifact}`")
    lines.extend(
        [
            "",
            "Rule: overdesign Apply must settle to a green accepted/terminal Design Guide card, or to explicit no-action terminal proof. It must not publish a second ACTION card.",
        ]
    )
    lines.extend([
        "",
        "| family | lock status | live status | rows | failing rows | first blocker |",
        "|---|---:|---:|---:|---:|---|",
    ])
    for family in payload["families"]:
        first = next(iter(family.get("failing_rows") or []), {})
        lines.append(
            "| "
            + " | ".join(
                [
                    str(family.get("family") or ""),
                    str(family.get("lock_status") or ""),
                    str(family.get("live_status") or ""),
                    str(family.get("row_count") or 0),
                    str(family.get("failed_count") or 0),
                    ", ".join(first.get("failures") or []) or "none",
                ]
            )
            + " |"
        )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    lines.extend(["", f"JSON artifact: `{_repo_rel(json_path)}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    families: list[dict[str, Any]] = []
    failures: list[str] = []
    source_artifacts: list[str] = []
    for family_id in TARGET_FAMILIES:
        try:
            source = _latest_live_lock_artifact(family_id)
        except AssertionError:
            failures.append(f"{family_id}:missing_from_latest_live_fuzz_artifact")
            continue
        source_payload = json.loads(source.read_text(encoding="utf-8"))
        source_artifacts.append(_repo_rel(source))
        compact = _compact_family_result(family_id, source, source_payload)
        families.append(compact)
        if compact.get("lock_status") != "LOCKED":
            failures.append(f"{family_id}:live_fuzz_lock_not_locked")
        if compact.get("live_status") != "PASS":
            failures.append(f"{family_id}:live_fuzz_status_not_pass")
        if compact["failed_count"]:
            failures.append(f"{family_id}:post_apply_not_green:{compact['failed_count']}")

    payload = {
        "schema": "design_guide.overdesign_post_apply_green_regression.v1",
        "status": "PASS" if not failures else "FAIL",
        "source_artifacts": source_artifacts,
        "families": families,
        "failures": failures,
    }
    json_path, md_path = _write_artifacts(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "failures": failures,
                "artifact": _repo_rel(json_path),
                "report": _repo_rel(md_path),
            },
            indent=2,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
