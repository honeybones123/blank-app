from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUDIT_DIR = ROOT / "artifacts" / "audits"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _has_direct_streamlit_import(source: str) -> bool:
    return bool(re.search(r"^\s*(import\s+streamlit|from\s+streamlit\s+import)\b", source, re.MULTILINE))


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    inputs_source = _read("inputs_page.py")
    models_source = _read("inputs_page_modules/summaries/models.py")
    builders_source = _read("inputs_page_modules/summaries/builders.py")
    contracts_source = _read("inputs_page_modules/summaries/contracts.py")
    init_source = _read("inputs_page_modules/summaries/__init__.py")

    checks = {
        "typed_summary_models_live_in_models_py": all(
            token in models_source
            for token in (
                "class InputsSummaryCardSource",
                "class InputsSummarySourceSnapshot",
                "class SummaryCardViewModel",
                "class InputsSummarySectionViewModel",
            )
        ),
        "summary_view_model_builder_lives_in_builders_py": "def build_inputs_summary_view_model" in builders_source,
        "summary_contracts_live_in_contracts_py": all(
            token in contracts_source
            for token in (
                "CARD_ORDER",
                "REQUIRED_CARD_FIELDS",
                "ALLOWED_STATUS_VALUES",
                "ALLOWED_TONES",
                "DISPLAY_HASH_FIELDS",
                "NO_ENGINEERING_RECALCULATION",
            )
        ),
        "inputs_page_imports_new_models_and_builder": all(
            token in inputs_source
            for token in (
                "InputsSummaryCardSource",
                "InputsSummarySourceSnapshot",
                "build_inputs_summary_view_model",
            )
        ),
        "inputs_page_calls_new_builder_trace_only": "build_inputs_summary_view_model(_summary_source_snapshot)" in inputs_source,
        "inputs_page_records_live_cutover_with_thin_wrapper": all(
            token in inputs_source
            for token in (
                '"summary_view_model_trace_only": False',
                '"live_summary_renderer_cutover": True',
                '"temporary_wrapper_classification": "THIN_WRAPPER_KEEP_TEMPORARILY"',
            )
        ),
        "inputs_page_imports_and_calls_extracted_html_builder": (
            "build_inputs_summary_html" in inputs_source
            and "return build_inputs_summary_html(" in inputs_source
        ),
        "new_summary_modules_do_not_directly_import_streamlit": not any(
            _has_direct_streamlit_import(source)
            for source in (models_source, builders_source, contracts_source, init_source)
        ),
        "new_summary_modules_do_not_call_engineering_solvers_directly": not any(
            token in (models_source + builders_source + contracts_source + init_source)
            for token in (
                "build_bending_check_rows_from_state",
                "build_shear_check_rows_from_state",
                "build_crack_check_rows_from_state",
                "build_deflection_check_rows_from_state",
                "compute_bending_capacity_from_state",
            )
        ),
        "current_renderer_remains_page_or_shared_renderer_owned": all(
            token in inputs_source
            for token in (
                "build_final_summary_check_card_html(",
                "summary_cards_html = _build_summary_cards_html_for_current_state()",
                "st.markdown(f'<div class=\"summary-card-stack\">{summary_cards_html}</div>'",
            )
        ),
        "no_second_active_renderer_created": "render_inputs_summaries(" not in inputs_source,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "inputs_summary_state_extraction_snapshot.v1",
        "generated_at": timestamp,
        "status": status,
        "decision": "SUMMARY_LIVE_CUTOVER_READY_FOR_CLEANUP" if status == "PASS" else "SUMMARY_EXTRACTION_OWNERSHIP_AMBIGUOUS",
        "checks": checks,
        "owner_map": {
            "typed_models": "inputs_page_modules/summaries/models.py",
            "view_model_builder": "inputs_page_modules/summaries/builders.py",
            "contracts": "inputs_page_modules/summaries/contracts.py",
            "live_renderer": "inputs_page.py plus ui.summary_sections",
            "temporary_page_wrapper": "THIN_WRAPPER_KEEP_TEMPORARILY",
        },
        "product_behavior_changed": False,
        "live_cutover_performed": True,
    }

    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_summary_state_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_summary_state_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    report_lines = [
        "# Inputs Summary State Extraction Snapshot",
        "",
        f"Status: `{status}`",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in checks.items():
        report_lines.append(f"- `{key}`: `{value}`")
    report_lines.extend(
        [
            "",
            "## Ownership",
            "",
            "- Typed summary models: `inputs_page_modules/summaries/models.py`",
            "- Summary view-model builder: `inputs_page_modules/summaries/builders.py`",
            "- Summary contracts: `inputs_page_modules/summaries/contracts.py`",
            "- Live renderer: unchanged in `inputs_page.py` / `ui.summary_sections`",
            "- Temporary wrapper: `THIN_WRAPPER_KEEP_TEMPORARILY`",
            "",
            "Live summary HTML generation now uses the extracted summary snapshot/builder while preserving the existing shared renderer.",
        ]
    )
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"inputs_summary_state_extraction_snapshot {status}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
