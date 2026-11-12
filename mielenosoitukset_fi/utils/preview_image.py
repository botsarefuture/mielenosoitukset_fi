"""Render the 1200×630 social preview image for a demonstration.

The image is drawn directly with Pillow from bundled fonts, so the output
depends only on the demonstration data: no browser, network font or system
font is involved, and the same input always produces the same PNG bytes.

Layout (all coordinates in pixels):

* a brand-blue hero gradient with the wordmark and, for cancelled events,
  a ``PERUTTU`` badge;
* the title, left-aligned, shrunk to fit at most three lines;
* an accent rule (orange, or the Pride stripes for Pride events);
* a white information band with the date, time and place.

The colours come from ``static/css/product-tokens.css`` and the hero gradient
in ``static/css/public_hero.css``. Visual parameters live in
:class:`PreviewTheme`, so a different background (for example an organizer's
own template) can reuse the same text layout later.
"""

from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from typing import Callable, Iterable, Mapping, Optional, Sequence

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1200
HEIGHT = 630

_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
_FONT_DIR = os.path.join(_STATIC_DIR, "fonts", "inter")
_ICON_FONT = os.path.join(_STATIC_DIR, "fa", "webfonts", "fa-solid-900.ttf")

TITLE_FONT = os.path.join(_FONT_DIR, "InterDisplay-ExtraBold.ttf")
STRONG_FONT = os.path.join(_FONT_DIR, "Inter-ExtraBold.ttf")
BODY_FONT = os.path.join(_FONT_DIR, "Inter-SemiBold.ttf")

# Font Awesome 6 solid code points.
ICON_CALENDAR = ""  # calendar-days
ICON_CLOCK = ""  # clock
ICON_PLACE = ""  # location-dot

WEEKDAYS_FI = (
    "maanantai",
    "tiistai",
    "keskiviikko",
    "torstai",
    "perjantai",
    "lauantai",
    "sunnuntai",
)

Color = tuple  # (r, g, b) or (r, g, b, a)


def _hex(value: str) -> Color:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


@dataclass(frozen=True)
class PreviewTheme:
    """Visual parameters for a preview image.

    ``background`` receives the canvas size and returns an RGB image. The
    default draws the site's hero gradient; another theme could load an image.
    """

    gradient: Sequence[tuple[float, Color]] = (
        (0.0, _hex("#1d4ed8")),  # hero-start
        (0.58, _hex("#2348b8")),  # hero-mid
        (1.0, _hex("#253b85")),  # hero-end
    )
    gradient_angle: float = 125.0
    on_hero: Color = _hex("#ffffff")
    band: Color = _hex("#ffffff")  # product-surface
    band_text: Color = _hex("#172033")  # product-text
    band_icon: Color = _hex("#0033a0")  # product-primary
    accent: Color = _hex("#ff6600")  # product-accent
    danger: Color = _hex("#b42318")  # product-danger (light)
    on_danger: Color = _hex("#ffffff")
    pride_stripes: Sequence[Color] = tuple(
        _hex(c) for c in ("#e40303", "#ff8c00", "#ffed00", "#008026", "#24408e", "#732982")
    )
    background: Optional[Callable[[int, int, "PreviewTheme"], Image.Image]] = field(
        default=None, compare=False
    )


DEFAULT_THEME = PreviewTheme()


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreviewContent:
    """The text shown on a preview, already formatted for display."""

    title: str
    date: str = ""
    time: str = ""
    place: str = ""
    city: str = ""
    cancelled: bool = False
    pride: bool = False


def _get(demo, key, default=None):
    if isinstance(demo, Mapping):
        return demo.get(key, default)
    return getattr(demo, key, default)


