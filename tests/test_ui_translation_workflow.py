import subprocess
from pathlib import Path

from mielenosoitukset_fi.utils.ui_translation_catalog import proposal_key
from mielenosoitukset_fi.utils.ui_translation_git_sync import (
    build_ui_translation_sync_branch_name,
    sync_ui_translation_to_git,
)


PO_TEMPLATE = '''msgid ""
msgstr ""
"Content-Type: text/plain; charset=utf-8\\n"
"Language: {locale}\\n"

msgid "Hello world"
msgstr "{hello_translation}"

msgid "Submit demonstration"
msgstr ""
'''


def _seed_translation_catalogs(app, tmp_path: Path):
    root = tmp_path / "translations"
    app.config["TRANSLATIONS_DIR"] = str(root)

    for locale, hello_translation in [("en", "Hello world"), ("sv", "Hej världen")]:
        locale_dir = root / locale / "LC_MESSAGES"
        locale_dir.mkdir(parents=True, exist_ok=True)
        (locale_dir / "messages.po").write_text(
            PO_TEMPLATE.format(locale=locale, hello_translation=hello_translation),
            encoding="utf-8",
        )

    return root


def test_translator_can_access_ui_translation_dashboard(translator_client, app, tmp_path):
    _seed_translation_catalogs(app, tmp_path)

    response = translator_client.get("/admin/ui-translations")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Käyttöliittymäkäännökset" in body


def test_admin_can_access_ui_translation_sync_dashboard(admin_client, app, db):
    app.config["UI_TRANSLATION_SYNC_ENABLED"] = True
    db.ui_translation_proposals.insert_one(
        {
            "_id": proposal_key("en", "Submit demonstration"),
            "locale": "en",
            "msgid": "Submit demonstration",
            "proposed_text": "Submit a demonstration",
            "status": "approved",
            "github_sync": {
                "status": "retry",
                "branch_name": build_ui_translation_sync_branch_name("en", "Submit demonstration"),
                "last_error": "Push failed",
            },
        }
    )

    response = admin_client.get("/admin/ui-translations/sync")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Käyttöliittymäkäännösten GitHub-synkit" in body
    assert "Submit demonstration" in body


