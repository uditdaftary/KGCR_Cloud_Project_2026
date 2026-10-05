"""Where the pipeline touches AWS: artifact storage and notifications.

The planned deployment (docs/Project_Report.md, AWS planning table) writes run
artifacts to S3 and publishes contested runs to SNS. Locally both are stood in for:
a directory plays the bucket, and a log line plays the topic. The review pipeline
only sees these two small interfaces, so the AWS-backed versions slot in without
touching it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

__all__ = ["ArtifactStore", "Notifier", "LocalArtifactStore", "LogNotifier"]

logger = logging.getLogger(__name__)


class ArtifactStore(Protocol):
    def put(self, key: str, body: str) -> str:
        """Store ``body`` under ``key``; return a URI for it."""
        ...


class Notifier(Protocol):
    def notify(self, subject: str, message: str) -> None: ...


class LocalArtifactStore:
    """Stand-in for the S3 run bucket: one file per key under ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, key: str, body: str) -> str:
        if key.startswith(("/", "\\")) or ".." in Path(key).parts:
            raise ValueError(f"artifact key must be relative and stay inside the store: {key!r}")
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path.as_posix()


class LogNotifier:
    """Stand-in for the SNS topic: the notification is logged, not sent."""

    def notify(self, subject: str, message: str) -> None:
        logger.warning("[notification stand-in, not sent] %s: %s", subject, message)