def _clean(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _parse_date(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean(value)
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def format_date(value) -> str:
    """``2026-11-13`` → ``Perjantai 13.11.2026`` (Finnish, no leading zeros)."""
    parsed = _parse_date(value)
    if parsed is None:
        return _clean(value)
    weekday = WEEKDAYS_FI[parsed.weekday()]
    return f"{weekday.capitalize()} {parsed.day}.{parsed.month}.{parsed.year}"


def format_clock(value) -> str:
    """``17:00`` or ``17:00:00`` → ``17.00``, matching the site's clock helper."""
    text = _clean(value)
    match = re.fullmatch(r"(\d{1,2})[:.](\d{2})(?::\d{2})?", text)
    if not match:
        return ""
    return f"{int(match.group(1)):02d}.{match.group(2)}"


def format_time(start, end) -> str:
    start_label, end_label = format_clock(start), format_clock(end)
    if start_label and end_label:
        return f"{start_label}–{end_label}"
    if start_label:
        return f"{start_label} alkaen"
    return ""


def build_content(demo) -> PreviewContent:
    """Extract display text from a demonstration dict or object."""
    tags = _get(demo, "tags") or []
    if isinstance(tags, str):
        tags = [tags]
    pride = any(isinstance(tag, str) and tag.strip().lower() == "pride" for tag in tags)
    city = _clean(_get(demo, "city"))
    address = _clean(_get(demo, "address"))
    if city and address and city.lower() in address.lower():
        # "Senaatintori, Helsinki" already names the city.
        city = ""
    return PreviewContent(
        title=_clean(_get(demo, "title")) or "Mielenosoitus",
        date=format_date(_get(demo, "date")),
        time=format_time(_get(demo, "start_time"), _get(demo, "end_time")),
        place=address,
        city=city,
        cancelled=bool(_get(demo, "cancelled")),
        pride=pride,
    )


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=64)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.BASIC)


def _lerp(a: Color, b: Color, t: float) -> Color:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient_color(stops: Sequence[tuple[float, Color]], t: float) -> Color:
    t = min(1.0, max(0.0, t))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            return _lerp(c0, c1, (t - p0) / (p1 - p0) if p1 > p0 else 0.0)
    return stops[-1][1]


def _hero_background(width: int, height: int, theme: PreviewTheme) -> Image.Image:
    """CSS-like ``linear-gradient(125deg, …)`` with the hero's two soft glows.

    Computed on a small grid and scaled up: smooth, fast and deterministic.
    """
    import math

    scale = 10
    w, h = width // scale, height // scale
    angle = math.radians(theme.gradient_angle)
    dx, dy = math.sin(angle), -math.cos(angle)
    half = abs(w * dx) / 2 + abs(h * dy) / 2
    glows = (
        # (centre x, centre y, radius as share of the diagonal, colour, alpha)
        (0.12, 0.08, 0.34, (255, 255, 255), 0.16),
        (0.92, 0.88, 0.30, (249, 115, 22), 0.16),
    )
    diagonal = math.hypot(w, h)
    small = Image.new("RGB", (w, h))
    pixels = small.load()
    for y in range(h):
        for x in range(w):
            px, py = x + 0.5 - w / 2, y + 0.5 - h / 2
            t = (px * dx + py * dy + half) / (2 * half)
            r, g, b = _gradient_color(theme.gradient, t)
            for gx, gy, radius, colour, alpha in glows:
                dist = math.hypot(x + 0.5 - gx * w, y + 0.5 - gy * h) / (radius * diagonal)
                if dist < 1:
                    a = alpha * (1 - dist)
                    r = r + (colour[0] - r) * a
                    g = g + (colour[1] - g) * a
                    b = b + (colour[2] - b) * a
            pixels[x, y] = (round(r), round(g), round(b))
    return small.resize((width, height), Image.Resampling.BICUBIC)


@lru_cache(maxsize=4)
def _cached_background(theme: PreviewTheme) -> Image.Image:
    return _hero_background(WIDTH, HEIGHT, theme)


def _text_width(font: ImageFont.FreeTypeFont, text: str) -> float:
    return font.getlength(text)


def _split_long_word(word: str, font, max_width: float) -> list[str]:
    parts, current = [], ""
    for char in word:
        if current and _text_width(font, current + char) > max_width:
            parts.append(current)
            current = char
        else:
            current += char
    if current:
        parts.append(current)
    return parts


