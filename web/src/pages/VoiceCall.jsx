import { useEffect, useRef, useState } from 'react';
import Avatar from '../components/Avatar.jsx';
import Icon from '../components/Icon.jsx';
import PlanPanel from '../components/PlanPanel.jsx';
import useUserMedia from '../hooks/useUserMedia.js';
import { createVoiceAgent, VOICE_WANTS_AUDIO, IS_LIVE_VOICE } from '../agents/index.js';
import { isSpeechMuted, setSpeechMuted } from '../agents/speech.js';
import { validateTriage } from '../contracts.js';

function fmt(sec) {
  return `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`;
}

// Voice first. The camera and photos are optional extras the user can add any time.
export default function VoiceCall({ t, lang, triage, vet, insurance, onTriage, onCall, onEnd }) {
  const [consent, setConsent] = useState(false);
  const [trace, setTrace] = useState([]);
  const [camOn, setCamOn] = useState(false);
  const [facing, setFacing] = useState('environment');
  const [micOn, setMicOn] = useState(!IS_LIVE_VOICE);
  const [soundOn, setSoundOn] = useState(!isSpeechMuted());
  const [aiLine, setAiLine] = useState('');
  const [userLine, setUserLine] = useState('');
  const [speaking, setSpeaking] = useState('none');
  const [listening, setListening] = useState(false);
  const [chips, setChips] = useState([]);
  const [draft, setDraft] = useState('');
  const [photos, setPhotos] = useState([]); // { url, received }
  const [error, setError] = useState('');
  const [sheetOpen, setSheetOpen] = useState(true);
  const [secs, setSecs] = useState(0);

  const videoRef = useRef(null);
  const fileRef = useRef(null);
  const agentRef = useRef(null);
  const photoUrls = useRef([]);
  const onTriageRef = useRef(onTriage);
  onTriageRef.current = onTriage;

  const mic = useUserMedia({ enabled: VOICE_WANTS_AUDIO && consent && micOn, audio: true });
  const cam = useUserMedia({ enabled: camOn, video: true, facing });

  // ---- the conversation with Pawse
  useEffect(() => {
    if (IS_LIVE_VOICE && !consent) return;
    const agent = createVoiceAgent({ lang, shareWithGemini: consent });
    agentRef.current = agent;
    const off = agent.on((e) => {
      switch (e.type) {
        case 'transcript':
          if (e.role === 'ai') setAiLine(e.text);
          else setUserLine(e.text);
          break;
        case 'speaking':
          setSpeaking(e.who);
          break;
        case 'listening':
          setListening(e.on);
          break;
        case 'suggestions':
          setChips(e.items || []);
          break;
        case 'image_received':
          setPhotos((p) => p.map((x, i) => (i === p.length - 1 ? { ...x, received: true } : x)));
          break;
        case 'agents': setTrace(e.trace); break;
        case 'triage': {
          const problems = validateTriage(e);
          if (problems.length) console.warn('[Pawse] triage violates the contract:', problems, e);
          onTriageRef.current(e);
          setSheetOpen(true);
          break;
        }
        case 'error':
          setError(e.message || '');
          break;
        default:
          break;
      }
    });
    agent.setMicMuted(!micOn);
    agent.start();
    return () => {
      off();
      agent.end();
    };
  }, [lang, consent]);

  // ---- media → <video> and → agent
  useEffect(() => {
    if (videoRef.current) videoRef.current.srcObject = cam.stream || null;
  }, [cam.stream, camOn]);

  useEffect(() => {
    agentRef.current && agentRef.current.attachMedia({ audio: mic.stream || null, video: cam.stream || null });
  }, [mic.stream, cam.stream]);

  useEffect(() => {
    const id = setInterval(() => setSecs((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(
    () => () => {
      photoUrls.current.forEach((u) => URL.revokeObjectURL(u));
    },
    []
  );

  // keep the screen awake during the call (best effort)
  useEffect(() => {
    let lock = null;
    (async () => {
      try {
        if ('wakeLock' in navigator) lock = await navigator.wakeLock.request('screen');
      } catch {
        /* not available */
      }
    })();
    return () => {
      try {
        lock && lock.release();
      } catch {
        /* ignore */
      }
    };
  }, []);

  const send = (text) => {
    const s = String(text || '').trim();
    if (!s) return;
    agentRef.current && agentRef.current.sendText(s);
    setDraft('');
  };

  const onPhoto = (e) => {
    const file = e.target.files && e.target.files[0];
    e.target.value = '';
    if (!file) return;
    const url = URL.createObjectURL(file);
    photoUrls.current.push(url);
    setPhotos((p) => [...p, { url, received: false }]);
    agentRef.current && agentRef.current.sendImage(file);
  };

  const toggleMic = () => {
    const next = !micOn;
    setMicOn(next);
    agentRef.current && agentRef.current.setMicMuted(!next);
  };

  const toggleSound = () => {
    const next = !soundOn;
    setSoundOn(next);
    setSpeechMuted(!next);
  };

  const status = listening ? null : speaking === 'ai' ? t.aiSpeaking : aiLine ? '' : t.connecting;
  const sheetVisible = triage && sheetOpen;
  const lastPhoto = photos[photos.length - 1];

  return (
    <main className="vcall">
      {IS_LIVE_VOICE && !consent && <section className="card">
        <p>Share your messages, selected photos and recorded speech with Gemini for care guidance. Camera video is a local preview only.</p>
        <button className="btn primary" onClick={() => setConsent(true)}>Agree and start</button>
        <button className="btn ghost" onClick={onEnd}>Back</button>
      </section>}
      {trace.length > 0 && <details className="card"><summary>Agent results</summary>{trace.map(x => <p key={x.agent_id}>{x.agent_id}: {x.state} — {x.detail}</p>)}</details>}
      <div className="vcall-top">
        <span className="timer-pill">
          <span className="rec-dot" aria-hidden="true" /> {fmt(secs)}
        </span>
        {triage && <span className={`top-level level-${triage.level}`}>{triage.headline || t.levels[triage.level]}</span>}
        <button type="button" className="round-btn" onClick={toggleSound} aria-pressed={!soundOn} aria-label={t.sound} title={t.sound}>
          <Icon name={soundOn ? 'volume' : 'volumeOff'} size={20} />
        </button>
      </div>

      <section className="stage">
        {camOn ? (
          <div className="cam-card">
            {cam.stream ? (
              <video ref={videoRef} className={facing === 'user' ? 'mirror' : ''} autoPlay playsInline muted />
            ) : (
              <div className="cam-msg">
                <Icon name="videoOff" size={28} />
                <span>{cam.error ? t.camUnavailable : t.camOpening}</span>
              </div>
            )}
            <div className={`cam-pip ${speaking === 'ai' ? 'talking' : ''}`}>
              <Avatar size={52} speaking={speaking === 'ai'} listening={listening} />
            </div>
            <div className="cam-tools">
              <button type="button" className="cam-tool" onClick={() => setFacing((f) => (f === 'user' ? 'environment' : 'user'))} aria-label={t.flip} disabled={!cam.stream}>
                <Icon name="flip" size={18} />
              </button>
              <button type="button" className="cam-tool" onClick={() => setCamOn(false)} aria-label={t.closeCamera}>
                <Icon name="x" size={18} />
              </button>
            </div>
          </div>
        ) : (
          <div className={`avatar-stage ${speaking === 'ai' ? 'talking' : ''} ${listening ? 'listening' : ''}`}>
            <span className="halo h1" aria-hidden="true" />
            <span className="halo h2" aria-hidden="true" />
            <Avatar size={168} speaking={speaking === 'ai'} listening={listening} />
          </div>
        )}
        <p className="stage-name">Pawse</p>
        <p className="stage-status" aria-live="polite">
          {listening ? (
            <span className="listening-label">
              <span className="dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              {t.listening}
            </span>
          ) : (
            status
          )}
        </p>
      </section>

      {!sheetVisible && (
        <div className="vcall-bottom">
          <div className="captions" aria-live="polite">
            {userLine && <p className="cap-user">{userLine}</p>}
            {lastPhoto && (
              <div className="cap-photo">
                <img src={lastPhoto.url} alt={t.photoSent} />
                <span>{lastPhoto.received ? `✓ ${t.photoSent}` : '…'}</span>
              </div>
            )}
            {aiLine && <p className="cap-ai">{aiLine}</p>}
            {error && <p className="cap-error">{error}</p>}
            {VOICE_WANTS_AUDIO && mic.error && <p className="cap-error">{t.micUnavailable}</p>}
          </div>

          {chips.length > 0 && (
            <div className="kw-chips" role="group" aria-label="Suggestions">
              {chips.map((c) => (
                <button key={c} type="button" className="kw-chip" onClick={() => send(c)}>
                  {c}
                </button>
              ))}
            </div>
          )}

          <form
            className="type-bar"
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
          >
            <button type="button" className="type-icon" onClick={() => fileRef.current && fileRef.current.click()} aria-label={t.photo} title={t.photo}>
              <Icon name="camera" size={20} />
            </button>
            <input
              disabled={IS_LIVE_VOICE && !consent}
              maxLength={4000}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={t.typePlaceholder}
              aria-label={t.typePlaceholder}
              enterKeyHint="send"
            />
            <button type="submit" className="type-send" aria-label={t.send} disabled={!draft.trim()}>
              <Icon name="send" size={18} />
            </button>
          </form>
          <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden onChange={onPhoto} />

          <nav className="call-controls" aria-label="Call controls">
            <button type="button" className={micOn ? 'ctl' : 'ctl off'} onClick={toggleMic} aria-pressed={!micOn} aria-label={t.mic}>
              <Icon name={micOn ? 'mic' : 'micOff'} size={26} />
            </button>
            <button type="button" className="ctl hang" onClick={onEnd} aria-label={t.hangup}>
              <Icon name="phone" size={28} style={{ transform: 'rotate(135deg)' }} />
            </button>
            <button type="button" className={camOn ? 'ctl on' : 'ctl'} onClick={() => setCamOn((v) => !v)} aria-pressed={camOn} aria-label={t.camera}>
              <Icon name={camOn ? 'video' : 'videoOff'} size={26} />
            </button>
          </nav>
        </div>
      )}

      {triage && !sheetOpen && (
        <button type="button" className="reopen" onClick={() => setSheetOpen(true)}>
          <Icon name="chevronUp" size={18} /> {t.viewAdvice}
        </button>
      )}

      {sheetVisible && (
        <div className="sheet" role="dialog" aria-label={t.adviceTitle}>
          <div className="sheet-grab" aria-hidden="true" />
          <PlanPanel t={t} triage={triage} vet={vet} insurance={insurance} onCall={onCall} />
          <div className="sheet-foot">
            <button type="button" className="btn ghost" onClick={() => setSheetOpen(false)}>
              {t.keepTalking}
            </button>
            <button type="button" className="btn soft" onClick={onEnd}>
              {t.done}
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
