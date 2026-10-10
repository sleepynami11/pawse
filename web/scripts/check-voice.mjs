// Plain-Node check for the live voice agent with a stubbed fetch. Run: node web/scripts/check-voice.mjs
import assert from 'node:assert/strict';
import { createLiveVoiceAgent, mapCareResult } from '../src/agents/liveVoiceAgent.js';
import { validateTriage } from '../src/contracts.js';

let n = 0;
const ok = (m) => console.log(`  ok  ${++n} ${m}`);
const calls = [];
let mode = 'ok';
globalThis.fetch = async (url, init) => {
  const body = JSON.parse(init.body);
  calls.push({ url, body });
  if (mode === 'fail') return { ok: false, status: 502, json: async () => ({ detail: 'upstream down' }) };
  return {
    ok: true,
    status: 201,
    json: async () => ({
      care: { assessment: { urgency: 'contact_vet', summary: 'Please see a vet today.', questions: ['Did she fall?'], services_to_ask_about: ['X-ray'] },
      handoff: 'h' }, trace: [], actions: [],
    }),
  };
};

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const until = async (pred, ms = 8000) => { const t0 = Date.now(); while (!pred()) { if (Date.now() - t0 > ms) throw new Error('timeout'); await wait(20); } };

const a = createLiveVoiceAgent({ lang: 'en', shareWithGemini: true });
const ev = [];
a.on((e) => ev.push(e));
assert.equal(a.wantsAudio, true);
a.start();
await until(() => ev.some((e) => e.type === 'transcript'));
assert.equal(ev.find((e) => e.type === 'transcript').role, 'ai');
ok('greeting transcript comes first');
await until(() => ev.some((e) => e.type === 'listening' && e.on));
ok('listening on after greeting');

a.sendText('My cat is limping');
await until(() => ev.some((e) => e.type === 'triage'));
const iu = ev.findIndex((e) => e.type === 'transcript' && e.role === 'user');
const it = ev.findIndex((e) => e.type === 'triage');
assert.ok(iu > 0 && iu < it);
assert.deepEqual(validateTriage(ev[it]), []);
assert.equal(ev[it].level, 'yellow');
assert.equal(calls[0].url, '/api/v1/agents/runs');
assert.equal(calls[0].body.care.query, 'My cat is limping');
assert.equal(calls[0].body.care.share_with_ai, true);
ok('sendText -> user transcript -> valid triage via /api/v1/care/requests');

assert.equal(mapCareResult({ assessment: { urgency: 'emergency', summary: 's' } }).level, 'red');
assert.deepEqual(validateTriage(mapCareResult({ assessment: { urgency: 'unknown', summary: 's' } })), []);
ok('urgency mapping (emergency=red, else yellow) and empty questions still valid');

await until(() => ev.filter((e) => e.type === 'speaking' && e.who === 'ai').length >= 2);
ok('verdict spoken (speaking ai event)');

mode = 'fail';
const before = ev.length;
a.sendText('She is also hiding');
await until(() => ev.slice(before).some((e) => e.type === 'error'));
assert.ok(ev.slice(before).some((e) => e.type === 'transcript' && e.role === 'user'));
assert.ok(!ev.some((e) => e.type === 'ended'));
assert.match(calls.at(-1).body.care.query, /limping\nShe is also hiding/);
ok('backend error -> error event, call continues, history accumulates');

mode = 'ok';
const tb = ev.filter((e) => e.type === 'triage').length;
a.sendText('Eating normally');
await until(() => ev.filter((e) => e.type === 'triage').length > tb);
ok('call still works after an error');

a.end();
a.end();
a.sendText('ignored');
await wait(50);
assert.equal(ev.filter((e) => e.type === 'ended').length, 1);
ok('end() idempotent, exactly one ended');
const denied = createLiveVoiceAgent({ lang: 'hi' });
const count = calls.length;
denied.sendText('Do not send without consent');
await wait(50);
assert.equal(calls.length, count, 'missing consent makes no request');
denied.end();
console.log(`\n${n} checks passed`);
process.exit(0);
