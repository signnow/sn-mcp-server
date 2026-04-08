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
   | "Send it for someone else to sign (freeform)" | Ask for the recipient’s email, then call `send_invite` with that email as recipient. |
   | "Prepare a role-based invite" | Call `create_embedded_sending` to get a link the user can open in SignNow to prepare fields and roles. |
   | "Turn it into a template" | Inform the user they can use the document ID with SignNow’s template creation features. Call `create_embedded_editor` to get a link the user can open to prepare the template. |

5. **If the user doesn’t specify intent,** default to asking: *“What would you like to do with this document?”* and present the four options above.
