"""Bot event names for the event system."""


class BotEvents:
    """Bot event names for the event system."""

    LOAD = "bot:load"
    CHAT_STARTED = "bot:chat_started"
    MESSAGE_SENT = "bot:message_sent"
    MESSAGE_RECEIVED = "bot:message_received"
    TURN_COMPLETE = "bot:turn_complete"
    TOOL_USE = "bot:tool_use"
    TOOL_RESULT = "bot:tool_result"
    THOUGHT = "bot:thought"
    SUMMARIZED = "bot:summarized"
    TOKEN_USAGE = "bot:token_usage"
    TOKEN_ESTIMATE = "bot:token_estimate"

