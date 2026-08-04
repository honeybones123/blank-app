"""Proof-only parity snapshot for FinalDesignGuidePublication CTA adapter."""

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

COMPARE_FIELDS = (
    "enabled",
    "label",
    "disabled_reason",
    "action_type",
    "apply_payload_fingerprint",
    "executor_backed_proof",
    "stale_fresh_token_proof",
    "source_precedence_proof",
    "one_click_action_handoff",
)

REMAINING_LIVE_CTA_PATHS = [
    "inputs_page.py::_publish_final_visible_design_guide_contract_binding",
    "inputs_page.py::_record_rendered_design_guide_primary_apply_payload",
    "inputs_page.py::_consume_design_guide_component_cta_value",
    "inputs_page.py::_queue_primary_design_guide_button_action",
    "inputs_page.py::_resolve_design_guide_button_contract_source_precedence",
    "design_brain/publication.py::resolve_design_guide_visible_blocker_disabled_contract",
    "design_brain/publication.py::disabled_design_guide_button_contract",
]


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
    forbidden = {"inputs_page", "streamlit"}
    hits: list[str] = []
    for name in imports:
        for root in forbidden:
            if name == root or name.startswith(root + "."):
                hits.append(name)
    return sorted(set(hits))


def _case_definitions() -> dict[str, dict[str, Any]]:
    return {
        "enabled_executor_backed_apply_cta": {
            "item": {
                "primary_action": "Run one-click auto design",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "bending",
                    "updates": {"bot_dia": 20},
                    "preview_pass": True,
                    "source_candidate_id": "enabled-1",
                    "executor_backed": True,
                },
                "action_payload": {"action_type": "apply_resolved_candidate", "updates": {"bot_dia": 20}},
                "candidate_search_evidence": {"safe_executor_backed_candidates_count": 1},
            },
            "source_precedence": {
                "button_contract_source": "displayed_primary_item",
                "update_payload_source": "button_contract_updates",
                "candidate_source": "source_candidate_id",
            },
        },
        "disabled_blocker_cta": {
            "item": {
                "primary_action": "Review blocker evidence",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "family": "shear",
                    "blocking_reason": "no_valid_shear_repair",
                    "updates": {},
                },
                "blocking_reason": "no_valid_shear_repair",
            },
        },
        "stale_payload_disabled_cta": {
            "item": {
                "primary_action": "Run one-click auto design",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "action_type": "apply_resolved_candidate",
                    "family": "bending",
                    "blocking_reason": "component_apply_token_mismatch",
                    "updates": {"bot_dia": 20},
                },
                "action_payload": {
                    "action_type": "apply_resolved_candidate",
                    "updates": {"bot_dia": 20},
                    "component_apply_token": "stale-token",
                    "stale_apply_payload_blocked": True,
                    "stale_apply_payload_mismatch_reason": "component_apply_token_mismatch",
                    "stale_apply_payload_expected_fingerprint": "expected-fp",
                    "stale_apply_payload_current_fingerprint": "current-fp",
                },
            },
        },
        "proof_pending_cta": {
            "item": {
                "primary_action": "Review Design Guide recommendation",
                "button_contract": {},
            },
            "debug": {"publication_probe_pending": True},
        },
        "no_action_pass_cta": {
            "item": {
                "status": "PASS",
                "bucket": "pass",
                "title_main": "Design accepted",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "blocking_reason": "target_band_reached_no_action",
                },
            },
        },
        "one_click_handoff_cta": {
            "item": {
                "primary_action": "Run one-click auto design",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "combined",
                    "updates": {"s_lig": 200, "bot_dia": 20},
                    "preview_pass": True,
                    "candidate_id": "one-click-1",
                },
                "action_payload": {
                    "action_type": "apply_resolved_candidate",
                    "family": "combined",
                    "updates": {"s_lig": 200, "bot_dia": 20},
                    "candidate_id": "one-click-1",
                },
            },
            "candidate_search_evidence": {"safe_executor_backed_candidates_count": 1},
        },
        "fallback_disabled_cta": {
            "item": {
                "primary_action": "Publication blocked by family contract.",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "family": "BENDING_FAIL_GOVERNS",
                    "action_type": None,
                    "updates": {},
                    "blocking_reason": "family_selection_contract_mismatch",
                },
            },
        },
    }


