import logging
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from app.pipeline.ingest.fetch import Fetcher

logger = logging.getLogger(__name__)


@dataclass
class RobotsPolicy:
    """What a host allows us to crawl.

    A missing or broken robots.txt is treated as "allow", which matches the
    behaviour of every mainstream crawler. A parsed file is enforced per URL.
    """

    user_agent: str
    status: str = "missing"  # ok | missing | error
    parser: RobotFileParser | None = None
    crawl_delay: float = 0.0
    sitemaps: list[str] = field(default_factory=list)

    def can_fetch(self, url: str) -> bool:
        if self.parser is None:
            return True
        return self.parser.can_fetch(self.user_agent, url)

    def wait(self) -> None:
        delay = min(max(self.crawl_delay, 0.0), 2.0)
        if delay:
            time.sleep(delay)


def site_root(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return f"{parsed.scheme}://{parsed.netloc}"


def fetch_robots(fetcher: Fetcher, url: str, user_agent: str) -> RobotsPolicy:
    root = site_root(url)
    robots_url = f"{root}/robots.txt"
    try:
        status_code, body = fetcher.fetch_text(robots_url)
    except Exception as exc:  # noqa: BLE001 - robots is advisory, never fatal
        logger.info("robots.txt unavailable for %s: %s", root, exc)
        return RobotsPolicy(user_agent=user_agent, status="error")

    if status_code >= 400 or not body.strip():
        return RobotsPolicy(user_agent=user_agent, status="missing")

    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.parse(body.splitlines())
    except Exception as exc:  # noqa: BLE001 - malformed file means no policy
        logger.info("robots.txt malformed for %s: %s", root, exc)
        return RobotsPolicy(user_agent=user_agent, status="error")

    delay = parser.crawl_delay(user_agent) or 0.0
    return RobotsPolicy(
        user_agent=user_agent,
        status="ok",
        parser=parser,
        crawl_delay=float(delay),
        sitemaps=list(parser.site_maps() or []),
    )
