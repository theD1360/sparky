"""Test script for the new quick-win features.

This script demonstrates and tests:
1. Regex search in file_search
2. symbol_search
3. find_references
4. batch_read_files
"""

import asyncio
import json
from server import (
    file_search,
    symbol_search,
    find_references,
    batch_read_files,
)


async def test_regex_search():
    """Test regex search functionality."""
    print("\n" + "=" * 70)
    print("TEST 1: Regex Search in file_search")
    print("=" * 70)

    # Test 1: Find function definitions
    print("\n1. Finding function definitions with regex:")
    result = file_search(
        pattern="server.py",
        query=r"def \w+\(",
        use_regex=True,
        max_results=5,
    )
    print(f"Status: {result.get('is_error', False) == False}")
    if not result.get("is_error"):
        print(f"Found {result['result']['total_matches']} matches")
        for match in result["result"]["matches"][:3]:
            print(f"  Line {match['line']}: {match['content'][:60]}...")

    # Test 2: Find async functions
    print("\n2. Finding async functions:")
    result = file_search(
        pattern="server.py",
        query=r"async def \w+",
        use_regex=True,
        max_results=5,
    )
    print(f"Status: {result.get('is_error', False) == False}")
    if not result.get("is_error"):
        print(f"Found {result['result']['total_matches']} async functions")

    # Test 3: Find decorators
    print("\n3. Finding decorators:")
    result = file_search(
        pattern="server.py",
        query=r"@\w+\.",
        use_regex=True,
        max_results=10,
    )
    print(f"Status: {result.get('is_error', False) == False}")
    if not result.get("is_error"):
        print(f"Found {result['result']['total_matches']} decorators")


async def test_symbol_search():
    """Test symbol search functionality."""
    print("\n" + "=" * 70)
    print("TEST 2: Symbol Search")
    print("=" * 70)

    # Note: This requires the knowledge graph to be initialized and populated
    print("\n1. Searching for all functions:")
    result = await symbol_search(symbol_type="function", limit=5)
    print(f"Status: {result.get('is_error', False) == False}")
    if not result.get("is_error"):
        symbols = result["result"]["symbols"]
        print(f"Found {len(symbols)} functions")
        for symbol in symbols[:3]:
            print(f"  {symbol['name']} in {symbol['file']} at line {symbol['line']}")
    else:
        print(f"Note: {result.get('message', 'Graph may not be initialized')}")

    # Test 2: Search with wildcard
    print("\n2. Searching for functions starting with '_':")
    result = await symbol_search(symbol_name="_*", symbol_type="function", limit=5)
    print(f"Status: {result.get('is_error', False) == False}")
    if not result.get("is_error"):
        symbols = result["result"]["symbols"]
        print(f"Found {len(symbols)} matching symbols")
    else:
        print(f"Note: {result.get('message', 'Graph may not be initialized')}")


async def test_find_references():
    """Test find_references functionality."""
    print("\n" + "=" * 70)
    print("TEST 3: Find References")
    print("=" * 70)

    # Test finding references to common modules
    modules_to_test = ["os", "pathlib", "asyncio"]

    for module in modules_to_test:
        print(f"\n1. Finding references to '{module}':")
        result = await find_references(module)
        print(f"Status: {result.get('is_error', False) == False}")
        if not result.get("is_error"):
            refs = result["result"]["references"]
            print(f"Found {len(refs)} files importing '{module}'")
            for ref in refs[:3]:
                print(f"  {ref['file']}")
        else:
            print(f"Note: {result.get('message', 'Graph may not be initialized')}")
        break  # Only test one module to avoid too much output


async def test_batch_read():
    """Test batch_read_files functionality."""
    print("\n" + "=" * 70)
    print("TEST 4: Batch Read Files")
    print("=" * 70)

    # Try to read multiple files at once
    files_to_read = [
        "server.py",
        "test_quick_wins.py",
        "QUICK_WINS_DEMO.md",
        "nonexistent_file.txt",  # This should fail gracefully
    ]

    print("\n1. Reading multiple files at once:")
    result = await batch_read_files(files_to_read, index_to_graph=False)
    print(f"Status: {result.get('is_error', False) == False}")

    if not result.get("is_error"):
        data = result["result"]
        print(f"Successfully read: {data['successful_count']}/{len(files_to_read)} files")
        print(f"Files read: {list(data['files'].keys())}")
        print(f"Errors: {data['errors']}")

        # Show size of each file read
        for path, content in data["files"].items():
            print(f"  {path}: {len(content)} bytes")


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("TESTING NEW QUICK-WIN FEATURES")
    print("=" * 70)

    try:
        await test_regex_search()
    except Exception as e:
        print(f"Error in regex search test: {e}")

    try:
        await test_symbol_search()
    except Exception as e:
        print(f"Error in symbol search test: {e}")

    try:
        await test_find_references()
    except Exception as e:
        print(f"Error in find_references test: {e}")

    try:
        await test_batch_read()
    except Exception as e:
        print(f"Error in batch_read test: {e}")

    print("\n" + "=" * 70)
    print("TESTS COMPLETE")
    print("=" * 70)
    print("\nNote: Some tests may show errors if the knowledge graph is not initialized.")
    print("This is expected behavior. The graph-powered tools require SPARKY_DB_URL to be set.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())

