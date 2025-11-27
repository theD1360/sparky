"""WebSocket message models for Sparky."""

from __future__ import annotations

import json
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, ValidationError

from models.enums import MessageType


class PersonalityPayload(BaseModel):
    text: str = Field(min_length=1, description="Initial system/personality prompt")


class ChatMessagePayload(BaseModel):
    text: str = Field(default="<Empty message>", description="User chat message text")
    file_id: Optional[str] = Field(None, description="Optional file node ID for attachments")
    task_id: Optional[str] = Field(None, description="Optional task ID if message is from task execution")


class StatusPayload(BaseModel):
    message: str
    task_id: Optional[str] = Field(None, description="Optional task ID if status is from task execution")


class ErrorPayload(BaseModel):
    message: str
    task_id: Optional[str] = Field(None, description="Optional task ID if error is from task execution")


class ToolUsePayload(BaseModel):
    name: str
    args: dict
    task_id: Optional[str] = Field(None, description="Optional task ID if tool use is from task execution")


class ToolResultPayload(BaseModel):
    name: str
    result: str
    status: Optional[str] = Field(None, description="Tool execution status: 'success' or 'error'")
    result_content: Optional[Any] = Field(None, description="Structured result content (dict/list)")
    messages: Optional[list] = Field(None, description="Additional messages from tool execution")
    task_id: Optional[str] = Field(None, description="Optional task ID if tool result is from task execution")


class ThoughtPayload(BaseModel):
    text: str = Field(min_length=1, description="AI thinking/reasoning text")
    task_id: Optional[str] = Field(None, description="Optional task ID if thought is from task execution")


class ConnectPayload(BaseModel):
    personality: Optional[str] = Field(None, description="Personality prompt")
    history: Optional[list] = Field(None, description="History of messages")
    user_id: Optional[str] = Field(None, description="User identifier (deprecated, use token)")
    token: Optional[str] = Field(None, description="JWT authentication token")
    chat_id: Optional[str] = Field(None, description="Chat identifier for grouping messages")
    chat_name: Optional[str] = Field(None, description="Display name for the chat")


class ToolLoadingProgressPayload(BaseModel):
    tool_name: str = Field(description="Name of the tool being loaded")
    status: str = Field(description="Status: loading, loaded, or error")
    message: str = Field(description="Progress message")


class ReadyPayload(BaseModel):
    tools_loaded: int = Field(description="Number of tools successfully loaded")


class StartChatPayload(BaseModel):
    chat_id: str = Field(description="Chat identifier to start/create")
    chat_name: Optional[str] = Field(None, description="Display name for the chat")


class SwitchChatPayload(BaseModel):
    chat_id: str = Field(description="Chat identifier to switch to")


class ChatReadyPayload(BaseModel):
    chat_id: str = Field(description="Chat identifier")
    is_new: bool = Field(description="Whether this is a newly created chat")


class TokenUsagePayload(BaseModel):
    input_tokens: int = Field(description="Number of input tokens used")
    output_tokens: int = Field(description="Number of output tokens generated")
    total_tokens: int = Field(description="Total tokens used (input + output)")
    cached_tokens: Optional[int] = Field(None, description="Number of cached tokens (if applicable)")


class TokenEstimatePayload(BaseModel):
    estimated_tokens: int = Field(description="Estimated number of tokens")
    source: str = Field(description="Source of the estimate (e.g., 'history', 'message', 'thought', 'tool_call')")


Payload = Union[
    PersonalityPayload,
    ChatMessagePayload,
    StatusPayload,
    ErrorPayload,
    ToolUsePayload,
    ToolResultPayload,
    ThoughtPayload,
    ConnectPayload,
    ToolLoadingProgressPayload,
    ReadyPayload,
    StartChatPayload,
    SwitchChatPayload,
    ChatReadyPayload,
    TokenUsagePayload,
    TokenEstimatePayload,
]


