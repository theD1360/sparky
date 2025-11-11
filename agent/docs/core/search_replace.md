# Search-Replace Parsing

This module serves as the front-end for the tolerant file editing system. Its primary responsibility is to parse the user-provided string of search-and-replace blocks, validate their syntax, and then hand them off to the `diff_edit` module to perform the actual file modification.

**Location:** `src/utils/file_ops/search_replace.py`

## Core Concepts

*   **Block Parsing:** The module defines the specific syntax for a search-and-replace block:
    ```
    <<<<<<< SEARCH
    ...lines to find...
    =======
    ...lines to replace with...
    >>>>>>> REPLACE
    ```
    It uses regular expressions to identify the `SEARCH`, `=======`, and `REPLACE` markers and extract the content in between.
*   **Syntax Validation:** It performs rigorous checks to ensure the blocks are well-formed. It will raise a `SearchReplaceSyntaxError` if it finds issues like missing markers, empty search blocks, or markers appearing in the wrong place.
*   **Individual Fallback:** This is a key feature for robustness. If a user provides multiple blocks and the `diff_edit` engine fails to find a *unique* match for the entire sequence, this module will catch the failure and then try to apply each block *one at a time*. This can help salvage an edit if only one block is problematic, and it provides more specific error messages to the user.
*   **Unique Match Enforcement:** After a successful edit, it checks if the `diff_edit` engine returned multiple "best" matches. If it did, it means one of the search blocks was ambiguous and matched in more than one place in the file. It raises a `SearchReplaceMatchError` with a helpful message, instructing the user to add more context to their search block to make the match unique.

## Key Functions

*   `search_replace_edit()`: This is the main public function of the module. It takes the raw lines from the user's input, the original file content, and a logger. It orchestrates the entire process:
    1.  It loops through the input lines, parsing them into a list of `(search_block, replace_block)` tuples.
    2.  It calls `edit_with_individual_fallback()` to perform the edit.
    3.  It formats the final result and any warnings into a user-friendly message.
*   `edit_with_individual_fallback()`: This function is the bridge to the `diff_edit` module.
    1.  It creates a `FileEditInput` and calls its `edit_file()` method.
    2.  It gets the best match(es) from the results.
    3.  It handles the unique match check and the individual fallback logic described above.
*   `identify_first_differing_block()`: A helper function used to improve error messages. When multiple unique matches are found, this function inspects the different match results to pinpoint which specific search block was the source of the ambiguity.
