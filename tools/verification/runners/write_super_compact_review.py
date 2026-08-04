from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]


def _relative(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _latest_super_run() -> Path | None:
    root = REPO / "artifacts" / "verification" / "latest" / "super_verification_runs"
    if not root.exists():
        root = REPO / "artifacts" / "super_verification_runs"
    if not root.exists():
        return None
    runs = [path for path in root.iterdir() if path.is_dir() and (path / "super_summary.json").exists()]
    if not runs:
        return None
    return max(runs, key=lambda p: p.stat().st_mtime)


def _gate(run_dir: Path, name: str) -> dict[str, Any]:
    path = run_dir / "gates" / f"{name}.json"
    if not path.exists():
        return {}
    try:
        return _load_json(path)
    except Exception as exc:
        return {"status": "CRASH", "error": str(exc)}


def _effective_gate_status(gate: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    runner_status = str(gate.get("runner_status") or "").upper()
    if runner_status and runner_status != "PASS":
        reasons.append(f"runner_status:{runner_status}")
    source_verdict = str(gate.get("source_verdict") or gate.get("verdict") or "").upper()
    if source_verdict in {"FAIL", "INVALID", "CRASH"}:
        reasons.append(f"top_level_verdict:{source_verdict}")
    validity = str(
        gate.get("source_verifier_validity_status")
        or gate.get("verifier_validity_status")
        or ""
    ).upper()
    if validity == "INVALID":
        reasons.append("verifier_validity_status:INVALID")
    one_click = str(
        gate.get("source_one_click_contract_status")
        or gate.get("one_click_contract_status")
        or ""
    ).upper()
    if one_click and one_click != "PASS":
        reasons.append(f"one_click_contract_status:{one_click}")
    reasons.extend(str(reason) for reason in (gate.get("gate_validity_fail_reasons") or []))
    status = "FAIL" if reasons or str(gate.get("status") or "").upper() != "PASS" else "PASS"
    return status, sorted(set(reasons))


def _summary_gate_rows(summary: dict[str, Any], gate_files: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in summary.get("gates") or []:
        if not isinstance(row, dict):
            continue
        merged = dict(row)
        gate_file = gate_files.get(str(row.get("name") or ""))
        if gate_file:
            for key in (
                "status",
                "runner_status",
                "source_verdict",
                "source_verifier_validity_status",
                "source_one_click_contract_status",
                "gate_validity_fail_reasons",
            ):
                if key in gate_file:
                    merged[key] = gate_file.get(key)
        status, reasons = _effective_gate_status(merged)
        merged["status"] = status
        merged["effective_fail_reasons"] = reasons
        rows.append(merged)
    return rows


def build_review(run_dir: Path) -> dict[str, Any]:
    summary_path = run_dir / "super_summary.json"
    summary = _load_json(summary_path)
    gates = {path.stem: _gate(run_dir, path.stem) for path in (run_dir / "gates").glob("*.json")}
    gate_rows = _summary_gate_rows(summary, gates)
    invalid_gate_rows = [row for row in gate_rows if row.get("status") != "PASS"]
    overall_verdict = summary.get("overall_verdict")
    safe_to_freeze = bool(summary.get("safe_to_freeze"))
    blocking_issues = list(summary.get("blocking_issues") or summary.get("top_issues") or [])
    unresolved_summary = {
        "required_count": int(summary.get("unresolved_required_count", 0) or 0),
        "advisory_count": int(summary.get("unresolved_advisory_count", 0) or 0),
        "skipped_count": int(summary.get("unresolved_skipped_count", 0) or 0),
        "required_cases": list(summary.get("unresolved_required_cases") or []),
        "advisory_cases": list(summary.get("unresolved_advisory_cases") or []),
        "skipped_cases": list(summary.get("unresolved_skipped_cases") or []),
    }
    if unresolved_summary["required_count"] or unresolved_summary["skipped_count"]:
        overall_verdict = "RED"
        safe_to_freeze = False
        if unresolved_summary["required_count"]:
            blocking_issues.insert(
                0,
                f"{unresolved_summary['required_count']} unresolved required Design Guide cases remain.",
            )
        if unresolved_summary["skipped_count"]:
            blocking_issues.insert(
                0,
                f"{unresolved_summary['skipped_count']} active matrix cases were skipped.",
            )
    if invalid_gate_rows:
        overall_verdict = "RED"
        safe_to_freeze = False
        for row in invalid_gate_rows:
            reasons = ", ".join(row.get("effective_fail_reasons") or ["status_not_pass"])
            blocking_issues.insert(0, f"{row.get('name')} gate is not valid/pass: {reasons}.")
    local = gates.get("local_cleanup_apply_effectiveness", {})
    contract = gates.get("recommendation_contract", {})
    expectation = gates.get("optimisation_expectation", {})
    truth = gates.get("summary_truth", {})
    matrix = gates.get("matrix_chooser", {})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "super_run": _relative(run_dir),
        "overall_verdict": overall_verdict,
        "safe_to_freeze": safe_to_freeze,
        "blocking_issues": blocking_issues,
        "unresolved_summary": unresolved_summary,
        "gates": gate_rows,
        "design_guide_proof_lines": dict(summary.get("compact_proof_lines") or {}),
        "local_cleanup_effectiveness_summary": {
            "status": _effective_gate_status(local)[0] if local else None,
            "total_cases": local.get("total_cases"),
            "pass_count": local.get("pass_count"),
            "fail_count": local.get("fail_count"),
            "post_click_not_accepted_failures": local.get("post_click_not_accepted_failures"),
            "post_click_cta_still_visible_failures": local.get("post_click_cta_still_visible_failures"),
            "post_click_unresolved_low_util_failures": local.get("post_click_unresolved_low_util_failures"),
        },
        "payload_binding_summary": {
            "requires_primary_payload_binding_match": local.get("requires_primary_payload_binding_match"),
            "requires_primary_payload_update_match": local.get("requires_primary_payload_update_match"),
            "payload_candidate_binding_failures": local.get("payload_candidate_binding_failures"),
            "payload_update_binding_failures": local.get("payload_update_binding_failures"),
            "legacy_fallback_primary_apply_failures": local.get("legacy_fallback_primary_apply_failures"),
        },
        "recommendation_contract_summary": {
            "status": _effective_gate_status(contract)[0] if contract else None,
            "total_cases": contract.get("total_cases"),
            "pass_count": contract.get("pass_count"),
            "fail_count": contract.get("fail_count"),
            "actionable_card_rejected_after_click": contract.get("actionable_card_rejected_after_click"),
        },
        "optimisation_expectation_summary": {
            "status": _effective_gate_status(expectation)[0] if expectation else None,
            "total_cases": expectation.get("total_cases"),
            "pass_count": expectation.get("pass_count"),
            "fail_count": expectation.get("fail_count"),
            "remaining_overdesign_unexplained_count": expectation.get("remaining_overdesign_unexplained_count"),
            "unnecessary_strengthening_count": expectation.get("unnecessary_strengthening_count"),
        },
        "summary_truth_summary": {
            "status": _effective_gate_status(truth)[0] if truth else None,
            "total_cases": truth.get("total_cases"),
            "pass_count": truth.get("pass_count"),
            "fail_count": truth.get("fail_count"),
            "false_pass_count": truth.get("false_pass_count"),
            "misleading_target_band_count": truth.get("misleading_target_band_count"),
        },
        "matrix_chooser_summary": {
            "status": _effective_gate_status(matrix)[0] if matrix else None,
            "required_gate": matrix.get("matrix_chooser_required_gate"),
            "total_cases": matrix.get("total_cases", matrix.get("matrix_chooser_total")),
            "pass_count": matrix.get("pass_count", matrix.get("matrix_chooser_pass")),
            "fail_count": matrix.get("fail_count", matrix.get("matrix_chooser_fail")),
            "artifact": matrix.get("artifact"),
        },
        "child_artifact_paths": dict(summary.get("child_artifact_paths") or {}),
    }


def render_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Super Verification Compact Review",
        "",
        f"Generated: {review['generated_at']}",
        f"Super run: `{review.get('super_run')}`",
        f"Overall verdict: **{review.get('overall_verdict') or 'UNKNOWN'}**",
        f"Safe to freeze: **{'YES' if review.get('safe_to_freeze') else 'NO'}**",
        "",
        "## Gates",
        "",
        "| Gate | Status | Runner | Validity | One-click | Artifact |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for gate in review.get("gates") or []:
        validity = gate.get("source_verifier_validity_status") or gate.get("verifier_validity_status") or ""
        one_click = gate.get("source_one_click_contract_status") or gate.get("one_click_contract_status") or ""
        lines.append(
            f"| {gate.get('name')} | {gate.get('status') or 'UNKNOWN'} | {gate.get('runner_status') or ''} | {validity} | {one_click} | `{gate.get('artifact') or ''}` |"
        )
    lines.extend(["", "## Blocking Issues", ""])
    issues = review.get("blocking_issues") or []
    if issues:
        for issue in issues:
            lines.append(f"- {issue}")
    else:
        lines.append("- None")

    unresolved = review.get("unresolved_summary") or {}
    lines.extend(
        [
            "",
            "## Unresolved Cases",
            "",
            f"- Required: {unresolved.get('required_count', 0)}",
            f"- Advisory: {unresolved.get('advisory_count', 0)}",
            f"- Skipped: {unresolved.get('skipped_count', 0)}",
        ]
    )
    for case in list(unresolved.get("required_cases") or [])[:10]:
        lines.append(f"- REQUIRED `{case.get('source')}` / `{case.get('case_id')}`: {case.get('reason')}")
    for case in list(unresolved.get("skipped_cases") or [])[:10]:
        lines.append(f"- SKIPPED `{case.get('source')}` / `{case.get('case_id')}`: {case.get('reason')}")

    proof = review.get("design_guide_proof_lines") or {}
    lines.extend(
        [
            "",
            "## Design Guide Proof Lines",
            "",
            f"- Requires post-click green/accepted: {proof.get('requires_post_click_green_or_accepted')}",
            f"- Requires target band or exact blocker: {proof.get('requires_target_band_or_exact_blocker')}",
            f"- Can pass without intended-family improvement: {proof.get('can_pass_without_intended_family_improvement')}",
            f"- Can pass with post-click CTA still visible: {proof.get('can_pass_with_post_click_cta_still_visible')}",
            f"- Final accepted min family util: {proof.get('final_accepted_min_family_util')}",
            f"- Requires all meaningful family utils >= 0.85 or exact blocker: {proof.get('requires_all_meaningful_family_utils_ge_0_85_or_exact_blocker')}",
            f"- Requires primary payload binding match: {proof.get('requires_primary_payload_binding_match')}",
            "",
            "## Summaries",
            "",
        ]
    )
    for key in (
        "local_cleanup_effectiveness_summary",
        "payload_binding_summary",
        "recommendation_contract_summary",
        "optimisation_expectation_summary",
        "summary_truth_summary",
        "matrix_chooser_summary",
    ):
        lines.append(f"### {key.replace('_', ' ').title()}")
        for item_key, value in (review.get(key) or {}).items():
            lines.append(f"- {item_key}: {value}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a compact review from a split super verification run.")
    parser.add_argument("--super-run", type=Path, default=None)
    args = parser.parse_args(argv)

    run_dir = args.super_run or _latest_super_run()
    if run_dir is None:
        raise SystemExit("No split super verification run found.")
    if not run_dir.is_absolute():
        run_dir = REPO / run_dir
    if not (run_dir / "super_summary.json").exists():
        raise SystemExit(f"Missing super_summary.json in {run_dir}")

    review = build_review(run_dir)
    timestamp = run_dir.name
    out_dir = REPO / "artifacts" / "verification" / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"compact_review_{timestamp}.json"
    md_path = out_dir / f"compact_review_{timestamp}.md"
    json_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(review), encoding="utf-8")
    print(f"Wrote {_relative(json_path)}")
    print(f"Wrote {_relative(md_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
