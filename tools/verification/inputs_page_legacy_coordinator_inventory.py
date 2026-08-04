from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
SHELL_PAGE = ROOT / "inputs_page_shell.py"

TRACKED_NAMES = {
    "_render_fast_design_guidance_panel",
    "render_inputs",
    "_render_fresh_design_guide_panel",
    "_render_inputs_summary_expanders_and_tables",
    "handle_apply_buttons",
    "handle_auto_design",
    "_render_guidance_secondary_items",
    "_render_section_2d_diagram_block",
    "_render_3d_diagram_block",
    "_render_fast_model_block",
    "_render_fast_materials_expander",
    "_render_design_guide_component_cta",
    "_render_design_guide_post_apply_banner",
    "_compute_design_guidance_items",
    "_compute_design_guidance_items_core",
    "run_one_click_auto_design",
    "_solve_one_click_to_target",
    "_apply_resolved_candidate_payload",
}

SHELL_WRAPPER_NAMES = {
    "render_inputs_widgets",
    "apply_widget_updates",
    "render_summary_section",
    "render_batch_design_section",
    "render_design_guide_section",
    "render_diagram_section",
    "render_calculation_section",
    "render_legacy_inputs_page",
}


@dataclass(frozen=True)
class FunctionRecord:
    name: str
    qualname: str
    line: int
    end_line: int
    size: int
    nested_in: str


class FunctionVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.records: list[FunctionRecord] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        nested_in = ".".join(self.stack)
        qualname = ".".join([*self.stack, node.name]) if self.stack else node.name
        end_line = int(getattr(node, "end_lineno", node.lineno))
        self.records.append(
            FunctionRecord(
                name=node.name,
                qualname=qualname,
                line=int(node.lineno),
                end_line=end_line,
                size=end_line - int(node.lineno) + 1,
                nested_in=nested_in,
            )
        )
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def _load_functions(path: Path) -> list[FunctionRecord]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    visitor = FunctionVisitor()
    visitor.visit(tree)
    return visitor.records


def _iter_scan_files() -> Iterable[Path]:
    roots = [ROOT / "app.py", INPUTS_PAGE, SHELL_PAGE, ROOT / "tools" / "verification"]
    for root in roots:
        if root.is_file():
            yield root
        elif root.is_dir():
            for path in root.rglob("*.py"):
                if "__pycache__" not in path.parts:
                    yield path


def _callers(name: str, *, max_hits: int = 18) -> list[str]:
    pattern = re.compile(rf"\b{re.escape(name)}\s*\(")
    hits: list[str] = []
    for path in _iter_scan_files():
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            if not pattern.search(line):
                continue
            if re.match(rf"\s*def\s+{re.escape(name)}\s*\(", line):
                continue
            rel = path.relative_to(ROOT)
            hits.append(f"{rel}:{line_no}")
            if len(hits) >= max_hits:
                return hits
    return hits


def _classify(record: FunctionRecord) -> str:
    if record.name == "render_inputs" and record.line < 9000:
        return "dead compatibility alias"
    if record.name in {"_render_fast_design_guidance_panel", "render_inputs"}:
        return "split required"
    if record.name in {"handle_apply_buttons", "handle_auto_design"}:
        return "large callback runner; split required"
    if record.name in {"_render_fresh_design_guide_panel", "_render_inputs_summary_expanders_and_tables"}:
        return "nested render coordinator; split required"
    if record.name.startswith("_render_"):
        return "render coordinator"
    if record.name in {
        "_compute_design_guidance_items",
        "_compute_design_guidance_items_core",
        "run_one_click_auto_design",
        "_solve_one_click_to_target",
        "_apply_resolved_candidate_payload",
    }:
        return "engineering/apply bridge; not shell-owned"
    return "coordinator"


