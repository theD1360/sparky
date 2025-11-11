import asyncio


def run_async(coro):
    """
    Run an asyncio coroutine, gracefully handling cases where an event loop is already running.
    This is a safer way to bridge sync and async code.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, so we can use asyncio.run
        return asyncio.run(coro)

    # If a loop is running, we need to schedule the coroutine
    # and wait for the result. This is primarily for calling async code
    # from a sync callback within an async application.
    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    else:
        # The loop exists but is not running, so we can run the coroutine on it.
        return loop.run_until_complete(coro)
