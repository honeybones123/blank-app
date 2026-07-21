from __future__ import annotations

from typing import Any


DEFAULT_FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except Exception:
        return None
    if parsed != parsed:
        return None
    return parsed


def _normalised_family_set(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(k or "").strip().lower() for k, v in value.items() if str(k or "").strip() and v}
    if isinstance(value, (list, tuple, set)):
        return {str(item or "").strip().lower() for item in value if str(item or "").strip()}
    text = str(value or "").strip().lower()
    return {text} if text else set()


def _blocker_families(debug: dict[str, Any], *, post_click: bool = False) -> set[str]:
    families: set[str] = set()
    keys = (
        (
            "post_click_exact_blockers_by_family",
            "post_click_cleanup_evidence_by_family",
        )
        if post_click
        else (
            "exact_blockers_by_family",
            "local_cleanup_blocked_reasons_by_family",
            "blocked_reasons_by_family",
            "cleanup_evidence_by_family",
        )
    )
    for key in keys:
        raw = debug.get(key)
        if isinstance(raw, dict):
            for family, detail in raw.items():
                if isinstance(detail, dict) and detail:
                    families.add(str(family or "").strip().lower())
                elif isinstance(detail, str) and detail.strip():
                    families.add(str(family or "").strip().lower())
    if not post_click:
        for key in ("local_cleanup_blocked_reasons", "blocked_reasons"):
            raw = debug.get(key)
            if isinstance(raw, (list, tuple)):
                for item in raw:
                    if isinstance(item, dict):
                        families |= _normalised_family_set(item.get("family") or item.get("blocked_family"))
    return {family for family in families if family}


def _blockers_by_family(debug: dict[str, Any], *, post_click: bool = False) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    keys = (
        (
            "post_click_exact_blockers_by_family",
            "post_click_cleanup_evidence_by_family",
        )
        if post_click
        else (
            "exact_blockers_by_family",
            "local_cleanup_blocked_reasons_by_family",
            "blocked_reasons_by_family",
            "cleanup_evidence_by_family",
        )
    )
    for key in keys:
        raw = debug.get(key)
        if not isinstance(raw, dict):
            continue
        for family, detail in raw.items():
            fam = str(family or "").strip().lower()
            if not fam:
                continue
            if isinstance(detail, dict):
                out.setdefault(fam, {}).update(dict(detail))
            elif isinstance(detail, str) and detail.strip():
                out.setdefault(fam, {})["reason"] = detail
    evidence = debug.get("candidate_search_evidence")
    if isinstance(evidence, dict):
        evidence_keys = (
            (
                "post_click_exact_blockers_by_family",
                "post_click_cleanup_evidence_by_family",
            )
            if post_click
            else (
                "exact_blockers_by_family",
                "cleanup_evidence_by_family",
                "post_click_exact_blockers_by_family",
                "post_click_cleanup_evidence_by_family",
            )
        )
        for key in evidence_keys:
            raw = evidence.get(key)
            if not isinstance(raw, dict):
                continue
            for family, detail in raw.items():
                fam = str(family or "").strip().lower()
                if not fam:
                    continue
                if isinstance(detail, dict):
                    out.setdefault(fam, {}).update(dict(detail))
                elif isinstance(detail, str) and detail.strip():
                    out.setdefault(fam, {})["reason"] = detail
    proof_key = "visible_card_proofs_after" if post_click else "visible_card_proofs_before"
    text_key = "design_guide_visible_text_after" if post_click else "design_guide_visible_text_before"
    for proof in list(debug.get(proof_key) or []):
        if not isinstance(proof, dict):
            continue
        exact_families = [
            value.strip().lower()
            for value in str(proof.get("exactBlockerFamilies") or "").split(",")
            if value.strip()
        ]
        if not exact_families:
            continue
        target_blocked = str(proof.get("targetBandContractBlocked") or "").strip().lower() in {"1", "true", "yes", "y"}
        search_ran = str(proof.get("localCleanupSearchRan") or "").strip().lower() in {"1", "true", "yes", "y"}
        search_exhaustive = str(proof.get("localCleanupSearchExhaustive") or "").strip().lower() in {"1", "true", "yes", "y"}
        safe_count = _float_or_none(proof.get("safeLocalCleanupCount"))
        executable_count = _float_or_none(proof.get("executableSafeCleanupCount"))
        reason = str(debug.get(text_key) or debug.get("design_guide_visible_text") or "").strip()
        for fam in exact_families:
            detail = out.setdefault(fam, {})
            detail.setdefault("reason", reason)
            detail["target_band_contract_blocked"] = target_blocked
            detail["local_cleanup_search_ran"] = search_ran
            detail["local_cleanup_search_exhaustive"] = search_exhaustive
            detail["safe_cleanup_count"] = safe_count
            detail["executable_cleanup_count"] = executable_count
            if fam == "bending":
                detail["bending_cleanup_search_ran"] = search_ran
                detail["bending_cleanup_search_exhaustive"] = search_exhaustive
                detail["safe_bending_cleanup_count"] = safe_count
                detail["executable_bending_cleanup_count"] = executable_count
    return out


