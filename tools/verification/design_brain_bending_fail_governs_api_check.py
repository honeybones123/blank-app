from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PACKAGE_INIT = ROOT / "design_brain" / "families" / "bending_fail_governs" / "__init__.py"


def _line_hits(path: Path, needle: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if not path.exists():
        return hits
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if needle in line:
            hits.append({"line": idx, "text": line.strip()[:240]})
    return hits


def main() -> int:
    from design_brain.families.bending_fail_governs import run_bending_fail_governs_ladder_runtime
    from design_brain.families.bending_fail_governs.runtime import (
        bending_fail_governs_contract_lane_order,
    )

    deleted_name = "evaluate_" + "bending_fail_governs"
    failures: list[str] = []
    source = PACKAGE_INIT.read_text(encoding="utf-8", errors="replace") if PACKAGE_INIT.exists() else ""
    engine_hits = _line_hits(ROOT / "design_brain" / "engine.py", deleted_name)
    inputs_hits = _line_hits(ROOT / "inputs_page.py", deleted_name)

    checks = {
        "package_init_exists": PACKAGE_INIT.exists(),
        "package_does_not_import_inputs_page": "inputs_page" not in source,
        "runtime_exported": "run_bending_fail_governs_ladder_runtime" in source,
        "runtime_callable": callable(run_bending_fail_governs_ladder_runtime),
        "deleted_compatibility_api_absent": deleted_name not in source,
        "engine_does_not_call_deleted_api": not engine_hits,
        "inputs_page_does_not_call_deleted_api": not inputs_hits,
        "contract_lane_order_available": bool(bending_fail_governs_contract_lane_order()),
    }
    failures = [key for key, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    output = {
        "schema": "design_brain_bending_fail_governs_runtime_export_check.v1",
        "status": status,
        "package": str(PACKAGE_INIT.relative_to(ROOT)),
        "checks": checks,
        "engine_deleted_api_hits": engine_hits,
        "inputs_page_deleted_api_hits": inputs_hits,
        "failures": failures,
    }
    output_path = ARTIFACT_DIR / f"design_brain_bending_fail_governs_api_check_{stamp}.json"
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    report_path = AUDIT_DIR / f"design_brain_bending_fail_governs_api_check_{stamp}.md"
    report_path.write_text(
        "\n".join(
            [
                "# Design Brain BENDING_FAIL_GOVERNS Runtime Export Check",
                "",
                f"Status: {status}",
                "",
                "This verifier now proves the package exposes the contract runtime directly and no longer keeps the old compatibility wrapper.",
                "",
                "## Checks",
                "",
                *[f"- {key}: `{value}`" for key, value in checks.items()],
                "",
                "## Failures",
                "",
                *([f"- {failure}" for failure in failures] or ["- none"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"{status}: {output_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
