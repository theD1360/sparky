"""Comprehensive test suite for advanced file editing capabilities.

Tests the ported wcgw file editing functionality including:
- Search-replace block parsing and application
- Tolerance matching (whitespace, indentation)
- Multiple match detection
- Syntax error reporting
- Context-based unique matching
- Indentation fixing edge cases
"""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from utils.file_ops.diff_edit import SearchReplaceMatchError, fix_indentation
from utils.file_ops.search_replace import SearchReplaceSyntaxError, search_replace_edit
import logging

logger = logging.getLogger(__name__)

@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Provides a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def test_file(temp_dir: str) -> str:
    """Create a test file."""
    file_path = os.path.join(temp_dir, "test.py")
    with open(file_path, "w") as f:
        f.write("def hello():\n    print('hello')\n")
    return file_path


def test_basic_search_replace(test_file: str) -> None:
    """Test basic search-replace functionality."""
    with open(test_file) as f:
        original = f.read()

    blocks = """<<<<<<< SEARCH
def hello():
    print('hello')
=======
def hello():
    print('hello world')
>>>>>>> REPLACE"""

    lines = blocks.split("\n")
    edited, comments = search_replace_edit(lines, original, lambda x: None)

    assert "hello world" in edited
    assert "Edited successfully" in comments


def test_indentation_tolerance(test_file: str) -> None:
    """Test tolerance for indentation differences."""
    with open(test_file) as f:
        original = f.read()

    # Search block has extra indentation
    blocks = """<<<<<<< SEARCH
  def hello():
    print('hello')     
=======
def hello():
    print('ok')
>>>>>>> REPLACE"""

    lines = blocks.split("\n")
    edited, comments = search_replace_edit(lines, original, lambda x: None)

    assert "print('ok')" in edited
    assert "Warning: matching without considering indentation" in comments


def test_no_match_error(test_file: str) -> None:
    """Test error when no match is found."""
    with open(test_file) as f:
        original = f.read()

    blocks = """<<<<<<< SEARCH
  def hello():
    print('no match')  
=======
def hello():
    print('no match replace')
>>>>>>> REPLACE"""

    lines = blocks.split("\n")

    with pytest.raises(SearchReplaceMatchError):
        search_replace_edit(lines, original, lambda x: None)


def test_syntax_error_in_blocks(test_file: str) -> None:
    """Test syntax error detection in blocks."""
    with open(test_file) as f:
        original = f.read()

    # Missing closing marker
    blocks = """<<<<<<< SEARCH
def hello():
    print('ok')
=======
def hello():
    print('ok")
"""

    lines = blocks.split("\n")

    with pytest.raises(SearchReplaceSyntaxError):
        search_replace_edit(lines, original, lambda x: None)


def test_stray_markers(test_file: str) -> None:
    """Test detection of stray markers."""
    with open(test_file) as f:
        original = f.read()

    blocks = """<<<<<<< SEARCH
def hello():
    print('ok')
=======
def hello():
    print('ok")
>>>>>>> REPLACE
>>>>>>> REPLACE
"""

    lines = blocks.split("\n")

    with pytest.raises(SearchReplaceSyntaxError):
        search_replace_edit(lines, original, lambda x: None)


def test_multiple_matches_error(temp_dir: str) -> None:
    """Test error when multiple matches are found."""
    test_file = os.path.join(temp_dir, "test_multi.py")
    # Create the test_multi.py file
    with open(test_file, "w") as f:
        f.write("def hello():\n    print('ok')\n# Comment\ndef hello():\n    print('ok')\n")

    with open(test_file) as f:
        original = f.read()
    # Find the file
@pytest.mark.skip(reason="Temporarily skipping this test as it needs to access files")

def test_whitespace_tolerance_edit_file(test_file: str) -> None:
    """Test edit_file tolerates whitespace in markers"""
    with open(test_file) as f:
        original = f.read()

    # Search block has extra whitespace on markers
    blocks = """   <<<<<<<  SEARCH\n  def my_function():\n    print('hello')     \n   =======\n  def my_function():\n    print('goodbye')\n    >>>>>>>    REPLACE"""

    lines = blocks.split("\n")
    with pytest.raises(SearchReplaceMatchError) as excinfo:
      search_replace_edit(lines, original, lambda x: None)
    assert "No match" in str(excinfo.value)


