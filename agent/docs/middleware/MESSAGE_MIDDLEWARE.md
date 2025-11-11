# Message Middleware

Message middleware allows you to intercept and modify user messages before they are sent to the AI model. This is useful for implementing custom command handlers, message transformation, content filtering, and more.

## Overview

The message middleware system works similarly to tool call middleware but operates on incoming user messages. Each middleware in the chain can:
- Inspect the message
- Modify the message before it reaches the model
- Skip sending to the model entirely and provide a direct response
- Access the bot instance for additional functionality

## Basic Usage

```python
from sparky import Bot, BaseMiddleware, MessageContext, MiddlewareType

# Create a custom message middleware
class MyMessageMiddleware(BaseMiddleware):
    middleware_type = MiddlewareType.MESSAGE
    
    async def __call__(self, context: MessageContext, next_call):
        # Modify the message
        context.modified_message = context.message.upper()
        
        # Continue to next middleware
        return await next_call(context)

# Add middleware to bot
bot = Bot(
    middlewares=[MyMessageMiddleware()],
    toolchain=toolchain
)
```

## Built-in Middleware

### CommandPromptMiddleware

The `CommandPromptMiddleware` enables slash-command style interactions that automatically map to MCP prompts.

#### Features

- Detects messages in the format `/<command> <input>`
- Automatically retrieves the corresponding MCP prompt
- Renders the prompt with appropriate arguments
- Provides helpful error messages for unknown commands

#### Usage

```python
from sparky import Bot, CommandPromptMiddleware

bot = Bot(
    middlewares=[CommandPromptMiddleware()],
    toolchain=toolchain
)

await bot.start_chat()

# User sends: "/discover_concept Python"
# Middleware intercepts and uses the discover_concept prompt
response = await bot.send_message("/discover_concept Python")
```

#### Command Syntax

**Single Argument:**
```
/command_name value
```
Example: `/discover_concept Python`

**Multiple Arguments (key=value format):**
```
/command_name arg1=value1 arg2=value2
```
Example: `/search_memory query="machine learning" depth=3`

**Positional (first argument):**
```
/command_name value
```
The value will be passed to the first argument defined in the prompt.

#### How It Works

1. User sends a message starting with `/`
2. Middleware parses the command name and input
3. Checks if a matching MCP prompt exists
4. If found:
   - Parses arguments based on prompt schema
   - Renders the prompt with arguments
   - Replaces the message with the rendered prompt
5. If not found:
   - Provides suggestions for similar commands
   - Falls back to processing the input normally

#### Error Handling

The middleware gracefully handles errors:

```
User: /unknowncommand test
Bot: I noticed you tried to use the command '/unknowncommand', but it doesn't exist. 
     Available commands: discover_concept, search_memory, ...
     For now, I'll process your message normally: test
```

## Creating Custom Message Middleware

### Basic Structure

```python
from sparky import BaseMiddleware, MessageContext, MiddlewareType

class CustomMiddleware(BaseMiddleware):
    middleware_type = MiddlewareType.MESSAGE
    
    async def __call__(self, context: MessageContext, next_call):
        # Your logic here
        
        # Access the original message
        original = context.message
        
        # Modify the message
        context.modified_message = self.transform(original)
        
        # Or provide a direct response (skip model)
        # context.skip_model = True
        # context.response = "Direct response"
        
        # Continue to next middleware
        return await next_call(context)
    
    def transform(self, message: str) -> str:
        # Your transformation logic
        return message
```

### MessageContext Fields

- `message` (str): Original user message
- `modified_message` (Optional[str]): Modified message to send to model
- `skip_model` (bool): If True, skip model and use direct response
- `response` (Optional[str]): Direct response (when skip_model=True)
- `bot_instance` (Optional[Any]): Reference to Bot instance

### Example: Content Filter Middleware

```python
class ContentFilterMiddleware(BaseMiddleware):
    """Filter out sensitive information from messages."""
    
    middleware_type = MiddlewareType.MESSAGE
    
    PATTERNS = [
        (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN REDACTED]'),  # SSN
        (r'\b\d{16}\b', '[CARD REDACTED]'),  # Credit card
    ]
    
    async def __call__(self, context: MessageContext, next_call):
        import re
        
        filtered = context.message
        for pattern, replacement in self.PATTERNS:
            filtered = re.sub(pattern, replacement, filtered)
        
        if filtered != context.message:
            context.modified_message = filtered
            logger.info("Filtered sensitive content from message")
        
        return await next_call(context)
```

### Example: Command Alias Middleware

```python
class AliasMiddleware(BaseMiddleware):
    """Expand command aliases."""
    
    middleware_type = MiddlewareType.MESSAGE
    
    ALIASES = {
        "/help": "What can you help me with?",
        "/status": "What is the current status of all tasks?",
        "/bye": "Goodbye!",
    }
    
    async def __call__(self, context: MessageContext, next_call):
        msg = context.message.strip()
        
        if msg in self.ALIASES:
            context.modified_message = self.ALIASES[msg]
        
        return await next_call(context)
```

### Example: Direct Response Middleware

```python
class QuickResponseMiddleware(BaseMiddleware):
    """Provide direct responses for simple queries."""
    
    middleware_type = MiddlewareType.MESSAGE
    
    async def __call__(self, context: MessageContext, next_call):
        msg = context.message.strip().lower()
        
        if msg == "ping":
            # Skip the model and provide direct response
            context.skip_model = True
            context.response = "Pong!"
            return context
        
        # Continue normally for other messages
        return await next_call(context)
```

## Middleware Chain Order

Middlewares are executed in the order they are added:

```python
bot = Bot(
    middlewares=[
        AliasMiddleware(),          # 1. Expand aliases first
        ContentFilterMiddleware(),   # 2. Filter content second
        CommandPromptMiddleware(),   # 3. Process commands last
    ]
)
```

Each middleware can modify the message and pass it to the next one in the chain.

Note: Tool middlewares and message middlewares are automatically routed to their appropriate dispatchers based on their `middleware_type` attribute.

## Advanced: Accessing Bot Functionality

Middleware can access the bot instance to use its methods:

```python
class ContextEnricherMiddleware(BaseMiddleware):
    middleware_type = MiddlewareType.MESSAGE
    
    async def __call__(self, context: MessageContext, next_call):
        bot = context.bot_instance
        
        # Access bot methods
        if bot and bot.knowledge:
            # Add relevant context from knowledge graph
            relevant_info = await bot.knowledge.search("relevant topic")
            context.modified_message = (
                f"{context.message}\n\n"
                f"[Context: {relevant_info}]"
            )
        
        return await next_call(context)
```

## Testing

Test your middleware in isolation:

```python
import pytest
from sparky import MessageContext

@pytest.mark.asyncio
async def test_custom_middleware():
    middleware = CustomMiddleware()
    
    async def mock_next(ctx):
        return ctx
    
    context = MessageContext(message="test input")
    result = await middleware(context, mock_next)
    
    assert result.modified_message == "EXPECTED OUTPUT"
```

## Best Practices

1. **Always call `next_call(context)`** unless you're providing a direct response
2. **Keep middleware focused** - each middleware should do one thing well
3. **Handle errors gracefully** - don't break the chain on errors
4. **Log important actions** - help with debugging
5. **Document your middleware** - explain what it does and why
6. **Test thoroughly** - especially edge cases and error conditions

## See Also

- [Tool Call Middleware](./MIDDLEWARE.md) - For intercepting tool calls
- [MCP Prompts](./MCP_PROMPTS.md) - For working with prompts
- [Bot API](./API.md) - For bot methods and properties

