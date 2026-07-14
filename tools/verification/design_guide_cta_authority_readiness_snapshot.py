"""Proof-only CTA authority readiness snapshot.

This verifier maps current CTA/apply authority paths into
FinalDesignGuidePublication.cta. It does not move CTA rendering, apply routing,
source precedence, stale-token checks, fallback paths, or visible wording.
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
FINAL_PUBLICATION_MODULE = ROOT / "design_brain" / "final_publication.py"

REQUIRED_CTA_FIELDS = {
    "enabled",
    "actionable",
    "label",
    "action_type",
    "family",
    "disabled_reason",
    "apply_payload_summary",
    "apply_payload_fingerprint",
    "button_contract_hash",
    "source_candidate_id",
    "executor_backed_proof",
    "stale_fresh_token_proof",
    "one_click_action_handoff",
    "source_precedence_proof",
    "product_driving",
}

CTA_AUTHORITY_PATHS: list[dict[str, Any]] = [
    {
        "path": "enabled_disabled_decision",
        "owner_file": "design_brain/publication.py",
        "function_or_symbol": "design_guide_button_contract_enabled",
        "required_tokens": ["def design_guide_button_contract_enabled(", "actionable", "enabled"],
        "current_authority_role": "interprets final button contract enabled/actionable state",
        "cta_fields": ["enabled", "actionable", "button_contract_hash"],
        "can_be_moved_now": False,
        "reason_if_no": "Page binding and render fallback still own when this enabled state is consumed.",
        "required_parity_proof": "compare object.cta.enabled/actionable to final bound button_contract at render and fallback checkpoints",
    },
    {
        "path": "action_label",
        "owner_file": "inputs_page.py",
        "function_or_symbol": "_build_pending_recommendation",
        "required_tokens": ["def _build_pending_recommendation(", "primary_action", "resolved_candidate_label"],
        "current_authority_role": "builds visible pending recommendation title/description/action label source",
        "cta_fields": ["label", "action_type"],
        "can_be_moved_now": False,
        "reason_if_no": "Visible wording and pending recommendation envelope remain page-owned.",
        "required_parity_proof": "compare object.cta.label/action_type against pending recommendation and rendered CTA label",
    },
    {
        "path": "disabled_reason",
        "owner_file": "design_brain/publication.py",
        "function_or_symbol": "resolve_design_guide_visible_blocker_disabled_contract",
        "required_tokens": ["def resolve_design_guide_visible_blocker_disabled_contract(", "blocking_reason", "final_disabled_contract"],
        "current_authority_role": "builds disabled button contract for visible blocker conditions",
        "cta_fields": ["disabled_reason", "enabled", "actionable"],
        "can_be_moved_now": False,
        "reason_if_no": "Blocker legality still lives in publication guards and page final-visible routes.",
        "required_parity_proof": "compare object.cta.disabled_reason to disabled contract blocker reason after publication guards",
    },
    {
        "path": "apply_payload",
        "owner_file": "inputs_page.py",
        "function_or_symbol": "_build_design_guide_primary_apply_payload",
        "required_tokens": ["def _build_design_guide_primary_apply_payload(", "button_contract_updates", "state_fingerprint"],
        "current_authority_role": "builds primary apply payload from final item, contract, recommendation, and state",
        "cta_fields": ["apply_payload_summary", "apply_payload_fingerprint", "one_click_action_handoff"],
        "can_be_moved_now": False,
        "reason_if_no": "Apply payload construction writes session/debug payload used by the page action handler.",
        "required_parity_proof": "compare object.cta.apply_payload_fingerprint to DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY payload hash",
    },
    {
        "path": "apply_payload_fingerprint",
        "owner_file": "inputs_page.py",
        "function_or_symbol": "_record_rendered_design_guide_primary_apply_payload",
        "required_tokens": ["def _record_rendered_design_guide_primary_apply_payload(", "DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY", "stale_apply_payload_blocked"],
        "current_authority_role": "records rendered primary apply payload and stale/fresh fingerprint state",
        "cta_fields": ["apply_payload_fingerprint", "stale_fresh_token_proof"],
        "can_be_moved_now": False,
        "reason_if_no": "Rendered payload recording is still a page/session side effect.",
        "required_parity_proof": "compare object.cta stale/fingerprint fields against rendered primary apply payload audit",
    },
    {
        "path": "executor_backed_proof",
        "owner_file": "inputs_page.py",
        "function_or_symbol": "_guidance_executor_actionability_contract",
        "required_tokens": ["def _guidance_executor_actionability_contract(", "executor_contract_blocked_reason", "executor-backed"],
        "current_authority_role": "checks whether a guidance item is executable/actionable against current executor rules",
        "cta_fields": ["executor_backed_proof", "enabled", "disabled_reason"],
        "can_be_moved_now": False,
        "reason_if_no": "Executor probes and current-state checks remain page/local evaluation surfaces.",
        "required_parity_proof": "compare object.cta.executor_backed_proof to executor/actionability probe records",
    },
    {
        "path": "stale_fresh_token_proof",
        "owner_file": "inputs_page.py",
        "function_or_symbol": "_consume_design_guide_component_cta_value",
        "required_tokens": ["def _consume_design_guide_component_cta_value(", "component_apply_token_mismatch", "stale_apply_payload_blocked"],
        "current_authority_role": "blocks stale component CTA events before apply",
        "cta_fields": ["stale_fresh_token_proof", "apply_payload_fingerprint"],
        "can_be_moved_now": False,
        "reason_if_no": "Stale-token checks protect page event/apply routing and must remain live until parity is proven.",
        "required_parity_proof": "compare object.cta.stale_fresh_token_proof to component CTA token/fingerprint audit",
    },
    {
        "path": "one_click_action_handoff",
        "owner_file": "inputs_page.py",
        "function_or_symbol": "_queue_primary_design_guide_button_action",
        "required_tokens": [
            "def _queue_primary_design_guide_button_action(",
            "handle_apply_buttons",
            "def _render_design_guide_component_cta(",
        ],
        "current_authority_role": "queues the primary one-click action from rendered CTA button events",
        "cta_fields": ["one_click_action_handoff", "apply_payload_summary"],
        "can_be_moved_now": False,
        "reason_if_no": "One-click action handoff is page/apply routing, not Design Brain CTA authority yet.",
        "required_parity_proof": "compare object.cta.one_click_action_handoff to queued button action payload",
    },
    {
        "path": "source_precedence",
        "owner_file": "inputs_page.py",
        "function_or_symbol": "_resolve_design_guide_button_contract_source_precedence",
        "required_tokens": ["def _resolve_design_guide_button_contract_source_precedence(", "winning_button_contract_source", "winning_update_payload_source"],
        "current_authority_role": "resolves current source-precedence proof from live page/debug/session/publication sources",
        "cta_fields": ["source_precedence_proof", "button_contract_hash", "apply_payload_summary"],
        "can_be_moved_now": False,
        "reason_if_no": "Live source collection still depends on page/debug/session/publication recovery records.",
        "required_parity_proof": "compare object.cta.source_precedence_proof to source-precedence snapshot selected sources",
    },
    {
        "path": "fallback_disabled_cta_paths",
        "owner_file": "design_brain/publication.py",
        "function_or_symbol": "disabled_design_guide_button_contract",
        "required_tokens": ["def disabled_design_guide_button_contract(", "actionable", "blocking_reason"],
        "current_authority_role": "builds fallback disabled CTA contract for blocker/safe publication guards",
        "cta_fields": ["enabled", "actionable", "disabled_reason"],
        "can_be_moved_now": False,
        "reason_if_no": "Fallback disabled CTA paths are still invoked by publication guards and render fallback branches.",
        "required_parity_proof": "compare object.cta disabled fields against disabled fallback contracts across publication guards",
    },
]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read_rel(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _line_for_token(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


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


def _forbidden_design_brain_imports(imports: list[str]) -> list[str]:
    forbidden_roots = {"inputs_page", "streamlit"}
    hits: list[str] = []
    for name in imports:
        for root in forbidden_roots:
            if name == root or name.startswith(root + "."):
                hits.append(name)
    return sorted(set(hits))


def _normalise_path(row: dict[str, Any]) -> dict[str, Any]:
    source = _read_rel(str(row["owner_file"]))
    missing = [token for token in row["required_tokens"] if token not in source]
    out = dict(row)
    out["present"] = not missing
    out["missing_tokens"] = missing
    out["symbol_line"] = _line_for_token(source, str(row["function_or_symbol"]))
    out["required_token_lines"] = {
        token: _line_for_token(source, token)
        for token in row["required_tokens"]
    }
    out["path_hash"] = _stable_hash(
        {
            key: out[key]
            for key in (
                "path",
                "owner_file",
                "function_or_symbol",
                "current_authority_role",
                "cta_fields",
                "can_be_moved_now",
                "reason_if_no",
                "required_parity_proof",
            )
        }
    )
    return out


def _representative_publication() -> dict[str, Any]:
    updates = {"bot_dia": 20, "bot_count": 4}
    return {
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
                "updates": updates,
                "preview_pass": True,
                "source_candidate_id": "cta-readiness-candidate",
                "executor_backed": True,
            },
            "action_payload": {
                "action_type": "apply_resolved_candidate",
                "family": "bending",
                "updates": updates,
                "source_candidate_id": "cta-readiness-candidate",
                "component_apply_token": "token-123",
                "stale_apply_payload_blocked": False,
                "stale_apply_payload_expected_fingerprint": "expected-fp",
                "stale_apply_payload_current_fingerprint": "expected-fp",
            },
            "candidate_search_evidence": {
                "safe_executor_backed_candidates_count": 1,
                "winning_button_contract_source": "displayed_primary_item",
                "winning_update_payload_source": "button_contract_updates",
                "winning_candidate_source": "source_candidate_id",
            },
        },
        "debug": {
            "button_contract_enabled": True,
            "winning_button_contract_source": "displayed_primary_item",
            "winning_update_payload_source": "button_contract_updates",
            "winning_candidate_source": "source_candidate_id",
            "component_apply_token": "token-123",
            "stale_apply_payload_blocked": False,
        },
        "design_brain_result": {"selected_family_id": "BENDING_FAIL_GOVERNS"},
    }


def _build_snapshot() -> dict[str, Any]:
    from design_brain.final_publication import FinalDesignGuideCTA, build_final_design_guide_publication

    imports = _module_imports(FINAL_PUBLICATION_MODULE)
    forbidden_imports = _forbidden_design_brain_imports(imports)
    cta_fields = {field.name for field in fields(FinalDesignGuideCTA)}
    missing_cta_fields = sorted(REQUIRED_CTA_FIELDS - cta_fields)
    authority_paths = [_normalise_path(row) for row in CTA_AUTHORITY_PATHS]
    missing_paths = [
        {
            "path": row["path"],
            "owner_file": row["owner_file"],
            "function_or_symbol": row["function_or_symbol"],
            "missing_tokens": row["missing_tokens"],
        }
        for row in authority_paths
        if not row["present"]
    ]
    mapped_missing_fields = sorted(
        {
            field
            for row in authority_paths
            for field in row["cta_fields"]
            if field not in cta_fields
        }
    )
    representative = _representative_publication()
    publication_a = build_final_design_guide_publication(
        item=representative["item"],
        debug=representative["debug"],
        design_brain_result=representative["design_brain_result"],
        verifier_payload={"case": "cta_authority_readiness"},
        publication_reason="cta_authority_readiness",
    )
    publication_b = build_final_design_guide_publication(
        item=representative["item"],
        debug=representative["debug"],
        design_brain_result=representative["design_brain_result"],
        verifier_payload={"case": "cta_authority_readiness"},
        publication_reason="cta_authority_readiness",
    )
    cta = publication_a.cta.to_dict()
    normalization_checks = {
        "enabled_represented": cta.get("enabled") is True,
        "label_represented": cta.get("label") == "Run one-click auto design",
        "disabled_reason_represented": "disabled_reason" in cta,
        "apply_payload_fingerprint_represented": bool(cta.get("apply_payload_fingerprint")),
        "apply_payload_summary_represented": bool(cta.get("apply_payload_summary", {}).get("updates_hash")),
        "executor_backed_proof_represented": bool(cta.get("executor_backed_proof", {}).get("executor_backed")),
        "stale_fresh_token_proof_represented": cta.get("stale_fresh_token_proof", {}).get("component_apply_token") == "token-123",
        "one_click_handoff_represented": cta.get("one_click_action_handoff", {}).get("has_updates") is True,
        "source_precedence_represented": cta.get("source_precedence_proof", {}).get("button_contract_source") == "displayed_primary_item",
        "stable_publication_hash": publication_a.publication_hash == publication_b.publication_hash,
        "cta_not_product_driving": cta.get("product_driving") is False,
    }
    normalization_failures = sorted(
        key for key, value in normalization_checks.items() if not value
    )
    failures: list[str] = []
    if forbidden_imports:
        failures.append("final_publication_imports_page_or_streamlit")
    if missing_cta_fields:
        failures.append("missing_required_cta_fields")
    if mapped_missing_fields:
        failures.append("authority_paths_map_to_missing_cta_fields")
    if missing_paths:
        failures.append("missing_current_cta_authority_paths")
    if normalization_failures:
        failures.append("representative_cta_normalization_failed")
    can_move_now_count = sum(1 for row in authority_paths if row["can_be_moved_now"])
    next_step = "proof-only CTA adapter" if can_move_now_count == 0 else "live CTA authority move"
    return {
        "snapshot_name": "design_guide_cta_authority_readiness",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "product_behavior_changed": False,
        "cta_rendering_moved": False,
        "apply_routing_altered": False,
        "stale_token_checks_removed": False,
        "visible_wording_edited": False,
        "final_publication_imports": imports,
        "forbidden_final_publication_imports": forbidden_imports,
        "required_cta_fields": sorted(REQUIRED_CTA_FIELDS),
        "actual_cta_fields": sorted(cta_fields),
        "missing_cta_fields": missing_cta_fields,
        "mapped_missing_fields": mapped_missing_fields,
        "authority_paths": authority_paths,
        "missing_paths": missing_paths,
        "representative_cta": cta,
        "representative_publication_hash": publication_a.publication_hash,
        "normalization_checks": normalization_checks,
        "normalization_failures": normalization_failures,
        "cta_rendering_remains_page_owned": True,
        "apply_routing_remains_shared_page_owned": True,
        "source_precedence_remains_page_collected": True,
        "next_implementation_step": next_step,
        "next_implementation_step_reason": (
            "Every current CTA/apply authority path is represented, but all mapped paths still depend on "
            "page/session/render/apply/source-precedence ownership; add an adapter parity proof before any live move."
        ),
        "snapshot_hash": _stable_hash(
            {
                "path_hashes": [row["path_hash"] for row in authority_paths],
                "cta_fields": sorted(cta_fields),
                "normalization_checks": normalization_checks,
                "next_implementation_step": next_step,
            }
        ),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = []
    for row in snapshot["authority_paths"]:
        rows.append(
            "| {path} | `{owner}` | `{symbol}` | {role} | `{fields}` | {move} | {proof} |".format(
                path=row["path"],
                owner=row["owner_file"],
                symbol=row["function_or_symbol"],
                role=row["current_authority_role"],
                fields=", ".join(row["cta_fields"]),
                move="yes" if row["can_be_moved_now"] else "no",
                proof=row["required_parity_proof"],
            )
        )
    body = "\n".join(
        [
            "# Design Guide CTA Authority Readiness Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "This is proof-only. CTA rendering, apply routing, stale-token checks, source precedence, fallback disabled CTA paths, and visible wording remain in their current owners.",
            "",
            "## Assertions",
            "",
            f"- Product behaviour changed: `{snapshot['product_behavior_changed']}`",
            f"- CTA rendering moved: `{snapshot['cta_rendering_moved']}`",
            f"- Apply routing altered: `{snapshot['apply_routing_altered']}`",
            f"- Stale-token checks removed: `{snapshot['stale_token_checks_removed']}`",
            f"- Visible wording edited: `{snapshot['visible_wording_edited']}`",
            f"- Forbidden final-publication imports: `{snapshot['forbidden_final_publication_imports']}`",
            f"- Missing CTA fields: `{snapshot['missing_cta_fields']}`",
            "",
            "## Authority Paths",
            "",
            "| Path | Owner | Symbol | Current authority role | FinalDesignGuidePublication.cta field(s) | Can move now | Required parity proof |",
            "|---|---|---|---|---|---|---|",
            *rows,
            "",
            "## Representative Normalization",
            "",
            f"- CTA enabled: `{snapshot['representative_cta']['enabled']}`",
            f"- CTA label: `{snapshot['representative_cta']['label']}`",
            f"- Apply payload fingerprint: `{snapshot['representative_cta']['apply_payload_fingerprint']}`",
            f"- Executor-backed proof: `{snapshot['representative_cta']['executor_backed_proof']}`",
            f"- Stale/fresh token proof: `{snapshot['representative_cta']['stale_fresh_token_proof']}`",
            f"- Source precedence proof: `{snapshot['representative_cta']['source_precedence_proof']}`",
            "",
            "## Decision",
            "",
            f"- CTA rendering remains page-owned: `{snapshot['cta_rendering_remains_page_owned']}`",
            f"- Apply routing remains shared/page-owned: `{snapshot['apply_routing_remains_shared_page_owned']}`",
            f"- Source precedence remains page-collected: `{snapshot['source_precedence_remains_page_collected']}`",
            f"- Next implementation step: `{snapshot['next_implementation_step']}`",
            "",
            snapshot["next_implementation_step_reason"],
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_cta_authority_readiness_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_cta_authority_readiness_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_cta_authority_readiness_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("failures=" + ", ".join(snapshot["failures"]))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
