"""Gemini (Google GenAI) provider implementation."""

import asyncio
import datetime
import json
import logging
import os
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple

import google.generativeai as genai
from dotenv import load_dotenv
from google.generativeai.types import StopCandidateException

from badmcp.transform.gemini_transformer import GeminiTransformer
from utils.helpers import to_plain_obj

from ..event_types import BotEvents
from .base import LLMProvider, ProviderConfig

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

    def configure(self) -> None:
        """Configure the Google GenAI API."""
        load_dotenv()
        api_key = self.config.api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "Google API key not found. Please set GOOGLE_API_KEY environment variable "
                "or pass it in the ProviderConfig."
            )
        genai.configure(api_key=api_key)
        self.config.api_key = api_key

    def initialize_model(
        self, toolchain: Optional[Any] = None
    ) -> Tuple[Any, Optional[Dict[str, str]]]:
        """Initialize the Gemini model with optional tool support.

        Args:
            toolchain: Optional ToolChain instance with available tools

        Returns:
            Tuple of (model_instance, safe_to_original_mapping)
        """
        try:
            if toolchain is None:
                self.model = genai.GenerativeModel(self.config.model_name)
                return self.model, None

            tools, self._safe_to_original = self.prepare_tools(toolchain)

            if not tools:
                self.model = genai.GenerativeModel(self.config.model_name)
                logger.warning(
                    "[gemini_provider] No valid tools found, falling back to non-tool mode."
                )
            else:
                logger.info(
                    "[gemini_provider] Creating model with %d tools", len(tools)
                )
                self.model = genai.GenerativeModel(
                    model_name=self.config.model_name, tools=tools
                )

            return self.model, self._safe_to_original

        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.warning(
                "Error initializing model '%s': %s: %s",
                self.config.model_name,
                type(e).__name__,
                e,
            )
            logger.warning("Detailed traceback:\n%s", error_traceback)
            if toolchain:
                logger.warning(
                    "Available tools at time of error: %s",
                    [tool.name for tool in toolchain.available_tools],
                )
            self._log_available_models()
            raise

    async def start_chat(
        self,
        history: Optional[List[Dict[str, Any]]] = None,
        enable_auto_function_calling: bool = False,
    ) -> Any:
        """Start a Gemini chat session.

        Args:
            history: Optional conversation history
            enable_auto_function_calling: Whether to enable automatic function calling

        Returns:
            Gemini chat session object
        """
        if self.model is None:
            raise ValueError("Model not initialized. Call initialize_model() first.")

        history = history or []
        self.chat = await asyncio.to_thread(
            self.model.start_chat,
            history=history,
            enable_automatic_function_calling=enable_auto_function_calling,
        )
        return self.chat

    async def send_message(self, message: str) -> Any:
        """Send a message in the Gemini chat session.

        Args:
            message: Message to send

        Returns:
            Gemini response object
        """
        if self.chat is None:
            raise ValueError("Chat not initialized. Call start_chat() first.")

        return await self.chat.send_message_async(message)

    async def generate_content(self, prompt: str) -> str:
        """Generate content from a prompt without chat context.

        Args:
            prompt: Prompt to generate from

        Returns:
            Generated text response
        """
        if self.model is None:
            raise ValueError("Model not initialized. Call initialize_model() first.")

        response = await self.model.generate_content_async(prompt)
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

        import base64
        import io

        # import google.generativeai as genai
        from PIL import Image

        # Decode base64 image
        image_bytes = base64.b64decode(base64_image)
        image = Image.open(io.BytesIO(image_bytes))

        # Send prompt with image
        response = await self.model.generate_content_async([prompt, image])
        return self.extract_text(response)

    def extract_text(self, response: Any) -> str:
        """Extract text content from a Gemini response.

        Args:
            response: Gemini response object

        Returns:
            Extracted text
        """
        texts = []
        try:
            if getattr(response, "candidates", None):
                for cand in response.candidates:
                    if (content := getattr(cand, "content", None)) and (
                        parts := getattr(content, "parts", [])
                    ):
                        for part in parts:
                            if txt := getattr(part, "text", None):
                                texts.append(txt)
            if not texts and (txt := getattr(response, "text", None)):
                return txt
        except Exception:
            # Fallback for unexpected structures
            pass
        return "\n".join(texts)

    def get_function_calls(self, response: Any) -> List[Any]:
        """Extract function calls from a Gemini response.

        Args:
            response: Gemini response object

        Returns:
            List of function call objects
        """
        function_calls = []
        try:
            if not getattr(response, "candidates", None):
                return function_calls
            cand = response.candidates[0]
            parts = getattr(getattr(cand, "content", None), "parts", None) or []
            for p in parts:
                if hasattr(p, "function_call") and p.function_call:
                    function_calls.append(p.function_call)
        except (AttributeError, IndexError):
            return function_calls
        return function_calls

    def extract_thinking_text(self, response: Any) -> str:
        """Extract thinking/reasoning text from a Gemini response.

        Args:
            response: Gemini response object

        Returns:
            Thinking text, or empty string if none
        """
        texts = []
        try:
            if not getattr(response, "candidates", None):
                return ""
            cand = response.candidates[0]
            parts = getattr(getattr(cand, "content", None), "parts", None) or []

            # Collect all text parts that appear before or with function calls
            for p in parts:
                if hasattr(p, "text") and p.text:
                    texts.append(p.text.strip())
                elif hasattr(p, "function_call") and p.function_call:
                    # Stop collecting once we hit a function call
                    break

            return " ".join(texts) if texts else ""
        except (AttributeError, IndexError):
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
        """Handle the Gemini tool calling loop.

        Args:
            response: Initial Gemini response
            execute_tool_callback: Callback to execute a tool call
            events: Events system for dispatching events
            safe_to_original: Mapping of safe tool names to original names
            task_id: Current task identifier
            executed_tool_calls: List to append executed tool calls to
            knowledge: Optional knowledge module for logging

        Returns:
            Final response after all tool calls completed

        Note:
            Token estimation is handled automatically by TokenUsageService
            listening to THOUGHT, TOOL_USE, and TOOL_RESULT events.
        """
        while True:
            # Safety check: ensure response has candidates
            if (
                not response
                or not hasattr(response, "candidates")
                or not response.candidates
            ):
                logger.warning("Response has no candidates, cannot process tool calls")
                return response

            # Check for malformed function calls
            if response.candidates[0].finish_reason == "MALFORMED_FUNCTION_CALL":
                await self._handle_malformed_call(
                    response, safe_to_original, task_id, knowledge
                )
                response = await asyncio.to_thread(
                    self.chat.send_message,
                    genai.protos.Content(
                        parts=[
                            genai.protos.Part(
                                text="Error: Malformed function call detected. Please check your function call syntax and try again."
                            )
                        ]
                    ),
                )
                continue

            # Get ALL function calls from the response
            function_calls = self.get_function_calls(response)
            if not function_calls:
                break

            # Extract and dispatch thinking text
            # TokenUsageService will automatically estimate tokens from this event
            thinking_text = self.extract_thinking_text(response)
            if thinking_text:
                await events.async_dispatch(BotEvents.THOUGHT, thinking_text)

            # Process all function calls concurrently
            function_responses = await self._process_function_calls(
                function_calls,
                safe_to_original,
                execute_tool_callback,
                events,
                executed_tool_calls,
                task_id,
                knowledge,
            )

            # Send all function responses back at once
            try:
                response = await asyncio.to_thread(
                    self.chat.send_message,
                    genai.protos.Content(parts=function_responses),
                )
            except StopCandidateException as e:
                await self._handle_stop_candidate(e, task_id, knowledge)
                response = await asyncio.to_thread(
                    self.chat.send_message,
                    genai.protos.Content(
                        parts=[
                            genai.protos.Part(
                                text=f"Error: {e}. Please provide a valid response without malformed function calls."
                            )
                        ]
                    ),
                )
                continue

        return response

    async def _process_function_calls(
        self,
        function_calls: List[Any],
        safe_to_original: Dict[str, str],
        execute_tool_callback: Any,
        events: Any,
        executed_tool_calls: List[Dict[str, Any]],
        task_id: str,
        knowledge: Optional[Any],
    ) -> List[Any]:
        """Process multiple function calls concurrently."""

        async def process_single_call(function_call):
            safe_name = function_call.name
            original_name = safe_to_original.get(safe_name, safe_name)
            plain_args = to_plain_obj(dict(function_call.args))

            # Log the tool call
            executed_tool_calls.append({"name": original_name, "arguments": plain_args})

            logger.info("Calling %s -> %s(%s): ", safe_name, original_name, plain_args)

            # Dispatch tool use event
            # TokenUsageService will automatically estimate tokens from this event
            await events.async_dispatch(BotEvents.TOOL_USE, original_name, plain_args)

            # Execute the tool call
            tool_result_obj = await execute_tool_callback(original_name, plain_args)
            tool_result = tool_result_obj.result

            if tool_result_obj.status == "error":
                logger.error(
                    "⚠ Unable to call %s: %s",
                    original_name,
                    tool_result_obj.message,
                )
                if knowledge:
                    asyncio.create_task(
                        knowledge.log_tool_error(
                            task_id,
                            original_name,
                            Exception(tool_result_obj.message),
                        )
                    )
                tool_result = f"Error: {tool_result_obj.message}"

            if isinstance(tool_result, (dict, list)):
                response_data = tool_result
                tool_result_str = json.dumps(tool_result)
            else:
                tool_result_str = str(tool_result) if tool_result is not None else ""
                response_data = {"result": tool_result_str}

            logger.info("Tool result for %s: %s", original_name, tool_result_str)
            # Dispatch tool result event
            # TokenUsageService will automatically estimate tokens from this event
            await events.async_dispatch(
                BotEvents.TOOL_RESULT, original_name, tool_result_str
            )

            return genai.protos.Part(
                function_response=genai.protos.FunctionResponse(
                    name=function_call.name,
                    response=response_data,
                )
            )

        # Create tasks for all tool calls
        tool_call_tasks = [process_single_call(fc) for fc in function_calls]

        # Run all tool calls concurrently
        function_responses = await asyncio.gather(
            *tool_call_tasks, return_exceptions=True
        )

        # Handle potential exceptions
        for i, result in enumerate(function_responses):
            if isinstance(result, Exception):
                tool_name = function_calls[i].name
                logger.error(
                    f"Exception during concurrent execution of tool '{tool_name}': {result}"
                )
                # Create a synthetic error response
                function_responses[i] = genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=tool_name,
                        response={"error": f"Tool execution failed: {result}"},
                    )
                )

        return function_responses

    async def _handle_malformed_call(
        self,
        response: Any,
        safe_to_original: Dict[str, str],
        task_id: str,
        knowledge: Optional[Any],
    ):
        """Handle malformed function call errors."""
        function_calls = self.get_function_calls(response)
        if function_calls:
            function_call = function_calls[0]
            safe_name = function_call.name
            original_name = safe_to_original.get(safe_name, safe_name)
            # plain_args = to_plain_obj(dict(function_call.args))

            error_message = (
                f"Malformed function call detected for tool '{original_name}'."
            )
            log_message = f"Task ID: {task_id}. {error_message}"
            logger.error(log_message)

            # Log to knowledge graph if available
            if knowledge:
                try:
                    error_node_id = f"error:{task_id}:malformed_call"
                    knowledge.repository.add_node(
                        node_id=error_node_id,
                        node_type="Error",
                        label="Malformed Function Call",
                        properties={
                            "task_id": task_id,
                            "error_type": "MALFORMED_FUNCTION_CALL",
                            "message": error_message,
                            "timestamp": datetime.datetime.utcnow().isoformat(),
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to log error to knowledge graph: {e}")

    async def _handle_stop_candidate(
        self, exception: StopCandidateException, task_id: str, knowledge: Optional[Any]
    ):
        """Handle stop candidate exceptions."""
        logger.error(f"Model made malformed function call: {exception}")

        if knowledge:
            try:
                error_node_id = f"error:{task_id}:stop_candidate:{datetime.datetime.utcnow().timestamp()}"
                knowledge.repository.add_node(
                    node_id=error_node_id,
                    node_type="Error",
                    label="Stop Candidate Exception",
                    properties={
                        "task_id": task_id,
                        "error_type": "STOP_CANDIDATE_EXCEPTION",
                        "message": str(exception),
                        "timestamp": datetime.datetime.utcnow().isoformat(),
                    },
                )
            except Exception as log_exc:
                logger.warning(f"Failed to log error to knowledge graph: {log_exc}")

    def prepare_tools(self, toolchain: Any) -> Tuple[List[Dict], Dict[str, str]]:
        """Prepare tools from toolchain for Gemini format.

        Args:
            toolchain: ToolChain instance with available tools

        Returns:
            Tuple of (transformed_tools, safe_to_original_mapping)
        """
        if not toolchain:
            return [], {}

        tools = []
        safe_to_original: Dict[str, str] = {}
        used_safe_names: set[str] = set()
        seen_originals: dict[str, str] = {}
        transformer = GeminiTransformer()

        for idx, tool in toolchain.available_tools:
            original = tool.name
            if original in seen_originals:
                logger.warning(
                    "[gemini_provider] Duplicate tool name '%s' detected! First seen from: %s, skipping duplicate.",
                    original,
                    seen_originals[original],
                )
                continue
            seen_originals[original] = f"index {idx}"

            safe_name = self._make_safe_tool_name(
                original, used_safe_names, safe_to_original
            )
            used_safe_names.add(safe_name)
            safe_to_original[safe_name] = original

            try:
                transformed_params = transformer.transform(tool.inputSchema)
                tool_def = {
                    "name": safe_name,
                    "description": tool.description,
                    "parameters": transformed_params,
                }
                tools.append(tool_def)
                logger.info(
                    "[gemini_provider] Added tool: %s (original: %s)",
                    safe_name,
                    original,
                )
                logger.debug(
                    "[gemini_provider] Tool schema for %s: %s",
                    safe_name,
                    transformed_params,
                )
            except Exception as tool_error:
                logger.error(
                    "[gemini_provider] Failed to transform tool '%s': %s: %s",
                    original,
                    type(tool_error).__name__,
                    tool_error,
                )
                logger.error("[gemini_provider] Tool schema: %s", tool.inputSchema)

        return tools, safe_to_original

    def _create_safe_tool_name(self, name: str) -> str:
        """Creates a Gemini-safe tool name."""
        safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
        if not re.match(r"^[A-Za-z_]", safe):
            safe = f"tool_{safe}"
        return safe[:64]

    def _make_safe_tool_name(
        self, name: str, used_names: set, safe_to_original: dict
    ) -> str:
        """Create a Gemini-safe and unique tool name."""
        safe = self._create_safe_tool_name(name)
        base = safe
        i = 1
        while safe in used_names and safe_to_original.get(safe) != name:
            suffix = f"_{i}"
            safe = (base[: 64 - len(suffix)]) + suffix
            i += 1
        return safe

    def _log_available_models(self):
        """Logs the available Gemini models."""
        logger.info("Trying to list available models...")
        try:
            models = genai.list_models()
            logger.info("Available models:")
            for m in models:
                if "generateContent" in m.supported_generation_methods:
                    logger.info("  - %s", m.name)
        except Exception as e:
            logger.error("Could not list available models: %s", e)

    def extract_token_usage(self, response: Any) -> Optional[Dict[str, int]]:
        """Extract token usage information from a Gemini response.

        Args:
            response: Gemini response object

        Returns:
            Dict with token usage information, or None if not available
        """
        try:
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                input_tokens = getattr(usage, "prompt_token_count", 0)
                output_tokens = getattr(usage, "candidates_token_count", 0)
                total_tokens = getattr(
                    usage, "total_token_count", input_tokens + output_tokens
                )
                cached_tokens = getattr(usage, "cached_content_token_count", None)

                result = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                }

                if cached_tokens is not None and cached_tokens > 0:
                    result["cached_tokens"] = cached_tokens

                return result
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
