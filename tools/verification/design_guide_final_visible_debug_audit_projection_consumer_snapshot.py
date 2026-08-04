"""Audit final-visible debug/audit projection consumers before deletion.

This snapshot covers the three remaining M1 page-shell projection helpers from
the final-visible branch classification:

* _set_final_visible_disabled_primary_payload_binding_audit_projection
* _update_final_visible_enabled_action_debug_projection
* _update_final_visible_disabled_debug_projection

It is intentionally proof-only.  It does not move authority or delete code.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


TARGET_HELPERS = {
    "disabled_payload_binding_audit_projection": {
        "definition": "def _set_final_visible_disabled_primary_payload_binding_audit_projection(",
        "call": "_set_final_visible_disabled_primary_payload_binding_audit_projection(",
        "protected_surface": "design_guide_primary_payload_binding_audit",
    },
    "enabled_action_debug_projection": {
        "definition": "def _update_final_visible_enabled_action_debug_projection(",
        "call": "_update_final_visible_enabled_action_debug_projection(",
        "protected_surface": "guidance_debug enabled CTA/apply projection",
    },
    "disabled_output_debug_projection": {
        "definition": "def _update_final_visible_disabled_debug_projection(",
        "call": "_update_final_visible_disabled_debug_projection(",
        "protected_surface": "guidance_debug disabled CTA/apply projection",
    },
}


CONSUMER_TOKENS = {
    "design_guide_primary_payload_binding_audit": {
        "tokens": (
            "DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY",
            "design_guide_primary_payload_binding_audit",
        ),
        "live_meaning": (
            "session/debug/apply-effect audit state is still read by apply traces, "
            "active-failure fresh-payload rebuild, post-click cleanup detection, "
            "browser/live verifiers, and regression ladders"
        ),
        "replacement_required": (
            "FinalDesignGuidePublication/controller adapter must produce the same "
            "payload binding audit projection before the page helper can be deleted"
        ),
    },
    "debug_cta_projection_fields": {
        "tokens": (
            "primary_button_contract",
            "displayed_primary_button_contract",
            "button_contract_enabled",
            "button_contract_updates",
            "button_contract_preview_pass",
            "button_contract_blocking_reason",
            "selected_action_updates",
        ),
        "live_meaning": (
            "debug/browser/verifier surfaces still inspect these fields to prove "
            "CTA/apply parity, card-state consistency, and post-click behavior"
        ),
        "replacement_required": (
            "FinalDesignGuidePublication verifier/debug payload adapter must own "
            "the projection before branch-local debug updates can be deleted"
        ),
    },
    "debug_evidence_projection_fields": {
        "tokens": (
            "candidate_search_evidence",
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
            "cleanup_evidence_by_family",
            "post_click_cleanup_evidence_by_family",
            "family_status_current",
            "family_status_preview",
            "blocker_attempts_by_family",
        ),
        "live_meaning": (
            "debug/browser/verifier surfaces still inspect family evidence and "
            "blocker rows to validate final publication/card state"
        ),
        "replacement_required": (
            "same-object final publication evidence/debug projection must cover "
            "these fields before branch-local debug updates can be deleted"
        ),
    },
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_numbers(source: str, token: str) -> list[int]:
    return [idx for idx, line in enumerate(source.splitlines(), start=1) if token in line]


def _function_body(source: str, name: str) -> str:
    needle = f"def {name}("
    start = source.find(needle)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(needle))
    return source[start:] if next_def < 0 else source[start:next_def]


def _branch_body(source: str) -> str:
    return _function_body(source, "_publish_final_visible_design_guide_contract_binding")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(_read(path))
    except Exception as exc:
        return {"found": True, "path": str(path), "status": None, "load_error": str(exc)}
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def _helper_rows(source: str, branch: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for helper_id, spec in TARGET_HELPERS.items():
        definition_lines = _line_numbers(source, spec["definition"])
        call_lines = [
            line
            for line in _line_numbers(source, spec["call"])
            if line not in definition_lines
        ]
        branch_call_lines = [
            line
            for line in call_lines
            if spec["call"] in source.splitlines()[line - 1]
            and spec["call"] in branch
        ]
        rows.append(
            {
                "helper": helper_id,
                "definition_lines": definition_lines,
                "call_lines": call_lines,
                "protected_surface": spec["protected_surface"],
                "current_classification": "M1 move/delete candidate after audit",
                "safe_to_delete_raw": False,
                "required_before_deletion": "adapter parity plus deadness proof",
            }
        )
        rows[-1]["branch_call_count"] = len(branch_call_lines) or len(call_lines)
    return rows


def _consumer_rows(source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tool_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT / "tools" / "verification").glob("**/*.py")
    )
    final_publication_source = _read(ROOT / "design_brain" / "final_publication.py")
    for surface, spec in CONSUMER_TOKENS.items():
        token_rows = []
        inputs_hits = 0
        tool_hits = 0
        final_publication_hits = 0
        for token in spec["tokens"]:
            input_lines = _line_numbers(source, token)
            tool_count = tool_source.count(token)
            final_publication_count = final_publication_source.count(token)
            inputs_hits += len(input_lines)
            tool_hits += tool_count
            final_publication_hits += final_publication_count
            token_rows.append(
                {
                    "token": token,
                    "inputs_page_line_count": len(input_lines),
                    "inputs_page_sample_lines": input_lines[:12],
                    "tools_verification_count": tool_count,
                    "final_publication_count": final_publication_count,
                }
            )
        rows.append(
            {
                "surface": surface,
                "tokens": token_rows,
                "inputs_page_hit_count": inputs_hits,
                "tools_verification_hit_count": tool_hits,
                "final_publication_hit_count": final_publication_hits,
                "live_meaning": spec["live_meaning"],
                "replacement_required": spec["replacement_required"],
                "safe_to_delete_raw": False,
            }
        )
    return rows


def build_snapshot() -> dict[str, Any]:
    source = _read(INPUTS)
    branch = _branch_body(source)
    helpers = _helper_rows(source, branch)
    consumers = _consumer_rows(source)
    classification = _latest("design_guide_final_visible_page_shell_effect_classification")
    inventory = _latest("design_guide_final_visible_branch_body_inventory")
    failures: list[str] = []
    if not branch:
        failures.append("final_visible_binding_helper_missing")
    for row in helpers:
        if not row["definition_lines"]:
            failures.append(f"missing_helper_definition:{row['helper']}")
        if not row["call_lines"]:
            failures.append(f"missing_helper_call:{row['helper']}")
    if classification.get("status") != "PASS":
        failures.append("latest_page_shell_classification_not_pass")
    if inventory.get("status") != "PASS":
        failures.append("latest_branch_body_inventory_not_pass")
    adapter_required = any(not row["safe_to_delete_raw"] for row in helpers)
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_final_visible_debug_audit_projection_consumer_snapshot.v1",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "decision": (
            "ADAPTER_REQUIRED_BEFORE_DEBUG_AUDIT_PROJECTION_DELETION"
            if status == "PASS" and adapter_required
            else "DEBUG_AUDIT_PROJECTION_AUDIT_FAILED"
        ),
        "helpers": helpers,
        "consumers": consumers,
        "latest_inputs": {
            "classification": {
                "path": classification.get("path"),
                "status": classification.get("status"),
            },
            "branch_body_inventory": {
                "path": inventory.get("path"),
                "status": inventory.get("status"),
            },
        },
        "safe_to_delete_now": False,
        "adapter_required_before_deletion": adapter_required,
        "recommended_adapter": (
            "FinalDesignGuidePublication final-visible debug/audit projection adapter "
            "for payload binding audit plus enabled/disabled debug projection fields"
        ),
        "next_safe_step": (
            "build a page-free projection adapter, prove parity against the current "
            "disabled payload-binding audit and enabled/disabled debug projection outputs, "
            "then cut over the branch calls before deadness/deletion"
        ),
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Visible Debug/Audit Projection Consumer Snapshot",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        f"Safe to delete now: `{snapshot['safe_to_delete_now']}`",
        "",
        "## Helpers",
        "| Helper | Calls | Protected surface | Safe to delete raw | Required before deletion |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in snapshot["helpers"]:
        lines.append(
            "| `{helper}` | {calls} | {surface} | `{safe}` | {required} |".format(
                helper=row["helper"],
                calls=len(row["call_lines"]),
                surface=row["protected_surface"],
                safe=row["safe_to_delete_raw"],
                required=row["required_before_deletion"],
            )
        )
    lines.extend(
        [
            "",
            "## Consumer Surfaces",
            "| Surface | Inputs hits | Verification hits | Final publication hits | Replacement required |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in snapshot["consumers"]:
        lines.append(
            "| `{surface}` | {inputs} | {tools} | {fp} | {required} |".format(
                surface=row["surface"],
                inputs=row["inputs_page_hit_count"],
                tools=row["tools_verification_hit_count"],
                fp=row["final_publication_hit_count"],
                required=row["replacement_required"],
            )
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            snapshot["next_safe_step"],
            "",
        ]
    )
    if snapshot["failures"]:
        lines.extend(["## Failures", *[f"- `{failure}`" for failure in snapshot["failures"]], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = snapshot["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_debug_audit_projection_consumer_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_debug_audit_projection_consumer_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_guide_final_visible_debug_audit_projection_consumer {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
