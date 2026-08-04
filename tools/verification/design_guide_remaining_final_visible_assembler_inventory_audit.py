"""Inventory remaining page-owned final-visible result assemblers."""

from __future__ import annotations

from datetime import datetime
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(source: str, function_name: str) -> tuple[str, int, int]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name}")


def _classify(name: str, function_source: str, live_calls: int, controller_source: str) -> str:
    if live_calls == 0:
        return "A. deletion proof candidate"
    if name == "_assemble_final_visible_active_action_result":
        return "B. needs controller result object and trace parity"
    if name == "_assemble_final_visible_low_shear_resolution_result":
        return "C. needs low-shear route ownership audit"
    if name == "_assemble_final_visible_combined_low_util_blocker_or_best_safe_result":
        return "C. needs combined low-util blocker/best-safe ownership audit"
    if name == "_assemble_final_visible_zero_shear_demand_accepted_result":
        return "C. needs zero-shear accepted route ownership audit"
    if name.replace("_assemble_", "build_design_guide_controller_") in controller_source:
        return "B. needs focused trace parity"
    if ".update(" in function_source or "contract.update(" in function_source:
        return "C. mutates item/contract before return"
    return "D. unknown / needs proof"


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    names = sorted(set(re.findall(r"^def (_assemble_final_visible_[A-Za-z0-9_]+)\(", source, re.M)))
    rows = []
    for name in names:
        function_source, start, end = _function_source(source, name)
        live_calls = source.count(f"{name}(") - 1
        rows.append(
            {
                "assembler": name,
                "start_line": start,
                "end_line": end,
                "line_count": end - start + 1,
                "live_call_count": live_calls,
                "mutates_item_or_contract": (
                    ".update(" in function_source
                    or "contract.update(" in function_source
                    or "active_item[" in function_source
                ),
                "returns_standard_result_shape": all(
                    token in function_source
                    for token in ['"item"', '"overview"', '"presentation"', '"render_reason"', '"debug"']
                ),
                "classification": _classify(name, function_source, live_calls, controller_source),
            }
        )
    return {
        "remaining_assembler_count": len(rows),
        "rows": rows,
        "safe_deletion_candidates": [
            row["assembler"] for row in rows if str(row.get("classification", "")).startswith("A.")
        ],
        "next_recommended_slice": (
            "final_visible_assembler_cleanup_complete"
            if not rows
            else "deletion_proof_for_zero_live_final_visible_assemblers"
            if any(str(row.get("classification", "")).startswith("A.") for row in rows)
            else (
                "active_action_result_controller_object_snapshot"
                if any(row["assembler"] == "_assemble_final_visible_active_action_result" for row in rows)
                else "inspect_next_single_callsite_assembler"
            )
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("rows") or [])
    return {
        "inventory_state_known": isinstance(capture.get("rows"), list),
        "no_unknown_without_classification": all(bool(row.get("classification")) for row in rows),
        "deletion_candidates_are_findings_only": True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    rows = list(capture.get("rows") or [])
    lines = [
        "# Design Guide Remaining Final-Visible Assembler Inventory Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Remaining assemblers: `{capture.get('remaining_assembler_count')}`",
        f"Next recommended slice: `{capture.get('next_recommended_slice')}`",
        "",
        "## Inventory",
        "",
        "| Assembler | Live calls | Lines | Classification |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {assembler} | {live_call_count} | {line_count} | {classification} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "No page-owned `_assemble_final_visible_*` functions remain in `inputs_page.py`."
                if not rows
                else "No deletion is performed by this audit. The next safe slice is to build a "
                "deletion proof for one zero-live assembler, then delete only that proven-dead function."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_remaining_final_visible_assembler_inventory_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_remaining_final_visible_assembler_inventory_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_remaining_final_visible_assembler_inventory {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
