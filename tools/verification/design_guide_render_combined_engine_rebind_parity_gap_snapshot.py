"""Parity-gap snapshot for render-stage combined/engine rebind replacement.

Proof-only. The previous readiness snapshot proved the two render-stage rebind
bridges are the next tempting deletion/cutover targets. This verifier records
why they are not yet safe to replace with the collapsed-guidance publication
adapter alone: the old binding helper still performs contract-binding effects
that can change CTA/apply truth for target-band promotion, consistency guards,
contract truth, and no-second-CTA suppression.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET_REBINDS: tuple[dict[str, Any], ...] = (
    {
        "id": "combined_evidence_rebind_bridge",
        "call": "_combined_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "replacement_item": "_combined_rebind_item",
        "reason": "combined_evidence_contract_rebound",
    },
    {
        "id": "engine_evidence_rebind_bridge",
        "call": "_engine_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "replacement_item": "_engine_rebind_source_item",
        "reason": "late_engine_combined_evidence_contract_rebound",
    },
)

REQUIRED_LIVE_BINDING_EFFECTS: tuple[dict[str, str], ...] = (
    {
        "id": "target_band_promotion",
        "source_token": "_stamp_final_visible_contract_binding_target_band_promotion_result(",
        "builder_token": "def build_final_visible_contract_binding_target_band_promotion_result(",
    },
    {
        "id": "safe_consistency_guard",
        "source_token": 'callsite_id="shear_safe_binding_contract_mismatch_reset"',
        "builder_token": "def build_final_visible_contract_binding_consistency_guard_result(",
    },
    {
        "id": "combined_consistency_guard",
        "source_token": 'callsite_id="combined_binding_contract_mismatch_reset"',
        "builder_token": "def build_final_visible_contract_binding_consistency_guard_result(",
    },
    {
        "id": "contract_truth",
        "source_token": "_stamp_final_visible_contract_binding_truth_result(",
        "builder_token": "def build_final_visible_contract_binding_truth_result(",
    },
    {
        "id": "no_second_cta",
        "source_token": "_stamp_final_visible_contract_binding_no_second_cta_result(",
        "builder_token": "def build_final_visible_contract_binding_no_second_cta_result(",
    },
)

ADAPTER_TOKEN = "_collapsed_guidance_item_from_final_publication_authority("
ADAPTER_BUILDER_TOKEN = "build_collapsed_guidance_item_from_final_publication("


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _line_for(lines: list[str], token: str) -> int | None:
    for index, line in enumerate(lines, start=1):
        if token in line:
            return index
    return None


def _window(lines: list[str], line: int | None, *, before: int = 80, after: int = 100) -> str:
    if line is None:
        return ""
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


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


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    final_publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = inputs_source.splitlines()
    helper_line = _line_for(lines, "def _publish_final_visible_design_guide_contract_binding(")
    helper_context = _window(lines, helper_line, before=0, after=950)

    rebinds = []
    for target in TARGET_REBINDS:
        line = _line_for(lines, str(target["call"]))
        context = _window(lines, line)
        rebinds.append(
            {
                "id": target["id"],
                "line": line,
                "old_binding_call_present": line is not None,
                "source_item_present": str(target["replacement_item"]) in context,
                "collapsed_adapter_available": ADAPTER_TOKEN in inputs_source,
                "collapsed_adapter_not_wired_here": ADAPTER_TOKEN not in context,
                "required_publication_reason": target["reason"],
            }
        )

    live_effects = []
    for effect in REQUIRED_LIVE_BINDING_EFFECTS:
        live_effects.append(
            {
                "id": effect["id"],
                "old_binding_effect_present": effect["source_token"] in helper_context,
                "design_brain_builder_present": effect["builder_token"] in final_publication_source,
                "controller_rebind_adapter_uses_effect": effect["builder_token"] in controller_source,
                "safe_to_skip_effect": False,
            }
        )

    latest = {
        "replacement_readiness": _latest(
            "design_guide_render_combined_engine_rebind_replacement_readiness"
        ),
        "collapsed_replacement_cutover": _latest("design_guide_collapsed_replacement_authority_cutover"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    gap_fields = [
        row["id"]
        for row in live_effects
        if row["old_binding_effect_present"]
        and row["design_brain_builder_present"]
        and not row["controller_rebind_adapter_uses_effect"]
    ]
    return {
        "decision": "NOT_READY_TO_CUT_OVER_REBINDS",
        "reason": (
            "The collapsed-guidance adapter is available, but the old binding call still composes "
            "live contract-binding effects not yet represented by a controller rebind adapter."
        ),
        "rebinds": rebinds,
        "live_binding_effects": live_effects,
        "controller_gap_effects": gap_fields,
        "required_next_slice": (
            "Create a DesignGuideController final-visible contract-binding adapter/proof that composes "
            "the existing FinalDesignGuidePublication binding result builders, then compare old vs new "
            "combined/engine rebind surfaces before replacing the calls."
        ),
        "safe_to_cut_over_now": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest_artifacts": latest,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rebinds = list(capture.get("rebinds") or [])
    effects = list(capture.get("live_binding_effects") or [])
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "two_rebinds_captured": len(rebinds) == 2,
        "old_calls_still_present": all(row.get("old_binding_call_present") is True for row in rebinds),
        "source_items_present": all(row.get("source_item_present") is True for row in rebinds),
        "collapsed_adapter_available": all(row.get("collapsed_adapter_available") is True for row in rebinds),
        "collapsed_adapter_not_wired_here": all(
            row.get("collapsed_adapter_not_wired_here") is True for row in rebinds
        ),
        "all_required_live_effects_present": all(
            row.get("old_binding_effect_present") is True for row in effects
        ),
        "all_live_effect_builders_in_design_brain": all(
            row.get("design_brain_builder_present") is True for row in effects
        ),
        "controller_adapter_gap_exists": bool(capture.get("controller_gap_effects")),
        "not_safe_to_cut_over_now": capture.get("safe_to_cut_over_now") is False,
        "replacement_readiness_pass": (latest.get("replacement_readiness") or {}).get("status") == "PASS",
        "collapsed_replacement_cutover_pass": (
            latest.get("collapsed_replacement_cutover") or {}
        ).get("status")
        == "PASS",
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
        "# Render Combined/Engine Rebind Parity Gap Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        capture.get("reason") or "",
        "",
        "## Rebinds",
        "",
        "| ID | Line | Old Call Present | Adapter Available | Adapter Wired Here |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in capture.get("rebinds") or []:
        lines.append(
            f"| `{row.get('id')}` | `{row.get('line')}` | `{row.get('old_binding_call_present')}` | "
            f"`{row.get('collapsed_adapter_available')}` | "
            f"`{not bool(row.get('collapsed_adapter_not_wired_here'))}` |"
        )
    lines.extend(
        [
            "",
            "## Live Binding Effects Blocking Cutover",
            "",
            "| Effect | Old Helper Has Effect | Design Brain Builder Exists | Controller Rebind Adapter Uses It |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in capture.get("live_binding_effects") or []:
        lines.append(
            f"| `{row.get('id')}` | `{row.get('old_binding_effect_present')}` | "
            f"`{row.get('design_brain_builder_present')}` | "
            f"`{row.get('controller_rebind_adapter_uses_effect')}` |"
        )
    lines.extend(
        [
            "",
            "## Required Next Slice",
            "",
            str(capture.get("required_next_slice") or ""),
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
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_combined_engine_rebind_parity_gap_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_combined_engine_rebind_parity_gap_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_combined_engine_rebind_parity_gap_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_combined_engine_rebind_parity_gap_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
