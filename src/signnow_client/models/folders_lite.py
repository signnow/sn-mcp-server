from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
)

from .templates_and_documents import DocumentThumbnail


# ----------------------------
# helpers
# ----------------------------


def _parse_int_value(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


IntFromAny = Annotated[int | None, BeforeValidator(_parse_int_value)]


def _normalize_folder_type_value(value: Any) -> Any:
    """Normalize folder type value from API.

    The SignNow API sometimes returns inconsistent type values:
    - Sometimes returns "document_group" instead of "document-group"
    - This function normalizes these inconsistencies to ensure consistent type values.
    """
    if value == "document_group":
        return "document-group"
    return value


def _normalize_roles(value: Any) -> list[str] | None:
    """Normalize roles to list[str] format.

    Handles:
    - list[str]: returns as-is
    - list[RoleLite]: extracts name from each RoleLite
    - list[dict]: extracts name from each dict
    - None: returns None
    - Other: returns None
    """
    if value is None:
        return None
    if not isinstance(value, list):
        return None

    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            if item:
                result.append(item)
        elif isinstance(item, dict):
            name = item.get("name")
            if name:
                result.append(name)
        elif hasattr(item, "name"):
            # RoleLite or similar object
            name = getattr(item, "name", None)
            if name:
                result.append(name)

    return result if result else None


def _folder_doc_type_from_payload(value: Any) -> str:
    """Discriminator function for Union by raw payload.

    Extracts and normalizes the type/entity_type from payload to determine which model to use.
    Known types: "document", "template", "document-group", "dgt" (document group template).

    Args:
        value: Raw payload (dict) or type value (str)

    Returns:
        Normalized type string, or "unknown" if type cannot be determined
    """
    if isinstance(value, dict):
        raw_type = value.get("entity_type") or value.get("type")
    else:
        raw_type = value
    if raw_type is None:
        # Return "unknown" as fallback for items without type/entity_type
        # This will be handled by UnknownFolderDocLite
        return "unknown"
    normalized = _normalize_folder_type_value(raw_type)
    # Validate that normalized type is one of the known types
    # "dgt" stands for "document group template" (DocumentGroupTemplateItemLite)
    if normalized not in ("document", "template", "document-group", "dgt"):
        return "unknown"
    return normalized


# ----------------------------
# base model
# ----------------------------


class SNBaseModel(BaseModel):
    # explicitly fix behavior: ignore extra fields
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ----------------------------
# roles / invites / group docs (minimal)
# ----------------------------


class RoleLite(SNBaseModel):
    id: str | None = Field(None, validation_alias=AliasChoices("unique_id", "id"))
    name: str | None = Field(None)
    signing_order: IntFromAny = Field(None)


class FieldInviteLite(SNBaseModel):
    id: str
    signer_user_id: str | None = None
    status: str | None = None
    email: str | None = None
    role: str | None = None
    role_id: str | None = None

    created: IntFromAny = None
    updated: IntFromAny = None
    expiration_time: IntFromAny = None


class DocumentGroupInviteLite(SNBaseModel):
    id: str
    email: str | None = None
    document_id: str | None = None
    document_name: str | None = None
    status: str | None = None
    is_full_declined: bool | None = None
    action: str | None = None

    order: IntFromAny = None
    created: IntFromAny = None
    updated: IntFromAny = None
    expiration_time: IntFromAny = None


class DocumentGroupDocumentLite(SNBaseModel):
    id: str
    name: str | None = None
    page_count: IntFromAny = None
    updated: IntFromAny = None
    roles: list[str] | None = None
    thumbnail: DocumentThumbnail | None = None


# ----------------------------
# folder items
# ----------------------------

DocTypeDocument = Annotated[Literal["document"], BeforeValidator(_normalize_folder_type_value)]
DocTypeTemplate = Annotated[Literal["template"], BeforeValidator(_normalize_folder_type_value)]
DocTypeDocGroup = Annotated[Literal["document-group"], BeforeValidator(_normalize_folder_type_value)]
DocTypeDgt = Annotated[Literal["dgt"], BeforeValidator(_normalize_folder_type_value)]
DocTypeUnknown = Annotated[Literal["unknown"], BeforeValidator(_normalize_folder_type_value)]


class DocumentItemLite(SNBaseModel):
    type: DocTypeDocument = Field(..., validation_alias=AliasChoices("type", "entity_type"))

    id: str
    user_id: str | None = None
    document_name: str | None = None
    owner: str | None = None
    parent_id: str | None = None

    page_count: IntFromAny = None
    created: IntFromAny = None
    updated: IntFromAny = None

    pinned: bool | None = None
    is_favorite: bool | None = None
    template: bool | None = None

    thumbnail: DocumentThumbnail | None = None

    roles: Annotated[list[str] | None, BeforeValidator(_normalize_roles)] = None

    field_invites: list[FieldInviteLite] | None = None


class TemplateItemLite(SNBaseModel):
    type: DocTypeTemplate = Field(..., validation_alias=AliasChoices("type", "entity_type"))

    id: str
    user_id: str | None = None
    document_name: str | None = None
    owner: str | None = None
    parent_id: str | None = None

    page_count: IntFromAny = None
    created: IntFromAny = None
    updated: IntFromAny = None
    version_time: IntFromAny = None

    pinned: bool | None = None
    is_favorite: bool | None = None
    template: bool | None = None

    thumbnail: DocumentThumbnail | None = None


class DocumentGroupItemLite(SNBaseModel):
    type: DocTypeDocGroup = Field(..., validation_alias=AliasChoices("type", "entity_type"))

    id: str
    user_id: str | None = None
    document_group_name: str | None = None
    owner: str | None = None
    parent_id: str | None = None

    invite_id: str | None = None

    created: IntFromAny = None
    updated: IntFromAny = None
    recently_used: IntFromAny = None

    state: str | None = None
    status: str | None = None

    pinned: bool | None = None
    is_favorite: bool | None = None

    invites: list[DocumentGroupInviteLite] | None = None
    documents: list[DocumentGroupDocumentLite] | None = None


class DocumentGroupTemplateItemLite(SNBaseModel):
    type: DocTypeDgt = Field(..., validation_alias=AliasChoices("type", "entity_type"))

    id: str
    user_id: str | None = None
    document_group_name: str | None = None
    owner: str | None = None
    parent_id: str | None = None

    invite_id: str | None = None

    created: IntFromAny = None
    updated: IntFromAny = None
    recently_used: IntFromAny = None

    state: str | None = None
    status: str | None = None

    pinned: bool | None = None
    is_favorite: bool | None = None

    invites: list[DocumentGroupInviteLite] | None = None
    documents: list[DocumentGroupDocumentLite] | None = None


class UnknownFolderDocLite(SNBaseModel):
    """Fallback model for folder items with unknown or missing type/entity_type."""

    type: DocTypeUnknown = Field(..., validation_alias=AliasChoices("type", "entity_type"))

    id: str
    user_id: str | None = None
    document_name: str | None = None
    document_group_name: str | None = None
    owner: str | None = None
    parent_id: str | None = None

    page_count: IntFromAny = None
    created: IntFromAny = None
    updated: IntFromAny = None

    pinned: bool | None = None
    is_favorite: bool | None = None
    template: bool | None = None

    thumbnail: DocumentThumbnail | None = None

    # Allow any additional fields that might be present
    # This is a fallback, so we want to be permissive


FolderDocLite = Annotated[
    Union[
        Annotated[DocumentItemLite, Tag("document")],
        Annotated[TemplateItemLite, Tag("template")],
        Annotated[DocumentGroupItemLite, Tag("document-group")],
        Annotated[DocumentGroupTemplateItemLite, Tag("dgt")],
        Annotated[UnknownFolderDocLite, Tag("unknown")],
    ],
    Field(discriminator=Discriminator(_folder_doc_type_from_payload)),
]


# ----------------------------
# folders endpoints
# ----------------------------


class FolderLite(SNBaseModel):
    id: str
    user_id: str
    name: str
    created: IntFromAny = None
    shared: bool | None = None

    document_count: IntFromAny = None
    template_count: IntFromAny = None
    folder_count: IntFromAny = None

    team_name: str | None = None
    team_id: str | None = None
    team_type: str | None = None


class GetFoldersResponseLite(SNBaseModel):
    id: str
    created: IntFromAny = None
    name: str
    user_id: str
    parent_id: str | None = None
    system_folder: bool | None = None
    shared: bool | None = None

    folders: list[FolderLite] = Field(default_factory=list)

    total_documents: IntFromAny = None


class GetFolderByIdResponseLite(SNBaseModel):
    id: str
    created: IntFromAny = None
    name: str
    user_id: str
    parent_id: str | None = None
    system_folder: bool | None = None
    shared: bool | None = None

    # subfolders (if needed — can be typed)
    folders: list[dict[str, Any]] | None = None

    total_documents: IntFromAny = None
    documents: list[FolderDocLite] = Field(default_factory=list)
