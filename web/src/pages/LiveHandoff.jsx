import { useEffect, useRef, useState } from 'react';
import { draftHandoff, searchDemoPolicy, generateSpeech } from '../agents/handoff.js';
import ProviderChips from '../components/ProviderChips.jsx';
import { loadCapabilities, handoffProviders } from '../agents/providers.js';
import { PHONE_AGENT_URL } from '../config.js';

export default function LiveHandoff({ t, lang, target, clinic, context, onDone, onRehearse }) {
  const [message, setMessage] = useState(context.summary || '');
  const [consent, setConsent] = useState(false);
  const [gradiumConsent, setGradiumConsent] = useState(false);
  const [voice, setVoice] = useState('my_voice');
  const [script, setScript] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [query, setQuery] = useState('accident deductible home visit');
  const [audio, setAudio] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [caps, setCaps] = useState(null);
  const pending = useRef(null);
  useEffect(() => { let alive = true; loadCapabilities(PHONE_AGENT_URL || '').then(c => alive && setCaps(c)); return () => { alive = false; }; }, []);
  const audioRef = useRef('');
  useEffect(() => () => { pending.current?.abort(); if (audioRef.current) URL.revokeObjectURL(audioRef.current); }, []);
  async function run(task) {
    if (pending.current) return;
    const controller = new AbortController(); pending.current = controller;
    const timer = setTimeout(() => controller.abort(), 65000);
    setBusy(true); setError('');
    try { await task(controller.signal); }
    catch (e) { if (!controller.signal.aborted) setError(e.message); else setError('Request stopped or timed out. Retry explicitly.'); }
    finally { clearTimeout(timer); pending.current = null; setBusy(false); }
  }
  function clearAudio() {
    if (audioRef.current) URL.revokeObjectURL(audioRef.current);
    audioRef.current = ''; setAudio('');
  }
  const callUrl = /^tel:\+[1-9]\d{6,14}$/.test(clinic?.callUrl || '') ? clinic.callUrl : null;
  return <main className="plan handoff">
    <h1>Prepare {target === 'insurance' ? 'insurer' : 'vet'} conversation</h1>
    <ProviderChips t={t} items={handoffProviders({ caps, voice, audioReady: !!audio, target })} />
    <p className="note">No call has been placed. No appointment or insurance coverage has been confirmed.</p>
    {clinic && <p>{clinic.name} · {clinic.phone || 'No published phone available'}</p>}
    <section className="card">
      <label>Facts and questions to include<textarea aria-label="Facts and questions" value={message} maxLength={4000} onChange={e => { setMessage(e.target.value); setScript(null); clearAudio(); }} /></label>
      <label><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /> Share these facts with Gemini to draft a German script with subtitles.</label>
      <button className="btn primary" disabled={busy || !consent || !message.trim()} onClick={() => run(async signal => { clearAudio(); setScript(null); setScript(await draftHandoff(message, lang, target, consent, signal)); })}>Generate German draft</button>
    </section>
    {script && <section className="card">
      <h2>Review before using</h2>
      {script.lines.map((line,i) => <div key={i}><p lang="de">{line.german}</p><p>{line.subtitle}</p></div>)}
      <label>Speech voice <select value={voice} onChange={e => {setVoice(e.target.value); clearAudio();}}><option value="my_voice">My approved voice</option><option value="standard">Standard German voice</option></select></label>
      <p>Own-voice enrollment is available in the <a href="/">existing voice setup</a> in this same browser session.</p>
      <label><input type="checkbox" checked={gradiumConsent} onChange={e => setGradiumConsent(e.target.checked)} /> I reviewed the script and agree to share it with Gradium using the selected voice.</label>
      <button className="btn primary" disabled={busy || !gradiumConsent} onClick={() => run(async signal => { clearAudio(); const blob = await generateSpeech(script.lines.map(x=>x.german).join('\n'),voice,gradiumConsent,signal); audioRef.current = URL.createObjectURL(blob); setAudio(audioRef.current); })}>Generate reviewed audio</button>
      {audio && <><audio controls src={audio} /><a href={audio} download="pawse-reviewed-script.wav">Download audio</a></>}
    </section>}
    {target === 'insurance' && <section className="card">
      <h2>Demo policy evidence — not your personal coverage</h2>
      <p>English lexical search over the demo policy only. Personal policy upload is not connected.</p>
      <input aria-label="Demo policy question in English" value={query} maxLength={1000} onChange={e => setQuery(e.target.value)} />
      <button className="btn soft" disabled={busy || !query.trim()} onClick={() => run(async signal => setEvidence(await searchDemoPolicy(query,signal)))}>Search demo evidence</button>
      {evidence && <><p>{evidence.status} · Insurance approval: {evidence.insurance_approval}</p>{evidence.evidence.map(e => <article key={e.evidence_id}><h3>{e.title} · {e.section}</h3><p style={{whiteSpace:'pre-wrap'}}>{e.snippet}</p><small>{e.source_id} · {e.source_sha256}</small></article>)}</>}
    </section>}
    {callUrl && <section className="card"><p>Open your device dialer for {clinic.name}. Pawse cannot join or speak into this call.</p><a className="btn soft" href={callUrl}>Open dialer: {clinic.phone}</a></section>}
    {busy && <p role="status">Preparing…</p>}{error && <p role="alert">{error}</p>}
    {onRehearse && <button className="btn soft" onClick={onRehearse}>Open simulated Mimi phone rehearsal</button>}
    <button className="btn ghost" onClick={() => onDone(null)}>Back to care summary</button>
  </main>;
}
