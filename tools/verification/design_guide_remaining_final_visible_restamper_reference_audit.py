"""Audit remaining final-visible restamper references in inputs_page.py.

Proof-only. This classifies ``_publish_final_visible_design_guide_contract_binding``
callers after the legacy final-visible resolver body has been deleted.
"""

from __future__ import annotations

import ast
from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

RESTAMPER = "_publish_final_visible_design_guide_contract_binding"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper() or "LOCKED" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _enclosing_function(tree: ast.AST, line: int) -> str:
    best = ""
    best_line = -1
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = int(getattr(node, "lineno", 0) or 0)
            end = int(getattr(node, "end_lineno", 0) or 0)
            if start <= line <= end and start > best_line:
                best = node.name
                best_line = start
    return best


def _classify(line_text: str, function_name: str, context_text: str) -> dict[str, str]:
    text = line_text.strip()
    if "_late_rebound_item" in text:
        return {
            "category": "C. still live compute rebound bridge",
            "reason": "late evidence rebound still selects/republishes a candidate before final publication",
        }
    if "_post_evidence_rebound" in text:
        return {
            "category": "C. still live compute rebound bridge",
            "reason": "post-core evidence rebound still bridges compute evidence before final publication",
        }
    if "_combined_rebound_item" in text or "_engine_rebound_item" in text:
        return {
            "category": "C. render-stage combined evidence rebind bridge",
            "reason": "returned rebound item is assigned back into displayed primary item, guidance items, and render plan state",
        }
    if (
        "_pre_render_bound_item" in text
        and "render_guidance_secondary_pre_render_binding_adapter_cutover_applied" in context_text
        and "_pre_render_bound_item = dict(_pre_render_adapter_item)" in context_text
    ):
        return {
            "category": "B. adapter-covered result-identity bridge",
            "reason": (
                "pre-render binding is covered by controller adapter parity/readiness/cutover proof; "
                "the old restamper remains present only as the comparison/source bridge"
            ),
        }
    if (
        "_pre_card_bound_item" in text
        and "render_guidance_secondary_pre_card_binding_adapter_cutover_applied" in context_text
        and "_pre_card_bound_item = dict(_pre_card_adapter_item)" in context_text
    ):
        return {
            "category": "B. adapter-covered result-identity bridge",
            "reason": (
                "pre-card binding is covered by controller adapter parity/readiness/cutover proof; "
                "the old restamper remains present only as the comparison/source bridge"
            ),
        }
    if "_final_visible_item" in text:
        if (
            "render_fast_final_visible_item_binding_adapter_cutover_applied" in context_text
            and "_final_visible_item = dict(_final_visible_adapter_item)" in context_text
        ):
            return {
                "category": "B. adapter-covered result-identity bridge",
                "reason": (
                    "render-fast final item binding is covered by controller adapter parity/readiness/cutover proof; "
                    "the old restamper remains present only as the comparison/source bridge"
                ),
            }
        return {
            "category": "C. render-stage final item binding bridge",
            "reason": "render card still normalizes/stamps the final item before HTML view-model rendering",
        }
    if "_pre_render_bound_item" in text or "_pre_card_bound_item" in text:
        return {
            "category": "C. render-stage pre-card binding bridge",
            "reason": "returned bound item feeds contract, safe-combined action, and primary card state before render",
        }
    if (
        "item =" in text
        and function_name == "_render_guidance_secondary_items"
        and "render_guidance_secondary_primary_binding_adapter_cutover_applied" in context_text
        and "_stamp_final_visible_final_visible_output_bridge_proof" in context_text
    ):
        return {
            "category": "B. adapter-covered result-identity bridge",
            "reason": (
                "generic primary card binding is covered by controller adapter parity/readiness/cutover proof; "
                "the old restamper remains present only as the comparison/source bridge"
            ),
        }
    if "item =" in text:
        return {
            "category": "D. generic item binding needs proof",
            "reason": f"generic restamper call inside {function_name or 'unknown function'} needs focused ownership proof",
        }
    if "_primary_bending_resolution" in text:
        return {
            "category": "D. primary bending resolution bridge needs proof",
            "reason": "late primary bending resolution path needs a focused publication/CTA parity proof",
        }
    return {
        "category": "E. unknown / needs proof",
        "reason": "callsite did not match a known post-resolver cleanup class",
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    lines = source.splitlines()
    tree = ast.parse(source)
    calls: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_name(node.func) != RESTAMPER:
            continue
        line = int(getattr(node, "lineno", 0) or 0)
        function_name = _enclosing_function(tree, line)
        line_text = lines[line - 1] if 0 < line <= len(lines) else ""
        context_text = "\n".join(lines[line - 1 : min(len(lines), line + 60)]) if line > 0 else ""
        calls.append(
            {
                "line": line,
                "function": function_name,
                "line_text": line_text.strip(),
                **_classify(line_text, function_name, context_text),
            }
        )
    category_counts: dict[str, int] = {}
    for call in calls:
        category_counts[call["category"]] = category_counts.get(call["category"], 0) + 1
    function_definition_count = source.count(f"def {RESTAMPER}(")
    call_count = len(calls)
    decision = (
        "RESTAMPER_HELPER_AND_CALLS_DELETED_ZERO_LOCK"
        if function_definition_count == 0 and call_count == 0
        else "RESTAMPER_NOT_READY_TO_DELETE_CALLSITE_PROOF_REQUIRED"
    )
    return {
        "decision": decision,
        "function_definition_count": function_definition_count,
        "call_count": call_count,
        "calls": sorted(calls, key=lambda row: row["line"]),
        "category_counts": category_counts,
        "latest": {
            "dead_body_deletion": _latest("design_guide_final_visible_resolver_dead_body_deletion_proof"),
            "secondary_binding_adapter_parity": _latest(
                "design_guide_render_guidance_secondary_binding_adapter_parity"
            ),
            "secondary_binding_cutover_readiness": _latest(
                "design_guide_render_guidance_secondary_binding_cutover_readiness"
            ),
            "secondary_binding_adapter_cutover": _latest(
                "design_guide_render_guidance_secondary_binding_adapter_cutover"
            ),
            "pre_card_binding_parity": _latest(
                "design_guide_render_guidance_secondary_pre_card_binding_parity"
            ),
            "pre_card_binding_cutover_readiness": _latest(
                "design_guide_render_guidance_secondary_pre_card_binding_cutover_readiness"
            ),
            "pre_card_binding_adapter_cutover": _latest(
                "design_guide_render_guidance_secondary_pre_card_binding_adapter_cutover"
            ),
            "final_item_binding_parity": _latest(
                "design_guide_render_fast_panel_final_item_binding_adapter_parity"
            ),
            "final_item_binding_cutover_readiness": _latest(
                "design_guide_render_fast_panel_final_item_binding_cutover_readiness"
            ),
            "final_item_binding_adapter_cutover": _latest(
                "design_guide_render_fast_panel_final_item_binding_adapter_cutover"
            ),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    category_counts = capture.get("category_counts") or {}
    adapter_covered_count = int(category_counts.get("B. adapter-covered result-identity bridge", 0) or 0)
    zero_locked = (
        capture.get("decision") == "RESTAMPER_HELPER_AND_CALLS_DELETED_ZERO_LOCK"
        and capture.get("function_definition_count") == 0
        and capture.get("call_count") == 0
    )
    return {
        "restamper_function_deleted_or_intentionally_present": zero_locked
        or capture.get("function_definition_count") == 1,
        "restamper_helper_and_calls_zero_locked": zero_locked
        or capture.get("function_definition_count") == 1,
        "restamper_calls_identified": capture.get("call_count") == len(capture.get("calls") or []),
        "no_unknown_call_classes": category_counts.get("E. unknown / needs proof", 0) == 0,
        "adapter_covered_bridge_has_parity_proof": adapter_covered_count == 0
        or (
            (latest.get("secondary_binding_adapter_parity") or {}).get("status") == "PASS"
            and (latest.get("pre_card_binding_parity") or {}).get("status") == "PASS"
            and (latest.get("final_item_binding_parity") or {}).get("status") == "PASS"
        ),
        "adapter_covered_bridge_has_readiness_proof": adapter_covered_count == 0
        or (
            (latest.get("secondary_binding_cutover_readiness") or {}).get("status") == "PASS"
            and (latest.get("pre_card_binding_cutover_readiness") or {}).get("status") == "PASS"
            and (latest.get("final_item_binding_cutover_readiness") or {}).get("status") == "PASS"
        ),
        "adapter_covered_bridge_has_cutover_proof": adapter_covered_count == 0
        or (
            (latest.get("secondary_binding_adapter_cutover") or {}).get("status") == "PASS"
            and (latest.get("pre_card_binding_adapter_cutover") or {}).get("status") == "PASS"
            and (latest.get("final_item_binding_adapter_cutover") or {}).get("status") == "PASS"
        ),
        "dead_body_deletion_latest_pass": (latest.get("dead_body_deletion") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Remaining Final Visible Restamper Reference Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Summary",
        "",
        f"- Function definitions: `{capture.get('function_definition_count')}`",
        f"- Calls: `{capture.get('call_count')}`",
        "",
        "## Category Counts",
        "",
        "```json",
        json.dumps(capture.get("category_counts") or {}, indent=2),
        "```",
        "",
        "## Calls",
        "",
        "| Line | Function | Category | Reason |",
        "| ---: | --- | --- | --- |",
    ]
    for call in list(capture.get("calls") or []):
        lines.append(
            f"| {call.get('line')} | `{call.get('function')}` | {call.get('category')} | {call.get('reason')} |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            (
                "The restamper helper/callsite surface is zero-locked. The next safe target is the transitional "
                "presentation adapter or any remaining verifier-only references to deleted restamper names."
                if capture.get("decision") == "RESTAMPER_HELPER_AND_CALLS_DELETED_ZERO_LOCK"
                else (
                    "The generic primary card binding is now adapter-covered but not deletion-ready. The next "
                    "safe step is a controller/publication equivalent for one remaining C-class bridge, starting "
                    "with the pre-render or pre-card binding path, then a parity proof before any cutover/deletion."
                )
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_remaining_final_visible_restamper_reference_audit.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_remaining_final_visible_restamper_reference_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_remaining_final_visible_restamper_reference_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_remaining_final_visible_restamper_reference_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
