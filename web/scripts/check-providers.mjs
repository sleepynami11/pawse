// Plain-Node check of the "powered by" mapping and of the live phone agent's voice switch.
import assert from 'node:assert/strict';
import { voiceCallProviders, clinicProviders, phoneProviders, handoffProviders, loadCapabilities, resetCapabilitiesCache, phoneVoiceEvent, browserVoice } from '../src/agents/providers.js';
import { strings } from '../src/i18n.js';

const caps = { models: { care: 'care-m', voice: 'voice-m', live: 'live-m' } };
const byStep = (a) => Object.fromEntries(a.map((p) => [p.step, p]));

// voice call: model ids come from the capabilities, never invented
let v = byStep(voiceCallProviders({ path: 'rest', caps, browser: { available: true, name: 'Samantha' } }));
assert.deepEqual([v.transcription.model, v.care.model, v.voice.name, v.voice.key], ['voice-m', 'care-m', 'Samantha', 'browser_voice']);
v = byStep(voiceCallProviders({ path: 'rest', caps: null, browser: { available: false } }));
assert.equal(v.transcription.model, undefined, 'no capabilities: no model id claimed');
assert.equal(v.voice.key, 'no_voice');
v = byStep(voiceCallProviders({ path: 'native', caps, muted: true }));
assert.deepEqual([v.conversation.model, v.care.model, v.voice.key], ['live-m', 'care-m', 'muted']);
v = byStep(voiceCallProviders({ path: 'mock', caps, browser: { available: true, name: null } }));
assert.equal(v.conversation.key, 'scripted');
assert.ok(!v.care && !v.transcription, 'mock claims no AI model');

// clinics
assert.deepEqual(clinicProviders({ live: false }), [{ step: 'clinics', key: 'demo' }]);
assert.deepEqual(clinicProviders({ live: true, clinics: [{ source: 'mapify' }, { source: 'mapify' }] }).map((p) => p.key), ['mapify']);
assert.deepEqual(clinicProviders({ live: true, clinics: [{ source: 'google_places' }, { source: 'mapify' }] }).map((p) => p.key), ['places', 'mapify']);
assert.deepEqual(clinicProviders({ live: true, clinics: [] }).map((p) => p.key), ['none']);
assert.deepEqual(clinicProviders({ live: true, clinics: [{ source: 'mapify' }], failed: true }).map((p) => p.key), ['none']);

// phone
const own = byStep(phoneProviders({ live: true, target: 'insurance', voice: { voice: 'gradium', variant: 'my_voice' } }));
assert.deepEqual([own.voice.key, own.callee.key, own.logic.key, own.script.key], ['gradium_own', 'simulated', 'rules_avb', 'backend_script']);
assert.equal(byStep(phoneProviders({ live: true, target: 'vet', voice: { voice: 'gradium', variant: 'standard' } })).voice.key, 'gradium_standard');
const fb = byStep(phoneProviders({ live: true, target: 'vet', voice: { voice: 'browser', name: 'Anna' } }));
assert.deepEqual([fb.voice.key, fb.voice.name, fb.logic.key], ['browser_voice', 'Anna', 'rules']);
assert.equal(byStep(phoneProviders({ live: true, target: 'vet', voice: { voice: 'off' } })).voice.key, 'muted');
const mock = byStep(phoneProviders({ live: false, target: 'vet', voice: null, browser: { available: true, name: 'Anna' } }));
assert.deepEqual([mock.script.key, mock.callee.key, mock.voice.name, !!mock.logic], ['scripted', 'simulated', 'Anna', false]);
assert.deepEqual(phoneVoiceEvent({ gradiumOk: true, muted: false, variant: 'my_voice' }), { type: 'provider', step: 'voice', voice: 'gradium', variant: 'my_voice' });
assert.equal(phoneVoiceEvent({ gradiumOk: false, muted: true }).voice, 'off');
assert.equal(browserVoice({ available: true, name: 'X' }, true).key, 'muted');
const h = byStep(handoffProviders({ caps, voice: 'standard', audioReady: false, target: 'insurance' }));
assert.deepEqual([h.draft.model, h.voice.key, h.voice.pending, h.evidence.key, h.callee.key], ['voice-m', 'gradium_standard', true, 'avb_search', 'not_called']);

