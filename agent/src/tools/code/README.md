# Code Tools Server

Consolidated code tools MCP server with filesystem, git, code execution, editing, and graph-powered intelligence.

## 📁 Documentation Structure

### 📚 `/docs` - Completed Work & User Guides

Documentation for currently implemented features:

- **README_QUICK_WINS.md** - Overview of quick win features implemented
- **QUICK_WINS_DEMO.md** - Complete user guide with examples and workflows
- **QUICK_REFERENCE.md** - One-page cheat sheet for new features
- **IMPLEMENTATION_SUMMARY.md** - Technical implementation details and statistics

**Start here for:** Learning how to use the current tools

---

### 🗺️ `/plans` - Future Roadmaps & Integration Plans

Planning documents for future enhancements:

- **README_GRAPH_INTEGRATION.md** - Overview & navigation guide (start here)
- **GRAPH_INTEGRATION_SUMMARY.md** - Executive summary of opportunities (5 min read)
- **GRAPH_INTEGRATION_ROADMAP.md** - Complete integration roadmap (15 min read)
- **GRAPH_METHOD_MAPPING.md** - Developer reference with code templates

**Start here for:** Understanding integration opportunities and planning next steps

---

## 🚀 Quick Start

### Using Current Features

See the docs:
```bash
cd docs
cat QUICK_REFERENCE.md  # Quick syntax reference
```

### Planning Next Features

See the plans:
```bash
cd plans
cat GRAPH_INTEGRATION_SUMMARY.md  # 5-minute overview
```

---

## ✨ Current Features (Implemented)

### 1. Enhanced Search
- ✅ **Regex search** - Advanced pattern matching in `file_search`
- ✅ **Symbol search** - Find functions/classes by name with wildcards
- ✅ **Reference finder** - Track where modules are used

### 2. Batch Operations
- ✅ **Batch file reading** - Read multiple files efficiently

### 3. File Operations
- ✅ Read, write, edit, append files
- ✅ File search with glob patterns
- ✅ Directory operations
- ✅ File protection system

### 4. Git Tools
- ✅ Status, diff, log, show, branch
- ✅ Add, commit, checkout

### 5. Graph-Powered Intelligence
- ✅ Automatic file indexing
- ✅ Semantic code search
- ✅ File context retrieval
- ✅ Symbol tracking
- ✅ Import relationship tracking

---

## 🔮 Future Opportunities (Planned)

85% of graph capabilities currently unused! Available features include:

### Dependency Analysis
- 🎯 Dependency path finding
- 🎯 Circular dependency detection
- 🎯 Impact analysis
- 🎯 Influence ranking (PageRank)

### Code Quality
- 🎯 Dead code detection
- 🎯 Duplicate code finder
- 🎯 Health checks
- 🎯 Code clustering

### Architecture
- 🎯 Architecture visualization
- 🎯 Component analysis
- 🎯 Subgraph extraction

**See `plans/` for detailed roadmap**

---

## 📊 Statistics

### Current Implementation
- **Tools**: 30+ tools available
- **Graph Usage**: 15% of available capabilities
- **Documentation**: 8 comprehensive guides
- **Test Coverage**: Test suite included

### Potential
- **Untapped Methods**: 40+ graph methods unused
- **Quick Wins**: 10+ tools ready in <20 hours
- **Expected ROI**: 10x productivity boost

---

## 🛠️ Development

### Running the Server
```bash
poetry run python server.py
```

### Running Tests
```bash
poetry run python test_quick_wins.py
```

### Adding New Tools
1. See `plans/GRAPH_METHOD_MAPPING.md` for templates
2. Use existing tools as examples
3. Follow FastMCP decorator pattern
4. Add tests to `test_quick_wins.py`

---

## 📚 Key Files

- **server.py** - Main MCP server implementation
- **test_quick_wins.py** - Test suite
- **docs/** - User documentation
- **plans/** - Future roadmaps

---

## 🎯 Next Steps

### To Learn Current Features
1. Read `docs/QUICK_REFERENCE.md` (5 min)
2. Try examples from `docs/QUICK_WINS_DEMO.md`

### To Plan Next Features
1. Read `plans/GRAPH_INTEGRATION_SUMMARY.md` (5 min)
2. Review `plans/GRAPH_INTEGRATION_ROADMAP.md` (15 min)
3. Choose: Quick Wins, Dependency Suite, or Health Dashboard

---

## 🔗 Related

- **Knowledge Graph**: `../../database/repository.py`
- **Models**: `../../database/models.py`
- **Embeddings**: `../../database/embeddings.py`

---

**Status**: Production Ready ✅  
**Version**: 1.0 (Quick Wins Complete)  
**Next**: Graph Integration Phase 2

