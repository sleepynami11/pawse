// Live phone agent for Pawse. There is NO telephony: the German script and the numbers come from
// the backend (GET /api/v1/demo/mimi), every AI line is spoken with the same Gradium German voice
// (POST /api/v1/voice/speech, only with explicit consent), and every callee reply and the result
// stay marked `simulated: true`. Nothing is ever dialled or booked. Implements ../contracts.js.
//
// One call = one server-issued call id: the first AI line carries the AI disclosure and the server
// answers with an X-Pawse-Call-Id header; later lines send that id so the server does not repeat
// the disclosure. If Gradium fails (no key, 503, network), the rest of the call uses browser speech
// so the voice never flips back and forth.

import { PHONE_AGENT_URL } from '../config.js';
import { speak, stopSpeech, isSpeechMuted } from './speech.js';

// Must equal DISCLOSURE in pawse/voice.py so the server does not prepend a second greeting.
const DISCLOSURE = 'Guten Tag, hier ist Pawse, die KI-Assistenz im Auftrag der Katzenhalterin oder des Katzenhalters.';
const FIRST_LINE = {
  original: `${DISCLOSURE} Ich bin ein KI-Assistent und kein Mensch.`,
  text: {
    en: 'Hello, this is Pawse, the AI assistant calling on behalf of the cat owner. I am an AI assistant, not a person.',
    zh: '您好，我是 Pawse，受猫主人委托的 AI 助手。我是 AI 助手，不是真人。',
  },
};
const STEP_INDEX = { vet: 2, insurance: 3 };
const T = (en, zh) => ({ en, zh });

const num = (v, d) => (typeof v === 'number' && Number.isFinite(v) ? v : d);

async function fetchStory(base) {
  const res = await fetch(`${base}/api/v1/demo/mimi`);
  if (!res.ok) throw new Error(`demo story unavailable (${res.status})`);
  return res.json();
}

/**
 * Fetches Gradium audio for the AI lines of one call, strictly in order (the first response
 * carries the call id the later ones need). Each line is fetched at most once, so the page can
 * preload the next AI line while the current one plays.
 */
function createGradiumLines(base, voice, state) {
  const cache = new Map();
  let chain = Promise.resolve();
  let callId = null;
  let failed = false;

  const request = async (text) => {
    if (failed || state.ended) return null;
    try {
      const res = await fetch(`${base}/api/v1/voice/speech`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, language: 'de', voice, share_with_gradium: true, ...(callId ? { call_id: callId } : {}) }),
      });
      if (!res.ok) throw new Error(`speech ${res.status}`);
      const id = res.headers && typeof res.headers.get === 'function' ? res.headers.get('x-pawse-call-id') : null;
      if (id) callId = id;
      return await res.blob();
    } catch {
      failed = true; // stay on browser speech for the rest of this call
      return null;
    }
  };

  return {
    get failed() {
      return failed;
    },
    /** Promise<Blob|null> for line `key`; queued behind every earlier request. */
    fetch(key, text) {
      if (!cache.has(key)) {
        const p = chain.then(() => request(text));
        chain = p;
        cache.set(key, p);
      }
      return cache.get(key);
    },
  };
}

/** Plays one audio blob. Resolves true if it played to the end, false to fall back. */
function playBlob(blob, state) {
  if (!blob || state.ended || typeof Audio === 'undefined' || typeof URL === 'undefined' || !URL.createObjectURL) {
    return Promise.resolve(false);
  }
  return new Promise((resolve) => {
    let url;
    try {
      url = URL.createObjectURL(blob);
    } catch {
      resolve(false);
      return;
    }
    const a = new Audio(url);
    state.audio = a;
    const done = (ok) => {
      if (state.audio === a) state.audio = null;
      try { URL.revokeObjectURL(url); } catch { /* ignore */ }
      resolve(ok);
    };
    a.onended = () => done(true);
    a.onerror = () => done(false);
    try {
      const p = a.play();
      if (p && p.catch) p.catch(() => done(false));
    } catch {
      done(false);
    }
  });
}

function buildVetResult(story, lang, context) {
  const c = story.costs || {};
  return {
    kind: 'appointment',
    time: story.calendar?.appointment || '16:30',
    place: context.clinic?.name || (lang === 'zh' ? '诊所（演示）' : 'Clinic (demo)'),
    estimate: num(c.treatment, 600),
    currency: c.currency || 'CHF',
    note:
      lang === 'zh'
        ? '模拟：这是演示脚本，没有真的打电话，也没有真的预约。上门另加约 150 瑞郎。'
        : 'Simulated: demo script, no real call was made and nothing was booked. A home visit would add about CHF 150.',
    simulated: true,
  };
}