def _blocker_text(blocker: dict[str, Any]) -> str:
    return " ".join(
        str(blocker.get(key) or "")
        for key in (
            "best_rejected_candidate_id",
            "failed_check_name",
            "failed_check_status",
            "why_reduction_would_hurt_other_design_elements",
            "reason_reducing_this_family_would_affect_other_design_elements",
            "reason",
        )
    ).strip().lower()


def _is_synthetic_bending_low_util_blocker(blocker: dict[str, Any]) -> bool:
    text = _blocker_text(blocker)
    return bool(
        "bending_cleanup_floor_shear_or_detailing_limited" in text
        or "further bending cleanup is blocked" in text
        or "safe local floor" in text
    )


def _family_cleanup_search_proof_valid(
    family: str,
    blocker: dict[str, Any],
    debug: dict[str, Any],
    *,
    post_click: bool = False,
) -> bool:
    if family != "bending":
        return True
    sources = [blocker, debug]
    prefix = "post_click_" if post_click else ""

    def _first_bool(*keys: str) -> bool:
        for source in sources:
            for key in keys:
                if source.get(key) is True:
                    return True
        return False

    def _first_number(*keys: str) -> float | None:
        for source in sources:
            for key in keys:
                parsed = _float_or_none(source.get(key))
                if parsed is not None:
                    return parsed
        return None

    ran = _first_bool(
        f"{prefix}bending_cleanup_search_ran",
        "bending_cleanup_search_ran",
    )
    exhaustive = _first_bool(
        f"{prefix}bending_cleanup_search_exhaustive",
        "bending_cleanup_search_exhaustive",
    )
    safe_count = _first_number(
        f"{prefix}safe_bending_cleanup_count",
        "safe_bending_cleanup_count",
    )
    executable_count = _first_number(
        f"{prefix}executable_bending_cleanup_count",
        "executable_bending_cleanup_count",
    )
    if safe_count is None or executable_count is None:
        return False
    if safe_count != 0 or executable_count != 0:
        return False
    if not ran or not exhaustive:
        return False
    text = _blocker_text(blocker)
    if not text:
        return False
    invalid = (
        "best candidate still outside target",
        "staged fix required",
        "candidate_preview_not_in_target_band_after_active_failure",
        "no safe cleanup found",
        "candidate failed",
        "engineering constraint",
    )
    return not any(token in text for token in invalid)


def _terminal_or_accepted(debug: dict[str, Any]) -> bool:
    title = " ".join(
        str(debug.get(key) or "")
        for key in (
            "selected_action_title",
            "post_click_design_guide_title",
            "visible_card_title",
            "visible_text",
            "design_guide_visible_text",
            "primary_title",
            "title",
        )
    ).lower()
    state = str(debug.get("post_click_design_guide_state") or debug.get("design_guide_state") or "").strip().lower()
    if debug.get("post_click_accepted_green") is True or debug.get("accepted_green") is True:
        return True
    if state in {"accepted_green", "terminal", "optimal", "already_efficient"}:
        return True
    return any(token in title for token in ("target band achieved", "design is efficient", "design accepted"))


