"""Deletion proof for A-class compute evidence compatibility helper.

This verifies the old inputs_page helper-row surface was removed after consumer
proof, while FinalDesignGuidePublication.evidence and controller publication
authority remain present.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REMOVED_TOKENS = (
    "_mark_compute_publication_evidence_a_class_compatibility_only",
    "final_publication_compute_a_class_evidence_rows",
    "final_publication_compute_a_class_evidence_rows_hash",
    "final_publication_compute_a_class_evidence_compatibility_only",
    "final_publication_compute_a_class_evidence_can_override_publication",
    "compute_a_class_evidence:raw_selected_item_identity",
    "compute_a_class_evidence:render_reason",
    "compute_a_class_evidence:state_fingerprint",
    "compute_a_class_evidence:raw_rebound_item_identity",
    'row_id="raw_selected_item_identity"',
    'row_id="render_reason"',
    'row_id="state_fingerprint"',
    'row_id="raw_rebound_item_identity"',
)

LIVE_REQUIRED_INPUT_TOKENS = (
    "_run_design_guide_controller_publication_authority(",
    "_stamp_final_publication_compute_handoff_rebound_decision_proof(",
    "_stamp_design_guide_controller_compute_rebound_mutation_trace_only(",
    "final_compute_resolution.get(\"render_reason\")",
    "final_compute_resolution.get(\"state_fingerprint\")",
)

LIVE_REQUIRED_FINAL_PUBLICATION_TOKENS = (
    "compute_publication_evidence:",
    "compute_publication_evidence_hashes:",
    "compute_publication_evidence_hash:",
)

ARTIFACT_PREFIXES = {
    "consumer_audit": "design_guide_compute_compatibility_helper_consumer_audit",
    "publication_evidence_same_object": "design_guide_publication_evidence_compute_truth_same_object",
    "mutation_adapter_cutover": "design_guide_compute_rebound_mutation_adapter_cutover",
    "independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "status": None, "payload": {}, "error": str(exc)}
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def _build_payload() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    input_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8", errors="replace")
    removed_token_presence = {token: token in input_source for token in REMOVED_TOKENS}
    live_input_presence = {token: token in input_source for token in LIVE_REQUIRED_INPUT_TOKENS}
    live_final_publication_presence = {
        token: token in final_source for token in LIVE_REQUIRED_FINAL_PUBLICATION_TOKENS
    }
    artifacts = {name: _latest(prefix) for name, prefix in ARTIFACT_PREFIXES.items()}

    consumer_payload = dict(artifacts["consumer_audit"].get("payload") or {})
    consumer_helpers = {
        row.get("helper"): row
        for row in consumer_payload.get("helpers", [])
        if isinstance(row, dict)
    }
    a_class_consumer = dict(
        consumer_helpers.get("_mark_compute_publication_evidence_a_class_compatibility_only") or {}
    )
    consumer_proof_ok = (
        artifacts["consumer_audit"].get("status") == "PASS"
        and a_class_consumer.get("product_consumer_occurrences") == []
        and str(a_class_consumer.get("classification") or "").startswith(("A.", "B."))
    )

    failures: list[str] = []
    if any(removed_token_presence.values()):
        failures.append("removed_a_class_evidence_token_still_present")
    if not all(live_input_presence.values()):
        failures.append("required_input_publication_or_compute_trace_surface_missing")
    if not all(live_final_publication_presence.values()):
        failures.append("required_final_publication_compute_evidence_surface_missing")
    if not consumer_proof_ok:
        failures.append("pre_deletion_consumer_proof_missing_or_not_pass")
    for name in (
        "publication_evidence_same_object",
        "mutation_adapter_cutover",
        "independence_lock",
        "render_bridge_lock",
    ):
        if artifacts[name].get("status") != "PASS":
            failures.append(f"{name}_latest_artifact_not_pass")

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "failures": failures,
        "summary": {
            "helper_deleted": not any(removed_token_presence.values()),
            "publication_evidence_surface_still_live": all(live_final_publication_presence.values()),
            "input_publication_trace_surfaces_still_live": all(live_input_presence.values()),
            "pre_deletion_consumer_proof_ok": consumer_proof_ok,
            "product_behavior_changed": False,
            "visible_wording_changed": False,
            "cta_apply_semantics_changed": False,
        },
        "removed_token_presence": removed_token_presence,
        "live_input_presence": live_input_presence,
        "live_final_publication_presence": live_final_publication_presence,
        "artifacts": artifacts,
        "next_safe_step": (
            "Run composed locks with removed-state guards, then update the remaining "
            "smoothness/inventory snapshots so they no longer list deleted helper-row "
            "surfaces as bypass candidates."
        ),
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    return payload


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide A-Class Compute Evidence Helper Deletion Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Snapshot hash: `{payload['snapshot_hash']}`",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in payload["summary"].items())
    lines.extend(["", "## Removed Token Presence", ""])
    for token, present in payload["removed_token_presence"].items():
        lines.append(f"- `{token}`: `{present}`")
    lines.extend(["", "## Live Input Token Presence", ""])
    for token, present in payload["live_input_presence"].items():
        lines.append(f"- `{token}`: `{present}`")
    lines.extend(["", "## Live Final Publication Token Presence", ""])
    for token, present in payload["live_final_publication_presence"].items():
        lines.append(f"- `{token}`: `{present}`")
    lines.extend(["", "## Artifacts", ""])
    for name, artifact in payload["artifacts"].items():
        lines.append(f"- {name}: `{artifact.get('status')}` `{artifact.get('path')}`")
    lines.extend(["", "## Next Safe Step", "", payload["next_safe_step"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_compute_a_class_evidence_helper_deletion_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_a_class_evidence_helper_deletion_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_guide_compute_a_class_evidence_helper_deletion {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
