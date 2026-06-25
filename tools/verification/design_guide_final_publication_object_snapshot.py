"""Proof-only snapshot for the FinalDesignGuidePublication object.

This proves the object shape only. It does not move CTA rendering, card
rendering, apply routing, browser driving, or current publication decisions.
"""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
MODULE_PATH = ROOT / "design_brain" / "final_publication.py"

FORBIDDEN_IMPORT_ROOTS = {
    "inputs_page",
    "streamlit",
    "design_brain.families",
    "design_brain.family_classification_runtime",
}

FORBIDDEN_SOURCE_TERMS = {
    "st.session_state",
    "session_state",
    "streamlit",
    "render_button",
    "button_rendering",
    "cta_rendering",
    "apply_routing",
    "browser_use",
}

FORBIDDEN_SOURCE_TERM_EXCEPTIONS = {
    "one_click": {"one_click_action_handoff"},
}

REQUIRED_PUBLICATION_FIELDS = {
    "selected_family",
    "outcome_state",
    "publication_reason",
    "blocker_reason",
    "exact_stop_proof",
    "target_band_proof",
    "cta",
    "display",
    "evidence",
    "verifier_payload",
    "stale_fresh_proof",
    "source_hash",
    "publication_hash",
    "proof_only",
}

REQUIRED_CTA_FIELDS = {
    "enabled",
    "actionable",
    "label",
    "disabled_reason",
    "apply_payload_fingerprint",
    "product_driving",
}

REQUIRED_DISPLAY_FIELDS = {
    "title",
    "badge",
    "summary",
    "visible_wording_hash",
    "renderer_driving",
}

REQUIRED_EVIDENCE_FIELDS = {
    "selected_family",
    "publication_reason",
    "blocker_reason",
    "exact_stop_proof",
    "target_band_proof",
    "stale_fresh_proof",
    "evidence_hash",
}

REQUIRED_VERIFIER_FIELDS = {
    "payload",
    "payload_hash",
    "browser_driving",
}


def _read_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def _module_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _forbidden_imports(imports: list[str]) -> list[str]:
    hits: list[str] = []
    for name in imports:
        for forbidden in FORBIDDEN_IMPORT_ROOTS:
            if name == forbidden or name.startswith(forbidden + "."):
                hits.append(name)
    return sorted(set(hits))


def _forbidden_source_hits(source: str) -> list[str]:
    hits: list[str] = []
    for term in FORBIDDEN_SOURCE_TERMS | set(FORBIDDEN_SOURCE_TERM_EXCEPTIONS):
        if term not in source:
            continue
        exceptions = FORBIDDEN_SOURCE_TERM_EXCEPTIONS.get(term, set())
        scrubbed = source
        for allowed in exceptions:
            scrubbed = scrubbed.replace(allowed, "")
        if term in scrubbed:
            hits.append(term)
    return sorted(hits)


def _case_payloads() -> dict[str, dict[str, Any]]:
    return {
        "PASS": {
            "item": {
                "selected_family_id": "TARGET_BAND_REACHED",
                "status": "PASS",
                "bucket": "pass",
                "title_main": "Design accepted",
                "summary_line": "Target band reached.",
                "design_guide_terminal_state": "optimal",
                "display_truth": {"target_low": 0.85, "target_high": 1.0, "displayed_util": 0.91},
            },
            "debug": {"design_guide_publication_fingerprint": "pass-fp"},
            "result": {"outcome_id": "passing_exact_stop"},
        },
        "ACTION": {
            "item": {
                "selected_family_id": "BENDING_FAIL_GOVERNS",
                "status": "FAIL",
                "bucket": "fail",
                "title_main": "Bending capacity is low",
                "primary_action": "Run one-click auto design",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "bending",
                    "updates": {"bot_dia": 20},
                    "preview_pass": True,
                    "source_candidate_id": "bend-action-1",
                },
                "action_payload": {"action_type": "apply_resolved_candidate", "updates": {"bot_dia": 20}},
            },
            "debug": {"button_contract_enabled": True},
            "result": {"selected_family_id": "BENDING_FAIL_GOVERNS"},
        },
        "BLOCKED": {
            "item": {
                "selected_family_id": "SHEAR_FAIL_GOVERNS",
                "status": "FAIL",
                "bucket": "fail",
                "guidance_intent": "specific_blocker",
                "final_state_class": "blocker",
                "title_main": "Shear repair blocked by shear/detailing limits",
                "blocking_reason": "no_valid_shear_repair",
                "exact_blockers_by_family": {"shear": {"search_ran": True, "search_exhaustive": True}},
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "family": "shear",
                    "blocking_reason": "no_valid_shear_repair",
                },
            },
            "debug": {"blocked_publication_type": "no_valid_shear_repair"},
            "result": {"outcome_id": "blocked_specific_reason"},
        },
        "ERROR": {
            "item": {
                "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
                "status": "ERROR",
                "bucket": "error",
                "title_main": "Design Guide family contract violation",
                "summary_line": "Publication blocked by family contract before final render.",
            },
            "debug": {"family_match_passed": False},
            "result": {"outcome_id": "publication_contract_error"},
        },
        "PROOF_PENDING": {
            "item": {
                "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "title_main": "Design guidance",
                "summary_line": "Proof pending.",
            },
            "debug": {"publication_probe_pending": True},
            "result": {},
        },
    }


