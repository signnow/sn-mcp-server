"""Unit tests for update_invite_recipient module."""

from __future__ import annotations

from unittest.mock import MagicMock

from signnow_client.models.document_groups import (
    DocumentGroupV2Data,
    DocumentGroupV2FreeformInvite,
    GetDocumentGroupV2Response,
)
from signnow_client.models.templates_and_documents import (
    DocumentFieldInviteStatus,
    DocumentFreeFormInvite,
    DocumentResponse,
    FieldInviteActionStatus,
    FieldInviteStatus,
    FieldInviteStepStatus,
    GetDocumentFreeFormInvitesResponse,
    GetFieldInviteResponse,
    ReplaceFieldInviteResponse,
    TriggerFieldInviteResponse,
)
from sn_mcp_server.tools.update_invite_recipient import (
    _find_pending_invites_for_email,
    _find_pending_steps_for_email,
    _update_document_group_invite_recipient,
    _update_invite_recipient,
)

TOKEN = "test-token"  # noqa: S105
DOC_ID = "doc-123"
GRP_ID = "grp-456"
INVITE_ID = "inv-789"


def _field_invite(
    invite_id: str = "inv-1",
    email: str = "old@example.com",
    status: str = "pending",
    role: str = "Signer 1",
    role_id: str = "role-abc",
) -> DocumentFieldInviteStatus:
    """Create a minimal DocumentFieldInviteStatus for tests."""
    return DocumentFieldInviteStatus.model_construct(
        id=invite_id,
        email=email,
        status=status,
        role=role,
        role_id=role_id,
        reminder="0",
        created="1700000000",
        updated="1700000000",
        declined=[],
    )


def _doc_resp(*field_invites: DocumentFieldInviteStatus, template: bool = False) -> DocumentResponse:
    """Create a minimal DocumentResponse for tests."""
    return DocumentResponse.model_construct(
        id=DOC_ID,
        field_invites=list(field_invites),
        template=template,
    )


class TestFindPendingInvitesForEmail:
    """Tests for _find_pending_invites_for_email."""

    def test_finds_pending_invite(self) -> None:
        """Match a pending invite by email."""
        inv = _field_invite(status="pending", email="alice@x.com")
        doc = _doc_resp(inv)
        result = _find_pending_invites_for_email(doc, "alice@x.com", None)
        assert len(result) == 1
        assert result[0].id == "inv-1"

    def test_finds_created_invite(self) -> None:
        """Match a created invite by email."""
        inv = _field_invite(status="created", email="alice@x.com")
        doc = _doc_resp(inv)
        result = _find_pending_invites_for_email(doc, "alice@x.com", None)
        assert len(result) == 1

    def test_skips_fulfilled_invite(self) -> None:
        """Fulfilled invites are not matched."""
        inv = _field_invite(status="fulfilled", email="alice@x.com")
        doc = _doc_resp(inv)
        result = _find_pending_invites_for_email(doc, "alice@x.com", None)
        assert result == []

    def test_email_case_insensitive(self) -> None:
        """Email matching is case-insensitive."""
        inv = _field_invite(status="pending", email="Alice@X.com")
        doc = _doc_resp(inv)
        result = _find_pending_invites_for_email(doc, "alice@x.com", None)
        assert len(result) == 1

    def test_role_filter(self) -> None:
        """When role is specified, only matching role is returned."""
        inv1 = _field_invite(invite_id="inv-1", status="pending", email="alice@x.com", role="Signer 1")
        inv2 = _field_invite(invite_id="inv-2", status="pending", email="alice@x.com", role="Signer 2")
        doc = _doc_resp(inv1, inv2)
        result = _find_pending_invites_for_email(doc, "alice@x.com", "Signer 2")
        assert len(result) == 1
        assert result[0].id == "inv-2"

    def test_role_filter_no_match(self) -> None:
        """When role filter doesn't match, returns empty list."""
        inv = _field_invite(status="pending", email="alice@x.com", role="Signer 1")
        doc = _doc_resp(inv)
        result = _find_pending_invites_for_email(doc, "alice@x.com", "Signer 99")
        assert result == []

    def test_no_invites(self) -> None:
        """Empty field_invites returns empty list."""
        doc = _doc_resp()
        result = _find_pending_invites_for_email(doc, "alice@x.com", None)
        assert result == []

    def test_returns_all_matching_invites(self) -> None:
        """Multiple pending invites for the same email are all returned."""
        inv1 = _field_invite(invite_id="inv-1", status="pending", email="alice@x.com", role="Signer 1")
        inv2 = _field_invite(invite_id="inv-2", status="pending", email="alice@x.com", role="Signer 2")
        inv3 = _field_invite(invite_id="inv-3", status="fulfilled", email="alice@x.com", role="Signer 3")
        doc = _doc_resp(inv1, inv2, inv3)
        result = _find_pending_invites_for_email(doc, "alice@x.com", None)
        assert len(result) == 2
        assert {r.id for r in result} == {"inv-1", "inv-2"}


