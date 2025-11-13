"""Tool chain caching with per-server invalidation.

This module provides a caching layer for MCP tool servers with:
- Lazy loading on first connection
- Per-server cache TTL with staggered invalidation
- Thread-safe access
"""

import asyncio
import hashlib
import traceback
from datetime import datetime, timedelta
from logging import getLogger
from typing import Dict, List, Optional, Tuple

from badmcp.config import MCPConfig
from badmcp.tool_chain import ToolChain
from badmcp.tool_client import ToolClient

logger = getLogger(__name__)


class ToolServerCache:
    """Cache entry for a single tool server."""

    def __init__(
        self,
        client: ToolClient,
        loaded_at: datetime,
        ttl_minutes: int,
    ):
        """Initialize cache entry.

        Args:
            client: Loaded ToolClient instance
            loaded_at: When the client was loaded
            ttl_minutes: Time-to-live in minutes
        """
        self.client = client
        self.loaded_at = loaded_at
        self.ttl_minutes = ttl_minutes

    def is_expired(self) -> bool:
        """Check if this cache entry has expired.

        Returns:
            True if cache entry should be invalidated
        """
        age = datetime.utcnow() - self.loaded_at
        return age > timedelta(minutes=self.ttl_minutes)

    @property
    def age_minutes(self) -> float:
        """Get age of cache entry in minutes."""
        age = datetime.utcnow() - self.loaded_at
        return age.total_seconds() / 60


