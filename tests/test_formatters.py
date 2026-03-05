# tests/test_formatters.py

import pytest
from app.utils.text_formatters import sanitize_for_telegram_markdown


@pytest.mark.parametrize(
    "input_text, expected_output",
    [
        # Test basic character escaping
        ("Hello. World!", "Hello. World!"),
        ("1+1=2", "1+1=2"),
        ("()[]{}<>#|-", "()[]{}<>#|-"),
        ("file_name.py", "file_name.py"),
        # Test that backticks for inline code are NOT escaped
        ("Use `pip install`", "Use `pip install`"),
        # Test bold text is not transformed by this function
        ("This is **bold** text.", "This is **bold** text."),
        # Test list items are not transformed by this function
        ("- First item", "- First item"),
        ("  - Nested item", "  - Nested item"),
        # Test header transformation
        ("### My Title", "*My Title*"),
        ("### My Title\nSome text", "*My Title*\n\nSome text"), # Header with text after
        ("  # Another Header", "*Another Header*"), # Indented header
        ("  # Another Header\n", "*Another Header*\n\n"), # Indented header with only newline after
        # Test combination of rules
        (
            "### Report\n- **Section 1**\n  - Point 1.1 `code`.",
            "*Report*\n\n- **Section 1**\n  - Point 1.1 `code`.",
        ),
        # Test empty string
        ("", ""),
        # Test string with no special characters
        ("A simple sentence", "A simple sentence"),
        # Test string with only newline
        ("\n", "\n"),
        # Multiple headers
        ("## Header 1\nText 1\n### Header 2\nText 2", "*Header 1*\n\nText 1\n*Header 2*\n\nText 2"),
    ],
)
def test_sanitize_for_telegram_markdown(input_text, expected_output):
    """
    Tests the sanitize_for_telegram_markdown function with various inputs.
    """
    assert sanitize_for_telegram_markdown(input_text) == expected_output