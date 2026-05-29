from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
MANIFEST_DIR = REPO / "artifacts" / "verification" / "latest"
MANIFEST_JSON = MANIFEST_DIR / "verification_latest_manifest.json"
MANIFEST_MD = MANIFEST_DIR / "verification_latest_manifest.md"

FAMILIES: dict[str, list[str]] = {
    "latest_super_artifact": ["super_verification_*.json"],
    "latest_super_run_summary": [
        "artifacts/verification/latest/super_verification_runs/*/super_summary.json",
        "artifacts/super_verification_runs/*/super_summary.json",
    ],
    "latest_compact_review_json": ["compact_review_*.json"],
    "latest_compact_review_md": ["compact_review_*.md"],
    "latest_recommendation_contract": ["recommendation_contract_ladder_*.json"],
    "latest_real_user_design_guide_ladder": ["real_user_design_guide_ladder_*.json"],
    "latest_local_cleanup_effectiveness_ladder": ["local_cleanup_apply_effectiveness_ladder_*.json"],
    "latest_optimisation_expectation_ladder": ["optimisation_expectation_ladder_*.json"],
    "latest_summary_truth_ladder": ["summary_truth_ladder_*.json"],
    "latest_matrix_chooser_verifier": ["matrix_chooser_verifier_*.json"],
    "latest_shear_overdesign_ladder": ["shear_overdesign_debug_ladder_*.json"],
    "latest_golden_ladder": ["full_golden_ladder_rerun_*.json"],
}

SUPER_GATE_BY_FAMILY = {
    "latest_recommendation_contract": "recommendation_contract",
    "latest_real_user_design_guide_ladder": "real_user_design_guide",
    "latest_local_cleanup_effectiveness_ladder": "local_cleanup_apply_effectiveness",
    "latest_optimisation_expectation_ladder": "optimisation_expectation",
    "latest_summary_truth_ladder": "summary_truth",
    "latest_matrix_chooser_verifier": "matrix_chooser",
    "latest_shear_overdesign_ladder": "shear_overdesign",
    "latest_golden_ladder": "golden",
}


