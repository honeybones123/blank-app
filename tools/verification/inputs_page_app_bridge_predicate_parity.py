from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _case(name: str, old_fn: Callable[..., Any], new_fn: Callable[..., Any], *args: Any) -> dict[str, Any]:
    expected = old_fn(*args)
    actual = new_fn(*args)
    return {
        "case": name,
        "passed": expected == actual,
        "expected": expected,
        "actual": actual,
    }


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    cases = [
        _case("parse_none", legacy_inputs_page._parse_util_value, bridge._parse_util_value, None),
        _case("parse_empty", legacy_inputs_page._parse_util_value, bridge._parse_util_value, ""),
        _case("parse_dash", legacy_inputs_page._parse_util_value, bridge._parse_util_value, "â€”"),
        _case("parse_float", legacy_inputs_page._parse_util_value, bridge._parse_util_value, "0.91"),
        _case("parse_bad", legacy_inputs_page._parse_util_value, bridge._parse_util_value, "n/a"),
        _case("shear_active_none", legacy_inputs_page._shear_reinforcement_is_active, bridge._shear_reinforcement_is_active, None),
        _case(
            "shear_active_true",
            legacy_inputs_page._shear_reinforcement_is_active,
            bridge._shear_reinforcement_is_active,
            {"lig_legs": 2, "lig_d": 10, "s_lig": 200},
        ),
        _case(
            "shear_active_false_spacing",
            legacy_inputs_page._shear_reinforcement_is_active,
            bridge._shear_reinforcement_is_active,
            {"lig_legs": 2, "lig_d": 10, "s_lig": 0},
        ),
        _case("shear_demands_none", legacy_inputs_page._shear_demands_negligible, bridge._shear_demands_negligible, None),
        _case(
            "shear_demands_true",
            legacy_inputs_page._shear_demands_negligible,
            bridge._shear_demands_negligible,
            {"Vu": 0.2, "Tu": 0.1},
        ),
        _case(
            "shear_demands_false_vu",
            legacy_inputs_page._shear_demands_negligible,
            bridge._shear_demands_negligible,
            {"Vu": 1.1, "Tu": 0.1},
        ),
        _case(
            "shear_demands_false_tu",
            legacy_inputs_page._shear_demands_negligible,
            bridge._shear_demands_negligible,
            {"Vu": 0.2, "Tu": 0.6},
        ),
    ]
    failures = [case["case"] for case in cases if not case["passed"]]
    payload = {
        "audit": "inputs_page_app_bridge_predicate_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_predicate_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_predicate_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Predicate Parity",
                "",
                f"Status: `{payload['status']}`",
                f"Case count: `{payload['case_count']}`",
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
