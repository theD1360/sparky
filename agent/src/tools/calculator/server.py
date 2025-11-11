from __future__ import annotations

import math

from mcp.server.fastmcp import FastMCP

from models import MCPResponse

mcp = FastMCP("calculator-tools")


@mcp.tool()
def add(a: float, b: float) -> dict:
    """Adds two numbers."""
    return MCPResponse.success(result=a + b).to_dict()


@mcp.tool()
def subtract(a: float, b: float) -> dict:
    """Subtracts two numbers."""
    return MCPResponse.success(result=a - b).to_dict()


@mcp.tool()
def multiply(a: float, b: float) -> dict:
    """Multiplies two numbers."""
    return MCPResponse.success(result=a * b).to_dict()


@mcp.tool()
def divide(a: float, b: float) -> dict:
    """Divides two numbers."""
    if b == 0:
        return MCPResponse.error("Cannot divide by zero").to_dict()
    return MCPResponse.success(result=a / b).to_dict()


@mcp.tool()
def power(base: float, exponent: float) -> dict:
    """Raises a number to a power."""
    return MCPResponse.success(result=base**exponent).to_dict()


@mcp.tool()
def sqrt(number: float) -> dict:
    """Calculates the square root of a number."""
    if number < 0:
        return MCPResponse.error(
            "Cannot calculate the square root of a negative number"
        ).to_dict()
    return MCPResponse.success(result=math.sqrt(number)).to_dict()


@mcp.tool()
def log(number: float) -> dict:
    """Calculates the natural logarithm of a number."""
    if number <= 0:
        return MCPResponse.error(
            "Cannot calculate the logarithm of a non-positive number"
        ).to_dict()
    return MCPResponse.success(result=math.log(number)).to_dict()


@mcp.tool()
def log2(number: float) -> dict:
    """Calculates the base-2 logarithm of a number."""
    if number <= 0:
        return MCPResponse.error(
            "Cannot calculate the logarithm of a non-positive number"
        ).to_dict()
    return MCPResponse.success(result=math.log2(number)).to_dict()


@mcp.tool()
def log10(number: float) -> dict:
    """Calculates the base-10 logarithm of a number."""
    if number <= 0:
        return MCPResponse.error(
            "Cannot calculate the logarithm of a non-positive number"
        ).to_dict()
    return MCPResponse.success(result=math.log10(number)).to_dict()


@mcp.tool()
def sin(number: float) -> dict:
    """Calculates the sine of a number in radians."""
    return MCPResponse.success(result=math.sin(number)).to_dict()


@mcp.tool()
def cos(number: float) -> dict:
    """Calculates the cosine of a number in radians."""
    return MCPResponse.success(result=math.cos(number)).to_dict()


@mcp.tool()
def tan(number: float) -> dict:
    """Calculates the tangent of a number in radians."""
    return MCPResponse.success(result=math.tan(number)).to_dict()


@mcp.tool()
def sinh(number: float) -> dict:
    """Calculates the hyperbolic sine of a number."""
    return MCPResponse.success(result=math.sinh(number)).to_dict()


@mcp.tool()
def cosh(number: float) -> dict:
    """Calculates the hyperbolic cosine of a number."""
    return MCPResponse.success(result=math.cosh(number)).to_dict()


@mcp.tool()
def tanh(number: float) -> dict:
    """Calculates the hyperbolic tangent of a number."""
    return MCPResponse.success(result=math.tanh(number)).to_dict()


@mcp.tool()
def asin(number: float) -> dict:
    """Calculates the inverse sine of a number."""
    if not -1 <= number <= 1:
        return MCPResponse.error("Input must be between -1 and 1 for asin").to_dict()
    return MCPResponse.success(result=math.asin(number)).to_dict()


@mcp.tool()
def acos(number: float) -> dict:
    """Calculates the inverse cosine of a number."""
    if not -1 <= number <= 1:
        return MCPResponse.error("Input must be between -1 and 1 for acos").to_dict()
    return MCPResponse.success(result=math.acos(number)).to_dict()


@mcp.tool()
def atan(number: float) -> dict:
    """Calculates the inverse tangent of a number."""
    return MCPResponse.success(result=math.atan(number)).to_dict()


@mcp.tool()
def abs(number: float) -> dict:
    """Calculates the absolute value of a number."""
    return MCPResponse.success(result=math.fabs(number)).to_dict()


@mcp.tool()
def ceil(number: float) -> dict:
    """Rounds a number up to the nearest integer."""
    return MCPResponse.success(result=math.ceil(number)).to_dict()


@mcp.tool()
def floor(number: float) -> dict:
    """Rounds a number down to the nearest integer."""
    return MCPResponse.success(result=math.floor(number)).to_dict()


@mcp.tool()
def factorial(number: int) -> dict:
    """Calculates the factorial of a non-negative integer."""
    if number < 0:
        return MCPResponse.error(
            "Cannot calculate the factorial of a negative number"
        ).to_dict()
    return MCPResponse.success(result=math.factorial(number)).to_dict()


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
