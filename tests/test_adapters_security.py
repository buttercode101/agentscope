import pytest

from habitat.adapters import HTTPJSONEvidenceAdapter


def test_http_evidence_rejects_loopback_targets():
    with pytest.raises(ValueError, match="private_address"):
        HTTPJSONEvidenceAdapter("http://127.0.0.1:8787")


def test_http_evidence_rejects_embedded_credentials():
    with pytest.raises(ValueError, match="credentials_not_allowed"):
        HTTPJSONEvidenceAdapter("https://user:pass@example.com")


def test_http_evidence_rejects_unsupported_scheme():
    with pytest.raises(ValueError, match="unsupported_evidence_url_scheme"):
        HTTPJSONEvidenceAdapter("file:///etc/hosts")
