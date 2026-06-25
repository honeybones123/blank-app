from __future__ import annotations

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
SNAPSHOT_PATH = ROOT / "tools" / "verification" / "design_guide_output_formatting_snapshot.py"

from design_brain.output_formatting_contract import (  # noqa: E402
    CONTRACT_PATH,
    allowed_reason_why_rows,
    allowed_title_status_formats,
    blocker_wording_categories,
    cleanup_no_repair_wording,
    cta_display_wording_expectations,
    exact_blocker_fallback_wording,
    ladder_stop_evidence_wording,
    load_design_guide_output_wording_contract,
    required_html_model_hash_fields,
    required_output_wording_gates,
    required_render_model_fields,
    required_snapshot_cases,
)


REQUIRED_TOP_LEVEL_KEYS = {
    "schema",
    "contract_identity",
    "allowed_title_status_formats",
    "allowed_reason_why_rows",
    "blocker_wording_categories",
    "cleanup_no_repair_wording",
    "exact_blocker_fallback_wording",
    "ladder_stop_evidence_wording",
    "cta_display_wording_expectations",
    "required_render_model_fields",
    "required_hash_fields",
    "required_snapshot_cases",
    "required_gates",
    "movement_rules",
}


def _run_snapshot() -> dict[str, Any]:
    command = [sys.executable, "tools/verification/design_guide_output_formatting_snapshot.py"]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    artifact = None
    for line in str(completed.stdout or "").splitlines():
        text = line.strip()
        if text.startswith("PASS:") or text.startswith("FAIL:"):
            artifact = text.split(":", 1)[1].strip()
            break
    artifact_path = Path(artifact) if artifact else None
    if artifact_path is not None and not artifact_path.is_absolute():
        artifact_path = ROOT / artifact_path
    return {
        "command": command,
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "artifact": str(artifact_path) if artifact_path else None,
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-4000:],
    }


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _validate_contract_shape(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(contract.keys()))
    failures.extend(f"missing_top_level_key:{key}" for key in missing)

    if contract.get("schema") != "design_brain.design_guide_output_wording_contract.v1":
        failures.append("schema_mismatch")

    identity = contract.get("contract_identity") or {}
    if identity.get("contract_id") != "DESIGN_GUIDE_OUTPUT_WORDING":
        failures.append("contract_id_mismatch")
    if identity.get("owner") != "design_brain.output_formatting":
        failures.append("owner_mismatch")
    if identity.get("snapshot_verifier") != "tools/verification/design_guide_output_formatting_snapshot.py":
        failures.append("snapshot_verifier_mismatch")

    formats = allowed_title_status_formats()
    for status in ("action", "blocked", "pass"):
        if status not in set(formats.get("statuses") or []):
            failures.append(f"allowed_status_missing:{status}")
    for pill in ("ACTION", "BLOCKED", "PASS"):
        if pill not in set(formats.get("pill_labels") or []):
            failures.append(f"allowed_pill_missing:{pill}")

    rows = allowed_reason_why_rows()
    for field in ("label", "text", "tone"):
        if field not in set(rows.get("required_row_fields") or []):
            failures.append(f"required_reason_row_field_missing:{field}")

    if not blocker_wording_categories():
        failures.append("blocker_wording_categories_empty")
    if not cleanup_no_repair_wording().get("source_precedence"):
        failures.append("cleanup_source_precedence_empty")
    if not exact_blocker_fallback_wording().get("source_precedence"):
        failures.append("exact_blocker_source_precedence_empty")
    if not ladder_stop_evidence_wording().get("source_precedence"):
        failures.append("ladder_stop_source_precedence_empty")
    if not cta_display_wording_expectations().get("disabled_reason_source_precedence"):
        failures.append("cta_disabled_reason_source_precedence_empty")
    if not required_render_model_fields():
        failures.append("required_render_model_fields_empty")
    if not required_html_model_hash_fields():
        failures.append("required_hash_fields_empty")
    if not required_snapshot_cases():
        failures.append("required_snapshot_cases_empty")
    if not required_output_wording_gates():
        failures.append("required_gates_empty")
    return failures