def _post_click_terminal_or_accepted(debug: dict[str, Any]) -> bool:
    title = " ".join(
        str(debug.get(key) or "")
        for key in (
            "post_click_design_guide_title",
            "post_click_visible_card_title",
            "post_click_primary_title",
        )
    ).lower()
    state = str(debug.get("post_click_design_guide_state") or "").strip().lower()
    if debug.get("post_click_accepted_green") is True:
        return True
    if state in {"accepted_green", "terminal", "optimal", "already_efficient"}:
        return True
    return any(token in title for token in ("target band achieved", "design is efficient", "design accepted"))


def _family_utils(debug: dict[str, Any], *, post_click: bool = False) -> dict[str, float]:
    raw = (
        (
            debug.get("post_click_family_utils_meaningful")
            or debug.get("post_click_family_utils")
            or {}
        )
        if post_click
        else (
            debug.get("family_utils_meaningful")
            or debug.get("family_utils")
            or {}
        )
    )
    out: dict[str, float] = {}
    if isinstance(raw, dict):
        for family, value in raw.items():
            parsed = _float_or_none(value)
            key = str(family or "").strip().lower()
            if key and parsed is not None:
                out[key] = parsed
    return out


def _merge_truthy(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if value not in (None, "", [], {}):
            target[key] = value


def overdesign_debug_from_browser_state(
    state: dict[str, Any] | None,
    *,
    primary: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the compact verifier audit view from a browser state probe.

    Browser ladders expose the same Design Guide truth through a few different
    probe bundles. This helper intentionally reads only stamped proof fields; it
    does not infer solver behaviour or manufacture cleanup evidence.
    """
    raw = dict(state or {})
    guidance = dict(raw.get("guidance_compute_probe") or {})
    design_probe = dict(raw.get("design_guide_probe") or {})
    post_cleanup = dict(raw.get("post_cleanup_acceptance_probe") or {})
    overview = dict(raw.get("summary_overview_probe") or {})
    primary = dict(primary or {})
    summary = dict(summary or {})
    debug_bundle = dict(design_probe.get("debug_bundle") or {})

    debug: dict[str, Any] = {
        "selected_action_title": primary.get("selected_title") or primary.get("title") or guidance.get("selected_title"),
        "primary_title": guidance.get("primary_title") or primary.get("title"),
        "visible_text": primary.get("visible_text"),
        "design_guide_state": guidance.get("primary_terminal_state") or primary.get("terminal_state"),
        "family_utils": overview.get("utils") or summary.get("utils"),
        "final_accepted_min_family_util": guidance.get("final_accepted_min_family_util"),
    }
    for source in (debug_bundle, guidance, design_probe, post_cleanup):
        if isinstance(source, dict):
            _merge_truthy(debug, source)
    return debug


def assert_no_unresolved_material_overdesign(
    case_id: str,
    debug: dict[str, Any],
    *,
    fail_reasons: list[str] | None = None,
) -> list[str]:
    """Append failures when terminal accepted state hides unresolved low-util families.

    This is intentionally verifier-only. It does not decide candidate ranking; it checks
    that any terminal/accepted-green proof includes the cleanup evidence needed to
    explain controllable families below the final acceptance threshold.
    """
    failures = fail_reasons if fail_reasons is not None else []
    if not isinstance(debug, dict) or not _terminal_or_accepted(debug):
        return failures

    threshold = _float_or_none(debug.get("final_accepted_min_family_util"))
    if threshold is None:
        threshold = DEFAULT_FINAL_ACCEPTED_MIN_FAMILY_UTIL

    post_click = _post_click_terminal_or_accepted(debug)
    utils = _family_utils(debug, post_click=post_click)
    if post_click:
        explicit_low = (
            _normalised_family_set(debug.get("post_click_unresolved_low_util_families"))
            | _normalised_family_set(debug.get("post_click_unresolved_overprovided_families"))
        )
        explicit_material = (
            _normalised_family_set(debug.get("post_click_materially_overprovided_families"))
            | _normalised_family_set(debug.get("post_click_families_below_final_threshold"))
        )
    else:
        explicit_low = _normalised_family_set(debug.get("unresolved_low_util_families"))
        explicit_material = (
            _normalised_family_set(debug.get("materially_overprovided_families"))
            | _normalised_family_set(debug.get("families_below_final_threshold"))
        )

    low_families: set[str] = set(explicit_low | explicit_material)
    if not low_families and utils:
        for family, util in utils.items():
            if family in {"crack", "deflection", "serviceability", "geometry"}:
                continue
            # Treat zero-util families as controllable only when the app has explicitly
            # stamped them as material/overprovided; otherwise they may be zero demand.
            if util > 0.0 and util < float(threshold):
                low_families.add(family)

    excluded = set()
    excluded_raw = (
        debug.get("post_click_excluded_families")
        if post_click
        else debug.get("excluded_families")
    ) or {}
    if isinstance(excluded_raw, dict):
        excluded = {str(family or "").strip().lower() for family in excluded_raw}
    low_families = {family for family in low_families if family and family not in excluded}
    if not low_families:
        return failures

    if post_click:
        cleanup_ran = debug.get("post_click_local_cleanup_search_ran") is True
        cleanup_exhaustive = debug.get("post_click_local_cleanup_search_exhaustive") is True
        safe_count = _float_or_none(debug.get("post_click_safe_local_cleanup_count"))
        executable_count = _float_or_none(debug.get("post_click_executable_safe_cleanup_count"))
    else:
        cleanup_ran = debug.get("local_cleanup_search_ran") is True
        cleanup_exhaustive = debug.get("local_cleanup_search_exhaustive") is True
        safe_count = _float_or_none(debug.get("safe_local_cleanup_count"))
        executable_count = _float_or_none(debug.get("executable_safe_cleanup_count"))
    if safe_count is None:
        safe_count = 0.0
    if executable_count is None:
        executable_count = 0.0
    blockers = _blocker_families(debug, post_click=post_click)
    blocker_details = _blockers_by_family(debug, post_click=post_click)

    for family in sorted(low_families):
        util = utils.get(family)
        util_text = "unknown" if util is None else f"{util:.3g}"
        missing = []
        has_family_blocker = family in blockers
        family_blocker = dict(blocker_details.get(family) or {})
        if family == "bending" and has_family_blocker:
            if _is_synthetic_bending_low_util_blocker(family_blocker):
                missing.append("synthetic_bending_low_util_blocker")
            if not _family_cleanup_search_proof_valid(family, family_blocker, debug, post_click=post_click):
                missing.append("bending_cleanup_exhaustive_proof_missing")
        if not cleanup_ran and not has_family_blocker:
            missing.append("cleanup_search_not_run")
        if not cleanup_exhaustive and not has_family_blocker:
            missing.append("cleanup_search_not_exhaustive")
        if safe_count > 0 or executable_count > 0:
            missing.append(f"safe_cleanup_count_nonzero:{safe_count:g}/{executable_count:g}")
        if not has_family_blocker:
            missing.append("missing_exact_blocker")
        if missing:
            failures.append(
                "Unresolved material overdesign accepted: "
                f"{family} util={util_text}, terminal green shown, "
                f"but no exhaustive cleanup/blocker evidence ({';'.join(missing)})."
            )
    return failures


def _visible_summary_family_utils(case: dict[str, Any], *, post_click: bool) -> dict[str, float]:
    summary_key = "visible_summary_after" if post_click else "visible_summary_before"
    summary = dict(case.get(summary_key) or case.get("visible_summary") or {})
    out: dict[str, float] = {}
    for family in ("bending", "shear"):
        row = dict(summary.get(family) or {})
        util = _float_or_none(row.get("util"))
        status = str(row.get("status") or "").strip().upper()
        # The visible strength rows are meaningful when they carry a parsed
        # utilisation and a real status. Zero-demand SLS placeholders are not
        # represented here.
        if util is not None and status in {"PASS", "FAIL", "NEAR LIMIT", "INFO"}:
            out[family] = util
    return out


def _visible_design_guide_text(case: dict[str, Any], *, post_click: bool) -> str:
    if post_click:
        return str(case.get("design_guide_visible_text_after") or "")
    return str(case.get("design_guide_visible_text_before") or case.get("design_guide_visible_text") or "")


def _looks_terminal_or_accepted_text(text: str) -> bool:
    lower = str(text or "").lower()
    return any(
        token in lower
        for token in (
            "design accepted",
            "target band achieved",
            "design is efficient",
            "within the target utilisation band",
            "within target band",
        )
    )


def _looks_like_visible_action(text: str) -> bool:
    lower = str(text or "").lower()
    return any(token in lower for token in ("change:", "expected util", "preview utilisation", "run one-click"))


def _looks_like_visible_blocker(text: str) -> bool:
    lower = str(text or "").lower()
    return any(
        token in lower
        for token in (
            "no one-click",
            "cannot",
            "blocked",
            "would fail",
            "preview did not pass",
            "spacing",
            "ductility",
            "detailing",
            "minimum reinforcement",
            "minimum shear",
            "geometry locked",
            "limit reached",
        )
    )


def _has_forbidden_unresolved_wording(text: str) -> bool:
    lower = str(text or "").lower()
    return any(
        token in lower
        for token in (
            "proof unresolved",
            "unresolved",
            "advisory",
            "optional cleanup",
            "proof-budget",
            "proof budget",
            "did not finish",
            "budget exhausted",
        )
    )


def _button_contract(case: dict[str, Any], *, post_click: bool = False) -> dict[str, Any]:
    if post_click:
        guidance = case.get("guidance_compute_probe_after")
        if isinstance(guidance, dict):
            for key in ("button_contract", "primary_button_contract"):
                contract = guidance.get(key)
                if isinstance(contract, dict):
                    return dict(contract)
    contract = case.get("button_contract")
    return dict(contract) if isinstance(contract, dict) else {}


def _selected_updates(case: dict[str, Any]) -> dict[str, Any]:
    for key in ("selected_action_updates", "selected_updates", "button_contract_updates", "visible_updates"):
        value = case.get(key)
        if isinstance(value, dict) and value:
            return dict(value)
    contract = _button_contract(case)
    return dict(contract.get("updates") or {})


def _exact_blocker_valid_for_visible_contract(
    family: str,
    case: dict[str, Any],
    *,
    post_click: bool,
) -> bool:
    blockers = _blockers_by_family(case, post_click=post_click)
    blocker = dict(blockers.get(family) or {})
    if not blocker:
        return False
    if family == "bending":
        if _is_synthetic_bending_low_util_blocker(blocker):
            return False
        return _family_cleanup_search_proof_valid(family, blocker, case, post_click=post_click)
    text = _blocker_text(blocker)
    return bool(text) and "no safe cleanup found" not in text and "engineering constraint" not in text


def _visible_blocker_has_structured_evidence(
    case: dict[str, Any],
    *,
    post_click: bool,
) -> bool:
    blockers = _blockers_by_family(case, post_click=post_click)
    if not blockers:
        return False
    for family, blocker in blockers.items():
        fam = str(family or "").strip().lower()
        repair_ran = (
            blocker.get("repair_search_ran") is True
            or blocker.get("active_fail_repair_search_ran") is True
            or blocker.get("bending_fail_contract_ladder_attempted") is True
        )
        repair_exhaustive = (
            blocker.get("repair_search_exhaustive") is True
            or blocker.get("active_fail_repair_search_exhaustive") is True
            or blocker.get("candidate_search_exhaustive") is True
        )
        safe_repair_count = _float_or_none(
            blocker.get("safe_repair_candidate_count")
            if blocker.get("safe_repair_candidate_count") is not None
            else blocker.get("safe_candidate_count")
        )
        executable_repair_count = _float_or_none(
            blocker.get("executable_repair_candidate_count")
            if blocker.get("executable_repair_candidate_count") is not None
            else blocker.get("executable_candidate_count")
        )
        active_repair_blocker_valid = bool(
            repair_ran
            and repair_exhaustive
            and safe_repair_count == 0
            and executable_repair_count == 0
        )
        if fam == "bending":
            if (
                not active_repair_blocker_valid
                and not _family_cleanup_search_proof_valid(fam, blocker, case, post_click=post_click)
            ):
                continue
        text = _blocker_text(blocker)
        if not text:
            continue
        cleanup_ran = (
            blocker.get("post_click_bending_cleanup_search_ran") is True
            or blocker.get("bending_cleanup_search_ran") is True
            or blocker.get("local_cleanup_search_ran") is True
            or case.get("post_click_local_cleanup_search_ran") is True
            or case.get("local_cleanup_search_ran") is True
        )
        cleanup_exhaustive = (
            blocker.get("post_click_bending_cleanup_search_exhaustive") is True
            or blocker.get("bending_cleanup_search_exhaustive") is True
            or blocker.get("local_cleanup_search_exhaustive") is True
            or case.get("post_click_local_cleanup_search_exhaustive") is True
            or case.get("local_cleanup_search_exhaustive") is True
        )
        safe_count = _float_or_none(
            blocker.get("post_click_safe_bending_cleanup_count")
            if fam == "bending"
            else blocker.get(f"post_click_safe_{fam}_cleanup_count")
            if blocker.get(f"post_click_safe_{fam}_cleanup_count") is not None
            else blocker.get("post_click_safe_cleanup_count")
        )
        if safe_count is None:
            safe_count = _float_or_none(
                blocker.get("safe_bending_cleanup_count" if fam == "bending" else f"safe_{fam}_cleanup_count")
            )
        if safe_count is None and fam != "bending":
            safe_count = _float_or_none(blocker.get("safe_cleanup_count"))
        if safe_count is None:
            safe_count = _float_or_none(case.get("post_click_safe_local_cleanup_count" if post_click else "safe_local_cleanup_count"))
        executable_count = _float_or_none(
            blocker.get("post_click_executable_bending_cleanup_count")
            if fam == "bending"
            else blocker.get(f"post_click_executable_{fam}_cleanup_count")
            if blocker.get(f"post_click_executable_{fam}_cleanup_count") is not None
            else blocker.get("post_click_executable_cleanup_count")
        )
        if executable_count is None:
            executable_count = _float_or_none(
                blocker.get(
                    "executable_bending_cleanup_count"
                    if fam == "bending"
                    else f"executable_{fam}_cleanup_count"
                )
            )
        if executable_count is None and fam != "bending":
            executable_count = _float_or_none(blocker.get("executable_cleanup_count"))
        if executable_count is None:
            executable_count = _float_or_none(
                case.get("post_click_executable_safe_cleanup_count" if post_click else "executable_safe_cleanup_count")
            )
        target_band_count = _float_or_none(
            blocker.get("executable_target_band_candidate_count")
            if blocker.get("executable_target_band_candidate_count") is not None
            else blocker.get("accepted_band_candidate_count")
        )
        if target_band_count is None:
            target_band_count = _float_or_none(
                case.get(
                    "post_click_executable_target_band_candidate_count"
                    if post_click
                    else "executable_target_band_candidate_count"
                )
            )
        target_band_blocker_valid = bool(
            cleanup_ran
            and cleanup_exhaustive
            and target_band_count == 0
            and (
                blocker.get("failed_check_status") is not None
                or blocker.get("failed_check_name") is not None
                or blocker.get("reason") is not None
            )
        )
        if cleanup_ran and cleanup_exhaustive and safe_count == 0 and executable_count == 0:
            return True
        if target_band_blocker_valid:
            return True
        if active_repair_blocker_valid:
            return True
    return False


def assert_visible_output_matches_one_click_contract(
    case_id: str,
    case: dict[str, Any],
    *,
    fail_reasons: list[str] | None = None,
) -> list[str]:
    """Validate the rendered browser output against the one-click/blocker/terminal contract.

    This assertion deliberately compares visible DOM-derived text and summary
    utilisations with hidden proof fields. A hidden accepted flag is not enough
    when the visible summary still shows a controllable family below the final
    accepted threshold.
    """
    failures = fail_reasons if fail_reasons is not None else []
    if not isinstance(case, dict):
        return failures

    threshold = _float_or_none(case.get("final_accepted_min_family_util"))
    if threshold is None:
        threshold = DEFAULT_FINAL_ACCEPTED_MIN_FAMILY_UTIL

    clicked = bool(case.get("click_attempted"))
    stages = [False, True] if clicked else [False]
    for post_click in stages:
        text = _visible_design_guide_text(case, post_click=post_click)
        if not text:
            continue
        stage_name = "post_click" if post_click else "pre_click"
        card_count = case.get("visible_card_count_after" if post_click else "visible_card_count_before")
        if card_count is not None and int(card_count or 0) != 1:
            failures.append(f"{stage_name}_visible_contract_card_count_not_one:{card_count}")

        cta_visible = bool(case.get("one_click_button_visible_after" if post_click else "one_click_button_visible_before"))
        cta_enabled = bool(case.get("one_click_button_enabled_after" if post_click else "one_click_button_enabled_before"))
        terminal = _looks_terminal_or_accepted_text(text)
        visible_action = _looks_like_visible_action(text)
        visible_blocker = _looks_like_visible_blocker(text)
        forbidden_unresolved = _has_forbidden_unresolved_wording(text)

        if forbidden_unresolved:
            failures.append(f"{stage_name}_visible_contract_unresolved_or_advisory_wording")

        if visible_action and not post_click and not cta_enabled:
            failures.append(f"{stage_name}_visible_action_without_enabled_cta")

        contract = _button_contract(case, post_click=post_click)
        executable_payload_exists = bool(
            contract.get("actionable") is True
            and dict(contract.get("updates") or {})
            and contract.get("preview_pass") is True
            and contract.get("blocking_reason") in (None, "")
        )
        if visible_blocker and not cta_enabled and executable_payload_exists:
            failures.append(f"{stage_name}_visible_blocker_but_executor_backed_payload_exists")
        if visible_blocker and not cta_enabled and not _visible_blocker_has_structured_evidence(case, post_click=post_click):
            failures.append(f"{stage_name}_visible_blocker_missing_structured_evidence")

        if cta_enabled and not executable_payload_exists and not post_click:
            failures.append(f"{stage_name}_enabled_cta_without_executor_backed_payload")

        if terminal:
            if cta_visible or cta_enabled:
                failures.append(f"{stage_name}_terminal_visible_with_cta:visible={cta_visible}:enabled={cta_enabled}")
            visible_utils = _visible_summary_family_utils(case, post_click=post_click)
            hidden_utils = _family_utils(case, post_click=post_click)
            merged_utils = dict(hidden_utils)
            merged_utils.update(visible_utils)
            for family, util in sorted(merged_utils.items()):
                if family not in {"bending", "shear"}:
                    continue
                if util <= 0.0 or util >= float(threshold):
                    continue
                if not _exact_blocker_valid_for_visible_contract(family, case, post_click=post_click):
                    visible_util = visible_utils.get(family, util)
                    failures.append(
                        "Visible accepted state invalid: "
                        f"{family} util={visible_util:.2f} is below final threshold, "
                        "but visible Design Guide says target band achieved without exact "
                        f"{family} cleanup/blocker proof."
                    )
            if post_click and case.get("post_click_accepted_green_valid") is True:
                unresolved = _normalised_family_set(case.get("post_click_unresolved_low_util_families"))
                if unresolved:
                    failures.append(
                        f"post_click_hidden_valid_contradicts_unresolved_visible_contract:{sorted(unresolved)}"
                    )

    if bool(case.get("click_attempted")):
        if case.get("payload_binding_match") is False:
            failures.append("post_click_visible_contract_payload_binding_mismatch")
        if case.get("payload_update_match") is False:
            failures.append("post_click_visible_contract_payload_update_mismatch")
        if bool(case.get("one_click_button_enabled_after")):
            failures.append("post_click_visible_contract_second_cta_enabled")

    return failures
