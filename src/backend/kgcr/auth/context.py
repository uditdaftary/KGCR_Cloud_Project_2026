"""Security context and actor roles (FD-01 §3, FD-03 §9).

Defines pseudonymous user identities, session metadata, and actor roles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4

from kgcr.hashing import canonical_hash

__all__ = ["ActorRole", "SecurityContext"]


class ActorRole(StrEnum):
    """System actor roles (FD-01 §3, FD-08 §4.1)."""

    ARCHITECT = "architect"
    AUDITOR = "auditor"
    STUDENT = "student"
    AGENT2_HARVESTER = "agent2_harvester"
    AGENT1_PROVISIONER = "agent1_provisioner"


@dataclass(frozen=True)
class SecurityContext:
    """Immutable security context for pipeline execution (FD-03 §9).

    ``user_id`` is pseudonymous. If a plain user identity is supplied, it is hashed
    to ensure personal data is not written directly to run records.
    """

    user_ref: str
    role: ActorRole = ActorRole.ARCHITECT
    session_id: str = field(default_factory=lambda: str(uuid4()))
    account_id: str | None = None

    @property
    def pseudonymous_id(self) -> str:
        """Deterministic pseudonymous hash of the user reference (FD-03 §9)."""
        return canonical_hash({"user_ref": self.user_ref})[:16]

    def to_dict(self) -> dict[str, str]:
        return {
            "pseudonymous_id": self.pseudonymous_id,
            "role": self.role.value,
            "session_id": self.session_id,
            "account_id": self.account_id or "",
        }

    @classmethod
    def create_default(
        cls,
        user_ref: str = "default_architect",
        role: ActorRole = ActorRole.ARCHITECT,
        account_id: str | None = None,
    ) -> SecurityContext:
        return cls(user_ref=user_ref, role=role, account_id=account_id)
