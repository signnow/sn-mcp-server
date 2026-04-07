"""
Skills tool — reads bundled Markdown skill files and exposes them via the `signnow_skills` MCP tool.

No API calls, no auth, no SignNowAPIClient. Pure filesystem reads.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .models import SkillResponse, SkillSummary

# Resolved once at module load — immutable constant, not mutable state.
# front-matter values are constrained to single-line `key: value` format by convention;
# do not switch to PyYAML without updating the constraint in the spec.
_SKILLS_DIR: Path = Path(__file__).parent.parent / "skills"

# P1: only alphanumerics, hyphens, and underscores are safe as filesystem identifiers.
_SKILL_NAME_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML front-matter delimited by --- from Markdown content.

    Args:
        content: Raw Markdown file content.

    Returns:
        Tuple of (frontmatter_dict, body_without_frontmatter).
        If no valid front-matter is found, returns ({}, content).
    """
    if not content.startswith("---\n"):
        return {}, content

    end_idx = content.find("---\n", 4)
    if end_idx == -1:
        return {}, content

    yaml_block = content[4:end_idx]
    matches = re.findall(r"^(\w+)\s*:\s*(.+)$", yaml_block, re.MULTILINE)
    frontmatter = {key: _strip_quotes(value.strip()) for key, value in matches}
    body = content[end_idx + 4 :]
    return frontmatter, body


def _strip_quotes(value: str) -> str:
    """Strip a single pair of matching surrounding quotes from a string value.

    Handles both double-quotes and single-quotes. Only symmetric pairs are stripped.
    Mismatched quotes (e.g. ``\"foo'``) are returned unchanged.

    Args:
        value: A string that may be surrounded by matching quotes.

    Returns:
        The value with surrounding quote pair removed, or the original string.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _list_skills(skills_dir: Path) -> SkillResponse:
    """Scan skills_dir for *.md files and return their names and descriptions.

    Each file's front-matter ``name`` and ``description`` fields are used.
    If front-matter is missing or malformed, the filename stem is used as name
    and description is left as an empty string (graceful degradation).

    Args:
        skills_dir: Directory to scan for *.md files.

    Returns:
        SkillResponse(skills=[...], name=None, body=None) — list mode.

    Raises:
        ValueError: If skills_dir does not exist.
    """
    if not skills_dir.exists():
        raise ValueError(f"Skills directory not found: {skills_dir}")

    summaries: list[SkillSummary] = []
    for file in sorted(skills_dir.glob("*.md")):
        content = file.read_text(encoding="utf-8")
        fm, _ = _parse_frontmatter(content)
        summaries.append(SkillSummary(name=fm.get("name", file.stem), description=fm.get("description", "")))

    return SkillResponse(skills=summaries, name=None, body=None)


def _get_skill(skills_dir: Path, skill_name: str) -> SkillResponse:
    """Read and return the body of a named skill file, front-matter stripped.

    Args:
        skills_dir: Directory containing *.md skill files.
        skill_name: Identifier for the skill (filename without .md extension).

    Returns:
        SkillResponse(skills=None, name=skill_name, body="...") — fetch mode.

    Raises:
        ValueError: If skill_name does not match any file in skills_dir.
                    Error message includes the list of available skill names.
    """
    if not _SKILL_NAME_RE.match(skill_name):
        raise ValueError(f"Invalid skill name '{skill_name}'. Names must contain only letters, digits, hyphens, and underscores.")

    target = skills_dir / f"{skill_name}.md"
    if not target.exists():
        available = [f.stem for f in sorted(skills_dir.glob("*.md"))]
        available_str = ", ".join(available) if available else "(none)"
        raise ValueError(f"Skill '{skill_name}' not found. Available skills: {available_str}")

    content = target.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(content)
    return SkillResponse(skills=None, name=fm.get("name", skill_name), body=body.strip())


def bind(mcp: FastMCP, cfg: Any) -> None:  # noqa: ANN401
    """Register the signnow_skills tool with the MCP server.

    Args:
        mcp: FastMCP server instance.
        cfg: Server configuration (unused; present for interface consistency).
    """
    # cfg unused — no auth
    _ = cfg

    @mcp.tool(
        name="signnow_skills",
        description=("Query the bundled SignNow skill library. Omit skill_name to list all skills with descriptions. Provide skill_name to read the full skill body."),
        annotations=ToolAnnotations(
            title="Query SignNow skill library",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        tags=["skill", "reference"],
    )
    async def signnow_skills(
        skill_name: Annotated[
            str | None,
            Field(
                default=None,
                description=("Name of the skill to retrieve (e.g. 'signnow101'). Omit to list all available skills with their descriptions."),
            ),
        ] = None,
    ) -> SkillResponse:
        """Query the bundled SignNow skill library.

        When called without arguments, returns a list of all available skills
        with their names and one-line descriptions (skills field populated).

        When called with skill_name, returns the full Markdown body of that skill,
        front-matter stripped (name and body fields populated).

        Use signnow101 first if you are unfamiliar with SignNow entity types,
        workflow actions, or which tool to call for a given task.
        """
        if skill_name is None:
            return _list_skills(_SKILLS_DIR)
        return _get_skill(_SKILLS_DIR, skill_name)
