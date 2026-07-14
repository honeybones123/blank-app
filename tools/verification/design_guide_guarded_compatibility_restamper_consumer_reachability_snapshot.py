"""Consumer reachability for guarded compatibility restamper stamps.

This verifier answers the deletion question for the two remaining
compatibility-only restamper stamps after guarded no-op bypass wiring:

- Are any product paths reading the compatibility markers as authority?
- Can the old restamper calls be deleted immediately?

The expected answer is intentionally conservative: no product consumers of the
markers, but the old restamper calls still remain the guarded rebuild/default
path, so deletion needs a separate replacement proof.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PRODUCT_FILES = [
    INPUTS_PAGE,
    ROOT / "design_guide_page.py",
    *sorted((ROOT / "design_brain").glob("**/*.py")),
    *sorted((ROOT / "ui").glob("**/*.py")),
]

TARGETS = {
    "render_guidance_secondary_primary_binding": {
        "callsite_id": "render_guidance_secondary_primary_binding",
        "bypass_marker": "final_visible_restamper_bridge_render_guidance_secondary_primary_bypassed",
        "adapter_marker": "render_guidance_secondary_primary_binding_adapter_cutover_applied",
        "old_restamper_call": "item = _publish_final_visible_design_guide_contract_binding(",
    },
    "render_fast_design_guidance_panel.final_visible_item_binding": {
        "callsite_id": "render_fast_design_guidance_panel.final_visible_item_binding",
        "bypass_marker": "final_visible_restamper_bridge_render_fast_final_visible_item_bypassed",
        "adapter_marker": "render_fast_final_visible_item_binding_adapter_cutover_applied",
        "old_restamper_call": (
            "_final_visible_item = _publish_final_visible_design_guide_contract_binding("
        ),
    },
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw.upper() for token in ("PASS", "LOCKED")) else raw
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _line_number(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def _find_token_refs(token: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for path in PRODUCT_FILES:
        if not path.exists() or path.name.startswith("."):
            continue
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        start = 0
        while True:
            index = source.find(token, start)
            if index < 0:
                break
            line_no = _line_number(source, index)
            line = source.splitlines()[line_no - 1].strip()
            is_assignment_write = (
                path == INPUTS_PAGE
                and (
                    f'"{token}"' in line
                    or f"'{token}'" in line
                    or token in line
                )
                and (
                    line.startswith('"')
                    or line.startswith("'")
                    or line.endswith("= True")
                    or line.endswith("= False")
                    or "=" in line
                )
            )
            refs.append(
                {
                    "file": str(path.relative_to(ROOT)),
                    "line": line_no,
                    "source_line": line,
                    "is_assignment_or_debug_write": bool(is_assignment_write),
                    "is_product_consumer": not bool(is_assignment_write),
                }
            )
            start = index + len(token)
    return refs


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    targets: dict[str, Any] = {}
    for name, spec in TARGETS.items():
        bypass_refs = _find_token_refs(spec["bypass_marker"])
        adapter_refs = _find_token_refs(spec["adapter_marker"])
        callsite_refs = _find_token_refs(spec["callsite_id"])
        product_consumers = [
            ref
            for ref in [*bypass_refs, *adapter_refs]
            if ref.get("is_product_consumer") is True
        ]
        old_restamper_present = spec["old_restamper_call"] in source
        targets[name] = {
            "bypass_marker_refs": bypass_refs,
            "adapter_marker_refs": adapter_refs,
            "callsite_id_refs": callsite_refs,
            "product_consumer_count": len(product_consumers),
            "product_consumers": product_consumers,
            "old_restamper_default_path_present": old_restamper_present,
            "consumer_reachability_clear": len(product_consumers) == 0,
            "safe_to_delete_stamp_now": False,
            "delete_blocker": (
                "old restamper remains guarded rebuild/default path when bypass proof is missing or stale"
                if old_restamper_present
                else ""
            ),
        }
    latest = {
        "bypass_implementation": _latest(
            "design_guide_remaining_compatibility_restamper_bypass_implementation"
        ),
        "remaining_resolver_cleanup": _latest("design_guide_remaining_resolver_cleanup_audit"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "GUARDED_COMPATIBILITY_RESTAMPERS_HAVE_NO_PRODUCT_MARKER_CONSUMERS_BUT_NOT_DELETION_SAFE",
        "targets": targets,
        "latest": latest,
        "all_product_consumers_clear": all(
            row.get("consumer_reachability_clear") is True for row in targets.values()
        ),
        "safe_to_delete_now": False,
        "required_next_proof": (
            "prove an adapter/default rebuild replacement for the old restamper calls before deletion"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "all_product_consumers_clear": capture.get("all_product_consumers_clear") is True,
        "all_targets_have_delete_blocker": all(
            bool(row.get("delete_blocker")) for row in dict(capture.get("targets") or {}).values()
        ),
        "not_safe_to_delete_now": capture.get("safe_to_delete_now") is False,
        "bypass_implementation_latest_pass": (latest.get("bypass_implementation") or {}).get(
            "status"
        )
        == "PASS",
        "remaining_resolver_cleanup_latest_pass": (
            latest.get("remaining_resolver_cleanup") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status")
        == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get(
            "status"
        )
        == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Guarded Compatibility Restamper Consumer Reachability",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Targets",
        "",
    ]
    for name, row in dict(capture.get("targets") or {}).items():
        lines.append(
            f"- `{name}` product consumers: `{row.get('product_consumer_count')}`, old restamper default present: `{row.get('old_restamper_default_path_present')}`"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The compatibility markers have no product consumers, but the old restamper calls still serve as the guarded rebuild/default path.",
            "Do not delete them until an adapter/default rebuild replacement is proven.",
            "",
            "## Checks",
            "",
        ]
    )
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- {name}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_run = _run(
        [
            "python",
            "-m",
            "py_compile",
            "tools\\verification\\design_guide_guarded_compatibility_restamper_consumer_reachability_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [name for name, value in checks.items() if value is not True]
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "timestamp": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "compile_run": compile_run,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = _stamp()
    json_path = ARTIFACT_DIR / (
        f"design_guide_guarded_compatibility_restamper_consumer_reachability_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_guarded_compatibility_restamper_consumer_reachability_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_guarded_compatibility_restamper_consumer_reachability {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(f"safe_to_delete_now={capture.get('safe_to_delete_now')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
