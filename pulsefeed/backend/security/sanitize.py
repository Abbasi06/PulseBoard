"""
Prompt injection sanitizer for LLM-bound user inputs.

Three-stage pipeline, applied in order:
  1. HTML  — decode entities (html.unescape) then strip all tags via regex.
             Prevents XSS if content is ever reflected to the frontend and
             catches encoded variants like &lt;script&gt;.
  2. Markdown — strip formatting syntax that can wrap injection payloads
             (images, links, headings, blockquotes, emphasis, HR rules).
             Visible link text is preserved; image markup is dropped entirely.
  3. Injection — strip LLM control tokens, instruction-override phrases,
             role-prefix patterns, null bytes, and excess whitespace.
             (Unchanged from the original implementation.)

Design: strip-only, never raise.  If content is modified a WARNING is emitted
with the field name only — the raw value is never logged.
"""
import html
import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage 1: HTML
# ---------------------------------------------------------------------------

# Match any HTML tag up to 2000 chars (incl. attributes); DOTALL for newlines
_HTML_TAG_RE = re.compile(r"<[^>]{0,2000}>", re.DOTALL)

# ---------------------------------------------------------------------------
# Stage 2: Markdown formatting
# ---------------------------------------------------------------------------

# Images: ![alt](url) → remove entirely (URL is the injection surface)
_MD_IMAGE_RE = re.compile(r"!\[[^\]]{0,500}\]\([^\)]{0,2000}\)")

# Links: [text](url) → keep visible text only
_MD_LINK_RE = re.compile(r"\[([^\]]{0,500})\]\([^\)]{0,2000}\)")

# Headings at line start: # … → strip the hashes
_MD_HEADING_RE = re.compile(r"(?im)^#{1,6}\s+")

# Blockquotes at line start: > … → strip the marker
_MD_BLOCKQUOTE_RE = re.compile(r"(?im)^>\s*")

# Horizontal rules on their own line
_MD_HR_RE = re.compile(r"(?m)^(---|\*\*\*|___)\s*$")

# Emphasis / inline-code delimiters: **, __, *, _, `, ```
_MD_EMPHASIS_RE = re.compile(r"(\*{1,3}|_{1,3}|`{1,3})")

# ---------------------------------------------------------------------------
# Stage 3: Injection patterns
# ---------------------------------------------------------------------------

_OVERRIDE_RE = re.compile(
    r"(?i)"
    r"(ignore\s+(?:(?:all|previous|prior|above)\s+){0,3}instructions?)"
    r"|(disregard\s+(?:(?:all|previous|prior)\s+){0,3}instructions?)"
    r"|(forget\s+(?:(?:all|previous|prior|above)\s+){0,3}instructions?)"
    r"|(override\s+(?:(?:all|previous|prior)\s+){0,3}instructions?)"
    r"|(repeat\s+(your\s+)?(system\s+)?prompt)"
    r"|(output\s+(your\s+)?(system\s+)?prompt)"
    r"|(print\s+(your\s+)?(system\s+)?prompt)",
)

_ROLE_PREFIX_RE = re.compile(
    r"(?im)^\s*(system|assistant|user|human)\s*:",
)

_SPECIAL_TOKEN_RE = re.compile(
    r"(<\|im_start\|>|<\|im_end\|>|<\|endoftext\|>)"
    r"|(\[INST\]|\[\/INST\]|<<SYS>>|<\/SYS>>|<\/s>(?!\w))"
    r"|(###\s*(Instruction|Response|Human|Assistant)\s*:)",
    re.IGNORECASE,
)

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_EXCESS_NEWLINES_RE = re.compile(r"\n{3,}")


def sanitize_llm_input(value: str, field_name: str = "field") -> str:
    """
    Return *value* with HTML, Markdown, injection patterns, and control
    characters removed.

    Never raises.  If content was modified, a WARNING is logged with the
    *field_name* only (the raw value is never included in the log line).
    """
    # Stage 1: HTML
    cleaned = html.unescape(value)       # &lt; → <, &amp; → &, &#x27; → '…
    cleaned = _HTML_TAG_RE.sub("", cleaned)

    # Stage 2: Markdown formatting
    cleaned = _MD_IMAGE_RE.sub("", cleaned)
    cleaned = _MD_LINK_RE.sub(r"\1", cleaned)
    cleaned = _MD_HR_RE.sub("", cleaned)
    cleaned = _MD_HEADING_RE.sub("", cleaned)
    cleaned = _MD_BLOCKQUOTE_RE.sub("", cleaned)
    cleaned = _MD_EMPHASIS_RE.sub("", cleaned)

    # Stage 3: Injection patterns
    cleaned = _CONTROL_RE.sub("", cleaned)
    cleaned = _ROLE_PREFIX_RE.sub(" ", cleaned)
    cleaned = _OVERRIDE_RE.sub(" ", cleaned)
    cleaned = _SPECIAL_TOKEN_RE.sub(" ", cleaned)
    cleaned = _EXCESS_NEWLINES_RE.sub("\n\n", cleaned)
    cleaned = cleaned.strip()

    if cleaned != value.strip():
        logger.warning(
            "Input sanitized in field '%s' — HTML/Markdown/injection content stripped",
            field_name,
        )

    return cleaned
