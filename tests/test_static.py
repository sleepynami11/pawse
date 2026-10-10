import re

from fastapi.testclient import TestClient

from pawse.app import app


def test_rehearsal_page_declares_a_favicon_that_resolves():
    with TestClient(app) as c:
        page = c.get("/").text
        icon = re.search(r'<link rel="icon" href="([^"]+)"', page)
        assert icon, "rehearsal page has no <link rel=icon>, so browsers 404 on /favicon.ico"
        res = c.get(icon.group(1))
        assert res.status_code == 200 and res.headers["content-type"].startswith("image/")