def _validate_snapshot_source() -> list[str]:
    failures: list[str] = []
    text = SNAPSHOT_PATH.read_text(encoding="utf-8", errors="replace")
    required_loaders = [
        "load_design_guide_output_wording_contract",
        "allowed_title_status_formats",
        "allowed_reason_why_rows",
        "blocker_wording_categories",
        "cleanup_no_repair_wording",
        "exact_blocker_fallback_wording",
        "ladder_stop_evidence_wording",
        "cta_display_wording_expectations",
        "required_render_model_fields",
        "required_html_model_hash_fields",
        "required_snapshot_cases",
        "required_output_wording_gates",
    ]
    for name in required_loaders:
        if name not in text:
            failures.append(f"snapshot_missing_contract_loader:{name}")
    if '"action_enabled_shear"' in text and "required_snapshot_cases" not in text:
        failures.append("snapshot_case_names_not_contract_checked")
    return failures


def _validate_snapshot_artifact(snapshot_result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    artifact_path = Path(str(snapshot_result.get("artifact") or "")) if snapshot_result.get("artifact") else None
    snapshot = _load_json(artifact_path)
    if not snapshot:
        return ["output_formatting_snapshot_artifact_missing"]
    if snapshot.get("status") != "PASS":
        failures.append("output_formatting_snapshot_failed")
    if snapshot.get("contract_path") != str(CONTRACT_PATH):
        failures.append("snapshot_contract_path_mismatch")
    if snapshot.get("required_render_model_fields") != list(required_render_model_fields()):
        failures.append("snapshot_required_render_model_fields_mismatch")
    if snapshot.get("required_hash_fields") != list(required_html_model_hash_fields()):
        failures.append("snapshot_required_hash_fields_mismatch")
    if snapshot.get("required_gates") != list(required_output_wording_gates()):
        failures.append("snapshot_required_gates_mismatch")

    case_names = {str(case.get("name")) for case in list(snapshot.get("cases") or []) if isinstance(case, dict)}
    coverage = dict(snapshot.get("contract_case_coverage") or {})
    for category, config in required_snapshot_cases().items():
        names = [str(value) for value in config.get("case_names") or []]
        required = bool(config.get("required"))
        if required and not any(name in case_names for name in names):
            failures.append(f"required_snapshot_case_missing:{category}")
        row = dict(coverage.get(category) or {})
        if required and row.get("status") != "covered":
            failures.append(f"required_snapshot_case_not_covered:{category}")

    required_fields = set(required_render_model_fields())
    required_hashes = set(required_html_model_hash_fields())
    for case in list(snapshot.get("cases") or []):
        if not isinstance(case, dict):
            continue
        render_fields = dict(case.get("final_card_model_fields") or {})
        for field in required_fields:
            if field not in render_fields and field not in dict(case.get("final_card_model_full") or {}):
                failures.append(f"{case.get('name')}:missing_render_model_field:{field}")
        for field in required_hashes:
            if field not in case:
                failures.append(f"{case.get('name')}:missing_hash_field:{field}")
    return failures


def _write_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Design Guide Output Wording Contract Check",
        "",
        f"Status: {output.get('status')}",
        "",
        "## Contract",
        "",
        f"- contract_json: `{output.get('contract_path')}`",
        f"- snapshot_artifact: `{output.get('output_formatting_snapshot', {}).get('artifact')}`",
        "",
        "## Checks",
        "",
        "- JSON contract loaded through `output_formatting_contract.py`",
        "- focused output-formatting snapshot imports/loads the contract",
        "- required snapshot cases are validated from the contract",
        "- required render-model fields and hash fields are validated from the contract",
        "",
        "## Failures",
        "",
    ]
    lines.extend([f"- {failure}" for failure in output.get("failures") or []] or ["- none"])
    lines.extend(["", "## Output", "", f"- `{output.get('artifact')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    contract = load_design_guide_output_wording_contract()
    snapshot_result = _run_snapshot()

    failures = (
        _validate_contract_shape(contract)
        + _validate_snapshot_source()
        + _validate_snapshot_artifact(snapshot_result)
    )
    if snapshot_result.get("status") != "PASS":
        failures.append("output_formatting_snapshot_failed")

    status = "PASS" if not failures else "FAIL"
    artifact_path = ARTIFACT_DIR / f"design_guide_output_wording_contract_check_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_output_wording_contract_check_{stamp}.md"
    output = {
        "schema": "design_guide_output_wording_contract_check.v1",
        "status": status,
        "contract_path": str(CONTRACT_PATH),
        "required_snapshot_cases": required_snapshot_cases(),
        "required_render_model_fields": list(required_render_model_fields()),
        "required_hash_fields": list(required_html_model_hash_fields()),
        "required_gates": list(required_output_wording_gates()),
        "output_formatting_snapshot": snapshot_result,
        "failures": failures,
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(output, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    if failures:
        for failure in failures:
            print(f"- {failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
