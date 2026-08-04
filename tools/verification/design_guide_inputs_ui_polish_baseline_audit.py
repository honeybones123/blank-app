"""Baseline audit for Inputs + Design Guide UI polish toward a 9/10 target.

This is proof-only. It composes the latest visual, formatting, layout, and
smoothness artifacts and inspects the shared renderer/style surfaces. It does
not change engineering behaviour, visible wording, CTA/apply semantics, family
runtimes, Design Brain authority, or Streamlit rendering.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

STYLE_PATH = ROOT / "ui" / "inputs_page_style.py"
FINAL_CARD_RENDERER_PATH = ROOT / "ui" / "final_design_guide_card.py"
DESIGN_GUIDE_PAGE_PATH = ROOT / "design_guide_page.py"


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return path, {"status": "UNREADABLE", "error": f"{type(exc).__name__}: {exc}"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _extract_family_visual_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in payload.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        checks = dict(scenario.get("checks") or {})
        design_guide = dict(scenario.get("design_guide") or {})
        rows.append(
            {
                "scenario_id": scenario.get("scenario_id"),
                "recipe": scenario.get("recipe"),
                "expected_visual_state": scenario.get("expected_visual_state"),
                "text_sample": str(design_guide.get("text_sample") or ""),
                "statuses": list(checks.get("design_guide_statuses") or []),
                "hard_failures": list(checks.get("hard_failures") or []),
                "warnings": list(checks.get("warnings") or []),
                "tone": dict(checks.get("tone") or {}),
                "cta": dict(checks.get("cta") or {}),
                "found": bool(design_guide.get("found")),
                "text_hash": design_guide.get("text_hash"),
            }
        )
    return rows


def _scenario_polish_findings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    encoding_re = re.compile(r"(?:Ãƒ.|Ã‚.|ï¿½|\\ufffd)")
    loading_re = re.compile(r"Checking design guidance|Reviewing strength, detailing", re.I)
    final_re = re.compile(r"Design is efficient|Strengthening required|repair is blocked|capacity is low", re.I)
    for row in rows:
        text = str(row.get("text_sample") or "")
        status_count = len(re.findall(r"(?im)(^|\n)Status\b", text))
        why_count = len(re.findall(r"(?im)(^|\n)Why\b", text))
        apply_count = len(re.findall(r"(?im)(^|\n)Apply:|Run one-click auto design|Repair preview", text))
        risk_flags: list[str] = []
        if not row.get("found"):
            risk_flags.append("design_guide_card_not_visible")
        if status_count:
            risk_flags.append("expanded_status_section_visible")
        if why_count > 1:
            risk_flags.append("duplicate_why_label_visible")
        if apply_count > 1:
            risk_flags.append("duplicate_apply_button_or_label_visible")
        if encoding_re.search(text):
            risk_flags.append("encoding_garbage_visible")
        if loading_re.search(text) and final_re.search(text):
            risk_flags.append("loading_shell_visible_with_final_card")
        tone = dict(row.get("tone") or {})
        if tone.get("red_card_blue_action_pill_risk"):
            risk_flags.append("red_card_blue_action_pill_risk")
        cta = dict(row.get("cta") or {})
        if cta.get("missing_or_hidden_apply_button"):
            risk_flags.append("action_state_without_visible_apply")
        if risk_flags:
            findings.append(
                {
                    "scenario_id": row.get("scenario_id"),
                    "recipe": row.get("recipe"),
                    "expected_visual_state": row.get("expected_visual_state"),
                    "risk_flags": risk_flags,
                    "status_label_count": status_count,
                    "why_label_count": why_count,
                    "apply_label_count": apply_count,
                    "statuses": row.get("statuses"),
                    "text_hash": row.get("text_hash"),
                    "text_sample": text[:900],
                }
            )
    return findings


def _source_polish_checks() -> dict[str, Any]:
    style = _read(STYLE_PATH)
    renderer = _read(FINAL_CARD_RENDERER_PATH)
    page = _read(DESIGN_GUIDE_PAGE_PATH)
    radii = sorted({int(match.group(1)) for match in re.finditer(r"border-radius:\s*(\d+)px", style)})
    always_status_section = (
        "<div class='dg-section-title'>Status</div>" in renderer
        and "design-guide-main-explanation" in renderer
        and "show_status_section" not in renderer
    )
    pending_shell_inline_styles = bool(re.search(r"style=['\"][^'\"]{40,}", page))
    return {
        "style_path": str(STYLE_PATH),
        "renderer_path": str(FINAL_CARD_RENDERER_PATH),
        "design_guide_page_path": str(DESIGN_GUIDE_PAGE_PATH),
        "style_found": STYLE_PATH.exists(),
        "renderer_found": FINAL_CARD_RENDERER_PATH.exists(),
        "design_guide_page_found": DESIGN_GUIDE_PAGE_PATH.exists(),
        "border_radius_values_px": radii,
        "too_many_radius_values": len(radii) > 4,
        "final_card_always_emits_status_section": always_status_section,
        "proof_pending_shell_has_large_inline_styles": pending_shell_inline_styles,
        "shared_final_card_renderer_present": "render_final_design_guide_card_html" in renderer,
        "inputs_page_style_owns_dg_card_css": ".dg-card" in style and ".fast-guidance-item" in style,
    }


def _score(
    *,
    ui_format: dict[str, Any],
    family_visual: dict[str, Any],
    layout: dict[str, Any],
    smoothness: dict[str, Any],
    status_readability: dict[str, Any],
    cta_visual: dict[str, Any],
    radius_scale: dict[str, Any],
    first_mount: dict[str, Any],
    first_mount_residual_acceptance: dict[str, Any],
    scenario_findings: list[dict[str, Any]],
    source_checks: dict[str, Any],
) -> tuple[float, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []

    if ui_format.get("status") != "PASS":
        issues.append(
            {
                "id": "format_contract_not_green",
                "severity": "high",
                "score_penalty": 0.55,
                "evidence": {"status": ui_format.get("status"), "decision": ui_format.get("decision")},
                "safe_patch": "Fix shared final-card format contract risks before cosmetic work.",
            }
        )

    if family_visual.get("hard_failures"):
        issues.append(
            {
                "id": "browser_visual_hard_failures",
                "severity": "high",
                "score_penalty": 0.75,
                "evidence": family_visual.get("hard_failures"),
                "safe_patch": "Address browser/live visual failure in shared renderer or card model.",
            }
        )

    status_readability_pass = status_readability.get("status") == "PASS"
    status_findings = [
        row
        for row in scenario_findings
        if "expanded_status_section_visible" in row["risk_flags"]
    ]
    if status_findings:
        if status_readability_pass:
            issues.append(
                {
                    "id": "expanded_status_section_noise_patched_needs_live_refresh",
                    "severity": "low",
                    "score_penalty": 0.05,
                    "evidence": {
                        "scenario_count": len(status_findings),
                        "scenarios": [row.get("scenario_id") for row in status_findings],
                        "readability_snapshot": status_readability.get("created_at"),
                    },
                    "safe_patch": "Refresh browser/live family visual consistency to confirm patched renderer output.",
                }
            )
        else:
            issues.append(
                {
                    "id": "expanded_status_section_noise",
                    "severity": "medium",
                    "score_penalty": 0.35,
                    "evidence": {
                        "scenario_count": len(status_findings),
                        "scenarios": [row.get("scenario_id") for row in status_findings],
                    },
                    "safe_patch": (
                        "Create a renderer-only readability verifier for the expanded Status section, then collapse "
                        "or suppress duplicate expanded status rows only when the same wording is already present in "
                        "the card summary/status fields."
                    ),
                }
            )

    cta_false_positive = cta_visual.get("decision") == "CTA_DUPLICATE_SIGNAL_IS_TEXT_CAPTURE_FALSE_POSITIVE"
    duplicate_apply = [row for row in scenario_findings if "duplicate_apply_button_or_label_visible" in row["risk_flags"]]
    if duplicate_apply:
        if not cta_false_positive:
            issues.append(
                {
                    "id": "duplicate_apply_or_cta_visual",
                    "severity": "medium",
                    "score_penalty": 0.25,
                    "evidence": [row.get("scenario_id") for row in duplicate_apply],
                    "safe_patch": "Audit CTA label/button rendering to ensure one visible primary action surface per card.",
                }
            )

    max_shift = layout.get("max_layout_shift_total")
    if isinstance(max_shift, (int, float)) and max_shift > 0.15:
        first_mount_decision = first_mount.get("decision")
        first_mount_bounded = first_mount_decision in {
            "NO_PRODUCT_LAYOUT_PATCH_PROVEN_FROM_CURRENT_EVIDENCE",
            "STREAMLIT_FIRST_MOUNT_RESIDUAL_BOUNDED",
        }
        residual_accepted = bool(
            first_mount_residual_acceptance.get("status") == "PASS"
            and first_mount_residual_acceptance.get("accepted_for_ui_polish_scoring") is True
        )
        if not residual_accepted:
            issues.append(
                {
                    "id": "first_paint_layout_shift_residual",
                    "severity": "low" if first_mount_bounded else "medium",
                    "score_penalty": 0.1 if first_mount_bounded else 0.35,
                    "evidence": {
                        "max_layout_shift_total": max_shift,
                        "decision": layout.get("decision"),
                        "first_mount_decision": first_mount_decision,
                        "first_mount_ready_for_product_layout_patch": first_mount.get("ready_for_product_layout_patch"),
                        "first_mount_residual_acceptance": first_mount_residual_acceptance.get("status"),
                    },
                    "safe_patch": (
                        "Do not add broad spacing or wrapper CSS from current evidence; the remaining first-mount "
                        "shift is bounded unless a user-specific reproduction proves a product-owned source."
                        if first_mount_bounded
                        else (
                            "Do not add ad hoc spacing. Use focused browser/live owner audit around first mount and "
                            "Streamlit slot clearing before a layout patch."
                        )
                    ),
                }
            )

    residual = dict(smoothness.get("residual") or {})
    residual_accepted = bool(
        first_mount_residual_acceptance.get("status") == "PASS"
        and first_mount_residual_acceptance.get("accepted_for_ui_polish_scoring") is True
    )
    if residual.get("residual_classification") and not residual_accepted:
        issues.append(
            {
                "id": "streamlit_first_mount_residual",
                "severity": "low",
                "score_penalty": 0.15,
                "evidence": residual,
                "safe_patch": "Keep as measured residual unless a focused source-node audit identifies a safe shared patch.",
            }
        )

    radius_scale_pass = radius_scale.get("status") == "PASS"
    if source_checks.get("too_many_radius_values"):
        if radius_scale_pass:
            issues.append(
                {
                    "id": "radius_scale_patched_source_residual",
                    "severity": "low",
                    "score_penalty": 0.02,
                    "evidence": {
                        "border_radius_values_px": source_checks.get("border_radius_values_px"),
                        "radius_scale_snapshot": radius_scale.get("created_at"),
                    },
                    "safe_patch": "No radius patch needed; remaining values are unrelated containers or pill radii.",
                }
            )
        else:
            issues.append(
                {
                    "id": "radius_scale_not_tight",
                    "severity": "low",
                    "score_penalty": 0.12,
                    "evidence": {"border_radius_values_px": source_checks.get("border_radius_values_px")},
                    "safe_patch": "Define a small UI radius scale for Inputs and Design Guide card surfaces.",
                }
            )

    if source_checks.get("proof_pending_shell_has_large_inline_styles"):
        issues.append(
            {
                "id": "proof_pending_shell_inline_styles",
                "severity": "low",
                "score_penalty": 0.12,
                "evidence": {"path": source_checks.get("design_guide_page_path")},
                "safe_patch": "Move proof-pending shell styles into the shared Inputs CSS surface after visual parity proof.",
            }
        )

    penalty = min(2.0, sum(float(issue["score_penalty"]) for issue in issues))
    score = round(max(0.0, 9.0 - penalty), 1)
    return score, sorted(issues, key=lambda issue: {"high": 0, "medium": 1, "low": 2}.get(issue["severity"], 3))


def _build_payload() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    ui_path, ui_format = _latest("design_guide_ui_format_consistency_audit")
    family_path, family_visual = _latest("design_guide_family_browser_live_visual_consistency")
    layout_path, layout = _latest("design_guide_summary_layout_shift_readiness")
    smoothness_path, smoothness = _latest("design_guide_smoothness_goal_completion_audit")
    status_readability_path, status_readability = _latest("design_guide_expanded_status_section_readability")
    cta_visual_path, cta_visual = _latest("design_guide_cta_visual_surface_readability")
    radius_scale_path, radius_scale = _latest("design_guide_ui_radius_scale")
    first_mount_path, first_mount = _latest("design_guide_first_mount_slot_clearing_owner")
    proof_shell_path, proof_shell = _latest("design_guide_proof_pending_shell_style_boundary")
    first_mount_residual_acceptance_path, first_mount_residual_acceptance = _latest(
        "design_guide_first_mount_residual_acceptance"
    )

    rows = _extract_family_visual_rows(family_visual)
    scenario_findings = _scenario_polish_findings(rows)
    source_checks = _source_polish_checks()
    score, issues = _score(
        ui_format=ui_format,
        family_visual=family_visual,
        layout=layout,
        smoothness=smoothness,
        status_readability=status_readability,
        cta_visual=cta_visual,
        radius_scale=radius_scale,
        first_mount=first_mount,
        first_mount_residual_acceptance=first_mount_residual_acceptance,
        scenario_findings=scenario_findings,
        source_checks=source_checks,
    )

    hard_blockers = [
        name
        for name, payload in (
            ("ui_format", ui_format),
            ("family_visual", family_visual),
            ("layout", layout),
            ("smoothness", smoothness),
            ("status_readability", status_readability),
            ("cta_visual", cta_visual),
            ("radius_scale", radius_scale),
            ("first_mount_slot_clearing_owner", first_mount),
            ("proof_pending_shell_style_boundary", proof_shell),
            ("first_mount_residual_acceptance", first_mount_residual_acceptance),
        )
        if payload and payload.get("status") not in {"PASS", "PARTIAL"}
    ]
    if hard_blockers:
        status = "FAIL"
        decision = "BLOCKED_BY_STALE_OR_FAILED_BASELINE_ARTIFACT"
    elif score >= 9.0 and not issues:
        status = "PASS"
        decision = "UI_POLISH_9_BASELINE_MET"
    else:
        status = "PASS"
        decision = "READY_FOR_FIRST_SHARED_UI_POLISH_PATCH"

    first_safe_patch = issues[0]["safe_patch"] if issues else "No patch needed from current baseline."
    return {
        "schema": "design_guide_inputs_ui_polish_baseline_audit.v1",
        "status": status,
        "decision": decision,
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "ui_rating_estimate": score,
        "target_ui_rating": 9.0,
        "product_behaviour_changed": False,
        "visible_engineering_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "design_brain_authority_changed": False,
        "source_artifacts": {
            "ui_format": str(ui_path) if ui_path else None,
            "family_visual": str(family_path) if family_path else None,
            "summary_layout": str(layout_path) if layout_path else None,
            "smoothness_completion": str(smoothness_path) if smoothness_path else None,
            "expanded_status_section_readability": str(status_readability_path) if status_readability_path else None,
            "cta_visual_surface_readability": str(cta_visual_path) if cta_visual_path else None,
            "ui_radius_scale": str(radius_scale_path) if radius_scale_path else None,
            "first_mount_slot_clearing_owner": str(first_mount_path) if first_mount_path else None,
            "proof_pending_shell_style_boundary": str(proof_shell_path) if proof_shell_path else None,
            "first_mount_residual_acceptance": (
                str(first_mount_residual_acceptance_path) if first_mount_residual_acceptance_path else None
            ),
        },
        "baseline_statuses": {
            "ui_format": ui_format.get("status"),
            "family_visual": family_visual.get("status"),
            "summary_layout": layout.get("status"),
            "smoothness_completion": smoothness.get("status"),
            "expanded_status_section_readability": status_readability.get("status"),
            "cta_visual_surface_readability": cta_visual.get("status"),
            "ui_radius_scale": radius_scale.get("status"),
            "first_mount_slot_clearing_owner": first_mount.get("status"),
            "proof_pending_shell_style_boundary": proof_shell.get("status"),
            "first_mount_residual_acceptance": first_mount_residual_acceptance.get("status"),
        },
        "source_polish_checks": source_checks,
        "scenario_polish_findings": scenario_findings,
        "ranked_polish_issues": issues,
        "first_safe_shared_patch": first_safe_patch,
        "required_next_verifier": (
            "design_guide_expanded_status_section_readability_snapshot.py"
            if issues and issues[0]["id"] == "expanded_status_section_noise"
            else "focused_shared_ui_polish_patch_snapshot.py"
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_inputs_ui_polish_baseline_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_inputs_ui_polish_baseline_{stamp}.md"
    lines = [
        "# Inputs / Design Guide UI Polish Baseline Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        f"Estimated UI rating: `{payload['ui_rating_estimate']}/10`",
        f"Target UI rating: `{payload['target_ui_rating']}/10`",
        "",
        "## Behaviour Guarantees",
        "",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"- Visible engineering wording changed: `{payload['visible_engineering_wording_changed']}`",
        f"- CTA/apply semantics changed: `{payload['cta_apply_semantics_changed']}`",
        f"- Family runtimes changed: `{payload['family_runtimes_changed']}`",
        f"- Design Brain authority changed: `{payload['design_brain_authority_changed']}`",
        "",
        "## Source Artifacts",
        "",
        "```json",
        json.dumps(payload["source_artifacts"], indent=2, sort_keys=True),
        "```",
        "",
        "## Baseline Statuses",
        "",
        "```json",
        json.dumps(payload["baseline_statuses"], indent=2, sort_keys=True),
        "```",
        "",
        "## Ranked Polish Issues",
        "",
    ]
    for issue in payload["ranked_polish_issues"]:
        lines.extend(
            [
                f"### {issue['id']}",
                "",
                f"- Severity: `{issue['severity']}`",
                f"- Score penalty: `{issue['score_penalty']}`",
                f"- Safe patch: {issue['safe_patch']}",
                "",
                "```json",
                json.dumps(issue.get("evidence"), indent=2, sort_keys=True, default=str),
                "```",
                "",
            ]
        )
    if not payload["ranked_polish_issues"]:
        lines.append("No ranked polish issues found in current evidence.")
        lines.append("")
    lines.extend(
        [
            "## Source Polish Checks",
            "",
            "```json",
            json.dumps(payload["source_polish_checks"], indent=2, sort_keys=True, default=str),
            "```",
            "",
            "## Scenario Findings",
            "",
        ]
    )
    if payload["scenario_polish_findings"]:
        for row in payload["scenario_polish_findings"]:
            lines.extend(
                [
                    f"### {row.get('scenario_id')}",
                    "",
                    f"- Recipe: `{row.get('recipe')}`",
                    f"- Risks: `{row.get('risk_flags')}`",
                    f"- Text hash: `{row.get('text_hash')}`",
                    "",
                    "```text",
                    str(row.get("text_sample") or ""),
                    "```",
                    "",
                ]
            )
    else:
        lines.append("No browser scenario-specific polish findings in latest family visual artifact.")
        lines.append("")
    lines.extend(
        [
            "## First Safe Shared Patch",
            "",
            payload["first_safe_shared_patch"],
            "",
            "## Required Next Verifier",
            "",
            f"`{payload['required_next_verifier']}`",
            "",
        ]
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build_payload()
    json_path, md_path = _write(payload)
    print(f"design_guide_inputs_ui_polish_baseline {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"ui_rating_estimate={payload['ui_rating_estimate']}/10")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print("first_safe_shared_patch=" + payload["first_safe_shared_patch"])
    return 0 if payload["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
