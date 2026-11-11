import json
from pathlib import Path

from habitat.proof_verify import verify_file


ROOT = Path(__file__).resolve().parents[1]


def test_published_habitat_proof_snapshots_verify_and_match_source_exports():
    manifest = json.loads((ROOT / "site" / "proofs-manifest.json").read_text(encoding="utf-8"))
    for project, entries in manifest["projects"].items():
        for entry in entries:
            relative = entry["proof_url"].lstrip("/")
            published = ROOT / "site" / relative
            source = ROOT / "web" / "public" / relative
            assert published.is_file(), f"missing published proof: {published}"
            assert source.is_file(), f"missing source proof: {source}"
            assert published.read_bytes() == source.read_bytes()
            result = verify_file(published)
            assert result["valid"], result["errors"]
            assert result["assurance"]["publisher_trust"] == "not-assessed"
            assert result["assurance"]["external_truth"] == "not-established"
            assert result["assurance"]["signature"] == "absent"
