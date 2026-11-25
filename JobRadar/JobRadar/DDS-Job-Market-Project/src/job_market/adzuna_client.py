"""Secure, reusable Adzuna Job Search API client for JobRadar.

Supports India's Adzuna endpoint, sequential pagination, timeouts, bounded
retries with backoff, HTTP 429 Retry-After handling, credential redaction,
and structured job extraction while preserving raw response payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Iterator, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from .database import PROJECT_ROOT


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AdzunaError(Exception):
    """Base exception for all Adzuna client errors."""


class AdzunaConfigError(AdzunaError):
    """Raised when client configuration is missing or invalid."""


class AdzunaAPIError(AdzunaError):
    """Base exception for network, HTTP, or protocol errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        sanitized_url: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.sanitized_url = sanitized_url
        super().__init__(message)


class AdzunaHTTPError(AdzunaAPIError):
    """Raised for non-successful HTTP status codes (e.g. 400, 401, 403, 404)."""


class AdzunaRateLimitError(AdzunaHTTPError):
    """Raised when HTTP 429 rate limit is encountered and retries are exhausted."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        sanitized_url: str | None = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, status_code=429, sanitized_url=sanitized_url)


class AdzunaTimeoutError(AdzunaAPIError):
    """Raised when an API request times out or suffers a transport failure."""


class AdzunaMalformedResponseError(AdzunaAPIError):
    """Raised when the API returns unparseable or schema-violating responses."""


class AdzunaMaxRetriesExceededError(AdzunaAPIError):
    """Raised when bounded retries are exhausted across transient failures."""


class AdzunaBudgetExhaustedError(AdzunaError):
    """Raised when an active request budget or limiter halts execution."""


# ---------------------------------------------------------------------------
# Sanitization & Helpers
# ---------------------------------------------------------------------------

def sanitize_url(url: str) -> str:
    """Mask sensitive query parameters (app_id, app_key) in a URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        sanitized_pairs: list[tuple[str, str]] = []
        for k, v in query_pairs:
            if k.lower() in {"app_id", "app_key", "key", "password", "secret", "token"}:
                sanitized_pairs.append((k, "***"))
            else:
                sanitized_pairs.append((k, v))
        sanitized_query = urlencode(sanitized_pairs)
        return urlunparse(parsed._replace(query=sanitized_query))
    except Exception:
        clean = re.sub(r"(app_id=)[^&]+", r"\1***", url, flags=re.IGNORECASE)
        clean = re.sub(r"(app_key=)[^&]+", r"\1***", clean, flags=re.IGNORECASE)
        return clean


def redact_text(text: str, secrets: list[str]) -> str:
    """Replace literal occurrences of secrets in text and sanitize URLs."""
    if not text:
        return ""
    result = text
    for secret in secrets:
        if secret and len(secret) >= 4:
            result = result.replace(secret, "***")
    return sanitize_url(result)


