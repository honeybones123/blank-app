"""Inventory verifier for Family Lock Contract v2 regression ownership.

This is an audit gate, not a runtime gate.  It reports whether each currently
locked family has the v2 pieces needed for permanent regression ownership:
family contract, lock verifier, family-scoped regression, known-error register,
and machine-readable family lock manifest.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FAMILIES_DIR = ROOT / "design_brain" / "families"
VERIFIER_DIR = ROOT / "tools" / "verification" / "families"
CONTRACT_DIR = ROOT / "artifacts" / "contracts" / "families"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

LOCKED_WIRING_SCRIPT = VERIFIER_DIR / "locked_family_live_wiring_snapshot.py"
V2_CONTRACT_PATH = CONTRACT_DIR / "family_lock_contract_v2.json"

REQUIRED_MANIFEST_FIELDS = {
    "family",
    "status",
    "owner",
    "contracts",
    "known_errors",
    "regressions",
    "coverage",
    "last_verified",
    "shared_dependencies",
    "allowed_edit_regions",
    "locked_regions",
}

REQUIRED_KNOWN_ERROR_FIELDS = {
    "id",
    "title",
    "status",
    "root_cause",
    "fix_summary",
    "regression",
    "locked",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def _locked_families_from_live_wiring() -> list[dict[str, str]]:
    source = LOCKED_WIRING_SCRIPT.read_text(encoding="utf-8", errors="ignore")
    rows: list[dict[str, str]] = []
    for block in re.finditer(r"LockedFamily\((.*?)\),", source, flags=re.DOTALL):
        text = block.group(1)
        family_match = re.search(r'family_id="([^"]+)"', text)
        runtime_match = re.search(r'runtime_path="([^"]+)"', text)
        method_match = re.search(r'method_name="([^"]+)"', text)
        authority_match = re.search(r'runtime_authority="([^"]+)"', text)
        if not family_match:
            continue
        runtime_path = runtime_match.group(1) if runtime_match else ""
        package = Path(runtime_path).parent.name if runtime_path else _normalise(family_match.group(1))
        rows.append(
            {
                "family_id": family_match.group(1),
                "package": package,
                "runtime_path": runtime_path,
                "method_name": method_match.group(1) if method_match else "",
                "runtime_authority": authority_match.group(1) if authority_match else "",
            }
        )
    return rows


def _contract_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in FAMILIES_DIR.glob("*/contract.json"):
        data = _read_json(path)
        identity = data.get("family_identity", {})
        family_ids = [
            identity.get("family_id"),
            identity.get("runtime_family_id"),
            data.get("family_id"),
            data.get("runtime_family_id"),
            data.get("family"),
        ]
        for family_id in family_ids:
            if family_id:
                index[str(family_id).upper()] = path
    return index


def _matching_verifier_files(family: dict[str, str], *, kind: str | None = None) -> list[Path]:
    family_token = _normalise(family["family_id"])
    package_token = _normalise(family["package"])
    loose_family_token = family_token.replace("_governs", "").replace("_govern", "")
    matches: list[Path] = []
    for path in VERIFIER_DIR.glob("*.py"):
        stem = _normalise(path.stem)
        if kind and kind not in stem:
            continue
        if (
            family_token in stem
            or package_token in stem
            or loose_family_token in stem
        ):
            matches.append(path)
    return sorted(matches)


def _known_error_register_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "entry_count": 0,
            "valid_entries": 0,
            "invalid_entries": [],
        }
    data = _read_json(path)
    entries = data.get("known_errors", data.get("entries", []))
    if not isinstance(entries, list):
        entries = []
    invalid: list[dict[str, Any]] = []
    valid_count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            invalid.append({"entry": str(entry), "missing": sorted(REQUIRED_KNOWN_ERROR_FIELDS)})
            continue
        missing = sorted(REQUIRED_KNOWN_ERROR_FIELDS - set(entry))
        if missing:
            invalid.append({"id": entry.get("id"), "missing": missing})
        else:
            valid_count += 1
    return {
        "exists": True,
        "entry_count": len(entries),
        "valid_entries": valid_count,
        "invalid_entries": invalid,
    }


def _manifest_status(path: Path, family_id: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "status": None,
            "missing_fields": sorted(REQUIRED_MANIFEST_FIELDS),
            "family_matches": False,
        }
    data = _read_json(path)
    missing = sorted(REQUIRED_MANIFEST_FIELDS - set(data))
    return {
        "exists": True,
        "status": data.get("status"),
        "missing_fields": missing,
        "family_matches": str(data.get("family", "")).upper() == family_id,
    }


def _family_inventory_row(family: dict[str, str], contract_index: dict[str, Path]) -> dict[str, Any]:
    family_id = family["family_id"]
    family_root = FAMILIES_DIR / family["package"]
    contract_path = contract_index.get(family_id)
    contract_data = _read_json(contract_path) if contract_path else {}
    contract_identity = contract_data.get("family_identity", {})
    lock_verifiers = _matching_verifier_files(family, kind="lock")
    regression_files = _matching_verifier_files(family, kind="regression")
    known_errors_path = family_root / "known_errors.json"
    manifest_path = family_root / "family_lock_manifest.json"
    known_errors = _known_error_register_status(known_errors_path)
    manifest = _manifest_status(manifest_path, family_id)

    checks = {
        "family_contract_present": bool(contract_path and contract_path.exists()),
        "lock_verifier_present": bool(lock_verifiers),
        "family_regression_present": bool(regression_files),
        "known_error_register_present": bool(known_errors["exists"]),
        "known_error_register_valid": bool(known_errors["exists"] and not known_errors["invalid_entries"]),
        "family_lock_manifest_present": bool(manifest["exists"]),
        "family_lock_manifest_valid": bool(
            manifest["exists"]
            and not manifest["missing_fields"]
            and manifest["status"] == "LOCKED"
            and manifest["family_matches"]
        ),
    }
    v2_ready = all(checks.values())
    return {
        "family_id": family_id,
        "package": family["package"],
        "runtime_path": family["runtime_path"],
        "runtime_authority": family["runtime_authority"],
        "contract_path": str(contract_path.relative_to(ROOT)) if contract_path else None,
        "contract_family_id": contract_identity.get("family_id"),
        "contract_runtime_family_id": contract_identity.get("runtime_family_id"),
        "lock_verifiers": [str(path.relative_to(ROOT)) for path in lock_verifiers],
        "regression_files": [str(path.relative_to(ROOT)) for path in regression_files],
        "known_errors_path": str(known_errors_path.relative_to(ROOT)),
        "known_errors": known_errors,
        "manifest_path": str(manifest_path.relative_to(ROOT)),
        "manifest": manifest,
        "checks": checks,
        "v2_ready": v2_ready,
        "next_action": (
            "LOCK_V2_READY"
            if v2_ready
            else "add known_errors.json, family_lock_manifest.json, or family regression ownership until checks pass"
        ),
    }


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"family_lock_contract_v2_inventory_{stamp}.json"
    report_path = AUDIT_DIR / f"family_lock_contract_v2_inventory_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report_lines = [
        "# Family Lock Contract v2 Inventory",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Summary",
        "",
        f"- Locked families audited: `{snapshot['summary']['locked_family_count']}`",
        f"- v2 ready: `{snapshot['summary']['v2_ready_count']}`",
        f"- missing known-error register: `{snapshot['summary']['missing_known_error_register_count']}`",
        f"- missing family lock manifest: `{snapshot['summary']['missing_manifest_count']}`",
        f"- missing family regression: `{snapshot['summary']['missing_regression_count']}`",
        "",
        "## Family Inventory",
        "",
        "| Family | Contract | Lock verifier | Regression | Known errors | Manifest | v2 ready |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in snapshot["families"]:
        checks = row["checks"]
        report_lines.append(
            "| `{family}` | {contract} | {lock} | {regression} | {known} | {manifest} | {ready} |".format(
                family=row["family_id"],
                contract="yes" if checks["family_contract_present"] else "no",
                lock="yes" if checks["lock_verifier_present"] else "no",
                regression="yes" if checks["family_regression_present"] else "no",
                known="yes" if checks["known_error_register_present"] else "no",
                manifest="yes" if checks["family_lock_manifest_present"] else "no",
                ready="yes" if row["v2_ready"] else "no",
            )
        )
    report_lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This audit does not change family runtime behaviour. It separates old lock status from v2 regression ownership.",
            "A family is not v2-ready until it has a permanent known-error register, a machine-readable lock manifest, and a family-scoped regression suite.",
            "",
            "## Next Safe Step",
            "",
            "Migrate one locked family at a time by adding its `known_errors.json`, `family_lock_manifest.json`, and permanent regression references, then rerun this inventory.",
            "",
        ]
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    contract = _read_json(V2_CONTRACT_PATH)
    locked_families = _locked_families_from_live_wiring()
    contract_index = _contract_index()
    family_rows = [_family_inventory_row(family, contract_index) for family in locked_families]
    summary = {
        "locked_family_count": len(family_rows),
        "v2_ready_count": sum(1 for row in family_rows if row["v2_ready"]),
        "missing_known_error_register_count": sum(
            1 for row in family_rows if not row["checks"]["known_error_register_present"]
        ),
        "missing_manifest_count": sum(
            1 for row in family_rows if not row["checks"]["family_lock_manifest_present"]
        ),
        "missing_regression_count": sum(
            1 for row in family_rows if not row["checks"]["family_regression_present"]
        ),
    }
    result = "PASS" if family_rows and summary["v2_ready_count"] == len(family_rows) else "PARTIAL"
    snapshot = {
        "schema": "design_brain.family_lock_contract_v2_inventory.v1",
        "result": result,
        "family_lock_contract_v2_path": str(V2_CONTRACT_PATH.relative_to(ROOT)),
        "family_lock_contract_v2_loaded": bool(contract),
        "families": family_rows,
        "summary": summary,
        "scope": {
            "runtime_behaviour_changed": False,
            "visible_wording_changed": False,
            "cta_apply_semantics_changed": False,
            "family_locks_modified": False,
            "inventory_only": True,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    print(f"family lock contract v2 inventory {result}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
