"""
Document listing functions for SignNow MCP server.

This module contains functions for retrieving documents and document groups
from the SignNow API and converting them to simplified formats for MCP tools.
"""

from __future__ import annotations

import time

from fastmcp import Context

from signnow_client import SignNowAPIClient
from signnow_client.models.folders_lite import (
    DocumentGroupInviteLite,
    DocumentGroupItemLite,
    DocumentItemLite,
    FieldInviteLite,
)

from .models import (
    SimplifiedDocumentGroup,
    SimplifiedDocumentGroupDocument,
    SimplifiedDocumentGroupsResponse,
    SimplifiedInvite,
    SimplifiedInviteParticipant,
)
from .utils import extract_role_names


# ----------------------------
# main
# ----------------------------


async def _list_document_groups(
    ctx: Context,
    token: str,
    client: SignNowAPIClient,
    filter: str | None = None,
    sortby: str | None = None,
    order: str | None = None,
    folder_id: str | None = None,
    expired_filter: str = "all",
) -> SimplifiedDocumentGroupsResponse:
    """Provide simplified list of document groups with basic fields.

    Args:
        token: Access token for SignNow API
        client: SignNow API client
        filter: signing-status filter value (optional)
        sortby: Sort by created date, updated date, or document name (optional)
        order: Order of sorting (optional, requires sortby)
        folder_id: Filter by folder ID (optional)
        expired_filter: Filter by invite expiredness (optional, default: all)

    Returns:
        SimplifiedDocumentGroupsResponse with documents + document groups
    """
    if expired_filter not in (None, "all", "expired", "not-expired"):
        raise ValueError("expired_filter must be one of: all, expired, not-expired")

    await ctx.report_progress(progress=0, message="Selecting all folders")

    folders_response = client.get_folders(token, entity_type="all")

    folder_entries: list[tuple[str, str, int | None]] = []
    if folder_id is None or folder_id == folders_response.id:
        folder_entries.append((folders_response.id, folders_response.name, folders_response.total_documents or 0))

    for folder in folders_response.folders:
        if folder_id is None or folder_id == folder.id:
            folder_entries.append((folder.id, folder.name, folder.document_count or 0))

    if folder_id is not None and not folder_entries:
        folder_entries.append((folder_id, "Selected folder", None))

    total = len(folder_entries) + 1
    progress = 1

    simplified_groups: list[SimplifiedDocumentGroup] = []
    filters = "signing-status" if filter else None
    filter_values = filter if filter else None
    now = int(time.time())

    for entry_id, entry_name, _ in folder_entries:
        await ctx.report_progress(progress=progress, total=total, message=f"Processing folder {entry_name}")
        progress += 1

        folder_content = client.get_folder_by_id(
            token,
            entry_id,
            filters=filters,
            filter_values=filter_values,
            sortby=sortby,
            order=order or "desc",
            entity_type="all",
        )

        for item in folder_content.documents:
            # ----------------------------
            # plain document
            # ----------------------------
            if isinstance(item, DocumentItemLite):
                document_name = item.document_name if item.document_name is not None else item.id

                invite = SimplifiedInvite.from_field_invites(item.field_invites, now)

                simplified_docs = [
                    SimplifiedDocumentGroupDocument(
                        id=item.id,
                        name=document_name,
                        roles=extract_role_names(item.roles if isinstance(item.roles, list) else None),
                    )
                ]

                if _matches_expired_filter(invite, expired_filter):
                    simplified_groups.append(
                        SimplifiedDocumentGroup(
                            last_updated=(item.updated or item.created or 0),
                            id=item.id,
                            name=document_name,
                            entity_type="document",
                            invite=invite,
                            documents=simplified_docs,
                        )
                    )
                continue

            # ----------------------------
            # document group
            # ----------------------------
            if isinstance(item, DocumentGroupItemLite):
                simplified_docs: list[SimplifiedDocumentGroupDocument] = []
                group_last_updated = item.updated or item.created or 0

                if item.documents:
                    for doc in item.documents:
                        group_last_updated = max(group_last_updated, doc.updated or 0)
                        doc_name = doc.name if doc.name is not None else doc.id
                        simplified_docs.append(
                            SimplifiedDocumentGroupDocument(
                                id=doc.id,
                                name=doc_name,
                                roles=doc.roles or [],
                            )
                        )

                invite = SimplifiedInvite.from_group_invites(
                    invite_id=item.invite_id,
                    raw_status=item.status,
                    invites=item.invites,
                    now=now,
                )

                group_name = item.document_group_name if item.document_group_name is not None else item.id

                if _matches_expired_filter(invite, expired_filter):
                    simplified_groups.append(
                        SimplifiedDocumentGroup(
                            last_updated=group_last_updated,
                            id=item.id,
                            name=group_name,
                            entity_type="document_group",
                            invite=invite,
                            documents=simplified_docs,
                        )
                    )
                continue

            # other entity_type (template/dgt) are ignored, as before

    return SimplifiedDocumentGroupsResponse(
        document_groups=simplified_groups,
        document_group_total_count=len(simplified_groups),
    )


def _matches_expired_filter(invite: SimplifiedInvite | None, expired_filter: str | None) -> bool:
    if expired_filter in (None, "all"):
        return True

    is_expired = invite.expired if invite is not None else False
    if expired_filter == "expired":
        return is_expired
    if expired_filter == "not-expired":
        return not is_expired

    return True
