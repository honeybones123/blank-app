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


def _legacy_getattr(module: Any, name: str, default: Any = None) -> Any:
    return getattr(module, name, default)


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    optional_none_hooks = (
        "_complete_exact_blocker_map_from_attempts",
        "_design_guide_blocker_attempts_table",
        "_exact_cleanup_blocker_for_outside_target_action",
        "_post_click_low_bending_resolution_item",
        "_publishable_safe_cleanup_updates_from_evidence",
    )
    constant_fallbacks = {
        "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY": "_design_guide_component_apply_in_flight",
        "DESIGN_GUIDE_PUBLICATION_FP_KEY": "design_guide_publication_fingerprint",
    }

    optional_rows = []
    for name in optional_none_hooks:
        legacy_value = _legacy_getattr(legacy_inputs_page, name, None)
        bridge_value = getattr(bridge, name, None)
        optional_rows.append(
            {
                "name": name,
                "legacy_getattr_default_value": repr(legacy_value),
                "bridge_value": repr(bridge_value),
                "match": legacy_value is bridge_value is None,
            }
        )

    constant_rows = []
    for name, fallback in constant_fallbacks.items():
        legacy_value = _legacy_getattr(legacy_inputs_page, name, fallback)
        bridge_value = getattr(bridge, name)
        constant_rows.append(
            {
                "name": name,
                "legacy_getattr_default_value": repr(legacy_value),
                "bridge_value": repr(bridge_value),
                "match": legacy_value == bridge_value,
            }
        )

    efficiency_match = (
        getattr(bridge, "EFFICIENCY_TARGET_UTIL_MAX", object())
        == getattr(legacy_inputs_page, "EFFICIENCY_TARGET_UTIL_MAX", object())
    )
    checks = {
        "optional_none_hooks_preserve_legacy_getattr_default": all(
            bool(row["match"]) for row in optional_rows
        ),
        "string_constant_fallbacks_preserved": all(bool(row["match"]) for row in constant_rows),
        "efficiency_target_constant_matches_legacy": bool(efficiency_match),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_app_bridge_optional_surface_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "optional_none_hooks": optional_rows,
        "constant_fallbacks": constant_rows,
        "wrapper_note": "explicit bridge symbols preserve previous app getattr fallback behavior after module __getattr__ removal",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_optional_surface_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_optional_surface_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Optional Surface Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Checks",
                "",
                *(f"- `{name}`: `{passed}`" for name, passed in checks.items()),
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