def _manual_expected(case: dict[str, Any]) -> dict[str, Any]:
    from design_brain.final_publication import stable_final_publication_hash

    item = dict(case.get("item") or {})
    debug = dict(case.get("debug") or {})
    contract = dict(case.get("button_contract") or item.get("button_contract") or {})
    action_payload = dict(case.get("action_payload") or item.get("action_payload") or {})
    evidence = dict(case.get("candidate_search_evidence") or item.get("candidate_search_evidence") or {})
    source_precedence = dict(case.get("source_precedence") or {})
    if source_precedence:
        debug.update(
            {
                "winning_button_contract_source": source_precedence.get("winning_button_contract_source")
                or source_precedence.get("button_contract_source"),
                "winning_update_payload_source": source_precedence.get("winning_update_payload_source")
                or source_precedence.get("update_payload_source"),
                "winning_candidate_source": source_precedence.get("winning_candidate_source")
                or source_precedence.get("candidate_source"),
            }
        )
    updates = dict(
        contract.get("updates")
        or action_payload.get("updates")
        or action_payload.get("resolved_candidate_updates")
        or item.get("updates")
        or {}
    )
    apply_payload_source = action_payload or {"updates": updates}

    def text(*values: Any) -> str | None:
        for value in values:
            value_text = str(value or "").strip()
            if value_text:
                return value_text
        return None

    executor_backed_proof = {
        "executor_backed": bool(
            contract.get("executor_backed")
            or action_payload.get("executor_backed")
            or evidence.get("executor_backed")
            or evidence.get("safe_executor_backed_candidate_found")
            or int(evidence.get("safe_executor_backed_candidates_count") or 0) > 0
        ),
        "safe_executor_backed_candidates_count": evidence.get("safe_executor_backed_candidates_count"),
        "preview_pass": contract.get("preview_pass"),
        "source": text(contract.get("executor_source"), evidence.get("executor_source"), "publication_payload"),
    }
    stale_fresh_token_proof = {
        "component_apply_token": text(action_payload.get("component_apply_token"), debug.get("component_apply_token")),
        "stale_apply_payload_blocked": bool(
            action_payload.get("stale_apply_payload_blocked")
            or debug.get("stale_apply_payload_blocked")
        ),
        "stale_apply_payload_mismatch_reason": text(
            action_payload.get("stale_apply_payload_mismatch_reason"),
            debug.get("stale_apply_payload_mismatch_reason"),
            debug.get("component_apply_stale_reason"),
        ),
        "expected_fingerprint": text(
            action_payload.get("stale_apply_payload_expected_fingerprint"),
            debug.get("stale_apply_payload_expected_fingerprint"),
        ),
        "current_fingerprint": text(
            action_payload.get("stale_apply_payload_current_fingerprint"),
            debug.get("stale_apply_payload_current_fingerprint"),
        ),
    }
    source_precedence_proof = {
        "button_contract_source": text(
            debug.get("winning_button_contract_source"),
            debug.get("button_contract_source"),
            evidence.get("winning_button_contract_source"),
        ),
        "update_payload_source": text(
            debug.get("winning_update_payload_source"),
            debug.get("update_payload_source"),
            evidence.get("winning_update_payload_source"),
        ),
        "candidate_source": text(
            debug.get("winning_candidate_source"),
            debug.get("candidate_source"),
            evidence.get("winning_candidate_source"),
        ),
        "source_precedence_hash": stable_final_publication_hash(
            {
                "button_contract_source": debug.get("winning_button_contract_source")
                or debug.get("button_contract_source")
                or evidence.get("winning_button_contract_source"),
                "update_payload_source": debug.get("winning_update_payload_source")
                or debug.get("update_payload_source")
                or evidence.get("winning_update_payload_source"),
                "candidate_source": debug.get("winning_candidate_source")
                or debug.get("candidate_source")
                or evidence.get("winning_candidate_source"),
            }
        ),
    }
    return {
        "enabled": bool(contract.get("enabled") or contract.get("actionable")),
        "label": text(item.get("primary_action"), item.get("cta_label"), contract.get("label")),
        "disabled_reason": text(contract.get("disabled_reason"), contract.get("blocking_reason"), item.get("blocking_reason")),
        "action_type": text(contract.get("action_type"), item.get("action_type"), action_payload.get("action_type")),
        "apply_payload_fingerprint": stable_final_publication_hash(apply_payload_source),
        "executor_backed_proof": executor_backed_proof,
        "stale_fresh_token_proof": stale_fresh_token_proof,
        "source_precedence_proof": source_precedence_proof,
        "one_click_action_handoff": {
            "action_type": text(contract.get("action_type"), item.get("action_type"), action_payload.get("action_type")),
            "candidate_id": text(
                contract.get("source_candidate_id"),
                contract.get("candidate_id"),
                action_payload.get("source_candidate_id"),
                action_payload.get("candidate_id"),
                item.get("source_candidate_id"),
                item.get("candidate_id"),
            ),
            "family": text(contract.get("family"), action_payload.get("family"), item.get("family")),
            "updates_hash": stable_final_publication_hash(updates),
            "has_updates": bool(updates),
        },
    }


