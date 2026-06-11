from flask import Flask

from mielenosoitukset_fi.utils.request_ip import get_client_ip


def test_client_ip_uses_socket_address_without_proxy_header():
    app = Flask(__name__)
    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "203.0.113.10"}):
        assert get_client_ip() == "203.0.113.10"


def test_client_ip_accepts_cloudflare_header_from_cloudflare_proxy():
    app = Flask(__name__)
    with app.test_request_context(
        "/",
        headers={"CF-Connecting-IP": "203.0.113.10"},
        environ_base={"REMOTE_ADDR": "172.64.10.20"},
    ):
        assert get_client_ip() == "203.0.113.10"


def test_client_ip_rejects_spoofed_cloudflare_header_from_direct_request():
    app = Flask(__name__)
    with app.test_request_context(
        "/",
        headers={"CF-Connecting-IP": "198.51.100.99"},
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
    ):
        assert get_client_ip() == "203.0.113.10"


def test_client_ip_rejects_invalid_cloudflare_header():
    app = Flask(__name__)
    with app.test_request_context(
        "/",
        headers={"CF-Connecting-IP": "not-an-ip"},
        environ_base={"REMOTE_ADDR": "172.64.10.20"},
    ):
        assert get_client_ip() == "172.64.10.20"


def test_client_ip_prefers_real_ipv6_when_cloudflare_pseudo_ipv4_is_enabled():
    app = Flask(__name__)
    with app.test_request_context(
        "/",
        headers={
            "CF-Connecting-IP": "240.0.0.10",
            "CF-Connecting-IPv6": "2001:db8::10",
        },
        environ_base={"REMOTE_ADDR": "2606:4700::100"},
    ):
        assert get_client_ip() == "2001:db8::10"
