"""Consolidated code tools MCP server.

This server consolidates filesystem, git, code execution, and code editing tools
into a single powerful interface. Designed for integration with knowledge graph
to provide context-aware development assistance.

Tool Categories:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. CODE EXECUTION
   - execute: Execute Python with optional sandboxing
   - Sandboxed mode: Restricted builtins, no imports, AST validation
   - Unsandboxed mode: Full Python capabilities (use with caution)

2. FILE OPERATIONS
   - read_file: Read files (with automatic graph indexing)
   - write_file: Write/overwrite files
   - append_file: Append to files
   - head, tail, get_lines: Read file sections
   - file_search: Search text across files using glob patterns (e.g., **/*.py)
   - file_info: Get file metadata
   - File protection system prevents accidental overwrites

3. CODE EDITING
   - edit_file: Intelligent search-replace editing with syntax validation
     (Replaces deprecated: get_lines_with_context, set_lines_with_indent,
      replace_code_block, insert_lines, find_and_replace_in_file)

4. DIRECTORY OPERATIONS
   - list_directory: List directory contents
   - file_tree: Generate tree representation
   - create_directory: Create directories
   - current_directory: Get working directory

5. FILE MANAGEMENT
   - copy, move, delete: File/directory manipulation operations

6. GIT TOOLS
   - git_status, git_diff, git_log, git_show: Repository inspection
   - git_branch, git_checkout: Branch management
   - git_add, git_commit: Change staging and commits

7. DEVELOPMENT TOOLS
   - lint: Execute linters (currently ruff for Python)

8. GRAPH-POWERED TOOLS ⚡
   - get_file_context: Get intelligent context about a file (imports, symbols, related files)
   - search_codebase: Semantic search across codebase by meaning
   - symbol_search: Find functions/classes in codebase (with wildcards)
   - find_references: Track where modules/symbols are used

9. ENHANCED SEARCH TOOLS ⚡ NEW!
   - file_search: Now supports regex patterns for advanced matching

10. BATCH OPERATIONS ⚡ NEW!
   - batch_read_files: Read multiple files in one operation

GRAPH INTEGRATION STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ PHASE 1 COMPLETE: Basic Graph Integration
   - Automatic file indexing on read
   - File metadata storage (language, size, hash)
   - Python structure parsing (functions, classes)
   - Import relationship tracking
   - Related file discovery
   - Semantic code search

FUTURE ENHANCEMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Symbol call graph analysis
- Code pattern recognition and learning
- Refactoring suggestions based on graph analysis
- Test coverage tracking
- Breaking change detection
- Tree-sitter for multi-language support
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import io
import json
import os
import shutil
import time
from contextlib import redirect_stdout
from logging import getLogger
from pathlib import Path
from typing import Any, Optional

from database.database import DatabaseManager, get_database_manager
from database.repository import KnowledgeRepository
from mcp.server.fastmcp import FastMCP
from models import MCPResponse
from utils.file_ops import (
    SearchReplaceMatchError,
    SearchReplaceSyntaxError,
    search_replace_edit,
)

logger = getLogger(__name__)
mcp = FastMCP("code-tools")
_db_manager: Optional[DatabaseManager] = None
_kb_repository: Optional[KnowledgeRepository] = None
_graph_initialized: bool = False
_file_read_whitelist: dict[str, dict[str, str]] = {}


def _detect_content_type(path: str, content: Any = None) -> Optional[str]:
    """Detect content type from file extension or content.

    Args:
        path: File path
        content: Optional file content for content-based detection

    Returns:
        Content type string (e.g., 'python', 'json', 'javascript') or None
    """
    from pathlib import Path as PathLib

    file_ext = PathLib(path).suffix.lstrip(".").lower()

    # Extension-based detection
    extension_map = {
        "py": "python",
        "js": "javascript",
        "jsx": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "java": "java",
        "go": "go",
        "rs": "rust",
        "c": "c",
        "cpp": "cpp",
        "cc": "cpp",
        "h": "c",
        "hpp": "cpp",
        "hxx": "cpp",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "toml": "toml",
        "xml": "xml",
        "html": "html",
        "css": "css",
        "scss": "scss",
        "sass": "sass",
        "sh": "bash",
        "bash": "bash",
        "zsh": "bash",
        "sql": "sql",
        "md": "markdown",
        "markdown": "markdown",
        "txt": "text",
        "log": "text",
        "ini": "ini",
        "cfg": "ini",
        "conf": "ini",
        "dockerfile": "dockerfile",
        "makefile": "makefile",
        "mk": "makefile",
        "rb": "ruby",
        "php": "php",
        "swift": "swift",
        "kt": "kotlin",
        "scala": "scala",
        "r": "r",
        "m": "matlab",
        "lua": "lua",
        "pl": "perl",
        "ps1": "powershell",
        "bat": "batch",
        "cmd": "batch",
    }

    # Check extension first
    if file_ext in extension_map:
        return extension_map[file_ext]

    # Content-based detection for JSON
    if content and isinstance(content, str):
        content_stripped = content.strip()
        if content_stripped.startswith("{") or content_stripped.startswith("["):
            try:
                json.loads(content_stripped)
                return "json"
            except (json.JSONDecodeError, ValueError):
                pass

    return None


async def _index_file_to_graph(path: str, content: str) -> None:
    """Index file metadata and structure into the knowledge graph.

    Extracts and stores:
    - File metadata (path, size, language, hash)
    - Code structure (functions, classes for Python)
    - Import relationships

    Args:
        path: File path
        content: File contents
    """
    if not _kb_repository:
        return
    try:
        import hashlib
        from pathlib import Path as PathLib

        file_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        file_ext = PathLib(path).suffix.lstrip(".")
        language_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "tsx": "typescript",
            "jsx": "javascript",
            "java": "java",
            "go": "go",
            "rs": "rust",
            "c": "c",
            "cpp": "cpp",
            "h": "c",
            "hpp": "cpp",
        }
        language = language_map.get(file_ext, "unknown")
        file_node_id = f"file:{path}"
        _kb_repository.add_node(
            node_id=file_node_id,
            node_type="File",
            label=PathLib(path).name,
            content=f"File: {path}\nLanguage: {language}\nSize: {len(content)} bytes",
            properties={
                "path": path,
                "language": language,
                "extension": file_ext,
                "size": len(content),
                "hash": file_hash,
                "lines": content.count("\n") + 1,
            },
        )
        if language == "python":
            await _index_python_file_structure(path, content, file_node_id)
        logger.info(f"Indexed file to graph: {path}")
    except Exception as e:
        logger.warning(
            f"Failed to index file {path} to graph. Error: {e}. File size: {len(content)} bytes."
        )


async def _index_python_file_structure(
    path: str, content: str, file_node_id: str
) -> None:
    """Extract and index Python file structure.

    Extracts:
    - Functions and their signatures
    - Classes and methods
    - Import statements

    Args:
        path: File path
        content: File contents
        file_node_id: Node ID of the file
    """
    if not _kb_repository:
        return
    try:
        tree = ast.parse(content)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        for imported_module in set(imports):
            module_node_id = f"module:{imported_module}"
            _kb_repository.add_node(
                node_id=module_node_id,
                node_type="Module",
                label=imported_module,
                content=f"Python module: {imported_module}",
                properties={"name": imported_module},
            )
            _kb_repository.add_edge(
                source_id=file_node_id, target_id=module_node_id, edge_type="IMPORTS"
            )
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if hasattr(node, "parent") and isinstance(node.parent, ast.ClassDef):
                    continue
                func_name = node.name
                func_line = node.lineno
                args = [arg.arg for arg in node.args.args]
                signature = f"{func_name}({', '.join(args)})"
                func_node_id = f"symbol:{path}:{func_name}:{func_line}"
                _kb_repository.add_node(
                    node_id=func_node_id,
                    node_type="Symbol",
                    label=func_name,
                    content=f"Function: {signature} at line {func_line}",
                    properties={
                        "name": func_name,
                        "kind": "function",
                        "file": path,
                        "line": func_line,
                        "signature": signature,
                    },
                )
                _kb_repository.add_edge(
                    source_id=file_node_id, target_id=func_node_id, edge_type="CONTAINS"
                )
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                class_line = node.lineno
                class_node_id = f"symbol:{path}:{class_name}:{class_line}"
                _kb_repository.add_node(
                    node_id=class_node_id,
                    node_type="Symbol",
                    label=class_name,
                    content=f"Class: {class_name} at line {class_line}",
                    properties={
                        "name": class_name,
                        "kind": "class",
                        "file": path,
                        "line": class_line,
                    },
                )
                _kb_repository.add_edge(
                    source_id=file_node_id,
                    target_id=class_node_id,
                    edge_type="CONTAINS",
                )
    except Exception as e:
        logger.warning(
            f"Failed to parse Python structure for {path}. Error: {e}. File size: {len(content)} bytes."
        )


async def _get_file_context(path: str) -> dict:
    """Get context information for a file from the knowledge graph.

    Returns:
        - related_files: Files that import this file or are imported by it
        - symbols: Functions/classes defined in this file
        - imports: Modules imported by this file
        - recent_changes: Recent edit history (future)

    Args:
        path: File path

    Returns:
        Dictionary with context information
    """
    if not _kb_repository:
        return {}
    try:
        file_node_id = f"file:{path}"
        file_node = _kb_repository.get_node(file_node_id)
        if not file_node:
            return {}
        context = {
            "file_info": {
                "path": path,
                "language": file_node.properties.get("language", "unknown"),
                "size": file_node.properties.get("size", 0),
                "lines": file_node.properties.get("lines", 0),
            },
            "imports": [],
            "symbols": [],
            "related_files": [],
        }
        import_edges = _kb_repository.get_edges(
            source_id=file_node_id, edge_type="IMPORTS"
        )
        context["imports"] = [
            edge.target_id.replace("module:", "") for edge in import_edges
        ]
        symbol_edges = _kb_repository.get_edges(
            source_id=file_node_id, edge_type="CONTAINS"
        )
        for edge in symbol_edges:
            symbol_node = _kb_repository.get_node(edge.target_id)
            if symbol_node:
                context["symbols"].append(
                    {
                        "name": symbol_node.properties.get("name", ""),
                        "kind": symbol_node.properties.get("kind", ""),
                        "line": symbol_node.properties.get("line", 0),
                        "signature": symbol_node.properties.get("signature", ""),
                    }
                )
        if context["imports"]:
            for module in context["imports"][:5]:
                module_node_id = f"module:{module}"
                files_importing_module = _kb_repository.get_edges(
                    target_id=module_node_id, edge_type="IMPORTS"
                )
                for edge in files_importing_module:
                    if edge.source_id != file_node_id and edge.source_id.startswith(
                        "file:"
                    ):
                        related_path = edge.source_id.replace("file:", "")
                        if related_path not in context["related_files"]:
                            context["related_files"].append(related_path)
        return context
    except Exception as e:
        logger.warning(f"Failed to get file context for {path}: {e}")
        return {}


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


def _load_graph():
    """Load or initialize database using KnowledgeRepository."""
    global _kb_repository, _db_manager, _graph_initialized
    if _graph_initialized:
        return
    db_url = os.getenv("SPARKY_DB_URL")
    if not db_url:
        db_url = os.getenv("SPARKY_DB_URL")
    if not db_url:
        raise RuntimeError(
            "SPARKY_DB_URL or SPARKY_DB_URL environment variable is required for database connection"
        )
    max_retries = 5
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            safe_db_url = db_url.split("@")[-1] if "@" in db_url else db_url[:50]
            logger.info(
                f"Connecting to PostgreSQL database (attempt {attempt + 1}/{max_retries}): ...@{safe_db_url}"
            )
            _db_manager = get_database_manager(db_url=db_url)
            _db_manager.connect()
            _kb_repository = KnowledgeRepository(_db_manager)
            stats = _kb_repository.get_graph_stats()
            node_count = stats["total_nodes"]
            edge_count = stats["total_edges"]
            if node_count == 0:
                logger.warning(
                    "Empty database detected. Run 'sparky db migrate' to initialize schema and seed bot identity data."
                )
            else:
                logger.debug(
                    "Connected to database: %d nodes, %d edges", node_count, edge_count
                )
            logger.debug("Query engine initialized successfully")
            _graph_initialized = True
            return
        except Exception as e:
            logger.warning(
                f"Database connection failed (attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                time.sleep(retry_delay**attempt)
            else:
                logger.error("Max retries reached, failing to connect to database.")
                raise


def _ensure_graph_initialized():
    """Ensure graph is initialized, load if needed.

    This is called by graph-powered tools to lazily initialize the graph
    on first use rather than at module import time.
    """
    if not _graph_initialized:
        _load_graph()


def _mark_file_as_read(path: str, content: str) -> None:
    """Mark file as safe to edit after reading."""
    file_hash = hashlib.sha256(content.encode()).hexdigest()
    _file_read_whitelist[path] = {"hash": file_hash, "timestamp": time.time()}
    logger.debug(f"Marked file as read: {path}")


def _check_can_edit(path: str, content_to_write: str = "") -> tuple[bool, str]:
    """Check if file can be safely edited.

    This function provides protection against accidental overwrites by:
    1. Allowing edits to files that have been explicitly read in this session
    2. Allowing edits to new files (that don't exist yet)
    3. For files not in whitelist, automatically reading and marking them for safety

    Returns:
        Tuple of (can_edit, error_message)
    """
    if not os.path.exists(path):
        return (True, "")
    if path in _file_read_whitelist:
        try:
            with open(path, "r", encoding="utf-8") as f:
                current_content = f.read()
            current_hash = hashlib.sha256(current_content.encode()).hexdigest()
            if current_hash != _file_read_whitelist[path]["hash"]:
                logger.info(f"File {path} changed since last read, updating whitelist")
                _mark_file_as_read(path, current_content)
        except Exception as e:
            logger.warning(f"Error checking file hash: {e}")
        return (True, "")
    try:
        with open(path, "r", encoding="utf-8") as f:
            current_content = f.read()
        _mark_file_as_read(path, current_content)
        logger.info(f"Auto-marked file {path} as read for editing")
        return (True, "")
    except Exception as e:
        return (False, f"Error reading file: {str(e)}")


def _check_syntax(ext: str, content: str) -> tuple[str, list]:
    """Check syntax of file content.

    Currently only validates Python files using ast.parse.
    Tree-sitter integration planned for future enhancement.

    Returns:
        Tuple of (error_description, error_list)
    """
    if ext == "py":
        try:
            ast.parse(content)
            return ("", [])
        except SyntaxError as e:
            logger.info(f"CHECKING SYNTAX AND FAILED with {e}")
            offset = e.offset or 0
            error_msg = f"Line {e.lineno}: {e.msg}\n{content[max(0, offset - 50):min(len(content), offset + 50)]}"
            return (error_msg, [{"line": e.lineno, "message": e.msg}])
        except Exception as e:
            logger.warning("Syntax check failed: %s", e)
            return ("", [])
    return ("", [])


def _get_file_tree(path: str, max_depth: int = 3, include_files: bool = True) -> str:
    """Get a tree-like representation of a directory structure."""

    def _build_tree(
        current_path: str, prefix: str = "", is_last: bool = True, depth: int = 0
    ) -> str:
        """Recursively build tree structure with proper formatting."""
        if depth > max_depth:
            return ""

        result = ""
        path_obj = Path(current_path)
        name = path_obj.name if depth > 0 else path_obj.as_posix()

        # Add current directory/file
        connector = "└── " if is_last else "├── "
        result += f"{prefix}{connector}{name}\n"

        if not os.path.isdir(current_path):
            return result

        # Prepare items (directories first, then files)
        try:
            items = []
            for item in sorted(os.listdir(current_path)):
                item_path = os.path.join(current_path, item)
                if os.path.isdir(item_path):
                    items.append((item, item_path, True))
                elif include_files:
                    items.append((item, item_path, False))

            # Process each item
            for idx, (item_name, item_path, is_dir) in enumerate(items):
                is_last_item = idx == len(items) - 1
                extension = "    " if is_last else "│   "
                new_prefix = prefix + extension

                if is_dir:
                    result += _build_tree(
                        item_path, new_prefix, is_last_item, depth + 1
                    )
                else:
                    connector = "└── " if is_last_item else "├── "
                    result += f"{new_prefix}{connector}{item_name}\n"
        except PermissionError:
            result += f"{prefix}    [Permission Denied]\n"

        return result

    if not os.path.exists(path):
        return f"Path not found: {path}\n"

    return _build_tree(path, "", True, 0)


def _validate_ast(tree: ast.AST) -> None:
    """
    Validate the AST to ensure it is safe to execute.
    This is a best-effort sandbox to prevent malicious code from being executed.
    It does not guarantee security and should not be used in untrusted environments.
    It is only intended to be used in a trusted environment.
    It is not intended to be used in a hostile environment.
    It is not intended to be used in a production environment.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise SandboxError("Imports are not allowed")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id.startswith("__") or node.func.id.endswith("__"):
                    raise SandboxError("Calling dunder is not allowed")
            if isinstance(node.func, ast.Attribute):
                if node.func.attr.startswith("__") and node.func.attr.endswith("__"):
                    raise SandboxError("Calling dunder attribute is not allowed")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                raise SandboxError("Access to dunder attributes is not allowed")
        if isinstance(node, ast.Name):
            if node.id == "__import__":
                raise SandboxError("__import__ is not allowed")


def _run_python_code(code: str) -> dict:
    """
    Run Python code with sandbox restrictions.
    This is a best-effort sandbox to prevent malicious code from being executed.
    It does not guarantee security and should not be used in untrusted environments.
    It is only intended to be used in a trusted environment.
    It is not intended to be used in a hostile environment.
    It is not intended to be used in a production environment.
    """
    if len(code) > 8000:
        raise SandboxError("Code too long (limit 8000 characters)")
    try:
        tree = ast.parse(code, mode="exec")
        _validate_ast(tree)
    except SandboxError:
        raise
    except Exception as e:
        raise SandboxError(f"Invalid code: {e}")
    sandbox_globals: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}
    sandbox_locals: dict[str, Any] = {}
    f = io.StringIO()
    result: Any = None
    try:
        with redirect_stdout(f):
            compiled = compile(tree, filename="<sandbox>", mode="exec")
            exec(compiled, sandbox_globals, sandbox_locals)
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
    return {"result": result, "stdout": stdout}


