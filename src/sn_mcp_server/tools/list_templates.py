"""
Template listing functions for SignNow MCP server.

This module contains functions for retrieving templates and template groups
from the SignNow API and converting them to simplified formats for MCP tools.
"""

from fastmcp import Context

from signnow_client import SignNowAPIClient
from signnow_client.models.folders_lite import DocumentItemLite, TemplateItemLite

from .models import TemplateSummary, TemplateSummaryList
from .utils import extract_role_names


async def _list_all_templates(ctx: Context, token: str, client: SignNowAPIClient) -> TemplateSummaryList:
    """Get all templates and template groups from all folders.

    This function combines both individual templates and template groups into a single response.
    Individual templates are marked with entity_type='template' and template groups with entity_type='template_group'.

    Note: Individual templates are deprecated. For new implementations, prefer using template groups
    which are more feature-rich and actively maintained.

    Args:
        ctx: FastMCP context object
        token: Access token for SignNow API
        client: SignNow API client instance

    Returns:
        TemplateSummaryList with all templates and template groups combined
    """
    await ctx.report_progress(progress=0, message="Selecting all folders")

    # Get all folders first
    folders_response = client.get_folders(token)

    # Calculate total progress steps: root folder + subfolders + template groups
    total = len(folders_response.folders) + 2  # +1 for root folder, +1 for template groups
    progress = 1

    all_templates = []

    # Process root folder using get_folder_by_id (same approach as subfolders)
    await ctx.report_progress(progress=progress, total=total, message="Processing root folder")
    progress += 1

    try:
        root_folder_content = client.get_folder_by_id(token, folders_response.id, entity_type="template")

        if root_folder_content.documents:
            for doc in root_folder_content.documents:
                # Process TemplateItemLite (entity_type="template" returns these)
                if isinstance(doc, TemplateItemLite):
                    all_templates.append(
                        TemplateSummary(
                            id=doc.id,
                            name=doc.document_name or "",
                            entity_type="template",
                            folder_id=folders_response.id,
                            last_updated=int(doc.updated) if doc.updated else 0,
                            is_prepared=True,  # Default to True for individual templates
                            roles=[],  # TemplateItemLite doesn't have roles field
                        )
                    )
                # Process DocumentItemLite with template=True (if any)
                elif isinstance(doc, DocumentItemLite) and doc.template:
                    role_names = extract_role_names(doc.roles if isinstance(doc.roles, list) else None)
                    all_templates.append(
                        TemplateSummary(
                            id=doc.id,
                            name=doc.document_name or "",
                            entity_type="template",
                            folder_id=folders_response.id,
                            last_updated=int(doc.updated) if doc.updated else 0,
                            is_prepared=True,  # Default to True for individual templates
                            roles=role_names,
                        )
                    )
    except (ValueError, KeyError, AttributeError):
        # Skip root folder if it can't be accessed
        pass

    # Process all subfolders
    for folder in folders_response.folders:
        await ctx.report_progress(progress=progress, total=total, message=f"Processing subfolder {folder.name}")
        progress += 1

        try:
            # Get folder content with entity_type='template'
            folder_content = client.get_folder_by_id(token, folder.id, entity_type="template")

            if folder_content.documents:
                for doc in folder_content.documents:
                    # Process TemplateItemLite (entity_type="template" returns these)
                    if isinstance(doc, TemplateItemLite):
                        all_templates.append(
                            TemplateSummary(
                                id=doc.id,
                                name=doc.document_name or "",
                                entity_type="template",
                                folder_id=folder.id,
                                last_updated=int(doc.updated) if doc.updated else 0,
                                is_prepared=True,  # Default to True for individual templates
                                roles=[],  # TemplateItemLite doesn't have roles field
                            )
                        )
                    # Process DocumentItemLite with template=True (if any)
                    elif isinstance(doc, DocumentItemLite) and doc.template:
                        role_names = extract_role_names(doc.roles if isinstance(doc.roles, list) else None)
                        all_templates.append(
                            TemplateSummary(
                                id=doc.id,
                                name=doc.document_name or "",
                                entity_type="template",
                                folder_id=folder.id,
                                last_updated=int(doc.updated) if doc.updated else 0,
                                is_prepared=True,  # Default to True for individual templates
                                roles=role_names,
                            )
                        )
        except (ValueError, KeyError, AttributeError):
            # Skip folders that can't be accessed
            # Log specific error types but continue processing other folders
            continue

    # Get template groups
    await ctx.report_progress(progress=progress, total=total, message="Processing template groups")
    progress += 1

    # Use the client to get document template groups - now returns validated model
    full_response = client.get_document_template_groups(token, limit=50)

    # Convert to simplified structure
    for template_group in full_response.document_group_templates:
        # Collect all unique roles from all templates in the group
        all_roles = set()
        for template in template_group.templates:
            all_roles.update(template.get("roles", []))

        template_summary = TemplateSummary(
            id=template_group.template_group_id,
            name=template_group.template_group_name,
            entity_type="template_group",
            folder_id=template_group.folder_id,
            last_updated=template_group.last_updated,
            is_prepared=template_group.is_prepared,
            roles=list(all_roles),
        )
        all_templates.append(template_summary)

    return TemplateSummaryList(templates=all_templates, total_count=len(all_templates))
