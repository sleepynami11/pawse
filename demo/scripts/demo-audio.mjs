// Pure, offline WAV synthesizer for the demo soundtrack. Playwright records video only, so
// finalize-demo.mjs calls buildPassWav with the recorded action log and muxes the result onto
// the trimmed video pass. No filesystem and no ffmpeg here, so the render math is unit-testable.
//
// Times in the log are raw-video seconds (Date.now() - t0). startSec is the head-trim, so a
// click at raw t lands at t - startSec in the trimmed pass, keeping sound in step with picture.
// Noise is seeded by sample index, never Math.random, so renders are identical across runs.

const TAU = Math.PI * 2;

// Deterministic pseudo-noise in [-1, 1], keyed by sample index for repeatable renders.
function noise(i) {
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return 2 * (x - Math.floor(x)) - 1;
}

// Render the single recorded pass to mono float samples in [-1, 1].
// - click: a ~45ms transient, a 1.8kHz sine blended with a short noise burst under an
//   exponential-decay envelope; the audible blip synchronized to each on-camera click.
// - move: a faint noise swish over the glide interval with a sine attack/release (set
//   moveGain to 0 to drop it).
// - type: faint, evenly spaced key ticks across the typing interval.
export function renderPassSamples({
  events = [],
  passDurationSec,
  startSec = 0,
  sampleRate = 44100,
  clickGain = 0.5,
  moveGain = 0.04,
  typeGain = 0.07,
}) {
  const n = Math.max(0, Math.round(passDurationSec * sampleRate));
  const out = new Float32Array(n);

  const addClick = (tSec) => {
    const start = Math.round(tSec * sampleRate);
    const dur = Math.round(0.045 * sampleRate);
    for (let k = 0; k < dur; k++) {
      const i = start + k;
      if (i < 0 || i >= n) continue;
      const tt = k / sampleRate;
      const env = Math.exp(-tt / 0.012);
      const tone = Math.sin(TAU * 1800 * tt);
      const burst = noise(i) * Math.exp(-tt / 0.004);
      out[i] += clickGain * env * (0.7 * tone + 0.3 * burst);
    }
  };

  const addMove = (tSec, durSec) => {
    if (moveGain <= 0 || !(durSec > 0)) return;
    const start = Math.round(tSec * sampleRate);
    const len = Math.round(durSec * sampleRate);
    for (let k = 0; k < len; k++) {
      const i = start + k;
      if (i < 0 || i >= n) continue;
      const p = k / len;
      const env = Math.sin(Math.PI * p); // gentle attack then release
      // Crude low-pass: average neighbouring noise taps to tame the harsh top end.
      const s = (noise(i) + noise(i - 1) + noise(i - 2)) / 3;
      out[i] += moveGain * env * s;
    }
  };

  const addType = (tSec, durSec, count) => {
    if (typeGain <= 0 || !(count > 0) || !(durSec > 0)) return;
    const tickDur = Math.round(0.008 * sampleRate);
    for (let j = 0; j < count; j++) {
      const start = Math.round((tSec + (durSec * j) / count) * sampleRate);
      for (let k = 0; k < tickDur; k++) {
        const i = start + k;
        if (i < 0 || i >= n) continue;
        out[i] += typeGain * Math.exp(-(k / sampleRate) / 0.002) * noise(i);
      }
    }
  };

  for (const ev of events) {
    const t = (ev.t ?? 0) - startSec;
    if (ev.kind === "click") addClick(t);
    else if (ev.kind === "move") addMove(t, ev.dur ?? 0);
    else if (ev.kind === "type") addType(t, ev.dur ?? 0, ev.n ?? 0);
  }

  // Soft-clip so summed transients never wrap; tanh leaves small signals nearly untouched.
  for (let i = 0; i < n; i++) out[i] = Math.tanh(out[i]);
  return out;
}

// Encode mono float samples to a 16-bit PCM RIFF/WAVE Buffer.
export function encodeWav(samples, sampleRate = 44100) {
  const numSamples = samples.length;
  const bytesPerSample = 2;
  const dataSize = numSamples * bytesPerSample;
  const buf = Buffer.alloc(44 + dataSize);
  buf.write("RIFF", 0, "ascii");
  buf.writeUInt32LE(36 + dataSize, 4);
  buf.write("WAVE", 8, "ascii");
  buf.write("fmt ", 12, "ascii");
  buf.writeUInt32LE(16, 16); // PCM fmt chunk size
  buf.writeUInt16LE(1, 20); // audio format: PCM
  buf.writeUInt16LE(1, 22); // channels: mono
  buf.writeUInt32LE(sampleRate, 24);
  buf.writeUInt32LE(sampleRate * bytesPerSample, 28); // byte rate
  buf.writeUInt16LE(bytesPerSample, 32); // block align
  buf.writeUInt16LE(16, 34); // bits per sample
  buf.write("data", 36, "ascii");
  buf.writeUInt32LE(dataSize, 40);
  let off = 44;
  for (let i = 0; i < numSamples; i++) {
    const c = Math.max(-1, Math.min(1, samples[i]));
    buf.writeInt16LE((c < 0 ? c * 0x8000 : c * 0x7fff) | 0, off);
    off += 2;
  }
  return buf;
}

// Render + encode in one call; what finalize-demo.mjs writes to _pass.wav.
export function buildPassWav(opts) {
  const sampleRate = opts.sampleRate ?? 44100;
  return encodeWav(renderPassSamples({ ...opts, sampleRate }), sampleRate);
}
