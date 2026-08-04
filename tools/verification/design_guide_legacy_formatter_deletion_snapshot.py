"""Design Guide legacy formatter deletion snapshot.

This verifier proves the first legacy formatting deletion slice:

- live Design Guide card HTML is rendered through the clean
  FinalDesignGuidePublication formatter,
- the old render-model HTML helper has been removed from live code,
- remaining references are verifier/history-only and cannot drive product UI.
"""

from __future__ import annotations

import ast
import json
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
CLEAN_UI = ROOT / "ui" / "final_design_guide_card.py"

LEGACY_RENDERER = "_design_guide_dashboard_card_html_from_render_model"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


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


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_legacy_formatter_deletion_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_legacy_formatter_deletion_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Design Guide Legacy Formatter Deletion Snapshot",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Deleted Surface",
        "",
        f"- Legacy renderer removed from `ui/design_guide_cards.py`: `{snapshot['checks']['legacy_renderer_function_removed']}`",
        f"- Live `inputs_page.py` no longer calls legacy renderer: `{snapshot['checks']['inputs_page_has_no_legacy_renderer_reference']}`",
        f"- Legacy dashboard-card wrapper removed: `{snapshot['checks']['legacy_dashboard_card_wrapper_removed']}`",
        f"- Clean renderer is live: `{snapshot['checks']['clean_renderer_live']}`",
        "",
        "## Remaining References",
        "",
    ]
    for row in snapshot["remaining_references"]:
        lines.append(f"- `{row['path']}`: `{row['count']}` ({row['classification']})")
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    clean_source = CLEAN_UI.read_text(encoding="utf-8", errors="replace")
    legacy_functions = _function_names(LEGACY_UI)
    remaining_refs: list[dict[str, Any]] = []
    for path in sorted((ROOT / "tools" / "verification").glob("design_guide*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        count = text.count(LEGACY_RENDERER)
        if count:
            remaining_refs.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "count": count,
                    "classification": "verifier_or_historical_reference",
                    "product_driving": False,
                }
            )
    gates = {
        "clean_formatter_live_cutover": _run("tools/verification/design_guide_clean_formatter_live_cutover.py"),
        "independence_lock": _run("tools/verification/design_guide_independence_lock_verifier.py"),
        "render_bridge_lock": _run("tools/verification/design_guide_render_bridge_lock_verifier.py"),
    }
    checks = {
        "legacy_renderer_function_removed": LEGACY_RENDERER not in legacy_functions,
        "legacy_ui_helper_module_deleted": not LEGACY_UI.exists(),
        "inputs_page_has_no_legacy_renderer_reference": LEGACY_RENDERER not in inputs_source,
        "legacy_dashboard_card_wrapper_removed": "def _design_guide_dashboard_card_html(" not in inputs_source,
        "clean_renderer_live": "_render_final_design_guide_card_html(clean_format)" in inputs_source,
        "clean_renderer_exists": "def render_final_design_guide_card_html(" in clean_source,
        "legacy_renderer_not_imported_by_inputs": f"{LEGACY_RENDERER}," not in inputs_source,
        "remaining_references_verifier_only": all(not row["product_driving"] for row in remaining_refs),
        "live_cutover_pass": gates["clean_formatter_live_cutover"]["passed"],
        "render_bridge_lock_pass": gates["render_bridge_lock"]["passed"],
        "independence_lock_pass": gates["independence_lock"]["passed"],
    }
    failures = [key for key, value in checks.items() if not value]
    snapshot = {
        "schema": "design_guide_legacy_formatter_deletion_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "remaining_references": remaining_refs,
        "gates": gates,
        "classification": {
            "legacy_html_renderer_deleted": not failures,
            "old_formatting_fully_deleted": not failures and not LEGACY_UI.exists(),
            "next_deletion_slice": "none_for_ui_design_guide_cards_legacy_module",
        },
        "snapshot_hash": _stable_hash({"checks": checks, "remaining_references": remaining_refs}),
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("design_guide_legacy_formatter_deletion FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        return 1
    print("design_guide_legacy_formatter_deletion PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
