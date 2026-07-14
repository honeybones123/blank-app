"""Audit Design Brain contract enforcement closure.

This verifier is intentionally proof-only. It does not execute product paths or
change behaviour; it maps declared contracts to runtime, callsite, and verifier
evidence so scalar rules and strategy ladders cannot drift quietly.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FAMILY_ROOT = ROOT / "design_brain" / "families"
VERIFICATION_ROOT = ROOT / "tools" / "verification"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

FORBIDDEN_PAGE_AUTHORITY_IMPORT_RE = re.compile(
    r"from\s+design_brain\.families\.[\w_]+\.contract\s+import|"
    r"import\s+design_brain\.families\.[\w_]+\.contract"
)

MUTATION_SURFACE_PATTERNS = {
    "geometry": (
        r"updates\[[\"']D[\"']\]",
        r"updates\[[\"']b[\"']\]",
        r"\bD\s*=",
        r"\bb\s*=",
        r"beam_width",
        r"beam_b",
    ),
    "bending_reinforcement": (
        r"db_bot_",
        r"bot_row_",
        r"bot\d+_count",
        r"s_bot",
    ),
    "shear_reinforcement": (
        r"s_lig",
        r"lig_d",
        r"lig_legs",
    ),
    "publication": (
        r"resolve_final_visible_design_guide_item",
        r"_publish_final_visible_design_guide_contract_binding",
        r"FinalDesignGuidePublication",
    ),
}

STATUS_CLOSED = "CLOSED"
STATUS_PARTIAL = "PARTIAL"
STATUS_DECLARED_ONLY = "DECLARED_ONLY"
STATUS_ENFORCED_UNVERIFIED = "ENFORCED_BUT_UNVERIFIED"
STATUS_BYPASS_RISK = "BYPASS_RISK"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        return {"_json_error": str(exc)}


def _module_imports(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(set(imports))


def _contract_lanes(contract: dict[str, Any]) -> list[str]:
    ladder = contract.get("internal_strategy_ladder")
    if isinstance(ladder, dict):
        lanes = ladder.get("lanes")
        if isinstance(lanes, list):
            sorted_lanes = sorted(
                (lane for lane in lanes if isinstance(lane, dict)),
                key=lambda lane: int(lane.get("lane_index") or 0),
            )
            return [str(lane.get("lane_id") or "") for lane in sorted_lanes]
    repair_ladder = contract.get("repair_ladder")
    if isinstance(repair_ladder, dict) and isinstance(repair_ladder.get("ordered_lanes"), list):
        return [str(lane or "") for lane in repair_ladder.get("ordered_lanes") or []]
    return []


def _contract_kind(contract: dict[str, Any]) -> str:
    if isinstance(contract.get("internal_strategy_ladder"), dict):
        return "internal_strategy_ladder"
    if isinstance(contract.get("repair_ladder"), dict):
        return "repair_ladder"
    if isinstance(contract.get("candidate_source_contract"), dict):
        return "merge_or_source_contract"
    if isinstance(contract.get("ranking"), dict):
        return "ranking_contract"
    return "result_or_rule_contract"


def _family_id(contract: dict[str, Any], contract_path: Path) -> str:
    identity = contract.get("family_identity")
    if isinstance(identity, dict) and identity.get("family_id"):
        return str(identity.get("family_id"))
    ladder = contract.get("internal_strategy_ladder")
    if isinstance(ladder, dict) and ladder.get("family_id"):
        return str(ladder.get("family_id"))
    return contract_path.parent.name.upper()


def _verification_index() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(VERIFICATION_ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        text = _read_text(path)
        rows.append(
            {
                "path": rel,
                "text": text,
                "is_contract_check": "contract_check" in path.name,
                "is_lock_verifier": "lock_verifier" in path.name,
                "is_runtime_snapshot": "runtime" in path.name and "snapshot" in path.name,
                "is_lane_snapshot": "lane" in path.name and "snapshot" in path.name,
                "is_cutover": "cutover" in path.name,
                "is_readiness_or_regression": any(
                    term in path.name for term in ("readiness", "regression", "boundary", "parity")
                ),
            }
        )
    return rows


def _matching_verifiers(family_id: str, package_name: str, index: list[dict[str, Any]]) -> dict[str, list[str]]:
    needles = {
        family_id,
        package_name,
        family_id.lower(),
        package_name.lower(),
    }
    matches = {"contract_checks": [], "lock_verifiers": [], "runtime_snapshots": [], "lane_snapshots": [], "cutover": []}
    for row in index:
        haystack = f"{row['path']}\n{row['text']}"
        haystack_lower = haystack.lower()
        if not any(str(needle).lower() in haystack_lower for needle in needles):
            continue
        if row["is_contract_check"]:
            matches["contract_checks"].append(row["path"])
        if row["is_lock_verifier"]:
            matches["lock_verifiers"].append(row["path"])
        if row["is_runtime_snapshot"]:
            matches["runtime_snapshots"].append(row["path"])
        if row["is_lane_snapshot"]:
            matches["lane_snapshots"].append(row["path"])
        if row["is_cutover"]:
            matches["cutover"].append(row["path"])
    return matches


def _runtime_enforcement_snapshot(package_dir: Path, contract_path: Path) -> dict[str, Any]:
    runtime_path = package_dir / "runtime.py"
    runtime_source = _read_text(runtime_path)
    imports = _module_imports(runtime_source)
    contract_module_name = f"design_brain.families.{package_dir.name}.contract"
    contract_loaded = (
        contract_module_name in imports
        or f"design_brain.families.{package_dir.name}" in imports
        or "load_" in runtime_source
        and "_contract" in runtime_source
    )
    return {
        "runtime_path": runtime_path.relative_to(ROOT).as_posix() if runtime_path.exists() else None,
        "runtime_exists": runtime_path.exists(),
        "imports_contract_loader": bool(contract_loaded),
        "imports_inputs_page": "inputs_page" in imports or "inputs_page" in runtime_source,
        "imports_streamlit": "streamlit" in imports or "streamlit" in runtime_source,
        "reads_contract_lanes": "internal_strategy_lanes" in runtime_source
        or "contract_lane_order" in runtime_source
        or "lane_order =" in runtime_source
        or "repair_ladder" in runtime_source,
        "mentions_candidate_source_or_ranking_contract": "candidate_source" in runtime_source
        or "ranking" in runtime_source
        or "selected_recommendation" in runtime_source,
        "emits_ladder_hash": "ladder_hash" in runtime_source,
        "emits_lane_evidence": "lane_id" in runtime_source
        and ("accepted_lane_evidence" in runtime_source or "rejected_lane_evidence" in runtime_source),
        "emits_terminal_proof": any(
            term in runtime_source
            for term in ("exact_stop", "EXACT_STOP", "exhausted", "NO_VALID", "blocked_reason")
        ),
        "contract_path": contract_path.relative_to(ROOT).as_posix(),
    }


def _page_surface_snapshot(family_id: str, package_name: str, inputs_source: str) -> dict[str, Any]:
    direct_contract_imports = sorted(
        set(match.group(0) for match in FORBIDDEN_PAGE_AUTHORITY_IMPORT_RE.finditer(inputs_source))
    )
    family_mentions = len(re.findall(re.escape(family_id), inputs_source))
    package_mentions = len(re.findall(re.escape(package_name), inputs_source))
    ladder_calls = len(re.findall(r"contracted_repair_ladder_specs\s*\(", inputs_source))
    runtime_calls = len(re.findall(rf"run_{re.escape(package_name)}.*runtime\s*\(", inputs_source))
    return {
        "family_mentions": family_mentions,
        "package_mentions": package_mentions,
        "contracted_repair_ladder_specs_calls_total": ladder_calls,
        "direct_runtime_calls_for_package": runtime_calls,
        "direct_contract_imports": direct_contract_imports,
        "page_contract_import_bypass_risk": bool(direct_contract_imports),
    }


def _rule_surface_rows(
    *,
    contract: dict[str, Any],
    family_id: str,
    package_name: str,
    package_dir: Path,
    inputs_source: str,
    verifier_index: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if "depth_width_rule" in contract:
        helper_path = package_dir / "geometry_ratio.py"
        helper_source = _read_text(helper_path)
        verifier_hits = [
            row["path"]
            for row in verifier_index
            if "depth_width" in row["text"] or "ratio_reo_arrangement" in row["path"]
        ]
        enforced = helper_path.exists() and "depth_width_rule" in helper_source
        page_delegates = "guard_bending_depth_width_geometry_update" in inputs_source
        rows.append(
            {
                "family_id": family_id,
                "rule_id": "depth_width_rule",
                "declared": True,
                "enforcement_helper": helper_path.relative_to(ROOT).as_posix() if helper_path.exists() else None,
                "family_owned_helper": enforced,
                "page_adapter_delegates_to_helper": page_delegates,
                "verifier_coverage": sorted(set(verifier_hits)),
                "closure_status": STATUS_CLOSED if enforced and page_delegates and verifier_hits else STATUS_PARTIAL,
                "notes": "D/b ratio enforcement is owned by family helper; page extracts primitive surfaces only."
                if enforced and page_delegates
                else "D/b rule is declared but enforcement/helper coverage is incomplete.",
            }
        )

    if "geometry_restrictions" in contract or "geometry_restriction" in contract:
        runtime_path = package_dir / "runtime.py"
        runtime_source = _read_text(runtime_path)
        verifier_hits = [
            row["path"]
            for row in verifier_index
            if family_id in row["text"]
            and ("geometry_restriction" in row["text"] or "geometry_compliance" in row["path"])
        ]
        no_geometry_reduction_terms = ("no_width_reduction", "no_depth_reduction", "prohibit_width_reduction")
        runtime_mentions_restriction = "geometry_restriction" in runtime_source or any(
            term in runtime_source for term in no_geometry_reduction_terms
        )
        rows.append(
            {
                "family_id": family_id,
                "rule_id": "geometry_restrictions",
                "declared": True,
                "enforcement_helper": runtime_path.relative_to(ROOT).as_posix() if runtime_path.exists() else None,
                "runtime_mentions_restriction": runtime_mentions_restriction,
                "verifier_coverage": sorted(set(verifier_hits)),
                "closure_status": STATUS_CLOSED
                if runtime_mentions_restriction and verifier_hits
                else STATUS_ENFORCED_UNVERIFIED
                if runtime_mentions_restriction
                else STATUS_DECLARED_ONLY,
                "notes": "Geometry restriction is contract-declared; closure depends on runtime and verifier evidence.",
            }
        )

    if "zero_shear_override" in contract or "zero_shear_protection" in contract:
        runtime_path = package_dir / "runtime.py"
        runtime_source = _read_text(runtime_path)
        verifier_hits = [
            row["path"]
            for row in verifier_index
            if family_id in row["text"] and ("zero_shear" in row["text"] or "zero_shear" in row["path"])
        ]
        runtime_mentions_zero_shear = "zero_shear" in runtime_source
        rows.append(
            {
                "family_id": family_id,
                "rule_id": "zero_shear_override",
                "declared": True,
                "enforcement_helper": runtime_path.relative_to(ROOT).as_posix() if runtime_path.exists() else None,
                "runtime_mentions_zero_shear": runtime_mentions_zero_shear,
                "verifier_coverage": sorted(set(verifier_hits)),
                "closure_status": STATUS_CLOSED
                if runtime_mentions_zero_shear and verifier_hits
                else STATUS_ENFORCED_UNVERIFIED
                if runtime_mentions_zero_shear
                else STATUS_DECLARED_ONLY,
                "notes": "Zero-shear override must remain active when ligatures exist.",
            }
        )

    return rows


def _ladder_closure_row(
    *,
    contract: dict[str, Any],
    contract_path: Path,
    verifier_index: list[dict[str, Any]],
    inputs_source: str,
) -> dict[str, Any]:
    package_dir = contract_path.parent
    package_name = package_dir.name
    family_id = _family_id(contract, contract_path)
    contract_kind = _contract_kind(contract)
    lane_order = _contract_lanes(contract)
    runtime = _runtime_enforcement_snapshot(package_dir, contract_path)
    verifiers = _matching_verifiers(family_id, package_name, verifier_index)
    page = _page_surface_snapshot(family_id, package_name, inputs_source)
    has_ladder = bool(lane_order)
    has_merge_or_ranking_contract = contract_kind in {"merge_or_source_contract", "ranking_contract"}
    if page["page_contract_import_bypass_risk"]:
        status = STATUS_BYPASS_RISK
    elif has_ladder and (
        runtime["runtime_exists"]
        and runtime["imports_contract_loader"]
        and runtime["reads_contract_lanes"]
        and runtime["emits_ladder_hash"]
        and verifiers["contract_checks"]
        and verifiers["lock_verifiers"]
    ):
        status = STATUS_CLOSED
    elif has_merge_or_ranking_contract and (
        runtime["runtime_exists"]
        and runtime["imports_contract_loader"]
        and runtime["mentions_candidate_source_or_ranking_contract"]
        and verifiers["contract_checks"]
        and verifiers["lock_verifiers"]
    ):
        status = STATUS_CLOSED
    elif has_ladder and runtime["runtime_exists"] and runtime["imports_contract_loader"] and runtime["reads_contract_lanes"]:
        status = STATUS_ENFORCED_UNVERIFIED
    elif has_merge_or_ranking_contract and runtime["runtime_exists"] and runtime["imports_contract_loader"]:
        status = STATUS_ENFORCED_UNVERIFIED
    elif not has_ladder and not has_merge_or_ranking_contract:
        status = STATUS_DECLARED_ONLY
    else:
        status = STATUS_PARTIAL if runtime["runtime_exists"] else STATUS_DECLARED_ONLY

    return {
        "family_id": family_id,
        "package": f"design_brain.families.{package_name}",
        "contract_kind": contract_kind,
        "contract_path": contract_path.relative_to(ROOT).as_posix(),
        "contract_hash": _stable_hash(contract),
        "declares_ladder": has_ladder,
        "contract_lane_order": lane_order,
        "runtime_enforcement": runtime,
        "page_surface": page,
        "verification_coverage": verifiers,
        "closure_status": status,
        "next_action": _next_action_for_status(status, has_ladder),
    }


def _next_action_for_status(status: str, has_ladder: bool) -> str:
    if not has_ladder and status == STATUS_CLOSED:
        return "Merge/ranking contract is runtime-backed and locked; rerun after source/ranking contract changes."
    if not has_ladder:
        return "No executable lane order detected; classify as merge/ranking/rule contract and add closure proof if needed."
    if status == STATUS_CLOSED:
        return "Keep under lock; rerun closure audit after contract/runtime changes."
    if status == STATUS_BYPASS_RISK:
        return "Remove or isolate direct page contract authority imports behind family-owned helpers."
    if status == STATUS_ENFORCED_UNVERIFIED:
        return "Add or refresh lock verifier proving runtime, cutover, and live callsites."
    if status == STATUS_DECLARED_ONLY:
        return "Create family-owned runtime/policy helper before relying on this contract."
    return "Audit missing runtime/cutover/live verifier coverage before extraction or deletion."


def _mutation_surface_inventory(inputs_source: str) -> dict[str, Any]:
    inventory: dict[str, Any] = {}
    lines = inputs_source.splitlines()
    for surface, patterns in MUTATION_SURFACE_PATTERNS.items():
        matches: list[dict[str, Any]] = []
        for lineno, line in enumerate(lines, start=1):
            if any(re.search(pattern, line) for pattern in patterns):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                matches.append(
                    {
                        "line": lineno,
                        "text": stripped[:180],
                        "mentions_family_helper": "design_brain" in stripped
                        or "final_publication" in stripped
                        or "_guard_bending_depth_width" in stripped,
                    }
                )
        inventory[surface] = {
            "match_count": len(matches),
            "sample": matches[:25],
            "closure_note": "This is a static surface inventory, not proof of product drift.",
        }
    return inventory


def _summary(ladder_rows: list[dict[str, Any]], rule_rows: list[dict[str, Any]]) -> dict[str, Any]:
    all_rows = ladder_rows + rule_rows
    status_counts: dict[str, int] = {}
    for row in all_rows:
        status = str(row.get("closure_status") or "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "result": "PASS",
        "pass_definition": "Audit completed and artifacts written; closure may still be partial.",
        "status_counts": status_counts,
        "closed_count": status_counts.get(STATUS_CLOSED, 0),
        "non_closed_count": len(all_rows) - status_counts.get(STATUS_CLOSED, 0),
        "full_contract_closure_claimed": False,
        "reason_full_closure_not_claimed": (
            "This verifier inventories enforcement closure. It deliberately does not claim 100 percent "
            "closure unless every declared rule and ladder has live runtime, callsite, and lock proof."
        ),
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    ladder_rows = payload["ladder_closure"]
    rule_rows = payload["rule_closure"]
    lines = [
        "# Design Brain Contract Enforcement Closure Audit",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## Result",
        "",
        f"- Audit result: `{summary['result']}`",
        f"- Full 100% closure claimed: `{summary['full_contract_closure_claimed']}`",
        f"- Closed rows: `{summary['closed_count']}`",
        f"- Non-closed rows: `{summary['non_closed_count']}`",
        f"- Status counts: `{summary['status_counts']}`",
        "",
        "This audit treats contract declarations, family runtimes, page/shared callsites, and verifiers as separate layers. A contract is not considered enforced merely because it exists.",
        "",
        "## Ladder Closure",
        "",
        "| Family | Kind | Status | Lane count | Runtime | Contract check | Lock verifier | Next action |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in ladder_rows:
        runtime = row["runtime_enforcement"]
        verifiers = row["verification_coverage"]
        lines.append(
            "| {family} | `{kind}` | `{status}` | {count} | {runtime} | {contract_check} | {lock} | {next_action} |".format(
                family=row["family_id"],
                kind=row.get("contract_kind") or "-",
                status=row["closure_status"],
                count=len(row["contract_lane_order"]),
                runtime="yes"
                if runtime.get("runtime_exists")
                and (
                    runtime.get("reads_contract_lanes")
                    or runtime.get("mentions_candidate_source_or_ranking_contract")
                )
                else "no",
                contract_check="yes" if verifiers["contract_checks"] else "no",
                lock="yes" if verifiers["lock_verifiers"] else "no",
                next_action=row["next_action"],
            )
        )
    lines.extend(
        [
            "",
            "## Rule Closure",
            "",
            "| Family | Rule | Status | Enforcement helper | Verifier count | Notes |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in rule_rows:
        lines.append(
            "| {family} | `{rule}` | `{status}` | {helper} | {count} | {notes} |".format(
                family=row["family_id"],
                rule=row["rule_id"],
                status=row["closure_status"],
                helper=row.get("enforcement_helper") or "-",
                count=len(row.get("verifier_coverage") or []),
                notes=row.get("notes") or "",
            )
        )
    lines.extend(
        [
            "",
            "## Page Mutation Surface Inventory",
            "",
            "Static page/shared mutation surfaces are recorded in the JSON artifact. They are not automatic failures, but they are where drift can enter if they do not delegate to family-owned helpers or FinalDesignGuidePublication.",
            "",
            "## Smallest Safe Next Slice",
            "",
            "1. Review every non-closed ladder row and decide whether it needs a lock verifier or is intentionally rule-only.",
            "2. For every non-closed rule row, add a family-owned pure helper first, then page adapter wiring, then a focused negative-case snapshot.",
            "3. Keep `inputs_page.py` adapter-only: it may extract primitives, evaluate/render/apply, and store compatibility/debug state; it should not own contract policy or ladder order.",
            "",
            "## Stop Conditions For Future Enforcement Work",
            "",
            "- A page/shared path computes ladder order directly.",
            "- A page/shared path imports a family contract and applies policy itself instead of calling a family helper.",
            "- A candidate/update builder mutates protected engineering fields without an owning family helper/runtime proof.",
            "- A verifier passes by checking declarations only and not live callsites or runtime evidence.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = time.strftime("%Y-%m-%dT%H-%M-%S")
    inputs_source = _read_text(ROOT / "inputs_page.py")
    verifier_index = _verification_index()

    ladder_rows: list[dict[str, Any]] = []
    rule_rows: list[dict[str, Any]] = []
    for contract_path in sorted(FAMILY_ROOT.glob("*/contract.json")):
        contract = _load_json(contract_path)
        if "_json_error" in contract:
            ladder_rows.append(
                {
                    "family_id": contract_path.parent.name.upper(),
                    "contract_path": contract_path.relative_to(ROOT).as_posix(),
                    "closure_status": STATUS_DECLARED_ONLY,
                    "json_error": contract["_json_error"],
                    "contract_lane_order": [],
                    "runtime_enforcement": {},
                    "verification_coverage": {},
                    "next_action": "Fix contract JSON before enforcement closure can be audited.",
                }
            )
            continue
        ladder_rows.append(
            _ladder_closure_row(
                contract=contract,
                contract_path=contract_path,
                verifier_index=verifier_index,
                inputs_source=inputs_source,
            )
        )
        rule_rows.extend(
            _rule_surface_rows(
                contract=contract,
                family_id=_family_id(contract, contract_path),
                package_name=contract_path.parent.name,
                package_dir=contract_path.parent,
                inputs_source=inputs_source,
                verifier_index=verifier_index,
            )
        )

    payload = {
        "generated_at": generated_at,
        "summary": _summary(ladder_rows, rule_rows),
        "closure_status_meaning": {
            STATUS_CLOSED: "Declared, runtime-enforced, live-callsite/verifier covered.",
            STATUS_PARTIAL: "Some closure evidence exists but runtime/callsite/verifier coverage is incomplete.",
            STATUS_DECLARED_ONLY: "Contract declaration found without executable enforcement proof.",
            STATUS_ENFORCED_UNVERIFIED: "Runtime/helper evidence exists but lock/live verifier coverage is incomplete.",
            STATUS_BYPASS_RISK: "A direct page/shared contract authority import or bypass-risk pattern exists.",
        },
        "ladder_closure": ladder_rows,
        "rule_closure": rule_rows,
        "page_mutation_surface_inventory": _mutation_surface_inventory(inputs_source),
        "artifact_hash": None,
    }
    payload["artifact_hash"] = _stable_hash({k: v for k, v in payload.items() if k != "artifact_hash"})

    json_path = ARTIFACT_DIR / f"design_brain_contract_enforcement_closure_{generated_at}.json"
    md_path = AUDIT_DIR / f"design_brain_contract_enforcement_closure_{generated_at}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(md_path, payload)

    print("Design Brain contract enforcement closure audit PASS")
    print(f"JSON: {json_path.relative_to(ROOT).as_posix()}")
    print(f"Report: {md_path.relative_to(ROOT).as_posix()}")
    print(f"Status counts: {payload['summary']['status_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
