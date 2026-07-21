from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
WIDGETS_CONTRACT = ROOT / "inputs_page_modules" / "widgets" / "contracts.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_number(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _surface(
    *,
    name: str,
    tokens: tuple[str, ...],
    current_owner: str,
    target_owner: str,
    classification: str,
    readiness: str,
    required_verifier: str,
    source: str,
) -> dict[str, Any]:
    missing = [token for token in tokens if token not in source]
    lines = {
        token: _line_number(source, token)
        for token in tokens
        if token in source
    }
    return {
        "surface": name,
        "tokens_present": not missing,
        "missing_tokens": missing,
        "line_numbers": lines,
        "current_owner": current_owner,
        "target_owner": target_owner,
        "classification": classification,
        "deletion_readiness": readiness,
        "required_verifier": required_verifier,
        "changes_engineering_outcome": False,
        "changes_cta_apply": False,
        "changes_visible_wording": True,
        "writes_session_or_callbacks": True,
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Remaining Detailing Boundary Audit",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This is audit-only. It does not change widget rendering, widget keys, callbacks, session behaviour, engineering values, or visible wording.",
        "",
        "## Remaining Surfaces",
        "",
        "| Surface | Classification | Current owner | Target owner | Deletion readiness | Required verifier |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["surfaces"]:
        lines.append(
            "| `{surface}` | `{classification}` | `{current_owner}` | `{target_owner}` | `{deletion_readiness}` | `{required_verifier}` |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Findings",
            "",
            "- Flange reinforcement controls are conditional on T/I sections and mirror toggles.",
            "- Crack-control inputs use direct `st.selectbox` plus `label_with_hover`, not the `select_row` wrapper.",
            "- Both surfaces are still page-owned widget rendering/callback/session plumbing; they are not engineering authority.",
            "- Neither surface is deletion-ready. They need trace-only metadata first, then a live conditional parity scenario.",
            "",
            "## First Safe Implementation Slice",
            "",
            "Add trace-only metadata for `crack_control_inputs_basic` because it is detailed-mode but not section-shape conditional. Keep all direct Streamlit/selectbox rendering and callbacks in `inputs_page.py`.",
            "",
            "## Stop Conditions",
            "",
            "- Any widget key changes.",
            "- Any visible label/help text changes.",
            "- Any callback or session-state behaviour changes.",
            "- Any crack-control or flange engineering result changes.",
            "- Conditional T/I branch cannot be exercised in live parity.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    contract = _read(WIDGETS_CONTRACT) if WIDGETS_CONTRACT.exists() else ""
    surfaces = [
        _surface(
            name="flange_reinforcement_conditional_widgets",
            tokens=(
                "inputs_top_flange_reo_enabled",
                "inputs_top_flange_mirror_lr",
                "inputs_bot_flange_reo_enabled",
                "inputs_bot_flange_mirror_lr",
                "inputs_top_flange_transverse_enabled",
                "inputs_bot_flange_transverse_enabled",
            ),
            current_owner="inputs_page.py",
            target_owner="inputs_page_modules.widgets metadata builder, with page rendering retained",
            classification="conditional_detailed_widget_surface",
            readiness="NOT_READY",
            required_verifier="inputs_widgets_flange_reinforcement_trace_parity_snapshot.py",
            source=page,
        ),
        _surface(
            name="crack_control_inputs_basic",
            tokens=(
                "inputs_exposure_class",
                "inputs_crack_member_type",
                "inputs_crack_k1",
                "inputs_crack_k2",
            ),
            current_owner="inputs_page.py",
            target_owner="inputs_page_modules.widgets metadata builder, with page rendering retained",
            classification="detailed_widget_surface_ready_for_trace",
            readiness="TRACE_READY",
            required_verifier="inputs_widgets_crack_control_trace_parity_snapshot.py",
            source=page,
        ),
    ]
    checks = {
        "inputs_page_present": INPUTS_PAGE.exists(),
        "widgets_contract_present": WIDGETS_CONTRACT.exists(),
        "flange_surface_found": surfaces[0]["tokens_present"],
        "crack_surface_found": surfaces[1]["tokens_present"],
        "crack_contract_added": '"crack_control_inputs_basic"' in contract,
        "crack_trace_added": '"crack_control_inputs_basic_widget_metadata_hash"' in page,
        "flange_contract_added": '"flange_reinforcement_basic"' in contract and '"flange_transverse_basic"' in contract,
        "flange_trace_added": '"flange_reinforcement_basic_widget_metadata_hash"' in page and '"flange_transverse_basic_widget_metadata_hash"' in page,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "READY_FOR_WIDGET_DELEGATION_READINESS_AUDIT" if not failures else "DETAILING_WIDGET_BOUNDARY_AUDIT_GAPS_REMAIN"
    payload = {
        "audit": "inputs_widgets_remaining_detailing_boundary_audit",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "surfaces": surfaces,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_widgets_remaining_detailing_boundary_audit_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_remaining_detailing_boundary_audit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_widgets_remaining_detailing_boundary_audit", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
