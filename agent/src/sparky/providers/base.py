"""Base abstract class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import BaseTool


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider.

    Attributes:
        model_name: Name of the model to use
        api_key: API key for authentication
        temperature: Sampling temperature (0.0 to 1.0+)
        max_tokens: Maximum tokens in response
        context_window: Total context window size for the model (input + output)
        token_budget_percent: Percentage of context window to use (0.0-1.0, default 0.8)
        additional_params: Provider-specific parameters
    """

    model_name: str
    api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None
    token_budget_percent: float = 0.8
    additional_params: Optional[Dict[str, Any]] = None

    def get_effective_token_budget(self) -> Optional[int]:
        """Calculate the effective token budget based on context window and percentage.

        Returns:
            Effective token budget in tokens, or None if context_window is not set
        """
        if self.context_window is None:
            return None
        return int(self.context_window * self.token_budget_percent)


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    This class defines the interface that all LLM providers must implement
    to work with the AgentOrchestrator. Each provider handles its own
    API configuration, tool schema transformation, and response parsing.
    """

    def __init__(self, config: ProviderConfig):
        """Initialize the provider with configuration.

        Args:
            config: Provider configuration
        """
        self.config = config
        self.model = None
        self.memory = None  # LangChain memory for conversation state

    @abstractmethod
    def configure(self) -> None:
        """Configure the provider's API client.

        This method should set up API keys, endpoints, and any other
        provider-specific configuration needed before model initialization.

        Raises:
            ValueError: If required configuration is missing
        """
        pass

    @abstractmethod
    def initialize_model(
        self,
        langchain_tools: Optional[List[BaseTool]] = None,
        execute_tool_callback: Optional[Any] = None,
        summary_token_threshold: Optional[float] = None,
    ) -> Tuple[Any, Optional[Dict[str, str]]]:
        """Initialize the LLM model with optional tool support.

        Args:
            langchain_tools: Optional list of LangChain BaseTool instances
            execute_tool_callback: Optional callback for tool execution (for middleware routing)
            summary_token_threshold: Optional token threshold for summarization (0.0-1.0)

        Returns:
            Tuple of (model_instance, safe_to_original_mapping)
            - model_instance: The initialized model object (or agent)
            - safe_to_original_mapping: Dict mapping safe tool names to original names,
              or None if no tools provided

        Raises:
            Exception: If model initialization fails
        """
        pass

    @abstractmethod
    async def start_chat(
        self,
        history: Optional[List[Dict[str, Any]]] = None,
        enable_auto_function_calling: bool = False,
        memory: Optional[Any] = None,
    ) -> Any:
        """Start a chat session with optional history or memory.

        Args:
            history: Optional conversation history (deprecated - use memory instead)
            enable_auto_function_calling: Whether to enable automatic function calling
            memory: Optional ChatMessageHistory instance for conversation state

        Returns:
            Memory instance or chat session object
        """
        pass

    @abstractmethod
    async def send_message(
        self,
        message: str,
        events: Optional[Any] = None,
        executed_tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """Send a message in the current chat session.

        Args:
            message: Message to send
            events: Optional events system for dispatching events
            executed_tool_calls: Optional list to append executed tool calls to

        Returns:
            Provider-specific response object

        Raises:
            ValueError: If chat not initialized
        """
        pass

    @abstractmethod
    async def generate_content(self, prompt: str) -> str:
        """Generate content from a prompt without chat context.

        Args:
            prompt: Prompt to generate from

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    def extract_text(self, response: Any) -> str:
        """Extract text content from a provider-specific response.

        Args:
            response: Provider-specific response object

        Returns:
            Extracted text
        """
        pass

    @abstractmethod
    def get_function_calls(self, response: Any) -> List[Any]:
        """Extract function calls from a provider-specific response.

        Args:
            response: Provider-specific response object

        Returns:
            List of function call objects
        """
        pass

    @abstractmethod
    def extract_thinking_text(self, response: Any) -> str:
        """Extract thinking/reasoning text that appears before function calls.

        Args:
            response: Provider-specific response object

        Returns:
            Thinking text, or empty string if none
        """
        pass

    @abstractmethod
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
        """Handle the tool calling loop for this provider.

        Args:
            response: Initial response that may contain tool calls
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
            listening to events. Provider should not handle token estimation.
        """
        pass

    def extract_token_usage(self, response: Any) -> Optional[Dict[str, int]]:
        """Extract token usage information from a provider-specific response.

        Args:
            response: Provider-specific response object

        Returns:
            Dict with keys: input_tokens, output_tokens, total_tokens, cached_tokens (optional)
            Returns None if token usage information is not available
        """
        # Default implementation returns None - providers should override if they support token tracking
        return None

    def get_model_context_window(self) -> int:
        """Get the context window size for the configured model.

        Returns:
            Context window size in tokens. Returns a default if not set in config.
        """
        if self.config.context_window is not None:
            return self.config.context_window

        # Return default context window size
        # Providers should override this method to provide model-specific limits
        return 1000000  # Default 1M tokens for modern models
