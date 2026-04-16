"""Unit tests for skills module."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sn_mcp_server.tools.models import SkillResponse, SkillSummary
from sn_mcp_server.tools.skills import _get_skill, _list_skills, _parse_frontmatter


class TestParseFrontmatter:
    """Test cases for _parse_frontmatter."""

    def test_parse_frontmatter_valid(self) -> None:
        """Test that valid YAML front-matter is parsed into a dict and body is separated."""
        content = "---\nname: foo\ndescription: bar\n---\nbody"
        fm, body = _parse_frontmatter(content)
        assert fm == {"name": "foo", "description": "bar"}
        assert body == "body"

    def test_parse_frontmatter_no_delimiters(self) -> None:
        """Test that content with no --- delimiters returns empty dict and original content."""
        content = "just body"
        fm, body = _parse_frontmatter(content)
        assert fm == {}
        assert body == "just body"

    def test_parse_frontmatter_unclosed(self) -> None:
        """Test that unclosed front-matter is treated as no front-matter."""
        content = "---\nname: foo\n"
        fm, body = _parse_frontmatter(content)
        assert fm == {}
        assert body == "---\nname: foo\n"

    def test_parse_frontmatter_extra_fields_ignored(self) -> None:
        """Test that unknown front-matter fields are parsed but do not cause errors."""
        content = "---\nname: myskill\ndescription: desc\ntags: a b c\n---\nsome body"
        fm, body = _parse_frontmatter(content)
        assert fm["name"] == "myskill"
        assert fm["description"] == "desc"
        assert fm["tags"] == "a b c"
        assert body == "some body"

    def test_parse_frontmatter_strips_value_whitespace(self) -> None:
        """Test that front-matter values have surrounding whitespace stripped."""
        content = "---\nname:   spaced value   \n---\nbody"
        fm, body = _parse_frontmatter(content)
        assert fm["name"] == "spaced value"

    def test_parse_frontmatter_strips_surrounding_double_quotes(self) -> None:
        """Test that values wrapped in double quotes have those quotes stripped (P3)."""
        content = '---\ndescription: "Quoted description"\n---\nbody'
        fm, _ = _parse_frontmatter(content)
        assert fm["description"] == "Quoted description"

    def test_parse_frontmatter_strips_surrounding_single_quotes(self) -> None:
        """Test that values wrapped in single quotes have those quotes stripped (P3)."""
        content = "---\ndescription: 'Quoted description'\n---\nbody"
        fm, _ = _parse_frontmatter(content)
        assert fm["description"] == "Quoted description"

    def test_parse_frontmatter_does_not_strip_mismatched_quotes(self) -> None:
        """Test that mismatched quotes are not stripped (only symmetric pairs)."""
        content = "---\nname: \"mismatched'\n---\nbody"
        fm, _ = _parse_frontmatter(content)
        assert fm["name"] == "\"mismatched'"


class TestListSkills:
    """Test cases for _list_skills."""

    def test_list_skills_returns_all(self, tmp_path: Path) -> None:
        """Test that all *.md files are returned with correct name and description."""
        (tmp_path / "alpha.md").write_text("---\nname: alpha\ndescription: Alpha skill\n---\nbody", encoding="utf-8")
        (tmp_path / "beta.md").write_text("---\nname: beta\ndescription: Beta skill\n---\nbody", encoding="utf-8")

        result = _list_skills(tmp_path)

        assert isinstance(result, SkillResponse)
        assert result.name is None
        assert result.body is None
        assert result.skills is not None
        assert len(result.skills) == 2
        names = [s.name for s in result.skills]
        descriptions = [s.description for s in result.skills]
        assert "alpha" in names
        assert "beta" in names
        assert "Alpha skill" in descriptions
        assert "Beta skill" in descriptions

    def test_list_skills_sorted_alphabetically(self, tmp_path: Path) -> None:
        """Test that skills list is sorted alphabetically by filename."""
        (tmp_path / "z_skill.md").write_text("---\nname: z_skill\ndescription: Z\n---\nbody", encoding="utf-8")
        (tmp_path / "a_skill.md").write_text("---\nname: a_skill\ndescription: A\n---\nbody", encoding="utf-8")

        result = _list_skills(tmp_path)

        assert result.skills is not None
        assert result.skills[0].name == "a_skill"
        assert result.skills[1].name == "z_skill"

    def test_list_skills_empty_dir(self, tmp_path: Path) -> None:
        """Test that an empty skills directory returns an empty skills list."""
        result = _list_skills(tmp_path)

        assert isinstance(result, SkillResponse)
        assert result.skills == []
        assert result.name is None
        assert result.body is None

    def test_list_skills_missing_dir(self, tmp_path: Path) -> None:
        """Test that a nonexistent skills directory raises ValueError."""
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(ValueError, match="Skills directory not found"):
            _list_skills(nonexistent)

    def test_list_skills_raises_when_path_is_file(self, tmp_path: Path) -> None:
        """Test that _list_skills raises ValueError when skills_dir is a file, not a directory."""
        fake_dir = tmp_path / "not_a_dir"
        fake_dir.write_text("I am a file, not a directory", encoding="utf-8")

        with pytest.raises(ValueError, match="Skills directory not found"):
            _list_skills(fake_dir)

    def test_list_skills_degraded_frontmatter(self, tmp_path: Path) -> None:
        """Test graceful degradation when a file has no front-matter."""
        (tmp_path / "nofm.md").write_text("Some content without front-matter.", encoding="utf-8")

        result = _list_skills(tmp_path)

        assert result.skills is not None
        assert len(result.skills) == 1
        skill = result.skills[0]
        assert skill.name == "nofm"
        assert skill.description == ""

    def test_list_skills_returns_skill_summary_instances(self, tmp_path: Path) -> None:
        """Test that each entry in the skills list is a SkillSummary instance."""
        (tmp_path / "sample.md").write_text("---\nname: sample\ndescription: Sample desc\n---\nbody", encoding="utf-8")

        result = _list_skills(tmp_path)

        assert result.skills is not None
        assert all(isinstance(s, SkillSummary) for s in result.skills)


class TestGetSkill:
    """Test cases for _get_skill."""

    def test_get_skill_happy_path(self, tmp_path: Path) -> None:
        """Test successful fetch returns name and body, skills is None."""
        (tmp_path / "signnow101.md").write_text(
            "---\nname: signnow101\ndescription: The desc\n---\n# Body\ncontent",
            encoding="utf-8",
        )

        result = _get_skill(tmp_path, "signnow101")

        assert isinstance(result, SkillResponse)
        assert result.skills is None
        assert result.name == "signnow101"
        assert result.body == "# Body\ncontent"

    def test_get_skill_body_is_stripped(self, tmp_path: Path) -> None:
        """Test that body leading and trailing whitespace is stripped."""
        (tmp_path / "myskill.md").write_text(
            "---\nname: myskill\ndescription: d\n---\n\n  # Title\n\nsome text\n\n",
            encoding="utf-8",
        )

        result = _get_skill(tmp_path, "myskill")

        assert result.body is not None
        assert result.body == result.body.strip()
        assert not result.body.startswith("\n")
        assert not result.body.endswith("\n")

    def test_get_skill_not_found(self, tmp_path: Path) -> None:
        """Test that requesting a missing skill raises ValueError naming available skills."""
        (tmp_path / "signnow101.md").write_text("---\nname: signnow101\ndescription: d\n---\nbody", encoding="utf-8")

        with pytest.raises(ValueError, match="'unknown' not found") as exc_info:
            _get_skill(tmp_path, "unknown")

        assert "signnow101" in str(exc_info.value)

    def test_get_skill_not_found_empty_dir(self, tmp_path: Path) -> None:
        """Test that requesting any skill from an empty dir raises ValueError with '(none)'."""
        with pytest.raises(ValueError, match=r"\(none\)"):
            _get_skill(tmp_path, "anything")

    def test_get_skill_uses_frontmatter_name(self, tmp_path: Path) -> None:
        """Test that the response name comes from front-matter, not the filename stem."""
        (tmp_path / "filename.md").write_text("---\nname: frontmatter_name\ndescription: d\n---\nbody", encoding="utf-8")

        result = _get_skill(tmp_path, "filename")

        assert result.name == "frontmatter_name"

    def test_get_skill_fallback_name_when_no_frontmatter(self, tmp_path: Path) -> None:
        """Test that skill_name is used as name when front-matter is absent."""
        (tmp_path / "bare.md").write_text("Just a bare body with no front-matter.", encoding="utf-8")

        result = _get_skill(tmp_path, "bare")

        assert result.name == "bare"
        assert result.body == "Just a bare body with no front-matter."

    def test_get_skill_rejects_path_traversal(self, tmp_path: Path) -> None:
        """Test that path traversal via .. is rejected before any file access (P1)."""
        with pytest.raises(ValueError, match="[Ii]nvalid skill name"):
            _get_skill(tmp_path, "../../etc/passwd")

    def test_get_skill_rejects_slash_in_name(self, tmp_path: Path) -> None:
        """Test that a slash in skill_name is rejected (P1)."""
        with pytest.raises(ValueError, match="[Ii]nvalid skill name"):
            _get_skill(tmp_path, "foo/bar")

    def test_get_skill_rejects_empty_name(self, tmp_path: Path) -> None:
        """Test that an empty skill_name is rejected (P1)."""
        with pytest.raises(ValueError, match="[Ii]nvalid skill name"):
            _get_skill(tmp_path, "")

    def test_get_skill_allows_hyphens_and_underscores(self, tmp_path: Path) -> None:
        """Test that skill names with hyphens and underscores are accepted (P1)."""
        (tmp_path / "my-skill_v2.md").write_text("---\nname: my-skill_v2\ndescription: d\n---\nbody", encoding="utf-8")
        result = _get_skill(tmp_path, "my-skill_v2")
        assert result.name == "my-skill_v2"

    def test_get_skill_raises_when_skills_dir_is_file(self, tmp_path: Path) -> None:
        """Test that _get_skill raises ValueError when skills_dir is a file, not a directory."""
        fake_dir = tmp_path / "not_a_dir"
        fake_dir.write_text("I am a file, not a directory", encoding="utf-8")

        with pytest.raises(ValueError, match="Skills directory not found"):
            _get_skill(fake_dir, "signnow101")

    def test_get_skill_raises_when_skills_dir_missing(self, tmp_path: Path) -> None:
        """Test that _get_skill raises ValueError when skills_dir does not exist."""
        missing = tmp_path / "does_not_exist"

        with pytest.raises(ValueError, match="Skills directory not found"):
            _get_skill(missing, "signnow101")


class TestBind:
    """Smoke tests for the bind() function."""

    def test_bind_tags_is_a_list(self) -> None:
        """tags must be a list, not a set — sets are not JSON-serializable (P2)."""
        import json
        from unittest.mock import MagicMock

        from sn_mcp_server.tools.skills import bind

        captured: dict = {}

        def capture_tool(**kwargs: object) -> object:
            captured.update(kwargs)
            return lambda fn: fn

        mock_mcp = MagicMock()
        mock_mcp.tool.side_effect = capture_tool

        bind(mock_mcp, None)

        assert "tags" in captured, "bind() must pass tags= to mcp.tool()"
        assert isinstance(captured["tags"], list), f"tags must be a list, got {type(captured['tags']).__name__}"
        # Serialize to JSON — would raise TypeError if tags is a set
        json.dumps(captured["tags"])


class TestSignnow101Staleness:
    """Staleness guard — ensures tool names referenced in signnow101.md exist as registered MCP tools."""

    _SIGNNOW101 = Path(__file__).parents[4] / "src" / "sn_mcp_server" / "skills" / "signnow101.md"
    _SIGNNOW_PY = Path(__file__).parents[4] / "src" / "sn_mcp_server" / "tools" / "signnow.py"
    _SKILLS_PY = Path(__file__).parents[4] / "src" / "sn_mcp_server" / "tools" / "skills.py"

    def _registered_tool_names(self) -> set[str]:
        """Extract all registered MCP tool names from signnow.py and skills.py source."""
        names: set[str] = set()
        for path in (self._SIGNNOW_PY, self._SKILLS_PY):
            source = path.read_text(encoding="utf-8")
            names.update(re.findall(r'name\s*=\s*"([^"]+)"', source))
        return names

    def _tool_names_in_mapping_table(self) -> set[str]:
        """Extract backtick-wrapped tool names from the Tool→API mapping table in signnow101.md.

        The mapping table is identified by columns containing 'MCP Tool' or 'Tool' in the header.
        Only rows inside such a table are scanned for backtick-wrapped identifiers.
        """
        content = self._SIGNNOW101.read_text(encoding="utf-8")
        lines = content.splitlines()

        in_tool_table = False
        tool_names: set[str] = set()

        for line in lines:
            if not line.startswith("|"):
                in_tool_table = False
                continue
            # Detect the header of a table that has a "Tool" column
            lower = line.lower()
            if "mcp tool" in lower or ("tool" in lower and "api" in lower):
                in_tool_table = True
                continue
            if in_tool_table:
                # Skip separator rows (|---|---|)
                if re.match(r"^\|[-| :]+\|$", line.strip()):
                    continue
                # Extract all backtick-wrapped identifiers from data rows
                tool_names.update(re.findall(r"`([^`]+)`", line))

        return tool_names

    def test_signnow101_tool_names_match_registered(self) -> None:
        """Test that every tool name in the signnow101.md mapping table is a registered MCP tool."""
        referenced = self._tool_names_in_mapping_table()
        if not referenced:
            # No tool mapping table present yet — test is a no-op (table not yet authored)
            pytest.skip("No tool→API mapping table found in signnow101.md — skipping staleness check")

        registered = self._registered_tool_names()
        missing = referenced - registered
        assert not missing, f"Tool(s) in signnow101.md mapping table are not registered: {sorted(missing)}. Update signnow101.md or register the missing tools."


class TestSignnow101Content:
    """Content assertions for the signnow101 skill — verifies SN-30533 sections exist."""

    _SKILLS_DIR: Path = Path(__file__).parents[4] / "src" / "sn_mcp_server" / "skills"

    def _body(self) -> str:
        result = _get_skill(self._SKILLS_DIR, "signnow101")
        assert result.body is not None
        return result.body

    def test_signnow101_contains_sending_for_signing_section(self) -> None:
        """Body must contain the '## 4. Sending for Signing' section heading."""
        assert "## 4. Sending for Signing" in self._body()

    def test_signnow101_contains_preview_before_sending(self) -> None:
        """Body must contain the 'Preview Before Sending' subsection heading."""
        assert "Preview Before Sending" in self._body()

    def test_signnow101_contains_view_document_reference_in_sending(self) -> None:
        """'view_document' must appear in the body after the 'Sending for Signing' heading."""
        body = self._body()
        sending_section_start = body.find("## 4. Sending for Signing")
        assert sending_section_start != -1, "Section '## 4. Sending for Signing' not found"
        sending_section_body = body[sending_section_start:]
        assert "`view_document`" in sending_section_body, "'view_document' tool not referenced in the Sending for Signing section"

    def test_signnow101_contains_signing_link_etiquette(self) -> None:
        """Body must contain the 'Signing Link Etiquette' subsection heading."""
        assert "Signing Link Etiquette" in self._body()

    def test_signnow101_contains_never_auto_send_rule(self) -> None:
        """Body must contain a 'NEVER auto-send' prohibition near the signing link section."""
        body = self._body()
        assert re.search(r"NEVER.*auto.?send|auto.?send.*NEVER", body, re.IGNORECASE | re.DOTALL), "Expected 'NEVER auto-send' rule in signnow101.md but not found"
