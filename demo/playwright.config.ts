import { defineConfig } from "@playwright/test";

// Scripted demo recorder (same setup as the SwissHacks 2026 DRIFTWATCH recorder). It records a
// 1920x1080 video of the single narrative spec into demo-out/. The page under test is the static
// mock in mock/ (no backend, no model key), served by Python's built-in http.server, so the take is
// offline and deterministic. Point baseURL at the real app once it can run the story end to end.

const PORT = 4173;
const baseURL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/demo-recording.spec.ts",
  outputDir: "demo-out",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 300_000,
  expect: { timeout: 30_000 },
  reporter: "list",
  use: {
    baseURL,
    viewport: { width: 1920, height: 1080 },
    video: { mode: "on", size: { width: 1920, height: 1080 } },
  },
  webServer: {
    command: `python3 -m http.server ${PORT} --bind 127.0.0.1 --directory mock`,
    url: baseURL,
    timeout: 30_000,
    reuseExistingServer: !process.env.CI,
  },
});
