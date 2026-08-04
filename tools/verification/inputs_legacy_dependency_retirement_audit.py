from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    ROOT
    / "design_brain"
    / "contracts"
    / "inputs_legacy_dependency_retirement_contract.json"
)
ROUTE = ROOT / "inputs_page_route_coordinators.py"
APP = ROOT / "app.py"


def _names(path: Path, prefix: str) -> set[str]:
    if not path.exists():
        return set()
    source = path.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(rf"{re.escape(prefix)}\.([A-Za-z_][A-Za-z0-9_]*)", source))


def _classified(groups: dict[str, list[str]]) -> set[str]:
    return {name for names in groups.values() for name in names}


def _dynamic_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    source = path.read_text(encoding="utf-8", errors="replace")
    return set(
        re.findall(
            r"getattr\(\s*inputs_page_bridge\s*,\s*[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']",
            source,
        )
    )


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    route_source = (
        ROUTE.read_text(encoding="utf-8", errors="replace")
        if ROUTE.exists()
        else ""
    )
    route_live = _names(ROUTE, "_legacy_inputs_page")
    route_module_reference_lines = [
        {
            "line": number,
            "text": line.strip(),
        }
        for number, line in enumerate(route_source.splitlines(), start=1)
        if re.search(r"\b_legacy_inputs_page\b", line)
    ]
    route_import_present = bool(
        re.search(
            r"(?m)^\s*import\s+inputs_page_app_contract_bridge\s+as\s+_legacy_inputs_page\b",
            route_source,
        )
    )
    app_live = _names(APP, "inputs_page_bridge")
    app_dynamic_live = _dynamic_names(APP)
    route_groups = contract["route_dependencies"]
    app_groups = contract["app_dependencies"]
    app_dynamic_groups = contract["app_dynamic_bridge_dependencies"]
    route_classified = _classified(route_groups)
    app_classified = _classified(app_groups)
    app_dynamic_classified = _classified(app_dynamic_groups)
    route_unclassified = sorted(route_live - route_classified)
    app_unclassified = sorted(app_live - app_classified)
    app_dynamic_unclassified = sorted(app_dynamic_live - app_dynamic_classified)
    stale_route_contract = sorted(route_classified - route_live)
    stale_app_contract = sorted(app_classified - app_live)
    failures = [
        *(f"unclassified_route:{name}" for name in route_unclassified),
        *(f"unclassified_app:{name}" for name in app_unclassified),
        *(f"unclassified_app_dynamic:{name}" for name in app_dynamic_unclassified),
    ]
    status = "PASS" if not failures else "FAIL"
    done_condition_met = bool(
        not ROUTE.exists()
        and not (ROOT / "inputs_page_app_contract_bridge.py").exists()
        and not route_live
        and not route_module_reference_lines
        and not route_import_present
        and not app_live
        and not app_dynamic_live
        and not route_unclassified
        and not app_unclassified
        and not app_dynamic_unclassified
    )
    payload = {
        "contract_version": contract["contract_version"],
        "status": status,
        "route": {
            "legacy_file_deleted": not ROUTE.exists(),
            "live_unique_count": len(route_live),
            "legacy_module_reference_count": len(route_module_reference_lines),
            "legacy_module_reference_lines": route_module_reference_lines,
            "bridge_import_present": route_import_present,
            "groups": {
                group: sorted(route_live.intersection(names))
                for group, names in route_groups.items()
            },
            "unclassified": route_unclassified,
            "retired_since_contract": stale_route_contract,
        },
        "app": {
            "legacy_bridge_file_deleted": not (
                ROOT / "inputs_page_app_contract_bridge.py"
            ).exists(),
            "live_unique_count": len(app_live),
            "groups": {
                group: sorted(app_live.intersection(names))
                for group, names in app_groups.items()
            },
            "unclassified": app_unclassified,
            "retired_since_contract": stale_app_contract,
            "dynamic_live_unique_count": len(app_dynamic_live),
            "dynamic_groups": {
                group: sorted(app_dynamic_live.intersection(names))
                for group, names in app_dynamic_groups.items()
            },
            "dynamic_unclassified": app_dynamic_unclassified,
            "bridge_import_present": bool(
                re.search(
                    r"(?m)^\s*import\s+inputs_page_app_contract_bridge\s+as\s+inputs_page_bridge\b",
                    APP.read_text(encoding="utf-8", errors="replace"),
                )
            ),
        },
        "retirement_order": contract["retirement_order"],
        "done_condition_met": done_condition_met,
        "failures": failures,
    }
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    out = (
        ROOT
        / "artifacts"
        / "verification"
        / f"inputs_legacy_dependency_retirement_audit_{stamp}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"artifact={out}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
