

"""Error contract tests for typed API exceptions."""

import json
import urllib.error

import pytest

from med_research.exceptions import (
    APIParseError,
    APIQuotaError,
    APITimeoutError,
    ExternalAPIError,
    classify_api_error,
    raise_api_error,
    retry_with_backoff,
)

pytestmark = pytest.mark.unit


class TestClassifyApiError:
    def test_json_decode_error_maps_to_api_parse_error(self):
        exc = json.JSONDecodeError("Expecting value", "doc", 0)
        err = classify_api_error(exc, "Europe PMC")
        assert isinstance(err, APIParseError)
        assert "Europe PMC" in str(err)

    def test_urllib_timeout_maps_to_api_timeout_error(self):
        exc = urllib.error.URLError(TimeoutError("timed out"))
        err = classify_api_error(exc, "NCBI GEO")
        assert isinstance(err, APITimeoutError)
        assert "NCBI GEO" in str(err)

    def test_requests_http_503_maps_to_api_quota_error(self):
        requests = pytest.importorskip("requests")
        response = requests.Response()
        response.status_code = 503
        response.headers["Retry-After"] = "7"
        exc = requests.exceptions.HTTPError(response=response)
        err = classify_api_error(exc, "ClinicalTrials.gov")
        assert isinstance(err, APIQuotaError)
        assert err.retry_after_seconds == 7.0

    def test_urllib_http_429_maps_to_api_quota_error(self):
        exc = urllib.error.HTTPError(
            url="https://example.com",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "3"},
            fp=None,
        )
        err = classify_api_error(exc, "rate limited API")
        assert isinstance(err, APIQuotaError)
        assert err.retry_after_seconds == 3.0

    def test_requests_timeout_maps_to_api_timeout_error(self):
        requests = pytest.importorskip("requests")
        exc = requests.exceptions.Timeout("read timed out")
        err = classify_api_error(exc, "GWAS Catalog")
        assert isinstance(err, APITimeoutError)

    def test_requests_connection_error_maps_to_api_timeout_error(self):
        requests = pytest.importorskip("requests")
        exc = requests.exceptions.ConnectionError("connection refused")
        err = classify_api_error(exc, "STRING API")
        assert isinstance(err, APITimeoutError)

    def test_external_api_error_passthrough(self):
        original = ExternalAPIError("already typed")
        err = classify_api_error(original, "ignored")
        assert err is original

    def test_raise_api_error_preserves_chain(self):
        exc = json.JSONDecodeError("Expecting value", "doc", 0)
        with pytest.raises(APIParseError) as raised:
            raise_api_error(exc, "parse failure")
        assert raised.value.__cause__ is exc


class TestRetryWithBackoff:
    def test_retries_transient_error_then_succeeds(self, monkeypatch):
        attempts = {"count": 0}

        def flaky():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise APITimeoutError("timed out")
            return "ok"

        sleeps: list[dict[str, object]] = []

        def _record_sleep(attempt, **kwargs):
            sleeps.append({"attempt": attempt, **kwargs})

        monkeypatch.setattr("med_research.exceptions.backoff_sleep", _record_sleep)
        assert retry_with_backoff(flaky, source="test API") == "ok"
        assert attempts["count"] == 3
        assert len(sleeps) == 2

    def test_retries_quota_error_with_retry_after(self, monkeypatch):
        attempts = {"count": 0}

        def flaky():
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise APIQuotaError("rate limited", retry_after_seconds=9.0)
            return "ok"

        sleeps: list[dict[str, object]] = []

        def _record_sleep(attempt, **kwargs):
            sleeps.append({"attempt": attempt, **kwargs})

        monkeypatch.setattr("med_research.exceptions.backoff_sleep", _record_sleep)
        assert retry_with_backoff(flaky, source="test API") == "ok"
        assert sleeps == [{"attempt": 0, "retry_after": 9.0}]

    def test_does_not_retry_parse_errors(self, monkeypatch):
        attempts = {"count": 0}

        def bad_json():
            attempts["count"] += 1
            raise APIParseError("invalid json")

        monkeypatch.setattr("med_research.exceptions.backoff_sleep", lambda *args, **kwargs: None)
        with pytest.raises(APIParseError):
            retry_with_backoff(bad_json, source="test API")
        assert attempts["count"] == 1


class TestGathererApiGet:
    def test_api_get_raises_api_parse_error_on_bad_json(self, monkeypatch):
        from med_research.pipeline.evidence import gatherer

        class FakeResponse:
            def read(self):
                return b"not-json"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda *args, **kwargs: FakeResponse(),
        )

        with pytest.raises(APIParseError):
            gatherer.api_get("https://example.com/api")

    def test_api_get_raises_api_timeout_error_on_timeout(self, monkeypatch):
        from med_research.pipeline.evidence import gatherer

        def _raise_timeout(*args, **kwargs):
            raise urllib.error.URLError(TimeoutError("timed out"))

        monkeypatch.setattr("urllib.request.urlopen", _raise_timeout)

        with pytest.raises(APITimeoutError):
            gatherer.api_get("https://example.com/api")

    def test_search_europe_pmc_degrades_on_api_error(self, monkeypatch):
        from med_research.pipeline.evidence import gatherer

        def _raise_timeout(*args, **kwargs):
            raise urllib.error.URLError(TimeoutError("timed out"))

        monkeypatch.setattr("urllib.request.urlopen", _raise_timeout)
        monkeypatch.setattr(gatherer, "cache_get", lambda *args, **kwargs: None)
        monkeypatch.setattr(gatherer, "cache_set", lambda *args, **kwargs: None)

        results = gatherer.search_europe_pmc("lupus", "pubmed", max_results=3, use_cache=False)
        assert results == []
