"""Standard response format for MCP tools to ensure consistent serialization."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from models.enums import ResponseStatus


class PaginationMetadata(BaseModel):
    """Pagination metadata for paginated responses."""

    offset: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")
    total_count: int = Field(..., description="Total number of items available")
    returned_count: int = Field(..., description="Actual number of items returned")
    has_more: bool = Field(..., description="Whether more items are available")


class MCPResponse(BaseModel):
    """Standardized response format for MCP tools.

    This ensures consistent serialization across all MCP tools and avoids
    issues with FastMCP's handling of lists and complex types.

    Attributes:
        status: Response status (success, error, or empty)
        message: Optional human-readable message
        result: The actual result data (can be any JSON-serializable type)
        content_type: Optional content type for frontend display (e.g., 'python', 'json', 'javascript')
        pagination: Optional pagination metadata for paginated responses
    """

    status: ResponseStatus = Field(..., description="Response status")
    message: Optional[str] = Field(None, description="Optional human-readable message")
    result: Any = Field(default=None, description="The actual result data")
    content_type: Optional[str] = Field(
        None, description="Content type for frontend display (e.g., 'python', 'json', 'javascript'). Defaults to 'text' if not specified."
    )
    pagination: Optional[PaginationMetadata] = Field(
        None, description="Optional pagination metadata"
    )

    @classmethod
    def success(
        cls,
        result: Any = None,
        message: Optional[str] = None,
        content_type: Optional[str] = None,
        pagination: Optional[PaginationMetadata] = None,
    ) -> "MCPResponse":
        """Create a success response."""
        return cls(
            status=ResponseStatus.SUCCESS,
            result=result,
            message=message,
            content_type=content_type,
            pagination=pagination,
        )

    @classmethod
    def paginated_success(
        cls,
        result: Any,
        offset: int,
        limit: int,
        total_count: int,
        message: Optional[str] = None,
    ) -> "MCPResponse":
        """Create a paginated success response.

        Args:
            result: The result data (should be a list)
            offset: Number of items skipped
            limit: Maximum number of items requested
            total_count: Total number of items available
            message: Optional message

        Returns:
            MCPResponse with pagination metadata
        """
        # Calculate returned count from result
        returned_count = len(result) if isinstance(result, list) else 0
        has_more = (offset + returned_count) < total_count

        pagination = PaginationMetadata(
            offset=offset,
            limit=limit,
            total_count=total_count,
            returned_count=returned_count,
            has_more=has_more,
        )

        return cls(
            status=ResponseStatus.SUCCESS,
            result=result,
            message=message,
            pagination=pagination,
        )

    @classmethod
    def error(cls, message: str, result: Any = None) -> "MCPResponse":
        """Create an error response."""
        return cls(status=ResponseStatus.ERROR, message=message, result=result)

    @classmethod
    def empty(cls, message: Optional[str] = None) -> "MCPResponse":
        """Create an empty response."""
        return cls(status=ResponseStatus.EMPTY, message=message, result=None)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns a plain dict with enum values converted to strings.
        """
        # Directly build dict to avoid Pydantic serialization quirks
        status_str = (
            self.status.value if hasattr(self.status, "value") else str(self.status)
        )
        response_dict = {
            "status": status_str,
            "message": self.message,
            "result": self.result,
        }

        # Add content_type (always include, defaults to "text")
        response_dict["content_type"] = self.content_type or "text"

        # Add pagination if present
        if self.pagination:
            response_dict["pagination"] = {
                "offset": self.pagination.offset,
                "limit": self.pagination.limit,
                "total_count": self.pagination.total_count,
                "returned_count": self.pagination.returned_count,
                "has_more": self.pagination.has_more,
            }

        return response_dict
