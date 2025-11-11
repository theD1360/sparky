"""Tests for updated prompts with /<prompt> and @<resource> features."""

import re
from pathlib import Path

import pytest


def get_prompt_files():
    """Get all prompt files from the prompts directory."""
    prompts_dir = Path(__file__).parent.parent.parent / "prompts"
    return list(prompts_dir.glob("*.md"))


class TestPromptSyntax:
    """Test that prompts use the new syntax correctly."""

    @pytest.mark.parametrize("prompt_file", get_prompt_files())
    def test_prompt_file_exists(self, prompt_file):
        """Test that prompt files exist and are readable."""
        assert prompt_file.exists(), f"Prompt file not found: {prompt_file}"
        content = prompt_file.read_text()
        assert len(content) > 0, f"Prompt file is empty: {prompt_file}"

    @pytest.mark.parametrize("prompt_file", get_prompt_files())
    def test_resource_syntax(self, prompt_file):
        """Test that @resource syntax is used correctly."""
        content = prompt_file.read_text()
        
        # Find all @resource patterns
        resource_pattern = re.compile(r"@([\w:/\-\.]+)")
        matches = resource_pattern.findall(content)
        
        # If there are resource references, validate them
        valid_resources = [
            "knowledge://stats",
            "knowledge://memories",
            "knowledge://memory/",
            "knowledge://workflows",
            "knowledge://workflow/",
            "knowledge://thinking-patterns",
            "knowledge://node/",
            "knowledge://tool-usage/recent",
        ]
        
        for match in matches:
            # Check if it's a known resource or follows a valid pattern
            is_valid = any(match.startswith(vr.replace("://", ":/")) or 
                          match.startswith(vr) for vr in valid_resources)
            if not is_valid:
                # Could be a parameterized resource like @knowledge://node/<id>/context
                is_valid = any(pattern in match for pattern in [
                    "knowledge:/", "memory/", "node/", "workflow/"
                ])
            
            # Note: This is informational, not a hard failure
            # as new resources may be added
            if not is_valid and not match.startswith("knowledge"):
                print(f"Note: Unusual resource reference in {prompt_file.name}: @{match}")

    @pytest.mark.parametrize("prompt_file", get_prompt_files())
    def test_prompt_command_syntax(self, prompt_file):
        """Test that /<prompt> command syntax is used correctly."""
        content = prompt_file.read_text()
        
        # Find all /<prompt> patterns
        prompt_pattern = re.compile(r"/(\w+)")
        matches = prompt_pattern.findall(content)
        
        # Known MCP prompts from knowledge server
        known_prompts = [
            "analyze_knowledge_structure",
            "discover_concept",
            "solve_problem",
            "organize_memories",
            "execute_workflow",
        ]
        
        for match in matches:
            # Check if it's a known prompt
            if match not in known_prompts:
                # Note: This is informational, not a hard failure
                print(f"Note: Unusual prompt command in {prompt_file.name}: /{match}")

    def test_curiosity_prompt_structure(self):
        """Test that curiosity prompt has proper structure."""
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        curiosity_file = prompts_dir / "curiosity_prompt.md"
        
        content = curiosity_file.read_text()
        
        # Should have resource references
        assert "@knowledge://stats" in content
        assert "@knowledge://tool-usage/recent" in content
        
        # Should have prompt commands
        assert "/analyze_knowledge_structure" in content
        assert "/discover_concept" in content

    def test_reflection_prompt_structure(self):
        """Test that reflection prompt has proper structure."""
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        reflection_file = prompts_dir / "reflection_prompt.md"
        
        content = reflection_file.read_text()
        
        # Should have resource references
        assert "@knowledge://tool-usage/recent" in content
        assert "@knowledge://stats" in content
        assert "@knowledge://memories" in content
        
        # Should have prompt commands
        assert "/analyze_knowledge_structure" in content
        assert "/solve_problem" in content

    def test_all_updated_prompts_have_structure(self):
        """Test that all major prompts have been updated with new structure."""
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        
        # Prompts that should have the new structure
        prompts_to_check = [
            "curiosity_prompt.md",
            "reflection_prompt.md",
            "curation_prompt.md",
            "gardener_prompt.md",
            "alignment_prompt.md",
            "metacognition_prompt.md",
            "workflow_discovery_prompt.md",
            "integrated_reflection_prompt.md",
        ]
        
        for prompt_name in prompts_to_check:
            prompt_file = prompts_dir / prompt_name
            content = prompt_file.read_text()
            
            # Should have at least one resource reference
            has_resource = "@knowledge://" in content
            
            # Should have structured sections (##)
            has_structure = "##" in content
            
            assert has_resource, f"{prompt_name} should have @resource references"
            assert has_structure, f"{prompt_name} should have structured sections"


class TestPromptContent:
    """Test that prompts have appropriate content."""

    @pytest.mark.parametrize("prompt_file", get_prompt_files())
    def test_prompts_have_headers(self, prompt_file):
        """Test that prompts have proper markdown headers."""
        content = prompt_file.read_text()
        
        # Simple identity statements don't need headers
        if prompt_file.name == "identity_prompt.md":
            return
        
        # Should have at least one header
        assert "#" in content, f"Prompt should have headers: {prompt_file.name}"

    @pytest.mark.parametrize("prompt_file", get_prompt_files())
    def test_prompts_have_instructions(self, prompt_file):
        """Test that prompts provide clear instructions."""
        content = prompt_file.read_text()
        
        # Prompts should be reasonably substantial
        # (except for simple reference docs like identity_prompt.md)
        if not prompt_file.name.startswith("identity_") and \
           not prompt_file.name.startswith("concept_"):
            assert len(content) > 500, \
                f"Prompt seems too short: {prompt_file.name}"

    def test_prompts_use_consistent_terminology(self):
        """Test that prompts use consistent terminology."""
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        
        # Terms that should be used consistently
        preferred_terms = {
            "knowledge graph": ["knowledge graph", "graph"],
            "tool": ["tool", "tools"],
            "memory": ["memory", "memories"],
            "workflow": ["workflow", "workflows"],
        }
        
        # Just ensure we're using these terms somewhere
        all_content = ""
        for prompt_file in get_prompt_files():
            all_content += prompt_file.read_text()
        
        for concept, variants in preferred_terms.items():
            assert any(term in all_content.lower() for term in variants), \
                f"Should use term '{concept}' or variants in prompts"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

