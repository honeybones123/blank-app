"""Compatibility exports for the application-owned audited fingerprint set."""

from inputs_application.local_cleanup_acceptance import (
    AuditedFingerprintSet,
    DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS,
)

__all__ = ["AuditedFingerprintSet", "DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS"]
