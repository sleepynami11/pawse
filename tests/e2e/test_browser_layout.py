"""Layout of the real pages at desktop and phone widths. Screenshots land in test-results/layout/ for a human look."""
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from e2e_helpers import FakeLive, wait_for

SIZES = [(1280, 800), (1440, 900), (1920, 1080), (390, 844)]
DESKTOP = SIZES[:3]
SHOTS = Path(__file__).resolve().parents[2] / "test-results" / "layout"

VISIBLE_CONTROLS = """() => [...document.querySelectorAll("button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button]")]
  .filter(el => { const s = getComputedStyle(el), r = el.getBoundingClientRect();
                  return s.visibility !== "hidden" && s.display !== "none" && r.width > 0 && r.height > 0
                         && el.parentElement.closest("button, a, label, summary, [role=button]") === null; })
  .map(el => ({ name: el.getAttribute("aria-label") || el.id || el.textContent.trim().slice(0, 30) || el.tagName,
                inline: el.tagName === "A" && getComputedStyle(el).display === "inline",
                // one box per line, so a link that wraps is not one big rectangle
                rects: [...el.getClientRects()].map(r => ({ x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height })) }))"""


def ids(sizes):
    return [f"{w}x{h}" for w, h in sizes]


def home(page: Page):
    page.goto("/app/")
    expect(page.locator(".start-btn")).to_be_visible()


def call_screen(page: Page):
    live = FakeLive(page)
    page.goto("/app/?live=1")
    page.locator(".start-btn").click()
    page.get_by_role("button", name="Agree and start").click()
    wait_for(page, lambda: live.frames("setup"), what="Live setup")
    live.push({"serverContent": {"outputTranscription": {"text": "Hello, I am Pawse. How can I help Mimi today?"}}})
    expect(page.locator(".cap-ai")).to_be_visible()


def original_page(page: Page):
    page.goto("/")
    page.wait_for_load_state("networkidle")


PAGES = {"app-home": home, "app-call": call_screen, "original": original_page}


def open_at(page: Page, name: str, width: int, height: int):
    page.set_viewport_size({"width": width, "height": height})
    PAGES[name](page)
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=SHOTS / f"{name}-{width}x{height}.png", full_page=True)


@pytest.mark.parametrize("width,height", SIZES, ids=ids(SIZES))
@pytest.mark.parametrize("name", PAGES)
def test_no_horizontal_scroll(page: Page, name, width, height):
    open_at(page, name, width, height)
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 0, f"{name} scrolls sideways by {overflow}px at {width}px"


@pytest.mark.parametrize("width,height", SIZES, ids=ids(SIZES))
@pytest.mark.parametrize("name", PAGES)
def test_controls_do_not_overlap_and_are_big_enough_to_hit(page: Page, name, width, height):
    open_at(page, name, width, height)
    controls = page.evaluate(VISIBLE_CONTROLS)
    overlaps = [(c["name"], d["name"]) for i, c in enumerate(controls) for d in controls[i + 1:]
                if any(intersects(r, q) for r in c["rects"] for q in d["rects"])]
    assert not overlaps, f"overlapping controls: {overlaps}"
    # WCAG 2.2 target size (minimum): under 24x24 px passes only if a 24 px circle on it touches no other
    # target (spacing exception); inline text links are exempt, as in the standard.
    small = [c for c in controls if not c["inline"] and any(r["w"] < 24 or r["h"] < 24 for r in c["rects"])]
    crowded = [c["name"] for c in small if any(near(c, d) for d in controls if d is not c)]
    assert not crowded, f"controls under 24x24px with another target within 12px of their centre: {crowded}"


def intersects(a, b):
    return min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]) > 1 and \
        min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]) > 1


def near(small, other):
    r = small["rects"][0]
    cx, cy = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
    for q in other["rects"]:
        dx = max(q["x"] - cx, 0, cx - q["x"] - q["w"])
        dy = max(q["y"] - cy, 0, cy - q["y"] - q["h"])
        if (dx * dx + dy * dy) ** 0.5 < 12:
            return True
    return False


@pytest.mark.parametrize("width,height", SIZES, ids=ids(SIZES))
def test_call_button_and_call_controls_are_on_screen_without_scrolling(page: Page, width, height):
    open_at(page, "app-home", width, height)
    expect(page.locator(".start-btn")).to_be_in_viewport()
    open_at(page, "app-call", width, height)
    for control in page.locator("nav.call-controls button").all():
        expect(control).to_be_in_viewport()
    expect(page.get_by_role("textbox")).to_be_in_viewport()


@pytest.mark.parametrize("width,height", DESKTOP, ids=ids(DESKTOP))
def test_desktop_centres_the_app_column(page: Page, width, height):
    open_at(page, "app-call", width, height)
    box = page.locator("main").bounding_box()
    left, right = box["x"], width - box["x"] - box["width"]
    assert abs(left - right) <= 2, f"app column is off-centre: {left:.0f}px left vs {right:.0f}px right"
    controls = page.locator("nav.call-controls").bounding_box()
    centre = controls["x"] + controls["width"] / 2
    assert abs(centre - width / 2) <= 2, "call controls are not centred under the cat"


@pytest.mark.parametrize("width,height", [SIZES[0], SIZES[-1]], ids=ids([SIZES[0], SIZES[-1]]))
def test_simulated_rehearsal_is_labelled_on_screen(page: Page, width, height):
    page.set_viewport_size({"width": width, "height": height})
    page.goto("/app/?demo=1")
    expect(page.locator(".badge")).to_be_visible()
    expect(page.locator(".badge")).to_be_in_viewport()
