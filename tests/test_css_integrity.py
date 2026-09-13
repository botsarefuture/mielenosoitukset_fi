"""Guarantee shipped stylesheets stay structurally valid.

An unclosed ``{`` or an extra ``}`` in a stylesheet is more than cosmetic:
the CSS parser keeps reading everything after the broken point as part of the
surrounding block. In August the admin workspace stylesheet lost exactly one
``}`` on the ``@media (max-width: 640px)`` block, which silently confined ~80%
of the shared admin component layer to screens narrower than 640px and broke
nearly every admin page on desktop.

These tests scan every ``.css`` file under ``static/css`` and fail on
imbalanced braces. Strings and comments are stripped before counting, so
editorial braces (``content: "{"``, SVG data URIs, ``/* { */``) are ignored.
"""

from pathlib import Path


CSS_ROOT = Path("mielenosoitukset_fi/static/css")


def _css_files():
    if not CSS_ROOT.exists():
        return
    for css_file in sorted(CSS_ROOT.rglob("*.css")):
        if css_file.is_file():
            yield css_file


def _strip_comments_and_strings(css):
    """Blank comment bodies and string literals so their braces are ignored."""
    out = []
    i = 0
    length = len(css)
    while i < length:
        char = css[i]
        if char == "/" and i + 1 < length and css[i + 1] == "*":
            end = css.find("*/", i + 2)
            if end == -1:
                end = length
            else:
                end += 2
            out.append(" " * (end - i))
            i = end
        elif char in "\"'":
            quote = char
            i += 1
            out.append(" ")
            while i < length:
                char = css[i]
                if char == "\\":
                    out.append("  ")
                    i += 2
                    continue
                out.append(" ")
                i += 1
                if char == quote:
                    break
        else:
            out.append(char)
            i += 1
    return "".join(out)


def _brace_balance(css):
    depth = 0
    for char in css:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return -1
    return depth


def test_brace_balance_ignores_braces_in_strings_and_comments():
    source = (
        '/* { } */\n'
        '.a { content: "{"; }\n'
        '.b { background: url("data:image/svg+xml,<svg viewBox=\"0 0 1 1\">{}</svg>"); profile: 2px blue; }\n'
        '.c { color: red; }\n'
    )
    balance = _brace_balance(_strip_comments_and_strings(source))
    assert balance == 0


def test_brace_balance_reports_unclosed_and_extra_braces():
    assert _brace_balance(".a { color: red") == 1
    assert _brace_balance(".a { } }") == -1


def test_all_shipped_css_files_have_balanced_braces():
    css_files = list(_css_files())
    assert css_files, "no css files found under {}".format(CSS_ROOT)

    broken = []
    for css_file in css_files:
        source = css_file.read_text(encoding="utf-8")
        balance = _brace_balance(_strip_comments_and_strings(source))
        if balance != 0:
            if balance < 0:
                message = "unexpected closing brace (extra '}')"
            else:
                message = "{} unclosed '{{' block(s)".format(balance)
            broken.append("{}: {}".format(css_file, message))

    assert not broken, (
        "unbalanced braces in stylesheet(s):\n  {}\n"
        "An unclosed block makes the parser treat every later rule as part of "
        "that block, hiding the rest of the sheet from normal viewports."
    ).format("\n  ".join(broken))