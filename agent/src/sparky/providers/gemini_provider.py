"""Gemini (Google GenAI) provider implementation using LangChain agents."""

import asyncio
import base64
import datetime
import json
import logging
import os
import traceback
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from events import BotEvents

from langchain.agents import create_agent

try:
    from langchain.agents.middleware import ToolRetryMiddleware
    from langchain.agents.middleware.summarization import SummarizationMiddleware
except ImportError:
    try:
        from langchain.agents.middleware import SummarizationMiddleware, ToolRetryMiddleware
    except ImportError:
        SummarizationMiddleware = None
        ToolRetryMiddleware = None

try:
    from langchain_classic.memory import ConversationBufferMemory
except ImportError:
    from langchain.memory import ConversationBufferMemory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI

from .base import LLMProvider, ProviderConfig
from .langchain_callbacks import LangChainEventCallbackHandler
from .middleware_tool_wrapper import MiddlewareToolWrapper
from ..gemini_schema import (
    gemini_automatic_function_calling_kwarg,
    tools_with_gemini_safe_arg_schemas,
)

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider implementation."""

    def __init__(self, config: ProviderConfig):
        """Initialize Gemini provider.

        Args:
            config: Provider configuration with model_name and api_key
        """
        super().__init__(config)
        self._safe_to_original: Dict[str, str] = {}
        self._original_tools: Dict[str, BaseTool] = {}
        self.agent: Optional[Any] = None  # LangChain agent created with create_agent
        self._event_handler: Optional[Any] = None
        self._summary_token_threshold: Optional[float] = (
            None  # Will be set from orchestrator
        )

    def configure(self) -> None:
        """Configure the Google GenAI API."""
        load_dotenv()
        api_key = self.config.api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "Google API key not found. Please set GOOGLE_API_KEY environment variable "
                "or pass it in the ProviderConfig."
            )
        self.config.api_key = api_key

    def initialize_model(
        self,
        langchain_tools: Optional[List[BaseTool]] = None,
        execute_tool_callback: Optional[Any] = None,
        summary_token_threshold: Optional[float] = None,
    ) -> Tuple[Any, Optional[Dict[str, str]]]:
        """Initialize the Gemini model with optional tool support using LangChain agents.

        Args:
            langchain_tools: Optional list of LangChain BaseTool instances
            execute_tool_callback: Optional callback for tool execution (for middleware routing)
            summary_token_threshold: Optional token threshold for summarization (0.0-1.0)

        Returns:
            Tuple of (agent, safe_to_original_mapping)
        """
        try:
            # Create LangChain ChatGoogleGenerativeAI model
            model_kwargs = {}
            if self.config.temperature is not None:
                model_kwargs["temperature"] = self.config.temperature
            if self.config.max_tokens is not None:
                model_kwargs["max_output_tokens"] = self.config.max_tokens

            disable_afc = os.getenv("SPARKY_GEMINI_DISABLE_AFC", "false").lower() in (
                "1",
                "true",
                "yes",
            )
            try:
                max_afc_calls = int(os.getenv("SPARKY_GEMINI_AFC_MAX_REMOTE_CALLS", "10"))
            except ValueError:
                max_afc_calls = 10
            afc_kwarg = gemini_automatic_function_calling_kwarg(
                disable_afc=disable_afc,
                max_remote_calls=max_afc_calls,
            )
            if afc_kwarg is not None:
                model_kwargs["automatic_function_calling"] = afc_kwarg

            llm = ChatGoogleGenerativeAI(
                model=self.config.model_name,
                google_api_key=self.config.api_key,
                **model_kwargs,
            )

            # Store summary threshold for middleware configuration
            self._summary_token_threshold = summary_token_threshold

            # Build safe_to_original mapping from tool names
            self._safe_to_original = {}
            if langchain_tools:
                langchain_tools = (
                    tools_with_gemini_safe_arg_schemas(langchain_tools) or langchain_tools
                )
                # Store original tools for middleware access
                for tool in langchain_tools:
                    self._original_tools[tool.name] = tool
                    # LangChain tools already have safe names, so mapping is 1:1
                    self._safe_to_original[tool.name] = tool.name

                # Wrap tools to route through middleware if callback provided
                if execute_tool_callback:
                    wrapped_tools = [
                        MiddlewareToolWrapper(tool, execute_tool_callback)
                        for tool in langchain_tools
                    ]
                else:
                    wrapped_tools = langchain_tools

                # Store tools and model for later use
                self._wrapped_tools = wrapped_tools
                self._llm = llm
                self._system_messages: List[str] = []

                # Build middleware list
                middleware = []

                if ToolRetryMiddleware is not None:
                    middleware.append(
                        ToolRetryMiddleware(
                            max_retries=2,
                            initial_delay=6.0,
                            backoff_factor=2.0,
                            max_delay=45.0,
                            jitter=True,
                            on_failure="continue",
                        )
                    )

                # Add SummarizationMiddleware if threshold is provided and available
                if (
                    summary_token_threshold is not None
                    and SummarizationMiddleware is not None
                ):
                    # Calculate trigger threshold in tokens
                    # Use a cheaper model for summarization (flash is faster and cheaper)
                    summary_model_name = self.config.model_name.replace(
                        "pro", "flash"
                    ).replace("2.0", "1.5")
                    if "flash" not in summary_model_name.lower():
                        summary_model_name = "gemini-1.5-flash"

                    summary_llm = ChatGoogleGenerativeAI(
                        model=summary_model_name,
                        google_api_key=self.config.api_key,
                    )

                    summarization_middleware = SummarizationMiddleware(
                        model=summary_llm,
                        trigger=("fraction", summary_token_threshold),
                        keep=("fraction", 0.10),
                    )
                    middleware.append(summarization_middleware)
                    logger.info(
                        "[gemini_provider] Added SummarizationMiddleware with trigger at %.1f%% of context",
                        summary_token_threshold * 100,
                    )
                elif summary_token_threshold is not None:
                    logger.warning(
                        "[gemini_provider] SummarizationMiddleware not available. "
                        "Summarization will be disabled. Please upgrade to LangChain 1.0+ for summarization support."
                    )

                # Create agent with create_agent API
                self.agent = create_agent(
                    model=llm,
                    tools=wrapped_tools,
                    middleware=middleware if middleware else None,
                )

                logger.info(
                    "[gemini_provider] Created agent with %d LangChain tools%s",
                    len(wrapped_tools),
                    " and summarization middleware" if middleware else "",
                )
            else:
                # No tools - just use the LLM directly
                self.model = llm
                logger.info("[gemini_provider] Created model without tools")

            # Store model reference for compatibility
            self.model = llm

            return (
                self.agent if langchain_tools else self.model,
                self._safe_to_original if langchain_tools else None,
            )

        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.warning(
                "Error initializing model '%s': %s: %s",
                self.config.model_name,
                type(e).__name__,
                e,
            )
            logger.warning("Detailed traceback:\n%s", error_traceback)
            if langchain_tools:
                logger.warning(
                    "Available tools at time of error: %s",
                    [tool.name for tool in langchain_tools],
                )
            raise

    async def start_chat(
        self,
        history: Optional[List[Dict[str, Any]]] = None,
        enable_auto_function_calling: bool = False,
        memory: Optional[BaseChatMessageHistory] = None,
    ) -> Any:
        """Start a chat session with LangChain.

        Args:
            history: Optional conversation history (deprecated - use memory instead)
            enable_auto_function_calling: Whether to enable automatic function calling
                (Note: LangChain handles this automatically when tools are bound)
            memory: Optional ChatMessageHistory instance for conversation state

        Returns:
            Memory instance or None
        """
        if self.model is None:
            raise ValueError("Model not initialized. Call initialize_model() first.")

        # Use provided memory or create a buffer memory
        if memory:
            # Wrap custom ChatMessageHistory in ConversationBufferMemory
            self.memory = ConversationBufferMemory(
                chat_memory=memory,
                memory_key="chat_history",
                return_messages=True,
            )
            # Load existing messages from memory
            if hasattr(memory, "aget_messages"):
                existing_messages = await memory.aget_messages()
                # Add existing messages to memory buffer
                if existing_messages:
                    self.memory.chat_memory.add_messages(existing_messages)
        else:
            # Create a simple buffer memory if no custom memory provided
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
            )
            # If history provided (legacy), convert and add to memory
            if history:
                for msg in history:
                    role = msg.get("role", "user")
                    parts = msg.get("parts", [])
                    content = " ".join(str(p) for p in parts) if parts else ""

                    if role == "user":
                        self.memory.chat_memory.add_user_message(content)
                    elif role == "model":
                        self.memory.chat_memory.add_ai_message(content)
                    elif role == "system":
                        self.memory.chat_memory.add_message(
                            SystemMessage(content=content)
                        )

        # Memory is handled via state in create_agent API
        # The agent will use messages from memory when invoking
        return self.memory

    async def send_message(
        self,
        message: str,
        events: Optional[Any] = None,
        executed_tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """Send a message using LangChain agent or model.

        Args:
            message: Message to send
            events: Optional events system for dispatching events
            executed_tool_calls: Optional list to append executed tool calls to

        Returns:
            Agent response (AIMessage-like object with content attribute)
        """
        if self.agent is None and self.model is None:
            raise ValueError("Model not initialized. Call initialize_model() first.")

        # If we have an agent, use it (with tools)
        if self.agent:
            # Create event handler for tool calls if events provided
            callbacks = []
            if events and executed_tool_calls is not None:
                callbacks.append(
                    LangChainEventCallbackHandler(events, executed_tool_calls)
                )

            # Build state for create_agent API
            # The agent expects a state dict with "messages" key
            state = {"messages": [HumanMessage(content=message)]}

            # Add existing messages from memory if available
            if self.memory:
                memory_vars = self.memory.load_memory_variables({})
                chat_history = memory_vars.get("chat_history", [])
                if chat_history:
                    # Prepend existing messages
                    state["messages"] = chat_history + state["messages"]

            # Invoke agent with state
            result = await self.agent.ainvoke(
                state,
                config={"callbacks": callbacks} if callbacks else {},
            )

            # Extract response from result
            # create_agent returns state with messages; prefer the last AI text,
            # not merely the last message (which can be a ToolMessage).
            response_messages = result.get("messages", [])
            response_text = ""
            if response_messages:
                for candidate in reversed(response_messages):
                    # Prefer AIMessage-like objects with extractable text
                    name = type(candidate).__name__
                    if name in ("HumanMessage", "ToolMessage", "SystemMessage"):
                        continue
                    text = self.extract_text(candidate)
                    if text and text.strip():
                        response_text = text
                        break
                if not response_text:
                    # Fall back to last message even if empty (preserves prior behavior)
                    response_text = self.extract_text(response_messages[-1])
                    if not (response_text or "").strip():
                        logger.warning(
                            "[gemini_provider] Agent returned no text content "
                            "(last message type=%s, total messages=%d)",
                            type(response_messages[-1]).__name__,
                            len(response_messages),
                        )

                # Update memory with all messages from state
                # This ensures summaries and all messages are persisted
                if self.memory and hasattr(self.memory, "chat_memory"):
                    # Get current messages in memory
                    current_messages = (
                        self.memory.chat_memory.messages
                        if hasattr(self.memory.chat_memory, "messages")
                        else []
                    )
                    current_count = len(current_messages)

                    # Add any new messages that aren't in memory yet
                    # Messages are added in order, so we can add from current_count onwards
                    new_messages = response_messages[current_count:]
                    if new_messages:
                        # Use aadd_messages if available (for KnowledgeGraphChatMessageHistory)
                        if hasattr(self.memory.chat_memory, "aadd_messages"):
                            await self.memory.chat_memory.aadd_messages(new_messages)
                        else:
                            self.memory.chat_memory.add_messages(new_messages)

                # Return a mock AIMessage-like object for compatibility
                class AgentResponse:
                    def __init__(self, output: str):
                        self.content = output
                        self.tool_calls = []
                        # Agent already handled all tool calls, so no tool_calls here

                return AgentResponse(response_text)
            else:
                # Fallback if no messages in result
                class AgentResponse:
                    def __init__(self, output: str):
                        self.content = output
                        self.tool_calls = []

                logger.warning("[gemini_provider] Agent result had no messages")
                return AgentResponse("")
        else:
            # No tools - use model directly with memory
            if self.memory:
                # Load history from memory
                memory_vars = self.memory.load_memory_variables({})
                chat_history = memory_vars.get("chat_history", [])
                # Add new user message
                chat_history.append(HumanMessage(content=message))
                # Invoke model
                response = await self.model.ainvoke(chat_history)
                # Save to memory
                self.memory.save_context(
                    {"input": message},
                    {"output": self.extract_text(response)},
                )
                return response
            else:
                # No memory - simple invocation
                response = await self.model.ainvoke([HumanMessage(content=message)])
                return response

    async def generate_content(self, prompt: str) -> str:
        """Generate content from a prompt without chat context.

        Args:
            prompt: Prompt to generate from

        Returns:
            Generated text response
        """
        if self.model is None:
            raise ValueError("Model not initialized. Call initialize_model() first.")

        response = await self.model.ainvoke([HumanMessage(content=prompt)])
        return self.extract_text(response)

    async def generate_content_with_image(
        self, prompt: str, base64_image: str, mime_type: str
    ) -> str:
        """Generate content from a prompt with an image.

        Args:
            prompt: Text prompt
            base64_image: Base64 encoded image
            mime_type: MIME type of the image (e.g., "image/jpeg")

        Returns:
            Generated text response
        """
        if self.model is None:
            raise ValueError("Model not initialized. Call initialize_model() first.")

        # Decode base64 image
        image_bytes = base64.b64decode(base64_image)

        # Create message with image
        # LangChain supports images via message parts

        # For now, use a simple approach - LangChain may need different handling
        # This is a placeholder - may need to adjust based on LangChain's image support
        response = await self.model.ainvoke([HumanMessage(content=prompt)])
        return self.extract_text(response)

    def extract_text(self, response: Any) -> str:
        """Extract text content from a LangChain response.

        Args:
            response: LangChain AIMessage response

        Returns:
            Extracted text
        """
        if hasattr(response, "content"):
            return self._normalize_content(response.content)
        return str(response)

    @staticmethod
    def _normalize_content(content: Any) -> str:
        """Flatten LangChain / Gemini content parts into plain text."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict):
                    text = part.get("text")
                    if text:
                        parts.append(str(text))
                    elif part.get("type") not in ("text", "thinking", "reasoning"):
                        # Skip binary / metadata-only parts
                        continue
                else:
                    text = getattr(part, "text", None)
                    if text:
                        parts.append(str(text))
            return "\n".join(p for p in parts if p).strip()
        return str(content)

    def get_function_calls(self, response: Any) -> List[Any]:
        """Extract function calls from a LangChain response.

        Args:
            response: LangChain AIMessage response

        Returns:
            List of tool call dictionaries with format: {"name": str, "args": dict, "id": str}
        """
        if hasattr(response, "tool_calls") and response.tool_calls:
            # Convert LangChain ToolCall objects to dicts if needed
            tool_calls = []
            for tc in response.tool_calls:
                if isinstance(tc, dict):
                    tool_calls.append(tc)
                else:
                    # Convert ToolCall object to dict
                    # LangChain ToolCall has: name, args, id attributes
                    tool_calls.append(
                        {
                            "name": getattr(tc, "name", ""),
                            "args": dict(getattr(tc, "args", {})),
                            "id": getattr(tc, "id", ""),
                        }
                    )
            return tool_calls
        return []

    def extract_thinking_text(self, response: Any) -> str:
        """Extract thinking/reasoning text from a LangChain response.

        Args:
            response: LangChain AIMessage response

        Returns:
            Thinking text, or empty string if none
        """
        if not hasattr(response, "content"):
            return ""
        content = response.content
        # Prefer explicit thinking/reasoning parts when content is structured.
        if isinstance(content, list):
            thinking_parts: List[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") in (
                    "thinking",
                    "reasoning",
                ):
                    text = part.get("thinking") or part.get("text") or ""
                    if text:
                        thinking_parts.append(str(text))
            if thinking_parts:
                return "\n".join(thinking_parts).strip()
            # Only treat plain content as thinking when there are tool calls.
            if hasattr(response, "tool_calls") and response.tool_calls:
                return self._normalize_content(content)
            return ""
        if hasattr(response, "tool_calls") and response.tool_calls:
            return self._normalize_content(content)
        return ""

    async def handle_tool_calls(
        self,
        response: Any,
        execute_tool_callback: Any,
        events: Any,
        safe_to_original: Dict[str, str],
        task_id: str,
        executed_tool_calls: List[Dict[str, Any]],
        knowledge: Optional[Any] = None,
    ) -> Any:
        """Handle tool calls - not needed when using AgentExecutor.

        AgentExecutor handles tool calling automatically, so this method
        is a no-op when using agents. Kept for interface compatibility.

        Args:
            response: Response from agent executor (already includes tool results)
            execute_tool_callback: Not used with AgentExecutor
            events: Events are handled via callbacks
            safe_to_original: Not used
            task_id: Not used
            executed_tool_calls: Already populated via callbacks
            knowledge: Optional knowledge module

        Returns:
            Response as-is (AgentExecutor already handled tool calls)
        """
        # AgentExecutor handles everything automatically, so just return the response
        return response

    def extract_token_usage(self, response: Any) -> Optional[Dict[str, int]]:
        """Extract token usage information from a LangChain response.

        Args:
            response: LangChain AIMessage response

        Returns:
            Dict with token usage information, or None if not available
        """
        try:
            # LangChain responses may have response_metadata with usage info
            if hasattr(response, "response_metadata"):
                metadata = response.response_metadata
                if metadata and "token_usage" in metadata:
                    usage = metadata["token_usage"]
                    return {
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
        except Exception as e:
            logger.debug("Failed to extract token usage: %s", e)

        return None

    def get_model_context_window(self) -> int:
        """Get the context window size for the configured Gemini model.

        Returns:
            Context window size in tokens based on the model name.
        """
        # If explicitly set in config, use that
        if self.config.context_window is not None:
            return self.config.context_window

        # Model-specific context windows
        model_windows = {
            "gemini-2.0-flash-exp": 1048576,  # 1M tokens
            "gemini-2.0-flash": 1048576,  # 1M tokens
            "gemini-1.5-flash": 1048576,  # 1M tokens
            "gemini-1.5-flash-8b": 1048576,  # 1M tokens
            "gemini-1.5-pro": 2097152,  # 2M tokens
            "gemini-pro": 32768,  # 32K tokens
            "gemini-pro-vision": 16384,  # 16K tokens
        }

        # Check for exact match or partial match
        model_name = self.config.model_name.lower()
        for name, window in model_windows.items():
            if name in model_name:
                return window

        # Default to 1M for unknown Gemini models (most modern ones support this)
        logger.warning(
            "Unknown Gemini model '%s', defaulting to 1M token context window",
            self.config.model_name,
        )
        return 1048576
