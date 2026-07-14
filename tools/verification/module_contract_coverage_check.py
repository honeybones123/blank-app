from __future__ import annotations

import argparse
import json
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "tools" / "verification" / "module_contract_registry.json"
ARTIFACT_DIR = ROOT / "artifacts" / "contracts"
LEVEL_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _brace_expand(pattern: str) -> list[str]:
    start = pattern.find("{")
    if start < 0:
        return [pattern]
    end = pattern.find("}", start)
    if end < 0:
        return [pattern]
    prefix = pattern[:start]
    suffix = pattern[end + 1 :]
    expanded: list[str] = []
    for option in pattern[start + 1 : end].split(","):
        expanded.extend(_brace_expand(prefix + option.strip() + suffix))
    return expanded


def _matches(path: str, pattern: str) -> bool:
    return any(fnmatch(path, expanded) for expanded in _brace_expand(pattern))


def _is_excluded(path: str, exclude_globs: list[str]) -> bool:
    return any(_matches(path, pattern) for pattern in exclude_globs)


def _inventory_modules(registry: dict[str, Any]) -> list[str]:
    inventory = registry.get("inventory") or {}
    exclude_globs = list(inventory.get("exclude_globs") or [])
    modules: set[str] = set()
    for root_spec in inventory.get("include_roots") or []:
        root = ROOT / str(root_spec.get("path") or ".")
        glob = str(root_spec.get("glob") or "*.py")
        recursive = bool(root_spec.get("recursive"))
        iterator = root.rglob(glob) if recursive else root.glob(glob)
        for path in iterator:
            if not path.is_file():
                continue
            rel = _rel(path)
            if _is_excluded(rel, exclude_globs):
                continue
            modules.add(rel)
    return sorted(modules)


def _find_rule(module: str, registry: dict[str, Any]) -> dict[str, Any] | None:
    for rule in registry.get("role_rules") or []:
        if _matches(module, str(rule.get("glob") or "")):
            return dict(rule)
    return None


def _family_name(module: str) -> str | None:
    parts = module.split("/")
    if len(parts) >= 4 and parts[0] == "design_brain" and parts[1] == "families":
        return parts[2]
    return None


