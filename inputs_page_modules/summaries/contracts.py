from __future__ import annotations

CARD_ORDER: tuple[str, ...] = ("bending", "shear", "crack", "deflection")

ALLOWED_CARD_IDENTIFIERS: frozenset[str] = frozenset(CARD_ORDER)

REQUIRED_CARD_FIELDS: tuple[str, ...] = (
    "check_id",
    "title",
    "applied_label",
    "applied_value",
    "capacity_label",
    "capacity_value",
    "utilisation",
    "status",
    "tone",
    "expanded_rows",
    "visible_text",
    "html_hash",
    "display_hash",
)

ALLOWED_STATUS_VALUES: frozenset[str] = frozenset(
    {
        "PASS",
        "OK",
        "FAIL",
        "NG",
        "WARN",
        "WARNING",
        "NEAR LIMIT",
        "CHECK",
        "CAPACITY",
        "REQUIRES ACTION",
        "ACTION REQUIRED",
        "NOT RUN",
        "INPUT REQUIRED",
        "INFO",
        "",
    }
)

ALLOWED_TONES: frozenset[str] = frozenset(
    {
        "pass",
        "fail",
        "warn",
        "capacity",
        "requires-action",
        "neutral",
        "info",
    }
)

DISPLAY_HASH_FIELDS: tuple[str, ...] = REQUIRED_CARD_FIELDS[:-1]

MISSING_ACTION_BEHAVIOUR = (
    "Existing summary adapter converts zero or missing non-deflection action "
    "rows with passing/capacity-like status into capacity/not-run display and "
    "uses dash utilisation."
)

NOT_RUN_BEHAVIOUR = (
    "Existing deflection summary displays NOT RUN with calculated deflection "
    "and design limit fields, preserving dash utilisation."
)

NO_ENGINEERING_RECALCULATION = (
    "Summary builders consume authoritative row/card values only; they do not "
    "recompute bending, shear, crack-control, or deflection engineering truth."
)
