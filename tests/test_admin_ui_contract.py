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
    style_block_allowlist = {
        "_users_table.html": ("7d2b36160b76de688cd17b79eaf781963a3d1cc932d63a2b846c99b997f08053",),
        "cities/index.html": ("3d27343693df99175c8ed03679c15a78ce9c031ece3180a1b89872f9f08f7d37",),
        "dashboard.html": ("b1946f48e192ef2949b4d5e8eed75989f46d50b07dd9eef9a2a0efead658f5f9",),
        "demonstrations/command_center.html": ("417fb57cd87fd0c1b3ff0068cd7dfed92acfc0e4cce58123d93fed347b22c345",),
        "demonstrations/dashboard.html": ("9f97a12eac3420515d3a71429da50bc5ebb130a30770a9b56c46221418abf622",),
        "demonstrations/translations_editor.html": ("a3ee7ec76c2da45da1fbcf3124c923ea93a1cdadd86b2d38767902ce696bf8c0",),
        "logs.html": ("6264f7731e696f127a64ac39c798b23f723d9be595b6d35a0495ba39a2ee4b2e",),
        "user/list.html": ("f0d93944cfcdd563188ba2482f2bcb08498697463f1d527b84754380128a8def",),
    }
    style_attribute_allowlist = {
        "demonstrations/form.html": ("0207b1097d91cbd2db5ca3c9c2d4f4a078f88bba9b76d54e47851d88f540f363",),
        "demonstrations/translations_editor.html": ("e5c4a4d9ceace908e840babc9cd36852b4c748b35a4c9ac632f1173443872df0",),
        "macros.html": ("c51ec35a4e6a31e3a4433913317b3297d7bb5300f543c35c378b1b9c00f7ec78",),
        "recu_demonstrations/_form.html": (
            "d0466aa33fa8061c7b805e27bd8d9b4aaa06cb2e332e3345f920d05c6a7f66b6",
            "2919379184ff8ef35568d89a979d13162e07c3613ff8fa65ea5b2826c8e87abc",
            "72370f42eb03e9339d67d4860ac05f87660c3e706ca83a42f3d1075c04b56894",
        ),
        "recu_demonstrations/_form_v2.html": (
            "002dc26c478b3c97f65ba75a55b91f5295a1e5eea02ef881a2f207cea85bec8e",
            "734200fc2335cf7f0bae5ea327eba62129ac34fece3f87b24bc4e8d196f6c25c",
            "65d1f1c3d796b67c546f79a4ead052fa02225543c4de918ce3bd247873c31651",
            "65d1f1c3d796b67c546f79a4ead052fa02225543c4de918ce3bd247873c31651",
            "5aa7a955a93e19ad6860cb2e79597f05760177b82c38c7413ab2b4f1f08eba84",
            "8b7a90798426bdbc75fd87ba4774f38bcd8cf595792137a0c3b76d1b494bfe6b",
            "ae7bf87ad3042f63e29ce68b156d3152d713fd714f7299dafb0026c2ad10ff00",
            "0207b1097d91cbd2db5ca3c9c2d4f4a078f88bba9b76d54e47851d88f540f363",
            "5aa7a955a93e19ad6860cb2e79597f05760177b82c38c7413ab2b4f1f08eba84",
            "8b7a90798426bdbc75fd87ba4774f38bcd8cf595792137a0c3b76d1b494bfe6b",
        ),
        "status.html": ("fd8a8ba5d1e16400323c06329adb6dbbf433e7ecc6be7d3e3041c29a6228720f",),
        "tag_form.html": ("d26dfcb508ff2a1ba922197b16b68b4d75dbb728205f0e2908ec3704db94d7c8",),
    }
    root = Path("mielenosoitukset_fi/templates/admin_V2")
    actual_blocks = {}
    actual_attributes = {}

    for template in root.rglob("*.html"):
        source = template.read_text(encoding="utf-8")
        relative = str(template.relative_to(root))
        blocks = re.findall(
            r"<style(?:\s[^>]*)?>(.*?)</style>", source, flags=re.IGNORECASE | re.DOTALL
        )
        attributes = [
            match.group(2)
            for match in re.finditer(
                r'''style\s*=\s*(["'])(.*?)\1''',
                source,
                flags=re.IGNORECASE | re.DOTALL,
            )
        ]
        if blocks:
            actual_blocks[relative] = tuple(
                hashlib.sha256(value.encode()).hexdigest() for value in blocks
            )
        if attributes:
            actual_attributes[relative] = tuple(
                hashlib.sha256(value.encode()).hexdigest() for value in attributes
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

    assert "admin_page_hero(" in edit
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
    assert "admin-data-view__footer admin-pagination" in dashboard
    assert "admin-pagination__info" in dashboard
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
    stats_css = Path(
        "mielenosoitukset_fi/static/css/admin/stats.css"
    ).read_text(encoding="utf-8")
    assert ".stats-hero" not in stats_css


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
    assert template.index("{% endcall %}") < template.index('class="status-badges"')
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
    assert ".demo-command-center {\n    padding: 1rem;\n    display: grid;\n    gap: 1.5rem;" in template


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
    assert template.count("style=") == 1
    assert "event_type != 'MARCH'" in template
    assert template.count('class="tags-wrapper admin-token-input"') == 2
    assert 'class="admin-form-image-preview"' in template
    assert 'class="row g-3 admin-coordinate-fields"' in template
    assert 'class="admin-form-section__header"' in template
    assert 'data-bs-target="#editLinkModal"' in template
    assert 'id="duplicate-demo-btn"' in template
    assert ".admin-token-input:focus-within" in workspace
    assert ':not(.admin-token-input__field), select, textarea)' in workspace
    assert 'input:not(.admin-token-input__field), select, textarea):focus' in workspace
    assert ".access-panel-card .list-group-item" in workspace
    assert "var(--admin-workspace-surface-muted)" in workspace


def test_recurring_collection_uses_shared_filter_data_and_modal_contracts():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/recu_demonstrations/dashboard.html"
    ).read_text(encoding="utf-8")

    assert "<style" not in template
    assert "style=" not in template
    assert 'class="admin-filter-bar"' in template
    assert 'class="admin-data-view admin-data-view--scrollable"' in template
    assert 'class="admin-data-view__table"' in template
    assert "admin-status-badge--success" in template
    assert 'class="admin-empty-state"' in template
    assert 'class="modal fade admin-modal"' in template
    assert "bootstrap.Modal.getOrCreateInstance" in template
    assert "modal-dark" not in template
    assert ".admin-data-view--scrollable .admin-data-view__viewport" in Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")


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

    assert "modal fade admin-modal" in demo_form
    assert "admin-data-view" in demo_form
    assert 'value="1h"' in demo_form
    assert 'value="24h"' in demo_form
    assert 'value="7d"' in demo_form
    assert "'X-CSRF-Token': editLinkCsrf" in demo_form
    assert "JSON.stringify({email, duration: duration.value})" in demo_form
    assert "JSON.stringify({ email, edit_link: editLink })" not in demo_form
    assert "generate-edit-link-btn" not in recurring_form
    assert "send_edit_link_email" not in recurring_form
