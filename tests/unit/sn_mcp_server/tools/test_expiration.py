"""
Unit tests for optional expiration_time and expiration_days handling.
"""

import pytest

from signnow_client.models.document_groups import DocumentGroupV2FieldInvite

from sn_mcp_server.tools.models import SimplifiedInviteParticipant


class TestExpirationHandling:
    """Test cases for optional expiration_time and expiration_days."""

    def test_simplified_invite_participant_from_field_invite_with_expiration(self):
        """Test SimplifiedInviteParticipant.from_document_group_v2_field_invite with expiration."""
        now = 1500000000
        field_invite = DocumentGroupV2FieldInvite(
            id="invite123",
            created=1000000000,
            updated=1000000001,
            status="pending",
            expiration_time=2000000000,  # Future expiration
            expiration_days=30,
            signer_email="test@example.com",
            password_protected="0",
            email_statuses=[],
        )
        participant = SimplifiedInviteParticipant.from_document_group_v2_field_invite(field_invite, now)
        assert participant.email == "test@example.com"
        assert participant.expires_at == 2000000000
        assert participant.expired is False  # Not expired yet
        assert participant.status == "pending"

    def test_simplified_invite_participant_from_field_invite_without_expiration(self):
        """Test SimplifiedInviteParticipant.from_document_group_v2_field_invite without expiration."""
        now = 1500000000
        field_invite = DocumentGroupV2FieldInvite(
            id="invite123",
            created=1000000000,
            updated=1000000001,
            status="pending",
            expiration_time=None,  # No expiration
            expiration_days=None,
            signer_email="test@example.com",
            password_protected="0",
            email_statuses=[],
        )
        participant = SimplifiedInviteParticipant.from_document_group_v2_field_invite(field_invite, now)
        assert participant.email == "test@example.com"
        assert participant.expires_at is None
        assert participant.expired is False  # No expiration means not expired
        assert participant.status == "pending"

    def test_simplified_invite_participant_from_field_invite_expired(self):
        """Test SimplifiedInviteParticipant.from_document_group_v2_field_invite with expired invite."""
        now = 2500000000  # After expiration
        field_invite = DocumentGroupV2FieldInvite(
            id="invite123",
            created=1000000000,
            updated=1000000001,
            status="pending",
            expiration_time=2000000000,  # Past expiration
            expiration_days=30,
            signer_email="test@example.com",
            password_protected="0",
            email_statuses=[],
        )
        participant = SimplifiedInviteParticipant.from_document_group_v2_field_invite(field_invite, now)
        assert participant.email == "test@example.com"
        assert participant.expires_at == 2000000000
        assert participant.expired is True  # Expired
        assert participant.status == "expired"

    def test_simplified_invite_participant_from_field_invite_expired_status(self):
        """Test SimplifiedInviteParticipant.from_document_group_v2_field_invite with expired status."""
        now = 1500000000
        field_invite = DocumentGroupV2FieldInvite(
            id="invite123",
            created=1000000000,
            updated=1000000001,
            status="expired",  # Already marked as expired
            expiration_time=2000000000,
            expiration_days=30,
            signer_email="test@example.com",
            password_protected="0",
            email_statuses=[],
        )
        participant = SimplifiedInviteParticipant.from_document_group_v2_field_invite(field_invite, now)
        assert participant.expired is True
        assert participant.status == "expired"

    @pytest.mark.parametrize(
        "status,expires_at,now,expected",
        [
            ("pending", None, 1500000000, False),  # None expiration_time
            ("pending", 2000000000, 1500000000, False),  # Future expiration
            ("pending", 2000000000, 2500000000, True),  # Past expiration with pending status
            ("signed", 2000000000, 2500000000, False),  # Past expiration but signed status (not in PENDING)
        ],
    )
    def test_check_expired(self, status: str, expires_at: int | None, now: int, expected: bool):
        """Test check_expired method with various status, expiration, and time combinations."""
        result = SimplifiedInviteParticipant.check_expired(status, expires_at, now)
        assert result == expected
