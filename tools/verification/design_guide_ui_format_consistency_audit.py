"""Audit Design Guide UI formatting consistency from live/browser artifacts.

Proof-only verifier. It does not launch a browser and does not change product
behaviour. It composes the latest browser/live visual snapshots with the shared
Final Design Guide formatting contract and reports whether the renderer/card
format is consistent enough to patch, lock, or needs a focused renderer slice.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTRACT_PATH = ROOT / "design_brain" / "final_design_guide_formatting_contract.json"
RENDERER_PATH = ROOT / "ui" / "final_design_guide_card.py"

RAW_DEBUG_RE = re.compile(
    r"\b(debug_payload|verifier_payload|final_publication_hash|publication_hash|"
    r"display_hash|cta_hash|apply_payload_fingerprint|button_contract_hash|"
    r"trace_id|session_state|compatibility_only|non_authoritative)\b",
    re.IGNORECASE,
)
ENCODING_RE = re.compile(r"(?:Ã.|Â.|�|\\ufffd)")
LOADING_SHELL_RE = re.compile(
    r"Checking design guidance|Reviewing strength, detailing, serviceability, and cleanup options",
    re.IGNORECASE,
)
FINAL_CARD_RE = re.compile(
    r"Design is efficient|Strengthening required|Design accepted|repair is blocked|"
    r"cleanup blocked|capacity is low|Apply:|Run one-click auto design|All checks pass",
    re.IGNORECASE,
)


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return path, {"status": "UNREADABLE", "error": f"{type(exc).__name__}: {exc}"}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "UNREADABLE", "error": f"{type(exc).__name__}: {exc}"}


def _scenario_rows(payload: dict[str, Any], *, source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in payload.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        checks = dict(scenario.get("checks") or {})
        design_guide = dict(scenario.get("design_guide") or {})
        text = str(design_guide.get("text_sample") or "")
        statuses = [str(item).upper() for item in checks.get("design_guide_statuses") or []]
        rows.append(
            {
                "source": source,
                "scenario_id": scenario.get("scenario_id"),
                "recipe": scenario.get("recipe"),
                "expected_visual_state": scenario.get("expected_visual_state"),
                "text": text,
                "statuses": statuses,
                "hard_failures": list(checks.get("hard_failures") or []),
                "warnings": list(checks.get("warnings") or []),
                "cta": dict(checks.get("cta") or {}),
                "tone": dict(checks.get("tone") or {}),
                "stale_fallback_publication_shell": dict(checks.get("stale_fallback_publication_shell") or {}),
                "found": bool(design_guide.get("found")),
                "text_hash": design_guide.get("text_hash"),
            }
        )
    return rows


def _contract_allowed_badges(contract: dict[str, Any]) -> set[str]:
    mapping = dict(contract.get("outcome_state_mapping") or {})
    badges = {
        str(row.get("default_badge") or "").strip().upper()
        for row in mapping.values()
        if isinstance(row, dict)
    }
    proof_pending = str(
        dict(contract.get("fallback_and_proof_pending") or {}).get("proof_pending_badge") or ""
    ).strip().upper()
    if proof_pending:
        badges.add(proof_pending)
    return {item for item in badges if item}


def _classify_scenario(row: dict[str, Any], allowed_badges: set[str]) -> dict[str, Any]:
    text = str(row.get("text") or "")
    statuses = [str(item).upper() for item in row.get("statuses") or []]
    # Browser text often includes lower page sections after the Design Guide
    # card, including summary-card statuses such as CAPACITY. The formatting
    # contract applies to the Design Guide card badge itself, which is the first
    # status token in the captured Design Guide section.
    card_badge = statuses[0] if statuses else ""
    disallowed = [card_badge] if card_badge and card_badge not in allowed_badges else []
    raw_debug = sorted(set(match.group(0) for match in RAW_DEBUG_RE.finditer(text)))
    encoding = sorted(set(match.group(0) for match in ENCODING_RE.finditer(text)))
    loading_visible = bool(LOADING_SHELL_RE.search(text))
    final_visible = bool(FINAL_CARD_RE.search(text))
    duplicate_headings = {
        "status": len(re.findall(r"(?im)^Status\b|(?:^|\s)Status(?:\s|$)", text)),
        "why": len(re.findall(r"(?im)^Why\b|(?:^|\s)Why\b", text)),
        "design_guide": len(re.findall(r"(?im)^Design Guide\b", text)),
    }
    tone = dict(row.get("tone") or {})
    cta = dict(row.get("cta") or {})
    risks: list[str] = []
    if not row.get("found"):
        risks.append("design_guide_card_not_found")
    if disallowed:
        risks.append("disallowed_or_legacy_badge_visible")
    if raw_debug:
        risks.append("raw_debug_or_hash_text_visible")
    if encoding:
        risks.append("encoding_garbage_visible")
    if loading_visible and final_visible:
        risks.append("loading_shell_visible_with_final_card")
    if tone.get("red_card_blue_action_pill_risk"):
        risks.append("red_card_blue_action_or_governing_pill_risk")
    if cta.get("missing_or_hidden_apply_button"):
        risks.append("action_state_without_visible_enabled_apply_button")
    if duplicate_headings["design_guide"] > 1:
        risks.append("duplicate_design_guide_heading_visible")
    return {
        "source": row.get("source"),
        "scenario_id": row.get("scenario_id"),
        "recipe": row.get("recipe"),
        "expected_visual_state": row.get("expected_visual_state"),
        "found": row.get("found"),
        "statuses": statuses,
        "card_badge": card_badge,
        "disallowed_badges": disallowed,
        "raw_debug_markers": raw_debug,
        "encoding_markers": encoding[:8],
        "loading_shell_visible": loading_visible,
        "final_card_visible": final_visible,
        "duplicate_headings": duplicate_headings,
        "hard_failures": row.get("hard_failures") or [],
        "warnings": row.get("warnings") or [],
        "risks": risks,
        "text_hash": row.get("text_hash"),
        "text_sample": text[:700],
    }


def _renderer_contract_checks(contract: dict[str, Any]) -> dict[str, Any]:
    renderer_text = RENDERER_PATH.read_text(encoding="utf-8") if RENDERER_PATH.exists() else ""
    required_ids = [str(item) for item in contract.get("required_test_ids") or []]
    missing_ids = [test_id for test_id in required_ids if test_id not in renderer_text]
    forbidden_renderer_terms = [
        term
        for term in (
            "import streamlit",
            "from streamlit",
            "st.session_state",
            "import inputs_page",
            "from inputs_page",
        )
        if term.lower() in renderer_text.lower()
    ]
    return {
        "contract_found": bool(contract),
        "renderer_found": RENDERER_PATH.exists(),
        "required_test_ids": required_ids,
        "missing_required_test_ids": missing_ids,
        "forbidden_renderer_terms": forbidden_renderer_terms,
        "renderer_contract_ready": bool(contract) and RENDERER_PATH.exists() and not missing_ids and not forbidden_renderer_terms,
    }


def _build_payload() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    contract = _load_json(CONTRACT_PATH)
    allowed_badges = _contract_allowed_badges(contract)

    single_path, single_payload = _latest("design_guide_browser_live_visual_consistency")
    family_path, family_payload = _latest("design_guide_family_browser_live_visual_consistency")
    rows = []
    rows.extend(_scenario_rows(single_payload, source="single_browser_live_visual_consistency"))
    rows.extend(_scenario_rows(family_payload, source="family_browser_live_visual_consistency"))
    scenario_checks = [_classify_scenario(row, allowed_badges) for row in rows]
    risks = sorted({risk for row in scenario_checks for risk in row.get("risks", [])})
    hard_artifact_failures = [
        name
        for name, payload in (
            ("single_browser_live_visual_consistency", single_payload),
            ("family_browser_live_visual_consistency", family_payload),
        )
        if payload.get("status") not in {"PASS", "PARTIAL"}
    ]
    renderer_checks = _renderer_contract_checks(contract)
    renderer_ready = bool(renderer_checks.get("renderer_contract_ready"))

    if hard_artifact_failures:
        status = "FAIL"
        decision = "BLOCKED_VISUAL_ARTIFACT_FAILURE"
    elif risks:
        status = "PARTIAL"
        decision = "READY_FOR_FOCUSED_RENDERER_FORMAT_PATCH"
    elif renderer_ready:
        status = "PASS"
        decision = "FORMAT_CONTRACT_CURRENTLY_CONSISTENT"
    else:
        status = "PARTIAL"
        decision = "FORMAT_CONTRACT_OR_RENDERER_CHECK_INCOMPLETE"

    first_safe_patch = (
        "Normalize legacy Design Guide status badges/tone mapping in the shared final card formatter or "
        "publication display adapter so browser-visible badges are limited to the formatting contract "
        f"{sorted(allowed_badges)}; do not change wording or CTA/apply semantics."
        if "disallowed_or_legacy_badge_visible" in risks
        else "No renderer patch is justified before expanding browser scenarios."
    )
    if "encoding_garbage_visible" in risks:
        first_safe_patch = (
            "First fix renderer text escaping/encoding for final Design Guide card text because browser-visible "
            "garbage characters were found; preserve exact source wording bytes where valid."
        )
    if "red_card_blue_action_or_governing_pill_risk" in risks:
        first_safe_patch = (
            "First add a focused tone/status parity patch in the shared card renderer so ACTION/governing pills "
            "inherit the final card tone when the card is red/blocked."
        )

    return {
        "schema": "design_guide_ui_format_consistency_audit.v1",
        "status": status,
        "decision": decision,
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "product_behaviour_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "contract_path": str(CONTRACT_PATH),
        "renderer_path": str(RENDERER_PATH),
        "source_artifacts": {
            "single_browser_live_visual_consistency": str(single_path) if single_path else None,
            "family_browser_live_visual_consistency": str(family_path) if family_path else None,
        },
        "allowed_publication_badges": sorted(allowed_badges),
        "renderer_contract_checks": renderer_checks,
        "risk_summary": {
            "risks": risks,
            "scenario_count": len(scenario_checks),
            "scenarios_with_risks": sum(1 for row in scenario_checks if row.get("risks")),
            "hard_artifact_failures": hard_artifact_failures,
        },
        "scenario_checks": scenario_checks,
        "first_safe_renderer_patch": first_safe_patch,
        "required_next_verifier": (
            "design_guide_ui_format_renderer_patch_snapshot.py"
            if risks
            else "expand_family_browser_live_visual_consistency_scenarios_before_patching"
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_ui_format_consistency_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_ui_format_consistency_audit_{stamp}.md"
    lines = [
        "# Design Guide UI Format Consistency Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"Visible wording changed: `{payload['visible_wording_changed']}`",
        f"CTA/apply semantics changed: `{payload['cta_apply_semantics_changed']}`",
        "",
        "## Shared Format Contract",
        "",
        f"- Contract: `{payload['contract_path']}`",
        f"- Renderer: `{payload['renderer_path']}`",
        f"- Allowed publication badges: `{payload['allowed_publication_badges']}`",
        "",
        "## Risk Summary",
        "",
        "```json",
        json.dumps(payload["risk_summary"], indent=2, sort_keys=True),
        "```",
        "",
        "## Renderer Contract Checks",
        "",
        "```json",
        json.dumps(payload["renderer_contract_checks"], indent=2, sort_keys=True),
        "```",
        "",
        "## Scenario Findings",
        "",
    ]
    for row in payload["scenario_checks"]:
        risks = row.get("risks") or []
        if not risks:
            continue
        lines.extend(
            [
                f"### {row.get('scenario_id') or row.get('source')}",
                "",
                f"- Source: `{row.get('source')}`",
                f"- Recipe: `{row.get('recipe')}`",
                f"- Risks: `{risks}`",
                f"- Statuses: `{row.get('statuses')}`",
                f"- Disallowed badges: `{row.get('disallowed_badges')}`",
                f"- Text hash: `{row.get('text_hash')}`",
                "",
                "```text",
                str(row.get("text_sample") or ""),
                "```",
                "",
            ]
        )
    if not any(row.get("risks") for row in payload["scenario_checks"]):
        lines.append("No browser-visible format risks found in the latest artifacts.")
        lines.append("")
    lines.extend(
        [
            "## First Safe Renderer Patch",
            "",
            payload["first_safe_renderer_patch"],
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
    print(f"design_guide_ui_format_consistency_audit {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print("risks=" + json.dumps(payload["risk_summary"], sort_keys=True))
    return 0 if payload["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
