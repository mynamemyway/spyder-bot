# app/utils/text_formatters.py

import re
from typing import Final

# A set of special characters for Telegram's legacy Markdown parse mode.
_LEGACY_MD_ESCAPE_CHARS: Final = r"([_*`\[])"


def _escape_markdown_v2(text: str) -> str:
    """
    Escapes special characters for Telegram's MarkdownV2 parse mode.
    NOTE: This is not currently used but kept for potential future use.

    Args:
        text: The input string to be escaped.
    Returns:
        The string with all special MarkdownV2 characters escaped.
    """
    escape_chars = r"([_*\\~`>#+\-=|{}.!])"  # MarkdownV2 special characters
    return re.sub(escape_chars, r"\\\1", text, 0, re.UNICODE)


def escape_markdown_legacy(text: str) -> str:
    """
    Escapes a minimal set of special characters for Telegram's legacy 'Markdown' parse mode.
    This is intended as a fallback mechanism to prevent parsing errors.
    """
    return re.sub(_LEGACY_MD_ESCAPE_CHARS, r"\\\1", text, 0, re.UNICODE)


def sanitize_for_telegram_markdown(text: str) -> str:
    """
    Performs a "cosmetic" sanitization for Telegram Markdown.

    It removes Markdown header characters ('#') from the beginning of lines and ensures
    that a blank line follows the header to improve readability and prevent
    text from sticking together.
    """
    if not text:
        return ""

    lines = text.split('\n')
    processed_lines = []
    for i, line in enumerate(lines):
        # Check if the line is a header (starts with #, possibly with whitespace)
        match = re.match(r"^\s*#+\s*(.*)", line)
        if match:
            header_content = match.group(1).strip()
            # Make the header bold for better visual separation
            processed_lines.append(f"*{header_content}*")
            # Add a blank line after the header if it's not the last line of the text
            if i < len(lines) - 1:
                processed_lines.append("")  # Ensures a visual break
        else:
            processed_lines.append(line)

    return '\n'.join(processed_lines)