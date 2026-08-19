"""Tests verifying that UptimeRobot rate-limit exemption is IP-based and cannot be spoofed.

The security model:
- get_client_ip() only trusts CF-Connecting-IP when remote_addr is a Cloudflare IP.
- An attacker cannot fake remote_addr at the application layer (it's TCP).
- Therefore, spoofing CF-Connecting-IP with a UptimeRobot IP from a non-Cloudflare
  source has no effect — get_client_ip() returns the attacker's real IP.
"""

import pytest
from flask import Flask

from mielenosoitukset_fi.utils.request_ip import get_client_ip
from mielenosoitukset_fi.utils.uptimerobot_ips import is_uptimerobot_ip


# --- Known UptimeRobot IPs from the official list ---
KNOWN_UR_IP_V4 = "5.161.75.7"
KNOWN_UR_IP_V6 = "2607:ff68:107::33"


class TestIsUptimerobotIp:
    def test_known_ipv4_returns_true(self):
        assert is_uptimerobot_ip(KNOWN_UR_IP_V4) is True

    def test_known_ipv6_returns_true(self):
        assert is_uptimerobot_ip(KNOWN_UR_IP_V6) is True

    def test_random_ip_returns_false(self):
        assert is_uptimerobot_ip("203.0.113.99") is False

    def test_none_returns_false(self):
        assert is_uptimerobot_ip(None) is False

    def test_empty_string_returns_false(self):
        assert is_uptimerobot_ip("") is False

    def test_invalid_ip_returns_false(self):
        assert is_uptimerobot_ip("not-an-ip") is False


class TestGetClientIpIpResolution:
    def test_direct_connection_uses_remote_addr(self):
        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": KNOWN_UR_IP_V4}):
            assert get_client_ip() == KNOWN_UR_IP_V4

    def test_spoofed_cf_header_from_non_cloudflare_ignored(self):
        """Attacker spoofs CF-Connecting-IP with a UptimeRobot IP, but their
        REMOTE_ADDR is not a Cloudflare IP. get_client_ip() must ignore the
        spoofed header and return the attacker's real IP."""
        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={"CF-Connecting-IP": KNOWN_UR_IP_V4},
            environ_base={"REMOTE_ADDR": "203.0.113.99"},
        ):
            assert get_client_ip() == "203.0.113.99"

    def test_legitimate_cloudflare_header_accepted(self):
        """When remote_addr IS a Cloudflare IP, CF-Connecting-IP is trusted.
        If that header contains a UptimeRobot IP, the exemption applies."""
        cloudflare_ip = "172.64.10.20"  # in 172.64.0.0/13
        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={"CF-Connecting-IP": KNOWN_UR_IP_V4},
            environ_base={"REMOTE_ADDR": cloudflare_ip},
        ):
            assert get_client_ip() == KNOWN_UR_IP_V4

    def test_spoofed_cf_header_with_normal_ip_uses_real_ip(self):
        """Attacker spoofs CF-Connecting-IP with a normal (non-UR) IP from
        non-Cloudflare. The spoofed header is ignored."""
        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={"CF-Connecting-IP": "198.51.100.99"},
            environ_base={"REMOTE_ADDR": "203.0.113.99"},
        ):
            assert get_client_ip() == "203.0.113.99"

    def test_x_forwarded_for_from_non_cloudflare_ignored(self):
        """X-Forwarded-For is not used by get_client_ip() at all when
        remote_addr is not Cloudflare. Only CF-Connecting-IP matters."""
        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={
                "X-Forwarded-For": KNOWN_UR_IP_V4,
                "CF-Connecting-IP": KNOWN_UR_IP_V4,
            },
            environ_base={"REMOTE_ADDR": "203.0.113.99"},
        ):
            assert get_client_ip() == "203.0.113.99"


class TestRateLimitExemptionCannotBeSpoofed:
    """Integration-style tests: simulate the rate-limit filter logic."""

    def _make_exempt_check(self):
        """Replicate the rate-limit filter from app.py."""
        from mielenosoitukset_fi.utils.uptimerobot_ips import is_uptimerobot_ip as _is_ur

        def _exempt(client_ip):
            return _is_ur(client_ip)
        return _exempt

    def test_direct_attacker_not_exempt(self):
        exempt = self._make_exempt_check()
        with Flask(__name__).test_request_context("/", environ_base={"REMOTE_ADDR": "203.0.113.99"}):
            ip = get_client_ip()
            assert exempt(ip) is False

    def test_spoofed_cf_with_ur_ip_attacker_not_exempt(self):
        """Attacker tries to spoof CF-Connecting-IP with a UptimeRobot IP
        from a non-Cloudflare source. Must not get exemption."""
        exempt = self._make_exempt_check()
        with Flask(__name__).test_request_context(
            "/",
            headers={"CF-Connecting-IP": KNOWN_UR_IP_V4},
            environ_base={"REMOTE_ADDR": "203.0.113.99"},
        ):
            ip = get_client_ip()
            assert exempt(ip) is False

    def test_legitimate_cf_proxied_ur_ip_gets_exempt(self):
        """A real request from UptimeRobot through Cloudflare should be exempt."""
        exempt = self._make_exempt_check()
        with Flask(__name__).test_request_context(
            "/",
            headers={"CF-Connecting-IP": KNOWN_UR_IP_V4},
            environ_base={"REMOTE_ADDR": "172.64.10.20"},
        ):
            ip = get_client_ip()
            assert ip == KNOWN_UR_IP_V4
            assert exempt(ip) is True

    def test_direct_ur_ip_gets_exempt(self):
        """If somehow UptimeRobot connects directly (no CF), their real IP
        in remote_addr should still get exemption."""
        exempt = self._make_exempt_check()
        with Flask(__name__).test_request_context("/", environ_base={"REMOTE_ADDR": KNOWN_UR_IP_V4}):
            ip = get_client_ip()
            assert ip == KNOWN_UR_IP_V4
            assert exempt(ip) is True