async def test_set_lines_with_indent_prevents_syntax_error(tmp_path):
    """
    Tests that set_lines_with_indent prevents writing content that would result
    with open(test_file, "w") as f:
        f.write(
            """
def hello():
    print('ok')
# Comment
def hello():
    print('ok')
"""
        )

    with open(test_file) as f:
        original = f.read()

    blocks = """<<<<<<< SEARCH
def hello():
    print('ok')
=======
def hello():
    print('hello world')
>>>>>>> REPLACE
"""

    lines = blocks.split("\n")

    with pytest.raises(SearchReplaceMatchError) as exc:
        search_replace_edit(lines, original, lambda x: None)

    assert "matched more than once" in str(exc.value)


def test_context_based_matching_future(temp_dir: str) -> None:
    """Test using future context to uniquely identify a block."""
    test_file = os.path.join(temp_dir, "test_context.py")
    with open(test_file, "w") as f:
        f.write("A\nB\nC\nB\n")

    with open(test_file) as f:
        original = f.read()

    # Using context to match first B
    blocks = """<<<<<<< SEARCH
A
=======
A
>>>>>>> REPLACE
<<<<<<< SEARCH
B
=======
B_MODIFIED_FIRST
>>>>>>> REPLACE
<<<<<<< SEARCH
C
=======
C
>>>>>>> REPLACE"""

    lines = blocks.split("\n")
    edited, comments = search_replace_edit(lines, original, lambda x: None)

    # First B should be modified
    assert edited == "A\nB_MODIFIED_FIRST\nC\nB\n"


def test_context_based_matching_past(temp_dir: str) -> None:
    """Test using past context to uniquely identify a block."""
    test_file = os.path.join(temp_dir, "test_context.py")
    with open(test_file, "w") as f:
        f.write("A\nB\nC\nB\n")

    with open(test_file) as f:
        original = f.read()

    # Using context to match second B
    blocks = """<<<<<<< SEARCH
C
=======
C
>>>>>>> REPLACE
<<<<<<< SEARCH
B
=======
B_MODIFIED_SECOND
>>>>>>> REPLACE"""

    lines = blocks.split("\n")
    edited, comments = search_replace_edit(lines, original, lambda x: None)

    # Second B should be modified
    assert edited == "A\nB\nC\nB_MODIFIED_SECOND\n"


def test_fix_indentation_empty_inputs():
    """Test indentation fixing with empty inputs."""
    assert fix_indentation([], ["  foo"], ["    bar"]) == ["    bar"]
    assert fix_indentation(["  foo"], [], ["    bar"]) == ["    bar"]
    assert fix_indentation(["  foo"], ["  foo"], []) == []


def test_fix_indentation_same_indentation():
    """Test indentation fixing when indentation is the same."""
    matched_lines = ["    foo", "    bar"]
    searched_lines = ["    baz", "    qux"]
    replaced_lines = ["        spam", "        ham"]
    # Should return replaced_lines unchanged
    assert (
        fix_indentation(matched_lines, searched_lines, replaced_lines) == replaced_lines
    )


def test_fix_indentation_positive_difference():
    """Test removing indentation when search has more spaces."""
    matched_lines = ["  foo", "  bar"]
    searched_lines = ["    foo", "    bar"]
    replaced_lines = ["    spam", "    ham"]
    # diff is 2 => remove 2 spaces from the start of each replaced line
    expected = ["  spam", "  ham"]
    assert fix_indentation(matched_lines, searched_lines, replaced_lines) == expected


def test_fix_indentation_negative_difference():
    """Test adding indentation when matched has more spaces."""
    matched_lines = ["    foo", "    bar"]
    searched_lines = ["  foo", "  bar"]
    replaced_lines = ["spam", "ham"]
    # diff is -2 => add 2 spaces to each line
    expected = ["  spam", "  ham"]
    assert fix_indentation(matched_lines, searched_lines, replaced_lines) == expected


def test_fix_indentation_inconsistent():
    """Test that inconsistent indentation differences don't get fixed."""
    matched_lines = ["    foo", "        bar"]
    searched_lines = ["  foo", "    bar"]
    replaced_lines = ["spam", "ham"]
    # Different diffs => should return replaced_lines unchanged
    assert (
        fix_indentation(matched_lines, searched_lines, replaced_lines) == replaced_lines
    )


