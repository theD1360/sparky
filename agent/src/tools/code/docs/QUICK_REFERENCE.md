# Quick Reference Card: New Features

## 🚀 One-Page Cheat Sheet

---

### 1. Regex Search (Enhanced file_search)

```python
# Find function definitions
file_search("**/*.py", r"def \w+\(", use_regex=True)

# Find async functions
file_search("**/*.py", r"async def", use_regex=True)

# Find TODO/FIXME comments
file_search("**/*.py", r"#.*(TODO|FIXME)", use_regex=True)

# Find classes
file_search("**/*.py", r"class \w+", use_regex=True)
```

**Key Parameters:**
- `pattern`: File glob (e.g., `"**/*.py"`)
- `query`: Text or regex pattern
- `use_regex`: Set to `True` for regex
- `case_sensitive`: Default `True`
- `max_results`: Default `100`

---

### 2. Symbol Search (NEW)

```python
# Find all functions
symbol_search(symbol_type="function")

# Find test functions
symbol_search(symbol_name="test_*", symbol_type="function")

# Find handler classes
symbol_search(symbol_name="*Handler", symbol_type="class")

# Find symbols in specific directory
symbol_search(file_pattern="src/tools/", symbol_type="function")
```

**Key Parameters:**
- `symbol_name`: Name with wildcards (e.g., `"test_*"`)
- `symbol_type`: `"function"`, `"class"`, or `"method"`
- `file_pattern`: Directory filter
- `limit`: Max results (default `50`)

---

### 3. Find References (NEW)

```python
# Find where requests is imported
find_references("requests")

# Find internal module usage
find_references("database.models")

# Find standard library usage
find_references("asyncio")
```

**Key Parameters:**
- `module_or_symbol`: Module name to find
- `reference_type`: `"imports"` (default)

**Returns:**
- List of files importing the module
- File paths and metadata

---

### 4. Batch Read Files (NEW)

```python
# Read multiple related files
batch_read_files([
    "src/auth/login.py",
    "src/auth/logout.py",
    "src/auth/register.py"
])

# Read test files
batch_read_files([
    "tests/test_auth.py",
    "tests/test_user.py"
])
```

**Key Parameters:**
- `paths`: List of file paths
- `index_to_graph`: Auto-index (default `True`)

**Returns:**
- `files`: Dict of path → content
- `errors`: Dict of path → error
- `successful_count`: Number of files read

---

## 🎯 Common Workflows

### Workflow 1: Before Refactoring
```python
# 1. Find all references
refs = find_references("module_to_change")

# 2. Load all affected files
files = [r["file"] for r in refs["references"]]
batch_read_files(files)

# 3. Proceed with confidence!
```

### Workflow 2: Find All Tests
```python
# Find all test functions
tests = symbol_search(
    symbol_name="test_*",
    symbol_type="function",
    file_pattern="tests/"
)
```

### Workflow 3: Code Quality Check
```python
# Find all TODOs
file_search("**/*.py", r"#.*TODO", use_regex=True)

# Find complex functions
file_search("**/*.py", r"def \w+\([^)]{100,}\)", use_regex=True)
```

---

## ⚡ Quick Tips

### Symbol Search
- ✅ Use wildcards for flexible matching
- ✅ Combine filters for precision
- ✅ Lightning fast (uses graph index)

### Find References
- ✅ Always check before refactoring
- ✅ Great for dependency analysis
- ✅ Requires files to be indexed (read first)

### Regex Search
- ✅ Use raw strings: `r"pattern"`
- ✅ Test on small file sets first
- ✅ Escape special chars: `\(`, `\)`, `\.`

### Batch Read
- ✅ More efficient than multiple reads
- ✅ Auto-indexes to knowledge graph
- ✅ Continues on individual errors

---

## 🔧 Setup Requirements

### For Basic Features (Regex Search)
- No setup needed ✅

### For Graph Features (Symbol Search, Find References)
- Set `SPARKY_DB_URL` environment variable
- Files must be indexed (happens on `read_file`)

---

## 📊 When to Use Each Tool

| Tool | Use When You Need To... |
|------|------------------------|
| **Regex Search** | Find complex patterns, syntax structures |
| **Symbol Search** | Find functions/classes by name quickly |
| **Find References** | See where a module is used (refactoring) |
| **Batch Read** | Load multiple related files at once |

---

## 🐛 Troubleshooting

### "Knowledge graph not available"
→ Set `SPARKY_DB_URL` environment variable

### "Module not found in graph"
→ Read files first to index them: `read_file(path)`

### "Invalid regex pattern"
→ Check regex syntax, escape special chars

### Empty results
→ Files may not be indexed yet, or pattern doesn't match

---

## 📖 More Information

- **Full Guide**: See `QUICK_WINS_DEMO.md`
- **Implementation**: See `IMPLEMENTATION_SUMMARY.md`
- **Tests**: Run `python test_quick_wins.py`

---

**Quick Start**: Try this!
```python
# Find all async functions in your codebase
file_search("**/*.py", r"async def \w+", use_regex=True)
```