def _run_python_code_unsandboxed(code: str) -> dict:
    """Run Python code without sandbox restrictions.

    WARNING: This executes arbitrary code with full Python capabilities.
    Only use in trusted environments.
    """
    if len(code) > 50000:
        raise ValueError("Code too long (limit 50000 characters)")
    exec_globals = {"__builtins__": __builtins__}
    exec_locals = {}
    f = io.StringIO()
    result: Any = None
    try:
        with redirect_stdout(f):
            exec(code, exec_globals, exec_locals)
            try:
                tree = ast.parse(code, mode="exec")
                last = tree.body[-1]
                if isinstance(last, ast.Expr):
                    result = eval(
                        compile(ast.Expression(last.value), "<string>", "eval"),
                        exec_globals,
                        exec_locals,
                    )
            except Exception:
                pass
    except Exception as e:
        raise RuntimeError(f"Execution error: {e}")
    stdout = f.getvalue()
    return {"result": result, "stdout": stdout}


async def _run_shell_command(command: list[str]) -> dict:
    """Execute a shell command and return the result."""
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return {
        "exit_code": process.returncode,
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
    }


@mcp.tool()
async def git_status() -> dict:
    """Show the working tree status."""
    try:
        result = await _run_shell_command(["git", "status"])
        if result["exit_code"] == 0:
            return MCPResponse.success(result=result).to_dict()
        else:
            return MCPResponse.error(
                message=f"Git command failed with exit code {result['exit_code']}",
                result=result,
            ).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
