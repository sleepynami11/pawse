import { useEffect, useRef, useState } from 'react';
import { blobToWavBase64 } from '../agents/liveVoiceAgent.js';
import { generateSpeech } from '../agents/handoff.js';

const EMERGENCY_TEST = 'Dies ist eine Übung, kein echter Notruf. Guten Tag, hier spricht die KI-Assistenz im Auftrag der Katzenhalterin oder des Katzenhalters. Meine Katze Mimi hinkt nach einem Sprung. Können wir sie heute untersuchen lassen? Bitte bestätigen Sie die Adresse und ob Sie Katzen behandeln.';
export default function OwnVoice({onBack}) {
  const [profile,setProfile]=useState({}),[language,setLanguage]=useState('en'),[consent,setConsent]=useState(false);
  const [recording,setRecording]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [sample,setSample]=useState(null),[sampleUrl,setSampleUrl]=useState(''),[preview,setPreview]=useState(''),[result,setResult]=useState('');
  const [heard,setHeard]=useState(false),[approved,setApproved]=useState(false);
  const resources=useRef({stream:null,recorder:null,timer:null,urls:[],controller:null,alive:true});
  const makeUrl=blob=>{if(!resources.current.alive)return '';const u=URL.createObjectURL(blob);resources.current.urls.push(u);return u;};
  async function api(path, body, binary=false, signal){
    const r=await fetch(`/api/v1/voice/${path}`,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,signal});
    if(!r.ok){const j=await r.json().catch(()=>({}));throw Error(typeof j.detail==='string'?j.detail:`Voice request failed (${r.status})`);}
    return binary?r.blob():r.json();
  }
  useEffect(()=>{
    resources.current.alive=true;
    const ctl=new AbortController();api('status',null,false,ctl.signal).then(setProfile).catch(()=>{});
    return ()=>{ctl.abort();const r=resources.current;r.alive=false;clearTimeout(r.timer);r.controller?.abort();if(r.recorder?.state==='recording')r.recorder.stop();r.stream?.getTracks().forEach(t=>t.stop());r.urls.forEach(URL.revokeObjectURL);};
  },[]);
  async function task(fn){
    if(resources.current.controller||recording)return;
    const ctl=new AbortController();resources.current.controller=ctl;const timer=setTimeout(()=>ctl.abort(),65000);
    setBusy(true);setError('');
    try{await fn(ctl.signal);}catch(e){if(resources.current.alive)setError(e.name==='AbortError'?'Request timed out. Check voice status before retrying.':e.message);}
    finally{clearTimeout(timer);resources.current.controller=null;if(resources.current.alive)setBusy(false);}
  }
  async function record(){
    if(busy||recording)return;
    setBusy(true);setError('');setSample(null);setSampleUrl('');
    try{
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});
      if(!resources.current.alive){stream.getTracks().forEach(t=>t.stop());return;}
      resources.current.stream=stream;
      const rec=new MediaRecorder(stream), chunks=[];resources.current.recorder=rec;
      rec.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
      rec.onstop=async()=>{
        clearTimeout(resources.current.timer);stream.getTracks().forEach(t=>t.stop());
        if(!resources.current.alive)return;
        setRecording(false);setBusy(true);
        try{
          const data=await blobToWavBase64(new Blob(chunks,{type:rec.mimeType}));
          if(!data)throw Error('Recording too short. Read the sample for 10–25 seconds.');
          const bytes=Uint8Array.from(atob(data),c=>c.charCodeAt(0));const duration=(bytes.length-44)/32000;
          if(duration<10||duration>30)throw Error('Record 10–30 seconds. Try again at a natural pace.');
          if(resources.current.alive){setSample(data);setSampleUrl(makeUrl(new Blob([bytes],{type:'audio/wav'})));}
        }catch(e){if(resources.current.alive)setError(e.message);}finally{if(resources.current.alive)setBusy(false);}
      };
      rec.start();setRecording(true);setBusy(false);resources.current.timer=setTimeout(()=>{if(rec.state==='recording')rec.stop();},25000);
    }catch(e){resources.current.stream?.getTracks().forEach(t=>t.stop());setBusy(false);setError('Microphone unavailable. Allow recording in your browser and try again.');}
  }
  return <main className="plan handoff">
    <h1>My voice · emergency rehearsal</h1>
    <p>Record your own voice for 10–25 seconds. Nothing is sent until you confirm cloning. This rehearsal does not call a clinic.</p>
    <p>{profile.gradium_configured?'Gradium configured':'Gradium key missing: local recording and playback work; cloning needs GRADIUM_API_KEY on the server.'}</p>
    <section className="card">
      <label>Recording language<select disabled={busy||recording} value={language} onChange={e=>{setLanguage(e.target.value);setSample(null);setSampleUrl('');}}><option value="en">English</option><option value="de">German</option></select></label>
      <p>{language==='en'?'Hello, I am recording my own voice for Pawse. My cat is very important to me. I want to explain calmly to the veterinary practice what happened, ask whether they can see her today, and understand every next step. Please include me in every decision.':'Hallo, ich nehme meine eigene Stimme für Pawse auf. Meine Katze ist mir sehr wichtig. Ich möchte der Tierarztpraxis ruhig erklären, was passiert ist, und alle nächsten Schritte verstehen. Bitte beziehen Sie mich bei jeder Entscheidung mit ein.'}</p>
      <button className="btn primary" disabled={busy} onClick={()=>recording?resources.current.recorder.stop():record()}>{recording?'Stop recording':'Record my voice'}</button>
      {sampleUrl&&<audio controls src={sampleUrl}/>}
      <label><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> This is my own voice. I agree to send this recording to Gradium to create and preview my voice.</label>
      <button className="btn soft" disabled={busy||recording||!sample||!consent||!profile.gradium_configured||!!profile.source_id} onClick={()=>task(async signal=>{setHeard(false);setApproved(false);setProfile(await api('clone',{audio:{data:sample},sample_language:language,own_voice_consent:true,share_with_gradium:true},false,signal));})}>Clone my voice</button>
    </section>
    {profile.source_id&&<section className="card">
      <h2>German voice preview</h2>
      {!profile.german_voice_id&&!profile.candidate_pending&&<button className="btn soft" disabled={busy||recording||!consent} onClick={()=>task(async signal=>setProfile(await api('localizations',{share_with_gradium:true},false,signal)))}>Create German version</button>}
      {profile.candidate_pending&&!profile.candidate_ready&&<button className="btn soft" disabled={busy||recording} onClick={()=>task(async signal=>setProfile(await api('localizations/current',null,false,signal)))}>Check readiness</button>}
      <button className="btn soft" disabled={busy||recording||!consent||!(profile.german_voice_id||profile.candidate_ready)} onClick={()=>task(async signal=>{setHeard(false);setApproved(false);setPreview(makeUrl(await api('preview',{share_with_gradium:true},true,signal)));})}>Generate preview</button>
      {preview&&<audio controls src={preview} onEnded={()=>setHeard(true)}/>}
      <label><input type="checkbox" disabled={!heard} checked={approved} onChange={e=>setApproved(e.target.checked)}/> I listened to the preview and approve this voice for the test below.</label>
      {profile.candidate_ready&&!profile.german_voice_id&&<button className="btn soft" disabled={busy||recording||!approved||!consent} onClick={()=>task(async signal=>setProfile(await api('localizations/current/save',{share_with_gradium:true,listened_to_preview:true},false,signal)))}>Save approved voice</button>}
    </section>}
    <section className="card"><h2>Emergency scenario · test only</h2><p lang="de">{EMERGENCY_TEST}</p>
      <p>English: This is a rehearsal, not a real emergency call. Mimi is limping after a jump. Can she be examined today? Please confirm the address and that the practice treats cats.</p>
      <button className="btn primary" disabled={busy||recording||!consent||!approved||!profile.my_voice_ready} onClick={()=>task(async signal=>setResult(makeUrl(await generateSpeech(EMERGENCY_TEST,'my_voice',consent,signal))))}>Speak the rehearsal in my voice</button>
      {result&&<><audio controls src={result}/><a href={result} download="pawse-own-voice-rehearsal.wav">Download rehearsal</a></>}
    </section>
    {busy&&<p role="status">Preparing voice…</p>}{error&&<p role="alert">{error}</p>}
    <button className="btn ghost" onClick={onBack}>Back</button>
  </main>;
}
