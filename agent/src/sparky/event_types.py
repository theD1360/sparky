"""Event type definitions for Sparky.

This module contains all event name constants used throughout the system.
Centralizing event definitions here prevents circular import issues.
"""


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


class KnowledgeEvents:
    """Event names for knowledge-related operations."""

    MEMORY_LOADED = "knowledge:memory_loaded"
    MEMORY_SAVED = "knowledge:memory_saved"
    TURN_PROCESSED = "knowledge:turn_processed"
    REFLECTION_STARTED = "knowledge:reflection_started"
    REFLECTION_COMPLETED = "knowledge:reflection_completed"
    SUMMARIZATION_STARTED = "knowledge:summarization_started"
    SUMMARIZATION_COMPLETED = "knowledge:summarization_completed"
    KNOWLEDGE_EXTRACTED = "knowledge:knowledge_extracted"


class TaskEvents:
    """Event names for task queue operations."""

    TASK_ADDED = "task:added"
    TASK_AVAILABLE = "task:available"
    TASK_STARTED = "task:started"
    TASK_COMPLETED = "task:completed"
    TASK_FAILED = "task:failed"
    TASK_STATUS_CHANGED = "task:status_changed"
