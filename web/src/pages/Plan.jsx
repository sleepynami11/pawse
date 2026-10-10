import { IS_LIVE_PHONE } from '../agents/index.js';
import { useState } from 'react';
import Avatar from '../components/Avatar.jsx';
import PlanPanel from '../components/PlanPanel.jsx';
import { buildSummary } from '../utils/summary.js';
import { copyText } from '../utils/copy.js';

export default function Plan({ t, lang, triage, vet, insurance, onCall, onRestart }) {
  const [copied, setCopied] = useState(false);
  const summary = buildSummary({ lang, triage, vet, insurance });

  return (
    <main className="plan">
      <header className="plan-head">
        <Avatar size={56} />
        <h1>{t.planTitle}</h1>
      </header>

      <div className="card">
        <PlanPanel t={t} triage={triage} vet={vet} insurance={insurance} onCall={onCall} />
      </div>

      <section className="card">
        <div className="card-head">
          <h2>{t.summary}</h2>
          <button
            type="button"
            className="btn soft small"
            onClick={async () => {
              if (await copyText(summary)) {
                setCopied(true);
                setTimeout(() => setCopied(false), 1800);
              }
            }}
          >
            {copied ? `✓ ${t.copied}` : t.copy}
          </button>
        </div>
        <pre className="summary">{summary}</pre>
      </section>

      <section className="card">
        <h2>{t.checklistTitle}</h2>
        <ul className="cov">
          {(IS_LIVE_PHONE ? ['Keep relevant photos and records', 'Request an itemised invoice', 'Check the actual policy and submission deadline with your insurer'] : t.checklist).map((c, i) => (
            <li key={i} className="ok">
              <span className="cov-icon" aria-hidden="true">✓</span>
              <span>{c}</span>
            </li>
          ))}
        </ul>
      </section>

      <p className="disclaimer">{t.disclaimer}</p>
      <button type="button" className="btn ghost wide" onClick={onRestart}>
        {t.restart}
      </button>
    </main>
  );
}
