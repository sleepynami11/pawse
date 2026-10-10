// Post-step for the demo recorder. Playwright writes the take to demo-out/<slug>/video.webm;
// this copies it to a stable demo-out/pawse-demo.webm, and builds the polished
// demo-out/pawse-demo.mp4 if ffmpeg is on PATH (the safest format for a Google Slides
// demo slide). The mp4 is built in two steps: trim the opening browser load off the head
// (the cut point is demo-out/trim.json, written by the spec), then loop the clean pass
// DEMO_LOOPS times so the deliverable loops with no reload in the seam. The mp4 is best
// effort: if ffmpeg is missing the script prints the commands and exits cleanly, the webm
// still stands (note the raw webm keeps the load; the mp4 is the trimmed, looped one).
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, writeFileSync, rmSync, statSync, copyFileSync } from "node:fs";
import { join } from "node:path";
import { buildPassWav } from "./demo-audio.mjs";

const OUT_DIR = join(process.cwd(), "demo-out");
const WEBM = join(OUT_DIR, "pawse-demo.webm");
const MP4 = join(OUT_DIR, "pawse-demo.mp4");
const PASS_MP4 = join(OUT_DIR, "_pass.mp4");
const PASS_WAV = join(OUT_DIR, "_pass.wav");
const PASS_AV = join(OUT_DIR, "_pass_av.mp4");

// Where to cut the opening load (seconds), written by the recorder spec; 0 if absent.
function readTrimSec() {
  try {
    const v = JSON.parse(readFileSync(join(OUT_DIR, "trim.json"), "utf8")).startSec;
    return Number.isFinite(v) ? v : 0;
  } catch {
    return 0;
  }
}

// How many times the clean pass repeats in the deliverable (default 1, the 2-minute video;
// set DEMO_LOOPS=2+ for a looping slide clip).
const LOOPS = Math.max(1, Number(process.env.DEMO_LOOPS) || 1);

// The action log the recorder spec wrote (clicks/moves/typing with raw-video timestamps).
function readEvents() {
  try {
    const v = JSON.parse(readFileSync(join(OUT_DIR, "events.json"), "utf8")).events;
    return Array.isArray(v) ? v : null;
  } catch {
    return null;
  }
}

// Duration of the trimmed pass (seconds) via ffprobe, with an event-log fallback so the synth
// can still size the track if ffprobe is missing.
function passDurationSec(events, startSec) {
  const probe = spawnSync(
    "ffprobe",
    ["-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", PASS_MP4],
    { encoding: "utf8" },
  );
  const d = Number(String(probe.stdout).trim());
  if (Number.isFinite(d) && d > 0) return d;
  const maxT = events.reduce((m, e) => Math.max(m, e.t + (e.dur || 0)), 0);
  return Math.max(1, maxT - startSec + 1.0);
}

// Find the newest .webm Playwright produced under demo-out/.
function findNewestWebm(dir) {
  let newest = null;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      const inner = findNewestWebm(full);
      if (inner && (!newest || inner.mtimeMs > newest.mtimeMs)) newest = inner;
    } else if (entry.name.endsWith(".webm") && full !== WEBM) {
      const mtimeMs = statSync(full).mtimeMs;
      if (!newest || mtimeMs > newest.mtimeMs) newest = { path: full, mtimeMs };
    }
  }
  return newest;
}

if (!existsSync(OUT_DIR)) {
  console.error("No demo-out/ directory found. Did the recording run?");
  process.exit(1);
}

const found = findNewestWebm(OUT_DIR);
if (!found) {
  console.error("No recorded .webm found under demo-out/. Did the spec record a video?");
  process.exit(1);
}

copyFileSync(found.path, WEBM);
console.log(`Recording (raw, keeps the load): ${WEBM}`);

const startSec = readTrimSec();
const hasFfmpeg = spawnSync("ffmpeg", ["-version"], { stdio: "ignore" }).status === 0;
if (hasFfmpeg) {
  // 1) Trim the opening load off the head and re-encode to h264. -ss after -i so the seek
  //    is frame accurate (the webm has sparse keyframes; a fast pre-input seek would jump).
  const trim = spawnSync(
    "ffmpeg",
    ["-y", "-i", WEBM, "-ss", String(startSec),
     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-an", PASS_MP4],
    { stdio: "inherit" },
  );
  // 2) Synthesize a click/move soundtrack from the action log and mux it onto the pass, so the
  //    deliverable has sound in step with the picture. Looping the muxed file (not the silent
  //    one) restarts audio and video together each pass, so every loop stays synchronized.
  //    If there is no event log the pass stays video-only, the original behaviour.
  const events = readEvents();
  let withAudio = false;
  let loopInput = PASS_MP4;
  if (trim.status === 0 && events && events.length) {
    const wav = buildPassWav({ events, passDurationSec: passDurationSec(events, startSec), startSec });
    writeFileSync(PASS_WAV, wav);
    const mux = spawnSync(
      "ffmpeg",
      ["-y", "-i", PASS_MP4, "-i", PASS_WAV,
       "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", PASS_AV],
      { stdio: "inherit" },
    );
    if (mux.status === 0) {
      withAudio = true;
      loopInput = PASS_AV;
    } else {
      console.warn("Audio mux failed; falling back to a video-only loop.");
    }
  }

  // 3) Loop the clean pass into the deliverable. Identical encodes concat with a stream copy,
  //    so the seam is a hard cut back to the idle app with no reload flash.
  const loop = trim.status === 0
    ? spawnSync(
        "ffmpeg",
        ["-y", "-stream_loop", String(LOOPS - 1), "-i", loopInput, "-c", "copy", MP4],
        { stdio: "inherit" },
      )
    : { status: 1 };
  try { rmSync(PASS_MP4, { force: true }); } catch {}
  try { rmSync(PASS_WAV, { force: true }); } catch {}
  try { rmSync(PASS_AV, { force: true }); } catch {}
  if (trim.status === 0 && loop.status === 0) {
    const audioNote = withAudio ? ", with sound" : "";
    console.log(`MP4 (trimmed, looped ${LOOPS}x${audioNote}; use this in Google Slides): ${MP4}`);
  } else {
    console.warn("ffmpeg failed; the raw .webm above is still usable.");
  }
} else {
  console.log("ffmpeg not found; skipping mp4. To build it manually:");
  console.log(`  ffmpeg -i "${WEBM}" -ss ${startSec} -c:v libx264 -pix_fmt yuv420p -crf 20 -an "${PASS_MP4}"`);
  console.log(`  ffmpeg -stream_loop ${LOOPS - 1} -i "${PASS_MP4}" -c copy "${MP4}"`);
  console.log("Then in Google Slides: Insert > Video > upload the mp4 to Drive, set Play automatically.");
}
