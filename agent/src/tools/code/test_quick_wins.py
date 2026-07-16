"""Test script for remaining code-server quick-win features.

Demonstrates:
1. symbol_search
2. find_references
3. batch_read_files
4. edit_file syntax error reporting

Plain filesystem search (file_search) now lives on the official filesystem MCP.
"""

import asyncio
from server import (
    batch_read_files,
    edit_file,
    find_references,
    symbol_search,
    write_file,
)


async def test_symbol_search():
    """Test symbol search functionality."""
    print("\n" + "=" * 70)
    print("TEST 1: Symbol Search")
    print("=" * 70)

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
    print("TEST 2: Find References")
    print("=" * 70)

    print("\n1. Finding references to 'os':")
    result = await find_references("os")
    print(f"Status: {result.get('is_error', False) == False}")
    if not result.get("is_error"):
        refs = result["result"]["references"]
        print(f"Found {len(refs)} files importing 'os'")
        for ref in refs[:3]:
            print(f"  {ref['file']}")
    else:
        print(f"Note: {result.get('message', 'Graph may not be initialized')}")


async def test_batch_read():
    """Test batch_read_files functionality."""
    print("\n" + "=" * 70)
    print("TEST 3: Batch Read Files")
    print("=" * 70)

    files_to_read = [
        "server.py",
        "test_quick_wins.py",
        "nonexistent_file.txt",
    ]

    print("\n1. Reading multiple files at once:")
    result = await batch_read_files(files_to_read, index_to_graph=False)
    print(f"Status: {result.get('is_error', False) == False}")

    if not result.get("is_error"):
        data = result["result"]
        print(
            f"Successfully read: {data['successful_count']}/{len(files_to_read)} files"
        )
        print(f"Files read: {list(data['files'].keys())}")
        print(f"Errors: {data['errors']}")
        for path, content in data["files"].items():
            print(f"  {path}: {len(content)} bytes")


async def test_edit_file_syntax_error():
    """Test edit_file syntax error reporting."""
    print("\n" + "=" * 70)
    print("TEST 4: Edit File Syntax Error")
    print("=" * 70)

    print("\n1. Testing syntax error reporting:")
    file_path = "/tmp/test_edit_file.py"
    error_code = 'def test():\n  print("hello") # Intentional syntax error'

    create_file_result = await write_file(path=file_path, content=error_code)
    print(f"Status of test file creation {create_file_result.get('status')}")
    if create_file_result.get("status") != "success":
        return

    edits = (
        "\n<<<<<<< SEARCH\n"
        'def test():\n  print("hello") # Intentional syntax error\n'
        "=======\n"
        'print("fixed")\n'
        ">>>>>>> REPLACE\n"
    )

    result = await edit_file(path=file_path, edits=edits)

    print(f"Status: {result.get('is_error', False) == False}")
    if result.get("is_error"):
        print(f"Error Message: {result.get('message')}")
    else:
        print("Edit was unexpectedly successful")


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("TESTING CODE SERVER FEATURES")
    print("=" * 70)

    for name, fn in (
        ("symbol search", test_symbol_search),
        ("find_references", test_find_references),
        ("batch_read", test_batch_read),
        ("edit file syntax error", test_edit_file_syntax_error),
    ):
        try:
            await fn()
        except Exception as e:
            print(f"Error in {name} test: {e}")

    print("\n" + "=" * 70)
    print("TESTS COMPLETE")
    print("=" * 70)
    print(
        "\nNote: Some tests may show errors if the knowledge graph is not initialized."
    )


if __name__ == "__main__":
    asyncio.run(run_all_tests())
