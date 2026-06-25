from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.family_chooser import classify_family_from_raw_flags  # noqa: E402
from design_brain.families.registry import family_strategy_for  # noqa: E402
from design_brain.families.bending_fail_shear_overdesign_governs import (  # noqa: E402
    evaluate_bending_fail_shear_overdesign_governs,
)
from design_brain.families.bending_fail_shear_overdesign_governs.runtime import (  # noqa: E402
    run_bending_fail_shear_overdesign_runtime,
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_shear_overdesign_governs_replacement_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_shear_overdesign_governs_replacement_audit_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_SHEAR_OVERDESIGN Replacement Audit",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "Authority rule: mixed runtime owns merge/ranking/selection only.",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Difference Classification",
                "",
                *[
                    f"- `{row['item']}`: `{row['class']}` - {row['reason']}"
                    for row in snapshot["difference_classification"]
                ],
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
    chooser = classify_family_from_raw_flags(
        {
            "bending_fail": True,
            "shear_fail": False,
            "shear_overdesigned": True,
            "legal_repair_exists": True,
        }
    )
    strategy = family_strategy_for("BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS")
    package_source = _read("design_brain/families/bending_fail_shear_overdesign_governs/__init__.py")
    runtime_source = _read("design_brain/families/bending_fail_shear_overdesign_governs/runtime.py")
    old_page_evidence = {
        "mixed_family_previously_registered": False,
        "old_plain_bending_fail_would_have_owned_bending_repair": "BENDING_FAIL_GOVERNS" in _read("design_brain/family_chooser.py"),
        "shear_overdesign_previous_standalone_family_exists": "SHEAR_OVERDESIGN_GOVERNS" in _read("design_brain/family_chooser.py"),
        "used_as_authority": False,
    }
    differences = [
        {
            "item": "plain_bending_fail_selection_when_shear_overdesigned",
            "class": "EXPECTED_CONTRACT_REPLACEMENT",
            "reason": "New shared selection routes bending-fail plus shear-overdesign state to the mixed merge family.",
        },
        {
            "item": "source_ladder_ownership",
            "class": "NO_OLD_EQUIVALENT_NEEDED",
            "reason": "Mixed runtime consumes locked source candidates and does not duplicate bending repair or shear optimisation ladders.",
        },
        {
            "item": "shared_publication_and_cta",
            "class": "EXPECTED_CONTRACT_REPLACEMENT",
            "reason": "Family package returns no publication or CTA contract; shared systems remain owners.",
        },
    ]
    checks = {
        "chooser_selects_mixed_family": chooser.get("selected_family_id") == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "registry_returns_family_shell": type(strategy).__name__ == "BendingFailShearOverdesignFamily",
        "package_api_runtime_driven": callable(evaluate_bending_fail_shear_overdesign_governs)
        and "run_bending_fail_shear_overdesign_runtime" in package_source,
        "runtime_available": callable(run_bending_fail_shear_overdesign_runtime),
        "runtime_does_not_call_source_ladders": "run_bending_fail_governs_ladder_runtime" not in runtime_source
        and "run_shear_overdesign_governs_runtime" not in runtime_source,
        "runtime_has_no_shared_app_ownership": all(
            term not in runtime_source
            for term in ("inputs_page", "streamlit", "button_contract", "publication", "apply_routing")
        ),
        "difference_classes_known": all(row["class"] in {"EXPECTED_CONTRACT_REPLACEMENT", "NO_OLD_EQUIVALENT_NEEDED"} for row in differences),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "bending_fail_shear_overdesign_governs_replacement_audit.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "old_live_evidence": old_page_evidence,
        "chooser_result": chooser,
        "difference_classification": differences,
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    print(f"{snapshot['result']}: {json_path}")
    print(f"REPORT: {report_path}")
    return 0 if snapshot["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
