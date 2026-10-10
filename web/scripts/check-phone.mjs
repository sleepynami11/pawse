// Plain-Node check of the live phone agent with stubbed fetch (no browser, no speech, no Audio).
import assert from 'node:assert/strict';
import { validateResult } from '../src/contracts.js';

const story = {
  costs: { currency: 'CHF', treatment: 600, remaining_deductible: 300, reimbursement_rate: 0.8, reimbursed: 240, clinic: 385, home: 510 },
  calendar: { appointment: '16:30' },
  steps: [{ lines: [] }, { lines: [] },
    { lines: [
      { speaker: 'Pawse', german: 'Meine Katze Mimi hinkt.', subtitle: 'My cat limps.' },
      { speaker: 'Vet · simulated', german: 'Termin um 16:30.', subtitle: 'Appointment at 16:30.' }] },
    { lines: [
      { speaker: 'Pawse', german: 'Ist das gedeckt?', subtitle: 'Is it covered?' },
      { speaker: 'Insurer · simulated', german: 'Ja, 80 Prozent.', subtitle: 'Yes, 80%.' }] }],
};
const calls = [];
globalThis.fetch = async (url, opts) => {
  calls.push(String(url));
  if (String(url).endsWith('/api/v1/demo/mimi')) return { ok: true, status: 200, json: async () => story };
  return { ok: false, status: 503, blob: async () => null };
};

const { createLivePhoneCall } = await import('../src/agents/livePhoneAgent.js');

async function runCall(target, context = {}) {
  const call = createLivePhoneCall({ target, lang: 'en', context, speed: 1000 });
  const ev = [];
  call.on((e) => ev.push(e));
  call.start();
  for (let i = 0; i < 400 && !ev.some((e) => e.type === 'status' && e.state === 'ended'); i++) await new Promise((r) => setTimeout(r, 10));
  return { call, ev };
}

for (const [target, ctx] of [['vet', { clinic: { name: 'Praxis X' } }], ['insurance', { gradiumConsent: true }]]) {
  const { call, ev } = await runCall(target, ctx);
  const states = ev.filter((e) => e.type === 'status').map((e) => e.state);
  assert.deepEqual(states, ['dialing', 'connected', 'ended'], `${target} status order`);
  const lines = ev.filter((e) => e.type === 'line');
  assert.ok(lines[0].who === 'ai' && lines[0].original.includes('KI-Assistent'), 'first line discloses KI-Assistent');
  assert.ok(lines.filter((l) => l.who === 'callee').length >= 1);
  assert.ok(lines.filter((l) => l.who === 'callee').every((l) => l.simulated === true), 'callee lines simulated');
  const r = ev.find((e) => e.type === 'result');
  assert.ok(r && r.simulated === true, 'result simulated');
  assert.deepEqual(validateResult(target, r), [], `${target} result valid`);
  if (target === 'vet') assert.equal(r.place, 'Praxis X');
  else { assert.equal(r.reimbursed, 240); assert.equal(r.outOfPocket, 360); assert.ok(r.points.some((p) => !p.ok)); }
  const n = ev.length;
  call.hangup(); call.hangup();
  assert.equal(ev.length, n, 'hangup after end is a no-op');
  assert.ok(!ev.some((e) => e.type === 'error'), 'no error event');
}

// hangup mid-call ends exactly once
{
  const call = createLivePhoneCall({ target: 'vet', lang: 'en', speed: 1 });
  const ev = [];
  call.on((e) => ev.push(e));
  call.start();
  await new Promise((r) => setTimeout(r, 20));
  call.hangup(); call.hangup();
  await new Promise((r) => setTimeout(r, 100));
  assert.equal(ev.filter((e) => e.type === 'status' && e.state === 'ended').length, 1);
  assert.ok(!ev.some((e) => e.type === 'result'));
}
console.log('check-phone: OK');
