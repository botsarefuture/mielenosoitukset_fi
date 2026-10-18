"""User-management history is scoped, meaningful and credential-free."""

from datetime import datetime, timezone

import pytest
from bson import ObjectId

from tests.conftest import _client_for_user
from tests.test_admin_account_status import _confirmation


def test_admin_bootstrap_is_pinned_and_served_locally():
    import hashlib
    from pathlib import Path
    source = Path("mielenosoitukset_fi/templates/admin_base.html").read_text()
    vendor = Path("mielenosoitukset_fi/static/vendor/bootstrap/5.3.3")
    assert "filename='vendor/bootstrap/5.3.3/bootstrap.min.css'" in source
    assert "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" not in source
    assert hashlib.sha256((vendor / "bootstrap.min.css").read_bytes()).hexdigest() == "3c8f27e6009ccfd710a905e6dcf12d0ee3c6f2ac7da05b0572d3e0d12e736fc8"
    assert "MIT" in (vendor / "LICENSE").read_text()


def _profile(document, **changes):
    payload = {"username": document["username"], "email": document["email"],
               "displayname": document.get("displayname", ""), "role": document.get("role", "user")}
    if document.get("confirmed"):
        payload["confirmed"] = "on"
    payload.update(changes)
    return payload


def _settle_transitions(page):
    page.evaluate("""async () => {
      await new Promise(requestAnimationFrame);
      await Promise.all(document.getAnimations()
        .filter(animation => animation instanceof CSSTransition)
        .map(animation => animation.finished.catch(() => {})));
    }""")


@pytest.mark.parametrize("endpoint", ["edit_user", "save_user"])
def test_profile_history_records_only_actual_changes_and_no_secrets(admin_client, db, seeded_data, endpoint):
    target = seeded_data["user_id"]
    db.users.update_one({"_id": target}, {"$set": {"mfa_secret": "never-record-this-secret"}})
    document = db.users.find_one({"_id": target})
    payload = _profile(document, displayname="Updated display name", role="translator")
    url = f"/admin/user/{endpoint}/{target}"
    assert admin_client.post(url, data=payload).status_code == 302
    event = db.admin_logs.find_one({"event": "user_details_changed", "entity_id": str(target)})
    assert event["old_state"]["displayname"] == document.get("displayname", "")
    assert event["new_state"]["displayname"] == "Updated display name"
    assert event["new_state"]["role"] == "translator"
    expected_permissions = {"TRANSLATE_DEMO", "TRANSLATE_UI"}
    if endpoint == "edit_user":
        expected_permissions.update(document.get("global_permissions", []))
    assert event["new_state"]["global_permissions"] == sorted(expected_permissions)
    assert event["actor_id"] == str(seeded_data["admin_id"])
    assert isinstance(event["timestamp"], datetime)
    assert "never-record-this-secret" not in repr(event)
    assert "password_hash" not in repr(event) and "mfa_secret" not in repr(event)
    assert admin_client.post(url, data=payload).status_code == 302
    assert db.admin_logs.count_documents({"event": "user_details_changed", "entity_id": str(target)}) == 1


def test_user_history_includes_city_grants_and_revocation(admin_client, db, seeded_data):
    target = seeded_data["user_id"]
    payload = _profile(db.users.find_one({"_id": target}), **{
        "admin_scope_cities[]": ["helsinki"], "admin_scope_permissions[city][]": ["EDIT_DEMO"],
    })
    endpoint = f"/admin/user/edit_user/{target}"
    assert admin_client.post(endpoint, data=payload).status_code == 302
    first = db.admin_logs.find_one({"event": "user_details_changed", "entity_id": str(target)})
    assert first["new_state"]["city_scope_keys"] == ["helsinki"]
    assert set(first["new_state"]["city_scope_permissions"]) == {"EDIT_DEMO", "LIST_DEMOS", "VIEW_DEMO"}
    assert first["new_state"]["role"] == "city_admin"
    payload = _profile(db.users.find_one({"_id": target}))
    assert admin_client.post(endpoint, data=payload).status_code == 302
    events = list(db.admin_logs.find({"event": "user_details_changed", "entity_id": str(target)}).sort("_id", 1))
    assert len(events) == 2
    assert events[1]["old_state"]["city_scope_keys"] == ["helsinki"]
    assert events[1]["new_state"]["city_scope_keys"] == []
    assert events[1]["new_state"]["role"] == "user"


