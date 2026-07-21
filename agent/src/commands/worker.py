"""Agent worker process: consume RunAgentTask commands from Redis."""

from __future__ import annotations

import argparse
import asyncio
import logging
import multiprocessing
import os
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_shutdown = False


def _signal_handler(signum, frame):
    global _shutdown
    logger.info("Received shutdown signal, stopping worker...")
    _shutdown = True


def _ensure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


async def _bootstrap_executor():
    """Initialize DB, toolchain, and AgentTaskExecutor for this worker process."""
    from commands.handlers.run_agent_task import set_executor
    from services.agent_task_executor import AgentTaskExecutor
    from sparky.initialization import create_langchain_toolchain
    from sparky.task_queue import create_task_queue

    logger.info("Worker bootstrap: creating LangChain toolchain...")
    toolchain, error = await create_langchain_toolchain(log_prefix="worker")
    if error or toolchain is None:
        raise RuntimeError(f"Failed to create toolchain: {error}")

    task_queue = await create_task_queue()
    executor = AgentTaskExecutor(toolchain=toolchain, task_queue=task_queue)
    set_executor(executor)
    logger.info("Worker bootstrap complete")
    return executor, task_queue


async def run_worker_async(
    queue_name: Optional[str] = None,
    redis_url: Optional[str] = None,
    enable_scheduled_tasks: bool = True,
) -> None:
    """BRPOP loop → dispatch handlers; also ticks schedules and reconciles."""
    global _shutdown

    if redis_url:
        os.environ["REDIS_URL"] = redis_url
    if queue_name:
        os.environ["REDIS_QUEUE_NAME"] = queue_name

    from commands.bus_config import create_bus, reset_redis_client
    from commands.handlers.register import register_handlers
    from commands.reconcile import reconcile_pending_tasks
    from commands.scheduler import tick_scheduled_tasks
    from sparky.scheduled_tasks import load_scheduled_tasks

    reset_redis_client()
    register_handlers()
    executor, task_queue = await _bootstrap_executor()

    bus = create_bus(queue_name=queue_name)
    qn = bus.queue_adapter.queue_name
    logger.info("Worker started, listening on queue: %s", qn)

    scheduled_tasks = []
    if enable_scheduled_tasks:
        scheduled_tasks = load_scheduled_tasks()
        logger.info("Loaded %d scheduled tasks", len(scheduled_tasks))

    # Reconcile pending tasks left without Redis messages
    try:
        n = await reconcile_pending_tasks(task_queue, min_age_seconds=5)
        if n:
            logger.info("Startup reconcile re-dispatched %d pending task(s)", n)
    except Exception as e:
        logger.warning("Startup reconcile failed: %s", e)

    cycle_count = 0
    last_heartbeat = time.time()
    last_schedule_tick = 0.0
    last_reconcile = time.time()
    schedule_interval = float(os.getenv("SPARKY_AGENT_POLL_INTERVAL", "10"))
    reconcile_interval = float(os.getenv("SPARKY_RECONCILE_INTERVAL_SECONDS", "60"))
    heartbeat_interval = 180.0
    base_path = Path(__file__).resolve().parents[2]

    while not _shutdown:
        try:
            messages = await asyncio.to_thread(
                bus.queue_adapter.get_messages,
                1,
                0.5,
            )
            if messages:
                message = messages[0]
                correlation_id = None
                try:
                    parser = bus.message_parser_class(message.body)
                    command_instance = parser.initialize()
                    correlation_id = getattr(
                        command_instance, "correlation_id", None
                    )
                except Exception as parse_err:
                    logger.error(
                        "Parse failed, dropping message: %s", parse_err, exc_info=True
                    )
                    try:
                        await asyncio.to_thread(bus.queue_adapter.dequeue, message)
                    except Exception:
                        pass
                    continue

                try:
                    await bus.dispatch(message.body)
                    await asyncio.to_thread(bus.queue_adapter.dequeue, message)
                except Exception as handler_error:
                    logger.error(
                        "Handler error: %s", handler_error, exc_info=True
                    )
                    if correlation_id and bus.response_store:
                        bus.response_store.set(
                            correlation_id,
                            {
                                "error": True,
                                "error_type": type(handler_error).__name__,
                                "error_message": str(handler_error),
                            },
                            ttl_seconds=bus.response_ttl_seconds,
                        )
                    try:
                        await asyncio.to_thread(bus.queue_adapter.dequeue, message)
                    except Exception as dq_err:
                        logger.warning(
                            "Dequeue after handler error failed: %s", dq_err
                        )
        except Exception as e:
            error_str = str(e).lower()
            if not any(
                k in error_str for k in ("timeout", "empty", "no message", "no item")
            ):
                logger.error("Error processing command: %s", e, exc_info=True)
                await asyncio.sleep(0.1)

        now = time.time()

        if enable_scheduled_tasks and now - last_schedule_tick >= schedule_interval:
            last_schedule_tick = now
            cycle_count += 1
            try:
                await tick_scheduled_tasks(
                    task_queue,
                    scheduled_tasks,
                    cycle_count,
                    base_path=base_path,
                )
            except Exception as e:
                logger.error("Schedule tick failed: %s", e, exc_info=True)

        if now - last_reconcile >= reconcile_interval:
            last_reconcile = now
            try:
                await reconcile_pending_tasks(task_queue, min_age_seconds=30)
            except Exception as e:
                logger.warning("Periodic reconcile failed: %s", e)

        if now - last_heartbeat >= heartbeat_interval:
            last_heartbeat = now
            logger.info(
                "Worker alive: queue=%r processed=%s cycles=%s",
                qn,
                executor.tasks_processed,
                cycle_count,
            )

    logger.info("Worker stopped (pid=%s)", os.getpid())


