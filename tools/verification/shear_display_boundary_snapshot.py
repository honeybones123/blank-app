"""Focused SHEAR Design Guide display-boundary snapshot.

This diagnostic intentionally reads the product-path gate report named in stdout
instead of selecting the newest gate artifact by mtime. The SHEAR/COMBINED
regressions can run in parallel, and timestamp-only artifact discovery can pick
up the wrong scenario report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "verification"
SCENARIO = "scenario_c1_pure_shear_underdesign_repair"
EXPECTED_FAMILY = "SHEAR_FAIL_GOVERNS"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _scenario_result(gate_report: dict[str, Any]) -> dict[str, Any]:
    for result in gate_report.get("results") or []:
        if isinstance(result, dict) and result.get("name") == SCENARIO:
            return dict(result)
    return {}


def _report_path_from_stdout(stdout: str) -> Path | None:
    for line in str(stdout or "").splitlines():
        match = re.match(r"^Report:\s*(.+\.json)\s*$", line.strip())
        if match:
            return Path(match.group(1))
    return None


def _bool_attr(value: object) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return None


def _candidate_identity_from_payload(payload_id: str) -> dict[str, Any]:
    text = str(payload_id or "")
    return {
        "payload_id": text,
        "family": "SHEAR_FAIL_GOVERNS" if "SHEAR_FAIL_GOVERNS" in text else (
            "COMBINED_BENDING_SHEAR_FAIL" if "COMBINED_BENDING_SHEAR_FAIL" in text else ""
        ),
        "owner": "shear_fail" if "shear_fail" in text.lower() else (
            "combined" if "combined" in text.lower() else ""
        ),
        "is_repair": "repair" in text.lower(),
        "is_cleanup": "cleanup" in text.lower(),
    }


def _family_label_from_card_text(text: str) -> str:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    for line in lines:
        if line.upper() in {"NEXT", "ACTION", "PASS", "WARNING", "BLOCKED"}:
            continue
        return line
    return ""


def _extract_why_body(body_text: str) -> str:
    lines = [line.strip() for line in str(body_text or "").splitlines() if line.strip()]
    for line in lines:
        lower = line.lower()
        if "sectional shear capacity fails" in lower:
            return line
        if "shear utilisation moves" in lower:
            return line
        if "bending and shear" in lower and "moves from" in lower:
            return line
    return ""


def _card_boundary(card: dict[str, Any]) -> dict[str, Any]:
    payload_id = str(card.get("render_cta_payload_id") or "")
    return {
        "text": str(card.get("text") or ""),
        "family_label_shown": _family_label_from_card_text(str(card.get("text") or "")),
        "selected_family_id": card.get("selected_family_id"),
        "selected_family": card.get("selected_family"),
        "published_family_id": card.get("published_family_id"),
        "cta_family_id": card.get("cta_family_id"),
        "apply_payload_family_id": card.get("apply_payload_family_id"),
        "candidate_family_id": card.get("candidate_family_id"),
        "card_family_id": card.get("card_family_id"),
        "family_route_owner": card.get("family_route_owner"),
        "selection_reason": card.get("selection_reason"),
        "family_match_passed": card.get("family_match_passed"),
        "class_name": card.get("className"),
        "card_tone_or_status": card.get("className"),
        "cta_enabled": _bool_attr(card.get("render_cta_enabled")),
        "button_contract_enabled": _bool_attr(card.get("render_gate_button_enabled")),
        "view_cta_enabled": _bool_attr(card.get("render_gate_vm_cta_enabled")),
        "terminal_exact": _bool_attr(card.get("render_gate_terminal_exact")),
        "cta_reason": card.get("render_blocking_reason"),
        "cta_payload_id": payload_id,
        "repair_candidate_identity": _candidate_identity_from_payload(payload_id),
        "optimisation_candidate_identity": (
            _candidate_identity_from_payload(payload_id)
            if "cleanup" in payload_id.lower() or "optim" in payload_id.lower()
            else None
        ),
    }


def _build_boundary(gate_path: Path, gate_report: dict[str, Any], completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    scenario = _scenario_result(gate_report)
    evidence = dict(scenario.get("evidence") or {})
    snapshot = dict(evidence.get("final_snapshot") or {})
    cards = [dict(card) for card in list(snapshot.get("cards") or []) if isinstance(card, dict)]
    primary_card = cards[0] if cards else {}
    actionable_cards = [
        card for card in cards
        if _bool_attr(card.get("render_gate_button_enabled")) or _bool_attr(card.get("render_gate_vm_cta_enabled"))
    ]
    actionable_card = actionable_cards[0] if actionable_cards else primary_card
    visible_ctas = list(evidence.get("visible_cta_buttons") or [])
    boundary = {
        "schema": "shear_display_boundary_snapshot.v1",
        "scenario": SCENARIO,
        "status": "PASS" if scenario.get("status") == "PASS" else "FAIL",
        "gate_report": str(gate_path),
        "command_returncode": completed.returncode,
        "selected_family": evidence.get("selected_family"),
        "selected_family_id": evidence.get("selected_family_id"),
        "published_family_id": evidence.get("published_family_id"),
        "cta_family_id": evidence.get("cta_family_id"),
        "apply_payload_family_id": evidence.get("apply_payload_family_id"),
        "card_family_id": evidence.get("card_family_id"),
        "family_route_owner": evidence.get("family_route_owner"),
        "family_label_shown": _family_label_from_card_text(str(snapshot.get("first_card_text") or "")),
        "terminal_status": {
            "scenario_status": scenario.get("status"),
            "terminal_exact": _bool_attr(primary_card.get("render_gate_terminal_exact")),
            "first_card_class": primary_card.get("className"),
        },
        "main_card_text": str(snapshot.get("first_card_text") or ""),
        "why_body": _extract_why_body(str(snapshot.get("body_text") or "")),
        "cta_label": visible_ctas[0] if visible_ctas else "",
        "cta_enabled": bool(visible_ctas),
        "cta_reason": primary_card.get("render_blocking_reason") or actionable_card.get("render_blocking_reason"),
        "card_tone_status": primary_card.get("className"),
        "repair_candidate_identity": _candidate_identity_from_payload(str(evidence.get("render_cta_payload_id") or "")),
        "optimisation_candidate_identity": None,
        "generated_display_html": None,
        "generated_display_html_available": False,
        "generated_display_html_unavailable_reason": "product_path_gate_snapshot_does_not_capture_outer_html",
        "primary_card": _card_boundary(primary_card),
        "actionable_card": _card_boundary(actionable_card),
        "cards": [_card_boundary(card) for card in cards],
        "assertions": {
            "selected_family_is_shear": evidence.get("selected_family_id") == EXPECTED_FAMILY,
            "published_family_is_shear": evidence.get("published_family_id") == EXPECTED_FAMILY,
            "cta_family_is_shear": evidence.get("cta_family_id") == EXPECTED_FAMILY,
            "apply_payload_family_is_shear": evidence.get("apply_payload_family_id") == EXPECTED_FAMILY,
            "family_owner_is_shear": "design_brain.families.shear_fail.ShearFailFamily"
            in str(evidence.get("family_route_owner") or ""),
            "main_card_mentions_shear": "shear capacity is low" in str(snapshot.get("first_card_text") or "").lower(),
            "cta_visible": bool(visible_ctas),
            "payload_identifies_shear_repair": (
                EXPECTED_FAMILY in str(evidence.get("render_cta_payload_id") or "")
                and "repair" in str(evidence.get("render_cta_payload_id") or "").lower()
            ),
            "not_combined_family": evidence.get("selected_family_id") != "COMBINED_BENDING_SHEAR_FAIL",
        },
    }
    boundary["assertion_failures"] = [
        name for name, ok in boundary["assertions"].items() if not ok
    ]
    boundary["status"] = "PASS" if not boundary["assertion_failures"] and completed.returncode == 0 else "FAIL"
    return boundary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="9751")
    parser.add_argument("--from-gate-report", default="")
    args = parser.parse_args(argv)

    if args.from_gate_report:
        gate_path = Path(args.from_gate_report)
        gate_report = _load_json(gate_path)
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    else:
        env = dict(os.environ)
        env.pop("CODEX_BROWSER_TEST_MODE", None)
        env["DESIGN_BRAIN_SHEAR_FAIL_FAMILY_ROUTING"] = "1"
        command = [
            sys.executable,
            "tools/verification/design_guide_product_path_gate.py",
            "--port",
            str(args.port),
            "--scenario",
            SCENARIO,
        ]
        completed = subprocess.run(command, cwd=REPO, env=env, text=True, capture_output=True)
        gate_path = _report_path_from_stdout(completed.stdout)
        if gate_path is None:
            raise SystemExit(f"Could not parse gate report path from stdout:\n{completed.stdout}")
        gate_report = _load_json(gate_path)

    boundary = _build_boundary(gate_path, gate_report, completed)
    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    output = ARTIFACT_DIR / f"shear_display_boundary_snapshot_{timestamp}_port{args.port}.json"
    output.write_text(json.dumps(boundary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{boundary['status']}: {output}")
    return 0 if boundary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
