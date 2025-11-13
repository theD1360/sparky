"""Test prompts and resources functionality."""

import asyncio
import json
import os

from badmcp.config import MCPServerConfig
from badmcp.tool_chain import ToolChain
from badmcp.tool_client import ToolClient


async def test_prompts():
    """Test prompt listing and retrieval."""
    print("\n=== Testing Prompts ===\n")

    # Create tool client for knowledge server
    client = ToolClient(
        mcp_config=MCPServerConfig(
            name="knowledge-graph-tools",
            type="stdio",
            command="python",
            args=["-m", "tools.knowledge.server"],
            env={"SPARKY_DB_URL": os.getenv("SPARKY_DB_URL")},
        )
    )

    toolchain = ToolChain([client])

    try:
        # Test listing prompts
        print("1. Listing all prompts...")
        prompts = await toolchain.list_all_prompts()
        print(f"   Found {len(prompts)} prompts:")
        for _, prompt in prompts:
            print(f"   - {prompt.name}: {prompt.description}")

        # Test getting a specific prompt
        print("\n2. Testing discover_concept prompt...")
        try:
            prompt_text = await toolchain.get_prompt(
                "discover_concept", {"concept_name": "Python"}
            )
            print(f"   Prompt text (first 200 chars):")
            print(f"   {prompt_text[:200]}...")
        except Exception as e:
            print(f"   Error: {e}")

        # Test getting another prompt
        print("\n3. Testing solve_problem prompt...")
        try:
            prompt_text = await toolchain.get_prompt(
                "solve_problem", {"problem_description": "Optimize database queries"}
            )
            print(f"   Prompt text (first 200 chars):")
            print(f"   {prompt_text[:200]}...")
        except Exception as e:
            print(f"   Error: {e}")

        # Test prompt with no arguments
        print("\n4. Testing analyze_knowledge_structure prompt...")
        try:
            prompt_text = await toolchain.get_prompt(
                "analyze_knowledge_structure", {}
            )
            print(f"   Prompt text (first 200 chars):")
            print(f"   {prompt_text[:200]}...")
        except Exception as e:
            print(f"   Error: {e}")

        print("\n✓ Prompts test completed")

    finally:
        await toolchain.tool_clients[0].stop()


async def test_resources():
    """Test resource listing and reading."""
    print("\n=== Testing Resources ===\n")

    # Create tool client for knowledge server
    client = ToolClient(
        mcp_config=MCPServerConfig(
            name="knowledge-graph-tools",
            type="stdio",
            command="python",
            args=["-m", "tools.knowledge.server"],
            env={"SPARKY_DB_URL": os.getenv("SPARKY_DB_URL")},
        )
    )

    toolchain = ToolChain([client])

    try:
        # Test listing resources
        print("1. Listing all resources...")
        resources = await toolchain.list_all_resources()
        print(f"   Found {len(resources)} resources:")
        for _, resource in resources:
            print(f"   - {resource.uri}: {resource.description}")

        # Test reading graph stats
        print("\n2. Reading knowledge://stats...")
        try:
            stats_json = await toolchain.read_resource("knowledge://stats")
            stats = json.loads(stats_json)
            if "error" in stats:
                print(f"   Error from server: {stats['error']}")
            else:
                print(f"   Total nodes: {stats.get('total_nodes', 'N/A')}")
                print(f"   Total edges: {stats.get('total_edges', 'N/A')}")
        except Exception as e:
            print(f"   Error: {e}")

        # Test reading memories list
        print("\n3. Reading knowledge://memories...")
        try:
            memories_json = await toolchain.read_resource("knowledge://memories")
            memories = json.loads(memories_json)
            if "error" in memories:
                print(f"   Error from server: {memories['error']}")
            else:
                count = memories.get("count", 0)
                print(f"   Found {count} memories")
                if count > 0:
                    # Show first memory
                    first = memories["memories"][0]
                    print(f"   First memory: {first['key']}")
        except Exception as e:
            print(f"   Error: {e}")

        # Test reading workflows
        print("\n4. Reading knowledge://workflows...")
        try:
            workflows_json = await toolchain.read_resource("knowledge://workflows")
            workflows = json.loads(workflows_json)
            if "error" in workflows:
                print(f"   Error from server: {workflows['error']}")
            else:
                count = workflows.get("count", 0)
                print(f"   Found {count} workflows")
        except Exception as e:
            print(f"   Error: {e}")

        # Test reading thinking patterns
        print("\n5. Reading knowledge://thinking-patterns...")
        try:
            patterns_json = await toolchain.read_resource(
                "knowledge://thinking-patterns"
            )
            patterns = json.loads(patterns_json)
            if "error" in patterns:
                print(f"   Error from server: {patterns['error']}")
            else:
                count = patterns.get("count", 0)
                print(f"   Found {count} thinking patterns")
        except Exception as e:
            print(f"   Error: {e}")

        # Test reading recent tool usage
        print("\n6. Reading knowledge://tool-usage/recent...")
        try:
            usage_json = await toolchain.read_resource("knowledge://tool-usage/recent")
            usage = json.loads(usage_json)
            if "error" in usage:
                print(f"   Error from server: {usage['error']}")
            else:
                count = usage.get("count", 0)
                print(f"   Found {count} recent tool calls")
        except Exception as e:
            print(f"   Error: {e}")

        # Test resource template (specific memory)
        print("\n7. Testing resource template knowledge://memory/{key}...")
        try:
            memory_json = await toolchain.read_resource(
                "knowledge://memory/test_memory"
            )
            memory = json.loads(memory_json)
            if "error" in memory:
                print(f"   Expected - memory not found: {memory['error']}")
            else:
                print(f"   Memory content: {memory.get('content', 'N/A')[:100]}...")
        except Exception as e:
            print(f"   Error: {e}")

        print("\n✓ Resources test completed")

    finally:
        await toolchain.tool_clients[0].stop()


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing FastMCP Prompts and Resources")
    print("=" * 60)

    # Check for required environment variables
    if not os.getenv("SPARKY_DB_URL"):
        print("\n⚠ Warning: SPARKY_DB_URL not set")
        print("Some tests may fail if database is not configured")

    try:
        await test_prompts()
        await test_resources()
        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())


