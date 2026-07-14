"""Verify GEOMETRY_DETAILING_GOVERNS classification enforcement.

This snapshot locks the decision that invalid input geometry/detailing is a
governing family selection, not a generic lock fallback and not a contract
violation sentinel. It is classification-only: no CTA, publication, apply,
rendering, session, or family runtime execution moves here.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.family_classification import (  # noqa: E402
    allowed_family_ids,
    classification_priority_order,
    classification_rules,
)
from design_brain.family_chooser import classify_family_from_raw_flags  # noqa: E402
from design_brain.family_classification_runtime import classify_family_from_whole_beam_evidence  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

EXPECTED_FAMILY = "GEOMETRY_DETAILING_GOVERNS"
FORBIDDEN_OWNERSHIP_TERMS = (
    "streamlit",
    "session_state",
    "button_contract",
    "apply_routing",
    "publication rendering",
    "rendered_html",
)


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _live(flags: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    return classify_family_from_raw_flags(flags, evidence=evidence)


def _contract(evidence: dict[str, Any]) -> dict[str, Any]:
    return classify_family_from_whole_beam_evidence(evidence)


def _case(
    case_id: str,
    *,
    flags: dict[str, Any],
    evidence: dict[str, Any],
    expected: str,
    expected_not: tuple[str, ...] = (),
) -> dict[str, Any]:
    live = _live(flags, {"case_id": case_id, **dict(evidence)})
    contract = _contract(evidence)
    live_family = str(live.get("selected_family_id") or "")
    contract_family = str(contract.get("selected_family_id") or "")
    failures: list[str] = []
    if live_family != expected:
        failures.append(f"live_expected_{expected}_got_{live_family}")
    if contract_family != expected:
        failures.append(f"contract_expected_{expected}_got_{contract_family}")
    for forbidden in expected_not:
        if live_family == forbidden:
            failures.append(f"live_forbidden_family:{forbidden}")
        if contract_family == forbidden:
            failures.append(f"contract_forbidden_family:{forbidden}")
    return {
        "case_id": case_id,
        "expected_family": expected,
        "forbidden_families": list(expected_not),
        "live_selected_family": live_family,
        "contract_selected_family": contract_family,
        "live_reason": live.get("classification_reason") or live.get("selection_reason"),
        "contract_reason": contract.get("classification_reason"),
        "live_matched_family_ids": list(live.get("matched_family_ids") or []),
        "contract_matched_family_ids": list(contract.get("matched_family_ids") or []),
        "classification_hash": _stable_hash(
            {
                "case_id": case_id,
                "live": live_family,
                "contract": contract_family,
                "flags": flags,
                "evidence": evidence,
            }
        ),
        "failures": failures,
    }


def _no_forbidden_imports() -> list[str]:
    failures: list[str] = []
    for module_name in (
        "design_brain.family_classification_runtime",
        "design_brain.family_chooser",
    ):
        importlib.import_module(module_name)
    if "inputs_page" in sys.modules:
        failures.append("classification_loaded_inputs_page")
    for path in (
        ROOT / "design_brain" / "family_classification_runtime.py",
        ROOT / "design_brain" / "family_chooser.py",
    ):
        source = path.read_text(encoding="utf-8", errors="replace").lower()
        for term in FORBIDDEN_OWNERSHIP_TERMS:
            if term in source:
                failures.append(f"{path.name}:forbidden_ownership_term:{term}")
    return failures


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# GEOMETRY_DETAILING_GOVERNS Classification Snapshot",
        "",
        f"Generated: `{payload['generated_at']}`",
        f"Status: `{payload['status']}`",
        "",
        "## Decision",
        "",
        "`GEOMETRY_DETAILING_GOVERNS` is now a selectable classification family for invalid input geometry/detailing. It is not treated as `FAMILY_SELECTION_CONTRACT_VIOLATION` and not collapsed into `LOCKED_NO_REPAIR` unless a separate higher-priority locked/no-valid repair proof applies.",
        "",
        "## Cases",
        "",
        "| Case | Live | Contract | Failures |",
        "| --- | --- | --- | --- |",
    ]
    for case in payload["cases"]:
        lines.append(
            f"| `{case['case_id']}` | `{case['live_selected_family']}` | `{case['contract_selected_family']}` | `{case['failures']}` |"
        )
    lines.extend(
        [
            "",
            "## Ownership",
            "",
            "- Classification only.",
            "- No CTA rendering moved.",
            "- No publication/apply/session/UI ownership moved.",
            "- Diagram suppression should consume this selected-family signal in a separate render gate.",
            "",
            "## Verification",
            "",
            f"- Contract allowed family: `{payload['contract_checks']['allowed_family_present']}`",
            f"- Contract priority index: `{payload['contract_checks']['priority_index']}`",
            f"- Runtime/import boundary failures: `{payload['forbidden_import_failures']}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = time.strftime("%Y-%m-%dT%H-%M-%S")
    priority = list(classification_priority_order())
    allowed = set(allowed_family_ids())
    rule = dict(classification_rules().get(EXPECTED_FAMILY) or {})

    cases = [
        _case(
            "geometry_detailing_only",
            flags={"geometry_detailing_fail": True},
            evidence={
                "bending_utilisation": 0.94,
                "shear_utilisation": 0.96,
                "geometry_detailing_state": "BLOCKED",
            },
            expected=EXPECTED_FAMILY,
            expected_not=("FAMILY_SELECTION_CONTRACT_VIOLATION", "LOCKED_NO_REPAIR"),
        ),
        _case(
            "geometry_detailing_priority_over_strength",
            flags={
                "geometry_detailing_fail": True,
                "bending_fail": True,
                "shear_fail": True,
                "legal_repair_exists": True,
            },
            evidence={
                "bending_utilisation": 1.12,
                "shear_utilisation": 1.16,
                "bending_state": "FAIL",
                "shear_state": "FAIL",
                "geometry_detailing_state": "BLOCKED",
                "can_strengthen_bending": True,
                "can_strengthen_shear": True,
            },
            expected=EXPECTED_FAMILY,
            expected_not=("BENDING_AND_SHEAR_FAIL_GOVERN", "COMBINED_BENDING_SHEAR_FAIL"),
        ),
        _case(
            "geometry_detailing_absent_strength_still_governs",
            flags={"bending_fail": True, "legal_repair_exists": True},
            evidence={
                "bending_utilisation": 1.12,
                "shear_utilisation": 0.93,
                "bending_state": "FAIL",
                "geometry_detailing_state": "PASS",
                "can_strengthen_bending": True,
            },
            expected="BENDING_FAIL_GOVERNS",
            expected_not=(EXPECTED_FAMILY,),
        ),
    ]

    failures: list[str] = []
    if EXPECTED_FAMILY not in allowed:
        failures.append("geometry_detailing_family_not_allowed")
    if EXPECTED_FAMILY not in priority:
        failures.append("geometry_detailing_family_not_in_priority")
    elif priority.index(EXPECTED_FAMILY) > priority.index("BENDING_AND_SHEAR_FAIL_GOVERN"):
        failures.append("geometry_detailing_priority_after_strength_family")
    if str(rule.get("rule_type") or "") != "geometry_detailing":
        failures.append("geometry_detailing_rule_type_missing")
    failures.extend(_no_forbidden_imports())
    for case in cases:
        failures.extend(f"{case['case_id']}:{failure}" for failure in case["failures"])

    payload = {
        "schema": "family_classification_geometry_detailing_governs_snapshot.v1",
        "generated_at": generated_at,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "contract_checks": {
            "allowed_family_present": EXPECTED_FAMILY in allowed,
            "priority_index": priority.index(EXPECTED_FAMILY) + 1 if EXPECTED_FAMILY in priority else None,
            "priority_order": priority,
            "rule": dict(rule),
        },
        "cases": cases,
        "forbidden_import_failures": _no_forbidden_imports(),
        "product_behaviour_changed": False,
        "diagram_suppression_wiring_moved": False,
        "classification_hash": _stable_hash(cases),
    }
    json_path = ARTIFACT_DIR / f"family_classification_geometry_detailing_governs_{generated_at}.json"
    report_path = AUDIT_DIR / f"family_classification_geometry_detailing_governs_{generated_at}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"family_classification_geometry_detailing_governs_snapshot {payload['status']}")
    print(f"artifact: {json_path}")
    print(f"report: {report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