def _artifact_summary(publication: Any) -> dict[str, Any]:
    data = publication.to_dict()
    return {
        "selected_family": data["selected_family"],
        "outcome_state": data["outcome_state"],
        "publication_hash": data["publication_hash"],
        "source_hash": data["source_hash"],
        "cta": {
            "enabled": data["cta"]["enabled"],
            "actionable": data["cta"]["actionable"],
            "label": data["cta"]["label"],
            "disabled_reason": data["cta"]["disabled_reason"],
            "apply_payload_fingerprint": data["cta"]["apply_payload_fingerprint"],
            "product_driving": data["cta"]["product_driving"],
        },
        "display": {
            "title": data["display"]["title"],
            "badge": data["display"]["badge"],
            "summary": data["display"]["summary"],
            "visible_wording_hash": data["display"]["visible_wording_hash"],
            "renderer_driving": data["display"]["renderer_driving"],
        },
        "verifier_payload": {
            "payload_hash": data["verifier_payload"]["payload_hash"],
            "browser_driving": data["verifier_payload"]["browser_driving"],
        },
    }


def _build_snapshot() -> dict[str, Any]:
    from design_brain.final_publication import (
        FinalDesignGuideCTA,
        FinalDesignGuideDisplay,
        FinalDesignGuideEvidence,
        FinalDesignGuidePublication,
        FinalDesignGuideVerifierPayload,
        build_final_design_guide_publication,
    )

    source = _read_source()
    imports = _module_imports(source)
    forbidden_imports = _forbidden_imports(imports)
    forbidden_source_hits = _forbidden_source_hits(source)
    field_checks = {
        "FinalDesignGuidePublication": sorted(field.name for field in fields(FinalDesignGuidePublication)),
        "FinalDesignGuideCTA": sorted(field.name for field in fields(FinalDesignGuideCTA)),
        "FinalDesignGuideDisplay": sorted(field.name for field in fields(FinalDesignGuideDisplay)),
        "FinalDesignGuideEvidence": sorted(field.name for field in fields(FinalDesignGuideEvidence)),
        "FinalDesignGuideVerifierPayload": sorted(field.name for field in fields(FinalDesignGuideVerifierPayload)),
    }
    missing_fields = {
        "FinalDesignGuidePublication": sorted(REQUIRED_PUBLICATION_FIELDS - set(field_checks["FinalDesignGuidePublication"])),
        "FinalDesignGuideCTA": sorted(REQUIRED_CTA_FIELDS - set(field_checks["FinalDesignGuideCTA"])),
        "FinalDesignGuideDisplay": sorted(REQUIRED_DISPLAY_FIELDS - set(field_checks["FinalDesignGuideDisplay"])),
        "FinalDesignGuideEvidence": sorted(REQUIRED_EVIDENCE_FIELDS - set(field_checks["FinalDesignGuideEvidence"])),
        "FinalDesignGuideVerifierPayload": sorted(REQUIRED_VERIFIER_FIELDS - set(field_checks["FinalDesignGuideVerifierPayload"])),
    }
    cases: dict[str, Any] = {}
    stable_hash_failures: list[str] = []
    for expected_outcome, payload in _case_payloads().items():
        publication_a = build_final_design_guide_publication(
            item=payload["item"],
            debug=payload["debug"],
            design_brain_result=payload["result"],
            verifier_payload={"case": expected_outcome, "source": "final_publication_object_snapshot"},
            publication_reason=f"snapshot_case:{expected_outcome}",
        )
        publication_b = build_final_design_guide_publication(
            item=payload["item"],
            debug=payload["debug"],
            design_brain_result=payload["result"],
            verifier_payload={"case": expected_outcome, "source": "final_publication_object_snapshot"},
            publication_reason=f"snapshot_case:{expected_outcome}",
        )
        if publication_a.publication_hash != publication_b.publication_hash:
            stable_hash_failures.append(expected_outcome)
        cases[expected_outcome] = {
            "expected_outcome": expected_outcome,
            "actual_outcome": publication_a.outcome_state,
            "outcome_matches": publication_a.outcome_state == expected_outcome,
            "stable_hash": publication_a.publication_hash == publication_b.publication_hash,
            "summary": _artifact_summary(publication_a),
        }
    outcome_failures = [
        name
        for name, case in cases.items()
        if not case["outcome_matches"]
    ]
    non_product_driving_failures: list[str] = []
    for name, case in cases.items():
        summary = case["summary"]
        if summary["cta"]["product_driving"]:
            non_product_driving_failures.append(f"{name}:cta_product_driving")
        if summary["display"]["renderer_driving"]:
            non_product_driving_failures.append(f"{name}:display_renderer_driving")
        if summary["verifier_payload"]["browser_driving"]:
            non_product_driving_failures.append(f"{name}:verifier_browser_driving")
    failures: list[str] = []
    if forbidden_imports:
        failures.append("forbidden_imports")
    if forbidden_source_hits:
        failures.append("forbidden_source_terms")
    if any(missing_fields.values()):
        failures.append("missing_required_fields")
    if outcome_failures:
        failures.append("outcome_representation_failures")
    if stable_hash_failures:
        failures.append("unstable_publication_hash")
    if non_product_driving_failures:
        failures.append("proof_object_started_driving_product_surfaces")
    return {
        "snapshot_name": "design_guide_final_publication_object",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "module": "design_brain/final_publication.py",
        "proof_only": True,
        "product_behavior_changed": False,
        "cta_product_driving": False,
        "display_renderer_driving": False,
        "verifier_browser_driving": False,
        "imports": imports,
        "forbidden_imports": forbidden_imports,
        "forbidden_source_hits": forbidden_source_hits,
        "field_checks": field_checks,
        "missing_fields": missing_fields,
        "cases": cases,
        "outcome_failures": outcome_failures,
        "stable_hash_failures": stable_hash_failures,
        "non_product_driving_failures": non_product_driving_failures,
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = []
    for name, case in snapshot["cases"].items():
        summary = case["summary"]
        rows.append(
            "| {name} | {actual} | {hash} | {cta} | {title} | {stable} |".format(
                name=name,
                actual=case["actual_outcome"],
                hash=summary["publication_hash"],
                cta="enabled" if summary["cta"]["enabled"] else "disabled",
                title=str(summary["display"]["title"] or ""),
                stable="yes" if case["stable_hash"] else "no",
            )
        )
    body = "\n".join(
        [
            "# FinalDesignGuidePublication Object Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            "",
            "This is proof-only. It creates the one-object publication shape without changing current publication, CTA, render, apply, browser, or session behaviour.",
            "",
            "## Assertions",
            "",
            f"- Product behaviour changed: `{snapshot['product_behavior_changed']}`",
            f"- CTA product-driving: `{snapshot['cta_product_driving']}`",
            f"- Display renderer-driving: `{snapshot['display_renderer_driving']}`",
            f"- Verifier browser-driving: `{snapshot['verifier_browser_driving']}`",
            f"- Forbidden imports: `{snapshot['forbidden_imports']}`",
            f"- Forbidden source hits: `{snapshot['forbidden_source_hits']}`",
            "",
            "## Outcome Cases",
            "",
            "| Case | Outcome | Publication hash | CTA | Title | Stable |",
            "|---|---|---|---|---|---|",
            *rows,
            "",
            "## Next Slice",
            "",
            "Use this object in a proof-only adapter snapshot around the existing final-visible publication checkpoints. Do not make it product-driving until the current distributed authority chain has hash parity.",
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_final_publication_object_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_publication_object_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_final_publication_object_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("failures=" + ", ".join(snapshot["failures"]))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
