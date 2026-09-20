import hashlib
import re
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


def test_admin_inline_style_debt_cannot_grow_without_review():
    style_block_allowlist = {}
    style_attribute_allowlist = {
        "status.html": ("fd8a8ba5d1e16400",),
    }
    root = Path("mielenosoitukset_fi/templates/admin_V2")
    actual_blocks = {}
    actual_attributes = {}

    for template in root.rglob("*.html"):
        source = template.read_text(encoding="utf-8")
        relative = str(template.relative_to(root))
        blocks = re.findall(r"<style(?:\s[^>]*)?>(.*?)</style>", source, re.I | re.S)
        attributes = [
            match.group(2)
            for match in re.finditer(
                r'''style\s*=\s*(["'])(.*?)\1''', source, re.I | re.S
            )
        ]
        if blocks:
            actual_blocks[relative] = tuple(
                hashlib.sha256(value.encode()).hexdigest()[:16] for value in blocks
            )
        if attributes:
            actual_attributes[relative] = tuple(
                hashlib.sha256(value.encode()).hexdigest()[:16] for value in attributes
            )

    assert actual_blocks == style_block_allowlist
    assert actual_attributes == style_attribute_allowlist


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


def test_root_admin_dashboard_uses_shared_components_and_safe_feed_rendering():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/dashboard.html"
    ).read_text(encoding="utf-8")
    stylesheet = Path(
        "mielenosoitukset_fi/static/css/admin/dashboard.css"
    ).read_text(encoding="utf-8")

    assert "<style" not in template
    assert "style=" not in template
    assert "css/admin/dashboard.css" in template
    assert "admin-page admin-workspace admin-dashboard-shell" in template
    assert template.count("admin-panel") >= 3
    assert "admin-empty-state" in template
    assert "admin-status-badge" in template
    assert "admin-dashboard-progress" in template
    assert "innerHTML" not in template
    assert "replaceChildren" in template
    assert "textContent" in template
    assert "light-dark(" not in stylesheet
    assert "--card-" not in stylesheet
    assert "--border-muted" not in stylesheet
    assert "@media (prefers-reduced-motion: reduce)" in stylesheet


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


def test_admin_hero_variants_are_limited_to_the_shared_stacked_contract():
    macro = Path(
        "mielenosoitukset_fi/templates/admin_V2/macros.html"
    ).read_text(encoding="utf-8")
    variant_calls = []

    assert "hero_classes" not in macro
    assert "allowed_variants = ('admin-page-hero--stacked',)" in macro
    for template in Path("mielenosoitukset_fi/templates/admin_V2").rglob("*.html"):
        if template.name == "macros.html":
            continue
        source = template.read_text(encoding="utf-8")
        assert "hero_classes=" not in source, str(template)
        if "variant=" in source:
            variant_calls.append((template, source))

    assert len(variant_calls) == 1
    template, source = variant_calls[0]
    assert template.name == "command_center.html"
    assert "variant='admin-page-hero--stacked'" in source


def test_legacy_admin_hero_selectors_and_action_aliases_are_absent():
    css_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("mielenosoitukset_fi/static/css/admin").glob("*.css")
    )
    template_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("mielenosoitukset_fi/templates/admin_V2").rglob("*.html")
    )
    legacy_selectors = (
        ".admin-page-header",
        ".admin-workspace-hero",
        ".governance-hero",
        ".governance-eyebrow",
        ".logs-header",
        ".case-hero",
        ".editor-hero",
        ".introduction",
    )
    legacy_action_classes = (
        "admin-workspace-hero-action",
        "users-hero-action",
    )

    for selector in legacy_selectors:
        assert selector not in css_sources
    for class_name in legacy_action_classes:
        assert class_name not in template_sources


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
    user_list = Path(
        "mielenosoitukset_fi/templates/admin_V2/user/list.html"
    ).read_text(encoding="utf-8")
    user_table = Path(
        "mielenosoitukset_fi/templates/admin_V2/_users_table.html"
    ).read_text(encoding="utf-8")
    users_css = Path(
        "mielenosoitukset_fi/static/css/admin/users.css"
    ).read_text(encoding="utf-8")

    assert "admin_page_hero(" in edit
    assert 'class="admin-form admin-user-form"' in edit
    assert "admin-form-section" in edit
    assert "admin-sticky-actions" in edit
    assert "modal fade admin-modal" in modals
    assert "<style" not in user_list
    assert "<style" not in user_table
    assert "css/admin/users.css" in user_list
    assert "{{ user.profile_picture }}" in user_table
    assert "class=\"user-avatar\"" in user_table
    assert "object-fit: cover;" in users_css
    assert "admin-workspace-summary" in user_list
    assert "admin-section-card" in user_list
    assert "admin-data-view" in user_list
    assert "--users-" not in users_css
    assert "--admin-workspace-primary-bg" in users_css
    assert "--admin-workspace-orange-strong" in users_css
    assert ".dark .admin-modal .btn-close" in Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")


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
        "admin-data-view",
        "admin-data-view__viewport",
        "admin-data-view__table",
        "admin-data-group-header",
        "admin-data-row--attention",
        "admin-modal",
    ):
        assert contract in template
    assert "admin_pagination(" in template
    common_macro = Path(
        "mielenosoitukset_fi/templates/admin_V2/macros.html"
    ).read_text(encoding="utf-8")
    for class_name in (
        "admin-pagination",
        "admin-page-size",
        "admin-data-view__footer admin-pagination",
        "admin-pagination__info",
    ):
        assert class_name in common_macro
    assert "css/admin/demonstrations.css" in template
    assert "admin-data-view__header admin-result-summary" in template
    assert "<style" not in template
    assert "modal-dark" not in template
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


