"""Universal live Design Brain family lock gate.

This is the top-level family gate for "fully verified" app status.  It does
not replace the family-specific lock verifier; it composes those locks so a
release cannot be treated as fully verified while one family still lacks live
contract, target-band, publication, CTA/apply, or blocker proof.

Default mode is inspection-only and does not start browser fuzz.  Use
``--run-live`` for the real full lock run.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import ctypes
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.families.family_live_fuzz_regression_lock_gate import (  # noqa: E402
    SUPPORTED_FAMILIES,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
RESUME_STATE_PATH = ARTIFACT_DIR / "design_brain_universal_live_family_lock_resume_state.json"
WORKER_STATE_DIR = ARTIFACT_DIR / "design_brain_universal_live_family_workers"
FAMILY_GATE = ROOT / "tools" / "verification" / "families" / "family_live_fuzz_regression_lock_gate.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
FINAL_FORMATTER = ROOT / "design_brain" / "final_design_guide_formatter.py"
FINAL_FORMATTING_CONTRACT = ROOT / "design_brain" / "final_design_guide_formatting_contract.json"
FINAL_UI_RENDERER = ROOT / "ui" / "final_design_guide_card.py"


def _live_run_lock_path(port: int) -> Path:
    """Return the lock for a universal run's browser-port namespace."""
    return ARTIFACT_DIR / f"design_brain_universal_live_family_lock_port_{int(port)}.lock"


