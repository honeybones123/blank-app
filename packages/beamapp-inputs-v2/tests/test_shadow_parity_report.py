import json
from pathlib import Path


def test_shadow_parity_report_contains_expected_families() -> None:
    report = Path(__file__).parents[1] / "outputs" / "shadow-parity-report.json"
    assert report.exists()
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["schema"] == "inputs_v2.shadow_parity.v1"
    assert len(payload["cases"]) >= 3
    assert {"bending", "shear"}.issubset(set(payload["cases"][0]["shadow_families"]))