def test_submitter_modal_keeps_stable_dom_across_reopens():
    dashboard = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/dashboard.html"
    ).read_text(encoding="utf-8")
    handler = dashboard.split("window.showSubmitterInfoModal = async", 1)[1].split(
        "// Initial button text update", 1
    )[0]

    assert 'class="modal fade admin-modal" id="submitterInfoModal"' in dashboard
    for element_id in (
        "submitterInfoLoading",
        "submitterInfoResult",
        "noSubmitterInfo",
        "submitterInfoError",
    ):
        assert f'id="{element_id}"' in dashboard
    assert "bootstrap.Modal.getOrCreateInstance(submitterModalEl)" in dashboard
    assert "textContent =" in handler
    assert "innerHTML" not in handler
    assert "hidden.bs.modal" in handler
def test_organization_workflows_use_shared_admin_components():
    form = Path(
        "mielenosoitukset_fi/templates/admin_V2/organizations/form.html"
    ).read_text(encoding="utf-8")
    review = Path(
        "mielenosoitukset_fi/templates/admin_V2/organizations/review_suggestion.html"
    ).read_text(encoding="utf-8")
    macros = Path(
        "mielenosoitukset_fi/templates/admin_V2/organizations/macros.html"
    ).read_text(encoding="utf-8")
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")

    for template in (form, review, macros):
        assert "<style" not in template
        assert "style=" not in template
    assert "admin-form-layout" in form
    assert "admin-form-section__header" in form
    assert "admin-sticky-actions__buttons" in form
    assert "{{ invite_modal(organization) }}" in form
    assert "organization and can_invite_members" in form
    assert "admin-data-view__viewport" in review
    assert "admin-selection-checkbox field-checkbox" in review
    assert "applyBtn.style" not in review
    assert "--admin-workspace-on-primary: #ffffff;" in workspace
    assert "background: var(--admin-workspace-primary-bg);" in workspace
    assert "background: var(--admin-workspace-primary-hover);" in workspace


def test_organization_collection_uses_shared_data_view_contract():
    dashboard = Path(
        "mielenosoitukset_fi/templates/admin_V2/organizations/dashboard.html"
    ).read_text(encoding="utf-8")

    assert "<style" not in dashboard
    assert "style=" not in dashboard
    assert 'class="admin-page admin-workspace"' in dashboard
    assert "admin-workspace-summary-card" in dashboard
    assert "admin-filter-bar__primary--search" in dashboard
    assert "admin-data-view__viewport" in dashboard
    assert "admin_pagination(" in dashboard
    common_macro = Path(
        "mielenosoitukset_fi/templates/admin_V2/macros.html"
    ).read_text(encoding="utf-8")
    assert "admin-data-view__footer admin-pagination" in common_macro
    assert "admin-pagination__info" in common_macro
    assert "admin-entity-identity" in dashboard
    assert "aria-selected" in dashboard


def test_organization_detail_uses_shared_components_and_scoped_controls():
    detail = Path(
        "mielenosoitukset_fi/templates/admin_V2/organizations/view.html"
    ).read_text(encoding="utf-8")

    assert "<style" not in detail
    assert "style=" not in detail
    assert "admin-detail-layout" in detail
    assert detail.count("admin-data-view") >= 2
    assert "admin-section-card" in detail
    assert "admin-modal admin-workflow-modal" in detail
    assert "admin-toast" in detail
    assert "{% if can_edit_organization %}" in detail
    assert "{% if can_invite_members %}" in detail
    assert "bootstrap.Modal.getOrCreateInstance" in detail
    assert "org-button" not in detail
    assert "org-role-select" not in detail


def test_organization_pages_use_canonical_hero_macro_and_navigation():
    macro = Path("mielenosoitukset_fi/templates/admin_V2/macros.html").read_text(
        encoding="utf-8"
    )
    pages = (
        "dashboard.html",
        "form.html",
        "review_suggestion.html",
        "view.html",
    )

    assert "macro admin_page_hero" in macro
    assert 'class="admin-breadcrumbs"' in macro
    assert 'class="admin-page-hero__content"' in macro
    assert 'class="admin-page-hero__actions"' in macro
    assert "admin-page-hero__back" in macro
    assert macro.index("back_url") < macro.index("caller()")
    for name in pages:
        source = Path(
            "mielenosoitukset_fi/templates/admin_V2/organizations", name
        ).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source


def test_city_admin_operational_pages_use_canonical_hero_macro():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/cities/index.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/form.html",
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/_form_v2.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source
    for name in pages[2:]:
        source = Path(name).read_text(encoding="utf-8")
        assert source.lstrip().startswith("{% extends")
        assert "float:right" not in source
    macro = Path(
        "mielenosoitukset_fi/templates/admin_V2/macros.html"
    ).read_text(encoding="utf-8")
    assert 'class="admin-page-hero__nav editor-section-nav"' in macro
    city_page = Path(pages[0]).read_text(encoding="utf-8")
    assert "<style" not in city_page
    assert "admin-section-card" in city_page
    assert "admin-data-view admin-data-view--scrollable" in city_page
    assert "admin-data-view__table" in city_page
    assert 'rel="noopener noreferrer"' in city_page


