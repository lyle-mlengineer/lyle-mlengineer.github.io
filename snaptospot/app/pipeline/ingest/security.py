import ipaddress
import socket
from urllib.parse import urlparse

from app.config import get_settings
from app.pipeline.ingest.errors import UnsafeURLError

_ALLOWED_SCHEMES = {"http", "https"}


def is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_url_allowed(url: str) -> None:
    """Reject non-http(s) URLs and hosts that resolve to private address space.

    This is a basic SSRF guard. DNS rebinding is not fully prevented; the
    production deployment should also filter at the egress proxy.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Only http and https URLs are allowed (got {parsed.scheme!r})")
    if not parsed.hostname:
        raise UnsafeURLError("URL has no hostname")

    settings = get_settings()
    if settings.ssrf_allow_private:
        return

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        infos = socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve {parsed.hostname}") from exc

    for info in infos:
        address = info[4][0]
        if not is_public_ip(address):
            raise UnsafeURLError(f"Refusing to crawl private address {address}")