// every key/step used has en and zh text
const used = new Set(), steps = new Set();
for (const p of [...voiceCallProviders({ path: 'rest', caps }), ...voiceCallProviders({ path: 'native', caps }), ...voiceCallProviders({ path: 'native', caps, muted: true }), ...voiceCallProviders({ path: 'mock', caps }),
  ...clinicProviders({ live: false }), ...clinicProviders({ live: true, clinics: [{ source: 'google_places' }, { source: 'mapify' }] }), ...clinicProviders({ live: true }),
  ...phoneProviders({ live: true, target: 'insurance', voice: { voice: 'gradium', variant: 'my_voice' } }), ...phoneProviders({ live: true, target: 'vet', voice: { voice: 'gradium' } }),
  ...phoneProviders({ live: false, target: 'vet' }), ...handoffProviders({ caps, voice: 'my_voice', target: 'insurance' }), browserVoice(null)]) { used.add(p.key); steps.add(p.step); }
for (const lang of ['en', 'zh']) {
  for (const k of used) assert.ok(strings[lang].prov.keys[k], `${lang} text for key ${k}`);
  for (const s of steps) assert.ok(strings[lang].prov.steps[s], `${lang} text for step ${s}`);
  assert.ok(strings[lang].prov.title && strings[lang].prov.pending);
}

// capabilities are fetched once and a failure yields null
resetCapabilitiesCache();
let n = 0;
const f = async () => { n++; return { ok: true, json: async () => caps }; };
assert.deepEqual(await loadCapabilities('', f), caps);
await loadCapabilities('', f);
assert.equal(n, 1);
resetCapabilitiesCache();
assert.equal(await loadCapabilities('', async () => { throw new Error('down'); }), null);
resetCapabilitiesCache();

// live phone agent: the voice event switches from Gradium to the browser when Gradium fails mid-call
const story = { costs: {}, calendar: {}, steps: [{ lines: [] }, { lines: [] }, { lines: [
  { speaker: 'Pawse', german: 'Eins.', subtitle: '1' }, { speaker: 'Vet · simulated', german: 'Zwei.', subtitle: '2' }, { speaker: 'Pawse', german: 'Drei.', subtitle: '3' }] }] };
let speechCalls = 0;
globalThis.fetch = async (url) => {
  if (String(url).endsWith('/api/v1/demo/mimi')) return { ok: true, status: 200, json: async () => story };
  if (String(url).endsWith('/api/v1/voice/speech')) {
    speechCalls += 1;
    if (speechCalls >= 2) return { ok: false, status: 503, headers: new Map(), blob: async () => null };
    return { ok: true, status: 200, headers: new Map([['x-pawse-call-id', 'call-0123456789abcdef']]), blob: async () => ({ size: 1 }) };
  }
  return { ok: false, status: 404 };
};
globalThis.Audio = class { play() { setTimeout(() => this.onended && this.onended(), 0); return Promise.resolve(); } pause() {} };
URL.createObjectURL = () => 'blob:stub';
URL.revokeObjectURL = () => {};
const { createLivePhoneCall } = await import('../src/agents/livePhoneAgent.js');
const call = createLivePhoneCall({ target: 'vet', lang: 'en', context: { gradiumConsent: true, voice: 'my_voice' }, speed: 1000 });
const ev = [];
call.on((e) => ev.push(e));
call.start();
for (let i = 0; i < 400 && !ev.some((e) => e.type === 'status' && e.state === 'ended'); i++) await new Promise((r) => setTimeout(r, 10));
const voices = ev.filter((e) => e.type === 'provider').map((e) => e.voice + (e.variant ? ':' + e.variant : ''));
assert.deepEqual(voices, ['gradium:my_voice', 'browser'], 'badge starts on own voice, switches once to browser when Gradium fails');
assert.ok(ev.filter((e) => e.type === 'line' && e.who === 'callee').every((l) => l.simulated === true));

console.log('check-providers: mapping, en/zh text, capabilities cache and live Gradium-to-browser switch OK');
