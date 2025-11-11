# Tolerant File Editing

This module provides the core logic for the `search_replace_edit_file` tool. It implements a sophisticated search-and-replace algorithm that is tolerant to common variations in code, such as whitespace and indentation differences. This makes it far more robust than a simple string replacement.

**Location:** `src/utils/file_ops/diff_edit.py`

## Core Concepts

*   **Search-Replace Blocks:** The primary input is a list of search-and-replace blocks. The algorithm processes these blocks sequentially, attempting to find each "search" block in the file and replace it with the corresponding "replace" block.
*   **Tolerances:** The system uses a multi-layered tolerance system to find matches even when the text isn't identical.
    *   **Level 1 (Exact Match):** First, it attempts a perfect, character-for-character match.
    *   **Level 2 (Whitespace Tolerance):** If that fails, it tries matching again after stripping trailing whitespace, then leading whitespace (indentation).
    *   **Level 3 (Max Space Tolerance):** As a last resort, it will try matching after removing *all* whitespace from both the source and search lines.
*   **Scoring:** Each tolerance that is used to achieve a match adds to a "cost" score. If the total score for a file edit becomes too high, the operation will be aborted to prevent incorrect or unintended changes.
*   **Indentation Fixing:** When a match is found using a tolerance that ignores indentation, the algorithm intelligently analyzes the indentation of the *matched* block and the *original search* block to automatically adjust the indentation of the *replacement* block. This is a critical feature for maintaining correct code formatting.
*   **Error Reporting:** If a search block cannot be matched at all, the system uses an edit distance algorithm (`SequenceMatcher`) to find the *closest* possible match in the file. It then reports this "near miss" to the user, providing valuable context that helps them correct their search block.

## Key Classes

*   `FileEditInput`: Represents a single file editing job. It holds the file content, the search-replace blocks, and the current state of the recursive matching process. Its `edit_file()` method is the main entry point for the algorithm.
*   `FileEditOutput`: Represents the result of an `edit_file()` call. It contains the proposed changes and a list of all the tolerances that were used. Its `replace_or_throw()` method is called at the end to either apply the changes or raise a `SearchReplaceMatchError` if the error threshold was exceeded.
*   `Tolerance`: A dataclass that defines a single tolerance level, including the function to process the text (e.g., `str.strip`), its severity, and its score multiplier.
*   `SearchReplaceMatchError`: A custom exception that is raised when the editing process fails, providing a detailed, formatted error message to the user.

## How it Works (High-Level)

The `edit_file()` method works as a recursive function:

1.  It takes the first search block from the list.
2.  It tries to find a match for that block in the file content, starting from where the last match ended. It tries the various tolerance levels in order.
3.  If a match is found:
    *   It records the match, the replacement text, and any tolerances that were used.
    *   It then calls `edit_file()` on *itself* with the *rest* of the search blocks and the remainder of the file.
4.  If multiple potential matches are found for a single block, it will explore *all* of them recursively.
5.  At the end, this process may result in multiple possible `FileEditOutput` scenarios. The `get_best_match()` static method is used to select the one with the lowest tolerance score (i.e., the "cleanest" match).
6.  Finally, the `replace_or_throw()` method is called on the best output to apply the changes.
