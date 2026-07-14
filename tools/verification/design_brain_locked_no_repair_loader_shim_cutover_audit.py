"""Audit the locked-no-repair package loader shim cutover path.

This is proof-only. It verifies the package now exports the family from a
package-local implementation module without the old dynamic loader shim.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_INIT = ROOT / "design_brain" / "families" / "locked_no_repair" / "__init__.py"
LEGACY_MODULE = ROOT / "design_brain" / "families" / "locked_no_repair.py"
PACKAGE_STRATEGY = ROOT / "design_brain" / "families" / "locked_no_repair" / "strategy.py"
REGISTRY = ROOT / "design_brain" / "families" / "registry.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _has_function(path: Path, name: str) -> bool:
    tree = ast.parse(_read(path))
    return any(isinstance(node, ast.FunctionDef) and node.name == name for node in ast.walk(tree))


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_brain_locked_no_repair_loader_shim_cutover_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_locked_no_repair_loader_shim_cutover_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(md_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Locked No Repair Loader Shim Cutover Audit",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Findings",
        "",
        f"- Package shim present: `{snapshot['checks']['package_loader_shim_present']}`",
        f"- Legacy sibling module present: `{snapshot['checks']['legacy_module_present']}`",
        f"- Package-local strategy present: `{snapshot['checks']['package_local_strategy_present']}`",
        f"- Registry imports package path: `{snapshot['checks']['registry_imports_package_path']}`",
        f"- Same-basename module/package collision exists: `{snapshot['checks']['same_basename_collision_exists']}`",
        f"- Direct import cutover complete: `{snapshot['checks']['direct_import_cutover_complete']}`",
        "",
        "## Recommended Next Slice",
        "",
        snapshot["recommended_next_slice"],
        "",
        "## Cutover Shape",
        "",
        "1. `design_brain/families/locked_no_repair/strategy.py` owns `LockedNoRepairFamily`.",
        "2. `design_brain/families/locked_no_repair/__init__.py` re-exports from the package-local module.",
        "3. `families.registry` keeps the same public package import path.",
        "4. The old sibling module file is gone, so the loader shim path no longer exists.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    init_source = _read(PACKAGE_INIT)
    strategy_source = _read(PACKAGE_STRATEGY)
    registry_source = _read(REGISTRY)

    checks = {
        "package_loader_shim_present": "_load_legacy_locked_no_repair_family" in init_source,
        "legacy_module_present": LEGACY_MODULE.exists(),
        "package_local_strategy_present": PACKAGE_STRATEGY.exists(),
        "package_local_strategy_has_family_class": "class LockedNoRepairFamily" in strategy_source,
        "registry_imports_package_path": "from design_brain.families.locked_no_repair import LockedNoRepairFamily" in registry_source,
        "same_basename_collision_exists": LEGACY_MODULE.exists() and PACKAGE_INIT.parent.name == LEGACY_MODULE.stem,
        "package_can_export_without_dynamic_loader_today": _has_function(PACKAGE_INIT, "evaluate_locked_no_repair"),
        "package_reexports_strategy_family": "from .strategy import LockedNoRepairFamily" in init_source,
    }
    checks["direct_import_cutover_complete"] = all(
        (
            not checks["package_loader_shim_present"],
            not checks["legacy_module_present"],
            checks["package_local_strategy_present"],
            checks["package_local_strategy_has_family_class"],
            checks["registry_imports_package_path"],
            checks["package_reexports_strategy_family"],
        )
    )

    failures: list[str] = []
    if not checks["direct_import_cutover_complete"]:
        failures.append("locked_no_repair_direct_import_cutover_incomplete")

    snapshot = {
        "snapshot_name": "design_brain_locked_no_repair_loader_shim_cutover_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "recommended_next_slice": (
            "Locked-no-repair no longer needs the package loader shim. The next safe scaffolding target is a different compatibility surface "
            "from the internal inventory, not this package."
        ),
        "failures": failures,
    }
    snapshot["snapshot_hash"] = _stable_hash(snapshot["checks"])
    json_path, md_path = _write(snapshot)
    print(f"design_brain_locked_no_repair_loader_shim_cutover_audit {snapshot['result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
