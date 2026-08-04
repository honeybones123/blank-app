"""Verify extracted shared bridge dependencies are bindable before runtime.

This catches the class of bug where an extracted module lists a late-bound
dependency, the app compiles, but a live branch crashes with ``NameError`` when
the missing name is first used.
"""

from __future__ import annotations

import ast
from datetime import datetime
import importlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = ROOT / "inputs_page_modules"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _literal_tuple(node: ast.AST | None) -> tuple[str, ...]:
    if node is None:
        return ()
    try:
        value = ast.literal_eval(node)
    except Exception:
        return ()
    if not isinstance(value, tuple):
        return ()
    return tuple(str(item) for item in value)


def _declared_dependency_names(tree: ast.Module) -> tuple[str, ...]:
    names: list[str] = []
    for node in tree.body:
        value_node = None
        target_name = ""
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.endswith("_DEPENDENCIES"):
                    target_name = target.id
                    value_node = node.value
                    break
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.endswith("_DEPENDENCIES"):
                target_name = node.target.id
                value_node = node.value
        if target_name and value_node is not None:
            names.extend(_literal_tuple(value_node))
    return tuple(dict.fromkeys(names))


def _module_defined_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    return ".".join(rel.parts)


def _binder_name(module: Any) -> str | None:
    for name in dir(module):
        if name.startswith("bind_") and name.endswith("_dependencies"):
            return name
    return None


def _active_runtime_modules() -> tuple[str, ...]:
    """Return the modules that the current Inputs shell explicitly binds.

    The old implementation imported the retired page-contract bridge and
    treated that page-level namespace as the dependency graph.  The shell now
    owns an explicit ``InputsRuntimeDependencyProvider`` instead.  Keeping
    this discovery here prevents the verifier from reintroducing the retired
    bridge merely to make the check green.
    """
    from inputs_application import page_runtime

    names = list(page_runtime._DESIGN_GUIDE_DEPENDENCY_MODULE_NAMES)
    names.extend(
        (
            "inputs_application.page_runtime.common",
            "inputs_application.page_runtime.widgets",
            "inputs_application.page_runtime.setup",
            "inputs_application.page_runtime.summaries",
            "inputs_application.page_runtime.tail",
            "inputs_application.page_runtime.mode",
            "inputs_application.page_runtime.batch",
            "inputs_application.page_runtime.design_guide",
            "inputs_application.page_runtime.divider",
        )
    )
    return tuple(dict.fromkeys(names))


_TYPED_GUIDANCE_RUNTIME_MODULES = frozenset(
    {
        "inputs_page_modules.design_guide.family_ladder_guidance",
        "inputs_page_modules.design_guide.local_cleanup_promotion",
        "inputs_page_modules.design_guide.shear_local_cleanup",
    }
)


def _probe_typed_guidance_runtime() -> tuple[bool, str | None]:
    """Prove nested guidance dependencies are owned by the typed runtime."""
    try:
        import os
        import streamlit as st

        from inputs_application.guidance_entrypoint import (
            build_guidance_entrypoint_runtime,
        )

        runtime = build_guidance_entrypoint_runtime(
            st_module=st,
            os_module=os,
            sys_module=sys,
        )
        for field_name in (
            "family_ladder_guidance",
            "local_cleanup_promotion",
            "shear_local_cleanup",
        ):
            if getattr(runtime.compute_runtime, field_name, None) is None:
                return False, f"missing GuidanceComputeRuntime.{field_name}"
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _build() -> dict[str, Any]:
    from inputs_application import page_runtime

    active_names = _active_runtime_modules()
    active_modules = tuple(importlib.import_module(name) for name in active_names)
    provider = page_runtime.InputsRuntimeDependencyProvider(modules=active_modules)
    page_runtime._bind_declared_runtime_dependencies(provider)
    typed_runtime_ready, typed_runtime_error = _probe_typed_guidance_runtime()

    rows: list[dict[str, Any]] = []
    for module_name, module in zip(active_names, active_modules):
        path = ROOT.joinpath(*module_name.split(".")).with_suffix(".py")
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        if "_DEPENDENCIES" not in source:
            continue
        tree = ast.parse(source)
        dependencies = _declared_dependency_names(tree)
        if not dependencies:
            continue
        binder = _binder_name(module)
        defined_in_module = _module_defined_names(tree)
        missing_from_bridge = [
            name
            for name in dependencies
            if name not in defined_in_module and not hasattr(provider, name)
        ]
        unbound_after_binder = [
            name
            for name in dependencies
            if name not in defined_in_module and hasattr(provider, name) and not hasattr(module, name)
        ]
        nested_runtime_owned = module_name in _TYPED_GUIDANCE_RUNTIME_MODULES
        passed = bool(binder) and not unbound_after_binder and (
            not missing_from_bridge or (nested_runtime_owned and typed_runtime_ready)
        )
        rows.append(
            {
                "module": path.relative_to(ROOT).as_posix(),
                "module_name": module_name,
                "dependency_count": len(dependencies),
                "binder": binder,
                "binder_present": bool(binder),
                "missing_from_bridge": missing_from_bridge,
                "unbound_after_binder": unbound_after_binder,
                "nested_runtime_owned": nested_runtime_owned,
                "passed": passed,
            }
        )

    failed = [row for row in rows if not row["passed"]]
    return {
        "schema": "shared_bridge_dependency_binding_lock.v1",
        "status": "PASS" if not failed else "FAIL",
        "timestamp": _stamp(),
        "module_count": len(rows),
        "failed_module_count": len(failed),
        "failed_modules": failed,
        "modules": rows,
        "product_behaviour_changed": False,
        "runtime_failure_class_prevented": "late_bound_extracted_bridge_dependency_name_error",
        "dependency_authority": "inputs_application.page_runtime.InputsRuntimeDependencyProvider",
        "retired_page_bridge_required": False,
        "active_runtime_module_count": len(active_modules),
        "typed_guidance_runtime_probe": {
            "passed": typed_runtime_ready,
            "error": typed_runtime_error,
            "owner": "inputs_application.guidance_entrypoint.GuidanceEntrypointRuntime",
        },
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Shared Bridge Dependency Binding Lock",
        "",
        f"Status: `{payload['status']}`",
        f"Modules checked: `{payload['module_count']}`",
        f"Failed modules: `{payload['failed_module_count']}`",
        "",
        "## Failed Modules",
        "",
    ]
    if payload["failed_modules"]:
        for row in payload["failed_modules"]:
            lines.append(f"- `{row['module']}`")
            lines.append(f"  - missing_from_bridge: `{row['missing_from_bridge']}`")
            lines.append(f"  - unbound_after_binder: `{row['unbound_after_binder']}`")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build()
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"shared_bridge_dependency_binding_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"shared_bridge_dependency_binding_lock_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"shared_bridge_dependency_binding_lock {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