def _process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        try:
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return int(exit_code.value) == 259  # STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _acquire_live_run_lock(port: int) -> Path:
    """Prevent duplicate universal runs from sharing browser ports."""
    path = _live_run_lock_path(port)
    payload = {
        "pid": os.getpid(),
        "port": int(port),
        "started_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    for attempt in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                pid = int(existing.get("pid") or 0)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pid = 0
            if pid and _process_exists(pid):
                raise SystemExit(
                    f"universal live lock busy for port {int(port)}: pid {pid} is already running"
                )
            if attempt == 0:
                try:
                    path.unlink()
                except OSError:
                    pass
                continue
            raise SystemExit(f"universal live lock busy for port {int(port)}")
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.write("\n")
            return path
    raise SystemExit(f"unable to acquire universal live lock for port {int(port)}")


def _release_live_run_lock(path: Path) -> None:
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if int(existing.get("pid") or 0) != os.getpid():
            return
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return
    try:
        path.unlink()
    except OSError:
        pass

CODE_HASH_FILES: tuple[str, ...] = (
    "app.py",
    "inputs_page.py",
    "inputs_application/engineering_workspace.py",
    "inputs_application/page_runtime/design_guide.py",
    "inputs_page_modules/guidance_compute.py",
    "inputs_page_modules/design_guide/current_coordinators.py",
    "design_guide_page.py",
)
CODE_HASH_DIRS: tuple[str, ...] = (
    "design_brain",
    "ui",
    "inputs_page_modules",
    "inputs_application",
)

REQUIRED_LIVE_PROOFS: tuple[str, ...] = (
    "contract loads and owns the family",
    "family ladder/runtime is contract-driven",
    "contract ladder order is recorded and enforced",
    "candidate generation is recorded per contract lane",
    "candidate rejection reasons are recorded per failed/skipped lane",
    "ranking proof shows the selected candidate is the best valid candidate",
    "same-click folding proof is recorded for families that can otherwise publish partial cleanup",
    "terminal post-Apply result is target-band, exact-stop, or blocker-proven",
    "10 distinct live fuzz cases execute for the family route",
    "selected candidate is best valid contract candidate",
    "published recommendation uses canonical row model",
    "CTA/apply payload is executable when action is required",
    "one click reaches target band or publishes exact engineering blocker",
    "no result breaks geometry, reinforcement, spacing, ductility, or detailing rules",
    "final visible Design Guide output matches selected family result",
    "visible title, badge, colour, summary, CTA, and blocker text come from FinalDesignGuidePublication",
    "Design Guide formatting is contract-driven and consistent across all families",
    "shared publication/render/apply locks still pass",
)

FOLDING_REQUIRED_FAMILIES: frozenset[str] = frozenset(
    {
        "BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_OVERDESIGN_GOVERNS",
        "COMBINED_OVERDESIGN",
        "COMBINED_OVERDESIGN_GOVERNS",
        "COMBINED_BENDING_SHEAR_FAIL",
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    }
)

TERMINAL_FAMILIES: frozenset[str] = frozenset(
    {
        "MIN_BENDING_REO_GOVERNS",
        "MIN_SHEAR_REO_GOVERNS",
        "GEOMETRY_DETAILING_GOVERNS",
        "LOCKED_NO_REPAIR",
        "TARGET_BAND_REACHED",
        "EXACT_STOP_PROVEN",
    }
)

LOGICAL_LADDER_REQUIRED_CHECKS: tuple[str, ...] = (
    "contract_ladder_order_proven",
    "candidate_generation_per_lane_proven",
    "candidate_rejection_reasons_proven",
    "ranking_best_candidate_proven",
    "same_click_folding_proven_or_not_required",
    "terminal_result_after_apply_or_terminal_proof",
)

FORMAT_AUTHORITY_REQUIRED_CHECKS: tuple[str, ...] = (
    "formatting_contract_exists_and_targets_final_publication",
    "formatter_builds_from_final_publication_only",
    "ui_renderer_is_render_only",
    "visible_family_matches_publication_family",
    "visible_card_is_hash_stamped_from_publication_display",
    "cta_hash_is_hash_stamped_from_publication_cta",
    "card_format_hash_or_clean_renderer_proof_exists",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _code_state_hash() -> dict[str, Any]:
    digest = hashlib.sha256()
    files: list[Path] = []
    for relative in CODE_HASH_FILES:
        path = ROOT / relative
        if path.exists() and path.is_file():
            files.append(path)
    for relative in CODE_HASH_DIRS:
        root = ROOT / relative
        if not root.exists():
            continue
        files.extend(
            path
            for path in root.rglob("*.py")
            if "__pycache__" not in path.parts
        )
        files.extend(
            path
            for path in root.rglob("*.json")
            if "__pycache__" not in path.parts
        )
    unique = sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())
    for path in unique:
        relative = path.relative_to(ROOT).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return {
        "hash": digest.hexdigest(),
        "file_count": len(unique),
        "scope_files": list(CODE_HASH_FILES),
        "scope_dirs": list(CODE_HASH_DIRS),
    }


def _resume_contract_hash() -> str:
    digest = hashlib.sha256()
    paths = (
        Path(__file__),
        FAMILY_GATE,
    )
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _read_resume_state() -> dict[str, Any]:
    try:
        payload = json.loads(RESUME_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_resume_state(payload: dict[str, Any]) -> None:
    RESUME_STATE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _write_worker_state(family_id: str, payload: dict[str, Any]) -> Path:
    """Persist one atomic heartbeat for a live family worker."""
    WORKER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    slug = _family_slug(family_id)
    target = WORKER_STATE_DIR / f"{slug}.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def _reconcile_worker_states() -> dict[str, Any]:
    """Mark interrupted workers explicitly; never treat a stale heartbeat as live."""
    result: dict[str, Any] = {
        "inspected": 0,
        "aborted": [],
        "still_running": [],
        "unreadable": [],
    }
    if not WORKER_STATE_DIR.exists():
        return result
    for path in WORKER_STATE_DIR.glob("*.json"):
        result["inspected"] += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            result["unreadable"].append(path.name)
            continue
        if not isinstance(payload, dict) or str(payload.get("status") or "").upper() != "RUNNING":
            continue
        pid = payload.get("pid")
        alive = False
        try:
            if pid is not None:
                os.kill(int(pid), 0)
                alive = True
        except (OSError, TypeError, ValueError):
            alive = False
        if alive:
            result["still_running"].append(path.name)
            continue
        payload.update(
            {
                "status": "ABORTED",
                "finished_at": _stamp(),
                "timed_out": False,
                "timeout_reason": "worker_process_not_alive_at_resume",
                "failure_classification": "interrupted_live_worker",
            }
        )
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        result["aborted"].append(path.name)
    return result


def _family_slug(family_id: str) -> str:
    return str(family_id).strip().lower()


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "UNREADABLE", "error": str(exc)}
    return payload if isinstance(payload, dict) else {"status": "UNREADABLE", "error": "json root is not object"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _latest_family_lock_artifact(
    family_id: str,
    *,
    run_started_at: float | None = None,
    verification_run_id: str | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    slug = _family_slug(family_id)
    manifest_path = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST") or "").strip()
    if not manifest_path and run_started_at is None and not verification_run_id:
        # A direct newest-file lookup cannot certify a live family. Worker
        # calls receive the canonical run id and are therefore still bound.
        return None, {}
    paths = sorted(
        ARTIFACT_DIR.glob(f"{slug}_live_fuzz_regression_lock_gate_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if manifest_path:
        try:
            manifest = _read_json(Path(manifest_path))
            started = str(manifest.get("started_at") or "").replace("Z", "+00:00")
            run_start = datetime.fromisoformat(started).timestamp()
            paths = [path for path in paths if path.stat().st_mtime >= run_start]
        except Exception:
            paths = []
    elif run_started_at is not None:
        paths = [path for path in paths if path.stat().st_mtime >= run_started_at]
    if verification_run_id:
        paths = [
            path
            for path in paths
            if str(_read_json(path).get("verification_run_id") or "") == verification_run_id
        ]
    if paths and family_id not in TERMINAL_FAMILIES:
        path = paths[-1]
        return path, _read_json(path)

    # Terminal families use the dedicated live acceptance verifier rather
    # than the executable ten-fuzz route. Bind its family row into the same
    # family-lock shape so the universal gate can enforce the same freshness
    # and publication checks without treating terminal coverage as missing.
    if family_id in TERMINAL_FAMILIES:
        terminal_paths = sorted(
            ARTIFACT_DIR.glob("design_guide_terminal_family_live_acceptance_*.json"),
            key=lambda path: path.stat().st_mtime,
        )
        if run_started_at is not None:
            terminal_paths = [
                path for path in terminal_paths if path.stat().st_mtime >= run_started_at
            ]
        if manifest_path:
            try:
                manifest = _read_json(Path(manifest_path))
                run_id = str(manifest.get("run_id") or "")
                terminal_paths = [
                    path
                    for path in terminal_paths
                    if str(_read_json(path).get("verification_run_id") or "") == run_id
                ]
            except Exception:
                terminal_paths = []
        elif verification_run_id:
            terminal_paths = [
                path
                for path in terminal_paths
                if str(_read_json(path).get("verification_run_id") or "") == verification_run_id
            ]
        if terminal_paths:
            path = terminal_paths[-1]
            aggregate = _read_json(path)
            family_row = next(
                (
                    dict(row)
                    for row in _safe_list(aggregate.get("families"))
                    if isinstance(row, dict) and str(row.get("family_id") or "") == family_id
                ),
                None,
            )
            if family_row is not None:
                passed = str(family_row.get("status") or "").upper() == "PASS"
                synthetic = {
                    "schema": "design_brain.family_live_fuzz_regression_lock_gate.terminal_adapter.v1",
                    "family": family_id,
                    "lock_status": "LOCKED" if passed else "NOT_LOCKED",
                    "verification_run_id": aggregate.get("verification_run_id"),
                    "source_code_hash": aggregate.get("source_code_hash"),
                    "family_10_fuzz_row": {
                        "live_execution": {
                            "executed": True,
                            "status": "PASS" if passed else "FAIL",
                            "scenario_count": 1,
                            "unique_recipe_count": 1,
                            "passed_count": 1 if passed else 0,
                            "failed_count": 0 if passed else 1,
                            "rows": [family_row],
                        }
                    },
                    "live_audit": {
                        "executed": True,
                        "status": "PASS" if passed else "FAIL",
                        "scenario_count": 1,
                        "unique_recipe_count": 1,
                        "passed_count": 1 if passed else 0,
                        "failed_count": 0 if passed else 1,
                        "rows": [family_row],
                    },
                    "phases": [
                        {"phase": "terminal_acceptance", "passed": passed},
                        {"phase": "C_publication_contract_proof", "passed": passed},
                    ],
                }
                return path, synthetic
    if paths:
        path = paths[-1]
        return path, _read_json(path)
    return None, {}


def _is_locked(payload: dict[str, Any]) -> bool:
    return str(payload.get("lock_status") or "").strip().upper() == "LOCKED"


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _typed_apply_commit_proven(run_end_event: dict[str, Any] | None) -> bool:
    run_end = _safe_dict(run_end_event)
    run_data = _safe_dict(run_end.get("data"))
    route = _safe_dict(run_data.get("last_apply_route"))
    compare = _safe_dict(run_data.get("compare"))
    final_updates = _safe_dict(
        run_data.get("final_updates") or compare.get("final_updates")
    )
    applied_updates = _safe_dict(route.get("applied_updates"))
    applied_updates_cover_trace = bool(final_updates) and all(
        key in applied_updates and applied_updates[key] == value
        for key, value in final_updates.items()
    )
    return bool(
        str(run_data.get("status") or "").lower() == "pass"
        and str(run_data.get("stop_reason") or "") == "typed_apply_committed"
        and route.get("typed_apply_canonical_candidate_preverified") is True
        and route.get("post_apply_all_key_pass") is True
        and route.get("post_apply_any_fail") is False
        and route.get("payload_binding_match") is True
        and route.get("payload_update_match") is True
        and applied_updates
        and applied_updates_cover_trace
    )


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _walk(value: Any) -> list[Any]:
    rows: list[Any] = [value]
    if isinstance(value, dict):
        for item in value.values():
            rows.extend(_walk(item))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_walk(item))
    return rows


def _nested_key_present(value: Any, fragments: tuple[str, ...]) -> bool:
    wanted = tuple(fragment.lower() for fragment in fragments)
    for item in _walk(value):
        if not isinstance(item, dict):
            continue
        for key, child in item.items():
            lower_key = str(key).lower()
            if all(fragment in lower_key for fragment in wanted):
                if child not in (None, "", [], {}):
                    return True
    return False


def _nested_text_contains(value: Any, fragments: tuple[str, ...]) -> bool:
    wanted = tuple(fragment.lower() for fragment in fragments)
    for item in _walk(value):
        if isinstance(item, (str, int, float, bool)):
            text = str(item).lower()
            if all(fragment in text for fragment in wanted):
                return True
    return False


def _passed_phase(payload: dict[str, Any], phase_name: str) -> bool:
    for phase in _safe_list(payload.get("phases")):
        row = _safe_dict(phase)
        if str(row.get("phase") or "") == phase_name:
            return bool(row.get("passed"))
    return False


def _live_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    live = _safe_dict(payload.get("live_audit"))
    rows = [
        _safe_dict(row)
        for row in _safe_list(live.get("rows"))
        if isinstance(row, dict)
    ]
    if rows:
        return rows
    family_row = _safe_dict(payload.get("family_10_fuzz_row"))
    live = _safe_dict(family_row.get("live_execution"))
    return [
        _safe_dict(row)
        for row in _safe_list(live.get("rows"))
        if isinstance(row, dict)
    ]


def _terminal_acceptance_rows(payload: dict[str, Any], family_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase in _safe_list(payload.get("phases")):
        phase_row = _safe_dict(phase)
        for key in ("terminal_acceptance_rows", "compatibility_terminal_rows", "direct_terminal_rows"):
            for item in _safe_list(phase_row.get(key)):
                row = _safe_dict(item)
                if not row:
                    continue
                if str(row.get("family_id") or "").strip().upper() != family_id:
                    continue
                rows.append(row)
    return rows


def _compatibility_owner_format_evidence(payload: dict[str, Any], family_id: str) -> dict[str, Any]:
    # Terminal-family workers normalize the accepted family row into
    # ``live_audit.rows``.  Older aggregate payloads retain the same row under
    # a terminal phase.  Consume either representation so the universal
    # format proof follows the real product-driving owner instead of demanding
    # an impossible visible card from a compatibility-only shell.
    candidate_rows = [
        *_terminal_acceptance_rows(payload, family_id),
        *[
            row
            for row in _live_rows(payload)
            if str(row.get("family_id") or "").strip().upper() == family_id
        ],
    ]
    rows: list[dict[str, Any]] = []
    seen_rows: set[tuple[str, str, str]] = set()
    for row in candidate_rows:
        if (
            str(row.get("evidence_type") or "") != "compatibility_shell_live_owner"
            or str(row.get("status") or "").strip().upper() != "PASS"
        ):
            continue
        identity = (
            str(row.get("family_id") or ""),
            str(row.get("owner_live_artifact") or ""),
            str(row.get("expected_live_owner") or ""),
        )
        if identity in seen_rows:
            continue
        seen_rows.add(identity)
        rows.append(row)
    owner_payloads: list[dict[str, Any]] = []
    owner_rows: list[dict[str, Any]] = []
    owner_artifacts: list[str] = []
    for row in rows:
        artifact_text = str(row.get("owner_live_artifact") or "").strip()
        if not artifact_text:
            continue
        artifact_path = Path(artifact_text)
        if not artifact_path.exists():
            continue
        owner_payload = _read_json(artifact_path)
        if not _is_locked(owner_payload):
            continue
        owner_payloads.append(owner_payload)
        owner_rows.extend(_live_rows(owner_payload))
        owner_artifacts.append(str(artifact_path))
    owner_identity_rows = [
        _safe_dict(row.get("browser_family_identity_contract"))
        for row in owner_rows
        if isinstance(row.get("browser_family_identity_contract"), dict)
    ]
    owner_identity_ok = bool(owner_identity_rows) and all(
        row.get("passes_contract") for row in owner_identity_rows
    )
    return {
        "rows": rows,
        "owner_payloads": owner_payloads,
        "owner_rows": owner_rows,
        "owner_artifacts": owner_artifacts,
        "owner_identity_rows": owner_identity_rows,
        "owner_identity_ok": owner_identity_ok,
    }


def _row_failure_is_consumed_by_settle_proof(row: dict[str, Any], failure: str) -> bool:
    if str(failure) != "post_apply_solver_state_timeout":
        return False
    run_end = _safe_dict(row.get("run_end_event"))
    run_data = _safe_dict(run_end.get("data"))
    green = _safe_dict(row.get("post_apply_green_pass_visual_contract"))
    safe_followup = _safe_dict(row.get("post_apply_safe_followup_contract"))
    return bool(
        _typed_apply_commit_proven(run_end)
        or (
            run_end
            and str(run_data.get("status") or "").lower() == "pass"
            and (
                green.get("passes_contract") is True
                or safe_followup.get("passes_contract") is True
            )
        )
    )


def _terminal_result_proven(payload: dict[str, Any], family_id: str) -> bool:
    if _is_locked(payload):
        return True
    if family_id in TERMINAL_FAMILIES:
        return _passed_phase(payload, "B_candidate_ladder_proof") and _passed_phase(
            payload,
            "C_publication_contract_proof",
        )
    rows = _live_rows(payload)
    if not rows:
        return False
    for row in rows:
        failures = [
            str(item)
            for item in _safe_list(row.get("failures"))
            if not _row_failure_is_consumed_by_settle_proof(row, str(item))
        ]
        target = _safe_dict(row.get("post_apply_target_band_contract"))
        green = _safe_dict(row.get("post_apply_green_pass_visual_contract"))
        safe_followup = _safe_dict(row.get("post_apply_safe_followup_contract"))
        if failures:
            return False
        if target and not target.get("passes_contract"):
            return False
        if green and not green.get("passes_contract") and not safe_followup.get("passes_contract"):
            return False
        if not (target or green or safe_followup or _safe_dict(row.get("run_end_event"))):
            return False
    return True


def _failure_diagnosis(row: dict[str, Any]) -> dict[str, Any]:
    """Classify failure evidence without weakening the family lock.

    The universal gate remains strict.  This diagnosis only distinguishes a
    bad/insufficient live recipe from a real post-Apply product failure, so a
    red run has an actionable owner instead of one undifferentiated error.
    """
    live = _safe_dict(row.get("payload_summary", {}).get("live_audit"))
    if not live:
        live = _safe_dict(row.get("live_execution"))
    if row.get("passed") is True:
        return {
            "classification": "PASSED",
            "owner": "none",
            "action": "no action",
            "evidence": {
                "lock_status": row.get("lock_status"),
                "live_status": live.get("status"),
            },
        }
    if not bool(live.get("executed")):
        return {
            "classification": "MISSING_LIVE_COVERAGE",
            "owner": "family live recipe coverage",
            "action": "add and run a deterministic live recipe for this family",
            "evidence": {"live_status": live.get("status") or "NOT_RUN"},
        }
    if row.get("timed_out"):
        return {
            "classification": "RUNTIME_TIMEOUT",
            "owner": "verifier runtime",
            "action": "resume or split the family run; do not treat timeout as product PASS",
            "evidence": {"timeout_reason": row.get("timeout_reason")},
        }

    mismatch_rows: list[dict[str, Any]] = []
    terminal_rows: list[dict[str, Any]] = []
    failure_texts: list[str] = []
    for item in _safe_list(live.get("rows")):
        scenario = _safe_dict(item)
        for failure in _safe_list(scenario.get("failures")):
            text = str(failure)
            failure_texts.append(text)
            if text.startswith("live_browser_family_mismatch:"):
                raw = text.split(":", 1)[1]
                try:
                    mismatch_rows.append(json.loads(raw))
                except json.JSONDecodeError:
                    mismatch_rows.append({"raw": raw})
            elif text.startswith("post_apply_outside_target_band_without_engineering_blocker:"):
                raw = text.split(":", 1)[1]
                try:
                    terminal_rows.append(json.loads(raw))
                except json.JSONDecodeError:
                    terminal_rows.append({"raw": raw})
    if terminal_rows:
        return {
            "classification": "LIVE_PRODUCT_TERMINAL_FAILURE",
            "owner": "family runtime / terminal publication proof",
            "action": "fix candidate folding, ranking, or terminal proof; do not weaken the gate",
            "evidence": {"post_apply_outside_target_band": terminal_rows},
        }
    settle_timeout_tokens = (
        "post_apply_solver_timeout",
        "post_apply_solver_state_timeout",
        "apply_run_end_event_missing",
        "live_scenario_budget_exceeded",
        "live_audit_deadline_exceeded",
    )
    settle_timeouts = [
        failure for failure in failure_texts
        if any(token in failure for token in settle_timeout_tokens)
    ]
    if settle_timeouts:
        return {
            "classification": "LIVE_POST_APPLY_SETTLE_TIMEOUT",
            "owner": "live browser/apply settle path",
            "action": "reduce rerun/evaluation churn or split the recipe; do not treat an unsettled Apply as PASS",
            "evidence": {"failure_tokens": settle_timeouts[:20]},
        }
    if mismatch_rows:
        return {
            "classification": "EXPECTED_FAMILY_RECIPE_MISMATCH_REQUIRES_REVIEW",
            "owner": "live recipe setup or family chooser",
            "action": "prove the recipe triggers the expected family, then either correct the recipe or fix chooser behavior",
            "evidence": {"family_mismatches": mismatch_rows},
        }
    phase_contract_failures = [
        str(failure)
        for phase in _safe_list(row.get("payload_summary", {}).get("phases"))
        for failure in _safe_list(_safe_dict(phase).get("failures"))
    ]
    publication_gap_tokens = {
        "missing_publication_hash",
        "selected_family_mismatch",
        "authority_hash_missing",
        "missing_authority_hash",
    }
    publication_gaps = [
        failure for failure in phase_contract_failures
        if any(token in failure for token in publication_gap_tokens)
    ]
    if publication_gaps:
        return {
            "classification": "LIVE_PUBLICATION_EVIDENCE_GAP",
            "owner": "family publication probe or live route",
            "action": "repair the publication/hash/family evidence path; do not reinterpret missing evidence as a valid result",
            "evidence": {"phase_contract_failures": publication_gaps[:20]},
        }
    logical = _safe_dict(row.get("logical_ladder_proof"))
    formatting = _safe_dict(row.get("format_authority_proof"))
    missing = list(logical.get("missing_checks") or []) + list(formatting.get("missing_checks") or [])
    if missing and int(live.get("failed_count") or 0) == 0:
        return {
            "classification": "LIVE_EVIDENCE_GAP",
            "owner": "family verifier evidence",
            "action": "add the missing proof fields; product behavior is not inferred from this gap",
            "evidence": {"missing_checks": sorted(set(str(item) for item in missing))},
        }
    return {
        "classification": "UNCLASSIFIED_LIVE_FAILURE",
        "owner": "family lock investigation",
        "action": "inspect the per-scenario failure rows before changing product code",
        "evidence": {
            "live_status": live.get("status"),
            "failed_count": live.get("failed_count"),
            "failures": [
                str(item)
                for scenario in _safe_list(live.get("rows"))
                for item in _safe_list(_safe_dict(scenario).get("failures"))
            ][:20],
        },
    }


def _with_failure_diagnosis(row: dict[str, Any]) -> dict[str, Any]:
    row["failure_diagnosis"] = _failure_diagnosis(row)
    return row


def _parallel_browser_readiness_retry_evidence(row: dict[str, Any]) -> dict[str, Any]:
    """Classify the one transient failure eligible for a clean serial retry.

    The retry is intentionally narrow.  It is allowed only when the live
    browser applied the requested recipe and update payload, authoritative
    engineering state reached terminal PASS, and the sole scenario failure was
    the final card's visual readiness window.  Engineering, family identity,
    recipe, runtime, solver, or apply-settle failures are never retried here.
    """

    live = _safe_dict(_safe_dict(row.get("payload_summary")).get("live_audit"))
    failed_rows = [
        _safe_dict(item)
        for item in _safe_list(live.get("rows"))
        if _safe_list(_safe_dict(item).get("failures"))
    ]
    failure_tokens = [
        str(failure)
        for scenario in failed_rows
        for failure in _safe_list(scenario.get("failures"))
    ]
    blocking_reasons = {
        str(_safe_dict(item).get("reason") or "")
        for item in _safe_list(
            _safe_dict(row.get("payload_summary")).get("blocking_failures")
        )
    }
    allowed_blocking_reasons = {
        "all_action_rows_have_visible_enabled_button_and_apply_effect",
        "final_design_guide_card_not_ready",
        "all_family_phases_pass",
    }

    scenario_checks: list[dict[str, Any]] = []
    for scenario in failed_rows:
        recipe_probe = _safe_dict(scenario.get("browser_recipe_probe"))
        identity = _safe_dict(scenario.get("browser_family_identity_contract"))
        settle = _safe_dict(scenario.get("post_apply_authoritative_settle_proof"))
        final_conditions = _safe_dict(settle.get("final_conditions"))
        publication_after = _safe_dict(scenario.get("publication_probe_after"))
        cta_after = _safe_dict(publication_after.get("cta"))
        scenario_checks.append(
            {
                "scenario_id": scenario.get("scenario_id"),
                "sole_failure_is_final_card_not_ready": (
                    _safe_list(scenario.get("failures"))
                    == ["final_design_guide_card_not_ready"]
                ),
                "recipe_matches": bool(recipe_probe.get("requested"))
                and recipe_probe.get("requested") == recipe_probe.get("applied"),
                "family_identity_matches": identity.get("passes_contract") is True,
                "trigger_passed": scenario.get("trigger_passed") is True,
                "solver_did_not_timeout": scenario.get("solver_state_timeout") is not True,
                "authoritative_apply_settled": all(
                    final_conditions.get(name) is True
                    for name in (
                        "applied_updates_match",
                        "applied_updates_published",
                        "authoritative_state_advanced",
                        "overview_terminal_pass",
                        "publication_terminal_pass",
                    )
                ),
                "terminal_publication_passed": (
                    str(publication_after.get("outcome_state") or "").upper() == "PASS"
                    and cta_after.get("enabled") is not True
                ),
            }
        )

    checks = {
        "parallel_run_was_used": True,
        "family_not_already_locked": row.get("passed") is not True,
        "worker_did_not_timeout": row.get("timed_out") is not True,
        "live_browser_executed": live.get("executed") is True,
        "live_browser_has_no_runtime_errors": not _safe_list(live.get("errors")),
        "failed_scenario_present": bool(failed_rows),
        "all_failure_tokens_are_final_card_not_ready": bool(failure_tokens)
        and set(failure_tokens) == {"final_design_guide_card_not_ready"},
        "only_readiness_blocking_reasons": bool(blocking_reasons)
        and blocking_reasons <= allowed_blocking_reasons
        and "final_design_guide_card_not_ready" in blocking_reasons,
        "failed_scenarios_pass_strict_transaction_checks": bool(scenario_checks)
        and all(all(value is True for key, value in check.items() if key != "scenario_id") for check in scenario_checks),
    }
    eligible = all(checks.values())
    return {
        "eligible": eligible,
        "classification": (
            "parallel_browser_readiness_timeout"
            if eligible
            else "not_parallel_browser_readiness_only"
        ),
        "checks": checks,
        "scenario_checks": scenario_checks,
        "failure_tokens": failure_tokens,
        "blocking_reasons": sorted(blocking_reasons),
    }


def _static_format_authority_checks() -> dict[str, bool]:
    contract = _read_json(FINAL_FORMATTING_CONTRACT)
    contract_identity = _safe_dict(contract.get("contract_identity"))
    formatter_source = _read_text(FINAL_FORMATTER)
    renderer_source = _read_text(FINAL_UI_RENDERER)
    return {
        "formatting_contract_exists_and_targets_final_publication": (
            contract_identity.get("input") == "FinalDesignGuidePublication"
            and contract_identity.get("output") == "FinalDesignGuideCardFormat"
            and "FinalDesignGuidePublication" in _safe_list(contract.get("allowed_inputs"))
            and "raw guidance item dicts" in _safe_list(contract.get("forbidden_inputs"))
        ),
        "formatter_builds_from_final_publication_only": (
            "def build_final_design_guide_card_format(" in formatter_source
            and "publication: FinalDesignGuidePublication" in formatter_source
            and "inputs_page" not in formatter_source
            and "streamlit" not in formatter_source.lower()
            and "st.session_state" not in formatter_source
        ),
        "ui_renderer_is_render_only": (
            "def render_final_design_guide_card_html(" in renderer_source
            and "FinalDesignGuideCardFormat" in renderer_source
            and "FinalDesignGuidePublication(" not in renderer_source
            and "st.button" not in renderer_source
            and "import streamlit" not in renderer_source.lower()
            and "from streamlit" not in renderer_source.lower()
            and "session_state" not in renderer_source
        ),
    }


def _format_authority_proof(payload: dict[str, Any], family_id: str) -> dict[str, Any]:
    static_checks = _static_format_authority_checks()
    rows = _live_rows(payload)
    compatibility_owner_evidence = (
        _compatibility_owner_format_evidence(payload, family_id)
        if family_id in TERMINAL_FAMILIES
        else {}
    )
    all_payload = {
        "payload": payload,
        "rows": rows,
        "compatibility_owner_evidence": compatibility_owner_evidence,
    }
    identity_rows = [
        _safe_dict(row.get("browser_family_identity_contract"))
        for row in rows
        if isinstance(row.get("browser_family_identity_contract"), dict)
    ]
    visible_family_ok = bool(identity_rows) and all(row.get("passes_contract") for row in identity_rows)
    compatibility_owner_ok = bool(compatibility_owner_evidence.get("owner_identity_ok"))
    if compatibility_owner_evidence.get("rows"):
        visible_family_ok = compatibility_owner_ok
    elif family_id in TERMINAL_FAMILIES and not rows:
        visible_family_ok = _is_locked(payload) and (
            compatibility_owner_ok
            or not compatibility_owner_evidence.get("rows")
        )

    display_hash_present = (
        _nested_key_present(all_payload, ("final_publication_display_hash",))
        or _nested_key_present(all_payload, ("display_hash",))
    )
    cta_hash_present = (
        _nested_key_present(all_payload, ("final_publication_cta_hash",))
        or _nested_key_present(all_payload, ("button_contract_hash",))
        or _nested_key_present(all_payload, ("cta_hash",))
    )
    format_hash_present = (
        _nested_key_present(all_payload, ("format_hash",))
        or _nested_text_contains(all_payload, ("FinalDesignGuidePublication", "render"))
        or _nested_key_present(all_payload, ("final_publication_authority_hash",))
        or (
            static_checks.get("formatting_contract_exists_and_targets_final_publication") is True
            and static_checks.get("formatter_builds_from_final_publication_only") is True
            and static_checks.get("ui_renderer_is_render_only") is True
        )
    )
    checks = {
        **static_checks,
        "visible_family_matches_publication_family": bool(visible_family_ok),
        "visible_card_is_hash_stamped_from_publication_display": bool(display_hash_present),
        "cta_hash_is_hash_stamped_from_publication_cta": bool(cta_hash_present),
        "card_format_hash_or_clean_renderer_proof_exists": bool(format_hash_present),
    }
    missing = [name for name, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not missing else "FAIL",
        "passed": not missing,
        "checks": checks,
        "missing_checks": missing,
        "evidence_summary": {
            "live_row_count": len(rows),
            "identity_contract_rows": len(identity_rows),
            "compatibility_owner_row_count": len(
                _safe_list(compatibility_owner_evidence.get("rows"))
            ),
            "compatibility_owner_live_row_count": len(
                _safe_list(compatibility_owner_evidence.get("owner_rows"))
            ),
            "compatibility_owner_artifacts": _safe_list(
                compatibility_owner_evidence.get("owner_artifacts")
            ),
            "formatting_contract": str(FINAL_FORMATTING_CONTRACT),
            "formatter": str(FINAL_FORMATTER),
            "ui_renderer": str(FINAL_UI_RENDERER),
        },
    }


def _logical_ladder_proof(payload: dict[str, Any], family_id: str) -> dict[str, Any]:
    family_row = _safe_dict(payload.get("family_10_fuzz_row"))
    ladder_methods = _safe_list(family_row.get("ladder_methods"))
    ladder_candidates = _safe_list(family_row.get("ladder_candidates_considered"))
    best_candidate = _safe_dict(family_row.get("best_candidate_proof"))
    winning_candidate = _safe_dict(family_row.get("winning_candidate"))
    published_result = _safe_list(family_row.get("published_result"))
    live_execution = _safe_dict(family_row.get("live_execution") or payload.get("live_audit"))
    live_rows = _live_rows(payload)
    live_passed_count = int(live_execution.get("passed_count") or best_candidate.get("passed_count") or 0)
    live_failed_count = int(live_execution.get("failed_count") or best_candidate.get("failed_count") or 0)
    live_unique_recipe_count = int(
        live_execution.get("unique_recipe_count")
        or best_candidate.get("unique_recipe_count")
        or len({str(row.get("recipe") or "") for row in live_rows if str(row.get("recipe") or "").strip()})
        or 0
    )
    live_ten_recipe_contract = bool(live_passed_count >= 10 and live_unique_recipe_count >= 10)
    phase_b_passed = _passed_phase(payload, "B_candidate_ladder_proof")
    phase_c_passed = _passed_phase(payload, "C_publication_contract_proof")
    all_payload = {
        "family_row": family_row,
        "payload": payload,
    }

    terminal_family = family_id in TERMINAL_FAMILIES
    terminal_proof = _terminal_result_proven(payload, family_id)
    folding_required = family_id in FOLDING_REQUIRED_FAMILIES
    same_click_folding_proven = (
        _nested_key_present(all_payload, ("fold",))
        or _nested_key_present(all_payload, ("terminal_candidate",))
        or _nested_text_contains(all_payload, ("folded", "candidate"))
        or _nested_text_contains(all_payload, ("same-click",))
        or (phase_c_passed and bool(live_rows))
    )
    ranking_proven = (
        bool(winning_candidate)
        or bool(best_candidate and best_candidate.get("source") == "browser_live_family_10_fuzz")
        and int(best_candidate.get("passed_count") or 0) >= 10
        and int(best_candidate.get("unique_recipe_count") or 0) >= 10
        or (_is_locked(payload) and phase_b_passed)
    )
    checks = {
        "contract_ladder_order_proven": (
            terminal_proof
            if terminal_family
            else bool(ladder_methods) and phase_b_passed
        ),
        "candidate_generation_per_lane_proven": terminal_family
        or bool(ladder_candidates)
        or (phase_b_passed and bool(live_rows) and live_unique_recipe_count >= 10)
        or _nested_key_present(all_payload, ("candidate_generation",))
        or _nested_key_present(all_payload, ("lane", "candidate")),
        "candidate_rejection_reasons_proven": terminal_family
        or (phase_b_passed and (live_ten_recipe_contract or live_failed_count > 0))
        or _nested_key_present(all_payload, ("rejected",))
        or _nested_key_present(all_payload, ("rejection",))
        or _nested_key_present(all_payload, ("blocked", "reason"))
        or _nested_text_contains(all_payload, ("rejected",)),
        "ranking_best_candidate_proven": terminal_family
        or bool(ranking_proven)
        or live_ten_recipe_contract
        and (
            _nested_key_present(all_payload, ("ranking",))
            or _nested_key_present(all_payload, ("best_candidate",))
            or _nested_text_contains(all_payload, ("best", "candidate"))
        ),
        "same_click_folding_proven_or_not_required": (not folding_required) or same_click_folding_proven,
        "terminal_result_after_apply_or_terminal_proof": terminal_proof,
    }
    missing = [name for name, passed in checks.items() if not passed]
    return {
        "status": "PASS" if not missing else "FAIL",
        "passed": not missing,
        "checks": checks,
        "missing_checks": missing,
        "folding_required": folding_required,
        "evidence_summary": {
            "ladder_methods": ladder_methods,
            "ladder_candidate_count": len(ladder_candidates),
            "best_candidate_source": best_candidate.get("source"),
            "best_candidate_passed_count": best_candidate.get("passed_count"),
            "best_candidate_unique_recipe_count": best_candidate.get("unique_recipe_count"),
            "winning_candidate_present": bool(winning_candidate),
            "published_result_count": len(published_result),
            "live_executed": live_execution.get("executed"),
            "live_passed_count": live_execution.get("passed_count"),
            "live_failed_count": live_execution.get("failed_count"),
            "terminal_family": terminal_family,
        },
    }


def _age_hours(path: Path | None) -> float | None:
    if not path:
        return None
    return round((time.time() - path.stat().st_mtime) / 3600.0, 3)


def _artifact_is_bound_to_run(row: dict[str, Any], verification_run_id: str) -> bool:
    """Return true only for a child artifact emitted by this universal run.

    Resume rows remain useful diagnostic context, but they must never be able
    to satisfy the release lock.  The child artifact's own run id is the
    authority, rather than the row's cached metadata or filename timestamp.
    """
    if bool(row.get("resumed")):
        return False
    artifact = str(row.get("artifact") or "").strip()
    if not artifact:
        return False
    payload = _read_json(Path(artifact))
    return str(payload.get("verification_run_id") or "") == str(verification_run_id)


def _collect_terminated_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    """Collect bounded output after a worker tree has been terminated.

    Descendant browser processes can retain inherited pipe handles on Windows.
    A second unbounded ``communicate`` would therefore strand the universal
    coordinator after the family deadline.  The timeout path must remain
    bounded and diagnostic output is best-effort.
    """
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return "", "worker process did not exit after termination"
    try:
        stdout, stderr = process.communicate(timeout=5)
        return str(stdout or ""), str(stderr or "")
    except subprocess.TimeoutExpired:
        return "", "worker output pipes did not close after termination"


def _run_family_gate(
    family_id: str,
    args: argparse.Namespace,
    *,
    port: int | None = None,
    run_started_at: float | None = None,
    verification_run_id: str | None = None,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(FAMILY_GATE),
        "--family",
        family_id,
        "--seed",
        str(args.seed),
        "--port",
        str(port if port is not None else args.port),
        "--live-card-timeout-s",
        str(args.live_card_timeout_s),
        "--live-apply-timeout-s",
        str(args.live_apply_timeout_s),
    ]
    if args.base_url:
        cmd.extend(["--base-url", str(args.base_url)])
    if args.headed:
        cmd.append("--headed")
    started = time.time()
    worker_state = _write_worker_state(
        family_id,
        {
            "schema": "design_brain.universal_live_family_worker.v1",
            "family_id": family_id,
            "status": "STARTING",
            "started_at": _stamp(),
            "timeout_s": float(args.family_timeout_s),
            "command": cmd,
            "verification_run_id": verification_run_id,
        },
    )
    child_env = os.environ.copy()
    if verification_run_id:
        child_env["DESIGN_BRAIN_VERIFICATION_RUN_ID"] = verification_run_id
    process = subprocess.Popen(
        cmd,
        cwd=ROOT,
        env=child_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    _write_worker_state(
        family_id,
        {
            "schema": "design_brain.universal_live_family_worker.v1",
            "family_id": family_id,
            "status": "RUNNING",
            "started_at": _stamp(),
            "timeout_s": float(args.family_timeout_s),
            "pid": process.pid,
            "command": cmd,
            "verification_run_id": verification_run_id,
        },
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=int(args.family_timeout_s))
        returncode = process.returncode
        worker_status = "PASS" if returncode == 0 else "FAIL"
        timeout_reason = None
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        stdout, stderr = _collect_terminated_process(process)
        returncode = 124
        timed_out = True
        worker_status = "TIMEOUT"
        timeout_reason = f"family worker exceeded {float(args.family_timeout_s):g}s deadline"
    authoritative_terminal_payload = False
    child_returncode = returncode
    if timed_out:
        path, payload = None, {}
    else:
        path, payload = _latest_family_lock_artifact(
            family_id,
            run_started_at=run_started_at,
            verification_run_id=verification_run_id,
        )
        # Terminal families are executed through a wrapper gate, but their
        # authoritative browser evidence is the dedicated terminal
        # acceptance artifact.  Prefer that same-run payload when the wrapper
        # returned without live rows; otherwise the universal lock can report
        # a false ``NOT_RUN`` coverage gap even though terminal evidence was
        # emitted by the child verifier.
        if family_id in TERMINAL_FAMILIES:
            terminal_path, terminal_payload = _latest_family_lock_artifact(
                family_id,
                run_started_at=run_started_at,
                verification_run_id=verification_run_id,
            )
            current_live = _safe_dict(payload.get("live_audit"))
            terminal_name = terminal_path.name if terminal_path else ""
            if (
                terminal_path is not None
                and terminal_name.startswith("design_guide_terminal_family_live_acceptance_")
                and (
                    not current_live.get("executed")
                    or str(current_live.get("status") or "").upper() == "NOT_RUN"
                    or not payload.get("terminal_acceptance_rows")
                )
            ):
                path, payload = terminal_path, terminal_payload
                authoritative_terminal_payload = True
                # The shared terminal verifier reports the aggregate result for
                # all terminal families.  Its process code may therefore be 1
                # because a different family failed, even when this family's
                # bound row passed.  The family row is the authority here; keep
                # the child code separately for diagnosis.
                child_returncode = returncode
                if _is_locked(payload):
                    returncode = 0
    logical_ladder = _logical_ladder_proof(payload, family_id)
    format_authority = _format_authority_proof(payload, family_id)
    worker_state = _write_worker_state(
        family_id,
        {
            "schema": "design_brain.universal_live_family_worker.v1",
            "family_id": family_id,
            "status": worker_status,
            "started_at": _stamp(),
            "finished_at": _stamp(),
            "duration_sec": round(time.time() - started, 3),
            "timeout_s": float(args.family_timeout_s),
            "pid": process.pid,
            "returncode": returncode,
            "timed_out": timed_out,
            "timeout_reason": timeout_reason,
            "command": cmd,
            "artifact": str(path) if path else None,
            "verification_run_id": verification_run_id,
        },
    )
    return _with_failure_diagnosis({
        "family_id": family_id,
        "command": cmd,
        "returncode": returncode,
        "child_returncode": child_returncode if authoritative_terminal_payload else None,
        "duration_sec": round(time.time() - started, 3),
        "stdout_tail": str(stdout or "").strip().splitlines()[-30:],
        "stderr_tail": str(stderr or "").strip().splitlines()[-30:],
        "timed_out": timed_out,
        "failure_classification": "family_verification_runtime_timeout" if timed_out else None,
        "timeout_reason": timeout_reason,
        "worker_state_artifact": str(worker_state),
        "artifact": str(path) if path else None,
        "artifact_age_hours": _age_hours(path),
        "lock_status": str(payload.get("lock_status") or "MISSING"),
        "passed": returncode == 0
        and _is_locked(payload)
        and logical_ladder["passed"]
        and format_authority["passed"],
        "logical_ladder_proof": logical_ladder,
        "format_authority_proof": format_authority,
        "payload_summary": {
            "schema": payload.get("schema"),
            "family": payload.get("family"),
            "lock_status": payload.get("lock_status"),
            "blocking_failures": payload.get("blocking_failures"),
            "live_audit": payload.get("live_audit"),
        },
    })


def _failed_worker_row(
    family_id: str,
    args: argparse.Namespace,
    exc: BaseException,
) -> dict[str, Any]:
    """Convert an unexpected worker exception into a composed gate row."""
    reason = f"{type(exc).__name__}: {exc}"
    worker_state = _write_worker_state(
        family_id,
        {
            "schema": "design_brain.universal_live_family_worker.v1",
            "family_id": family_id,
            "status": "ABORTED",
            "finished_at": _stamp(),
            "returncode": 125,
            "timed_out": False,
            "timeout_reason": reason,
            "verification_run_id": os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID"),
        },
    )
    logical_ladder = {"status": "FAIL", "passed": False, "missing_checks": ["worker_completed"]}
    format_authority = {"status": "FAIL", "passed": False, "missing_checks": ["worker_completed"]}
    return _with_failure_diagnosis({
        "family_id": family_id,
        "command": [],
        "returncode": 125,
        "duration_sec": None,
        "stdout_tail": [],
        "stderr_tail": [reason],
        "timed_out": False,
        "failure_classification": "unhandled_worker_exception",
        "timeout_reason": reason,
        "worker_state_artifact": str(worker_state),
        "artifact": None,
        "artifact_age_hours": None,
        "lock_status": "MISSING",
        "passed": False,
        "logical_ladder_proof": logical_ladder,
        "format_authority_proof": format_authority,
        "payload_summary": {},
    })


def _inspect_family_gate(family_id: str, *, max_age_hours: float | None = None) -> dict[str, Any]:
    path, payload = _latest_family_lock_artifact(family_id)
    age = _age_hours(path)
    stale = bool(max_age_hours is not None and age is not None and age > max_age_hours)
    logical_ladder = _logical_ladder_proof(payload, family_id)
    format_authority = _format_authority_proof(payload, family_id)
    return _with_failure_diagnosis({
        "family_id": family_id,
        "artifact": str(path) if path else None,
        "artifact_age_hours": age,
        "lock_status": str(payload.get("lock_status") or "MISSING"),
        "passed": bool(path)
        and _is_locked(payload)
        and not stale
        and logical_ladder["passed"]
        and format_authority["passed"],
        "stale": stale,
        "logical_ladder_proof": logical_ladder,
        "format_authority_proof": format_authority,
        "payload_summary": {
            "schema": payload.get("schema"),
            "family": payload.get("family"),
            "lock_status": payload.get("lock_status"),
            "blocking_failures": payload.get("blocking_failures"),
            "live_audit": payload.get("live_audit"),
        },
    })


def _selected_families(args: argparse.Namespace) -> list[str]:
    available = tuple(SUPPORTED_FAMILIES.keys())
    if args.family:
        requested = [part.strip().upper() for part in str(args.family).split(",") if part.strip()]
        unknown = [family for family in requested if family not in SUPPORTED_FAMILIES]
        if unknown:
            raise SystemExit(f"Unknown family for universal lock: {unknown}")
        return requested
    return list(available)


def _build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    families = _selected_families(args)
    max_age = float(args.max_age_hours) if args.max_age_hours is not None else None
    code_state = _code_state_hash()
    resume_contract_hash = _resume_contract_hash()
    canonical_run = bool(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"))
    verification_run_id = str(
        os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID")
        or f"universal-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.getpid()}"
    )
    run_started_at = time.time()
    # A release run must produce same-run child artifacts. Resume is retained
    # for interactive diagnostics, but cannot reuse rows from an earlier
    # canonical run because that would make stale browser evidence authoritative.
    resume_state = _read_resume_state() if args.run_live and args.resume and not canonical_run else {}
    resume_matches = bool(
        args.resume
        and not canonical_run
        and resume_state.get("code_state_hash") == code_state["hash"]
        and resume_state.get("resume_contract_hash") == resume_contract_hash
    )
    rows: list[dict[str, Any]] = []
    serial_readiness_retries: list[dict[str, Any]] = []
    if args.run_live:
        _reconcile_worker_states()
        progress = {
            "schema": "design_brain.universal_live_family_lock_resume_state.v1",
            "code_state_hash": code_state["hash"],
            "resume_contract_hash": resume_contract_hash,
            "families": {},
        }
        if resume_matches:
            progress["families"] = dict(resume_state.get("families") or {})
        pending: list[tuple[int, str]] = []
        for index, family in enumerate(families):
            cached = progress["families"].get(family)
            if (
                resume_matches
                and family not in TERMINAL_FAMILIES
                and isinstance(cached, dict)
                and cached.get("passed")
            ):
                row = dict(cached)
                row["resumed"] = True
                rows.append(row)
            else:
                pending.append((index, family))
        # Terminal families share one aggregate browser verifier artifact.  They
        # must not run concurrently: concurrent workers can overwrite or race
        # the aggregate file, leaving the parent with false NOT_RUN coverage.
        terminal_pending = [item for item in pending if item[1] in TERMINAL_FAMILIES]
        parallel_pending = [item for item in pending if item[1] not in TERMINAL_FAMILIES]

        def record_row(family: str, row: dict[str, Any]) -> None:
            row["resumed"] = False
            progress["families"][family] = row
            _write_resume_state(progress)
            rows.append(row)

        def replace_row(family: str, row: dict[str, Any]) -> None:
            row["resumed"] = False
            progress["families"][family] = row
            _write_resume_state(progress)
            rows[:] = [
                row if str(existing.get("family_id") or "") == family else existing
                for existing in rows
            ]

        if int(args.max_workers) <= 1 or len(parallel_pending) <= 1:
            for index, family in parallel_pending:
                try:
                    row = _run_family_gate(
                        family,
                        args,
                        port=int(args.port) + index,
                        run_started_at=run_started_at,
                        verification_run_id=verification_run_id,
                    )
                except BaseException as exc:
                    row = _failed_worker_row(family, args, exc)
                record_row(family, row)
        else:
            worker_count = min(int(args.max_workers), len(parallel_pending))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(
                        _run_family_gate,
                        family,
                        args,
                        port=int(args.port) + index,
                        run_started_at=run_started_at,
                        verification_run_id=verification_run_id,
                    ): family
                    for index, family in parallel_pending
                }
                for future in as_completed(futures):
                    family = futures[future]
                    try:
                        row = future.result()
                    except BaseException as exc:
                        row = _failed_worker_row(family, args, exc)
                    record_row(family, row)

            # A parallel browser pass can exhaust a visual readiness window
            # after the authoritative transaction has already completed.  Run
            # only that narrowly classified failure once more, serially, after
            # every competing browser worker has exited.  The strict family
            # gate remains authoritative: a failed serial retry stays failed.
            for index, family in parallel_pending:
                parallel_row = next(
                    (
                        item
                        for item in rows
                        if str(item.get("family_id") or "") == family
                    ),
                    {},
                )
                retry_evidence = _parallel_browser_readiness_retry_evidence(
                    parallel_row
                )
                if retry_evidence.get("eligible") is not True:
                    continue
                try:
                    retry_row = _run_family_gate(
                        family,
                        args,
                        port=int(args.port) + index,
                        run_started_at=run_started_at,
                        verification_run_id=verification_run_id,
                    )
                except BaseException as exc:
                    retry_row = _failed_worker_row(family, args, exc)
                retry_row["serial_readiness_retry"] = {
                    "attempted": True,
                    "classification": retry_evidence.get("classification"),
                    "parallel_attempt_artifact": parallel_row.get("artifact"),
                    "parallel_attempt_returncode": parallel_row.get("returncode"),
                    "parallel_attempt_duration_sec": parallel_row.get("duration_sec"),
                    "parallel_attempt_failure_diagnosis": parallel_row.get(
                        "failure_diagnosis"
                    ),
                    "eligibility_evidence": retry_evidence,
                    "serial_attempt_artifact": retry_row.get("artifact"),
                    "serial_attempt_passed": retry_row.get("passed") is True,
                }
                serial_readiness_retries.append(
                    {
                        "family_id": family,
                        **_safe_dict(retry_row.get("serial_readiness_retry")),
                    }
                )
                replace_row(family, retry_row)

        # Keep the dedicated terminal acceptance route isolated and serialized.
        # This preserves bounded parallelism for independent family gates while
        # making the shared terminal evidence deterministic and same-run bound.
        for index, family in terminal_pending:
            try:
                row = _run_family_gate(
                    family,
                    args,
                    port=int(args.port) + index,
                    run_started_at=run_started_at,
                    verification_run_id=verification_run_id,
                )
            except BaseException as exc:
                row = _failed_worker_row(family, args, exc)
            record_row(family, row)
        rows.sort(key=lambda row: families.index(str(row.get("family_id") or "")))
    else:
        rows = [_inspect_family_gate(family, max_age_hours=max_age) for family in families]
    locked_rows = [row for row in rows if row.get("passed")]
    missing_or_failed = [row for row in rows if not row.get("passed")]
    current_run_locked_rows = [
        row for row in locked_rows if _artifact_is_bound_to_run(row, verification_run_id)
    ]
    stale_or_resumed_rows = [
        str(row.get("family_id") or "")
        for row in locked_rows
        if not _artifact_is_bound_to_run(row, verification_run_id)
    ]
    universal_locked = (
        bool(args.run_live)
        and len(current_run_locked_rows) == len(rows)
        and not missing_or_failed
    )
    inspection_complete = not bool(args.run_live)
    return {
        "schema": "design_brain.universal_live_family_lock.v1",
        "verification_run_id": verification_run_id,
        "run_started_at": datetime.fromtimestamp(run_started_at).isoformat(),
        "source_code_hash": code_state["hash"],
        "status": "PASS" if inspection_complete or universal_locked else "FAIL",
        "universal_lock_status": "LOCKED" if universal_locked else "NOT_RUN" if inspection_complete else "NOT_LOCKED",
        "generated_at": _stamp(),
        "mode": "live-run" if args.run_live else "inspection-only",
        "run_live": bool(args.run_live),
        "code_state_hash": code_state["hash"],
        "code_state_hash_scope": {
            "file_count": code_state["file_count"],
            "scope_files": code_state["scope_files"],
            "scope_dirs": code_state["scope_dirs"],
        },
        "seed": int(args.seed),
        "base_url": args.base_url,
        "port": int(args.port),
        "max_age_hours": max_age,
        "required_live_proofs": list(REQUIRED_LIVE_PROOFS),
        "logical_ladder_required_checks": list(LOGICAL_LADDER_REQUIRED_CHECKS),
        "format_authority_required_checks": list(FORMAT_AUTHORITY_REQUIRED_CHECKS),
        "resume": bool(args.resume and not canonical_run),
        "resume_disabled_for_canonical_run": canonical_run and bool(args.resume),
        "resume_state_path": str(RESUME_STATE_PATH),
        "resume_state_reused": bool(resume_matches),
        "resume_contract_hash": resume_contract_hash,
        "serial_readiness_retries": serial_readiness_retries,
        "families_required": families,
        "family_count": len(families),
        "locked_family_count": len(locked_rows),
        "current_run_bound_locked_family_count": len(current_run_locked_rows),
        "stale_or_resumed_locked_families": stale_or_resumed_rows,
        "not_locked_family_count": len(missing_or_failed),
        "families": rows,
        "missing_or_failed_families": [row["family_id"] for row in missing_or_failed],
        "families_missing_logical_ladder_proof": [
            row["family_id"]
            for row in rows
            if _safe_dict(row.get("logical_ladder_proof")).get("passed") is not True
        ],
        "families_missing_format_authority_proof": [
            row["family_id"]
            for row in rows
            if _safe_dict(row.get("format_authority_proof")).get("passed") is not True
        ],
        "fully_verified_app_requires": "Run this verifier with --run-live and reach universal_lock_status=LOCKED.",
        "product_behaviour_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Universal Live Design Brain Family Lock",
        "",
        f"Status: `{payload['status']}`",
        f"Universal lock status: `{payload['universal_lock_status']}`",
        f"Mode: `{payload['mode']}`",
        f"Run live: `{payload['run_live']}`",
        "",
        "## Fully Verified Rule",
        "",
        "The app is not fully verified unless this gate is run in live mode and returns `universal_lock_status=LOCKED`.",
        "",
        "## Required Proofs",
        "",
    ]
    for proof in payload["required_live_proofs"]:
        lines.append(f"- {proof}")
    lines.extend(
        [
            "",
            "## Family Results",
            "",
            "| Family | Locked | Logical ladder | Format authority | Status | Artifact |",
            "| --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in payload["families"]:
        ladder = _safe_dict(row.get("logical_ladder_proof"))
        format_authority = _safe_dict(row.get("format_authority_proof"))
        lines.append(
            "| `{family}` | `{passed}` | `{ladder}` | `{format_authority}` | `{status}` | `{artifact}` |".format(
                family=row["family_id"],
                passed=row.get("passed"),
                ladder=ladder.get("status"),
                format_authority=format_authority.get("status"),
                status=row.get("lock_status"),
                artifact=row.get("artifact"),
            )
        )
    lines.extend(
        [
            "",
            "## Missing Or Failed Families",
            "",
        ]
    )
    if payload["missing_or_failed_families"]:
        for family in payload["missing_or_failed_families"]:
            lines.append(f"- `{family}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Families Missing Format/Text Authority Proof", ""])
    if payload["families_missing_format_authority_proof"]:
        by_family = {
            row["family_id"]: _safe_dict(row.get("format_authority_proof")).get("missing_checks")
            for row in payload["families"]
        }
        for family in payload["families_missing_format_authority_proof"]:
            lines.append(f"- `{family}`: `{by_family.get(family)}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Families Missing Logical Ladder Proof", ""])
    if payload["families_missing_logical_ladder_proof"]:
        by_family = {
            row["family_id"]: _safe_dict(row.get("logical_ladder_proof")).get("missing_checks")
            for row in payload["families"]
        }
        for family in payload["families_missing_logical_ladder_proof"]:
            lines.append(f"- `{family}`: `{by_family.get(family)}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Failure Diagnosis",
            "",
            "This section separates missing coverage, recipe/chooser mismatches, real post-Apply failures, and evidence gaps. A diagnosis does not override the strict lock result.",
            "",
            "| Family | Classification | Owner | Action |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["families"]:
        diagnosis = _safe_dict(row.get("failure_diagnosis"))
        lines.append(
            "| `{family}` | `{classification}` | `{owner}` | {action} |".format(
                family=row["family_id"],
                classification=diagnosis.get("classification", "UNKNOWN"),
                owner=diagnosis.get("owner", "unknown"),
                action=str(diagnosis.get("action", "inspect artifact")).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Next Command",
            "",
            "```powershell",
            "python tools/verification/design_brain_universal_live_family_lock.py --run-live --port 9301",
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true", help="Run every family live fuzz regression lock gate.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed family rows from a matching current-code live run.",
    )
    parser.add_argument(
        "--reconcile-workers",
        action="store_true",
        help="Reconcile stale universal worker records without starting a live browser run.",
    )
    parser.add_argument("--family", help="Comma-separated subset of family ids. Omit to require every supported family.")
    parser.add_argument("--seed", type=int, default=1007)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--port", type=int, default=8586)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Bounded parallel family workers. Each worker receives an isolated browser port.",
    )
    parser.add_argument("--live-card-timeout-s", type=float, default=20.0)
    parser.add_argument("--live-apply-timeout-s", type=float, default=20.0)
    parser.add_argument("--family-timeout-s", type=float, default=900.0)
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=None,
        help="Inspection-only freshness check for existing artifacts. Live mode writes fresh artifacts.",
    )
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    if args.reconcile_workers:
        reconciliation = _reconcile_worker_states()
        stamp = _stamp()
        payload = {
            "schema": "design_brain.universal_live_family_worker_reconciliation.v1",
            "status": "PASS" if not reconciliation["unreadable"] and not reconciliation["still_running"] else "FAIL",
            "generated_at": stamp,
            "worker_state_dir": str(WORKER_STATE_DIR),
            "reconciliation": reconciliation,
            "action": (
                "stale workers were marked ABORTED; resume the live lock"
                if reconciliation["aborted"]
                else "no stale workers found"
            ),
        }
        json_path = ARTIFACT_DIR / f"design_brain_universal_live_family_worker_reconciliation_{stamp}.json"
        report_path = AUDIT_DIR / f"design_brain_universal_live_family_worker_reconciliation_{stamp}.md"
        payload["artifact"] = str(json_path)
        payload["report"] = str(report_path)
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report_path.write_text(
            "# Universal Live Family Worker Reconciliation\n\n"
            f"Status: `{payload['status']}`\n\n"
            f"Inspected: `{reconciliation['inspected']}`\n\n"
            f"Aborted stale workers: `{', '.join(reconciliation['aborted']) or 'none'}`\n\n"
            f"Still running: `{', '.join(reconciliation['still_running']) or 'none'}`\n\n"
            f"Unreadable: `{', '.join(reconciliation['unreadable']) or 'none'}`\n\n"
            "This command does not certify any family and does not start a browser run.\n",
            encoding="utf-8",
        )
        print(f"design_brain_universal_live_family_worker_reconciliation {payload['status']}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 0 if payload["status"] == "PASS" else 1
    live_lock = _acquire_live_run_lock(args.port) if args.run_live else None
    try:
        payload = _build_snapshot(args)
        stamp = payload["generated_at"]
        json_path = ARTIFACT_DIR / f"design_brain_universal_live_family_lock_{stamp}.json"
        report_path = AUDIT_DIR / f"design_brain_universal_live_family_lock_{stamp}.md"
        payload["artifact"] = str(json_path)
        payload["report"] = str(report_path)
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        _write_markdown(payload, report_path)
        print(f"design_brain_universal_live_family_lock {payload['status']}")
        print(f"universal_lock_status={payload['universal_lock_status']}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        if args.run_live:
            return 0 if payload["universal_lock_status"] == "LOCKED" else 1
        return 0
    finally:
        if live_lock is not None:
            _release_live_run_lock(live_lock)


if __name__ == "__main__":
    raise SystemExit(main())
