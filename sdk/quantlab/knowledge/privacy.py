"""Privacy deny-list scrubbing for Knowledge Lake writes and exports (REQ-107).

Every lake write and training export MUST be scrubbed against a deny-list of
license codes, API keys, ``.env`` contents, credentials, and personal account
data. Scoping is **by field name**, not blind substring redaction: only values
stored under deny-listed keys are redacted, so a secret that merely appears
inside a prose field (e.g. an executive summary mentioning the license code)
is left intact and cannot produce false positives.

Campaign IDs are SHA-256 hashed **only** in training exports (``export=True``);
normal lake writes keep readable IDs for operations.
"""

from __future__ import annotations

import hashlib
from typing import Any

# Placeholder written over a denied field value.
REDACTED = "[REDACTED]"

# Field-scoped deny-list. Values stored under these keys are secrets and are
# redacted wholesale before persisting.
SECRET_FIELD_NAMES: frozenset[str] = frozenset(
    {
        # License codes (FUTLABF255 family — CampaignConfig default)
        "sqx_license",
        "license",
        "license_code",
        "license_key",
        "licence",
        # API keys / tokens
        "api_key",
        "apikey",
        "api_key_id",
        "api_secret",
        "access_token",
        "refresh_token",
        "token",
        "client_secret",
        "client_key",
        "secret",
        "secret_key",
        "private_key",
        # Credentials (.env contents, JForex, broker)
        "password",
        "passwd",
        "pwd",
        "jforex_password",
        "jforex_pin",
        "jforex_username",
        "jforex_account",
        # Personal account data
        "account_number",
        "account_id",
    }
)

# Keys whose values MUST be SHA-256 hashed in training exports (REQ-107).
EXPORT_HASH_FIELDS: frozenset[str] = frozenset({"campaign_id", "campaignid"})

# Suffix rules for deny-listed field names (e.g. ``google_api_key``,
# ``broker_password``). Kept narrow to avoid false positives.
_SECRET_SUFFIXES: tuple[str, ...] = (
    "_token",
    "_secret",
    "_password",
    "_api_key",
    "_license",
    "_credential",
)

# Hex digits used to recognise a SHA-256 digest (64 chars).
_HEXDIGITS = frozenset("0123456789abcdef")


def hash_campaign_id(campaign_id: str) -> str:
    """Return the SHA-256 hex digest of a campaign ID (export-safe, REQ-107)."""
    return hashlib.sha256(str(campaign_id).encode("utf-8")).hexdigest()


def is_secret_field(key: str) -> bool:
    """Return True when *key* names a deny-listed secret field.

    Field-level scoping (D4): the decision is based on the field NAME, so a
    secret value is never redacted when it only appears inside a prose field.
    """
    normalized = str(key).strip().lower().replace("-", "_")
    if normalized in SECRET_FIELD_NAMES:
        return True
    return any(normalized.endswith(suffix) for suffix in _SECRET_SUFFIXES)


def is_export_hash_field(key: str) -> bool:
    """Return True when *key* must be hashed in training exports."""
    return str(key).strip().lower().replace("-", "_") in EXPORT_HASH_FIELDS


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in _HEXDIGITS for c in value)
    )


class PrivacyScrubber:
    """Field-scoped deny-list scrubber with export-mode campaign-ID hashing.

    Usage::

        scrubber = PrivacyScrubber()
        record = scrubber.scrub(record)                    # normal lake write
        export = scrubber.scrub(record, export=True)       # training export
        assert scrubber.is_deny_list_clean(export, export=True)
    """

    # ── Scrubbing ──────────────────────────────────────────────────────────

    def scrub(self, data: Any, *, export: bool = False) -> Any:
        """Return a deep copy of *data* with secrets redacted.

        Args:
            data: The record dict (or list/primitive) to scrub.
            export: When True, campaign-ID fields are SHA-256 hashed
                (REQ-107). Normal lake writes keep readable IDs.

        Returns:
            A new structure with denied values replaced by ``REDACTED``.
        """
        if isinstance(data, dict):
            return {
                key: (
                    REDACTED
                    if is_secret_field(str(key))
                    else (
                        hash_campaign_id(value)
                        if export and is_export_hash_field(str(key))
                        else self.scrub(value, export=export)
                    )
                )
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [self.scrub(item, export=export) for item in data]
        if isinstance(data, tuple):
            return tuple(self.scrub(item, export=export) for item in data)
        return data

    # ── Conformance check ──────────────────────────────────────────────────

    def is_deny_list_clean(self, data: Any, *, export: bool = False) -> bool:
        """Return True when *data* contains no raw denied values.

        A record is clean when every deny-listed field holds ``REDACTED`` and
        (for exports) every campaign-ID field holds a SHA-256 digest. Prose
        fields are out of scope by design (field-scoped deny-list).

        Args:
            data: The record to inspect.
            export: When True, campaign-ID fields must be hashed.
        """
        if isinstance(data, dict):
            for key, value in data.items():
                if is_secret_field(str(key)):
                    if value != REDACTED:
                        return False
                elif export and is_export_hash_field(str(key)):
                    if not _is_sha256(value):
                        return False
                elif not self.is_deny_list_clean(value, export=export):
                    return False
            return True
        if isinstance(data, (list, tuple)):
            return all(
                self.is_deny_list_clean(item, export=export) for item in data
            )
        return True

    # ── Hashing helper ─────────────────────────────────────────────────────

    @staticmethod
    def hash_campaign_id(campaign_id: str) -> str:
        """Return the SHA-256 hex digest of a campaign ID (REQ-107)."""
        return hash_campaign_id(campaign_id)
