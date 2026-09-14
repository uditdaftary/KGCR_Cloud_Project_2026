"""Backend Service Orchestration Subsystem (FD-01).

Implements the interface-independent pipeline execution controller, stage transitions (S0-S11),
and terminal state transitions (T1-T5), integrating persistence, auth, and AWS adapters.
"""

from kgcr.service.orchestrator import ExecutionResult, KGCRBackendService, PipelineContext

__all__ = [
    "ExecutionResult",
    "KGCRBackendService",
    "PipelineContext",
]
