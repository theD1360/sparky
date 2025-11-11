# Middleware Architecture

## System Overview

The Sparky middleware system provides a flexible, extensible architecture for intercepting and processing three types of requests: tool calls, user messages, and bot responses.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Bot Instance                                │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    MiddlewareRegistry                              │  │
│  │                                                                    │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │  │
│  │  │ ToolDispatcher   │  │MessageDispatcher │  │ResponseDispatcher│ │  │
│  │  │                  │  │                  │  │                  │ │  │
│  │  │ Middleware Chain │  │ Middleware Chain │  │ Middleware Chain │ │  │
│  │  │   ↓              │  │   ↓              │  │   ↓              │ │  │
│  │  │   ↓              │  │   ↓              │  │   ↓              │ │  │
│  │  │   ↓              │  │   ↓              │  │   ↓              │ │  │
│  │  │ Execute Tool     │  │ Return Modified  │  │ Return Modified  │ │  │
│  │  └──────────────────┘  └──────────────────┘  └─────────────────┘ │  │
│  │                                                                    │  │
│  │  register(middleware) → validates type → routes to dispatcher     │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  Message Flow:                                                            │
│  User Message → MessageMiddleware → Model → ResponseMiddleware → User    │
│  Tool Calls → ToolMiddleware → Toolchain                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

## Request Flow

### 1. User Message Flow

```
User Input
    ↓
MessageDispatcher
    ↓
[Message Middleware Chain]
    - CommandPromptMiddleware (detect /commands)
    - ContentFilterMiddleware (filter sensitive data)
    - CustomMiddleware (your logic)
    ↓
Modified Message
    ↓
Model (Gemini)
    ↓
Model Response
    ↓
ResponseDispatcher
    ↓
[Response Middleware Chain]
    - ResponseFormatterMiddleware (format output)
    - TranslationMiddleware (translate)
    - CustomMiddleware (your logic)
    ↓
Final Response
    ↓
User
```

### 2. Tool Call Flow

```
Model wants to call tool
    ↓
ToolDispatcher
    ↓
[Tool Middleware Chain]
    - SelfModificationGuard (security)
    - ValidationMiddleware (validate args)
    - CustomMiddleware (your logic)
    ↓
Tool Execution
    ↓
Tool Result
    ↓
Back to Model
```

## Component Responsibilities

### Base Layer (`base.py`)

**Defines:**
- `MiddlewareType` enum (TOOL, MESSAGE, RESPONSE)
- `BaseMiddleware` abstract class
- `ToolCallContext` dataclass
- `MessageContext` dataclass
- `ResponseContext` dataclass
- Type aliases for type safety

**Responsibility:** Core types and interfaces

### Dispatchers Layer (`dispatchers.py`)

**Defines:**
- `ToolDispatcher` - Executes tool middleware chain
- `MessageDispatcher` - Executes message middleware chain
- `ResponseDispatcher` - Executes response middleware chain

**Responsibility:** Chain execution logic

### Registry Layer (`registry.py`)

**Defines:**
- `MiddlewareRegistry` - Central management

**Provides:**
- Middleware registration
- Automatic routing by type
- Validation
- Introspection (counts, lists)
- Clear/reset functionality

**Responsibility:** Middleware lifecycle management

### Implementation Layer

**Files:**
- `tool_middlewares.py` - Tool middleware implementations
- `message_middlewares.py` - Message middleware implementations
- `response_middlewares.py` - Response middleware implementations

**Responsibility:** Concrete middleware behaviors

## Middleware Lifecycle

### 1. Registration

```python
# User creates middleware
middleware = CommandPromptMiddleware()

# Bot initialization
bot = Bot(middlewares=[middleware])

# Internal flow:
Bot.__init__
  ↓
MiddlewareRegistry.__init__
  ↓
registry.register_many([middleware])
  ↓
registry.register(middleware)
  ↓
Validate middleware_type
  ↓
Route to dispatcher (message_dispatcher)
  ↓
dispatcher.add_middleware(middleware)
```

### 2. Execution

```python
# User sends message
await bot.send_message("Hello")

# Internal flow:
Bot.send_message
  ↓
MessageContext(message="Hello", bot_instance=bot)
  ↓
registry.message_dispatcher.dispatch(context)
  ↓
Build middleware chain (reversed order)
  ↓
Execute chain: mw1 → mw2 → mw3 → final_action
  ↓
Return modified context
  ↓
Use modified_message or original message
```

