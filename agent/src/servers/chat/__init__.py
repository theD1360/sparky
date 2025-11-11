from .chat_server import ConnectionManager, app

# Alias for backward compatibility
ChatServer = app

__all__ = ["ChatServer", "app", "ConnectionManager"]
