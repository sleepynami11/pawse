import { test, expect, type Locator, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

// Scripted demo recorder. Drives the mock Pawse app (mock/index.html) through the "Mimi is
// limping" story from research/pet-insurance/demo-video-script.md and records it as a
// 1920x1080 video. Offline and deterministic: the mock plays canned lines and cards, the spec
// only clicks what a user would (mic, reply chips, option A). The expect() calls double as a
// smoke test, a failure here means a story beat stopped rendering. Run via: npm run record:demo.
// Tune pace with SPEED (scales both the spec's holds and the mock's own pauses).
//
// Same pipeline as the DRIFTWATCH recorder: the spec measures where the opening load ends and
// writes demo-out/trim.json, logs every click/glide to demo-out/events.json, and
// scripts/finalize-demo.mjs trims, synthesizes a click soundtrack and encodes the mp4.
const SPEED = Number(process.env.SPEED) || 1;

// Action log for the post-step soundtrack. Playwright records video only (no audio), so
// finalize-demo.mjs synthesizes a click/move track from this log and muxes it on. Times are
// (Date.now() - t0) / 1000, the same raw-video clock the head-trim uses.
let t0 = 0;
const now = () => (Date.now() - t0) / 1000;
const events: { kind: string; t: number; dur?: number; n?: number }[] = [];

// A visible cursor that follows the mouse, so glides read on camera. Injected after load;
// idempotent.
const INSTALL_CURSOR = `
  (() => {
    if (document.getElementById('pawse-demo-cursor')) return;
    const dot = document.createElement('div');
    dot.id = 'pawse-demo-cursor';
    dot.style.cssText = [
      'position:fixed','top:0','left:0','width:24px','height:24px',
      'border-radius:50%','background:rgba(224,69,123,.85)',
      'box-shadow:0 0 0 4px rgba(224,69,123,.25)',
      'pointer-events:none','z-index:2147483647',
      'transform:translate(-50%,-50%)','transition:transform .05s linear',
    ].join(';');
    document.documentElement.appendChild(dot);
    document.addEventListener('mousemove', (e) => {
      dot.style.left = e.clientX + 'px';
      dot.style.top = e.clientY + 'px';
    }, true);
    document.addEventListener('mousedown', () => { dot.style.transform = 'translate(-50%,-50%) scale(.7)'; }, true);
    document.addEventListener('mouseup', () => { dot.style.transform = 'translate(-50%,-50%) scale(1)'; }, true);
  })();
`;

// Pause so the eye can land. Base ms scaled by SPEED.
const beat = (page: Page, ms: number) => page.waitForTimeout(ms / SPEED);

// Where the cursor currently is; each move starts from the last point (Playwright has no
// "current pos").
let cursor = { x: 960, y: 540 };

// Move the cursor like a hand would: a gently curved, eased path with sub-pixel jitter.
async function humanMove(page: Page, x: number, y: number) {
  const start = { ...cursor };
  const tStart = now();
  const dx = x - start.x;
  const dy = y - start.y;
  const dist = Math.hypot(dx, dy) || 1;
  const steps = Math.max(18, Math.min(40, Math.round(dist / 18)));
  const mx = (start.x + x) / 2;
  const my = (start.y + y) / 2;
  const arc = Math.min(60, dist * 0.12) * (Math.random() < 0.5 ? -1 : 1);
  const cx = mx + (-dy / dist) * arc;
  const cy = my + (dx / dist) * arc;
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; // easeInOutQuad
    const u = 1 - e;
    const px = u * u * start.x + 2 * u * e * cx + e * e * x;
    const py = u * u * start.y + 2 * u * e * cy + e * e * y;
    await page.mouse.move(px + (Math.random() - 0.5) * 0.6, py + (Math.random() - 0.5) * 0.6);
    await page.waitForTimeout(12 / SPEED);
  }
  await page.mouse.move(x, y);
  cursor = { x, y };
  events.push({ kind: "move", t: tStart, dur: now() - tStart });
}

// Glide to an element, then click it. Single choke point for every filmed click, so each is
// logged exactly once, just before the handler fires.
async function glideClick(page: Page, locator: Locator) {
  await expect(locator).toBeVisible();
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) {
    await humanMove(page, box.x + box.width / 2, box.y + box.height / 2);
    await beat(page, 250);
  }
  events.push({ kind: "click", t: now() });
  await locator.click();
}

// Wait for the mock to hand control back to the user (it sets data-state="idle" when it
// offers chips or options), then hold briefly so the viewer reads the last line.
async function awaitTurn(page: Page, hold = 700) {
  await expect(page.locator("body")).toHaveAttribute("data-state", "idle");
  await beat(page, hold);
}

const chip = (page: Page, name: string) => page.getByRole("button", { name, exact: true });

test("demo recording: Mimi is limping", async ({ page }) => {
  t0 = Date.now();

  // 1) Open on the idle cat.
  await page.goto(`/?speed=${SPEED}`);
  const mic = page.getByRole("button", { name: "Talk to Pawse" });
  await expect(mic).toBeVisible();
  // Everything before this is browser load, cut by the head-trim (+250ms margin).
  const outDir = join(process.cwd(), "demo-out");
  mkdirSync(outDir, { recursive: true });
  writeFileSync(join(outDir, "trim.json"), JSON.stringify({ startSec: (Date.now() - t0 + 250) / 1000 }));
  await page.evaluate(INSTALL_CURSOR);
  await page.mouse.move(cursor.x, cursor.y);
  // Fixed (not SPEED-scaled) so the clip always opens on ~1.5s of the idle app.
  await page.waitForTimeout(1500);

  // 2) Speak: "My cat is limping." Pawse asks one follow-up.
  await glideClick(page, mic);
  await expect(page.locator("body")).toHaveAttribute("data-state", "listening");
  await awaitTurn(page);

  // 3) Answer the follow-up; triage card and the closest practice appear.
  await glideClick(page, chip(page, "She jumped off the wardrobe."));
  await expect(page.locator("#triage")).toContainText("See a vet today");
  await awaitTurn(page, 1000);

  // 4) Call the vet (German, live subtitles); calendar shows the free slot.
  await glideClick(page, chip(page, "Yes, call them."));
  await expect(page.locator("#call-vet")).toContainText("Calling");
  await expect(page.locator("#calendar")).toBeVisible();
  await awaitTurn(page);

  // 5) Take 16:30; the vet quotes the cost.
  await glideClick(page, chip(page, "16:30 works."));
  await awaitTurn(page);

  // 6) Check coverage with the insurer; two policy lines turn red.
  await glideClick(page, chip(page, "Yes, please."));
  await expect(page.locator("#row-home")).toContainText("❌");
  await expect(page.locator("#row-physio")).toContainText("❌");

  // 7) The choice: clinic (~CHF 385) vs home visit (CHF 510). Pick the clinic.
  await expect(page.locator("#options")).toBeVisible();
  await awaitTurn(page, 1500);
  await glideClick(page, page.locator("#opt-a"));

  // 8) Pawse confirms the vet and books a pet-friendly taxi, then hands over the claim kit.
  await expect(page.locator("#booked")).toContainText("16:30");
  await expect(page.locator("#taxi")).toContainText("16:05");
  await expect(page.locator("#summary")).toContainText("Submit within 30 days");
  await expect(page.locator("body")).toHaveAttribute("data-done", "true");
  // Park the cursor out of the way and hold the end frame.
  await humanMove(page, 1880, 1040);
  await beat(page, 3000);

  writeFileSync(join(outDir, "events.json"), JSON.stringify({ events }));
});
