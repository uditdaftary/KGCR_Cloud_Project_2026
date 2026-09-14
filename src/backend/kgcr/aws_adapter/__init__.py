"""AWS Adapter Subsystem (FD-08 §3, §4).

Provides clean abstractions for harvesting AWS cloud configurations and executing gated provisions,
including a local offline fake adapter for credential-free testing.
"""

from kgcr.aws_adapter.fake_adapter import LocalFakeAWSAdapter
from kgcr.aws_adapter.interface import ApplyResult, AWSAdapter, HarvestResult

__all__ = [
    "AWSAdapter",
    "ApplyResult",
    "HarvestResult",
    "LocalFakeAWSAdapter",
]