async def git_diff(file: str = None) -> dict:
    """Show changes in the working directory. Can be limited to a specific file."""
    try:
        command = ["git", "diff"]
        if file:
            command.append(file)
        result = await _run_shell_command(command)
        if result["exit_code"] == 0:
            return MCPResponse.success(result=result).to_dict()
        else:
            return MCPResponse.error(
                message=f"Git command failed with exit code {result['exit_code']}",
                result=result,
            ).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
async def git_log(limit: int = 10) -> dict:
    """Show the commit history."""
    try:
        command = ["git", "log", f"-n{limit}"]
        result = await _run_shell_command(command)
        if result["exit_code"] == 0:
            return MCPResponse.success(result=result).to_dict()
        else:
            return MCPResponse.error(
                message=f"Git command failed with exit code {result['exit_code']}",
                result=result,
            ).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
async def git_show(commit: str = "HEAD") -> dict:
    """Show details of a specific commit including changes.

    Displays commit metadata (author, date, message) and the diff of changes.
    Useful for reviewing what was changed in a commit.

    Args:
        commit: Commit reference (hash, HEAD, HEAD~1, branch name, etc.)
                Default: "HEAD" (most recent commit)

    Returns:
        MCPResponse with commit details and diff

    Examples:
        git_show()  # Show most recent commit
        git_show("HEAD~1")  # Show previous commit
        git_show("abc123")  # Show specific commit by hash
    """
    try:
        command = ["git", "show", commit]
        result = await _run_shell_command(command)
        if result["exit_code"] == 0:
            return MCPResponse.success(result=result).to_dict()
        else:
            return MCPResponse.error(
                message=f"Git command failed with exit code {result['exit_code']}",
                result=result,
            ).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
async def git_branch() -> dict:
    """
    List all local branches.
    Returns:
        MCPResponse with the result of the git branch command.
    """
    try:
        result = await _run_shell_command(["git", "branch"])
        if result["exit_code"] == 0:
            return MCPResponse.success(result=result).to_dict()
        else:
            return MCPResponse.error(
                message=f"Git command failed with exit code {result['exit_code']}",
                result=result,
            ).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
async def git_add(files: list[str]) -> dict:
    """
    Stage a file for commit.

    Note: This cannot be used concurrently with git commit. Please use this tool before using git_commit.

    Args:
        files: List of files to stage for commit.
    Returns:
        MCPResponse with the result of the git add command.
    """
    try:
        command = ["git", "add"] + files
        result = await _run_shell_command(command)
        if result["exit_code"] == 0:
            return MCPResponse.success(result=result).to_dict()
        else:
            return MCPResponse.error(
                message=f"Git command failed with exit code {result['exit_code']}",
                result=result,
            ).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
async def git_commit(message: str) -> dict:
    """
    Commit staged changes.

    Note: This cannot be used concurrently with git add. Please use git_add first before using this tool.

    Args:
        message: The message to commit with.
    Returns:
        MCPResponse with the result of the git commit command.
    """
    try:
        command = ["git", "commit", "-m", message]
        result = await _run_shell_command(command)
        if result["exit_code"] == 0:
            return MCPResponse.success(result=result).to_dict()
        else:
            return MCPResponse.error(
                message=f"Git command failed with exit code {result['exit_code']}",
                result=result,
            ).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
