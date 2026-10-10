import { useEffect, useState } from 'react';
import Home from './pages/Home.jsx';
import VoiceCall from './pages/VoiceCall.jsx';
import ClinicList from './pages/ClinicList.jsx';
import PhoneCall from './pages/PhoneCall.jsx';
import Plan from './pages/Plan.jsx';
import { strings, detectLang, saveLang } from './i18n.js';
import { primeSpeech } from './agents/speech.js';
import { buildSummary } from './utils/summary.js';
import { IS_LIVE_PHONE } from './agents/index.js';
import { PHONE_AGENT_URL } from './config.js';

const GRADIUM_KEY = 'pawse.gradium';
function loadGradiumChoice() {
  try {
    return localStorage.getItem(GRADIUM_KEY) !== '0'; // on by default, the owner can turn it off
  } catch {
    return true;
  }
}

// home → voice call with Pawse → advice
//   → "call the vet": clinic list → Pawse calls the chosen clinic
//   → "call the insurer": Pawse calls the insurer
//   → plan (summary)
export default function App() {
  const [view, setView] = useState('home'); // home | voice | clinics | phone | plan
  const [lang, setLangState] = useState(detectLang);
  const [triage, setTriage] = useState(null);
  const [vet, setVet] = useState(null);
  const [insurance, setInsurance] = useState(null);
  const [clinic, setClinic] = useState(null);
  const [target, setTarget] = useState(null);
  const [gradiumOn, setGradiumOnState] = useState(loadGradiumChoice);
  const [voiceStatus, setVoiceStatus] = useState(null);

  const setGradiumOn = (on) => {
    setGradiumOnState(on);
    try {
      localStorage.setItem(GRADIUM_KEY, on ? '1' : '0');
    } catch {
      /* storage unavailable */
    }
  };

  // Live phone calls only: is Gradium configured, and does this session have its own German voice?
  useEffect(() => {
    if (!IS_LIVE_PHONE) return undefined;
    let alive = true;
    fetch(`${PHONE_AGENT_URL || ''}/api/v1/voice/status`)
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => alive && s && setVoiceStatus(s))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);
  // Unknown status: still offer Gradium; the call falls back to the browser voice on 503.
  const gradiumAvailable = IS_LIVE_PHONE && (!voiceStatus || voiceStatus.gradium_configured === true);
  const ownVoice = !!(voiceStatus && voiceStatus.my_voice_ready);

  const t = strings[lang];

  const setLang = (l) => {
    setLangState(l);
    saveLang(l);
  };

  useEffect(() => {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  }, [lang]);

  const startCall = () => {
    primeSpeech(); // unlock speech on iOS while we are inside the tap
    setTriage(null);
    setVet(null);
    setInsurance(null);
    setClinic(null);
    setView('voice');
  };

  const call = (to) => {
    primeSpeech();
    if (to === 'vet') {
      setView('clinics');
      return;
    }
    setTarget(to);
    setView('phone');
  };

  const pickClinic = (c) => {
    primeSpeech();
    setClinic(c);
    setTarget('vet');
    setView('phone');
  };

  const callDone = (result) => {
    if (result && target === 'vet') setVet(result);
    if (result && target === 'insurance') setInsurance(result);
    setView(triage ? 'plan' : 'home');
  };

  if (view === 'voice') {
    return (
      <VoiceCall
        t={t}
        lang={lang}
        triage={triage}
        vet={vet}
        insurance={insurance}
        onTriage={setTriage}
        onCall={call}
        onEnd={() => setView(triage ? 'plan' : 'home')}
      />
    );
  }
  if (view === 'clinics') {
    // Going back from the list never restarts the voice call: show the plan instead.
    return <ClinicList t={t} lang={lang} triage={triage} onPick={pickClinic} onBack={() => setView(triage ? 'plan' : 'home')} />;
  }
  if (view === 'phone') {
    return (
      <PhoneCall
        key={`${target}-${clinic ? clinic.id : ''}`}
        t={t}
        lang={lang}
        target={target}
        clinic={target === 'vet' ? clinic : null}
        gradium={gradiumAvailable ? { on: gradiumOn, ownVoice, set: setGradiumOn } : null}
        context={{
          gradiumConsent: gradiumAvailable && gradiumOn,
          voice: ownVoice ? 'my_voice' : 'standard',
          summary: buildSummary({ lang, triage, vet, insurance }),
          clinic: target === 'vet' ? clinic : undefined,
          estimate: vet ? vet.estimate : undefined,
        }}
        onDone={callDone}
      />
    );
  }
  if (view === 'plan' && triage) {
    return (
      <Plan
        t={t}
        lang={lang}
        triage={triage}
        vet={vet}
        insurance={insurance}
        onCall={call}
        onRestart={() => setView('home')}
      />
    );
  }
  return <Home t={t} lang={lang} setLang={setLang} onStart={startCall} />;
}
