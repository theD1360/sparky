# Tool Fixes Summary

**Date:** November 13, 2025  
**Status:** ✅ All Issues Resolved

## Overview

Fixed 4 critical tool issues affecting the agent's functionality. All tools are now working correctly.

---

## 1. ✅ find_similar_nodes - Missing pgvector Dependency

### Problem
- **Error:** `'Node' object has no attribute 'embedding'`
- **Root Cause:** The `pgvector` library was not in the project dependencies, causing:
  1. `PGVECTOR_AVAILABLE` flag to be `False`
  2. `embedding` column never added to the `Node` SQLAlchemy model
  3. Code attempting to access `ref_node.embedding` failing with AttributeError

### Solution
1. **Added pgvector to dependencies** (`pyproject.toml`):
   ```toml
   "pgvector (>=0.3.0,<0.4.0)",
   ```

2. **Updated Node model** (`database/models.py`):
   ```python
   try:
       from pgvector.sqlalchemy import Vector
       PGVECTOR_AVAILABLE = True
   except ImportError:
       PGVECTOR_AVAILABLE = False
   
   # In Node class:
   if PGVECTOR_AVAILABLE:
       embedding = Column(Vector(768), nullable=True)
   ```

3. **Added safety check** in `repository.py`:
   ```python
   if not hasattr(ref_node, 'embedding') or not ref_node.embedding:
       raise ValueError(f"Node {node_id} has no embedding")
   ```

### Verification
```bash
✓ PGVECTOR_AVAILABLE: True
✓ Node has embedding attr: True
```

---

## 2. ✅ symbol_search - Incorrect Session Access

### Problem
- **Error:** `'KnowledgeRepository' object has no attribute 'session'`
- **Root Cause:** Code tried to access `_kb_repository.session.execute()`, but `KnowledgeRepository` uses a database manager with context-managed sessions, not a direct session attribute.

### Solution
Changed from direct session access to proper context manager pattern in `tools/code/server.py`:

```python
# Before:
stmt = select(Node).where(Node.node_type == "Symbol")
result = _kb_repository.session.execute(stmt)
nodes = [row[0] for row in result.fetchall()][: limit * 2]

# After:
with _kb_repository.db_manager.get_session() as session:
    stmt = select(Node).where(Node.node_type == "Symbol")
    result = session.execute(stmt)
    nodes = [row[0] for row in result.fetchall()][: limit * 2]
```

---

## 3. ✅ edit_file & git_status - TaskGroup Errors (Syntax Error)

### Problem
- **Error:** `unhandled errors in a TaskGroup (1 sub-exception)`
- **Root Cause:** Critical syntax error in `database/repository.py` line 571:
  ```python
  SyntaxError: 'await' outside async function
  ```
  This prevented the entire database module from importing, causing all tools that depend on it to fail.

### Detailed Analysis
The `_generate_and_store_embedding()` method was incorrectly marked as `async`:

```python
async def _generate_and_store_embedding(self, session, node: Node, ...):
    # ... synchronous code ...
    embedding = embedding_manager.embed_text(combined_text)  # Synchronous!
```

But was called with `await` from the synchronous `add_node()` method:

```python
def add_node(self, ...):
    # ...
    await self._generate_and_store_embedding(session, node)  # ❌ await in non-async function
```

### Solution
Removed the `async` keyword from `_generate_and_store_embedding()` since it performs no async operations:

```python
# Before:
async def _generate_and_store_embedding(self, session, node: Node, ...):
    ...

# After:
def _generate_and_store_embedding(self, session, node: Node, ...):
    ...
```

Also removed all `await` keywords when calling this method.

### Why This Fixed TaskGroup Errors
The TaskGroup errors were symptoms of the underlying import failure. When tools tried to use the knowledge graph (which most do), Python couldn't import `database.repository` due to the syntax error. The MCP framework wrapped these import errors in TaskGroup exceptions.

Now:
- ✅ All database modules import successfully
- ✅ `edit_file` works without import errors
- ✅ `git_status` executes properly
- ✅ All knowledge graph tools function correctly

---

## Files Modified

1. **`pyproject.toml`**
   - Added `pgvector (>=0.3.0,<0.4.0)` dependency

2. **`src/database/models.py`**
   - Added pgvector import with fallback
   - Added conditional `embedding` column to `Node` model

3. **`src/database/repository.py`**
   - Changed `_generate_and_store_embedding` from async to sync
   - Removed `await` keywords when calling the method
   - Added `hasattr` check for embedding attribute

4. **`src/tools/code/server.py`**
   - Fixed `symbol_search` to use proper session context manager

---

## Testing Results

### Before Fixes
- ❌ `find_similar_nodes`: AttributeError
- ❌ `symbol_search`: AttributeError
- ❌ `edit_file`: TaskGroup error
- ❌ `git_status`: TaskGroup error

### After Fixes
- ✅ `find_similar_nodes`: Working (embedding column available)
- ✅ `symbol_search`: Working (correct session access)
- ✅ `edit_file`: Working (imports succeed)
- ✅ `git_status`: Working (imports succeed)

---

## Installation Note

After pulling these changes, run:

```bash
poetry install
```

This will install the newly added `pgvector` dependency.

---

## Additional Notes

### For SQLite Users
The system works with both SQLite and PostgreSQL:
- **SQLite**: Uses `sqlite-vec` virtual table for embeddings (no pgvector needed)
- **PostgreSQL**: Uses `pgvector` extension for embeddings

The code automatically detects which database is in use and handles embeddings accordingly.

### Embedding Generation
Embeddings are generated automatically when nodes are created or updated via the `_generate_and_store_embedding()` method. This is a synchronous operation that:
1. Combines node type, label, and content
2. Calls the Gemini embedding API
3. Stores the embedding in the appropriate location (nodes_vec for SQLite, nodes.embedding for PostgreSQL)

---

## Conclusion

All four tool issues have been resolved through:
1. Adding missing dependency (`pgvector`)
2. Fixing incorrect session access pattern
3. Correcting async/sync function mismatches
4. Adding defensive programming checks

The agent should now have full access to all tools without errors.

