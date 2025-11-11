# Sparky Testing Guide

## Overview

This directory contains unit tests for the Sparky project servers and components.

## Running Tests

### Run all tests
```bash
poetry run python -m unittest discover tests -v
```

### Run specific test file
```bash
poetry run python -m unittest tests.test_advanced_networking_server -v
```

### Run specific test class
```bash
poetry run python -m unittest tests.test_advanced_networking_server.TestAdvancedNetworkingServer -v
```

### Run specific test method
```bash
poetry run python -m unittest tests.test_advanced_networking_server.TestAdvancedNetworkingServer.test_whois_info_success -v
```

## Test Coverage

### advanced_networking

**Status:** ✅ All 18 tests passing

The `test_advanced_networking_server.py` file provides comprehensive coverage for the advanced networking tool:

#### Functions Tested:
- **whois_info** - 3 tests
  - Success case with parsed data
  - Failure case (non-zero return code)
  - Exception handling

- **dns_records** - 3 tests  
  - Success case with A, MX, TXT, NS records
  - Missing dnspython dependency
  - Partial failures (some records succeed, others fail)

- **enumerate_subdomains** - 2 tests
  - Success case with found subdomains
  - Missing dnspython dependency

- **ip_info** - 3 tests
  - Success case with geolocation data
  - Missing requests dependency
  - Socket exception handling

- **web_stack** - 3 tests
  - Success case with technology detection
  - Missing requests dependency
  - HTTP exception handling

- **call_tool** - 3 tests
  - domain_investigate tool success
  - Missing domain argument validation
  - Unknown tool handling

- **list_tools** - 1 test
  - Tool definition validation

#### Test Strategy:
- Uses `unittest.IsolatedAsyncioTestCase` for async test support
- Comprehensive mocking of external dependencies (dns, requests, socket, subprocess)
- Tests both success and failure paths
- Validates error handling for missing dependencies
- Ensures proper JSON serialization and MCP protocol compliance

## Adding New Tests

When adding tests for other servers, follow this pattern:

1. Create a new test file: `tests/test_<server_name>.py`
2. Use `unittest.IsolatedAsyncioTestCase` for async functions
3. Mock external dependencies comprehensively
4. Test both success and failure paths
5. Validate error messages and return types
6. Ensure MCP protocol compliance (TextContent type="text")

### Example Test Structure:

```python
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import json
from mcp.types import TextContent


class TestYourServer(unittest.IsolatedAsyncioTestCase):
    """Test suite for your_server.py"""

    async def test_function_success(self):
        """Test successful operation"""
        from src.tools.your_tool import your_function
        
        # Setup mocks
        # ...
        
        # Execute
        result = await your_function("test_input")
        
        # Assert
        self.assertEqual(result["key"], "expected_value")

    async def test_function_error_handling(self):
        """Test error handling"""
        from src.tools.your_tool import your_function
        
        # Execute
        result = await your_function("invalid_input")
        
        # Assert
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
```

## Continuous Integration

Consider adding these tests to a CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: poetry run python -m unittest discover tests -v
```

## Next Steps

Consider adding tests for:
- `network`
- `memory`
- `git_tool`
- `filesystem`
- `shell`
- `code`
- `linter`
- Other tools in `src/tools/`

Each tool should aim for similar comprehensive coverage as `advanced_networking`.

