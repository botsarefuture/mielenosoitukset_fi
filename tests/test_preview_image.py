"""Tests for the Pillow-rendered demonstration social preview image."""

import io

import pytest
from PIL import Image

from mielenosoitukset_fi.utils import preview_image as preview
from mielenosoitukset_fi.utils.preview_image import (
    HEIGHT,
    PAD_X,
    TITLE_MAX_LINES,
    WIDTH,
    build_content,
    fit_place,
    fit_title,
    format_date,
    format_time,
    render_preview,
    render_preview_png,
    wrap_text,
)
# Captured at import time: the ``app`` fixture stubs the module attribute.
from mielenosoitukset_fi.utils.screenshot import create_screenshot as REAL_CREATE_SCREENSHOT


DEMO = {
    "_id": "6560f0c0c0ffee0000000001",
    "title": "Ilmastolakko",
    "date": "2026-11-20",
    "start_time": "12:00",
    "end_time": "14:00",
    "address": "Senaatintori",
    "city": "Helsinki",
    "tags": ["ilmasto"],
}

TITLE_WIDTH = WIDTH - 2 * PAD_X
TITLE_HEIGHT = preview.TITLE_BOTTOM - preview.TITLE_TOP


def _png(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def test_renders_open_graph_sized_png():
    image = _png(render_preview_png(DEMO))

    assert image.format == "PNG"
    assert image.size == (WIDTH, HEIGHT) == (1200, 630)
    assert image.mode == "RGB"


def test_rendering_is_deterministic():
    assert render_preview_png(DEMO) == render_preview_png(dict(DEMO))


def test_different_content_gives_different_image():
    assert render_preview_png(DEMO) != render_preview_png({**DEMO, "title": "Toinen"})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-11-20", "Perjantai 20.11.2026"),
        ("2026-12-06", "Sunnuntai 6.12.2026"),
        ("06.12.2026", "Sunnuntai 6.12.2026"),
        ("", ""),
        ("pian", "pian"),
    ],
)
def test_format_date_uses_finnish_weekday_without_leading_zeros(value, expected):
    assert format_date(value) == expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("17:00", "19:00", "17.00–19.00"),
        ("08:30:00", "09:00:00", "08.30–09.00"),
        ("13:00", "", "13.00 alkaen"),
        ("13:00", None, "13.00 alkaen"),
        ("", "", ""),
        (None, "18:00", ""),
    ],
)
def test_format_time_matches_site_clock(start, end, expected):
    assert format_time(start, end) == expected


def test_build_content_reads_status_and_place():
    content = build_content({**DEMO, "cancelled": True, "tags": ["Pride"]})

    assert content.title == "Ilmastolakko"
    assert content.date == "Perjantai 20.11.2026"
    assert content.time == "12.00–14.00"
    assert (content.place, content.city) == ("Senaatintori", "Helsinki")
    assert content.cancelled is True
    assert content.pride is True


def test_build_content_does_not_repeat_city_already_in_address():
    content = build_content({**DEMO, "address": "Senaatintori, Helsinki"})

    assert content.city == ""


def test_build_content_accepts_demonstration_like_objects():
    class Demo:
        title = "  Nuoriso   kaduille!  "
        date = "2026-11-14"
        start_time = "13:00"
        end_time = None
        address = None
        city = "Oulu"
        tags = None
        cancelled = False

    content = build_content(Demo())

    assert content.title == "Nuoriso kaduille!"
    assert content.time == "13.00 alkaen"
    assert content.city == "Oulu"


def test_short_title_uses_largest_size():
    layout = fit_title("Ilmastolakko", TITLE_WIDTH, TITLE_HEIGHT)

    assert layout.size == preview.TITLE_SIZES[0]
    assert layout.lines == ("Ilmastolakko",)


def test_long_title_shrinks_and_stays_within_bounds():
    title = (
        "Planeetan rajoissa – tule vaatimaan Suomen yhteiskuntaa planeetan "
        "rajoihin ennen kuin on liian myöhäistä"
    )
    layout = fit_title(title, TITLE_WIDTH, TITLE_HEIGHT)
    font = preview._font(preview.TITLE_FONT, layout.size)

    assert layout.size < preview.TITLE_SIZES[0]
    assert len(layout.lines) <= TITLE_MAX_LINES
    assert len(layout.lines) * layout.line_height <= TITLE_HEIGHT
    assert all(font.getlength(line) <= TITLE_WIDTH for line in layout.lines)
    assert " ".join(layout.lines).replace(" ", " ") == title


