import { describe, it, expect } from "vitest";
// @unit. Pure render math for the demo soundtrack: no ffmpeg, no browser, no filesystem.
// Proves a transient lands exactly at each recorded click, that gaps stay silent, and that
// the WAV header is a well-formed mono 16-bit PCM stream sized to the samples.
import { renderPassSamples, encodeWav, buildPassWav } from "./demo-audio.mjs";

const SR = 44100;

// RMS of samples in the window [tSec, tSec + winSec).
function rmsAt(samples: Float32Array, tSec: number, winSec: number, sampleRate = SR) {
  const start = Math.round(tSec * sampleRate);
  const len = Math.round(winSec * sampleRate);
  let sum = 0;
  for (let k = 0; k < len; k++) sum += samples[start + k] ** 2;
  return Math.sqrt(sum / len);
}

describe("demo-audio renderPassSamples (@unit)", () => {
  const events = [
    { kind: "click", t: 1.0 },
    { kind: "click", t: 2.0 },
  ];
  // moveGain 0 isolates clicks so the gaps are provably silent.
  const samples = renderPassSamples({ events, passDurationSec: 3, startSec: 0, moveGain: 0 });

  it("renders exactly passDurationSec * sampleRate mono samples", () => {
    expect(samples.length).toBe(Math.round(3 * SR));
  });

  it("places an audible transient at each click and silence between", () => {
    const win = 0.05;
    const c1 = rmsAt(samples, 1.0, win);
    const c2 = rmsAt(samples, 2.0, win);
    const quiet = rmsAt(samples, 0.5, win);
    expect(quiet).toBe(0); // no events near 0.5s -> exact silence
    expect(c1).toBeGreaterThan(0.05);
    expect(c2).toBeGreaterThan(0.05);
    expect(c1).toBeGreaterThan(quiet * 10 + 0.01);
    expect(c2).toBeGreaterThan(quiet * 10 + 0.01);
  });

  it("subtracts startSec so a click maps into trimmed-pass time", () => {
    // Click recorded at raw t=2.0 with a 1.0s head-trim lands at 1.0s in the pass.
    const trimmed = renderPassSamples({
      events: [{ kind: "click", t: 2.0 }],
      passDurationSec: 3,
      startSec: 1.0,
      moveGain: 0,
    });
    expect(rmsAt(trimmed, 1.0, 0.05)).toBeGreaterThan(0.05);
    expect(rmsAt(trimmed, 2.0, 0.05)).toBe(0);
  });
});

describe("demo-audio encodeWav (@unit)", () => {
  it("writes a mono 16-bit PCM RIFF/WAVE header sized to the samples", () => {
    const wav = buildPassWav({ events: [{ kind: "click", t: 0.1 }], passDurationSec: 0.5 });
    expect(wav.toString("ascii", 0, 4)).toBe("RIFF");
    expect(wav.toString("ascii", 8, 12)).toBe("WAVE");
    expect(wav.readUInt16LE(20)).toBe(1); // PCM
    expect(wav.readUInt16LE(22)).toBe(1); // mono
    expect(wav.readUInt32LE(24)).toBe(SR); // sample rate
    expect(wav.readUInt16LE(34)).toBe(16); // bits per sample
    expect(wav.toString("ascii", 36, 40)).toBe("data");
    const numSamples = Math.round(0.5 * SR);
    expect(wav.readUInt32LE(40)).toBe(numSamples * 2); // data chunk = samples * 2 bytes
    expect(wav.length).toBe(44 + numSamples * 2);
  });

  it("clamps out-of-range samples without overflowing 16-bit range", () => {
    const wav = encodeWav(new Float32Array([2, -2, 0]), SR);
    expect(wav.readInt16LE(44)).toBe(0x7fff);
    expect(wav.readInt16LE(46)).toBe(-0x8000);
    expect(wav.readInt16LE(48)).toBe(0);
  });
});
