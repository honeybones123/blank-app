"""Inventory remaining old-shaped scaffolding inside design_brain.

This audit does not change product behavior. It classifies the current
compatibility, fallback, restamper, and legacy-marked surfaces that still exist
inside ``design_brain`` so later deletion work can be proof-backed instead of
guess-based.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DESIGN_BRAIN = ROOT / "design_brain"
TOOLS_VERIFICATION = ROOT / "tools" / "verification"
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


@dataclass(frozen=True)
class SurfaceSpec:
    surface_id: str
    classification: str
    symbols: tuple[str, ...]
    primary_file: str
    purpose: str
    deletion_blocker: str
    recommended_next_action: str


SURFACES: tuple[SurfaceSpec, ...] = ()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _iter_python_json_files(base: Path) -> list[Path]:
    return sorted([*base.rglob("*.py"), *base.rglob("*.json")])


def _line_hits(path: Path, token: str) -> list[int]:
    pattern = re.compile(re.escape(token))
    hits: list[int] = []
    for lineno, line in enumerate(_read(path).splitlines(), start=1):
        if pattern.search(line):
            hits.append(lineno)
    return hits


def _file_hits(paths: list[Path], token: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for path in paths:
        lines = _line_hits(path, token)
        if lines:
            hits.append(
                {
                    "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "line_count": len(lines),
                    "lines": lines[:12],
                }
            )
    return hits


def _symbol_summary(symbol: str, design_brain_paths: list[Path], verification_paths: list[Path]) -> dict[str, Any]:
    design_brain_hits = _file_hits(design_brain_paths, symbol)
    verification_hits = _file_hits(verification_paths, symbol)
    inputs_hits = _line_hits(INPUTS_PAGE, symbol)
    return {
        "symbol": symbol,
        "inputs_page_hit_count": len(inputs_hits),
        "inputs_page_lines": inputs_hits[:20],
        "design_brain_hits": design_brain_hits,
        "verification_hits": verification_hits,
        "live_product_consumer_count": len(inputs_hits) + sum(
            row["line_count"] for row in design_brain_hits if not row["path"].startswith("design_brain/contracts/")
        ),
        "verification_consumer_count": sum(row["line_count"] for row in verification_hits),
    }


def _surface_row(
    spec: SurfaceSpec, design_brain_paths: list[Path], verification_paths: list[Path]
) -> dict[str, Any]:
    symbol_rows = [_symbol_summary(symbol, design_brain_paths, verification_paths) for symbol in spec.symbols]
    inputs_hits = sum(row["inputs_page_hit_count"] for row in symbol_rows)
    verification_hits = sum(row["verification_consumer_count"] for row in symbol_rows)
    design_brain_hits = sum(
        sum(hit["line_count"] for hit in row["design_brain_hits"])
        for row in symbol_rows
    )
    status = "live_internal_scaffolding"
    if spec.classification == "PROOF_ONLY_KEEP" and inputs_hits == 0:
        status = "proof_surface_only"
    elif spec.classification == "SAFETY_KEEP":
        status = "safety_guard_live"
    elif spec.classification == "COMPATIBILITY_KEEP" and inputs_hits == 0 and verification_hits > 0:
        status = "compatibility_debug_only"
    return {
        "surface_id": spec.surface_id,
        "classification": spec.classification,
        "status": status,
        "primary_file": spec.primary_file,
        "purpose": spec.purpose,
        "deletion_blocker": spec.deletion_blocker,
        "recommended_next_action": spec.recommended_next_action,
        "symbols": symbol_rows,
        "inputs_page_total_hits": inputs_hits,
        "design_brain_total_hits": design_brain_hits,
        "verification_total_hits": verification_hits,
        "safe_delete_now": False,
    }


def _run_gate(command: str) -> dict[str, Any]:
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, command],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": command,
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-6:],
        "stderr_tail": proc.stderr.strip().splitlines()[-6:],
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_brain_internal_scaffolding_inventory_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_internal_scaffolding_inventory_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(md_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Design Brain Internal Scaffolding Inventory Audit",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Summary",
        "",
        f"- Total audited surfaces: `{snapshot['summary']['total_surfaces']}`",
        f"- Safe delete now: `{snapshot['summary']['safe_delete_now']}`",
        f"- Compatibility keep: `{snapshot['summary']['compatibility_keep']}`",
        f"- Safety keep: `{snapshot['summary']['safety_keep']}`",
        f"- Proof-only keep: `{snapshot['summary']['proof_only_keep']}`",
        f"- Next safe target: `{snapshot['summary']['next_safe_target']}`",
        "",
        "## Surface Classification",
        "",
    ]
    for row in snapshot["surfaces"]:
        lines.extend(
            [
                f"### `{row['surface_id']}`",
                f"- classification: `{row['classification']}`",
                f"- status: `{row['status']}`",
                f"- primary file: `{row['primary_file']}`",
                f"- inputs_page hits: `{row['inputs_page_total_hits']}`",
                f"- design_brain hits: `{row['design_brain_total_hits']}`",
                f"- verifier hits: `{row['verification_total_hits']}`",
                f"- deletion blocker: {row['deletion_blocker']}",
                f"- next action: {row['recommended_next_action']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Lock Gates",
            "",
            f"- `design_guide_independence_lock_verifier`: `{snapshot['gates']['independence_lock']['passed']}`",
            f"- `design_guide_render_bridge_lock_verifier`: `{snapshot['gates']['render_bridge_lock']['passed']}`",
            f"- `design_guide_compute_resolver_publication_bridge_lock_verifier`: `{snapshot['gates']['compute_bridge_lock']['passed']}`",
            "",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    design_brain_paths = _iter_python_json_files(DESIGN_BRAIN)
    verification_paths = _iter_python_json_files(TOOLS_VERIFICATION)
    surface_rows = [_surface_row(spec, design_brain_paths, verification_paths) for spec in SURFACES]
    next_safe_target = next(
        (
            row["recommended_next_action"]
            for row in surface_rows
            if row["classification"] == "COMPATIBILITY_KEEP"
        ),
        "No remaining compatibility scaffolding targets.",
    )

    summary = {
        "total_surfaces": len(surface_rows),
        "safe_delete_now": sum(1 for row in surface_rows if row["classification"] == "SAFE_DELETE"),
        "compatibility_keep": sum(1 for row in surface_rows if row["classification"] == "COMPATIBILITY_KEEP"),
        "safety_keep": sum(1 for row in surface_rows if row["classification"] == "SAFETY_KEEP"),
        "proof_only_keep": sum(1 for row in surface_rows if row["classification"] == "PROOF_ONLY_KEEP"),
        "live_inputs_consumers": sum(1 for row in surface_rows if row["inputs_page_total_hits"] > 0),
        "next_safe_target": next_safe_target,
    }

    gates = {
        "independence_lock": _run_gate("tools/verification/design_guide_independence_lock_verifier.py"),
        "render_bridge_lock": _run_gate("tools/verification/design_guide_render_bridge_lock_verifier.py"),
        "compute_bridge_lock": _run_gate(
            "tools/verification/design_guide_compute_resolver_publication_bridge_lock_verifier.py"
        ),
    }

    failures: list[str] = []
    if not all(gate["passed"] for gate in gates.values()):
        failures.append("lock_gates_not_green")

    snapshot = {
        "snapshot_name": "design_brain_internal_scaffolding_inventory_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if not failures else "FAIL",
        "surfaces": surface_rows,
        "summary": summary,
        "gates": gates,
        "failures": failures,
    }
    snapshot["snapshot_hash"] = _stable_hash(
        {"surfaces": surface_rows, "summary": summary, "gates": {k: v["passed"] for k, v in gates.items()}}
    )
    json_path, md_path = _write(snapshot)
    print(f"design_brain_internal_scaffolding_inventory_audit {snapshot['result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
