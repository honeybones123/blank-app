from __future__ import annotations

import ast
import importlib
import json
import pkgutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DESIGN_BRAIN_DIR = ROOT / "design_brain"


@dataclass(frozen=True)
class ImportFinding:
    path: str
    line: int
    module: str
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "module": self.module,
            "kind": self.kind,
        }


class _BlockInputsPageImport:
    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        if fullname == "inputs_page" or fullname.startswith("inputs_page."):
            raise ImportError("blocked inputs_page import during design_brain independence audit")
        return None


def _repo_path(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _python_files() -> list[Path]:
    return sorted(path for path in DESIGN_BRAIN_DIR.rglob("*.py") if "__pycache__" not in path.parts)


def _ast_import_findings(path: Path) -> list[ImportFinding]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=str(path))
    findings: list[ImportFinding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "inputs_page" or alias.name.startswith("inputs_page."):
                    findings.append(ImportFinding(_repo_path(path), node.lineno, alias.name, "import"))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "inputs_page" or module.startswith("inputs_page."):
                findings.append(ImportFinding(_repo_path(path), node.lineno, module, "from_import"))
    return findings


def _text_mentions(path: Path) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if "inputs_page" in line:
            mentions.append(
                {
                    "path": _repo_path(path),
                    "line": lineno,
                    "text": line.strip(),
                }
            )
    return mentions


def _design_brain_modules() -> list[str]:
    import design_brain

    modules = ["design_brain"]
    for module_info in pkgutil.walk_packages(design_brain.__path__, prefix="design_brain."):
        modules.append(module_info.name)
    return sorted(set(modules))


def _import_modules_with_inputs_page_blocked() -> dict[str, Any]:
    blocker = _BlockInputsPageImport()
    sys.meta_path.insert(0, blocker)
    imported: list[str] = []
    failed: list[dict[str, str]] = []
    before_had_inputs_page = "inputs_page" in sys.modules
    sys.modules.pop("inputs_page", None)
    try:
        for module_name in _design_brain_modules():
            try:
                importlib.import_module(module_name)
                imported.append(module_name)
            except Exception as exc:  # pragma: no cover - audit records failure.
                failed.append(
                    {
                        "module": module_name,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    finally:
        if blocker in sys.meta_path:
            sys.meta_path.remove(blocker)
    return {
        "before_had_inputs_page": before_had_inputs_page,
        "inputs_page_loaded_after_imports": "inputs_page" in sys.modules,
        "imported_count": len(imported),
        "imported_modules_sample": imported[:20],
        "failed_imports": failed,
    }


def _reverse_dependency_snapshot() -> dict[str, Any]:
    inputs_path = ROOT / "inputs_page.py"
    if not inputs_path.exists():
        return {"inputs_page_exists": False, "imports_design_brain": False, "lines": []}
    lines: list[dict[str, Any]] = []
    for lineno, line in enumerate(inputs_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if "design_brain" in line:
            lines.append({"line": lineno, "text": line.strip()})
    return {
        "inputs_page_exists": True,
        "imports_design_brain": bool(lines),
        "line_count": len(lines),
        "lines_sample": lines[:25],
        "classification": "EXPECTED_REVERSE_APP_DEPENDENCY" if lines else "NO_REVERSE_DEPENDENCY_FOUND",
    }


def _ui_dependency_snapshot() -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8", errors="replace")
        if "from ui." not in source and "import ui." not in source:
            continue
        for lineno, line in enumerate(source.splitlines(), start=1):
            if "from ui." in line or "import ui." in line:
                hits.append({"path": _repo_path(path), "line": lineno, "text": line.strip()})
    return {
        "ui_import_count": len(hits),
        "ui_imports": hits,
        "classification": "PRESENTATION_MODEL_COUPLING_NOT_INPUTS_PAGE" if hits else "NO_UI_IMPORTS",
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_inputs_page_independence_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_inputs_page_independence_audit_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Brain Inputs Page Independence Audit",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Conclusion",
                "",
                snapshot["conclusion"],
                "",
                "## Findings",
                "",
                f"- direct `inputs_page` imports in `design_brain`: `{len(snapshot['direct_inputs_page_imports'])}`",
                f"- import-time `inputs_page` load: `{snapshot['import_probe']['inputs_page_loaded_after_imports']}`",
                f"- design_brain modules imported under blocker: `{snapshot['import_probe']['imported_count']}`",
                f"- reverse app dependency from `inputs_page.py` into `design_brain`: `{snapshot['reverse_dependency']['imports_design_brain']}`",
                f"- design_brain UI model imports: `{snapshot['ui_dependency']['ui_import_count']}`",
                "",
                "## Direct Import Findings",
                "",
                *(
                    [
                        f"- `{finding['path']}:{finding['line']}` imports `{finding['module']}`"
                        for finding in snapshot["direct_inputs_page_imports"]
                    ]
                    or ["- none"]
                ),
                "",
                "## Notes",
                "",
                "- Text mentions of `inputs_page` inside Design Brain are audit/evidence strings, not import dependencies.",
                "- Reverse dependency is expected while `inputs_page.py` remains the app orchestrator/evaluator.",
                "- UI model imports are not `inputs_page` coupling, but they mean Design Brain is not yet completely presentation-package independent.",
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    direct_findings = [finding for path in _python_files() for finding in _ast_import_findings(path)]
    text_mentions = [mention for path in _python_files() for mention in _text_mentions(path)]
    import_probe = _import_modules_with_inputs_page_blocked()
    reverse_dependency = _reverse_dependency_snapshot()
    ui_dependency = _ui_dependency_snapshot()
    failures: list[str] = []
    if direct_findings:
        failures.append("design_brain_directly_imports_inputs_page")
    if import_probe["inputs_page_loaded_after_imports"]:
        failures.append("design_brain_imports_load_inputs_page")
    if import_probe["failed_imports"]:
        failures.append("design_brain_modules_failed_import_probe")
    result = "PASS" if not failures else "FAIL"
    conclusion = (
        "Design Brain is independent of `inputs_page.py` as a Python dependency: no direct imports were found, "
        "and importing Design Brain modules with `inputs_page` blocked did not load `inputs_page`."
        if result == "PASS"
        else "Design Brain is not fully independent of `inputs_page.py`; see failures."
    )
    snapshot = {
        "schema": "design_brain_inputs_page_independence_audit.v1",
        "result": result,
        "conclusion": conclusion,
        "direct_inputs_page_imports": [finding.to_dict() for finding in direct_findings],
        "inputs_page_text_mentions": text_mentions,
        "import_probe": import_probe,
        "reverse_dependency": reverse_dependency,
        "ui_dependency": ui_dependency,
        "scope": {
            "audits_design_brain_to_inputs_page_dependency": True,
            "reverse_inputs_page_to_design_brain_dependency_allowed": True,
            "ui_model_dependency_is_reported_separately": True,
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("Design Brain inputs_page independence audit FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("Design Brain inputs_page independence audit PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
