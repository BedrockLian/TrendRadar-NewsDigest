"""Transport-level tests for the RSS fetcher.

These cover the conditional-request path that integration tests with a single
successful fetch cannot reach: a 304 must stay a normal result, and only real
redirects may be followed.
"""

import httpx
import pytest

from app.news.crawler import fetch


def transport(handler):
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def local_urls(monkeypatch):
    # Skip DNS resolution; these tests exercise HTTP behaviour only.
    monkeypatch.setattr("app.news.crawler.public_url", lambda url: url)


def test_not_modified_is_not_treated_as_a_redirect():
    def handler(request):
        assert request.headers["if-none-match"] == '"v1"'
        return httpx.Response(304, headers={"etag": '"v1"'})

    status, headers, body = fetch(
        "https://example.org/rss", {"If-None-Match": '"v1"'}, transport=transport(handler)
    )
    assert status == 304 and body == b"" and headers["etag"] == '"v1"'


def test_redirect_is_followed_to_the_final_url():
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "https://example.org/new"})
        return httpx.Response(200, headers={"content-type": "application/rss+xml"}, content=b"<rss/>")

    status, _, body = fetch("https://example.org/old", {}, transport=transport(handler))
    assert status == 200 and body == b"<rss/>"


def test_redirect_without_location_is_rejected():
    def handler(request):
        return httpx.Response(301)

    with pytest.raises(ValueError):
        fetch("https://example.org/old", {}, transport=transport(handler))


def test_redirect_loop_is_bounded():
    def handler(request):
        return httpx.Response(302, headers={"location": "https://example.org/loop"})

    with pytest.raises(ValueError):
        fetch("https://example.org/loop", {}, transport=transport(handler))


def test_oversized_body_is_rejected():
    def handler(request):
        return httpx.Response(200, content=b"x" * (6 * 1024 * 1024))

    with pytest.raises(ValueError):
        fetch("https://example.org/big", {}, transport=transport(handler))
