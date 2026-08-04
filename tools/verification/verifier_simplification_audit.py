"""Audit verifier roles, consolidation opportunities, and deletion safety.

This is deliberately audit-only.  It does not delete verifier code and it does
not treat a missing standalone artifact as proof that an imported helper is
dead.  Deletion remains authorized only by the retirement workflow after this
audit's reference checks and the composed release locks pass.
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_DIR = ROOT / "tools" / "verification"
MANIFEST_PATH = VERIFICATION_DIR / "release_gate_manifest.json"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _scripts() -> list[Path]:
    return sorted(
        path for path in VERIFICATION_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _manifest_scripts(manifest: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for gate in manifest.get("release_gates", []):
        command = str(gate.get("command", "")).replace("\\", "/")
        result.update(re.findall(r"tools/verification/[A-Za-z0-9_./-]+\.py", command))
    return result


def _imports(text: str) -> set[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def _latest(prefix: str) -> Path | None:
    candidates = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _build() -> dict[str, Any]:
    manifest = _read_json(MANIFEST_PATH)
    paths = _scripts()
    texts = {_rel(path): path.read_text(encoding="utf-8", errors="ignore") for path in paths}
    manifest_scripts = _manifest_scripts(manifest)

    references: dict[str, set[str]] = defaultdict(set)
    module_owners: dict[str, set[str]] = defaultdict(set)
    nested_calls: list[dict[str, str]] = []
    for owner, text in texts.items():
        for module_name in _imports(text):
            module_owners[module_name].add(owner)
            module_owners[module_name.rsplit(".", 1)[-1]].add(owner)
        for match in re.finditer(r"tools/verification/[A-Za-z0-9_./-]+\.py", text.replace("\\", "/")):
            target = match.group(0)
            if target != owner:
                references[target].add(owner)
                nested_calls.append({"owner": owner, "target": target})

    rows: list[dict[str, Any]] = []
    role_counts: Counter[str] = Counter()
    deletion_candidates: list[str] = []
    blocked_candidates: list[dict[str, Any]] = []
    for path in paths:
        rel = _rel(path)
        module_name = rel[:-3].replace("/", ".")
        imported_by = sorted(module_owners.get(module_name, set()) | module_owners.get(Path(rel).stem, set()))
        is_manifest_gate = rel in manifest_scripts
        direct_refs = sorted(references.get(rel, set()))
        if is_manifest_gate:
            role = "RELEASE_GATE"
            decision = "KEEP_CANONICAL"
        elif direct_refs or imported_by:
            role = "SHARED_DEPENDENCY"
            decision = "KEEP_UNTIL_DEPENDENTS_RETIRED"
        elif path.name.startswith("test_") or "snapshot" in path.name or "audit" in path.name:
            role = "STANDALONE_PROOF"
            decision = "REVIEW_ARTIFACT_AND_CALLSITE"
        else:
            role = "UNREFERENCED_VERIFIER_OR_HELPER"
            decision = "DELETION_CANDIDATE_ONLY_AFTER_RETIREMENT_PROOF"
        role_counts[role] += 1
        row = {
            "path": rel,
            "role": role,
            "decision": decision,
            "manifest_gate": is_manifest_gate,
            "direct_script_references": direct_refs,
            "import_or_text_references": imported_by,
            "has_entrypoint": "if __name__" in texts[rel] or "def main(" in texts[rel],
        }
        rows.append(row)
        if role == "UNREFERENCED_VERIFIER_OR_HELPER":
            deletion_candidates.append(rel)
        elif role != "RELEASE_GATE":
            blocked_candidates.append({"path": rel, "role": role, "references": direct_refs or imported_by})

    efficiency_path = _latest("verifier_system_efficiency_audit")
    retirement_path = _latest("verifier_retirement_deletion_workflow")
    canonical_path = _latest("canonical_verification_runner")
    taxonomy_path = _latest("verification_taxonomy_and_retirement_map")
    efficiency = _read_json(efficiency_path) if efficiency_path else {}
    retirement = _read_json(retirement_path) if retirement_path else {}
    canonical = _read_json(canonical_path) if canonical_path else {}
    taxonomy = _read_json(taxonomy_path) if taxonomy_path else {}
    return {
        "schema": "design_brain.verifier_simplification_audit.v1",
        "status": "PASS",
        "audit_only": True,
        "product_behaviour_changed": False,
        "timestamp": _stamp(),
        "manifest": _rel(MANIFEST_PATH),
        "verifier_count": len(paths),
        "manifest_gate_count": len(manifest_scripts),
        "role_counts": dict(sorted(role_counts.items())),
        "rows": rows,
        "nested_script_invocation_count": len(nested_calls),
        "nested_script_invocations": nested_calls,
        "consolidation_targets": [
            {"target": row.get("target"), "invocation_count": row.get("invocation_count"), "action": "invoke once per canonical run and reuse hash-bound artifact"}
            for row in efficiency.get("repeated_shared_locks", [])
        ],
        "static_unreferenced_candidates": sorted(deletion_candidates),
        "static_unreferenced_candidate_count": len(deletion_candidates),
        "deletion_authorized_candidates": [],
        "deletion_authorized_candidate_count": 0,
        "retirement_safe_deletion_count": retirement.get("safe_deletion_candidate_count", 0),
        "retirement_blocked_count": retirement.get("blocked_candidate_count", 0),
        "latest_efficiency_audit": str(efficiency_path) if efficiency_path else None,
        "latest_retirement_workflow": str(retirement_path) if retirement_path else None,
        "latest_taxonomy": {
            "artifact": str(taxonomy_path) if taxonomy_path else None,
            "status": taxonomy.get("status"),
            "counts": taxonomy.get("counts", {}),
        },
        "latest_canonical_runner": {
            "artifact": str(canonical_path) if canonical_path else None,
            "status": canonical.get("status"),
            "tier": canonical.get("tier"),
            "run_id": canonical.get("run_id"),
            "run_manifest": canonical.get("run_manifest"),
        },
        "deletion_policy": [
            "Do not delete a release-gate script.",
            "Do not delete an imported helper or nested dependency while references remain.",
            "Require a current retirement artifact with safe_to_delete=true.",
            "Delete one small group, then rerun the canonical manifest and composed locks.",
        ],
        "recommended_order": [
            "Use release_gate_manifest.json as the only canonical entry list.",
            "Move repeated shared-lock execution to run-scoped hash-bound reuse.",
            "Separate fast structural checks from live browser checks.",
            "Retire duplicate standalone wrappers only after zero reference proof.",
            "Keep imported helpers until all dependents are removed.",
        ],
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Verifier Simplification Audit",
        "",
        "Status: `PASS` (audit only)",
        "",
        f"Verifier scripts scanned: `{payload['verifier_count']}`",
        f"Canonical manifest gates: `{payload['manifest_gate_count']}`",
        f"Nested script invocations: `{payload['nested_script_invocation_count']}`",
        f"Static unreferenced candidates: `{payload['static_unreferenced_candidate_count']}`",
        f"Retirement-approved deletion candidates: `{payload['retirement_safe_deletion_count']}`",
        "",
        "## Findings",
        "",
        "The manifest is the single release entry point. The verifier directory contains many historical, family-specific, audit, snapshot, and helper scripts; they must not all be run as independent release gates.",
        "",
        "Static no-entrypoint/no-reference candidates are only review candidates, not deletion approvals: imported helpers and nested dependencies must be resolved first. The current retirement workflow is the deletion authority, and it currently authorizes zero deletions.",
        "",
        "## Consolidation Targets",
        "",
    ]
    targets = payload["consolidation_targets"]
    if targets:
        for row in targets:
            lines.append(f"- `{row['target']}` is invoked `{row['invocation_count']}` times; run it once per canonical run and reuse a hash-bound artifact.")
    else:
        lines.append("- none reported by the latest efficiency audit")
    lines.extend(["", "## Deletion Boundary", "", "No deletion is authorized by this audit. The current retirement workflow reports the safe set; anything else remains blocked until references, manifest use, and composed locks are proven clear.", "", "## Required Release Workflow", ""])
    for index, item in enumerate(payload["recommended_order"], 1):
        lines.append(f"{index}. {item}")
    lines.extend(["", "## Current Status", "", f"Retirement blocked candidates: `{payload['retirement_blocked_count']}`.", "Fast and live tiers must remain separate; a fast PASS cannot certify live browser or Apply behavior."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build()
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"verifier_simplification_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"verifier_simplification_audit_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"verifier_simplification_audit {payload['status']}")
    print(f"verifier_count={payload['verifier_count']}")
    print(f"manifest_gates={payload['manifest_gate_count']}")
    print(f"static_unreferenced_candidates={payload['static_unreferenced_candidate_count']}")
    print(f"retirement_safe_deletion_candidates={payload['retirement_safe_deletion_count']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