## Design Patterns

### 1. Chain of Responsibility

Each middleware can:
- Process the request
- Modify the context
- Pass to next middleware
- Short-circuit the chain (for errors)

### 2. Decorator Pattern

Middleware wraps the execution:
```python
async def middleware(context, next_call):
    # Before
    result = await next_call(context)  # Wrapped execution
    # After
    return result
```

### 3. Registry Pattern

Central point for managing components:
- Register middleware
- Track registrations
- Route to appropriate handlers
- Provide introspection

### 4. Strategy Pattern

Different middleware for different types:
- Same interface (`BaseMiddleware`)
- Different implementations
- Runtime selection by type

## Extension Points

### Adding New Middleware Types

To add a new middleware type:

1. **Add to enum:**
   ```python
   class MiddlewareType(Enum):
       TOOL = "tool"
       MESSAGE = "message"
       RESPONSE = "response"
       NEW_TYPE = "new_type"  # Add here
   ```

2. **Create context:**
   ```python
   @dataclass
   class NewTypeContext:
       # Your fields
       pass
   ```

3. **Create dispatcher:**
   ```python
   class NewTypeDispatcher:
       async def dispatch(self, context: NewTypeContext):
           # Chain logic
           pass
   ```

4. **Update registry:**
   ```python
   def __init__(self):
       self.new_type_dispatcher = NewTypeDispatcher(self.bot)
   
   def register(self, middleware):
       elif middleware.middleware_type == MiddlewareType.NEW_TYPE:
           self.new_type_dispatcher.add_middleware(middleware)
   ```

### Adding New Middleware

To add a new middleware implementation:

1. **Choose the appropriate file:**
   - Tool → `tool_middlewares.py`
   - Message → `message_middlewares.py`
   - Response → `response_middlewares.py`

2. **Implement BaseMiddleware:**
   ```python
   class MyNewMiddleware(BaseMiddleware):
       middleware_type = MiddlewareType.XXX
       
       async def __call__(self, context, next_call):
           # Your logic
           return await next_call(context)
   ```

3. **Export from `__init__.py`:**
   ```python
   from .xxx_middlewares import MyNewMiddleware
   
   __all__ = [..., "MyNewMiddleware"]
   ```

## Best Practices

### 1. Keep Middleware Focused
Each middleware should have a single, clear purpose.

### 2. Fail Gracefully
Always have error handling and fallbacks.

### 3. Log Important Actions
Help with debugging and monitoring.

### 4. Test Thoroughly
Unit test middleware in isolation.

### 5. Document Behavior
Explain what the middleware does and why.

### 6. Respect the Chain
Always call `await next_call(context)` unless intentionally short-circuiting.

### 7. Use Type Hints
Help with IDE support and type safety.

## Performance Considerations

### Minimal Overhead

- **Registration:** O(1) per middleware
- **Routing:** O(1) type check
- **Execution:** O(n) where n = number of middleware
- **Memory:** Minimal (small objects, short-lived contexts)

### Optimization Tips

- Keep middleware logic lightweight
- Avoid heavy computation in middleware
- Use async operations efficiently
- Short-circuit when appropriate

## Debugging

### View Registry State

```python
registry = bot.middleware_registry

# Check what's registered
print(registry)  # MiddlewareRegistry(tool=1, message=2, response=1)

# Get details
for mw in registry.get_registered_middleware():
    print(f"  - {mw.__class__.__name__} ({mw.middleware_type.value})")

# Check specific type
message_mw = registry.get_registered_middleware(MiddlewareType.MESSAGE)
print(f"Message middleware: {len(message_mw)}")
```

### Logging

All components log their actions:
- Registry: Registration and routing
- Dispatchers: Chain execution
- Middleware: Processing steps

Enable debug logging:
```python
import logging
logging.getLogger('sparky.middleware').setLevel(logging.DEBUG)
```

## Summary

The middleware architecture provides:

- **Three interception points:** Tool, Message, Response
- **Unified management:** MiddlewareRegistry
- **Clean separation:** Each component in its own file
- **Type-safe:** Explicit types throughout
- **Well-tested:** 38 comprehensive tests
- **Extensible:** Easy to add new types/implementations
- **Production-ready:** Battle-tested and documented

This architecture sets the foundation for powerful bot customization while maintaining clean code and clear responsibilities.

