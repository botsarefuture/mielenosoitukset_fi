import re

import pytest

from tests.conftest import _client_for_user, _seed_database


PARAM_PATTERN = re.compile(r"<(?:[^:]+:)?([^>]+)>")


def _path_value(rule, key, seeded_data):
    if key == "action_idx":
        return "0"
    if key == "app_id":
        return str(seeded_data["app_id"])
    if key == "case_id":
        return str(seeded_data["case_id"])
    if key == "city":
        return "Helsinki"
    if key == "demo_id":
        if "pending" in rule:
            return str(seeded_data["pending_demo_id"])
        return str(seeded_data["demo_id"])
    if key == "filename":
        return "demo.jpg"
    if key == "friend_username":
        return seeded_data["friend_username"]
    if key == "history_id":
        return str(seeded_data["history_id"])
    if key == "job_key":
        return "prep"
    if key == "lang":
        return "en"
    if key == "month":
        return "5"
    if key in {"org_id", "organization_id"}:
        return str(seeded_data["org_id"])
    if key == "page":
        return "security"
    if key == "parent":
        return str(seeded_data["recu_demo_id"])
    if key == "req_id":
        if "/developer/requests/" in rule:
            return str(seeded_data["scope_request_id"])
        return str(seeded_data["api_access_request_id"])
    if key == "suggestion_id":
        if "/organization/" in rule:
            return str(seeded_data["org_suggestion_id"])
        return str(seeded_data["suggestion_id"])
    if key == "tag_name":
        return "test-tag"
    if key == "token":
        if "/users/auth/confirm_email/" in rule:
            return seeded_data["confirmation_token"]
        if "/users/auth/password_reset/" in rule:
            return seeded_data["reset_token"]
        if "/cancel_demonstration/" in rule:
            return seeded_data["cancel_token"]
        if "/kampanja/confirm/" in rule:
            return seeded_data["volunteer_token"]
        if "preview_demo_with_token" in rule:
            return seeded_data["preview_token"]
        if "approve_demo_with_token" in rule:
            return seeded_data["approve_token"]
        if "reject_demo_with_token" in rule:
            return seeded_data["reject_token"]
        if "edit_demo_with_token" in rule:
            return seeded_data["edit_token"]
        return "invalid-token"
    if key == "user_id":
        return str(seeded_data["user_id"])
    if key == "username":
        return seeded_data["user_username"]
    if key == "vol_id":
        return str(seeded_data["volunteer_id"])
    if key == "year":
        return "2026"
    return "1"


def _build_path(rule, seeded_data):
    return PARAM_PATTERN.sub(lambda match: _path_value(rule, match.group(1), seeded_data), rule)


def _payload_for(path, seeded_data):
    demo_form = {
        "title": "Smoke Demo",
        "date": "2026-06-01",
        "start_time": "12:00",
        "end_time": "14:00",
        "city": "Helsinki",
        "address": "Mannerheimintie 1",
        "type": "other",
    }
    if path == "/kampanja/api/volunteers":
        return {"name": "Volunteer User", "email": "volunteer@example.test"}
    if path == "/admin/demo/create_demo":
        return demo_form
    if "/admin/demo/edit_demo/" in path:
        return demo_form
    if "/admin/demo/edit_demo_with_token/" in path:
        return demo_form
    if path == "/developer/apps":
        return {"name": "New App", "description": "Smoke-created app"}
    if path.endswith("/request_scopes"):
        return {"scopes": ["write"], "reason": "Smoke test"}
    if path.endswith("/token"):
        return {"type": "short", "scopes": ["read"]}
    if path.startswith("/api/follow/organization/"):
        return {"follow": True}
    if path.startswith("/api/unfollow/organization/"):
        return {"follow": False}
    if path.startswith("/users/profile/api/follow/"):
        return {"username": seeded_data["friend_username"]}
    if path.startswith("/users/profile/api/unfollow/"):
        return {"username": seeded_data["friend_username"]}
    if path.startswith("/users/profile/api/send_friend_request/"):
        return {"username": seeded_data["friend_username"]}
    if path.startswith("/users/profile/api/accept_friend_request/"):
        return {"username": seeded_data["friend_username"]}
    if path.startswith("/users/profile/api/decline_friend_request/"):
        return {"username": seeded_data["friend_username"]}
    if path.startswith("/users/profile/api/send_message/"):
        return {"friend_username": seeded_data["friend_username"], "content": "Hello from smoke test"}
    if path.startswith("/users/auth/password_reset/"):
        return {"password": "UpdatedPass1!", "password_confirm": "UpdatedPass1!"}
    if path == "/admin/user/create_user":
        return {"email": "created.user@example.test", "username": "created-user", "displayname": "Created User", "role": "user"}
    if path.endswith("/api/clearance/" + str(seeded_data["user_id"])):
        return {"approved": True}
    return {}


def _request_kwargs_for(path, method, seeded_data):
    payload = _payload_for(path, seeded_data)
    if method == "GET":
        return {"follow_redirects": False}

    if path in {
        "/admin/demo/create_demo",
        "/admin/user/create_user",
    } or "/admin/demo/edit_demo/" in path or "/admin/demo/edit_demo_with_token/" in path or path.startswith("/users/auth/password_reset/"):
        return {"follow_redirects": False, "data": payload}

    return {"follow_redirects": False, "json": payload}


def _client_for_path(path, clients):
    if path.startswith("/api/admin/demo/"):
        return clients["admin"]
    if path.startswith("/admin") or path.startswith("/board"):
        return clients["admin"]
    if path.startswith("/developer"):
        return clients["developer"]
    if path.startswith("/users") or path.startswith("/api/"):
        return clients["user"]
    return clients["anon"]


@pytest.mark.integration
def test_all_registered_http_routes_respond_without_server_errors(
    app,
    db,
    monkeypatch,
):
    from mielenosoitukset_fi.background_jobs.manager import BackgroundJobManager

    monkeypatch.setattr(
        BackgroundJobManager,
        "run_job_now",
        lambda self, job_key, triggered_by, metadata=None: None,
        raising=True,
    )

    rules = sorted(
        (
            rule.rule,
            tuple(sorted(method for method in rule.methods if method not in {"HEAD", "OPTIONS"})),
            rule.endpoint,
        )
        for rule in app.url_map.iter_rules()
        if rule.endpoint != "static"
    )

    failures = []
    for raw_path, methods, endpoint in rules:
        seeded_data = _seed_database(app, db)
        clients = {
            "anon": app.test_client(),
            "user": _client_for_user(app, seeded_data["user_id"]),
            "admin": _client_for_user(app, seeded_data["admin_id"]),
            "developer": _client_for_user(app, seeded_data["developer_id"]),
        }
        path = _build_path(raw_path, seeded_data)
        selected_client = _client_for_path(path, clients)
        for method in methods:
            request_kwargs = _request_kwargs_for(path, method, seeded_data)

            try:
                response = selected_client.open(path, method=method, **request_kwargs)
            except Exception as exc:
                failures.append(f"{method} {path} ({endpoint}) raised {type(exc).__name__}: {exc}")
                continue

            if response.status_code >= 500:
                failures.append(
                    f"{method} {path} ({endpoint}) returned {response.status_code}"
                )

    assert not failures, "Route smoke failures:\n" + "\n".join(failures)
