# Utility Tools MCP Server

Consolidated utility tools server providing comprehensive general-purpose functionality.

## Available Tools (54 total)

### Mathematical Operations (23 tools)
- **add, subtract, multiply, divide** - Basic arithmetic
- **power** - Exponentiation
- **sqrt** - Square root
- **log, log2, log10** - Logarithms (natural, base-2, base-10)
- **sin, cos, tan** - Trigonometric functions
- **sinh, cosh, tanh** - Hyperbolic functions
- **asin, acos, atan** - Inverse trigonometric functions
- **abs_value** - Absolute value
- **ceil, floor** - Rounding functions
- **factorial** - Factorial calculation

### String Manipulation (7 tools)
- **concatenate_strings** - Join strings with separator
- **split_string** - Split by delimiter
- **replace_string** - Replace substrings
- **substring** - Extract substring
- **to_lower, to_upper** - Case conversion
- **strip_whitespace** - Trim whitespace

### Encoding/Decoding (2 tools)
- **base64_encode** - Encode to Base64
- **base64_decode** - Decode from Base64

### JSON Operations (2 tools)
- **json_parse** - Parse JSON string to object
- **json_stringify** - Convert object to JSON string

### List/Dict Operations (0 tools - temporarily disabled)
~~These tools are temporarily disabled due to FastMCP JSON schema generation limitations with Gemini API. FastMCP doesn't generate the required `items` field for `List[Any]` and `Dict[str, Any]` parameters that Gemini validates.~~
- ~~get_list_item~~ - Get item by index
- ~~set_list_item~~ - Set item at index
- ~~append_to_list~~ - Append item
- ~~get_dict_value~~ - Get dict value by key
- ~~set_dict_value~~ - Set dict value by key

### Date & Time Operations (16 tools)
- **get_current_datetime** - Get current date and time (ISO format)
- **get_current_date** - Get current date only
- **get_current_time** - Get current time only
- **get_current_timestamp** - Get Unix timestamp
- **format_datetime** - Format datetime with custom format codes
- **parse_datetime** - Parse datetime from string (auto-detects common formats)
- **datetime_difference** - Calculate time difference (seconds, minutes, hours, days, weeks)
- **datetime_add** - Add time to a datetime
- **datetime_subtract** - Subtract time from a datetime
- **datetime_to_timezone** - Convert datetime to different timezone
- **datetime_is_weekend** - Check if datetime is weekend (Sat/Sun)
- **datetime_is_weekday** - Check if datetime is weekday (Mon-Fri)
- **datetime_get_weekday** - Get day name (Monday, Tuesday, etc.)
- **datetime_is_leap_year** - Check if year is a leap year
- **datetime_days_in_month** - Get number of days in a month

## Dependencies

- **math** - Standard library for mathematical operations
- **base64** - Standard library for encoding/decoding
- **json** - Standard library for JSON operations
- **datetime** - Standard library for date/time operations

## Datetime Format Notes

Most datetime tools accept ISO format strings (e.g., `"2024-01-15T14:30:00"`). The `parse_datetime` tool can auto-detect common formats:
- ISO format: `2024-01-15T14:30:00`
- YYYY-MM-DD HH:MM:SS: `2024-01-15 14:30:00`
- YYYY-MM-DD: `2024-01-15`
- US format: `01/15/2024`
- European format: `15-01-2024`

Timezone format for `datetime_to_timezone`: `+HH:MM` or `-HH:MM` (e.g., `+05:30` for IST, `-08:00` for PST)

## History

This server was consolidated from multiple separate servers:
- `calculator/server.py` - Mathematical operations (consolidated Nov 12, 2025)
- `strings/server.py` - String manipulation (consolidated Nov 12, 2025)
- `encryption/server.py` - Encoding/decoding (consolidated Nov 12, 2025)
- Datetime tools from `knowledge_graph/server.py` (moved Nov 12, 2025)

Consolidation provides better performance with fewer MCP server processes.
