import html
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import markdown


_MARKDOWN_HTML_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}


def markdown_to_html(value):
    """Convert editor Markdown to safe HTML without accepting raw HTML."""
    text = (value or "").strip()
    if not text:
        return ""

    rendered = markdown.markdown(
        html.escape(text),
        extensions=["sane_lists", "nl2br"],
    )
    sanitizer = _SafeMarkdownHTMLParser()
    sanitizer.feed(rendered)
    sanitizer.close()
    return sanitizer.html()


def _safe_link_target(value):
    target = (value or "").strip()
    parsed = urlparse(target)
    if parsed.scheme.lower() in {"http", "https", "mailto"}:
        return target
    return ""


class _SafeMarkdownHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in _MARKDOWN_HTML_TAGS:
            return
        if tag == "a":
            target = _safe_link_target(dict(attrs).get("href"))
            href = f' href="{html.escape(target, quote=True)}"' if target else ""
            self.parts.append(f"<a{href}>")
            return
        self.parts.append(f"<{tag}>")

    def handle_startendtag(self, tag, attrs):
        if tag in {"br", "hr"}:
            self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in _MARKDOWN_HTML_TAGS and tag not in {"br", "hr"}:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(html.escape(data))

    def html(self):
        return "".join(self.parts)


class _HTMLToMarkdownParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.list_stack = []
        self.link_stack = []

    def _append(self, value):
        self.parts.append(value)

    def _ensure_newline(self, count=1):
        current = "".join(self.parts)
        missing = count - len(current) + len(current.rstrip("\n"))
        if missing > 0:
            self._append("\n" * missing)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"p", "div", "blockquote"}:
            self._ensure_newline(2)
        elif tag == "br":
            self._ensure_newline()
        elif tag in {"strong", "b"}:
            self._append("**")
        elif tag in {"em", "i"}:
            self._append("*")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._ensure_newline(2)
            self._append(f"{'#' * int(tag[1])} ")
        elif tag in {"ul", "ol"}:
            self._ensure_newline()
            self.list_stack.append({"tag": tag, "index": 0})
        elif tag == "li":
            self._ensure_newline()
            indent = "  " * max(len(self.list_stack) - 1, 0)
            if self.list_stack and self.list_stack[-1]["tag"] == "ol":
                self.list_stack[-1]["index"] += 1
                marker = f"{self.list_stack[-1]['index']}. "
            else:
                marker = "- "
            self._append(f"{indent}{marker}")
        elif tag == "a":
            target = _safe_link_target(attrs.get("href"))
            self.link_stack.append(target)
            if target:
                self._append("[")

    def handle_endtag(self, tag):
        if tag in {"p", "div", "blockquote"}:
            self._ensure_newline(2)
        elif tag in {"strong", "b"}:
            self._append("**")
        elif tag in {"em", "i"}:
            self._append("*")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._ensure_newline(2)
        elif tag in {"ul", "ol"}:
            if self.list_stack:
                self.list_stack.pop()
            self._ensure_newline(2)
        elif tag == "li":
            self._ensure_newline()
        elif tag == "a":
            target = self.link_stack.pop() if self.link_stack else ""
            if target:
                self._append(f"]({target})")

    def handle_data(self, data):
        self._append(data)

    def markdown(self):
        value = "".join(self.parts)
        value = re.sub(r"[ \t]+\n", "\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()


def html_to_markdown(value):
    """Convert stored HTML into readable Markdown for text editors."""
    text = (value or "").strip()
    if not text:
        return ""

    parser = _HTMLToMarkdownParser()
    parser.feed(text)
    parser.close()
    return parser.markdown()