def parse_retry_after(header_value: str | None, default_seconds: float = 1.0) -> float:
    """Parse HTTP Retry-After header as integer seconds or RFC 2822 date."""
    if not header_value:
        return default_seconds
    header_str = header_value.strip()
    try:
        seconds = float(header_str)
        return max(0.0, seconds)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(header_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        diff = (dt - now).total_seconds()
        return max(0.0, diff)
    except Exception:
        return default_seconds


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdzunaConfig:
    """Configuration settings for the Adzuna API client."""

    app_id: str
    app_key: str
    country: str = "in"
    base_url: str = "https://api.adzuna.com/v1/api/jobs"
    timeout_seconds: float = 10.0
    max_retries: int = 3
    backoff_factor: float = 0.5
    results_per_page: int = 20
    max_retry_after: float = 60.0

    def __post_init__(self) -> None:
        if not self.app_id or not str(self.app_id).strip():
            raise AdzunaConfigError("ADZUNA_APP_ID must be a non-empty string.")
        if not self.app_key or not str(self.app_key).strip():
            raise AdzunaConfigError("ADZUNA_APP_KEY must be a non-empty string.")
        if self.timeout_seconds <= 0:
            raise AdzunaConfigError("timeout_seconds must be positive.")
        if self.max_retries < 0:
            raise AdzunaConfigError("max_retries must be non-negative.")
        if self.results_per_page <= 0:
            raise AdzunaConfigError("results_per_page must be positive.")

    def __repr__(self) -> str:
        return (
            f"AdzunaConfig(app_id='***', app_key='***', country={self.country!r}, "
            f"base_url={self.base_url!r}, timeout_seconds={self.timeout_seconds}, "
            f"max_retries={self.max_retries}, results_per_page={self.results_per_page})"
        )

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        env_file: Path | str | None = None,
    ) -> AdzunaConfig:
        """Load configuration from environment variables or .env file."""
        merged_env: dict[str, str] = {}

        # 1. Read .env file if present
        file_path = Path(env_file) if env_file else PROJECT_ROOT / ".env"
        if file_path.is_file():
            try:
                for line in file_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        merged_env[k.strip()] = v.strip().strip("'\"")
            except Exception:
                pass

        # 2. Overlay system environment variables
        merged_env.update(os.environ)

        # 3. Overlay caller-provided dictionary
        if env is not None:
            merged_env.update(env)

        app_id = merged_env.get("ADZUNA_APP_ID", "").strip()
        app_key = merged_env.get("ADZUNA_APP_KEY", "").strip()

        if not app_id:
            raise AdzunaConfigError("Missing required environment variable: ADZUNA_APP_ID")
        if not app_key:
            raise AdzunaConfigError("Missing required environment variable: ADZUNA_APP_KEY")

        country = merged_env.get("ADZUNA_COUNTRY", "in").strip() or "in"
        base_url = merged_env.get("ADZUNA_BASE_URL", "https://api.adzuna.com/v1/api/jobs").strip()
        timeout = float(merged_env.get("ADZUNA_TIMEOUT_SECONDS", "10.0"))
        max_retries = int(merged_env.get("ADZUNA_MAX_RETRIES", "3"))
        results_per_page = int(merged_env.get("ADZUNA_RESULTS_PER_PAGE", "20"))

        return cls(
            app_id=app_id,
            app_key=app_key,
            country=country,
            base_url=base_url,
            timeout_seconds=timeout,
            max_retries=max_retries,
            results_per_page=results_per_page,
        )


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdzunaJob:
    """Structured job posting record parsed from an Adzuna search result."""

    id: str
    title: str
    description: str
    company_name: str | None = None
    location_display_name: str | None = None
    location_area: tuple[str, ...] = ()
    salary_min: float | None = None
    salary_max: float | None = None
    salary_is_predicted: bool | None = None
    contract_time: str | None = None
    contract_type: str | None = None
    redirect_url: str | None = None
    category_tag: str | None = None
    category_label: str | None = None
    created: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    raw_record: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdzunaJob:
        if not isinstance(data, dict):
            raise AdzunaMalformedResponseError("Job record must be a JSON object dictionary.")

        raw_id = data.get("id")
        job_id = str(raw_id).strip() if raw_id is not None else ""
        if not job_id:
            raise AdzunaMalformedResponseError("Job record missing mandatory 'id' field.")

        title = str(data.get("title") or "").strip()
        description = str(data.get("description") or "").strip()

        company = data.get("company")
        company_name = company.get("display_name") if isinstance(company, dict) else None

        location = data.get("location")
        loc_display = None
        loc_area: list[str] = []
        if isinstance(location, dict):
            loc_display = location.get("display_name")
            area = location.get("area")
            if isinstance(area, list):
                loc_area = [str(a) for a in area if a is not None]

        def _to_float(val: Any) -> float | None:
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        salary_min = _to_float(data.get("salary_min"))
        salary_max = _to_float(data.get("salary_max"))

        pred_val = data.get("salary_is_predicted")
        salary_is_predicted = None
        if pred_val is not None:
            if isinstance(pred_val, str):
                salary_is_predicted = pred_val.strip() in {"1", "true", "True"}
            else:
                salary_is_predicted = bool(pred_val)

        category = data.get("category")
        cat_tag = None
        cat_label = None
        if isinstance(category, dict):
            cat_tag = category.get("tag")
            cat_label = category.get("label")

        return cls(
            id=job_id,
            title=title,
            description=description,
            company_name=company_name,
            location_display_name=loc_display,
            location_area=tuple(loc_area),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_is_predicted=salary_is_predicted,
            contract_time=data.get("contract_time"),
            contract_type=data.get("contract_type"),
            redirect_url=data.get("redirect_url"),
            category_tag=cat_tag,
            category_label=cat_label,
            created=data.get("created"),
            latitude=_to_float(data.get("latitude")),
            longitude=_to_float(data.get("longitude")),
            raw_record=data,
        )


@dataclass(frozen=True)
class AdzunaPage:
    """Preserves raw page response alongside extracted structured job records."""

    page: int
    total_count: int
    results: list[AdzunaJob]
    raw_json: str
    raw_payload: dict[str, Any]
    http_status: int = 200
    content_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.content_sha256 and self.raw_json:
            object.__setattr__(
                self,
                "content_sha256",
                hashlib.sha256(self.raw_json.encode("utf-8")).hexdigest(),
            )


