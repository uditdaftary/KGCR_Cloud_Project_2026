"""Tests for kgcr.auth (FD-01, FD-02, FD-04, FD-08)."""

from __future__ import annotations

import pytest

from kgcr.auth import AccessPolicy, ActorRole, SecurityContext, WaiverPolicy


def test_security_context_pseudonymisation() -> None:
    ctx1 = SecurityContext(user_ref="manya_student2", role=ActorRole.ARCHITECT)
    ctx2 = SecurityContext(user_ref="manya_student2", role=ActorRole.AUDITOR)

    # Same user_ref produces identical pseudonymous_id
    assert ctx1.pseudonymous_id == ctx2.pseudonymous_id
    assert len(ctx1.pseudonymous_id) == 16
    assert ctx1.pseudonymous_id != "manya_student2"

    payload = ctx1.to_dict()
    assert payload["role"] == "architect"
    assert "pseudonymous_id" in payload


def test_inv5_harvester_read_only() -> None:
    ctx = SecurityContext(user_ref="agent2", role=ActorRole.AGENT2_HARVESTER)

    # Read operations pass
    AccessPolicy.enforce_inv5_read(ctx, "get_config")
    AccessPolicy.enforce_inv5_read(ctx, "describe_instances")

    # Write operations raise PermissionError
    with pytest.raises(PermissionError, match="INV-5 Violation"):
        AccessPolicy.enforce_inv5_read(ctx, "apply_changes")

    with pytest.raises(PermissionError, match="INV-5 Violation"):
        AccessPolicy.enforce_inv5_read(ctx, "create_bucket")


def test_inv5_provisioner_write() -> None:
    architect_ctx = SecurityContext(user_ref="arch", role=ActorRole.ARCHITECT)
    provisioner_ctx = SecurityContext(user_ref="agent1", role=ActorRole.AGENT1_PROVISIONER)

    # Non-provisioner role blocked on write
    with pytest.raises(PermissionError, match="requires Agent 1 Provisioner role"):
        AccessPolicy.enforce_inv5_write(architect_ctx, "apply_plan")

    # Provisioner allowed write
    AccessPolicy.enforce_inv5_write(provisioner_ctx, "apply_plan")


def test_inv7_advisor_isolation() -> None:
    raw_spec = {
        "compute": {"instance_type": "m6i.xlarge"},
        "recommender_scores": [0.95, 0.88],
        "recommender_rationale": "High TPS workload preference",
        "candidate_rankings": {"top_1": "option_a"},
    }

    isolated = AccessPolicy.enforce_inv7_advisor_isolation(raw_spec)

    assert "compute" in isolated
    assert "recommender_scores" not in isolated
    assert "recommender_rationale" not in isolated
    assert "candidate_rankings" not in isolated


def test_waiver_governance_policy() -> None:
    assert not WaiverPolicy.can_waive("CRITICAL")
    assert WaiverPolicy.can_waive("HIGH")
    assert WaiverPolicy.can_waive("MEDIUM")

    # Attempting to waive CRITICAL raises ValueError
    with pytest.raises(ValueError, match="CRITICAL findings.*CANNOT be waived"):
        WaiverPolicy.validate_waiver("CRITICAL", "Business exception")

    # Empty justification raises ValueError
    with pytest.raises(ValueError, match="non-empty, recorded justification"):
        WaiverPolicy.validate_waiver("HIGH", "   ")

    # Valid HIGH waiver passes
    WaiverPolicy.validate_waiver("HIGH", "Risk accepted by CISO until Q4 patching window")
