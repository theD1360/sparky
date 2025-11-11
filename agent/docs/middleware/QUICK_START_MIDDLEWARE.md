# Quick Start: Command Middleware

This guide will get you started with the new command-style message middleware in under 5 minutes.

## What is it?

Command middleware allows users to interact with your bot using slash commands (like `/discover_concept Python`) that automatically map to MCP prompts. It's a powerful way to provide a command-line style interface to your bot's capabilities.

## Basic Setup

### 1. Install Sparky

```bash
poetry install
```

### 2. Create a Simple Bot with Command Support

```python
import asyncio
from sparky import Bot, CommandPromptMiddleware
from sparky.initialization import initialize_toolchain

async def main():
    # Initialize toolchain
    toolchain, error = await initialize_toolchain()
    if error:
        print(f"Error: {error}")
        return
    
    # Create bot with CommandPromptMiddleware
    bot = Bot(
        toolchain=toolchain,
        middlewares=[CommandPromptMiddleware()],
    )
    
    await bot.start_chat()
    
    # Now you can use commands!
    response = await bot.send_message("/discover_concept Python")
    print(response)

asyncio.run(main())
```

### 3. Use Slash Commands

Once your bot is running, you can use any available MCP prompt as a command:

```
User: /discover_concept Python
Bot: [Uses the discover_concept prompt to explore Python]

User: /search_memory machine learning
Bot: [Searches memory graph for machine learning content]
```

## How It Works

1. **User sends a command**: `/command_name arguments`
2. **Middleware intercepts**: Recognizes the slash command pattern
3. **Prompt lookup**: Finds the matching MCP prompt
4. **Argument mapping**: Maps the input to prompt arguments
5. **Prompt rendering**: Renders the prompt with arguments
6. **Model receives**: The rendered prompt is sent to the model

## List Available Commands

```python
# Get all available commands
prompts = await bot.list_prompts()
for _, prompt in prompts:
    print(f"/{prompt.name} - {prompt.description}")
```

## Command Syntax

### Simple Command (Single Argument)
```
/discover_concept Python
```
The entire input after the command becomes the first argument.

### Multiple Arguments (Key=Value)
```
/search query="machine learning" depth=3
```
Arguments are parsed as key=value pairs.

### Fallback for Unknown Commands
```
User: /unknown_command test
Bot: I noticed you tried to use '/unknown_command', but it doesn't exist.
     Available commands: discover_concept, search_memory, ...
     For now, I'll process your message normally: test
```

## Creating Custom Message Middleware

You can create your own middleware to process messages:

```python
from sparky import BaseMiddleware, MessageContext, MiddlewareType

class MyMiddleware(BaseMiddleware):
    middleware_type = MiddlewareType.MESSAGE
    
    async def __call__(self, context: MessageContext, next_call):
        # Transform the message
        context.modified_message = context.message.upper()
        
        # Continue to next middleware
        return await next_call(context)

# Add to bot
bot = Bot(
    middlewares=[
        MyMiddleware(),
        CommandPromptMiddleware(),
    ],
    toolchain=toolchain
)
```

## Examples

Run the included example:

```bash
poetry run python examples/command_middleware_example.py
```

## Next Steps

- Read the [full documentation](MESSAGE_MIDDLEWARE.md) for advanced usage
- Learn about [tool call middleware](MIDDLEWARE.md)
- Explore [MCP prompts](MCP_PROMPTS.md)

## Common Use Cases

1. **Command-line style bot interactions**
2. **Shortcut commands for common operations**
3. **Message preprocessing and transformation**
4. **Content filtering and validation**
5. **Multi-step command workflows**

## Troubleshooting

**Commands not working?**
- Make sure your MCP servers are properly configured
- Check that prompts are available: `await bot.list_prompts()`
- Verify CommandPromptMiddleware is added to middlewares list

**Need help?**
- Check the [full documentation](MESSAGE_MIDDLEWARE.md)
- See [examples](../examples/command_middleware_example.py)
- Review the [tests](../tests/test_message_middleware.py)