def wrap_text(text: str, font, max_width: float) -> list[str]:
    """Greedy word wrap; words wider than a line are broken by character.

    A Finnish open compound suffix (``Suomi -marssi``) and a spaced dash stay
    with the preceding word, so no line starts with ``-marssi`` or ``–``.
    """
    words: list[str] = []
    for word in text.split(" "):
        if not word:
            continue
        if words and (word.startswith("-") or word in ("–", "—")):
            words[-1] = f"{words[-1]} {word}"
        else:
            words.append(word)
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if _text_width(font, candidate) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        if _text_width(font, word) <= max_width:
            current = word
        else:
            pieces = _split_long_word(word, font, max_width)
            lines.extend(pieces[:-1])
            current = pieces[-1]
    if current:
        lines.append(current)
    return lines


def ellipsize(text: str, font, max_width: float) -> str:
    """Trim ``text`` to ``max_width``, ending in an ellipsis when cut.

    The cut prefers a word boundary unless that would drop more than a third
    of the line.
    """
    if _text_width(font, text) <= max_width:
        return text
    trimmed = text
    while trimmed and _text_width(font, trimmed.rstrip(" ,.–- ") + "…") > max_width:
        trimmed = trimmed[:-1]
    if not text[len(trimmed) : len(trimmed) + 1].isspace():
        boundary = max(trimmed.rfind(" "), trimmed.rfind(" "))
        if boundary > len(trimmed) * 2 / 3:
            trimmed = trimmed[:boundary]
    return trimmed.rstrip(" ,.–- ") + "…"


@dataclass(frozen=True)
class TitleLayout:
    size: int
    lines: tuple[str, ...]
    line_height: int


TITLE_SIZES = (96, 84, 78, 72, 66, 60, 56, 52)
TITLE_MAX_LINES = 3


def fit_title(title: str, max_width: float, max_height: float) -> TitleLayout:
    """Largest size whose wrap fits; the smallest size truncates with an ellipsis."""
    for size in TITLE_SIZES:
        font = _font(TITLE_FONT, size)
        line_height = round(size * 1.1)
        lines = wrap_text(title, font, max_width)
        if len(lines) <= TITLE_MAX_LINES and len(lines) * line_height <= max_height:
            return TitleLayout(size, tuple(lines), line_height)
    size = TITLE_SIZES[-1]
    font = _font(TITLE_FONT, size)
    lines = wrap_text(title, font, max_width)
    kept = lines[:TITLE_MAX_LINES]
    if len(lines) > TITLE_MAX_LINES:
        # Force a cut so the reader can see the title continues.
        overflow = " ".join(lines[TITLE_MAX_LINES - 1 :])
        kept[-1] = ellipsize(overflow, font, max_width)
    return TitleLayout(size, tuple(kept), round(size * 1.1))


def fit_place(place: str, city: str, font, max_width: float) -> str:
    """Join address and city, shortening the address first so the city stays.

    A long address drops its trailing comma-separated parts first
    (``Pohjoisesplanadi 11–13, Kauppatorin laidalla`` → ``Pohjoisesplanadi
    11–13``), so the line never reads ``…, Helsinki`` unless even the first
    part is too long.
    """
    if not place:
        return ellipsize(city, font, max_width)
    if not city:
        return ellipsize(place, font, max_width)
    full = f"{place}, {city}"
    if _text_width(font, full) <= max_width:
        return full
    suffix = f", {city}"
    room = max_width - _text_width(font, suffix)
    if room < _text_width(font, "Xxxxx…"):
        return ellipsize(full, font, max_width)
    parts = [part.strip() for part in place.split(",") if part.strip()]
    for count in range(len(parts) - 1, 0, -1):
        shorter = ", ".join(parts[:count])
        if _text_width(font, shorter) <= room:
            return shorter + suffix
    return ellipsize(parts[0] if parts else place, font, room) + suffix


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

PAD_X = 72
HEADER_Y = 52
BAND_TOP = 456
ACCENT_HEIGHT = 8
PRIDE_EXTRA = 6  # Pride stripes: 14px in all
PRIDE_GAP = 3
TITLE_TOP = 124
TITLE_BOTTOM = BAND_TOP - 32


def _draw_icon_row(draw, x, centre_y, items: Iterable[tuple[str, str]], theme, max_right) -> None:
    """Draw ``(icon, text)`` pairs on one line, vertically centred on ``centre_y``."""
    icon_font = _font(_ICON_FONT, 30)
    text_font = _font(BODY_FONT, 36)
    for icon, text in items:
        if not text:
            continue
        draw.text((x + 15, centre_y), icon, font=icon_font, fill=theme.band_icon, anchor="mm")
        x += 50
        text = ellipsize(text, text_font, max_right - x)
        draw.text((x, centre_y), text, font=text_font, fill=theme.band_text, anchor="lm")
        x += _text_width(text_font, text) + 44


