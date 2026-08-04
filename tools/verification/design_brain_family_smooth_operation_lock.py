"""Live family smooth-operation lock.

This verifier is deliberately different from the family correctness locks.
It assumes the latest universal live family lock has already exercised each
family in the browser, then checks whether those family paths operated
smoothly: one visible Design Guide card, at most one actionable CTA, no loading
shell residue, no stale fallback shell, bounded settle time, and no immediate
post-Apply churn.
"""

from __future__ import annotations

import json
from datetime import datetime
import os
from pathlib import Path
from typing import Any

try:
    from tools.verification.verification_run_manifest import current_run_artifact
except ModuleNotFoundError:
    from verification_run_manifest import current_run_artifact


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

MAX_PRE_APPLY_SETTLE_SEC = 12.0
MAX_POST_APPLY_SETTLE_SEC = 12.0
EXPECTED_LIVE_ROWS_PER_FAMILY = 10


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    # This lock is release authority, not a historical report. It may only
    # consume a hash-checked artifact from the active canonical run.
    if not os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        return None, {}
    return current_run_artifact(prefix)


def _latest_live_universal_family_lock() -> tuple[Path | None, dict[str, Any]]:
    # Do not use a filesystem newest-file fallback for universal live proof.
    return current_run_artifact("design_brain_universal_live_family_lock")


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(float(value))
    except Exception:
        return None


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _card_count(visual_checks: dict[str, Any]) -> int | None:
    cards = _dict(visual_checks.get("visible_design_guide_cards"))
    return _as_int(cards.get("count"))


def _duplicate_card_reasons(visual_checks: dict[str, Any]) -> list[str]:
    cards = _dict(visual_checks.get("visible_design_guide_cards"))
    reasons: list[str] = []
    for key in ("duplicate_publication_hashes", "duplicate_titles"):
        values = _list(cards.get(key))
        if values:
            reasons.append(f"{key}:{len(values)}")
    count = _card_count(visual_checks)
    if count is not None and count > 1:
        reasons.append(f"visible_design_guide_card_count:{count}")
    return reasons


def _action_count_from_visual(visual_checks: dict[str, Any]) -> int | None:
    cta = _dict(visual_checks.get("cta"))
    for key in ("enabled_action_count", "visible_action_count", "action_button_count", "button_count"):
        value = _as_int(cta.get(key))
        if value is not None:
            return value
    buttons = _list(cta.get("buttons"))
    if buttons:
        enabled = 0
        visible = 0
        for button in buttons:
            row = _dict(button)
            if row.get("enabled") is True:
                enabled += 1
            if row.get("visible") is not False:
                visible += 1
        return max(enabled, visible)
    return None


def _post_apply_action_allowed(row: dict[str, Any]) -> bool:
    after_publication = _dict(row.get("publication_probe_after"))
    outcome = str(after_publication.get("outcome_state") or "").upper()
    cta = _dict(after_publication.get("cta"))
    if outcome in {"PASS", "BLOCKED", "ERROR", "PROOF_PENDING"}:
        return not bool(cta.get("enabled"))
    return True