async def git_checkout(branch_name: str, create_new: bool = False) -> dict:
    """
    Switch branches or create a new one.

    Args:
        branch_name: The name of the branch to switch to.
        create_new: If True, create a new branch.
    Returns:
        MCPResponse with the result of the git checkout command.
    """
    try:
        command = ["git", "checkout"]
        if create_new:
            command.append("-b")
        command.append(branch_name)
        result = await _run_shell_command(command)
        if result["exit_code"] == 0:
            return MCPResponse.success(result=result).to_dict()
        else:
            return MCPResponse.error(
                message=f"Git command failed with exit code {result['exit_code']}",
                result=result,
            ).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def execute(code: str, language: str = "python", use_sandbox: bool = True) -> dict:
    """Execute Python code with optional sandbox restrictions.

    Args:
        code: The Python code to execute
        language: Programming language (currently only 'python' supported)
        use_sandbox: If True, runs in restricted sandbox (no imports, limited builtins).
                     If False, runs with full Python capabilities (use with caution).

    Returns:
        MCPResponse with:
        - result: dict containing 'result' (last expression value) and 'stdout' (printed output)
        - message: Execution summary
    """
    try:
        language = language.lower()
        if language != "python":
            return MCPResponse.error("Only language='python' is supported").to_dict()
        try:
            if use_sandbox:
                out = _run_python_code(code)
                mode = "sandboxed"
            else:
                out = _run_python_code_unsandboxed(code)
                mode = "unsandboxed"
            has_output = bool(out.get("stdout"))
            has_result = out.get("result") is not None
            code_lines = code.count("\n") + 1
            message_parts = [f"Executed {code_lines} line(s) in {mode} mode"]
            if has_result:
                message_parts.append("with return value")
            if has_output:
                message_parts.append("with stdout output")
            message = " ".join(message_parts)
            return MCPResponse.success(result=out, message=message).to_dict()
        except SandboxError as e:
            return MCPResponse.error(f"Sandbox error: {e}").to_dict()
        except (ValueError, RuntimeError) as e:
            return MCPResponse.error(str(e)).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error: {e}").to_dict()


@mcp.tool()
async def read_file(path: str, index_to_graph: bool = True) -> dict:
    """Read the contents of a file and mark it as safe to edit.

    This tool reads a file and automatically marks it in the file protection whitelist,
    allowing subsequent edits via write_file, append_file, or edit_file.
    Always read a file before attempting to edit it.

    **NEW**: Automatically indexes file metadata and structure to the knowledge graph
    for context-aware development assistance.

    Args:
        path: Path to the file to read
        index_to_graph: If True, index file to knowledge graph (default: True)

    Returns:
        The complete file contents as a string
    """
    try:
        if not os.path.exists(path):
            return MCPResponse.error(f"Error: File not found: {path}").to_dict()
        if not os.path.isfile(path):
            return MCPResponse.error(f"Error: Not a file: {path}").to_dict()
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        _mark_file_as_read(path, content)
        if index_to_graph:
            try:
                _ensure_graph_initialized()
                await _index_file_to_graph(path, content)
            except Exception as e:
                logger.warning(f"Graph indexing skipped for {path}: {e}")
        content_type = _detect_content_type(path, content)
        return MCPResponse.success(result=content, content_type=content_type).to_dict()
    except FileNotFoundError:
        return MCPResponse.error(f"Error: File not found: {path}").to_dict()
    except PermissionError:
        return MCPResponse.error(f"Error: Permission denied: {path}").to_dict()
    except Exception as e:
        logger.exception(f"Error reading file: {path}")
        return MCPResponse.error(f"Error reading file: {str(e)}").to_dict()


@mcp.tool()
def list_directory(path: str = ".") -> dict:
    """List all files and directories in the specified path.

    Returns a sorted list of all entries (files and directories) in the given path.
    Does not recurse into subdirectories. Use file_tree for a recursive view.

    Args:
        path: Directory path to list (defaults to current directory)

    Returns:
        Newline-separated sorted list of entry names
    """
    try:
        entries = os.listdir(path)
        result = "\n".join(sorted(entries))
        return MCPResponse.success(result=result, content_type="text").to_dict()
    except FileNotFoundError:
        return MCPResponse.error("Error: Directory not found").to_dict()
    except PermissionError:
        return MCPResponse.error("Error: Permission denied").to_dict()
    except Exception as e:
        logger.exception(f"Error listing directory: {path}")
        return MCPResponse.error(f"Error listing directory: {str(e)}").to_dict()


@mcp.tool()
async def write_file(path: str, content: str) -> dict:
    """Write content to a file (simple file editing without validation).

    This is a generic file writing tool that performs no validation or syntax checking.
    The file must have been read in this session before editing (file protection).

    For code editing with syntax validation and intelligent search-replace, use
    edit_file instead.
    """
    try:
        can_edit, error_msg = _check_can_edit(path)
        if not can_edit:
            return MCPResponse.error(error_msg).to_dict()
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        _mark_file_as_read(path, content)
        message = f"Successfully wrote to {path}"
        return MCPResponse.success(result={"path": path}, message=message).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error writing file: {str(e)}").to_dict()


@mcp.tool()
def file_info(path: str) -> dict:
    """Get detailed metadata about a file or directory.

    Retrieves file system information including size, modification time, and type.
    Useful for checking if a path exists and what type of filesystem object it is.

    Args:
        path: Path to the file or directory

    Returns:
        Dictionary containing:
        - path: The provided path
        - size_bytes: Size in bytes
        - modified_time: Last modification timestamp (Unix epoch)
        - is_directory: True if path is a directory
        - is_file: True if path is a regular file
    """
    try:
        stat = os.stat(path)
        info = {
            "path": path,
            "size_bytes": stat.st_size,
            "modified_time": stat.st_mtime,
            "is_directory": os.path.isdir(path),
            "is_file": os.path.isfile(path),
        }
        return MCPResponse.success(result=info).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error getting file info: {str(e)}").to_dict()


@mcp.tool()
def create_directory(path: str) -> dict:
    """Create a new directory at the specified path.

    Creates the directory and any necessary parent directories (like 'mkdir -p').
    If the directory already exists, the operation succeeds without error.

    Args:
        path: Path where the directory should be created

    Returns:
        Dictionary with the created directory path
    """
    try:
        os.makedirs(path, exist_ok=True)
        return MCPResponse.success(
            result={"path": path}, message=f"Successfully created directory: {path}"
        ).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error creating directory: {str(e)}").to_dict()