def render_preview(demo, theme: PreviewTheme = DEFAULT_THEME) -> Image.Image:
    """Render the preview image for ``demo`` (dict or ``Demonstration``)."""
    content = demo if isinstance(demo, PreviewContent) else build_content(demo)

    if theme.background is not None:
        image = theme.background(WIDTH, HEIGHT, theme).convert("RGB").resize((WIDTH, HEIGHT))
    else:
        image = _cached_background(theme).copy()
    draw = ImageDraw.Draw(image)
    content_right = WIDTH - PAD_X

    # Header: wordmark and status badge.
    wordmark = _font(STRONG_FONT, 32)
    draw.text((PAD_X, HEADER_Y), "Mielenosoitukset.fi", font=wordmark, fill=theme.on_hero, anchor="lt")
    if content.cancelled:
        badge_font = _font(STRONG_FONT, 28)
        label = "PERUTTU"
        tracking = 2
        label_width = sum(_text_width(badge_font, ch) for ch in label) + tracking * (len(label) - 1)
        pad_x, height = 24, 52
        right = content_right
        left = right - label_width - 2 * pad_x
        top = HEADER_Y - 10
        draw.rounded_rectangle((left, top, right, top + height), radius=height // 2, fill=theme.danger)
        cx = left + pad_x
        for ch in label:
            draw.text((cx, top + height / 2), ch, font=badge_font, fill=theme.on_danger, anchor="lm")
            cx += _text_width(badge_font, ch) + tracking

    # Title, vertically centred in its area.
    layout = fit_title(content.title, content_right - PAD_X, TITLE_BOTTOM - TITLE_TOP)
    title_font = _font(TITLE_FONT, layout.size)
    block = layout.line_height * len(layout.lines)
    y = TITLE_TOP + (TITLE_BOTTOM - TITLE_TOP - block) / 2
    for line in layout.lines:
        draw.text((PAD_X, y + layout.line_height / 2), line, font=title_font, fill=theme.on_hero, anchor="lm")
        y += layout.line_height

    # Accent rule and information band.
    if content.pride:
        # A white hairline above the stripes keeps the blue and violet stripes
        # from merging into the blue hero; the stripes are taller than the
        # orange rule so each colour reads at feed size.
        top = BAND_TOP - PRIDE_EXTRA
        draw.rectangle((0, top - PRIDE_GAP, WIDTH, top - 1), fill=theme.band)
        stripe = WIDTH / len(theme.pride_stripes)
        for index, colour in enumerate(theme.pride_stripes):
            draw.rectangle(
                (round(index * stripe), top, round((index + 1) * stripe) - 1, BAND_TOP + ACCENT_HEIGHT - 1),
                fill=colour,
            )
    else:
        draw.rectangle((0, BAND_TOP, WIDTH, BAND_TOP + ACCENT_HEIGHT - 1), fill=theme.accent)
    band_top = BAND_TOP + ACCENT_HEIGHT
    draw.rectangle((0, band_top, WIDTH, HEIGHT), fill=theme.band)

    when = [(ICON_CALENDAR, content.date), (ICON_CLOCK, content.time)]
    when = [item for item in when if item[1]]
    place = fit_place(content.place, content.city, _font(BODY_FONT, 36), content_right - PAD_X - 50)
    rows = [row for row in (when, [(ICON_PLACE, place)] if place else []) if row]
    band_height = HEIGHT - band_top
    row_gap = 74
    first = band_top + band_height / 2 - row_gap * (len(rows) - 1) / 2
    for index, row in enumerate(rows):
        _draw_icon_row(draw, PAD_X, first + index * row_gap, row, theme, content_right)

    return image


def render_preview_png(demo, theme: PreviewTheme = DEFAULT_THEME) -> bytes:
    """Return the preview as PNG bytes. Identical input gives identical bytes."""
    buffer = io.BytesIO()
    render_preview(demo, theme).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
