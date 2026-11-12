"""Trusted real-client IP extraction for proxied requests."""

from functools import lru_cache
from ipaddress import ip_address, ip_network

from flask import has_request_context, request


# Published by Cloudflare at https://www.cloudflare.com/ips/
CLOUDFLARE_NETWORKS = (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22",
    "103.31.4.0/22", "141.101.64.0/18", "108.162.192.0/18",
    "190.93.240.0/20", "188.114.96.0/20", "197.234.240.0/22",
    "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32",
    "2405:b500::/32", "2405:8100::/32", "2a06:98c0::/29",
    "2c0f:f248::/32",
)


@lru_cache(maxsize=1)
def _cloudflare_networks():
    return tuple(ip_network(network) for network in CLOUDFLARE_NETWORKS)


def _valid_ip(value):
    if not value:
        return None
    try:
        return str(ip_address(value.strip()))
    except ValueError:
        return None


def _is_cloudflare_ip(value):
    parsed = _valid_ip(value)
    if not parsed:
        return False
    address = ip_address(parsed)
    return any(address in network for network in _cloudflare_networks())


def get_client_ip(default="0.0.0.0", request=None):
    """Return the visitor IP, trusting Cloudflare's header only from Cloudflare.

    If ``request`` is provided, use it instead of the Flask global ``request``.
    This allows the function to be used outside a request context (e.g. in tests).
    """
    from flask import has_request_context, request as flask_request

    if request is None:
        if not has_request_context():
            return default
        request = flask_request

    proxy_ip = _valid_ip(request.environ.get("REMOTE_ADDR"))
    cloudflare_ip = (
        _valid_ip(request.headers.get("CF-Connecting-IPv6"))
        or _valid_ip(request.headers.get("CF-Connecting-IP"))
    )
    if cloudflare_ip and _is_cloudflare_ip(proxy_ip):
        return cloudflare_ip
    return proxy_ip or default