def _check_row(family_id: str, row: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(row.get("scenario_id") or row.get("recipe") or "")
    failures: list[str] = []

    row_failures = _list(row.get("failures"))
    if row_failures:
        failures.append(f"live_row_failures:{len(row_failures)}")

    before_probe = _dict(row.get("final_card_probe"))
    after_probe = _dict(row.get("post_apply_final_card_probe"))
    before_visual = _dict(row.get("visual_checks"))
    after_visual = _dict(row.get("post_apply_visual_checks"))
    before_button = _dict(row.get("button_probe_before"))
    enabled_before = _as_int(before_button.get("enabled_action_count"))
    visible_before = _as_int(before_button.get("visible_action_count"))
    apply_was_available = bool(
        (enabled_before is not None and enabled_before > 0)
        or (enabled_before is None and visible_before is not None and visible_before > 0)
    )

    probe_pairs = [("pre", before_probe)]
    if apply_was_available:
        probe_pairs.append(("post", after_probe))
    for label, probe in probe_pairs:
        if probe.get("final_card_ready") is not True:
            failures.append(f"{label}_final_card_not_ready")
        if probe.get("loading_shell_visible") is True:
            failures.append(f"{label}_loading_shell_visible")
        if probe.get("loading_shell_only") is True:
            failures.append(f"{label}_loading_shell_only")
        settle = _as_float(probe.get("wait_elapsed_sec"))
        if settle is not None:
            threshold = MAX_PRE_APPLY_SETTLE_SEC if label == "pre" else MAX_POST_APPLY_SETTLE_SEC
            if settle > threshold:
                failures.append(f"{label}_settle_over_budget:{settle:.2f}s>{threshold:.2f}s")

    visual_pairs = [("pre", before_visual)]
    if apply_was_available:
        visual_pairs.append(("post", after_visual))
    for label, visual in visual_pairs:
        hard_failures = _list(visual.get("hard_failures"))
        if hard_failures:
            failures.append(f"{label}_visual_hard_failures:{len(hard_failures)}")
        if visual.get("stale_fallback_publication_shell") is True:
            failures.append(f"{label}_stale_fallback_publication_shell")
        failures.extend(f"{label}_{reason}" for reason in _duplicate_card_reasons(visual))

    if enabled_before is not None and enabled_before > 1:
        failures.append(f"pre_duplicate_enabled_action_buttons:{enabled_before}")
    if visible_before is not None and visible_before > 1:
        failures.append(f"pre_duplicate_visible_action_buttons:{visible_before}")

    post_action_count = _action_count_from_visual(after_visual)
    if post_action_count is not None and post_action_count > 1:
        failures.append(f"post_duplicate_action_buttons:{post_action_count}")
    if not _post_apply_action_allowed(row):
        failures.append("post_apply_terminal_state_has_enabled_cta")

    recipe_probe = _dict(row.get("browser_recipe_probe"))
    if recipe_probe and recipe_probe.get("requested") != recipe_probe.get("applied"):
        failures.append("browser_recipe_requested_applied_mismatch")

    return {
        "family_id": family_id,
        "scenario_id": scenario_id,
        "recipe": row.get("recipe"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "pre_card_count": _card_count(before_visual),
        "post_card_count": _card_count(after_visual),
        "pre_enabled_action_count": enabled_before,
        "pre_visible_action_count": visible_before,
        "post_action_count": post_action_count,
        "pre_settle_sec": _as_float(before_probe.get("wait_elapsed_sec")),
        "post_settle_sec": _as_float(after_probe.get("wait_elapsed_sec")),
        "pre_loading_shell_visible": before_probe.get("loading_shell_visible"),
        "post_loading_shell_visible": after_probe.get("loading_shell_visible"),
        "pre_stale_fallback_shell": before_visual.get("stale_fallback_publication_shell"),
        "post_stale_fallback_shell": after_visual.get("stale_fallback_publication_shell"),
    }


def _family_rows(family_payload: dict[str, Any]) -> list[dict[str, Any]]:
    summary = _dict(family_payload.get("payload_summary"))
    live_audit = _dict(summary.get("live_audit"))
    rows = [_dict(row) for row in _list(live_audit.get("rows")) if isinstance(row, dict)]
    if rows:
        return rows
    artifact_path = family_payload.get("artifact")
    if artifact_path:
        try:
            payload = json.loads(Path(str(artifact_path)).read_text(encoding="utf-8"))
            live_audit = _dict(payload.get("live_audit"))
            return [_dict(row) for row in _list(live_audit.get("rows")) if isinstance(row, dict)]
        except Exception:
            return []
    return []


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Brain Family Smooth Operation Lock",
        "",
        f"Status: `{payload['status']}`",
        f"Universal live family artifact: `{payload['universal_live_family_artifact']}`",
        "",
        "## Summary",
        "",
        f"- Families checked: `{payload['family_count']}`",
        f"- Live rows checked: `{payload['live_row_count']}`",
        f"- Families passed: `{payload['family_pass_count']}`",
        f"- Families failed: `{payload['family_fail_count']}`",
        f"- Smooth operation lock: `{payload['smooth_operation_lock']}`",
        "",
        "## Family Results",
        "",
        "| Family | Rows | Failed Rows | Max pre settle | Max post settle | Status |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["families"]:
        lines.append(
            "| `{family}` | {rows} | {failed} | {pre} | {post} | `{status}` |".format(
                family=row["family_id"],
                rows=row["row_count"],
                failed=row["failed_row_count"],
                pre=row["max_pre_settle_sec"],
                post=row["max_post_settle_sec"],
                status=row["status"],
            )
        )
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- {failure}" for failure in payload["failures"])
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    stamp = _stamp()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    universal_path, universal = _latest_live_universal_family_lock()
    families = [_dict(row) for row in _list(universal.get("families")) if isinstance(row, dict)]
    family_results: list[dict[str, Any]] = []
    all_row_results: list[dict[str, Any]] = []
    failures: list[str] = []

    if not universal_path:
        failures.append("missing_universal_live_family_lock_artifact")
    if str(universal.get("universal_lock_status") or "").upper() != "LOCKED":
        failures.append("universal_live_family_lock_not_locked")
    if not families:
        failures.append("universal_live_family_lock_has_no_families")

    for family in families:
        family_id = str(family.get("family_id") or "")
        rows = _family_rows(family)
        evidence = _dict(_dict(family.get("logical_ladder_proof")).get("evidence_summary"))
        terminal_family = evidence.get("terminal_family") is True and evidence.get("live_executed") is False
        if terminal_family and not rows:
            family_results.append(
                {
                    "family_id": family_id,
                    "status": "TERMINAL_NOT_LIVE_EXECUTED",
                    "row_count": 0,
                    "failed_row_count": 0,
                    "max_pre_settle_sec": None,
                    "max_post_settle_sec": None,
                    "failed_rows": [],
                    "terminal_family": True,
                }
            )
            continue
        if len(rows) < EXPECTED_LIVE_ROWS_PER_FAMILY:
            failures.append(f"{family_id}:live_row_count_below_expected:{len(rows)}<{EXPECTED_LIVE_ROWS_PER_FAMILY}")
        row_results = [_check_row(family_id, row) for row in rows]
        all_row_results.extend(row_results)
        failed_rows = [row for row in row_results if row["status"] != "PASS"]
        pre_settles = [row["pre_settle_sec"] for row in row_results if row["pre_settle_sec"] is not None]
        post_settles = [row["post_settle_sec"] for row in row_results if row["post_settle_sec"] is not None]
        family_result = {
            "family_id": family_id,
            "status": "PASS" if not failed_rows and len(rows) >= EXPECTED_LIVE_ROWS_PER_FAMILY else "FAIL",
            "row_count": len(rows),
            "failed_row_count": len(failed_rows),
            "max_pre_settle_sec": max(pre_settles) if pre_settles else None,
            "max_post_settle_sec": max(post_settles) if post_settles else None,
            "failed_rows": failed_rows,
            "terminal_family": False,
        }
        family_results.append(family_result)
        if family_result["status"] != "PASS":
            failures.append(f"{family_id}:smooth_operation_failed")
            for failed in failed_rows[:5]:
                failures.append(f"{family_id}:{failed['scenario_id']}:{','.join(failed['failures'])}")

    payload = {
        "schema": "design_brain.family_smooth_operation_lock.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "smooth_operation_lock": "LOCKED" if not failures else "NOT_LOCKED",
        "universal_live_family_artifact": str(universal_path) if universal_path else None,
        "family_count": len(family_results),
        "live_row_count": len(all_row_results),
        "family_pass_count": sum(1 for row in family_results if row["status"] == "PASS"),
        "family_terminal_not_live_executed_count": sum(
            1 for row in family_results if row["status"] == "TERMINAL_NOT_LIVE_EXECUTED"
        ),
        "family_fail_count": sum(1 for row in family_results if row["status"] == "FAIL"),
        "thresholds": {
            "expected_live_rows_per_family": EXPECTED_LIVE_ROWS_PER_FAMILY,
            "max_pre_apply_settle_sec": MAX_PRE_APPLY_SETTLE_SEC,
            "max_post_apply_settle_sec": MAX_POST_APPLY_SETTLE_SEC,
            "max_visible_design_guide_cards": 1,
            "max_enabled_action_buttons": 1,
        },
        "families": family_results,
        "row_results": all_row_results,
        "failures": failures,
    }
    artifact_path = ARTIFACT_DIR / f"design_brain_family_smooth_operation_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_family_smooth_operation_lock_{stamp}.md"
    payload["artifact"] = str(artifact_path)
    payload["report"] = str(report_path)
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_brain_family_smooth_operation_lock {payload['status']}")
    print(f"smooth_operation_lock={payload['smooth_operation_lock']}")
    print(f"families={payload['family_count']} rows={payload['live_row_count']}")
    print(f"artifact={artifact_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