class ToolChainCache:
    """Manages caching of MCP tool servers with staggered invalidation."""

    # Base TTL for tool servers (in minutes)
    BASE_TTL_MINUTES = 60

    def __init__(self):
        """Initialize the tool chain cache."""
        # server_name -> ToolServerCache
        self._server_cache: Dict[str, ToolServerCache] = {}
        # Lock for thread-safe access
        self._lock = asyncio.Lock()
        # Track if initial load has happened
        self._initialized = False
        # Cached toolchain instance
        self._toolchain: Optional[ToolChain] = None
        # Loading status (for preventing concurrent loads)
        self._loading = False
        # Track load attempts per server for staggering
        self._load_count: Dict[str, int] = {}

    def _get_server_ttl(self, server_name: str) -> int:
        """Get TTL for a specific server with staggering.

        Uses a hash-based approach to distribute TTLs across different times
        to prevent all servers from invalidating simultaneously.

        Args:
            server_name: Name of the server

        Returns:
            TTL in minutes for this server
        """
        # Use hash of server name to deterministically vary TTL
        hash_val = int(hashlib.md5(server_name.encode()).hexdigest(), 16)
        # Vary TTL by ±20% based on hash (48-72 minutes with BASE_TTL=60)
        variance = (hash_val % 40) - 20  # -20 to +20
        ttl = self.BASE_TTL_MINUTES + variance

        # Add additional offset based on load count to further stagger reloads
        load_count = self._load_count.get(server_name, 0)
        offset = (load_count * 5) % 30  # 0-30 minutes offset
        ttl += offset

        logger.debug(
            f"Server '{server_name}' TTL: {ttl} minutes (base={self.BASE_TTL_MINUTES}, variance={variance}, offset={offset})"
        )
        return ttl

    async def get_or_load_toolchain(
        self, progress_callback=None
    ) -> Tuple[Optional[ToolChain], Optional[str]]:
        """Get cached toolchain or load it if not available.

        This method handles:
        - Initial lazy loading on first call
        - Returning cached toolchain if valid
        - Selective reloading of expired servers
        - Progress updates via callback

        Args:
            progress_callback: Optional async callback for progress updates
                               Signature: callback(server_name: str, status: str, message: str)

        Returns:
            Tuple of (toolchain, error_message)
            - toolchain: ToolChain instance or None on failure
            - error_message: Error message if loading failed, None on success
        """
        async with self._lock:
            # Check if we're already loading (prevent concurrent loads)
            if self._loading:
                logger.info("Tool loading already in progress, waiting...")
                # Wait and return current toolchain (may be None)
                return self._toolchain, None

            try:
                self._loading = True

                # Determine which servers need loading/reloading
                mcp_config = MCPConfig()
                all_servers = mcp_config.get_all_servers()
                servers_to_load: List[Tuple[str, any]] = []

                # Check each server's cache status
                for server_name, server_config in all_servers.items():
                    cached = self._server_cache.get(server_name)

                    if cached is None:
                        # Never loaded
                        logger.info(f"Server '{server_name}' not cached, will load")
                        servers_to_load.append((server_name, server_config))
                    elif cached.is_expired():
                        # Expired, needs reload
                        age = cached.age_minutes
                        logger.info(
                            f"Server '{server_name}' cache expired (age: {age:.1f} min, ttl: {cached.ttl_minutes} min), will reload"
                        )
                        servers_to_load.append((server_name, server_config))
                        # Clean up old client
                        try:
                            await cached.client.stop()
                        except Exception as e:
                            logger.warning(
                                f"Error stopping expired client '{server_name}': {e}"
                            )
                        del self._server_cache[server_name]
                    else:
                        # Still valid
                        age = cached.age_minutes
                        logger.debug(
                            f"Server '{server_name}' cache valid (age: {age:.1f} min, ttl: {cached.ttl_minutes} min)"
                        )

                # If nothing to load and we have a toolchain, return it
                if not servers_to_load and self._toolchain:
                    logger.info(
                        f"All {len(all_servers)} servers cached and valid, using cached toolchain"
                    )
                    return self._toolchain, None

                # Load/reload servers
                logger.info(
                    f"Loading {len(servers_to_load)} server(s) out of {len(all_servers)} total"
                )

                loaded_clients = []
                for server_name, server_config in servers_to_load:
                    try:
                        if progress_callback:
                            await progress_callback(
                                server_name, "loading", f"Loading {server_name}..."
                            )

                        # Increment load count for this server
                        self._load_count[server_name] = (
                            self._load_count.get(server_name, 0) + 1
                        )

                        # Create and start client
                        client = ToolClient(server_config)
                        await client.start()

                        # Get TTL for this server (staggered)
                        ttl = self._get_server_ttl(server_name)

                        # Cache the loaded client
                        self._server_cache[server_name] = ToolServerCache(
                            client=client,
                            loaded_at=datetime.utcnow(),
                            ttl_minutes=ttl,
                        )

                        loaded_clients.append(client)

                        if progress_callback:
                            await progress_callback(
                                server_name,
                                "loaded",
                                f"{server_name} loaded successfully (TTL: {ttl} min)",
                            )

                        logger.info(
                            f"Successfully loaded server '{server_name}' (TTL: {ttl} min)"
                        )

                    except Exception as e:
                        error_msg = f"Failed to load server '{server_name}': {e}"
                        logger.error(error_msg)
                        logger.error(f"Traceback: {traceback.format_exc()}")

                        if progress_callback:
                            await progress_callback(server_name, "error", error_msg)

                # Rebuild toolchain with all cached clients
                all_cached_clients = [cache.client for cache in self._server_cache.values()]

                if not all_cached_clients:
                    error_msg = "No MCP servers loaded successfully"
                    logger.error(error_msg)
                    self._toolchain = None
                    self._initialized = False
                    return None, error_msg

                # Create new toolchain
                logger.info(
                    f"Building toolchain with {len(all_cached_clients)} server(s)"
                )
                toolchain = ToolChain(all_cached_clients)

                # Initialize toolchain (loads tools, prompts, resources)
                logger.info("Initializing toolchain...")
                await toolchain.initialize()
                logger.info("Toolchain initialized successfully")

                self._toolchain = toolchain
                self._initialized = True

                logger.info(
                    f"Tool chain ready with {len(all_cached_clients)} server(s): {', '.join(self._server_cache.keys())}"
                )
                return self._toolchain, None

            except Exception as e:
                error_msg = f"Error loading toolchain: {type(e).__name__}: {e}"
                logger.error(error_msg)
                logger.error(f"Traceback: {traceback.format_exc()}")
                return None, error_msg

            finally:
                self._loading = False

    async def force_reload_server(self, server_name: str) -> bool:
        """Force reload a specific server (ignoring cache).

        Args:
            server_name: Name of server to reload

        Returns:
            True if reload successful, False otherwise
        """
        async with self._lock:
            logger.info(f"Force reloading server '{server_name}'")

            # Remove from cache if present
            if server_name in self._server_cache:
                cached = self._server_cache[server_name]
                try:
                    await cached.client.stop()
                except Exception as e:
                    logger.warning(f"Error stopping client during reload: {e}")
                del self._server_cache[server_name]

            # Trigger full reload
            self._toolchain = None

        # Load with cache miss
        toolchain, error = await self.get_or_load_toolchain()
        return error is None

    def get_cache_status(self) -> Dict[str, dict]:
        """Get status of all cached servers.

        Returns:
            Dictionary mapping server names to status info
        """
        status = {}
        for server_name, cache in self._server_cache.items():
            status[server_name] = {
                "loaded_at": cache.loaded_at.isoformat(),
                "age_minutes": cache.age_minutes,
                "ttl_minutes": cache.ttl_minutes,
                "expired": cache.is_expired(),
                "load_count": self._load_count.get(server_name, 0),
            }
        return status

    async def cleanup(self):
        """Clean up all cached clients."""
        async with self._lock:
            logger.info("Cleaning up tool chain cache")
            for server_name, cache in self._server_cache.items():
                try:
                    await cache.client.stop()
                    logger.debug(f"Stopped client '{server_name}'")
                except Exception as e:
                    logger.warning(f"Error stopping client '{server_name}': {e}")

            self._server_cache.clear()
            self._toolchain = None
            self._initialized = False
            logger.info("Tool chain cache cleaned up")


# Global singleton instance
_global_cache: Optional[ToolChainCache] = None


def get_toolchain_cache() -> ToolChainCache:
    """Get the global toolchain cache instance.

    Returns:
        Global ToolChainCache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = ToolChainCache()
    return _global_cache

