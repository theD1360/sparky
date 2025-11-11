"""
Example demonstrating command-style message middleware.

This example shows how to use the CommandPromptMiddleware to enable
slash-command style interactions that map to MCP prompts.

Usage:
    poetry run python examples/command_middleware_example.py
"""

import asyncio
import logging
import os

from sparky import AgentOrchestrator, CommandPromptMiddleware
from sparky.initialization import initialize_toolchain
from sparky.providers import GeminiProvider, ProviderConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main example function."""
    # Initialize toolchain with MCP servers that have prompts
    toolchain, error = await initialize_toolchain()
    if error:
        logger.error("Failed to initialize toolchain: %s", error)
        return

    # Create agent orchestrator with the CommandPromptMiddleware
    model_name = os.getenv("AGENT_MODEL", "gemini-2.0-flash")
    config = ProviderConfig(model_name=model_name)
    provider = GeminiProvider(config)
    
    bot = AgentOrchestrator(
        provider=provider,
        toolchain=toolchain,
        middlewares=[CommandPromptMiddleware()],
    )

    await bot.start_chat()

    print("\n" + "=" * 60)
    print("Command Middleware Demo")
    print("=" * 60)
    print("\nYou can now use slash commands to invoke MCP prompts!")
    print("Example: /discover_concept Python")
    print("\nType 'quit' to exit\n")

    # List available prompts/commands
    try:
        prompts = await bot.list_prompts()
        if prompts:
            print("Available commands:")
            for _, prompt in prompts:
                print(f"  /{prompt.name} - {prompt.description or 'No description'}")
            print()
    except Exception as e:
        logger.warning("Could not list prompts: %s", e)

    # Interactive loop
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            if not user_input:
                continue

            # Send message through the bot (middleware will intercept commands)
            response = await bot.send_message(user_input)
            print(f"\nBot: {response}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error("Error: %s", e)
            continue


if __name__ == "__main__":
    asyncio.run(main())