def test_access_management_pages_use_canonical_hero_navigation():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/user/list.html",
        "mielenosoitukset_fi/templates/admin_V2/user/edit.html",
        "mielenosoitukset_fi/templates/admin_V2/governance/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/governance/clearances.html",
        "mielenosoitukset_fi/templates/admin_V2/governance/audit.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source
    for name in pages[1:2] + pages[3:]:
        assert "back_url=" in Path(name).read_text(encoding="utf-8")


def test_governance_workspaces_use_shared_collection_components():
    dashboard = Path(
        "mielenosoitukset_fi/templates/admin_V2/governance/dashboard.html"
    ).read_text(encoding="utf-8")
    clearances = Path(
        "mielenosoitukset_fi/templates/admin_V2/governance/clearances.html"
    ).read_text(encoding="utf-8")
    audit = Path(
        "mielenosoitukset_fi/templates/admin_V2/governance/audit.html"
    ).read_text(encoding="utf-8")
    tabs = Path(
        "mielenosoitukset_fi/templates/admin_V2/governance/_tabs.html"
    ).read_text(encoding="utf-8")

    for source in (dashboard, clearances, audit):
        assert "admin-page admin-workspace" in source
        assert "admin-page-hero" not in source or "admin_page_hero(" in source
        assert "admin-data-view__header admin-result-summary" in source
        assert "admin-data-view__viewport" in source
        assert "admin-data-view__table" in source
        assert "admin-empty-state" in source
        assert "governance-card" not in source
        assert "table-responsive" not in source
        assert "<style" not in source
        assert "style=" not in source

    for source in (clearances, audit):
        assert "admin-filter-bar" in source
        assert "admin_pagination(" in source

    assert "admin-workspace-summary" in dashboard
    assert "admin-section-tabs" in tabs
    assert not Path("mielenosoitukset_fi/static/css/admin/governance.css").exists()


def test_translation_workspaces_use_canonical_hero_navigation():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/translations_dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/translations_editor.html",
        "mielenosoitukset_fi/templates/admin_V2/ui_translations/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/ui_translations/editor.html",
        "mielenosoitukset_fi/templates/admin_V2/ui_translations/sync_dashboard.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source
    for name in pages[:2] + pages[3:]:
        assert "back_url=" in Path(name).read_text(encoding="utf-8")
    demo_dashboard = Path(pages[0]).read_text(encoding="utf-8")
    assert "back_url=url_for('admin.admin_dashboard')" in demo_dashboard
    demo_editor = Path(pages[1]).read_text(encoding="utf-8")
    translation_css = Path(
        "mielenosoitukset_fi/static/css/admin/translations.css"
    ).read_text(encoding="utf-8")
    assert "<style" not in demo_editor
    assert "style=" not in demo_editor
    assert "css/admin/translations.css" in demo_editor
    assert "admin-page admin-workspace translation-editor" in demo_editor
    assert demo_editor.count("admin-section-card") >= 3
    assert "admin-panel-inset" in demo_editor
    assert "admin-check-row" in demo_editor
    assert "admin-status-badge" in demo_editor
    assert "admin-form admin-section-card translation-step" in demo_editor
    assert "admin-sticky-actions" in demo_editor
    assert "{% block scripts %}" in demo_editor
    assert "light-dark(" not in translation_css
    assert "--translation-" not in translation_css
    assert "--bs-" not in translation_css


def test_translation_collections_use_shared_filter_data_and_pagination_contracts():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/translations_dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/ui_translations/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/ui_translations/sync_dashboard.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero, admin_pagination" in source
        assert "admin-filter-bar" in source
        assert "admin-data-view__header admin-result-summary" in source
        assert "admin-data-view__viewport" in source
        assert "admin-data-view__table" in source
        assert "admin-empty-state" in source
        assert "admin_pagination(" in source
        assert "class=\"card" not in source
        assert "table-responsive admin-workspace-table" not in source
        assert "<style" not in source
        assert "style=" not in source

    ui_dashboard = Path(pages[1]).read_text(encoding="utf-8")
    sync_dashboard = Path(pages[2]).read_text(encoding="utf-8")
    assert "admin-workspace-summary" in ui_dashboard
    assert "admin-workspace-summary" in sync_dashboard
    assert "admin-selection-checkbox" in sync_dashboard
    assert "aria-selected" in sync_dashboard

    shared_script = Path(
        "mielenosoitukset_fi/static/js/admin_workspace.js"
    ).read_text(encoding="utf-8")
    assert '.matches(".admin-page-size select")' in shared_script
    assert 'url.searchParams.set("per_page", event.target.value)' in shared_script
    assert 'url.searchParams.set("page", "1")' in shared_script

    pagination_pages = pages + (
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/organizations/dashboard.html",
    )
    for name in pagination_pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "page-size')?.addEventListener" not in source
        assert "pageSize?.addEventListener" not in source


