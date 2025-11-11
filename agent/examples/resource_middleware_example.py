"""Example demonstrating ResourceFetchingMiddleware usage.

This example shows how to use the ResourceFetchingMiddleware to automatically
fetch and insert resource content into messages using @<resource> syntax.
"""

import asyncio
import os

from dotenv import load_dotenv

from sparky import AgentOrchestrator, ResourceFetchingMiddleware
from sparky.initialization import initialize_toolchain
from sparky.providers import GeminiProvider, ProviderConfig

# Load environment variables
load_dotenv()


async def main():
    """Example of using ResourceFetchingMiddleware."""
    
    # Initialize toolchain with available resources
    toolchain, error = await initialize_toolchain()
    if error:
        print(f"Error initializing toolchain: {error}")
        return
    
    # Create agent orchestrator with ResourceFetchingMiddleware
    model_name = os.getenv("AGENT_MODEL", "gemini-2.0-flash")
    config = ProviderConfig(model_name=model_name)
    provider = GeminiProvider(config)
    
    bot = AgentOrchestrator(
        provider=provider,
        toolchain=toolchain,
        middlewares=[ResourceFetchingMiddleware()],
    )
    
    print("=" * 60)
    print("Resource Fetching Middleware Example")
    print("=" * 60)
    print()
    
    # Example 1: Using full URI
    print("Example 1: Using full resource URI")
    print("-" * 40)
    message1 = "What can you tell me about this? @knowledge://stats"
    print(f"User: {message1}")
    print()
    response1 = await bot.send(message1)
    print(f"Bot: {response1[:200]}...")
    print()
    
    # Example 2: Using short name
    print("Example 2: Using short resource name")
    print("-" * 40)
    message2 = "Show me recent activity @memories"
    print(f"User: {message2}")
    print()
    response2 = await bot.send(message2)
    print(f"Bot: {response2[:200]}...")
    print()
    
    # Example 3: Multiple resources
    print("Example 3: Using multiple resources")
    print("-" * 40)
    message3 = "Compare @stats with @memories and summarize"
    print(f"User: {message3}")
    print()
    response3 = await bot.send(message3)
    print(f"Bot: {response3[:200]}...")
    print()
    
    # Example 4: Resource not found
    print("Example 4: Non-existent resource (error handling)")
    print("-" * 40)
    message4 = "What about @nonexistent resource?"
    print(f"User: {message4}")
    print()
    response4 = await bot.send(message4)
    print(f"Bot: {response4[:200]}...")
    print()
    
    print("=" * 60)
    print("Examples completed!")
    print("=" * 60)
    
    # Cleanup
    await toolchain.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

