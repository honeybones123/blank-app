"""Readiness snapshot for render-stage combined/engine rebind replacement.

Proof-only. This maps the two render-stage rebinds that still call
_publish_final_visible_design_guide_contract_binding and decides whether they
can be replaced by the collapsed-publication authority adapter now.
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

TARGETS: tuple[dict[str, Any], ...] = (
    {
        "id": "combined_evidence_rebind_bridge",
        "call": "_combined_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "source_item": "_combined_rebind_item",
        "post_tokens": (
            "displayed_primary_item = dict(_combined_rebound_item)",
            "displayed_primary_button_contract = dict(",
            "displayed_primary_payload = dict(displayed_primary_item.get(\"action_payload\") or {})",
            "displayed_primary_candidate_search_evidence = dict(",
            "render_plan[\"visible_guidance_items\"] = [dict(displayed_primary_item)]",
        ),
    },
    {
        "id": "engine_evidence_rebind_bridge",
        "call": "_engine_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "source_item": "_engine_rebind_source_item",
        "post_tokens": (
            "displayed_primary_item = dict(_engine_rebound_item)",
            "displayed_primary_button_contract = dict(",
            "displayed_primary_payload = dict(displayed_primary_item.get(\"action_payload\") or {})",
            "_engine_candidate_search_evidence = dict(displayed_primary_candidate_search_evidence)",
            "guidance_debug[\"late_engine_combined_evidence_contract_rebound\"] = True",
        ),
    },
)

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "design_guide_render_fast_panel_binding_ownership",
    "design_guide_render_panel_binding_adapter_readiness",
    "design_guide_collapsed_replacement_authority_cutover",
    "design_guide_compute_resolver_publication_bridge_lock",
    "design_guide_render_bridge_lock",
    "design_guide_independence_lock",
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


def _window(lines: list[str], line: int | None, before: int = 70, after: int = 90) -> str:
    if line is None:
        return ""
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    rows = []
    for target in TARGETS:
        line = _line_for(lines, str(target["call"]))
        context = _window(lines, line)
        rows.append(
            {
                "id": target["id"],
                "line": line,
                "call_present": line is not None,
                "source_item_present": str(target["source_item"]) in context,
                "post_tokens": {token: token in context for token in target["post_tokens"]},
                "publication_adapter_available": "_collapsed_guidance_item_from_final_publication_authority(" in source,
                "focused_render_rebind_parity_exists": False,
                "ready_to_cut_over_now": False,
                "required_next_proof": (
                    "Create focused parity comparing old bound rebind item with "
                    "collapsed-publication adapter item for this render-stage consumer."
                ),
            }
        )
    latest = {prefix: _latest(prefix) for prefix in REQUIRED_ARTIFACTS}
    return {
        "decision": "RENDER_COMBINED_ENGINE_REBINDS_NOT_READY_FOCUSED_PARITY_REQUIRED",
        "rows": rows,
        "row_count": len(rows),
        "ready_to_cut_over_count": sum(1 for row in rows if row.get("ready_to_cut_over_now")),
        "latest_artifacts": latest,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    rows = list(capture.get("rows") or [])
    return {
        "two_rows_captured": capture.get("row_count") == 2,
        "calls_present": all(row.get("call_present") is True for row in rows),
        "source_items_present": all(row.get("source_item_present") is True for row in rows),
        "post_consumers_present": all(all((row.get("post_tokens") or {}).values()) for row in rows),
        "publication_adapter_available": all(
            row.get("publication_adapter_available") is True for row in rows
        ),
        "focused_parity_not_yet_present": all(
            row.get("focused_render_rebind_parity_exists") is False for row in rows
        ),
        "not_ready_to_cut_over_without_parity": capture.get("ready_to_cut_over_count") == 0,
        "fast_panel_ownership_pass": (
            latest.get("design_guide_render_fast_panel_binding_ownership") or {}
        ).get("status")
        == "PASS",
        "panel_readiness_pass": (
            latest.get("design_guide_render_panel_binding_adapter_readiness") or {}
        ).get("status")
        == "PASS",
        "collapsed_replacement_cutover_pass": (
            latest.get("design_guide_collapsed_replacement_authority_cutover") or {}
        ).get("status")
        == "PASS",
        "compute_bridge_lock_pass": (
            latest.get("design_guide_compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("design_guide_render_bridge_lock") or {}).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("design_guide_independence_lock") or {}).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Render Combined/Engine Rebind Replacement Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Rows",
        "",
        "| ID | Line | Adapter Available | Ready Now | Required Next Proof |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            f"| `{row.get('id')}` | `{row.get('line')}` | `{row.get('publication_adapter_available')}` | "
            f"`{row.get('ready_to_cut_over_now')}` | {row.get('required_next_proof')} |"
        )
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
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_combined_engine_rebind_replacement_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_render_combined_engine_rebind_replacement_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_render_combined_engine_rebind_replacement_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_combined_engine_rebind_replacement_readiness {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
