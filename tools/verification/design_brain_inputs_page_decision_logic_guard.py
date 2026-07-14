"""Ratchet guard for Design Brain decision authority in inputs_page.py.

This does not claim every historical decision-shaped helper has already been
deleted. It freezes the current set as a deletion backlog and fails if new or
edited decision-shaped logic appears in `inputs_page.py` without an extraction
proof.
"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
AGENTS = ROOT / "AGENTS.md"
BASELINE = ROOT / "tools" / "verification" / "design_brain_inputs_page_decision_logic_guard_baseline.json"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDITS_DIR = ROOT / "artifacts" / "audits"

DECISION_NAME_RE = re.compile(
    r"(candidate|classif|cleanup|contract|cta|exact|family|govern|ladder|"
    r"one_click|optim|publish|rank|recommend|repair|resolve|score|select|"
    r"solver|target_band|tighten)",
    re.IGNORECASE,
)

AUTHORITY_BODY_RE = re.compile(
    r"(BENDING_|SHEAR_|GEOMETRY_DETAILING|SERVICEABILITY|TARGET_BAND|"
    r"EXACT_STOP|NO_VALID|selected_family|candidate_search|ranking_rule|"
    r"ladder|contract|target_band|exact_stop|blocked_reason|cta_intent)",
    re.IGNORECASE,
)

SHELL_ONLY_PREFIXES = (
    "_render_",
    "_record_",
    "_stamp_",
    "_trace_",
    "_debug_",
    "_log_",
)

SHELL_EXACT_NAMES = {
    "_direct_target_band_diag_enabled",
    "_direct_target_band_diag_trace",
    "_apply_button_binding_tail_trace_enabled",
    "_apply_button_binding_tail_trace_path",
    "_apply_button_binding_tail_trace_counts",
    "_apply_button_binding_tail_trace_items",
    "_apply_button_binding_tail_trace_binding_result",
    "_apply_button_binding_tail_trace_event",
    "_apply_final_visible_contract_binding_cta_authority_projection",
    "_apply_final_visible_combined_outside_target_blocker_projection",
}

RULE_REQUIRED_SNIPPETS = (
    "Streamlit/page shell only",
    "must not own Design Brain decision authority",
    "move the decision into the relevant `design_brain` contract/runtime/service",
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _function_rows() -> list[dict[str, Any]]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    lines = source.splitlines()
    tree = ast.parse(source)
    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        segment = "\n".join(lines[node.lineno - 1 : (node.end_lineno or node.lineno)])
        name_matches = bool(DECISION_NAME_RE.search(node.name))
        body_matches = bool(AUTHORITY_BODY_RE.search(segment))
        if not (name_matches or body_matches):
            continue
        if node.name in SHELL_EXACT_NAMES or node.name.startswith(SHELL_ONLY_PREFIXES):
            classification = "approved_shell_pattern"
        else:
            classification = "decision_shaped_backlog"
        rows.append(
            {
                "function": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
                "classification": classification,
                "name_matches_decision_pattern": name_matches,
                "body_matches_authority_pattern": body_matches,
                "source_hash": _stable_hash(segment),
            }
        )
    rows.sort(key=lambda row: (row["classification"], row["function"], row["line_start"]))
    return rows


def _load_baseline() -> dict[str, Any] | None:
    if not BASELINE.exists():
        return None
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _baseline_entries(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        f"{row['function']}:{row['line_start']}": {
            "function": row["function"],
            "line_start": row["line_start"],
            "classification": row["classification"],
            "source_hash": row["source_hash"],
        }
        for row in rows
    }


def _write_baseline(rows: list[dict[str, Any]]) -> None:
    payload = {
        "schema": "design_brain_inputs_page_decision_logic_guard_baseline.v1",
        "generated_at": _timestamp(),
        "purpose": (
            "Current decision-shaped inputs_page.py inventory. These entries are a deletion "
            "backlog, not permission to add or edit page-owned Design Brain decision authority."
        ),
        "baseline_entries": _baseline_entries(rows),
    }
    payload["baseline_hash"] = _stable_hash(payload["baseline_entries"])
    BASELINE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _compare_to_baseline(rows: list[dict[str, Any]], baseline: dict[str, Any] | None) -> dict[str, Any]:
    current = _baseline_entries(rows)
    if baseline is None:
        return {
            "baseline_found": False,
            "new_entries": sorted(current),
            "removed_entries": [],
            "changed_entries": [],
            "baseline_hash": None,
            "current_hash": _stable_hash(current),
        }
    expected = dict(baseline.get("baseline_entries") or {})
    new_entries = sorted(key for key in current if key not in expected)
    removed_entries = sorted(key for key in expected if key not in current)
    changed_entries = sorted(
        key
        for key in current
        if key in expected
        and current[key].get("source_hash") != expected[key].get("source_hash")
    )
    return {
        "baseline_found": True,
        "new_entries": new_entries,
        "removed_entries": removed_entries,
        "changed_entries": changed_entries,
        "baseline_hash": baseline.get("baseline_hash"),
        "current_hash": _stable_hash(current),
    }


def _rule_doc_checks() -> dict[str, bool]:
    text = AGENTS.read_text(encoding="utf-8", errors="replace") if AGENTS.exists() else ""
    return {
        "agents_rule_present": all(snippet in text for snippet in RULE_REQUIRED_SNIPPETS),
        "forbids_inputs_page_decision_authority": "Forbidden decision authority in `inputs_page.py`" in text,
        "requires_design_brain_move_or_shell_proof": "prove it is only render/session/apply/debug shell code" in text,
    }


def _write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = payload["generated_at"].replace(":", "-")
    json_path = VERIFICATION_DIR / f"design_brain_inputs_page_decision_logic_guard_{stamp}.json"
    report_path = AUDITS_DIR / f"design_brain_inputs_page_decision_logic_guard_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    inventory = payload["inventory"]
    comparison = payload["baseline_comparison"]
    lines = [
        "# Design Brain Inputs Page Decision Logic Guard",
        "",
        f"Status: `{payload['status']}`",
        f"Guard mode: `{payload['guard_mode']}`",
        f"Snapshot hash: `{payload['snapshot_hash']}`",
        "",
        "## Rule",
        "",
        "`inputs_page.py` may be a page shell, renderer, session/debug store, and apply router. "
        "It must not own Design Brain decision authority.",
        "",
        "## Counts",
        "",
        f"- Decision-shaped backlog entries: `{inventory['decision_shaped_backlog_count']}`",
        f"- Approved shell-pattern entries: `{inventory['approved_shell_pattern_count']}`",
        f"- New decision-shaped entries since baseline: `{len(comparison['new_entries'])}`",
        f"- Changed baseline entries: `{len(comparison['changed_entries'])}`",
        f"- Removed baseline entries: `{len(comparison['removed_entries'])}`",
        "",
        "## Enforcement Result",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a ratchet. Existing decision-shaped entries are treated as deletion backlog. "
            "New or edited entries fail the guard unless the change extracts/deletes the page-owned "
            "decision or proves the function is shell-only.",
            "",
            "## Next Action",
            "",
            payload["next_action"],
        ]
    )
    if comparison["new_entries"] or comparison["changed_entries"]:
        lines.extend(["", "## Blocking Entries", ""])
        for key in comparison["new_entries"]:
            lines.append(f"- new: `{key}`")
        for key in comparison["changed_entries"]:
            lines.append(f"- changed: `{key}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()

    rows = _function_rows()
    if args.write_baseline:
        _write_baseline(rows)

    baseline = _load_baseline()
    comparison = _compare_to_baseline(rows, baseline)
    rule_checks = _rule_doc_checks()
    inventory = {
        "decision_shaped_backlog_count": sum(
            1 for row in rows if row["classification"] == "decision_shaped_backlog"
        ),
        "approved_shell_pattern_count": sum(
            1 for row in rows if row["classification"] == "approved_shell_pattern"
        ),
        "rows": rows,
    }
    checks = {
        **rule_checks,
        "baseline_found": comparison["baseline_found"],
        "no_new_decision_shaped_inputs_page_entries": not comparison["new_entries"],
        "no_changed_decision_shaped_inputs_page_entries": not comparison["changed_entries"],
    }
    passed = all(checks.values())
    payload = {
        "schema": "design_brain_inputs_page_decision_logic_guard.v1",
        "generated_at": _timestamp(),
        "status": "PASS" if passed else "FAIL",
        "guard_mode": "ratchet_no_new_or_edited_inputs_page_decision_authority",
        "inventory": inventory,
        "baseline_comparison": comparison,
        "checks": checks,
        "next_action": (
            "Keep deleting/extracting existing backlog entries one proof-backed slice at a time."
            if passed
            else "Do not keep the changed/new decision-shaped page code. Extract it into Design Brain or prove it is shell-only, then refresh the baseline only for removed/extracted code."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "status": payload["status"],
            "comparison": comparison,
            "counts": {
                key: value for key, value in inventory.items() if key != "rows"
            },
        }
    )
    json_path, report_path = _write_artifacts(payload)
    print(f"design_brain_inputs_page_decision_logic_guard {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if comparison["new_entries"]:
        print("new_entries=" + ",".join(comparison["new_entries"]))
    if comparison["changed_entries"]:
        print("changed_entries=" + ",".join(comparison["changed_entries"]))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
