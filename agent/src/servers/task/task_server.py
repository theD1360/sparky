"""Task server — AgentLoop retained as a thin deprecated shim.

Background execution now runs in the command-bus worker
(`python -m commands.worker` / `sparky agent worker`).
"""

from logging import getLogger
from typing import Any, Optional

from sparky.langchain_toolchain import LangChainToolchain

logger = getLogger(__name__)


class AgentLoop:
    """Deprecated in-process poll loop.

    Prefer the Redis command-bus worker. This class remains only so older
    imports of ``AgentLoop`` / ``TaskServer`` do not break.
    """

    def __init__(
        self,
        toolchain: LangChainToolchain,
        control: Optional[Any] = None,
        poll_interval: int = 10,
        enable_scheduled_tasks: bool = True,
        config_path: Optional[Any] = None,
        connection_manager: Optional[Any] = None,
    ):
        self.toolchain = toolchain
        self.poll_interval = poll_interval
        self.enable_scheduled_tasks = enable_scheduled_tasks
        self.connection_manager = connection_manager
        self.running = False
        self._task = None
        logger.warning(
            "AgentLoop is deprecated; start `sparky agent worker` instead of "
            "running the in-process poll loop"
        )

    def start_background(self):
        raise RuntimeError(
            "In-process AgentLoop is retired. Run: sparky agent worker "
            "(or docker compose up worker)"
        )

    async def run(self):
        raise RuntimeError(
            "In-process AgentLoop is retired. Run: sparky agent worker "
            "(or docker compose up worker)"
        )

    async def stop(self):
        self.running = False

    async def get_stats(self):
        return {
            "deprecated": True,
            "message": "Use sparky agent worker for background tasks",
        }


async def run_agent_loop(
    toolchain: LangChainToolchain,
    control: Optional[Any] = None,
    poll_interval: int = 1,
):
    """Deprecated convenience wrapper."""
    loop = AgentLoop(toolchain, control, poll_interval)
    await loop.run()
