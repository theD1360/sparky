# Code Tools Server

Guarded code editing, Python execution, lint, and graph-powered code intelligence.

Plain filesystem browsing and git are provided by third-party MCP servers:

- **filesystem** — `@modelcontextprotocol/server-filesystem`
- **git** — `mcp-server-git`

With `SPARKY_MCP_TOOL_NAME_PREFIX=true` (default in Docker), tool names are prefixed
by server (`code_read_file`, `filesystem_list_directory`, `git_git_status`, etc.).

## Kept tools (this server)

- `execute` — sandboxed/unsandboxed Python
- `read_file` / `write_file` / `append_file` / `edit_file` — edit guards + graph indexing
- `lint` — ruff
- `get_file_context`, `search_codebase`, `symbol_search`, `find_references`
- `batch_read_files`

## Docs

See `docs/` for quick wins and graph integration plans.
