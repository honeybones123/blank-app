from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "design_brain" / "contracts" / "inputs_legacy_freeze_contract.json"
ROUTE = ROOT / "inputs_page_route_coordinators.py"
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
APP = ROOT / "app.py"
REPLACEMENT = ROOT / "inputs_application"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_count(path: Path) -> int:
    return len(_text(path).splitlines())


def _reference_count(path: Path, pattern: str) -> int:
    return len(re.findall(pattern, _text(path)))


def main() -> int:
    contract = json.loads(_text(CONTRACT))
    ceilings = contract["ceilings"]
    replacement_source = "\n".join(
        _text(path) for path in sorted(REPLACEMENT.rglob("*.py"))
    )
    measurements = {
        "route_line_count": _line_count(ROUTE),
        "route_legacy_attribute_reference_count": _reference_count(
            ROUTE, r"_legacy_inputs_page\."
        ),
        "route_legacy_module_reference_count": _reference_count(
            ROUTE, r"\b_legacy_inputs_page\b"
        ),
        "bridge_line_count": _line_count(BRIDGE),
        "app_bridge_attribute_reference_count": _reference_count(
            APP, r"inputs_page_bridge\."
        ),
        "app_bridge_module_reference_count": _reference_count(
            APP, r"\binputs_page_bridge\b"
        ),
    }
    checks = {
        "route_line_count_did_not_grow": measurements["route_line_count"]
        <= ceilings[ROUTE.name]["line_count"],
        "route_legacy_references_did_not_grow":
        measurements["route_legacy_attribute_reference_count"]
        <= ceilings[ROUTE.name]["legacy_attribute_reference_count"],
        "route_legacy_module_references_did_not_grow":
        measurements["route_legacy_module_reference_count"]
        <= ceilings[ROUTE.name]["legacy_module_reference_count"],
        "bridge_line_count_did_not_grow": measurements["bridge_line_count"]
        <= ceilings[BRIDGE.name]["line_count"],
        "app_bridge_references_did_not_grow":
        measurements["app_bridge_attribute_reference_count"]
        <= ceilings[APP.name]["bridge_attribute_reference_count"],
        "app_bridge_module_references_did_not_grow":
        measurements["app_bridge_module_reference_count"]
        <= ceilings[APP.name]["bridge_module_reference_count"],
        "replacement_does_not_import_route_bridge":
        "inputs_page_route_coordinators" not in replacement_source,
        "replacement_does_not_import_app_contract_bridge":
        "inputs_page_app_contract_bridge" not in replacement_source,
        "replacement_does_not_access_legacy_alias":
        "_legacy_inputs_page" not in replacement_source,
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "contract_version": contract["contract_version"],
        "status": "PASS" if not failures else "FAIL",
        "measurements": measurements,
        "checks": checks,
        "failures": failures,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
