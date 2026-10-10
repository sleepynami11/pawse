// SLOT 1: live voice agent, turn-based over the same-origin Pawse REST API.
//   mic -> (silence detection) -> WAV -> POST /api/v1/voice/transcriptions -> user transcript
//   text -> POST /api/v1/care/requests (non-stream JSON) -> triage event + spoken verdict
// Implements the VOICE AGENT contract in ../contracts.js. Browser APIs are looked up lazily so the
// module also loads (and is testable) in plain Node.

import { VOICE_AGENT_URL } from '../config.js';
import { speak, stopSpeech } from './speech.js';

const T = {
  en: {
    greet: "Hi, I'm Pawse. Tell me what's going on with your cat. You can also send a photo.",
    chips: ['Limping', 'Not eating', 'Vomiting', 'Breathing fast'],
    headline: { red: 'See an emergency vet now', yellow: 'Contact a vet today', green: 'Keep watching' },
    fallbackStep: 'Call a veterinarian and describe what you see.',
    noSpeech: "I couldn't make out what you said. Please try again or type it.",
    errTranscribe: 'Could not transcribe your voice. Please try again or type your message.',
    errCare: 'Could not get advice right now. Please try again in a moment.',
    errPhoto: 'This photo type is not supported. Use JPEG, PNG or WebP.',
    errMic: 'Microphone recording is not available. You can type instead.',
    ownerLabel: 'Owner',
  },
  zh: {
    greet: '你好，我是 Pawse。请告诉我你的猫怎么了，也可以发一张照片。',
    chips: ['一瘸一拐', '不吃东西', '呕吐', '呼吸急促'],
    headline: { red: '请立即去急诊', yellow: '今天联系兽医', green: '继续观察' },
    fallbackStep: '联系兽医并说明你看到的情况。',
    noSpeech: '我没听清，请再说一次或直接打字。',
    errTranscribe: '语音识别失败，请重试或直接打字。',
    errCare: '暂时无法给出建议，请稍后再试。',
    errPhoto: '不支持这种照片格式，请使用 JPEG、PNG 或 WebP。',
    errMic: '无法录音，你可以直接打字。',
    ownerLabel: '主人',
  },
};

const SILENCE_MS = 1500;
const SPEECH_RMS = 0.02;
const MIN_SPEECH_MS = 400;
const MAX_TURN_MS = 30000;
const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

/** Backend urgency -> UI level. Never "green": the backend cannot rule out an emergency. */
export function urgencyToLevel(urgency) {
  return urgency === 'emergency' ? 'red' : 'yellow';
}

export function mapCareResult(res, lang = 'en') {
  const t = T[lang] || T.en;
  const a = (res && res.assessment) || {};
  const level = urgencyToLevel(a.urgency);
  const steps = [...(a.questions || []), ...(a.services_to_ask_about || [])].filter(Boolean);
  if (!steps.length) steps.push(t.fallbackStep);
  const out = {
    type: 'triage',
    level,
    headline: t.headline[level],
    steps,
    summary: a.summary || (res && res.handoff) || t.headline[level],
  };
  if (level === 'red') out.escalation = a.summary || t.headline.red;
  return out;
}

function encodeWav(samples, rate) {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);
  const w = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  w(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); w(8, 'WAVE'); w(12, 'fmt ');
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  w(36, 'data'); v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Uint8Array(buf);
}

function toBase64(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

/** Recorded Blob (webm/mp4/...) -> base64 mono 16 kHz 16-bit WAV. Returns null if under 0.5 s. */
async function blobToWavBase64(blob) {
  const AC = globalThis.AudioContext || globalThis.webkitAudioContext;
  const ctx = new AC();
  try {
    const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
    const rate = 16000;
    const off = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * rate)), rate);
    const src = off.createBufferSource();
    src.buffer = decoded;
    src.connect(off.destination);
    src.start();
    const rendered = await off.startRendering();
    const pcm = rendered.getChannelData(0);
    if (pcm.length < rate * 0.5) return null;
    return toBase64(encodeWav(pcm.subarray(0, rate * 59), rate));
  } finally {
    try { ctx.close(); } catch { /* ignore */ }
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(',')[1] || '');
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