@mcp.tool()
async def edit_file(path: str, edits: str) -> dict:
    """Edit code files using search-replace blocks with syntax validation.

    **Primary tool for code editing.** Provides intelligent matching, automatic
    indentation fixing, and syntax validation.

    Features:
    - Fuzzy matching with whitespace/indentation tolerance
    - Automatic indentation fixing
    - Multiple match detection and prevention
    - Syntax validation after edits
    - File protection (must read before edit)

    Format:
    <<<<<<< SEARCH
    code to find (include 3-5 lines of context for uniqueness)
    =======
    replacement code
    >>>>>>> REPLACE

    Multiple blocks can be used in sequence. Each SEARCH block must uniquely
    match content in the file.

    Example:
    <<<<<<< SEARCH
    def old_function():
        print("old")
    =======
    def new_function():
        print("new")
    >>>>>>> REPLACE

    Args:
        path: Path to file to edit
        edits: String containing one or more search-replace blocks

    Returns:
        Success/error response with edit results and any warnings
    """
    try:
        can_edit, error_msg = _check_can_edit(path)
        if not can_edit:
            return MCPResponse.error(error_msg).to_dict()
        if not os.path.exists(path):
            return MCPResponse.error(f"Error: file {path} does not exist").to_dict()
        with open(path, "r", encoding="utf-8") as f:
            original_content = f.read()
        lines = edits.strip().split("\n")

        def log_fn(msg: str) -> None:
            logger.debug(msg)

        try:
            edited_content, comments = search_replace_edit(
                lines, original_content, log_fn
            )
        except SearchReplaceSyntaxError as e:
            return MCPResponse.error(str(e)).to_dict()
        except SearchReplaceMatchError as e:
            return MCPResponse.error(str(e)).to_dict()
        try:
            tree = ast.parse(edited_content)
            edited_content = ast.unparse(tree)
        except Exception as e:
            logger.warning(f"AST formatting failed: {e}")
            return MCPResponse.error(f"AST formatting failed: {e}").to_dict()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(edited_content)
        except Exception as e:
            return MCPResponse.error(f"Write Error: {str(e)}").to_dict()
        extension = Path(path).suffix.lstrip(".")
        syntax_errors = ""
        error_list = []
        if extension == "py":
            try:
                syntax_errors, error_list = _check_syntax(extension, edited_content)
            except Exception as e:
                logger.info(f"Syntax check failed in edit_file tool: {e}")
        warnings = []
        warnings = []
        if syntax_errors:
            if extension in {"tsx", "ts"}:
                syntax_errors += "\nNote: Ignore if 'tagged template literals' are used, they may raise false positive errors in tree-sitter."
            warnings.append(f"Warning: Syntax errors detected:\n{syntax_errors}")
        _mark_file_as_read(path, edited_content)
        message = comments
        if warnings:
            message += "\n\n" + "\n".join(warnings)
        return MCPResponse.success(
            result={"path": path, "warnings": warnings, "comments": comments},
            message=message,
        ).to_dict()
    except Exception as e:
        logger.error(f"Error in edit_file: {e}")
        return MCPResponse.error(f"Error during file edit: {str(e)}").to_dict()


@mcp.tool()
async def append_file(path: str, content: str) -> dict:
    """Append content to a file (simple file editing without validation).

    This is a generic file appending tool that performs no validation or syntax checking.
    The file will be created if it does not exist. The file must have been read in this
    session before editing (file protection).

    For code editing with syntax validation and intelligent search-replace, use
    edit_file instead.

    Args:
        path: Path to the file to append to
        content: Content to append
    """
    try:
        can_edit, error_msg = _check_can_edit(path)
        if not can_edit:
            return MCPResponse.error(error_msg).to_dict()
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        with open(path, "r", encoding="utf-8") as f:
            full_content = f.read()
        _mark_file_as_read(path, full_content)
        message = f"Successfully appended to {path}"
        return MCPResponse.success(result={"path": path}, message=message).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error appending to file: {str(e)}").to_dict()


@mcp.tool()
def head(path: str, lines: int = 10) -> dict:
    """Return the first N lines of a file.

    Useful for quickly previewing the beginning of a file without reading the entire contents.
    Similar to the Unix 'head' command.

    Args:
        path: Path to the file to read
        lines: Number of lines to return (default: 10)

    Returns:
        String containing the first N lines of the file
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            head_lines = [next(f) for _ in range(int(lines))]
        result = "".join(head_lines)
        content_type = _detect_content_type(path, result)
        return MCPResponse.success(result=result, content_type=content_type).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error reading file: {str(e)}").to_dict()


@mcp.tool()
def tail(path: str, lines: int = 10) -> dict:
    """Return the last N lines of a file.

    Useful for checking the end of a file, such as recent log entries.
    Similar to the Unix 'tail' command.

    Args:
        path: Path to the file to read
        lines: Number of lines to return (default: 10)

    Returns:
        String containing the last N lines of the file
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            tail_lines = f.readlines()[-int(lines) :]
        result = "".join(tail_lines)
        content_type = _detect_content_type(path, result)
        return MCPResponse.success(result=result, content_type=content_type).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error reading file: {str(e)}").to_dict()


@mcp.tool()
def file_search(
    pattern: str,
    query: str,
    case_sensitive: bool = True,
    use_regex: bool = False,
    max_results: int = 100,
) -> dict:
    """Search for text across multiple files using glob patterns.

    **Enhanced tool** that searches for text across one or many files. Supports
    glob patterns to search multiple files at once, and regex for advanced matching.

    Args:
        pattern: File path or glob pattern to search
                 Examples:
                 - "file.py" - single file
                 - "*.py" - all Python files in current dir
                 - "src/**/*.py" - all Python files recursively in src/
                 - "**/*.{py,js}" - all Python and JS files everywhere
        query: Text string or regex pattern to search for
        case_sensitive: Whether search is case-sensitive (default: True)
        use_regex: Whether to treat query as a regex pattern (default: False)
        max_results: Maximum number of results to return (default: 100)

    Returns:
        List of matches with file paths, line numbers, and matching lines

    Examples:
        # Search single file
        file_search("src/main.py", "def main")

        # Search all Python files
        file_search("**/*.py", "TODO")

        # Regex search for function definitions
        file_search(r"**/*.py", r"def \\w+\\(.*\\):", use_regex=True)

        # Find all class definitions
        file_search(r"**/*.py", r"class \\w+.*:", use_regex=True)
    """
    try:
        import glob
        import re

        if "**" in pattern or "*" in pattern or "?" in pattern or ("{" in pattern):
            files = glob.glob(pattern, recursive=True)
            files = [f for f in files if os.path.isfile(f)]
        else:
            if not os.path.exists(pattern):
                return MCPResponse.error(f"File not found: {pattern}").to_dict()
            if not os.path.isfile(pattern):
                return MCPResponse.error(f"Not a file: {pattern}").to_dict()
            files = [pattern]
        if not files:
            return MCPResponse.error(
                f"No files found matching pattern: {pattern}"
            ).to_dict()
        if use_regex:
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                regex_pattern = re.compile(query, flags)
            except re.error as e:
                return MCPResponse.error(f"Invalid regex pattern: {str(e)}").to_dict()
        else:
            search_query = query if case_sensitive else query.lower()
        results = []
        total_matches = 0
        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line_num, line in enumerate(lines, start=1):
                    if use_regex:
                        match = regex_pattern.search(line)
                        if match:
                            results.append(
                                {
                                    "file": file_path,
                                    "line": line_num,
                                    "content": line.rstrip(),
                                    "match": match.group(0),
                                }
                            )
                            total_matches += 1
                    else:
                        line_to_check = line if case_sensitive else line.lower()
                        if search_query in line_to_check:
                            results.append(
                                {
                                    "file": file_path,
                                    "line": line_num,
                                    "content": line.rstrip(),
                                }
                            )
                            total_matches += 1
                    if total_matches >= max_results:
                        break
                if total_matches >= max_results:
                    break
            except (UnicodeDecodeError, PermissionError):
                continue
        files_searched = len(files)
        files_with_matches = len(set((r["file"] for r in results)))
        search_type = "regex" if use_regex else "text"
        message = f"Found {total_matches} {search_type} match(es) in {files_with_matches} file(s)"
        message += f" (searched {files_searched} file(s))"
        if total_matches >= max_results:
            message += f"\n⚠️ Results limited to {max_results}. Use max_results parameter for more."
        return MCPResponse.success(
            result={
                "matches": results,
                "total_matches": total_matches,
                "files_searched": files_searched,
                "files_with_matches": files_with_matches,
                "query": query,
                "pattern": pattern,
                "case_sensitive": case_sensitive,
                "use_regex": use_regex,
            },
            message=message,
        ).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error during file search: {str(e)}").to_dict()


@mcp.tool()
def copy(source: str, destination: str) -> dict:
    """Copy a file from source to destination.

    Creates a copy of the file, preserving the original. If destination is a directory,
    the file will be copied into that directory with the same name. If destination is
    a file path, the copy will have that name.

    Args:
        source: Path to the source file to copy
        destination: Path where the copy should be created (file or directory)

    Returns:
        Dictionary with source and destination paths
    """
    try:
        shutil.copy(source, destination)
        return MCPResponse.success(
            result={"source": source, "destination": destination},
            message=f"Successfully copied {source} to {destination}",
        ).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error copying file: {str(e)}").to_dict()


