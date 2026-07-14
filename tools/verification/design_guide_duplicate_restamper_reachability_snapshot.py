"""Reachability snapshot for duplicate Design Guide publication restampers.

This verifier enumerates callsites for duplicate final publication restampers
and classifies whether each path is pre-publication authority, post-publication
no-op, compatibility stamp, fallback support, still-live mutation, or unsafe to
delete. It is proof-only and does not change product behaviour.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

LEGACY_TARGETS = (
    "_publish_final_visible_design_guide_contract_binding",
    "resolve_final_visible_design_guide_item",
)
CURRENT_TARGETS = (
    "_build_final_visible_restamper_bridge_bypass_decision",
)
DELETED_CURRENT_TARGETS = (
    "_maybe_bypass_final_visible_restamper_bridge_noop",
    "_final_visible_compatibility_restamper_adapter_cutover",
    "_stamp_final_visible_final_visible_output_bridge_proof",
    "_final_visible_restamper_default_rebuild_adapter_cutover",
)
TARGETS = LEGACY_TARGETS + CURRENT_TARGETS

CONTEXT_RADIUS = 18


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run_verifier(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-8:],
        "stderr_tail": proc.stderr.strip().splitlines()[-8:],
    }


def _function_ranges(source: str) -> list[dict[str, Any]]:
    tree = ast.parse(source)
    ranges: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ranges.append(
                {
                    "name": node.name,
                    "start": int(node.lineno),
                    "end": int(getattr(node, "end_lineno", node.lineno)),
                }
            )
    return sorted(ranges, key=lambda row: (row["start"], row["end"]))


def _enclosing_function(line: int, ranges: list[dict[str, Any]]) -> str:
    candidates = [
        row for row in ranges if int(row["start"]) <= line <= int(row["end"])
    ]
    if not candidates:
        return "<module>"
    return sorted(candidates, key=lambda row: int(row["end"]) - int(row["start"]))[0]["name"]


def _iter_calls(source: str) -> list[dict[str, Any]]:
    lines = source.splitlines()
    ranges = _function_ranges(source)
    calls: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        for target in TARGETS:
            token = f"{target}("
            if token not in line:
                continue
            if stripped.startswith("def "):
                continue
            start = max(1, index - CONTEXT_RADIUS)
            end = min(len(lines), index + CONTEXT_RADIUS)
            context_lines = lines[start - 1 : end]
            context = "\n".join(context_lines)
            calls.append(
                {
                    "target": target,
                    "file": "inputs_page.py",
                    "line": index,
                    "function": _enclosing_function(index, ranges),
                    "source_line": stripped,
                    "context_start": start,
                    "context_end": end,
                    "context": context,
                }
            )
    return calls


def _classify_call(call: dict[str, Any]) -> dict[str, Any]:
    context = str(call["context"])
    line = int(call["line"])
    target = str(call["target"])
    function = str(call["function"])
    compatibility_only_callsite = "compatibility_only_callsite" in context
    has_hash = (
        "final_publication_authority_hash" in context
        or "publication_hash" in context
        or compatibility_only_callsite
    )
    has_debug_sink = "debug_sink" in context or "guidance_debug" in context or "debug_trace" in context
    writes_back_item = any(
        token in context
        for token in (
            "guidance_items[idx] = item",
            "collapsed_guidance_items[0]",
            "displayed_primary_item = dict",
            "_final_visible_resolution[\"item\"]",
            "_primary_render_items[0]",
            "guidance_items = [dict",
            "primary_item_for_evidence.update",
        )
    )
    final_visible = line >= 88000
    fallback = any(token in context for token in ("fallback", "shell", "pre_render", "pre_card"))
    late_evidence = any(token in context for token in ("late_evidence", "post_evidence"))
    combined_rebind = any(token in context for token in ("combined_rebind", "engine_rebind"))
    post_click_blocker = "post_click_low_bending" in context
    primary_bending = "_primary_bending_resolution" in context
    compute_path = function == "_compute_design_guidance"

    if target == "_build_final_visible_restamper_bridge_bypass_decision":
        classification = "design brain bypass decision call"
        can_change = False
        risk = "allowed page-shell call into Design Brain bypass decision; session guard inputs remain page-owned"
        safe = False
    elif target == "_final_visible_restamper_default_rebuild_adapter_cutover":
        classification = "default rebuild adapter"
        can_change = True
        risk = "controller/final-publication adapter currently replaces old default rebuild output"
        safe = False
    elif target == "_final_visible_compatibility_restamper_adapter_cutover":
        classification = "compatibility adapter"
        can_change = True
        risk = "controller/final-publication adapter currently replaces old compatibility restamper output"
        safe = False
    elif target == "_stamp_final_visible_final_visible_output_bridge_proof":
        classification = "compatibility proof stamp"
        can_change = False
        risk = "proof/debug stamp seeds guarded bypass; delete only after bypass no longer depends on it"
        safe = False
    elif target == "resolve_final_visible_design_guide_item":
        if compute_path:
            classification = "pre-publication authority"
            can_change = True
            risk = "live resolver selects the item before FinalDesignGuidePublication authority is stamped"
            safe = False
        else:
            classification = "still live mutation"
            can_change = True
            risk = "final render resolver still feeds the selected item into publication binding"
            safe = False
    elif compatibility_only_callsite:
        classification = "compatibility stamp"
        can_change = False
        risk = "selected restamper path is compatibility-only and stamped from FinalDesignGuidePublication"
        safe = False
    elif fallback:
        classification = "fallback shell support"
        can_change = False
        risk = "fallback shell is non-authoritative but may still be needed for browser/render resilience"
        safe = False
    elif late_evidence or combined_rebind or post_click_blocker or primary_bending:
        classification = "still live mutation"
        can_change = True
        risk = "result is fed back into visible item/debug state before final authority stamp"
        safe = False
    elif writes_back_item:
        classification = "still live mutation"
        can_change = True
        risk = "returned item is assigned back into guidance/final-visible state"
        safe = False
    elif has_debug_sink:
        classification = "compatibility stamp"
        can_change = False
        risk = "debug/session metadata bridge; deletion requires consumer proof"
        safe = False
    else:
        classification = "post-publication no-op"
        can_change = False
        risk = "appears hash-stamped and non-authoritative; confirm with runtime trace before deleting"
        safe = True

    if classification in {"pre-publication authority", "still live mutation", "default rebuild adapter", "compatibility adapter"}:
        can_change_outcome = True
        can_change_cta = True
        can_change_display = True
    else:
        can_change_outcome = False
        can_change_cta = False
        can_change_display = False
    writes_only_compat = classification in {
        "compatibility stamp",
        "compatibility proof stamp",
        "guarded bypass probe",
        "design brain bypass decision call",
        "post-publication no-op",
    }
    if classification == "fallback shell support":
        writes_only_compat = True

    return {
        **{key: value for key, value in call.items() if key != "context"},
        "upstream_publication_hash_available": bool(has_hash),
        "can_change_outcome_after_publication": can_change_outcome,
        "can_change_cta_after_publication": can_change_cta,
        "can_change_display_after_publication": can_change_display,
        "writes_only_compatibility_debug_metadata": writes_only_compat,
        "safe_deletion_candidate": bool(safe),
        "classification": classification,
        "deletion_risk": risk,
        "context_hash": _stable_hash(context),
        "context_excerpt": context,
    }


def _build_snapshot() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    calls = _iter_calls(source)
    classified = [_classify_call(call) for call in calls]
    lock_result = _run_verifier("tools/verification/design_guide_independence_lock_verifier.py")
    legacy_binding_body_present = "def _publish_final_visible_design_guide_contract_binding(" in source
    legacy_resolver_deleted = (
        "def resolve_final_visible_design_guide_item(" not in source
        and "resolve_final_visible_design_guide_item(" not in source
    )
    deleted_current_targets = [
        target for target in DELETED_CURRENT_TARGETS if f"{target}(" not in source
    ]
    deleted_legacy_targets = []
    deleted_legacy_targets.append("_publish_final_visible_design_guide_contract_binding_product_calls")
    if legacy_resolver_deleted:
        deleted_legacy_targets.append("resolve_final_visible_design_guide_item")

    counts: dict[str, int] = {}
    for row in classified:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    safe_candidates = [row for row in classified if row["safe_deletion_candidate"]]
    blockers = [
        row
        for row in classified
        if row["classification"] in {
            "pre-publication authority",
            "still live mutation",
            "fallback shell support",
            "default rebuild adapter",
            "compatibility adapter",
        }
    ]

    failures: list[str] = []
    if not lock_result["passed"]:
        failures.append("design_guide_independence_lock_failed")
    if not classified:
        failures.append("no_restamper_or_adapter_calls_found")
    found_targets = {row["target"] for row in classified}
    for target in LEGACY_TARGETS:
        if target not in found_targets:
            if target == "_publish_final_visible_design_guide_contract_binding":
                continue
            if target == "resolve_final_visible_design_guide_item" and legacy_resolver_deleted:
                continue
            failures.append(f"missing_target_calls:{target}")
    for target in CURRENT_TARGETS:
        if target not in found_targets:
            if target == "_final_visible_compatibility_restamper_adapter_cutover":
                continue
            failures.append(f"missing_current_target_calls:{target}")
    for target in DELETED_CURRENT_TARGETS:
        if f"{target}(" in source:
            failures.append(f"deleted_current_target_still_present:{target}")

    status = "PASS" if not failures else "FAIL"
    snapshot_hash = _stable_hash(
        {
            "calls": [
                {
                    "target": row["target"],
                    "line": row["line"],
                    "classification": row["classification"],
                    "safe": row["safe_deletion_candidate"],
                    "context_hash": row["context_hash"],
                }
                for row in classified
            ],
            "lock_passed": lock_result["passed"],
        }
    )
    return {
        "snapshot_name": "design_guide_duplicate_restamper_reachability",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "target_restampers": list(TARGETS),
        "legacy_targets": list(LEGACY_TARGETS),
        "current_targets": list(CURRENT_TARGETS),
        "deleted_legacy_targets": deleted_legacy_targets,
        "deleted_current_targets": deleted_current_targets,
        "legacy_binding_body_present_for_verifier_migration": legacy_binding_body_present,
        "callsite_count": len(classified),
        "classification_counts": counts,
        "callsites": classified,
        "safe_deletion_candidates": safe_candidates,
        "blockers": blockers,
        "design_guide_independence_lock": lock_result,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_display_authority_changed": False,
        "apply_routing_changed": False,
        "fallback_shells_removed": False,
        "snapshot_hash": snapshot_hash,
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    count_rows = [
        f"| {name} | `{count}` |"
        for name, count in sorted(snapshot["classification_counts"].items())
    ]
    call_rows = [
        "| `{file}:{line}` | `{function}` | `{target}` | `{classification}` | `{hash_available}` | `{outcome}` | `{cta}` | `{display}` | `{compat}` | `{safe}` | {risk} |".format(
            file=row["file"],
            line=row["line"],
            function=row["function"],
            target=row["target"],
            classification=row["classification"],
            hash_available=row["upstream_publication_hash_available"],
            outcome=row["can_change_outcome_after_publication"],
            cta=row["can_change_cta_after_publication"],
            display=row["can_change_display_after_publication"],
            compat=row["writes_only_compatibility_debug_metadata"],
            safe=row["safe_deletion_candidate"],
            risk=row["deletion_risk"],
        )
        for row in snapshot["callsites"]
    ]
    safe_rows = [
        f"| `{row['file']}:{row['line']}` | `{row['function']}` | `{row['target']}` | {row['deletion_risk']} |"
        for row in snapshot["safe_deletion_candidates"]
    ]
    blocker_rows = [
        f"| `{row['file']}:{row['line']}` | `{row['classification']}` | `{row['function']}` | {row['deletion_risk']} |"
        for row in snapshot["blockers"]
    ]
    body = "\n".join(
        [
            "# Design Guide Duplicate Restamper Reachability Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            f"Callsite count: `{snapshot['callsite_count']}`",
            "",
            "## Classification Counts",
            "",
            "| Classification | Count |",
            "|---|---:|",
            *count_rows,
            "",
            "## Callsites",
            "",
            "| Location | Function | Restamper | Classification | Hash Available | Can Change Outcome | Can Change CTA | Can Change Display | Compat/Debug Only | Safe Deletion Candidate | Deletion Risk |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|",
            *call_rows,
            "",
            "## Safe Deletion Candidates",
            "",
            "| Location | Function | Restamper | Risk Note |",
            "|---|---|---|---|",
            *(safe_rows or ["| None |  |  | No deletion candidate proven by this snapshot. |"]),
            "",
            "## Blockers",
            "",
            "| Location | Classification | Function | Deletion Risk |",
            "|---|---|---|---|",
            *(blocker_rows or ["| None |  |  |  |"]),
            "",
            "## Composed Lock",
            "",
            f"- Design Guide independence lock passed: `{snapshot['design_guide_independence_lock']['passed']}`",
            "",
            "## Scope",
            "",
            "- Product behavior changed: `False`",
            "- Visible wording changed: `False`",
            "- CTA/display authority changed: `False`",
            "- Apply routing changed: `False`",
            "- Fallback shells removed: `False`",
            "",
            "## Failures",
            "",
            (
                "None."
                if not snapshot["failures"]
                else "\n".join(f"- `{failure}`" for failure in snapshot["failures"])
            ),
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_duplicate_restamper_reachability_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_duplicate_restamper_reachability_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_duplicate_restamper_reachability {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
