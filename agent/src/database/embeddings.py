"""Abstract embedding interface and Gemini provider implementation.

This module provides an abstract interface for text embeddings and implements
a Gemini-based provider using the gemini-embedding-001 model.
"""

import logging
import math
import os
from abc import ABC, abstractmethod
from typing import List, Optional

import google.generativeai as genai
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Default embedding dimension for Gemini
DEFAULT_EMBEDDING_DIM = 768


class EmbeddingProvider(ABC):
    """Abstract interface for text embedding providers."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding vector
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the dimension of embeddings produced by this provider.

        Returns:
            Dimension of the embedding vectors
        """
        pass


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using Google's Gemini embedding model."""

    def __init__(
        self,
        model_name: str = "gemini-embedding-001",
        dimension: int = DEFAULT_EMBEDDING_DIM,
        api_key: Optional[str] = None,
    ):
        """Initialize Gemini embedding provider.

        Args:
            model_name: Name of the Gemini embedding model to use
            dimension: Output dimension (768, 1536, or 3072)
            api_key: Google API key (if None, uses GOOGLE_API_KEY env var)
        """
        self.model_name = model_name
        self.dimension = dimension
        self.api_key = api_key

        # Load environment and configure API
        load_dotenv()
        if not self.api_key:
            self.api_key = os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Google API key not found. Please set GOOGLE_API_KEY environment variable "
                "or pass it to GeminiEmbeddingProvider constructor."
            )

        # Configure genai if not already configured
        try:
            genai.configure(api_key=self.api_key)
        except Exception:
            pass  # Already configured

        logger.info(
            f"Initialized GeminiEmbeddingProvider with model={model_name}, dim={dimension}"
        )

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text using Gemini.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.dimension

        try:
            # Use google.generativeai API
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="SEMANTIC_SIMILARITY",
                output_dimensionality=self.dimension,
            )

            if not result.get("embedding"):
                logger.warning("No embedding returned from Gemini API")
                return [0.0] * self.dimension

            embedding = result["embedding"]

            # Normalize for dimensions < 3072 (per Gemini docs)
            if self.dimension < 3072:
                embedding = self._normalize_embedding(embedding)

            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}", exc_info=True)
            # Return zero vector on error
            return [0.0] * self.dimension

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently using batch functionality.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter out empty texts and track indices
        non_empty_texts = []
        indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_texts.append(text)
                indices.append(i)
            else:
                indices.append(i)

        if not non_empty_texts:
            # All texts are empty, return zero vectors
            return [[0.0] * self.dimension] * len(texts)

        try:
            # Use google.generativeai API to embed the batch
            result = genai.embed_content(
                model=self.model_name,
                content=non_empty_texts,
                task_type="SEMANTIC_SIMILARITY",
                output_dimensionality=self.dimension,
        )

            embeddings_list = result.get("embedding")

            if not embeddings_list:
                logger.warning("No embeddings returned from Gemini API for batch")
                return [[0.0] * self.dimension] * len(texts)

            # Normalize embeddings if necessary
            if self.dimension < 3072:
                embeddings_list = [self._normalize_embedding(emb) for emb in embeddings_list]

            # Build result list with embeddings in original order
            results = []
            result_idx = 0
            for i in range(len(texts)):
                if i in indices and texts[i] and texts[i].strip():
                    # This text had an embedding generated
                    embedding = embeddings_list[result_idx]
                    result_idx += 1
                else:
                    # Empty text, use zero vector
                    embedding = [0.0] * self.dimension
                results.append(embedding)

            return results

        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}", exc_info=True)
            # Return zero vectors on error
            return [[0.0] * self.dimension] * len(texts)

    def get_dimension(self) -> int:
        """Get the dimension of embeddings produced by this provider.

        Returns:
            Dimension of the embedding vectors
        """
        return self.dimension

    @staticmethod
    def _normalize_embedding(embedding: List[float]) -> List[float]:
        """Normalize embedding vector to unit length using pure Python.

        Args:
            embedding: The embedding vector to normalize

        Returns:
            Normalized embedding vector
        """
        # Calculate L2 norm
        norm = math.sqrt(sum(v * v for v in embedding))

        # Return original if norm is zero (avoid division by zero)
        if norm == 0:
            return embedding

        # Normalize by dividing each component by the norm
        return [v / norm for v in embedding]


class EmbeddingManager:
    """Singleton manager for embedding provider instances."""

    _instance: Optional["EmbeddingManager"] = None
    _provider: Optional[EmbeddingProvider] = None

    def __init__(self):
        """Initialize embedding manager (private, use get_instance())."""
        if EmbeddingManager._instance is not None:
            raise RuntimeError("EmbeddingManager is a singleton. Use get_instance()")

    @classmethod
    def get_instance(cls) -> "EmbeddingManager":
        """Get the singleton instance of EmbeddingManager.

        Returns:
            The singleton EmbeddingManager instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_provider(self) -> EmbeddingProvider:
        """Get the current embedding provider.

        Returns:
            The configured EmbeddingProvider instance

        Raises:
            RuntimeError: If no provider has been set
        """
        if self._provider is None:
            # Default to Gemini provider
            self._provider = GeminiEmbeddingProvider()
        return self._provider

    def set_provider(self, provider: EmbeddingProvider) -> None:
        """Set the embedding provider to use.

        Args:
            provider: The EmbeddingProvider instance to use
        """
        self._provider = provider
        logger.info(f"EmbeddingProvider set to {type(provider).__name__}")

    def embed_text(self, text: str) -> List[float]:
        """Convenience method to embed a single text.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding vector
        """
        return self.get_provider().embed_text(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Convenience method to embed multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        return self.get_provider().embed_batch(texts)

    def get_dimension(self) -> int:
        """Get the dimension of embeddings from the current provider.

        Returns:
            Dimension of the embedding vectors
        """
        return self.get_provider().get_dimension()
