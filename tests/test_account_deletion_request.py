import importlib


DESTRUCTIVE_CONFIRMATION = "YMMÄRRÄN ETTÄ TILIN POISTO ON PYSYVÄ JA VOI VAIKUTTAA ILMOITTAMIINI MIELENOSOITUKSIIN"


class CapturingEmailSender:
    def __init__(self):
        self.messages = []

    def queue_email(self, **kwargs):
        self.messages.append(kwargs)


def test_account_deletion_request_requires_confirmation(user_client, db, seeded_data):
    response = user_client.post(
        "/users/auth/api/v2/account_deletion_request",
        json={"confirmation": "POISTA", "reason": "Haluan poistaa tilini."},
    )

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
    assert db.account_deletion_requests.count_documents({"user_id": seeded_data["user_id"]}) == 0


def test_account_deletion_request_records_request_and_emails_support(
    user_client,
    db,
    seeded_data,
    monkeypatch,
):
    auth_module = importlib.import_module("mielenosoitukset_fi.users.BPs.auth")
    sender = CapturingEmailSender()
    monkeypatch.setattr(auth_module, "email_sender", sender, raising=True)

    response = user_client.post(
        "/users/auth/api/v2/account_deletion_request",
        json={"confirmation": DESTRUCTIVE_CONFIRMATION, "reason": "Haluan poistaa tilini."},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"

    request_doc = db.account_deletion_requests.find_one({"user_id": seeded_data["user_id"]})
    assert request_doc is not None
    assert request_doc["email"] == "alice@example.test"
    assert request_doc["status"] == "pending"
    assert request_doc["reason"] == "Haluan poistaa tilini."

    assert len(sender.messages) == 1
    message = sender.messages[0]
    assert message["template_name"] == "account_deletion_request.html"
    assert message["recipients"] == ["tuki@mielenosoitukset.fi"]
    assert str(seeded_data["user_id"]) in message["context"]["admin_user_url"]


def test_account_deletion_request_does_not_duplicate_open_requests(
    user_client,
    db,
    seeded_data,
    monkeypatch,
):
    auth_module = importlib.import_module("mielenosoitukset_fi.users.BPs.auth")
    sender = CapturingEmailSender()
    monkeypatch.setattr(auth_module, "email_sender", sender, raising=True)

    for _ in range(2):
        response = user_client.post(
            "/users/auth/api/v2/account_deletion_request",
            json={"confirmation": DESTRUCTIVE_CONFIRMATION, "reason": "Tuplapyyntö."},
        )
        assert response.status_code == 200

    assert db.account_deletion_requests.count_documents({"user_id": seeded_data["user_id"]}) == 1
    assert len(sender.messages) == 1