def _build_snapshot() -> dict[str, Any]:
    from design_brain.final_publication import build_final_publication_cta_from_current_state

    imports = _module_imports(FINAL_PUBLICATION_MODULE)
    forbidden_imports = _forbidden_imports(imports)
    cases: dict[str, Any] = {}
    failures: list[str] = []
    for name, case in _case_definitions().items():
        cta_a = build_final_publication_cta_from_current_state(
            item=case.get("item"),
            debug=case.get("debug"),
            button_contract=case.get("button_contract"),
            action_payload=case.get("action_payload"),
            candidate_search_evidence=case.get("candidate_search_evidence"),
            source_precedence=case.get("source_precedence"),
        )
        cta_b = build_final_publication_cta_from_current_state(
            item=case.get("item"),
            debug=case.get("debug"),
            button_contract=case.get("button_contract"),
            action_payload=case.get("action_payload"),
            candidate_search_evidence=case.get("candidate_search_evidence"),
            source_precedence=case.get("source_precedence"),
        )
        actual = cta_a.to_dict()
        expected = _manual_expected(case)
        mismatches = {
            field: {"expected": expected.get(field), "actual": actual.get(field)}
            for field in COMPARE_FIELDS
            if actual.get(field) != expected.get(field)
        }
        stable_hash = _stable_hash(actual) == _stable_hash(cta_b.to_dict())
        if mismatches:
            failures.append(f"{name}:field_parity")
        if not stable_hash:
            failures.append(f"{name}:unstable_hash")
        if actual.get("product_driving") is not False:
            failures.append(f"{name}:product_driving")
        cases[name] = {
            "parity_status": "PASS" if not mismatches and stable_hash else "FAIL",
            "actual": {field: actual.get(field) for field in COMPARE_FIELDS},
            "expected": expected,
            "mismatches": mismatches,
            "stable_hash": stable_hash,
            "cta_hash": _stable_hash(actual),
        }
    if forbidden_imports:
        failures.append("final_publication_forbidden_imports")
    parity_status = "PASS" if not failures else "FAIL"
    object_ready_for_live_cta_authority = bool(parity_status == "PASS")
    return {
        "snapshot_name": "design_guide_cta_adapter_parity",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "parity_status": parity_status,
        "status": parity_status,
        "product_behavior_changed": False,
        "cta_rendering_moved": False,
        "apply_routing_moved": False,
        "button_labels_changed": False,
        "disabled_reasons_changed": False,
        "one_click_orchestration_changed": False,
        "visible_wording_edited": False,
        "final_publication_imports": imports,
        "forbidden_final_publication_imports": forbidden_imports,
        "cases": cases,
        "object_ready_for_live_cta_authority": object_ready_for_live_cta_authority,
        "object_ready_for_live_cta_authority_text": "yes" if object_ready_for_live_cta_authority else "no",
        "remaining_live_cta_paths": list(REMAINING_LIVE_CTA_PATHS),
        "required_before_live_move": [
            "wire adapter trace-only beside live final-visible CTA binding",
            "compare adapter output to live button contract/session apply payload in product-shaped snapshots",
            "prove render fallback shells do not diverge from adapter CTA",
            "keep source precedence and stale-token checks page-owned until live parity is green",
        ],
        "snapshot_hash": _stable_hash(
            {
                "case_hashes": {name: case["cta_hash"] for name, case in cases.items()},
                "remaining_live_cta_paths": REMAINING_LIVE_CTA_PATHS,
                "ready": object_ready_for_live_cta_authority,
            }
        ),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = []
    for name, case in snapshot["cases"].items():
        actual = case["actual"]
        rows.append(
            "| {name} | {status} | {enabled} | {label} | {reason} | {stable} | {mismatch_count} |".format(
                name=name,
                status=case["parity_status"],
                enabled=actual.get("enabled"),
                label=str(actual.get("label") or ""),
                reason=str(actual.get("disabled_reason") or ""),
                stable="yes" if case["stable_hash"] else "no",
                mismatch_count=len(case["mismatches"]),
            )
        )
    body = "\n".join(
        [
            "# Design Guide CTA Adapter Parity Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['parity_status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "This is proof-only. CTA rendering, apply routing, labels, disabled reasons, one-click orchestration, fallback branches, and visible wording are unchanged.",
            "",
            "## Assertions",
            "",
            f"- Product behaviour changed: `{snapshot['product_behavior_changed']}`",
            f"- CTA rendering moved: `{snapshot['cta_rendering_moved']}`",
            f"- Apply routing moved: `{snapshot['apply_routing_moved']}`",
            f"- Button labels changed: `{snapshot['button_labels_changed']}`",
            f"- Disabled reasons changed: `{snapshot['disabled_reasons_changed']}`",
            f"- One-click orchestration changed: `{snapshot['one_click_orchestration_changed']}`",
            f"- Visible wording edited: `{snapshot['visible_wording_edited']}`",
            f"- Forbidden final-publication imports: `{snapshot['forbidden_final_publication_imports']}`",
            "",
            "## Parity Cases",
            "",
            "| Case | Parity | Enabled | Label | Disabled reason | Stable | Mismatches |",
            "|---|---|---|---|---|---|---:|",
            *rows,
            "",
            "## Live CTA Authority Readiness",
            "",
            f"- object_ready_for_live_cta_authority: `{snapshot['object_ready_for_live_cta_authority_text']}`",
            "",
            "Remaining live CTA paths:",
            "",
            *[f"- `{path}`" for path in snapshot["remaining_live_cta_paths"]],
            "",
            "Required before live move:",
            "",
            *[f"- {item}" for item in snapshot["required_before_live_move"]],
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_cta_adapter_parity_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_cta_adapter_parity_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_cta_adapter_parity_snapshot {snapshot['parity_status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("failures=" + ", ".join(snapshot["failures"]))
    return 0 if snapshot["parity_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
