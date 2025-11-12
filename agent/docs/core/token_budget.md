# Token Budget Configuration

## Overview

Sparky now supports configurable token budget management, allowing you to control what percentage of the model's context window the agent can use for conversation history. This helps optimize token usage, reduce costs, and ensure the agent stays within safe operational limits.

## Configuration

### Environment Variable

Set the `SPARKY_TOKEN_BUDGET_PERCENT` environment variable to control the token budget:

```bash
# Use 80% of the model's context window (default)
export SPARKY_TOKEN_BUDGET_PERCENT=0.8

# Use 60% for more conservative token usage
export SPARKY_TOKEN_BUDGET_PERCENT=0.6

# Use 90% for maximum context
export SPARKY_TOKEN_BUDGET_PERCENT=0.9
```

### Docker Compose

The environment variable is already configured in `docker-compose.yml` with a default value:

```yaml
environment:
  - SPARKY_TOKEN_BUDGET_PERCENT=${SPARKY_TOKEN_BUDGET_PERCENT:-0.8}
```

You can override this in your `.env` file:

```env
SPARKY_TOKEN_BUDGET_PERCENT=0.7
```

### Valid Range

- **Minimum:** 0.1 (10% of context window)
- **Maximum:** 1.0 (100% of context window)
- **Default:** 0.8 (80% of context window)

Values outside this range will be automatically clamped to the nearest valid value.

## How It Works

### Model-Specific Context Windows

Sparky automatically detects the context window size based on the model:

| Model | Context Window |
|-------|----------------|
| Gemini 2.0 Flash | 1,048,576 tokens (1M) |
| Gemini 1.5 Flash | 1,048,576 tokens (1M) |
| Gemini 1.5 Pro | 2,097,152 tokens (2M) |
| Gemini Pro | 32,768 tokens (32K) |
| Gemini Pro Vision | 16,384 tokens (16K) |

### Effective Token Budget Calculation

The effective token budget is calculated as:

```
Effective Budget = Context Window × Token Budget Percent
```

**Examples:**

- **Gemini 2.0 Flash** with 80% budget: 1,048,576 × 0.8 = **838,860 tokens**
- **Gemini 1.5 Pro** with 70% budget: 2,097,152 × 0.7 = **1,467,806 tokens**
- **Gemini Pro** with 60% budget: 32,768 × 0.6 = **19,660 tokens**

### Message Loading Strategy

When loading conversation history, Sparky uses the token budget to determine how much history to include:

1. **Token-based limiting** (default): Loads messages that fit within the token budget
2. **Summary preference**: Prioritizes loading from the most recent summary forward
3. **Smart truncation**: Includes most recent messages first, working backward until the budget is reached

This ensures that:
- The agent never exceeds the configured token budget
- Recent context is always preserved
- Older messages are automatically summarized and compressed
- The agent maintains efficient token usage

### Automatic Token-Based Summarization

Sparky automatically summarizes conversations when they approach the token budget threshold. This proactive summarization happens during chat session initialization, before loading message history.

#### Configuration

Set the `SPARKY_SUMMARY_TOKEN_THRESHOLD` environment variable to control when summarization triggers:

```bash
# Summarize at 85% of token budget (default)
export SPARKY_SUMMARY_TOKEN_THRESHOLD=0.85

# More aggressive - summarize at 75%
export SPARKY_SUMMARY_TOKEN_THRESHOLD=0.75

# Conservative - summarize at 90%
export SPARKY_SUMMARY_TOKEN_THRESHOLD=0.90
```

**Docker Compose:**

```yaml
environment:
  - SPARKY_SUMMARY_TOKEN_THRESHOLD=${SPARKY_SUMMARY_TOKEN_THRESHOLD:-0.85}
```

#### Valid Range

- **Minimum:** 0.5 (50% of token budget)
- **Maximum:** 0.95 (95% of token budget)
- **Default:** 0.85 (85% of token budget)

#### How It Works

1. **Check During Start:** When starting a chat session, Sparky checks if messages since the last summary exceed the threshold
2. **Token Estimation:** Estimates the token count of unsummarized messages
3. **Threshold Comparison:** Compares against `token_budget × summary_threshold`
4. **Proactive Summarization:** If threshold is met, generates a summary before loading messages
5. **Graph Storage:** Summary is saved to knowledge graph for future reference
6. **Efficient Loading:** Next load automatically includes summary and only recent messages

**Example Calculation (Gemini 2.0 Flash with 80% budget):**
- Context window: 1,048,576 tokens
- Token budget (80%): 838,860 tokens
- Summary threshold (85%): 712,831 tokens
- **Summarizes when:** Messages exceed ~713K tokens

#### Migration from Turn-Based Summarization

