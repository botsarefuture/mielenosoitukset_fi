"""Profile images must stop fetching when both source and fallback fail."""

import pytest


@pytest.mark.parametrize("fallback_available", [True, False])
def test_profile_image_failure_uses_fallback_once(
    client, seeded_data, db, browser_page, fallback_available
):
    primary = "https://images.example.test/broken-profile.png"
    fallback = "https://cdn2.mielenosoitukset.fi/default-pfp.jpg"
    user_id = seeded_data["user_id"]
    user = db.users.find_one({"_id": user_id})
    db.users.update_one({"_id": user_id}, {"$set": {
        "profile_picture": primary,
        "followers": [user_id], "following": [user_id],
    }})
    response = client.get(f"/users/profile/{user['username']}")
    assert response.status_code == 200
    requests = []

    def image_response(route):
        requests.append(route.request.url)
        if route.request.url == fallback and fallback_available:
            route.fulfill(status=200, content_type="image/svg+xml", body=(
                '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
                '<rect width="16" height="16" fill="blue"/></svg>'
            ))
        else:
            route.fulfill(status=404, body="missing")

    browser_page.route(primary, image_response)
    browser_page.route(fallback, image_response)
    # Actual rendered handlers and images; isolate unrelated CDN/scripts.
    browser_page.set_content(response.get_data(as_text=True), wait_until="load")
    images = browser_page.locator("img.profile-avatar, img.follow-list-avatar")
    assert images.count() == 3
    for image in images.all():
        # Follow-list images may be in closed modals; fetching does not need
        # visibility and must not depend on whether modal CSS was loaded.
        image.evaluate("image => image.loading = 'eager'")
    browser_page.wait_for_function("""() => [...document.querySelectorAll(
      'img.profile-avatar, img.follow-list-avatar'
    )].every(image => image.complete && image.getAttribute('src').endsWith('default-pfp.jpg'))""")
    assert all(image.evaluate("image => image.onerror === null") for image in images.all())
    assert all(image.evaluate("image => image.naturalWidth > 0") == fallback_available for image in images.all())
    # Browsers may coalesce identical image fetches, but never an unbounded loop.
    assert 1 <= requests.count(primary) <= 3
    assert 1 <= requests.count(fallback) <= 3
