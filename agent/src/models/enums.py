"""Enums for Sparky models."""

from enum import Enum


class ResponseStatus(str, Enum):
    """Status values for MCP tool responses."""

    SUCCESS = "success"
    ERROR = "error"
    EMPTY = "empty"


class MessageType(str, Enum):
    """WebSocket message types."""

    personality = "personality"
    message = "message"
    status = "status"
    error = "error"
    tool_use = "tool_use"
    tool_result = "tool_result"
    thought = "thought"
    connect = "connect"
    session_info = "session_info"
    tool_loading_progress = "tool_loading_progress"
    ready = "ready"
    start_chat = "start_chat"
    switch_chat = "switch_chat"
    chat_ready = "chat_ready"
    token_usage = "token_usage"
    token_estimate = "token_estimate"
