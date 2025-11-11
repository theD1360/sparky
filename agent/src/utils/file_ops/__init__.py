"""File operations module with advanced search-replace editing capabilities.

This module provides sophisticated file editing tools ported from wcgw,
including:
- Search-replace block editing with tolerance matching
- Intelligent indentation fixing
- Syntax validation
- Multiple match detection and error reporting
"""

from .diff_edit import (
    FileEditInput,
    FileEditOutput,
    SearchReplaceMatchError,
    Tolerance,
    TolerancesHit,
)
from .search_replace import (
    SearchReplaceSyntaxError,
    search_replace_edit,
)

__all__ = [
    "FileEditInput",
    "FileEditOutput",
    "SearchReplaceMatchError",
    "SearchReplaceSyntaxError",
    "Tolerance",
    "TolerancesHit",
    "search_replace_edit",
]

