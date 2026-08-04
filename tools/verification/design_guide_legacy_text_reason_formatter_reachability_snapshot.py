"""Design Guide legacy text/reason formatter reachability snapshot.

This verifier proves the next deletion boundary after the old Design Guide card
HTML renderer was removed. It intentionally does not claim that every text or
reason helper is dead: several helpers still feed live product paths and must
stay until a clean formatter owns those exact surfaces.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
LEGACY_UI = ROOT / "ui" / "design_guide_cards.py"

OLD_RENDERER = "_design_guide_dashboard_card_html_from_render_model"
OLD_WRAPPER = "_design_guide_dashboard_card_html"

HELPERS = {
    "_design_guide_format_mm_value": {
        "expected": "deleted",
        "reason": "unused after clean formatter cutover",
    },
    "_design_guide_text_html": {
        "expected": "deleted",
        "reason": "replaced by ui.final_design_guide_card.render_final_design_guide_text_html",
    },
    "_guidance_card_why_body": {
        "expected": "deleted",
        "reason": "replaced by design_brain.final_design_guide_formatter.resolve_final_design_guide_why_body",
    },
    "_design_guide_clean_main_card_text": {
        "expected": "deleted",
        "reason": "replaced by design_brain.final_design_guide_formatter.clean_final_design_guide_reason_text",
    },
    "_design_guide_failure_engineering_cause_text": {
        "expected": "deleted",
        "reason": "replaced by design_brain.final_design_guide_formatter.resolve_final_design_guide_failure_engineering_cause_text",
    },
    "_design_guide_card_tone_for_status": {
        "expected": "deleted",
        "reason": "replaced by design_brain.final_design_guide_formatter.resolve_final_design_guide_status_tone",
    },
    "_design_guide_reason_display_rows": {
        "expected": "deleted",
        "reason": "replaced by design_brain.final_design_guide_formatter.build_final_design_guide_reason_display_rows",
    },
    "_design_guide_preview_display_rows": {
        "expected": "deleted",
        "reason": "replaced by design_brain.final_design_guide_formatter.build_final_design_guide_preview_display_rows",
    },
    "_design_guide_card_data_attributes_html": {
        "expected": "deleted",
        "reason": "replaced by ui.final_design_guide_card.render_final_design_guide_data_attributes_html",
    },
    "_assemble_design_guide_card_data_attribute_scalars": {
        "expected": "deleted",
        "reason": "replaced by design_brain.design_guide_card_attrs.assemble_final_design_guide_card_data_attribute_scalars",
    },
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def _line_refs(path: Path, symbol: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if not path.exists():
        return refs
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])")
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if pattern.search(line):
            refs.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "line": idx,
                    "text": line.strip(),
                }
            )
    return refs


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
        "stdout_tail": proc.stdout.strip().splitlines()[-6:],
        "stderr_tail": proc.stderr.strip().splitlines()[-6:],
    }


def _classify(symbol: str, defined: bool, input_refs: list[dict[str, Any]], ui_refs: list[dict[str, Any]]) -> str:
    input_product_refs = [ref for ref in input_refs if not ref["text"].startswith("#")]
    definition_only = len(ui_refs) == (1 if defined else 0)
    if not defined and not input_product_refs:
        return "deleted"
    if not input_product_refs and definition_only:
        return "safe_deletion_candidate"
    if input_product_refs:
        return "live_product_callsite"
    return "verifier_or_internal_only"


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_legacy_text_reason_formatter_reachability_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_legacy_text_reason_formatter_reachability_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Design Guide Legacy Text/Reason Formatter Reachability Snapshot",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Summary",
        "",
        f"- Deleted helpers: `{snapshot['summary']['deleted_count']}`",
        f"- Live product helpers: `{snapshot['summary']['live_product_count']}`",
        f"- Safe deletion candidates remaining: `{snapshot['summary']['safe_deletion_candidate_count']}`",
        "",
        "## Helper Classification",
        "",
    ]
    for row in snapshot["helpers"]:
        lines.extend(
            [
                f"### `{row['symbol']}`",
                f"- classification: `{row['classification']}`",
                f"- expected: `{row['expected']}`",
                f"- defined in `ui/design_guide_cards.py`: `{row['defined']}`",
                f"- `inputs_page.py` references: `{row['inputs_ref_count']}`",
                f"- reason: {row['reason']}",
                "",
            ]
        )
    lines.extend(["## Gates", ""])
    for name, gate in snapshot["gates"].items():
        lines.append(f"- `{name}`: `{'PASS' if gate['passed'] else 'FAIL'}`")
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    clean_ui_source = (ROOT / "ui" / "final_design_guide_card.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    ui_functions = _function_names(LEGACY_UI)
    rows: list[dict[str, Any]] = []
    for symbol, spec in HELPERS.items():
        input_refs = _line_refs(INPUTS_PAGE, symbol)
        ui_refs = _line_refs(LEGACY_UI, symbol)
        defined = symbol in ui_functions
        classification = _classify(symbol, defined, input_refs, ui_refs)
        rows.append(
            {
                "symbol": symbol,
                "classification": classification,
                "expected": spec["expected"],
                "matches_expected": classification == spec["expected"],
                "reason": spec["reason"],
                "defined": defined,
                "inputs_ref_count": len(input_refs),
                "ui_ref_count": len(ui_refs),
                "inputs_refs": input_refs,
                "ui_refs": ui_refs,
            }
        )

    gates = {
        "legacy_formatter_deletion": _run("tools/verification/design_guide_legacy_formatter_deletion_snapshot.py"),
        "clean_formatter_live_cutover": _run("tools/verification/design_guide_clean_formatter_live_cutover.py"),
        "render_bridge_lock": _run("tools/verification/design_guide_render_bridge_lock_verifier.py"),
        "independence_lock": _run("tools/verification/design_guide_independence_lock_verifier.py"),
    }
    checks = {
        "old_renderer_absent_from_inputs": OLD_RENDERER not in inputs_source,
        "old_wrapper_absent_from_inputs": f"def {OLD_WRAPPER}(" not in inputs_source,
        "legacy_ui_helper_module_deleted": not LEGACY_UI.exists(),
        "clean_text_renderer_exists": "def render_final_design_guide_text_html(" in clean_ui_source,
        "inputs_uses_clean_text_renderer": "_render_final_design_guide_text_html(" in inputs_source,
        "legacy_text_renderer_absent_from_inputs": not re.search(
            r"(?<![A-Za-z0-9_])_design_guide_text_html(?![A-Za-z0-9_])",
            inputs_source,
        ),
        "all_helpers_match_expected_classification": all(row["matches_expected"] for row in rows),
        "no_safe_deletion_candidates_left_in_this_set": all(
            row["classification"] != "safe_deletion_candidate" for row in rows
        ),
        "legacy_deletion_gate_pass": gates["legacy_formatter_deletion"]["passed"],
        "clean_live_cutover_pass": gates["clean_formatter_live_cutover"]["passed"],
        "render_bridge_lock_pass": gates["render_bridge_lock"]["passed"],
        "independence_lock_pass": gates["independence_lock"]["passed"],
    }
    failures = [key for key, value in checks.items() if not value]
    snapshot = {
        "schema": "design_guide_legacy_text_reason_formatter_reachability.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "helpers": rows,
        "summary": {
            "deleted_count": sum(row["classification"] == "deleted" for row in rows),
            "live_product_count": sum(row["classification"] == "live_product_callsite" for row in rows),
            "safe_deletion_candidate_count": sum(
                row["classification"] == "safe_deletion_candidate" for row in rows
            ),
            "next_deletion_slice": "none_in_text_reason_helper_set_until_live_product_callsites_move",
        },
        "gates": gates,
        "snapshot_hash": _stable_hash({"checks": checks, "helpers": rows}),
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("design_guide_legacy_text_reason_formatter_reachability FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        return 1
    print("design_guide_legacy_text_reason_formatter_reachability PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
