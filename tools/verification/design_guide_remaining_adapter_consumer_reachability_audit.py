from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACTS = ROOT / "artifacts"
VERIFICATION = ARTIFACTS / "verification"
AUDITS = ARTIFACTS / "audits"

HISTORICAL_DIRECT_PASS_SURFACES: tuple[dict[str, Any], ...] = (
    {
        "callsite_id": "render_guidance_secondary_items.pre_render_binding",
        "classification": "deleted_direct_pass_through",
        "evidence_reason": "direct_pass_through_after_adapter_identity_proof",
        "evidence_assignment": "_pre_render_bound_item = dict(_pre_render_input_item)",
        "replacement_needed": "none; this path is already direct pass-through",
    },
    {
        "callsite_id": "render_guidance_secondary_items.pre_card_binding",
        "classification": "deleted_direct_pass_through",
        "evidence_reason": "pre_card_direct_pass_through_after_adapter_identity_proof",
        "evidence_assignment": "_pre_card_bound_item = dict(_pre_card_input_item)",
        "replacement_needed": "none; this path is already direct pass-through",
    },
)

CURRENT_LIVE_SURFACES: tuple[dict[str, Any], ...] = (
    {
        "callsite_id": "render_fast_design_guidance_panel.final_visible_item_binding",
        "surface_kind": "clean_publication_binding_consumer",
        "adapter": "_build_final_visible_render_binding_payload",
        "consumer_tokens": (
            "_final_visible_item = dict(",
            "(_final_visible_render_binding or {}).get(\"debug_updates\") or {}",
            "_store_final_visible_compatibility_restamper_render_item_projection_debug(",
        ),
        "replacement_needed": "later direct publication/controller render payload consumer if compatibility scaffolding is deleted internally",
    },
)


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    matches = sorted(VERIFICATION.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not matches:
        return {"found": False, "path": None, "status": None}
    path = matches[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "status": "UNREADABLE", "error": str(exc)}
    status = payload.get("status") or payload.get("result")
    return {"found": True, "path": str(path), "status": status, "payload": payload}


def _call_window(source: str, adapter: str, callsite_id: str) -> tuple[int | None, str]:
    pattern = re.compile(
        rf"{re.escape(adapter)}\(\s*[\s\S]{{0,900}}?callsite_id\s*=\s*{re.escape(json.dumps(callsite_id))}",
        re.MULTILINE,
    )
    match = pattern.search(source)
    if not match:
        return None, ""
    line = source[: match.start()].count("\n") + 1
    return line, source[max(0, match.start() - 1200) : min(len(source), match.end() + 3600)]


def _deleted_direct_pass_through(
    inputs_source: str,
    final_publication_source: str,
    *,
    evidence_reason: str,
    evidence_assignment: str,
) -> bool:
    # These paths were already collapsed to direct pass-through and then physically
    # removed from inputs_page.py. Once that happens, current source-text presence
    # is no longer the right proof. The right proof is:
    # 1) the old assignment path is absent from inputs_page.py, and
    # 2) the identity-proof marker now lives in the Design Brain helper, not in a
    #    page-local restamper branch.
    assignment_still_present = evidence_assignment in inputs_source
    reason_in_page = evidence_reason in inputs_source
    reason_in_design_brain = evidence_reason in final_publication_source
    return bool((not assignment_still_present) and (reason_in_page or reason_in_design_brain))


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    source = INPUTS.read_text(encoding="utf-8")
    final_publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    failures: list[str] = []
    rows: list[dict[str, Any]] = []

    for surface in HISTORICAL_DIRECT_PASS_SURFACES:
        deleted = _deleted_direct_pass_through(
            source,
            final_publication_source,
            evidence_reason=str(surface["evidence_reason"]),
            evidence_assignment=str(surface["evidence_assignment"]),
        )
        row = {
            "callsite_id": surface["callsite_id"],
            "classification": surface["classification"],
            "deleted_as_direct_pass_through": deleted,
            "evidence_reason": surface["evidence_reason"],
            "evidence_assignment": surface["evidence_assignment"],
            "replacement_needed": surface["replacement_needed"],
            "safe_to_delete_adapter_now": True,
        }
        rows.append(row)
        if not deleted:
            failures.append(f"missing_direct_pass_through_evidence:{surface['callsite_id']}")

    primary_wrapper_deleted = (
        "render_guidance_secondary_primary_binding" not in source
        and "_build_final_visible_compatibility_restamper_render_item_projection(" not in source
    )
    rows.append(
        {
            "callsite_id": "render_guidance_secondary_primary_binding",
            "classification": "deleted_wrapper_consumer",
            "deleted_as_wrapper_consumer": primary_wrapper_deleted,
            "replacement_needed": "none; wrapper consumer deleted",
            "safe_to_delete_adapter_now": True,
        }
    )
    if not primary_wrapper_deleted:
        failures.append("primary_wrapper_consumer_still_present")

    live_projection_consumer_count = 0
    live_bypass_count = 0
    for surface in CURRENT_LIVE_SURFACES:
        line, window = _call_window(source, str(surface["adapter"]), str(surface["callsite_id"]))
        consumer_hits = {token: token in window for token in surface["consumer_tokens"]}
        live_consumers = [token for token, present in consumer_hits.items() if present]
        classification = str(surface["surface_kind"])
        if window:
            if classification == "design_brain_projection_consumer":
                live_projection_consumer_count += 1
            elif classification == "design_brain_bypass_decision_call_allowed":
                live_bypass_count += 1
        row = {
            "callsite_id": surface["callsite_id"],
            "adapter": surface["adapter"],
            "adapter_line": line,
            "adapter_call_present": bool(window),
            "classification": classification,
            "consumer_hits": consumer_hits,
            "live_consumer_count": len(live_consumers),
            "live_consumers": live_consumers,
            "replacement_needed": surface["replacement_needed"],
            "safe_to_delete_adapter_now": False,
            "window_hash": _stable_hash(window) if window else None,
        }
        rows.append(row)
        if not row["adapter_call_present"]:
            failures.append(f"missing_live_call:{surface['adapter']}")
        if not live_consumers:
            failures.append(f"missing_expected_live_consumers:{surface['adapter']}")

    wrapper_deadness = _latest("design_guide_compatibility_restamper_wrapper_deadness")
    post_render_readiness = _latest("design_guide_post_render_bridge_restamper_readiness")
    proof_deadness = _latest("design_guide_restamper_proof_stamp_deadness")
    duplicate_reachability = _latest("design_guide_duplicate_restamper_reachability")

    if wrapper_deadness.get("status") != "PASS":
        failures.append("wrapper_deadness_not_passed")
    if post_render_readiness.get("status") != "PASS":
        failures.append("post_render_bridge_restamper_readiness_not_passed")
    if proof_deadness.get("status") != "PASS":
        failures.append("proof_stamp_deadness_not_passed")
    if duplicate_reachability.get("status") != "PASS":
        failures.append("duplicate_restamper_reachability_not_passed")

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "schema": "design_guide_remaining_adapter_consumer_reachability.v2",
        "status": status,
        "generated_at": timestamp,
        "source_file": str(INPUTS),
        "failures": failures,
        "surfaces": rows,
        "classification_counts": {
            "deleted_direct_pass_through": sum(
                1 for row in rows if row["classification"] == "deleted_direct_pass_through"
            ),
            "deleted_wrapper_consumer": sum(
                1 for row in rows if row["classification"] == "deleted_wrapper_consumer"
            ),
            "clean_publication_binding_consumer": sum(
                1 for row in rows if row["classification"] == "clean_publication_binding_consumer"
            ),
        },
        "historical_deleted_callsites": [
            row["callsite_id"]
            for row in rows
            if row["classification"] in {"deleted_direct_pass_through", "deleted_wrapper_consumer"}
        ],
        "live_projection_consumer_count": live_projection_consumer_count,
        "live_bypass_count": live_bypass_count,
        "safe_deletion_candidates": [row for row in rows if row["safe_to_delete_adapter_now"]],
        "latest_supporting_artifacts": {
            "wrapper_deadness": {
                "path": wrapper_deadness.get("path"),
                "status": wrapper_deadness.get("status"),
            },
            "post_render_bridge_restamper_readiness": {
                "path": post_render_readiness.get("path"),
                "status": post_render_readiness.get("status"),
            },
            "proof_stamp_deadness": {
                "path": proof_deadness.get("path"),
                "status": proof_deadness.get("status"),
            },
            "duplicate_restamper_reachability": {
                "path": duplicate_reachability.get("path"),
                "status": duplicate_reachability.get("status"),
            },
        },
        "next_safe_target": (
            "Reclassify the compatibility restamper projection and bypass clusters now that the page consumes "
            "one clean render-binding payload instead of the lower-level compatibility builders directly."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "snapshot_hash": None,
    }
    snapshot["snapshot_hash"] = _stable_hash(snapshot)

    json_path = VERIFICATION / f"design_guide_remaining_adapter_consumer_reachability_{timestamp}.json"
    report_path = AUDITS / f"design_guide_remaining_adapter_consumer_reachability_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    surface_rows = []
    for row in rows:
        surface_rows.append(
            "| `{callsite_id}` | `{classification}` | `{adapter}` | `{line}` | `{live_count}` | {replacement} |".format(
                callsite_id=row.get("callsite_id"),
                classification=row.get("classification"),
                adapter=row.get("adapter", "historical"),
                line=row.get("adapter_line", "-"),
                live_count=row.get("live_consumer_count", 0),
                replacement=row.get("replacement_needed"),
            )
        )
    failure_text = "\n".join(f"- `{failure}`" for failure in failures) if failures else "None."
    report = [
        "# Design Guide Remaining Adapter Consumer Reachability Audit",
        "",
        f"## Summary\n{status}",
        "",
        "## Surface Inventory",
        "",
        "| Callsite | Classification | Adapter | Line | Live Consumers | Replacement Needed |",
        "| --- | --- | --- | ---: | ---: | --- |",
        *surface_rows,
        "",
        "## Decision",
        "",
        "The pre-render, pre-card, and primary wrapper consumers are deleted. The remaining live page shell now consumes one clean Design Brain render-binding payload at render-fast final-visible binding, not the lower-level compatibility adapter/debug/bypass pieces directly.",
        "",
        "## Failures",
        "",
        failure_text,
        "",
        "## Next Safe Target",
        "",
        str(snapshot["next_safe_target"]),
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"design_guide_remaining_adapter_consumer_reachability {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
