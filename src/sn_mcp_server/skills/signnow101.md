---
name: signnow101
description: SignNow entity types and MCP tool reference. Load this skill whenever the agent needs to interact with SignNow via MCP tools — including uploading, listing, sending, signing, checking status, or working with documents, templates, or groups. Also load when the agent is unsure which entity type or tool applies to the user's request. Do NOT load for general questions about e-signatures that do not involve the SignNow MCP tools.
---

# SignNow 101 — Concepts Reference

## 1. Entity Types Glossary

| Entity             | Generation | Description                                                                                              |
|--------------------|------------|----------------------------------------------------------------------------------------------------------|
| **Document Group** | Modern     | An ordered collection of one or more Documents sent as a single signing workflow.                        |
| **Template Group** | Modern     | A reusable blueprint for Document Groups. Cloned into a Document Group when a signing flow is started.   |
| **Document**       | Legacy     | A single uploaded file. Still fully supported; many users have large libraries of legacy documents.      |
| **Template**       | Legacy     | A reusable blueprint for a single Document. Cloned into a Document when a signing flow is started.       |

## 2. Modern vs. Legacy Entities

SignNow has two generations of entities. **Always prefer modern entities**, but legacy entities remain fully supported because users have large existing libraries of them.

| Concept            | Legacy entity    | Modern equivalent          |
|--------------------|------------------|----------------------------|
| Single document    | Document         | Document Group (1 doc)     |
| Reusable blueprint | Template         | Template Group             |
| Bulk workflow      | —                | Document Group (N docs)    |

**Decision rule:**
- If the user refers to a **document group** or has a `document_group_id` → use Document Group tools.
- If the user refers to a **template group** or has a template group ID → use Template Group tools (`create_from_template` with group).
- If the user has a plain `document_id` or `template_id` → use legacy Document/Template tools.
- When auto-detecting entity type from an ID, try `get_document_group` first, fall back to `get_document`.


## 3. Upload Document Flow

When a user wants to upload a document to SignNow:

1. **Ask for the file.** The user provides one of:
   - An `@`-attached file (MCP resource) — preferred when the client supports it
   - A local file path (e.g. `~/Documents/contract.pdf`)
   - A public URL to the file

2. **Optional: ask for a custom name.** If the user hasn’t specified how the document should be named in SignNow,
   you may ask — but defaulting to the original filename is fine for most cases.

3. **Upload.** Call `upload_document` with `resource_uri`, `file_path`, or `file_url` (and optionally `filename`).

4. **After upload succeeds, ask what the user wants to do next:**

   | User intent | What to do |
   |-------------|------------|
   | "I want to sign it myself" | Call `send_invite` with the user as recipient, then call `get_signing_link` to get a link the user can open to sign. |
   | "Send it for someone else to sign (freeform)" | Ask for the recipient's email, then call `send_invite` with that email as recipient. See section 4.1 — **offer a preview via `view_document` before sending** unless the user has already confirmed. |
   | "Prepare a role-based invite" | Call `create_embedded_sending` to get a link the user can open in SignNow to prepare fields and roles. |
   | "Turn it into a template" | Inform the user they can use the document ID with SignNow’s template creation features. Call `create_embedded_editor` to get a link the user can open to prepare the template. |

5. **If the user doesn’t specify intent,** default to asking: *“What would you like to do with this document?”* and present the four options above.
## 4. Sending for Signing

### 4.1 Preview Before Sending

When the user asks to send a document or document group for signing, the agent **MUST** offer to preview the document first — unless the user has already explicitly confirmed they want to send without reviewing.

| Condition | Action |
|-----------|--------|
| User message already contains explicit send intent (e.g., includes recipient email AND "send now" / "go ahead" / "skip preview") | Skip preview offer — proceed directly to `send_invite` or `send_invite_from_template` |
| User has not confirmed send intent | Offer preview: *"Would you like to preview the document before sending?"* |
| User accepts preview offer | Call `view_document(entity_id=<id>)`, present the result, then ask: *"Ready to send for signing?"* |
| User declines preview offer | Proceed to collect signer information and call `send_invite` / `send_invite_from_template` |

**Rules:**

1. **MUST** offer `view_document` before sending unless the user has already confirmed.
2. **Do NOT** skip the preview offer based on assumptions — only skip when the user's message explicitly confirms.
3. This rule applies equally to `send_invite`, `send_invite_from_template`, `create_embedded_invite`, and `create_embedded_invite_from_template`.
4. The preview offer **must not block the flow** — one declined offer is enough; do not re-ask.

### 4.2 Signing Link Etiquette

When the user requests a signing link:

1. Call `get_signing_link(entity_id=<id>)` and return the link to the user.
2. After returning the link, suggest: *"Would you like me to also send a signing invite by email?"*
3. **NEVER** auto-send an invite after generating a signing link. Wait for explicit user confirmation.
4. If user confirms → call `send_invite`. If user declines → do nothing further.