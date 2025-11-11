"""Miscellaneous MCP server providing utility tools for sandboxed code.

This server exposes a collection of general-purpose tools under the MCP protocol
so they can be used from Sparky sessions.

Notes on run_code safety:
- Only language="python" is supported.
- We parse the code with ast and block Import/ImportFrom, Attribute access to dunder names,
  and calls to "__import__" or other dunder-named objects.
- Execution happens with extremely limited builtins (len, range, min, max, sum, any, all, list, dict, set, tuple, enumerate).
- Code length is limited and result is captured as last expression value if possible; stdout is also captured.
- This is a best-effort sandbox and not suitable for running untrusted code in hostile environments.
"""

from __future__ import annotations

import ast
import io
import subprocess
import sys
from contextlib import redirect_stdout
from typing import Any

import mcp.server.stdio
from mcp.server.fastmcp import FastMCP

from models import MCPResponse

mcp = FastMCP("miscellaneous")


# -----------------------------
# Tool specifications
# -----------------------------


# -----------------------------
# Helper functions
# -----------------------------

_SAFE_BUILTINS = {
    "len": len,
    "range": range,
    "min": min,
    "max": max,
    "sum": sum,
    "any": any,
    "all": all,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "enumerate": enumerate,
}


class SandboxError(Exception):
    pass


def _validate_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise SandboxError("Imports are not allowed")
        if isinstance(node, ast.Call):
            # Disallow calling names that start/end with '__'
            if isinstance(node.func, ast.Name):
                if node.func.id.startswith("__") or node.func.id.endswith("__"):
                    raise SandboxError("Calling dunder is not allowed")
            if isinstance(node.func, ast.Attribute):
                # Disallow calling __dunder__ attributes
                if node.func.attr.startswith("__") and node.func.attr.endswith("__"):
                    raise SandboxError("Calling dunder attribute is not allowed")
        if isinstance(node, ast.Attribute):
            # Disallow access to __dict__, __class__, etc.
            if node.attr.startswith("__") and node.attr.endswith("__"):
                raise SandboxError("Access to dunder attributes is not allowed")
        if isinstance(node, ast.Name):
            if node.id == "__import__":
                raise SandboxError("__import__ is not allowed")


def _run_python_code(code: str) -> dict:
    if len(code) > 8000:
        raise SandboxError("Code too long (limit 8000 characters)")
    try:
        tree = ast.parse(code, mode="exec")
        _validate_ast(tree)
    except SandboxError:
        raise
    except Exception as e:
        raise SandboxError(f"Invalid code: {e}")

    # Prepare envs
    sandbox_globals: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}
    sandbox_locals: dict[str, Any] = {}

    f = io.StringIO()
    result: Any = None
    try:
        with redirect_stdout(f):
            compiled = compile(tree, filename="<sandbox>", mode="exec")
            exec(compiled, sandbox_globals, sandbox_locals)
            # If last statement is an expression, evaluate it to get a result
            # We'll attempt to eval the last expression stored in a temp variable
            # Approach: append a final expression "_last_expr" if possible.
            try:
                last = tree.body[-1]
                if isinstance(last, ast.Expr):
                    expr_code = compile(
                        ast.Expression(last.value), filename="<sandbox>", mode="eval"
                    )
                    result = eval(expr_code, sandbox_globals, sandbox_locals)
            except Exception:
                pass
    except SandboxError:
        raise
    except Exception as e:
        raise SandboxError(str(e))

    stdout = f.getvalue()
    out = {"result": result, "stdout": stdout}
    return out


# -----------------------------
# Tool dispatcher
# -----------------------------


@mcp.tool()
def run_code(language: str = "python", code: str = None, path: str = None) -> dict:
    if language != "python":
        return MCPResponse.error("Only language='python' is supported").to_dict()

    if (code is not None and path is not None) or (code is None and path is None):
        return MCPResponse.error(
            "Provide either code or path, but not both or neither."
        ).to_dict()

    try:
        if code:
            out = _run_python_code(code)
            return MCPResponse.success(result=out).to_dict()
        elif path:
            # This is the crucial part: set the PYTHONPATH to the project root.
            # This assumes the script is run from the project root.
            env = {"PYTHONPATH": "."}

            process = subprocess.run(
                [sys.executable, path],
                capture_output=True,
                text=True,
                env=env,
                check=False,  # Don't raise exception on non-zero exit code
            )

            result = {
                "exit_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }
            return MCPResponse.success(result=result).to_dict()

    except SandboxError as e:
        return MCPResponse.error(f"Sandbox error: {e}").to_dict()
    except FileNotFoundError:
        return MCPResponse.error(f"File not found: {path}").to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error: {e}").to_dict()


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
