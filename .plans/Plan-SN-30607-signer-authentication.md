# Plan: SN-30607 — Signer Authentication for Field Invites

**Spec:** [.specs/Spec-SN-30607-signer-authentication.md](../.specs/Spec-SN-30607-signer-authentication.md)  
**Ticket:** [SN-30607](https://pdffiller.atlassian.net/browse/SN-30607)

---

## Philosophy Checklist

- [x] Every response model carries ONLY minimum data? — No new response models; existing `SendInviteResponse` is unchanged.
- [x] Tool count minimized? — Extends `InviteRecipient` in-place; no new MCP tools.
- [x] Every business logic function testable with mocked client? — Two pure-transform helpers have zero client calls; wire-up functions use existing mock pattern.
- [x] All error messages specific? — Pydantic `ValueError` messages name field + constraint; `SignNowAPIError` propagated as-is with entity ID from the caller.
- [x] Zero state, zero caching? — Auth config lives in the request; no module-level state added.
- [x] Feature actually needed now? — Explicitly in acceptance criteria.
- [x] `signnow_client/` has zero imports from `sn_mcp_server/`? — No changes in `signnow_client/`.

---

## Phase 1 — API Models

> No new API models needed. `DocumentFieldInviteRecipient` and `FieldInviteAuthentication` / `FieldInviteAction` already carry all required fields.
> One cleanup annotation is required.

- [ ] **[API Model]** `src/signnow_client/models/templates_and_documents.py`
  Add inline comment above `DocumentFieldInviteAuthentication` (≈ line 464):
  ```
  # Unused — document path uses flat fields on DocumentFieldInviteRecipient; scheduled for cleanup
  ```
  No field changes. Do not remove the class — removal is deferred to a cleanup story.

---

## Phase 2 — API Client Methods

> No new client methods needed. `client.get_document_group_v2`, `create_document_field_invite`, and `create_field_invite` already exist.

*(Phase skipped — no steps.)*

---

## Phase 3 — Tool Response Models

> No new response models needed. `SendInviteResponse` is unchanged.

*(Phase skipped — no steps.)*

---

## Phase 4 — Tool Business Logic

Steps must be executed in the order listed.

### 4.1 — Add `SignerAuthentication` model

- [ ] **[Tool Model]** `src/sn_mcp_server/tools/models.py`

  Insert `SignerAuthentication` **above** the `InviteRecipient` class.

  Fields and validators exactly as specified in Spec §4.1:
  - `type: Literal["password", "phone"]` — required, no default
  - `password: str | None = None`
  - `phone: str | None = None`
  - `method: Literal["sms", "phone_call"] | None = None`
  - `sms_message: str | None = None` with `max_length=140`
  - `@model_validator(mode="before")` classmethod `_strip_irrelevant_credential(cls, data: Any) -> Any` — strips password when `type="phone"`, strips phone/method/sms_message when `type="password"`
  - `@model_validator(mode="after")` `_validate_required_credentials(self) -> "SignerAuthentication"` — raises `ValueError("password is required...")` / `ValueError("phone is required...")` on blank/whitespace value
  - `__repr__` — masks `password` via `_mask_secret_value`

  Required imports (verify already present, add if missing):
  - `from pydantic import model_validator`
  - `from typing import Any`

### 4.2 — Add `authentication` field to `InviteRecipient`

- [ ] **[Tool Model]** `src/sn_mcp_server/tools/models.py`

  Append to `InviteRecipient` after `expiration_days`:
  ```
  authentication: SignerAuthentication | None = Field(
      None,
      description=(
          "Optional signer identity verification. "
          "ONLY set this when the user explicitly asks for authentication. "
          "Leave as None (the default) to send invites without any verification — "
          "this is the standard behaviour and must not be changed unless asked."
      ),
  )
  ```

### 4.3 — Add `_build_document_auth_kwargs` helper

- [ ] **[Tool Logic]** `src/sn_mcp_server/tools/send_invite.py`

  Add private helper above `_send_document_field_invite`:
  ```
  def _build_document_auth_kwargs(
      authentication: SignerAuthentication | None,
  ) -> dict[str, Any]:
  ```

  Logic (pseudo-code):
  1. If `authentication is None` → return `{}`
  2. `kwargs = {"authentication_type": authentication.type}`
  3. If `type == "password"`: add `password`
  4. If `type == "phone"`: add `phone`; if `method is not None` add `method`; if `sms_message` add `authentication_sms_message`
  5. Return `kwargs`

  Pure transformation — no validation, no network calls.

### 4.4 — Add `_build_field_invite_authentication` helper + import

- [ ] **[Tool Logic]** `src/sn_mcp_server/tools/send_invite.py`

  Add module-level import (required for return type annotation — `NameError` at parse time without it):
  ```python
  from signnow_client.models.templates_and_documents import FieldInviteAuthentication
  ```

  Add private helper above `_send_document_group_field_invite`:
  ```
  def _build_field_invite_authentication(
      authentication: SignerAuthentication | None,
  ) -> FieldInviteAuthentication | None:
  ```

  Logic (pseudo-code):
  1. If `authentication is None` → return `None`
  2. If `type == "password"` → return `FieldInviteAuthentication(type="password", value=authentication.password)`
  3. If `type == "phone"` → return `FieldInviteAuthentication(type="phone", value=authentication.phone, phone=authentication.phone, method=authentication.method, message=authentication.sms_message)`
     — dual-field mapping: both `value` and `phone` set to same number to cover both possible SignNow API interpretations

  Pure transformation — no validation, no network calls.

### 4.5 — Wire auth in `_send_document_field_invite`

- [ ] **[Tool Logic]** `src/sn_mcp_server/tools/send_invite.py`

  In `recipient_data` construction, after setting `expiration_days`, add:
  ```python
  auth_kwargs = _build_document_auth_kwargs(recipient.authentication)
  recipient_data.update(auth_kwargs)
  ```

  No other changes to this function.

### 4.6 — Wire auth in `_send_document_group_field_invite`

- [ ] **[Tool Logic]** `src/sn_mcp_server/tools/send_invite.py`

  In the `FieldInviteAction` construction block, after building `action_data`, add:
  ```python
  field_auth = _build_field_invite_authentication(recipient.authentication)
  if field_auth is not None:
      action_data["authentication"] = field_auth
  ```

  Guard pattern (`if not None`) prevents injecting `"authentication": null` into the API payload — consistent with how `redirect_target` is handled in other tools.

---

## Phase 5 — Tool Orchestrator & Registration

> `send_invite` and `send_invite_from_template` are already registered. `send_invite_from_template` delegates to `_send_invite` which calls the two private functions — no orchestrator changes needed.

*(Phase skipped — no steps.)*

---

## Phase 6 — Tests

Run `pytest tests/unit/sn_mcp_server/tools/test_send_invite.py tests/integration/test_send_invite.py -x` after each sub-phase.

> Existing tests that mock `client.get_document_group` remain unchanged — v1 is still the production call path.

### 6.1 — Unit tests for helpers and model (steps 4.1–4.4)

- [ ] **[Tests]** `tests/unit/sn_mcp_server/tools/test_send_invite.py`

  Add the following unit tests (all mock nothing; pure Pydantic + helper logic):

  | Test | Coverage |
  |------|----------|
  | `test_build_document_auth_kwargs_none` | Returns `{}` when `authentication=None` |
  | `test_build_document_auth_kwargs_password` | Returns `{"authentication_type": "password", "password": "secret"}` |
  | `test_build_document_auth_kwargs_phone_sms` | Returns dict with `authentication_type`, `phone`, `method="sms"` |
  | `test_build_document_auth_kwargs_phone_call` | `method="phone_call"` in returned dict |
  | `test_build_document_auth_kwargs_sms_message` | `authentication_sms_message` present when `sms_message` provided |
  | `test_build_document_auth_kwargs_password_no_method` | `"method"` key **not** present in dict for password type |
  | `test_build_field_invite_auth_none` | Returns `None` |
  | `test_build_field_invite_auth_password` | Returns `FieldInviteAuthentication(type="password", value="s3cr3t")` |
  | `test_build_field_invite_auth_phone_sms` | Returns object with `value`, `phone` both set to phone number; `method="sms"` |
  | `test_build_field_invite_auth_phone_call` | `method="phone_call"` on returned object |
  | `test_signer_authentication_password_missing` | `ValidationError` with `"password is required"` |
  | `test_signer_authentication_phone_missing` | `ValidationError` with `"phone is required"` |
  | `test_signer_authentication_password_whitespace` | Whitespace-only password raises `ValidationError` |
  | `test_signer_authentication_phone_whitespace` | Whitespace-only phone raises `ValidationError` |
  | `test_signer_authentication_repr_masks_password` | `repr()` does NOT contain the actual password value |

### 6.2 — Unit tests for auth propagation (steps 4.5–4.6)

- [ ] **[Tests]** `tests/unit/sn_mcp_server/tools/test_send_invite.py`

  Add tests that mock `SignNowAPIClient`:

  | Test | Mocks | Coverage |
  |------|-------|----------|
  | `test_send_document_field_invite_with_password_auth` | `get_user_info`, `create_document_field_invite` | Recipient built with `authentication_type="password"`, `password="abc"` |
  | `test_send_document_field_invite_no_auth` | same | Recipient dict does NOT contain `authentication_type` key |
  | `test_send_document_group_field_invite_with_phone_auth` | `get_document_group_v2`, `create_field_invite` | `FieldInviteAction.authentication.type == "phone"`, both `value` and `phone` fields set |
  | `test_send_document_group_field_invite_no_auth` | `get_document_group_v2`, `create_field_invite` | `FieldInviteAction.authentication is None` |

### 6.3 — Integration tests (steps 4.5–4.6 end-to-end)

- [ ] **[Tests]** `tests/integration/test_send_invite.py`

  Add integration tests (mock HTTP layer via `respx`):

  | Test | Mocks | Assertion |
  |------|-------|-----------|
  | `test_send_invite_document_password_auth` | `get_user_info`, `create_document_field_invite` | `request.to[0].authentication_type == "password"` and `request.to[0].password == "secret"` on captured `DocumentFieldInviteRequest` |
  | `test_send_invite_document_phone_auth_default_sms` | same | `method` key absent from recipient (SignNow backend default applies) when `method=None` |
  | `test_send_invite_document_group_phone_auth` | `get_document_group_v2`, `create_field_invite` | `FieldInviteAction.authentication.type == "phone"` |
  | `test_send_invite_document_group_phone_call_auth` | same | `FieldInviteAction.authentication.method == "phone_call"` |
  | `test_send_invite_from_template_with_auth` | `get_document` (template), `get_user_info`, `create_document_field_invite` | Auth propagated end-to-end; `authentication_type="password"` in captured request |
  | `test_send_invite_password_auth_missing_password_error` | none | `ValidationError` raised before any API call |

---

## Phase 7 — Verification

- [ ] **[Docs]** No `README.md` changes needed — `send_invite` is already documented; auth is an optional field extension.

- [ ] **[Docs]** Run full test suite and linters:
  ```
  pytest tests/unit/sn_mcp_server/tools/test_send_invite.py tests/integration/test_send_invite.py -v
  pytest tests/ -x -q
  ruff check src/
  ruff format --check src/
  ```

- [ ] **[Docs]** Manual smoke test via `make up`:
  1. Send a document field invite with `authentication: {type: "password", password: "test123"}` — verify SignNow creates the invite with auth
  2. Send with `authentication: {type: "phone", phone: "+1234567890"}` — verify SMS OTP triggered
  3. Send with `authentication: null` — verify invite created with no auth (baseline unchanged)
  4. Send with `authentication: {type: "password", password: ""}` — verify `isError: true` returned before any API call