def _evidence_for(module: str, rule: dict[str, Any], registry: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    contract_files = list(rule.get("contract_files") or [])
    verifiers = list(rule.get("verifiers") or [])
    if rule.get("evidence") == "family_contracts":
        family = _family_name(module)
        family_contract = dict((registry.get("family_contracts") or {}).get(str(family), {}) or {})
        contract_files.extend(family_contract.get("contract_files") or [])
        verifiers.extend(family_contract.get("verifiers") or [])
    evidence_files = contract_files + verifiers
    missing = [path for path in evidence_files if not (ROOT / path).exists()]
    return contract_files, verifiers, missing


def _level_gap(rule: dict[str, Any]) -> bool:
    current = LEVEL_ORDER.get(str(rule.get("current_level") or "L0"), -1)
    minimum = LEVEL_ORDER.get(str(rule.get("minimum_level") or "L0"), 0)
    return current < minimum


def _module_record(module: str, rule: dict[str, Any] | None, registry: dict[str, Any]) -> dict[str, Any]:
    if rule is None:
        return {
            "module": module,
            "status": "unclassified",
            "role": None,
            "current_level": None,
            "minimum_level": None,
            "contract_files": [],
            "verifiers": [],
            "missing_evidence": [],
            "accepted_gap": False,
            "accepted_low_risk": False,
            "gap_reason": "No registry rule matched this module.",
        }
    contract_files, verifiers, missing = _evidence_for(module, rule, registry)
    has_level_gap = _level_gap(rule)
    accepted_gap = bool(rule.get("accepted_gap"))
    accepted_low_risk = bool(rule.get("accepted_low_risk"))
    status = "covered"
    if missing:
        status = "missing_evidence"
    elif has_level_gap and accepted_gap:
        status = "accepted_gap"
    elif has_level_gap:
        status = "level_gap"
    elif accepted_low_risk:
        status = "accepted_low_risk"
    return {
        "module": module,
        "status": status,
        "role": rule.get("role"),
        "rule": rule.get("name"),
        "current_level": rule.get("current_level"),
        "minimum_level": rule.get("minimum_level"),
        "contract_files": contract_files,
        "verifiers": verifiers,
        "missing_evidence": missing,
        "accepted_gap": accepted_gap,
        "accepted_low_risk": accepted_low_risk,
        "gap_reason": rule.get("gap_reason") or rule.get("next_level_target") or "",
    }


def build_report() -> dict[str, Any]:
    registry = _load_registry()
    modules = _inventory_modules(registry)
    records = [_module_record(module, _find_rule(module, registry), registry) for module in modules]
    counts: dict[str, int] = {}
    by_role: dict[str, int] = {}
    for record in records:
        counts[str(record["status"])] = counts.get(str(record["status"]), 0) + 1
        role = str(record.get("role") or "unclassified")
        by_role[role] = by_role.get(role, 0) + 1
    hard_failures = [
        record
        for record in records
        if record["status"] in {"unclassified", "missing_evidence", "level_gap"}
    ]
    accepted_gaps = [record for record in records if record["status"] == "accepted_gap"]
    return {
        "schema": "module_contract_coverage_report.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "registry": _rel(REGISTRY_PATH),
        "module_count": len(records),
        "counts": counts,
        "by_role": dict(sorted(by_role.items())),
        "strict_pass": not hard_failures and not accepted_gaps,
        "baseline_pass": not hard_failures,
        "hard_failures": hard_failures,
        "accepted_gaps": accepted_gaps,
        "records": records,
    }


def _write_artifacts(report: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"module_contract_coverage_{stamp}.json"
    md_path = ARTIFACT_DIR / f"module_contract_coverage_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    accepted = report.get("accepted_gaps") or []
    hard = report.get("hard_failures") or []
    md_lines = [
        "# Module Contract Coverage",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- registry: `{report['registry']}`",
        f"- module_count: `{report['module_count']}`",
        f"- baseline_pass: `{report['baseline_pass']}`",
        f"- strict_pass: `{report['strict_pass']}`",
        "",
        "## Counts",
        "",
        *[f"- `{key}`: `{value}`" for key, value in sorted((report.get("counts") or {}).items())],
        "",
        "## Accepted Gaps",
        "",
        *(
            [
                f"- `{row['module']}` ({row.get('role')}, {row.get('current_level')} < {row.get('minimum_level')}): {row.get('gap_reason')}"
                for row in accepted
            ]
            or ["- none"]
        ),
        "",
        "## Hard Failures",
        "",
        *(
            [
                f"- `{row['module']}` ({row.get('status')}): {row.get('gap_reason') or row.get('missing_evidence')}"
                for row in hard
            ]
            or ["- none"]
        ),
    ]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Check production module contract coverage.")
    parser.add_argument("--strict", action="store_true", help="Fail on accepted gaps as well as hard failures.")
    parser.add_argument("--report-only", action="store_true", help="Always exit 0 after writing the report.")
    parser.add_argument("--no-artifact", action="store_true", help="Do not write JSON/Markdown artifacts.")
    args = parser.parse_args()

    report = build_report()
    if args.no_artifact:
        json_path = md_path = None
    else:
        json_path, md_path = _write_artifacts(report)
    print(json.dumps({k: report[k] for k in ("module_count", "counts", "baseline_pass", "strict_pass")}, indent=2, sort_keys=True))
    if json_path and md_path:
        print(f"artifact_json={_rel(json_path)}")
        print(f"artifact_md={_rel(md_path)}")
    if args.report_only:
        return 0
    if args.strict:
        return 0 if report["strict_pass"] else 1
    return 0 if report["baseline_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
