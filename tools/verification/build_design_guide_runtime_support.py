"""Mechanically extract the last Design Guide runtime-support closure.

This is a migration utility, not a production dependency.  Production imports
the generated module and never reads the archived page.
"""

from __future__ import annotations

import ast
import builtins
import importlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = (
    ROOT
    / "artifacts"
    / "audits"
    / "legacy_inputs_page_removed_2026-07-19T06-12.py"
)
TARGET = (
    ROOT
    / "inputs_application"
    / "page_runtime"
    / "design_guide_runtime_support.py"
)

ROOT_SYMBOLS = {
    "DESIGN_GUIDE_INTENTS",
    "DESIGN_GUIDE_LAST_AUTO_GEOM_KEY",
    "DESIGN_GUIDE_LAST_USER_GEOM_KEY",
    "DESIGN_GUIDE_REFERENCE_B_KEY",
    "DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT",
    "_apply_guidance_ui_state",
    "_derived_guidance_title_from_updates",
    "_design_guide_primary_uses_success_style",
    "_design_guide_render_plan",
    "_design_guide_step_history_debug_summary",
    "_design_guide_text_html",
    "_final_publication_cta_authority_payload",
    "_get_design_guide_fp",
    "_guidance_before_after_text",
    "_guidance_card_label",
    "_guidance_card_proposed_change_html",
    "_guidance_card_why_body",
    "_guidance_primary_compact_lines_html",
    "_label_consistent_with_updates_families",
    "_normalise_invalid_shear_state_updates",
    "_one_click_feedback_cta_state",
    "_overview_debug_summary",
    "_recommendation_blocked_reason",
    "_recommendation_cache_fingerprint",
    "_recommendation_commit_eligible",
    "_reset_design_guide_reco_trace",
    "_set_design_guide_primary_payload_binding_audit",
    "_selector_final_winner_label_from_guidance_debug",
    "_suppress_redundant_guidance_items",
    "_sync_auto_design_mode_tracking",
}

OWNER_MODULES = (
    "inputs_page_app_contracts",
    "inputs_application.guidance_runtime_config",
    "inputs_page_modules.guidance_compute",
    "inputs_page_modules.design_overview_adapter",
    "inputs_page_modules.recommendation_compute",
    "inputs_page_modules.design_guide",
    "inputs_page_modules.design_guide.presentation_state",
    "inputs_page_modules.design_guide.pending_recommendation",
    "inputs_page_modules.design_guide.guidance_item_consolidation",
    "inputs_page_modules.design_guide.guidance_item_dedupe",
    "inputs_page_modules.design_guide.terminal_state",
    "inputs_page_modules.design_guide.display_truth",
    "inputs_page_modules.design_guide.banner_render_state",
    "inputs_page_modules.design_guide.button_contract",
    "inputs_page_modules.design_guide.title_alignment_verification",
    "inputs_page_modules.design_guide.family_ladder_guidance",
    "inputs_page_modules.design_guide.guidance_items",
    "inputs_page_modules.design_guide.local_cleanup_promotion",
    "inputs_page_modules.design_guide.primary_button_queue",
    "inputs_page_modules.design_guide.main_panel_status",
    "inputs_page_modules.design_guide.shear_local_cleanup",
    "inputs_page_modules.session",
    "inputs_application.efficiency_classification",
    "inputs_application.guidance_entrypoint",
    "inputs_application.state_utils",
    "inputs_application.recommendation_envelope",
    "design_brain.engine",
    "state_and_helpers",
)


def _defined_names(node: ast.AST) -> set[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    targets = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    return {target.id for target in targets if isinstance(target, ast.Name)}


def _argument_names(node: ast.AST) -> set[str]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return set()
    args = node.args
    return {
        item.arg
        for item in (
            list(args.posonlyargs)
            + list(args.args)
            + list(args.kwonlyargs)
        )
    } | {
        item.arg
        for item in (args.vararg, args.kwarg)
        if item is not None
    }


def _local_names(node: ast.AST) -> set[str]:
    return _defined_names(node) | _argument_names(node) | {
        item.id
        for item in ast.walk(node)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)
    } | {
        item.arg
        for item in ast.walk(node)
        if isinstance(item, ast.arg)
    } | {
        item.name
        for item in ast.walk(node)
        if isinstance(
            item,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        )
    }


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    definitions: dict[str, ast.AST] = {}
    for node in tree.body:
        for name in _defined_names(node):
            definitions[name] = node

    modules = [importlib.import_module(name) for name in OWNER_MODULES]
    externally_owned = set(dir(builtins))
    for module in modules:
        externally_owned.update(dir(module))

    closure: set[str] = set()
    pending = list(ROOT_SYMBOLS)
    while pending:
        name = pending.pop()
        if name in closure or name in externally_owned:
            continue
        node = definitions.get(name)
        if node is None:
            raise RuntimeError(f"Archived definition not found: {name}")
        closure.add(name)
        local_names = _local_names(node)
        used = {
            item.id
            for item in ast.walk(node)
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
        } - local_names
        pending.extend(
            used_name
            for used_name in used
            if used_name in definitions
            and used_name not in externally_owned
            and used_name not in closure
        )

    selected_nodes = sorted(
        {definitions[name] for name in closure},
        key=lambda item: int(item.lineno),
    )
    selected_names = set().union(
        *(_defined_names(node) for node in selected_nodes)
    )
    external_loads: set[str] = set()
    for node in selected_nodes:
        external_loads.update(
            {
                item.id
                for item in ast.walk(node)
                if isinstance(item, ast.Name)
                and isinstance(item.ctx, ast.Load)
            }
            - _local_names(node)
        )
    external_loads -= selected_names
    external_loads -= set(dir(builtins))

    special_imports = {
        "_build_final_publication_cta_from_current_state": (
            "from design_brain.final_publication import "
            "build_final_publication_cta_from_current_state as "
            "_build_final_publication_cta_from_current_state"
        ),
        "html": "import html",
        "json": "import json",
        "st": "import streamlit as st",
    }
    imports: list[str] = []
    unresolved: list[str] = []
    for name in sorted(external_loads):
        if name in special_imports:
            imports.append(special_imports[name])
            continue
        owner = next(
            (module for module in modules if hasattr(module, name)),
            None,
        )
        if owner is None:
            unresolved.append(name)
            continue
        imports.append(f"from {owner.__name__} import {name}")
    if unresolved:
        raise RuntimeError(
            "Unresolved generated imports: " + ", ".join(unresolved)
        )

    sections = [
        '"""Permanent support owned by the typed Inputs Design Guide runtime.\n\n'
        "Generated mechanically from the last archived page closure; this "
        "module has no runtime dependency on that archive.\n"
        '"""',
        "from __future__ import annotations",
        "\n".join(sorted(set(imports))),
    ]
    lines = source.splitlines()
    sections.extend(
        "\n".join(lines[node.lineno - 1 : node.end_lineno])
        for node in selected_nodes
    )
    sections.append(
        "__all__ = [\n"
        + "\n".join(f'    "{name}",' for name in sorted(ROOT_SYMBOLS))
        + "\n]"
    )
    TARGET.write_text("\n\n\n".join(sections) + "\n", encoding="utf-8")
    print(
        f"WROTE {TARGET.relative_to(ROOT)}: "
        f"{len(selected_names)} symbols, "
        f"{sum(node.end_lineno - node.lineno + 1 for node in selected_nodes)} "
        "source lines"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