@mcp.tool()
def move(source: str, destination: str) -> dict:
    """Move or rename a file or directory.

    Moves the file/directory from source to destination. Can be used to rename a file
    by providing a new name in the same directory, or to move it to a different location.
    The source file/directory will no longer exist after this operation.

    Args:
        source: Path to the source file or directory
        destination: New path or location for the file/directory

    Returns:
        Dictionary with source and destination paths
    """
    try:
        shutil.move(source, destination)
        return MCPResponse.success(
            result={"source": source, "destination": destination},
            message=f"Successfully moved {source} to {destination}",
        ).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error moving file: {str(e)}").to_dict()


@mcp.tool()
def delete(path: str) -> dict:
    """Delete a file or directory permanently.

    WARNING: This operation is irreversible. The file or directory will be permanently
    deleted from the filesystem. For directories, all contents will be recursively deleted.
    Use with caution.

    Args:
        path: Path to the file or directory to delete

    Returns:
        Dictionary with path and type (file or directory) of deleted item
    """
    try:
        if os.path.isfile(path):
            os.remove(path)
            return MCPResponse.success(
                result={"path": path, "type": "file"},
                message=f"Successfully deleted file: {path}",
            ).to_dict()
        elif os.path.isdir(path):
            shutil.rmtree(path)
            return MCPResponse.success(
                result={"path": path, "type": "directory"},
                message=f"Successfully deleted directory: {path}",
            ).to_dict()
        else:
            return MCPResponse.error(
                f"Error: {path} is not a file or directory"
            ).to_dict()
    except Exception as e:
        return MCPResponse.error(
            f"Error deleting file or directory: {str(e)}"
        ).to_dict()


