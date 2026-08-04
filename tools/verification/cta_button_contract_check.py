from __future__ import annotations

import importlib.util
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
CONTRACT_MODULE_PATH = ROOT / "design_brain" / "contracts" / "cta_button_contract.py"
SNAPSHOT_PATH = ROOT / "tools" / "verification" / "design_guide_cta_source_precedence_current_snapshot.py"


REQUIRED_TOP_LEVEL_KEYS = {
    "schema",
    "contract_identity",
    "source_precedence",
    "payload_precedence",
    "required_proof_fields",
    "required_source_record_fields",
    "allowed_cta_states",
    "required_gates",
    "movement_rules",
}

EXPECTED_SOURCE_PRECEDENCE = (
    "primary.button_contract",
    "debug.displayed_primary_button_contract",
    "debug.primary_button_contract",
    "debug.button_contract",
)

REQUIRED_PAYLOAD_PRECEDENCE_KEYS = {
    "update_payload",
    "action_type",
    "candidate",
    "disabled_reason",
}


def _load_contract_module() -> Any:
    spec = importlib.util.spec_from_file_location("cta_button_contract_file", CONTRACT_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load CTA contract module: {CONTRACT_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_snapshot() -> dict[str, Any]:
    command = [sys.executable, "tools/verification/design_guide_cta_source_precedence_current_snapshot.py"]
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


def _validate_contract_shape(module: Any, contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(contract.keys()))
    failures.extend(f"missing_top_level_key:{key}" for key in missing)

    if contract.get("schema") != "design_brain.cta_button_contract.v1":
        failures.append("schema_mismatch")

    identity = contract.get("contract_identity") or {}
    if identity.get("contract_id") != "DESIGN_GUIDE_CTA_BUTTON_SOURCE_PRECEDENCE":
        failures.append("contract_id_mismatch")
    if identity.get("live_resolver") != "inputs_page._resolve_design_guide_button_contract_source_precedence":
        failures.append("live_resolver_mismatch")

    if tuple(module.cta_button_source_precedence_order()) != EXPECTED_SOURCE_PRECEDENCE:
        failures.append("source_precedence_order_mismatch")

    payload_precedence = module.cta_payload_source_precedence_order()
    missing_payload = sorted(REQUIRED_PAYLOAD_PRECEDENCE_KEYS - set(payload_precedence.keys()))
    failures.extend(f"missing_payload_precedence:{key}" for key in missing_payload)

    if not module.required_cta_proof_fields():
        failures.append("required_proof_fields_empty")
    if not module.required_cta_source_record_fields():
        failures.append("required_source_record_fields_empty")
    if not module.allowed_cta_states():
        failures.append("allowed_cta_states_empty")
    if not module.required_cta_gates():
        failures.append("required_gates_empty")
    return failures


def _validate_snapshot_source(module: Any) -> list[str]:
    failures: list[str] = []
    text = SNAPSHOT_PATH.read_text(encoding="utf-8", errors="replace")
    required_loaders = [
        "load_cta_button_contract",
        "cta_button_source_precedence_order",
        "cta_payload_source_precedence_order",
        "required_cta_proof_fields",
        "required_cta_source_record_fields",
        "allowed_cta_states",
        "required_cta_gates",
    ]
    for name in required_loaders:
        if name not in text:
            failures.append(f"snapshot_missing_contract_loader:{name}")

    duplicate_literal = repr(set(module.cta_candidate_source_keys()))
    if duplicate_literal in text:
        failures.append("snapshot_contains_hardcoded_candidate_source_set")
    if "expected_winners = {" in text:
        failures.append("snapshot_contains_hardcoded_expected_winners")
    if "required_source_keys = {" in text:
        failures.append("snapshot_contains_hardcoded_required_source_keys")
    return failures


def _validate_snapshot_artifact(module: Any, snapshot_result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    artifact_path = Path(str(snapshot_result.get("artifact") or "")) if snapshot_result.get("artifact") else None
    snapshot = _load_json(artifact_path)
    if not snapshot:
        return ["cta_snapshot_artifact_missing"]
    if snapshot.get("status") != "PASS":
        failures.append("cta_snapshot_failed")
    if snapshot.get("contract_path") != str(module.CONTRACT_PATH):
        failures.append("cta_snapshot_contract_path_mismatch")
    if snapshot.get("contract_source_precedence_order") != list(module.cta_button_source_precedence_order()):
        failures.append("cta_snapshot_source_precedence_order_mismatch")
    if snapshot.get("contract_payload_source_precedence_order") != {
        key: list(value) for key, value in module.cta_payload_source_precedence_order().items()
    }:
        failures.append("cta_snapshot_payload_precedence_order_mismatch")
    if snapshot.get("required_proof_fields") != list(module.required_cta_proof_fields()):
        failures.append("cta_snapshot_required_proof_fields_mismatch")
    if snapshot.get("required_source_record_fields") != list(module.required_cta_source_record_fields()):
        failures.append("cta_snapshot_required_source_record_fields_mismatch")
    if snapshot.get("allowed_cta_states") != list(module.allowed_cta_states()):
        failures.append("cta_snapshot_allowed_states_mismatch")
    if snapshot.get("required_gates") != list(module.required_cta_gates()):
        failures.append("cta_snapshot_required_gates_mismatch")

    for scenario, row in dict(snapshot.get("scenario_winners") or {}).items():
        typed = dict(row.get("typed_source_resolution") or {})
        missing_proof = [field for field in module.required_cta_proof_fields() if field not in typed]
        failures.extend(f"{scenario}:missing_required_proof_field:{field}" for field in missing_proof)
        records = dict(row.get("typed_source_records") or {})
        missing_records = [field for field in module.required_cta_source_record_fields() if field not in records]
        failures.extend(f"{scenario}:missing_required_source_record_field:{field}" for field in missing_records)
    return failures


def _write_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# CTA/Button Contract Check",
        "",
        f"Status: {output.get('status')}",
        "",
        "## Contract",
        "",
        f"- contract_json: `{output.get('contract_path')}`",
        f"- contract_loader: `{output.get('contract_module_path')}`",
        f"- cta_snapshot_artifact: `{output.get('cta_snapshot', {}).get('artifact')}`",
        "",
        "## Checks",
        "",
        "- JSON contract loaded through `cta_button_contract.py`",
        "- snapshot imports/loads the contract",
        "- source precedence and required proof fields are validated from the contract",
        "- focused CTA snapshot includes required proof/source-record fields",
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
    module = _load_contract_module()
    contract = module.load_cta_button_contract()
    snapshot_result = _run_snapshot()

    failures = (
        _validate_contract_shape(module, contract)
        + _validate_snapshot_source(module)
        + _validate_snapshot_artifact(module, snapshot_result)
    )
    if snapshot_result.get("status") != "PASS":
        failures.append("cta_source_precedence_snapshot_failed")

    status = "PASS" if not failures else "FAIL"
    artifact_path = ARTIFACT_DIR / f"cta_button_contract_check_{stamp}.json"
    report_path = AUDIT_DIR / f"cta_button_contract_check_{stamp}.md"
    output = {
        "schema": "cta_button_contract_check.v1",
        "status": status,
        "contract_path": str(module.CONTRACT_PATH),
        "contract_module_path": str(CONTRACT_MODULE_PATH),
        "source_precedence_order": list(module.cta_button_source_precedence_order()),
        "payload_source_precedence_order": {
            key: list(value) for key, value in module.cta_payload_source_precedence_order().items()
        },
        "required_proof_fields": list(module.required_cta_proof_fields()),
        "required_source_record_fields": list(module.required_cta_source_record_fields()),
        "allowed_cta_states": list(module.allowed_cta_states()),
        "required_gates": list(module.required_cta_gates()),
        "cta_snapshot": snapshot_result,
        "failures": failures,
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(output, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
