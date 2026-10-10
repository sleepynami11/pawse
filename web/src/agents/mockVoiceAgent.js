// Scripted Pawse voice call. Speaks with the browser's voice, waits for the user to type or
// tap a keyword (or "hears" a scripted answer after a few seconds), then gives triage.
// Camera and photos are optional: the mock accepts them but doesn't analyse them.
// Implements the VOICE AGENT contract in ../contracts.js.

import { voiceScript as S, AUTO_REPLY_MS } from './mockScripts.js';
import { speak, stopSpeech } from './speech.js';

export function createMockVoiceAgent({ lang = 'zh', speed = 1 } = {}) {
  const L = (o) => o[lang] ?? o.en;
  const listeners = new Set();
  const timers = new Set();
  let started = false;
  let ended = false;
  let pending = null; // resolves the current "waiting for the user" step
  let thanked = false;

  const emit = (e) => {
    if (!ended) listeners.forEach((l) => l(e));
  };

  const wait = (ms) =>
    new Promise((resolve) => {
      const id = setTimeout(() => {
        timers.delete(id);
        resolve();
      }, ms / speed);
      timers.add(id);
    });

  async function say(text) {
    if (ended) return;
    emit({ type: 'speaking', who: 'ai' });
    emit({ type: 'transcript', role: 'ai', text });
    await speak(text, lang, { speed });
    emit({ type: 'speaking', who: 'none' });
  }

  function waitForUser(fallback, chips) {
    emit({ type: 'suggestions', items: chips });
    emit({ type: 'listening', on: true });
    return new Promise((resolve) => {
      const finish = (text, simulated) => {
        pending = null;
        clearTimeout(id);
        timers.delete(id);
        if (ended) return resolve(null);
        emit({ type: 'listening', on: false });
        emit({ type: 'suggestions', items: [] });
        emit({ type: 'speaking', who: 'user' });
        emit({ type: 'transcript', role: 'user', text, simulated });
        resolve(text);
      };
      const id = setTimeout(() => finish(fallback, true), AUTO_REPLY_MS / speed);
      timers.add(id);
      pending = (text) => finish(text, false);
    });
  }

  async function run() {
    await wait(800);
    await say(L(S.greet));
    if (ended) return;
    await waitForUser(L(S.user1), S.chips0[lang] || S.chips0.en);
    if (ended) return;
    await wait(900);
    await say(L(S.ask));
    if (ended) return;
    await waitForUser(L(S.user2), S.chips1[lang] || S.chips1.en);
    if (ended) return;
    await wait(900);
    await say(L(S.verdict));
    if (ended) return;
    emit({
      type: 'triage',
      level: S.triage.level,
      headline: L(S.triage.headline),
      steps: S.triage.steps[lang] || S.triage.steps.en,
      escalation: L(S.triage.escalation),
      summary: L(S.triage.summary),
    });
  }

  return {
    wantsAudio: false, // the mock doesn't listen, so don't ask for the microphone
    on(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    start() {
      if (started) return;
      started = true;
      run();
    },
    end() {
      if (ended) return;
      ended = true;
      timers.forEach(clearTimeout);
      timers.clear();
      stopSpeech();
      if (pending) pending('');
      listeners.forEach((l) => l({ type: 'ended' }));
    },
    sendText(text) {
      const s = String(text || '').trim();
      if (!s || ended) return;
      if (pending) pending(s);
      else emit({ type: 'transcript', role: 'user', text: s });
    },
    sendImage(file) {
      if (ended || !file) return;
      emit({ type: 'image_received' });
      if (!thanked) {
        thanked = true;
        // A short acknowledgement in the captions; the script keeps its own pace.
        emit({ type: 'transcript', role: 'ai', text: L(S.photoThanks) });
      }
    },
    attachMedia() {
      /* the mock doesn't listen or look */
    },
    setMicMuted() {
      /* nothing to mute in the mock */
    },
  };
}
