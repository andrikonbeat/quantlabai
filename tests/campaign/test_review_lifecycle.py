"""REQ-905: review lifecycle doc for SDK changes.

Tests verify that `docs/guides/review-lifecycle.md` exists and contains
the required 4R envelope, stop-reason continuation table, repair
--preflight reference, and explicit RDD out-of-scope statement.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOC_PATH = REPO_ROOT / "docs" / "guides" / "review-lifecycle.md"


class TestReviewLifecycleDoc:
    """REQ-905: review-lifecycle.md must exist and define the lifecycle."""

    def test_review_lifecycle_doc_exists(self) -> None:
        assert DOC_PATH.exists(), f"Missing {DOC_PATH}"

    def test_doc_contains_4r_envelope(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        assert "4R" in text or "Request" in text
        assert "Review" in text
        assert "Repair" in text
        assert "Release" in text

    def test_doc_contains_route_command(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        assert "gentle-ai review status" in text
        assert "--contract gentle-ai.review-integration/v2" in text
        assert "--next-transition" in text

    def test_doc_contains_repair_preflight(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        assert "repair --preflight" in text or "repair" in text.lower()

    def test_doc_contains_stop_reason_table(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        assert "stop-reason" in text.lower() or "stop reason" in text.lower()

    def test_doc_states_rdd_out_of_scope(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        assert "RDD" in text
        assert "out of scope" in text.lower() or "out-of-scope" in text.lower()

    def test_doc_contains_consent_envelope_details(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        assert "lossless" in text.lower()
        assert "blocking-prompt" in text.lower()
        assert "granted" in text
        assert "declined" in text

    def test_doc_contains_specific_stop_reason_codes(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        required_codes = [
            "captured_artifacts_unverifiable",
            "manual_intervention_required",
            "corrupted_or_unverifiable_authority",
            "rdd_disabled",
            "staged_delivery_candidate_required",
        ]
        for code in required_codes:
            assert code in text, f"Missing stop-reason code: {code}"

    def test_doc_contains_repair_preflight_command(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        assert "gentle-ai review repair --preflight" in text
