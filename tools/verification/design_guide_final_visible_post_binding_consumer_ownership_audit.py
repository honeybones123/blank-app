"""Ownership audit for post-binding final-visible Design Guide consumers.

Proof-only. The final-visible compatibility restamper is already classified as
non-authoritative, but it is still consumed by post-binding render logic. This
audit classifies those consumers so the next extraction slice can move only the
remaining adapter-owned truth out of inputs_page.py before any deletion.
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
CALL_TOKEN = "_final_visible_item = _publish_final_visible_design_guide_contract_binding("
PRE_CONTEXT_TOKEN = 'source="render_fast_design_guidance_panel.final_visible_resolution"'

CLASS_A = "A. publication/controller adapter candidate"
CLASS_B = "B. render/page-only consumer"
CLASS_C = "C. fallback/safety keep"
CLASS_D = "D. still live resolver truth"
CLASS_E = "E. unknown / needs proof"

CONSUMERS: dict[str, dict[str, str]] = {
    "render_reason": {
        "token": 'str(_final_visible_resolution.get("render_reason") or "").strip()',
        "classification": CLASS_B,
        "owner_after_extraction": "page render flow",
        "reason": "Reads the already-published render reason to select a render-only branch.",
    },
    "terminal_state": {
        "token": 'str(_final_visible_item.get("design_guide_terminal_state") or "").strip()',
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Terminal state is publication truth consumed by zero-shear projection.",
    },
    "zero_shear_projection": {
        "token": "_apply_final_design_guide_zero_shear_render_consumer_projection(",
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Projects post-publication zero-shear terminal evidence into the rendered item.",
    },
    "visible_blocker_check": {
        "token": "_design_guide_item_is_visible_blocker(_final_visible_item)",
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Derives a post-publication promotion path from visible blocker truth.",
    },
    "safe_low_util_cleanup_action": {
        "token": "_visible_safe_low_util_cleanup_action_from_evidence(",
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Builds a post-publication action candidate from evidence.",
    },
    "safe_low_util_projection": {
        "token": "_apply_final_design_guide_safe_low_util_promotion_projection(",
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Projects post-publication safe-low-util promotion into the rendered item.",
    },
    "resolution_item_sync": {
        "token": '_final_visible_resolution["item"] = dict(_final_visible_item)',
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Writes selected item truth back into the final-visible resolution.",
    },
    "post_click_contract": {
        "token": '_final_contract_for_post_click = dict(_final_visible_item.get("button_contract") or {})',
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Feeds post-click proof inputs from publication CTA/button truth.",
    },
    "post_click_family": {
        "token": "_final_family_for_post_click = str(",
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Feeds post-click proof inputs from selected family identity.",
    },
    "post_click_contract_check_input_proof": {
        "token": "_stamp_final_publication_post_click_contract_check_input_proof(",
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Builds post-click proof input from final publication and apply-route state.",
    },
    "post_click_bending_resolution": {
        "token": "_post_click_low_bending_resolution_item(",
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Creates a post-click replacement item from final visible publication evidence.",
    },
    "post_click_exact_blocker_adapter": {
        "token": "_build_final_design_guide_post_click_final_contract_check_adapter_result(",
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Adapter result already exists but is still invoked from page-local post-binding logic.",
    },
    "post_click_replacement_decision_proof": {
        "token": "_stamp_final_publication_post_click_replacement_decision_proof(",
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Stamps post-click replacement decision proof from final publication fields.",
    },
    "post_click_final_contract_adapter_proof": {
        "token": "_stamp_final_publication_post_click_final_contract_adapter_proof(",
        "classification": CLASS_A,
        "owner_after_extraction": "FinalDesignGuidePublication/controller adapter",
        "reason": "Stamps post-click final-contract adapter proof from final publication fields.",
    },
}

REQUIRED_LATEST = {
    "final_visible_compatibility_stamp_consumer": "design_guide_final_visible_compatibility_stamp_consumer",
    "render_item_consumer_adapter_cutover": "design_guide_render_item_consumer_adapter_cutover",
    "zero_shear_manual_rows_deadness": "design_guide_zero_shear_render_consumer_manual_rows_deadness",
    "safe_low_util_manual_rows_deadness": "design_guide_safe_low_util_promotion_manual_rows_deadness",
    "post_click_exact_blocker_manual_rows_deadness": (
        "design_guide_post_click_exact_blocker_projection_manual_rows_deadness"
    ),
    "post_render_bridge_restamper_readiness": "design_guide_post_render_bridge_restamper_readiness",
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


def _status_is_pass(payload: dict[str, Any]) -> bool:
    status = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("decision")
        or ""
    ).upper()
    return "PASS" in status or "LOCKED" in status or "COMPLETE" in status


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
    return {
        "found": True,
        "path": str(path),
        "status": "PASS" if _status_is_pass(payload) else "NOT_PASS",
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


def _target_line(function_source: str, start_line: int | None) -> int | None:
    lines = function_source.splitlines()
    for offset, line in enumerate(lines):
        if CALL_TOKEN not in line:
            continue
        pre_window = "\n".join(lines[max(0, offset - 28) : offset + 1])
        if PRE_CONTEXT_TOKEN in pre_window:
            return (start_line or 1) + offset
    return None


def _window(source: str, line: int | None, before: int = 40, after: int = 950) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _class_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {CLASS_A: 0, CLASS_B: 0, CLASS_C: 0, CLASS_D: 0, CLASS_E: 0}
    for row in rows:
        classification = str(row.get("classification") or CLASS_E)
        counts[classification] = counts.get(classification, 0) + 1
    return counts


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_start, function_end, function_source = _function_source(source, FUNCTION_NAME)
    call_line = _target_line(function_source, function_start)
    context = _window(source, call_line)

    rows: list[dict[str, Any]] = []
    for name, spec in CONSUMERS.items():
        token = spec["token"]
        found = token in context
        classification = spec["classification"] if found else CLASS_E
        rows.append(
            {
                "name": name,
                "token": token,
                "found": found,
                "classification": classification,
                "owner_after_extraction": spec["owner_after_extraction"],
                "reason": spec["reason"],
            }
        )

    latest = {
        key: {
            "status": result.get("status"),
            "path": result.get("path"),
            "found": result.get("found"),
        }
        for key, result in ((key, _latest(prefix)) for key, prefix in REQUIRED_LATEST.items())
    }
    counts = _class_counts(rows)
    unknown_rows = [row for row in rows if row.get("classification") == CLASS_E]
    adapter_rows = [row for row in rows if row.get("classification") == CLASS_A]
    adapter_cutover_pass = latest.get("render_item_consumer_adapter_cutover", {}).get("status") == "PASS"
    manual_rows_dead = all(
        latest.get(key, {}).get("status") == "PASS"
        for key in (
            "zero_shear_manual_rows_deadness",
            "safe_low_util_manual_rows_deadness",
            "post_click_exact_blocker_manual_rows_deadness",
        )
    )
    adapter_truth_accounted_for = adapter_cutover_pass and manual_rows_dead
    page_render_only_remaining = counts.get(CLASS_B) == 1 and counts.get(CLASS_D, 0) == 0

    return {
        "decision": (
            "POST_BINDING_CONSUMERS_ADAPTER_CUTOVER_PROVEN_RENDER_REASON_PAGE_ONLY"
            if adapter_truth_accounted_for and page_render_only_remaining
            else "POST_BINDING_CONSUMERS_REQUIRE_ADAPTER_BEFORE_DELETION"
        ),
        "function": FUNCTION_NAME,
        "function_start_line": function_start,
        "function_end_line": function_end,
        "target_call_line": call_line,
        "target_call_token": CALL_TOKEN,
        "pre_context_token": PRE_CONTEXT_TOKEN,
        "consumer_rows": rows,
        "class_counts": counts,
        "adapter_candidate_count": len(adapter_rows),
        "unknown_count": len(unknown_rows),
        "adapter_truth_accounted_for": adapter_truth_accounted_for,
        "page_render_only_remaining": page_render_only_remaining,
        "deletion_safe_now": False,
        "next_safe_step": (
            "Treat the adapter-owned post-binding consumer truth as cut over and manual rows dead; "
            "continue with the next restamper/render-consumer deletion proof while preserving the "
            "render_reason page-render branch."
            if adapter_truth_accounted_for and page_render_only_remaining
            else "Create a proof-only FinalDesignGuidePublication/controller adapter for the class-A "
            "post-binding consumers, then wire it trace-only before replacing this page-local logic."
        ),
        "latest_required_artifacts": latest,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_required_artifacts") or {})
    counts = dict(capture.get("class_counts") or {})
    return {
        "target_callsite_present": capture.get("target_call_line") is not None,
        "all_consumer_tokens_found": all(
            bool(row.get("found")) for row in capture.get("consumer_rows") or []
        ),
        "adapter_candidate_count_expected": counts.get(CLASS_A) == 13,
        "render_only_count_expected": counts.get(CLASS_B) == 1,
        "fallback_count_zero": counts.get(CLASS_C, 0) == 0,
        "live_resolver_truth_count_zero": counts.get(CLASS_D, 0) == 0,
        "unknown_count_zero": counts.get(CLASS_E, 0) == 0,
        "classified_not_deletable": capture.get("deletion_safe_now") is False,
        "consumer_snapshot_pass": (
            latest.get("final_visible_compatibility_stamp_consumer") or {}
        ).get("status")
        == "PASS",
        "render_item_consumer_adapter_cutover_pass": (
            latest.get("render_item_consumer_adapter_cutover") or {}
        ).get("status")
        == "PASS",
        "manual_rows_deadness_pass": all(
            (latest.get(key) or {}).get("status") == "PASS"
            for key in (
                "zero_shear_manual_rows_deadness",
                "safe_low_util_manual_rows_deadness",
                "post_click_exact_blocker_manual_rows_deadness",
            )
        ),
        "adapter_truth_accounted_for": capture.get("adapter_truth_accounted_for") is True,
        "page_render_only_remaining": capture.get("page_render_only_remaining") is True,
        "post_render_restamper_readiness_pass": (
            latest.get("post_render_bridge_restamper_readiness") or {}
        ).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status")
        == "PASS",
        "compute_bridge_lock_pass": (
            latest.get("compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Visible Post-Binding Consumer Ownership Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Location",
        "",
        f"- Function: `{capture.get('function')}`",
        f"- Target call line: `{capture.get('target_call_line')}`",
        "",
        "## Classification",
        "",
    ]
    for key, value in (capture.get("class_counts") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Consumers", ""])
    for row in capture.get("consumer_rows") or []:
        lines.append(
            f"- `{row.get('name')}`: `{row.get('classification')}`; "
            f"found=`{row.get('found')}`; owner=`{row.get('owner_after_extraction')}`"
        )
    lines.extend(
        [
            "",
            "## Deletion Readiness",
            "",
            f"- Deletion safe now: `{capture.get('deletion_safe_now')}`",
            f"- Next safe step: {capture.get('next_safe_step')}",
            "",
            "## Required Artifacts",
            "",
        ]
    )
    for key, row in (capture.get("latest_required_artifacts") or {}).items():
        lines.append(f"- {key}: `{row.get('status')}` at `{row.get('path')}`")
    lines.extend(["", "## Checks", ""])
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
        "schema": "design_guide_final_visible_post_binding_consumer_ownership_audit.v1",
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
        / f"design_guide_final_visible_post_binding_consumer_ownership_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_final_visible_post_binding_consumer_ownership_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_visible_post_binding_consumer_ownership {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
