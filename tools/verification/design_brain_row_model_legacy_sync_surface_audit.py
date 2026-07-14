from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
VERIFICATION = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

TOKENS = (
    "row_model_legacy_sync_applied",
    "row_model_legacy_sync_diff_keys",
)


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_context(source: str, line_number: int, radius: int = 4) -> str:
    lines = source.splitlines()
    start = max(1, line_number - radius)
    end = min(len(lines), line_number + radius)
    return "\n".join(lines[start - 1 : end])


def _line_hits(path: Path, token: str) -> list[int]:
    hits: list[int] = []
    for lineno, line in enumerate(_read(path).splitlines(), start=1):
        if token in line:
            hits.append(lineno)
    return hits


def _classify_inputs_line(line: int, context: str) -> dict[str, Any]:
    if line in (1558, 1559):
        return {
            "surface_role": "summary_state_session_payload",
            "classification": "compatibility_debug_only",
            "can_delete_now": False,
            "reason": "Still copied into summary/session state bundle; likely non-visible, but needs summary payload parity proof before deletion.",
        }
    if line in (56685, 56686):
        return {
            "surface_role": "canonical_state_allowlist",
            "classification": "compatibility_debug_only",
            "can_delete_now": False,
            "reason": "Still listed in canonical/state packing schema; delete only after all downstream debug payload consumers stop expecting the keys.",
        }
    if 71939 <= line <= 72600:
        return {
            "surface_role": "early_debug_fast_path_payload",
            "classification": "compatibility_debug_only",
            "can_delete_now": False,
            "reason": "Only carried into early debug/trace payloads; no evidence of visible rendering, but needs early-debug parity proof before deletion.",
        }
    if 74452 <= line <= 74453:
        return {
            "surface_role": "final_debug_trace_payload",
            "classification": "compatibility_debug_only",
            "can_delete_now": False,
            "reason": "Final debug trace still carries the fields; delete after trace/debug verifier parity is updated.",
        }
    return {
        "surface_role": "unknown_inputs_usage",
        "classification": "needs_proof",
        "can_delete_now": False,
        "reason": "Unexpected line; do not delete until the consumer role is proven.",
    }


def _classify_controller_line(line: int, context: str) -> dict[str, Any]:
    return {
        "surface_role": "invalid_state_debug_payload_builder",
        "classification": "compatibility_debug_only",
        "can_delete_now": False,
        "reason": "Controller still emits these fields into the invalid-state debug payload; remove only after payload parity verifiers stop requiring them.",
    }


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS)
    controller_source = _read(CONTROLLER)

    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    for token in TOKENS:
        for line in _line_hits(INPUTS, token):
            context = _line_context(inputs_source, line)
            classification = _classify_inputs_line(line, context)
            rows.append(
                {
                    "file": "inputs_page.py",
                    "line": line,
                    "token": token,
                    "context_hash": _stable_hash(context),
                    **classification,
                }
            )
        for line in _line_hits(CONTROLLER, token):
            context = _line_context(controller_source, line)
            classification = _classify_controller_line(line, context)
            rows.append(
                {
                    "file": "design_brain/design_guide_controller.py",
                    "line": line,
                    "token": token,
                    "context_hash": _stable_hash(context),
                    **classification,
                }
            )

    if any(row["classification"] == "needs_proof" for row in rows):
        failures.append("unexpected_row_model_legacy_sync_consumer_found")

    summary = {
        "total_rows": len(rows),
        "compatibility_debug_only": sum(1 for row in rows if row["classification"] == "compatibility_debug_only"),
        "needs_proof": sum(1 for row in rows if row["classification"] == "needs_proof"),
        "can_delete_now": sum(1 for row in rows if row["can_delete_now"]),
    }

    payload = {
        "snapshot_name": "design_brain_row_model_legacy_sync_surface_audit",
        "generated_at": timestamp,
        "result": "PASS" if not failures else "FAIL",
        "summary": summary,
        "rows": rows,
        "failures": failures,
        "next_safe_target": (
            "Add a parity snapshot for summary/debug invalid-state payloads, then delete row_model_legacy_sync_* "
            "from controller invalid-state debug payloads and page debug/session packers in one slice."
        ),
    }
    payload["snapshot_hash"] = _stable_hash(payload)

    json_path = VERIFICATION / f"design_brain_row_model_legacy_sync_surface_audit_{timestamp.replace(':', '-')}.json"
    md_path = AUDITS / f"design_brain_row_model_legacy_sync_surface_audit_{timestamp.replace(':', '-')}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Design Brain Row-Model Legacy Sync Surface Audit",
        "",
        f"## Summary\n{payload['result']}",
        "",
        f"- Total rows: `{summary['total_rows']}`",
        f"- Compatibility/debug-only rows: `{summary['compatibility_debug_only']}`",
        f"- Needs-proof rows: `{summary['needs_proof']}`",
        f"- Safe delete now rows: `{summary['can_delete_now']}`",
        "",
        "## Rows",
        "",
        "| File | Line | Token | Role | Classification | Can delete now |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['file']}` | `{row['line']}` | `{row['token']}` | `{row['surface_role']}` | `{row['classification']}` | `{row['can_delete_now']}` |"
        )
    lines.extend(
        [
            "",
            "## Failures",
            "",
            *([f"- `{failure}`" for failure in failures] or ["None."]),
            "",
            "## Next Safe Target",
            "",
            payload["next_safe_target"],
            "",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"design_brain_row_model_legacy_sync_surface_audit {payload['result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
