// Plain-Node checks for the mock agents and the contracts. Run with: npm run check

import assert from 'node:assert/strict';
import { createMockVoiceAgent } from '../src/agents/mockVoiceAgent.js';
import { mockSearchClinics } from '../src/agents/mockClinicSearch.js';
import { createMockPhoneCall } from '../src/agents/mockPhoneAgent.js';
import { reimbursement } from '../src/agents/mockScripts.js';
import { validateTriage, validateResult, validateClinics } from '../src/contracts.js';
import { buildSummary } from '../src/utils/summary.js';

const SPEED = 400;
let n = 0;
const ok = (m) => console.log(`  ok  ${++n} ${m}`);

function runVideo({ lang, onEvent, stopOn } = {}) {
  return new Promise((resolve, reject) => {
    const events = [];
    const a = createMockVoiceAgent({ lang, speed: SPEED });
    const to = setTimeout(() => reject(new Error('video timeout')), 5000);
    a.on((e) => {
      events.push(e);
      onEvent && onEvent(e, a);
      if (e.type === 'triage' || (stopOn && stopOn(e))) {
        clearTimeout(to);
        setTimeout(() => {
          a.end();
          setTimeout(() => resolve({ events, a }), 30);
        }, 20);
      }
    });
    a.start();
  });
}

function runPhone(target, lang, context) {
  return new Promise((resolve, reject) => {
    const events = [];
    const c = createMockPhoneCall({ target, lang, context, speed: SPEED });
    const to = setTimeout(() => reject(new Error('phone timeout')), 5000);
    c.on((e) => {
      events.push(e);
      if (e.type === 'status' && e.state === 'ended') {
        clearTimeout(to);
        setTimeout(() => resolve({ events, c }), 30);
      }
    });
    c.start();
  });
}

