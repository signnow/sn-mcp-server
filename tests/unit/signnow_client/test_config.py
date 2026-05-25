"""Unit tests for SignNowConfig static token credential option."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest
from pydantic import AnyHttpUrl, ValidationError

from signnow_client.config import SignNowConfig, _print_config_values


def _make_config(**overrides: object) -> SignNowConfig:
    """Build a SignNowConfig via model_construct, skipping env/file loading."""
    defaults: dict[str, object] = dict(
        api_base=AnyHttpUrl("https://api.signnow.com"),
        app_base=AnyHttpUrl("https://app.signnow.com"),
        client_id=None,
        client_secret=None,
        basic_token=None,
        user_email=None,
        password=None,
        access_token=None,
        default_scope="*",
    )
    defaults.update(overrides)
    return SignNowConfig.model_construct(**defaults)


class TestStaticTokenValidation:
    """Test Option C (static token) in validate_one_of_credentials."""

    def test_access_token_alone_satisfies_validation(self) -> None:
        """Non-empty access_token is sufficient — no OAuth credentials required."""
        config = _make_config(access_token="tok123")  # noqa: S106
        result = config.validate_one_of_credentials()
        assert result is config

    @pytest.mark.parametrize("token", ["t", "a" * 64, "Bearer some-long-token"])
    def test_any_non_empty_access_token_is_valid(self, token: str) -> None:
        """Any truthy string satisfies Option C regardless of format or length."""
        config = _make_config(access_token=token)
        assert config.validate_one_of_credentials() is config

    def test_empty_string_access_token_fails_validation(self) -> None:
        """Empty string is falsy — not a valid credential, raises ValidationError."""
        config = _make_config(access_token="")
        with pytest.raises(ValidationError):
            config.validate_one_of_credentials()

    def test_none_access_token_without_other_creds_fails_validation(self) -> None:
        """None access_token with no other credentials raises ValidationError."""
        config = _make_config()
        with pytest.raises(ValidationError):
            config.validate_one_of_credentials()

    def test_error_message_mentions_option_c(self) -> None:
        """Validation error text guides the user to Option C."""
        config = _make_config()
        with pytest.raises(ValidationError, match="Option C"):
            config.validate_one_of_credentials()

    def test_error_message_names_both_env_vars(self) -> None:
        """Error message names SIGNNOW_ACCESS_TOKEN so the user knows which var to set."""
        config = _make_config()
        with pytest.raises(ValidationError, match="SIGNNOW_ACCESS_TOKEN"):
            config.validate_one_of_credentials()

    def test_access_token_takes_precedence_allows_absent_oauth_fields(self) -> None:
        """access_token alone is enough even when all OAuth fields are None."""
        config = _make_config(
            access_token="my_token",  # noqa: S106
            client_id=None,
            client_secret=None,
            user_email=None,
            password=None,
            basic_token=None,
        )
        assert config.validate_one_of_credentials() is config


class TestAccessTokenFieldValidator:
    """Test that validate_access_token normalises empty strings to None."""

    def test_empty_string_becomes_none(self) -> None:
        """Empty string maps to None, consistent with all other credential validators."""
        result = SignNowConfig.validate_access_token("")  # type: ignore[arg-type]
        assert result is None

    def test_non_empty_string_is_returned_unchanged(self) -> None:
        """Non-empty token passes through without modification."""
        result = SignNowConfig.validate_access_token("abc123")  # type: ignore[arg-type]
        assert result == "abc123"

    def test_none_is_returned_unchanged(self) -> None:
        """None input returns None."""
        result = SignNowConfig.validate_access_token(None)  # type: ignore[arg-type]
        assert result is None


class TestAccessTokenMaskedInOutput:
    """Test that access_token is redacted in _print_config_values output."""

    def test_plaintext_token_is_not_printed(self) -> None:
        """Raw token value must never appear in diagnostic output."""
        config = _make_config(access_token="super_secret_token_xyz")  # noqa: S106
        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_config_values(config)
        assert "super_secret_token_xyz" not in buf.getvalue()

    def test_signnow_access_token_key_appears_in_output(self) -> None:
        """The env var name SIGNNOW_ACCESS_TOKEN is present so the user can identify the field."""
        config = _make_config(access_token="super_secret_token_xyz")  # noqa: S106
        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_config_values(config)
        assert "SIGNNOW_ACCESS_TOKEN" in buf.getvalue()

    def test_masked_value_shows_first_and_last_two_chars(self) -> None:
        """Masked output exposes only the first 2 and last 2 characters."""
        config = _make_config(access_token="abcdefghij")  # noqa: S106  # 10 chars
        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_config_values(config)
        # _mask_secret_value("abcdefghij") → "ab******ij"
        assert "ab******ij" in buf.getvalue()