def test_system_workspaces_use_canonical_hero_navigation():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/background_jobs.html",
        "mielenosoitukset_fi/templates/admin_V2/background_job_detail.html",
        "mielenosoitukset_fi/templates/admin_V2/status.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
    for name in pages[1:]:
        source = Path(name).read_text(encoding="utf-8")
        assert "admin.admin_dashboard" in source
    assert "back_url=" in Path(pages[2]).read_text(encoding="utf-8")


def test_audit_and_developer_pages_use_canonical_hero_navigation():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/logs.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/audit_log.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/audit_timeline.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/magic_tokens.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/submission_errors.html",
        "mielenosoitukset_fi/templates/admin_V2/developer/requests.html",
        "mielenosoitukset_fi/templates/admin_V2/developer/user_apps.html",
        "mielenosoitukset_fi/templates/admin_V2/user/api_tokens.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source
    for name in pages[1:4] + pages[6:]:
        assert "back_url=" in Path(name).read_text(encoding="utf-8")
    logs = Path(pages[0]).read_text(encoding="utf-8")
    audit_css = Path(
        "mielenosoitukset_fi/static/css/admin/audit.css"
    ).read_text(encoding="utf-8")
    assert "back_url=" in logs
    assert "<style" not in logs
    assert "css/admin/audit.css" in logs
    assert "admin-filter-bar" in logs
    assert "admin-section-tabs" in logs
    assert "admin-data-view__header admin-result-summary" in logs
    assert "admin-data-view__viewport" in logs
    assert "admin_pagination(" in logs
    assert "admin-disclosure" in logs
    assert "fetchLogs" not in logs
    assert "innerHTML" not in logs
    assert "<script" not in logs
    assert "--surface" not in audit_css
    assert "--border-color" not in audit_css
    assert "var(--admin-workspace-surface)" in audit_css
    assert "var(--admin-workspace-border)" in audit_css
    submission_errors = Path(pages[4]).read_text(encoding="utf-8")
    assert 'class="admin-data-view admin-workspace h-100"' in submission_errors
    assert 'class="admin-data-view__header"' in submission_errors
    assert submission_errors.count("card shadow-sm") == 2


def test_analytics_pages_use_shared_hero_metric_slot():
    macro = Path(
        "mielenosoitukset_fi/templates/admin_V2/macros.html"
    ).read_text(encoding="utf-8")
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/analytics.html",
        "mielenosoitukset_fi/templates/admin_V2/stats.html",
    )

    assert "metric_value=none" in macro
    assert 'class="admin-page-hero__metric"' in macro
    assert "metric_id" in macro
    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "metric_value=" in source
        assert "admin.admin_dashboard" in source
    assert "analytics-hero" not in Path(pages[0]).read_text(encoding="utf-8")
    stats = Path(pages[1]).read_text(encoding="utf-8")
    assert "stats.css" not in stats
    assert "stats-shell" not in stats
    assert 'class="admin-page admin-workspace"' in stats
    assert 'class="admin-workspace-summary"' in stats
    assert 'class="admin-data-view admin-data-view--scrollable"' in stats
    assert "admin_pagination(" in stats
    assert "innerHTML" not in stats


def test_analytics_pages_use_shared_theme_aware_components():
    base = Path("mielenosoitukset_fi/templates/admin_base.html").read_text(
        encoding="utf-8"
    )
    analytics_css = Path(
        "mielenosoitukset_fi/static/css/admin/analytics.css"
    ).read_text(encoding="utf-8")
    pages = (
        Path("mielenosoitukset_fi/templates/admin_V2/analytics.html"),
        Path("mielenosoitukset_fi/templates/admin_V2/per_demo_analytics.html"),
    )

    assert "css/admin/analytics.css" in base
    assert "admin:themechange" in base
    assert "html.light" in analytics_css
    assert "html.dark" in analytics_css
    assert "--admin-chart-text" in analytics_css
    assert "var(--admin-workspace-surface)" in analytics_css
    assert "@media (max-width: 760px)" in analytics_css

    for page in pages:
        source = page.read_text(encoding="utf-8")
        assert "<style" not in source
        assert 'class="admin-page admin-analytics"' in source
        assert "admin-section-card" in source
        assert 'role="img"' in source
        assert "getAdminChartColors" in source
        assert "admin:themechange" in source

    per_demo = pages[1].read_text(encoding="utf-8")
    assert "admin-workspace-summary" in per_demo
    assert "admin-analytics__data-disclosure" in per_demo
    assert "admin-data-view__table" in per_demo
    assert "prefers-reduced-motion: reduce" in per_demo


def test_case_and_merge_pages_use_canonical_hero_navigation():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/cases/all.html",
        "mielenosoitukset_fi/templates/admin_V2/cases/case.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/merge.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source
    for name in pages[1:]:
        assert "back_url=" in Path(name).read_text(encoding="utf-8")
    case_list = Path(pages[0]).read_text(encoding="utf-8")
    assert "case-hero" not in case_list
    assert "aclass=" not in case_list
    case_detail = Path(pages[1]).read_text(encoding="utf-8")
    assert "case-chip" not in case_detail
    assert "admin-status-badge--danger" in case_detail
    assert "admin-status-badge--info" in Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")


