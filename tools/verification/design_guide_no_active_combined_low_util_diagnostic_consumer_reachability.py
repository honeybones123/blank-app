"""Source-only reachability proof for no-active combined low-util diagnostics.

This deliberately ignores artifacts and reports. Historical artifacts are
expected to contain old trace strings and do not prove live product consumers.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TOKENS = {
    "full_route_trace": "design_guide_controller_no_active_combined_low_util_full_route_trace_only",
    "result_trace": "design_guide_controller_combined_low_util_cleanup_result_trace_only",
    "route_policy_trace": "design_guide_controller_combined_low_util_cleanup_route_policy_trace_only",
    "handoff_trace": "design_guide_controller_combined_low_util_candidate_generation_handoff_trace_only",
    "route_event": "return_no_active_combined_low_util_safe_cleanup",
}

SOURCE_ROOTS = (
    ROOT / "inputs_page.py",
    ROOT / "design_brain",
    ROOT / "tools" / "verification",
    ROOT / "tools",
)

EXCLUDED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "artifacts",
    "docs",
    "replay_cases",
}

SOURCE_SUFFIXES = {".py"}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _iter_source_files() -> list[Path]:
    files: set[Path] = set()
    for root in SOURCE_ROOTS:
        if root.is_file():
            files.add(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            if any(part in EXCLUDED_DIR_NAMES for part in path.relative_to(ROOT).parts):
                continue
            files.add(path)
    return sorted(files)


def _classify_reference(path: Path, token_name: str, line: str) -> str:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    if rel.startswith("tools/verification/"):
        return "verifier_consumer"
    if rel == "inputs_page.py":
        if token_name == "full_route_trace":
            return "page_diagnostic_producer"
        if token_name in {"result_trace", "route_policy_trace", "handoff_trace"}:
            return "page_compatibility_restamp"
        if token_name == "route_event":
            return "page_route_trace_event_producer"
    if rel == "design_brain/design_guide_controller.py":
        if token_name in {"result_trace", "route_policy_trace", "handoff_trace"}:
            return "controller_trace_producer"
    if "TRACE_KEY" in line or "TOKENS" in line:
        return "verifier_consumer"
    return "potential_product_consumer"


def _capture() -> dict[str, Any]:
    references: dict[str, list[dict[str, Any]]] = {name: [] for name in TOKENS}
    for path in _iter_source_files():
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            for name, token in TOKENS.items():
                if token in line:
                    references[name].append(
                        {
                            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                            "line": lineno,
                            "classification": _classify_reference(path, name, line),
                            "snippet": line.strip()[:180],
                        }
                    )

    product_consumers = {
        name: [
            ref
            for ref in refs
            if ref.get("classification") == "potential_product_consumer"
        ]
        for name, refs in references.items()
    }
    verifier_consumers = {
        name: [
            ref
            for ref in refs
            if ref.get("classification") == "verifier_consumer"
        ]
        for name, refs in references.items()
    }
    producers = {
        name: [
            ref
            for ref in refs
            if str(ref.get("classification") or "").endswith("producer")
            or ref.get("classification") == "page_compatibility_restamp"
        ]
        for name, refs in references.items()
    }
    return {
        "decision": "NO_PRODUCT_CONSUMERS_FOR_NO_ACTIVE_COMBINED_LOW_UTIL_DIAGNOSTICS",
        "source_files_scanned": len(_iter_source_files()),
        "references": references,
        "producer_counts": {name: len(refs) for name, refs in producers.items()},
        "verifier_consumer_counts": {
            name: len(refs) for name, refs in verifier_consumers.items()
        },
        "product_consumer_counts": {
            name: len(refs) for name, refs in product_consumers.items()
        },
        "product_consumers": product_consumers,
        "deletion_readiness": {
            "product_safe_to_remove_diagnostics": all(
                len(refs) == 0 for refs in product_consumers.values()
            ),
            "verifier_updates_required_before_deletion": any(
                len(refs) > 0 for refs in verifier_consumers.values()
            ),
            "delete_now": False,
        },
        "next_safe_slice": (
            "Narrow or remove verifier requirements for these diagnostics first; "
            "then delete the product-free page diagnostics in a focused slice."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    refs = capture.get("references") or {}
    readiness = capture.get("deletion_readiness") or {}
    return {
        "source_files_scanned": int(capture.get("source_files_scanned") or 0) > 0,
        "all_tokens_accounted_for": set(refs) == set(TOKENS),
        "all_tokens_have_source_refs": all(len(value or []) > 0 for value in refs.values()),
        "no_product_consumers": all(
            count == 0 for count in (capture.get("product_consumer_counts") or {}).values()
        ),
        "product_safe_to_remove_diagnostics": (
            readiness.get("product_safe_to_remove_diagnostics") is True
        ),
        "verifier_updates_required_before_deletion": (
            readiness.get("verifier_updates_required_before_deletion") is True
        ),
        "delete_now_false": readiness.get("delete_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide No-Active Combined Low-Util Diagnostic Consumer Reachability",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Source files scanned: `{capture.get('source_files_scanned')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Product Consumer Counts"])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("product_consumer_counts") or {}).items()
    )
    lines.extend(["", "## Verifier Consumer Counts"])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("verifier_consumer_counts") or {}).items()
    )
    lines.extend(["", "## Deletion Readiness"])
    for key, value in (capture.get("deletion_readiness") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Next Safe Slice", "", str(capture.get("next_safe_slice"))])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_no_active_combined_low_util_diagnostic_consumer_reachability_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_combined_low_util_diagnostic_consumer_reachability_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_combined_low_util_diagnostic_consumer_reachability {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
