import { useState } from 'react';
import { loadInsuranceProfile, saveInsuranceProfile } from '../agents/insuranceProfile.js';

/** Optional insurer and plan, kept on this device. Pawse asks during the call when it is missing. */
export default function InsuranceProfileForm() {
  const [profile, setProfile] = useState(() => loadInsuranceProfile());
  const [company, setCompany] = useState(profile?.company || '');
  const [plan, setPlan] = useState(profile?.plan || '');
  function save(e) {
    e.preventDefault();
    setProfile(saveInsuranceProfile({ company, plan }));
  }
  return (
    <details className="insurance-profile">
      <summary>{profile ? `My insurance: ${profile.company}${profile.plan ? ` · ${profile.plan}` : ''}` : 'My insurance (optional)'}</summary>
      <form onSubmit={save}>
        <label>Insurer <input value={company} maxLength={100} onChange={(e) => setCompany(e.target.value)} placeholder="As shown on your policy" /></label>
        <label>Plan <input value={plan} maxLength={120} onChange={(e) => setPlan(e.target.value)} placeholder="If you know it" /></label>
        <button type="submit" className="btn soft">{company.trim() ? 'Save' : 'Clear'}</button>
        <p className="muted small">Stored on this device only. If you skip this, Pawse asks when you have an insurance question. This is never proof of cover.</p>
      </form>
    </details>
  );
}