def test_case_views_use_shared_workspace_components_without_inline_css():
    case_list = Path(
        "mielenosoitukset_fi/templates/admin_V2/cases/all.html"
    ).read_text(encoding="utf-8")
    case_detail = Path(
        "mielenosoitukset_fi/templates/admin_V2/cases/case.html"
    ).read_text(encoding="utf-8")

    assert "<style" not in case_list
    assert "<style" not in case_detail
    assert "admin-workspace-summary" in case_list
    assert case_list.count("<div><span>") == 4
    assert "admin-filter-chip" in case_list
    assert 'href="{{ url_for(\'admin_case.single_case\'' in case_list
    assert "onclick=\"window.location" not in case_list
    assert "aria-pressed" in case_list
    assert "card.hidden = !visible" in case_list
    assert "admin-detail-layout" in case_detail
    assert case_detail.count("admin-section-card") >= 5
    assert case_detail.count('class="admin-section-card__title"') == 5
    assert "admin-row-actions" in case_detail


def test_demo_command_center_separates_hero_copy_from_operational_context():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/command_center.html"
    ).read_text(encoding="utf-8")

    assert "import admin_page_hero" in template
    assert "admin_page_hero(" in template
    assert "admin-page-hero--stacked" in template
    assert "back_url=" in template
    assert template.index("{% endcall %}") < template.index('class="status-badges admin-row-actions"')
    assert template.index("{% endcall %}") < template.index('class="hero-metadata"')
    for legacy_class in (
        ".hero-card",
        ".hero-header",
        ".hero-title",
        ".hero-subtitle",
        ".hero-links",
        ".hero-link",
    ):
        assert legacy_class not in template
    styles = Path(
        "mielenosoitukset_fi/static/css/admin/demonstrations.css"
    ).read_text(encoding="utf-8")
    assert "<style" not in template
    assert "css/admin/demonstrations.css" in template
    assert "admin-page admin-workspace" in template
    assert "admin-status-badge" in template
    assert template.count("admin-section-card") >= 10
    assert 'type="button" class="action-btn btn' in template
    assert "--admin-workspace-surface" in styles
    assert "light-dark(" not in styles


def test_destructive_confirmations_use_canonical_hero_navigation():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/confirm_delete.html",
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/confirm_delete.html",
        "mielenosoitukset_fi/templates/admin_V2/organizations/confirm_delete.html",
        "mielenosoitukset_fi/templates/admin_V2/user/confirm.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source
        assert "back_url=" in source
        assert "title_id='confirm-title'" in source
        assert source.count("<h1") == 0


def test_specialist_admin_pages_use_canonical_hero_navigation():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/kampanja/list.html",
        "mielenosoitukset_fi/templates/admin_V2/overall_24h_analytics.html",
        "mielenosoitukset_fi/templates/admin_V2/s3/dashboard.html",
        "mielenosoitukset_fi/templates/admin_V2/s3/view_media.html",
        "mielenosoitukset_fi/templates/admin_V2/super_audit/logs.html",
    )

    for name in pages:
        source = Path(name).read_text(encoding="utf-8")
        assert "import admin_page_hero" in source
        assert "admin_page_hero(" in source
        assert "admin.admin_dashboard" in source
    for name in (pages[1], pages[3], pages[4]):
        assert "back_url=" in Path(name).read_text(encoding="utf-8")
    campaign = Path(pages[0]).read_text(encoding="utf-8")
    assert 'class="header' not in campaign
    assert ".header" not in campaign


def test_super_audit_uses_shared_collection_contract():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/super_audit/logs.html"
    ).read_text(encoding="utf-8")
    route = Path(
        "mielenosoitukset_fi/admin/admin_demo_bp.py"
    ).read_text(encoding="utf-8")

    for contract in (
        "admin-page admin-workspace",
        "admin-filter-bar",
        "admin-active-filters",
        "admin-data-view__header admin-result-summary",
        "admin-data-view__viewport",
        "admin-data-view__table",
        "admin-code-block",
        "admin-empty-state",
        "admin_pagination(",
    ):
        assert contract in template

    assert "class=\"card" not in template
    assert "table-responsive" not in template
    assert 'name="limit"' not in template
    assert "<style" not in template
    assert "style=" not in template
    assert '.sort([("timestamp", -1), ("_id", -1)])' in route
    assert '.skip(pagination["slice_start"])' in route
    assert ".limit(per_page)" in route


def test_campaign_collection_uses_shared_admin_components():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/kampanja/list.html"
    ).read_text(encoding="utf-8")
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")

    assert "<style" not in template
    assert "style=" not in template
    assert "admin-workspace-summary" in template
    assert "admin-section-card" in template
    assert "admin-filter-bar" in template
    assert "admin-data-view admin-data-view--scrollable" in template
    assert "admin-data-view__footer admin-pagination" in template
    assert "modal fade admin-modal" in template
    assert "admin-check-row" in template
    assert "bootstrap.Modal.getOrCreateInstance" in template
    assert template.index("bootstrap.Modal.getOrCreateInstance") > template.index(
        "function boot()"
    )
    assert "campaign-modal" not in template
    assert "btn-icon" not in template
    assert ".campaign-filters__grid" in workspace
    assert ".campaign-volunteers .admin-data-view__table" in workspace


