import { useEffect, useState } from 'react';

/** RMS of a time-domain buffer mapped to 0..1 (normal speech lands around 0.3-0.8). */
export function micLevel(buf) {
  let sum = 0;
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
  const rms = Math.sqrt(sum / (buf.length || 1));
  return Math.min(1, rms * 8);
}

/**
 * Live microphone loudness for visual feedback, 0..1, smoothed and updated ~15x a second.
 * Pass null to stop metering. Uses its own AudioContext so it never touches what the agent sends.
 */
export default function useMicLevel(stream) {
  const [level, setLevel] = useState(0);

  useEffect(() => {
    const AC = globalThis.AudioContext || globalThis.webkitAudioContext;
    if (!stream || !AC || !stream.getAudioTracks?.().length) {
      setLevel(0);
      return undefined;
    }
    let ctx;
    let timer = null;
    const resume = () => ctx && ctx.state === 'suspended' && ctx.resume().catch(() => {});
    try {
      ctx = new AC();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaStreamSource(stream).connect(analyser);
      const buf = new Float32Array(analyser.fftSize);
      let smooth = 0;
      let shown = 0;
      timer = setInterval(() => {
        analyser.getFloatTimeDomainData(buf);
        const now = micLevel(buf);
        smooth = now > smooth ? now : smooth * 0.75 + now * 0.25; // fast attack, slow release
        const rounded = Math.round(smooth * 20) / 20;
        if (rounded !== shown) {
          shown = rounded;
          setLevel(rounded);
        }
      }, 66);
      resume();
      window.addEventListener('pointerdown', resume);
    } catch {
      /* metering is best effort */
    }
    return () => {
      clearInterval(timer);
      window.removeEventListener('pointerdown', resume);
      try {
        ctx && ctx.close();
      } catch {
        /* ignore */
      }
      setLevel(0);
    };
  }, [stream]);

  return level;
}
