"""Miscellaneous MCP server providing comprehensive utility tools.

This server consolidates various utility functions including:
- Mathematical operations (calculator)
- String manipulation
- Encoding/decoding (base64)
- JSON operations
- List/dict operations
- Sandboxed Python code execution

Notes on run_code safety:
- Only language="python" is supported.
- We parse the code with ast and block Import/ImportFrom, Attribute access to dunder names,
  and calls to "__import__" or other dunder-named objects.
- Execution happens with extremely limited builtins (len, range, min, max, sum, any, all, list, dict, set, tuple, enumerate).
- Code length is limited and result is captured as last expression value if possible; stdout is also captured.
- This is a best-effort sandbox and not suitable for running untrusted code in hostile environments.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import ast
import base64
import io
import json
import math
import subprocess
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP
from models import MCPResponse

mcp = FastMCP("utility-tools")


# ============================================================================
# MATHEMATICAL OPERATIONS
# ============================================================================


@mcp.tool()
def add(a: float, b: float) -> dict:
    """Add two numbers."""
    return MCPResponse.success(result=a + b).to_dict()


@mcp.tool()
def subtract(a: float, b: float) -> dict:
    """Subtract two numbers."""
    return MCPResponse.success(result=a - b).to_dict()


@mcp.tool()
def multiply(a: float, b: float) -> dict:
    """Multiply two numbers."""
    return MCPResponse.success(result=a * b).to_dict()


@mcp.tool()
def divide(a: float, b: float) -> dict:
    """Divide two numbers."""
    if b == 0:
        return MCPResponse.error("Cannot divide by zero").to_dict()
    return MCPResponse.success(result=a / b).to_dict()


@mcp.tool()
def power(base: float, exponent: float) -> dict:
    """Raise a number to a power."""
    return MCPResponse.success(result=base**exponent).to_dict()


@mcp.tool()
def sqrt(number: float) -> dict:
    """Calculate the square root of a number."""
    if number < 0:
        return MCPResponse.error(
            "Cannot calculate the square root of a negative number"
        ).to_dict()
    return MCPResponse.success(result=math.sqrt(number)).to_dict()


@mcp.tool()
def log(number: float) -> dict:
    """Calculate the natural logarithm of a number."""
    if number <= 0:
        return MCPResponse.error(
            "Cannot calculate the logarithm of a non-positive number"
        ).to_dict()
    return MCPResponse.success(result=math.log(number)).to_dict()


@mcp.tool()
def log2(number: float) -> dict:
    """Calculate the base-2 logarithm of a number."""
    if number <= 0:
        return MCPResponse.error(
            "Cannot calculate the logarithm of a non-positive number"
        ).to_dict()
    return MCPResponse.success(result=math.log2(number)).to_dict()


@mcp.tool()
def log10(number: float) -> dict:
    """Calculate the base-10 logarithm of a number."""
    if number <= 0:
        return MCPResponse.error(
            "Cannot calculate the logarithm of a non-positive number"
        ).to_dict()
    return MCPResponse.success(result=math.log10(number)).to_dict()


@mcp.tool()
def sin(number: float) -> dict:
    """Calculate the sine of a number in radians."""
    return MCPResponse.success(result=math.sin(number)).to_dict()


@mcp.tool()
def cos(number: float) -> dict:
    """Calculate the cosine of a number in radians."""
    return MCPResponse.success(result=math.cos(number)).to_dict()


@mcp.tool()
def tan(number: float) -> dict:
    """Calculate the tangent of a number in radians."""
    return MCPResponse.success(result=math.tan(number)).to_dict()


@mcp.tool()
def sinh(number: float) -> dict:
    """Calculate the hyperbolic sine of a number."""
    return MCPResponse.success(result=math.sinh(number)).to_dict()


@mcp.tool()
def cosh(number: float) -> dict:
    """Calculate the hyperbolic cosine of a number."""
    return MCPResponse.success(result=math.cosh(number)).to_dict()


@mcp.tool()
def tanh(number: float) -> dict:
    """Calculate the hyperbolic tangent of a number."""
    return MCPResponse.success(result=math.tanh(number)).to_dict()


@mcp.tool()
def asin(number: float) -> dict:
    """Calculate the inverse sine of a number."""
    if not -1 <= number <= 1:
        return MCPResponse.error("Input must be between -1 and 1 for asin").to_dict()
    return MCPResponse.success(result=math.asin(number)).to_dict()


@mcp.tool()
def acos(number: float) -> dict:
    """Calculate the inverse cosine of a number."""
    if not -1 <= number <= 1:
        return MCPResponse.error("Input must be between -1 and 1 for acos").to_dict()
    return MCPResponse.success(result=math.acos(number)).to_dict()


@mcp.tool()
def atan(number: float) -> dict:
    """Calculate the inverse tangent of a number."""
    return MCPResponse.success(result=math.atan(number)).to_dict()


@mcp.tool()
def abs_value(number: float) -> dict:
    """Calculate the absolute value of a number."""
    return MCPResponse.success(result=math.fabs(number)).to_dict()


@mcp.tool()
def ceil(number: float) -> dict:
    """Round a number up to the nearest integer."""
    return MCPResponse.success(result=math.ceil(number)).to_dict()


@mcp.tool()
def floor(number: float) -> dict:
    """Round a number down to the nearest integer."""
    return MCPResponse.success(result=math.floor(number)).to_dict()


@mcp.tool()
def factorial(number: int) -> dict:
    """Calculate the factorial of a non-negative integer."""
    if number < 0:
        return MCPResponse.error(
            "Cannot calculate the factorial of a negative number"
        ).to_dict()
    return MCPResponse.success(result=math.factorial(number)).to_dict()


# ============================================================================
# STRING MANIPULATION
# ============================================================================


@mcp.tool()
def concatenate_strings(strings: List[str], separator: str = "") -> dict:
    """Join a list of strings into one string."""
    try:
        result = separator.join(strings)
        return MCPResponse.success(result=result).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def split_string(text: str, delimiter: str, maxsplit: int = -1) -> dict:
    """Split text by a delimiter."""
    try:
        parts = text.split(delimiter, maxsplit if maxsplit >= 0 else -1)
        return MCPResponse.success(result=parts).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def replace_string(text: str, old: str, new: str, count: int = -1) -> dict:
    """Replace occurrences of a substring with another substring."""
    try:
        result = text.replace(old, new, count if count >= 0 else text.count(old))
        return MCPResponse.success(result=result).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def substring(text: str, start: int, end: int = None) -> dict:
    """Extract a substring from start (inclusive) to end (exclusive)."""
    try:
        result = text[start:end]
        return MCPResponse.success(result=result).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def to_lower(text: str) -> dict:
    """Convert text to lowercase."""
    return MCPResponse.success(result=text.lower()).to_dict()


@mcp.tool()
def to_upper(text: str) -> dict:
    """Convert text to uppercase."""
    return MCPResponse.success(result=text.upper()).to_dict()


@mcp.tool()
def strip_whitespace(text: str) -> dict:
    """Strip leading and trailing whitespace."""
    return MCPResponse.success(result=text.strip()).to_dict()


# ============================================================================
# ENCODING/DECODING
# ============================================================================


@mcp.tool()
async def base64_encode(data: str, encoding: str = "utf-8") -> dict:
    """Encode a string to Base64."""
    try:
        input_bytes = data.encode(encoding)
        encoded_bytes = base64.b64encode(input_bytes)
        encoded_string = encoded_bytes.decode(encoding)
        return MCPResponse.success(result={"encoded_string": encoded_string}).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Encoding error: {e}").to_dict()


@mcp.tool()
async def base64_decode(data: str, encoding: str = "utf-8") -> dict:
    """Decode a Base64 string."""
    try:
        input_bytes = data.encode(encoding)
        decoded_bytes = base64.b64decode(input_bytes)
        decoded_string = decoded_bytes.decode(encoding)
        return MCPResponse.success(result={"decoded_string": decoded_string}).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Decoding error: {e}").to_dict()


# ============================================================================
# JSON OPERATIONS
# ============================================================================


@mcp.tool()
def json_parse(json_string: str) -> dict:
    """Parse a JSON string into a Python object (dict or list)."""
    try:
        parsed_data = json.loads(json_string)
        return MCPResponse.success(result=parsed_data).to_dict()
    except json.JSONDecodeError as e:
        return MCPResponse.error(f"Invalid JSON string: {e}").to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def json_stringify(data: Any) -> dict:
    """Convert a Python object (dict/list) to a JSON string."""
    try:
        json_string = json.dumps(data)
        return MCPResponse.success(result=json_string).to_dict()
    except TypeError as e:
        return MCPResponse.error(f"Object is not JSON serializable: {e}").to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


# ============================================================================
# LIST/DICT OPERATIONS
# ============================================================================
# NOTE: These tools are temporarily disabled due to JSON schema generation issues
# with Gemini API. FastMCP's automatic schema generation for List[Any] and Dict[str, Any]
# doesn't include the required 'items' field that Gemini validates.
# TODO: Re-enable once we can provide explicit JSON schemas or FastMCP is updated.

# @mcp.tool()
# def get_list_item(list_obj: List[Any], index: int) -> dict:
#     """Retrieve an item from a list by index."""
#     try:
#         item = list_obj[index]
#         return MCPResponse.success(result=item).to_dict()
#     except IndexError:
#         return MCPResponse.error(f"Index {index} out of range").to_dict()
#     except Exception as e:
#         return MCPResponse.error(str(e)).to_dict()


# @mcp.tool()
# def set_list_item(list_obj: List[Any], index: int, value: Any) -> dict:
#     """Set a list item at a specific index."""
#     try:
#         list_obj[index] = value
#         return MCPResponse.success(result=list_obj).to_dict()
#     except IndexError:
#         return MCPResponse.error(f"Index {index} out of range").to_dict()
#     except Exception as e:
#         return MCPResponse.error(str(e)).to_dict()


# @mcp.tool()
# def append_to_list(list_obj: List[Any], item: Any) -> dict:
#     """Append an item to a list."""
#     try:
#         list_obj.append(item)
#         return MCPResponse.success(result=list_obj).to_dict()
#     except Exception as e:
#         return MCPResponse.error(str(e)).to_dict()


# @mcp.tool()
# def get_dict_value(dict_obj: Dict[str, Any], key: str) -> dict:
#     """Get a value from a dict by key."""
#     try:
#         value = dict_obj.get(key)
#         return MCPResponse.success(result=value).to_dict()
#     except Exception as e:
#         return MCPResponse.error(str(e)).to_dict()


# @mcp.tool()
# def set_dict_value(dict_obj: Dict[str, Any], key: str, value: Any) -> dict:
#     """Set or update a value in a dict by key."""
#     try:
#         dict_obj[key] = value
#         return MCPResponse.success(result=dict_obj).to_dict()
#     except Exception as e:
#         return MCPResponse.error(str(e)).to_dict()


# ============================================================================
# DATETIME OPERATIONS
# ============================================================================


@mcp.tool()
def get_current_datetime() -> dict:
    """Get the current date and time in ISO format."""
    return MCPResponse.success(result=datetime.now().isoformat()).to_dict()


@mcp.tool()
def get_current_date() -> dict:
    """Get the current date (without time) in ISO format."""
    return MCPResponse.success(result=datetime.now().date().isoformat()).to_dict()


@mcp.tool()
def get_current_time() -> dict:
    """Get the current time (without date) in ISO format."""
    return MCPResponse.success(result=datetime.now().time().isoformat()).to_dict()


@mcp.tool()
def get_current_timestamp() -> dict:
    """Get the current Unix timestamp (seconds since epoch)."""
    return MCPResponse.success(result=datetime.now().timestamp()).to_dict()


@mcp.tool()
def format_datetime(
    datetime_str: str,
    input_format: str = None,
    output_format: str = "%Y-%m-%d %H:%M:%S",
) -> dict:
    """Format a datetime string using format codes. If input_format is not provided, assumes ISO format."""
    try:
        if input_format:
            dt = datetime.strptime(datetime_str, input_format)
        else:
            dt = datetime.fromisoformat(datetime_str)
        return MCPResponse.success(result=dt.strftime(output_format)).to_dict()
    except ValueError as e:
        return MCPResponse.error(f"Invalid datetime format: {e}").to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def parse_datetime(datetime_str: str, format_string: str = None) -> dict:
    """Parse a datetime string and return it in ISO format. If format_string is not provided, tries common formats."""
    try:
        if format_string:
            dt = datetime.strptime(datetime_str, format_string)
        else:
            # Try common formats
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d",
                "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y",
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y",
            ]
            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(datetime_str, fmt)
                    break
                except ValueError:
                    continue
            if dt is None:
                # Try ISO format as last resort
                dt = datetime.fromisoformat(datetime_str)

        return MCPResponse.success(result=dt.isoformat()).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Could not parse datetime: {e}").to_dict()


@mcp.tool()
def datetime_difference(datetime1: str, datetime2: str, unit: str = "seconds") -> dict:
    """Calculate the difference between two datetimes. Unit can be: seconds, minutes, hours, days, weeks."""
    try:
        dt1 = datetime.fromisoformat(datetime1)
        dt2 = datetime.fromisoformat(datetime2)
        diff = abs((dt1 - dt2).total_seconds())

        if unit == "seconds":
            result = diff
        elif unit == "minutes":
            result = diff / 60
        elif unit == "hours":
            result = diff / 3600
        elif unit == "days":
            result = diff / 86400
        elif unit == "weeks":
            result = diff / 604800
        else:
            return MCPResponse.error(
                f"Invalid unit: {unit}. Use: seconds, minutes, hours, days, weeks"
            ).to_dict()

        return MCPResponse.success(result=result).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def datetime_add(
    datetime_str: str, days: int = 0, hours: int = 0, minutes: int = 0, seconds: int = 0
) -> dict:
    """Add time to a datetime. Provide days, hours, minutes, and/or seconds to add."""
    try:
        dt = datetime.fromisoformat(datetime_str)
        new_dt = dt + timedelta(
            days=days, hours=hours, minutes=minutes, seconds=seconds
        )
        return MCPResponse.success(result=new_dt.isoformat()).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def datetime_subtract(
    datetime_str: str, days: int = 0, hours: int = 0, minutes: int = 0, seconds: int = 0
) -> dict:
    """Subtract time from a datetime. Provide days, hours, minutes, and/or seconds to subtract."""
    try:
        dt = datetime.fromisoformat(datetime_str)
        new_dt = dt - timedelta(
            days=days, hours=hours, minutes=minutes, seconds=seconds
        )
        return MCPResponse.success(result=new_dt.isoformat()).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def datetime_to_timezone(datetime_str: str, target_timezone: str) -> dict:
    """Convert a datetime to a different timezone. timezone format: '+HH:MM' or '-HH:MM' (e.g., '+05:30', '-08:00')."""
    try:
        dt = datetime.fromisoformat(datetime_str)

        # Parse target timezone offset
        if not target_timezone.startswith(("+", "-")):
            return MCPResponse.error(
                "Timezone must be in format '+HH:MM' or '-HH:MM'"
            ).to_dict()

        sign = 1 if target_timezone[0] == "+" else -1
        parts = target_timezone[1:].split(":")
        offset_hours = int(parts[0])
        offset_minutes = int(parts[1]) if len(parts) > 1 else 0

        target_tz = timezone(
            timedelta(hours=sign * offset_hours, minutes=sign * offset_minutes)
        )

        # If datetime is naive, assume it's UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        new_dt = dt.astimezone(target_tz)
        return MCPResponse.success(result=new_dt.isoformat()).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def datetime_is_weekend(datetime_str: str) -> dict:
    """Check if a datetime falls on a weekend (Saturday or Sunday)."""
    try:
        dt = datetime.fromisoformat(datetime_str)
        is_weekend = dt.weekday() in [5, 6]  # 5=Saturday, 6=Sunday
        return MCPResponse.success(result=is_weekend).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def datetime_is_weekday(datetime_str: str) -> dict:
    """Check if a datetime falls on a weekday (Monday-Friday)."""
    try:
        dt = datetime.fromisoformat(datetime_str)
        is_weekday = dt.weekday() not in [5, 6]
        return MCPResponse.success(result=is_weekday).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def datetime_get_weekday(datetime_str: str) -> dict:
    """Get the day of the week for a datetime. Returns: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday."""
    try:
        dt = datetime.fromisoformat(datetime_str)
        weekdays = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        return MCPResponse.success(result=weekdays[dt.weekday()]).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def datetime_is_leap_year(year: int) -> dict:
    """Check if a year is a leap year."""
    try:
        is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
        return MCPResponse.success(result=is_leap).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
def datetime_days_in_month(year: int, month: int) -> dict:
    """Get the number of days in a specific month of a year."""
    try:
        if month < 1 or month > 12:
            return MCPResponse.error("Month must be between 1 and 12").to_dict()

        # Days in each month (non-leap year)
        days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

        # Check for leap year in February
        if month == 2:
            is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
            return MCPResponse.success(result=29 if is_leap else 28).to_dict()

        return MCPResponse.success(result=days[month - 1]).to_dict()
    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
