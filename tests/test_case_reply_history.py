"""Permission-scoped reply history; real Mongo/Jinja, no real SMTP delivery."""

from datetime import datetime, timedelta
from html.parser import HTMLParser
from xml.etree.ElementTree import Element, SubElement

import pytest

from tests.test_case_city_scope import _city_cases


@pytest.fixture(autouse=True)
def support_case(db, seeded_data):
    db.cases.update_one({"_id": seeded_data["case_id"]}, {"$set": {
        "type": "support_ticket", "submitter": {"submitter_email": "alice@example.test"},
    }})


class _Page(HTMLParser):
    """Small stdlib DOM collector; no new test-only parser dependency."""
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.stack = [self.root]
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = SubElement(self.stack[-1], tag, {key: value or "" for key, value in attrs})
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        node = self.stack[-1]
        node.text = (node.text or "") + data


def _text(node):
    return "".join(node.itertext())


def _history(source):
    return _Page(source).root.find(".//*[@id='outgoing-replies']")


def _messages(db, case_id):
    now = datetime(2026, 10, 25, 9)
    messages = [
        {"message": "Inbound only", "from_email": "submitter@example.test", "timestamp": now},
        {"direction": "out", "message": "First reply\nSecond line", "from_name": "First admin", "status": "sent", "timestamp": now, "sent_at": now + timedelta(minutes=1)},
        {"direction": "out", "message": '<script>window.historyInjected=true</script>\n' + "LongText" * 100,
         "from_name": "Second admin", "to_email": "recorded@example.test", "subject": "Follow-up question",
         "status": "queued", "timestamp": now + timedelta(minutes=2)},
    ]
    db.cases.update_one({"_id": case_id}, {"$set": {"suggestion.messages": messages}})
    return messages


@pytest.mark.parametrize("locale,heading,recipient,labels", [
    ("fi", "Lähetetyt vastaukset", "Vastaanottaja", ["Lähettäjä", "Lähetetty", "Jonossa", "Ei tiedossa"]),
    ("en", "Sent replies", "Recipient", ["Sender", "Sent", "Queued", "Unknown"]),
    ("sv", "Skickade svar", "Mottagare", ["Avsändare", "Skickat", "I kö", "Okänd"]),
])
def test_history_is_separate_localized_and_escaped(app, admin_client, db, seeded_data, monkeypatch, locale, heading, recipient, labels):
    monkeypatch.setitem(app.config, "BABEL_PUBLIC_LOCALES", ["fi", "en", "sv"])
    case_id = seeded_data["case_id"]
    _messages(db, case_id)
    with admin_client.session_transaction() as session:
        session["locale"] = locale
    response = admin_client.get(f"/admin/case/{case_id}/")
    assert response.status_code == 200
    source = response.get_data(as_text=True)
    history = _history(source)
    assert _text(history.find(".//h2")) == heading
    assert recipient in _text(history)
    assert all(label in _text(history) for label in labels)
    assert "Inbound only" not in _text(history) and "Inbound only" in source
    replies = history.findall(".//article")
    assert len(replies) == 2 and "Second admin" in _text(replies[0])
    assert "First reply\nSecond line" in _text(replies[1].find(".//*[@class='admin-message-body']"))
    assert "recorded@example.test" in _text(replies[0])
    assert not history.findall(".//script") and "<script>" in _text(replies[0])
    assert "Toimitettu" not in _text(history)  # sent is not confirmed mailbox delivery
    assert source.count("First reply") == source.count("Second admin") == 1


@pytest.mark.parametrize("messages", [None, []])
def test_legacy_empty_history_does_not_invent_recipients(admin_client, db, seeded_data, messages):
    case_id = seeded_data["case_id"]
    db.cases.update_one({"_id": case_id}, {"$set": {"suggestion.messages": messages}})
    response = admin_client.get(f"/admin/case/{case_id}/")
    assert response.status_code == 200
    history = _history(response.get_data(as_text=True))
    assert "Ei vielä vastauksia." in _text(history) and not history.findall(".//article")


