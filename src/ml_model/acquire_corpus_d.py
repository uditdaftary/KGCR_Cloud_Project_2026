"""Acquire corpus D (TerraGoat, CloudGoat) and write its provenance manifest.

Shallow, read-only clones go under ``dataset/raw/corpus_d/`` (git-ignored). Each repository's
licence is read from its own LICENSE file and must be on the accepted list; the commit is
pinned. Only the manifest is committed. Nothing is executed, and no ``terraform init`` is run.

    python src/ml_model/acquire_corpus_d.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from kgcr.adversarial.acquire import REPOSITORIES, acquire
from kgcr.defects.adversarial import AdversarialRegistry

DEFAULT_ROOT = Path("dataset/raw/corpus_d")
DEFAULT_MANIFEST = Path("dataset/processed/corpus_d_manifest.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Where to clone")
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    registry = AdversarialRegistry()
    for artifact_id, url, defects in REPOSITORIES:
        artifact = acquire(artifact_id, url, defects, args.root)  # refuses a non-permissive licence
        registry.add(artifact)
        print(f"{artifact.artifact_id}: {artifact.licence} at {artifact.provenance_ref[:12]}")
    path = registry.write_manifest(args.manifest_out)
    print(f"manifest: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
