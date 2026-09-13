"""Run against an existing local server; credentials stay in ignored local files."""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
out = root / ".local/qa"
out.mkdir(parents=True, exist_ok=True)
password = (root / ".local/admin-password").read_text().strip()
report = {"pages": [], "errors": []}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    page.on("pageerror", lambda error: report["errors"].append(str(error)))
    page.goto("http://127.0.0.1:18081/login/")
    page.get_by_label("用户名").fill("admin")
    page.get_by_label("密码").fill(password)
    page.get_by_role("button", name="登录工作台").click()
    page.wait_for_url("http://127.0.0.1:18081/")
    for name, url in [
        ("home", "/"),
        ("news", "/news/"),
        ("briefs", "/briefs/"),
        ("events", "/events/"),
        ("dashboard", "/dashboard/"),
        ("settings", "/settings/"),
    ]:
        response = page.goto("http://127.0.0.1:18081" + url)
        page.wait_for_load_state("networkidle")
        assert response.status == 200, (name, response.status)
        page.screenshot(path=str(out / f"desktop-{name}.png"), full_page=True)
        report["pages"].append({"page": name, "status": response.status})
    page.goto("http://127.0.0.1:18081/news/?q=人工智能")
    if page.locator(".news-row h3 a").count():
        page.locator(".news-row h3 a").first.click()
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="收藏此版本", exact=True).click()
        page.get_by_role("button", name="取消收藏", exact=True).wait_for()
        page.get_by_role("button", name="取消收藏", exact=True).click()
        page.screenshot(path=str(out / "desktop-article.png"), full_page=True)
    page.goto("http://127.0.0.1:18081/events/new/")
    page.get_by_label("事件名称").fill("人工智能与算力产业动态（本地验收）")
    page.get_by_label("关注内容").fill("用于验证事件创建、报道确认和时间线布局。")
    page.get_by_label("关键词与别名").fill("人工智能,芯片")
    page.get_by_role("button", name="保存", exact=True).click()
    page.wait_for_url("**/events/*/")
    event_url = page.url
    page.screenshot(path=str(out / "desktop-event-empty.png"), full_page=True)
    page.get_by_role("button", name="询问新闻库 ↗").click()
    page.get_by_role("dialog").wait_for(state="visible")
    page.get_by_role("button", name="关闭问答").click()
    page.set_viewport_size({"width": 390, "height": 844})
    for name, url in [
        ("home", "/"),
        ("news", "/news/?q=人工智能"),
        ("dashboard", "/dashboard/"),
        ("events", "/events/"),
    ]:
        page.goto("http://127.0.0.1:18081" + url)
        page.wait_for_load_state("networkidle")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"mobile overflow: {name}"
        page.screenshot(path=str(out / f"mobile-{name}.png"), full_page=True)
    browser.close()
assert not report["errors"], report["errors"]
(out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=True))
