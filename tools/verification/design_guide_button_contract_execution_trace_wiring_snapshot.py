"""Trace-only wiring snapshot for Design Guide button-contract execution proof."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[2]
INPUTS_PATH = REPO / "inputs_page.py"
PUBLICATION_PATH = REPO / "design_brain" / "publication.py"
VERIFICATION_DIR = REPO / "artifacts" / "verification"
AUDITS_DIR = REPO / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, function_name: str) -> str:
    match = re.search(rf"^def {re.escape(function_name)}\(.*?(?=^def |\Z)", source, re.M | re.S)
    return match.group(0) if match else ""


def main() -> int:
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    inputs_source = _read(INPUTS_PATH)
    publication_source = _read(PUBLICATION_PATH)
    helper_source = _function_source(inputs_source, "_design_guide_button_contract")

    proof_call_count = helper_source.count("build_design_guide_button_contract_execution_proof(")
    append_guard_present = (
        "if button_contract_execution_proof_records is not None:" in helper_source
        and "button_contract_execution_proof_records.append(" in helper_source
    )
    return_unchanged = "return emit_design_guide_button_contract_records(context=emission_context)" in helper_source
    signature_opt_in = (
        "button_contract_execution_proof_records: list[DesignGuideButtonContractExecutionProof] | None = None"
        in helper_source
    )
    proof_not_written_to_contract = (
        "\"button_contract_execution_proof\"" not in helper_source
        and "'button_contract_execution_proof'" not in helper_source
    )
    import_present = (
        "DesignGuideButtonContractExecutionProof" in inputs_source
        and "build_design_guide_button_contract_execution_proof" in inputs_source
    )
    publication_boundary_present = (
        "class DesignGuideButtonContractExecutionProof" in publication_source
        and "def build_design_guide_button_contract_execution_proof" in publication_source
    )
    live_callers = [
        line.strip()
        for line in inputs_source.splitlines()
        if "_design_guide_button_contract(" in line
        and "def _design_guide_button_contract" not in line
        and "button_contract_execution_proof_records" in line
    ]

    failures: list[str] = []
    if not publication_boundary_present:
        failures.append("publication_execution_proof_boundary_missing")
    if not import_present:
        failures.append("inputs_trace_import_missing")
    if not signature_opt_in:
        failures.append("trace_signature_not_opt_in")
    if not append_guard_present:
        failures.append("trace_append_guard_missing")
    if proof_call_count != 1:
        failures.append(f"unexpected_proof_call_count:{proof_call_count}")
    if not return_unchanged:
        failures.append("button_contract_return_path_changed")
    if not proof_not_written_to_contract:
        failures.append("proof_written_into_return_contract")
    if live_callers:
        failures.append("trace_records_passed_by_live_callers")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "status": status,
        "surface": "_design_guide_button_contract",
        "trace_wiring": "optional_records_list",
        "publication_boundary_present": publication_boundary_present,
        "signature_opt_in": signature_opt_in,
        "append_guard_present": append_guard_present,
        "proof_call_count": proof_call_count,
        "return_unchanged": return_unchanged,
        "proof_not_written_to_contract": proof_not_written_to_contract,
        "live_callers_passing_trace_records": live_callers,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "render_apply_session_ownership_changed": False,
        "failures": failures,
    }

    stamp = _timestamp().replace(":", "-")
    json_path = VERIFICATION_DIR / f"design_guide_button_contract_execution_trace_wiring_{stamp}.json"
    md_path = AUDITS_DIR / f"design_guide_button_contract_execution_trace_wiring_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Button Contract Execution Trace Wiring Snapshot",
                "",
                f"## Result: {status}",
                "",
                "## Boundary",
                "",
                "- The trace proof is opt-in through a records list.",
                "- Existing live callers do not pass the trace records list.",
                "- The returned button contract remains produced by `emit_design_guide_button_contract_records(...)`.",
                "- The proof is not written into the returned contract.",
                "",
                "## Failures",
                "",
                "\n".join(f"- {failure}" for failure in failures) if failures else "- None",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design guide button contract execution trace wiring {status}")
    print(json_path)
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
