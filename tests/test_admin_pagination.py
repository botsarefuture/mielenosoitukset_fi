from flask import Flask

from mielenosoitukset_fi.admin.pagination import (
    build_admin_pagination,
    parse_admin_pagination,
)


def test_parse_admin_pagination_normalizes_invalid_values():
    assert parse_admin_pagination({}) == (1, 20)
    assert parse_admin_pagination({"page": "-8", "per_page": "999"}) == (1, 20)
    assert parse_admin_pagination({"page": "oops", "per_page": "50"}) == (1, 50)


def test_build_admin_pagination_clamps_page_and_preserves_query_state():
    app = Flask(__name__)

    @app.get("/items")
    def items():
        return ""

    with app.test_request_context():
        pagination = build_admin_pagination(
            "items",
            total_count=41,
            page=99,
            per_page=20,
            query_args={"search": "climate", "state": "pending", "empty": ""},
        )

    assert pagination["current_page"] == 3
    assert pagination["total_pages"] == 3
    assert pagination["range_start"] == 41
    assert pagination["range_end"] == 41
    assert pagination["slice_start"] == 40
    assert pagination["slice_end"] == 60
    assert pagination["next_page"] is None
    assert pagination["prev_page"] == 2
    assert "search=climate" in pagination["prev_page_url"]
    assert "state=pending" in pagination["prev_page_url"]
    assert "per_page=20" in pagination["prev_page_url"]
    assert "page=2" in pagination["prev_page_url"]
    assert "empty=" not in pagination["prev_page_url"]


def test_build_admin_pagination_exposes_an_empty_first_page():
    app = Flask(__name__)

    @app.get("/items")
    def items():
        return ""

    with app.test_request_context():
        pagination = build_admin_pagination(
            "items", total_count=0, page=4, per_page=20
        )

    assert pagination["current_page"] == 1
    assert pagination["total_pages"] == 1
    assert pagination["range_start"] == 0
    assert pagination["range_end"] == 0
    assert pagination["prev_page"] is None
    assert pagination["next_page"] is None
