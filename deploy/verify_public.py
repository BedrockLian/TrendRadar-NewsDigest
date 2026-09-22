"""Verify the deployed news workbench over HTTPS with a real login session.

Reads the administrator password from a local file (never from the command line)
and checks the public boundary: anonymous pages, JSON auth, static assets, and the
authenticated reading surfaces.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import httpx

PAGES = ["/", "/news/", "/briefs/", "/events/", "/dashboard/", "/settings/"]
PRIVATE_PATHS = ["/output/briefings/.state.json", "/.state.json", "/db.sqlite3", "/.env", "/../etc/passwd"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("RADAR_TEST_URL"))
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password-file", required=True)
    args = parser.parse_args()
    if not args.base_url:
        parser.error("provide --base-url or set RADAR_TEST_URL")
    password = Path(args.password_file).read_text(encoding="utf-8").strip()
    if len(password) < 8:
        raise SystemExit("password file looks empty or truncated")
    report = {"anonymous": {}, "assets": {}, "private": {}, "pages": {}, "errors": []}
    with httpx.Client(base_url=args.base_url, timeout=60, follow_redirects=False) as client:
        health = client.get("/health/")
        report["anonymous"]["health"] = health.status_code
        report["anonymous"]["health_body"] = health.json() if health.status_code == 200 else None
        for route in PAGES:
            response = client.get(route)
            report["anonymous"][route] = response.status_code
            if response.status_code not in (301, 302):
                report["errors"].append(f"anonymous access to {route} returned {response.status_code}")
        api = client.get("/api/v1/news/")
        report["anonymous"]["api"] = {"status": api.status_code, "body": api.json()}
        if api.status_code != 401:
            report["errors"].append(f"/api/v1/news/ returned {api.status_code} for an anonymous caller")
        for path in PRIVATE_PATHS:
            response = client.get(path)
            report["private"][path] = response.status_code
            if response.status_code == 200:
                report["errors"].append(f"private path {path} is publicly readable")
        for asset in ["/static/workspace.css", "/static/htmx.min.js", "/static/workspace.js"]:
            response = client.get(asset)
            report["assets"][asset] = {"status": response.status_code, "bytes": len(response.content)}
            if response.status_code != 200 or not response.content:
                report["errors"].append(f"asset {asset} not served ({response.status_code})")
        login = client.get("/login/")
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login.text)
        if login.status_code != 200 or not token:
            raise SystemExit("login form unavailable; cannot verify the private surfaces")
        signed_in = client.post(
            "/login/",
            data={"username": args.username, "password": password, "csrfmiddlewaretoken": token.group(1)},
            headers={"Referer": args.base_url + "/login/"},
        )
        report["login"] = signed_in.status_code
        if signed_in.status_code != 302:
            report["errors"].append(f"login failed with {signed_in.status_code}")
        for route in PAGES:
            response = client.get(route)
            title = re.search(r"<title>(.*?)</title>", response.text, re.DOTALL)
            report["pages"][route] = {
                "status": response.status_code,
                "bytes": len(response.content),
                "title": (title.group(1).strip() if title else ""),
            }
            if response.status_code != 200 or len(response.content) < 500:
                report["errors"].append(f"authenticated {route} returned {response.status_code}")
        search = client.get("/news/", params={"q": "人工智能"})
        report["search"] = {"status": search.status_code, "rows": search.text.count('class="news-row"')}
        archive = client.get("/briefs/")
        report["briefs_listed"] = archive.text.count("brief-tile")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        print(f"\nFAILED: {len(report['errors'])} check(s)", file=sys.stderr)
        raise SystemExit(1)
    print("\nAll public boundary checks passed")


if __name__ == "__main__":
    main()
