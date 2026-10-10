// SLOT FOR THE PHONE-CALL TEAMMATE.
//
// Replace this file with the real calling agent from your repo (or import it from there).
// It must return the PHONE AGENT shape documented in ../contracts.js:
//
//   on(cb) / start() / hangup()
//
// and emit: status, speaking, line {who, original, text}, result, error.
// `context.summary` is the case summary Pawse should pass on; `context.estimate` is the
// vet's price estimate once the vet call has happened (useful for the insurer call).
//
// Switch on with VITE_PHONE_AGENT=live and VITE_PHONE_AGENT_URL=wss://… in .env.local.

import { PHONE_AGENT_URL } from '../config.js';

export function createLivePhoneCall({ target = 'vet', lang = 'zh', context = {} } = {}) {
  const listeners = new Set();
  const emit = (e) => listeners.forEach((l) => l(e));
  let ws = null;
  let ended = false;

  return {
    on(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    start() {
      if (!PHONE_AGENT_URL) {
        emit({ type: 'error', message: 'VITE_PHONE_AGENT_URL is not set: the live phone agent is not connected yet.' });
        emit({ type: 'status', state: 'ended' });
        return;
      }
      emit({ type: 'status', state: 'dialing' });
      ws = new WebSocket(PHONE_AGENT_URL);
      ws.onopen = () => ws.send(JSON.stringify({ type: 'start_call', target, lang, context }));
      ws.onmessage = (msg) => {
        try {
          emit(JSON.parse(msg.data));
        } catch {
          /* ignore non-JSON frames */
        }
      };
      ws.onerror = () => emit({ type: 'error', message: 'Phone agent connection failed.' });
    },
    hangup() {
      if (ended) return;
      ended = true;
      try {
        if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'hangup' }));
        ws && ws.close();
      } catch {
        /* ignore */
      }
      emit({ type: 'status', state: 'ended' });
    },
  };
}
