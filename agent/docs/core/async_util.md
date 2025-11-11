# Async Utilities (`async_util.py`)

This module provides utility functions to help manage and bridge synchronous and asynchronous code, which is a common requirement in a system that has both synchronous and asynchronous components.

## `run_async(coro)`

This is the key function in this module. Its purpose is to execute an `async` coroutine from a synchronous piece of code in a safe and reliable way.

### The Problem it Solves

Standard Python `asyncio` can be tricky to work with when you need to call an `async` function from a regular `def` function.

*   If no asyncio event loop is running, you can simply use `asyncio.run()`.
*   However, if an event loop *is* already running (which is common in applications that use libraries like `asyncio` or `fastapi`), calling `asyncio.run()` will raise a `RuntimeError`.

The `run_async` function handles this complexity automatically.

### How it Works

1.  **Check for a Running Loop:** It first tries to get the current event loop using `asyncio.get_running_loop()`.
2.  **No Loop Running:** If this fails with a `RuntimeError`, it means no loop is active, and it is safe to use `asyncio.run()` to execute the coroutine.
3.  **Loop is Running:** If a loop is found, it uses `asyncio.run_coroutine_threadsafe()`. This function schedules the coroutine to be run on the existing loop and returns a `Future`. The code then waits for this future to complete using `future.result()` and returns the final value.
4.  **Loop Exists but is Stopped:** In the less common case that a loop exists but is not currently running, it uses `loop.run_until_complete()`.

This utility is essential for components like the `Knowledge` module, which may have synchronous methods but need to call `async` methods on the `KnowledgeRepository`.