def test_every_full_admin_v2_page_uses_canonical_hero_macro():
    pages = []

    for template in Path("mielenosoitukset_fi/templates/admin_V2").rglob("*.html"):
        source = template.read_text(encoding="utf-8")
        if "{% extends" not in source or "{% block main_content %}" not in source:
            continue
        pages.append(template)
        assert "import admin_page_hero" in source, str(template)
        assert "admin_page_hero(" in source, str(template)

    # Exact inventory ratchet: the unreachable legacy recurring form was removed,
    # leaving 51 routed full-page admin templates.
    assert len(pages) == 51
    for locale in ("en", "fi", "sv"):
        catalog = Path(
            f"mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.po"
        ).read_text(encoding="utf-8")
        for message in (
            "Tarkista poistettava mielenosoitus ennen peruuttamatonta toimintoa.",
            "Tarkista poistettava toistuva mielenosoitus ennen peruuttamatonta toimintoa.",
            "Tarkista poistettava organisaatio ennen peruuttamatonta toimintoa.",
            "Tarkista käyttäjätili ja sen rooli ennen peruuttamatonta toimintoa.",
        ):
            assert f'msgid "{message}"' in catalog


def test_full_admin_pages_use_breadcrumbs_and_standard_back_actions():
    from jinja2 import Environment, nodes
    from jinja2.visitor import NodeVisitor

    top_level_without_back = {
        "analytics.html",
        "background_jobs.html",
        "cases/all.html",
        "dashboard.html",
        "demonstrations/dashboard.html",
        "governance/dashboard.html",
        "kampanja/list.html",
        "organizations/dashboard.html",
        "s3/dashboard.html",
        "stats.html",
        "status.html",
        "ui_translations/dashboard.html",
        "user/list.html",
    }

    class HeroCallVisitor(NodeVisitor):
        def __init__(self):
            self.calls = []

        def visit_Call(self, node):
            if isinstance(node.node, nodes.Name) and node.node.name == "admin_page_hero":
                self.calls.append(node)
            self.generic_visit(node)

    def breadcrumb_lengths(node):
        if isinstance(node, (nodes.List, nodes.Tuple)):
            return [len(node.items)]
        if isinstance(node, nodes.CondExpr):
            return breadcrumb_lengths(node.expr1) + breadcrumb_lengths(node.expr2)
        return []

    root = Path("mielenosoitukset_fi/templates/admin_V2")
    environment = Environment()
    seen = set()
    for template in root.rglob("*.html"):
        source = template.read_text(encoding="utf-8")
        if "{% extends" not in source or "{% block main_content %}" not in source:
            continue

        relative = str(template.relative_to(root))
        visitor = HeroCallVisitor()
        visitor.visit(environment.parse(source))
        assert len(visitor.calls) == 1, relative
        call = visitor.calls[0]
        assert len(call.args) >= 4, relative
        lengths = breadcrumb_lengths(call.args[3])
        assert lengths, relative
        if relative == "dashboard.html":
            assert lengths == [0]
        else:
            assert min(lengths) >= 2, relative

        keyword_names = {keyword.key for keyword in call.kwargs}
        if relative in top_level_without_back:
            assert "back_url" not in keyword_names, relative
        else:
            assert "back_url" in keyword_names, relative
        seen.add(relative)

    assert seen >= top_level_without_back


def test_dead_admin_template_copies_and_legacy_sync_actions_are_absent():
    assert not Path(
        "mielenosoitukset_fi/templates/admin_V2/_users_table copy.html"
    ).exists()
    assert not Path(
        "mielenosoitukset_fi/templates/admin_V2/mac_test.html"
    ).exists()
    sync_dashboard = Path(
        "mielenosoitukset_fi/templates/admin_V2/ui_translations/sync_dashboard.html"
    ).read_text(encoding="utf-8")
    assert "admin-page-header__actions" not in sync_dashboard
    assert "admin-row-actions" in sync_dashboard


def test_media_admin_uses_shared_theme_aware_components():
    upload = Path(
        "mielenosoitukset_fi/templates/admin_V2/s3/dashboard.html"
    ).read_text(encoding="utf-8")
    library = Path(
        "mielenosoitukset_fi/templates/admin_V2/s3/view_media.html"
    ).read_text(encoding="utf-8")
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")

    for template in (upload, library):
        assert "<style" not in template
        assert "style=" not in template
        assert "admin_org_control.css" not in template
        assert "form.css" not in template
        assert "table.css" not in template
    assert "admin-form-section" in upload
    assert 'class="admin-form-section__body"' in upload
    assert 'class="admin-form-section__body admin-media-upload"' in library
    assert "admin-media-grid" in library
    assert "admin-media-card__preview" in library
    assert "onclick=" not in library
    assert ".admin-media-card" in workspace
    assert "repeat(auto-fill, minmax(min(100%, 16rem), 1fr))" in workspace
    assert "var(--admin-workspace-surface)" in workspace
    assert "var(--admin-workspace-border)" in workspace


def test_system_status_uses_shared_theme_aware_health_components():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/status.html"
    ).read_text(encoding="utf-8")
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")

    assert "<style" not in template
    assert "prefers-color-scheme" not in template
    assert template.count("style=") == 1
    assert 'style="width:{{ server.disk.used_pct }}%"' in template
    assert 'class="admin-health-grid"' in template
    assert 'class="admin-health-panel' in template
    assert 'class="admin-data-view__viewport"' in template
    assert 'role="progressbar"' in template
    assert ".admin-health-panel" in workspace
    assert ".admin-health-service" in workspace
    assert ".admin-health-errors" in workspace
    assert "var(--admin-workspace-surface)" in workspace
    assert "var(--admin-workspace-border)" in workspace


