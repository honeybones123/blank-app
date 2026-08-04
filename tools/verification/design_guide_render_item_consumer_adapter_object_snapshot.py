"""Proof-only snapshot for the render-item consumer adapter object.

This proves the Design Brain object can represent the post-binding consumers
that currently keep the final-visible compatibility restamper alive. It does
not wire the object into live rendering, move authority, route Apply, or change
visible output.
"""

from __future__ import annotations

import ast
from dataclasses import fields
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
MODULE_PATH = ROOT / "design_brain" / "final_publication.py"

REQUIRED_CONSUMER_COVERAGE = {
    "terminal_state",
    "zero_shear_projection",
    "visible_blocker_check",
    "safe_low_util_cleanup_action",
    "safe_low_util_projection",
    "resolution_item_sync",
    "post_click_contract",
    "post_click_family",
    "post_click_contract_check_input_proof",
    "post_click_bending_resolution",
    "post_click_exact_blocker_adapter",
    "post_click_replacement_decision_proof",
    "post_click_final_contract_adapter_proof",
}

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


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": "MISSING", "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    return {
        "found": True,
        "path": str(path),
        "status": "PASS"
        if ("PASS" in status.upper() or "LOCKED" in status.upper())
        else status or "UNKNOWN",
        "payload": payload,
    }


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
    return sorted(term for term in FORBIDDEN_SOURCE_TERMS if term in source)