for (const lang of ['zh', 'en']) {
  console.log(`voice agent (${lang})`);

  // nobody answers: the mock "hears" scripted answers and reaches triage
  const auto = await runVideo({ lang });
  const tri = auto.events.find((e) => e.type === 'triage');
  assert.deepEqual(validateTriage(tri), []);
  assert.equal(tri.level, 'yellow');
  ok('reaches a valid triage with no input (simulated answers)');

  const firstAi = auto.events.find((e) => e.type === 'transcript');
  assert.equal(firstAi.role, 'ai');
  ok('Pawse speaks first');

  const users = auto.events.filter((e) => e.type === 'transcript' && e.role === 'user');
  assert.equal(users.length, 2);
  assert.ok(users.every((u) => u.simulated === true));
  ok('two simulated user answers, flagged simulated');

  const sug = auto.events.filter((e) => e.type === 'suggestions');
  assert.ok(sug[0].items.length >= 3, 'keyword chips offered');
  assert.deepEqual(sug[1].items, [], 'chips cleared after answering');
  ok('keyword chips appear while listening and clear after the answer');

  assert.equal(auto.events.filter((e) => e.type === 'ended').length, 1);
  auto.a.end();
  assert.equal(auto.events.filter((e) => e.type === 'ended').length, 1);
  ok('end() emits ended once and is idempotent');

  // the user taps a chip / types: their words are used, not the script
  const typed = await runVideo({
    lang,
    onEvent: (e, a) => {
      if (e.type === 'suggestions' && e.items.length) queueMicrotask(() => a.sendText(e.items[0]));
    },
  });
  const typedUsers = typed.events.filter((e) => e.type === 'transcript' && e.role === 'user');
  assert.equal(typedUsers.length, 2);
  assert.ok(typedUsers.every((u) => u.simulated === false));
  ok('tapping a keyword answers immediately with that keyword');

  // hanging up mid-conversation stops everything
  const early = await runVideo({ lang, stopOn: (e) => e.type === 'listening' && e.on });
  assert.ok(!early.events.some((e) => e.type === 'triage'));
  assert.equal(early.events[early.events.length - 1].type, 'ended');
  ok('hang-up while listening stops cleanly, nothing after ended');

  // photo while listening: acknowledged once, conversation still reaches triage
  const withPhoto = await runVideo({
    lang,
    onEvent: (e, a) => {
      if (e.type === 'listening' && e.on) queueMicrotask(() => { a.sendImage({ name: 'cat.jpg' }); a.sendImage({ name: 'cat2.jpg' }); });
    },
  });
  assert.equal(withPhoto.events.filter((e) => e.type === 'image_received').length, 4);
  const thanks = withPhoto.events.filter((e) => e.type === 'transcript' && e.role === 'ai' && /Got the photo|收到照片/.test(e.text));
  assert.equal(thanks.length, 1);
  assert.ok(withPhoto.events.some((e) => e.type === 'triage'));
  ok('photos: each one acknowledged with image_received, thanked once, triage still reached');

  console.log(`clinic search (${lang})`);
  const found = await mockSearchClinics({ lang, speed: SPEED });
  assert.deepEqual(validateClinics(found), []);
  const d = found.clinics.map((c) => c.distanceKm);
  assert.deepEqual(d, [...d].sort((x, y) => x - y));
  assert.ok(found.clinics.some((c) => !c.openNow) && found.clinics.some((c) => c.emergency));
  assert.ok(found.clinics.every((c) => typeof c.hoursText === 'string' && c.mapsUrl.startsWith('https://')));
  assert.ok(found.clinics.every((c) => c.name.includes('(Demo)')));
  ok('valid list, sorted by distance, open/closed + emergency, localised hours, demo names');

  console.log(`phone agent (${lang})`);
  const chosen = found.clinics[0];
  const vet = await runPhone('vet', lang, { clinic: chosen });
  const st = vet.events.filter((e) => e.type === 'status').map((e) => e.state);
  assert.deepEqual(st, ['dialing', 'connected', 'ended']);
  ok('vet call: dialing → connected → ended');
  const lines = vet.events.filter((e) => e.type === 'line');
  assert.match(lines[0].original, /KI-Assistent/, 'Pawse must say it is an AI first');
  assert.ok(lines.every((l) => l.original && l.text));
  ok('first line discloses AI; every line has German + translation');
  const vr = vet.events.find((e) => e.type === 'result');
  assert.deepEqual(validateResult('vet', vr), []);
  assert.equal(vr.time, '16:30');
  assert.equal(vr.place, chosen.name);
  ok('vet result: valid appointment at 16:30 at the chosen clinic');

  const ins = await runPhone('insurance', lang, { estimate: vr.estimate });
  const ir = ins.events.find((e) => e.type === 'result');
  assert.deepEqual(validateResult('insurance', ir), []);
  assert.equal(ir.reimbursed, 240);
  assert.equal(ir.outOfPocket, 360);
  assert.ok(ir.points.some((p) => p.ref === 'AVB 1.2.5') && ir.points.some((p) => p.ref === 'AVB 1.2.6'));
  ok('insurance result: 600 → 240 back, 360 out of pocket, AVB clauses listed');

  // hang up while dialing
  const c = createMockPhoneCall({ target: 'vet', lang, speed: SPEED, context: {} });
  const evs = [];
  c.on((e) => evs.push(e));
  c.start();
  c.hangup();
  c.hangup();
  await new Promise((r) => setTimeout(r, 60));
  assert.deepEqual(evs.map((e) => e.state || e.type), ['dialing', 'ended']);
  ok('hang-up while dialing ends once, no result');

  const summary = buildSummary({ lang, triage: tri, vet: vr, insurance: ir });
  assert.ok(summary.includes('16:30') && summary.includes('360') && summary.includes('AVB 1.2.5'));
  ok('case summary includes appointment, out-of-pocket and clauses');
}

console.log('maths');
assert.equal(reimbursement(600), 240);
assert.equal(reimbursement(250), 0);
assert.equal(reimbursement(1000), 560);
ok('reimbursement = 80% above the CHF 300 excess');

console.log(`\nAll good: ${n} checks passed.`);