def test_overlong_title_is_cut_at_a_word_with_ellipsis():
    title = " ".join(["mielenosoitus"] * 40)
    layout = fit_title(title, TITLE_WIDTH, TITLE_HEIGHT)
    font = preview._font(preview.TITLE_FONT, layout.size)

    assert len(layout.lines) == TITLE_MAX_LINES
    assert layout.lines[-1].endswith("mielenosoitus…")
    assert all(font.getlength(line) <= TITLE_WIDTH for line in layout.lines)


def test_unbreakable_word_is_split_to_fit():
    font = preview._font(preview.TITLE_FONT, 52)
    lines = wrap_text("A" * 200, font, 400)

    assert len(lines) > 1
    assert all(font.getlength(line) <= 400 for line in lines)


def test_open_compound_suffix_and_dash_stay_with_previous_word():
    font = preview._font(preview.TITLE_FONT, 96)
    lines = wrap_text("Turkistarhaton Suomi -marssi – nyt", font, 900)

    assert not any(line.startswith(("-", "–")) for line in lines)


def test_long_address_is_shortened_but_city_is_kept():
    font = preview._font(preview.BODY_FONT, 36)
    address = "Pohjoisesplanadi 11–13, Kauppatorin laidalla vastapäätä Presidentinlinnaa"
    text = fit_place(address, "Helsinki", font, 700)

    assert text.endswith("…, Helsinki")
    assert font.getlength(text) <= 700


def test_finnish_and_swedish_letters_have_glyphs():
    font = preview._font(preview.TITLE_FONT, 96)
    missing = font.getmask("￾").getbbox()
    for char in "ÄÖÅäöåŠšŽž–…":
        assert font.getmask(char).getbbox() != missing, char


def _red_pixels(image, box):
    region = image.crop(box)
    danger = (0xB4, 0x23, 0x18)
    return sum(1 for pixel in region.getdata() if pixel == danger)


def test_cancelled_event_shows_badge():
    badge_box = (WIDTH - 360, 30, WIDTH - PAD_X, 110)

    assert _red_pixels(render_preview(DEMO), badge_box) == 0
    assert _red_pixels(render_preview({**DEMO, "cancelled": True}), badge_box) > 1000


def test_pride_event_uses_rainbow_accent():
    y = preview.BAND_TOP + 2
    plain = render_preview(DEMO)
    pride = render_preview({**DEMO, "tags": ["pride"]})

    assert plain.getpixel((10, y)) == (0xFF, 0x66, 0x00)
    assert pride.getpixel((10, y)) == (0xE4, 0x03, 0x03)
    assert pride.getpixel((WIDTH - 10, y)) == (0x73, 0x29, 0x82)


def test_missing_fields_still_render():
    image = _png(render_preview_png({"_id": "x", "title": "", "date": None}))

    assert image.size == (WIDTH, HEIGHT)


def test_create_screenshot_returns_preview_bytes(tmp_path):
    data = REAL_CREATE_SCREENSHOT(DEMO, return_bytes=True)

    assert data == render_preview_png(DEMO)


def test_create_screenshot_writes_png_to_disk(tmp_path):
    result = REAL_CREATE_SCREENSHOT(DEMO, output_path=str(tmp_path))

    written = tmp_path / f"{DEMO['_id']}.png"
    assert result == str(written)
    assert _png(written.read_bytes()).size == (WIDTH, HEIGHT)
    # An existing file is reused rather than re-rendered.
    assert REAL_CREATE_SCREENSHOT(DEMO, output_path=str(tmp_path)) == (
        f"/static/demo_preview/{DEMO['_id']}.png"
    )


def test_preview_job_uploads_to_existing_demo_preview_path(app, monkeypatch):
    from mielenosoitukset_fi.scripts import preview_image_creator as job

    stored = {**DEMO, "in_past": False}
    updates = []
    uploads = []

    class Collection:
        def find(self, query):
            return [stored]

        def update_one(self, selector, change):
            updates.append((selector, change))

    class Db(dict):
        def __getitem__(self, name):
            return Collection()

    class Manager:
        def get_instance(self):
            return self

        def get_db(self):
            return Db()

    def upload(bucket, fileobj, filename, image_type):
        uploads.append((filename, image_type, fileobj.read()))
        return "https://cdn.example/DEM/demo_preview-1.jpg"

    monkeypatch.setattr(job, "DatabaseManager", Manager)
    monkeypatch.setattr(job, "upload_image_fileobj", upload)
    monkeypatch.setattr(job, "create_screenshot", REAL_CREATE_SCREENSHOT)

    with app.app_context():
        job.run()

    assert uploads == [(f"{DEMO['_id']}.png", "demo_preview", render_preview_png(DEMO))]
    assert updates == [
        ({"_id": DEMO["_id"]}, {"$set": {"preview_image": "https://cdn.example/DEM/demo_preview-1.jpg"}})
    ]
