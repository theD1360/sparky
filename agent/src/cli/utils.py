"""Utility commands for BadRobot CLI."""

import os
from typing import Optional

import typer

from badmcp.config import MCPConfig
from sparky import AgentOrchestrator
from sparky.providers import GeminiProvider, ProviderConfig
from cli.common import console, logger

app = typer.Typer(name="utils", help="Utility commands")


@app.command("test")
def test():
    """Test your Sparky setup."""
    logger.info("\n🤖 Sparky Setup Test\n")

    # Check for .env file
    logger.info("1. Checking for .env file...")
    if os.path.exists(".env"):
        logger.info("   ✓ .env file found")
    else:
        logger.error("   ✗ .env file not found")
        logger.warning("   → Run: cp .env.example .env")
        logger.warning("   → Then add your GOOGLE_API_KEY to .env")
        raise typer.Exit(1)

    # Check for API key
    logger.info("\n2. Checking for API key...")
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        logger.error("   ✗ GOOGLE_API_KEY not found in .env")
        logger.warning("   → Get an API key: https://makersuite.google.com/app/apikey")
        logger.warning("   → Add it to your .env file")
        raise typer.Exit(1)
    elif api_key == "your_api_key_here":
        logger.error("   ✗ GOOGLE_API_KEY is still set to placeholder")
        logger.warning("   → Replace 'your_api_key_here' with your actual API key")
        raise typer.Exit(1)
    else:
        logger.info(f"   ✓ API key found ({api_key[:8]}...)")

    # Try to create an agent orchestrator
    logger.info("\n3. Testing agent orchestrator initialization...")
    try:
        config = ProviderConfig(model_name="gemini-1.5-pro")
        provider = GeminiProvider(config)
        orchestrator = AgentOrchestrator(provider=provider)
        logger.info("   ✓ AgentOrchestrator initialized successfully")
    except Exception as e:
        logger.error(f"   ✗ Failed to initialize orchestrator: {e}")
        raise typer.Exit(1)

    # Try to generate a response
    logger.info("\n4. Testing orchestrator response...")
    try:
        with console.status("Testing..."):
            response = orchestrator.generate("Say hello in exactly 3 words")
        logger.info(f"   ✓ Orchestrator responded: '{response.strip()}'")
    except Exception as e:
        logger.error(f"   ✗ Failed to get response: {e}")
        raise typer.Exit(1)

    logger.info("\n✅ All tests passed! Your Sparky is ready to go!\n")
    logger.info("Next steps:")
    logger.info("  • Try: sparky client start")
    logger.info("  • Try: sparky generate 'Tell me a joke'")
    logger.info("  • Try: sparky models list\n")


@app.command("version")
def version():
    """Show Sparky version."""
    try:
        from sparky import __version__

        logger.info(f"\nSparky version {__version__}\n")
    except (ImportError, AttributeError):
        # Fallback if __version__ is not defined
        logger.info("\nSparky (version unknown)\n")


@app.command("mcp")
def mcp_config_command(
    action: str = typer.Argument(..., help="Action: list, create, show"),
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to MCP config file"
    ),
):
    """Manage MCP server configuration.

    Actions:
    - list: Show all configured servers
    - create: Create a default badmcp.json config file
    - show: Show current config file path and contents

    Note: Use 'badrobot client start' to automatically use all configured servers.
    """

    if action == "create":
        path = config_path or "badmcp.json"
        try:
            MCPConfig.create_default_config(path)
            logger.info(f"\n✓ Created MCP config file: {path}")
            logger.info("\nEdit this file to add your MCP servers.")
            logger.info("See badmcp.example.json for more examples.")
            logger.info("\nThen run: sparky client start")
            logger.info("All configured servers will be loaded automatically!\n")
        except Exception as e:
            logger.error(f"\nError creating config: {e}\n")
            raise typer.Exit(1)
        return

    # Load configuration
    try:
        config = MCPConfig(config_path)

        if not config.config_path:
            logger.error("\nNo MCP config file found!")
            logger.warning("\nCreate one with:")
            logger.warning("  sparky utils mcp create\n")
            raise typer.Exit(1)

    except Exception as e:
        logger.error(f"\nError loading config: {e}\n")
        raise typer.Exit(1)

    if action == "list":
        logger.info(f"\nMCP Servers ({config.config_path})\n")

        servers = config.get_all_servers()
        if not servers:
            logger.warning("No servers configured")
            logger.info(
                "\nAdd servers to badmcp.json, then run 'badrobot client start'\n"
            )
            return

        for name, server in servers.items():
            logger.info(f"• {name}")
            if server.description:
                logger.info(f"  {server.description}")
            logger.info(f"  Command: {server.command} {' '.join(server.args)}")
            logger.info()

        logger.info("Use all servers: sparky client start")
        logger.info("All configured servers will be loaded automatically!\n")

    elif action == "show":
        logger.info("\nMCP Configuration\n")
        logger.info(f"Config file: {config.config_path}\n")

        try:
            with open(config.config_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info("─" * 60)
            logger.info(content)
            logger.info("─" * 60 + "\n")
        except Exception as e:
            logger.error(f"Error reading file: {e}\n")

    else:
        logger.error(f"\nUnknown action: {action}")
        logger.warning("\nAvailable actions: list, create, show\n")
        raise typer.Exit(1)
