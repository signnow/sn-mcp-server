import json
import time
from fastmcp import Context
from typing import Dict, List, Optional
from fastmcp import FastMCP
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from fastmcp.server.dependencies import get_http_headers
from ..token_provider import TokenProvider
from signnow_client import (
    Thumbnail,
    Template,
    DocumentGroupTemplate,
    DocumentGroupTemplatesResponse,
    SignNowAPIClient
)
from .models import (
    TemplateSummary,
    TemplateSummaryList,
    SimplifiedDocumentGroupDocument,
    SimplifiedDocumentGroup,
    SimplifiedDocumentGroupsResponse,
    InviteRecipient,
    InviteOrder,
    SendInviteResponse,
    EmbeddedInviteOrder,
    CreateEmbeddedInviteResponse,
    CreateEmbeddedEditorResponse,
    CreateEmbeddedSendingResponse,
    CreateFromTemplateRequest,
    CreateFromTemplateResponse,
    SendInviteFromTemplateResponse,
    CreateEmbeddedSendingFromTemplateResponse,
    CreateEmbeddedInviteFromTemplateResponse,
    DocumentGroupStatusAction,
    DocumentGroupStatusStep,
    InviteStatus
)


def bind(mcp, cfg):
    # Initialize token provider
    token_provider = TokenProvider()

    @mcp.tool(
        name="list_templates",
        description="Get simplified list of all templates from all folders (DEPRECATED: prefer list_template_groups for newer template groups)",
        tags=["template", "list", "deprecated"]
    )
    def list_templates(ctx: Context) -> TemplateSummaryList:
        """Get all templates from all folders including root folder.
        
        Note: This tool retrieves individual templates which are deprecated.
        For new implementations, prefer using list_template_groups which works with
        modern template groups that are more feature-rich and actively maintained.
        Individual templates are still supported but may be removed in future versions.
        """
        from signnow_client import SignNowAPIClient
        
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")
        
        try:
            client = SignNowAPIClient(token_provider.signnow_config)
            
            # Get all folders first
            folders_response = client.get_folders(token)
            
            all_templates = []
            
            # Process root folder
            root_folder = folders_response
            if hasattr(root_folder, 'documents') and root_folder.documents:
                for doc in root_folder.documents:
                    # Check if document is a template
                    if doc.get('template', False):
                        # Extract role names from roles array
                        role_names = []
                        if doc.get('roles'):
                            role_names = [role.get('name', '') for role in doc['roles'] if role.get('name')]
                        
                        all_templates.append(
                            TemplateSummary(
                                id=doc['id'],
                                name=doc.get('document_name', doc.get('name', '')),
                                folder_id=root_folder.id,
                                last_updated=int(doc.get('updated', 0)) if doc.get('updated') else 0,
                                is_prepared=True,  # Default to True for individual templates
                                roles=role_names
                            )
                        )
            
            # Process all subfolders
            for folder in folders_response.folders:
                try:
                    # Get folder content with entity_type='template'
                    folder_content = client.get_folder_by_id(
                        token, 
                        folder.id, 
                        entity_type='template'
                    )
                    
                    if folder_content.documents:
                        for doc in folder_content.documents:
                            # Check if document is a template
                            if doc.get('template', False):
                                # Extract role names from roles array
                                role_names = []
                                if doc.get('roles'):
                                    role_names = [role.get('name', '') for role in doc['roles'] if role.get('name')]
                                
                                all_templates.append(
                                    TemplateSummary(
                                        id=doc['id'],
                                        name=doc.get('document_name', doc.get('name', '')),
                                        folder_id=folder.id,
                                        last_updated=int(doc.get('updated', 0)) if doc.get('updated') else 0,
                                        is_prepared=True,  # Default to True for individual templates
                                        roles=role_names
                                    )
                                )
                except Exception as e:
                    # Skip folders that can't be accessed
                    continue
            
            return TemplateSummaryList(
                templates=all_templates,
                total_count=len(all_templates)
            )
            
        except Exception as e:
            raise ValueError(f"Error getting templates: {str(e)}")

    @mcp.tool(
        name="list_template_groups",
        description="Get simplified list of template groups with basic information",
        tags=["template_group", "list"]
    )
    def list_template_groups(ctx: Context) -> TemplateSummaryList:
        """Provide simplified list of templates with basic fields."""
        from signnow_client import SignNowAPIClient
        
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")

        try:
            # Use the client to get document template groups - now returns validated model
            client = SignNowAPIClient(token_provider.signnow_config)
            full_response = client.get_document_template_groups(token, limit=50)
            
            # Преобразуем в упрощенную структуру
            templates = []
            for template_group in full_response.document_group_templates:
                # Собираем все уникальные роли из всех шаблонов в группе
                all_roles = set()
                for template in template_group.templates:
                    all_roles.update(template.get("roles", []))
                
                template_summary = TemplateSummary(
                    id=template_group.template_group_id,
                    name=template_group.template_group_name,
                    folder_id=template_group.folder_id,
                    last_updated=template_group.last_updated,
                    is_prepared=template_group.is_prepared,
                    roles=list(all_roles)
                )
                templates.append(template_summary)
            
            return TemplateSummaryList(
                templates=templates,
                total_count=full_response.document_group_template_total_count
            )
        except ValueError as e:
            raise ValueError(f"Error getting templates: {str(e)}")

    @mcp.tool(
        name="list_document_groups",
        description="Get simplified list of document groups with basic information",
        tags=["document_group", "list"]
    )
    def list_document_groups(ctx: Context, limit: int = 50, offset: int = 0) -> SimplifiedDocumentGroupsResponse:
        """Provide simplified list of document groups with basic fields.
        
        Args:
            limit: Maximum number of document groups to return (default: 50, max: 50)
            offset: Number of document groups to skip for pagination (default: 0)
        """
        from signnow_client import SignNowAPIClient
        
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")

        try:
            # Use the client to get document groups - API already applies limit and offset
            client = SignNowAPIClient(token_provider.signnow_config)
            full_response = client.get_document_groups(token, limit=limit, offset=offset)
            
            # Convert to simplified models for MCP tools
            simplified_groups = []
            for group in full_response.document_groups:
                simplified_docs = []
                for doc in group.documents:
                    simplified_doc = SimplifiedDocumentGroupDocument(
                        id=doc.id,
                        name=doc.name,
                        roles=doc.roles
                    )
                    simplified_docs.append(simplified_doc)
                
                simplified_group = SimplifiedDocumentGroup(
                    last_updated=group.last_updated,
                    group_id=group.group_id,
                    group_name=group.group_name,
                    invite_id=group.invite_id,
                    invite_status=group.invite_status,
                    documents=simplified_docs
                )
                simplified_groups.append(simplified_group)
            
            # Use the total count from API response, not the length of current page
            return SimplifiedDocumentGroupsResponse(
                document_groups=simplified_groups,
                document_group_total_count=full_response.document_group_total_count
            )
        except ValueError as e:
            raise ValueError(f"Error getting document groups: {str(e)}")

    def _send_document_group_field_invite(client, token, entity_id, orders, document_group):
        """Private function to send document group field invite."""
        from signnow_client import CreateFieldInviteRequest, FieldInviteStep, FieldInviteAction, FieldInviteEmail
        
        # Convert orders to field invite steps
        invite_steps = []
        for order_info in orders:
            actions = []
            invite_emails = []
            
            for recipient in order_info.recipients:
                # Create FieldInviteEmail for each recipient
                invite_email = FieldInviteEmail(
                    email=recipient.email,
                    subject=recipient.subject,
                    message=recipient.message
                )
                invite_emails.append(invite_email)
                
                # Create FieldInviteAction only for documents with matching roles
                for document in document_group.documents:
                    # Only create action if the document has the required role
                    if recipient.role_name in document.roles:
                        # Only include redirect_target if redirect_uri is provided
                        action_data = {
                            "email": recipient.email,
                            "role_name": recipient.role_name,
                            "action": recipient.action,
                            "document_id": document.id,  # Use actual document ID from the group
                            "redirect_uri": recipient.redirect_uri,
                            "decline_redirect_uri": recipient.decline_redirect_uri,
                            "close_redirect_uri": recipient.close_redirect_uri
                        }
                        
                        # Only add redirect_target if redirect_uri is provided and not empty
                        if recipient.redirect_uri and recipient.redirect_uri.strip():
                            action_data["redirect_target"] = recipient.redirect_target
                        
                        action = FieldInviteAction(**action_data)
                        actions.append(action)
            
            step = FieldInviteStep(
                order=order_info.order,
                invite_emails=invite_emails,  # All recipients' emails with their subjects and messages
                invite_actions=actions
            )
            invite_steps.append(step)
        
        request_data = CreateFieldInviteRequest(
            invite_steps=invite_steps,
            cc=[],  # TODO: Add CC support if needed
            cc_subject=None,
            cc_message=None
        )
        
        response = client.create_field_invite(token, entity_id, request_data)
        
        return SendInviteResponse(
            invite_id=response.id,
            invite_entity="document_group"
        )

    def _send_document_field_invite(client, token, entity_id, orders):
        """Private function to send document field invite."""
        from signnow_client import CreateDocumentFieldInviteRequest, DocumentFieldInviteRecipient
        
        # Convert orders to document field invite recipients
        recipients = []
        for order_info in orders:
            for recipient in order_info.recipients:
                # Create DocumentFieldInviteRecipient for each recipient
                recipient_data = {
                    "email": recipient.email,
                    "role": recipient.role_name,
                    "order": order_info.order,
                    "redirect_uri": recipient.redirect_uri,
                    "decline_by_signature": "1" if recipient.decline_redirect_uri else "0",
                    "subject": recipient.subject,
                    "message": recipient.message
                }
                
                # Only add redirect_target if redirect_uri is provided and not empty
                if recipient.redirect_uri and recipient.redirect_uri.strip():
                    recipient_data["redirect_target"] = recipient.redirect_target
                
                doc_recipient = DocumentFieldInviteRecipient(**recipient_data)
                recipients.append(doc_recipient)
        
        # Create document field invite request
        request_data = CreateDocumentFieldInviteRequest(
            document_id=entity_id,
            to=recipients
        )
        
        response = client.create_document_field_invite(token, entity_id, request_data)
        
        return SendInviteResponse(
            invite_id=response.status,  # Document field invite returns status, not id
            invite_entity="document"
        )

    def _send_invite(
        entity_id: str, 
        entity_type: Optional[str] = None,
        orders: List[InviteOrder] = []
    ) -> SendInviteResponse:
        """Private function to send invite to sign a document or document group.
        
        Args:
            entity_id: ID of the document or document group
            entity_type: Type of entity: 'document' or 'document_group' (optional)
            orders: List of orders with recipients
            
        Returns:
            SendInviteResponse with invite ID and entity type
        """
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")

        # Initialize client first
        client = SignNowAPIClient(token_provider.signnow_config)
        
        # Determine entity type if not provided
        document_group = None  # Store document group if found during auto-detection
        
        if not entity_type:
            # Try to determine entity type by attempting to get document group first (higher priority)
            try:
                document_group = client.get_document_group(token, entity_id)
                entity_type = "document_group"
            except:
                # If document group not found, try document
                try:
                    client.get_document(token, entity_id)
                    entity_type = "document"
                except:
                    raise ValueError(f"Entity with ID {entity_id} not found as either document group or document")
        
        if entity_type == "document_group":
            # Send document group field invite
            # Get the document group if we don't have it yet
            if not document_group:
                document_group = client.get_document_group(token, entity_id)
            
            return _send_document_group_field_invite(client, token, entity_id, orders, document_group)
        else:
            # Send document field invite
            return _send_document_field_invite(client, token, entity_id, orders)

    @mcp.tool(
        name="send_invite",
        description="Send invite to sign a document or document group",
        tags=["send_invite", "document", "document_group", "sign", "workflow"]
    )
    def send_invite(
        ctx: Context, 
        entity_id: str, 
        entity_type: Optional[str] = None,
        orders: List[InviteOrder] = []
    ) -> SendInviteResponse:
        """Send invite to sign a document or document group.
        
        Args:
            entity_id: ID of the document or document group
            entity_type: Type of entity: 'document' or 'document_group' (optional)
            orders: List of orders with recipients
            
        Returns:
            SendInviteResponse with invite ID and entity type
        """
        return _send_invite(entity_id, entity_type, orders)

    def _create_document_group_embedded_invite(client, token, entity_id, orders, document_group):
        """Private function to create document group embedded invite."""
        from signnow_client import CreateEmbeddedInviteRequest as SignNowEmbeddedInviteRequest, EmbeddedInviteStep, EmbeddedInviteSigner
        
        # Convert orders to embedded invite steps
        invite_steps = []
        for order_info in orders:
            signers = []
            for recipient in order_info.recipients:
                # Create EmbeddedInviteSigner for each recipient
                signer_data = {
                    "email": recipient.email,
                    "auth_method": recipient.auth_method,
                    "first_name": recipient.first_name,
                    "last_name": recipient.last_name,
                    "language": "en",  # Default language
                    "required_preset_signature_name": None,
                    "redirect_uri": recipient.redirect_uri,
                    "decline_redirect_uri": recipient.decline_redirect_uri,
                    "close_redirect_uri": recipient.close_redirect_uri,
                    "delivery_type": recipient.delivery_type,
                    "subject": recipient.subject,
                    "message": recipient.message,
                    "documents": [{"id": doc.id, "role": recipient.role_name, "action": recipient.action} for doc in document_group.documents]
                }
                
                # Only add redirect_target if redirect_uri is provided and not empty
                if recipient.redirect_uri and recipient.redirect_uri.strip():
                    signer_data["redirect_target"] = recipient.redirect_target
                
                signer = EmbeddedInviteSigner(**signer_data)
                signers.append(signer)
            
            step = EmbeddedInviteStep(
                order=str(order_info.order),
                signers=signers
            )
            invite_steps.append(step)
        
        request_data = SignNowEmbeddedInviteRequest(
            invites=invite_steps,
            sign_as_merged="1"  # Send as merged document group
        )
        
        response = client.create_embedded_invite(token, entity_id, request_data)
        
        # Generate links for recipients with delivery_type='link'
        recipient_links = []
        for order_info in orders:
            for recipient in order_info.recipients:
                if recipient.delivery_type == "link":
                    try:
                        from signnow_client import GenerateEmbeddedInviteLinkRequest
                        link_request = GenerateEmbeddedInviteLinkRequest(
                            email=recipient.email,
                            auth_method=recipient.auth_method
                        )
                        link_response = client.generate_embedded_invite_link(token, entity_id, response.data.id, link_request)
                        recipient_links.append({
                            "role": recipient.role_name,
                            "link": link_response.data.link
                        })
                    except Exception as e:
                        # If link generation fails, still return the role but with error message
                        recipient_links.append({
                            "role": recipient.role_name,
                            "link": f"Error generating link: {str(e)}"
                        })
        
        return CreateEmbeddedInviteResponse(
            invite_id=response.data.id,
            invite_entity="document_group",
            recipient_links=recipient_links
        )

    def _create_document_embedded_invite(client, token, entity_id, orders):
        """Private function to create document embedded invite."""
        from signnow_client import CreateDocumentEmbeddedInviteRequest, DocumentEmbeddedInvite, DocumentEmbeddedInviteSignature
        
        # Convert orders to document embedded invite
        invites = []
        for order_info in orders:
            signers = []
            for recipient in order_info.recipients:
                # Create DocumentEmbeddedInvite for each recipient
                invite_data = {
                    "email": recipient.email,
                    "auth_method": recipient.auth_method,
                    "first_name": recipient.first_name,
                    "last_name": recipient.last_name,
                    "language": "en",  # Default language
                    "required_preset_signature_name": None,
                    "redirect_uri": recipient.redirect_uri,
                    "decline_redirect_uri": recipient.decline_redirect_uri,
                    "close_redirect_uri": recipient.close_redirect_uri,
                    "delivery_type": recipient.delivery_type,
                    "subject": recipient.subject,
                    "message": recipient.message,
                    "documents": [{"id": entity_id, "role": recipient.role_name, "action": recipient.action}]
                }
                
                # Only add redirect_target if redirect_uri is provided and not empty
                if recipient.redirect_uri and recipient.redirect_uri.strip():
                    invite_data["redirect_target"] = recipient.redirect_target
                
                doc_invite = DocumentEmbeddedInvite(**invite_data)
                signers.append(doc_invite)
            
            invites.append({
                "order": str(order_info.order),
                "signers": signers
            })
        
        request_data = CreateDocumentEmbeddedInviteRequest(
            invites=invites
        )
        
        response = client.create_document_embedded_invite(token, entity_id, request_data)
        
        # Generate links for recipients with delivery_type='link'
        recipient_links = []
        for order_info in orders:
            for recipient in order_info.recipients:
                if recipient.delivery_type == "link":
                    try:
                        from signnow_client import GenerateDocumentEmbeddedInviteLinkRequest
                        link_request = GenerateDocumentEmbeddedInviteLinkRequest(
                            email=recipient.email,
                            auth_method=recipient.auth_method
                        )
                        link_response = client.generate_document_embedded_invite_link(token, entity_id, response.data.id, link_request)
                        recipient_links.append({
                            "role": recipient.role_name,
                            "link": link_response.data.link
                        })
                    except Exception as e:
                        # If link generation fails, still return the role but with error message
                        recipient_links.append({
                            "role": recipient.role_name,
                            "link": f"Error generating link: {str(e)}"
                        })
        
        return CreateEmbeddedInviteResponse(
            invite_id=response.data.id,
            invite_entity="document",
            recipient_links=recipient_links
        )

    @mcp.tool(
        name="create_embedded_invite",
        description="Create embedded invite for signing a document or document group",
        tags=["send_invite", "document", "document_group", "sign", "embedded", "workflow"]
    )
    def create_embedded_invite(
        ctx: Context, 
        entity_id: str, 
        entity_type: Optional[str] = None,
        orders: List[EmbeddedInviteOrder] = []
    ) -> CreateEmbeddedInviteResponse:
        """Create embedded invite for signing a document or document group.
        
        Args:
            entity_id: ID of the document or document group
            entity_type: Type of entity: 'document' or 'document_group' (optional)
            orders: List of orders with recipients
            
        Returns:
            CreateEmbeddedInviteResponse with invite ID and entity type
        """
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")

        # Initialize client first
        client = SignNowAPIClient(token_provider.signnow_config)
        
        # Determine entity type if not provided
        document_group = None  # Store document group if found during auto-detection
        
        if not entity_type:
            # Try to determine entity type by attempting to get document group first (higher priority)
            try:
                document_group = client.get_document_group(token, entity_id)
                entity_type = "document_group"
            except:
                # If document group not found, try document
                try:
                    client.get_document(token, entity_id)
                    entity_type = "document"
                except:
                    raise ValueError(f"Entity with ID {entity_id} not found as either document group or document")
        
        try:
            # Validate orders
            if not orders:
                raise ValueError("At least one order with recipients is required")
            
            if entity_type == "document_group":
                # Create document group embedded invite
                # Get the document group if we don't have it yet
                if not document_group:
                    document_group = client.get_document_group(token, entity_id)
                
                return _create_document_group_embedded_invite(client, token, entity_id, orders, document_group)
            else:
                # Create document embedded invite
                return _create_document_embedded_invite(client, token, entity_id, orders)
                
        except Exception as e:
            raise ValueError(f"Error creating embedded invite: {str(e)}")


    def _create_document_group_embedded_editor(client, token, entity_id, redirect_uri, redirect_target, link_expiration):
        """Private function to create document group embedded editor."""
        from signnow_client import CreateEmbeddedEditorRequest as SignNowEmbeddedEditorRequest
        
        request_data = SignNowEmbeddedEditorRequest(
            redirect_uri=redirect_uri,
            redirect_target=redirect_target,
            link_expiration=link_expiration
        )
        
        response = client.create_embedded_editor(token, entity_id, request_data)
        
        return CreateEmbeddedEditorResponse(
            editor_id=response.data.id,
            editor_entity="document_group",
            editor_url=response.data.url
        )

    def _create_document_embedded_editor(client, token, entity_id, redirect_uri, redirect_target, link_expiration):
        """Private function to create document embedded editor."""
        from signnow_client import CreateDocumentEmbeddedEditorRequest
        
        request_data = CreateDocumentEmbeddedEditorRequest(
            redirect_uri=redirect_uri,
            redirect_target=redirect_target,
            link_expiration=link_expiration
        )
        
        response = client.create_document_embedded_editor(token, entity_id, request_data)
        
        return CreateEmbeddedEditorResponse(
            editor_id=response.data.id,
            editor_entity="document",
            editor_url=response.data.url
        )

    def _create_document_group_embedded_sending(client, token, entity_id, redirect_uri, redirect_target, link_expiration, sending_type):
        """Private function to create document group embedded sending."""
        from signnow_client import CreateEmbeddedSendingRequest as SignNowEmbeddedSendingRequest
        
        request_data = SignNowEmbeddedSendingRequest(
            redirect_uri=redirect_uri,
            redirect_target=redirect_target,
            link_expiration=link_expiration,
            type=sending_type
        )
        
        response = client.create_embedded_sending(token, entity_id, request_data)
        
        return CreateEmbeddedSendingResponse(
            sending_id=response.data.id,
            sending_entity="document_group",
            sending_url=response.data.url
        )

    def _create_document_embedded_sending(client, token, entity_id, redirect_uri, redirect_target, link_expiration, sending_type):
        """Private function to create document embedded sending."""
        from signnow_client import CreateDocumentEmbeddedSendingRequest
        
        # Map sending type to entity type for documents BEFORE making the request
        if sending_type == "send-invite":
            mapped_type = "invite"
        else:  # manage or edit
            mapped_type = "document"
        
        request_data = CreateDocumentEmbeddedSendingRequest(
            redirect_uri=redirect_uri,
            redirect_target=redirect_target,
            link_expiration=link_expiration,
            type=mapped_type
        )
        
        response = client.create_document_embedded_sending(token, entity_id, request_data)
        
        return CreateEmbeddedSendingResponse(
            sending_id=response.data.id,
            sending_entity="document",
            sending_url=response.data.url
        )

    @mcp.tool(
        name="create_embedded_sending",
        description="Create embedded sending for managing, editing, or sending invites for a document or document group",
        tags=["edit", "document", "document_group", "send_invite", "embedded", "workflow"]
    )
    def create_embedded_sending(
        ctx: Context, 
        entity_id: str, 
        entity_type: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        redirect_target: Optional[str] = None,
        link_expiration: Optional[int] = None,
        type: Optional[str] = "manage"
    ) -> CreateEmbeddedSendingResponse:
        """Create embedded sending for managing, editing, or sending invites for a document or document group.
        
        Args:
            entity_id: ID of the document or document group
            entity_type: Type of entity: 'document' or 'document_group' (optional)
            redirect_uri: Optional redirect URI for the sending link
            redirect_target: Optional redirect target for the sending link
            link_expiration: Optional number of days for the sending link to expire (14-45)
            type: Specifies the sending step: 'manage' (default), 'edit', 'send-invite'
            
        Returns:
            CreateEmbeddedSendingResponse with sending ID, entity type, and URL
        """
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")

        # Initialize client first
        client = SignNowAPIClient(token_provider.signnow_config)
        
        # Determine entity type if not provided
        document_group = None  # Store document group if found during auto-detection
        
        if not entity_type:
            # Try to determine entity type by attempting to get document group first (higher priority)
            try:
                document_group = client.get_document_group(token, entity_id)
                entity_type = "document_group"
            except:
                # If document group not found, try document
                try:
                    client.get_document(token, entity_id)
                    entity_type = "document"
                except:
                    raise ValueError(f"Entity with ID {entity_id} not found as either document group or document")
        
        try:
            if entity_type == "document_group":
                # Create document group embedded sending
                # Get the document group if we don't have it yet
                if not document_group:
                    document_group = client.get_document_group(token, entity_id)
                
                return _create_document_group_embedded_sending(client, token, entity_id, redirect_uri, redirect_target, link_expiration, type)
            else:
                # Create document embedded sending
                return _create_document_embedded_sending(client, token, entity_id, redirect_uri, redirect_target, link_expiration, type)
                
        except Exception as e:
            raise ValueError(f"Error creating embedded sending: {str(e)}")

    @mcp.tool(
        name="create_embedded_editor",
        description="Create embedded editor for editing a document or document group",
        tags=["edit", "document", "document_group", "embedded"]
    )
    def create_embedded_editor(
        ctx: Context, 
        entity_id: str, 
        entity_type: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        redirect_target: Optional[str] = None,
        link_expiration: Optional[int] = None
    ) -> CreateEmbeddedEditorResponse:
        """Create embedded editor for editing a document or document group.
        
        Args:
            entity_id: ID of the document or document group
            entity_type: Type of entity: 'document' or 'document_group' (optional)
            redirect_uri: Optional redirect URI for the editor link
            redirect_target: Optional redirect target for the editor link
            link_expiration: Optional number of minutes for the editor link to expire (15-43200)
            
        Returns:
            CreateEmbeddedEditorResponse with editor ID and entity type
        """
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")

        # Initialize client first
        client = SignNowAPIClient(token_provider.signnow_config)
        
        # Determine entity type if not provided
        document_group = None  # Store document group if found during auto-detection
        
        if not entity_type:
            # Try to determine entity type by attempting to get document group first (higher priority)
            try:
                document_group = client.get_document_group(token, entity_id)
                entity_type = "document_group"
            except:
                # If document group not found, try document
                try:
                    client.get_document(token, entity_id)
                    entity_type = "document"
                except:
                    raise ValueError(f"Entity with ID {entity_id} not found as either document group or document")
        
        try:
            if entity_type == "document_group":
                # Create document group embedded editor
                # Get the document group if we don't have it yet
                if not document_group:
                    document_group = client.get_document_group(token, entity_id)
                
                return _create_document_group_embedded_editor(client, token, entity_id, redirect_uri, redirect_target, link_expiration)
            else:
                # Create document embedded editor
                return _create_document_embedded_editor(client, token, entity_id, redirect_uri, redirect_target, link_expiration)
                
        except Exception as e:
            raise ValueError(f"Error creating embedded editor: {str(e)}")



    def _create_document_from_template(client, token, entity_id, name):
        """Private function to create document from template."""
        from signnow_client import CreateDocumentFromTemplateRequest
        
        # Prepare request data
        request_data = None
        if name:
            request_data = CreateDocumentFromTemplateRequest(document_name=name)
        
        # Create document from template
        response = client.create_document_from_template(token, entity_id, request_data)
        
        # Use provided name or fallback to response document_name or entity_id
        document_name = name or getattr(response, 'document_name', None) or f"Document_{response.id[:8]}"
        
        return CreateFromTemplateResponse(
            entity_id=response.id,
            entity_type="document",
            name=document_name
        )

    def _create_document_group_from_template(client, token, entity_id, name):
        """Private function to create document group from template group."""
        from signnow_client import CreateDocumentGroupFromTemplateRequest


        if not name:
            raise ValueError("name is required when creating document group from template group")
        
        # Prepare request data
        request_data = CreateDocumentGroupFromTemplateRequest(
            group_name=name
        )
        
        # Create document group from template group
        response = client.create_document_group_from_template(token, entity_id, request_data)
        
        # Extract document group ID from response data
        response_data = response.data
        if isinstance(response_data, dict) and 'unique_id' in response_data:
            created_id = response_data['unique_id']
        elif isinstance(response_data, dict) and 'id' in response_data:
            created_id = response_data['id']
        elif isinstance(response_data, dict) and 'group_id' in response_data:
            created_id = response_data['group_id']
        else:
            created_id = str(response_data.get('id', response_data.get('group_id', 'unknown')))
        
        return CreateFromTemplateResponse(
            entity_id=created_id,
            entity_type="document_group",
            name=name
        )

    def _find_template_group(entity_id: str, token: str) -> Optional[DocumentGroupTemplate]:
        """Find template group by ID.
        
        Args:
            entity_id: ID to search for
            token: Access token for authentication
            
        Returns:
            DocumentGroupTemplate if found, None otherwise
        """
        client = SignNowAPIClient(token_provider.signnow_config)
        template_groups_response = client.get_document_template_groups(token)
        template_groups = template_groups_response.document_group_templates
        
        # Look for our entity_id in the template groups
        for template_group in template_groups:
            if template_group.template_group_id == entity_id:
                return template_group
        return None

    def _create_from_template(
        entity_id: str,
        entity_type: Optional[str] = None,
        name: str = None
    ) -> CreateFromTemplateResponse:
        """Private function to create a new document or document group from an existing template or template group.
        
        Args:
            entity_id: ID of the template or template group
            entity_type: Type of entity: 'template' or 'template_group' (optional)
            name: Optional name for the new document group or document (required for template groups)
            
        Returns:
            CreateFromTemplateResponse with created entity ID, type and name
        """
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")
            
        client = SignNowAPIClient(token_provider.signnow_config)

        # Find template group if needed (for entity type detection or name extraction)
        found_template_group = None
        if not entity_type:
            found_template_group = _find_template_group(entity_id, token)
        
        # Determine entity type if not provided
        if not entity_type:
            if found_template_group:
                entity_type = "template_group"
            else:
                entity_type = "template"
        
        if entity_type == "template_group":
            
            return _create_document_group_from_template(client, token, entity_id, name)
        else:
            # Create document from template
            return _create_document_from_template(client, token, entity_id, name)
                

    @mcp.tool(
        name="create_from_template",
        description="Create a new document or document group from an existing template or template group",
        tags=["template", "template_group", "document", "document_group", "create", "workflow"]
    )
    def create_from_template(
        ctx: Context,
        entity_id: str,
        entity_type: Optional[str] = None,
        name: Optional[str] = None
    ) -> CreateFromTemplateResponse:
        """Create a new document or document group from an existing template or template group.
        
        Args:
            entity_id: ID of the template or template group
            entity_type: Type of entity: 'template' or 'template_group' (optional)
            name: Optional name for the new document group or document (required for template groups)
            folder_id: Optional ID of the folder to store the document group
            
        Returns:
            CreateFromTemplateResponse with created entity ID, type and name
        """
        return _create_from_template(entity_id, entity_type, name)



    @mcp.tool(
        name="send_invite_from_template",
        description="Create document/group from template and send invite immediately",
        tags=["template", "template_group", "document", "document_group", "send_invite", "workflow"]
    )
    def send_invite_from_template(
        ctx: Context,
        entity_id: str,
        entity_type: Optional[str] = None,
        name: str = None,
        orders: List[InviteOrder] = []
    ) -> SendInviteFromTemplateResponse:
        """Create document or document group from template and send invite immediately.
        
        This tool combines two operations:
        1. Creates a document/group from template using create_from_template
        2. Sends an invite to the created entity using send_invite
        
        Args:
            entity_id: ID of the template or template group
            entity_type: Type of entity: 'template' or 'template_group' (optional)
            name: Optional name for the new document or document group
            folder_id: Optional ID of the folder to store the document group
            orders: List of orders with recipients for the invite
            
        Returns:
            SendInviteFromTemplateResponse with created entity info and invite details
        """
        # Use private functions to avoid MCP tool call issues
        # First create document/group from template
        created_entity = _create_from_template(entity_id, entity_type, name)
        
        # Then send invite
        invite_response = _send_invite(created_entity.entity_id, created_entity.entity_type, orders)
        
        return SendInviteFromTemplateResponse(
            created_entity_id=created_entity.entity_id,
            created_entity_type=created_entity.entity_type,
            created_entity_name=created_entity.name,
            invite_id=invite_response.invite_id,
            invite_entity=invite_response.invite_entity
        )
                

    @mcp.tool(
        name="create_embedded_sending_from_template",
        description="Create document/group from template and create embedded sending immediately",
        tags=["template", "template_group", "document", "document_group", "send_invite", "embedded", "workflow"]
    )
    def create_embedded_sending_from_template(
        ctx: Context,
        entity_id: str,
        entity_type: Optional[str] = None,
        name: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        redirect_target: Optional[str] = None,
        link_expiration: Optional[int] = None,
        type: Optional[str] = None
    ) -> CreateEmbeddedSendingFromTemplateResponse:
        """Create document or document group from template and create embedded sending immediately.
        
        This tool combines two operations:
        1. Creates a document/group from template using create_from_template
        2. Creates an embedded sending for the created entity using create_embedded_sending
        
        Args:
            entity_id: ID of the template or template group
            entity_type: Type of entity: 'template' or 'template_group' (optional)
            name: Optional name for the new document or document group
            redirect_uri: Optional redirect URI after completion
            redirect_target: Optional redirect target: 'self', 'blank', or 'self' (default)
            link_expiration: Optional link expiration in days (14-45)
            type: Type of sending step: 'manage', 'edit', or 'send-invite'
            
        Returns:
            CreateEmbeddedSendingFromTemplateResponse with created entity info and embedded sending details
        """
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)

        client = SignNowAPIClient(token_provider.signnow_config)
        
        if not token:
            raise ValueError("No access token available")

        try:
            # Use private function to create from template
            created_entity = _create_from_template(entity_id, entity_type, name)
            
            if created_entity.entity_type == "document_group":
                sending_response = _create_document_group_embedded_sending(client, token, created_entity.entity_id, redirect_uri, redirect_target, link_expiration, type)
                return CreateEmbeddedSendingFromTemplateResponse(
                    created_entity_id=created_entity.entity_id,
                    created_entity_type=created_entity.entity_type,
                    created_entity_name=created_entity.name,
                    sending_id=sending_response.sending_id,
                    sending_entity=sending_response.sending_entity,
                    sending_url=sending_response.sending_url
                )
            else:
                # Create document embedded sending
                sending_response = _create_document_embedded_sending(client, token, created_entity.entity_id, redirect_uri, redirect_target, link_expiration, type)
                return CreateEmbeddedSendingFromTemplateResponse(
                    created_entity_id=created_entity.entity_id,
                    created_entity_type=created_entity.entity_type,
                    created_entity_name=created_entity.name,
                    sending_id=sending_response.sending_id,
                    sending_entity=sending_response.sending_entity,
                    sending_url=sending_response.sending_url
                )
                
        except Exception as e:
            raise ValueError(f"Error creating embedded sending from template: {str(e)}")

    @mcp.tool(
        name="create_embedded_invite_from_template",
        description="Create document/group from template and create embedded invite immediately",
        tags=["template", "template_group", "document", "document_group", "send_invite", "embedded", "workflow"]
    )
    def create_embedded_invite_from_template(
        ctx: Context,
        entity_id: str,
        entity_type: Optional[str] = None,
        name: Optional[str] = None,
        orders: List[EmbeddedInviteOrder] = []
    ) -> CreateEmbeddedInviteFromTemplateResponse:
        """Create document or document group from template and create embedded invite immediately.
        
        This tool combines two operations:
        1. Creates a document/group from template using create_from_template
        2. Creates an embedded invite for the created entity using create_embedded_invite
        
        Args:
            entity_id: ID of the template or template group
            entity_type: Type of entity: 'template' or 'template_group' (optional)
            name: Optional name for the new document or document group
            orders: List of orders with recipients for the embedded invite
            
        Returns:
            CreateEmbeddedInviteFromTemplateResponse with created entity info and embedded invite details
        """
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")

        try:
            # Use private function to create from template
            created_entity = _create_from_template(entity_id, entity_type, name)
            
            # Then create embedded invite for the created entity
            client = SignNowAPIClient(token_provider.signnow_config)
            headers = get_http_headers()
            token = token_provider.get_access_token(headers)
            
            if created_entity.entity_type == "document_group":
                # Create document group embedded invite
                document_group = client.get_document_group(token, created_entity.entity_id)
                invite_response = _create_document_group_embedded_invite(client, token, created_entity.entity_id, orders, document_group)
                return CreateEmbeddedInviteFromTemplateResponse(
                    created_entity_id=created_entity.entity_id,
                    created_entity_type=created_entity.entity_type,
                    created_entity_name=created_entity.name,
                    invite_id=invite_response.invite_id,
                    invite_entity=invite_response.invite_entity,
                    recipient_links=invite_response.recipient_links
                )
            else:
                # Create document embedded invite
                invite_response = _create_document_embedded_invite(client, token, created_entity.entity_id, orders)
                return CreateEmbeddedInviteFromTemplateResponse(
                    created_entity_id=created_entity.entity_id,
                    created_entity_type=created_entity.entity_type,
                    created_entity_name=created_entity.name,
                    invite_id=invite_response.invite_id,
                    invite_entity=invite_response.invite_entity,
                    recipient_links=invite_response.recipient_links
                )
                
        except Exception as e:
            raise ValueError(f"Error creating embedded invite from template: {str(e)}")


    def _get_document_group_status(client: SignNowAPIClient, token: str, document_group_data, document_group_id: str) -> InviteStatus:
        """
        Get document group status information.
        
        This function extracts invite_id from document group data, then gets field invite details
        and returns formatted status information.
        
        Args:
            client: SignNow API client instance
            token: Access token for authentication
            document_group_data: Document group data
            
        Returns:
            InviteStatus with invite_id, status, and steps information
            
        Raises:
            ValueError: If group not found or no invite_id found
        """
        group_response = document_group_data
        invite_id = group_response.data.invite_id
        
        if not invite_id:
            raise ValueError(f"No invite_id found for document group {document_group_id}")
        
        # Get field invite details
        invite_response = client.get_field_invite(token, document_group_id, invite_id)
        invite = invite_response.invite
        
        # Transform steps and actions to our format
        steps = []
        for step in invite.steps:
            actions = []
            for action in step.actions:
                # Only include actions with email (skip email_group actions)
                if action.email:
                    actions.append(DocumentGroupStatusAction(
                        action=action.action,
                        email=action.email,
                        document_id=action.document_id,
                        status=action.status,
                        role_name=action.role_name
                    ))
            
            steps.append(DocumentGroupStatusStep(
                status=step.status,
                order=step.order,
                actions=actions
            ))
        
        return InviteStatus(
            invite_id=invite.id,
            status=invite.status,
            steps=steps
        )


    def _get_document_status(client: SignNowAPIClient, token: str, document_data) -> InviteStatus:
        """
        Get document status information.
        
        This function extracts field_invites from document data, then transforms them
        into InviteStatus format.
        
        Args:
            client: SignNow API client instance
            token: Access token for authentication
            document_data: Document data
            
        Returns:
            InviteStatus with document field invites information
            
        Raises:
            ValueError: If document not found or no field invites found
        """
        document_response = document_data
        field_invites = document_response.field_invites
        
        if not field_invites:
            raise ValueError(f"No field invites found for document {document_id}")
        
        # Transform field_invites to InviteStatus format
        # For documents, we create a single step with all field invites as actions
        actions = []
        for field_invite in field_invites:
            # Only include field invites with email (skip email_group invites)
            if field_invite.email:
                actions.append(DocumentGroupStatusAction(
                    action="sign",  # Documents typically have sign action
                    email=field_invite.email,
                    document_id=document_response.id,
                    status=field_invite.status,
                    role_name=field_invite.role
                ))
        
        # Create a single step with all actions
        steps = []
        if actions:
            steps.append(DocumentGroupStatusStep(
                status=field_invites[0].status,  # Use first invite status as step status
                order=1,
                actions=actions
            ))
        
        # Use first field invite ID as invite_id, or generate a placeholder
        invite_id = field_invites[0].id if field_invites else f"doc_{document_id}"
        
        return InviteStatus(
            invite_id=invite_id,
            status=field_invites[0].status if field_invites else "unknown",
            steps=steps
        )

    @mcp.tool(
        name="get_invite_status",
        description="Get invite status for a document or document group",
        tags=["invite", "status", "document", "document_group", "workflow"]
    )
    def get_invite_status(
        ctx: Context,
        entity_id: str,
        entity_type: Optional[str] = None
    ) -> InviteStatus:
        """Get invite status for a document or document group.
        
        Args:
            entity_id: ID of the document or document group
            entity_type: Type of entity: 'document' or 'document_group' (optional)
            
        Returns:
            InviteStatus with invite ID, status, and steps information
        """
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")

        # Determine entity type if not provided and get entity data
        client = SignNowAPIClient(token_provider.signnow_config)
        document_group = None
        document = None
        
        if not entity_type:
            # Try to determine entity type by attempting to get document group first (higher priority)
            try:
                document_group = client.get_document_group_v2(token, entity_id)
                entity_type = "document_group"
            except:
                # If document group not found, try document
                try:
                    document = client.get_document(token, entity_id)
                    entity_type = "document"
                except:
                    raise ValueError(f"Entity with ID {entity_id} not found as either document group or document")
        else:
            # Entity type is provided, get the entity data
            if entity_type == "document_group":
                try:
                    document_group = client.get_document_group_v2(token, entity_id)
                except Exception as e:
                    raise ValueError(f"Error getting document group {entity_id}: {str(e)}")
            else:
                try:
                    document = client.get_document(token, entity_id)
                except Exception as e:
                    raise ValueError(f"Error getting document {entity_id}: {str(e)}")
        
        try:
            if entity_type == "document_group":
                # Get document group status using the already fetched data
                return _get_document_group_status(client, token, document_group, entity_id)
            else:
                # Get document status using the already fetched data
                return _get_document_status(client, token, document)
                
        except Exception as e:
            raise ValueError(f"Error getting invite status: {str(e)}")

    return mcp
