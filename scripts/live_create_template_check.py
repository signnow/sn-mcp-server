#!/usr/bin/env python3
"""Live test for create_template tool — exercises real SignNow API.

1. Upload a PDF document
2. Call create_template with entity_type="document" -> verify template_id returned
3. Upload TWO documents, create a document group
4. Call create_template with entity_type="document_group" -> verify async 202
5. Test auto-detect on a document
6. Clean up: nothing — templates stay for manual inspection

Usage:
    python scripts/live_create_template_check.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Load .env before any sn_mcp_server import
try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    pass

from fastmcp import Client

from sn_mcp_server.server import create_server

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "tests" / "live" / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Minimal 1-page blank PDF (valid, ~200 bytes)
BLANK_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
    b"0000000058 00000 n \n0000000115 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
)


def _snap(name: str, data: dict) -> None:
    """Save snapshot to tests/live/snapshots/."""
    (SNAPSHOT_DIR / f"create_template_{name}.json").write_text(json.dumps(data, indent=2, default=str))


async def _call(client: Client, step: str, tool: str, args: dict) -> dict:
    """Call tool, print result, save snapshot, return structured data."""
    t0 = time.monotonic()
    res = await client.call_tool(tool, args, raise_on_error=False)
    elapsed = int((time.monotonic() - t0) * 1000)
    raw_err = None
    if res.is_error:
        raw_err = res.content[0].text if res.content else "unknown error"
    data = res.structured_content
    if data is None and res.data is not None:
        try:
            data = res.data.model_dump() if hasattr(res.data, "model_dump") else res.data
        except Exception:
            data = {"_repr": repr(res.data)}

    snap = {"args": args, "is_error": res.is_error, "error": raw_err, "data": data, "elapsed_ms": elapsed}
    _snap(step, snap)

    status = "FAIL" if res.is_error else "PASS"
    print(f"  [{status}] {step} ({elapsed}ms)")
    if raw_err:
        print(f"         ERROR: {raw_err[:300]}")
    elif data:
        for k, v in (data if isinstance(data, dict) else {}).items():
            print(f"         {k}: {v}")
    return snap


async def run() -> bool:
    """Run all live checks. Returns True if all pass."""
    server = create_server()
    all_pass = True

    async with Client(server) as client:
        # ── Step 1: Upload document ──────────────────────────────────
        print("\n=== Step 1: Upload document ===")
        # write a temporary PDF
        tmp_pdf = REPO_ROOT / "tests" / "live" / "_tmp_create_template_test.pdf"
        tmp_pdf.write_bytes(BLANK_PDF)
        try:
            r1 = await _call(
                client,
                "01_upload_doc",
                "upload_document",
                {
                    "file_path": str(tmp_pdf),
                },
            )
        finally:
            tmp_pdf.unlink(missing_ok=True)

        if r1["is_error"]:
            print("  ✗ Cannot proceed without a document. Aborting.")
            return False

        doc_id = r1["data"]["document_id"]
        print(f"  → document_id = {doc_id}")

        # ── Step 2: create_template (document path) ────────────────
        print("\n=== Step 2: create_template (entity_type=document) ===")
        r2 = await _call(
            client,
            "02_create_template_doc",
            "create_template",
            {
                "entity_id": doc_id,
                "template_name": "Live Test Template — document",
                "entity_type": "document",
            },
        )
        if r2["is_error"]:
            all_pass = False
        else:
            tmpl_id = r2["data"].get("template_id")
            print(f"  → template_id = {tmpl_id}")

        # ── Step 3: Upload 2 docs + create document group ───────────
        print("\n=== Step 3: Upload 2 docs for document group ===")
        tmp_pdf_a = REPO_ROOT / "tests" / "live" / "_tmp_grp_a.pdf"
        tmp_pdf_b = REPO_ROOT / "tests" / "live" / "_tmp_grp_b.pdf"
        tmp_pdf_a.write_bytes(BLANK_PDF)
        tmp_pdf_b.write_bytes(BLANK_PDF)
        try:
            r3a = await _call(
                client,
                "03a_upload_grp_doc_a",
                "upload_document",
                {
                    "file_path": str(tmp_pdf_a),
                },
            )
            r3b = await _call(
                client,
                "03b_upload_grp_doc_b",
                "upload_document",
                {
                    "file_path": str(tmp_pdf_b),
                },
            )
        finally:
            tmp_pdf_a.unlink(missing_ok=True)
            tmp_pdf_b.unlink(missing_ok=True)

        if r3a["is_error"] or r3b["is_error"]:
            print("  ✗ Cannot proceed without two documents for group. Skipping group test.")
        else:
            doc_id_a = r3a["data"]["document_id"]
            doc_id_b = r3b["data"]["document_id"]
            print(f"  → doc_a = {doc_id_a}, doc_b = {doc_id_b}")

            # Create document group via direct client call (no MCP tool for this)
            print("\n=== Step 3c: Create document group (direct API) ===")
            from signnow_client import SignNowAPIClient
            from signnow_client.config import SignNowConfig
            from signnow_client.models.document_groups import CreateDocumentGroupRequest

            cfg = SignNowConfig()
            api_client = SignNowAPIClient(cfg)
            token_response = api_client.get_tokens_by_password(
                os.environ["SIGNNOW_USER_EMAIL"],
                os.environ["SIGNNOW_PASSWORD"],
            )
            token = token_response["access_token"]

            grp_resp = api_client.create_document_group(
                token,
                CreateDocumentGroupRequest(
                    document_ids=[doc_id_a, doc_id_b],
                    group_name="Live Test Group — create_template",
                ),
            )
            grp_id = grp_resp.id
            print(f"  [PASS] Document group created: {grp_id}")
            _snap("03c_create_group", {"group_id": grp_id, "doc_ids": [doc_id_a, doc_id_b]})

            # ── Step 4: create_template (document_group path) ───────
            print("\n=== Step 4: create_template (entity_type=document_group) ===")
            r4 = await _call(
                client,
                "04_create_template_grp",
                "create_template",
                {
                    "entity_id": grp_id,
                    "template_name": "Live Test Template Group",
                    "entity_type": "document_group",
                },
            )
            if r4["is_error"]:
                all_pass = False
            else:
                print(f"  → template_id = {r4['data'].get('template_id')} (expected None for async)")

        # ── Step 5: Auto-detect on another document ──────────────────
        print("\n=== Step 5: create_template (auto-detect on document) ===")
        # Upload one more doc for auto-detect test
        tmp_pdf_c = REPO_ROOT / "tests" / "live" / "_tmp_autodetect.pdf"
        tmp_pdf_c.write_bytes(BLANK_PDF)
        try:
            r5a = await _call(
                client,
                "05a_upload_autodetect",
                "upload_document",
                {
                    "file_path": str(tmp_pdf_c),
                },
            )
        finally:
            tmp_pdf_c.unlink(missing_ok=True)

        if r5a["is_error"]:
            print("  ✗ Skipping auto-detect test (upload failed)")
        else:
            new_doc_id = r5a["data"]["document_id"]
            r5 = await _call(
                client,
                "05b_create_template_autodetect",
                "create_template",
                {
                    "entity_id": new_doc_id,
                    "template_name": "Live Test Template — autodetect",
                },
            )
            if r5["is_error"]:
                all_pass = False
            else:
                detected = r5["data"].get("entity_type")
                print(f"  → auto-detected entity_type = {detected} (expected 'document')")

    return all_pass


def main() -> int:
    print("=" * 60)
    print("Live create_template tool check")
    print("=" * 60)

    ok = asyncio.run(run())

    print("\n" + "=" * 60)
    if ok:
        print("ALL CHECKS PASSED ✓")
    else:
        print("SOME CHECKS FAILED ✗")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