def _relative(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def _latest(patterns: list[str]) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(p for p in REPO.glob(pattern) if p.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _path_from_reference(ref: Any) -> Path | None:
    if not isinstance(ref, str) or not ref:
        return None
    path = Path(ref)
    if not path.is_absolute():
        path = REPO / path
    return path if path.exists() else None


def _load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists() or path.suffix.lower() != ".json":
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_load_error": str(exc)}


def _markdown_verdict(path: Path | None) -> str | None:
    if not path or path.suffix.lower() != ".md" or not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    for marker in ("Overall verdict:", "Latest super verdict:"):
        for line in text.splitlines():
            if marker not in line:
                continue
            upper = line.upper()
            for verdict in ("GREEN", "AMBER", "RED", "PASS", "FAIL"):
                if verdict in upper:
                    return verdict
    return None


def _file_size(path: Path | None) -> int | None:
    if not path or not path.exists():
        return None
    return path.stat().st_size


def _mtime_iso(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _verdict(data: dict[str, Any]) -> str | None:
    if not data:
        return None
    top_level_verdict = str(data.get("verdict") or data.get("status") or "").strip().upper()
    if top_level_verdict in {"FAIL", "INVALID", "CRASH"}:
        return "FAIL"
    verifier_validity = str(data.get("verifier_validity_status") or "").strip().upper()
    if verifier_validity == "INVALID":
        return "FAIL"
    one_click_status = str(data.get("one_click_contract_status") or "").strip().upper()
    if one_click_status and one_click_status != "PASS":
        return "FAIL"
    for key, value in data.items():
        if not str(key).lower().endswith("returncode"):
            continue
        try:
            if value is not None and int(value) != 0:
                return "FAIL"
        except (TypeError, ValueError):
            return "FAIL"
    summary = data.get("summary")
    if isinstance(summary, dict):
        fail_count = summary.get("FAIL_count")
        pass_count = summary.get("PASS_count")
        if fail_count is not None and pass_count is not None:
            try:
                return "PASS" if int(fail_count or 0) == 0 else "FAIL"
            except (TypeError, ValueError):
                pass
        real_gap = summary.get("real_optimiser_gap", summary.get("cases_where_this_is_a_real_optimiser_gap"))
        if real_gap is not None:
            try:
                return "PASS" if int(real_gap or 0) == 0 else "FAIL"
            except (TypeError, ValueError):
                pass
    for key in ("overall_verdict", "verdict", "status"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    if isinstance(summary, dict):
        for key in ("overall_verdict", "verdict", "status"):
            value = summary.get(key)
            if isinstance(value, str) and value:
                return value
        fail_count = summary.get("FAIL_count")
        if fail_count is not None:
            try:
                return "PASS" if int(fail_count or 0) == 0 else "FAIL"
            except (TypeError, ValueError):
                pass
    fail_count = data.get("fail_count")
    if fail_count is not None:
        try:
            return "PASS" if int(fail_count or 0) == 0 else "FAIL"
        except (TypeError, ValueError):
            pass
    return None


def _generated_at(data: dict[str, Any], path: Path | None) -> str | None:
    for key in ("generated_at", "timestamp", "run_started_at"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    summary = data.get("summary")
    if isinstance(summary, dict):
        value = summary.get("generated_at")
        if isinstance(value, str) and value:
            return value
    return _mtime_iso(path)


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _browser_live_state(data: dict[str, Any]) -> tuple[bool | None, bool | None]:
    modes: list[str] = []
    required_flags: list[bool] = []
    summary = data.get("summary")
    if isinstance(summary, dict) and summary.get("browser_mode_required") == "browser_live":
        required_flags.append(True)
    for item in _walk_dicts(data):
        if "browser_mode" in item:
            modes.append(str(item.get("browser_mode") or "missing"))
        if "requires_browser_live" in item:
            required_flags.append(bool(item.get("requires_browser_live")))
    if not modes and not required_flags:
        return None, None
    required = bool(required_flags) or "browser_live" in modes
    if not required:
        return False, None
    satisfied = bool(modes) and all(mode == "browser_live" for mode in modes)
    return required, satisfied


def _latest_super_reference() -> tuple[Path | None, dict[str, Any], set[str]]:
    super_summary = _latest(FAMILIES["latest_super_run_summary"])
    super_compat = _latest(FAMILIES["latest_super_artifact"])
    if super_summary and (not super_compat or super_summary.stat().st_mtime >= super_compat.stat().st_mtime):
        path = super_summary
    else:
        path = super_compat
    data = _load_json(path)
    refs: set[str] = set()
    for item in _walk_dicts(data):
        for key in ("artifact", "path", "child_artifact", "path_to_super_summary_json"):
            value = item.get(key)
            if isinstance(value, str) and value:
                refs.add(value.replace("\\", "/"))
        child_paths = item.get("child_artifact_paths")
        if isinstance(child_paths, dict):
            refs.update(str(v).replace("\\", "/") for v in child_paths.values() if v)
    return path, data, refs


def _parse_iso_timestamp(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _super_gate_statuses(data: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    by_name: dict[str, str] = {}
    by_artifact: dict[str, str] = {}
    for gate in data.get("gates") or []:
        if not isinstance(gate, dict):
            continue
        status = gate.get("status")
        name = gate.get("name")
        artifact = gate.get("artifact")
        if isinstance(name, str) and isinstance(status, str):
            by_name[name] = status
        if isinstance(artifact, str) and isinstance(status, str):
            by_artifact[artifact.replace("\\", "/")] = status
    return by_name, by_artifact


def build_manifest() -> dict[str, Any]:
    latest_super_path, latest_super_data, latest_super_refs = _latest_super_reference()
    latest_super_mtime = latest_super_path.stat().st_mtime if latest_super_path else None
    latest_super_started_at = _parse_iso_timestamp(latest_super_data.get("run_started_at"))
    super_status_by_name, super_status_by_artifact = _super_gate_statuses(latest_super_data)
    child_artifact_paths = dict(latest_super_data.get("child_artifact_paths") or {})
    artifacts: dict[str, Any] = {}

    for family, patterns in FAMILIES.items():
        gate_name = SUPER_GATE_BY_FAMILY.get(family)
        path = _path_from_reference(child_artifact_paths.get(gate_name)) if gate_name else None
        if path is None:
            path = _latest(patterns)
        if path is None and family == "latest_golden_ladder":
            for ref in sorted(latest_super_refs):
                if "full_golden_ladder" in ref:
                    candidate = Path(ref)
                    if candidate.exists():
                        path = candidate
                        break
        data = _load_json(path)
        rel = _relative(path)
        rel_norm = rel.replace("\\", "/") if rel else None
        browser_required, browser_satisfied = _browser_live_state(data)
        referenced = bool(rel_norm and rel_norm in latest_super_refs)
        verdict = _verdict(data) or _markdown_verdict(path)
        if rel_norm and rel_norm in super_status_by_artifact:
            verdict = super_status_by_artifact[rel_norm]
        if gate_name and gate_name in super_status_by_name and referenced:
            verdict = super_status_by_name[gate_name]
        stale = None
        if path and latest_super_mtime is not None:
            if latest_super_started_at is not None and path.stat().st_mtime >= latest_super_started_at:
                stale = False
            else:
                stale = path.stat().st_mtime < latest_super_mtime and not referenced and path != latest_super_path
        artifacts[family] = {
            "path": rel,
            "verdict": verdict,
            "generated_at": _generated_at(data, path),
            "size_bytes": _file_size(path),
            "browser_live_required": browser_required,
            "browser_live_satisfied": browser_satisfied,
            "referenced_by_latest_super": referenced or path == latest_super_path,
            "stale_compared_with_latest_super": stale,
            "load_error": data.get("_load_error"),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_super_reference": _relative(latest_super_path),
        "latest_super_verdict": _verdict(latest_super_data),
        "latest_super_safe_to_freeze": latest_super_data.get("safe_to_freeze"),
        "artifacts": artifacts,
    }


def write_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# Verification Latest Manifest",
        "",
        f"Generated: {manifest['generated_at']}",
        f"Latest super reference: `{manifest.get('latest_super_reference')}`",
        f"Latest super verdict: **{manifest.get('latest_super_verdict') or 'UNKNOWN'}**",
        f"Safe to freeze: **{'YES' if manifest.get('latest_super_safe_to_freeze') else 'NO'}**",
        "",
        "| Artifact | Verdict | Browser live | Stale vs latest super | Size | Path |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for family, info in manifest["artifacts"].items():
        required = info.get("browser_live_required")
        satisfied = info.get("browser_live_satisfied")
        if required is None:
            browser = "unknown"
        elif required is False:
            browser = "not required"
        else:
            browser = "yes" if satisfied else "NO"
        stale = info.get("stale_compared_with_latest_super")
        stale_txt = "unknown" if stale is None else "YES" if stale else "no"
        size = info.get("size_bytes")
        size_txt = "" if size is None else str(size)
        path = info.get("path") or ""
        lines.append(
            f"| {family} | {info.get('verdict') or 'UNKNOWN'} | {browser} | {stale_txt} | {size_txt} | `{path}` |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    manifest = build_manifest()
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    MANIFEST_MD.write_text(write_markdown(manifest), encoding="utf-8")
    print(f"Wrote {_relative(MANIFEST_JSON)}")
    print(f"Wrote {_relative(MANIFEST_MD)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