class WSMessage(BaseModel):
    type: MessageType
    data: Payload
    user_id: Optional[str] = Field(None, description="User identifier for message validation")
    chat_id: Optional[str] = Field(None, description="Chat identifier for message validation")

    @classmethod
    def from_dict(cls, obj: dict) -> "WSMessage":
        # Tolerate legacy keys
        msg_type = obj.get("type")
        data = obj.get("data")
        user_id = obj.get("user_id")
        chat_id = obj.get("chat_id")
        if msg_type is None:
            raise ValidationError(
                [{"loc": ("type",), "msg": "Missing type", "type": "value_error"}], cls
            )
        # Route to specific payload model
        mt = MessageType(msg_type)
        if mt == MessageType.personality:
            payload = PersonalityPayload.model_validate(
                data if isinstance(data, dict) else {"text": data}
            )
        elif mt == MessageType.message:
            payload = ChatMessagePayload.model_validate(
                data if isinstance(data, dict) else {"text": data}
            )
        elif mt == MessageType.status:
            payload = StatusPayload.model_validate(
                data if isinstance(data, dict) else {"message": str(data)}
            )
        elif mt == MessageType.error:
            payload = ErrorPayload.model_validate(
                data if isinstance(data, dict) else {"message": str(data)}
            )
        elif mt == MessageType.tool_use:
            if isinstance(data, dict):
                payload = ToolUsePayload.model_validate(data)
            else:
                # tolerate legacy shape if someone sent a string
                payload = ToolUsePayload(name=str(data), args={})
        elif mt == MessageType.tool_result:
            if isinstance(data, dict):
                payload = ToolResultPayload.model_validate(data)
            else:
                payload = ToolResultPayload(name=str(data), result="", status=None)
        elif mt == MessageType.thought:
            payload = ThoughtPayload.model_validate(
                data if isinstance(data, dict) else {"text": str(data)}
            )
        elif mt == MessageType.connect:
            payload = ConnectPayload.model_validate(
                data if isinstance(data, dict) else {}
            )
        elif mt == MessageType.tool_loading_progress:
            if isinstance(data, dict):
                payload = ToolLoadingProgressPayload.model_validate(data)
            else:
                payload = ToolLoadingProgressPayload(
                    tool_name=str(data), status="unknown", message=str(data)
                )
        elif mt == MessageType.ready:
            if isinstance(data, dict):
                payload = ReadyPayload.model_validate(data)
            else:
                payload = ReadyPayload(tools_loaded=0)
        elif mt == MessageType.start_chat:
            if isinstance(data, dict):
                payload = StartChatPayload.model_validate(data)
            else:
                payload = StartChatPayload(chat_id=str(data))
        elif mt == MessageType.switch_chat:
            if isinstance(data, dict):
                payload = SwitchChatPayload.model_validate(data)
            else:
                payload = SwitchChatPayload(chat_id=str(data))
        elif mt == MessageType.chat_ready:
            if isinstance(data, dict):
                payload = ChatReadyPayload.model_validate(data)
            else:
                payload = ChatReadyPayload(chat_id=str(data), is_new=False)
        elif mt == MessageType.token_usage:
            if isinstance(data, dict):
                payload = TokenUsagePayload.model_validate(data)
            else:
                # Fallback - shouldn't happen
                payload = TokenUsagePayload(input_tokens=0, output_tokens=0, total_tokens=0)
        elif mt == MessageType.token_estimate:
            if isinstance(data, dict):
                payload = TokenEstimatePayload.model_validate(data)
            else:
                # Fallback - shouldn't happen
                payload = TokenEstimatePayload(estimated_tokens=0, source="unknown")
        else:
            # Fallback shouldn't happen due to Enum, but keep for safety
            payload = StatusPayload(message=str(data))
        return cls(type=mt, data=payload, user_id=user_id, chat_id=chat_id)

    @classmethod
    def from_text(cls, text: str) -> "WSMessage":
        obj = json.loads(text)
        return cls.from_dict(obj)

    def to_dict(self) -> dict:
        # Keep wire format: { "type": str, "data": <payload_as_dict_or_primitive>, "session_id": str, ... }
        data: dict | str
        if isinstance(self.data, PersonalityPayload):
            data = {"text": self.data.text}
        elif isinstance(self.data, ChatMessagePayload):
            data = {"text": self.data.text}
            if self.data.file_id:
                data["file_id"] = self.data.file_id
            if self.data.task_id:
                data["task_id"] = self.data.task_id
        elif isinstance(self.data, StatusPayload):
            data = {"message": self.data.message}
            if self.data.task_id:
                data["task_id"] = self.data.task_id
        elif isinstance(self.data, ErrorPayload):
            data = {"message": self.data.message}
            if self.data.task_id:
                data["task_id"] = self.data.task_id
        elif isinstance(self.data, ToolUsePayload):
            data = {"name": self.data.name, "args": self.data.args}
            if self.data.task_id:
                data["task_id"] = self.data.task_id
        elif isinstance(self.data, ToolResultPayload):
            data = {"name": self.data.name, "result": self.data.result}
            if self.data.status:
                data["status"] = self.data.status
            if self.data.result_content is not None:
                data["result_content"] = self.data.result_content
            if self.data.messages:
                data["messages"] = self.data.messages
            if self.data.task_id:
                data["task_id"] = self.data.task_id
        elif isinstance(self.data, ThoughtPayload):
            data = {"text": self.data.text}
            if self.data.task_id:
                data["task_id"] = self.data.task_id
        elif isinstance(self.data, ConnectPayload):
            data = {}
        elif isinstance(self.data, ToolLoadingProgressPayload):
            data = {
                "tool_name": self.data.tool_name,
                "status": self.data.status,
                "message": self.data.message,
            }
        elif isinstance(self.data, ReadyPayload):
            data = {
                "tools_loaded": self.data.tools_loaded,
            }
        elif isinstance(self.data, StartChatPayload):
            data = {
                "chat_id": self.data.chat_id,
                "chat_name": self.data.chat_name,
            }
        elif isinstance(self.data, SwitchChatPayload):
            data = {"chat_id": self.data.chat_id}
        elif isinstance(self.data, ChatReadyPayload):
            data = {
                "chat_id": self.data.chat_id,
                "is_new": self.data.is_new,
            }
        elif isinstance(self.data, TokenUsagePayload):
            data = {
                "input_tokens": self.data.input_tokens,
                "output_tokens": self.data.output_tokens,
                "total_tokens": self.data.total_tokens,
            }
            if self.data.cached_tokens is not None:
                data["cached_tokens"] = self.data.cached_tokens
        elif isinstance(self.data, TokenEstimatePayload):
            data = {
                "estimated_tokens": self.data.estimated_tokens,
                "source": self.data.source,
            }
        else:
            # As last resort
            data = (
                json.loads(self.data.model_dump_json())
                if isinstance(self.data, BaseModel)
                else str(self.data)
            )
        result = {"type": self.type.value, "data": data}
        # Add metadata fields if present
        if self.user_id:
            result["user_id"] = self.user_id
        if self.chat_id:
            result["chat_id"] = self.chat_id
        return result

    def to_text(self) -> str:
        return json.dumps(self.to_dict())


# Rebuild model to resolve forward references after all classes are defined
WSMessage.model_rebuild()