class TestUpdateInviteRecipient:
    """Tests for _update_invite_recipient business logic."""

    def _client(self, doc_resp: DocumentResponse) -> MagicMock:
        """Create mock client returning the given document."""
        client = MagicMock()
        client.get_document.return_value = doc_resp
        client.get_document_group_v2.side_effect = Exception("not found")
        client.delete_field_invite.return_value = None
        client.replace_field_invite.return_value = ReplaceFieldInviteResponse.model_construct(id="new-inv-99")
        client.trigger_field_invite.return_value = TriggerFieldInviteResponse.model_construct(status="success")
        return client

    def test_happy_path_replace(self) -> None:
        """Successful replace: delete → replace → trigger."""
        inv = _field_invite(invite_id="inv-1", email="old@x.com", status="pending", role_id="role-abc")
        doc = _doc_resp(inv)
        client = self._client(doc)

        result = _update_invite_recipient(
            entity_id=DOC_ID,
            entity_type="document",
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "replaced"
        assert result.new_invite_id == "new-inv-99"
        assert result.previous_email == "old@x.com"
        assert result.new_email == "new@x.com"
        assert result.entity_type == "document"

        client.delete_field_invite.assert_called_once_with(TOKEN, "inv-1")
        client.replace_field_invite.assert_called_once()
        req = client.replace_field_invite.call_args[0][1]
        assert req.email == "new@x.com"
        assert req.role_id == "role-abc"
        assert req.is_replace is True
        client.trigger_field_invite.assert_called_once_with(TOKEN, DOC_ID)

    def test_no_pending_invite(self) -> None:
        """No pending invite found → status='no_pending_invite'."""
        inv = _field_invite(status="fulfilled", email="old@x.com")
        doc = _doc_resp(inv)
        client = self._client(doc)

        result = _update_invite_recipient(
            entity_id=DOC_ID,
            entity_type="document",
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "no_pending_invite"
        assert result.new_invite_id is None
        client.delete_field_invite.assert_not_called()
        client.replace_field_invite.assert_not_called()
        client.trigger_field_invite.assert_not_called()

    def test_unsupported_embedded_invite(self) -> None:
        """Embedded invites return status='unsupported_invite_type'."""
        inv = _field_invite(status="pending", email="old@x.com")
        inv.is_embedded = True
        doc = _doc_resp(inv)
        client = self._client(doc)

        result = _update_invite_recipient(
            entity_id=DOC_ID,
            entity_type="document",
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "unsupported_invite_type"
        assert result.new_invite_id is None
        client.delete_field_invite.assert_not_called()

    def test_replace_request_has_no_extra_params(self) -> None:
        """Replace request only sets email, role_id, is_replace — no optional params."""
        inv = _field_invite(email="old@x.com", status="pending", role_id="role-abc")
        doc = _doc_resp(inv)
        client = self._client(doc)

        _update_invite_recipient(
            entity_id=DOC_ID,
            entity_type="document",
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        req = client.replace_field_invite.call_args[0][1]
        assert req.email == "new@x.com"
        assert req.role_id == "role-abc"
        assert req.is_replace is True
        assert req.expiration_days is None
        assert req.decline_by_signature is None
        assert req.reminder is None
        assert req.authentication_type is None
        assert req.password is None
        assert req.phone is None

    def test_role_filter_selects_correct_invite(self) -> None:
        """Role filter selects the correct invite when multiple exist for same email."""
        inv1 = _field_invite(invite_id="inv-1", email="old@x.com", status="pending", role="Signer 1", role_id="role-1")
        inv2 = _field_invite(invite_id="inv-2", email="old@x.com", status="pending", role="Signer 2", role_id="role-2")
        doc = _doc_resp(inv1, inv2)
        client = self._client(doc)

        result = _update_invite_recipient(
            entity_id=DOC_ID,
            entity_type="document",
            current_email="old@x.com",
            new_email="new@x.com",
            role="Signer 2",
            token=TOKEN,
            client=client,
        )

        assert result.status == "replaced"
        client.delete_field_invite.assert_called_once_with(TOKEN, "inv-2")
        req = client.replace_field_invite.call_args[0][1]
        assert req.role_id == "role-2"

    def test_multiple_matching_invites_all_replaced(self) -> None:
        """When multiple pending invites match, all are deleted and replaced."""
        inv1 = _field_invite(invite_id="inv-1", email="old@x.com", status="pending", role="Signer 1", role_id="role-1")
        inv2 = _field_invite(invite_id="inv-2", email="old@x.com", status="pending", role="Signer 2", role_id="role-2")
        doc = _doc_resp(inv1, inv2)
        client = self._client(doc)

        result = _update_invite_recipient(
            entity_id=DOC_ID,
            entity_type="document",
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "replaced"
        assert client.delete_field_invite.call_count == 2
        assert client.replace_field_invite.call_count == 2
        # Trigger is called once after all replacements
        client.trigger_field_invite.assert_called_once_with(TOKEN, DOC_ID)


# ── document-group helpers ────────────────────────────────────────────────────


def _action(
    email: str | None = "signer@x.com",
    role_name: str = "Signer 1",
    document_id: str = "doc-1",
) -> FieldInviteActionStatus:
    """Create a minimal FieldInviteActionStatus."""
    return FieldInviteActionStatus.model_construct(
        action="sign",
        email=email,
        document_id=document_id,
        status="pending",
        role_name=role_name,
    )


def _step(
    step_id: str = "step-1",
    status: str = "pending",
    actions: list[FieldInviteActionStatus] | None = None,
) -> FieldInviteStepStatus:
    """Create a minimal FieldInviteStepStatus."""
    return FieldInviteStepStatus.model_construct(
        id=step_id,
        status=status,
        order=1,
        actions=actions or [],
    )


def _invite_response(
    steps: list[FieldInviteStepStatus] | None = None,
    is_embedded: bool = False,
) -> GetFieldInviteResponse:
    """Create a minimal GetFieldInviteResponse."""
    return GetFieldInviteResponse.model_construct(
        invite=FieldInviteStatus.model_construct(
            id=INVITE_ID,
            status="pending",
            is_embedded=is_embedded,
            steps=steps or [],
        ),
    )


def _group_resp(
    state: str = "pending",
    invite_id: str | None = INVITE_ID,
    freeform_invite: DocumentGroupV2FreeformInvite | None = None,
) -> GetDocumentGroupV2Response:
    """Create a minimal GetDocumentGroupV2Response."""
    data = DocumentGroupV2Data.model_construct(
        id=GRP_ID,
        name="Test Group",
        created=1700000000,
        state=state,
        invite_id=invite_id,
        freeform_invite=freeform_invite,
        documents=[],
    )
    return GetDocumentGroupV2Response.model_construct(data=data)


# ── TestFindPendingStepsForEmail ──────────────────────────────────────────────


class TestFindPendingStepsForEmail:
    """Tests for _find_pending_steps_for_email."""

    def test_finds_matching_action(self) -> None:
        """Step with a matching email action is returned."""
        act = _action(email="signer@x.com", role_name="Signer 1")
        invite = _invite_response([_step("step-1", "pending", [act])]).invite

        result = _find_pending_steps_for_email(invite, "signer@x.com", None)

        assert len(result) == 1
        assert result[0][0].id == "step-1"
        assert len(result[0][1]) == 1

    def test_skips_fulfilled_step(self) -> None:
        """Steps with fulfilled status are not matched."""
        act = _action(email="signer@x.com")
        invite = _invite_response([_step("step-1", "fulfilled", [act])]).invite

        result = _find_pending_steps_for_email(invite, "signer@x.com", None)

        assert result == []

    def test_role_filter_returns_only_matching_action(self) -> None:
        """Role filter narrows down actions within the step."""
        a1 = _action(email="signer@x.com", role_name="Signer 1")
        a2 = _action(email="signer@x.com", role_name="Signer 2")
        invite = _invite_response([_step("step-1", "pending", [a1, a2])]).invite

        result = _find_pending_steps_for_email(invite, "signer@x.com", "Signer 2")

        assert len(result) == 1
        assert len(result[0][1]) == 1
        assert result[0][1][0].role_name == "Signer 2"

    def test_role_filter_no_match_excludes_step(self) -> None:
        """Step is excluded when no action matches the role filter."""
        act = _action(email="signer@x.com", role_name="Signer 1")
        invite = _invite_response([_step("step-1", "pending", [act])]).invite

        result = _find_pending_steps_for_email(invite, "signer@x.com", "Signer 99")

        assert result == []

    def test_skips_action_with_null_email(self) -> None:
        """Actions with email=None are ignored."""
        act = _action(email=None)
        invite = _invite_response([_step("step-1", "pending", [act])]).invite

        result = _find_pending_steps_for_email(invite, "signer@x.com", None)

        assert result == []

    def test_email_case_insensitive(self) -> None:
        """Email matching is case-insensitive."""
        act = _action(email="SIGNER@X.COM")
        invite = _invite_response([_step("step-1", "pending", [act])]).invite

        result = _find_pending_steps_for_email(invite, "signer@x.com", None)

        assert len(result) == 1

    def test_empty_steps_returns_empty(self) -> None:
        """No steps → empty list."""
        invite = _invite_response([]).invite

        result = _find_pending_steps_for_email(invite, "signer@x.com", None)

        assert result == []

    def test_multiple_matching_steps_all_returned(self) -> None:
        """Multiple pending steps with matching actions are all returned."""
        a1 = _action(email="signer@x.com", role_name="Signer 1", document_id="doc-1")
        a2 = _action(email="signer@x.com", role_name="Signer 2", document_id="doc-2")
        step1 = _step("step-1", "pending", [a1])
        step2 = _step("step-2", "pending", [a2])
        invite = _invite_response([step1, step2]).invite

        result = _find_pending_steps_for_email(invite, "signer@x.com", None)

        assert len(result) == 2
        assert {r[0].id for r in result} == {"step-1", "step-2"}


# ── TestUpdateDocumentGroupInviteRecipient ────────────────────────────────────


class TestUpdateDocumentGroupInviteRecipient:
    """Tests for _update_document_group_invite_recipient."""

    def test_no_invite_id_returns_no_pending_invite(self) -> None:
        """Group with invite_id=None → status='no_pending_invite', no API calls."""
        group = _group_resp(invite_id=None)
        client = MagicMock()

        result = _update_document_group_invite_recipient(
            entity_id=GRP_ID,
            document_group=group,
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "no_pending_invite"
        assert result.entity_type == "document_group"
        client.get_field_invite.assert_not_called()

    def test_no_matching_steps_returns_no_pending_invite(self) -> None:
        """get_field_invite returns no matching steps → status='no_pending_invite'."""
        group = _group_resp(invite_id=INVITE_ID)
        client = MagicMock()
        client.get_field_invite.return_value = _invite_response(steps=[])

        result = _update_document_group_invite_recipient(
            entity_id=GRP_ID,
            document_group=group,
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "no_pending_invite"
        client.update_document_group_invite_step.assert_not_called()

    def test_happy_path_updates_matching_step(self) -> None:
        """Matching step found → status='replaced', step updated."""
        act = _action(email="old@x.com", document_id="doc-1")
        group = _group_resp(invite_id=INVITE_ID)
        client = MagicMock()
        client.get_field_invite.return_value = _invite_response([_step("step-1", "pending", [act])])

        result = _update_document_group_invite_recipient(
            entity_id=GRP_ID,
            document_group=group,
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "replaced"
        assert result.new_invite_id == INVITE_ID
        assert result.previous_email == "old@x.com"
        assert result.new_email == "new@x.com"
        assert result.updated_steps == ["step-1"]
        client.update_document_group_invite_step.assert_called_once()

    def test_update_step_called_with_correct_args(self) -> None:
        """update_document_group_invite_step receives correct token, IDs, and request body."""
        act = _action(email="old@x.com", document_id="doc-abc")
        group = _group_resp(invite_id=INVITE_ID)
        client = MagicMock()
        client.get_field_invite.return_value = _invite_response([_step("step-1", "pending", [act])])

        _update_document_group_invite_recipient(
            entity_id=GRP_ID,
            document_group=group,
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        args = client.update_document_group_invite_step.call_args[0]
        assert args[0] == TOKEN
        assert args[1] == GRP_ID
        assert args[2] == INVITE_ID
        assert args[3] == "step-1"
        req = args[4]
        assert req.user_to_update == "old@x.com"
        assert req.replace_with_this_user == "new@x.com"
        assert req.invite_email.email == "new@x.com"

    def test_multiple_steps_all_updated(self) -> None:
        """Two matching steps → both updated, updated_steps contains both IDs."""
        a1 = _action(email="old@x.com", document_id="doc-1")
        a2 = _action(email="old@x.com", document_id="doc-2")
        step1 = _step("step-1", "pending", [a1])
        step2 = _step("step-2", "pending", [a2])
        group = _group_resp(invite_id=INVITE_ID)
        client = MagicMock()
        client.get_field_invite.return_value = _invite_response([step1, step2])

        result = _update_document_group_invite_recipient(
            entity_id=GRP_ID,
            document_group=group,
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "replaced"
        assert set(result.updated_steps) == {"step-1", "step-2"}
        assert client.update_document_group_invite_step.call_count == 2


# ── document-group path in TestUpdateInviteRecipient ─────────────────────────


class TestUpdateInviteRecipientDocumentGroup:
    """Tests for _update_invite_recipient with document_group entities."""

    def test_document_group_field_invite_replaced(self) -> None:
        """Document group with pending field invite → status='replaced'."""
        act = _action(email="old@x.com", document_id="doc-1")
        group = _group_resp(state="pending", invite_id=INVITE_ID)
        client = MagicMock()
        client.get_document_group_v2.return_value = group
        # get_field_invite called twice: once in resolve info check, once in update
        client.get_field_invite.return_value = _invite_response([_step("step-1", "pending", [act])])

        result = _update_invite_recipient(
            entity_id=GRP_ID,
            entity_type="document_group",
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "replaced"
        assert result.entity_type == "document_group"
        client.update_document_group_invite_step.assert_called_once()

    def test_document_group_freeform_invite_unsupported(self) -> None:
        """Document group with freeform invite → status='unsupported_invite_type'."""
        freeform = DocumentGroupV2FreeformInvite.model_construct(id="ff-1", last_id=None)
        group = _group_resp(state="pending", invite_id=None, freeform_invite=freeform)
        client = MagicMock()
        client.get_document_group_v2.return_value = group

        result = _update_invite_recipient(
            entity_id=GRP_ID,
            entity_type="document_group",
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "unsupported_invite_type"
        assert result.entity_type == "document_group"
        client.update_document_group_invite_step.assert_not_called()

    def test_document_group_embedded_invite_unsupported(self) -> None:
        """Document group with embedded invite → status='unsupported_invite_type'."""
        group = _group_resp(state="pending", invite_id=INVITE_ID)
        client = MagicMock()
        client.get_document_group_v2.return_value = group
        client.get_field_invite.return_value = _invite_response(is_embedded=True)

        result = _update_invite_recipient(
            entity_id=GRP_ID,
            entity_type="document_group",
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "unsupported_invite_type"
        assert result.entity_type == "document_group"

    def test_document_freeform_invite_unsupported(self) -> None:
        """Document with freeform invite → status='unsupported_invite_type'."""
        freeform = DocumentFreeFormInvite.model_construct(id="ff-1", status="pending", created=1700000000, email="old@x.com")
        client = MagicMock()
        client.get_document.return_value = _doc_resp()  # empty field_invites → freeform path
        client.get_document_group_v2.side_effect = Exception("not a group")
        client.get_document_freeform_invites.return_value = GetDocumentFreeFormInvitesResponse.model_construct(data=[freeform])

        result = _update_invite_recipient(
            entity_id=DOC_ID,
            entity_type="document",
            current_email="old@x.com",
            new_email="new@x.com",
            role=None,
            token=TOKEN,
            client=client,
        )

        assert result.status == "unsupported_invite_type"
        client.delete_field_invite.assert_not_called()
