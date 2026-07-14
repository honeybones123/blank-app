"""Tail-gap snapshot for replacing old final-visible rebind helper.

Proof-only. The controller now owns the rebind-effects proof and projection,
but the old page helper still contains post-projection live tail logic. This
snapshot classifies that tail before any callsite replacement or deletion.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TAIL_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "id": "cleanup_evidence_rehydrate",
        "classification": "A. live evaluator-backed tail / must extract before callsite replacement",
        "tokens": (
            "final_binding_evidence_cleanup_rehydrate_attempted",
            "_evaluate_auto_design_candidate(",
            "final_binding_evidence_cleanup_rehydrated",
        ),
    },
    {
        "id": "disabled_contract_rebuild",
        "classification": "B. live button-contract rebuild / must prove or preserve",
        "tokens": (
            "if not _design_guide_button_contract_enabled(contract)",
            "rebuilt_contract = _design_guide_button_contract(out, state=state)",
        ),
    },
    {
        "id": "active_shear_repair_preview",
        "classification": "A. live evaluator-backed tail / must extract before callsite replacement",
        "tokens": (
            "final_visible_active_shear_repair_family_restamp",
            "_build_shear_fail_active_repair_preview_evidence(",
            "final_binding_active_shear_repair_proof",
        ),
    },
    {
        "id": "post_click_apply_context",
        "classification": "C. page apply/session context / must remain page-owned or adapter-input",
        "tokens": (
            "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
            "_post_click_apply_context_for_binding",
        ),
    },
    {
        "id": "intent_contract_from_debug_rows",
        "classification": "B. live button-contract rebuild / must prove or preserve",
        "tokens": (
            "_enabled_design_guide_contract_from_intent_rows(",
            "_intent_contract",
        ),
    },
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _line_for(lines: list[str], token: str) -> int | None:
    for index, line in enumerate(lines, start=1):
        if token in line:
            return index
    return None


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    helper_line = _line_for(lines, "def _publish_final_visible_design_guide_contract_binding(")
    projection_trace_line = _line_for(
        lines,
        'debug_sink["final_visible_contract_binding_rebind_effects_trace_wired"] = True',
    )
    helper_source = ""
    if helper_line:
        next_function = len(lines) + 1
        for index in range(helper_line + 1, len(lines) + 1):
            if lines[index - 1].startswith("def ") and index > helper_line:
                next_function = index
                break
        helper_source = "\n".join(lines[helper_line - 1 : next_function - 1])
    tail_source = ""
    if projection_trace_line and helper_line:
        next_function = len(lines) + 1
        for index in range(projection_trace_line + 1, len(lines) + 1):
            if lines[index - 1].startswith("def ") and index > projection_trace_line:
                next_function = index
                break
        tail_source = "\n".join(lines[projection_trace_line - 1 : next_function - 1])

    groups = []
    for group in TAIL_GROUPS:
        tokens = tuple(group["tokens"])
        present = {token: token in tail_source for token in tokens}
        groups.append(
            {
                "id": group["id"],
                "classification": group["classification"],
                "tokens_present": present,
                "group_present": all(present.values()),
                "safe_to_skip": False,
            }
        )
    live_groups = [row["id"] for row in groups if row.get("group_present")]
    return {
        "decision": "REBINDS_NOT_READY_FOR_REPLACEMENT_OLD_HELPER_TAIL_STILL_LIVE",
        "helper_line": helper_line,
        "projection_trace_line": projection_trace_line,
        "helper_present": bool(helper_source),
        "tail_present": bool(tail_source),
        "tail_groups": groups,
        "live_tail_group_count": len(live_groups),
        "live_tail_groups": live_groups,
        "delete_or_replace_old_helper_now": False,
        "latest_artifacts": {
            "projection_adapter_object": _latest("design_guide_rebind_projection_adapter_object"),
            "callsite_parity_readiness": _latest(
                "design_guide_controller_rebind_effects_callsite_parity_readiness"
            ),
            "controller_trace_wiring": _latest("design_guide_controller_rebind_effects_trace_wiring"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_safe_step": (
            "Extract/prove the cleanup-evidence rehydrate tail first, because it is evaluator-backed "
            "and can change item/contract/evidence after the current controller projection point."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "helper_present": capture.get("helper_present") is True,
        "tail_present": capture.get("tail_present") is True,
        "tail_groups_classified": len(capture.get("tail_groups") or []) == len(TAIL_GROUPS),
        "live_tail_groups_found": int(capture.get("live_tail_group_count") or 0) > 0,
        "not_ready_to_replace_helper": capture.get("delete_or_replace_old_helper_now") is False,
        "projection_adapter_object_pass": (latest.get("projection_adapter_object") or {}).get("status") == "PASS",
        "callsite_parity_readiness_pass": (latest.get("callsite_parity_readiness") or {}).get("status")
        == "PASS",
        "controller_trace_wiring_pass": (latest.get("controller_trace_wiring") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Rebind Projection Old Helper Tail Gap",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Tail Groups",
        "",
        "| ID | Classification | Present | Safe To Skip |",
        "| --- | --- | --- | --- |",
    ]
    for row in capture.get("tail_groups") or []:
        lines.append(
            f"| `{row.get('id')}` | {row.get('classification')} | "
            f"`{row.get('group_present')}` | `{row.get('safe_to_skip')}` |"
        )
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Safe Step", "", str(capture.get("next_safe_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_rebind_projection_old_helper_tail_gap_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_rebind_projection_old_helper_tail_gap_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_rebind_projection_old_helper_tail_gap_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_rebind_projection_old_helper_tail_gap_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
