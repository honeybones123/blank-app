"""Proof-only render-stage selected-item mutation snapshot.

The snapshot inspects the render-stage window after `_final_visible_item` is
produced and before the final render selected item is consumed. It classifies
mutations to final item, final visible resolution, guidance debug, button
contract, candidate evidence, exact blockers, and terminal state.
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

CLASS_A = "A. pure compatibility/debug stamp"
CLASS_B = "B. display/card projection from FinalDesignGuidePublication"
CLASS_C = "C. CTA/apply projection from FinalDesignGuidePublication"
CLASS_D = "D. unique resolver truth still not in FinalDesignGuidePublication"
CLASS_E = "E. fallback-only/non-authoritative"

TRACKED_TARGET_HINTS = (
    "_final_visible_item",
    '_final_visible_resolution["item"]',
    "guidance_debug",
    "_final_visible_contract",
    "candidate_search_evidence",
    "exact_blockers_by_family",
    "post_click_design_guide_state",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
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
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _latest_artifact(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"path": None, "snapshot": None}
    path = artifacts[-1]
    return {
        "path": str(path),
        "snapshot": json.loads(path.read_text(encoding="utf-8")),
    }


def _function_node(source: str, function_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return node
    return None


def _segment_lines(source: str, start_line: int, end_line: int) -> list[str]:
    lines = source.splitlines()
    return lines[start_line - 1 : end_line]


def _line_text(lines: list[str], absolute_line: int, start_line: int) -> str:
    index = absolute_line - start_line
    if 0 <= index < len(lines):
        return lines[index].strip()
    return ""


def _target_text(target: ast.AST, source: str) -> str:
    try:
        return ast.get_source_segment(source, target) or ast.dump(target)
    except Exception:
        return ast.dump(target)


def _value_text(node: ast.AST, source: str) -> str:
    try:
        return ast.get_source_segment(source, node) or ast.dump(node)
    except Exception:
        return ast.dump(node)


def _is_interesting_target(text: str, value_text: str) -> bool:
    haystack = f"{text} {value_text}"
    return any(hint in haystack for hint in TRACKED_TARGET_HINTS)


def _context_window(lines: list[str], line_no: int, start_line: int, radius: int = 8) -> str:
    relative = line_no - start_line
    start = max(0, relative - radius)
    end = min(len(lines), relative + radius + 1)
    return "\n".join(lines[start:end])


def _classify_mutation(target: str, value: str, context: str) -> tuple[str, str]:
    combined = f"{target}\n{value}\n{context}"
    lower = combined.lower()
    if (
        "collapsed_guidance_replacement_fallback_only" in combined
        or "fallback_only" in lower
        or "legacy_non_authoritative" in combined
        or "compatibility_only" in combined
    ):
        return CLASS_E, "Mutation is explicitly fallback-only or non-authoritative."
    if (
        "guidance_debug" in target
        and (
            "final_visible_design_guide_resolver" in combined
            or "primary_card_title" in combined
            or "primary_guidance_intent" in combined
            or "selected_action" in combined
        )
    ):
        return CLASS_A, "Guidance debug/session trace stamp; not final publication authority."
    if (
        "final_publication_display" in combined
        or "title_main" in target
        or "title" in target
        or "primary_card_title" in target
        or "render_plan" in target
    ):
        return CLASS_B, "Display/card projection surface."
    if (
        "final_publication_cta" in combined
        or "button_contract" in target
        or "_final_visible_contract" in target
        or "action_payload" in target
        or "selected_action_updates" in target
        or "updates" in target
    ):
        return CLASS_C, "CTA/apply projection surface."
    if (
        "candidate_search_evidence" in target
        or "exact_blockers_by_family" in target
        or "post_click_exact_blockers_by_family" in target
        or "blocker_attempts_by_family" in target
        or "design_guide_terminal_state" in target
        or "post_click_design_guide_state" in target
    ):
        return CLASS_D, "Evidence/blocker/terminal truth is still mutated in render-stage resolver path."
    if (
        "_final_visible_item" in target
        or '_final_visible_resolution["item"]' in target
        or "_final_visible_resolution" in target
    ):
        return CLASS_D, "Selected-item or resolver output truth is still mutated after final resolver."
    return CLASS_A, "Tracked assignment appears to be a debug/compatibility stamp."


def _collect_mutations() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    node = _function_node(source, "_render_fast_design_guidance_panel")
    if node is None:
        return {"error": "_render_fast_design_guidance_panel_not_found", "mutations": []}
    lines = _segment_lines(source, int(node.lineno), int(getattr(node, "end_lineno", node.lineno)))
    function_source = "\n".join(lines)
    resolver_line = None
    binding_line = None
    consume_line = None
    for offset, line in enumerate(lines, start=int(node.lineno)):
        if resolver_line is None and "_final_visible_resolution = resolve_final_visible_design_guide_item(" in line:
            resolver_line = offset
        if binding_line is None and "_final_visible_item = _publish_final_visible_design_guide_contract_binding(" in line:
            binding_line = offset
        if binding_line is not None and consume_line is None and "_record_rendered_design_guide_primary_apply_payload(" in line:
            consume_line = offset
            break
    if binding_line is None:
        return {"error": "final_visible_item_binding_line_not_found", "mutations": []}
    window_end = consume_line or int(getattr(node, "end_lineno", node.lineno))
    mutations: list[dict[str, Any]] = []
    for child in ast.walk(node):
        if not isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        line_no = int(getattr(child, "lineno", 0) or 0)
        if line_no <= binding_line or line_no >= window_end:
            continue
        targets: list[ast.AST]
        if isinstance(child, ast.Assign):
            targets = list(child.targets)
            value_node = child.value
        elif isinstance(child, ast.AnnAssign):
            targets = [child.target]
            value_node = child.value or child.target
        else:
            targets = [child.target]
            value_node = child.value
        value = _value_text(value_node, source)
        for target_node in targets:
            target = _target_text(target_node, source)
            if not _is_interesting_target(target, value):
                continue
            context = _context_window(lines, line_no, int(node.lineno), radius=8)
            classification, reason = _classify_mutation(target, value, context)
            mutations.append(
                {
                    "line": line_no,
                    "target": target,
                    "value": value,
                    "line_text": _line_text(lines, line_no, int(node.lineno)),
                    "classification": classification,
                    "reason": reason,
                    "context_hash": _stable_hash(context),
                }
            )
    mutations.sort(key=lambda row: (int(row["line"]), str(row["target"])))
    return {
        "function": "_render_fast_design_guidance_panel",
        "function_location": f"inputs_page.py:{node.lineno}",
        "resolver_line": resolver_line,
        "final_visible_item_binding_line": binding_line,
        "window_end_line": window_end,
        "window_source_hash": _stable_hash(function_source),
        "mutations": mutations,
    }


def _build_snapshot() -> dict[str, Any]:
    render_same_object = _run("tools/verification/design_guide_render_stage_resolver_same_object_snapshot.py")
    cutover = _run("tools/verification/design_guide_collapsed_replacement_authority_cutover.py")
    lock = _run("tools/verification/design_guide_independence_lock_verifier.py")
    render_artifact = _latest_artifact("design_guide_render_stage_resolver_same_object")
    cutover_artifact = _latest_artifact("design_guide_collapsed_replacement_authority_cutover")
    lock_artifact = _latest_artifact("design_guide_independence_lock")
    collection = _collect_mutations()
    mutations = list(collection.get("mutations") or [])
    class_counts = {
        CLASS_A: sum(1 for row in mutations if row["classification"] == CLASS_A),
        CLASS_B: sum(1 for row in mutations if row["classification"] == CLASS_B),
        CLASS_C: sum(1 for row in mutations if row["classification"] == CLASS_C),
        CLASS_D: sum(1 for row in mutations if row["classification"] == CLASS_D),
        CLASS_E: sum(1 for row in mutations if row["classification"] == CLASS_E),
    }
    unique_truth_mutations = [row for row in mutations if row["classification"] == CLASS_D]
    failures: list[str] = []
    if not render_same_object["passed"]:
        failures.append("render_stage_resolver_same_object_failed")
    if not cutover["passed"]:
        failures.append("collapsed_replacement_authority_cutover_failed")
    if not lock["passed"]:
        failures.append("design_guide_independence_lock_failed")
    if collection.get("error"):
        failures.append(str(collection["error"]))
    if not mutations:
        failures.append("no_tracked_mutations_found")

    status = "PASS" if not failures else "FAIL"
    smallest_truth = (
        "render-stage evidence/blocker/terminal and selected-item mutations"
        if unique_truth_mutations
        else None
    )
    next_slice = (
        "Add a proof object/adapter for render-stage post-resolver item mutation before narrowing."
        if unique_truth_mutations
        else "Narrow render-stage resolver to compatibility/debug stamps."
    )
    proof_surface = {
        "collection": collection,
        "class_counts": class_counts,
        "unique_truth_mutation_lines": [row["line"] for row in unique_truth_mutations],
        "source_artifacts": {
            "render_stage_same_object": render_artifact.get("path"),
            "collapsed_replacement_cutover": cutover_artifact.get("path"),
            "independence_lock": lock_artifact.get("path"),
        },
    }
    return {
        "snapshot_name": "design_guide_render_stage_selected_item_mutation_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "focus_window": {
            "function": collection.get("function"),
            "resolver_line": collection.get("resolver_line"),
            "final_visible_item_binding_line": collection.get("final_visible_item_binding_line"),
            "window_end_line": collection.get("window_end_line"),
        },
        "tracked_targets": list(TRACKED_TARGET_HINTS),
        "mutations": mutations,
        "class_counts": class_counts,
        "summary": {
            "mutation_count": len(mutations),
            "pure_compatibility_debug_stamp": class_counts[CLASS_A],
            "display_card_projection": class_counts[CLASS_B],
            "cta_apply_projection": class_counts[CLASS_C],
            "unique_resolver_truth_not_in_final_publication": class_counts[CLASS_D],
            "fallback_only_non_authoritative": class_counts[CLASS_E],
            "can_narrow_render_bridge_now": not bool(unique_truth_mutations),
            "smallest_remaining_truth": smallest_truth,
            "next_recommended_slice": next_slice,
        },
        "verification": {
            "render_stage_resolver_same_object": render_same_object,
            "collapsed_replacement_authority_cutover": cutover,
            "design_guide_independence_lock": lock,
        },
        "source_artifacts": proof_surface["source_artifacts"],
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = [
        "| `{line}` | `{target}` | `{classification}` | `{reason}` |".format(
            line=row["line"],
            target=str(row["target"]).replace("|", "\\|"),
            classification=row["classification"],
            reason=row["reason"],
        )
        for row in snapshot["mutations"]
    ]
    body = "\n".join(
        [
            "# Design Guide Render-Stage Selected-Item Mutation Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Mutation count: `{snapshot['summary']['mutation_count']}`",
            f"- A pure compatibility/debug stamp: `{snapshot['summary']['pure_compatibility_debug_stamp']}`",
            f"- B display/card projection: `{snapshot['summary']['display_card_projection']}`",
            f"- C CTA/apply projection: `{snapshot['summary']['cta_apply_projection']}`",
            f"- D unique resolver truth: `{snapshot['summary']['unique_resolver_truth_not_in_final_publication']}`",
            f"- E fallback-only/non-authoritative: `{snapshot['summary']['fallback_only_non_authoritative']}`",
            f"- Can narrow render bridge now: `{snapshot['summary']['can_narrow_render_bridge_now']}`",
            f"- Smallest remaining truth: `{snapshot['summary']['smallest_remaining_truth']}`",
            f"- Next recommended slice: {snapshot['summary']['next_recommended_slice']}",
            "",
            "## Focus Window",
            "",
            f"- Function: `{snapshot['focus_window']['function']}`",
            f"- Resolver line: `{snapshot['focus_window']['resolver_line']}`",
            f"- Final visible item binding line: `{snapshot['focus_window']['final_visible_item_binding_line']}`",
            f"- Window end line: `{snapshot['focus_window']['window_end_line']}`",
            "",
            "## Mutations",
            "",
            "| Line | Target | Classification | Reason |",
            "|---:|---|---|---|",
            *rows,
            "",
            "## Source Artifacts",
            "",
            f"- Render-stage same-object proof: `{snapshot['source_artifacts']['render_stage_same_object']}`",
            f"- Collapsed replacement cutover: `{snapshot['source_artifacts']['collapsed_replacement_cutover']}`",
            f"- Independence lock: `{snapshot['source_artifacts']['independence_lock']}`",
            "",
            "## Scope",
            "",
            "- Product behavior changed: `False`",
            "- This is proof-only.",
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
    json_path = ARTIFACT_DIR / f"design_guide_render_stage_selected_item_mutation_snapshot_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_stage_selected_item_mutation_snapshot_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_render_stage_selected_item_mutation_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
