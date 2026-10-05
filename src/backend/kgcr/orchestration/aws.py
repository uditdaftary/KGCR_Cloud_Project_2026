"""Where the pipeline touches AWS: artifact storage and notifications.

The planned deployment (docs/Project_Report.md, AWS planning table) writes run
artifacts to S3 and publishes contested runs to SNS. The default is local: a
directory plays the bucket and a log line plays the topic. ``S3ArtifactStore`` and
``SnsNotifier`` are the real thing, behind the same two interfaces, for the bucket
and topic in ``src/aws/run_artifacts.tf``. They are tested against moto's
in-process AWS mock; nothing in this repository has been deployed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

__all__ = [
    "ArtifactStore",
    "Notifier",
    "LocalArtifactStore",
    "LogNotifier",
    "S3ArtifactStore",
    "SnsNotifier",
]

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


# --- AWS-backed versions (the ``aws`` extra). boto3 is imported inside each
# constructor so the package imports and type-checks without it. Credentials and
# region come from the standard AWS chain; nothing here reads or stores them.
# ``client`` is typed Any because boto3 ships no type stubs; tests inject a
# moto-backed client through it.


class S3ArtifactStore:
    """Run artifacts in the S3 bucket provisioned by src/aws/run_artifacts.tf."""

    def __init__(self, bucket: str, client: Any = None) -> None:
        if not bucket:
            raise ValueError("bucket is required")
        if client is None:
            import boto3

            client = boto3.client("s3")
        self.bucket = bucket
        self._client = client

    def put(self, key: str, body: str) -> str:
        if key.startswith("/") or ".." in key.split("/"):
            raise ValueError(f"artifact key must be relative: {key!r}")
        # SSE-S3 is also the bucket default; stating it keeps a misconfigured
        # bucket from silently storing plaintext.
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json" if key.endswith(".json") else "text/plain",
            ServerSideEncryption="AES256",
        )
        return f"s3://{self.bucket}/{key}"


class SnsNotifier:
    """Publish contested-run notifications to the SNS topic in run_artifacts.tf."""

    def __init__(self, topic_arn: str, client: Any = None) -> None:
        if not topic_arn.startswith("arn:aws:sns:"):
            raise ValueError(f"not an SNS topic ARN: {topic_arn!r}")
        if client is None:
            import boto3

            client = boto3.client("sns")
        self.topic_arn = topic_arn
        self._client = client

    def notify(self, subject: str, message: str) -> None:
        # SNS caps email subjects at 100 characters.
        self._client.publish(TopicArn=self.topic_arn, Subject=subject[:100], Message=message)
        logger.info("published notification to %s", self.topic_arn)