**Deprecated Parameters:**
- `enable_turn_summarization` - No longer used
- `summary_turn_threshold` - Replaced by token-based threshold
- `SPARKY_SUMMARY_EVERY` - Replaced by `SPARKY_SUMMARY_TOKEN_THRESHOLD`

**Benefits of Token-Based Approach:**
- **More Accurate:** Based on actual token usage, not message count
- **Proactive:** Summarizes before hitting limits
- **Consistent:** Works seamlessly with token budget system
- **Simpler:** Single check point during chat initialization
- **Efficient:** No need to restart chat sessions

**Backward Compatibility:**

The old parameters are deprecated but won't break existing code. A warning will be logged if they're used:

```
WARNING: enable_turn_summarization and summary_turn_threshold are deprecated.
Token-based summarization is now used automatically.
Use SPARKY_SUMMARY_TOKEN_THRESHOLD to configure.
```

## Usage Examples

### Conservative Budget (60%)

Good for:
- Cost-sensitive applications
- Models with smaller context windows
- Tasks requiring frequent model interactions

```bash
export SPARKY_TOKEN_BUDGET_PERCENT=0.6
```

**Gemini 2.0 Flash:** 629,145 tokens available for history

### Default Budget (80%)

Good for:
- Balanced token usage and context retention
- Most general-purpose applications
- Standard conversational agents

```bash
export SPARKY_TOKEN_BUDGET_PERCENT=0.8  # or omit for default
```

**Gemini 2.0 Flash:** 838,860 tokens available for history

### Aggressive Budget (95%)

Good for:
- Maximum context retention
- Complex multi-turn conversations
- Analysis tasks requiring extensive history

```bash
export SPARKY_TOKEN_BUDGET_PERCENT=0.95
```

**Gemini 2.0 Flash:** 996,147 tokens available for history

## Programmatic Usage

### Provider Configuration

You can also set the token budget programmatically when creating a provider:

```python
from sparky.providers import ProviderConfig, GeminiProvider

# Create config with explicit token budget
config = ProviderConfig(
    model_name="gemini-2.0-flash",
    token_budget_percent=0.7
)

provider = GeminiProvider(config)
```

### Custom Context Window

Override the automatic context window detection:

```python
config = ProviderConfig(
    model_name="gemini-2.0-flash",
    context_window=500000,  # Custom limit
    token_budget_percent=0.8
)
```

### Getting Effective Budget

```python
from sparky.agent_orchestrator import AgentOrchestrator

# Create orchestrator
orchestrator = AgentOrchestrator(provider=provider)

# Get the effective token budget
budget = orchestrator.get_effective_token_budget()
print(f"Effective token budget: {budget} tokens")
```

## Monitoring Token Usage

The agent logs token budget information at startup:

```
INFO: Using token budget: 80.0% of context window
DEBUG: Token budget: 838860 tokens (80.0% of 1048576)
```

Monitor these logs to understand your token usage patterns and adjust the budget accordingly.

## Best Practices

1. **Start with the default (80%)**: This provides a good balance for most applications

2. **Monitor your usage**: Check logs to see if you're consistently hitting the limit

3. **Adjust based on needs**: 
   - Decrease for cost optimization
   - Increase for complex, context-heavy tasks

4. **Consider model differences**: Larger context windows (like Gemini 1.5 Pro's 2M) allow for lower percentages while still maintaining substantial history

5. **Use summaries**: Sparky's automatic summarization works hand-in-hand with token budgets to maintain context efficiency

## Troubleshooting

### "Token budget too low" warnings

If you see frequent truncation, consider:
- Increasing the `SPARKY_TOKEN_BUDGET_PERCENT` value
- Enabling more aggressive summarization
- Checking if your prompts are too long

### Context seems insufficient

Try increasing the budget:
```bash
export SPARKY_TOKEN_BUDGET_PERCENT=0.9
```

### High token costs

Try decreasing the budget:
```bash
export SPARKY_TOKEN_BUDGET_PERCENT=0.6
```

## Technical Details

### Implementation

- **Base Provider**: `ProviderConfig` includes `token_budget_percent` and `context_window` fields
- **Provider-specific**: Each provider (e.g., `GeminiProvider`) implements `get_model_context_window()` to return model-specific limits
- **Agent Orchestrator**: Reads `SPARKY_TOKEN_BUDGET_PERCENT` environment variable and calculates effective budget
- **Message Service**: Uses `get_messages_within_token_limit()` to respect the budget when loading history

### Testing

Run the token budget tests:

```bash
poetry run pytest tests/sparky/test_token_budget.py -v
```

This validates:
- Configuration parsing
- Budget calculation
- Model-specific context windows
- Message loading with token limits
- Environment variable handling

