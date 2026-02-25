# Plan: Pagination for List Endpoints

**Spec:** `.specs/Spec-Pagination-List-Endpoints.md`
**Task:** Add `limit`/`offset` pagination to `list_all_templates` and `list_documents` endpoints to comply with Claude MCP Directory's 25k-token-per-tool-result limit.

---

## Phase 1: Tool Response Models (Curated DTOs)

*Add pagination metadata fields to existing response models. Pure Pydantic changes — zero logic, zero dependencies on other phases.*

- [ ] `[Tool Model]` Add pagination fields to `TemplateSummaryList`
  - **File:** `src/sn_mcp_server/tools/models.py`
  - **Logic:** Add three new fields to the existing `TemplateSummaryList` class:
    - `offset: int = Field(0, description="Number of items skipped")` 
    - `limit: int = Field(50, description="Maximum number of items in this page")`
    - `has_more: bool = Field(False, description="Whether more items exist beyond this page")`
  - Existing `templates` and `total_count` fields remain unchanged (semantics of `total_count` will shift to "total across all pages" — but the field definition itself doesn't change)

- [ ] `[Tool Model]` Add pagination fields to `SimplifiedDocumentGroupsResponse`
  - **File:** `src/sn_mcp_server/tools/models.py`
  - **Logic:** Add three new fields to the existing `SimplifiedDocumentGroupsResponse` class:
    - `offset: int = Field(0, description="Number of items skipped")`
    - `limit: int = Field(50, description="Maximum number of items in this page")`
    - `has_more: bool = Field(False, description="Whether more items exist beyond this page")`
  - Existing `document_groups` and `document_group_total_count` fields remain unchanged

- [ ] **Constraint Check:** Both models import ONLY from `pydantic`. No new imports needed. No upward imports from `sn_mcp_server.*`.

---

## Phase 2: Tool Business Logic

*Modify the two business logic functions to accept `limit`/`offset` parameters and apply post-fetch slicing. Depends on Phase 1 models being updated.*

- [ ] `[Tool Logic]` Add pagination to `_list_all_templates()`
  - **File:** `src/sn_mcp_server/tools/list_templates.py`
  - **Signature change:** `async def _list_all_templates(ctx: Context, token: str, client: SignNowAPIClient, limit: int = 50, offset: int = 0) -> TemplateSummaryList`
  - **Logic:** All existing fetch logic (folders iteration, template group fetch) remains untouched. After the existing collection loop completes and `all_templates` list is fully populated:
    1. Capture `total_count = len(all_templates)`
    2. Slice: `page = all_templates[offset : offset + limit]`
    3. Compute: `has_more = (offset + limit) < total_count`
    4. Change the final return statement to: `TemplateSummaryList(templates=page, total_count=total_count, offset=offset, limit=limit, has_more=has_more)`
  - The only changes are: (a) two new parameters in the signature, (b) three lines of slicing logic before the return, (c) updated return statement constructor args

- [ ] `[Tool Logic]` Add pagination to `_list_document_groups()`
  - **File:** `src/sn_mcp_server/tools/list_documents.py`
  - **Signature change:** `async def _list_document_groups(ctx: Context, token: str, client: SignNowAPIClient, filter: str | None = None, sortby: str | None = None, order: str | None = None, folder_id: str | None = None, expired_filter: str = "all", limit: int = 50, offset: int = 0) -> SimplifiedDocumentGroupsResponse`
  - **Logic:** All existing fetch/filter logic remains untouched. After `simplified_groups` list is fully populated (after the folder iteration loop):
    1. Capture `total_count = len(simplified_groups)`
    2. Slice: `page = simplified_groups[offset : offset + limit]`
    3. Compute: `has_more = (offset + limit) < total_count`
    4. Change the final return statement to: `SimplifiedDocumentGroupsResponse(document_groups=page, document_group_total_count=total_count, offset=offset, limit=limit, has_more=has_more)`
  - Same minimal change pattern: two new params, three lines of slicing, updated return

- [ ] **Isolation Rule:** Business logic remains transport-agnostic. No Starlette imports, no token resolution. `limit`/`offset` are plain `int` parameters with defaults — no Pydantic `Field` annotations at this layer (annotations live in the orchestrator).

---

## Phase 3: Tool Orchestrator & Registration

*Wire pagination parameters through the thin orchestrator layer. Depends on Phase 2 signatures being updated. No registration changes needed — existing tools gain new optional params, no new tools created.*

- [ ] `[Tool Orchestrator]` Add `limit`/`offset` to `_list_all_templates_impl` and propagate to tool + resource
  - **File:** `src/sn_mcp_server/tools/signnow.py`
  - **Logic — `_list_all_templates_impl`:** Add `limit: int = 50` and `offset: int = 0` parameters. Pass them through to `_list_all_templates(ctx, token, client, limit=limit, offset=offset)`.
  - **Logic — `list_all_templates` tool:** Add two new annotated parameters after `ctx`:
    - `limit: Annotated[int, Field(ge=1, le=100, description="Maximum number of items to return (1-100, default 50)")] = 50`
    - `offset: Annotated[int, Field(ge=0, description="Number of items to skip for pagination (default 0)")] = 0`
    - Pass both to `_list_all_templates_impl(ctx, limit=limit, offset=offset)`
    - Update docstring to document the two new args
  - **Logic — `list_all_templates_resource`:** Add identical `limit`/`offset` annotated parameters. Pass to `_list_all_templates_impl(ctx, limit=limit, offset=offset)`.
  - **Logic — resource URI template:** Update from `"signnow://templates"` to `"signnow://templates{?limit,offset}"` to allow parameterized resource reads.

- [ ] `[Tool Orchestrator]` Add `limit`/`offset` to `_list_documents_impl` and propagate to tool + resource
  - **File:** `src/sn_mcp_server/tools/signnow.py`
  - **Logic — `_list_documents_impl`:** Add `limit: int = 50` and `offset: int = 0` parameters. Pass them through to `_list_document_groups(..., limit=limit, offset=offset)`.
  - **Logic — `list_documents` tool:** Add two new annotated parameters after the existing `expired_filter` param:
    - `limit: Annotated[int, Field(ge=1, le=100, description="Maximum number of items to return (1-100, default 50)")] = 50`
    - `offset: Annotated[int, Field(ge=0, description="Number of items to skip for pagination (default 0)")] = 0`
    - Pass both through the existing call chain: `_list_documents_impl(ctx, ..., limit=limit, offset=offset)`
    - Update docstring to document the two new args
  - **Logic — `list_documents_resource`:** Add identical `limit`/`offset` annotated parameters. Pass to `_list_documents_impl(ctx, ..., limit=limit, offset=offset)`.
  - **Logic — resource URI template:** Update from `"signnow://documents/{?filter,sortby,order,folder_id,expired_filter}"` to `"signnow://documents/{?filter,sortby,order,folder_id,expired_filter,limit,offset}"`.

- [ ] `[Registration]` No changes needed — `tools/__init__.py` calls `signnow.bind()` which already registers both tools. No new tools are created.

- [ ] **Constraint Check:** Orchestrator functions remain thin wrappers: resolve token → call business logic → return result. Pydantic `Field(ge=..., le=...)` constraints handle all input validation — no manual validation in orchestrator.

---

## Phase 4: Tests

*Unit tests for pagination behavior. Mock `SignNowAPIClient` to avoid network calls. Mirror source structure under `tests/unit/`.*

- [ ] `[Tests]` Update existing tests in `test_list_templates.py` to account for new response fields
  - **File:** `tests/unit/sn_mcp_server/tools/test_list_templates.py`
  - **Coverage:** All existing tests that assert on `TemplateSummaryList` results need updated assertions to also check the new pagination fields (`offset`, `limit`, `has_more`). Specifically:
    - `test_list_all_templates_success`: Add assertions for `offset=0, limit=50, has_more=False` (default pagination with 5 items < 50 limit)
    - `test_list_all_templates_empty_folders`: Add assertions for `offset=0, limit=50, has_more=False` (0 items)
    - `test_list_all_templates_folder_access_error`: Add assertions for `offset=0, limit=50, has_more=False` (2 items)
    - `test_list_all_templates_missing_optional_fields`: Add assertions for `offset=0, limit=50, has_more=False` (1 item)
    - `test_list_all_templates_progress_reporting`: No assertion changes needed (doesn't check response shape)

- [ ] `[Tests]` Add pagination-specific test cases to `test_list_templates.py`
  - **File:** `tests/unit/sn_mcp_server/tools/test_list_templates.py`
  - **Test cases** (all reuse the existing `sample_*` fixtures that produce 5 templates total):
    - `test_list_templates_with_limit` — Call with `limit=2`. Assert: `len(templates)=2, total_count=5, offset=0, limit=2, has_more=True`
    - `test_list_templates_with_offset` — Call with `offset=3, limit=50`. Assert: `len(templates)=2, total_count=5, offset=3, has_more=False`
    - `test_list_templates_offset_beyond_total` — Call with `offset=100`. Assert: `len(templates)=0, total_count=5, offset=100, has_more=False`
    - `test_list_templates_limit_and_offset` — Call with `offset=1, limit=2`. Assert: `len(templates)=2, total_count=5, has_more=True`
    - `test_list_templates_exact_page_boundary` — Call with `offset=3, limit=2`. Assert: `len(templates)=2, total_count=5, has_more=False`

- [ ] `[Tests]` Create pagination tests for `_list_document_groups`
  - **File:** `tests/unit/sn_mcp_server/tools/test_list_documents.py` (NEW file)
  - **Fixtures needed:**
    - `mock_context` — `AsyncMock(spec=Context)` with `report_progress = AsyncMock()`
    - `mock_client` — `MagicMock()` for `SignNowAPIClient`
    - `sample_folders_response` — `GetFoldersResponseLite` with root + 1 subfolder
    - `sample_folder_content_with_documents` — `GetFolderByIdResponseLite` containing a mix of `DocumentItemLite` and `DocumentGroupItemLite` items (at least 5 items total to test slicing)
  - **Test cases:**
    - `test_list_documents_default_pagination` — No limit/offset passed. Assert: all items returned, `offset=0, limit=50, has_more=False`, `document_group_total_count` equals actual count
    - `test_list_documents_with_limit` — `limit=2` with 5+ items. Assert: `len(document_groups)=2, has_more=True, document_group_total_count=total`
    - `test_list_documents_with_offset` — `offset=3, limit=50`. Assert: remaining items returned, `has_more=False`
    - `test_list_documents_offset_beyond_total` — `offset=100`. Assert: empty list, `has_more=False`, `document_group_total_count=total`
    - `test_list_documents_limit_and_offset` — `offset=1, limit=2`. Assert: 2 items, `has_more=True`
    - `test_list_documents_empty_result` — Mock returns no documents. Assert: `document_group_total_count=0, has_more=False`, empty list

- [ ] **Constraint Check:** No network calls in tests. All `SignNowAPIClient` interactions are mocked via `MagicMock`. Tests runnable with `pytest` in isolation.

---

## Phase 5: Documentation & Verification

*Keep project documentation in sync. Validate the implementation against all constraints.*

- [ ] `[Docs]` Update `README.md` → Tools section — add pagination info to `list_all_templates` and `list_documents` descriptions
  - **File:** `README.md`
  - **Logic:** Expand the two bullet points for these tools to mention `limit`/`offset` parameters. Example:
    - `**list_all_templates**` — "List templates & template groups with simplified metadata. Supports `limit`/`offset` pagination (default: 50 items per page)."
    - `**list_documents**` — "Browse your documents, document groups and statuses. Supports `limit`/`offset` pagination (default: 50 items per page)."

- [ ] `[Docs]` Verify tool docstrings in `signnow.py` are concise, accurate, and document the new `limit`/`offset` params

- [ ] Run `pytest` — all tests pass (existing + new)
- [ ] Run `ruff check src/` — no linting errors
- [ ] Run `ruff format --check src/` — formatting is correct
- [ ] Manual verification: Run the MCP server locally, call `list_all_templates` with default params, then with `limit=2, offset=0` and `limit=2, offset=2` — verify `has_more`, `total_count`, and item counts are correct across pages

---

## Philosophy Checklist

- [x] Does every response model carry ONLY the minimum data an agent needs? — Yes. Three small metadata fields added (`offset`, `limit`, `has_more`). Essential for agents to know whether to paginate.
- [x] Is the tool count minimized? — Yes. Zero new tools. Two existing tools gain two optional parameters each.
- [x] Is every business logic function testable by injecting a mocked client? — Yes. `_list_all_templates` and `_list_document_groups` take `client` as a parameter. New `limit`/`offset` params are plain ints.
- [x] Are all error messages specific? — Yes. Input validation via Pydantic `Field(ge=..., le=...)`. No new custom error handling needed.
- [x] Does the solution add zero state, zero caching, zero infrastructure coupling? — Yes. Pure Python list slicing. Stateless `offset`/`limit`.
- [x] Is every new feature actually needed right now? — Yes. Required by Claude MCP Directory submission guide (25k token limit).
- [x] Does `signnow_client/` have zero imports from `sn_mcp_server/`? — Yes. No changes to `signnow_client/` at all.
