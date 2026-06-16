# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Browser-level health checks for the GitHub Pages docs site (docs/).

Loads each page in a real headless Chromium (via pytest-playwright) and asserts
it renders without console/page errors, carries the required navigation (a
clickable home brand and a GitHub link on every page; a Home breadcrumb on every
sub-page), and that its local hrefs/src references resolve to files that exist.

Requires a Playwright browser, which install.sh and CI both provision. If it is
missing these tests FAIL (with Playwright's own "run playwright install" message)
rather than silently skipping — a green run should mean the docs were actually
checked, not quietly skipped. Install locally with:
    uv run playwright install chromium
"""

import pathlib
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"
PAGES = sorted(DOCS.glob("*.html"))
PAGE_IDS = [p.name for p in PAGES]
SUBPAGES = [p for p in PAGES if p.name != "index.html"]
SUBPAGE_IDS = [p.name for p in SUBPAGES]


@pytest.mark.parametrize("html", PAGES, ids=PAGE_IDS)
def test_page_renders_without_errors(page: Page, html: pathlib.Path) -> None:
    """Each page loads cleanly: a <title>, no console/page errors, no failed asset.

    A failed script/stylesheet load surfaces as a `requestfailed` event, not a
    console error, so it is listened for explicitly — otherwise a page whose JS or
    CSS 404s would pass while silently shipping no interactivity or styling.
    """
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on(
        "requestfailed",
        lambda req: (
            errors.append(f"requestfailed {req.resource_type}: {req.url}")
            if req.resource_type in ("script", "stylesheet")
            else None
        ),
    )
    page.goto(html.as_uri())
    assert page.title(), f"{html.name}: missing <title>"
    assert not errors, f"{html.name}: runtime errors {errors}"


@pytest.mark.parametrize("html", PAGES, ids=PAGE_IDS)
def test_interactive_handlers_run(page: Page, html: pathlib.Path) -> None:
    """Clicking the theme toggle and a copy button runs the JS handlers cleanly.

    Load-time checks never exercise the click handlers, so a typo inside one would
    pass unnoticed. The theme toggle must flip data-theme; the copy button (over
    file://, a non-secure context) must take its graceful no-clipboard path
    without throwing.
    """
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(html.as_uri())

    before = page.locator("html").get_attribute("data-theme")
    page.locator("[data-theme-toggle]").click()
    after = page.locator("html").get_attribute("data-theme")
    assert after, f"{html.name}: theme toggle cleared data-theme"
    assert after != before, f"{html.name}: theme toggle did not flip data-theme"

    copies = page.locator(".copy-btn")
    if copies.count():
        copies.first.click()
    assert not errors, f"{html.name}: handler errors {errors}"


@pytest.mark.parametrize("html", PAGES, ids=PAGE_IDS)
def test_page_has_home_brand_and_github_link(page: Page, html: pathlib.Path) -> None:
    """Every page links home via the brand and out to the GitHub repository."""
    page.goto(html.as_uri())
    assert page.locator('a.brand[href="index.html"]').count() == 1, "no home-brand link"
    assert page.locator('a[href*="github.com/nivintw/dotfiles"]').count() >= 1, "no GitHub link"


@pytest.mark.parametrize("html", SUBPAGES, ids=SUBPAGE_IDS)
def test_subpage_has_home_breadcrumb(page: Page, html: pathlib.Path) -> None:
    """Each sub-page exposes a clickable Home breadcrumb back to the index."""
    page.goto(html.as_uri())
    assert page.locator('.crumb a[href="index.html"]').count() == 1, "no Home breadcrumb"


@pytest.mark.parametrize("html", PAGES, ids=PAGE_IDS)
def test_local_references_resolve(page: Page, html: pathlib.Path) -> None:
    """Local href/src references on each page point at files that exist."""
    page.goto(html.as_uri())
    refs = page.eval_on_selector_all(
        "[href], [src]",
        "els => els.map(e => e.getAttribute('href') || e.getAttribute('src'))",
    )
    checked = 0
    for ref in refs:
        if not ref or ref.startswith(("http://", "https://", "#", "mailto:")):
            continue
        clean = ref.split("#", 1)[0]
        if not clean:
            continue
        target = (html.parent / clean).resolve()
        assert target.exists(), f"{html.name}: dead local reference {ref!r}"
        checked += 1
    assert checked, f"{html.name}: no local references checked — test would pass vacuously"