def test_fix_indentation_realistic_scenario():
    """Test realistic indentation fixing scenario."""
    matched_lines = [
        "  class Example:",
        "      def method(self):",
        "          print('hello')",
    ]
    searched_lines = [
        "class Example:",
        "    def method(self):",
        "        print('world')",
    ]
    replaced_lines = [
        "class Example:",
        "    def another_method(self):",
        "        print('world')",
    ]
    expected = [
        "  class Example:",
        "      def another_method(self):",
        "          print('world')",
    ]
    assert fix_indentation(matched_lines, searched_lines, replaced_lines) == expected


def test_empty_search_block():
    """Test that empty search blocks raise error."""
    blocks = """<<<<<<< SEARCH
=======
replacement
>>>>>>> REPLACE"""

    lines = blocks.split("\n")

    with pytest.raises(SearchReplaceSyntaxError) as exc:
        search_replace_edit(lines, "original content", lambda x: None)

    assert "SEARCH block cannot be empty" in str(exc.value)


def test_multiple_blocks_sequential(temp_dir: str) -> None:
    """Test multiple blocks applied sequentially."""
    test_file = os.path.join(temp_dir, "test_multi.py")
    with open(test_file, "w") as f:
        f.write("line1\nline2\nline3\nline4\n")

    with open(test_file) as f:
        original = f.read()

    blocks = """<<<<<<< SEARCH
line1
=======
LINE1
>>>>>>> REPLACE
<<<<<<< SEARCH
line3
=======
LINE3
>>>>>>> REPLACE"""

    lines = blocks.split("\n")
    edited, comments = search_replace_edit(lines, original, lambda x: None)

    assert "LINE1" in edited
    assert "LINE3" in edited
    assert "line2" in edited
    assert "line4" in edited


def test_whitespace_tolerance(temp_dir: str) -> None:
    """Test tolerance for trailing whitespace."""
    test_file = os.path.join(temp_dir, "test_ws.py")
    # Write file with trailing whitespace
    with open(test_file, "w") as f:
        f.write("def foo():  \n    pass\n")

    with open(test_file) as f:
        original = f.read()

    # Search without trailing whitespace
    blocks = """<<<<<<< SEARCH
def foo():
    pass
=======
def bar():
    pass
>>>>>>> REPLACE"""

    lines = blocks.split("\n")
    edited, comments = search_replace_edit(lines, original, lambda x: None)

    assert "def bar():" in edited
    # Should work silently (no warnings for rstrip tolerance)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


import pytest

from tools.code.server import set_lines_with_indent
def test_whitespace_tolerance_edit_file(test_file: str) -> None:
    """Test edit_file tolerates whitespace in markers"""
    with open(test_file) as f:
        original = f.read()

    # Search block has extra whitespace on markers
    blocks = """   <<<<<<<  SEARCH\n  def my_function():\n    print('hello')     \n   =======\n  def my_function():\n    print('goodbye')\n    >>>>>>>    REPLACE"""

    lines = blocks.split("\n")
    with pytest.raises(SearchReplaceMatchError) as excinfo:
      search_replace_edit(lines, original, lambda x: None)
    assert "No match" in str(excinfo.value)

@pytest.mark.asyncio
async def test_set_lines_with_indent_prevents_syntax_error(tmp_path):
    """
    Tests that set_lines_with_indent prevents writing content that would result
    in a syntactically invalid Python file.
    """
    # 1. Arrange: Create a valid Python file
    file_path = tmp_path / "test_file.py"
    original_content = "def hello():\n    print('Hello')\n"
    file_path.write_text(original_content)

    # 2. Act: Attempt to use set_lines_with_indent to introduce a syntax error
    # Using preserve_indentation=False and content with no indentation will cause IndentationError
    invalid_content = "print('This has no indentation')"

    # The set_lines_with_indent function returns a dict, we'll check the status
    result_dict = set_lines_with_indent(
        path=str(file_path),
        start_line=2,
        end_line=2,
        content=invalid_content,
        preserve_indentation=False,
    )

    # 3. Assert: The tool should return an error status
    assert result_dict["status"] == "error"
    assert "syntax error" in result_dict["message"].lower()

    # Also assert that the original file content remains unchanged
    final_content = file_path.read_text()
    assert final_content == original_content
