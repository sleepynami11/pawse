// Gradium voice in the Live conversation, offline: STT/TTS sockets and the agent wiring with fakes.
import assert from 'node:assert/strict';
import { createGradiumStt, createGradiumReply, gradiumSupports, gradiumVoiceName, GRADIUM_VOICES } from '../src/agents/gradiumVoice.js';
import { createGeminiLiveAgent } from '../src/agents/geminiLiveAgent.js';
import { voiceCallProviders } from '../src/agents/providers.js';

const tick = () => new Promise((r) => setTimeout(r, 0));
assert.ok(gradiumSupports('en') && gradiumSupports('de') && !gradiumSupports('zh') && !gradiumSupports('hi'));
assert.equal(gradiumVoiceName('en', GRADIUM_VOICES.en[0].id), 'Emma');

// Sockets: one-use token from our backend, setup first, frames as base64 audio, end of turn from the VAD.
const sockets = [], tokenCalls = [];
class FakeWS {
  constructor(url) { this.url = url; this.sent = []; this.readyState = 1; sockets.push(this); setTimeout(() => this.onopen?.(), 0); }
  send(m) { this.sent.push(JSON.parse(m)); if (this.sent.length === 1) setTimeout(() => this.onmessage({ data: JSON.stringify({ type: 'ready' }) }), 0); }
  close() { this.readyState = 3; }
  emit(m) { this.onmessage({ data: JSON.stringify(m) }); }
}
const fetchImpl = async (url, init) => { tokenCalls.push([url, JSON.parse(init.body)]); return { ok: true, json: async () => ({ token: 't/1' }) }; };
const partials = [], turns = [];
const stt = createGradiumStt({ lang: 'en', onPartial: (t) => partials.push(t), onTurn: (t) => turns.push(t), onError: assert.fail, fetchImpl, WebSocketImpl: FakeWS });
await stt.start();
const sws = sockets[0];
assert.deepEqual(tokenCalls[0], ['/api/v1/voice/stream-tokens', { share_with_gradium: true }]);
assert.equal(sws.url, 'wss://api.gradium.ai/api/speech/asr?token=t%2F1');
assert.deepEqual(sws.sent[0], { type: 'setup', model_name: 'default', input_format: 'pcm_16000', json_config: { language: 'en' } });
stt.send('AAAA');
assert.deepEqual(sws.sent[1], { type: 'audio', audio: 'AAAA' });
sws.emit({ type: 'step', vad: [{}, {}, { inactivity_prob: 0.9 }] }); // silence before any words: not a turn
sws.emit({ type: 'text', text: 'my cat' });
sws.emit({ type: 'text', text: 'is limping' });
sws.emit({ type: 'step', vad: [{}, {}, { inactivity_prob: 0.2 }] });
sws.emit({ type: 'step', vad: [{}, {}, { inactivity_prob: 0.8 }] });
assert.deepEqual(sws.sent.at(-1), { type: 'flush', flush_id: 1 });
sws.emit({ type: 'step', vad: [{}, {}, { inactivity_prob: 0.9 }] }); // one flush per turn
assert.equal(sws.sent.filter((m) => m.type === 'flush').length, 1);
assert.deepEqual(turns, [], 'the turn waits for the flush');
sws.emit({ type: 'text', text: 'today' }); // trailing words still belong to this turn
sws.emit({ type: 'flushed', flush_id: 1 });
assert.deepEqual(partials, ['my cat', 'my cat is limping', 'my cat is limping today']);
assert.deepEqual(turns, ['my cat is limping today']);
stt.close();
assert.equal(sws.sent.at(-1).type, 'end_of_stream');

// A reply queues text until the TTS socket is ready, then streams PCM 24 kHz back.
const audio = [];
const reply = createGradiumReply({ voiceId: 'v1', onAudio: (a) => audio.push(a), onError: assert.fail, fetchImpl, WebSocketImpl: FakeWS });
reply.text('Hello there.');
reply.end();
await tick(); await tick(); await tick();
const tws = sockets[1];
assert.equal(tws.url, 'wss://api.gradium.ai/api/speech/tts?token=t%2F1');
assert.deepEqual(tws.sent.map((m) => m.type), ['setup', 'text', 'end_of_stream']);
assert.deepEqual([tws.sent[0].voice_id, tws.sent[0].output_format], ['v1', 'pcm_24000']);
tws.emit({ type: 'audio', audio: 'UENN' });
reply.cancel();
tws.emit({ type: 'audio', audio: 'TEFURQ==' });
assert.deepEqual(audio, ['UENN']);