def test_stats_and_demo_audits_use_shared_data_cues():
    pages = (
        "mielenosoitukset_fi/templates/admin_V2/stats.html",
        "mielenosoitukset_fi/templates/admin_V2/overall_24h_analytics.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/audit_log.html",
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/audit_timeline.html",
    )
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")

    for name in pages:
        assert "<style" not in Path(name).read_text(encoding="utf-8")
    assert "th.sortable::after" in workspace
    assert '.audit-list .list-group-item[data-action="approve_demo"]' in workspace
    assert ".timeline-item::before" in workspace
    assert "var(--admin-workspace-muted)" in workspace
    assert "var(--admin-workspace-border)" in workspace


def test_user_editor_layout_lives_in_shared_admin_components():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/user/edit.html"
    ).read_text(encoding="utf-8")
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")

    assert "<style" not in template
    assert 'class="admin-form admin-user-form"' in template
    assert ".admin-user-form .admin-form-grid" in workspace
    assert ".admin-user-form .permission-list" in workspace
    assert ".admin-user-form :is(.permission-item, .select-all)" in workspace
    assert "var(--admin-workspace-surface-muted)" in workspace
    assert "var(--admin-workspace-border)" in workspace


def test_demo_editor_static_geometry_uses_shared_form_components():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/form.html"
    ).read_text(encoding="utf-8")
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")

    assert "<style" not in template
    assert "style=" not in template
    assert "event_type != 'MARCH'" in template and " hidden" in template
    assert "marchRouteContainer.hidden = typeSelect.value !== 'MARCH'" in template
    assert template.count('class="tags-wrapper admin-token-input"') == 2
    assert "import demo_media_fields" in template
    assert "{{ demo_media_fields(demo) }}" in template
    assert 'class="row g-3 admin-coordinate-fields"' in template
    assert 'class="admin-form-section__header"' in template
    assert 'data-bs-target="#editLinkModal"' in template
    assert 'id="duplicate-demo-btn"' in template
    assert ".admin-token-input:focus-within" in workspace
    assert ':not(.admin-token-input__field), select, textarea)' in workspace
    assert 'input:not(.admin-token-input__field), select, textarea):focus' in workspace
    assert ".access-panel-card .list-group-item" in workspace
    assert "var(--admin-workspace-surface-muted)" in workspace


def test_recurring_editor_static_geometry_uses_shared_form_components():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/_form_v2.html"
    ).read_text(encoding="utf-8")

    assert "style=" not in template
    assert template.count('class="tags-wrapper admin-token-input"') == 2
    assert template.count('class="admin-token-input__field"') == 2
    assert "import demo_media_fields" in template
    assert "{{ demo_media_fields(demo, recurring=true) }}" in template
    assert 'class="main-container admin-editor-richtext"' in template
    assert 'class="admin-editor-spacer" aria-hidden="true"' in template
    assert "weeklyOptions.hidden = freqSelect.value !== 'weekly'" in template
    assert "monthlyOptions.hidden = freqSelect.value !== 'monthly'" in template
    assert "marchRouteContainer.hidden = typeSelect.value !== 'MARCH'" in template


def test_demo_editors_share_the_canonical_media_field_contract():
    partial = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/_media_fields.html"
    ).read_text(encoding="utf-8")

    assert "<style" not in partial
    assert "style=" not in partial
    assert 'class="admin-form-section"' in partial
    assert 'class="admin-form-section__header"' in partial
    assert 'class="admin-form-section__body admin-form-grid"' in partial
    assert 'class="admin-form-image-preview"' in partial
    for field_name in (
        "facebook",
        "slug",
        "cover_picture",
        "cover_picture_file",
        "img",
        "preview_image",
        "gallery_images",
    ):
        assert f'name="{field_name}"' in partial


def test_recurring_collection_uses_shared_filter_data_and_modal_contracts():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/dashboard.html"
    ).read_text(encoding="utf-8")

    assert "<style" not in template
    assert "style=" not in template
    assert 'class="admin-filter-bar"' in template
    assert 'class="admin-data-view admin-data-view--scrollable"' in template
    assert "admin-data-view__header admin-result-summary" in template
    assert 'class="admin-data-view__table"' in template
    assert 'class="admin-data-view__header admin-result-summary"' in template
    assert "filtered_count = mongo.recu_demos.count_documents(filter_query)" in Path(
        "mielenosoitukset_fi/admin/admin_recu_demo_bp.py"
    ).read_text(encoding="utf-8")
    assert '.sort([("date", 1), ("_id", 1)])' in Path(
        "mielenosoitukset_fi/admin/admin_recu_demo_bp.py"
    ).read_text(encoding="utf-8")
    assert "rows.forEach" not in template
    assert 'has_permission("EDIT_RECURRING_DEMO")' in template
    assert 'has_permission("DELETE_RECURRING_DEMO")' in template
    assert "admin-status-badge--success" in template
    assert 'class="admin-empty-state"' in template
    assert 'class="modal fade admin-modal"' in template
    assert "bootstrap.Modal.getOrCreateInstance" in template
    assert "modal-dark" not in template
    assert ".admin-data-view--scrollable .admin-data-view__viewport" in Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")


