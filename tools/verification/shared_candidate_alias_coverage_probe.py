from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_CONTRACT = Path("artifacts/contracts/shared_candidate_contract.json")
DEFAULT_ALIAS_MAP = Path("artifacts/contracts/shared_candidate_alias_map.json")
DEFAULT_ARTIFACT_ROOT = Path("artifacts/verification")
DEFAULT_OUTPUT_DIR = Path("artifacts/verification")

COVERAGE_CATEGORIES = (
    "covered",
    "alias_covered",
    "missing",
    "ambiguous",
    "not_applicable",
    "high_risk_mismatch",
)

SEVERITY_BY_CATEGORY = {
    "covered": "informational",
    "alias_covered": "informational",
    "not_applicable": "informational",
    "missing": "warning",
    "ambiguous": "warning",
    "high_risk_mismatch": "high_warning",
}

SEVERITY_ORDER = (
    "informational",
    "warning",
    "high_warning",
)

CONTENT_REPAIR_TOKENS = (
    "active_fail_repair_candidate_rows",
    "repair_search_ran",
    "repair_search_exhaustive",
    "safe_repair_candidate_count",
    "executable_repair_candidate_count",
)

CONTENT_OPTIMISATION_TOKENS = (
    "candidate_search_evidence",
    "local_cleanup_search_ran",
    "local_cleanup_search_exhaustive",
    "target_band_candidate_count",
    "safe_executor_backed_candidates",
)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _jsonable_preview(value: Any, *, limit: int = 160) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        text = value
    elif isinstance(value, dict):
        text = {str(k): value[k] for k in list(value.keys())[:6]}
    elif isinstance(value, list):
        text = value[:4]
    else:
        text = str(value)
    rendered = json.dumps(text, sort_keys=True, default=str)
    if len(rendered) > limit:
        return rendered[: limit - 3] + "..."
    return text


