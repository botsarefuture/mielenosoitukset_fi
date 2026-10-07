"""Guard the public critical path against known redundant dependencies."""

from pathlib import Path


TEMPLATES = Path(__file__).parents[1] / "mielenosoitukset_fi" / "templates"


def test_base_does_not_load_unused_jquery_ui_on_every_public_page():
    source = (TEMPLATES / "base.html").read_text(encoding="utf-8")

    assert "code.jquery.com/ui/" not in source
    assert "jquery-ui.css" not in source


def test_bootstrap_is_versioned_on_the_first_party_cdn():
    source = (TEMPLATES / "base.html").read_text(encoding="utf-8")

    assert "cdn.jsdelivr.net/npm/bootstrap" not in source
    assert source.count(
        "https://cdn2.mielenosoitukset.fi/vendor/bootstrap/5.3.0/"
    ) == 3


def test_high_traffic_pages_do_not_duplicate_font_awesome():
    for template_name in ("index.html", "detail.html"):
        source = (TEMPLATES / template_name).read_text(encoding="utf-8")
        assert "cdnjs.cloudflare.com/ajax/libs/font-awesome" not in source


def test_detail_map_is_lazy_loaded_below_the_fold():
    source = (TEMPLATES / "detail.html").read_text(encoding="utf-8")

    assert 'script.src = "{{ url_for(\'static\', filename=\'leaflet/leaflet.js\') }}"' in source
    assert "new IntersectionObserver" in source
    assert "await Promise.all([stylesheetLoaded, scriptLoaded])" in source
    assert ".then(() => observer.disconnect())" in source
    assert "mapStarted = false" in source
    assert '<script src="{{ url_for(\'static\', filename=\'leaflet/leaflet.js\') }}"></script>' not in source
