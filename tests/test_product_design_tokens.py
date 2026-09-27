from pathlib import Path


PRODUCT_TOKENS = Path("mielenosoitukset_fi/static/css/product-tokens.css")
PUBLIC_WORKSPACE = Path("mielenosoitukset_fi/static/css/user-workspace.css")
ADMIN_WORKSPACE = Path("mielenosoitukset_fi/static/css/admin/workspace.css")


def test_public_and_admin_shells_load_product_tokens_before_components():
    public_base = Path("mielenosoitukset_fi/templates/base.html").read_text(
        encoding="utf-8"
    )
    admin_base = Path("mielenosoitukset_fi/templates/admin_base.html").read_text(
        encoding="utf-8"
    )

    assert public_base.index("css/product-tokens.css") < public_base.index(
        "css/user-workspace.css"
    )
    assert admin_base.index("css/product-tokens.css") < admin_base.index(
        "css/admin/workspace.css"
    )


def test_product_tokens_cover_shared_semantic_roles():
    tokens = PRODUCT_TOKENS.read_text(encoding="utf-8")

    for token in (
        "--product-primary",
        "--product-action-bg",
        "--product-on-action",
        "--product-canvas",
        "--product-surface",
        "--product-border",
        "--product-text",
        "--product-text-muted",
        "--product-success",
        "--product-danger",
        "--product-shadow",
    ):
        assert token in tokens


def test_public_components_do_not_depend_on_admin_scoped_tokens():
    public = PUBLIC_WORKSPACE.read_text(encoding="utf-8")

    assert "--admin-workspace-" not in public
    assert "var(--product-primary)" in public
    assert "var(--product-surface)" in public
    assert "var(--product-text)" in public


def test_admin_component_api_aliases_the_product_foundation():
    admin = ADMIN_WORKSPACE.read_text(encoding="utf-8")

    aliases = {
        "--admin-workspace-blue": "--product-primary",
        "--admin-workspace-blue-dark": "--product-primary-strong",
        "--admin-workspace-blue-soft": "--product-primary-soft",
        "--admin-workspace-primary-bg": "--product-action-bg",
        "--admin-workspace-primary-hover": "--product-action-hover",
        "--admin-workspace-on-primary": "--product-on-action",
        "--admin-workspace-orange": "--product-accent",
        "--admin-workspace-orange-strong": "--product-accent-strong",
        "--admin-workspace-orange-soft": "--product-accent-soft",
        "--admin-workspace-surface": "--product-surface",
        "--admin-workspace-surface-muted": "--product-surface-muted",
        "--admin-workspace-border": "--product-border",
        "--admin-workspace-text": "--product-text",
        "--admin-workspace-muted": "--product-text-muted",
        "--admin-workspace-success": "--product-success",
        "--admin-workspace-success-soft": "--product-success-soft",
        "--admin-workspace-danger": "--product-danger",
        "--admin-workspace-danger-soft": "--product-danger-soft",
        "--admin-workspace-shadow": "--product-shadow",
    }
    for admin_token, product_token in aliases.items():
        assert f"{admin_token}: var({product_token});" in admin