def test_creation_and_reset_requirement_have_safe_history(admin_client, db, seeded_data):
    assert admin_client.post("/admin/user/create_user", json={
        "username": "history-created", "email": "history-created@example.test", "displayname": "History Created",
    }).status_code == 302
    user = db.users.find_one({"username": "history-created"})
    event = db.admin_logs.find_one({"event": "user_created", "entity_id": str(user["_id"])})
    assert event["new_state"]["username"] == "history-created"
    assert user["password_hash"] not in repr(event)
    target = seeded_data["user_id"]
    assert admin_client.post("/admin/user/api/force_password_change/", json={"user_id": str(target)}).status_code == 200
    event = db.admin_logs.find_one({"event": "user_password_reset_required", "entity_id": str(target)})
    assert event["old_state"]["forced_pwd_reset"] is False
    assert event["new_state"]["forced_pwd_reset"] is True
    assert admin_client.post("/admin/user/api/force_password_change/", json={"user_id": str(target)}).status_code == 200
    events = list(db.admin_logs.find({"event": "user_password_reset_required", "entity_id": str(target)}).sort("_id", 1))
    assert len(events) == 2
    assert events[1]["state_changed"] is False
    assert "Ei kenttämuutoksia." in admin_client.get(f"/admin/user/history/{target}").get_data(as_text=True)


def test_history_adapts_status_logs_and_escapes_values(admin_client, db, seeded_data):
    target = seeded_data["user_id"]
    token = _confirmation(admin_client, target)
    assert admin_client.post(f"/admin/user/account_status/{target}", data={"status_token": token}).status_code == 302
    db.admin_logs.insert_one({
        "event": "user_details_changed", "entity_type": "user", "entity_id": str(target),
        "timestamp": datetime.now(timezone.utc), "actor": {"username": "<img src=x onerror=alert(1)>"},
        "old_state": {"email": "old@example.test", "password_hash": "hidden-password"},
        "new_state": {"email": "new@example.test", "password_hash": "hidden-new-password"},
        "request": {"status_token": "hidden-token"},
    })
    page = admin_client.get(f"/admin/user/history/{target}")
    assert page.status_code == 200
    assert page.cache_control.no_store and page.cache_control.private
    source = page.get_data(as_text=True)
    assert "Käyttötila muutettu" in source and "old@example.test" in source and "new@example.test" in source
    assert "&lt;img" in source and "<img src=x" not in source
    assert all(secret not in source for secret in (token, "hidden-password", "hidden-new-password", "hidden-token"))
    assert "admin-change-diff" in source and "datetime=" in source


def test_history_rejects_missing_capability_and_higher_targets(app, db, seeded_data, admin_client):
    target = seeded_data["user_id"]
    regular = _client_for_user(app, target)
    assert regular.get(f"/admin/user/history/{target}").status_code == 403
    db.users.update_one({"_id": target}, {"$set": {"role": "admin", "global_permissions": ["VIEW_USER"]}})
    assert _client_for_user(app, target).get(f"/admin/user/history/{seeded_data['friend_id']}").status_code == 403
    db.users.update_one({"_id": target}, {"$set": {"global_permissions": ["EDIT_USER"]}})
    actor = _client_for_user(app, target)
    assert actor.get(f"/admin/user/history/{seeded_data['admin_id']}").status_code == 403
    assert actor.get(f"/admin/user/history/{target}").status_code == 200
    assert admin_client.get("/admin/user/history/not-an-id").status_code == 404
    assert admin_client.get(f"/admin/user/history/{ObjectId()}").status_code == 404


def test_history_pagination_is_scoped_bounded_and_stable(admin_client, db, seeded_data):
    target = seeded_data["user_id"]
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    entries = [{"_id": ObjectId(), "event": "user_details_changed", "entity_type": "user",
                "entity_id": str(target), "timestamp": timestamp,
                "old_state": {}, "new_state": {"displayname": f"history-row-{number:02d}"}}
               for number in range(41)]
    db.admin_logs.insert_many(entries)
    db.admin_logs.insert_one({"event": "user_details_changed", "entity_type": "user",
        "entity_id": str(seeded_data["friend_id"]), "new_state": {"displayname": "unrelated-user-secret"}})
    seen = []
    for number in (1, 2, 3):
        response = admin_client.get(f"/admin/user/history/{target}?page={number}&per_page=600000")
        assert response.status_code == 200
        import re
        source = response.get_data(as_text=True)
        rows = re.findall(r"history-row-\d+", source)
        assert len(rows) == (20 if number < 3 else 1)
        assert "unrelated-user-secret" not in source
        seen.extend(rows)
    assert seen == [f"history-row-{number:02d}" for number in reversed(range(41))]
    assert admin_client.get(f"/admin/user/history/{target}?page=999999999").status_code == 200


def test_invalid_profile_save_does_not_invent_history(admin_client, db, seeded_data):
    target = seeded_data["user_id"]
    document = db.users.find_one({"_id": target})
    response = admin_client.post(f"/admin/user/save_user/{target}", data=_profile(document, email="invalid"))
    assert response.status_code == 302
    assert db.users.find_one({"_id": target})["email"] == document["email"]
    assert db.admin_logs.count_documents({"event": "user_details_changed", "entity_id": str(target)}) == 0


