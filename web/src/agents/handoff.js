// Reviewed communication and evidence tools. These endpoints do not place calls.
import { PHONE_AGENT_URL } from '../config.js';
export async function requestTool(path, body, { binary = false, signal } = {}) {
  const response = await fetch(`${PHONE_AGENT_URL || ''}/api/v1/${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`);
  }
  return binary ? response.blob() : response.json();
}
export function draftHandoff(message, lang, target, consent, signal) {
  if (!consent) return Promise.reject(new Error('Confirm sharing with Gemini.'));
  return requestTool('voice/scripts', { message, input_language: lang, subtitle_language: lang,
    target_language: 'de', recipient: target === 'insurance' ? 'insurer' : 'vet', share_with_gemini: true }, { signal });
}
export function searchDemoPolicy(query, signal) {
  return requestTool('knowledge/search', { query, top_k: 3, scope: 'synthetic_demo' }, { signal });
}
export function generateSpeech(text, voice, consent, signal) {
  if (!consent) return Promise.reject(new Error('Confirm sharing the reviewed script with Gradium.'));
  return requestTool('voice/speech', { text, language: 'de', voice, share_with_gradium: true }, { binary: true, signal });
}