function buildInsuranceResult(story, lang) {
  const c = story.costs || {};
  const deductible = num(c.remaining_deductible, 300);
  const rate = num(c.reimbursement_rate, 0.8);
  const estimate = num(c.treatment, 600);
  const reimbursed = num(c.reimbursed, Math.max(estimate - deductible, 0) * rate);
  const cur = c.currency || 'CHF';
  const zh = lang === 'zh';
  const clinic = num(c.clinic, 385);
  const home = num(c.home, 510);
  return {
    kind: 'coverage',
    covered: true,
    currency: cur,
    deductible,
    rate,
    estimate,
    reimbursed,
    outOfPocket: estimate - reimbursed,
    points: [
      { ok: true, text: zh ? '意外从第一天起就保' : 'Accident covered from day 1' },
      {
        ok: true,
        text: zh
          ? `先付前 ${deductible} 瑞郎，之后报销 ${Math.round(rate * 100)}%`
          : `You pay the first ${cur} ${deductible}, then ${Math.round(rate * 100)}% is reimbursed`,
      },
      { ok: false, text: zh ? '上门费不保' : 'Home visit not covered', ref: 'AVB 1.2' },
      { ok: false, text: zh ? '之后的理疗不保' : 'Physiotherapy not covered', ref: 'AVB 1.2' },
      {
        ok: true,
        text: zh
          ? `估算自付：诊所约 ${cur} ${clinic}，上门约 ${cur} ${home}（含出租车 / 上门费）`
          : `Estimated cost to you: clinic about ${cur} ${clinic} vs home visit about ${cur} ${home}`,
      },
    ],
    simulated: true,
  };
}

export function createLivePhoneCall({ target = 'vet', lang = 'zh', context = {}, speed = 1 } = {}) {
  const base = PHONE_AGENT_URL || '';
  const listeners = new Set();
  const timers = new Set();
  const state = { ended: false, audio: null };
  let started = false;

  const emit = (e) => {
    if (!state.ended) listeners.forEach((l) => l(e));
  };
  const wait = (ms) =>
    new Promise((resolve) => {
      const id = setTimeout(() => {
        timers.delete(id);
        resolve();
      }, ms / speed);
      timers.add(id);
    });

  // Gradium audio only with explicit consent from the page (context.gradiumConsent === true);
  // the page may withdraw or give it mid-call with setGradiumConsent().
  const voice = context.voice === 'my_voice' ? 'my_voice' : 'standard';
  let gradiumConsent = context.gradiumConsent === true;
  const gradium = createGradiumLines(base, voice, state);
  const useGradium = () => gradiumConsent && !gradium.failed && !isSpeechMuted() && typeof fetch === 'function';

  async function say(lines, i) {
    const line = lines[i];
    if (line.who === 'ai' && useGradium()) {
      const blob = await gradium.fetch(i, line.original);
      // Preload the next AI line while this one plays.
      const next = lines.findIndex((l, j) => j > i && l.who === 'ai');
      if (next >= 0 && useGradium()) gradium.fetch(next, lines[next].original);
      if (state.ended) return;
      if (await playBlob(blob, state)) return;
    }
    if (state.ended) return;
    await speak(line.original, 'de', { speed, pitch: line.who === 'callee' ? 0.8 : 1.15 });
  }

  async function run() {
    emit({ type: 'status', state: 'dialing' });
    let story;
    try {
      story = await fetchStory(base);
    } catch (err) {
      emit({ type: 'error', message: `Phone agent: ${err.message}` });
      finish();
      return;
    }
    await wait(1500);
    if (state.ended) return;
    emit({ type: 'status', state: 'connected' });

    const step = (story.steps || [])[STEP_INDEX[target] ?? 2] || { lines: [] };
    const lines = [
      { who: 'ai', original: FIRST_LINE.original, text: FIRST_LINE.text[lang] ?? FIRST_LINE.text.en },
      ...(step.lines || []).map((l) => ({
        who: /^pawse/i.test(l.speaker) ? 'ai' : 'callee',
        original: l.german,
        // The backend subtitles are English; the zh UI shows them as is rather than inventing a translation.
        text: l.subtitle,
      })),
    ];
    for (const [i, line] of lines.entries()) {
      await wait(450);
      if (state.ended) return;
      emit({ type: 'speaking', who: line.who });
      const ev = { type: 'line', who: line.who, original: line.original, text: line.text };
      if (line.who === 'callee') ev.simulated = true;
      emit(ev);
      await say(lines, i);
      if (state.ended) return;
      emit({ type: 'speaking', who: 'none' });
    }
    await wait(500);
    if (state.ended) return;
    emit({ type: 'result', ...(target === 'insurance' ? buildInsuranceResult(story, lang) : buildVetResult(story, lang, context)) });
    finish();
  }

  function finish() {
    if (state.ended) return;
    emit({ type: 'status', state: 'ended' });
    state.ended = true;
    timers.forEach(clearTimeout);
    timers.clear();
    if (state.audio) {
      try { state.audio.pause(); } catch { /* ignore */ }
      state.audio = null;
    }
    stopSpeech();
  }

  return {
    on(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    start() {
      if (started) return;
      started = true;
      run().catch((err) => {
        emit({ type: 'error', message: String(err && err.message ? err.message : err) });
        finish();
      });
    },
    hangup: finish,
    /** Give or withdraw consent for Gradium audio for the remaining lines of this call. */
    setGradiumConsent(on) {
      gradiumConsent = on === true;
    },
  };
}
