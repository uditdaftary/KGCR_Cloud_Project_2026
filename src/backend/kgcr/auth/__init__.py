"""Authentication, Security Context, and Access Policy Subsystem (FD-01, FD-02, FD-04, FD-08).

Implements pseudonymous user context, role-based access control, waiver governance,
and enforcement of system invariants INV-5 and INV-7.
"""

from kgcr.auth.context import ActorRole, SecurityContext
from kgcr.auth.policy import AccessPolicy, WaiverPolicy

__all__ = [
    "AccessPolicy",
    "ActorRole",
    "SecurityContext",
    "WaiverPolicy",
]
