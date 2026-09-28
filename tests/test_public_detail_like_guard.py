from pathlib import Path

import pytest

from tests.conftest import _seed_database


DETAIL = Path("mielenosoitukset_fi/templates/detail.html")


def test_optional_like_controls_are_guarded_in_every_entrypoint():
    source = DETAIL.read_text(encoding="utf-8")

    assert 'if (!likeButton) return;' in source
    assert 'if (anonymousLikeButton) {' in source
    assert source.count('if (!likeButton || !likeCountEl) return;') == 2
    assert 'if (!count) return;' in source


@pytest.mark.e2e
@pytest.mark.integration
def test_cancelled_detail_omits_like_controls_without_page_errors(
    app, db, live_server, browser_page
):
    seeded = _seed_database(app, db)
    db.demonstrations.update_one(
        {"_id": seeded["demo_id"]},
        {"$set": {"cancelled": True}},
    )
    page_errors = []
    browser_page.on("pageerror", lambda error: page_errors.append(str(error)))

    browser_page.goto(
        f"{live_server}/demonstration/{seeded['demo_id']}?force_reload=1",
        wait_until="domcontentloaded",
    )
    browser_page.wait_for_timeout(250)

    assert browser_page.locator("#like-button").count() == 0
    assert browser_page.locator("#like-count").count() == 0
    assert browser_page.get_by_text(
        "Osallistumisilmoituksia ei voi tehdä, koska mielenosoitus on peruttu."
    ).is_visible()
    browser_page.evaluate(
        """async (demoId) => {
            handleLikeClick(demoId);
            await toggleLike(demoId);
            await getLikes(demoId);
            animateLikeCount();
        }""",
        str(seeded["demo_id"]),
    )
    assert not any("Cannot read properties of null" in error for error in page_errors)
