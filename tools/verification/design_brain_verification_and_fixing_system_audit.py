"""Audit the Design Brain verification and fixing workflow.

This is an audit-only verifier.  It does not run live fuzz, delete product
code, or change behaviour.  It checks whether the verification system can:

- catch live red-screen/runtime failures,
- prevent missing extracted bridge dependencies,
- stop retired visible legacy surfaces from returning,
- promote live bugs into permanent regressions,
- distinguish focused fixes from full app certification,
- and prove when broad legacy deletion is actually safe.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read(path: str) -> str:
    target = ROOT / path
    return target.read_text(encoding="utf-8", errors="ignore") if target.exists() else ""


def _read_json(path: Path | str) -> dict[str, Any]:
    target = Path(path)
    if not target.is_absolute():
        target = ROOT / target
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    return path, _read_json(path)


def _status(payload: dict[str, Any]) -> str:
    return str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("completion_status")
        or payload.get("meta_lock_status")
        or "MISSING"
    )


def _active_live_bug_rows() -> list[dict[str, Any]]:
    registry = _read_json("tools/verification/design_guide_live_bug_regression_registry.json")
    rows: list[dict[str, Any]] = []
    for entry in list(registry.get("entries") or []):
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "").strip().lower()
        verifier = str(entry.get("regression_verifier") or "").strip()
        rows.append(
            {
                "bug_id": entry.get("bug_id"),
                "status": status,
                "family_id": entry.get("family_id"),
                "regression_verifier": verifier,
                "verifier_exists": bool(verifier and (ROOT / verifier).exists()),
                "expected_card_state": entry.get("expected_card_state"),
                "expected_cta_state": entry.get("expected_cta_state"),
            }
        )
    return rows


def _artifact_status_rows() -> list[dict[str, Any]]:
    prefixes = {
        "regression_contracts": "regression_invariant_audit",
        "shared_bridge_dependency_binding": "shared_bridge_dependency_binding_lock",
        "legacy_visible_surface_deletion": "design_guide_legacy_visible_surface_deletion_lock",
        "live_bug_registry_contract": "design_guide_live_bug_registry_contract",
        "red_screen_sentinel_contract": "browser_red_screen_sentinel_contract",
        "universal_live_family_lock": "design_brain_universal_live_family_lock",
        "universal_verification_meta_lock": "design_brain_universal_verification_meta_lock",
        "app_stability_completion": "app_stability_goal_completion_audit",
        "family_10_fuzz": "family_10_fuzz_audit",
        "critical_workflows": "app_stability_critical_workflows_lock",
        "inputs_apply_10x": "app_stability_inputs_apply_10x_workflow_lock",
        "visual_consistency": "design_guide_browser_live_visual_consistency",
    }
    rows: list[dict[str, Any]] = []
    for key, prefix in prefixes.items():
        path, payload = _latest(prefix)
        rows.append(
            {
                "key": key,
                "prefix": prefix,
                "path": str(path) if path else None,
                "status": _status(payload),
                "meta_lock_status": payload.get("meta_lock_status"),
                "completion_status": payload.get("completion_status"),
                "universal_lock_status": payload.get("universal_lock_status"),
            }
        )
    return rows


def _workflow_checks() -> dict[str, bool]:
    workflow = _read("tools/verification/VERIFICATION_WORKFLOW.md")
    meta = _read("tools/verification/design_brain_universal_verification_meta_lock.py")
    completion = _read("tools/verification/app_stability_goal_completion_audit.py")
    family_gate = _read("tools/verification/families/family_live_fuzz_regression_lock_gate.py")
    regression_contracts = _read("tools/verification/check_regression_contracts.py")
    live_bug_contract = _read("tools/verification/design_guide_live_bug_registry_contract.py")
    return {
        "staged_fix_workflow_documented": "Stage 1 - Focused Replay" in workflow
        and "Stage 6 - Fully Verified Family Lock" in workflow,
        "fix_protection_rule_documented": "Fix Protection Rule" in workflow
        and "same failure mode cannot silently return" in workflow,
        "universal_family_ladder_proof_required": "contract ladder order" in workflow
        and "candidate generation per lane" in workflow
        and "terminal result after Apply" in workflow,
        "red_screen_sentinel_in_family_gate": "browser_red_screen_findings" in family_gate
        and "live_browser_red_screen_sentinel" in family_gate,
        "shared_bridge_dependency_lock_in_meta": "shared_bridge_dependency_binding_lock" in meta
        and "shared_bridge_dependency_binding_lock" in completion,
        "legacy_visible_surface_lock_in_meta": "legacy_visible_surface_deletion_lock" in meta
        and "legacy_visible_surface_deletion_lock" in completion,
        "regression_contract_checker_exists": "regression_contract_manifest.json" in regression_contracts
        and "never_regress_rule" in regression_contracts,
        "active_live_bug_registry_is_checked_by_contract_checker": "design_guide_live_bug_regression_registry" in regression_contracts,
        "active_live_bug_registry_contract_exists": "design_guide_live_bug_regression_registry.json" in live_bug_contract
        and "active live/browser-observed bug" in live_bug_contract,
        "active_live_bug_registry_contract_in_meta": "live_bug_registry_contract" in meta,
        "active_live_bug_registry_contract_in_completion": "live_bug_registry_contract" in completion,
        "completion_audit_blocks_legacy_deletion_until_complete": "safe_to_begin_legacy_deletion" in completion
        and 'completion_status == "COMPLETE"' in completion,
        "meta_lock_has_enforce_mode": "--enforce" in meta and "NOT_LOCKED" in meta,
    }


def _classify_findings(checks: dict[str, bool], active_bugs: list[dict[str, Any]], artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    def add(severity: str, title: str, evidence: Any, recommendation: str) -> None:
        findings.append(
            {
                "severity": severity,
                "title": title,
                "evidence": evidence,
                "recommendation": recommendation,
            }
        )

    live_registry_hard_gate = (
        checks["active_live_bug_registry_contract_exists"]
        and checks["active_live_bug_registry_contract_in_meta"]
        and checks["active_live_bug_registry_contract_in_completion"]
    )
    if not live_registry_hard_gate:
        add(
            "HIGH",
            "Active live-bug registry is not enforced as a composed gate",
            {
                "checked_by_regression_contract_checker": checks[
                    "active_live_bug_registry_is_checked_by_contract_checker"
                ],
                "separate_contract_exists": checks["active_live_bug_registry_contract_exists"],
                "separate_contract_in_meta": checks["active_live_bug_registry_contract_in_meta"],
                "separate_contract_in_completion": checks["active_live_bug_registry_contract_in_completion"],
            },
            "Keep the live-bug registry contract gate wired into meta/completion and require a PASS artifact before full verification.",
        )
    else:
        add(
            "INFO",
            "Active live-bug registry now has a composed enforcement gate",
            "design_guide_live_bug_registry_contract.py exists and is wired into the meta/completion gates.",
            "Run the live-bug registry contract after focused bug verifiers and before claiming full verification.",
        )
    missing_active_verifiers = [row for row in active_bugs if row["status"] == "active" and not row["verifier_exists"]]
    if missing_active_verifiers:
        add(
            "HIGH",
            "Some active live bugs point at missing verifier files",
            missing_active_verifiers,
            "Create or correct each missing verifier before calling the bug fixed.",
        )
    meta = next((row for row in artifacts if row["key"] == "universal_verification_meta_lock"), {})
    completion = next((row for row in artifacts if row["key"] == "app_stability_completion"), {})
    universal = next((row for row in artifacts if row["key"] == "universal_live_family_lock"), {})
    if meta.get("meta_lock_status") != "LOCKED":
        add(
            "MEDIUM",
            "Universal verification meta-lock is not locked",
            meta,
            "Do not describe the app as fully verified until the live universal family lock is current and meta-lock is run with --enforce.",
        )
    if completion.get("completion_status") != "COMPLETE":
        add(
            "MEDIUM",
            "App stability completion remains partial",
            completion,
            "Keep using focused fixes, but do not start broad legacy deletion or architecture claims from this state.",
        )
    if universal.get("universal_lock_status") != "LOCKED":
        add(
            "MEDIUM",
            "Universal live family lock is not locked",
            universal,
            "Run the all-family live lock only after focused gates are green; use it as the release/certification gate.",
        )
    if checks["legacy_visible_surface_lock_in_meta"]:
        add(
            "INFO",
            "Named old visible surfaces are now regression-locked",
            "Old launch card, old advisory panel, and one-click stale feedback banner have a source-level deletion lock.",
            "Extend this pattern to other legacy UI surfaces only after each one is proven non-authoritative or dead.",
        )
    if checks["red_screen_sentinel_in_family_gate"]:
        add(
            "INFO",
            "Live red-screen/runtime failures are now part of the family gate",
            "Family gate imports browser_red_screen_findings and has live_browser_red_screen_sentinel phase.",
            "Also add a top-level browser DOM sentinel to critical workflow/apply gates if not already covered.",
        )
    return findings


def _next_slices(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "priority": "1",
            "slice": "Run and enforce the active live-bug registry contract gate",
            "why": "Active live bugs now have a composed gate, but full verification still needs a fresh PASS artifact.",
            "expected_output": "tools/verification/design_guide_live_bug_registry_contract.py",
        },
        {
            "priority": "2",
            "slice": "Add top-level browser DOM health sentinel to critical workflow locks",
            "why": "Family live rows are protected, but shared UI/workflow gates should also fail on red screens, duplicate cards, stale banners, and old launch shells.",
            "expected_output": "Shared helper used by app_stability_critical_workflows_lock and inputs_apply_10x workflow.",
        },
        {
            "priority": "3",
            "slice": "Verifier taxonomy and retirement map",
            "why": "There are many historical verifiers; classify them as release gate, focused regression, audit-only, stale/retired, or deletion candidate so runtime stays sane.",
            "expected_output": "artifacts/audits/verification_taxonomy_and_retirement_map_<timestamp>.md",
        },
        {
            "priority": "4",
            "slice": "Live visual regression baseline for shared layout",
            "why": "Layout regressions keep leaking through engineering-focused gates.",
            "expected_output": "Stable screenshot/DOM diff for Inputs summary, diagram, Batch design, Design Guide, tabs, and calc panels.",
        },
    ]


def _build() -> dict[str, Any]:
    checks = _workflow_checks()
    active_bugs = _active_live_bug_rows()
    artifacts = _artifact_status_rows()
    findings = _classify_findings(checks, active_bugs, artifacts)
    return {
        "schema": "design_brain.verification_and_fixing_system_audit.v1",
        "status": "PASS",
        "timestamp": _stamp(),
        "product_behaviour_changed": False,
        "audit_scope": [
            "tools/verification/VERIFICATION_WORKFLOW.md",
            "tools/verification/check_regression_contracts.py",
            "tools/verification/design_guide_live_bug_regression_registry.json",
            "tools/verification/design_guide_live_bug_registry_contract.py",
            "tools/verification/design_brain_universal_live_family_lock.py",
            "tools/verification/families/family_live_fuzz_regression_lock_gate.py",
            "tools/verification/design_brain_universal_verification_meta_lock.py",
            "tools/verification/app_stability_goal_completion_audit.py",
        ],
        "workflow_checks": checks,
        "active_live_bug_rows": active_bugs,
        "artifact_status_rows": artifacts,
        "findings": findings,
        "next_slices": _next_slices(findings),
        "overall_assessment": {
            "strength": "The system is much stronger than a normal app test setup: staged fixes, focused replays, family locks, live browser fuzz, red-screen sentinel, dependency binding, and legacy visible-surface locks all exist.",
            "main_gap": "The active live-bug registry is not yet a hard composed gate, and visual/shared workflow sentinels are less universal than family gates.",
            "risk": "A bug can still be recorded as active with a verifier path while not being automatically required by the main completion gates.",
        },
    }


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Brain Verification And Fixing System Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Overall",
        "",
        f"- Strength: {payload['overall_assessment']['strength']}",
        f"- Main gap: {payload['overall_assessment']['main_gap']}",
        f"- Risk: {payload['overall_assessment']['risk']}",
        "",
        "## Workflow Checks",
        "",
    ]
    for key, value in dict(payload["workflow_checks"]).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Findings", ""])
    for row in payload["findings"]:
        lines.append(f"### `{row['severity']}` - {row['title']}")
        lines.append(f"- evidence: `{row['evidence']}`")
        lines.append(f"- recommendation: {row['recommendation']}")
        lines.append("")
    lines.extend(["## Active Live Bug Registry", ""])
    lines.append("| Bug | Status | Family | Verifier exists | Verifier |")
    lines.append("| --- | --- | --- | ---: | --- |")
    for row in payload["active_live_bug_rows"]:
        lines.append(
            f"| `{row['bug_id']}` | `{row['status']}` | `{row['family_id']}` | "
            f"`{row['verifier_exists']}` | `{row['regression_verifier']}` |"
        )
    lines.extend(["", "## Latest Artifact Snapshot", ""])
    lines.append("| Key | Status | Extra | Artifact |")
    lines.append("| --- | --- | --- | --- |")
    for row in payload["artifact_status_rows"]:
        extra = row.get("meta_lock_status") or row.get("completion_status") or row.get("universal_lock_status") or ""
        lines.append(f"| `{row['key']}` | `{row['status']}` | `{extra}` | `{row['path']}` |")
    lines.extend(["", "## Recommended Next Slices", ""])
    for row in payload["next_slices"]:
        lines.append(f"{row['priority']}. **{row['slice']}**")
        lines.append(f"   - why: {row['why']}")
        lines.append(f"   - output: `{row['expected_output']}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build()
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"design_brain_verification_and_fixing_system_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_verification_and_fixing_system_audit_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_markdown(payload, md_path)
    print(f"design_brain_verification_and_fixing_system_audit {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
