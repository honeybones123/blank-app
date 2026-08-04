from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:/Users/jono/OneDrive/Documents/GitHub/complete-app - Copy (3)")
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


@dataclass(frozen=True)
class Shim:
    surface_id: str
    package_file: str
    package_symbol: str
    contract_file: str
    runtime_module: str
    runtime_symbol: str


SHIMS: tuple[Shim, ...] = (
    Shim(
        surface_id="combined_fail_govern_package_public_api",
        package_file="design_brain/families/bending_and_shear_fail_govern/__init__.py",
        package_symbol="evaluate_bending_and_shear_fail_govern",
        contract_file="design_brain/families/bending_and_shear_fail_govern/contract.json",
        runtime_module="design_brain.families.bending_and_shear_fail_govern.runtime",
        runtime_symbol="run_combined_bending_shear_fail_runtime",
    ),
    Shim(
        surface_id="shear_overdesign_package_public_api",
        package_file="design_brain/families/shear_overdesign_governs/__init__.py",
        package_symbol="evaluate_shear_overdesign_governs",
        contract_file="design_brain/families/shear_overdesign_governs/contract.json",
        runtime_module="design_brain.families.shear_overdesign_governs.runtime",
        runtime_symbol="run_shear_overdesign_governs_runtime",
    ),
    Shim(
        surface_id="serviceability_package_public_api",
        package_file="design_brain/families/serviceability_governs/__init__.py",
        package_symbol="evaluate_serviceability_governs",
        contract_file="design_brain/families/serviceability_governs/contract.json",
        runtime_module="design_brain.families.serviceability_governs.runtime",
        runtime_symbol="evaluate_serviceability_governs",
    ),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _hits(term: str, *, include_tools: bool) -> list[str]:
    roots = [ROOT / "design_brain", ROOT / "inputs_page.py", ROOT / "ui"]
    hits: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            files = [root]
        else:
            files = list(root.rglob("*.py"))
        for file in files:
            rel = file.relative_to(ROOT).as_posix()
            if not include_tools and rel.startswith("tools/"):
                continue
            text = _read(file)
            if term in text:
                line_no = next((i for i, line in enumerate(text.splitlines(), start=1) if term in line), 1)
                hits.append(f"{rel}:{line_no}")
    if include_tools:
        for file in (ROOT / "tools" / "verification").rglob("*.py"):
            rel = file.relative_to(ROOT).as_posix()
            text = _read(file)
            if term in text:
                line_no = next((i for i, line in enumerate(text.splitlines(), start=1) if term in line), 1)
                hits.append(f"{rel}:{line_no}")
    return hits


def _contract_meta(contract_file: str) -> dict:
    payload = json.loads(_read(ROOT / contract_file))
    family_identity = payload.get("family_identity") or {}
    return {
        "family_id": family_identity.get("family_id"),
        "public_api": payload.get("public_api") or family_identity.get("public_api"),
        "runtime_module": payload.get("runtime_module") or family_identity.get("runtime_module"),
    }


def _classify(
    *,
    package_symbol_present: bool,
    live_hits: list[str],
    verifier_hits: list[str],
    contract_api_matches: bool,
) -> tuple[str, str]:
    if not package_symbol_present and not live_hits and not verifier_hits and not contract_api_matches:
        return (
            "shim_removed",
            "The legacy package shim is gone, the contract no longer points at it, and no live or verifier consumer remains.",
        )
    if live_hits:
        return (
            "safety_keep",
            "Live source still imports or calls the package public API shim.",
        )
    if verifier_hits and contract_api_matches:
        return (
            "contract_verifier_only_candidate",
            "No live source uses the shim; it remains because contracts and verifiers still require the package API.",
        )
    if verifier_hits:
        return (
            "verifier_only_candidate",
            "No live source uses the shim; only verification currently references it.",
        )
    return (
        "safe_delete_now",
        "No live, contract, or verifier consumer was found.",
    )


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    rows = []
    for shim in SHIMS:
        term = f"{shim.package_symbol}("
        package_source = _read(ROOT / shim.package_file)
        package_symbol_present = shim.package_symbol in package_source
        live_hits = [
            hit for hit in _hits(term, include_tools=False)
            if not hit.startswith(Path(shim.package_file).as_posix())
        ]
        verifier_hits = [
            hit for hit in _hits(term, include_tools=True)
            if hit.startswith("tools/verification/")
            and not hit.startswith("tools/verification/design_brain_package_public_api_shim_readiness_audit.py:")
        ]
        contract = _contract_meta(shim.contract_file)
        classification, reason = _classify(
            package_symbol_present=package_symbol_present,
            live_hits=live_hits,
            verifier_hits=verifier_hits,
            contract_api_matches=contract.get("public_api") == shim.package_symbol,
        )
        rows.append(
            {
                "surface_id": shim.surface_id,
                "package_file": shim.package_file,
                "package_symbol": shim.package_symbol,
                "contract_file": shim.contract_file,
                "runtime_module": shim.runtime_module,
                "runtime_symbol": shim.runtime_symbol,
                "package_symbol_present": package_symbol_present,
                "contract_family_id": contract.get("family_id"),
                "contract_public_api": contract.get("public_api"),
                "contract_runtime_module": contract.get("runtime_module"),
                "live_hits": live_hits,
                "verifier_hits": verifier_hits,
                "classification": classification,
                "reason": reason,
            }
        )
    summary = {
        "safe_delete_now": sum(1 for row in rows if row["classification"] == "safe_delete_now"),
        "shim_removed": sum(1 for row in rows if row["classification"] == "shim_removed"),
        "contract_verifier_only_candidate": sum(
            1 for row in rows if row["classification"] == "contract_verifier_only_candidate"
        ),
        "safety_keep": sum(1 for row in rows if row["classification"] == "safety_keep"),
    }
    payload = {
        "snapshot_name": "design_brain_package_public_api_shim_readiness_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS",
        "summary": summary,
        "surfaces": rows,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_brain_package_public_api_shim_readiness_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_package_public_api_shim_readiness_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# Design Brain Package Public API Shim Readiness Audit",
        "",
        f"Generated: `{stamp}`",
        "",
        "## Summary",
        "",
        f"- Safe delete now: `{summary['safe_delete_now']}`",
        f"- Shim removed: `{summary['shim_removed']}`",
        f"- Contract/verifier-only candidates: `{summary['contract_verifier_only_candidate']}`",
        f"- Safety keep: `{summary['safety_keep']}`",
        "",
        "## Surfaces",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['surface_id']}",
                "",
                f"- Package file: `{row['package_file']}`",
                f"- Symbol: `{row['package_symbol']}`",
                f"- Symbol present: `{row['package_symbol_present']}`",
                f"- Contract public_api: `{row['contract_public_api']}`",
                f"- Classification: `{row['classification']}`",
                f"- Reason: {row['reason']}",
                f"- Live hits: `{len(row['live_hits'])}` {row['live_hits']}",
                f"- Verifier hits: `{len(row['verifier_hits'])}` {row['verifier_hits'][:8]}",
                "",
            ]
        )
    lines.extend(
        [
            "## Recommendation",
            "",
            "Only delete package API shims in the same slice that updates the family contract public_api field and all verifier imports. Until then, contract/verifier-only shims are not behavior-risky, but they are not yet deletion-ready.",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print("design_brain_package_public_api_shim_readiness_audit PASS")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
