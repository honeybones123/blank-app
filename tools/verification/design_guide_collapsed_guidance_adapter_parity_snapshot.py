"""Proof-only parity snapshot for collapsed guidance item publication adapter.

This verifier proves Design Brain can build the collapsed_guidance_items item
shape from FinalDesignGuidePublication without importing page/UI/session/apply
or render ownership. It does not wire the adapter into the live replacement
path.
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

FORBIDDEN_IMPORT_FRAGMENTS = (
    "inputs_page",
    "streamlit",
    "session_state",
    "publication rendering",
    "apply routing",
    "button rendering",
)

REQUIRED_ADAPTER_FIELDS = (
    "published_item_id",
    "final_visible_item_id",
    "publication_item_id",
    "post_click_design_guide_state",
    "selected_family_id",
    "published_family_id",
    "family",
    "outcome_state",
    "button_contract",
    "action_payload",
    "candidate_search_evidence",
    "publication_hash",
    "final_publication_authority_hash",
    "final_publication_cta_hash",
    "final_publication_display_hash",
    "final_publication_evidence_hash",
    "collapsed_guidance_item_hash",
    "legacy_non_authoritative",
    "compatibility_only",
    "derived_from",
    "collapsed_guidance_adapter_proof_only",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _module_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(str(node.module or ""))
    return sorted(set(imports))


def _case_definitions() -> dict[str, dict[str, Any]]:
    return {
        "action": {
            "item": {
                "published_item_id": "dg-bending-action-001",
                "post_click_design_guide_state": "ACTION",
                "selected_family_id": "BENDING_FAIL_GOVERNS",
                "family": "BENDING_FAIL_GOVERNS",
                "status": "ACTION",
                "bucket": "action",
                "title_main": "Increase bottom reinforcement",
                "pill": "Action",
                "summary_line": "Add reinforcement to reach target utilisation.",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "label": "Apply repair",
                    "action_type": "apply_repair",
                    "family": "BENDING_FAIL_GOVERNS",
                    "source_candidate_id": "candidate-bending-001",
                },
                "action_payload": {
                    "action_type": "apply_repair",
                    "family": "BENDING_FAIL_GOVERNS",
                    "candidate_id": "candidate-bending-001",
                    "updates": {"bot_bar_count": 4},
                },
                "candidate_search_evidence": {"executor_backed": True, "target_low": 0.85, "target_high": 1.0},
            }
        },
        "blocked": {
            "item": {
                "published_item_id": "dg-shear-blocked-001",
                "post_click_design_guide_state": "BLOCKED",
                "selected_family_id": "SHEAR_FAIL_GOVERNS",
                "family": "SHEAR_FAIL_GOVERNS",
                "status": "BLOCKED",
                "bucket": "blocked",
                "title_main": "Shear repair blocked",
                "pill": "Blocked",
                "summary_line": "No legal shear repair remains.",
                "blocking_reason": "Spacing and leg count limits are exhausted.",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "label": "No automatic repair",
                    "disabled_reason": "Spacing and leg count limits are exhausted.",
                    "family": "SHEAR_FAIL_GOVERNS",
                },
                "candidate_search_evidence": {
                    "exact_blockers_by_family": {"shear": {"reason": "spacing_exhausted"}},
                    "target_low": 0.85,
                    "target_high": 1.0,
                },
            }
        },
        "pass": {
            "item": {
                "published_item_id": "dg-target-pass-001",
                "post_click_design_guide_state": "PASS",
                "selected_family_id": "TARGET_BAND_REACHED",
                "family": "TARGET_BAND_REACHED",
                "status": "PASS",
                "bucket": "pass",
                "title_main": "Design is in target band",
                "pill": "Pass",
                "summary_line": "No repair is required.",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "label": "No action required",
                    "family": "TARGET_BAND_REACHED",
                },
                "target_band_proof": {"in_band": True, "target_low": 0.85, "target_high": 1.0},
            }
        },
    }


def _build_snapshot() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_collapsed_guidance_item_from_final_publication,
        build_final_design_guide_publication,
        stable_final_publication_hash,
    )

    imports = _module_imports(FINAL_PUBLICATION_MODULE)
    forbidden_imports = [
        module
        for module in imports
        if any(fragment in module.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    ]
    cases: dict[str, Any] = {}
    failures: list[str] = []
    for name, case in _case_definitions().items():
        publication = build_final_design_guide_publication(item=case["item"])
        adapter_a = build_collapsed_guidance_item_from_final_publication(
            publication,
            current_item_compatibility=case["item"],
        )
        adapter_b = build_collapsed_guidance_item_from_final_publication(
            publication,
            current_item_compatibility=case["item"],
        )
        missing_fields = [field for field in REQUIRED_ADAPTER_FIELDS if field not in adapter_a]
        hash_stable = _stable_hash(adapter_a) == _stable_hash(adapter_b)
        identity_matches = {
            "published_item_id": adapter_a.get("published_item_id") == publication.published_item_id,
            "post_click_design_guide_state": adapter_a.get("post_click_design_guide_state")
            == publication.post_click_design_guide_state,
            "selected_family": adapter_a.get("selected_family_id") == publication.selected_family,
            "outcome_state": adapter_a.get("outcome_state") == publication.outcome_state,
        }
        cta_hash = stable_final_publication_hash(publication.cta.to_dict())
        display_hash = stable_final_publication_hash(publication.display.to_dict())
        evidence_hash = stable_final_publication_hash(publication.evidence.to_dict())
        hash_matches = {
            "cta_hash": adapter_a.get("final_publication_cta_hash") == cta_hash,
            "display_hash": adapter_a.get("final_publication_display_hash") == display_hash,
            "evidence_hash": adapter_a.get("final_publication_evidence_hash") == evidence_hash,
            "publication_hash": adapter_a.get("publication_hash") == publication.publication_hash,
        }
        compatibility_shape_preserved = all(
            adapter_a.get(field) == case["item"].get(field)
            for field in ("title_main", "pill", "summary_line", "status", "bucket")
            if field in case["item"]
        )
        non_product_driving = bool(
            adapter_a.get("collapsed_guidance_adapter_proof_only")
            and adapter_a.get("product_driving") is False
            and adapter_a.get("render_driving") is False
            and adapter_a.get("legacy_non_authoritative") is True
            and adapter_a.get("compatibility_only") is True
        )
        case_failures = []
        if missing_fields:
            case_failures.append("missing_adapter_fields")
        if not hash_stable:
            case_failures.append("unstable_adapter_hash")
        if not all(identity_matches.values()):
            case_failures.append("identity_mismatch")
        if not all(hash_matches.values()):
            case_failures.append("hash_mismatch")
        if not compatibility_shape_preserved:
            case_failures.append("compatibility_shape_changed")
        if not non_product_driving:
            case_failures.append("product_or_render_driving_flag")
        if case_failures:
            failures.extend(f"{name}:{failure}" for failure in case_failures)
        cases[name] = {
            "publication_hash": publication.publication_hash,
            "adapter_hash": _stable_hash(adapter_a),
            "adapter_output": adapter_a,
            "missing_fields": missing_fields,
            "hash_stable": hash_stable,
            "identity_matches": identity_matches,
            "hash_matches": hash_matches,
            "compatibility_shape_preserved": compatibility_shape_preserved,
            "non_product_driving": non_product_driving,
            "case_failures": case_failures,
        }

    source = FINAL_PUBLICATION_MODULE.read_text(encoding="utf-8")
    adapter_has_no_forbidden_terms = not any(
        token in source
        for token in (
            "import inputs_page",
            "import streamlit",
            "st.session_state",
            "render_html",
            "apply routing",
        )
    )
    if forbidden_imports:
        failures.append("forbidden_imports")
    if not adapter_has_no_forbidden_terms:
        failures.append("forbidden_adapter_terms")

    parity_status = "PASS" if not failures else "FAIL"
    proof_surface = {
        "cases": {
            name: {
                "publication_hash": row["publication_hash"],
                "adapter_hash": row["adapter_hash"],
                "identity_matches": row["identity_matches"],
                "hash_matches": row["hash_matches"],
                "compatibility_shape_preserved": row["compatibility_shape_preserved"],
                "non_product_driving": row["non_product_driving"],
            }
            for name, row in cases.items()
        },
        "forbidden_imports": forbidden_imports,
        "adapter_has_no_forbidden_terms": adapter_has_no_forbidden_terms,
    }
    return {
        "snapshot_name": "design_guide_collapsed_guidance_adapter_parity_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "parity_status": parity_status,
        "status": parity_status,
        "object_ready_for_collapsed_replacement_wiring": parity_status == "PASS",
        "replacement_consumes_publication_still_requires_live_wiring": True,
        "required_adapter_fields": list(REQUIRED_ADAPTER_FIELDS),
        "cases": cases,
        "imports": imports,
        "forbidden_imports": forbidden_imports,
        "adapter_has_no_page_ui_session_apply_render_ownership": adapter_has_no_forbidden_terms
        and not forbidden_imports,
        "product_behavior_changed": False,
        "live_replacement_wired": False,
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = []
    for name, case in snapshot["cases"].items():
        rows.append(
            "| `{name}` | `{status}` | `{pub_hash}` | `{adapter_hash}` | `{identity}` | `{hashes}` | `{shape}` |".format(
                name=name,
                status="PASS" if not case["case_failures"] else "FAIL",
                pub_hash=case["publication_hash"],
                adapter_hash=case["adapter_hash"],
                identity=all(case["identity_matches"].values()),
                hashes=all(case["hash_matches"].values()),
                shape=case["compatibility_shape_preserved"],
            )
        )
    body = "\n".join(
        [
            "# Design Guide Collapsed Guidance Adapter Parity Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Adapter parity status: `{snapshot['parity_status']}`",
            f"- Object ready for collapsed replacement wiring: `{snapshot['object_ready_for_collapsed_replacement_wiring']}`",
            f"- Live replacement wired: `{snapshot['live_replacement_wired']}`",
            f"- Product behavior changed: `{snapshot['product_behavior_changed']}`",
            f"- No page/UI/session/apply/render ownership: `{snapshot['adapter_has_no_page_ui_session_apply_render_ownership']}`",
            "",
            "## Cases",
            "",
            "| Case | Status | Publication Hash | Adapter Hash | Identity Matches | Hashes Match | Compatibility Shape Preserved |",
            "|---|---|---|---|---:|---:|---:|",
            *rows,
            "",
            "## Scope",
            "",
            "- The adapter accepts `FinalDesignGuidePublication` and optional plain compatibility data only.",
            "- The adapter is proof-only and non-product-driving.",
            "- `collapsed_guidance_items` replacement is not wired in this slice.",
            "",
            "## Failures",
            "",
            (
                "None."
                if not snapshot["failures"]
                else "\n".join(f"- `{failure}`" for failure in snapshot["failures"])
            ),
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_collapsed_guidance_adapter_parity_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_collapsed_guidance_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_collapsed_guidance_adapter_parity_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
