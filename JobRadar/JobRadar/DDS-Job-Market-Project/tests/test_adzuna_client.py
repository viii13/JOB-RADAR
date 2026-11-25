"""Unit tests for the Adzuna API client in JobRadar."""

from __future__ import annotations

import io
import json
import logging
import sys
import unittest
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.adzuna_client import (
    AdzunaClient,
    AdzunaConfig,
    AdzunaConfigError,
    AdzunaHTTPError,
    AdzunaJob,
    AdzunaMalformedResponseError,
    AdzunaMaxRetriesExceededError,
    AdzunaPage,
    AdzunaRateLimitError,
    AdzunaTimeoutError,
    parse_retry_after,
    redact_text,
    sanitize_url,
)


class MockHTTPResponse:
    """Mock urllib response object."""

    def __init__(
        self,
        status: int = 200,
        body: bytes = b"{}",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.code = status
        self._body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body


class MockOpener:
    """Mock OpenerDirector that returns pre-configured responses or raises errors."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[Any] = []

    def open(self, request: Any, timeout: float = 10.0) -> Any:
        self.calls.append({"request": request, "timeout": timeout})
        if not self.outcomes:
            raise RuntimeError("MockOpener ran out of configured outcomes.")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def sample_adzuna_payload(
    jobs_count: int = 2,
    total_count: int = 10,
    prefix: str = "job",
) -> dict[str, Any]:
    """Generate a realistic Adzuna job search response payload."""
    results = []
    for i in range(1, jobs_count + 1):
        results.append({
            "id": f"{prefix}-{i}",
            "title": f"Software Engineer {i}",
            "description": f"Exciting tech role number {i} with Python and SQL.",
            "company": {"display_name": f"TechCorp {i}"},
            "location": {
                "display_name": "Bengaluru, Karnataka",
                "area": ["India", "Karnataka", "Bengaluru"],
            },
            "salary_min": 1200000.0 + (i * 100000),
            "salary_max": 2000000.0 + (i * 100000),
            "salary_is_predicted": "0",
            "contract_time": "full_time",
            "contract_type": "permanent",
            "redirect_url": f"https://www.adzuna.in/land/ad/{prefix}-{i}",
            "category": {"tag": "it-jobs", "label": "IT Jobs"},
            "created": "2026-02-14T10:00:00Z",
            "latitude": 12.9716,
            "longitude": 77.5946,
        })
    return {
        "__class": "Adzuna::API::Response::JobSearchResults",
        "count": total_count,
        "mean": 1600000.0,
        "results": results,
    }


class AdzunaConfigTests(unittest.TestCase):
    """Tests for configuration validation and environment loading."""

    def test_missing_app_id_raises_config_error(self) -> None:
        with self.assertRaises(AdzunaConfigError):
            AdzunaConfig(app_id="", app_key="valid-key")

    def test_missing_app_key_raises_config_error(self) -> None:
        with self.assertRaises(AdzunaConfigError):
            AdzunaConfig(app_id="valid-id", app_key="")

    def test_invalid_parameters_raise_config_error(self) -> None:
        with self.assertRaises(AdzunaConfigError):
            AdzunaConfig(app_id="id", app_key="key", timeout_seconds=-1.0)
        with self.assertRaises(AdzunaConfigError):
            AdzunaConfig(app_id="id", app_key="key", max_retries=-1)
        with self.assertRaises(AdzunaConfigError):
            AdzunaConfig(app_id="id", app_key="key", results_per_page=0)

    def test_from_env_loads_successfully(self) -> None:
        env_dict = {
            "ADZUNA_APP_ID": "test-env-id",
            "ADZUNA_APP_KEY": "test-env-key",
            "ADZUNA_COUNTRY": "in",
            "ADZUNA_TIMEOUT_SECONDS": "15.0",
            "ADZUNA_MAX_RETRIES": "2",
            "ADZUNA_RESULTS_PER_PAGE": "50",
        }
        config = AdzunaConfig.from_env(env=env_dict)
        self.assertEqual(config.app_id, "test-env-id")
        self.assertEqual(config.app_key, "test-env-key")
        self.assertEqual(config.country, "in")
        self.assertEqual(config.timeout_seconds, 15.0)
        self.assertEqual(config.max_retries, 2)
        self.assertEqual(config.results_per_page, 50)

    def test_from_env_missing_keys_raises_error(self) -> None:
        with self.assertRaises(AdzunaConfigError):
            AdzunaConfig.from_env(env={"ADZUNA_APP_KEY": "key-only"}, env_file=Path("non_existent_env"))
        with self.assertRaises(AdzunaConfigError):
            AdzunaConfig.from_env(env={"ADZUNA_APP_ID": "id-only"}, env_file=Path("non_existent_env"))

    def test_repr_and_str_mask_credentials(self) -> None:
        config = AdzunaConfig(app_id="sensitive-app-id", app_key="super-secret-key")
        repr_str = repr(config)
        self.assertNotIn("sensitive-app-id", repr_str)
        self.assertNotIn("super-secret-key", repr_str)
        self.assertIn("***", repr_str)


class AdzunaSanitizationTests(unittest.TestCase):
    """Tests for URL masking and credential redacting helpers."""

    def test_sanitize_url_masks_query_parameters(self) -> None:
        raw_url = "https://api.adzuna.com/v1/api/jobs/in/search/1?app_id=myid123&app_key=secretkey456&what=python"
        clean = sanitize_url(raw_url)
        self.assertNotIn("myid123", clean)
        self.assertNotIn("secretkey456", clean)
        self.assertIn("app_id=%2A%2A%2A", clean)
        self.assertIn("app_key=%2A%2A%2A", clean)
        self.assertIn("what=python", clean)

    def test_redact_text_masks_literal_secrets(self) -> None:
        secrets = ["sensitive-id-99", "secret-password-xyz"]
        text = "Failed connecting with sensitive-id-99 using secret-password-xyz token"
        redacted = redact_text(text, secrets)
        self.assertNotIn("sensitive-id-99", redacted)
        self.assertNotIn("secret-password-xyz", redacted)
        self.assertIn("***", redacted)

    def test_parse_retry_after_integer_seconds(self) -> None:
        self.assertEqual(parse_retry_after("15"), 15.0)
        self.assertEqual(parse_retry_after(" 30 "), 30.0)

    def test_parse_retry_after_http_date(self) -> None:
        future_dt = datetime.now(UTC) + timedelta(seconds=25)
        http_date_str = format_datetime(future_dt)
        parsed = parse_retry_after(http_date_str)
        self.assertGreater(parsed, 20.0)
        self.assertLessEqual(parsed, 30.0)

    def test_parse_retry_after_invalid_falls_back(self) -> None:
        self.assertEqual(parse_retry_after(None, default_seconds=3.0), 3.0)
        self.assertEqual(parse_retry_after("not-a-number", default_seconds=4.0), 4.0)


class AdzunaClientFetchingTests(unittest.TestCase):
    """Tests for successful page requests, data mapping, and raw response preservation."""

    def setUp(self) -> None:
        self.config = AdzunaConfig(app_id="test-app-id", app_key="test-app-key", country="in")

    def test_india_endpoint_url_and_params(self) -> None:
        client = AdzunaClient(self.config)
        url = client.build_url(page=3)
        self.assertEqual(url, "https://api.adzuna.com/v1/api/jobs/in/search/3")

        params = client.build_params(what="data engineer", where="Bangalore", results_per_page=15)
        self.assertEqual(params["app_id"], "test-app-id")
        self.assertEqual(params["app_key"], "test-app-key")
        self.assertEqual(params["what"], "data engineer")
        self.assertEqual(params["where"], "Bangalore")
        self.assertEqual(params["results_per_page"], 15)
        self.assertEqual(params["content-type"], "application/json")

    def test_successful_single_page_fetch(self) -> None:
        payload = sample_adzuna_payload(jobs_count=2, total_count=50)
        raw_json = json.dumps(payload)
        mock_resp = MockHTTPResponse(status=200, body=raw_json.encode("utf-8"))
        opener = MockOpener([mock_resp])

        client = AdzunaClient(self.config, opener=opener)
        page: AdzunaPage = client.fetch_page(1, what="python")

        self.assertEqual(page.page, 1)
        self.assertEqual(page.total_count, 50)
        self.assertEqual(page.http_status, 200)
        self.assertEqual(len(page.results), 2)
        self.assertEqual(page.raw_json, raw_json)
        self.assertTrue(len(page.content_sha256) == 64)

        # Inspect first job
        job: AdzunaJob = page.results[0]
        self.assertEqual(job.id, "job-1")
        self.assertEqual(job.title, "Software Engineer 1")
        self.assertEqual(job.company_name, "TechCorp 1")
        self.assertEqual(job.location_display_name, "Bengaluru, Karnataka")
        self.assertEqual(job.location_area, ("India", "Karnataka", "Bengaluru"))
        self.assertEqual(job.salary_min, 1300000.0)
        self.assertEqual(job.salary_max, 2100000.0)
        self.assertFalse(job.salary_is_predicted)
        self.assertEqual(job.contract_time, "full_time")
        self.assertEqual(job.contract_type, "permanent")
        self.assertEqual(job.category_tag, "it-jobs")
        self.assertEqual(job.category_label, "IT Jobs")


class AdzunaClientPaginationTests(unittest.TestCase):
    """Tests for sequential pagination across multiple pages and termination conditions."""

    def setUp(self) -> None:
        self.config = AdzunaConfig(
            app_id="test-app-id",
            app_key="test-app-key",
            country="in",
            results_per_page=2,
        )

    def test_pagination_across_multiple_pages(self) -> None:
        page1_payload = sample_adzuna_payload(jobs_count=2, total_count=4, prefix="p1")
        page2_payload = sample_adzuna_payload(jobs_count=2, total_count=4, prefix="p2")

        resp1 = MockHTTPResponse(200, json.dumps(page1_payload).encode("utf-8"))
        resp2 = MockHTTPResponse(200, json.dumps(page2_payload).encode("utf-8"))
        opener = MockOpener([resp1, resp2])

        client = AdzunaClient(self.config, opener=opener)
        pages = list(client.paginate(start_page=1, max_pages=5))

        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0].page, 1)
        self.assertEqual(pages[1].page, 2)
        all_jobs = [job.id for p in pages for job in p.results]
        self.assertEqual(all_jobs, ["p1-1", "p1-2", "p2-1", "p2-2"])

    def test_pagination_stops_when_empty_results(self) -> None:
        page1_payload = sample_adzuna_payload(jobs_count=0, total_count=0)
        resp1 = MockHTTPResponse(200, json.dumps(page1_payload).encode("utf-8"))
        opener = MockOpener([resp1])

        client = AdzunaClient(self.config, opener=opener)
        pages = list(client.paginate(start_page=1))

        self.assertEqual(len(pages), 1)
        self.assertEqual(len(pages[0].results), 0)
        self.assertEqual(len(opener.calls), 1)

    def test_pagination_stops_when_max_pages_reached(self) -> None:
        p1 = MockHTTPResponse(200, json.dumps(sample_adzuna_payload(jobs_count=2, total_count=100)).encode("utf-8"))
        p2 = MockHTTPResponse(200, json.dumps(sample_adzuna_payload(jobs_count=2, total_count=100)).encode("utf-8"))
        opener = MockOpener([p1, p2])

        client = AdzunaClient(self.config, opener=opener)
        pages = list(client.paginate(start_page=1, max_pages=2))
        self.assertEqual(len(pages), 2)
        self.assertEqual(len(opener.calls), 2)

    def test_pagination_stops_when_max_results_reached(self) -> None:
        p1 = MockHTTPResponse(200, json.dumps(sample_adzuna_payload(jobs_count=2, total_count=100)).encode("utf-8"))
        p2 = MockHTTPResponse(200, json.dumps(sample_adzuna_payload(jobs_count=2, total_count=100)).encode("utf-8"))
        opener = MockOpener([p1, p2])

        client = AdzunaClient(self.config, opener=opener)
        pages = list(client.paginate(start_page=1, max_results=2))
        self.assertEqual(len(pages), 1)
        self.assertEqual(len(opener.calls), 1)


class AdzunaClientErrorAndRetryTests(unittest.TestCase):
    """Tests for HTTP error handling, request timeouts, and rate-limit backoff."""

    def setUp(self) -> None:
        self.config = AdzunaConfig(
            app_id="test-app-id",
            app_key="test-app-key",
            country="in",
            max_retries=2,
            backoff_factor=0.01,
            max_retry_after=10.0,
        )
        self.sleep_calls: list[float] = []

    def _sleep_tracker(self, duration: float) -> None:
        self.sleep_calls.append(duration)

    def test_http_401_raises_http_error_immediately_no_retry(self) -> None:
        err = HTTPError(
            url="https://api.adzuna.com/v1/api/jobs/in/search/1",
            code=401,
            msg="Unauthorized",
            hdrs={},  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"error": "Invalid app_id or app_key"}'),
        )
        opener = MockOpener([err])
        client = AdzunaClient(self.config, opener=opener, sleep_fn=self._sleep_tracker)

        with self.assertRaises(AdzunaHTTPError) as ctx:
            client.fetch_page(1)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(len(opener.calls), 1)  # No retries on 401
        self.assertEqual(len(self.sleep_calls), 0)

    def test_http_500_retries_and_succeeds(self) -> None:
        err500 = HTTPError(
            url="https://api.adzuna.com/v1/api/jobs/in/search/1",
            code=500,
            msg="Internal Server Error",
            hdrs={},  # type: ignore[arg-type]
            fp=io.BytesIO(b"Internal Error"),
        )
        ok_payload = sample_adzuna_payload(jobs_count=1)
        resp200 = MockHTTPResponse(200, json.dumps(ok_payload).encode("utf-8"))
        opener = MockOpener([err500, resp200])

        client = AdzunaClient(self.config, opener=opener, sleep_fn=self._sleep_tracker)
        page = client.fetch_page(1)

        self.assertEqual(len(page.results), 1)
        self.assertEqual(len(opener.calls), 2)
        self.assertEqual(len(self.sleep_calls), 1)
        self.assertAlmostEqual(self.sleep_calls[0], 0.01)

    def test_http_500_exhausts_retries_and_raises(self) -> None:
        errs = [
            HTTPError(
                url="https://api.adzuna.com/v1/api/jobs/in/search/1",
                code=503,
                msg="Service Unavailable",
                hdrs={},  # type: ignore[arg-type]
                fp=io.BytesIO(b"Unavailable"),
            )
            for _ in range(3)
        ]
        opener = MockOpener(errs)
        client = AdzunaClient(self.config, opener=opener, sleep_fn=self._sleep_tracker)

        with self.assertRaises(AdzunaMaxRetriesExceededError) as ctx:
            client.fetch_page(1)

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(len(opener.calls), 3)  # Initial + 2 retries
        self.assertEqual(len(self.sleep_calls), 2)

    def test_request_timeout_retries_and_succeeds(self) -> None:
        timeout_err = URLError(TimeoutError("Connection timed out"))
        ok_payload = sample_adzuna_payload(jobs_count=1)
        resp200 = MockHTTPResponse(200, json.dumps(ok_payload).encode("utf-8"))
        opener = MockOpener([timeout_err, resp200])

        client = AdzunaClient(self.config, opener=opener, sleep_fn=self._sleep_tracker)
        page = client.fetch_page(1)

        self.assertEqual(len(page.results), 1)
        self.assertEqual(len(opener.calls), 2)
        self.assertEqual(len(self.sleep_calls), 1)

    def test_request_timeout_exhausts_retries(self) -> None:
        timeout_errs = [URLError(TimeoutError("Connection timed out")) for _ in range(3)]
        opener = MockOpener(timeout_errs)

        client = AdzunaClient(self.config, opener=opener, sleep_fn=self._sleep_tracker)
        with self.assertRaises(AdzunaMaxRetriesExceededError):
            client.fetch_page(1)

        self.assertEqual(len(opener.calls), 3)

    def test_http_429_respects_retry_after_header(self) -> None:
        err429 = HTTPError(
            url="https://api.adzuna.com/v1/api/jobs/in/search/1",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "2"},  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"error": "rate limit"}'),
        )
        ok_payload = sample_adzuna_payload(jobs_count=1)
        resp200 = MockHTTPResponse(200, json.dumps(ok_payload).encode("utf-8"))
        opener = MockOpener([err429, resp200])

        client = AdzunaClient(self.config, opener=opener, sleep_fn=self._sleep_tracker)
        page = client.fetch_page(1)

        self.assertEqual(len(page.results), 1)
        self.assertEqual(len(opener.calls), 2)
        self.assertEqual(self.sleep_calls, [2.0])

    def test_http_429_excessive_retry_after_fails_fast(self) -> None:
        err429 = HTTPError(
            url="https://api.adzuna.com/v1/api/jobs/in/search/1",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "120"},  # 120s > max_retry_after (10s)
            fp=io.BytesIO(b'{"error": "rate limit"}'),
        )
        opener = MockOpener([err429])

        client = AdzunaClient(self.config, opener=opener, sleep_fn=self._sleep_tracker)
        with self.assertRaises(AdzunaRateLimitError) as ctx:
            client.fetch_page(1)

        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(ctx.exception.retry_after, 120.0)
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(len(self.sleep_calls), 0)

    def test_http_429_exhausts_retries(self) -> None:
        errs = [
            HTTPError(
                url="https://api.adzuna.com/v1/api/jobs/in/search/1",
                code=429,
                msg="Too Many Requests",
                hdrs={"Retry-After": "1"},  # type: ignore[arg-type]
                fp=io.BytesIO(b'{"error": "rate limit"}'),
            )
            for _ in range(3)
        ]
        opener = MockOpener(errs)

        client = AdzunaClient(self.config, opener=opener, sleep_fn=self._sleep_tracker)
        with self.assertRaises(AdzunaRateLimitError) as ctx:
            client.fetch_page(1)

        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(len(opener.calls), 3)
        self.assertEqual(len(self.sleep_calls), 2)


class AdzunaClientMalformedResponseTests(unittest.TestCase):
    """Tests for validating API response structure and handling malformed data."""

    def setUp(self) -> None:
        self.config = AdzunaConfig(app_id="test-app-id", app_key="test-app-key", country="in")

    def test_malformed_json_response_raises_error(self) -> None:
        resp = MockHTTPResponse(200, b"<html>502 Bad Gateway</html>")
        opener = MockOpener([resp])
        client = AdzunaClient(self.config, opener=opener)

        with self.assertRaises(AdzunaMalformedResponseError):
            client.fetch_page(1)

    def test_top_level_not_a_dictionary_raises_error(self) -> None:
        resp = MockHTTPResponse(200, b'["an", "array"]')
        opener = MockOpener([resp])
        client = AdzunaClient(self.config, opener=opener)

        with self.assertRaises(AdzunaMalformedResponseError):
            client.fetch_page(1)

    def test_missing_results_field_raises_error(self) -> None:
        resp = MockHTTPResponse(200, b'{"count": 100, "status": "ok"}')
        opener = MockOpener([resp])
        client = AdzunaClient(self.config, opener=opener)

        with self.assertRaises(AdzunaMalformedResponseError):
            client.fetch_page(1)

    def test_malformed_job_item_skipped_gracefully(self) -> None:
        # One valid job, one missing id, one not a dictionary
        payload = {
            "count": 3,
            "results": [
                {"id": "job-valid", "title": "Good Job", "description": "Valid job description."},
                {"title": "Missing ID", "description": "Invalid item without id"},
                "not-even-a-dict",
            ],
        }
        resp = MockHTTPResponse(200, json.dumps(payload).encode("utf-8"))
        opener = MockOpener([resp])
        client = AdzunaClient(self.config, opener=opener)

        page = client.fetch_page(1)
        self.assertEqual(len(page.results), 1)
        self.assertEqual(page.results[0].id, "job-valid")


class CredentialLeakagePreventionTests(unittest.TestCase):
    """Tests verifying credentials never appear in error messages or logs."""

    def setUp(self) -> None:
        self.secret_id = "sensitive-super-app-id"
        self.secret_key = "confidential-super-app-key-999"
        self.config = AdzunaConfig(
            app_id=self.secret_id,
            app_key=self.secret_key,
            country="in",
            max_retries=1,
            backoff_factor=0.01,
        )

    def test_credentials_never_in_error_messages(self) -> None:
        # Trigger an HTTPError containing the full raw URL with secrets
        err = HTTPError(
            url=f"https://api.adzuna.com/v1/api/jobs/in/search/1?app_id={self.secret_id}&app_key={self.secret_key}",
            code=403,
            msg="Forbidden",
            hdrs={},  # type: ignore[arg-type]
            fp=io.BytesIO(f"Access denied for {self.secret_id}".encode("utf-8")),
        )
        opener = MockOpener([err])
        client = AdzunaClient(self.config, opener=opener)

        with self.assertRaises(AdzunaHTTPError) as ctx:
            client.fetch_page(1)

        err_msg = str(ctx.exception)
        self.assertNotIn(self.secret_id, err_msg)
        self.assertNotIn(self.secret_key, err_msg)
        self.assertIn("***", err_msg)

    def test_credentials_never_in_logs(self) -> None:
        log_stream = io.StringIO()
        logger = logging.getLogger("test_adzuna_security_logger")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(log_stream)
        logger.addHandler(handler)

        err = HTTPError(
            url=f"https://api.adzuna.com/v1/api/jobs/in/search/1?app_id={self.secret_id}&app_key={self.secret_key}",
            code=500,
            msg="Server Error",
            hdrs={},  # type: ignore[arg-type]
            fp=io.BytesIO(b"Internal Error"),
        )
        ok_payload = sample_adzuna_payload(jobs_count=1)
        resp200 = MockHTTPResponse(200, json.dumps(ok_payload).encode("utf-8"))
        opener = MockOpener([err, resp200])

        client = AdzunaClient(
            self.config,
            opener=opener,
            sleep_fn=lambda _: None,
            logger=logger,
        )
        client.fetch_page(1)

        log_output = log_stream.getvalue()
        self.assertNotIn(self.secret_id, log_output)
        self.assertNotIn(self.secret_key, log_output)


if __name__ == "__main__":
    unittest.main()
