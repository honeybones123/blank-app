"""Audit Design Brain for duplicate or ambiguous authority surfaces.

This is a structural audit. It does not execute product logic.
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESIGN_BRAIN = ROOT / "design_brain"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

AUTHORITY_WORDS = (
    "classify",
    "choose",
    "select",
    "resolve",
    "publish",
    "publication",
    "contract",
    "candidate",
    "family",
    "governing",
    "decision",
    "cta",
    "apply",
)

SAFE_DUPLICATE_NAMES = {
    "__post_init__",
    "to_dict",
    "to_kwargs",
    "input_hash",
    "update_hash",
    "update_keys",
    "source_families",
    "source_allowed",
    "sources_allowed",
    "source_family_allowed",
    "selection_boundary_satisfied",
    "with_evaluation_hash",
    "interaction_flags",
    "merge_updates",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _py_files() -> list[Path]:
    return sorted(
        p
        for p in DESIGN_BRAIN.rglob("*.py")
        if "__pycache__" not in p.parts and p.name != "__init__.py"
    )


def _is_public_name(name: str) -> bool:
    return not name.startswith("_")


def _authority_like(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in AUTHORITY_WORDS)


def _normalised_authority_key(name: str) -> str:
    key = name.lower()
    for prefix in (
        "build_design_guide_controller_",
        "run_design_guide_controller_",
        "resolve_design_guide_controller_",
        "select_design_guide_controller_",
        "assess_design_guide_",
        "build_design_guide_",
        "run_design_guide_",
        "resolve_design_guide_",
        "select_design_guide_",
        "build_",
        "resolve_",
        "select_",
        "run_",
        "apply_",
        "enforce_",
        "normalise_",
        "normalize_",
        "finalize_",
    ):
        if key.startswith(prefix):
            key = key[len(prefix) :]
            break
    return key


def _call_counts(names: set[str]) -> dict[str, int]:
    counts = {name: 0 for name in names}
    for path in sorted(ROOT.rglob("*.py")):
        if "__pycache__" in path.parts or "artifacts" in path.parts:
            continue
        source = _read(path)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called = None
                if isinstance(node.func, ast.Name):
                    called = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    called = node.func.attr
                if called in counts:
                    counts[called] += 1
    return counts


def _module_exports() -> dict[str, list[str]]:
    exports: dict[str, list[str]] = {}
    for path in [DESIGN_BRAIN / "__init__.py", *DESIGN_BRAIN.rglob("__init__.py")]:
        if "__pycache__" in path.parts:
            continue
        source = _read(path)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            names.extend(
                                elt.value
                                for elt in node.value.elts
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                            )
        if names:
            exports[str(path.relative_to(ROOT))] = sorted(set(names))
    return exports


def build_payload() -> dict:
    records: list[dict] = []
    classes: list[str] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self, module_path: Path) -> None:
            self.module_path = module_path

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            classes.append(node.name)
            for child in node.body:
                self.visit(child)
            classes.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            records.append(
                {
                    "module": str(self.module_path.relative_to(ROOT)),
                    "name": node.name,
                    "line": int(node.lineno),
                    "line_count": int(getattr(node, "end_lineno", node.lineno) - node.lineno + 1),
                    "class": classes[-1] if classes else None,
                    "public": _is_public_name(node.name),
                    "authority_like": _authority_like(node.name),
                    "normalised_key": _normalised_authority_key(node.name),
                }
            )

    for path in _py_files():
        try:
            tree = ast.parse(_read(path))
        except SyntaxError as exc:
            records.append(
                {
                    "module": str(path.relative_to(ROOT)),
                    "name": "<syntax-error>",
                    "line": exc.lineno,
                    "line_count": 0,
                    "class": None,
                    "public": False,
                    "authority_like": False,
                    "normalised_key": "<syntax-error>",
                }
            )
            continue
        Visitor(path).visit(tree)

    public_authority = [
        r for r in records if r["class"] is None and r["public"] and r["authority_like"]
    ]
    exact_groups = defaultdict(list)
    for r in public_authority:
        exact_groups[r["name"]].append(r)
    exact_duplicate_public_authority = {
        name: rows
        for name, rows in sorted(exact_groups.items())
        if len(rows) > 1 and name not in SAFE_DUPLICATE_NAMES
    }

    normalised_groups = defaultdict(list)
    for r in public_authority:
        normalised_groups[r["normalised_key"]].append(r)
    near_duplicate_public_authority = {
        key: rows
        for key, rows in sorted(normalised_groups.items())
        if len({row["name"] for row in rows}) > 1
        and len(rows) > 1
        and not re.fullmatch(r"(candidate|family|contract|decision|publication)", key)
    }

    exported = _module_exports()
    exported_names = {
        name
        for names in exported.values()
        for name in names
        if isinstance(name, str)
    }
    counts = _call_counts({r["name"] for r in public_authority} | exported_names)

    exported_authority = [
        {
            "name": name,
            "call_count": counts.get(name, 0),
            "exports": [module for module, names in exported.items() if name in names],
        }
        for name in sorted(exported_names)
        if _authority_like(name)
    ]

    ambiguous_exported_authority = [
        row
        for row in exported_authority
        if row["call_count"] > 0
        and row["name"]
        not in {
            "resolve_design_guide_decision",
            "validate_design_brain_result",
            "enforce_design_brain_publication_contract",
        }
    ]

    large_authority = [
        r
        for r in public_authority
        if int(r["line_count"]) >= 120
    ]

    payload = {
        "status": "PASS",
        "surface": "design_brain_duplicate_authority_audit",
        "function_count": len(records),
        "public_authority_function_count": len(public_authority),
        "exact_duplicate_public_authority_count": len(exact_duplicate_public_authority),
        "near_duplicate_public_authority_count": len(near_duplicate_public_authority),
        "ambiguous_exported_authority_count": len(ambiguous_exported_authority),
        "large_public_authority_count": len(large_authority),
        "exact_duplicate_public_authority": exact_duplicate_public_authority,
        "near_duplicate_public_authority": near_duplicate_public_authority,
        "exported_authority": exported_authority,
        "ambiguous_exported_authority": ambiguous_exported_authority,
        "large_public_authority": large_authority,
        "call_counts": counts,
        "exports": exported,
    }
    if exact_duplicate_public_authority or ambiguous_exported_authority:
        payload["status"] = "REVIEW"
    return payload


def write_artifacts(payload: dict) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_brain_duplicate_authority_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_duplicate_authority_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Design Brain Duplicate Authority Audit",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Counts",
        "",
        f"- Functions scanned: `{payload['function_count']}`",
        f"- Public authority-like functions: `{payload['public_authority_function_count']}`",
        f"- Exact duplicate public authority names: `{payload['exact_duplicate_public_authority_count']}`",
        f"- Near-duplicate public authority groups: `{payload['near_duplicate_public_authority_count']}`",
        f"- Ambiguous exported authority surfaces: `{payload['ambiguous_exported_authority_count']}`",
        f"- Large public authority functions: `{payload['large_public_authority_count']}`",
        "",
        "## Exported Authority",
        "",
    ]
    for row in payload["exported_authority"]:
        lines.append(
            f"- `{row['name']}` call_count=`{row['call_count']}` exports=`{', '.join(row['exports'])}`"
        )

    lines.extend(["", "## Exact Duplicate Public Authority Names", ""])
    if payload["exact_duplicate_public_authority"]:
        for name, rows in payload["exact_duplicate_public_authority"].items():
            lines.append(f"- `{name}`")
            for row in rows:
                lines.append(f"  - `{row['module']}:{row['line']}`")
    else:
        lines.append("- None.")

    lines.extend(["", "## Ambiguous Exported Authority", ""])
    if payload["ambiguous_exported_authority"]:
        for row in payload["ambiguous_exported_authority"]:
            lines.append(f"- `{row['name']}` call_count=`{row['call_count']}`")
    else:
        lines.append("- None.")

    lines.extend(["", "## Near-Duplicate Public Authority Groups", ""])
    if payload["near_duplicate_public_authority"]:
        for key, rows in list(payload["near_duplicate_public_authority"].items())[:80]:
            lines.append(f"- `{key}`")
            for row in rows:
                lines.append(f"  - `{row['name']}` at `{row['module']}:{row['line']}`")
    else:
        lines.append("- None.")

    lines.extend(["", "## Large Public Authority Functions", ""])
    for row in sorted(payload["large_public_authority"], key=lambda r: (-r["line_count"], r["module"], r["line"]))[:80]:
        lines.append(
            f"- `{row['name']}` lines=`{row['line_count']}` at `{row['module']}:{row['line']}`"
        )
    if not payload["large_public_authority"]:
        lines.append("- None.")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "md": str(md_path)}, indent=2))
    return 0 if payload["status"] in {"PASS", "REVIEW"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
