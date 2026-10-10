// Scripted phone call: Pawse calls the vet or the insurer in German, with a live translation.
// Implements the PHONE AGENT contract in ../contracts.js.

import { phoneScripts, buildVetResult, buildInsuranceResult, DEFAULT_ESTIMATE } from './mockScripts.js';
import { speak, stopSpeech } from './speech.js';

export function createMockPhoneCall({ target = 'vet', lang = 'zh', context = {}, speed = 1 } = {}) {
  const script = phoneScripts[target] || phoneScripts.vet;
  const L = (o) => o[lang] ?? o.en;
  const listeners = new Set();
  const timers = new Set();
  let started = false;
  let ended = false;

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

  async function run() {
    emit({ type: 'status', state: 'dialing' });
    await wait(2400);
    if (ended) return;
    emit({ type: 'status', state: 'connected' });
    for (const line of script.lines) {
      await wait(450);
      if (ended) return;
      emit({ type: 'speaking', who: line.who });
      emit({ type: 'line', who: line.who, original: line.de, text: L(line.text) });
      await speak(line.de, 'de', { speed, pitch: line.who === 'callee' ? 0.8 : 1.15 });
      if (ended) return;
      emit({ type: 'speaking', who: 'none' });
    }
    await wait(500);
    if (ended) return;
    const result =
      target === 'insurance'
        ? buildInsuranceResult(lang, typeof context.estimate === 'number' ? context.estimate : DEFAULT_ESTIMATE)
        : buildVetResult(lang, context.clinic);
    emit({ type: 'result', ...result });
    emit({ type: 'status', state: 'ended' });
  }

  return {
    on(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    start() {
      if (started) return;
      started = true;
      run();
    },
    hangup() {
      if (ended) return;
      emit({ type: 'status', state: 'ended' });
      ended = true;
      timers.forEach(clearTimeout);
      timers.clear();
      stopSpeech();
    },
  };
}
