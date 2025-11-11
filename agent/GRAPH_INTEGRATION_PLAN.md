# Knowledge Graph Integration Plan for Code Tools

## Overview

This document outlines the strategy for integrating the knowledge graph into the consolidated code tools server to create an incredibly powerful, context-aware development assistant.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Code Tools Server                        │
│  (File Ops + Git + Code Exec + Editing + Linting)          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Knowledge Graph Layer                       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Code       │  │   Project    │  │   Developer  │     │
│  │   Context    │  │   Structure  │  │   Patterns   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Symbol      │  │  Dependencies│  │   Test       │     │
│  │  Relations   │  │   & Imports  │  │   Coverage   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               PostgreSQL + Knowledge Repository              │
└─────────────────────────────────────────────────────────────┘
```

## Integration Points

### 1. File Read Operations Enhancement

**Current State:**
```python
@mcp.tool()
def read_file(path: str) -> dict:
    # Reads file and marks as safe to edit
    content = f.read()
    _mark_file_as_read(path, content)
    return MCPResponse.success(result=content).to_dict()
```

**Enhanced with Graph:**
```python
@mcp.tool()
def read_file(path: str) -> dict:
    content = f.read()
    _mark_file_as_read(path, content)
    
    # GRAPH ENHANCEMENT: Store file metadata and extract code structure
    if _kb_repository:
        await _index_file_to_graph(path, content)
    
    # GRAPH ENHANCEMENT: Get relevant context
    context = await _get_file_context(path)
    
    return MCPResponse.success(
        result={
            "content": content,
            "context": context,  # Related files, dependencies, recent changes
            "suggestions": await _get_suggestions_for_file(path)
        }
    ).to_dict()
```

### 2. Code Editing with Context Awareness

**Current State:**
```python
@mcp.tool()
async def search_replace_edit_file(path: str, search_replace_blocks: str) -> dict:
    # Performs search-replace with syntax validation
    edited_content, comments = search_replace_edit(lines, original_content, log_fn)
    # Check syntax
    syntax_errors = _check_syntax(extension, edited_content)
```

**Enhanced with Graph:**
```python
@mcp.tool()
async def search_replace_edit_file(path: str, search_replace_blocks: str) -> dict:
    # GRAPH ENHANCEMENT: Pre-edit analysis
    impact_analysis = await _analyze_edit_impact(path, search_replace_blocks)
    
    edited_content, comments = search_replace_edit(lines, original_content, log_fn)
    syntax_errors = _check_syntax(extension, edited_content)
    
    # GRAPH ENHANCEMENT: Update symbol relationships
    await _update_code_graph(path, original_content, edited_content)
    
    # GRAPH ENHANCEMENT: Check for affected files
    affected_files = await _find_dependent_files(path)
    
    return MCPResponse.success(
        result={
            "path": path,
            "warnings": warnings,
            "affected_files": affected_files,
            "suggested_updates": await _suggest_related_edits(path, edited_content)
        }
    ).to_dict()
```

### 3. Git Operations with Learning

**Enhanced:**
```python
@mcp.tool()
async def git_commit(message: str) -> dict:
    result = await _run_shell_command(["git", "commit", "-m", message])
    
    # GRAPH ENHANCEMENT: Learn from commit patterns
    if result["exit_code"] == 0:
        await _learn_commit_patterns(message, changed_files)
    
    return MCPResponse.success(result=result).to_dict()
```

### 4. Intelligent Code Suggestions

**New Tool:**
```python
@mcp.tool()
async def get_code_suggestions(path: str, cursor_position: dict = None) -> dict:
    """Get context-aware code suggestions from the knowledge graph.
    
    Args:
        path: File path
        cursor_position: Optional dict with 'line' and 'column'
    
    Returns:
        - Similar code patterns from codebase
        - Common next steps based on project patterns
        - Related functions/classes
        - Potential refactoring opportunities
    """
    suggestions = await _kb_repository.query_code_context(
        file_path=path,
        cursor_pos=cursor_position
    )
    
    return MCPResponse.success(result=suggestions).to_dict()
```

### 5. Semantic Code Search

**New Tool:**
```python
@mcp.tool()
async def semantic_code_search(query: str, scope: str = None) -> dict:
    """Search code by meaning, not just text matching.
    
    Uses knowledge graph to find:
    - Similar implementations
    - Related functionality
    - Usage examples
    - API patterns
    """
    results = await _kb_repository.semantic_search(
        query=query,
        scope=scope,
        search_type="code"
    )
    
    return MCPResponse.success(result=results).to_dict()
```

### 6. Refactoring Assistant

**New Tool:**
```python
@mcp.tool()
async def suggest_refactoring(path: str, target: str = None) -> dict:
    """Analyze code and suggest refactoring opportunities.
    
    Graph-based analysis identifies:
    - Code duplication
    - Complex functions that could be simplified
    - Dead code
    - Circular dependencies
    - Inconsistent patterns
    """
    analysis = await _analyze_code_quality(path)
    suggestions = await _generate_refactoring_suggestions(analysis)
    
    return MCPResponse.success(
        result={
            "quality_score": analysis.score,
            "issues": analysis.issues,
            "suggestions": suggestions
        }
    ).to_dict()