def run_worker(
    queue_name: Optional[str] = None,
    redis_url: Optional[str] = None,
    enable_scheduled_tasks: bool = True,
) -> None:
    global _shutdown
    _ensure_logging()
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    try:
        asyncio.run(
            run_worker_async(queue_name, redis_url, enable_scheduled_tasks)
        )
    except KeyboardInterrupt:
        logger.info("Worker interrupted")


def run_worker_pool(
    workers: int,
    queue_name: Optional[str] = None,
    redis_url: Optional[str] = None,
    enable_scheduled_tasks: bool = True,
) -> None:
    if workers < 1:
        raise ValueError("workers must be >= 1")
    if workers == 1:
        run_worker(queue_name, redis_url, enable_scheduled_tasks)
        return

    ctx = multiprocessing.get_context("spawn")
    procs: List[multiprocessing.Process] = []

    def _stop_children(_signum=None, _frame=None) -> None:
        for p in procs:
            if p.is_alive():
                p.terminate()
        for p in procs:
            p.join(timeout=30)

    signal.signal(signal.SIGINT, _stop_children)
    signal.signal(signal.SIGTERM, _stop_children)

    logger.info("Starting %d worker processes", workers)
    for i in range(workers):
        p = ctx.Process(
            target=run_worker,
            args=(queue_name, redis_url, enable_scheduled_tasks),
            name=f"sparky-worker-{i + 1}",
        )
        p.start()
        procs.append(p)

    exit_code = 0
    for p in procs:
        p.join()
        if p.exitcode not in (0, None):
            exit_code = max(
                exit_code,
                int(p.exitcode) if p.exitcode and p.exitcode > 0 else 1,
            )
    if exit_code:
        sys.exit(exit_code)


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Sparky agent command-bus worker")
    parser.add_argument(
        "-n",
        "--workers",
        type=int,
        default=int(os.getenv("WORKER_PROCESSES", "1")),
        help="Number of worker processes",
    )
    parser.add_argument("--queue-name", default=None)
    parser.add_argument("--redis-url", default=None)
    parser.add_argument(
        "--no-scheduled-tasks",
        action="store_true",
        help="Disable scheduled task ticker in this worker",
    )
    args = parser.parse_args(argv)
    _ensure_logging()
    run_worker_pool(
        workers=args.workers,
        queue_name=args.queue_name,
        redis_url=args.redis_url,
        enable_scheduled_tasks=not args.no_scheduled_tasks,
    )


if __name__ == "__main__":
    main()
