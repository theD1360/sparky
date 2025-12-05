"""Service layer for Sparky.

This module provides service classes that handle domain logic and interface
with the knowledge graph repository. Services act as an intermediary layer
between the orchestrator (controller) and the repository (data access).
"""

from typing import Any, Optional

from database.repository import KnowledgeRepository

from .auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    get_user_from_token,
    is_token_revoked,
    revoke_token,
    verify_password,
)
from .chat_service import ChatService
from .file_service import FileService
from .identity_service import IdentityService
from .knowledge_service import KnowledgeService
from .message_service import MessageService
from .task_service import TaskService
from .token_usage import CharacterBasedEstimator, TokenEstimator, TokenUsageService
from .user_management_service import UserManagementService
from .user_service import UserService

__all__ = [
    "TokenEstimator",
    "CharacterBasedEstimator",
    "TokenUsageService",
    "MessageService",
    "UserService",
    "UserManagementService",
    "IdentityService",
    "FileService",
    "KnowledgeService",
    "TaskService",
    "ChatService",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "get_password_hash",
    "get_user_from_token",
    "is_token_revoked",
    "revoke_token",
    "verify_password",
    "create_services",
]


def create_services(
    repository: KnowledgeRepository,
    identity_search_terms: Optional[list] = None,
    events: Optional[Any] = None,
    provider: Optional[Any] = None,
) -> dict:
    """Create all services from a repository (dependency injection helper).

    Args:
        repository: Knowledge graph repository instance
        identity_search_terms: Optional search terms for identity service
        events: Optional events instance for token service
        provider: Optional provider instance for token service

    Returns:
        Dictionary with all service instances:
        - file_service: FileService
        - message_service: MessageService
        - user_service: UserService
        - chat_service: ChatService
        - identity_service: IdentityService
        - token_service: TokenUsageService (if events and provider provided)
    """
    # Initialize file service first since message service depends on it
    file_service = FileService(repository)

    message_service = MessageService(repository, file_service=file_service)

    user_service = UserService(repository)

    chat_service = ChatService(repository)

    identity_service = IdentityService(
        repository, identity_search_terms=identity_search_terms
    )

    token_service = None
    if events and provider:
        token_service = TokenUsageService(
            token_estimator=message_service.token_estimator,
            events=events,
            provider=provider,
        )

    return {
        "file_service": file_service,
        "message_service": message_service,
        "user_service": user_service,
        "chat_service": chat_service,
        "identity_service": identity_service,
        "token_service": token_service,
    }

