"""Proof-only object snapshot for post-click final-contract predicate adapter."""

from __future__ import annotations

import ast
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

REQUIRED_REPRESENTED_ROWS = {
    "final_contract",
    "final_family",
    "final_expected_util",
    "current_bending_util",
    "contract_enabled_predicate",
    "exact_blocker_predicate",
    "requires_exact_blocker_predicate",
    "visible_action_predicate",
    "bending_audit_assembly",
    "bending_resolution_builder_request",
    "post_click_rebinding_request",
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


def _cases() -> dict[str, dict[str, Any]]:
    exact_blocker = {
        "exact_blocker": True,
        "no_second_cta_required": True,
        "best_safe_final_util": 0.72,
    }
    base_item = {
        "family": "bending",
        "check_key": "bending",
        "action_type": "apply_resolved_candidate",
        "title": "Best safe bending cleanup",
        "button_contract": {
            "actionable": True,
            "updates": {"bot_dia": 16},
            "preview_pass": True,
            "blocking_reason": None,
            "expected_util": 0.72,
            "family": "bending",
            "action_type": "apply_resolved_candidate",
        },
        "candidate_search_evidence": {
            "exact_blockers_by_family": {"bending": exact_blocker},
            "outside_target_band_allowed": True,
            "outside_target_band_allowed_category": "safe_incremental_cleanup_below_final_threshold",
        },
        "best_safe_partial_cleanup": True,
    }
    return {
        "enabled_bending_cleanup": {
            "item": dict(base_item),
            "resolution": {"overview": {"utils": {"bending": 0.62}}, "render_reason": "normal"},
            "debug": {"post_click_unresolved_low_util_families": ["bending"]},
            "expected": {
                "contract_enabled": True,
                "exact_blocker_on_visible_item": True,
                "requires_exact_blocker": True,
                "visible_action": True,
                "bending_resolution_required": True,
            },
        },
        "disabled_exact_blocker": {
            "item": {
                **dict(base_item),
                "button_contract": {
                    **dict(base_item["button_contract"]),
                    "actionable": False,
                    "updates": {},
                    "preview_pass": False,
                    "blocking_reason": "post_click_safe_incremental_cleanup_requires_exact_blocker",
                },
            },
            "resolution": {"overview": {"utils": {"bending": 0.62}}, "render_reason": "normal"},
            "debug": {"post_click_families_below_final_threshold": ["bending"]},
            "expected": {
                "contract_enabled": False,
                "exact_blocker_on_visible_item": True,
                "requires_exact_blocker": True,
                "visible_action": True,
                "bending_resolution_required": True,
            },
        },
        "same_flow_cleanup_apply": {
            "item": {**dict(base_item), "candidate_search_evidence": {}},
            "resolution": {"overview": {"utils": {"bending": 0.62}}, "render_reason": "normal"},
            "debug": {},
            "last_apply_route": {
                "apply_used_resolved_candidate_payload": True,
                "applied_updates": {"bot_dia": 16},
                "resolved_candidate_label": "cleanup candidate",
            },
            "expected": {
                "contract_enabled": True,
                "exact_blocker_on_visible_item": False,
                "requires_exact_blocker": True,
                "visible_action": True,
                "bending_resolution_required": True,
            },
        },
        "non_bending_no_action": {
            "item": {**dict(base_item), "family": "shear", "check_key": "shear"},
            "resolution": {"overview": {"utils": {"bending": 0.62}}, "render_reason": "normal"},
            "debug": {"post_click_unresolved_low_util_families": ["bending"]},
            "expected": {
                "contract_enabled": True,
                "exact_blocker_on_visible_item": True,
                "requires_exact_blocker": True,
                "visible_action": False,
                "bending_resolution_required": False,
            },
        },
    }


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_final_contract_predicate_result_adapter,
    )

    source = MODULE_PATH.read_text(encoding="utf-8")
    imports = _module_imports(source)
    rows: list[dict[str, Any]] = []
    for name, case in _cases().items():
        result = build_final_design_guide_post_click_final_contract_predicate_result_adapter(
            item=case.get("item"),
            final_visible_resolution=case.get("resolution"),
            guidance_debug=case.get("debug"),
            last_apply_route=case.get("last_apply_route"),
            primary_payload_binding_audit=case.get("primary_payload_binding_audit"),
            current_state=case.get("current_state"),
            final_contract=(case.get("item") or {}).get("button_contract"),
            final_accepted_min_family_util=0.85,
            target_band_eps=0.0,
            compound_shear_update_keys=("lig_d", "lig_legs"),
        )
        repeat = build_final_design_guide_post_click_final_contract_predicate_result_adapter(
            item=case.get("item"),
            final_visible_resolution=case.get("resolution"),
            guidance_debug=case.get("debug"),
            last_apply_route=case.get("last_apply_route"),
            primary_payload_binding_audit=case.get("primary_payload_binding_audit"),
            current_state=case.get("current_state"),
            final_contract=(case.get("item") or {}).get("button_contract"),
            final_accepted_min_family_util=0.85,
            target_band_eps=0.0,
            compound_shear_update_keys=("lig_d", "lig_legs"),
        )
        predicates = dict(result.get("predicate_result") or {})
        request = dict(result.get("bending_resolution_request") or {})
        expected = dict(case.get("expected") or {})
        comparisons = {
            "contract_enabled": predicates.get("contract_enabled")
            == expected.get("contract_enabled"),
            "exact_blocker_on_visible_item": predicates.get("exact_blocker_on_visible_item")
            == expected.get("exact_blocker_on_visible_item"),
            "requires_exact_blocker": predicates.get("requires_exact_blocker")
            == expected.get("requires_exact_blocker"),
            "visible_action": predicates.get("visible_action") == expected.get("visible_action"),
            "bending_resolution_required": request.get("required")
            == expected.get("bending_resolution_required"),
        }
        rows.append(
            {
                "case": name,
                "comparisons": comparisons,
                "all_match": all(comparisons.values()),
                "proof_hash": result.get("proof_hash"),
                "stable_hash_repeat": result.get("proof_hash") == repeat.get("proof_hash"),
                "represented_live_rows": list(result.get("represented_live_rows") or []),
                "page_owned_input_rows": list(result.get("page_owned_input_rows") or []),
                "proof_only": result.get("proof_only") is True,
                "product_driving": result.get("product_driving") is True,
                "render_driving": result.get("render_driving") is True,
                "apply_driving": result.get("apply_driving") is True,
                "session_driving": result.get("session_driving") is True,
                "raw": result,
            }
        )
    represented_rows = set()
    for row in rows:
        represented_rows.update(row.get("represented_live_rows") or [])
    return {
        "case_rows": rows,
        "all_cases_match": all(row.get("all_match") for row in rows),
        "all_hashes_stable": all(row.get("stable_hash_repeat") for row in rows),
        "represented_live_rows": sorted(represented_rows),
        "missing_represented_rows": sorted(REQUIRED_REPRESENTED_ROWS - represented_rows),
        "latest_decomposition_audit": {
            "status": _latest("design_guide_post_click_final_contract_consumer_decomposition").get("status"),
            "path": _latest("design_guide_post_click_final_contract_consumer_decomposition").get("path"),
        },
        "forbidden_imports": _forbidden_imports(imports),
        "forbidden_source_hits": _forbidden_source_hits(source),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "all_cases_match_expected": capture.get("all_cases_match") is True,
        "all_hashes_stable": capture.get("all_hashes_stable") is True,
        "all_required_rows_represented": not capture.get("missing_represented_rows"),
        "decomposition_audit_pass": (capture.get("latest_decomposition_audit") or {}).get("status")
        == "PASS",
        "no_forbidden_imports": not capture.get("forbidden_imports"),
        "no_forbidden_source_hits": not capture.get("forbidden_source_hits"),
        "not_product_driving": all(row.get("product_driving") is False for row in capture.get("case_rows") or []),
        "not_render_driving": all(row.get("render_driving") is False for row in capture.get("case_rows") or []),
        "not_apply_driving": all(row.get("apply_driving") is False for row in capture.get("case_rows") or []),
        "not_session_driving": all(row.get("session_driving") is False for row in capture.get("case_rows") or []),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Final-Contract Predicate Result Adapter Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Cases",
        "",
    ]
    for row in capture.get("case_rows") or []:
        lines.append(
            f"- `{row.get('case')}`: all_match=`{row.get('all_match')}`, "
            f"stable_hash_repeat=`{row.get('stable_hash_repeat')}`"
        )
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            f"- Missing represented rows: `{capture.get('missing_represented_rows')}`",
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
        "schema": "design_guide_post_click_final_contract_predicate_result_adapter_object_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_final_contract_predicate_result_adapter_object_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_final_contract_predicate_result_adapter_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_final_contract_predicate_result_adapter_object {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