@pytest.mark.parametrize("locale,title,current,after", [
    ("fi", "Muutoshistoria", "Nykyinen tila", "Muutoksen jälkeen"),
    ("en", "Change history", "Current status", "After the change"),
    ("sv", "Ändringshistorik", "Nuvarande status", "Efter ändringen"),
])
def test_user_history_and_transition_copy_follow_locale(app, admin_client, seeded_data, locale, title, current, after):
    app.config.update(BABEL_PUBLIC_LOCALES=["fi", "en", "sv"])
    with admin_client.session_transaction() as session:
        session["locale"] = locale
    target = seeded_data["user_id"]
    assert title in admin_client.get(f"/admin/user/history/{target}").get_data(as_text=True)
    source = admin_client.get(f"/admin/user/account_status/{target}").get_data(as_text=True)
    assert current in source and after in source
    import gettext
    from pathlib import Path
    with Path(f"mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.mo").open("rb") as stream:
        catalog = gettext.GNUTranslations(stream)
    assert catalog.gettext("Muokkaa käyttäjää") == {"fi": "Muokkaa käyttäjää", "en": "Edit user", "sv": "Redigera användare"}[locale]
    assert catalog.gettext("Peruuta") == {"fi": "Peruuta", "en": "Cancel", "sv": "Avbryt"}[locale]


@pytest.mark.e2e
@pytest.mark.parametrize("enable", [False, True])
@pytest.mark.parametrize("theme,width", [("light", 320), ("dark", 390), ("light", 1440), ("dark", 1440)])
def test_status_and_history_share_readable_responsive_layout(
    app, admin_client, db, seeded_data, live_server, browser_page, tmp_path, theme, width, enable
):
    target = seeded_data["user_id"]
    db.users.update_one({"_id": target}, {"$set": {
        "displayname": "A very long display name " * 3,
        "email": "long-address-" * 6 + "@example.test",
        "active": not enable, "banned": enable,
    }})
    db.admin_logs.insert_one({"event": "user_details_changed", "entity_type": "user", "entity_id": str(target),
        "timestamp": datetime.now(timezone.utc), "actor": {"username": "Example administrator"},
        "old_state": {"displayname": "Previous display name"}, "new_state": {"displayname": "Updated display name"}})
    cookie = admin_client.get_cookie(app.config["SESSION_COOKIE_NAME"])
    browser_page.context.add_cookies([{"name": cookie.key, "value": cookie.value, "url": live_server}])
    browser_page.set_viewport_size({"width": width, "height": 1000})
    for path in ("account_status", "history"):
        browser_page.goto(f"{live_server}/admin/user/{path}/{target}")
        browser_page.evaluate("""theme => {
          document.documentElement.classList.toggle('dark', theme === 'dark');
          document.documentElement.classList.toggle('light', theme === 'light');
          document.documentElement.dataset.bsTheme = theme;
          document.documentElement.style.colorScheme = theme;
        }""", theme)
        _settle_transitions(browser_page)
        assert browser_page.locator(".admin-page-hero h1").is_visible()
        assert browser_page.locator(".admin-identity").is_visible()
        assert browser_page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        assert browser_page.locator(".admin-identity").evaluate("e => e.scrollWidth <= e.clientWidth + 1")
        if path == "account_status":
            assert browser_page.locator(".admin-state-transition").is_visible()
            assert browser_page.locator(".admin-identity").bounding_box()["y"] < browser_page.locator(".admin-state-transition").bounding_box()["y"]
            cancel = browser_page.locator(".admin-sticky-actions a")
            cancel.focus()
            browser_page.keyboard.press("Tab")
            submit = browser_page.locator(".admin-sticky-actions button")
            assert submit.evaluate("e => e === document.activeElement")
            assert submit.bounding_box()["height"] >= 44
            assert ("btn-primary" if enable else "btn-danger") in submit.get_attribute("class")
            contrast = """element => {
                  const style = getComputedStyle(element);
                  const luminance = color => {
                    const values = color.match(/[\\d.]+/g).slice(0, 3).map(Number).map(v => {
                      v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4;
                    });
                    return values[0]*.2126 + values[1]*.7152 + values[2]*.0722;
                  };
                  const a=luminance(style.color), b=luminance(style.backgroundColor);
                  return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
                }"""
            for selector, control in ((".admin-sticky-actions a", cancel), (".admin-sticky-actions button", submit)):
                browser_page.wait_for_function(
                    "selector => (" + contrast + ")(document.querySelector(selector)) >= 4.5", arg=selector,
                )
                assert control.evaluate(contrast) >= 4.5
        else:
            assert browser_page.locator(".admin-change-diff").is_visible()
            summary = browser_page.locator(".admin-change-history summary").first
            summary.focus()
            browser_page.keyboard.press("Enter")
            assert not browser_page.locator(".admin-change-history details").first.evaluate("e => e.open")
            browser_page.keyboard.press("Enter")
        browser_page.evaluate("document.activeElement.blur(); window.scrollTo(0, 0)")
        _settle_transitions(browser_page)
        browser_page.screenshot(path=str(tmp_path / f"{path}-{theme}-{width}.png"), full_page=True)
