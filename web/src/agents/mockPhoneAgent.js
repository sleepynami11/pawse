// Scripted phone call: Pawse calls the vet or the insurer in German, in the background.
// The owner gets English progress steps, questions when a decision is needed, and the result;
// the German audio only plays if they choose to listen in.
// Implements the PHONE AGENT contract in ../contracts.js.

import { phoneScripts, buildVetResult, buildInsuranceResult, DEFAULT_ESTIMATE, AUTO_REPLY_MS } from './mockScripts.js';
import { speak, stopSpeech } from './speech.js';

export function createMockPhoneCall({ target = 'vet', lang = 'zh', context = {}, speed = 1 } = {}) {
  const script = phoneScripts[target] || phoneScripts.vet;
  const L = (o) => o[lang] ?? o.en;
  const listeners = new Set();
  const timers = new Set();
  const answers = {};
  let pendingQuestion = null; // { id, resolve }
  let listening = false;
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

  // Pauses the call until the owner answers. In rehearsal / tests (speed > 1) the fallback is
  // picked automatically so the demo runs hands-free; at normal speed it waits for the owner.
  function ask(q) {
    emit({
      type: 'question',
      id: q.id,
      text: L(q.text),
      options: q.options.map((o) => ({ id: o.id, label: L(o.label) })),
    });
    return new Promise((resolve) => {
      pendingQuestion = { id: q.id, resolve };
      if (speed > 1) {
        const tid = setTimeout(() => answer(q.id, q.fallback), AUTO_REPLY_MS / speed);
        timers.add(tid);
      }
    });
  }

  function answer(id, optionId) {
    if (!pendingQuestion || pendingQuestion.id !== id) return;
    const { resolve } = pendingQuestion;
    pendingQuestion = null;
    answers[id] = optionId;
    emit({ type: 'answered', id, optionId });
    resolve(optionId);
  }

  async function playLines(lines) {
    for (const line of lines) {
      if (line.question) {
        const choice = await ask(line.question);
        if (ended) return;
        await playLines(line.branches[choice] || line.branches[line.question.fallback]);
        if (ended) return;
        continue;
      }
      await wait(450);
      if (ended) return;
      if (line.step) emit({ type: 'progress', text: L(line.step) });
      emit({ type: 'speaking', who: line.who });
      emit({ type: 'line', who: line.who, original: line.de, text: L(line.text) });
      await speak(line.de, 'de', { speed, silent: !listening, pitch: line.who === 'callee' ? 0.8 : 1.15 });
      if (ended) return;
      emit({ type: 'speaking', who: 'none' });
    }
  }

  async function run() {
    emit({ type: 'status', state: 'dialing' });
    await wait(2400);
    if (ended) return;
    emit({ type: 'status', state: 'connected' });
    await playLines(script.lines);
    if (ended) return;
    await wait(500);
    if (ended) return;
    const result =
      target === 'insurance'
        ? buildInsuranceResult(
            lang,
            typeof context.estimate === 'number' ? context.estimate : DEFAULT_ESTIMATE,
            typeof context.homeVisitFee === 'number' ? context.homeVisitFee : 0
          )
        : buildVetResult(lang, context.clinic, answers.slot);
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
    answer,
    /** Play the German call audio (true) or keep it in the background (false, the default). */
    setListening(on) {
      listening = !!on;
      if (!listening) stopSpeech();
    },
    hangup() {
      if (ended) return;
      emit({ type: 'status', state: 'ended' });
      ended = true;
      pendingQuestion = null;
      timers.forEach(clearTimeout);
      timers.clear();
      stopSpeech();
    },
  };
}
