"""HTTP fetching with SSRF protection, robots.txt and hard size limits.

The fetcher is the trust boundary: everything it returns is untrusted text from
a stranger's website. It refuses non-HTTP schemes, resolves hostnames and rejects
any address that is not globally routable, re-checks every redirect hop, and
streams with a byte cap so a hostile page cannot exhaust memory.

robots.txt is enforced for crawled links (company research). A URL the user
pasted themselves is still fetched even if robots disallows it, matching how a
browser would behave for a user-initiated visit.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from .extract import ExtractedPage, extract_page

USER_AGENT = "SkipperBot/0.1 (+personal job-search agent; respects robots.txt)"
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
HTML_TYPES = ("text/html", "application/xhtml+xml")


class FetchError(RuntimeError):
    """Any failure the caller should surface as 'this link could not be read'."""


class UnsafeUrlError(FetchError):
    """The URL points at a loopback, private, or otherwise non-public address."""


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    content_type: str
    page: ExtractedPage
    html: str = field(repr=False, default="")

    @property
    def title(self) -> str:
        return self.page.title

    @property
    def text(self) -> str:
        return self.page.text

    @property
    def ok(self) -> bool:
        return self.page.ok


def resolve_host(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [str(info[4][0]) for info in infos]


def assert_public_url(url: str, *, resolver=resolve_host) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError(f"Unsupported URL scheme: {parsed.scheme or '(none)'}")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("URLs with embedded credentials are not allowed.")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise UnsafeUrlError("URL has no hostname.")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise UnsafeUrlError(f"Refusing to fetch local host: {host}")

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        _assert_global(literal, host)
        return

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = resolver(host, port)
    except OSError as exc:
        raise FetchError(f"Could not resolve {host}: {exc}") from exc
    if not addresses:
        raise FetchError(f"Could not resolve {host}.")
    for address in addresses:
        _assert_global(ipaddress.ip_address(address), host)


def _assert_global(address: ipaddress._BaseAddress, host: str) -> None:
    if not address.is_global:
        raise UnsafeUrlError(f"Refusing to fetch non-public address {address} for {host}.")


class Fetcher:
    def __init__(
        self,
        *,
        max_bytes: int = 3_000_000,
        timeout_s: float = 20.0,
        max_redirects: int = 5,
        client: httpx.Client | None = None,
        resolver=resolve_host,
        ua: str = USER_AGENT,
    ) -> None:
        self.max_bytes = max_bytes
        self.timeout_s = timeout_s
        self.max_redirects = max_redirects
        self.resolver = resolver
        self.ua = ua
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout_s,
            follow_redirects=False,
            headers={"User-Agent": ua, "Accept": "text/html,application/xhtml+xml"},
        )
        self._robots: dict[str, RobotFileParser | None] = {}

    # ------------------------------------------------------------------ fetch

    def fetch(self, url: str, *, respect_robots: bool = False) -> FetchResult:
        current = url
        response: httpx.Response | None = None
        html = ""

        for _hop in range(self.max_redirects + 1):
            assert_public_url(current, resolver=self.resolver)
            if respect_robots and not self._robots_allowed(current):
                raise FetchError(f"robots.txt disallows fetching {current}")

            try:
                with self._client.stream(
                    "GET",
                    current,
                    timeout=self.timeout_s,
                    headers={"User-Agent": self.ua},
                ) as stream:
                    if stream.status_code in REDIRECT_STATUSES:
                        location = stream.headers.get("location")
                        if not location:
                            raise FetchError(f"HTTP {stream.status_code} without a Location header.")
                        current = urljoin(current, location)
                        continue

                    if stream.status_code >= 400:
                        raise FetchError(f"HTTP {stream.status_code} for {current}")
                    if stream.status_code != 200:
                        raise FetchError(f"Unexpected HTTP {stream.status_code} for {current}")

                    content_type = stream.headers.get("content-type", "").split(";")[0].strip().lower()
                    if not any(content_type.startswith(kind) for kind in HTML_TYPES):
                        raise FetchError(f"Not an HTML page ({content_type or 'unknown type'}).")

                    chunks: list[bytes] = []
                    total = 0
                    for chunk in stream.iter_bytes():
                        total += len(chunk)
                        if total > self.max_bytes:
                            raise FetchError(
                                f"Page is larger than the {self.max_bytes // 1000} KB limit."
                            )
                        chunks.append(chunk)
                    html = b"".join(chunks).decode(stream.encoding or "utf-8", errors="replace")
                    response = stream
                    break
            except httpx.TimeoutException as exc:
                raise FetchError(f"Timed out fetching {current}.") from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"Could not fetch {current}: {exc}") from exc
        else:
            raise FetchError(f"Too many redirects (limit {self.max_redirects}).")

        if response is None:  # pragma: no cover - loop always breaks or raises
            raise FetchError(f"Could not fetch {url}.")

        page = extract_page(html, current)
        return FetchResult(
            url=url,
            final_url=current,
            status=response.status_code,
            content_type=response.headers.get("content-type", ""),
            page=page,
            html=html,
        )

    # ----------------------------------------------------------------- robots

    def _robots_allowed(self, url: str) -> bool:
        parser = self._robots_for(url)
        if parser is None:
            return True
        return parser.can_fetch(self.ua, url)

    def _robots_for(self, url: str) -> RobotFileParser | None:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._robots:
            return self._robots[origin]

        parser: RobotFileParser | None = None
        try:
            response = self._client.get(
                origin + "/robots.txt",
                timeout=min(10.0, self.timeout_s),
                headers={"User-Agent": self.ua},
            )
            if response.status_code == 200 and len(response.content) < 200_000:
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
            elif response.status_code == 401:
                parser = RobotFileParser()
                parser.disallow_all = True
        except httpx.HTTPError:
            parser = None
        self._robots[origin] = parser
        return parser

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