```

## Graph Schema Design

### Node Types

```python
# File Node
{
    "type": "file",
    "path": str,
    "language": str,
    "size": int,
    "last_modified": timestamp,
    "hash": str
}

# Symbol Node (function, class, variable)
{
    "type": "symbol",
    "name": str,
    "kind": str,  # function, class, method, variable
    "file": str,
    "line_start": int,
    "line_end": int,
    "signature": str
}

# Commit Node
{
    "type": "commit",
    "hash": str,
    "message": str,
    "author": str,
    "timestamp": timestamp,
    "files_changed": list[str]
}

# Pattern Node
{
    "type": "pattern",
    "name": str,
    "description": str,
    "usage_count": int,
    "examples": list[str]
}
```

### Relationship Types

```python
# CONTAINS: file -> symbol
# IMPORTS: file -> file
# CALLS: symbol -> symbol
# EXTENDS: class -> class
# IMPLEMENTS: class -> interface
# DEPENDS_ON: file -> file
# MODIFIED_IN: file -> commit
# SIMILAR_TO: pattern -> pattern
# TESTS: file -> file
```

## Implementation Phases

### Phase 1: Basic Graph Integration ✅ COMPLETE
- ✅ Database connection already in place
- ✅ Implement file indexing on read operations
- ✅ Store basic file metadata in graph
- ✅ Track file relationships (imports)
- ✅ Extract Python symbols (functions, classes)
- ✅ Create graph-powered tools (get_file_context, search_codebase)

**What was implemented:**
- `_index_file_to_graph()`: Automatically indexes files when read
- `_index_python_file_structure()`: Parses Python AST to extract symbols
- `_get_file_context()`: Queries graph for file context
- `read_file()`: Enhanced to automatically index files
- `get_file_context()`: New MCP tool for querying file context
- `search_codebase()`: New MCP tool for semantic search

### Phase 2: Symbol Tracking (Week 2)
- [ ] Parse Python files to extract symbols
- [ ] Store function/class definitions in graph
- [ ] Track symbol relationships (calls, inheritance)
- [ ] Build symbol index for fast lookup

### Phase 3: Context-Aware Reading (Week 3)
- [ ] Enhance `read_file` to return related context
- [ ] Implement `get_file_context()` helper
- [ ] Show related files and dependencies
- [ ] Display recent changes and history

### Phase 4: Impact Analysis (Week 4)
- [ ] Analyze edit impact before changes
- [ ] Track dependent files
- [ ] Suggest related edits
- [ ] Warn about breaking changes

### Phase 5: Learning & Patterns (Week 5)
- [ ] Learn from commit patterns
- [ ] Identify common code patterns
- [ ] Build pattern library
- [ ] Suggest patterns during editing

### Phase 6: Advanced Features (Week 6+)
- [ ] Semantic code search
- [ ] Refactoring suggestions
- [ ] Test coverage tracking
- [ ] Code quality metrics
- [ ] Intelligent code completion

## Helper Functions to Implement

```python
async def _index_file_to_graph(path: str, content: str) -> None:
    """Parse file and store structure in graph."""
    pass

async def _get_file_context(path: str) -> dict:
    """Get related files, dependencies, recent changes."""
    pass

async def _get_suggestions_for_file(path: str) -> list:
    """Get context-aware suggestions for file."""
    pass

async def _analyze_edit_impact(path: str, changes: str) -> dict:
    """Analyze what will be affected by an edit."""
    pass

async def _update_code_graph(path: str, old_content: str, new_content: str) -> None:
    """Update graph based on code changes."""
    pass

async def _find_dependent_files(path: str) -> list[str]:
    """Find files that depend on this file."""
    pass

async def _suggest_related_edits(path: str, content: str) -> list:
    """Suggest edits to related files."""
    pass

async def _learn_commit_patterns(message: str, files: list[str]) -> None:
    """Learn from commit to improve future suggestions."""
    pass

async def _analyze_code_quality(path: str) -> dict:
    """Analyze code quality using graph data."""
    pass
```

## Configuration

```python
# Add to server.py

GRAPH_CONFIG = {
    "enable_indexing": True,
    "enable_suggestions": True,
    "enable_learning": True,
    "max_context_files": 10,
    "max_suggestions": 5,
    "index_on_read": True,
    "index_on_write": True,
}
```

## Testing Strategy

1. **Unit Tests**: Test each graph operation independently
2. **Integration Tests**: Test tool + graph interactions
3. **Performance Tests**: Ensure graph queries are fast (<100ms)
4. **Accuracy Tests**: Verify suggestions are relevant
5. **Learning Tests**: Verify pattern learning works

## Success Metrics

- **Context Relevance**: >80% of suggested related files are actually relevant
- **Suggestion Quality**: >70% of code suggestions are helpful
- **Performance**: <100ms for context queries
- **Pattern Recognition**: Identifies >90% of duplicate code patterns
- **Impact Analysis**: Catches >95% of breaking changes before commit

## Resources Needed

- PostgreSQL database (already configured)
- AST parsers for target languages (Python ast module available)
- Tree-sitter for multi-language support (future)
- Graph query optimization

---

**Next Action**: Begin Phase 1 - Basic Graph Integration

