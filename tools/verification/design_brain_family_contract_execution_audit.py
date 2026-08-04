"""Family-wide 10-scenario contract/actionability audit.

This audit is stricter than the structural family 10-fuzz runner, but it keeps
the family contracts honest:

- executable repair families must expose a live action button and applying it
  must change the page to a compliant result
- non-executable or terminal families must still publish an explicit
  engineering reason and must not fabricate an Apply path
- no family may publish a result that breaks geometry/reo legality
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_brain_family_contract_compliance_summary import (  # noqa: E402
    FAMILY_SPECS,
    _family_row,
)
from tools.verification.run_family_10_fuzz_audit import (  # noqa: E402
    LIVE_EXECUTABLE_FAMILIES,
    _audit_family,
    _safe_dict,
    _scenario_trigger_rows,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

CTA_EXPECTATIONS: dict[str, str] = {
    "BENDING_FAIL_GOVERNS": "EXECUTABLE_REPAIR_REQUIRED",
    "SHEAR_FAIL_GOVERNS": "EXECUTABLE_REPAIR_REQUIRED",
    "COMBINED_BENDING_SHEAR_FAIL": "EXECUTABLE_REPAIR_REQUIRED",
    "BENDING_OVERDESIGN_GOVERNS": "ACTIONABLE_OR_ENGINEERING_REASON",
    "SHEAR_OVERDESIGN_GOVERNS": "ACTIONABLE_OR_ENGINEERING_REASON",
    "COMBINED_OVERDESIGN": "ACTIONABLE_OR_ENGINEERING_REASON",
    "MIN_BENDING_REO_GOVERNS": "ENGINEERING_REASON_ONLY",
    "MIN_SHEAR_REO_GOVERNS": "ENGINEERING_REASON_ONLY",
    "GEOMETRY_DETAILING_GOVERNS": "ACTIONABLE_OR_ENGINEERING_REASON",
    "SERVICEABILITY_GOVERNS": "ACTIONABLE_OR_ENGINEERING_REASON",
    "LOCKED_NO_REPAIR": "ENGINEERING_REASON_ONLY",
    "TARGET_BAND_REACHED": "ENGINEERING_REASON_ONLY",
    "EXACT_STOP_PROVEN": "ENGINEERING_REASON_ONLY",
}

REQUIRES_CLASSIFICATION_RULE: dict[str, bool] = {
    spec.family_id: bool(spec.requires_classification_rule) for spec in FAMILY_SPECS
}

RESULT_POLICIES: dict[str, str] = {
    "BENDING_FAIL_GOVERNS": "REPAIR_TO_COMPLIANCE",
    "SHEAR_FAIL_GOVERNS": "REPAIR_TO_COMPLIANCE",
    "COMBINED_BENDING_SHEAR_FAIL": "REPAIR_TO_COMPLIANCE",
    "BENDING_OVERDESIGN_GOVERNS": "OPTIMISE_TO_TARGET_BAND_OR_REASON",
    "SHEAR_OVERDESIGN_GOVERNS": "OPTIMISE_TO_TARGET_BAND_OR_REASON",
    "COMBINED_OVERDESIGN": "OPTIMISE_TO_TARGET_BAND_OR_REASON",
    "MIN_BENDING_REO_GOVERNS": "TERMINAL_OR_BLOCKED_EXPLICIT_REASON",
    "MIN_SHEAR_REO_GOVERNS": "TERMINAL_OR_BLOCKED_EXPLICIT_REASON",
    "GEOMETRY_DETAILING_GOVERNS": "REPAIR_OR_EXPLICIT_BLOCKER",
    "SERVICEABILITY_GOVERNS": "REPAIR_OR_EXPLICIT_BLOCKER",
    "LOCKED_NO_REPAIR": "TERMINAL_OR_BLOCKED_EXPLICIT_REASON",
    "TARGET_BAND_REACHED": "TERMINAL_OR_BLOCKED_EXPLICIT_REASON",
    "EXACT_STOP_PROVEN": "TERMINAL_OR_BLOCKED_EXPLICIT_REASON",
}


def _stable_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())


def _expected_families() -> tuple[str, ...]:
    return tuple(spec.family_id for spec in FAMILY_SPECS)


def _count_trigger_passes(scenarios: list[dict[str, Any]]) -> int:
    return sum(1 for row in scenarios if row.get("trigger_passed"))


def _publication_reason_proven(summary_row: dict[str, Any], family_id: str) -> bool:
    if summary_row.get("final_status") != "PASS":
        return False
    expectation = CTA_EXPECTATIONS.get(family_id, "ENGINEERING_REASON_ONLY")
    if expectation == "EXECUTABLE_REPAIR_REQUIRED":
        return True
    return (
        summary_row.get("product_consumes_contract") == "PASS"
        and summary_row.get("final_visible_output_matches_selected_family_result") == "PASS"
    )


def _live_row_passes_contract(row: dict[str, Any]) -> tuple[bool, list[str]]:
    failures = list(row.get("failures") or [])
    click_result = _safe_dict(row.get("click_result"))
    before_probe = _safe_dict(row.get("publication_probe_before"))
    after_probe = _safe_dict(row.get("publication_probe_after"))
    run_end = _safe_dict(row.get("run_end_event"))
    run_data = _safe_dict(run_end.get("data"))
    compare = _safe_dict(run_data.get("compare"))
    final_updates = _safe_dict(compare.get("final_updates"))
    before_hash = before_probe.get("publication_hash")
    after_hash = after_probe.get("publication_hash")
    page_changed = bool(final_updates) or (before_hash and after_hash and before_hash != after_hash)
    if not click_result.get("clicked"):
        failures.append("button_not_clicked")
    if run_end and run_data.get("all_key_pass") is not True:
        failures.append("post_apply_all_key_pass_false")
    final_worst = run_data.get("final_live_worst_util")
    if final_worst is not None:
        try:
            if float(final_worst) > 1.0:
                failures.append(f"final_live_worst_util_above_limit:{final_worst}")
        except Exception:
            failures.append("final_live_worst_util_not_numeric")
    else:
        failures.append("final_live_worst_util_missing")
    if not page_changed:
        failures.append("page_state_not_changed_after_apply")
    return (not failures, failures)


def _run_live_family_rows(
    family_id: str,
    *,
    base_url: str,
    headed: bool,
    live_card_timeout_s: float,
    live_apply_timeout_s: float,
) -> dict[str, Any]:
    return _audit_family(
        family_id,
        1007,
        True,
        base_url=base_url,
        headed=headed,
        live_card_timeout_s=live_card_timeout_s,
        live_apply_timeout_s=live_apply_timeout_s,
    )


def _reuse_live_family_row(reuse_snapshot: dict[str, Any], family_id: str) -> dict[str, Any] | None:
    for row in list(reuse_snapshot.get("families") or []):
        if str(row.get("family_id") or "") == family_id and row.get("live_execution_required"):
            return row
    return None


def _family_execution_row(
    family_id: str,
    summary_row: dict[str, Any],
    *,
    base_url: str | None,
    headed: bool,
    live_card_timeout_s: float,
    live_apply_timeout_s: float,
    reuse_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scenarios = _scenario_trigger_rows(family_id, 1007)
    trigger_passes = _count_trigger_passes(scenarios)
    trigger_required = REQUIRES_CLASSIFICATION_RULE.get(family_id, True)
    expectation = CTA_EXPECTATIONS[family_id]
    result_policy = RESULT_POLICIES[family_id]
    contract_summary_pass = summary_row.get("final_status") == "PASS"
    publication_reason_pass = _publication_reason_proven(summary_row, family_id)

    live_audit: dict[str, Any] = {
        "executed": False,
        "status": "NOT_RUN",
        "reason": "live execution not required for this family in this audit slice",
    }
    live_contract_pass = expectation != "EXECUTABLE_REPAIR_REQUIRED"
    live_failures: list[str] = []
    enabled_button_count = 0
    applied_button_count = 0
    changed_page_count = 0
    explicit_reason_required = expectation != "EXECUTABLE_REPAIR_REQUIRED"

    if family_id in LIVE_EXECUTABLE_FAMILIES:
        reused_live_row = _reuse_live_family_row(reuse_snapshot or {}, family_id)
        if reused_live_row is not None:
            enabled_button_count = int(reused_live_row.get("live_button_enabled_count") or 0)
            applied_button_count = int(reused_live_row.get("live_button_applied_count") or 0)
            changed_page_count = int(reused_live_row.get("live_page_changed_count") or 0)
            live_contract_pass = bool(reused_live_row.get("live_contract_pass"))
            live_failures = list(reused_live_row.get("live_failures") or [])
            live_audit = {
                "live_execution": {
                    "status": "REUSED",
                    "reused_from_artifact": True,
                },
            }
        elif not base_url:
            live_failures.append("base_url_required_for_live_family_execution")
            live_contract_pass = False
        else:
            live_audit = _run_live_family_rows(
                family_id,
                base_url=base_url,
                headed=headed,
                live_card_timeout_s=live_card_timeout_s,
                live_apply_timeout_s=live_apply_timeout_s,
            )
            rows = list(_safe_dict(live_audit).get("live_execution", {}).get("rows") or [])
            if not rows:
                live_failures.append("no_live_rows_captured")
                live_contract_pass = False
            else:
                for row in rows:
                    probe = _safe_dict(row.get("button_probe_before"))
                    if int(probe.get("enabled_action_count") or 0) > 0:
                        enabled_button_count += 1
                    click_result = _safe_dict(row.get("click_result"))
                    if click_result.get("clicked"):
                        applied_button_count += 1
                    passed, row_failures = _live_row_passes_contract(row)
                    if passed:
                        before_hash = _safe_dict(row.get("publication_probe_before")).get("publication_hash")
                        after_hash = _safe_dict(row.get("publication_probe_after")).get("publication_hash")
                        run_data = _safe_dict(_safe_dict(row.get("run_end_event")).get("data"))
                        final_updates = _safe_dict(_safe_dict(run_data.get("compare")).get("final_updates"))
                        if final_updates or (before_hash and after_hash and before_hash != after_hash):
                            changed_page_count += 1
                    else:
                        live_failures.extend([f"{row.get('scenario_id')}:{item}" for item in row_failures])
                if expectation == "EXECUTABLE_REPAIR_REQUIRED":
                    live_contract_pass = (
                        enabled_button_count == 10
                        and applied_button_count == 10
                        and changed_page_count == 10
                        and not live_failures
                    )
                else:
                    live_contract_pass = not live_failures

    legality_pass = contract_summary_pass and (live_contract_pass if family_id in LIVE_EXECUTABLE_FAMILIES else True)
    final_status = (
        "PASS"
        if (
            ((trigger_passes == 10) if trigger_required else True)
            and contract_summary_pass
            and publication_reason_pass
            and live_contract_pass
            and legality_pass
        )
        else "FAIL"
    )
    issues: list[str] = []
    if trigger_required and trigger_passes != 10:
        issues.append(f"trigger_mismatch:{trigger_passes}/10")
    if not contract_summary_pass:
        issues.append("family_contract_compliance_summary_failed")
    if not publication_reason_pass:
        issues.append("publication_reason_not_proven")
    if family_id in LIVE_EXECUTABLE_FAMILIES and not live_contract_pass:
        issues.extend(live_failures or ["live_contract_failed"])
    if not legality_pass:
        issues.append("geometry_reo_legality_not_proven")

    return {
        "family_id": family_id,
        "cta_expectation": expectation,
        "result_policy": result_policy,
        "contract_summary_status": summary_row.get("final_status"),
        "trigger_passes": trigger_passes,
        "trigger_total": 10,
        "trigger_required": trigger_required,
        "contract_consumption_proven": summary_row.get("product_consumes_contract") == "PASS",
        "final_visible_output_proven": summary_row.get("final_visible_output_matches_selected_family_result")
        == "PASS",
        "cta_action_proven": summary_row.get("cta_action_works") == "PASS",
        "explicit_engineering_reason_required": explicit_reason_required,
        "explicit_engineering_reason_proven": publication_reason_pass,
        "live_execution_required": family_id in LIVE_EXECUTABLE_FAMILIES,
        "live_execution_status": _safe_dict(live_audit).get("live_execution", {}).get("status")
        if family_id in LIVE_EXECUTABLE_FAMILIES
        else "NOT_REQUIRED",
        "live_button_enabled_count": enabled_button_count,
        "live_button_applied_count": applied_button_count,
        "live_page_changed_count": changed_page_count,
        "live_contract_pass": live_contract_pass,
        "legality_pass": legality_pass,
        "issues": issues,
        "final_status": final_status,
        "summary_row": {
            "contract_exists": summary_row.get("contract_exists"),
            "product_consumes_contract": summary_row.get("product_consumes_contract"),
            "verifier_enforces_contract": summary_row.get("verifier_enforces_contract"),
            "fuzz_coverage_exists": summary_row.get("fuzz_coverage_exists"),
            "cta_action_works": summary_row.get("cta_action_works"),
            "final_visible_output_matches_selected_family_result": summary_row.get(
                "final_visible_output_matches_selected_family_result"
            ),
        },
        "live_audit_probe_mapping": _safe_dict(_safe_dict(live_audit).get("live_audit_probe_mapping")),
        "live_failures": live_failures,
        "report": summary_row.get("report"),
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stable_stamp()
    json_path = ARTIFACT_DIR / f"design_brain_family_contract_execution_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_family_contract_execution_audit_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(md_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Design Brain Family Contract Execution Audit",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "This audit uses 10 deterministic trigger scenarios per family. Repair families must prove a live executable",
        "button path. Terminal/blocker/no-action families must instead prove explicit engineering reason and",
        "must not fabricate an Apply path.",
        "",
        "## Summary",
        "",
        f"- Families audited: `{snapshot['summary']['families_audited']}`",
        f"- Families passing: `{snapshot['summary']['families_passed']}`",
        f"- Families failing: `{snapshot['summary']['families_failed']}`",
        f"- Live executable families audited in browser: `{snapshot['summary']['live_families_audited']}`",
        f"- Live executable families passed: `{snapshot['summary']['live_families_passed']}`",
        f"- Live executable families failed: `{snapshot['summary']['live_families_failed']}`",
        "",
        "## Family Table",
        "",
        "| Family | CTA expectation | Trigger 10/10 | Live apply | Reason proof | Legality | Status |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in snapshot["families"]:
        lines.append(
            f"| {row['family_id']} | {row['cta_expectation']} | {row['trigger_passes']}/10 | "
            f"{'PASS' if row['live_contract_pass'] else 'FAIL'} | "
            f"{'PASS' if row['explicit_engineering_reason_proven'] else 'FAIL'} | "
            f"{'PASS' if row['legality_pass'] else 'FAIL'} | `{row['final_status']}` |"
        )
    lines.extend(["", "## Per-family Details", ""])
    for row in snapshot["families"]:
        lines.extend(
            [
                f"### {row['family_id']}",
                "",
                f"- CTA expectation: `{row['cta_expectation']}`",
                f"- result policy: `{row['result_policy']}`",
                f"- trigger pass count: `{row['trigger_passes']}/{row['trigger_total']}`",
                f"- contract summary status: `{row['contract_summary_status']}`",
                f"- live execution required: `{row['live_execution_required']}`",
                f"- live execution status: `{row['live_execution_status']}`",
                f"- live enabled button count: `{row['live_button_enabled_count']}`",
                f"- live applied button count: `{row['live_button_applied_count']}`",
                f"- live page changed count: `{row['live_page_changed_count']}`",
                f"- explicit engineering reason proven: `{row['explicit_engineering_reason_proven']}`",
                f"- legality pass: `{row['legality_pass']}`",
                f"- issues: {', '.join(row['issues']) if row['issues'] else 'none'}",
                f"- final status: `{row['final_status']}`",
                "",
            ]
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8504", help="Running app base URL for live families")
    parser.add_argument("--headed", action="store_true", help="Run browser headed for live families")
    parser.add_argument("--live-card-timeout-s", type=float, default=20.0)
    parser.add_argument("--live-apply-timeout-s", type=float, default=12.0)
    parser.add_argument("--reuse-live-artifact", default=None, help="Reuse live executable family evidence from a prior audit artifact")
    args = parser.parse_args(argv)

    summary_rows = {row["family_id"]: row for row in (_family_row(spec) for spec in FAMILY_SPECS)}
    family_ids = _expected_families()
    reuse_snapshot: dict[str, Any] = {}
    if args.reuse_live_artifact:
        reuse_path = Path(str(args.reuse_live_artifact))
        if reuse_path.exists():
            reuse_snapshot = json.loads(reuse_path.read_text(encoding="utf-8"))
    rows = [
        _family_execution_row(
            family_id,
            summary_rows[family_id],
            base_url=args.base_url,
            headed=bool(args.headed),
            live_card_timeout_s=float(args.live_card_timeout_s),
            live_apply_timeout_s=float(args.live_apply_timeout_s),
            reuse_snapshot=reuse_snapshot,
        )
        for family_id in family_ids
    ]
    snapshot = {
        "schema": "design_brain_family_contract_execution_audit.v1",
        "result": "PASS" if all(row["final_status"] == "PASS" for row in rows) else "FAIL",
        "families": rows,
        "summary": {
            "families_audited": len(rows),
            "families_passed": sum(1 for row in rows if row["final_status"] == "PASS"),
            "families_failed": sum(1 for row in rows if row["final_status"] != "PASS"),
            "live_families_audited": sum(1 for row in rows if row["live_execution_required"]),
            "live_families_passed": sum(
                1
                for row in rows
                if row["live_execution_required"] and row["live_contract_pass"]
            ),
            "live_families_failed": sum(
                1
                for row in rows
                if row["live_execution_required"] and not row["live_contract_pass"]
            ),
        },
        "commands_required": [
            "python -m compileall -q design_brain ui tools/verification",
            "python tools/verification/design_brain_inputs_page_zero_authority_inventory_lock.py",
            "python tools/verification/design_brain_family_contract_compliance_summary.py",
            "python tools/verification/design_brain_family_contract_execution_audit.py",
        ],
    }
    json_path, md_path = _write(snapshot)
    print(
        "design_brain_family_contract_execution_audit PASS"
        if snapshot["result"] == "PASS"
        else "design_brain_family_contract_execution_audit FAIL"
    )
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