def test_admin_get_to_approve_route_redirects_instead_of_error(admin_client, app, db):
    app.config["UI_TRANSLATION_SYNC_ENABLED"] = True

    response = admin_client.get("/admin/ui-translations/en/approve", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/ui-translations?locale=en")


def test_translator_can_open_ui_translation_editor(translator_client, app, tmp_path):
    _seed_translation_catalogs(app, tmp_path)

    response = translator_client.get(
        "/admin/ui-translations/en/edit?msgid=Submit%20demonstration"
    )

    assert response.status_code == 200


def test_admin_can_open_real_catalog_ui_translation_editor(admin_client):
    response = admin_client.get(
        "/admin/ui-translations/en/edit?msgid=Virheellinen+p%C3%A4iv%C3%A4m%C3%A4%C3%A4r%C3%A4n+muoto.+Ole+hyv%C3%A4+ja+k%C3%A4yt%C3%A4+muotoa+vvvv-kk-pp."
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Incorrect date format. Please use the format dd.mm.yyyy." in body


def test_translator_can_submit_ui_translation_proposal(translator_client, app, db, tmp_path):
    _seed_translation_catalogs(app, tmp_path)

    response = translator_client.post(
        "/admin/ui-translations/en/propose",
        data={
            "msgid": "Submit demonstration",
            "proposed_text": "Submit a demonstration",
            "notes": "Prefer imperative voice.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    proposal = db.ui_translation_proposals.find_one(
        {"_id": proposal_key("en", "Submit demonstration")}
    )
    assert proposal["status"] == "pending"
    assert proposal["proposed_text"] == "Submit a demonstration"
    assert proposal["notes"] == "Prefer imperative voice."


def test_admin_can_approve_ui_translation_proposal(admin_client, app, db, seeded_data, tmp_path):
    root = _seed_translation_catalogs(app, tmp_path)
    app.config["UI_TRANSLATION_SYNC_ENABLED"] = True
    queued = {}
    app.extensions["job_manager"].run_job_now = (
        lambda job_key, triggered_by, metadata=None: queued.update(
            {"job_key": job_key, "triggered_by": triggered_by, "metadata": metadata or {}}
        )
    )
    db.ui_translation_proposals.insert_one(
        {
            "_id": proposal_key("en", "Submit demonstration"),
            "locale": "en",
            "msgid": "Submit demonstration",
            "current_msgstr": "",
            "proposed_text": "Submit a demonstration",
            "status": "pending",
            "submitted_by": str(seeded_data["translator_id"]),
            "submitted_by_name": "Translator User",
        }
    )

    response = admin_client.post(
        "/admin/ui-translations/en/approve",
        data={
            "msgid": "Submit demonstration",
            "review_notes": "Looks good.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    po_contents = (root / "en" / "LC_MESSAGES" / "messages.po").read_text(encoding="utf-8")
    assert 'msgid "Submit demonstration"' in po_contents
    assert 'msgstr "Submit a demonstration"' in po_contents
    assert (root / "en" / "LC_MESSAGES" / "messages.mo").exists()

    proposal = db.ui_translation_proposals.find_one(
        {"_id": proposal_key("en", "Submit demonstration")}
    )
    assert proposal["status"] == "approved"
    assert proposal["review_notes"] == "Looks good."
    assert proposal["github_sync"]["status"] == "queued"
    assert proposal["github_sync"]["branch_name"] == build_ui_translation_sync_branch_name("en", "Submit demonstration")
    assert queued["job_key"] == "process_ui_translation_sync"


def test_admin_can_bulk_requeue_ui_translation_sync(admin_client, app, db):
    app.config["UI_TRANSLATION_SYNC_ENABLED"] = True
    queued = {}
    app.extensions["job_manager"].run_job_now = (
        lambda job_key, triggered_by, metadata=None: queued.update(
            {"job_key": job_key, "triggered_by": triggered_by, "metadata": metadata or {}}
        )
    )
    proposal_id = proposal_key("en", "Submit demonstration")
    db.ui_translation_proposals.insert_one(
        {
            "_id": proposal_id,
            "locale": "en",
            "msgid": "Submit demonstration",
            "proposed_text": "Submit a demonstration",
            "status": "approved",
            "github_sync": {
                "status": "retry",
                "branch_name": build_ui_translation_sync_branch_name("en", "Submit demonstration"),
                "last_error": "Push failed",
            },
        }
    )

    response = admin_client.post(
        "/admin/ui-translations/sync/requeue",
        data={"proposal_ids": [proposal_id]},
        follow_redirects=False,
    )

    assert response.status_code == 302
    proposal = db.ui_translation_proposals.find_one({"_id": proposal_id})
    assert proposal["github_sync"]["status"] == "queued"
    assert proposal["github_sync"]["last_error"] == ""
    assert queued["job_key"] == "process_ui_translation_sync"
    assert queued["metadata"]["bulk_requeue"] is True


def _init_sync_repo(repo_root: Path):
    remote_root = repo_root / "remote.git"
    workspace_root = repo_root / "workspace"
    subprocess.run(["git", "init", "--bare", str(remote_root)], check=True)
    subprocess.run(["git", "clone", str(remote_root), str(workspace_root)], check=True)
    subprocess.run(["git", "-C", str(workspace_root), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(workspace_root), "config", "user.email", "test@example.test"], check=True)
    translation_dir = workspace_root / "mielenosoitukset_fi" / "translations" / "en" / "LC_MESSAGES"
    translation_dir.mkdir(parents=True, exist_ok=True)
    (translation_dir / "messages.po").write_text(
        PO_TEMPLATE.format(locale="en", hello_translation="Hello world"),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(workspace_root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(workspace_root), "commit", "-m", "Initial translations"], check=True)
    subprocess.run(["git", "-C", str(workspace_root), "push", "origin", "HEAD:main"], check=True)
    subprocess.run(["git", "-C", str(workspace_root), "checkout", "-B", "main"], check=True)
    return workspace_root, remote_root


def test_background_sync_can_push_approved_ui_translation_to_git(app, db, tmp_path):
    from mielenosoitukset_fi.scripts.process_ui_translation_sync import run

    workspace_root, remote_root = _init_sync_repo(tmp_path / "sync-repo")
    app.config["UI_TRANSLATION_SYNC_ENABLED"] = True
    app.config["UI_TRANSLATION_SYNC_REPO_PATH"] = str(workspace_root)
    app.config["UI_TRANSLATION_SYNC_BASE_BRANCH"] = "main"
    app.config["UI_TRANSLATION_SYNC_REMOTE"] = "origin"
    app.config["UI_TRANSLATION_GITHUB_REPO"] = ""
    app.config["UI_TRANSLATION_GITHUB_TOKEN"] = ""

    db.ui_translation_proposals.update_one(
        {"_id": proposal_key("en", "Submit demonstration")},
        {
            "$set": {
                "locale": "en",
                "msgid": "Submit demonstration",
                "current_msgstr": "",
                "proposed_text": "Submit a demonstration",
                "status": "approved",
                "github_sync": {
                    "status": "queued",
                    "branch_name": build_ui_translation_sync_branch_name("en", "Submit demonstration"),
                    "attempts": 0,
                },
            }
        },
        upsert=True,
    )

    with app.app_context():
        run(limit=1)

    proposal = db.ui_translation_proposals.find_one(
        {"_id": proposal_key("en", "Submit demonstration")}
    )
    assert proposal["github_sync"]["status"] == "branch_pushed"
    assert proposal["github_sync"]["commit_sha"]

    branch_name = build_ui_translation_sync_branch_name("en", "Submit demonstration")
    branch_sha = subprocess.run(
        ["git", "--git-dir", str(remote_root), "rev-parse", f"refs/heads/{branch_name}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert branch_sha == proposal["github_sync"]["commit_sha"]


def test_sync_can_open_pr_and_attempt_auto_merge(app, tmp_path, monkeypatch):
    workspace_root, _ = _init_sync_repo(tmp_path / "sync-pr-repo")
    app.config["UI_TRANSLATION_SYNC_REPO_PATH"] = str(workspace_root)
    app.config["UI_TRANSLATION_SYNC_BASE_BRANCH"] = "main"
    app.config["UI_TRANSLATION_SYNC_REMOTE"] = "origin"
    app.config["UI_TRANSLATION_GITHUB_REPO"] = "botsarefuture/mielenosoitukset_fi"
    app.config["UI_TRANSLATION_GITHUB_TOKEN"] = "test-token"
    app.config["UI_TRANSLATION_GITHUB_AUTO_MERGE"] = True

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

    requests_seen = {"get": [], "post": [], "put": []}

    def fake_get(url, **kwargs):
        requests_seen["get"].append((url, kwargs))
        return FakeResponse(200, [])

    def fake_post(url, **kwargs):
        requests_seen["post"].append((url, kwargs))
        return FakeResponse(201, {"number": 584, "html_url": "https://github.com/example/pr/584"})

    def fake_put(url, **kwargs):
        requests_seen["put"].append((url, kwargs))
        return FakeResponse(200, {"message": "Pull Request successfully merged"})

    monkeypatch.setattr("mielenosoitukset_fi.utils.ui_translation_git_sync.requests.get", fake_get)
    monkeypatch.setattr("mielenosoitukset_fi.utils.ui_translation_git_sync.requests.post", fake_post)
    monkeypatch.setattr("mielenosoitukset_fi.utils.ui_translation_git_sync.requests.put", fake_put)

    with app.app_context():
        result = sync_ui_translation_to_git(
            locale="en",
            msgid="Submit demonstration",
            translated_text="Submit a demonstration",
        )

    assert result.status == "pr_opened"
    assert result.pr_number == 584
    assert result.pr_url == "https://github.com/example/pr/584"
    assert result.merge_status == "merged"
    assert "merged" in (result.merge_message or "").lower()
    assert requests_seen["post"]
    assert requests_seen["put"]
