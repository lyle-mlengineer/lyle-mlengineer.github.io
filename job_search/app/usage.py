"""Usage aggregation for the resources dashboard.

Two sources feed the page, and each job uses exactly one of them:

* ``llm_calls`` — one row per model call, written by the ledger wrapper. This
  drives call counts, the model/skill split and the time series.
* ``runs`` — rolling totals written by the pipeline. A job that finished before
  the ledger existed has no call rows, so its run totals stand in. Jobs with call
  rows ignore their run totals, so nothing is counted twice.

Filtering (search, status, model, skill, window) happens in SQL. The page never
loads more rows than it renders.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from .domain import JOB_STATUSES, SKILL_LABELS
from .models import Company, Job, LlmCall, Run, SearchCall

WINDOWS: tuple[int, ...] = (7, 30, 90, 0)  # 0 means all time
DEFAULT_WINDOW = 30
MAX_ALL_TIME_DAYS = 60
UNATTRIBUTED = "unattributed"


# ---------------------------------------------------------------- filters


@dataclass(frozen=True)
class UsageFilters:
    query: str = ""
    status: str = ""
    model: str = ""
    skill: str = ""
    days: int = DEFAULT_WINDOW
    #: Set by the company page; never comes from the query string.
    company_id: int | None = None

    @property
    def is_filtered(self) -> bool:
        return bool(
            self.query or self.status or self.model or self.skill
            or self.days != DEFAULT_WINDOW
        )

    @property
    def since(self) -> str | None:
        return since_iso(self.days)

    @property
    def window_label(self) -> str:
        return "all time" if self.days <= 0 else f"last {self.days} days"


def since_iso(days: int) -> str | None:
    """Midnight, ``days`` ago, in the ISO-Z format the database stores."""
    if days <= 0:
        return None
    start = datetime.now(UTC) - timedelta(days=days - 1)
    return start.replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_filters(params: Mapping[str, str]) -> UsageFilters:
    """Read the query string without trusting any of it."""

    def text(name: str, limit: int = 120) -> str:
        return (params.get(name) or "").strip()[:limit]

    status = text("status", 30)
    days_raw = text("days", 6)
    try:
        days = int(days_raw) if days_raw else DEFAULT_WINDOW
    except ValueError:
        days = DEFAULT_WINDOW
    if days not in WINDOWS:
        days = DEFAULT_WINDOW
    return UsageFilters(
        query=text("q"),
        status=status if status in JOB_STATUSES else "",
        model=text("model"),
        skill=text("skill", 60),
        days=days,
    )


# ---------------------------------------------------------------- report types


@dataclass
class JobUsage:
    job: Job
    calls: int = 0
    cached: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    search_calls: int = 0
    search_cost_usd: float = 0.0
    cached_searches: int = 0
    runs: int = 0
    last_at: str | None = None
    from_ledger: bool = True
    #: share of the filtered total, and bar width relative to the largest row.
    share: float = 0.0
    width: float = 0.0

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    @property
    def total_cost(self) -> float:
        return round(self.cost_usd + self.search_cost_usd, 6)


@dataclass
class DailyPoint:
    day: str
    label: str
    calls: int = 0
    tokens: int = 0
    searches: int = 0
    #: LLM plus web-search spend for the day.
    cost_usd: float = 0.0
    share: float = 0.0
    width: float = 0.0


@dataclass
class Slice:
    key: str
    label: str
    sub: str = ""
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    share: float = 0.0
    width: float = 0.0

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass
class Totals:
    calls: int = 0
    cached: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    search_calls: int = 0
    search_cost_usd: float = 0.0
    cached_searches: int = 0
    runs: int = 0
    jobs: int = 0
    avg_latency_ms: int = 0

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    @property
    def total_cost(self) -> float:
        return round(self.cost_usd + self.search_cost_usd, 6)

    @property
    def cost_per_job(self) -> float:
        return round(self.total_cost / self.jobs, 6) if self.jobs else 0.0

    @property
    def cost_per_call(self) -> float:
        return round(self.total_cost / self.calls, 6) if self.calls else 0.0


@dataclass
class UsageReport:
    filters: UsageFilters
    totals: Totals = field(default_factory=Totals)
    rows: list[JobUsage] = field(default_factory=list)
    daily: list[DailyPoint] = field(default_factory=list)
    skills: list[Slice] = field(default_factory=list)
    models: list[Slice] = field(default_factory=list)
    searches: list[Slice] = field(default_factory=list)
    model_options: list[str] = field(default_factory=list)
    skill_options: list[str] = field(default_factory=list)
    legacy_jobs: int = 0
    idle_jobs: int = 0
    #: Usage exists at all, ignoring the current filters.
    has_any_data: bool = False
    #: Usage exists inside the current filters.
    has_data: bool = False


# ---------------------------------------------------------------- queries


_CALL_SUMS = (
    func.count(LlmCall.id),
    func.coalesce(func.sum(case((LlmCall.cached.is_(True), 1), else_=0)), 0),
    func.coalesce(func.sum(LlmCall.tokens_in), 0),
    func.coalesce(func.sum(LlmCall.tokens_out), 0),
    func.coalesce(func.sum(LlmCall.cost_usd), 0.0),
    func.coalesce(func.avg(LlmCall.latency_ms), 0),
)

_RUN_SUMS = (
    func.coalesce(func.sum(Run.tokens_in), 0),
    func.coalesce(func.sum(Run.tokens_out), 0),
    func.coalesce(func.sum(Run.cost_usd), 0.0),
    func.max(Run.created_at),
)

_SEARCH_SUMS = (
    func.count(SearchCall.id),
    func.coalesce(func.sum(case((SearchCall.cached.is_(True), 1), else_=0)), 0),
    func.coalesce(func.sum(SearchCall.cost_usd), 0.0),
    func.coalesce(func.sum(SearchCall.results), 0),
    func.max(SearchCall.created_at),
)


def build_report(db: Session, filters: UsageFilters) -> UsageReport:
    jobs = _scoped_jobs(db, filters)
    report = UsageReport(
        filters=filters,
        model_options=_distinct(db, LlmCall.model),
        skill_options=_distinct(db, LlmCall.skill),
        has_any_data=_any_activity(db),
    )
    if not jobs:
        return report

    job_ids = [job.id for job in jobs]
    clauses = _call_clauses(filters, job_ids)
    search_clauses = _search_clauses(filters, job_ids)
    legacy_allowed = not (filters.model or filters.skill)

    per_job_calls = _per_job_calls(db, clauses)
    per_job_searches = _per_job_searches(db, search_clauses)
    run_counts = _run_counts(db, job_ids)
    per_job_runs = _per_job_runs(db, filters, job_ids) if legacy_allowed else {}

    totals = Totals()
    rows: list[JobUsage] = []
    for job in jobs:
        usage = _job_usage(
            job,
            per_job_calls.get(job.id),
            per_job_runs.get(job.id),
            per_job_searches.get(job.id),
            run_counts.get(job.id, 0),
        )
        rows.append(usage)
        totals.calls += usage.calls
        totals.cached += usage.cached
        totals.tokens_in += usage.tokens_in
        totals.tokens_out += usage.tokens_out
        totals.cost_usd += usage.cost_usd
        totals.search_calls += usage.search_calls
        totals.cached_searches += usage.cached_searches
        totals.search_cost_usd += usage.search_cost_usd
        totals.runs += usage.runs
        if usage.calls or usage.tokens or usage.search_calls:
            totals.jobs += 1
        if not usage.from_ledger:
            report.legacy_jobs += 1

    totals.cost_usd = round(totals.cost_usd, 6)
    totals.search_cost_usd = round(totals.search_cost_usd, 6)
    totals.avg_latency_ms = _avg_latency(db, clauses)

    rows.sort(key=lambda row: (row.total_cost, row.tokens), reverse=True)
    _apply_shares(
        rows,
        lambda row: row.total_cost,
        lambda row: row.tokens + row.search_calls,
    )

    report.totals = totals
    report.rows = rows
    report.idle_jobs = sum(1 for row in rows if not (row.calls or row.tokens or row.search_calls))
    report.daily = _daily_series(db, clauses, search_clauses, filters.days)
    report.skills = _skill_slices(db, clauses)
    report.models = _model_slices(db, clauses)
    report.searches = _search_slices(db, search_clauses)
    report.has_data = bool(
        totals.calls or totals.tokens or totals.search_calls or report.legacy_jobs
    )
    return report


def _any_activity(db: Session) -> bool:
    """Has anything ever been generated? Used to tell "no data" from "no match"."""
    for table in (LlmCall, SearchCall, Run):
        if db.scalar(select(table.id).limit(1)) is not None:
            return True
    return False


def _scoped_jobs(db: Session, filters: UsageFilters) -> list[Job]:
    stmt = select(Job).options(joinedload(Job.company)).order_by(Job.updated_at.desc())
    if filters.company_id is not None:
        stmt = stmt.where(Job.company_id == filters.company_id)
    if filters.status:
        stmt = stmt.where(Job.status == filters.status)
    if filters.query:
        needle = f"%{filters.query}%"
        stmt = stmt.outerjoin(Company, Job.company_id == Company.id).where(
            or_(Job.title.ilike(needle), Company.name.ilike(needle))
        )
    return list(db.execute(stmt).unique().scalars().all())


def _distinct(db: Session, column) -> list[str]:
    values = db.scalars(select(column).where(column.is_not(None)).distinct().order_by(column)).all()
    return [value for value in values if value]


def _call_clauses(filters: UsageFilters, job_ids: Iterable[int]) -> list:
    clauses: list = [LlmCall.job_id.in_(list(job_ids))]
    if filters.since:
        clauses.append(LlmCall.created_at >= filters.since)
    if filters.model:
        clauses.append(LlmCall.model == filters.model)
    if filters.skill:
        clauses.append(LlmCall.skill == filters.skill)
    return clauses


def _search_clauses(filters: UsageFilters, job_ids: Iterable[int]) -> list:
    """Searches have no model, so only the skill filter applies to them."""
    clauses: list = [SearchCall.job_id.in_(list(job_ids))]
    if filters.since:
        clauses.append(SearchCall.created_at >= filters.since)
    if filters.skill:
        clauses.append(SearchCall.skill == filters.skill)
    return clauses


def _per_job_calls(db: Session, clauses: list) -> dict[int, tuple]:
    stmt = (
        select(LlmCall.job_id, *_CALL_SUMS, func.max(LlmCall.created_at))
        .where(*clauses)
        .group_by(LlmCall.job_id)
    )
    return {int(row[0]): tuple(row[1:]) for row in db.execute(stmt).all() if row[0] is not None}


def _per_job_runs(db: Session, filters: UsageFilters, job_ids: list[int]) -> dict[int, tuple]:
    stmt = select(Run.job_id, *_RUN_SUMS).where(Run.job_id.in_(job_ids)).group_by(Run.job_id)
    if filters.since:
        stmt = stmt.where(Run.created_at >= filters.since)
    return {int(row[0]): tuple(row[1:]) for row in db.execute(stmt).all()}


def _run_counts(db: Session, job_ids: list[int]) -> dict[int, int]:
    stmt = select(Run.job_id, func.count(Run.id)).where(Run.job_id.in_(job_ids)).group_by(Run.job_id)
    return {int(row[0]): int(row[1]) for row in db.execute(stmt).all()}


def _per_job_searches(db: Session, clauses: list) -> dict[int, tuple]:
    stmt = (
        select(SearchCall.job_id, *_SEARCH_SUMS)
        .where(*clauses)
        .group_by(SearchCall.job_id)
    )
    return {int(row[0]): tuple(row[1:]) for row in db.execute(stmt).all() if row[0] is not None}


def _job_usage(
    job: Job,
    calls: tuple | None,
    runs: tuple | None,
    searches: tuple | None,
    run_count: int,
) -> JobUsage:
    search_calls, cached_searches, search_cost, _results, search_last = (
        searches if searches is not None else (0, 0, 0.0, 0, None)
    )
    base = {
        "job": job,
        "runs": run_count,
        "search_calls": int(search_calls),
        "cached_searches": int(cached_searches),
        "search_cost_usd": round(float(search_cost), 6),
    }
    if calls is not None:
        count, cached, tokens_in, tokens_out, cost, _latency, last_at = calls
        return JobUsage(
            **base,
            calls=int(count),
            cached=int(cached),
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            cost_usd=round(float(cost), 6),
            last_at=_latest(last_at, search_last),
            from_ledger=True,
        )
    if runs is not None:
        tokens_in, tokens_out, cost, last_at = runs
        return JobUsage(
            **base,
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            cost_usd=round(float(cost), 6),
            last_at=_latest(last_at, search_last),
            from_ledger=False,
        )
    return JobUsage(**base, last_at=search_last, from_ledger=False)


def _latest(*stamps: str | None) -> str | None:
    return max((stamp for stamp in stamps if stamp), default=None)


def _avg_latency(db: Session, clauses: list) -> int:
    value = db.scalar(
        select(func.coalesce(func.avg(LlmCall.latency_ms), 0)).where(*clauses)
    )
    return int(value or 0)


def _daily_series(
    db: Session, clauses: list, search_clauses: list, days: int
) -> list[DailyPoint]:
    day = func.substr(LlmCall.created_at, 1, 10).label("day")
    stmt = (
        select(
            day,
            func.count(LlmCall.id),
            func.coalesce(func.sum(LlmCall.tokens_in + LlmCall.tokens_out), 0),
            func.coalesce(func.sum(LlmCall.cost_usd), 0.0),
        )
        .where(*clauses)
        .group_by(day)
        .order_by(day)
    )
    seen = {str(row[0]): row for row in db.execute(stmt).all()}

    search_day = func.substr(SearchCall.created_at, 1, 10).label("day")
    search_stmt = (
        select(
            search_day,
            func.count(SearchCall.id),
            func.coalesce(func.sum(SearchCall.cost_usd), 0.0),
        )
        .where(*search_clauses)
        .group_by(search_day)
    )
    searched = {str(row[0]): row for row in db.execute(search_stmt).all()}

    if days > 0:
        today = datetime.now(UTC).date()
        dates = [(today - timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]
    else:
        dates = sorted(set(seen) | set(searched))[-MAX_ALL_TIME_DAYS:]

    points = []
    for stamp in dates:
        llm = seen.get(stamp)
        search = searched.get(stamp)
        points.append(
            DailyPoint(
                day=stamp,
                label=_day_label(stamp),
                calls=int(llm[1]) if llm else 0,
                tokens=int(llm[2]) if llm else 0,
                searches=int(search[1]) if search else 0,
                cost_usd=round(
                    (float(llm[3]) if llm else 0.0) + (float(search[2]) if search else 0.0), 6
                ),
            )
        )
    _apply_shares(
        points,
        lambda point: point.cost_usd,
        lambda point: point.tokens + point.searches,
    )
    return points


def _skill_slices(db: Session, clauses: list) -> list[Slice]:
    stmt = (
        select(LlmCall.skill, *_CALL_SUMS)
        .where(*clauses)
        .group_by(LlmCall.skill)
        .order_by(func.coalesce(func.sum(LlmCall.cost_usd), 0.0).desc())
    )
    slices = [
        Slice(
            key=row[0] or UNATTRIBUTED,
            label=SKILL_LABELS.get(row[0], row[0]) if row[0] else "Unattributed",
            calls=int(row[1]),
            tokens_in=int(row[3]),
            tokens_out=int(row[4]),
            cost_usd=round(float(row[5]), 6),
        )
        for row in db.execute(stmt).all()
    ]
    _apply_shares(slices, lambda item: item.cost_usd, lambda item: item.tokens)
    return slices


def _model_slices(db: Session, clauses: list) -> list[Slice]:
    stmt = (
        select(LlmCall.model, LlmCall.provider, *_CALL_SUMS)
        .where(*clauses)
        .group_by(LlmCall.model, LlmCall.provider)
        .order_by(func.coalesce(func.sum(LlmCall.cost_usd), 0.0).desc())
    )
    slices = [
        Slice(
            key=row[0],
            label=row[0],
            sub=row[1],
            calls=int(row[2]),
            tokens_in=int(row[4]),
            tokens_out=int(row[5]),
            cost_usd=round(float(row[6]), 6),
        )
        for row in db.execute(stmt).all()
    ]
    _apply_shares(slices, lambda item: item.cost_usd, lambda item: item.tokens)
    return slices


def _apply_shares(items: list, cost, volume) -> None:
    """Fill in each item's share of the total and its bar width.

    Bars are scaled by cost, falling back to a volume measure (tokens or calls)
    when every cost is zero — a fake provider, DuckDuckGo or an unpriced model
    would otherwise flatten the chart.
    """
    total_cost = sum(cost(item) for item in items)
    total_volume = sum(volume(item) for item in items)
    use_cost = total_cost > 0
    values = [cost(item) if use_cost else volume(item) for item in items]
    base = total_cost if use_cost else total_volume
    peak = max(values) if values else 0.0
    for item, value in zip(items, values, strict=True):
        item.share = round(100 * value / base, 1) if base else 0.0
        item.width = round(100 * value / peak, 1) if peak else 0.0


def _search_slices(db: Session, clauses: list) -> list[Slice]:
    stmt = (
        select(SearchCall.provider, *_SEARCH_SUMS)
        .where(*clauses)
        .group_by(SearchCall.provider)
        .order_by(func.count(SearchCall.id).desc())
    )
    slices = [
        Slice(
            key=row[0],
            label=row[0],
            sub="per query",
            calls=int(row[1]),
            cost_usd=round(float(row[3]), 6),
        )
        for row in db.execute(stmt).all()
    ]
    _apply_shares(slices, lambda item: item.cost_usd, lambda item: item.calls)
    return slices


def job_resources(
    db: Session, job_id: int, *, limit: int = 200
) -> tuple[Totals, list[LlmCall], list[SearchCall]]:
    """Call totals plus the most recent model calls and searches for one job."""
    totals = Totals()
    clauses = [LlmCall.job_id == job_id]
    row = db.execute(select(*_CALL_SUMS).where(*clauses)).one()
    count, cached, tokens_in, tokens_out, cost, latency = row
    totals.calls = int(count)
    totals.cached = int(cached)
    totals.tokens_in = int(tokens_in)
    totals.tokens_out = int(tokens_out)
    totals.cost_usd = round(float(cost), 6)
    totals.avg_latency_ms = int(latency or 0)

    search_clauses = [SearchCall.job_id == job_id]
    searched = db.execute(select(*_SEARCH_SUMS).where(*search_clauses)).one()
    totals.search_calls = int(searched[0])
    totals.cached_searches = int(searched[1])
    totals.search_cost_usd = round(float(searched[2]), 6)

    calls = list(
        db.scalars(
            select(LlmCall)
            .where(*clauses)
            .order_by(LlmCall.created_at.desc(), LlmCall.id.desc())
            .limit(limit)
        ).all()
    )
    searches = list(
        db.scalars(
            select(SearchCall)
            .where(*search_clauses)
            .order_by(SearchCall.created_at.desc(), SearchCall.id.desc())
            .limit(limit)
        ).all()
    )
    return totals, calls, searches


def _day_label(stamp: str) -> str:
    try:
        return datetime.strptime(stamp, "%Y-%m-%d").strftime("%d %b")
    except ValueError:
        return stamp