def _owned_sections(name: str) -> list[str]:
    sections = {
        "_render_fast_design_guidance_panel": ["Design Guide", "CTA", "publication", "browser state", "debug", "loading"],
        "render_inputs": ["page composition", "widgets", "summary", "batch design", "design guide", "diagrams", "calculations", "footer"],
        "_render_fresh_design_guide_panel": ["Design Guide publication", "Design Guide recovery", "Design Guide slot"],
        "_render_inputs_summary_expanders_and_tables": ["summary render"],
        "handle_apply_buttons": ["Apply routing", "CTA execution", "session mutation"],
        "handle_auto_design": ["auto design trigger", "rerun orchestration"],
        "_render_guidance_secondary_items": ["Design Guide secondary items", "compatibility rendering"],
        "_render_section_2d_diagram_block": ["2D diagram render"],
        "_render_3d_diagram_block": ["3D diagram render"],
        "_render_fast_model_block": ["model inputs", "diagram previews"],
        "_render_fast_materials_expander": ["materials widgets"],
    }
    return sections.get(name, [])


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    input_records = _load_functions(INPUTS_PAGE)
    shell_records = _load_functions(SHELL_PAGE) if SHELL_PAGE.exists() else []

    tracked_records = [
        record
        for record in input_records
        if record.name in TRACKED_NAMES or record.size >= 500
    ]
    tracked_records.sort(key=lambda item: (-item.size, item.line, item.qualname))

    shell_wrappers = [
        record
        for record in shell_records
        if record.name in SHELL_WRAPPER_NAMES
    ]
    shell_wrappers.sort(key=lambda item: item.line)

    payload = {
        "audit": "inputs_page_legacy_coordinator_inventory",
        "timestamp": timestamp,
        "inputs_page_line_count": len(INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").splitlines()),
        "inputs_page_shell_line_count": (
            len(SHELL_PAGE.read_text(encoding="utf-8", errors="replace").splitlines())
            if SHELL_PAGE.exists()
            else 0
        ),
        "tracked_coordinators": [
            {
                "name": record.name,
                "qualname": record.qualname,
                "line": record.line,
                "end_line": record.end_line,
                "size": record.size,
                "current_callers": _callers(record.name),
                "owned_sections": _owned_sections(record.name),
                "classification": _classify(record),
                "progress_status": "AUDITED",
                "engineering_responsibilities": (
                    "present in physical page; do not move during shell composition"
                    if _classify(record) == "engineering/apply bridge; not shell-owned"
                    else "none identified by inventory"
                ),
            }
            for record in tracked_records
        ],
        "shell_wrappers": [
            {
                "name": record.name,
                "line": record.line,
                "size": record.size,
                "classification": "TEMPORARY_LEGACY_COORDINATOR",
                "progress_status": "AUDITED",
            }
            for record in shell_wrappers
        ],
        "blocking_gates": [
            "inputs_session_snapshot_boundary_lock currently reports gaps",
            "design_brain_family_process_and_churn_lock currently reports churn_guard_lock incomplete",
            "inputs_page_final_composition_ownership_lock still permits old page shell ownership and is not a deletion-phase lock",
            "inputs_page_final_shell_deletion_lock is blocked until routing, wrappers, and old page deletion are complete",
        ],
        "next_safe_slice": "resolve blocker gates, then split one render-only coordinator behind browser parity",
    }

    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    progress_dir = ROOT / "artifacts" / "progress"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    progress_dir.mkdir(parents=True, exist_ok=True)

    json_path = verification_dir / f"inputs_page_legacy_coordinator_inventory_{timestamp}.json"
    report_path = audit_dir / f"inputs_page_legacy_coordinator_inventory_{timestamp}.md"
    progress_path = progress_dir / "inputs_page_shell_migration_progress.md"

    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_render_markdown(payload), encoding="utf-8")
    progress_path.write_text(_render_progress(payload), encoding="utf-8")

    print("INPUTS_PAGE_LEGACY_COORDINATOR_INVENTORY_COMPLETE")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(f"progress={progress_path}")
    return 0


def _render_markdown(payload: dict) -> str:
    rows = payload["tracked_coordinators"]
    lines = [
        "# Inputs Page Legacy Coordinator Inventory",
        "",
        f"Generated: `{payload['timestamp']}`",
        "",
        f"`inputs_page.py` lines: `{payload['inputs_page_line_count']}`",
        f"`inputs_page_shell.py` lines: `{payload['inputs_page_shell_line_count']}`",
        "",
        "## Blocking Gates",
        "",
        *[f"- {gate}" for gate in payload["blocking_gates"]],
        "",
        "## Tracked Coordinators",
        "",
        "| Status | Name | Line | Size | Classification | Owned Sections | Callers |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {status} | `{name}` | {line} | {size} | {classification} | {sections} | {callers} |".format(
                status=row["progress_status"],
                name=row["qualname"],
                line=row["line"],
                size=row["size"],
                classification=row["classification"],
                sections=", ".join(row["owned_sections"]) or "-",
                callers=", ".join(row["current_callers"]) or "-",
            )
        )
    lines.extend(
        [
            "",
            "## Shell Wrappers",
            "",
            "| Status | Name | Line | Size | Classification |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in payload["shell_wrappers"]:
        lines.append(
            f"| {row['progress_status']} | `{row['name']}` | {row['line']} | {row['size']} | {row['classification']} |"
        )
    lines.extend(["", f"Next safe slice: `{payload['next_safe_slice']}`", ""])
    return "\n".join(lines)


def _render_progress(payload: dict) -> str:
    lines = [
        "# Inputs Page Shell Migration Progress",
        "",
        f"Last updated: `{payload['timestamp']}`",
        "",
        "Statuses: `NOT_AUDITED`, `AUDITED`, `SPLITTING`, `COORDINATOR_LOCKED`, `WRAPPER_REMOVED`, `LEGACY_DELETED`.",
        "",
        "## Current Blockers",
        "",
        *[f"- {gate}" for gate in payload["blocking_gates"]],
        "",
        "## Coordinator Tracker",
        "",
        "| Status | Coordinator | Size | Classification |",
        "| --- | --- | ---: | --- |",
    ]
    for row in payload["tracked_coordinators"]:
        lines.append(
            f"| {row['progress_status']} | `{row['qualname']}` | {row['size']} | {row['classification']} |"
        )
    lines.extend(
        [
            "",
            "## Wrapper Tracker",
            "",
            "| Status | Wrapper | Classification |",
            "| --- | --- | --- |",
        ]
    )
    for row in payload["shell_wrappers"]:
        lines.append(f"| {row['progress_status']} | `{row['name']}` | `{row['classification']}` |")
    lines.extend(["", f"Next safe slice: `{payload['next_safe_slice']}`", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
