import { useEffect, useRef, useState } from 'react';
import Avatar from '../components/Avatar.jsx';
import Icon from '../components/Icon.jsx';
import { createPhoneCall } from '../agents/index.js';
import { isSpeechMuted, setSpeechMuted } from '../agents/speech.js';
import { validateResult } from '../contracts.js';

function fmt(sec) {
  return `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`;
}

function ResultCard({ t, target, result }) {
  if (target === 'vet') {
    return (
      <div className="result-card">
        <h3>✓ {t.appointment}</h3>
        {result.simulated && <span className="sim-badge">{t.simulated}</span>}
        <div className="result-big">{result.time}</div>
        <p>{result.place}</p>
        <p>
          {t.estimate}: <strong>≈ {result.currency || 'CHF'} {result.estimate}</strong>
        </p>
        {result.note && <p className="muted small">{result.note}</p>}
      </div>
    );
  }
  const cur = result.currency || 'CHF';
  return (
    <div className="result-card">
      <h3>{t.insuranceAnswer}</h3>
      {result.simulated && <span className="sim-badge">{t.simulated}</span>}
      <ul className="cov">
        {result.points.map((p, i) => (
          <li key={i} className={p.ok ? 'ok' : 'no'}>
            <span className="cov-icon" aria-hidden="true">{p.ok ? '✓' : '✕'}</span>
            <span>
              {p.text}
              {p.ref && <span className="ref">{p.ref}</span>}
            </span>
          </li>
        ))}
      </ul>
      <div className="money">
        <div>
          <span className="muted small">{t.reimbursed}</span>
          <strong>≈ {cur} {result.reimbursed}</strong>
        </div>
        <div>
          <span className="muted small">{t.outOfPocket}</span>
          <strong className="accent">≈ {cur} {result.outOfPocket}</strong>
        </div>
      </div>
    </div>
  );
}

export default function PhoneCall({ t, lang, target, clinic, context, gradium, onDone }) {
  const base = t.callees[target];
  const callee = clinic
    ? { ...base, name: clinic.name, role: `${clinic.distanceKm.toFixed(1)} km` }
    : base;
  const [status, setStatus] = useState('dialing');
  const [lines, setLines] = useState([]);
  const [speaking, setSpeaking] = useState('none');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [secs, setSecs] = useState(0);
  const [soundOn, setSoundOn] = useState(!isSpeechMuted());
  const callRef = useRef(null);
  const listRef = useRef(null);
  const resultRef = useRef(null);
  resultRef.current = result;

  useEffect(() => {
    const call = createPhoneCall({ target, lang, context });
    callRef.current = call;
    const off = call.on((e) => {
      switch (e.type) {
        case 'status':
          setStatus(e.state);
          break;
        case 'speaking':
          setSpeaking(e.who);
          break;
        case 'line':
          setLines((p) => [...p, e]);
          break;
        case 'result': {
          const { type, ...r } = e;
          const problems = validateResult(target, r);
          if (problems.length) console.warn('[Pawse] call result violates the contract:', problems, r);
          setResult(r);
          break;
        }
        case 'error':
          setError(e.message || '');
          break;
        default:
          break;
      }
    });
    call.start();
    return () => {
      off();
      call.hangup();
    };
    // context is captured once per call on purpose
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, lang]);

  useEffect(() => {
    if (status !== 'connected') return undefined;
    const id = setInterval(() => setSecs((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [status]);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines, result]);

  const hangup = () => {
    callRef.current && callRef.current.hangup();
    onDone(resultRef.current);
  };

  const toggleSound = () => {
    const next = !soundOn;
    setSoundOn(next);
    setSpeechMuted(!next);
  };

  const toggleGradium = () => {
    const next = !gradium.on;
    gradium.set(next);
    callRef.current && callRef.current.setGradiumConsent && callRef.current.setGradiumConsent(next);
  };

  const statusText = status === 'dialing' ? t.dialing : status === 'connected' ? `${t.inCall} · ${fmt(secs)}` : t.callEnded;

  return (
    <main className="pc">
      <header className="pc-head">
        <div className={`pc-callee ${speaking === 'callee' ? 'talking' : ''} ${status === 'dialing' ? 'ringing' : ''}`}>
          <span aria-hidden="true">{callee.icon}</span>
        </div>
        <h1>{callee.name}</h1>
        <p className="muted">
          {callee.role} · {statusText}
        </p>
        <span className="pill">{t.liveTranslate}</span>
      </header>

      <div className="pc-pawse">
        <Avatar size={44} speaking={speaking === 'ai'} />
        <span>{t.aiNote}</span>
      </div>

      {gradium && (
        <label className="pc-gradium">
          <input type="checkbox" checked={gradium.on} onChange={toggleGradium} />
          <span>
            <strong>{gradium.ownVoice ? t.gradiumOwnVoice : t.gradiumVoice}</strong>
            <span className="muted small">{t.gradiumNote}</span>
          </span>
        </label>
      )}

      <section className="pc-lines" ref={listRef} aria-live="polite">
        {lines.map((l, i) => (
          <div key={i} className={`line line-${l.who}`}>
            <span className="line-who">{l.who === 'ai' ? t.pawse : callee.name}</span>
            {l.simulated && <span className="sim-badge">{t.simulated}</span>}
            <p className="line-original" lang="de">{l.original}</p>
            <p className="line-text">{l.text}</p>
          </div>
        ))}
        {result && <ResultCard t={t} target={target} result={result} />}
        {error && <p className="pc-error">{error}</p>}
      </section>

      <footer className="pc-foot">
        {result || status === 'ended' ? (
          <button type="button" className="btn primary wide" onClick={() => onDone(resultRef.current)}>
            {t.backToPawse}
          </button>
        ) : (
          <div className="pc-controls">
            <button type="button" className="pc-ctl" onClick={toggleSound} aria-pressed={!soundOn} aria-label={t.sound}>
              <Icon name={soundOn ? 'volume' : 'volumeOff'} />
            </button>
            <button type="button" className="pc-ctl hang" onClick={hangup} aria-label={t.hangup}>
              <Icon name="phone" size={28} style={{ transform: 'rotate(135deg)' }} />
            </button>
            <span className="pc-ctl-spacer" />
          </div>
        )}
      </footer>
    </main>
  );
}
