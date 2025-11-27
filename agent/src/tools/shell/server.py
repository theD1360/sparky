from __future__ import annotations

import os
import shlex
import subprocess
import time
from typing import Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from models import MCPResponse

mcp = FastMCP("badmcp-shell-server")


def _truncate(b: bytes, limit: int) -> bytes:
    """Truncate bytes to a maximum length."""
    if limit < 0 or len(b) <= limit:
        return b

    elision = b"<...truncated...>\n"
    if limit <= len(elision):
        return b[:limit]

    return elision + b[-(limit - len(elision)) :]


def _prepare_popen_args(
    use_shell: bool,
    command: str | None,
    argv: list[str],
    cwd: str | None,
    env_over: dict | None,
) -> tuple[dict | None, str | None]:
    """Validates inputs and prepares arguments for subprocess.run."""
    if use_shell:
        if not command or not isinstance(command, str):
            return None, "Error: 'command' (string) is required when shell=true"
        return {
            "args": command,
            "shell": True,
            "cwd": cwd,
            "env": {**os.environ, **(env_over or {})},
        }, None
    else:
        if not argv and command:
            try:
                argv = shlex.split(command)
            except Exception as e:
                return None, f"Error parsing command: {e}"
        if not argv or not all(isinstance(x, str) for x in argv):
            return (
                None,
                "Error: provide non-empty 'argv' (array of strings) or set shell=true with 'command'",
            )
        return {
            "args": argv,
            "shell": False,
            "cwd": cwd,
            "env": {**os.environ, **(env_over or {})},
        }, None


def _run_process(
    popen_args: dict, timeout: float
) -> tuple[int | None, bytes, bytes, bool, int]:
    """Runs a subprocess and captures its output and timing information."""
    start = time.time()
    timed_out = False
    try:
        cp = subprocess.run(
            **popen_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=False,
        )
        exit_code = cp.returncode
        stdout_b = cp.stdout or b""
        stderr_b = cp.stderr or b""
    except subprocess.TimeoutExpired as e:
        timed_out = True
        exit_code = None
        stdout_b = e.stdout or b""
        stderr_b = e.stderr or b""
    except (FileNotFoundError, PermissionError) as e:
        exit_code = -1
        stdout_b = b""
        stderr_b = str(e).encode("utf-8")
    except OSError as e:
        exit_code = -1
        stdout_b = b""
        error_message = f"File operation error: {e}"
        if e.errno == 2:  # errno.ENOENT: No such file or directory
            error_message += ". Check the file path."
        stderr_b = error_message.encode("utf-8")
        print(
            f"shell command error: {error_message}", file=os.sys.stderr
        )  # Simple logging to stderr
    except Exception as e:
        exit_code = -1
        stdout_b = b""
        stderr_b = f"Error running process: {e}".encode("utf-8")
    finally:
        duration_ms = int((time.time() - start) * 1000)

    return exit_code, stdout_b, stderr_b, timed_out, duration_ms


@mcp.tool()
async def shell(
    argv: Optional[List[str]] = None,
    command: Optional[str] = None,
    shell: bool = False,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
    max_output_bytes: int = 200000,
    text: bool = True,
    strip: bool = True,
) -> dict:
    """Run a non-interactive shell command. Prefer argv for safety (no shell).

    Returns JSON: exit_code, stdout, stderr, timed_out, duration_ms.

    Args:
        argv: Executable and arguments, e.g. ['ls', '-la'] (safer than shell)
        command: Command string to pass to /bin/sh -c when shell=true
        shell: If true, run via shell (/bin/sh -c). Requires 'command'
        cwd: Working directory for the process
        env: Environment variables to add/override
        timeout: Timeout in seconds (float)
        max_output_bytes: Truncate stdout/stderr to at most this many bytes
        text: Return text (UTF-8) instead of bytes for stdout/stderr
        strip: Strip trailing whitespace from stdout/stderr when text=true
    """
    argv = argv or []

    popen_args, error = _prepare_popen_args(shell, command, argv, cwd, env)
    if error:
        error_result = {
            "exit_code": -1,
            "stdout": "",
            "stderr": error,
            "timed_out": False,
            "duration_ms": 0,
        }
        return MCPResponse.error(message=error, result=error_result).to_dict()

    exit_code, stdout_b, stderr_b, timed_out, duration_ms = _run_process(
        popen_args, timeout
    )

    stdout_b = _truncate(stdout_b, max_output_bytes)
    stderr_b = _truncate(stderr_b, max_output_bytes)

    if text:
        stdout_out = (
            stdout_b.decode("utf-8", errors="replace").rstrip()
            if strip
            else stdout_b.decode("utf-8", errors="replace")
        )
        stderr_out = (
            stderr_b.decode("utf-8", errors="replace").rstrip()
            if strip
            else stderr_b.decode("utf-8", errors="replace")
        )
    else:
        stdout_out = stdout_b.decode("latin-1")
        stderr_out = stderr_b.decode("latin-1")

    result = {
        "argv": argv if not shell else None,
        "command": command if shell else None,
        "shell": shell,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
        "stdout": stdout_out,
        "stderr": stderr_out,
    }

    return MCPResponse.success(result=result, content_type="json").to_dict()


def main():
    mcp.run()


if __name__ == "__main__":
    main()
