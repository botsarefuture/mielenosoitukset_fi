from pathlib import Path

import pytest


def test_shared_information_cards_have_mobile_shrink_contract():
    css = Path("mielenosoitukset_fi/static/css/v2/gen.css").read_text(
        encoding="utf-8"
    )

    assert ".container-main-content {" in css
    assert "box-sizing: border-box;" in css
    assert ".cards-grid > *" in css
    assert "overflow-wrap: anywhere;" in css


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [320, 360, 390])
def test_information_cards_fit_portrait_viewport(
    live_server, browser_page, viewport_width
):
    browser_page.set_viewport_size({"width": viewport_width, "height": 800})
    browser_page.goto(f"{live_server}/info", wait_until="domcontentloaded")

    contract = browser_page.evaluate(
        """() => ({
            viewport: document.documentElement.clientWidth,
            documentWidth: document.documentElement.scrollWidth,
            cards: [...document.querySelectorAll('.section-card')].map(card => {
                const rect = card.getBoundingClientRect();
                return {
                    left: rect.left,
                    right: rect.right,
                    contentOverflow: card.scrollWidth - card.clientWidth,
                };
            }),
        })"""
    )

    assert contract["documentWidth"] <= contract["viewport"] + 1
    assert contract["cards"]
    for card in contract["cards"]:
        assert card["left"] >= -1
        assert card["right"] <= contract["viewport"] + 1
        assert card["contentOverflow"] <= 1
