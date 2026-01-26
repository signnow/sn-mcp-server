"""
Unit tests for optional expiration_time and expiration_days handling.
"""

from signnow_client.models.document_groups import DocumentGroupV2FieldInvite

from sn_mcp_server.tools.models import SimplifiedInviteParticipant


class TestExpirationHandling:
    """Test cases for optional expiration_time and expiration_days."""

    def test_document_group_v2_field_invite_with_expiration_time(self):
        """Test DocumentGroupV2FieldInvite with expiration_time."""
        field_invite = DocumentGroupV2FieldInvite(
            id="invite123",
            created=1000000000,
            updated=1000000001,
            status="pending",
            expiration_time=2000000000,
            expiration_days=30,
            signer_email="test@example.com",
            password_protected="0",
            email_statuses=[],
        )
        assert field_invite.expiration_time == 2000000000
        assert field_invite.expiration_days == 30

    def test_document_group_v2_field_invite_without_expiration_time(self):
        """Test DocumentGroupV2FieldInvite without expiration_time (None)."""
        field_invite = DocumentGroupV2FieldInvite(
            id="invite123",
            created=1000000000,
            updated=1000000001,
            status="pending",
            expiration_time=None,
            expiration_days=None,
            signer_email="test@example.com",
            password_protected="0",
            email_statuses=[],
        )
        assert field_invite.expiration_time is None
        assert field_invite.expiration_days is None

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

    def test_check_expired_with_none_expiration_time(self):
        """Test check_expired method with None expiration_time."""
        now = 1500000000
        # check_expired should return False when expires_at is None
        result = SimplifiedInviteParticipant.check_expired("pending", None, now)
        assert result is False

    def test_check_expired_with_future_expiration(self):
        """Test check_expired method with future expiration."""
        now = 1500000000
        expiration_time = 2000000000  # Future
        result = SimplifiedInviteParticipant.check_expired("pending", expiration_time, now)
        assert result is False

    def test_check_expired_with_past_expiration(self):
        """Test check_expired method with past expiration."""
        now = 2500000000
        expiration_time = 2000000000  # Past
        result = SimplifiedInviteParticipant.check_expired("pending", expiration_time, now)
        assert result is True

    def test_check_expired_with_signed_status(self):
        """Test check_expired method with signed status (should not be expired)."""
        now = 2500000000
        expiration_time = 2000000000  # Past, but status is signed
        result = SimplifiedInviteParticipant.check_expired("signed", expiration_time, now)
        # Signed status is not in PENDING set, so should return False
        assert result is False
