// Central switches. Set them in .env.local (see .env.example).
// import.meta.env is undefined outside Vite (e.g. plain-Node checks), so guard it.
const env = (typeof import.meta !== 'undefined' && import.meta.env) || {};

const param = (k) => {
  try {
    return new URLSearchParams(window.location.search).get(k);
  } catch {
    return null;
  }
};

/** 'mock' = scripted demo (default). 'live' = the Pawse backend. "?live=1" in the URL switches all three at runtime. */
const LIVE_ALL = param('live') === '1';
export const VOICE_AGENT = LIVE_ALL ? 'live' : env.VITE_VOICE_AGENT || 'mock';
export const CLINIC_SEARCH = LIVE_ALL ? 'live' : env.VITE_CLINIC_SEARCH || 'mock';
export const PHONE_AGENT = LIVE_ALL ? 'live' : env.VITE_PHONE_AGENT || 'mock';

export const VOICE_AGENT_URL = env.VITE_VOICE_AGENT_URL || '';
export const CLINIC_SEARCH_URL = env.VITE_CLINIC_SEARCH_URL || '';
export const PHONE_AGENT_URL = env.VITE_PHONE_AGENT_URL || '';

/** Mock playback speed. "?speed=3" in the URL plays the demo 3x faster (handy for rehearsing). */
export const MOCK_SPEED = (() => {
  const v = Number(param('speed'));
  return v > 0 ? v : 1;
})();