export function createLiveVoiceAgent({ lang = 'zh' } = {}) {
  const t = T[lang] || T.en;
  const apiLang = lang === 'zh' ? 'zh' : 'en';
  const base = (VOICE_AGENT_URL || '').replace(/\/$/, '');
  const listeners = new Set();
  const userTurns = [];
  let started = false;
  let ended = false;
  let muted = false;
  let aiSpeaking = false;
  let photo = null; // { mime_type, data }
  let queue = Promise.resolve();
  let stream = null;
  let recorder = null;
  let chunks = [];
  let audioCtx = null;
  let poll = null;
  let heardMs = 0;
  let silentMs = 0;
  let turnMs = 0;

  const emit = (e) => {
    if (ended && e.type !== 'ended') return;
    listeners.forEach((l) => {
      try { l(e); } catch { /* a bad listener must not break the call */ }
    });
  };
  const fail = (message) => emit({ type: 'error', message });

  async function api(path, body) {
    const ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timer = ctl && setTimeout(() => ctl.abort(), 60000);
    try {
      const res = await fetch(`${base}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: ctl ? ctl.signal : undefined,
      });
      if (!res.ok) {
        let detail = '';
        try { const j = await res.json(); detail = typeof j.detail === 'string' ? j.detail : ''; } catch { /* ignore */ }
        throw new Error(detail || `HTTP ${res.status}`);
      }
      return await res.json();
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  async function say(text) {
    if (ended) return;
    aiSpeaking = true;
    emit({ type: 'listening', on: false });
    emit({ type: 'speaking', who: 'ai' });
    emit({ type: 'transcript', role: 'ai', text });
    try { await speak(text, lang); } catch { /* speech is best effort */ }
    aiSpeaking = false;
    if (ended) return;
    emit({ type: 'speaking', who: 'none' });
    emit({ type: 'listening', on: !muted });
    resetTurn();
  }

  async function advise() {
    const query = userTurns.join('\n');
    const body = { query, language: apiLang, share_with_ai: true };
    if (photo) body.photo = photo;
    let res;
    try {
      res = await api('/api/v1/care/requests', body);
    } catch (err) {
      fail(`${t.errCare} (${err.message})`);
      emit({ type: 'listening', on: !muted });
      return;
    }
    if (ended) return;
    const triage = mapCareResult(res, lang);
    emit(triage);
    await say(triage.summary);
  }

  const enqueue = (fn) => {
    queue = queue.then(fn).catch((err) => fail(String(err && err.message || err)));
    return queue;
  };

  function takeUserText(text) {
    userTurns.push(text);
    emit({ type: 'speaking', who: 'user' });
    emit({ type: 'transcript', role: 'user', text });
    emit({ type: 'suggestions', items: [] });
    emit({ type: 'speaking', who: 'none' });
    return advise();
  }

  async function transcribe(blob) {
    let wav;
    try {
      wav = await blobToWavBase64(blob);
    } catch {
      fail(t.errTranscribe);
      return;
    }
    if (!wav || ended) return;
    let out;
    try {
      out = await api('/api/v1/voice/transcriptions', { audio: { data: wav }, language: apiLang, share_with_gemini: true });
    } catch (err) {
      fail(`${t.errTranscribe} (${err.message})`);
      return;
    }
    const text = String((out && out.text) || '').trim();
    if (!text) { fail(t.noSpeech); return; }
    await takeUserText(text);
  }

  // --- recording with silence detection -----------------------------------------------------
  function resetTurn() {
    heardMs = 0; silentMs = 0; turnMs = 0;
    if (recorder && recorder.state === 'inactive') startRecorder();
  }

  function startRecorder() {
    if (!stream || ended) return;
    chunks = [];
    heardMs = 0; silentMs = 0; turnMs = 0;
    try {
      recorder = new MediaRecorder(new MediaStream(stream.getAudioTracks()));
    } catch {
      fail(t.errMic);
      return;
    }
    const rec = recorder;
    rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    rec.onstop = () => {
      const keep = rec.keepTurn;
      const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
      chunks = [];
      if (keep && !ended) enqueue(() => transcribe(blob));
      if (!ended && recorder === rec) startRecorder();
    };
    rec.start();
  }

  function finishTurn(keep) {
    if (!recorder || recorder.state !== 'recording') return;
    recorder.keepTurn = keep;
    emit({ type: 'speaking', who: 'none' });
    try { recorder.stop(); } catch { /* ignore */ }
  }

  function tick(analyser, buf, step) {
    if (ended) return;
    if (muted || aiSpeaking) { heardMs = 0; silentMs = 0; turnMs = 0; return; }
    analyser.getFloatTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
    const loud = Math.sqrt(sum / buf.length) > SPEECH_RMS;
    if (loud) {
      if (heardMs === 0) emit({ type: 'speaking', who: 'user' });
      heardMs += step; silentMs = 0;
    } else if (heardMs > 0) {
      silentMs += step;
    }
    turnMs += step;
    if (heardMs >= MIN_SPEECH_MS && (silentMs >= SILENCE_MS || turnMs >= MAX_TURN_MS)) {
      finishTurn(true);
    } else if (heardMs === 0 && turnMs >= 10000) {
      finishTurn(false); // nothing said: recycle the recorder, discard
    } else if (heardMs > 0 && heardMs < MIN_SPEECH_MS && silentMs >= SILENCE_MS) {
      finishTurn(false); // a click or cough
    }
  }

  function stopRecording() {
    if (poll) { clearInterval(poll); poll = null; }
    if (recorder) {
      recorder.keepTurn = false;
      try { if (recorder.state !== 'inactive') recorder.stop(); } catch { /* ignore */ }
      recorder = null;
    }
    try { audioCtx && audioCtx.close(); } catch { /* ignore */ }
    audioCtx = null;
  }

  return {
    wantsAudio: true,
    on(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    start() {
      if (started || ended) return;
      started = true;
      enqueue(async () => {
        emit({ type: 'suggestions', items: t.chips });
        await say(t.greet);
        emit({ type: 'listening', on: !muted });
      });
    },
    end() {
      if (ended) return;
      stopRecording();
      stopSpeech();
      if (stream) { try { stream.getTracks().forEach((tr) => tr.stop()); } catch { /* ignore */ } }
      stream = null;
      ended = true;
      listeners.forEach((l) => { try { l({ type: 'ended' }); } catch { /* ignore */ } });
    },
    sendText(text) {
      const s = String(text || '').trim();
      if (!s || ended) return;
      stopSpeech();
      aiSpeaking = false;
      enqueue(() => takeUserText(s));
    },
    async sendImage(file) {
      if (ended || !file) return;
      const mime = file.type;
      if (!PHOTO_TYPES.includes(mime)) { fail(t.errPhoto); return; }
      try {
        photo = { mime_type: mime, data: await fileToBase64(file) };
      } catch {
        fail(t.errPhoto);
        return;
      }
      emit({ type: 'image_received' });
    },
    attachMedia({ audio } = {}) {
      if (ended || !audio || audio === stream) return;
      stopRecording();
      stream = audio;
      const AC = globalThis.AudioContext || globalThis.webkitAudioContext;
      if (!AC || typeof MediaRecorder === 'undefined') { fail(t.errMic); return; }
      try {
        audioCtx = new AC();
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 1024;
        audioCtx.createMediaStreamSource(audio).connect(analyser);
        const buf = new Float32Array(analyser.fftSize);
        startRecorder();
        poll = setInterval(() => tick(analyser, buf, 100), 100);
      } catch {
        fail(t.errMic);
      }
    },
    setMicMuted(m) {
      muted = !!m;
      if (!started || ended) return;
      emit({ type: 'listening', on: !muted && !aiSpeaking });
      if (muted && heardMs > 0) finishTurn(false);
    },
  };
}
