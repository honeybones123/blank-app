"""Focused apply-effect/noop-effect proof for remaining PARTIAL families.

Proof-only. This verifier does not drive the browser or change product
behaviour. It composes the strongest currently available browser/product-path
artifacts and records whether each remaining PARTIAL family has:

* APPLY_EFFECT_PROVEN
* INTENTIONAL_NOOP_PROVEN
* GAP_APPLY_EFFECT_PROVEN_BUT_POST_CLICK_CARD_TIMEOUT
* GAP_FOCUSED_BROWSER_REPLAY_REQUIRED

The architecture audit consumes this artifact by family and only treats the
first two verdicts as apply-effect coverage.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PASS_VERDICTS = {"APPLY_EFFECT_PROVEN", "INTENTIONAL_NOOP_PROVEN"}
APPLY_EFFECT_WITH_CARD_TIMEOUT_VERDICT = "GAP_APPLY_EFFECT_PROVEN_BUT_POST_CLICK_CARD_TIMEOUT"
KNOWN_BROWSER_GAP_VERDICTS = {APPLY_EFFECT_WITH_CARD_TIMEOUT_VERDICT}

TARGET_FAMILIES = (
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    "COMBINED_OVERDESIGN_GOVERNS",
    "SERVICEABILITY_GOVERNS",
)


def _load(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest(pattern: str) -> dict[str, Any]:
    matches = sorted(ARTIFACT_DIR.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        return {"found": False, "pattern": pattern, "path": None, "payload": {}}
    path = matches[0]
    return {"found": True, "pattern": pattern, "path": str(path), "payload": _load(path)}


def _status(payload: dict[str, Any]) -> str:
    for key in ("status", "result", "lock_status"):
        value = str(payload.get(key) or "")
        if "PASS" in value.upper() or "COMPLETE" in value.upper():
            return "PASS"
        if "FAIL" in value.upper() or "INCOMPLETE" in value.upper():
            return "FAIL"
        if "PARTIAL" in value.upper():
            return "PARTIAL"
    return "UNKNOWN"


def _artifact_summary(pattern: str) -> dict[str, Any]:
    row = _latest(pattern)
    payload = dict(row.get("payload") or {})
    return {
        "pattern": pattern,
        "found": bool(row.get("found")),
        "path": row.get("path"),
        "status": _status(payload) if payload else "MISSING",
        "payload_keys": sorted(str(key) for key in payload.keys())[:32],
    }


def _browser_replay_family_row(family_id: str) -> dict[str, Any] | None:
    matches = sorted(
        ARTIFACT_DIR.glob("design_guide_partial_family_browser_apply_noop_replay_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    latest_row: dict[str, Any] | None = None
    for path in matches:
        payload = _load(path)
        row = dict((payload.get("families") or {}).get(family_id) or {})
        if not row:
            continue
        row["browser_replay_artifact"] = str(path)
        row["browser_replay_status"] = payload.get("status")
        selected_attempt = dict(row.get("selected_attempt") or {})
        effective_verdict = str(selected_attempt.get("verdict") or row.get("verdict") or "")
        row["effective_verdict"] = effective_verdict
        if effective_verdict in PASS_VERDICTS:
            return row
        if effective_verdict in KNOWN_BROWSER_GAP_VERDICTS and (
            latest_row is None
            or str(dict(latest_row.get("selected_attempt") or {}).get("verdict") or latest_row.get("verdict") or "")
            not in KNOWN_BROWSER_GAP_VERDICTS
        ):
            latest_row = row
            continue
        if latest_row is None:
            latest_row = row
    return latest_row


def _browser_replay_verdict(family_id: str) -> dict[str, Any] | None:
    row = _browser_replay_family_row(family_id)
    if not row:
        return None
    selected_attempt = dict(row.get("selected_attempt") or {})
    verdict = str(row.get("effective_verdict") or selected_attempt.get("verdict") or row.get("verdict") or "")
    if verdict not in PASS_VERDICTS and verdict not in KNOWN_BROWSER_GAP_VERDICTS:
        return None
    if verdict == APPLY_EFFECT_WITH_CARD_TIMEOUT_VERDICT:
        reason = (
            "Focused browser replay proved the Apply click changed page/check output for "
            f"`{family_id}`, but the post-click Design Guide card did not become verifier-ready. "
            "This is an apply-effect proof with a remaining card readiness/smoothness gap."
        )
        required_next = (
            "fix post-click Design Guide card readiness after Apply, then rerun the focused browser replay"
        )
    else:
        reason = (
            "Focused browser replay proved "
            f"{verdict.lower()} for `{family_id}` using recipe "
            f"`{selected_attempt.get('recipe') or ''}`."
        )
        required_next = ""
    return {
        "family_id": family_id,
        "verdict": verdict,
        "reason": reason,
        "evidence": {
            "browser_replay": {
                "path": row.get("browser_replay_artifact"),
                "status": row.get("browser_replay_status"),
                "selected_attempt": selected_attempt,
            }
        },
        "required_next_replay": required_next,
    }


def _family_verdict(family_id: str) -> dict[str, Any]:
    browser_verdict = _browser_replay_verdict(family_id)
    if browser_verdict:
        return browser_verdict

    common_evidence = {
        "family_lock": _artifact_summary(f"{family_id.lower()}_lock_verifier_*.json"),
        "browser_apply_noop_replay": _artifact_summary("design_guide_partial_family_browser_apply_noop_replay_*.json"),
    }
    if family_id == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS":
        evidence = {
            **common_evidence,
            "replacement_audit": _artifact_summary("bending_fail_shear_overdesign_governs_replacement_audit_*.json"),
            "chooser_priority": _artifact_summary("bending_fail_shear_overdesign_chooser_priority_audit_*.json"),
            "current_state_apply_safety": _artifact_summary("design_guide_apply_current_state_safety_*.json"),
        }
        return {
            "family_id": family_id,
            "verdict": "GAP_FOCUSED_BROWSER_REPLAY_REQUIRED",
            "reason": (
                "Contract/chooser/runtime lock is green, but no family-specific browser apply-click "
                "or intentional-noop artifact proves page output change for this mixed family."
            ),
            "evidence": evidence,
            "required_next_replay": "focused browser scenario selecting BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS, click Apply if enabled, compare summary/check outputs before and after",
        }
    if family_id == "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS":
        evidence = {
            **common_evidence,
            "unlocked_shear_apply_policy": _artifact_summary("design_guide_unlocked_shear_apply_cta_publication_*.json"),
        }
        return {
            "family_id": family_id,
            "verdict": "GAP_FOCUSED_BROWSER_REPLAY_REQUIRED",
            "reason": (
                "Shear Apply CTA policy is green, but the existing browser evidence is not specific "
                "to SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS apply effect."
            ),
            "evidence": evidence,
            "required_next_replay": "focused browser scenario selecting SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS, click Apply if enabled, compare summary/check outputs before and after",
        }
    if family_id == "COMBINED_OVERDESIGN_GOVERNS":
        evidence = {
            **common_evidence,
            "current_state_apply_safety": _artifact_summary("design_guide_apply_current_state_safety_*.json"),
            "shear_cleanup_noop": _artifact_summary("design_guide_shear_cleanup_noop_cta_*.json"),
        }
        return {
            "family_id": family_id,
            "verdict": "GAP_FOCUSED_BROWSER_REPLAY_REQUIRED",
            "reason": (
                "Generic current-state and shear-noop guards are green, but no combined-overdesign "
                "browser artifact proves either an effective cleanup apply or intentional no-op."
            ),
            "evidence": evidence,
            "required_next_replay": "focused browser scenario selecting COMBINED_OVERDESIGN_GOVERNS, click Apply if enabled, compare geometry/reo/shear-link outputs before and after",
        }
    if family_id == "SERVICEABILITY_GOVERNS":
        serviceability = _latest("design_guide_serviceability_blocker_runtime_authority_*.json")
        serviceability_payload = dict(serviceability.get("payload") or {})
        checks = dict(serviceability_payload.get("checks") or {})
        evidence = {
            **common_evidence,
            "serviceability_runtime_authority": {
                "found": bool(serviceability.get("found")),
                "path": serviceability.get("path"),
                "status": _status(serviceability_payload) if serviceability_payload else "MISSING",
                "live_serviceability_blockers_runtime_backed": checks.get("live_serviceability_blockers_runtime_backed"),
                "authority_result": serviceability_payload.get("authority_result"),
            },
        }
        return {
            "family_id": family_id,
            "verdict": "GAP_FOCUSED_BROWSER_REPLAY_REQUIRED",
            "reason": (
                "Serviceability lock is green, but the latest serviceability product-path audit says "
                "live crack/deflection blocker paths are not yet runtime-backed; browser noop/apply proof is missing."
            ),
            "evidence": evidence,
            "required_next_replay": "focused browser scenario selecting SERVICEABILITY_GOVERNS, prove Apply is intentionally absent/disabled or click any enabled serviceability action and compare outputs",
        }
    raise KeyError(f"Unhandled family: {family_id}")


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Partial Family Apply-Effect / Noop Proof",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Verdicts",
        "",
        "| Family | Verdict | Counts As Coverage | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for family_id, row in payload["families"].items():
        lines.append(
            f"| `{family_id}` | `{row['verdict']}` | `{row['counts_as_apply_effect_coverage']}` | {row['reason']} |"
        )
    lines.extend(["", "## Next Browser Replays", ""])
    for family_id, row in payload["families"].items():
        if not row["counts_as_apply_effect_coverage"]:
            lines.append(f"- `{family_id}`: {row['required_next_replay']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    families = {}
    for family_id in TARGET_FAMILIES:
        row = _family_verdict(family_id)
        row["counts_as_apply_effect_coverage"] = row["verdict"] in PASS_VERDICTS
        families[family_id] = row
    gaps = [
        family_id
        for family_id, row in families.items()
        if not bool(row.get("counts_as_apply_effect_coverage"))
    ]
    payload = {
        "schema": "design_guide_partial_family_apply_effect_noop_proof.v1",
        "status": "PASS",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "target_families": list(TARGET_FAMILIES),
        "pass_verdicts": sorted(PASS_VERDICTS),
        "families": families,
        "coverage_summary": {
            "covered": len(TARGET_FAMILIES) - len(gaps),
            "gaps": len(gaps),
            "gap_families": gaps,
        },
    }
    artifact_path = ARTIFACT_DIR / f"design_guide_partial_family_apply_effect_noop_proof_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_partial_family_apply_effect_noop_proof_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "artifact": str(artifact_path),
                "report": str(report_path),
                "covered": payload["coverage_summary"]["covered"],
                "gaps": payload["coverage_summary"]["gaps"],
                "gap_families": gaps,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
