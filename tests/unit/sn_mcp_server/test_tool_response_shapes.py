"""Architectural invariant: every MCP tool returns a curated Pydantic model.

AGENTS.md § Boundaries → Always:
    "Curate every API response through tools/models.py — never return raw
     SignNow JSON."

Turning that prose rule into an automated test: on registration, inspect
each tool's return annotation and verify it is a `pydantic.BaseModel`
subclass defined under sn_mcp_server.tools. Plain `dict`, `Any`, or
`list[...]` returns fail the test — those are exactly the shapes that
would leak raw API JSON through.

When adding a new tool:
  1. Define a response model in tools/models.py (or a per-tool models
     module, see skills.py:SkillResponse for the one precedent).
  2. Annotate the tool function's return type with that model.
  3. Nothing to do here — the test auto-discovers via register_tools.
"""

from __future__ import annotations

import inspect
import typing
from typing import Any

import pytest
from fastmcp import FastMCP
from pydantic import BaseModel

from sn_mcp_server.tools import register_tools


def _collect_registered_tools() -> list[tuple[str, Any]]:
    """Register every tool against a stub FastMCP and capture (name, fn).

    We intercept `mcp.tool` at decoration time so we can recover both the
    tool's declared name and the underlying Python function without
    poking FastMCP internals. `register_tools` is driven by the real
    `bind()` modules, so the list stays in sync with production
    registration without the test having to know which tools exist.
    """
    mcp: Any = FastMCP("shape-invariant-test")
    captured: list[tuple[str, Any]] = []
    original_tool = mcp.tool

    def recording_tool(*args: Any, **kwargs: Any) -> Any:
        decorator = original_tool(*args, **kwargs)

        def wrap(fn: Any) -> Any:
            captured.append((kwargs.get("name") or fn.__name__, fn))
            return decorator(fn)

        return wrap

    mcp.tool = recording_tool

    # Minimal stand-in for Settings. `bind()` passes this down to helpers
    # that only call attribute access at request time, not at bind time —
    # so a bare object is enough to register all decorators.
    class _StubCfg:
        pass

    register_tools(mcp, _StubCfg())
    return captured


_REGISTERED = _collect_registered_tools()


def test_tools_were_registered() -> None:
    # Sanity: if this ever returns empty, the parametrized tool check
    # below vacuously passes and we'd miss the real problem (broken
    # registration).
    assert len(_REGISTERED) >= 10, f"Expected at least 10 registered tools, got {len(_REGISTERED)}. register_tools() may be broken."


@pytest.mark.parametrize("name,fn", _REGISTERED, ids=[n for n, _ in _REGISTERED])
def test_tool_returns_curated_pydantic_model(name: str, fn: Any) -> None:
    """Each MCP tool must declare a BaseModel return type from tools/.

    This catches four failure modes at registration time:
      1. Missing return annotation (-> nothing) — impossible to audit.
      2. Return annotation is `dict` / `Any` / `list` — raw JSON leak.
      3. Return annotation is a BaseModel from outside tools/ (e.g. a
         raw signnow_client model) — skipping the curation layer.
      4. Return annotation is a non-BaseModel class — not serializable
         as a stable MCP response contract.
    """
    # Source modules use `from __future__ import annotations`, so
    # inspect.signature returns string annotations. get_type_hints
    # resolves them against the function's own globals/locals, which is
    # what we need to actually see the class object.
    sig = inspect.signature(fn)
    if sig.return_annotation is inspect.Signature.empty:
        pytest.fail(f"Tool {name!r} has no return annotation — must declare a curated response model.")

    hints = typing.get_type_hints(fn)
    annotation = hints.get("return")
    assert annotation is not None, f"Tool {name!r} has no resolvable return type hint."

    # Support Union return types (e.g. SendInviteResponse | SigningLinkResponse)
    # by checking that every member of the union is a BaseModel subclass.
    # `X | Y` syntax produces types.UnionType; typing.Union produces typing.Union.
    origin = typing.get_origin(annotation)
    if origin is typing.Union or isinstance(annotation, type(int | str)):
        members = typing.get_args(annotation)
        for member in members:
            assert inspect.isclass(member) and issubclass(member, BaseModel), (
                f"Tool {name!r} returns a union containing {member!r}, which is not a "
                f"pydantic.BaseModel subclass. AGENTS.md requires every tool to return "
                f"a curated model from tools/models.py (or a per-tool models module), "
                f"never raw dict / list / Any."
            )
            module = member.__module__
            assert module.startswith("sn_mcp_server.tools"), (
                f"Tool {name!r} returns a union containing {member.__name__} from {module!r}. "
                f"Response models must live under sn_mcp_server.tools so the curation "
                f"layer owns the shape — don't leak signnow_client models to clients."
            )
    else:
        assert inspect.isclass(annotation) and issubclass(annotation, BaseModel), (
            f"Tool {name!r} returns {annotation!r}, which is not a pydantic.BaseModel subclass. "
            f"AGENTS.md requires every tool to return a curated model from tools/models.py "
            f"(or a per-tool models module), never raw dict / list / Any."
        )

        module = annotation.__module__
        assert module.startswith("sn_mcp_server.tools"), (
            f"Tool {name!r} returns {annotation.__name__} from {module!r}. "
            f"Response models must live under sn_mcp_server.tools so the curation "
            f"layer owns the shape — don't leak signnow_client models to clients."
        )
