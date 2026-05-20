"""Unit tests for EmbeddedInviteAuthentication type validation."""

import pytest
from pydantic import ValidationError

from signnow_client.models.templates_and_documents import EmbeddedInviteAuthentication


class TestEmbeddedInviteAuthenticationType:
    """Test cases for EmbeddedInviteAuthentication type field validation."""

    def test_password_type_accepted(self) -> None:
        """Test 'password' is a valid authentication type."""
        auth = EmbeddedInviteAuthentication(type="password", password="s3cr3t")  # noqa: S106
        assert auth.type == "password"

    def test_phone_type_accepted(self) -> None:
        """Test 'phone' is a valid authentication type."""
        auth = EmbeddedInviteAuthentication(type="phone", phone="+1234567890", method="sms")
        assert auth.type == "phone"

    def test_invalid_type_raises_validation_error(self) -> None:
        """Test invalid type like 'email' raises ValidationError with clear message."""
        with pytest.raises(ValidationError, match="phone.*password|password.*phone"):
            EmbeddedInviteAuthentication(type="email")

    def test_empty_type_raises_validation_error(self) -> None:
        """Test empty string type raises ValidationError."""
        with pytest.raises(ValidationError, match="phone.*password|password.*phone"):
            EmbeddedInviteAuthentication(type="")

    @pytest.mark.parametrize("invalid_type", ["mfa", "biometric", "social", "none", "EMAIL", "Phone"])
    def test_various_invalid_types_rejected(self, invalid_type: str) -> None:
        """Test various invalid type values are rejected."""
        with pytest.raises(ValidationError):
            EmbeddedInviteAuthentication(type=invalid_type)
