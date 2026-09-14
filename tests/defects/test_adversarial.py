"""The adversarial registry enforces permissive licensing and provenance."""

from __future__ import annotations

import json

import pytest

from kgcr.defects.adversarial import AdversarialArtifact, AdversarialRegistry


def _artifact(**overrides) -> AdversarialArtifact:
    base = {
        "artifact_id": "terragoat-s3-public",
        "source": "TerraGoat",
        "licence": "Apache-2.0",
        "provenance_url": "https://github.com/bridgecrewio/terragoat",
        "provenance_ref": "v1.0",
        "defect_classes": ("DF-1",),
    }
    base.update(overrides)
    return AdversarialArtifact(**base)  # type: ignore[arg-type]


def test_permissive_artifact_is_accepted() -> None:
    art = _artifact()
    assert art.licence == "Apache-2.0"
    assert art.to_dict()["provenance_url"].startswith("https://")


def test_non_permissive_licence_is_refused() -> None:
    with pytest.raises(ValueError, match="non-permissive licence"):
        _artifact(licence="GPL-3.0")


def test_missing_provenance_is_refused() -> None:
    with pytest.raises(ValueError, match="provenance"):
        _artifact(provenance_ref="")


def test_registry_rejects_duplicate_ids() -> None:
    reg = AdversarialRegistry()
    reg.add(_artifact())
    with pytest.raises(ValueError, match="duplicate"):
        reg.add(_artifact())


def test_manifest_is_written_and_deterministic(tmp_path) -> None:
    reg = AdversarialRegistry()
    reg.add(_artifact())
    reg.add(_artifact(artifact_id="cloudgoat-iam", source="CloudGoat", defect_classes=("DF-3",)))

    path = reg.write_manifest(tmp_path / "corpus_d.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["count"] == 2
    assert manifest["licences"] == ["Apache-2.0"]
    ids = [a["artifact_id"] for a in manifest["artifacts"]]
    assert ids == ["cloudgoat-iam", "terragoat-s3-public"]
