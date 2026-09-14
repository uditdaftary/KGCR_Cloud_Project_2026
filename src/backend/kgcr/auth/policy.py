"""Access policies, invariant enforcement, and waiver governance (FD-01, FD-02, FD-04, FD-08).

Enforces system invariants INV-5 (read/write role split) and INV-7 (advisor isolation),
as well as strict waiver governance rules.
"""

from __future__ import annotations

from typing import Any

from kgcr.auth.context import ActorRole, SecurityContext

__all__ = ["AccessPolicy", "WaiverPolicy"]

# Action prefixes that represent write operations
_WRITE_ACTIONS = {"create", "put", "delete", "apply", "update", "patch", "destroy"}


class AccessPolicy:
    """Enforces role-based permissions and structural invariant boundaries."""

    @staticmethod
    def enforce_inv5_read(ctx: SecurityContext, action: str) -> None:
        """Enforce INV-5: Harvester (Agent 2) holds strictly read-only capabilities (FD-08 §4.1).

        Raises PermissionError if a write action is attempted under Agent 2 context.
        """
        action_lower = action.lower()
        if ctx.role == ActorRole.AGENT2_HARVESTER:
            if any(action_lower.startswith(w) for w in _WRITE_ACTIONS):
                raise PermissionError(
                    f"INV-5 Violation: Harvester role '{ctx.role}' is read-only "
                    f"and cannot perform write action '{action}'."
                )

    @staticmethod
    def enforce_inv5_write(ctx: SecurityContext, action: str) -> None:
        """Enforce INV-5: Provisioner (Agent 1) is sole writer (FD-08 §4.1).

        Raises PermissionError if a write action is attempted by a non-provisioner role.
        """
        action_lower = action.lower()
        is_write = any(action_lower.startswith(w) for w in _WRITE_ACTIONS)
        if is_write and ctx.role != ActorRole.AGENT1_PROVISIONER:
            raise PermissionError(
                f"INV-5 Violation: Action '{action}' requires Agent 1 Provisioner role, "
                f"but current role is '{ctx.role}'."
            )

    @staticmethod
    def enforce_inv7_advisor_isolation(candidate_spec: dict[str, Any]) -> dict[str, Any]:
        """Enforce INV-7: Strip recommender scores/rationale before Advisor review (FD-04 §3).

        The Advisor sees only the candidate spec artifact and declared intent.
        """
        isolated = dict(candidate_spec)
        # Forbidden keys associated with recommender rationale
        for forbidden in (
            "recommender_scores",
            "recommender_rationale",
            "candidate_rankings",
            "confidence_scores",
            "model_trace",
        ):
            isolated.pop(forbidden, None)
        return isolated


class WaiverPolicy:
    """Governs finding waiver decisions according to FD-02 §7."""

    @staticmethod
    def can_waive(severity: str) -> bool:
        """Determine whether a finding of the given severity may be waived.

        Per FD-02 §7: CRITICAL findings CANNOT be waived under any flag.
        """
        return severity.upper() != "CRITICAL"

    @staticmethod
    def validate_waiver(severity: str, justification: str) -> None:
        """Validate a waiver request.

        Raises ValueError if attempting to waive a CRITICAL finding or if justification is missing.
        """
        sev_upper = severity.upper()
        if sev_upper == "CRITICAL":
            raise ValueError(
                "FD-02 §7 Rule: CRITICAL findings violate mandatory regulatory controls "
                "and CANNOT be waived under any flag."
            )

        if not justification or not justification.strip():
            raise ValueError("Waiver requires a non-empty, recorded justification.")