def _walk_dicts(value: Any, path: str = "$"):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            child_path = f"{path}.{key}" if path != "$" else f"$.{key}"
            yield from _walk_dicts(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_dicts(child, f"{path}[{index}]")


def _get_dotted(node: dict[str, Any], parts: list[str]) -> tuple[bool, Any]:
    current: Any = node
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current.get(part)
    return True, current


def _find_field_occurrences(value: Any, field_name: str, *, limit: int = 8) -> list[dict[str, Any]]:
    if not field_name:
        return []
    parts = str(field_name).split(".")
    found: list[dict[str, Any]] = []
    for base_path, node in _walk_dicts(value):
        if len(found) >= limit:
            break
        if len(parts) == 1:
            if field_name in node:
                found.append(
                    {
                        "field": field_name,
                        "path": f"{base_path}.{field_name}" if base_path != "$" else f"$.{field_name}",
                        "value_preview": _jsonable_preview(node.get(field_name)),
                    }
                )
        else:
            exists, matched = _get_dotted(node, parts)
            if exists:
                found.append(
                    {
                        "field": field_name,
                        "path": f"{base_path}.{field_name}" if base_path != "$" else f"$.{field_name}",
                        "value_preview": _jsonable_preview(matched),
                    }
                )
    return found


def _contains_any_text(path: Path, tokens: tuple[str, ...], *, max_bytes: int = 8_000_000) -> bool:
    try:
        if path.stat().st_size > max_bytes:
            return False
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    lower = text.lower()
    return any(token.lower() in lower for token in tokens)


def _artifact_kind(path: Path) -> str:
    text = str(path).replace("\\", "/").lower()
    if "previous_fixes" in text or "previous-fixed" in text:
        return "previous_fixed"
    if "optimisation" in text or "optimization" in text or "cleanup" in text:
        return "optimisation"
    if "repair" in text or "active_fail" in text or "underdesign" in text:
        return "repair"
    return "unknown"


def _artifact_kind_from_data(path: Path, data: Any) -> str:
    kind = _artifact_kind(path)
    if kind != "unknown":
        return kind
    for token in CONTENT_REPAIR_TOKENS:
        if _find_field_occurrences(data, token, limit=1):
            return "repair"
    for token in CONTENT_OPTIMISATION_TOKENS:
        if _find_field_occurrences(data, token, limit=1):
            return "optimisation"
    return kind


def _candidate_artifact_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files = [
        path
        for path in root.rglob("*.json")
        if path.is_file()
        and not path.name.startswith("shared_candidate_alias_coverage_")
        and path.name != "shared_candidate_alias_map.json"
        and path.name != "shared_candidate_contract.json"
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def _select_default_artifacts(root: Path, *, max_scan: int = 200) -> tuple[list[Path], list[str]]:
    files = _candidate_artifact_files(root)[:max_scan]
    selected: list[Path] = []
    gaps: list[str] = []

    def add_first(predicate) -> Path | None:
        for path in files:
            if path in selected:
                continue
            if predicate(path):
                selected.append(path)
                return path
        return None

    previous = add_first(lambda p: _artifact_kind(p) == "previous_fixed")
    optimisation = add_first(lambda p: _artifact_kind(p) == "optimisation")
    repair = add_first(lambda p: _artifact_kind(p) == "repair")

    if repair is None:
        repair = add_first(lambda p: _contains_any_text(p, CONTENT_REPAIR_TOKENS))
    if optimisation is None:
        optimisation = add_first(lambda p: _contains_any_text(p, CONTENT_OPTIMISATION_TOKENS))

    # If a previous-fixed artifact contains repair evidence, it still covers the
    # required repair class for this read-only probe, but keep the gap explicit.
    if previous is None:
        gaps.append("missing_previous_fixed_artifact")
    if optimisation is None:
        gaps.append("missing_optimisation_artifact")
    if repair is None:
        gaps.append("missing_repair_artifact")

    # Add a couple of recent evidence-rich artifacts for broader coverage without
    # turning this into an expensive full-artifact scan.
    for path in files:
        if len(selected) >= 6:
            break
        if path in selected:
            continue
        kind = _artifact_kind(path)
        if kind in {"previous_fixed", "optimisation", "repair"}:
            selected.append(path)

    return selected, gaps


def _field_names_from_contract(contract: dict[str, Any]) -> set[str]:
    fields: set[str] = set()
    candidate_schema = dict(contract.get("candidate_schema") or {})
    fields.update(str(x) for x in candidate_schema.get("required_fields") or [])
    fields.update(str(x) for x in dict(candidate_schema.get("fields") or {}).keys())

    evaluation_schema = dict(contract.get("evaluation_schema") or {})
    fields.update(str(x) for x in evaluation_schema.get("required_fields") or [])
    fields.update(str(x) for x in dict(evaluation_schema.get("fields") or {}).keys())

    evidence_schema = dict(contract.get("shared_evidence_schema") or {})
    fields.update(str(x) for x in evidence_schema.get("candidate_search_evidence_fields") or [])
    row_shape = dict(evidence_schema.get("row_shape") or {})
    fields.update(str(x) for x in row_shape.get("required_or_recommended_fields") or [])
    for section in ("safe_executable_proof", "rejected_proof", "target_band_proof", "exact_stop_proof"):
        section_payload = dict(evidence_schema.get(section) or {})
        fields.update(str(x) for x in section_payload.get("required_or_recommended_fields") or [])
    return {field for field in fields if field and field != "None"}


def _mappings_by_field(alias_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in alias_map.get("mappings") or []:
        if isinstance(row, dict) and str(row.get("canonical_field") or "").strip():
            out[str(row.get("canonical_field")).strip()] = row
    return out


def _mapping_for_field(field: str, mappings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if field in mappings:
        return dict(mappings[field])
    return {
        "canonical_field": field,
        "category": "unmapped",
        "product_fields": [],
        "verifier_fields": [],
        "status": "missing in product",
        "drift_risk": "high",
        "notes": "Field appears in the shared contract but has no alias-map entry.",
    }


def _classify_coverage(
    *,
    mapping: dict[str, Any],
    canonical_found: bool,
    product_found: bool,
    verifier_found: bool,
    artifact_has_candidate_context: bool,
) -> str:
    if not artifact_has_candidate_context:
        return "not_applicable"
    if canonical_found:
        return "covered"
    if product_found or verifier_found:
        status = str(mapping.get("status") or "").strip().lower()
        risk = str(mapping.get("drift_risk") or "").strip().lower()
        if status == "ambiguous":
            return "ambiguous"
        if risk == "high":
            return "high_risk_mismatch"
        return "alias_covered"
    return "missing"


def _artifact_has_candidate_context(data: Any) -> bool:
    keys = {
        "candidate_search_evidence",
        "candidate_rows",
        "active_fail_repair_candidate_rows",
        "button_contract",
        "candidate_id",
        "source_candidate_id",
        "safe_executor_backed_candidates",
        "target_band_candidates",
    }
    for _path, node in _walk_dicts(data):
        if any(key in node for key in keys):
            return True
    return False


def _inspect_artifact(path: Path, fields: list[str], mappings: dict[str, dict[str, Any]], repo_root: Path) -> dict[str, Any]:
    try:
        data = _load_json(path)
    except Exception as exc:
        return {
            "path": str(path),
            "relative_path": str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path),
            "kind": _artifact_kind(path),
            "parsed": False,
            "error": str(exc),
            "field_results": [],
            "coverage_summary": {category: 0 for category in COVERAGE_CATEGORIES},
        }

    has_context = _artifact_has_candidate_context(data)
    kind = _artifact_kind_from_data(path, data)
    field_results: list[dict[str, Any]] = []
    summary = Counter()

    for field in fields:
        mapping = _mapping_for_field(field, mappings)
        product_fields = [str(x) for x in mapping.get("product_fields") or [] if str(x).strip()]
        verifier_fields = [str(x) for x in mapping.get("verifier_fields") or [] if str(x).strip()]
        canonical_hits = _find_field_occurrences(data, field)
        product_hits: list[dict[str, Any]] = []
        verifier_hits: list[dict[str, Any]] = []
        for alias in product_fields:
            if alias == field:
                continue
            product_hits.extend(_find_field_occurrences(data, alias, limit=max(1, 8 - len(product_hits))))
            if len(product_hits) >= 8:
                break
        for alias in verifier_fields:
            if alias == field:
                continue
            verifier_hits.extend(_find_field_occurrences(data, alias, limit=max(1, 8 - len(verifier_hits))))
            if len(verifier_hits) >= 8:
                break

        category = _classify_coverage(
            mapping=mapping,
            canonical_found=bool(canonical_hits),
            product_found=bool(product_hits),
            verifier_found=bool(verifier_hits),
            artifact_has_candidate_context=has_context,
        )
        summary[category] += 1
        field_results.append(
            {
                "canonical_field": field,
                "artifact_source": str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path),
                "coverage_category": category,
                "drift_risk": mapping.get("drift_risk") or "high",
                "alias_status": mapping.get("status") or "missing in product",
                "product_aliases": product_fields,
                "verifier_aliases": verifier_fields,
                "canonical_found": bool(canonical_hits),
                "product_alias_found": bool(product_hits),
                "verifier_alias_found": bool(verifier_hits),
                "canonical_hits": canonical_hits[:4],
                "product_alias_hits": product_hits[:4],
                "verifier_alias_hits": verifier_hits[:4],
                "notes": mapping.get("notes") or "",
            }
        )

    return {
        "path": str(path),
        "relative_path": str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path),
        "kind": kind,
        "parsed": True,
        "candidate_context_found": bool(has_context),
        "field_results": field_results,
        "coverage_summary": {category: int(summary.get(category, 0)) for category in COVERAGE_CATEGORIES},
    }


def _write_markdown_summary(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Shared Candidate Alias Coverage",
        "",
        f"Timestamp: `{report['metadata']['timestamp']}`",
        "",
        "## Coverage Summary",
        "",
    ]
    for key, value in report.get("coverage_summary", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Severity Summary", ""])
    for key, value in report.get("severity_summary", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Artifact Set", ""])
    for artifact in report.get("artifact_set", []):
        lines.append(
            f"- `{artifact.get('relative_path')}`: kind=`{artifact.get('kind')}`, "
            f"parsed=`{artifact.get('parsed')}`, candidate_context=`{artifact.get('candidate_context_found')}`"
        )
    lines.extend(["", "## High Risk Findings", ""])
    findings = report.get("high_risk_findings", [])
    if not findings:
        lines.append("- None.")
    else:
        for row in findings[:40]:
            lines.append(
                f"- `{row.get('canonical_field')}` in `{row.get('artifact_source')}`: "
                f"{row.get('coverage_category')} ({row.get('notes')})"
            )
    lines.extend(["", "## Missing Or Ambiguous Findings", ""])
    warning_findings = report.get("missing_ambiguous_findings", [])
    if not warning_findings:
        lines.append("- None.")
    else:
        for row in warning_findings[:40]:
            lines.append(
                f"- `{row.get('canonical_field')}` in `{row.get('artifact_source')}`: "
                f"{row.get('coverage_category')} ({row.get('notes')})"
            )
    lines.extend(["", "## Recommendations", ""])
    for item in report.get("recommendations", []):
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_report(
    *,
    contract_path: Path,
    alias_map_path: Path,
    artifact_paths: list[Path],
    output_dir: Path,
    write_md: bool,
    repo_root: Path,
    artifact_gaps: list[str],
) -> tuple[dict[str, Any], Path, Path | None]:
    contract = _load_json(contract_path)
    alias_map = _load_json(alias_map_path)
    fields = sorted(_field_names_from_contract(contract) | set(_mappings_by_field(alias_map).keys()))
    mappings = _mappings_by_field(alias_map)

    artifact_reports = [_inspect_artifact(path, fields, mappings, repo_root) for path in artifact_paths]
    summary = Counter()
    all_results: list[dict[str, Any]] = []
    for artifact in artifact_reports:
        for category, count in dict(artifact.get("coverage_summary") or {}).items():
            summary[category] += int(count or 0)
        all_results.extend(list(artifact.get("field_results") or []))

    high_risk = [
        row
        for row in all_results
        if row.get("coverage_category") in {"high_risk_mismatch", "ambiguous", "missing"}
        and row.get("drift_risk") in {"high", "medium"}
    ]
    high_risk_mismatches = [
        row for row in all_results if row.get("coverage_category") == "high_risk_mismatch"
    ]
    missing_ambiguous = [
        row for row in all_results if row.get("coverage_category") in {"missing", "ambiguous"}
    ]
    severity_summary = Counter()
    for category, count in summary.items():
        severity_summary[SEVERITY_BY_CATEGORY.get(category, "warning")] += int(count or 0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"shared_candidate_alias_coverage_{timestamp}.json"
    md_path = output_dir / f"shared_candidate_alias_coverage_{timestamp}.md" if write_md else None
    report = {
        "metadata": {
            "probe_id": "design_brain.shared_candidate_alias_coverage_probe",
            "timestamp": timestamp,
            "contract_path": str(contract_path),
            "alias_map_path": str(alias_map_path),
            "runtime_loading": False,
            "non_failing": True,
            "coverage_categories": list(COVERAGE_CATEGORIES),
            "severity_by_category": dict(SEVERITY_BY_CATEGORY),
            "total_canonical_fields_checked": len(fields),
        },
        "artifact_selection": {
            "artifact_root": str(DEFAULT_ARTIFACT_ROOT),
            "artifact_count": len(artifact_paths),
            "minimum_artifact_gaps": artifact_gaps,
        },
        "artifact_set": [
            {
                "path": item.get("path"),
                "relative_path": item.get("relative_path"),
                "kind": item.get("kind"),
                "parsed": item.get("parsed"),
                "candidate_context_found": item.get("candidate_context_found", False),
                "coverage_summary": item.get("coverage_summary", {}),
                **({"error": item.get("error")} if item.get("error") else {}),
            }
            for item in artifact_reports
        ],
        "coverage_summary": {category: int(summary.get(category, 0)) for category in COVERAGE_CATEGORIES},
        "severity_summary": {severity: int(severity_summary.get(severity, 0)) for severity in SEVERITY_ORDER},
        "artifact_sources_inspected": [
            {
                "relative_path": item.get("relative_path"),
                "kind": item.get("kind"),
                "parsed": item.get("parsed"),
                "candidate_context_found": item.get("candidate_context_found", False),
            }
            for item in artifact_reports
        ],
        "field_results": all_results,
        "high_risk_findings": high_risk[:120],
        "high_risk_mismatch_findings": high_risk_mismatches[:120],
        "missing_ambiguous_findings": missing_ambiguous[:120],
        "recommendations": [
            "Keep this probe warning-only and non-failing until selected checks are explicitly promoted in a later phase.",
            "Do not load shared candidate contracts in product or verifier runtime yet.",
            "Prioritise additive alias work for high-risk fields: safe, executor_backed, updates, preview, evidence, apply_payload_ref, blocker_reason, exact_stop_reason.",
            "Keep _build_candidate_search_evidence(...) deferred until full evidence-parity verification exists.",
            "Next action: Phase 5.9 should plan selected failing checks only after warning-only reports are stable.",
        ],
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    if md_path is not None:
        _write_markdown_summary(report, md_path)
    return report, report_path, md_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only shared candidate alias coverage probe.")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--alias-map", type=Path, default=DEFAULT_ALIAS_MAP)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--artifact", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-md", action="store_true", help="Do not write the optional Markdown summary.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or sys.argv[1:]))
    repo_root = Path.cwd()
    contract_path = args.contract
    alias_map_path = args.alias_map
    artifact_gaps: list[str] = []

    if not contract_path.exists():
        print(f"Contract JSON not found: {contract_path}", file=sys.stderr)
        return 2
    if not alias_map_path.exists():
        print(f"Alias map JSON not found: {alias_map_path}", file=sys.stderr)
        return 2

    if args.artifact:
        artifact_paths = [path for path in args.artifact if path.exists()]
        missing = [str(path) for path in args.artifact if not path.exists()]
        artifact_gaps.extend(f"explicit_artifact_missing:{path}" for path in missing)
    else:
        artifact_paths, artifact_gaps = _select_default_artifacts(args.artifact_root)

    report, report_path, md_path = _build_report(
        contract_path=contract_path,
        alias_map_path=alias_map_path,
        artifact_paths=artifact_paths,
        output_dir=args.output_dir,
        write_md=not args.no_md,
        repo_root=repo_root,
        artifact_gaps=artifact_gaps,
    )

    print(f"Wrote JSON report: {report_path}")
    if md_path is not None:
        print(f"Wrote Markdown summary: {md_path}")
    print("Coverage summary:")
    for category in COVERAGE_CATEGORIES:
        print(f"  {category}: {report['coverage_summary'].get(category, 0)}")
    print("Severity summary:")
    for severity in SEVERITY_ORDER:
        print(f"  {severity}: {report['severity_summary'].get(severity, 0)}")
    high_warning_count = report["severity_summary"].get("high_warning", 0)
    warning_count = report["severity_summary"].get("warning", 0)
    if warning_count or high_warning_count:
        print(
            "Warning-only: coverage gaps were reported but do not fail this probe "
            f"(warning={warning_count}, high_warning={high_warning_count})."
        )
    if report.get("high_risk_mismatch_findings"):
        print("High-risk mismatch sample:")
        for row in report["high_risk_mismatch_findings"][:8]:
            print(f"  {row.get('canonical_field')} in {row.get('artifact_source')}")
    if artifact_gaps:
        print("Artifact coverage gaps:")
        for gap in artifact_gaps:
            print(f"  {gap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
