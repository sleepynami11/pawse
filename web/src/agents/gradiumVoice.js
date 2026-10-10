// Gradium streaming speech for the Live conversation. The browser talks to Gradium directly with
// one-use tokens from POST /api/v1/voice/stream-tokens, so the API key never leaves the server.
//   STT: mic PCM 16 kHz -> Gradium -> live captions, then the finished turn at end of speech (semantic VAD)
//   TTS: one socket per Pawse reply; sentences go in while Gemini is still talking, PCM 24 kHz comes back

const WS = 'wss://api.gradium.ai/api/speech/';

/** Voices offered in the dropdown (Gradium catalog, calm and friendly). The first one is the default. */
export const GRADIUM_VOICES = {
  en: [
    { id: 'YTpq7expH9539ERJ', name: 'Emma', note: 'warm, empathic' },
    { id: 'NIWIOv5vTi5eRMj8', name: 'Juniper', note: 'cheerful' },
    { id: 'vtjTMKK7e8Q6Munf', name: 'Nina', note: 'bright, open' },
    { id: 'sMe4oUbMUEi4Fwss', name: 'Avery', note: 'soft, rounded' },
    { id: 'cYO5kTeFmmXMyKk2', name: 'Brady', note: 'upbeat' },
  ],
  de: [
    { id: 'p6Uutkyi3j2iNAUu', name: 'Annika', note: 'friendly' },
    { id: 'POGjiVFGry6yTV2R', name: 'Valerie', note: 'calm, polished' },
    { id: 'anFey60lIlYD2ClM', name: 'Chiara', note: 'sunny' },
    { id: '5qR8zYpVfe4BpilC', name: 'Till', note: 'light, friendly' },
  ],
};

/** Gradium transcribes and speaks these conversation languages; others stay on Gemini's native voice. */
export const gradiumSupports = (lang) => Boolean(GRADIUM_VOICES[lang]);

export const gradiumVoiceName = (lang, id) => (GRADIUM_VOICES[lang] || []).find((v) => v.id === id)?.name;

/** The Gradium voice id a saved choice means in this language: null = Gemini's native voice.
 *  No choice yet, or a voice from another language, means this language's default Gradium voice. */
export function resolveVoiceChoice(choice, lang) {
  if (choice === 'gemini' || !gradiumSupports(lang)) return null;
  return gradiumVoiceName(lang, choice) ? choice : GRADIUM_VOICES[lang][0].id;
}

// The 2 s VAD horizon above 0.5 marks the end of the owner's turn (Gradium's suggested starting point).
const END_OF_TURN = 0.5;

async function streamToken(base, fetchImpl) {
  const r = await fetchImpl(`${base}/api/v1/voice/stream-tokens`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ share_with_gradium: true }),
  });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    throw Error(typeof j.detail === 'string' ? j.detail : `Gradium voice unavailable (${r.status})`);
  }
  return (await r.json()).token;
}

function open(base, path, setup, onMessage, fetchImpl, WebSocketImpl) {
  return streamToken(base, fetchImpl).then(
    (token) =>
      new Promise((resolve, reject) => {
        const ws = new WebSocketImpl(`${WS}${path}?token=${encodeURIComponent(token)}`);
        ws.onopen = () => ws.send(JSON.stringify(setup));
        ws.onerror = () => reject(Error('Gradium voice connection failed.'));
        ws.onmessage = (e) => {
          let m;
          try {
            m = JSON.parse(e.data);
          } catch {
            return;
          }
          if (m.type === 'ready') resolve(ws);
          else onMessage(m);
        };
      }),
  );
}

/** Streaming transcription of the owner's microphone. */
export function createGradiumStt({ base = '', lang, onPartial, onTurn, onError, fetchImpl = globalThis.fetch, WebSocketImpl = globalThis.WebSocket }) {
  let ws = null, closed = false, text = '', flushing = 0, nextFlush = 1;
  // At the end of speech, flush: the last words' text can trail the VAD, so the turn waits for `flushed`.
  const onMessage = (m) => {
    if (closed) return;
    if (m.type === 'text' && m.text) {
      text = text ? `${text} ${m.text}` : m.text;
      onPartial(text);
    } else if (m.type === 'step' && text && !flushing && (m.vad?.[2]?.inactivity_prob ?? 0) > END_OF_TURN) {
      flushing = nextFlush++;
      ws?.send(JSON.stringify({ type: 'flush', flush_id: flushing }));
    } else if (m.type === 'flushed' && m.flush_id === flushing) {
      flushing = 0;
      const turn = text;
      text = '';
      if (turn) onTurn(turn);
    } else if (m.type === 'error') {
      onError(m.message || 'Gradium transcription failed.');
    }
  };
  return {
    async start() {
      const socket = await open(base, 'asr', { type: 'setup', model_name: 'default', input_format: 'pcm_16000', json_config: { language: lang } }, onMessage, fetchImpl, WebSocketImpl);
      if (closed) socket.close();
      else {
        ws = socket;
        ws.onclose = () => { if (!closed) onError('Gradium transcription disconnected. Start a new conversation.'); };
      }
    },
    /** One base64 PCM16 16 kHz frame from the mic worklet. */
    send(frame) {
      if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'audio', audio: frame }));
    },
    close() {
      closed = true;
      try {
        if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'end_of_stream' }));
        ws?.close();
      } catch { /* already closed */ }
      ws = null;
    },
  };
}

/** One spoken reply in a Gradium voice. text() can be called while the reply is still being written. */
export function createGradiumReply({ base = '', voiceId, onAudio, onError, fetchImpl = globalThis.fetch, WebSocketImpl = globalThis.WebSocket }) {
  let ws = null, cancelled = false;
  const pending = [];
  const send = (m) => (ws ? ws.send(JSON.stringify(m)) : pending.push(m));
  open(base, 'tts', { type: 'setup', model_name: 'default', voice_id: voiceId, output_format: 'pcm_24000' }, (m) => {
    if (cancelled) return;
    if (m.type === 'audio' && m.audio) onAudio(m.audio);
    else if (m.type === 'error') onError(m.message || 'Gradium speech failed.');
  }, fetchImpl, WebSocketImpl).then(
    (socket) => {
      if (cancelled) return socket.close();
      ws = socket;
      while (pending.length) ws.send(JSON.stringify(pending.shift()));
    },
    (e) => !cancelled && onError(e.message),
  );
  return {
    text(s) {
      if (!cancelled && s.trim()) send({ type: 'text', text: s });
    },
    end() {
      if (!cancelled) send({ type: 'end_of_stream' });
    },
    cancel() {
      cancelled = true;
      try { ws?.close(); } catch { /* already closed */ }
    },
  };
}
