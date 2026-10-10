// SLOT 1 – FOR THE VOICE TEAMMATE.
//
// Replace this file with the real agent from your repo (or import it from there).
// It must return the VOICE AGENT shape documented in ../contracts.js:
//
//   on(cb) / start() / end() / sendText(text) / sendImage(file)
//   attachMedia({ audio, video }) / setMicMuted(bool) / wantsAudio
//
// and emit: transcript, speaking, listening, suggestions, image_received, triage, error, ended.
//
// Voice is the main channel: the page opens the microphone (wantsAudio = true) and passes it
// as `audio`. The camera is optional – `video` is a MediaStream only while the user has it on,
// otherwise null. Photos arrive through sendImage(file). Play the AI's audio yourself.
//
// Switch on with VITE_VOICE_AGENT=live and VITE_VOICE_AGENT_URL=wss://… in .env.local.

import { VOICE_AGENT_URL } from '../config.js';

export function createLiveVoiceAgent({ lang = 'zh' } = {}) {
  const listeners = new Set();
  const emit = (e) => listeners.forEach((l) => l(e));
  let ws = null;
  let ended = false;

  const send = (obj) => {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
  };

  return {
    wantsAudio: true,
    on(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    start() {
      if (!VOICE_AGENT_URL) {
        emit({ type: 'error', message: 'VITE_VOICE_AGENT_URL is not set: the live voice agent is not connected yet.' });
        return;
      }
      ws = new WebSocket(`${VOICE_AGENT_URL}?lang=${encodeURIComponent(lang)}`);
      ws.onmessage = (msg) => {
        try {
          emit(JSON.parse(msg.data)); // enough if the server already speaks the contract
        } catch {
          /* binary frames (audio) – TODO(teammate): play them */
        }
      };
      ws.onerror = () => emit({ type: 'error', message: 'Voice agent connection failed.' });
    },
    end() {
      if (ended) return;
      ended = true;
      try {
        ws && ws.close();
      } catch {
        /* ignore */
      }
      emit({ type: 'ended' });
    },
    sendText(text) {
      send({ type: 'user_text', text });
    },
    sendImage(file) {
      // Simple default: send the photo as a data URL. Change to an upload if you prefer.
      const reader = new FileReader();
      reader.onload = () => send({ type: 'user_image', dataUrl: reader.result });
      reader.readAsDataURL(file);
    },
    attachMedia(/* { audio, video } */) {
      // TODO(teammate): stream mic audio (and camera frames while video != null) to the model.
    },
    setMicMuted(/* muted */) {
      // TODO(teammate): pause / resume sending mic audio.
    },
  };
}
