"""Audit Design Guide CTA visual surface duplication signals.

This is proof-only. It distinguishes a true duplicated CTA surface from a text
capture false-positive where one button label contains both "Apply:" and
"Run one-click auto design".
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
INPUTS_PAGE = ROOT / "inputs_page.py"


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return path, {"status": "UNREADABLE", "error": f"{type(exc).__name__}: {exc}"}


def _scenario_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in payload.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        design_guide = dict(scenario.get("design_guide") or {})
        checks = dict(scenario.get("checks") or {})
        rows.append(
            {
                "scenario_id": scenario.get("scenario_id"),
                "recipe": scenario.get("recipe"),
                "text_sample": str(design_guide.get("text_sample") or ""),
                "cta": dict(checks.get("cta") or {}),
                "statuses": list(checks.get("design_guide_statuses") or []),
                "hard_failures": list(checks.get("hard_failures") or []),
                "warnings": list(checks.get("warnings") or []),
            }
        )
    return rows


def _action_lines(text: str) -> list[str]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(text or "").splitlines()]
    return [
        line
        for line in lines
        if line
        and (
            line.startswith("Apply:")
            or line == "Run one-click auto design"
            or line == "Repair preview"
            or line.startswith("Apply Recommendation")
            or line.startswith("Apply Auto Design")
        )
    ]


def _classify(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in rows:
        lines = _action_lines(str(row.get("text_sample") or ""))
        duplicate_token_count = sum(
            len(re.findall(r"Apply:|Run one-click auto design|Repair preview", line))
            for line in lines
        )
        unique_lines = sorted(set(lines))
        true_duplicate = len(unique_lines) > 1
        false_positive = bool(len(unique_lines) == 1 and duplicate_token_count > 1)
        if true_duplicate or false_positive:
            findings.append(
                {
                    "scenario_id": row.get("scenario_id"),
                    "recipe": row.get("recipe"),
                    "action_lines": unique_lines,
                    "duplicate_token_count": duplicate_token_count,
                    "classification": (
                        "true_duplicate_cta_surface"
                        if true_duplicate
                        else "single_button_label_text_overlap"
                    ),
                    "cta": row.get("cta"),
                    "statuses": row.get("statuses"),
                }
            )
    return findings


def _source_checks() -> dict[str, Any]:
    text = INPUTS_PAGE.read_text(encoding="utf-8") if INPUTS_PAGE.exists() else ""
    render_match = re.search(
        r"def _render_guidance_secondary_items\(.*?(?=\ndef [a-zA-Z_])",
        text,
        flags=re.S,
    )
    render_body = render_match.group(0) if render_match else ""
    return {
        "inputs_page": str(INPUTS_PAGE),
        "render_helper_found": bool(render_body),
        "streamlit_button_calls_in_render_helper": len(re.findall(r"\bst\.button\(", render_body)),
        "apply_label_prefix_path_present": "apply_label = f\"Apply: {apply_label}\"" in render_body,
        "hidden_anchor_before_button_present": "fast-guidance-action-anchor" in render_body,
        "final_card_cta_attributes_only": "data-cta-label" in (ROOT / "ui" / "final_design_guide_card.py").read_text(encoding="utf-8"),
    }


def _build_payload() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    family_path, family_payload = _latest("design_guide_family_browser_live_visual_consistency")
    rows = _scenario_rows(family_payload)
    findings = _classify(rows)
    source_checks = _source_checks()
    true_duplicates = [row for row in findings if row["classification"] == "true_duplicate_cta_surface"]
    false_positives = [row for row in findings if row["classification"] == "single_button_label_text_overlap"]
    failures: list[str] = []
    if source_checks.get("streamlit_button_calls_in_render_helper") != 1:
        failures.append("unexpected_streamlit_button_count_in_render_helper")
    if true_duplicates:
        failures.append("true_duplicate_cta_surface_detected")
    status = "PASS" if not failures else "FAIL"
    decision = (
        "CTA_DUPLICATE_SIGNAL_IS_TEXT_CAPTURE_FALSE_POSITIVE"
        if status == "PASS" and false_positives
        else "CTA_VISUAL_SURFACE_NEEDS_PATCH"
        if true_duplicates
        else "NO_CTA_DUPLICATE_SIGNAL_FOUND"
    )
    return {
        "schema": "design_guide_cta_visual_surface_readability_audit.v1",
        "status": status,
        "decision": decision,
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "product_behaviour_changed": False,
        "visible_engineering_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "source_artifact": str(family_path) if family_path else None,
        "source_checks": source_checks,
        "findings": findings,
        "true_duplicate_count": len(true_duplicates),
        "single_label_text_overlap_count": len(false_positives),
        "failures": failures,
        "next_safe_target": (
            "Do not patch CTA visual surface from current evidence; update UI polish baseline to stop "
            "penalising single-label text overlap, then continue to layout/radius/shell polish."
            if status == "PASS"
            else "Create focused CTA renderer patch only for true duplicate action surfaces."
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_cta_visual_surface_readability_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_cta_visual_surface_readability_{stamp}.md"
    lines = [
        "# Design Guide CTA Visual Surface Readability Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "## Behaviour Guarantees",
        "",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"- Visible engineering wording changed: `{payload['visible_engineering_wording_changed']}`",
        f"- CTA/apply semantics changed: `{payload['cta_apply_semantics_changed']}`",
        f"- Family runtimes changed: `{payload['family_runtimes_changed']}`",
        "",
        "## Source Checks",
        "",
        "```json",
        json.dumps(payload["source_checks"], indent=2, sort_keys=True),
        "```",
        "",
        "## Findings",
        "",
        "```json",
        json.dumps(payload["findings"], indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Next Safe Target",
        "",
        payload["next_safe_target"],
        "",
    ]
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build_payload()
    json_path, md_path = _write(payload)
    print(f"design_guide_cta_visual_surface_readability {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print("failures=" + json.dumps(payload["failures"], sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
