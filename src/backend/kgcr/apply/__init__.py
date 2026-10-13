"""Applying a plan: a local simulated apply, and the one gated path that can reach AWS."""


class ApplyRefused(RuntimeError):
    """The apply was refused before anything changed; the message says why."""