def test_recurring_collection_uses_shared_pagination_component():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/dashboard.html"
    ).read_text(encoding="utf-8")
    macro = Path(
        "mielenosoitukset_fi/templates/admin_V2/macros.html"
    ).read_text(encoding="utf-8")

    assert "import admin_page_hero, admin_pagination" in template
    assert "admin_pagination(" in template
    assert "client_side=true" not in template
    assert "current_page," in template
    assert "prev_page_url=prev_page_url" in template
    assert "visible_pages=visible_pages" in template
    assert "data-admin-pagination" in macro
    assert "admin-data-view__footer admin-pagination" in macro
    assert "admin-page-size" in macro


def test_background_job_detail_uses_shared_code_and_disclosure_components():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/background_job_detail.html"
    ).read_text(encoding="utf-8")
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")

    assert "<style" not in template
    assert template.count('class="admin-disclosure') == 3
    assert template.count('class="admin-code-block') == 3
    assert "metadata-block" not in template
    assert ".admin-disclosure > summary:focus-visible" in workspace


def test_background_job_collection_uses_shared_workspace_components():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/background_jobs.html"
    ).read_text(encoding="utf-8")
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")
    admin_routes = Path(
        "mielenosoitukset_fi/admin/admin_bp.py"
    ).read_text(encoding="utf-8")
    job_manager = Path(
        "mielenosoitukset_fi/background_jobs/manager.py"
    ).read_text(encoding="utf-8")

    assert "<style" not in template
    assert "style=" not in template
    assert 'class="jobs-container admin-page"' in template
    assert "admin-section-card" in template
    assert "admin-data-view" in template
    assert "admin-filter-bar" in template
    assert "admin-data-view__footer admin-pagination" in template
    assert "admin-empty-state" in template
    assert "admin-status-badge" in template
    assert "admin-code-block" in template
    assert "btn-modern" not in template
    assert ".admin-jobs__layout" in workspace
    assert ".admin-jobs__grid" in workspace
    assert "@media (prefers-reduced-motion: reduce)" in workspace
    assert "total_runs = job_manager.count_runs(selected_job)" in admin_routes
    assert "skip=skip" in admin_routes
    assert '.sort([("started_at", -1), ("_id", -1)])' in job_manager


def test_admin_boolean_controls_do_not_inherit_text_field_geometry():
    workspace = Path("mielenosoitukset_fi/static/css/admin/workspace.css").read_text(
        encoding="utf-8"
    )
    demo_form = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/form.html"
    ).read_text(encoding="utf-8")
    recurring_form = Path(
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/_form_v2.html"
    ).read_text(encoding="utf-8")

    assert ":is(.form-control, .form-select, .form-check-input)" not in workspace
    assert 'input[type="checkbox"].form-check-input' in workspace
    assert 'input[type="radio"].form-check-input' in workspace
    assert ".form-check-input:indeterminate" in workspace
    assert ".form-check-input:focus-visible" in workspace
    for template in (demo_form, recurring_form):
        assert "{% if can_approve_demo|default(false) %}" in template
        assert 'class="admin-check-row"' in template
        assert "data-admin-boolean" in template
        assert 'aria-live="polite"' in template


def test_demo_edit_links_use_the_shared_secure_lifecycle_contract():
    demo_form = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/form.html"
    ).read_text(encoding="utf-8")
    recurring_form = Path(
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/_form_v2.html"
    ).read_text(encoding="utf-8")
    edit_link_modal = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/_edit_link_modal.html"
    ).read_text(encoding="utf-8")
    edit_link_script = Path(
        "mielenosoitukset_fi/static/js/admin_demo_edit_links.js"
    ).read_text(encoding="utf-8")

    assert "import demo_edit_link_modal" in demo_form
    assert "demo_edit_link_modal('editLinkModal'" in demo_form
    assert "modal fade admin-modal" in edit_link_modal
    assert "admin-data-view" in demo_form
    assert 'value="1h"' in edit_link_modal
    assert 'value="24h"' in edit_link_modal
    assert 'value="7d"' in edit_link_modal
    assert 'data-demo-edit-link-generate' in edit_link_modal
    assert 'data-demo-edit-link-copy' in edit_link_modal
    assert 'data-demo-edit-link-send' in edit_link_modal
    assert '"X-CSRF-Token": modalElement.dataset.csrfToken' in edit_link_script
    assert "JSON.stringify({ email: email.value, duration: duration.value })" in edit_link_script
    assert "edit_link: editLink" not in edit_link_script
    assert "generate-edit-link-btn" not in recurring_form
    assert "send_edit_link_email" not in recurring_form


def test_retired_admin_styles_and_templates_do_not_return():
    admin_css = Path("mielenosoitukset_fi/static/css/admin")
    retired_styles = {
        "activities.css",
        "case.css",
        "dash.css",
        "demo_checkbox.css",
        "demo_form.css",
        "recu_dash.css",
        "sidebar_v2.css",
    }

    assert not retired_styles.intersection(path.name for path in admin_css.glob("*.css"))
    assert not Path(
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/_form.html"
    ).exists()

    admin_base = Path("mielenosoitukset_fi/templates/admin_base.html").read_text(
        encoding="utf-8"
    )
    macros = Path("mielenosoitukset_fi/templates/admin_V2/macros.html").read_text(
        encoding="utf-8"
    )
    for stylesheet in retired_styles:
        assert stylesheet not in admin_base
    assert "macro render_table" not in macros
