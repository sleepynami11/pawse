// Which AI / provider runs each step, derived from what actually happens at runtime.
// Nothing here is a claim: model ids come from GET /api/v1/capabilities, clinic sources from the
// clinics the backend returned, the voice from what the phone agent really played. Pure functions
// so a plain-Node check can pin the mapping. A provider is { step, key, model?, name? }; the page
// turns key/step into text through t.prov (see i18n.js).

let capsPromise = null;

/** Capabilities once per page load. Resolves null if the backend is unreachable (badges then omit model ids). */
export function loadCapabilities(base = '', fetchImpl = globalThis.fetch) {
  if (!capsPromise) {
    capsPromise = Promise.resolve()
      .then(() => fetchImpl(`${base}/api/v1/capabilities`))
      .then((r) => (r && r.ok ? r.json() : null))
      .then((d) => (d && typeof d === 'object' ? d : null))
      .catch(() => null);
  }
  return capsPromise;
}

export function resetCapabilitiesCache() {
  capsPromise = null;
}

const model = (caps, k) => (caps && caps.models && typeof caps.models[k] === 'string' ? caps.models[k] : undefined);

/** Browser speech: `v` is { available, name } from speech.resolveVoiceName; muted silences it. */
export function browserVoice(v, muted = false) {
  if (muted) return { step: 'voice', key: 'muted' };
  if (!v || !v.available) return { step: 'voice', key: 'no_voice' };
  return { step: 'voice', key: 'browser_voice', name: v.name || undefined };
}

/** Voice call with Pawse. path: 'mock' | 'rest' (transcribe + care REST) | 'native' (Gemini Live). */
export function voiceCallProviders({ path, caps, browser, muted = false }) {
  if (path === 'mock') return [{ step: 'conversation', key: 'scripted' }, browserVoice(browser, muted)];
  if (path === 'native') {
    return [
      { step: 'conversation', key: 'gemini_live', model: model(caps, 'live') },
      { step: 'care', key: 'gemini', model: model(caps, 'care') },
      muted ? { step: 'voice', key: 'muted' } : { step: 'voice', key: 'gemini_native_voice', model: model(caps, 'live') },
    ];
  }
  return [
    { step: 'transcription', key: 'gemini', model: model(caps, 'voice') },
    { step: 'care', key: 'gemini', model: model(caps, 'care') },
    browserVoice(browser, muted),
  ];
}

const CLINIC_KEYS = { google_places: 'places', gemini_maps: 'gemini_maps', mapify: 'mapify', openstreetmap: 'osm' };

/** Clinic search. `clinics` are the mapped results (each has .source from the backend). */
export function clinicProviders({ live, clinics = [], failed = false }) {
  if (!live) return [{ step: 'clinics', key: 'demo' }];
  const sources = [...new Set(clinics.map((c) => c && c.source).filter(Boolean))];
  if (failed || !sources.length) return [{ step: 'clinics', key: 'none' }];
  return sources.map((s) => ({ step: 'clinics', key: CLINIC_KEYS[s] || 'none' }));
}

/**
 * Pawse's own voice on a phone call. voice = { voice: 'gradium'|'browser'|'off', variant, name }
 * (the event the live phone agent emits). Callee replies are always simulated.
 */
export function phoneVoice(voice, browser) {
  if (!voice || voice.voice === 'browser') return browserVoice(voice && voice.name ? { available: true, name: voice.name } : browser);
  if (voice.voice === 'off') return { step: 'voice', key: 'muted' };
  return { step: 'voice', key: voice.variant === 'my_voice' ? 'gradium_own' : 'gradium_standard' };
}

export function phoneProviders({ live, target, voice, browser }) {
  const out = [{ step: 'script', key: live ? 'backend_script' : 'scripted' }, phoneVoice(voice, browser), { step: 'callee', key: 'simulated' }];
  if (live) out.push({ step: 'logic', key: target === 'insurance' ? 'rules_avb' : 'rules' });
  return out;
}

/** Live phone handoff page (draft, audio, evidence). */
export function handoffProviders({ caps, voice, audioReady, target }) {
  const out = [{ step: 'draft', key: 'gemini', model: model(caps, 'voice') }];
  out.push({ step: 'voice', key: voice === 'my_voice' ? 'gradium_own' : 'gradium_standard', pending: !audioReady });
  if (target === 'insurance') out.push({ step: 'evidence', key: 'avb_search' });
  out.push({ step: 'callee', key: 'not_called' });
  return out;
}

/** Voice descriptor the live phone agent emits; pure so the fallback switch is testable. */
export function phoneVoiceEvent({ gradiumOk, muted, variant, browser }) {
  if (muted) return { type: 'provider', step: 'voice', voice: 'off' };
  if (gradiumOk) return { type: 'provider', step: 'voice', voice: 'gradium', variant: variant === 'my_voice' ? 'my_voice' : 'standard' };
  return { type: 'provider', step: 'voice', voice: 'browser', name: browser && browser.available ? browser.name : undefined };
}
