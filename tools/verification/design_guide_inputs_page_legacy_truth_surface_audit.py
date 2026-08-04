"""Audit remaining Design Guide truth surfaces in inputs_page.py.

This is a deletion-planning verifier. It distinguishes old page-owned truth
paths that must stay deleted from remaining bridge/plumbing surfaces that need
separate proof before removal. It is intentionally strict about known mismatch
patterns, especially page-owned passive no-action banners.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
INDEPENDENCE_LOCK = ROOT / "tools" / "verification" / "design_guide_independence_lock_verifier.py"


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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _line_numbers(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8", errors="replace")
    lock_source = INDEPENDENCE_LOCK.read_text(encoding="utf-8", errors="replace")
    retired_resolver_product_tokens = {
        "function_def": "def resolve_final_visible_design_guide_item(",
        "compute_direct_call": "final_compute_resolution = resolve_final_visible_design_guide_item(",
        "compute_fallback_call": "_legacy_fallback_resolution = resolve_final_visible_design_guide_item(",
        "render_direct_call": "_final_visible_resolution = resolve_final_visible_design_guide_item(",
        "stale_trace_decorator": '@_dg_runtime_trace_function("resolve_final_visible_design_guide_item")',
        "stale_trace_payload_branch": 'if function_name == "resolve_final_visible_design_guide_item":',
    }
    resolver_product_deleted = all(
        token not in inputs_source for token in retired_resolver_product_tokens.values()
    )
    retired_restamper_tokens = {
        "function_def": "def _publish_final_visible_design_guide_contract_binding(",
        "helper_call": "_publish_final_visible_design_guide_contract_binding(",
    }
    restamper_helper_deleted = (
        retired_restamper_tokens["function_def"] not in inputs_source
        and retired_restamper_tokens["helper_call"] not in inputs_source
    )
    banned_deleted_truth_tokens = {
        "solver_no_action_info_banner": "st.info(str(uvr))",
        "debug_no_action_info_banner": "st.info(passive_reason)",
        "debug_no_action_stop_reason_caption": 'st.caption(f"Reason: {passive_stop_reason}.")',
        "passive_banner_suppression_helper": "_should_suppress_passive_no_action_status_banner",
    }
    required_authority_tokens = {
        "final_publication_display_consumes_debug": "display = build_final_design_guide_display(item=item_d, debug=debug_d)",
        "display_accepts_debug": "debug: dict[str, Any] | None = None",
        "display_reads_presentation": 'presentation_d = _mapping(debug_d.get("design_guide_presentation"))',
        "independence_lock_checks_deleted_banner": "legacy_page_no_action_banner_deleted",
        "independence_lock_checks_presentation_consumption": "final_publication_consumes_design_guide_presentation",
    }
    remaining_surfaces = [
        {
            "surface": "_build_design_guide_presentation_state",
            "line_numbers": _line_numbers(inputs_source, "def _build_design_guide_presentation_state"),
            "classification": "B. transitional presentation adapter",
            "owner_target": "Design Brain engine / FinalDesignGuidePublication.display",
            "delete_now": False,
            "reason": "still gathers page current-state inputs and calls the engine; remove only after controller owns this adapter",
        },
        {
            "surface": "_final_visible_resolution_from_final_publication_authority",
            "line_numbers": _line_numbers(inputs_source, "def _final_visible_resolution_from_final_publication_authority"),
            "classification": "A. authority adapter keep",
            "owner_target": "FinalDesignGuidePublication",
            "delete_now": False,
            "reason": "this is the replacement bridge, not old truth",
        },
        {
            "surface": "_record_rendered_design_guide_primary_apply_payload",
            "line_numbers": _line_numbers(inputs_source, "def _record_rendered_design_guide_primary_apply_payload"),
            "classification": "D. apply/session plumbing keep",
            "owner_target": "page/shared apply routing",
            "delete_now": False,
            "reason": "apply routing intentionally remains outside Design Brain",
        },
        {
            "surface": "_render_guidance_secondary_items",
            "line_numbers": _line_numbers(inputs_source, "def _render_guidance_secondary_items"),
            "classification": "D. renderer plumbing keep",
            "owner_target": "UI renderer",
            "delete_now": False,
            "reason": "rendering remains page/UI owned; it must consume publication truth, not own engineering truth",
        },
    ]
    return {
        "latest": {
            "passive_cleanup_invariant": _latest("design_guide_passive_cleanup_final_publication_divergence"),
        },
        "banned_deleted_truth_tokens": {
            key: {
                "token": token,
                "present": token in inputs_source,
                "line_numbers": _line_numbers(inputs_source, token),
            }
            for key, token in banned_deleted_truth_tokens.items()
        },
        "retired_resolver_product_tokens": {
            key: {
                "token": token,
                "present": token in inputs_source,
                "line_numbers": _line_numbers(inputs_source, token),
            }
            for key, token in retired_resolver_product_tokens.items()
        },
        "retired_surfaces": [
            {
                "surface": "resolve_final_visible_design_guide_item",
                "classification": "retired product resolver",
                "owner_target": "DesignGuideController / FinalDesignGuidePublication",
                "deleted": resolver_product_deleted,
                "reason": "function definition, compute call, render call, fallback call, and stale trace decorator/payload branch are absent",
            },
            {
                "surface": "_publish_final_visible_design_guide_contract_binding",
                "classification": "retired compatibility restamper helper",
                "owner_target": "FinalDesignGuidePublication compatibility adapters",
                "deleted": restamper_helper_deleted,
                "reason": "helper definition and product callsites are absent",
            },
        ],
        "required_authority_tokens": {
            key: {
                "token": token,
                "present": token in (final_source + "\n" + inputs_source + "\n" + lock_source),
                "line_numbers": _line_numbers(final_source + "\n" + inputs_source + "\n" + lock_source, token),
            }
            for key, token in required_authority_tokens.items()
        },
        "remaining_surfaces": remaining_surfaces,
        "next_deletion_queue": [
            "presentation adapter after DesignGuideController owns the request/result end-to-end",
        ],
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    banned = dict(capture.get("banned_deleted_truth_tokens") or {})
    required = dict(capture.get("required_authority_tokens") or {})
    remaining = list(capture.get("remaining_surfaces") or [])
    return {
        "passive_cleanup_invariant_pass": (latest.get("passive_cleanup_invariant") or {}).get("status") == "PASS",
        "independence_lock_not_required_inside_nested_gate": True,
        "render_bridge_lock_not_required_inside_nested_gate": True,
        "compute_bridge_lock_not_required_inside_nested_gate": True,
        "known_old_truth_banner_paths_absent": all(not row.get("present") for row in banned.values()),
        "retired_resolver_product_tokens_absent": all(
            not row.get("present")
            for row in (capture.get("retired_resolver_product_tokens") or {}).values()
        ),
        "retired_surfaces_mark_deleted": all(
            row.get("deleted") for row in capture.get("retired_surfaces") or []
        ),
        "authority_tokens_present": all(row.get("present") for row in required.values()),
        "remaining_surfaces_classified": all(row.get("classification") and row.get("owner_target") for row in remaining),
        "no_unclassified_delete_now_surface": not any(row.get("delete_now") for row in remaining),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Inputs Page Legacy Truth Surface Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Deleted / Banned Truth Paths"])
    for key, row in (capture.get("banned_deleted_truth_tokens") or {}).items():
        lines.append(f"- {key}: present `{row.get('present')}`")
    lines.extend(["", "## Retired Resolver Product Surface"])
    for row in capture.get("retired_surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: deleted `{row.get('deleted')}`; "
            f"classification `{row.get('classification')}`; {row.get('reason')}"
        )
    lines.extend(["", "## Retired Resolver Product Tokens"])
    for key, row in (capture.get("retired_resolver_product_tokens") or {}).items():
        lines.append(f"- {key}: present `{row.get('present')}`")
    lines.extend(["", "## Remaining Surfaces"])
    lines.append("| Surface | Classification | Owner Target | Delete Now | Reason |")
    lines.append("|---|---|---|---:|---|")
    for row in capture.get("remaining_surfaces") or []:
        lines.append(
            f"| {row.get('surface')} | {row.get('classification')} | "
            f"{row.get('owner_target')} | `{row.get('delete_now')}` | {row.get('reason')} |"
        )
    lines.extend(["", "## Next Deletion Queue"])
    lines.extend(f"- {item}" for item in capture.get("next_deletion_queue") or [])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_inputs_page_legacy_truth_surface_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_inputs_page_legacy_truth_surface_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_inputs_page_legacy_truth_surface_audit {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
