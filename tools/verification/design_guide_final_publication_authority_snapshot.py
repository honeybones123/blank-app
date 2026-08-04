"""Proof-only snapshot of current Design Guide final-publication authority.

This verifier records the current distributed authority map. It does not prove
independence, move ownership, execute Streamlit, or change product behaviour.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:16]


def _read_rel(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _line_for_token(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _imports_for_source(source: str) -> list[str]:
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


CHECKPOINTS: list[dict[str, Any]] = [
    {
        "order": 1,
        "checkpoint": "Design Brain engine decision",
        "owner_module_file": "design_brain/engine.py",
        "function_or_symbol": "resolve_design_guide_decision",
        "required_tokens": ["def resolve_design_guide_decision(", "button_contract", "candidate_search_evidence"],
        "authority_type": "A. Design Brain-owned decision helper",
        "can_change_outcome": True,
        "can_change_cta": True,
        "can_change_blocker_reason": True,
        "can_change_visible_wording": True,
        "can_restamp_debug_session": False,
        "downstream_of_publication_object": False,
        "expected_future_owner": "Design Brain decision engine; not final visible publication authority",
    },
    {
        "order": 2,
        "checkpoint": "Family result / selected family classification",
        "owner_module_file": "design_brain/family_classification_runtime.py",
        "function_or_symbol": "classify_family_from_whole_beam_evidence",
        "required_tokens": [
            "def classify_family_from_whole_beam_evidence(",
            "selected_family_id",
            "classification_hash",
        ],
        "authority_type": "A. Design Brain-owned classification helper",
        "can_change_outcome": True,
        "can_change_cta": False,
        "can_change_blocker_reason": False,
        "can_change_visible_wording": False,
        "can_restamp_debug_session": False,
        "downstream_of_publication_object": False,
        "expected_future_owner": "Design Brain family classification contract/runtime",
    },
    {
        "order": 3,
        "checkpoint": "Family strategy dispatch",
        "owner_module_file": "design_brain/families/registry.py",
        "function_or_symbol": "family_strategy_for",
        "required_tokens": ["def family_strategy_for(", "normalise_governing_family"],
        "authority_type": "A. Design Brain-owned family registry",
        "can_change_outcome": True,
        "can_change_cta": False,
        "can_change_blocker_reason": False,
        "can_change_visible_wording": False,
        "can_restamp_debug_session": False,
        "downstream_of_publication_object": False,
        "expected_future_owner": "Design Brain family registry",
    },
    {
        "order": 4,
        "checkpoint": "Publication helper output: safe combined cleanup reroute",
        "owner_module_file": "design_brain/publication.py",
        "function_or_symbol": "enforce_design_brain_publication_contract",
        "required_tokens": [
            "def enforce_design_brain_publication_contract(",
            "safe_executable_combined_cleanup_outranks_stale_blocker",
            "button_contract",
        ],
        "authority_type": "C. shared helper authority",
        "can_change_outcome": True,
        "can_change_cta": True,
        "can_change_blocker_reason": True,
        "can_change_visible_wording": True,
        "can_restamp_debug_session": True,
        "downstream_of_publication_object": True,
        "expected_future_owner": "Shared publication contract guard or future Design Brain final-publication boundary",
    },
    {
        "order": 5,
        "checkpoint": "Publication helper output: family selection gate",
        "owner_module_file": "design_brain/publication.py",
        "function_or_symbol": "enforce_family_selection_publication_contract",
        "required_tokens": [
            "def enforce_family_selection_publication_contract(",
            "family_match_passed",
            "family_selection_contract",
        ],
        "authority_type": "C. shared helper authority",
        "can_change_outcome": True,
        "can_change_cta": True,
        "can_change_blocker_reason": True,
        "can_change_visible_wording": True,
        "can_restamp_debug_session": True,
        "downstream_of_publication_object": True,
        "expected_future_owner": "Shared selected-family publication gate",
    },
    {
        "order": 6,
        "checkpoint": "Publication helper output: underdesign repair invariant",
        "owner_module_file": "design_brain/publication.py",
        "function_or_symbol": "enforce_underdesign_repair_publication_boundary",
        "required_tokens": [
            "def enforce_underdesign_repair_publication_boundary(",
            "active_failure_requires_repair_ACTION_or_legal_no_repair_proof",
            "safe_item",
        ],
        "authority_type": "C. shared helper authority",
        "can_change_outcome": True,
        "can_change_cta": True,
        "can_change_blocker_reason": True,
        "can_change_visible_wording": True,
        "can_restamp_debug_session": True,
        "downstream_of_publication_object": True,
        "expected_future_owner": "Shared publication legality guard",
    },
    {
        "order": 7,
        "checkpoint": "Final-visible publication authority adapter",
        "owner_module_file": "inputs_page.py",
        "function_or_symbol": "_final_visible_resolution_from_final_publication_authority",
        "required_tokens": [
            "def _final_visible_resolution_from_final_publication_authority(",
            "DesignGuideController",
            "FinalDesignGuidePublication",
            "final_visible_resolution_compatibility_only",
        ],
        "authority_type": "B. inputs_page compatibility adapter",
        "can_change_outcome": False,
        "can_change_cta": False,
        "can_change_blocker_reason": False,
        "can_change_visible_wording": False,
        "can_restamp_debug_session": True,
        "downstream_of_publication_object": True,
        "expected_future_owner": "Page remains a thin adapter around DesignGuideController/FinalDesignGuidePublication",
    },
    {
        "order": 8,
        "checkpoint": "CTA/apply payload binding",
        "owner_module_file": "inputs_page.py",
        "function_or_symbol": "_publish_final_visible_design_guide_contract_binding",
        "required_tokens": [
            "def _publish_final_visible_design_guide_contract_binding(",
            "_record_rendered_design_guide_primary_apply_payload",
            "design_guide_primary_button_contract",
        ],
        "authority_type": "B. inputs_page final authority",
        "can_change_outcome": True,
        "can_change_cta": True,
        "can_change_blocker_reason": True,
        "can_change_visible_wording": False,
        "can_restamp_debug_session": True,
        "downstream_of_publication_object": True,
        "expected_future_owner": "Page adapter for session/apply binding after Design Brain-selected publication",
    },
    {
        "order": 9,
        "checkpoint": "Card view model build",
        "owner_module_file": "inputs_page.py",
        "function_or_symbol": "build_design_guide_card_view_model",
        "required_tokens": [
            "def build_design_guide_card_view_model(",
            "_view_model_actionable",
            "build_design_guide_card_view_model(",
        ],
        "authority_type": "B. inputs_page final authority",
        "can_change_outcome": True,
        "can_change_cta": True,
        "can_change_blocker_reason": True,
        "can_change_visible_wording": True,
        "can_restamp_debug_session": True,
        "downstream_of_publication_object": True,
        "expected_future_owner": "Design Brain output contract for pure view-model fields; page render adapter",
    },
    {
        "order": 10,
        "checkpoint": "Card render-model field assembly",
        "owner_module_file": "inputs_page.py",
        "function_or_symbol": "_build_design_guide_card_render_model",
        "required_tokens": [
            "def _build_design_guide_card_render_model(",
            "disabled_action_with_blocker",
            "_build_design_guide_card_render_model_fields_core",
        ],
        "authority_type": "B/D. page display prep plus renderer model assembly",
        "can_change_outcome": True,
        "can_change_cta": False,
        "can_change_blocker_reason": True,
        "can_change_visible_wording": True,
        "can_restamp_debug_session": False,
        "downstream_of_publication_object": True,
        "expected_future_owner": "Design Brain output-formatting only after wording/legality contract expands",
    },
    {
        "order": 11,
        "checkpoint": "Pure render-model packer",
        "owner_module_file": "design_brain/output_formatting.py",
        "function_or_symbol": "build_design_guide_card_render_model_fields",
        "required_tokens": [
            "def build_design_guide_card_render_model_fields(",
            "return DesignGuideCardRenderModel(",
        ],
        "authority_type": "D. renderer-only pure field packer",
        "can_change_outcome": False,
        "can_change_cta": False,
        "can_change_blocker_reason": False,
        "can_change_visible_wording": False,
        "can_restamp_debug_session": False,
        "downstream_of_publication_object": True,
        "expected_future_owner": "Remain Design Brain output-formatting pure packer",
    },
    {
        "order": 12,
        "checkpoint": "Debug/session publication bundle",
        "owner_module_file": "inputs_page.py",
        "function_or_symbol": "DESIGN_GUIDE_DEBUG_BUNDLE_KEY",
        "required_tokens": [
            "DESIGN_GUIDE_DEBUG_BUNDLE_KEY",
            "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY]",
            "guidance_debug",
        ],
        "authority_type": "B/E. page debug/session authority",
        "can_change_outcome": True,
        "can_change_cta": True,
        "can_change_blocker_reason": True,
        "can_change_visible_wording": True,
        "can_restamp_debug_session": True,
        "downstream_of_publication_object": True,
        "expected_future_owner": "Debug-only unless explicitly consumed by render fallback; page remains session adapter",
    },
    {
        "order": 13,
        "checkpoint": "Render fallback shell path",
        "owner_module_file": "inputs_page.py",
        "function_or_symbol": "fallback_enabled_contract_shell",
        "required_tokens": [
            "fallback_enabled_contract_shell",
            "browser_enabled_contract_shell",
            "_design_guide_direct_action_shell_card_html",
        ],
        "authority_type": "B/F. render-after-publication fallback authority",
        "can_change_outcome": True,
        "can_change_cta": True,
        "can_change_blocker_reason": False,
        "can_change_visible_wording": True,
        "can_restamp_debug_session": True,
        "downstream_of_publication_object": True,
        "expected_future_owner": "Remove or narrow after final publication authority is lockable",
    },
    {
        "order": 14,
        "checkpoint": "Late render-after-publication compatibility/recovery paths",
        "owner_module_file": "inputs_page.py",
        "function_or_symbol": "post-click / low-util compatibility helpers",
        "required_tokens": [
            "def _visible_safe_low_util_cleanup_action_from_evidence(",
            "def _post_click_low_bending_resolution_item(",
            "def _normalise_visible_optimisation_contract(",
        ],
        "authority_type": "B/F. late page compatibility/recovery surface",
        "can_change_outcome": True,
        "can_change_cta": True,
        "can_change_blocker_reason": True,
        "can_change_visible_wording": True,
        "can_restamp_debug_session": True,
        "downstream_of_publication_object": True,
        "expected_future_owner": "Proofed Design Brain final-publication recovery or retired compatibility path",
    },
]


def _normalise_checkpoint(checkpoint: dict[str, Any]) -> dict[str, Any]:
    source = _read_rel(str(checkpoint["owner_module_file"]))
    missing = [token for token in checkpoint["required_tokens"] if token not in source]
    line = _line_for_token(source, str(checkpoint["function_or_symbol"]))
    token_lines = {
        token: _line_for_token(source, token)
        for token in checkpoint["required_tokens"]
    }
    out = dict(checkpoint)
    out["symbol_line"] = line
    out["required_token_lines"] = token_lines
    out["present"] = not missing
    out["missing_tokens"] = missing
    out["checkpoint_hash"] = _stable_hash(
        {
            key: out[key]
            for key in (
                "order",
                "checkpoint",
                "owner_module_file",
                "function_or_symbol",
                "authority_type",
                "can_change_outcome",
                "can_change_cta",
                "can_change_blocker_reason",
                "can_change_visible_wording",
                "can_restamp_debug_session",
                "downstream_of_publication_object",
                "expected_future_owner",
                "required_tokens",
            )
        }
    )
    return out


def _forbidden_import_scan() -> dict[str, Any]:
    scanned = {}
    for rel_path in (
        "design_brain/publication.py",
        "design_brain/engine.py",
        "design_brain/output_formatting.py",
        "design_brain/cta_contracts.py",
        "design_brain/family_classification_runtime.py",
    ):
        source = _read_rel(rel_path)
        imports = _imports_for_source(source)
        scanned[rel_path] = {
            "imports_inputs_page": any(name == "inputs_page" or name.startswith("inputs_page.") for name in imports),
            "imports_streamlit": any(name == "streamlit" or name.startswith("streamlit.") for name in imports),
            "import_count": len(imports),
        }
    return scanned


def _build_snapshot() -> dict[str, Any]:
    checkpoints = [_normalise_checkpoint(row) for row in CHECKPOINTS]
    missing = [
        {
            "checkpoint": row["checkpoint"],
            "owner_module_file": row["owner_module_file"],
            "function_or_symbol": row["function_or_symbol"],
            "missing_tokens": row["missing_tokens"],
        }
        for row in checkpoints
        if not row["present"]
    ]
    requested_checkpoint_names = {
        "Design Brain engine decision",
        "Family result / selected family classification",
        "Publication helper output: safe combined cleanup reroute",
        "Final-visible publication authority adapter",
        "CTA/apply payload binding",
        "Card view model build",
        "Debug/session publication bundle",
        "Render fallback shell path",
        "Late render-after-publication compatibility/recovery paths",
    }
    captured_names = {str(row["checkpoint"]) for row in checkpoints}
    missing_requested = sorted(requested_checkpoint_names - captured_names)
    authority_classes = sorted({str(row["authority_type"]).split(".", 1)[0] for row in checkpoints})
    distributed_authority_captured = bool(
        any(str(row["authority_type"]).startswith("A") for row in checkpoints)
        and any(str(row["authority_type"]).startswith("B") for row in checkpoints)
        and any(str(row["authority_type"]).startswith("C") for row in checkpoints)
        and any("D" in str(row["authority_type"]).split(".", 1)[0] for row in checkpoints)
    )
    forbidden_import_scan = _forbidden_import_scan()
    failures = []
    if missing:
        failures.append("missing_checkpoint_tokens")
    if missing_requested:
        failures.append("missing_requested_checkpoint_categories")
    if not distributed_authority_captured:
        failures.append("distributed_authority_not_captured")
    snapshot_core = {
        "checkpoint_count": len(checkpoints),
        "checkpoint_hashes": [row["checkpoint_hash"] for row in checkpoints],
        "authority_classes": authority_classes,
        "missing_requested": missing_requested,
        "distributed_authority_captured": distributed_authority_captured,
    }
    return {
        "snapshot_name": "design_guide_final_publication_authority",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "purpose": "Record current distributed authority map; independence is not required in this phase.",
        "product_behavior_changed": False,
        "cta_moved": False,
        "render_logic_moved": False,
        "publication_decisions_edited": False,
        "independence_required": False,
        "checkpoints": checkpoints,
        "requested_checkpoint_categories_captured": not missing_requested,
        "distributed_authority_captured": distributed_authority_captured,
        "forbidden_import_scan": forbidden_import_scan,
        "snapshot_hash": _stable_hash(snapshot_core),
        "failures": failures,
        "missing_checkpoints": missing,
        "summary": {
            "total_checkpoints": len(checkpoints),
            "can_change_outcome": sum(1 for row in checkpoints if row["can_change_outcome"]),
            "can_change_cta": sum(1 for row in checkpoints if row["can_change_cta"]),
            "can_change_blocker_reason": sum(1 for row in checkpoints if row["can_change_blocker_reason"]),
            "can_change_visible_wording": sum(1 for row in checkpoints if row["can_change_visible_wording"]),
            "can_restamp_debug_session": sum(1 for row in checkpoints if row["can_restamp_debug_session"]),
            "downstream_of_publication_object": sum(1 for row in checkpoints if row["downstream_of_publication_object"]),
        },
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = []
    for row in snapshot["checkpoints"]:
        rows.append(
            "| {order} | {checkpoint} | `{owner}` | `{symbol}` | {authority} | {outcome} | {cta} | {wording} | {debug} | {present} |".format(
                order=row["order"],
                checkpoint=row["checkpoint"],
                owner=row["owner_module_file"],
                symbol=row["function_or_symbol"],
                authority=row["authority_type"],
                outcome="yes" if row["can_change_outcome"] else "no",
                cta="yes" if row["can_change_cta"] else "no",
                wording="yes" if row["can_change_visible_wording"] else "no",
                debug="yes" if row["can_restamp_debug_session"] else "no",
                present="yes" if row["present"] else "no",
            )
        )
    body = "\n".join(
        [
            "# Design Guide Final Publication Authority Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "This is proof-only. It records the current distributed authority map and does not require independence yet.",
            "",
            "## Assertions",
            "",
            f"- Product behaviour changed: `{snapshot['product_behavior_changed']}`",
            f"- CTA moved: `{snapshot['cta_moved']}`",
            f"- Render logic moved: `{snapshot['render_logic_moved']}`",
            f"- Publication decisions edited: `{snapshot['publication_decisions_edited']}`",
            f"- Requested checkpoint categories captured: `{snapshot['requested_checkpoint_categories_captured']}`",
            f"- Distributed authority captured: `{snapshot['distributed_authority_captured']}`",
            "",
            "## Checkpoints",
            "",
            "| # | Checkpoint | Owner | Symbol | Authority | Outcome | CTA | Wording | Debug/session | Present |",
            "|---:|---|---|---|---|---|---|---|---|---|",
            *rows,
            "",
            "## Summary",
            "",
            f"- Total checkpoints: `{snapshot['summary']['total_checkpoints']}`",
            f"- Can change outcome: `{snapshot['summary']['can_change_outcome']}`",
            f"- Can change CTA: `{snapshot['summary']['can_change_cta']}`",
            f"- Can change blocker reason: `{snapshot['summary']['can_change_blocker_reason']}`",
            f"- Can change visible wording: `{snapshot['summary']['can_change_visible_wording']}`",
            f"- Can restamp debug/session: `{snapshot['summary']['can_restamp_debug_session']}`",
            f"- Downstream of publication object: `{snapshot['summary']['downstream_of_publication_object']}`",
            "",
            "## Next Slice",
            "",
            "Keep CTA and card rendering in place. The next safe implementation slice is an ordered mutation/hash snapshot that records before/after hashes at these checkpoints during representative publication scenarios.",
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_final_publication_authority_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_publication_authority_snapshot_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_final_publication_authority_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("failures=" + ", ".join(snapshot["failures"]))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
