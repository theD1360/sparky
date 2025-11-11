"""Models listing command for BadRobot CLI."""

import os

import google.generativeai as genai
import typer

from cli.common import logger

app = typer.Typer(name="models", help="List available Google AI models")


@app.command()
def list_models(
    generate_only: bool = typer.Option(
        True,
        "--generate-only/--all",
        help="Show only models that support text generation",
    ),
):
    """List available Google AI models."""
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        logger.error("❌ Error: GOOGLE_API_KEY not found in environment variables\n")
        raise typer.Exit(1)

    if api_key == "your_api_key_here":
        logger.error(
            "❌ Error: Please replace 'your_api_key_here' with your actual API key in .env\n"
        )
        raise typer.Exit(1)

    logger.info("\n🔍 Available Google AI Models\n")

    try:
        genai.configure(api_key=api_key)
        models = genai.list_models()

        count = 0
        for model in models:
            # Filter by generation capability if requested
            if (
                generate_only
                and "generateContent" not in model.supported_generation_methods
            ):
                continue

            count += 1

            # Extract model name
            model_name = model.name.replace("models/", "")

            logger.info(f"✓ {model_name}")
            logger.info(f"  {model.display_name}")
            if model.description:
                logger.info(f"  {model.description}")
            logger.info()

        logger.info(f"Found {count} models\n")

        logger.info("💡 Usage:")
        logger.info("   sparky generate 'your prompt' --model gemini-2.5-flash")
        logger.info("   sparky generate 'your prompt' --model gemini-2.5-pro\n")

    except Exception as e:
        logger.error(f"❌ Error: {e}\n")
        raise typer.Exit(1)
