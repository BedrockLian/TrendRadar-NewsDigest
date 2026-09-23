"""Browser acceptance for the workstation; run against local or production data."""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

root = Path(__file__).resolve().parents[1]
base = os.environ.get("RADAR_TEST_URL", "http://127.0.0.1:18081")
production = base.startswith("https:")
password = (root / ".local" / ("prod-admin-password" if production else "admin-password")).read_text().strip()
username = (root / ".local/prod-admin-username").read_text().strip() if production else "admin"
out = root / ".local/qa-redesign"
out.mkdir(exist_ok=True)
errors = []
checks = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="light")
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base + "/login/", wait_until="networkidle")
    page.locator("[data-theme-select]:visible").select_option("dark")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.reload(wait_until="networkidle")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_label("用户名").fill(username)
    page.locator("input[name=password]").fill(password)
    page.get_by_role("button", name="登录工作台").click()
    page.wait_for_url(base + "/")

    def set_theme(value, mobile=False):
        if mobile:
            page.locator(".mobile-nav details > summary").click()
        page.locator("[data-theme-select]:visible").select_option(value)
        if mobile:
            page.locator(".mobile-nav details > summary").click()

    pages = [
        ("home", "/"),
        ("news", "/news/"),
        ("briefs", "/briefs/"),
        ("events", "/events/"),
        ("dashboard", "/dashboard/"),
        ("settings", "/settings/"),
    ]
    for width in [1440, 1024, 390, 320]:
        page.set_viewport_size({"width": width, "height": 900 if width > 400 else 844})
        for theme in ["light", "dark"]:
            for name, path in pages:
                response = page.goto(base + path, wait_until="networkidle")
                set_theme(theme, width <= 760)
                assert response.status == 200, (path, response.status)
                assert page.locator("html").get_attribute("data-theme") == theme
                fits = page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                if not fits:
                    offenders = page.evaluate("""[...document.querySelectorAll('body *')]
                        .filter(node => node.getBoundingClientRect().right > innerWidth + 1)
                        .slice(0, 8).map(node => [node.tagName, node.className, Math.round(node.getBoundingClientRect().right)])""")
                    page.screenshot(path=str(out / f"overflow-{width}-{theme}-{name}.png"), full_page=True)
                    raise AssertionError((width, theme, path, offenders))
                if name == "home" and page.locator(".brief-headline").count():
                    assert page.locator(".brief-headline").first.bounding_box()["y"] < 360
                    visible = page.locator(".brief-headline:visible").count()
                    assert visible <= (3 if width <= 760 else 6)
                    if width <= 760:
                        assert (
                            page.locator("#intelligence").bounding_box()["y"]
                            < page.locator(".home-new").bounding_box()["y"]
                        )
                page.screenshot(path=str(out / f"{width}-{theme}-{name}.png"), full_page=True)
                checks.append([width, theme, name])

    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(base + "/news/", wait_until="networkidle")
    page.get_by_role("button", name="紧凑").click()
    assert page.locator("html").get_attribute("data-density") == "compact"
    page.reload(wait_until="networkidle")
    assert page.locator("html").get_attribute("data-density") == "compact"
    page.locator("a.news-row").first.click()
    page.locator("#reader-content .reading").wait_for()
    assert "article=" in page.url
    page.reload(wait_until="networkidle")
    page.locator("#reader-content .reading").wait_for()
    assert page.locator(".news-row.selected").count() == 1
    page.get_by_role("button", name="专注阅读").click()
    assert page.locator(".archive-layout").evaluate("node => node.classList.contains('reader-focused')")

    page.get_by_role("button", name="询问新闻库", exact=True).click()
    expect(page.locator("#ask-dialog")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#ask-dialog")).not_to_be_visible()
    set_theme("system")
    page.emulate_media(color_scheme="dark")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.emulate_media(color_scheme="light")
    expect(page.locator("html")).to_have_attribute("data-theme", "light")

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(base + "/news/?start=2020-01-01", wait_until="networkidle")
    page.locator("a.news-row").first.click()
    page.locator(".archive-back").wait_for()
    assert "start=2020-01-01" in page.locator(".archive-back").get_attribute("href")
    page.locator(".archive-back").click()
    assert "start=2020-01-01" in page.url
    assert page.locator(".mobile-nav").is_visible()

    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(base + "/dashboard/", wait_until="networkidle")
    assert page.locator("#arrival-chart").count() == 1
    assert page.locator("#duplicate-chart").count() == 1
    before = page.locator("#arrival-chart").evaluate("node => node.toDataURL()")
    set_theme("dark")
    after = page.locator("#arrival-chart").evaluate("node => node.toDataURL()")
    if page.evaluate("JSON.parse(document.getElementById('crawl-data').textContent).series.length"):
        assert before != after, "Chart must redraw with theme colors"

    page.set_viewport_size({"width": 720, "height": 500})
    page.goto(base + "/", wait_until="networkidle")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    browser.close()

assert not errors, errors
(out / "report.json").write_text(json.dumps({"checks": checks, "errors": errors}, indent=2), "utf-8")
print(f"{len(checks)} viewport/theme/page checks plus reader, mobile return, theme and chart checks passed")
