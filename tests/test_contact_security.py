import re


def _contact_token(client):
    response = client.get("/contact")
    assert response.status_code == 200
    match = re.search(
        rb'name="csrf_token" value="([^"]+)"',
        response.data,
    )
    assert match
    return match.group(1).decode("utf-8")


def _valid_payload(token, **updates):
    payload = {
        "csrf_token": token,
        "website": "",
        "name": "Test Visitor",
        "email": "VISITOR@Example.Test ",
        "subject": "Tuki",
        "message": "This is a valid support request.",
    }
    payload.update(updates)
    return payload


def _reset_rate_limit_storage(app):
    for limiter in app.extensions.get("limiter", ()):
        limiter.reset()


def test_contact_accepts_bounded_submission_and_adds_correlation_id(
    app,
    client,
    monkeypatch,
):
    import basic_routes

    app.config["CONTACT_MIN_FORM_SECONDS"] = 0
    queued = []
    monkeypatch.setattr(
        basic_routes.email_sender,
        "queue_email",
        lambda **kwargs: queued.append(kwargs),
    )

    response = client.post(
        "/contact",
        data=_valid_payload(_contact_token(client)),
    )

    assert response.status_code == 302
    request_id = response.headers["X-MF-Request-ID"]
    assert re.fullmatch(r"[a-f0-9]{32}", request_id)
    assert len(queued) == 1
    assert queued[0]["context"]["email"] == "visitor@example.test"
    assert queued[0]["context"]["request_id"] == request_id
    assert queued[0]["extra_headers"] == {"X-MF-Request-ID": request_id}


def test_contact_rejects_missing_or_replayed_csrf_token(app, client, monkeypatch):
    import basic_routes

    app.config["CONTACT_MIN_FORM_SECONDS"] = 0
    queued = []
    monkeypatch.setattr(
        basic_routes.email_sender,
        "queue_email",
        lambda **kwargs: queued.append(kwargs),
    )
    token = _contact_token(client)

    missing = client.post("/contact", data=_valid_payload(""))
    replayed = client.post("/contact", data=_valid_payload(token))

    assert missing.status_code == 400
    assert replayed.status_code == 400
    assert queued == []


def test_contact_honeypot_silently_suppresses_submission(app, client, monkeypatch):
    import basic_routes

    app.config["CONTACT_MIN_FORM_SECONDS"] = 0
    queued = []
    monkeypatch.setattr(
        basic_routes.email_sender,
        "queue_email",
        lambda **kwargs: queued.append(kwargs),
    )

    response = client.post(
        "/contact",
        data=_valid_payload(_contact_token(client), website="bot.example"),
    )

    assert response.status_code == 302
    assert queued == []


def test_contact_rejects_unapproved_subject_and_oversized_message(
    app,
    client,
    monkeypatch,
):
    import basic_routes

    app.config["CONTACT_MIN_FORM_SECONDS"] = 0
    queued = []
    monkeypatch.setattr(
        basic_routes.email_sender,
        "queue_email",
        lambda **kwargs: queued.append(kwargs),
    )

    bad_subject = client.post(
        "/contact",
        data=_valid_payload(_contact_token(client), subject="Injected"),
    )
    oversized = client.post(
        "/contact",
        data=_valid_payload(
            _contact_token(client),
            message="x" * (app.config["CONTACT_MESSAGE_MAX_LENGTH"] + 1),
        ),
    )

    assert bad_subject.status_code == 302
    assert oversized.status_code == 302
    assert queued == []


def test_contact_runtime_circuit_breaker_preserves_support_email_path(
    app,
    client,
    monkeypatch,
):
    import basic_routes

    app.config["CONTACT_MIN_FORM_SECONDS"] = 0
    app.config["CONTACT_FORM_ENABLED"] = False
    queued = []
    monkeypatch.setattr(
        basic_routes.email_sender,
        "queue_email",
        lambda **kwargs: queued.append(kwargs),
    )

    response = client.post(
        "/contact",
        data=_valid_payload(_contact_token(client)),
    )

    assert response.status_code == 302
    assert queued == []


def test_contact_per_ip_rate_limit_is_enforced(app_factory, monkeypatch):
    import basic_routes

    monkeypatch.setattr(
        basic_routes.email_sender,
        "queue_email",
        lambda **_kwargs: None,
    )
    protected_app = app_factory(
        ENFORCE_RATELIMIT=True,
        CONTACT_MIN_FORM_SECONDS=0,
        CONTACT_PER_IP_LIMIT="2 per minute",
        CONTACT_GLOBAL_LIMIT="100 per minute",
    )
    _reset_rate_limit_storage(protected_app)
    protected_client = protected_app.test_client()

    first = protected_client.post(
        "/contact",
        data=_valid_payload(_contact_token(protected_client)),
    )
    second = protected_client.post(
        "/contact",
        data=_valid_payload(_contact_token(protected_client)),
    )
    limited = protected_client.post(
        "/contact",
        data=_valid_payload(_contact_token(protected_client)),
    )

    assert first.status_code == 302
    assert second.status_code == 302
    assert limited.status_code == 429


def test_contact_global_rate_limit_applies_across_client_addresses(
    app_factory,
    monkeypatch,
):
    import basic_routes

    monkeypatch.setattr(
        basic_routes.email_sender,
        "queue_email",
        lambda **_kwargs: None,
    )
    protected_app = app_factory(
        ENFORCE_RATELIMIT=True,
        CONTACT_MIN_FORM_SECONDS=0,
        CONTACT_PER_IP_LIMIT="100 per minute",
        CONTACT_GLOBAL_LIMIT="2 per minute",
    )
    _reset_rate_limit_storage(protected_app)

    responses = []
    for index in range(3):
        protected_client = protected_app.test_client()
        remote_addr = f"192.0.2.{index + 1}"
        get_response = protected_client.get(
            "/contact",
            environ_overrides={"REMOTE_ADDR": remote_addr},
        )
        match = re.search(
            rb'name="csrf_token" value="([^"]+)"',
            get_response.data,
        )
        assert match
        responses.append(
            protected_client.post(
                "/contact",
                data=_valid_payload(match.group(1).decode("utf-8")),
                environ_overrides={"REMOTE_ADDR": remote_addr},
            )
        )

    assert [response.status_code for response in responses] == [302, 302, 429]
