"""Proof-only boundary snapshot for FinalDesignGuidePublication normalization.

This compares representative distributed publication-shaped payloads with the
normalized Design Brain proof object. It does not make the object authoritative
for CTA, card view models, rendering, or page publication.
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
FINAL_PUBLICATION_MODULE = ROOT / "design_brain" / "final_publication.py"

LIVE_AUTHORITY_OUTSIDE_OBJECT = [
    {
        "checkpoint": "final-visible resolver",
        "owner": "inputs_page.py",
        "symbol": "resolve_final_visible_design_guide_item",
        "live_authority": "final visible publication route selection",
    },
    {
        "checkpoint": "CTA/apply payload binding",
        "owner": "inputs_page.py",
        "symbol": "_publish_final_visible_design_guide_contract_binding",
        "live_authority": "session/debug button contract and apply payload binding",
    },
    {
        "checkpoint": "card view model build",
        "owner": "inputs_page.py",
        "symbol": "build_design_guide_card_view_model",
        "live_authority": "visible card VM action/blocker shaping",
    },
    {
        "checkpoint": "card render-model field assembly",
        "owner": "inputs_page.py",
        "symbol": "_build_design_guide_card_render_model",
        "live_authority": "late display title/status/reason adjustment",
    },
    {
        "checkpoint": "underdesign repair publication boundary",
        "owner": "design_brain/publication.py",
        "symbol": "enforce_underdesign_repair_publication_boundary",
        "live_authority": "repair/no-repair legality guard",
    },
    {
        "checkpoint": "family selection publication gate",
        "owner": "design_brain/publication.py",
        "symbol": "enforce_family_selection_publication_contract",
        "live_authority": "selected/published/CTA/card family restamping",
    },
    {
        "checkpoint": "safe combined publication reroute",
        "owner": "design_brain/publication.py",
        "symbol": "enforce_design_brain_publication_contract",
        "live_authority": "safe combined cleanup stale publication reroute",
    },
    {
        "checkpoint": "render fallback shell",
        "owner": "inputs_page.py",
        "symbol": "fallback_enabled_contract_shell",
        "live_authority": "render-after-publication enabled shell fallback",
    },
]

FORBIDDEN_IMPORT_ROOTS = {
    "inputs_page",
    "streamlit",
    "design_brain.families",
    "design_brain.family_classification_runtime",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _module_imports(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
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


def _payload_cases() -> dict[str, dict[str, Any]]:
    return {
        "distributed_pass": {
            "item": {
                "selected_family_id": "TARGET_BAND_REACHED",
                "published_family_id": "TARGET_BAND_REACHED",
                "status": "PASS",
                "bucket": "pass",
                "title_main": "Design accepted",
                "summary_line": "Target band reached.",
                "design_guide_terminal_state": "optimal",
                "display_truth": {"target_low": 0.85, "target_high": 1.0, "displayed_util": 0.92},
            },
            "debug": {
                "design_guide_publication_fingerprint": "distributed-pass-fp",
                "selected_family_id": "TARGET_BAND_REACHED",
            },
            "design_brain_result": {
                "outcome_id": "passing_exact_stop",
                "selected_family_id": "TARGET_BAND_REACHED",
            },
            "publication_reason": "final_visible_target_band_reached",
            "expected": {
                "selected_family": "TARGET_BAND_REACHED",
                "outcome_state": "PASS",
                "publication_reason": "final_visible_target_band_reached",
                "blocker_reason": None,
                "cta_enabled": False,
                "cta_label": None,
                "cta_disabled_reason": None,
                "display_title": "Design accepted",
                "display_badge": "PASS",
                "display_summary": "Target band reached.",
            },
        },
        "distributed_action": {
            "item": {
                "selected_family_id": "BENDING_FAIL_GOVERNS",
                "published_family_id": "BENDING_FAIL_GOVERNS",
                "cta_family_id": "BENDING_FAIL_GOVERNS",
                "status": "FAIL",
                "bucket": "fail",
                "title_main": "Bending capacity is low",
                "primary_action": "Run one-click auto design",
                "summary_line": "Increase bottom reinforcement.",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "bending",
                    "updates": {"bot_dia": 20, "bot_count": 4},
                    "preview_pass": True,
                    "source_candidate_id": "bending-candidate-1",
                },
                "action_payload": {
                    "action_type": "apply_resolved_candidate",
                    "updates": {"bot_dia": 20, "bot_count": 4},
                },
            },
            "debug": {
                "primary_button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "bending",
                    "updates": {"bot_dia": 20, "bot_count": 4},
                    "source_candidate_id": "bending-candidate-1",
                },
                "button_contract_enabled": True,
            },
            "design_brain_result": {"selected_family_id": "BENDING_FAIL_GOVERNS"},
            "publication_reason": "final_visible_active_failure_repair_action",
            "expected": {
                "selected_family": "BENDING_FAIL_GOVERNS",
                "outcome_state": "ACTION",
                "publication_reason": "final_visible_active_failure_repair_action",
                "blocker_reason": None,
                "cta_enabled": True,
                "cta_label": "Run one-click auto design",
                "cta_disabled_reason": None,
                "display_title": "Bending capacity is low",
                "display_badge": "FAIL",
                "display_summary": "Increase bottom reinforcement.",
            },
        },
        "distributed_blocked": {
            "item": {
                "selected_family_id": "SHEAR_FAIL_GOVERNS",
                "published_family_id": "SHEAR_FAIL_GOVERNS",
                "status": "FAIL",
                "bucket": "fail",
                "guidance_intent": "specific_blocker",
                "final_state_class": "blocker",
                "title_main": "Shear repair blocked by shear/detailing limits",
                "summary_line": "No checked shear repair restored the required checks.",
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
            "design_brain_result": {"outcome_id": "blocked_specific_reason"},
            "publication_reason": "final_visible_active_strength_blocker",
            "expected": {
                "selected_family": "SHEAR_FAIL_GOVERNS",
                "outcome_state": "BLOCKED",
                "publication_reason": "final_visible_active_strength_blocker",
                "blocker_reason": "no_valid_shear_repair",
                "cta_enabled": False,
                "cta_label": None,
                "cta_disabled_reason": "no_valid_shear_repair",
                "display_title": "Shear repair blocked by shear/detailing limits",
                "display_badge": "FAIL",
                "display_summary": "No checked shear repair restored the required checks.",
            },
        },
        "distributed_error": {
            "item": {
                "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
                "status": "ERROR",
                "bucket": "error",
                "title_main": "Design Guide family contract violation",
                "summary_line": "Publication blocked by family contract before final render.",
            },
            "debug": {"family_match_passed": False, "family_match_violation_reason": "wrong_family_publication"},
            "design_brain_result": {"outcome_id": "publication_contract_error"},
            "publication_reason": "family_selection_contract_boundary",
            "expected": {
                "selected_family": "GEOMETRY_DETAILING_GOVERNS",
                "outcome_state": "ERROR",
                "publication_reason": "family_selection_contract_boundary",
                "blocker_reason": None,
                "cta_enabled": False,
                "cta_label": None,
                "cta_disabled_reason": None,
                "display_title": "Design Guide family contract violation",
                "display_badge": "ERROR",
                "display_summary": "Publication blocked by family contract before final render.",
            },
        },
        "distributed_proof_pending": {
            "item": {
                "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "title_main": "Design guidance",
                "summary_line": "Publication proof pending.",
            },
            "debug": {"publication_probe_pending": True},
            "design_brain_result": {},
            "publication_reason": "publication_probe_pending",
            "expected": {
                "selected_family": "BENDING_OVERDESIGN_GOVERNS",
                "outcome_state": "PROOF_PENDING",
                "publication_reason": "publication_probe_pending",
                "blocker_reason": None,
                "cta_enabled": False,
                "cta_label": None,
                "cta_disabled_reason": None,
                "display_title": "Design guidance",
                "display_badge": None,
                "display_summary": "Publication proof pending.",
            },
        },
    }


def _extract_preserved_fields(publication: Any) -> dict[str, Any]:
    data = publication.to_dict()
    return {
        "selected_family": data["selected_family"],
        "outcome_state": data["outcome_state"],
        "publication_reason": data["publication_reason"],
        "blocker_reason": data["blocker_reason"],
        "cta_enabled": data["cta"]["enabled"],
        "cta_label": data["cta"]["label"],
        "cta_disabled_reason": data["cta"]["disabled_reason"],
        "apply_payload_fingerprint": data["cta"]["apply_payload_fingerprint"],
        "display_title": data["display"]["title"],
        "display_badge": data["display"]["badge"],
        "display_summary": data["display"]["summary"],
        "verifier_payload_hash": data["verifier_payload"]["payload_hash"],
        "publication_hash": data["publication_hash"],
        "source_hash": data["source_hash"],
        "proof_only": data["proof_only"],
        "cta_product_driving": data["cta"]["product_driving"],
        "display_renderer_driving": data["display"]["renderer_driving"],
        "verifier_browser_driving": data["verifier_payload"]["browser_driving"],
    }


def _build_snapshot() -> dict[str, Any]:
    from design_brain.final_publication import build_final_design_guide_publication

    imports = _module_imports(FINAL_PUBLICATION_MODULE)
    forbidden_imports = _forbidden_imports(imports)
    cases: dict[str, Any] = {}
    preservation_failures: list[str] = []
    stable_hash_failures: list[str] = []
    product_driving_failures: list[str] = []
    for name, payload in _payload_cases().items():
        verifier_payload = {
            "case": name,
            "debug": payload["debug"],
            "authority_snapshot": "design_guide_final_publication_boundary",
        }
        publication_a = build_final_design_guide_publication(
            item=payload["item"],
            debug=payload["debug"],
            design_brain_result=payload["design_brain_result"],
            verifier_payload=verifier_payload,
            publication_reason=payload["publication_reason"],
        )
        publication_b = build_final_design_guide_publication(
            item=payload["item"],
            debug=payload["debug"],
            design_brain_result=payload["design_brain_result"],
            verifier_payload=verifier_payload,
            publication_reason=payload["publication_reason"],
        )
        preserved = _extract_preserved_fields(publication_a)
        expected = payload["expected"]
        mismatches = {
            key: {"expected": expected.get(key), "actual": preserved.get(key)}
            for key in expected
            if preserved.get(key) != expected.get(key)
        }
        if mismatches:
            preservation_failures.append(name)
        if publication_a.publication_hash != publication_b.publication_hash:
            stable_hash_failures.append(name)
        if (
            preserved["cta_product_driving"]
            or preserved["display_renderer_driving"]
            or preserved["verifier_browser_driving"]
        ):
            product_driving_failures.append(name)
        cases[name] = {
            "preserved_fields": preserved,
            "expected_fields": expected,
            "mismatches": mismatches,
            "stable_hash": publication_a.publication_hash == publication_b.publication_hash,
            "distributed_payload_hash": _stable_hash(
                {
                    "item": payload["item"],
                    "debug": payload["debug"],
                    "design_brain_result": payload["design_brain_result"],
                    "publication_reason": payload["publication_reason"],
                }
            ),
        }
    live_authority_outside_object = list(LIVE_AUTHORITY_OUTSIDE_OBJECT)
    failures: list[str] = []
    if forbidden_imports:
        failures.append("forbidden_final_publication_imports")
    if preservation_failures:
        failures.append("preservation_failures")
    if stable_hash_failures:
        failures.append("stable_hash_failures")
    if product_driving_failures:
        failures.append("proof_object_started_driving_product_surfaces")
    return {
        "snapshot_name": "design_guide_final_publication_boundary",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "purpose": "Compare current distributed publication-shaped data to FinalDesignGuidePublication.",
        "product_behavior_changed": False,
        "cta_moved": False,
        "card_rendering_moved": False,
        "inputs_page_publication_replaced": False,
        "fallback_branches_removed": False,
        "final_publication_imports": imports,
        "forbidden_final_publication_imports": forbidden_imports,
        "cases": cases,
        "preservation_failures": preservation_failures,
        "stable_hash_failures": stable_hash_failures,
        "product_driving_failures": product_driving_failures,
        "live_authority_outside_object": live_authority_outside_object,
        "object_ready_for_cta_authority": False,
        "object_ready_for_cta_authority_reason": "CTA/apply binding and source precedence remain live outside the proof object.",
        "object_ready_for_card_vm_authority": False,
        "object_ready_for_card_vm_authority_reason": "Card VM and render-model prep still mutate visible title/status/action/blocker surfaces.",
        "object_ready_for_render_freeze": False,
        "object_ready_for_render_freeze_reason": "Render fallback shells and late render-after-publication overrides remain live.",
        "snapshot_hash": _stable_hash(
            {
                "case_hashes": {
                    name: case["preserved_fields"]["publication_hash"]
                    for name, case in cases.items()
                },
                "live_authority_outside_object": live_authority_outside_object,
                "readiness": {
                    "cta": False,
                    "card_vm": False,
                    "render_freeze": False,
                },
            }
        ),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    case_rows = []
    for name, case in snapshot["cases"].items():
        preserved = case["preserved_fields"]
        case_rows.append(
            "| {name} | {outcome} | {family} | {cta} | {title} | {stable} | {mismatches} |".format(
                name=name,
                outcome=preserved["outcome_state"],
                family=preserved["selected_family"],
                cta="enabled" if preserved["cta_enabled"] else "disabled",
                title=str(preserved["display_title"] or ""),
                stable="yes" if case["stable_hash"] else "no",
                mismatches=len(case["mismatches"]),
            )
        )
    live_rows = []
    for row in snapshot["live_authority_outside_object"]:
        live_rows.append(
            "| {checkpoint} | `{owner}` | `{symbol}` | {authority} |".format(
                checkpoint=row["checkpoint"],
                owner=row["owner"],
                symbol=row["symbol"],
                authority=row["live_authority"],
            )
        )
    body = "\n".join(
        [
            "# Design Guide Final Publication Boundary Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "This is proof-only. It proves current distributed publication-shaped data can normalize into `FinalDesignGuidePublication`, while live authority remains outside the object.",
            "",
            "## Assertions",
            "",
            f"- Product behaviour changed: `{snapshot['product_behavior_changed']}`",
            f"- CTA moved: `{snapshot['cta_moved']}`",
            f"- Card rendering moved: `{snapshot['card_rendering_moved']}`",
            f"- `inputs_page.py` publication replaced: `{snapshot['inputs_page_publication_replaced']}`",
            f"- Fallback branches removed: `{snapshot['fallback_branches_removed']}`",
            f"- Forbidden final-publication imports: `{snapshot['forbidden_final_publication_imports']}`",
            "",
            "## Readiness",
            "",
            f"- object_ready_for_cta_authority: `{'yes' if snapshot['object_ready_for_cta_authority'] else 'no'}`",
            f"  Reason: {snapshot['object_ready_for_cta_authority_reason']}",
            f"- object_ready_for_card_vm_authority: `{'yes' if snapshot['object_ready_for_card_vm_authority'] else 'no'}`",
            f"  Reason: {snapshot['object_ready_for_card_vm_authority_reason']}",
            f"- object_ready_for_render_freeze: `{'yes' if snapshot['object_ready_for_render_freeze'] else 'no'}`",
            f"  Reason: {snapshot['object_ready_for_render_freeze_reason']}",
            "",
            "## Normalization Cases",
            "",
            "| Case | Outcome | Selected family | CTA | Display title | Stable | Mismatches |",
            "|---|---|---|---|---|---|---:|",
            *case_rows,
            "",
            "## Live Authority Still Outside Object",
            "",
            "| Checkpoint | Owner | Symbol | Live authority |",
            "|---|---|---|---|",
            *live_rows,
            "",
            "## Next Slice",
            "",
            "Add an in-place proof adapter snapshot at the live final-visible resolver/binding boundary that emits `FinalDesignGuidePublication` beside the existing payload and asserts hash parity without driving CTA or render.",
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_final_publication_boundary_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_publication_boundary_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_final_publication_boundary_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("failures=" + ", ".join(snapshot["failures"]))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
