"""Meta-verifier for Design Guide regression contracts.

This script is intentionally product-neutral. It checks that confirmed product
bugs recorded in regression_contract_manifest.json have all five protection
pieces: focused replay, global invariant, permanent suite entry, named failure
classification, and never-regress rule.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
MANIFEST_PATH = REPO / "tools" / "verification" / "regression_contract_manifest.json"
AUDIT_JSON_PATH = REPO / "artifacts" / "verification" / "regression_invariant_audit_2026-05-17.json"
AUDIT_MD_PATH = REPO / "artifacts" / "verification" / "regression_invariant_audit_2026-05-17.md"
VERIFIER_CODE_PATHS = (
    REPO / "tools" / "browser_live_design_guide_fuzz_verifier.py",
    REPO / "tools" / "verification" / "helpers" / "browser_helpers.py",
)
REQUIRED_FIELDS = (
    "id",
    "description",
    "global_invariant",
    "regression_suite",
    "failure_classification",
    "never_regress_rule",
    "date_added",
    "source_artifact_or_screenshot",
    "owner_area",
)


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _normalise_replay(path_value: str) -> str:
    return str(Path(path_value)).replace("\\", "/")


def _entry_replays(entry: dict[str, Any]) -> list[dict[str, str]]:
    if entry.get("focused_replays"):
        result: list[dict[str, str]] = []
        for item in entry.get("focused_replays") or []:
            if isinstance(item, str):
                result.append({"path": _normalise_replay(item), "suite": str(entry.get("regression_suite") or "")})
            elif isinstance(item, dict):
                result.append(
                    {
                        "path": _normalise_replay(str(item.get("path") or item.get("focused_replay") or "")),
                        "suite": str(item.get("suite") or entry.get("regression_suite") or ""),
                    }
                )
        return result
    replay = _normalise_replay(str(entry.get("focused_replay") or ""))
    return [{"path": replay, "suite": str(entry.get("regression_suite") or "")}] if replay else []


def _entry_invariants(entry: dict[str, Any]) -> list[str]:
    names: list[str] = []
    primary = entry.get("global_invariant")
    if isinstance(primary, list):
        names.extend(str(item or "").strip() for item in primary)
    else:
        names.append(str(primary or "").strip())
    names.extend(str(item or "").strip() for item in entry.get("additional_global_invariants") or [])
    return [name for name in names if name]


def _entry_classifications(entry: dict[str, Any]) -> list[str]:
    names: list[str] = []
    primary = entry.get("failure_classification")
    if isinstance(primary, list):
        names.extend(str(item or "").strip() for item in primary)
    else:
        names.append(str(primary or "").strip())
    names.extend(str(item or "").strip() for item in entry.get("failure_classifications") or [])
    return [name for name in names if name]


def _suite_entries() -> dict[str, dict[str, dict[str, Any]]]:
    suites: dict[str, dict[str, dict[str, Any]]] = {
        "previous_fixed": {},
        "fuzz_regression": {},
        "design_guide_contract": {},
    }
    previous = _load_module(REPO / "tools" / "verification" / "previous_fixes_gate.py", "_regression_previous_fixes_gate")
    for replay in getattr(previous, "FIXED_REPLAYS", []):
        path = _normalise_replay(str(getattr(replay, "path", "")))
        suites["previous_fixed"][path] = {
            "name": getattr(replay, "name", ""),
            "failure_classification": getattr(replay, "original_failure_classification", ""),
            "never_regress": getattr(replay, "never_regress", ""),
        }
    fuzz = _load_module(REPO / "tools" / "verification" / "fuzz_regression_gate.py", "_regression_fuzz_regression_gate")
    for replay in getattr(fuzz, "FUZZ_REGRESSION_REPLAYS", []):
        path = _normalise_replay(str(getattr(replay, "path", "")))
        suites["fuzz_regression"][path] = {
            "name": getattr(replay, "name", ""),
            "failure_classification": getattr(replay, "original_failure_classification", ""),
            "never_regress": getattr(replay, "never_regress", ""),
        }
    contract_manifest = REPO / "tools" / "replay_cases" / "design_guide_contract" / "manifest.json"
    if contract_manifest.exists():
        payload = json.loads(contract_manifest.read_text(encoding="utf-8"))
        for case in payload.get("cases", []):
            path = _normalise_replay(str(case.get("case_file") or ""))
            suites["design_guide_contract"][path] = {
                "name": case.get("name") or "",
                "failure_classification": case.get("name") or "",
                "never_regress": case.get("notes") or "",
            }
    return suites


def _verifier_text() -> str:
    parts: list[str] = []
    for path in VERIFIER_CODE_PATHS:
        if path.exists():
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _manifest_entry_errors(
    entry: dict[str, Any],
    seen_ids: set[str],
    suites: dict[str, dict[str, dict[str, Any]]],
    verifier_text: str,
) -> list[str]:
    errors: list[str] = []
    entry_id = str(entry.get("id") or "")
    if entry_id in seen_ids:
        errors.append("duplicate id")
    seen_ids.add(entry_id)
    for field in REQUIRED_FIELDS:
        if not str(entry.get(field) or "").strip():
            errors.append(f"missing {field}")
    replays = _entry_replays(entry)
    if not replays:
        errors.append("missing focused_replay or focused_replays")
    for replay_item in replays:
        replay = replay_item.get("path") or ""
        suite = replay_item.get("suite") or ""
        if replay and not (REPO / replay).exists():
            errors.append(f"missing replay file: {replay}")
        if suite not in suites:
            errors.append(f"unknown regression suite {suite!r}")
        elif replay not in suites[suite]:
            errors.append(f"replay not included in regression suite: {suite}:{replay}")
    for invariant in _entry_invariants(entry):
        if invariant not in verifier_text:
            errors.append(f"invariant name not referenced by verifier code: {invariant}")
    for classification in _entry_classifications(entry):
        if classification not in verifier_text:
            errors.append(f"failure classification not referenced by verifier code: {classification}")
    return errors


def _audit_suite_rows(
    suites: dict[str, dict[str, dict[str, Any]]],
    entries: list[dict[str, Any]],
    verifier_text: str,
) -> list[dict[str, Any]]:
    entries_by_replay: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        for replay in _entry_replays(entry):
            entries_by_replay.setdefault(replay.get("path") or "", []).append(entry)
    rows: list[dict[str, Any]] = []
    for suite_name, suite_replays in suites.items():
        for replay_path, replay in sorted(suite_replays.items()):
            manifest_entries = entries_by_replay.get(replay_path, [])
            invariant_names = [name for item in manifest_entries for name in _entry_invariants(item)]
            classifications = [name for item in manifest_entries for name in _entry_classifications(item)]
            rows.append(
                {
                    "suite": suite_name,
                    "name": replay.get("name") or "",
                    "replay_path": replay_path,
                    "replay_exists": bool((REPO / replay_path).exists()),
                    "global_invariant_exists": any(name and name in verifier_text for name in invariant_names),
                    "regression_suite_entry_exists": True,
                    "named_failure_classification_exists": any(name and name in verifier_text for name in classifications),
                    "never_regress_note_exists": bool(replay.get("never_regress") or any(item.get("never_regress_rule") for item in manifest_entries)),
                    "manifest_entry_exists": bool(manifest_entries),
                    "manifest_ids": [item.get("id") for item in manifest_entries],
                }
            )
    return rows


def _write_audit(payload: dict[str, Any]) -> None:
    AUDIT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_JSON_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    rows = payload.get("suite_audit", [])
    manifest_results = payload.get("manifest_results", [])
    lines = [
        "# Regression Invariant Audit",
        "",
        f"- Status: **{payload.get('status')}**",
        f"- Failure classification: `{payload.get('failure_classification')}`",
        f"- Manifest: `{payload.get('manifest_path')}`",
        f"- Entries: `{payload.get('manifest_entry_count')}`",
        f"- Suite rows audited: `{len(rows)}`",
        "",
        "## Manifest Contract Results",
        "",
        "| id | replay | suite | invariant | classification | errors |",
        "|---|---|---|---|---|---|",
    ]
    for item in manifest_results:
        replay_display = item.get("focused_replay") or ", ".join(item.get("focused_replays") or [])
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("id") or ""),
                    f"`{replay_display}`",
                    str(item.get("regression_suite") or ""),
                    str(item.get("global_invariant") or ""),
                    str(item.get("failure_classification") or ""),
                    "; ".join(item.get("errors") or []) or "none",
                ]
            )
            + " |"
        )
    gaps = [row for row in rows if not row.get("manifest_entry_exists")]
    lines.extend(
        [
            "",
            "## Legacy Suite Coverage Gaps",
            "",
            "These replay rows already live in permanent gates, but do not yet have entries in the new manifest.",
            "",
            "| suite | replay | replay exists | manifest entry | global invariant | failure classification | never-regress note |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("suite") or ""),
                    str(row.get("name") or row.get("replay_path") or ""),
                    str(bool(row.get("replay_exists"))),
                    str(bool(row.get("manifest_entry_exists"))),
                    str(bool(row.get("global_invariant_exists"))),
                    str(bool(row.get("named_failure_classification_exists"))),
                    str(bool(row.get("never_regress_note_exists"))),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Manifest entries with errors: `{payload.get('manifest_error_count')}`",
            f"- Legacy suite entries missing manifest rows: `{len(gaps)}`",
            "- The meta-verifier fails incomplete manifest entries. Legacy gaps are reported so they can be promoted deliberately without blocking today's focused hard-rule contract.",
        ]
    )
    AUDIT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    manifest = _load_manifest()
    entries = list(manifest.get("entries") or [])
    suites = _suite_entries()
    verifier_text = _verifier_text()
    seen_ids: set[str] = set()
    manifest_results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for entry in entries:
        entry_errors = _manifest_entry_errors(entry, seen_ids, suites, verifier_text)
        result = {
            "id": entry.get("id"),
            "focused_replay": entry.get("focused_replay"),
            "focused_replays": [item.get("path") for item in _entry_replays(entry)],
            "regression_suite": entry.get("regression_suite"),
            "global_invariant": entry.get("global_invariant"),
            "additional_global_invariants": entry.get("additional_global_invariants") or [],
            "failure_classification": entry.get("failure_classification"),
            "failure_classifications": entry.get("failure_classifications") or [],
            "never_regress_rule": entry.get("never_regress_rule"),
            "errors": entry_errors,
        }
        manifest_results.append(result)
        if entry_errors:
            errors.append(result)
    suite_audit = _audit_suite_rows(suites, entries, verifier_text)
    payload = {
        "status": "PASS" if not errors else "FAIL",
        "failure_classification": "" if not errors else "regression_contract_incomplete",
        "manifest_path": _repo_rel(MANIFEST_PATH),
        "audit_json_path": _repo_rel(AUDIT_JSON_PATH),
        "audit_markdown_path": _repo_rel(AUDIT_MD_PATH),
        "manifest_entry_count": len(entries),
        "manifest_error_count": len(errors),
        "manifest_results": manifest_results,
        "suite_audit": suite_audit,
        "suite_counts": {name: len(items) for name, items in suites.items()},
    }
    _write_audit(payload)
    print(json.dumps({k: payload[k] for k in ("status", "failure_classification", "audit_json_path", "audit_markdown_path", "manifest_error_count")}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