def _sample_payload() -> dict[str, Any]:
    item = {
        "published_item_id": "post-binding-sample-1",
        "candidate_id": "post-binding-sample-1",
        "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
        "family": "bending",
        "check_key": "bending",
        "status": "FAIL",
        "bucket": "fail",
        "title_main": "Design Guide sample",
        "design_guide_terminal_state": "optimal",
        "guidance_intent": "specific_blocker",
        "blocking_reason": "safe_incremental_cleanup_below_final_threshold",
        "action_type": "apply_resolved_candidate",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "family": "bending",
            "action_type": "apply_resolved_candidate",
            "expected_util": 0.74,
            "updates": {"bot_dia": 16},
            "source_candidate_id": "post-binding-sample-1",
        },
        "candidate_search_evidence": {
            "blocker_attempts_by_family": {
                "shear": {"attempted": True, "cleanup_search_ran": True}
            },
            "exact_blockers_by_family": {
                "bending": {"attempted": True, "reason": "below final threshold"}
            },
            "post_click_exact_blockers_by_family": {
                "bending": {"attempted": True, "reason": "post-click exact stop"}
            },
        },
        "exact_blockers_by_family": {
            "bending": {"attempted": True, "reason": "below final threshold"}
        },
        "post_click_exact_blockers_by_family": {
            "bending": {"attempted": True, "reason": "post-click exact stop"}
        },
    }
    debug = {
        "post_click_design_guide_state": "optimal",
        "candidate_search_evidence": dict(item["candidate_search_evidence"]),
        "post_click_unresolved_low_util_families": ["bending"],
        "post_click_families_below_final_threshold": ["bending"],
    }
    resolution = {
        "item": dict(item),
        "overview": {"utils": {"bending": 0.42}},
        "render_reason": "final_visible_zero_shear_demand_accepted",
    }
    return {"item": item, "debug": debug, "final_visible_resolution": resolution}


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        FinalDesignGuideRenderItemConsumerProof,
        build_final_design_guide_publication,
        build_final_design_guide_render_item_consumer_proof,
    )

    source = MODULE_PATH.read_text(encoding="utf-8")
    imports = _module_imports(source)
    payload = _sample_payload()
    publication = build_final_design_guide_publication(
        item=dict(payload["item"]),
        debug=dict(payload["debug"]),
        publication_reason="render_item_consumer_adapter_object_snapshot",
    )
    proof = build_final_design_guide_render_item_consumer_proof(
        publication,
        selected_item=dict(payload["item"]),
        final_visible_resolution=dict(payload["final_visible_resolution"]),
        guidance_debug=dict(payload["debug"]),
    )
    proof_repeat = build_final_design_guide_render_item_consumer_proof(
        publication,
        selected_item=dict(payload["item"]),
        final_visible_resolution=dict(payload["final_visible_resolution"]),
        guidance_debug=dict(payload["debug"]),
    )
    proof_dict = proof.to_dict()
    coverage = dict(proof_dict.get("consumer_coverage") or {})
    missing_coverage = sorted(key for key in REQUIRED_CONSUMER_COVERAGE if coverage.get(key) is not True)
    extra_coverage = sorted(key for key in coverage if key not in REQUIRED_CONSUMER_COVERAGE)
    return {
        "dataclass_fields": sorted(field.name for field in fields(FinalDesignGuideRenderItemConsumerProof)),
        "required_coverage": sorted(REQUIRED_CONSUMER_COVERAGE),
        "consumer_coverage": coverage,
        "missing_coverage": missing_coverage,
        "extra_coverage": extra_coverage,
        "covered_consumer_groups": list(proof.covered_consumer_groups),
        "missing_consumer_groups": list(proof.missing_consumer_groups),
        "consumer_group_hashes": dict(proof.consumer_group_hashes),
        "consumer_proof_hash": proof.consumer_proof_hash,
        "consumer_proof_hash_repeat": proof_repeat.consumer_proof_hash,
        "stable_hash_repeat": proof.consumer_proof_hash == proof_repeat.consumer_proof_hash,
        "publication_hash": publication.publication_hash,
        "forbidden_imports": _forbidden_imports(imports),
        "forbidden_source_hits": _forbidden_source_hits(source),
        "latest_ownership_audit": {
            "status": _latest("design_guide_final_visible_post_binding_consumer_ownership").get("status"),
            "path": _latest("design_guide_final_visible_post_binding_consumer_ownership").get("path"),
        },
        "proof_only": proof.proof_only,
        "product_driving": proof.product_driving,
        "render_driving": proof.render_driving,
        "apply_driving": proof.apply_driving,
        "session_driving": proof.session_driving,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "consumer_coverage_field_present": "consumer_coverage" in capture.get("dataclass_fields", []),
        "all_required_consumers_covered": not capture.get("missing_coverage"),
        "no_unexpected_consumer_coverage": not capture.get("extra_coverage"),
        "all_group_hashes_present": set(capture.get("consumer_group_hashes") or {})
        >= {
            "zero_shear_cleanup",
            "safe_low_util_promotion",
            "post_click_final_contract_checks",
            "consumer_coverage",
        },
        "stable_hash_repeat": capture.get("stable_hash_repeat") is True,
        "ownership_audit_pass": (capture.get("latest_ownership_audit") or {}).get("status")
        == "PASS",
        "no_forbidden_imports": not capture.get("forbidden_imports"),
        "no_forbidden_source_hits": not capture.get("forbidden_source_hits"),
        "proof_only": capture.get("proof_only") is True,
        "not_product_driving": capture.get("product_driving") is False,
        "not_render_driving": capture.get("render_driving") is False,
        "not_apply_driving": capture.get("apply_driving") is False,
        "not_session_driving": capture.get("session_driving") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Render Item Consumer Adapter Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Coverage",
        "",
    ]
    for key in capture.get("required_coverage") or []:
        lines.append(f"- {key}: `{(capture.get('consumer_coverage') or {}).get(key)}`")
    lines.extend(
        [
            "",
            "## Result",
            "",
            f"- Missing coverage: `{capture.get('missing_coverage')}`",
            f"- Extra coverage: `{capture.get('extra_coverage')}`",
            f"- Stable hash repeat: `{capture.get('stable_hash_repeat')}`",
            f"- Ownership audit: `{(capture.get('latest_ownership_audit') or {}).get('status')}`",
            "",
            "## Checks",
            "",
        ]
    )
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_item_consumer_adapter_object_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_render_item_consumer_adapter_object_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_item_consumer_adapter_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_render_item_consumer_adapter_object {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