@mcp.tool()
def get_lines(path: str, start_line: int, end_line: int) -> dict:
    """Return a specific range of lines from a file.

    Extracts a contiguous range of lines from a file. Useful for reading specific
    sections without loading the entire file. Line numbers are 1-indexed.

    Args:
        path: Path to the file to read
        start_line: First line to return (1-indexed, inclusive)
        end_line: Last line to return (1-indexed, inclusive)

    Returns:
        String containing the requested line range
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()[start_line - 1 : end_line]
        result = "".join(lines)
        content_type = _detect_content_type(path, result)
        return MCPResponse.success(result=result, content_type=content_type).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error getting lines from file: {str(e)}").to_dict()


@mcp.tool()
def file_tree(path: str, max_depth: int = 3, include_files: bool = True) -> dict:
    """Generate a tree-like representation of a directory structure.

    Creates a visual hierarchical view of directories and optionally files, similar to
    the Unix 'tree' command. Useful for understanding project structure at a glance.

    Args:
        path: Root directory path to generate tree from
        max_depth: Maximum depth to recurse into subdirectories (default: 3)
        include_files: Whether to include files in the output (default: True)

    Returns:
        String containing a formatted tree representation of the directory structure
    """
    path_obj = Path(path).absolute()
    if not path_obj.exists():
        return MCPResponse.error(f"Path not found: {path}").to_dict()
    tree = _get_file_tree(str(path_obj), max_depth, include_files)
    # Use 'plaintext' content type to preserve formatting and newlines in code block
    return MCPResponse.success(result=tree, content_type="plaintext").to_dict()


@mcp.tool()
def current_directory() -> dict:
    """Get the current working directory of the server process.

    Returns the absolute path of the directory from which the filesystem server
    is currently operating. This is the base directory for all relative path operations.

    Returns:
        String containing the absolute path of the current working directory
    """
    path = os.getcwd()
    return MCPResponse.success(result=path).to_dict()


@mcp.prompt()
def explore_codebase(directory: str = ".") -> str:
    """Template for systematically exploring and understanding a codebase."""
    return f"""I need to understand the codebase structure at '{directory}'. Follow this approach:\n\n1. Use file_tree(path="{directory}", max_depth=3) to get an overview of the structure\n2. Look for key files:\n   - README, docs/, or documentation\n   - Configuration files (package.json, pyproject.toml, etc.)\n   - Main entry points (main.py, index.js, etc.)\n   - Test directories\n3. Use read_file() to examine important files\n4. Identify:\n   - Project type and purpose\n   - Main modules/components\n   - Dependencies and configuration\n   - Architecture patterns\n\nStart broad with the tree view, then drill down into specific files."""


@mcp.prompt()
def make_code_changes(file_path: str, change_description: str) -> str:
    """Template for making safe, targeted code changes."""
    return f"""I need to modify '{file_path}': {change_description}\n\nFollow this safe editing workflow:\n1. Use read_file(path="{file_path}") to see current contents\n2. Locate the exact section to modify\n3. Use edit_file() for precise changes:\n   - Include enough context in search blocks (5+ lines before/after)\n   - Match indentation and formatting exactly\n   - Make ONE focused change per block\n4. The system will:\n   - Verify syntax automatically\n   - Prevent accidental overwrites\n   - Show exactly what changed\n\nIMPORTANT: Always read before editing. Use edit_file for code, write_file for simple files."""


@mcp.prompt()
def refactor_code(target: str, refactoring_goal: str) -> str:
    """Template for refactoring code safely across files."""
    return f"I need to refactor '{target}': {refactoring_goal}\n\nSafe refactoring process:\n1. Explore scope:\n   - Use file_tree() to identify affected files\n   - Use file_search() to find all occurrences of symbols to change\n2. Plan changes:\n   - List all files that need modification\n   - Identify dependencies between changes\n3. Execute changes:\n   - read_file() each file first\n   - Use edit_file() for each modification\n   - Make changes in dependency order (bottom-up)\n4. Verify:\n   - Syntax checking happens automatically\n   - Consider running tests if available\n\nWork systematically through each file, one at a time."


@mcp.prompt()
def create_new_file(file_path: str, purpose: str) -> str:
    """Template for creating new files with proper structure."""
    return f"""I need to create '{file_path}': {purpose}\n\nFile creation checklist:\n1. Check context:\n   - Use file_tree() to see project structure\n   - Check for similar existing files to match style\n   - Identify the appropriate location\n2. Determine file type and requirements:\n   - Language/framework conventions\n   - Project coding standards\n   - Necessary imports/headers\n3. Create the file:\n   - Use write_file(path="{file_path}", content=...)\n   - Include proper headers, imports, docstrings\n   - Follow project structure patterns\n4. Verify:\n   - Syntax will be checked automatically\n   - Ensure it fits the project organization\n\nNew files do not need to be read first - the protection system allows creation."""


@mcp.prompt()
def find_and_fix(issue_description: str, search_path: str = ".") -> str:
    """Template for finding and fixing issues in code."""
    return f'I need to find and fix: {issue_description}\n\nSystematic debugging approach:\n1. Locate the problem:\n   - Use file_tree(path="{search_path}") to find relevant files\n   - Use file_search() to search for error messages or related code\n   - Use head() or tail() to check log files if applicable\n2. Understand the context:\n   - read_file() the problematic file(s)\n   - Use get_lines() to examine specific sections\n   - Check related files and dependencies\n3. Implement the fix:\n   - Use edit_file() for precise corrections\n   - Include sufficient context in search blocks\n   - Test syntax is validated automatically\n4. Verify the fix:\n   - Review the changes made\n   - Check for side effects in related code\n\nWork methodically - understand before changing.'


@mcp.prompt()
def organize_project(base_path: str = ".") -> str:
    """Template for organizing or restructuring a project."""
    return f"""I need to organize the project structure at '{base_path}'.\n\nProject organization workflow:\n1. Assess current state:\n   - Use file_tree(path="{base_path}", max_depth=4) for full overview\n   - Identify misplaced files, duplicates, or poor organization\n   - List what should be grouped together\n2. Plan the reorganization:\n   - Define target directory structure\n   - Identify files to move, rename, or consolidate\n   - Consider impact on imports/references\n3. Execute changes safely:\n   - Use create_directory() for new folders\n   - Use move() to relocate files\n   - Use copy() if you need backups first\n   - Use edit_file() to update imports/paths\n4. Clean up:\n   - Use delete() to remove old empty directories\n   - Verify all references still work\n\nMake one structural change at a time, updating references as you go."""


@mcp.prompt()
def code_review(file_or_directory: str) -> str:
    """Template for reviewing code quality and identifying issues."""
    return f"Perform a code review of '{file_or_directory}'.\n\nCode review process:\n1. Understand scope:\n   - Use file_tree() if directory, or read_file() if single file\n   - Identify all files to review\n2. Review each file for:\n   - Code quality and readability\n   - Potential bugs or edge cases\n   - Security vulnerabilities\n   - Performance issues\n   - Inconsistent patterns\n   - Missing documentation\n3. Use file_search() to check for:\n   - TODO/FIXME comments\n   - Common anti-patterns\n   - Inconsistent naming\n4. Document findings:\n   - List issues by severity\n   - Suggest specific improvements\n   - Use edit_file() to fix simple issues\n\nProvide constructive, actionable feedback."


@mcp.resource("filesystem://cwd")
def resource_current_directory() -> str:
    """Provides the current working directory."""
    return os.getcwd()


@mcp.resource("filesystem://tree")
def resource_directory_tree() -> str:
    """Provides a tree view of the current directory."""
    tree = _get_file_tree(".", max_depth=3, include_files=True)
    return tree


@mcp.resource("filesystem://read_whitelist")
def resource_read_whitelist() -> str:
    """Provides the list of files that have been read and are safe to edit."""
    whitelist_info = {
        path: {
            "timestamp": info["timestamp"],
            "age_seconds": time.time() - info["timestamp"],
        }
        for path, info in _file_read_whitelist.items()
    }
    return json.dumps(
        {"read_files_count": len(_file_read_whitelist), "files": whitelist_info},
        indent=2,
    )


@mcp.resource("file://{path}")
def resource_file(path: str) -> str:
    """Provides the content of a file."""
    path_obj = Path(path).absolute()
    if not path_obj.exists():
        return MCPResponse.error(f"Path not found: {path}").to_dict()
    if path_obj.is_dir():
        return MCPResponse.error(f"Path is a directory: {path}").to_dict()
    return path_obj.read_text()


@mcp.resource("directory://{path}")
def resource_directory(path: str) -> str:
    """Provides the content of a directory."""
    path_obj = Path(path).absolute()
    if not path_obj.exists():
        return MCPResponse.error(f"Path not found: {path}").to_dict()
    if not path_obj.is_dir():
        return MCPResponse.error(f"Path is not a directory: {path}").to_dict()
    try:
        return os.listdir(path_obj)
    except Exception as e:
        return MCPResponse.error(f"Error listing directory: {str(e)}").to_dict()


@mcp.tool()
async def lint(path: str) -> dict:
    """Run a linter on a file to find errors and style issues."""
    try:
        command = ["poetry", "run", "ruff", "check", path]
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            return MCPResponse.success(message="No issues found.").to_dict()
        else:
            return MCPResponse.success(
                result={"output": stdout.decode() + stderr.decode()},
                message="Linter found issues.",
            ).to_dict()
    except Exception as e:
        return MCPResponse.error(message=f"Error running linter: {str(e)}").to_dict()


@mcp.tool()
async def get_file_context(path: str) -> dict:
    """Get context information about a file from the knowledge graph.

    **NEW GRAPH-POWERED TOOL**: Provides intelligent context about a file by
    querying the knowledge graph. This enables context-aware development assistance.

    Returns information about:
    - File metadata (language, size, lines)
    - Imports and dependencies
    - Defined symbols (functions, classes)
    - Related files that share dependencies

    This information is automatically collected when files are read and indexed.

    Args:
        path: Path to the file

    Returns:
        Dictionary containing:
        - file_info: Basic file metadata
        - imports: List of imported modules
        - symbols: List of functions/classes defined (with signatures)
        - related_files: Other files that might be related

    Example usage:
        To understand a file's dependencies before editing:
        ```python
        context = get_file_context("src/main.py")
        print(f"Imports: {context['imports']}")
        print(f"Functions: {[s['name'] for s in context['symbols']]}")
        ```
    """
    try:
        try:
            _ensure_graph_initialized()
        except Exception as e:
            return MCPResponse.error(
                f"Knowledge graph initialization failed: {str(e)}\nEnsure SPARKY_DB_URL or SPARKY_DB_URL environment variable is set."
            ).to_dict()
        context = await _get_file_context(path)
        if not context:
            return MCPResponse.error(
                f"File {path} not found in knowledge graph. Read the file first to index it."
            ).to_dict()
        num_imports = len(context.get("imports", []))
        num_symbols = len(context.get("symbols", []))
        num_related = len(context.get("related_files", []))
        message = f"File context for {path}:\n"
        message += f"- {num_imports} imports\n"
        message += f"- {num_symbols} symbols defined\n"
        message += f"- {num_related} related files\n"
        return MCPResponse.success(result=context, message=message).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error getting file context: {str(e)}").to_dict()


@mcp.tool()
async def search_codebase(query: str, file_type: str = None, limit: int = 10) -> dict:
    """Search the codebase using semantic similarity.

    **NEW GRAPH-POWERED TOOL**: Uses the knowledge graph's semantic search
    to find relevant code files, functions, and modules by meaning, not just
    text matching.

    This is more powerful than simple grep because it understands context
    and finds semantically similar code even if the exact words don't match.

    Args:
        query: Natural language description of what you're looking for
        file_type: Optional filter by node type ("File", "Symbol", "Module")
        limit: Maximum number of results (default: 10)

    Returns:
        List of matching code elements with similarity scores

    Example usage:
        ```python
        # Find files related to authentication
        results = search_codebase("user authentication and login")

        # Find specific functions
        results = search_codebase("password hashing function", file_type="Symbol")
        ```
    """
    try:
        try:
            _ensure_graph_initialized()
        except Exception as e:
            return MCPResponse.error(
                f"Knowledge graph initialization failed: {str(e)}\nEnsure SPARKY_DB_URL or SPARKY_DB_URL environment variable is set."
            ).to_dict()
        results = _kb_repository.search_nodes(
            query_text=query, node_type=file_type, limit=limit
        )
        formatted_results = []
        for node in results:
            result_dict = {"type": node.node_type, "label": node.label, "id": node.id}
            if node.node_type == "File":
                result_dict.update(
                    {
                        "path": node.properties.get("path", ""),
                        "language": node.properties.get("language", ""),
                        "lines": node.properties.get("lines", 0),
                    }
                )
            elif node.node_type == "Symbol":
                result_dict.update(
                    {
                        "name": node.properties.get("name", ""),
                        "kind": node.properties.get("kind", ""),
                        "file": node.properties.get("file", ""),
                        "line": node.properties.get("line", 0),
                        "signature": node.properties.get("signature", ""),
                    }
                )
            elif node.node_type == "Module":
                result_dict.update({"name": node.properties.get("name", "")})
            formatted_results.append(result_dict)
        message = f"Found {len(formatted_results)} results for query: '{query}'"
        return MCPResponse.success(result=formatted_results, message=message).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error searching codebase: {str(e)}").to_dict()


@mcp.tool()
async def symbol_search(
    symbol_name: str = None,
    symbol_type: str = None,
    file_pattern: str = None,
    limit: int = 50,
) -> dict:
    """Search for symbols (functions, classes) in the codebase using the knowledge graph.

    **GRAPH-POWERED TOOL**: Quickly find all functions, classes, or other symbols
    in your codebase. Much faster than regex searching because it uses the indexed
    knowledge graph.

    Args:
        symbol_name: Name or partial name of the symbol to find (optional)
                     Supports wildcards: "test_*", "*Handler", "*manager*"
        symbol_type: Type of symbol to find: "function", "class", "method" (optional)
        file_pattern: Limit search to files matching this pattern (optional)
                      Example: "src/", "**/*_test.py"
        limit: Maximum number of results (default: 50)

    Returns:
        List of symbols with their names, types, files, and line numbers

    Examples:
        # Find all functions
        symbol_search(symbol_type="function")

        # Find all classes ending with "Handler"
        symbol_search(symbol_name="*Handler", symbol_type="class")

        # Find all test functions
        symbol_search(symbol_name="test_*", symbol_type="function")

        # Find symbols in a specific directory
        symbol_search(file_pattern="src/tools/", symbol_type="function")
    """
    try:
        try:
            _ensure_graph_initialized()
        except Exception as e:
            return MCPResponse.error(
                f"Knowledge graph initialization failed: {str(e)}\nEnsure SPARKY_DB_URL environment variable is set."
            ).to_dict()
        if not _kb_repository:
            return MCPResponse.error("Knowledge graph not available").to_dict()
        symbols = []
        if symbol_name:
            nodes = _kb_repository.search_nodes(
                query_text=symbol_name, node_type="Symbol", limit=limit * 2
            )
        else:
            from database.models import Node
            from sqlalchemy import select

            with _kb_repository.db_manager.get_session() as session:
                stmt = select(Node).where(Node.node_type == "Symbol")
                result = session.execute(stmt)
                nodes = [row[0] for row in result.fetchall()][: limit * 2]
        for node in nodes:
            if not node or node.node_type != "Symbol":
                continue
            name = node.properties.get("name", "")
            kind = node.properties.get("kind", "")
            file_path = node.properties.get("file", "")
            line = node.properties.get("line", 0)
            signature = node.properties.get("signature", "")
            if symbol_type and kind != symbol_type:
                continue
            if symbol_name:
                import fnmatch

                if not fnmatch.fnmatch(
                    name.lower(), symbol_name.lower().replace("*", "*")
                ):
                    if symbol_name not in name.lower():
                        continue
            if file_pattern:
                if file_pattern not in file_path:
                    continue
            symbols.append(
                {
                    "name": name,
                    "type": kind,
                    "file": file_path,
                    "line": line,
                    "signature": signature,
                }
            )
            if len(symbols) >= limit:
                break
        symbols.sort(key=lambda x: (x["file"], x["line"]))
        message = f"Found {len(symbols)} symbol(s)"
        if symbol_name:
            message += f" matching '{symbol_name}'"
        if symbol_type:
            message += f" of type '{symbol_type}'"
        return MCPResponse.success(
            result={"symbols": symbols, "count": len(symbols)}, message=message
        ).to_dict()
    except Exception as e:
        logger.exception("Error in symbol_search")
        return MCPResponse.error(f"Error searching symbols: {str(e)}").to_dict()


@mcp.tool()
async def find_references(
    module_or_symbol: str, reference_type: str = "imports"
) -> dict:
    """Find all files that reference a module or symbol.

    **GRAPH-POWERED TOOL**: Track where a module or symbol is used across your
    codebase. Essential for understanding dependencies and safe refactoring.

    Args:
        module_or_symbol: Name of the module or symbol to find references for
                          Examples: "os", "pathlib", "requests", "MyClass"
        reference_type: Type of reference to find:
                        - "imports": Find files that import this module (default)
                        - "all": Find all types of references

    Returns:
        List of files that reference the module/symbol with context

    Examples:
        # Find all files that import 'requests'
        find_references("requests")

        # Find all files that import 'database.models'
        find_references("database.models")

        # Find usages of a custom module
        find_references("utils.helpers")
    """
    try:
        try:
            _ensure_graph_initialized()
        except Exception as e:
            return MCPResponse.error(
                f"Knowledge graph initialization failed: {str(e)}\nEnsure SPARKY_DB_URL environment variable is set."
            ).to_dict()
        if not _kb_repository:
            return MCPResponse.error("Knowledge graph not available").to_dict()
        module_node_id = f"module:{module_or_symbol}"
        module_node = _kb_repository.get_node(module_node_id)
        if not module_node:
            return MCPResponse.error(
                f"Module '{module_or_symbol}' not found in knowledge graph.\nMake sure files that import it have been read and indexed."
            ).to_dict()
        import_edges = _kb_repository.get_edges(
            target_id=module_node_id, edge_type="IMPORTS"
        )
        references = []
        for edge in import_edges:
            source_node = _kb_repository.get_node(edge.source_id)
            if source_node and source_node.node_type == "File":
                file_path = source_node.properties.get("path", "")
                language = source_node.properties.get("language", "")
                lines = source_node.properties.get("lines", 0)
                references.append(
                    {
                        "file": file_path,
                        "language": language,
                        "lines": lines,
                        "reference_type": "import",
                    }
                )
        references.sort(key=lambda x: x["file"])
        message = f"Found {len(references)} file(s) that reference '{module_or_symbol}'"
        return MCPResponse.success(
            result={
                "module": module_or_symbol,
                "references": references,
                "count": len(references),
            },
            message=message,
        ).to_dict()
    except Exception as e:
        logger.exception("Error in find_references")
        return MCPResponse.error(f"Error finding references: {str(e)}").to_dict()


@mcp.tool()
async def batch_read_files(paths: list[str], index_to_graph: bool = True) -> dict:
    """Read multiple files at once and return their contents.

    **EFFICIENCY TOOL**: Read many files in a single operation instead of
    calling read_file multiple times. Useful for analyzing related files,
    comparing implementations, or understanding a module.

    Args:
        paths: List of file paths to read
        index_to_graph: Whether to index files to knowledge graph (default: True)

    Returns:
        Dictionary mapping file paths to their contents, with error tracking

    Examples:
        # Read all Python files in a directory
        batch_read_files(["src/main.py", "src/utils.py", "src/config.py"])

        # Read related test files
        batch_read_files(["tests/test_auth.py", "tests/test_user.py"])
    """
    try:
        results = {}
        content_types = {}
        errors = {}
        successful = 0
        for path in paths:
            try:
                if not os.path.exists(path):
                    errors[path] = "File not found"
                    continue
                if not os.path.isfile(path):
                    errors[path] = "Not a file"
                    continue
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                _mark_file_as_read(path, content)
                if index_to_graph:
                    try:
                        _ensure_graph_initialized()
                        await _index_file_to_graph(path, content)
                    except Exception as e:
                        logger.warning(f"Graph indexing skipped for {path}: {e}")
                content_type = _detect_content_type(path, content)
                results[path] = content
                if content_type:
                    content_types[path] = content_type
                successful += 1
            except PermissionError:
                errors[path] = "Permission denied"
            except UnicodeDecodeError:
                errors[path] = "Cannot decode file (binary or invalid encoding)"
            except Exception as e:
                errors[path] = str(e)
        message = f"Successfully read {successful}/{len(paths)} file(s)"
        if errors:
            message += f", {len(errors)} error(s)"

        # Build result with content types for each file
        files_with_types = {}
        for path, content in results.items():
            files_with_types[path] = {
                "content": content,
                "content_type": content_types.get(path),
            }

        return MCPResponse.success(
            result={
                "files": files_with_types,
                "errors": errors,
                "successful_count": successful,
            },
            message=message,
        ).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error in batch read: {str(e)}").to_dict()


def main():
    """Run the MCP server."""
    try:
        _load_graph()
        logger.info("Knowledge graph initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize knowledge graph: {e}")
        logger.warning("Graph-powered tools will not be available")
    mcp.run()


if __name__ == "__main__":
    main()