def test_reply_records_actual_recipient_and_retains_source_message(admin_client, db, seeded_data):
    case_id = seeded_data["case_id"]
    message = "**Question**\n\nPlease clarify the location."
    before = db.cases.find_one({"_id": case_id})
    response = admin_client.post(f"/admin/case/{case_id}/reply/", data={"reply_message": message})
    assert response.status_code == 302
    case = db.cases.find_one({"_id": case_id})
    reply = case["suggestion"]["messages"][-1]
    assert reply["to_email"] == before["submitter"]["submitter_email"]
    assert reply["message"] == message and reply["status"] == "queued"
    assert reply["from_name"] and reply["message_id"] in case["meta"]["ticket"]["reply_message_ids"]
    db.cases.update_one({"_id": case_id}, {"$set": {"submitter.submitter_email": "new@example.test"}})
    history = _history(admin_client.get(f"/admin/case/{case_id}/").get_data(as_text=True))
    assert reply["to_email"] in _text(history) and "new@example.test" not in _text(history)


@pytest.mark.parametrize("status,label,tone", [
    ("sent", "Lähetetty", "success"), ("queued", "Jonossa", "warning"),
    ("failed", "Epäonnistui", "danger"), (None, "Ei tiedossa", None),
])
def test_reply_status_is_explicit_without_guessing_delivery(admin_client, db, seeded_data, status, label, tone):
    case_id = seeded_data["case_id"]
    messages = _messages(db, case_id)
    messages[-1]["status"] = status
    db.cases.update_one({"_id": case_id}, {"$set": {"suggestion.messages": messages}})
    history = _history(admin_client.get(f"/admin/case/{case_id}/").get_data(as_text=True))
    first = history.find(".//article")
    badge = first.find(".//span")
    assert _text(badge) == label
    assert badge.get("class") == "admin-status-badge" + (f" admin-status-badge--{tone}" if tone else "")
    assert "Toimitettu" not in _text(first)
    legacy_recipient = history.findall(".//article")[1].findall(".//dd")[1]
    assert _text(legacy_recipient) == "Ei tiedossa"


def test_read_only_city_history_does_not_widen_case_scope(app, db, seeded_data):
    client, _actor, own, foreign, _demo = _city_cases(app, db, seeded_data, permissions=["VIEW_CASE"])
    _messages(db, own)
    _messages(db, foreign)
    response = client.get(f"/admin/case/{own}/")
    assert response.status_code == 200 and 'id="outgoing-replies"' in response.get_data(as_text=True)
    assert 'name="reply_message"' not in response.get_data(as_text=True)
    assert client.get(f"/admin/case/{foreign}/").status_code == 403
    before = db.cases.find_one({"_id": own})
    assert client.post(f"/admin/case/{own}/reply/", data={"reply_message": "Forged"}).status_code == 403
    assert db.cases.find_one({"_id": own}) == before


@pytest.mark.parametrize("width,theme", [(390, "light"), (1440, "dark")])
def test_reply_history_shared_layout_fits_and_preserves_lines(app, db, seeded_data, live_server, browser_page, width, theme):
    client, actor, own, _foreign, _demo = _city_cases(app, db, seeded_data)
    _messages(db, own)
    cookie = app.session_interface.get_signing_serializer(app).dumps({"_user_id": str(actor), "_fresh": True})
    browser_page.context.add_cookies([{"name": app.config.get("SESSION_COOKIE_NAME", "session"), "value": cookie, "url": live_server}])
    browser_page.set_viewport_size({"width": width, "height": 1000})
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    browser_page.goto(f"{live_server}/admin/case/{own}/", wait_until="domcontentloaded")
    history = browser_page.locator("#outgoing-replies")
    history.scroll_into_view_if_needed()
    assert history.is_visible() and history.locator("article").count() == 2
    assert browser_page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert browser_page.evaluate("window.historyInjected === undefined")
    assert history.locator(".admin-message-body").first.evaluate("el => getComputedStyle(el).whiteSpace") == "pre-wrap"
    assert browser_page.evaluate("getComputedStyle(document.documentElement).colorScheme") == theme
    browser_page.screenshot(path=f"/tmp/moso-case-history-{width}-{theme}.png", full_page=True)
