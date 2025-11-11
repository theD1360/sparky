"""Generate command for Sparky CLI."""

from typing import Optional

import typer

from sparky import AgentOrchestrator
from sparky.providers import GeminiProvider, ProviderConfig
from cli.common import console, logger

app = typer.Typer(name="generate", help="Generate a one-off response")


@app.command()
def generate(
    prompt: str = typer.Argument(..., help="The prompt to generate from"),
    model: str = typer.Option(
        "gemini-2.5-flash", "--model", "-m", help="Gemini model to use"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save output to a file"
    ),
):
    """Generate a one-off response from a prompt."""
    try:
        config = ProviderConfig(model_name=model)
        provider = GeminiProvider(config)
        orchestrator = AgentOrchestrator(provider=provider)

        with console.status(f"Generating with {model}..."):
            response = orchestrator.generate(prompt)

        logger.info("\nResponse:")
        logger.info(response)
        logger.info()

        # Save to file if requested
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(response)
            logger.info(f"✓ Saved to {output_file}\n")

    except ValueError as e:
        logger.error(f"\n❌ Error: {e}\n")
        raise typer.Exit(1)
    except Exception as e:
        logger.error(f"\n❌ An error occurred: {e}\n")
        raise typer.Exit(1)
