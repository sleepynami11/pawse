import { useCallback, useEffect, useState } from 'react';
import Icon from '../components/Icon.jsx';
import { searchClinics, IS_LIVE_CLINICS } from '../agents/index.js';
import ProviderChips from '../components/ProviderChips.jsx';
import { clinicProviders } from '../agents/providers.js';
import { validateClinics } from '../contracts.js';

/** Best-effort location; resolves null if refused, unavailable or slow. */
function getLocation() {
  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => resolve(null),
      { timeout: 5000, maximumAge: 120000 }
    );
  });
}

// Attribution for each clinic source; OSM data is ODbL and Google Maps content must be credited.
const SOURCE_LABELS = {
  google_places: 'Google Maps',
  gemini_maps: 'Google Maps',
  openstreetmap: '© OpenStreetMap contributors',
  mapify: 'Mapify',
};

export default function ClinicList({ t, lang, triage, onPick, onBack }) {
  const [state, setState] = useState({ status: 'loading', clinics: [], located: true });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, status: 'loading' }));
    const location = await getLocation();
    try {
      const res = await searchClinics({ lang, location, triage });
      const problems = validateClinics(res);
      if (problems.length) console.warn('[Pawse] clinic list violates the contract:', problems, res);
      setState({ status: 'ok', clinics: (res && res.clinics) || [], located: !!location });
    } catch (e) {
      console.warn('[Pawse] clinic search failed:', e);
      setState({ status: 'error', clinics: [], located: !!location, error: e.message });
    }
  }, [lang, triage]);

  useEffect(() => {
    load();
  }, [load]);

  const firstOpen = state.clinics.find((c) => c.openNow);

  return (
    <main className="clinics">
      <header className="clinics-head">
        <button type="button" className="round-btn light" onClick={onBack} aria-label={t.back}>
          <Icon name="arrowLeft" size={20} />
        </button>
        <div>
          <h1>{t.clinicsTitle}</h1>
          <p className="muted small">{t.clinicsSub}</p>
        </div>
      </header>
      {state.status !== 'loading' && (
        <ProviderChips t={t} items={clinicProviders({ live: IS_LIVE_CLINICS, clinics: state.clinics, failed: state.status === 'error' })} />
      )}

      {state.status === 'loading' && (
        <div className="clinic-list" aria-busy="true">
          <p className="muted center">{t.clinicsLoading}</p>
          {[0, 1, 2].map((i) => (
            <div key={i} className="clinic skeleton" aria-hidden="true">
              <span className="sk sk-title" />
              <span className="sk sk-line" />
              <span className="sk sk-line short" />
            </div>
          ))}
        </div>
      )}

      {state.status === 'error' && (
        <div className="clinic-empty">
          <p>{state.error || t.clinicsError}</p>
          <button type="button" className="btn primary" onClick={load}>
            {t.retry}
          </button>
        </div>
      )}

      {state.status === 'ok' && (
        <div className="clinic-list">
          {!state.located && <p className="note">{t.noLocation}</p>}
          {state.clinics.length === 0 && (
            <div className="clinic-empty">
              <p>{state.error || t.clinicsError}</p>
              <button type="button" className="btn primary" onClick={load}>
                {t.retry}
              </button>
            </div>
          )}
          {state.clinics.map((c) => (
            <article key={c.id} className={c.openNow || c.openUnknown ? 'clinic' : 'clinic closed'}>
              <div className="clinic-top">
                <h2>{c.name}</h2>
                <span className="clinic-dist">{Number.isFinite(c.distanceKm) ? `${c.distanceKm.toFixed(1)} km` : '–'}</span>
              </div>
              <div className="clinic-tags">
                {c.openUnknown ? (
                  <span className="tag plain">{c.hoursText}</span>
                ) : (
                  <span className={c.openNow ? 'tag open' : 'tag shut'}>{c.openNow ? t.openNow : t.closed}</span>
                )}
                {c.emergency && <span className="tag emer">{IS_LIVE_CLINICS ? 'Emergency service reported — confirm hours' : t.emergency24}</span>}
                {!IS_LIVE_CLINICS && firstOpen && firstOpen.id === c.id && <span className="tag near">{t.nearest}</span>}
                {typeof c.rating === 'number' && <span className="tag plain">★ {c.rating.toFixed(1)}</span>}
              </div>
              {c.hoursText && !c.openUnknown && <p className="muted small">{c.hoursText}</p>}
              {c.callUrl && <p className="small"><a href={c.callUrl}>{c.phone}</a></p>}
              {c.hoursList && (
                <details className="muted small">
                  <summary>Listed opening hours (call to confirm)</summary>
                  {c.hoursList.map((h) => <div key={h}>{h}</div>)}
                </details>
              )}
              <p className="muted small"><span translate="no">{SOURCE_LABELS[c.source] || c.source}</span> {c.retrievedAt}</p>
              <p className="clinic-addr small">{c.address}</p>
              <div className="clinic-actions">
                {c.mapsUrl && (
                  <a className="btn ghost small" href={c.mapsUrl} target="_blank" rel="noreferrer">
                    <Icon name="pin" size={16} /> {t.map}
                  </a>
                )}
                <button type="button" className="btn primary small" disabled={!c.openNow && !c.openUnknown} onClick={() => onPick(c)}>
                  <Icon name="phone" size={16} /> {IS_LIVE_CLINICS ? 'Prepare conversation' : t.callThis}
                </button>
              </div>
            </article>
          ))}
          <p className="ai-note center">{t.aiNote}</p>
        </div>
      )}
    </main>
  );
}
