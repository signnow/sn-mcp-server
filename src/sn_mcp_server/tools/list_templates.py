"""
Template listing functions for SignNow MCP server.

This module contains functions for retrieving templates and template groups
from the SignNow API and converting them to simplified formats for MCP tools.
"""

from fastmcp import Context

from signnow_client import SignNowAPIClient

from .models import TemplateSummary, TemplateSummaryList


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

    # Process root folder
    await ctx.report_progress(progress=progress, total=total, message="Processing root folder")
    progress += 1

    root_folder = folders_response
    if hasattr(root_folder, "documents") and root_folder.documents:
        for doc in root_folder.documents:
            # Check if document is a template
            if doc.get("template", False):
                # Extract role names from roles array
                role_names = []
                if doc.get("roles"):
                    role_names = [role.get("name", "") for role in doc["roles"] if role.get("name")]

                all_templates.append(
                    TemplateSummary(
                        id=doc["id"],
                        name=doc.get("document_name", doc.get("name", "")),
                        entity_type="template",
                        folder_id=root_folder.id,
                        last_updated=int(doc.get("updated", 0)) if doc.get("updated") else 0,
                        is_prepared=True,  # Default to True for individual templates
                        roles=role_names,
                    )
                )

    # Process all subfolders
    for folder in folders_response.folders:
        await ctx.report_progress(progress=progress, total=total, message="Processing subfolder {folder.name}")
        progress += 1

        try:
            # Get folder content with entity_type='template'
            folder_content = client.get_folder_by_id(token, folder.id, entity_type="template")

            if folder_content.documents:
                for doc in folder_content.documents:
                    # Check if document is a template
                    if doc.get("template", False):
                        # Extract role names from roles array
                        role_names = []
                        if doc.get("roles"):
                            role_names = [role.get("name", "") for role in doc["roles"] if role.get("name")]

                        all_templates.append(
                            TemplateSummary(
                                id=doc["id"],
                                name=doc.get("document_name", doc.get("name", "")),
                                entity_type="template",
                                folder_id=folder.id,
                                last_updated=int(doc.get("updated", 0)) if doc.get("updated") else 0,
                                is_prepared=True,  # Default to True for individual templates
                                roles=role_names,
                            )
                        )
        except Exception:
            # Skip folders that can't be accessed
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