# ---------------------------------------------------------------------------
# Adzuna API Client
# ---------------------------------------------------------------------------

class AdzunaClient:
    """Secure, reusable Adzuna API client for India and international endpoints."""

    def __init__(
        self,
        config: AdzunaConfig,
        *,
        opener: Any | None = None,
        sleep_fn: Callable[[float], None] | None = None,
        logger: logging.Logger | None = None,
        request_hook: Callable[[], Any] | None = None,
    ) -> None:
        self.config = config
        self._opener = opener
        self._sleep = sleep_fn if sleep_fn is not None else time.sleep
        self._logger = logger or logging.getLogger("job_market.adzuna_client")
        self.request_hook = request_hook

    def _sanitize(self, text: str) -> str:
        return redact_text(text, [self.config.app_id, self.config.app_key])

    def build_url(self, page: int) -> str:
        if page < 1:
            raise ValueError(f"Page number must be >= 1, got {page}")
        return f"{self.config.base_url.rstrip('/')}/{self.config.country}/search/{page}"

    def build_params(
        self,
        *,
        what: str | None = None,
        where: str | None = None,
        results_per_page: int | None = None,
        **extra_params: Any,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "app_id": self.config.app_id,
            "app_key": self.config.app_key,
            "results_per_page": results_per_page or self.config.results_per_page,
            "content-type": "application/json",
        }
        if what:
            params["what"] = what
        if where:
            params["where"] = where
        for k, v in extra_params.items():
            if v is not None:
                params[k] = v
        return params

    def build_sanitized_url(self, url: str, params: dict[str, Any]) -> str:
        safe_params = dict(params)
        safe_params["app_id"] = "***"
        safe_params["app_key"] = "***"
        return f"{url}?{urlencode(safe_params)}"

    def _execute_http_request(
        self, url: str, params: dict[str, Any]
    ) -> tuple[int, bytes, dict[str, str]]:
        if getattr(self, "request_hook", None) is not None:
            self.request_hook()

        query_string = urlencode(params)
        full_url = f"{url}?{query_string}"
        sanitized_url = self.build_sanitized_url(url, params)

        req = Request(
            full_url,
            headers={
                "User-Agent": "JobRadar-AdzunaClient/1.0",
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            if self._opener is not None:
                resp = self._opener.open(req, timeout=self.config.timeout_seconds)
            else:
                resp = urlopen(req, timeout=self.config.timeout_seconds)

            status = getattr(resp, "status", getattr(resp, "code", 200))
            body = resp.read() if hasattr(resp, "read") else b""
            headers = dict(resp.headers.items()) if hasattr(resp, "headers") else {}
            if hasattr(resp, "close"):
                resp.close()
            return status, body, headers
        except HTTPError as err:
            status = err.code
            body = err.read() if hasattr(err, "read") else b""
            headers = dict(err.headers.items()) if hasattr(err, "headers") else {}
            if hasattr(err, "close"):
                err.close()
            return status, body, headers
        except (TimeoutError, URLError, OSError) as err:
            clean_err = self._sanitize(str(err))
            raise AdzunaTimeoutError(
                f"Request to {sanitized_url} failed with network/timeout error: {clean_err}",
                sanitized_url=sanitized_url,
            ) from None

    def fetch_page(
        self,
        page: int = 1,
        *,
        what: str | None = None,
        where: str | None = None,
        results_per_page: int | None = None,
        **extra_params: Any,
    ) -> AdzunaPage:
        """Fetch a single page with request timeouts and bounded retries."""
        url = self.build_url(page)
        params = self.build_params(
            what=what, where=where, results_per_page=results_per_page, **extra_params
        )
        sanitized_url = self.build_sanitized_url(url, params)

        retry = 0
        while True:
            try:
                status, body, headers = self._execute_http_request(url, params)
            except AdzunaTimeoutError as err:
                if retry < self.config.max_retries:
                    retry += 1
                    backoff = self.config.backoff_factor * (2 ** (retry - 1))
                    self._logger.warning(
                        "Timeout on %s; retrying attempt %d/%d after %.2fs",
                        sanitized_url,
                        retry,
                        self.config.max_retries,
                        backoff,
                    )
                    self._sleep(backoff)
                    continue
                raise AdzunaMaxRetriesExceededError(
                    f"Max retries ({self.config.max_retries}) exceeded due to timeout on {sanitized_url}",
                    sanitized_url=sanitized_url,
                ) from err

            # 2xx Success
            if 200 <= status < 300:
                break

            # 429 Rate Limiting
            if status == 429:
                retry_after_hdr = headers.get("Retry-After") or headers.get("retry-after")
                retry_after = parse_retry_after(
                    retry_after_hdr,
                    default_seconds=self.config.backoff_factor * (2 ** retry),
                )
                if retry_after > self.config.max_retry_after:
                    raise AdzunaRateLimitError(
                        f"Rate limit exceeded (HTTP 429) on {sanitized_url}; "
                        f"Retry-After ({retry_after:.1f}s) exceeds max allowed wait ({self.config.max_retry_after}s)",
                        retry_after=retry_after,
                        sanitized_url=sanitized_url,
                    )
                if retry < self.config.max_retries:
                    retry += 1
                    self._logger.warning(
                        "Rate limited (HTTP 429) on %s; sleeping for %.2fs before retry %d/%d",
                        sanitized_url,
                        retry_after,
                        retry,
                        self.config.max_retries,
                    )
                    self._sleep(retry_after)
                    continue
                raise AdzunaRateLimitError(
                    f"Rate limit exceeded (HTTP 429) on {sanitized_url}; exhausted {self.config.max_retries} retries",
                    retry_after=retry_after,
                    sanitized_url=sanitized_url,
                )

            # 5xx Server Errors (transient)
            if 500 <= status < 600:
                if retry < self.config.max_retries:
                    retry += 1
                    backoff = self.config.backoff_factor * (2 ** (retry - 1))
                    self._logger.warning(
                        "Server error (HTTP %d) on %s; retrying attempt %d/%d after %.2fs",
                        status,
                        sanitized_url,
                        retry,
                        self.config.max_retries,
                        backoff,
                    )
                    self._sleep(backoff)
                    continue
                raise AdzunaMaxRetriesExceededError(
                    f"Max retries ({self.config.max_retries}) exceeded on {sanitized_url} (HTTP {status})",
                    status_code=status,
                    sanitized_url=sanitized_url,
                )

            # Non-retryable 4xx client errors
            clean_body = self._sanitize(body.decode("utf-8", errors="replace"))[:300]
            raise AdzunaHTTPError(
                f"Adzuna API returned HTTP {status} on {sanitized_url}: {clean_body}",
                status_code=status,
                sanitized_url=sanitized_url,
            )

        # Parse & validate payload
        raw_text = body.decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as err:
            clean_text = self._sanitize(raw_text[:200])
            raise AdzunaMalformedResponseError(
                f"Adzuna API returned malformed JSON on {sanitized_url}: {clean_text}",
                status_code=status,
                sanitized_url=sanitized_url,
            ) from err

        if not isinstance(payload, dict):
            raise AdzunaMalformedResponseError(
                f"Adzuna API top-level response must be a JSON object, got {type(payload).__name__}",
                status_code=status,
                sanitized_url=sanitized_url,
            )

        if "results" not in payload or not isinstance(payload["results"], list):
            raise AdzunaMalformedResponseError(
                f"Adzuna API response missing 'results' list on {sanitized_url}",
                status_code=status,
                sanitized_url=sanitized_url,
            )

        total_count = int(payload.get("count") or 0)
        jobs: list[AdzunaJob] = []
        for idx, item in enumerate(payload["results"]):
            try:
                job = AdzunaJob.from_dict(item)
                jobs.append(job)
            except Exception as item_err:
                self._logger.warning(
                    "Skipping malformed job item at index %d on page %d: %s",
                    idx,
                    page,
                    self._sanitize(str(item_err)),
                )

        return AdzunaPage(
            page=page,
            total_count=total_count,
            results=jobs,
            raw_json=raw_text,
            raw_payload=payload,
            http_status=status,
        )

    def paginate(
        self,
        start_page: int = 1,
        max_pages: int | None = None,
        max_results: int | None = None,
        *,
        what: str | None = None,
        where: str | None = None,
        results_per_page: int | None = None,
        **extra_params: Any,
    ) -> Iterator[AdzunaPage]:
        """Sequentially yield AdzunaPage objects until exhaustion or limits reached."""
        if start_page < 1:
            raise ValueError(f"start_page must be >= 1, got {start_page}")
        if max_pages is not None and max_pages < 1:
            return

        current_page = start_page
        pages_yielded = 0
        total_jobs_yielded = 0
        rpp = results_per_page or self.config.results_per_page

        while True:
            page = self.fetch_page(
                current_page,
                what=what,
                where=where,
                results_per_page=rpp,
                **extra_params,
            )

            yield page
            pages_yielded += 1
            total_jobs_yielded += len(page.results)

            if len(page.results) == 0:
                break
            if page.total_count > 0 and (current_page * rpp) >= page.total_count:
                break
            if max_pages is not None and pages_yielded >= max_pages:
                break
            if max_results is not None and total_jobs_yielded >= max_results:
                break

            current_page += 1