// The agent: Gradium hears the owner and speaks; Gemini Live gets text and its audio is not played.
function setup({ sttFails = false } = {}) {
  const s = { sent: [], played: [], flushed: 0, replies: [], events: [] };
  s.session = { sendRealtimeInput: (p) => s.sent.push(p), sendToolResponse() {}, close() {} };
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ token: 'live', model: 'm', api_version: 'v1alpha' }) });
  s.agent = createGeminiLiveAgent({
    lang: 'en', shareWithGemini: true, voice: { engine: 'gradium', voiceId: 'v1' },
    audioFactory: (frame) => { s.onFrame = frame; return { setMuted() {}, attach: async () => {}, flush: () => s.flushed++, close: async () => {}, play: async (d, rate) => s.played.push([d, rate]) }; },
    clientFactory: () => ({ live: { connect: async (o) => { s.cb = o.callbacks; return s.session; } } }),
    sttFactory: (o) => { s.stt = o; return { start: async () => { if (sttFails) throw Error('Gradium voice unavailable (503).'); }, send: (f) => (s.frames = (s.frames || 0) + 1), close() {} }; },
    replyFactory: (o) => { const r = { o, texts: [], ended: false, cancelled: false, text: (t) => r.texts.push(t), end: () => (r.ended = true), cancel: () => (r.cancelled = true) }; s.replies.push(r); return r; },
  });
  s.agent.on((e) => s.events.push(e));
  return s;
}
const a = setup();
await a.agent.start();
a.agent.setMicMuted(false);
const greeting = a.sent.length;
a.onFrame('AAAA');
assert.equal(a.frames, 1);
assert.equal(a.sent.length, greeting, 'mic audio goes to Gradium, not Gemini');
a.cb.onmessage({ serverContent: { outputTranscription: { text: "Hello! I'm Pawse. How" }, modelTurn: { parts: [{ inlineData: { data: 'AAA=', mimeType: 'audio/pcm;rate=24000' } }] } } });
assert.deepEqual(a.replies[0].texts, ["Hello! I'm Pawse."]);
a.cb.onmessage({ serverContent: { outputTranscription: { text: ' can I help?' } } });
a.cb.onmessage({ serverContent: { turnComplete: true } });
assert.deepEqual(a.replies[0].texts, ["Hello! I'm Pawse.", ' How can I help?']);
assert.ok(a.replies[0].ended);
a.replies[0].o.onAudio('UENN');
await tick();
assert.deepEqual(a.played, [['UENN', 24000]], "Gemini's own audio is not played; Gradium's is");
// The owner talks over Pawse: playback stops, then the finished turn goes to Live as text.
a.cb.onmessage({ serverContent: { outputTranscription: { text: 'Is she eating' } } });
const flushes = a.flushed;
a.stt.onPartial('she');
assert.ok(a.replies[1].cancelled && a.flushed > flushes);
a.stt.onPartial('she jumped');
a.stt.onTurn('she jumped off a wardrobe');
assert.deepEqual(a.sent.at(-1), { text: 'she jumped off a wardrobe' });
const mine = a.events.filter((e) => e.type === 'transcript' && e.role === 'user');
assert.deepEqual(mine.map((e) => [e.text, e.partial]), [['she', true], ['she jumped', true], ['she jumped off a wardrobe', false]]);
a.agent.end();

// Gradium unavailable: the call carries on with Gemini's native voice.
const b = setup({ sttFails: true });
await b.agent.start();
b.agent.setMicMuted(false);
b.onFrame('AAAA');
assert.equal(b.sent.at(-1).audio.mimeType, 'audio/pcm;rate=16000');
assert.ok(b.events.some((e) => e.type === 'error' && /Gemini voice instead/.test(e.message)));
b.cb.onmessage({ serverContent: { modelTurn: { parts: [{ inlineData: { data: 'AAA=', mimeType: 'audio/pcm;rate=24000' } }] } } });
await tick();
assert.equal(b.played.length, 1);
b.agent.end();

// Chinese and Hindi stay on Gemini even if a Gradium voice was chosen.
const c = setup();
c.agent.end();
const zh = createGeminiLiveAgent({ lang: 'zh', shareWithGemini: true, voice: { engine: 'gradium', voiceId: 'v1' }, audioFactory: (f) => { c.onFrame = f; return { setMuted() {}, attach: async () => {}, flush() {}, close: async () => {}, play: async () => {} }; }, clientFactory: () => ({ live: { connect: async () => c.session } }), sttFactory: () => assert.fail('no Gradium STT for zh') });
await zh.start();
zh.setMicMuted(false);
c.onFrame('AAAA');
assert.equal(c.sent.at(-1).audio.mimeType, 'audio/pcm;rate=16000');
zh.end();

const chips = Object.fromEntries(voiceCallProviders({ path: 'native', caps: { models: { live: 'live-m', care: 'care-m' } }, gradium: 'Emma' }).map((p) => [p.step, p]));
assert.deepEqual([chips.conversation.key, chips.transcription.key, chips.voice.key, chips.voice.name], ['gemini_live', 'gradium_stt', 'gradium_voice', 'Emma']);
console.log('check-gradium-voice: tokens, STT turns, TTS queueing, agent routing, barge-in, fallback and chips OK');

// Default voice: Gradium (first voice of the language); 'gemini' opts out; zh/hi stay on Gemini.
const { resolveVoiceChoice } = await import('../src/agents/gradiumVoice.js');
assert.equal(resolveVoiceChoice('', 'en'), GRADIUM_VOICES.en[0].id);
assert.equal(resolveVoiceChoice('gemini', 'en'), null);
assert.equal(resolveVoiceChoice(GRADIUM_VOICES.en[2].id, 'en'), GRADIUM_VOICES.en[2].id);
assert.equal(resolveVoiceChoice(GRADIUM_VOICES.en[2].id, 'de'), GRADIUM_VOICES.de[0].id, 'an English voice falls back to the German default');
assert.equal(resolveVoiceChoice('', 'zh'), null);
console.log('check-gradium-voice: default voice resolution OK');
