from pathlib import Path
from html.parser import HTMLParser


ADMIN_TEMPLATE_ROOTS = (
    Path("mielenosoitukset_fi/templates/admin"),
    Path("mielenosoitukset_fi/templates/admin_V2"),
)


def _admin_templates():
    for root in ADMIN_TEMPLATE_ROOTS:
        yield from root.rglob("*.html")


class _AdminHeroContractParser(HTMLParser):
    """Collect structural hero violations without rendering Jinja templates."""

    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
    _ALLOWED_CHILDREN = {
        "admin-page-hero__content",
        "admin-page-hero__actions",
        "admin-page-hero__metric",
        "admin-page-hero__nav",
    }

    def __init__(self):
        super().__init__()
        self.stack = []
        self.violations = []

    def handle_starttag(self, tag, attrs):
        classes = set(dict(attrs).get("class", "").split())
        if self.stack and self.stack[-1]["is_hero"]:
            if not classes.intersection(self._ALLOWED_CHILDREN):
                self.violations.append(
                    f"unexpected direct <{tag}> child of admin-page-hero"
                )
            if "admin-page-hero__content" in classes:
                self.stack[-1]["has_content"] = True

        node = {
            "tag": tag,
            "is_hero": "admin-page-hero" in classes,
            "has_content": False,
        }
        if tag not in self._VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] != tag:
                continue
            closing = self.stack[index:]
            del self.stack[index:]
            for node in reversed(closing):
                if node["is_hero"] and not node["has_content"]:
                    self.violations.append(
                        "admin-page-hero is missing admin-page-hero__content"
                    )
            return


def test_full_admin_templates_use_the_admin_shell():
    violations = []

    for template in _admin_templates():
        source = template.read_text(encoding="utf-8")
        if "{% extends" not in source:
            continue
        if "admin_base.html" not in source or "{% block content %}" in source:
            violations.append(str(template))

    assert violations == []


def test_admin_theme_is_applied_before_styles_and_controls_color_scheme():
    base = Path("mielenosoitukset_fi/templates/admin_base.html").read_text(
        encoding="utf-8"
    )
    workspace = Path("mielenosoitukset_fi/static/css/admin/workspace.css").read_text(
        encoding="utf-8"
    )

    assert base.index("localStorage.getItem('theme')") < base.index("variables.css")
    assert "html.light" in workspace and "color-scheme: light" in workspace
    assert "html.dark" in workspace and "color-scheme: dark" in workspace
    assert "modal-content, .modal-header, .modal-body, .modal-footer" not in base


def test_legacy_dialog_does_not_override_bootstrap_modal():
    modal_css = Path("mielenosoitukset_fi/static/css/admin/modal.css").read_text(
        encoding="utf-8"
    )

    selectors = {
        line.strip().removesuffix("{").strip()
        for line in modal_css.splitlines()
        if line.strip().endswith("{")
    }
    assert ".modal" not in selectors
    assert ".modal-header" not in selectors
    assert ".modal-body" not in selectors
    assert ".modal-footer" not in selectors


def test_admin_design_standard_is_documented():
    standard = Path("docs/ADMIN_UI_STANDARD.md").read_text(encoding="utf-8")

    assert "## Lists and tables" in standard
    assert "## Modals" in standard
    assert "--admin-workspace-surface" in standard


def test_admin_page_heroes_keep_copy_in_one_content_group():
    violations = []

    for template in Path("mielenosoitukset_fi/templates/admin_V2").rglob("*.html"):
        parser = _AdminHeroContractParser()
        parser.feed(template.read_text(encoding="utf-8"))
        violations.extend(f"{template}: {message}" for message in parser.violations)

    assert violations == []


def test_admin_hero_foreground_and_data_view_surfaces_are_shared():
    workspace = Path("mielenosoitukset_fi/static/css/admin/workspace.css").read_text(
        encoding="utf-8"
    )
    users = Path(
        "mielenosoitukset_fi/templates/admin_V2/_users_table.html"
    ).read_text(encoding="utf-8")

    assert "color: var(--admin-heading-color, var(--admin-workspace-text));" in workspace
    assert "--admin-heading-color: var(--admin-hero-foreground);" in workspace
    assert "--admin-hero-muted-foreground:" in workspace
    assert "admin-data-view__header admin-result-summary" in users
    assert "admin-data-view__viewport users-table-scroll" in users
    assert "admin-data-view__footer admin-pagination" in users
    assert ".users-results-heading" not in users


def test_user_role_forms_use_shared_admin_contract():
    edit = Path(
        "mielenosoitukset_fi/templates/admin_V2/user/edit.html"
    ).read_text(encoding="utf-8")
    modals = Path(
        "mielenosoitukset_fi/templates/admin_V2/_modals_users.html"
    ).read_text(encoding="utf-8")

    assert 'class="admin-page-hero__content"' in edit
    assert 'class="admin-form admin-user-form"' in edit
    assert "admin-form-section" in edit
    assert "admin-sticky-actions" in edit
    assert "modal fade admin-modal" in modals


def test_demo_collection_uses_server_side_filter_and_pagination_contract():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/dashboard.html"
    ).read_text(encoding="utf-8")
    route = Path(
        "mielenosoitukset_fi/admin/admin_demo_bp.py"
    ).read_text(encoding="utf-8")

    for contract in (
        "admin-filter-bar",
        "admin-advanced-filters",
        "admin-active-filters",
        "admin-result-summary",
        "admin-pagination",
        "admin-page-size",
    ):
        assert contract in template
    assert "filterRows" not in template
    assert '"priority": {"_sort_priority": 1, "date": 1, "_id": 1}' in route
    assert '"date_desc": {"date": -1, "_id": -1}' in route
    assert "filtered_count = mongo.demonstrations.count_documents(filter_query)" in route


def test_secondary_editors_use_shared_form_primitives():
    merge = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/merge.html"
    ).read_text(encoding="utf-8")
    ui_editor = Path(
        "mielenosoitukset_fi/templates/admin_V2/ui_translations/editor.html"
    ).read_text(encoding="utf-8")

    assert "{% block styles %}" not in merge
    assert "admin-form admin-merge-form" in merge
    assert "admin-sticky-actions" in merge
    assert "admin-code-block" in ui_editor
    assert "admin-panel-inset" in ui_editor
    assert 'class="admin-form"' in ui_editor
