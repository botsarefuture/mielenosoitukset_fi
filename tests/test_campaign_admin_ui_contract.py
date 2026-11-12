from pathlib import Path


def test_campaign_modal_initializes_inside_deferred_boot():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/kampanja/list.html"
    ).read_text(encoding="utf-8")

    boot = template.split("function boot()", 1)[1]
    assert "bootstrap.Modal.getOrCreateInstance(editModalElement)" in boot
    assert template.index("function boot()") < template.index(
        "bootstrap.Modal.getOrCreateInstance(editModalElement)"
    )
    assert "document.addEventListener('DOMContentLoaded', boot)" in template
