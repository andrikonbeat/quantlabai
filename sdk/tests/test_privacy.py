"""Privacy deny-list tests (REQ-107).

Every lake write and export MUST be scrubbed against a field-scoped deny-list
(license codes, API keys, .env contents, credentials, personal account data).
Campaign IDs MUST be SHA-256 hashed in training exports. Scoping is by field
name — a secret that merely appears inside a prose field is NOT redacted, to
avoid false positives. A conformance check MUST fail on deny-listed exports.
"""

import hashlib

from quantlab.knowledge.privacy import (
    REDACTED,
    PrivacyScrubber,
)

# The canonical FUTLABF255 license code is the deny-list material from
# CampaignConfig (phase4/campaign_orchestrator.py:93).
LICENSE = "FUTLABF255"


class TestScrubAtWrite:
    """REQ-107 scenario: secret redacted at write."""

    def test_license_code_redacted_at_write(self) -> None:
        scrubber = PrivacyScrubber()
        record = {"phase": "config", "config": {"sqx_license": LICENSE}}
        out = scrubber.scrub(record)
        assert out["config"]["sqx_license"] == REDACTED
        # The raw secret must not survive anywhere in the persisted record.
        assert LICENSE not in str(out)

    def test_scrub_is_recursive_into_lists(self) -> None:
        scrubber = PrivacyScrubber()
        record = {"risks": [{"api_key": "sk-proj-123"}, "plain-risk"]}
        out = scrubber.scrub(record)
        assert out["risks"][0]["api_key"] == REDACTED
        assert out["risks"][1] == "plain-risk"

    def test_field_scoped_no_false_positive_in_prose(self) -> None:
        # Field-level scoping, NOT blind substring redaction: a prose field
        # merely mentioning the license string must be left intact.
        scrubber = PrivacyScrubber()
        record = {
            "executive_summary": f"Default license {LICENSE} was used this run.",
        }
        out = scrubber.scrub(record)
        assert out["executive_summary"] == (
            f"Default license {LICENSE} was used this run."
        )

    def test_api_keys_and_credentials_redacted(self) -> None:
        scrubber = PrivacyScrubber()
        record = {
            "api_key": "sk-proj-abc123",
            "config": {
                "password": "hunter2",
                "jforex_password": "s3cret",
                "client_secret": "cs-xyz",
                "token": "tok-1",
            },
        }
        out = scrubber.scrub(record)
        assert out["api_key"] == REDACTED
        assert out["config"]["password"] == REDACTED
        assert out["config"]["jforex_password"] == REDACTED
        assert out["config"]["client_secret"] == REDACTED
        assert out["config"]["token"] == REDACTED

    def test_personal_account_data_redacted(self) -> None:
        scrubber = PrivacyScrubber()
        out = scrubber.scrub({"account_number": "842173", "jforex_account": "842173"})
        assert out["account_number"] == REDACTED
        assert out["jforex_account"] == REDACTED


class TestHashCampaignId:
    """REQ-107 scenario: hashed campaign IDs in exports."""

    def test_export_hashes_campaign_id(self) -> None:
        scrubber = PrivacyScrubber()
        expected = hashlib.sha256(b"campaign-7").hexdigest()
        out = scrubber.scrub({"campaign_id": "campaign-7"}, export=True)
        assert out["campaign_id"] == expected
        assert "campaign-7" not in str(out)

    def test_normal_write_keeps_readable_campaign_id(self) -> None:
        # Only training exports hash campaign IDs; normal lake writes keep
        # readable IDs for operations.
        scrubber = PrivacyScrubber()
        out = scrubber.scrub({"campaign_id": "campaign-7"})
        assert out["campaign_id"] == "campaign-7"

    def test_hash_is_deterministic_and_distinct(self) -> None:
        a = PrivacyScrubber.hash_campaign_id("campaign-9")
        b = PrivacyScrubber.hash_campaign_id("campaign-9")
        c = PrivacyScrubber.hash_campaign_id("campaign-10")
        assert a == b
        assert a != c
        assert len(a) == 64


class TestDenyListClean:
    """REQ-107 conformance: exports must be deny-list-clean."""

    def test_unscrubbed_export_fails_deny_list_clean(self) -> None:
        scrubber = PrivacyScrubber()
        raw = {
            "campaign_id": "campaign-7",
            "config": {"sqx_license": LICENSE},
        }
        assert scrubber.is_deny_list_clean(raw, export=True) is False

    def test_scrubbed_export_passes_deny_list_clean(self) -> None:
        scrubber = PrivacyScrubber()
        raw = {
            "campaign_id": "campaign-7",
            "config": {"sqx_license": LICENSE},
        }
        clean = scrubber.scrub(raw, export=True)
        assert scrubber.is_deny_list_clean(clean, export=True) is True
