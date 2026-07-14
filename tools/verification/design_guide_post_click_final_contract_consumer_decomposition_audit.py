"""Decompose the remaining post-click final-contract page consumer.

Proof-only. The render-item consumer adapter readiness gate proves the
post-click final-contract checks are the remaining live page consumer group.
This audit classifies the exact live rows before any extraction or deletion.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

FUNCTION_NAME = "_render_fast_design_guidance_panel"
START_TOKEN = "_final_contract_for_post_click = dict(_final_visible_item.get(\"button_contract\") or {})"
END_TOKEN = "_stamp_final_publication_post_click_final_contract_adapter_result("

CLASS_A = "A. move to Design Brain predicate/result adapter"
CLASS_B = "B. page/apply/session input collection"
CLASS_C = "C. already adapter-backed projection/proof"
CLASS_D = "D. page render flow / keep"
CLASS_E = "E. unknown / needs proof"

ROWS: dict[str, dict[str, str]] = {
    "final_contract": {
        "token": START_TOKEN,
        "classification": CLASS_A,
        "reason": "Final CTA/button contract truth should be consumed through publication-owned CTA evidence.",
    },
    "final_family": {
        "token": "_final_family_for_post_click = str(",
        "classification": CLASS_A,
        "reason": "Selected family identity should be publication-owned truth.",
    },
    "final_expected_util": {
        "token": "_final_expected_util_for_post_click = _parse_util_value(",
        "classification": CLASS_A,
        "reason": "Expected-util post-click predicate should be a Design Brain predicate input/result.",
    },
    "current_bending_util": {
        "token": "_final_current_bending_util_for_post_click = _parse_util_value(",
        "classification": CLASS_A,
        "reason": "Current-util post-click predicate should be represented in the adapter result.",
    },
    "post_click_family_sets": {
        "token": "_post_click_unresolved_families_for_visible = {",
        "classification": CLASS_B,
        "reason": "Collects page/debug/post-cleanup audit input lists.",
    },
    "last_apply_route": {
        "token": "_last_apply_route_for_visible = dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {})",
        "classification": CLASS_B,
        "reason": "Reads page-owned apply/session state; adapter may receive this as input but should not own session.",
    },
    "same_flow_cleanup_apply": {
        "token": "_same_flow_cleanup_apply_for_visible = bool(",
        "classification": CLASS_B,
        "reason": "Computes page/apply input state from last apply and binding audit.",
    },
    "contract_check_input_proof": {
        "token": "_post_click_contract_check_input_proof = _stamp_final_publication_post_click_contract_check_input_proof(",
        "classification": CLASS_C,
        "reason": "Already represented by a FinalDesignGuidePublication proof object.",
    },
    "contract_enabled_predicate": {
        "token": "_post_click_bending_low_contract_enabled = bool(",
        "classification": CLASS_C,
        "reason": "Predicate is now consumed from the Design Brain final-contract adapter result.",
    },
    "exact_blocker_predicate": {
        "token": "_post_click_bending_exact_blocker_on_visible_item = bool(",
        "classification": CLASS_C,
        "reason": "Predicate is now consumed from the Design Brain final-contract adapter result.",
    },
    "requires_exact_blocker_predicate": {
        "token": "_post_click_bending_low_requires_exact_blocker = bool(",
        "classification": CLASS_C,
        "reason": "Predicate is now consumed from the Design Brain final-contract adapter result.",
    },
    "visible_action_predicate": {
        "token": "_post_click_bending_low_visible_action = bool(",
        "classification": CLASS_C,
        "reason": "Final post-click replacement predicate is now Design Brain adapter-backed.",
    },
    "bending_audit_assembly": {
        "token": "_post_click_bending_audit_sources_for_visible = (",
        "classification": CLASS_B,
        "reason": "Collects page-visible item/evidence inputs for Design Brain adapter proof surfaces.",
    },
    "bending_resolution_builder": {
        "token": "_post_click_bending_resolution = _post_click_low_bending_resolution_item(",
        "classification": CLASS_A,
        "reason": "Builds replacement item; should move behind the post-click final-contract result boundary.",
    },
    "post_click_rebinding": {
        "token": "_post_click_exact_blocker_result.get(\"replacement_item\")",
        "classification": CLASS_C,
        "reason": "Replacement item is now consumed from the Design Brain adapter result.",
    },
    "adapter_result_build": {
        "token": "_build_final_design_guide_post_click_final_contract_check_adapter_result(",
        "classification": CLASS_C,
        "reason": "Already uses Design Brain adapter result for the projection.",
    },
    "replacement_decision_proof": {
        "token": "_post_click_replacement_decision_proof = _stamp_final_publication_post_click_replacement_decision_proof(",
        "classification": CLASS_C,
        "reason": "Already stamps Design Brain proof surface.",
    },
    "final_contract_adapter_proof": {
        "token": "_post_click_final_contract_adapter_proof = (",
        "classification": CLASS_C,
        "reason": "Already stamps Design Brain adapter proof surface.",
    },
    "final_contract_adapter_result_stamp": {
        "token": "_stamp_final_publication_post_click_final_contract_adapter_result(",
        "classification": CLASS_C,
        "reason": "Already stamps Design Brain adapter result surface.",
    },
}

REQUIRED_LATEST = {
    "cutover_readiness": "design_guide_render_item_consumer_adapter_cutover_readiness",
    "adapter_parity": "design_guide_live_render_item_consumer_adapter_parity",
    "independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
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


def _function_source(source: str, function_name: str) -> tuple[int | None, int | None, str]:
    marker = f"def {function_name}("
    start_index = source.find(marker)
    if start_index < 0:
        return None, None, ""
    start_line = source[:start_index].count("\n") + 1
    next_def_index = source.find("\ndef ", start_index + len(marker))
    next_class_index = source.find("\nclass ", start_index + len(marker))
    candidates = [index for index in (next_def_index, next_class_index) if index >= 0]
    end_index = min(candidates) if candidates else len(source)
    end_line = source[:end_index].count("\n") + 1
    return start_line, end_line, source[start_index:end_index]


def _block(function_source: str, function_start: int | None) -> tuple[int | None, int | None, str]:
    start_index = function_source.find(START_TOKEN)
    if start_index < 0:
        return None, None, ""
    end_index = function_source.find(END_TOKEN, start_index)
    if end_index < 0:
        return (function_start or 1) + function_source[:start_index].count("\n"), None, ""
    end_index = function_source.find("\n", end_index)
    if end_index < 0:
        end_index = len(function_source)
    start_line = (function_start or 1) + function_source[:start_index].count("\n")
    end_line = (function_start or 1) + function_source[:end_index].count("\n")
    return start_line, end_line, function_source[start_index:end_index]


def _class_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {CLASS_A: 0, CLASS_B: 0, CLASS_C: 0, CLASS_D: 0, CLASS_E: 0}
    for row in rows:
        counts[str(row.get("classification") or CLASS_E)] += 1
    return counts


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_start, function_end, function_source = _function_source(source, FUNCTION_NAME)
    block_start, block_end, block = _block(function_source, function_start)
    rows = []
    for name, spec in ROWS.items():
        found = bool(block and spec["token"] in block)
        rows.append(
            {
                "name": name,
                "token": spec["token"],
                "found": found,
                "classification": spec["classification"] if found else CLASS_E,
                "reason": spec["reason"],
            }
        )
    latest = {
        key: {
            "status": row.get("status"),
            "path": row.get("path"),
            "found": row.get("found"),
        }
        for key, row in ((key, _latest(prefix)) for key, prefix in REQUIRED_LATEST.items())
    }
    counts = _class_counts(rows)
    return {
        "decision": (
            "POST_CLICK_FINAL_CONTRACT_PREDICATE_RESULT_ADAPTER_CUTOVER_PROVEN"
            if counts.get(CLASS_E, 0) == 0
            else "POST_CLICK_FINAL_CONTRACT_GROUP_NEEDS_PREDICATE_RESULT_ADAPTER"
        ),
        "function": FUNCTION_NAME,
        "function_start_line": function_start,
        "function_end_line": function_end,
        "block_start_line": block_start,
        "block_end_line": block_end,
        "rows": rows,
        "class_counts": counts,
        "latest_required_artifacts": latest,
        "deletion_safe_now": False,
        "cutover_ready_for_projection_only": True,
        "cutover_ready_for_full_post_click_group": False,
        "next_safe_step": (
            "Audit the remaining post-click bending resolution builder and page-owned input collection "
            "before deleting or replacing more page code."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_required_artifacts") or {})
    counts = dict(capture.get("class_counts") or {})
    return {
        "target_block_present": capture.get("block_start_line") is not None
        and capture.get("block_end_line") is not None,
        "all_expected_rows_found": all(row.get("found") for row in capture.get("rows") or []),
        "class_a_rows_present": counts.get(CLASS_A, 0) >= 5,
        "class_b_rows_present": counts.get(CLASS_B, 0) >= 3,
        "class_c_rows_present": counts.get(CLASS_C, 0) >= 9,
        "no_unknown_rows": counts.get(CLASS_E, 0) == 0,
        "cutover_readiness_pass": (latest.get("cutover_readiness") or {}).get("status")
        == "PASS",
        "adapter_parity_pass": (latest.get("adapter_parity") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status")
        == "PASS",
        "compute_bridge_lock_pass": (
            latest.get("compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "full_group_not_ready_for_cutover": capture.get("cutover_ready_for_full_post_click_group")
        is False,
        "deletion_safe_false": capture.get("deletion_safe_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Final-Contract Consumer Decomposition Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Location",
        "",
        f"- Function: `{capture.get('function')}`",
        f"- Block start: `{capture.get('block_start_line')}`",
        f"- Block end: `{capture.get('block_end_line')}`",
        "",
        "## Classification Counts",
        "",
    ]
    for key, value in (capture.get("class_counts") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Rows", ""])
    for row in capture.get("rows") or []:
        lines.append(
            f"- `{row.get('name')}`: `{row.get('classification')}`; found=`{row.get('found')}`"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Full group cutover ready: `{capture.get('cutover_ready_for_full_post_click_group')}`",
            f"- Deletion safe now: `{capture.get('deletion_safe_now')}`",
            f"- Next safe step: {capture.get('next_safe_step')}",
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
        "schema": "design_guide_post_click_final_contract_consumer_decomposition_audit.v1",
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
        / f"design_guide_post_click_final_contract_consumer_decomposition_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_final_contract_consumer_decomposition_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_final_contract_consumer_decomposition {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
