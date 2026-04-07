---
name: signnow101
description: SignNow entity types and MCP tool reference. Load this skill whenever the agent needs to interact with SignNow via MCP tools — including listing, sending, signing, checking status, or working with documents, templates, or groups. Also load when the agent is unsure which entity type or tool applies to the user's request. Do NOT load for general questions about e-signatures that do not involve the SignNow MCP tools.
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

