// Tiny wrapper around the browser's built-in text-to-speech, used ONLY by the mock agents
// so the demo actually talks. The live agents play their own audio.

const hasTTS = () =>
  typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined';

let muted = false;
try {
  muted = localStorage.getItem('pawse.muted') === '1';
} catch {
  /* storage unavailable */
}

export const isSpeechMuted = () => muted;

export function setSpeechMuted(m) {
  muted = !!m;
  try {
    localStorage.setItem('pawse.muted', muted ? '1' : '0');
  } catch {
    /* ignore */
  }
  if (muted && hasTTS()) window.speechSynthesis.cancel();
}

/** Rough spoken duration, used for pacing when the voice is muted or unavailable. */
export function estimateMs(text, lang) {
  const per = String(lang).startsWith('zh') ? 210 : 68;
  return Math.max(1200, String(text).length * per);
}

const TAGS = { zh: 'zh-CN', en: 'en-US', de: 'de-DE', hi: 'hi-IN' };

function pickVoice(tag) {
  const voices = window.speechSynthesis.getVoices();
  return voices.find((v) => v.lang === tag) || voices.find((v) => v.lang.toLowerCase().startsWith(tag.slice(0, 2)));
}

/** Which browser voice would speak `lang` (null name = the browser default). Used for the "powered by" badge. */
export function resolveVoiceName(lang) {
  if (!hasTTS()) return { available: false, name: null };
  const v = pickVoice(TAGS[lang] || lang);
  return { available: true, name: v ? v.name : null };
}

const voiceListeners = new Set();
/** Subscribe to the voice list becoming available (Chrome loads it late). Returns an unsubscribe. */
export function onVoicesChanged(cb) {
  voiceListeners.add(cb);
  if (hasTTS() && voiceListeners.size === 1) window.speechSynthesis.onvoiceschanged = () => voiceListeners.forEach((l) => l());
  return () => voiceListeners.delete(cb);
}

/** Call inside a tap so iOS Safari allows speech later on. */
export function primeSpeech() {
  if (!hasTTS()) return;
  try {
    const u = new SpeechSynthesisUtterance(' ');
    u.volume = 0;
    window.speechSynthesis.speak(u);
  } catch {
    /* ignore */
  }
}

export function stopSpeech() {
  if (hasTTS()) window.speechSynthesis.cancel();
}

/**
 * Speak `text`; resolves when finished. speed > 1 (tests / rehearsal) skips the voice.
 * silent: don't play it, just wait as long as it would take (a call running in the background).
 */
export function speak(text, lang, { speed = 1, pitch = 1, rate = 1, silent = false } = {}) {
  const est = estimateMs(text, lang);
  if (speed > 1 || silent || muted || !hasTTS()) return new Promise((r) => setTimeout(r, est / speed));

  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(guard);
      resolve();
    };
    const guard = setTimeout(finish, est * 2 + 3000); // never hang if the engine stalls
    try {
      const u = new SpeechSynthesisUtterance(text);
      const tag = TAGS[lang] || lang;
      u.lang = tag;
      const v = pickVoice(tag);
      if (v) u.voice = v;
      u.pitch = pitch;
      u.rate = rate;
      u.onend = finish;
      u.onerror = finish;
      window.speechSynthesis.speak(u);
    } catch {
      setTimeout(finish, est);
    }
  });
}
