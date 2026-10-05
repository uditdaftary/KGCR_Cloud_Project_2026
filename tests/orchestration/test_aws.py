"""S3 and SNS adapters against moto's in-process AWS mock. No real AWS call is made."""

from __future__ import annotations

import pytest

boto3 = pytest.importorskip("boto3")
moto = pytest.importorskip("moto")
pytest.importorskip("sklearn")

from kgcr.orchestration.aws import S3ArtifactStore, SnsNotifier  # noqa: E402
from kgcr.orchestration.review import run_review  # noqa: E402

REGION = "eu-west-1"


@pytest.fixture(autouse=True)
def fake_aws(monkeypatch: pytest.MonkeyPatch):
    # Fake credentials so nothing can reach a real account even if mocking slipped.
    for name, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": REGION,
    }.items():
        monkeypatch.setenv(name, value)
    with moto.mock_aws():
        yield


def test_review_writes_encrypted_artifacts_to_s3() -> None:
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(
        Bucket="kgcr-runs-test", CreateBucketConfiguration={"LocationConstraint": REGION}
    )
    store = S3ArtifactStore("kgcr-runs-test", client=s3)

    run = run_review(
        variant="unencrypted_database", store=store, notifier=SnsNotifier(_topic()), count=60
    )
    assert all(uri.startswith("s3://kgcr-runs-test/runs/") for uri in run.artifacts.values())
    key = run.artifacts["bundle"].removeprefix("s3://kgcr-runs-test/")
    head = s3.head_object(Bucket="kgcr-runs-test", Key=key)
    assert head["ServerSideEncryption"] == "AES256"


def test_s3_store_refuses_escaping_keys() -> None:
    with pytest.raises(ValueError):
        S3ArtifactStore("b", client=object()).put("../x", "{}")


def test_sns_notifier_publishes_and_validates_the_arn() -> None:
    from moto.sns.models import sns_backends

    arn = _topic()
    SnsNotifier(arn).notify("KGCR review CONTESTED " + "x" * 200, "estate e: OSCILLATING")
    topic = sns_backends["123456789012"][REGION].topics[arn]
    assert len(topic.sent_notifications) == 1
    with pytest.raises(ValueError):
        SnsNotifier("not-an-arn", client=object())


def _topic() -> str:
    arn: str = boto3.client("sns", region_name=REGION).create_topic(Name="kgcr-contested-runs")[
        "TopicArn"
    ]
    return arn


def test_cli_flags_route_artifacts_to_s3(capsys: pytest.CaptureFixture[str]) -> None:
    from kgcr.cli import main

    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket="kgcr-cli", CreateBucketConfiguration={"LocationConstraint": REGION})
    args = ["review", "--variant", "unencrypted_database", "--count", "60"]
    assert main([*args, "--s3-bucket", "kgcr-cli", "--sns-topic-arn", _topic()]) == 0
    assert "stored bundle: s3://kgcr-cli/runs/" in capsys.readouterr().out
    assert s3.list_objects_v2(Bucket="kgcr-cli")["KeyCount"] == 6
