import { useEffect, useRef, useState } from 'react';
import Avatar from '../components/Avatar.jsx';
import Icon from '../components/Icon.jsx';
import ProviderChips from '../components/ProviderChips.jsx';
import { createPhoneCall, IS_LIVE_PHONE } from '../agents/index.js';
import { resolveVoiceName, onVoicesChanged } from '../agents/speech.js';
import { phoneProviders } from '../agents/providers.js';
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

// The owner only ever deals in English (their language): Pawse talks German with the clinic or
// insurer in the background. The screen shows progress steps, questions that need the owner's
// decision, and the result. The German transcript and audio are there on request, never in the way.
export default function PhoneCall({ t, lang, target, clinic, context, gradium, onDone }) {
  const base = t.callees[target];
  const callee = clinic
    ? { ...base, name: clinic.name, role: `${clinic.distanceKm.toFixed(1)} km` }
    : base;
  const [status, setStatus] = useState('dialing');
  const [lines, setLines] = useState([]);
  const [steps, setSteps] = useState([]); // [{ text } | { chose: label }], in call order
  const [question, setQuestion] = useState(null);
  const [speaking, setSpeaking] = useState('none');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [secs, setSecs] = useState(0);
  const [listening, setListening] = useState(false);
  // Pawse's real voice, updated by the agent's 'provider' events (e.g. Gradium -> browser fallback).
  const [voice, setVoice] = useState(() =>
    IS_LIVE_PHONE && gradium && gradium.on ? { voice: 'gradium', variant: context && context.voice } : null
  );
  const [browser, setBrowser] = useState(() => resolveVoiceName('de'));
  useEffect(() => {
    const refresh = () => setBrowser(resolveVoiceName('de'));
    return onVoicesChanged(refresh);
  }, []);
  const callRef = useRef(null);
  const listRef = useRef(null);
  const resultRef = useRef(null);
  const questionRef = useRef(null);
  resultRef.current = result;
  questionRef.current = question;

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
        case 'provider':
          if (e.step === 'voice') setVoice(e);
          break;
        case 'line':
          setLines((p) => [...p, e]);
          break;
        case 'progress':
          setSteps((p) => [...p, { text: e.text }]);
          break;
        case 'question':
          setQuestion(e);
          break;
        case 'answered': {
          const q = questionRef.current;
          if (q && q.id === e.id) {
            const opt = q.options.find((o) => o.id === e.optionId);
            setSteps((p) => [...p, { chose: opt ? opt.label : e.optionId }]);
            setQuestion(null);
          }
          break;
        }
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
  }, [steps, question, result]);

  const hangup = () => {
    callRef.current && callRef.current.hangup();
    onDone(resultRef.current);
  };

  const choose = (optionId) => {
    if (question && callRef.current && callRef.current.answer) callRef.current.answer(question.id, optionId);
  };

  const toggleListen = () => {
    const next = !listening;
    setListening(next);
    callRef.current && callRef.current.setListening && callRef.current.setListening(next);
  };

  const toggleGradium = () => {
    const next = !gradium.on;
    gradium.set(next);
    callRef.current && callRef.current.setGradiumConsent && callRef.current.setGradiumConsent(next);
  };

  const live = status !== 'ended' && !result;
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
        <span className="sim-badge">{t.simulatedCall}</span>
        <ProviderChips t={t} items={phoneProviders({ live: IS_LIVE_PHONE, target, voice, browser })} />
      </header>

      <section className="bridge" aria-label={t.bridgeNote}>
        <div className="bridge-side you">
          <span className="bridge-who">{t.you}</span>
          <strong>{t.ownerLang}</strong>
        </div>
        <div className="bridge-mid" aria-hidden="true">
          <span className={`bridge-wire ${status === 'connected' ? 'on' : ''}`} />
          <Avatar size={40} speaking={speaking === 'ai'} />
          <span className={`bridge-wire ${status === 'connected' ? 'on' : ''}`} />
        </div>
        <div className="bridge-side call">
          <span className="bridge-who">{t.onTheCall}</span>
          <strong lang="de">Deutsch</strong>
        </div>
        <p className="bridge-note">{t.bridgeNote}</p>
      </section>

      <section className="pc-lines" ref={listRef} aria-live="polite">
        <h2 className="pc-sub">{t.progressTitle}</h2>
        <ol className="steps">
          {status === 'dialing' && <li className="step now">{t.dialing}</li>}
          {steps.map((s, i) =>
            s.chose ? (
              <li key={i} className="step done you">
                {t.youChose}: <strong>{s.chose}</strong>
              </li>
            ) : (
              <li key={i} className={`step ${live && i === steps.length - 1 && !question ? 'now' : 'done'}`}>
                {s.text}
              </li>
            )
          )}
        </ol>

        {question && (
          <div className="ask-card" role="group" aria-label={t.questionTitle}>
            <h3>{t.questionTitle}</h3>
            <p>{question.text}</p>
            <div className="ask-options">
              {question.options.map((o) => (
                <button key={o.id} type="button" className="btn primary" onClick={() => choose(o.id)}>
                  {o.label}
                </button>
              ))}
            </div>
            <p className="muted small">{t.holdNote}</p>
          </div>
        )}

        {result && <ResultCard t={t} target={target} result={result} />}
        {error && <p className="pc-error">{error}</p>}

        {lines.length > 0 && (
          <details className="transcript">
            <summary>{t.transcript}</summary>
            {lines.map((l, i) => (
              <div key={i} className={`line line-${l.who}`}>
                <span className="line-who">{l.who === 'ai' ? t.pawse : callee.name}</span>
                {l.simulated && <span className="sim-badge">{t.simulated}</span>}
                <p className="line-text">{l.text}</p>
                <p className="line-original" lang="de">{l.original}</p>
              </div>
            ))}
          </details>
        )}
      </section>

      {gradium && listening && (
        <label className="pc-gradium">
          <input type="checkbox" checked={gradium.on} onChange={toggleGradium} />
          <span>
            <strong>{gradium.ownVoice ? t.gradiumOwnVoice : t.gradiumVoice}</strong>
            <span className="muted small">{t.gradiumNote}</span>
          </span>
        </label>
      )}

      <footer className="pc-foot">
        {!live ? (
          <button type="button" className="btn primary wide" onClick={() => onDone(resultRef.current)}>
            {t.backToPawse}
          </button>
        ) : (
          <div className="pc-controls">
            <button
              type="button"
              className={`pc-listen ${listening ? 'on' : ''}`}
              onClick={toggleListen}
              aria-pressed={listening}
            >
              <span className="pc-ctl">
                <Icon name={listening ? 'volume' : 'volumeOff'} />
              </span>
              <span className="small">{listening ? t.listeningIn : t.listenIn}</span>
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
