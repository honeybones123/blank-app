from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _sample_overviews() -> list[tuple[dict[str, Any] | None, float]]:
    return [
        (None, 0.70),
        ({}, 0.70),
        (
            {
                "utils": {
                    "bending": 0.92,
                    "shear": 0.44,
                    "crack": 0.0,
                    "deflection": 0.51,
                },
                "governing_check": "bending strength",
            },
            0.70,
        ),
        (
            {
                "utils": {"bending": "0.56", "shear": "0.98", "ductility": "0.69"},
                "governing_family": "shear",
            },
            0.70,
        ),
        (
            {
                "packs": {
                    "bending": {"summary_util": "0.86"},
                    "serviceability": {"summary_util": "0.42"},
                    "shear": {"governing_util": "0.64"},
                },
                "governing_check": "deflection limit",
            },
            0.70,
        ),
        (
            {
                "utils": {"bending": float("nan"), "shear": "not numeric"},
                "bending_util": "0.49",
                "crack_utilisation": "0.0",
                "deflection_util": "0.63",
            },
            0.65,
        ),
        (
            {
                "utils": {"bending": 0.74, "shear": 0.71, "crack": 0.62},
                "governing_family": "overview_worst_util",
            },
            0.75,
        ),
    ]


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for index, (overview, threshold) in enumerate(_sample_overviews()):
        legacy_value = legacy_inputs_page.identify_materially_overprovided_non_governing_families(
            overview,
            threshold=threshold,
        )
        bridge_value = bridge.identify_materially_overprovided_non_governing_families(
            overview,
            threshold=threshold,
        )
        match = legacy_value == bridge_value
        rows.append(
            {
                "index": index,
                "threshold": threshold,
                "match": match,
                "legacy": repr(legacy_value),
                "bridge": repr(bridge_value),
            }
        )
        if not match:
            failures.append(f"sample_{index}_overprovided_family_mismatch")

    payload = {
        "audit": "inputs_page_app_bridge_overprovided_families_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "samples": rows,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_overprovided_families_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_overprovided_families_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Overprovided Families Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Samples",
                "",
                *(f"- sample `{row['index']}` match: `{row['match']}`" for row in rows),
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
