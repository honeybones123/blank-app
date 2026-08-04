"""Exercise the cut-over production route through the browser transaction matrix."""

from __future__ import annotations

import json
from datetime import datetime

from inputs_one_click_browser_transaction_parity import (
    ROOT,
    _assert_contract,
    _run,
    _updates_digest,
)


CASES = (
    "AB_IN_TARGET_BAND",
    "AB_BLOCKED_INVALID_STATE",
    "A_bending_under_only",
    "B_shear_under_only",
    "C_combined_underdesign",
    "D_bending_overdesign",
    "E_shear_overdesign",
    "F_combined_overdesign",
)


def main() -> int:
    evidence = {
        "gate": "inputs_one_click_production_browser_transactions",
        "generated_at": datetime.now().astimezone().isoformat(),
        "production_route": (
            "inputs_application.one_click_entrypoint.run_one_click_auto_design"
        ),
        "cases": {},
    }
    for case in CASES:
        result = _run(case, "production")
        _assert_contract(case, result)
        evidence["cases"][case] = {
            "result": result,
            "final_updates_sha256": _updates_digest(result),
        }
    evidence["status"] = "PASS"
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifact = (
        ROOT
        / "artifacts/verification"
        / f"inputs_one_click_production_browser_transactions_{stamp}.json"
    )
    artifact.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=True),
        encoding="utf-8",
    )
    print(
        "PASS: cut-over production route browser transactions "
        f"{len(CASES)}/{len(CASES)}; artifact={artifact.relative_to(ROOT)}"
    )
    for case in CASES:
        solver = evidence["cases"][case]["result"]["solver_result"]
        print(f"  {case}: {solver['status']}/{solver['stop_reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
