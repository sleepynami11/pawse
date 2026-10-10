// Pawse's advice + the two "let Pawse call for you" actions.
// Used as the bottom sheet on the video call and at the top of the plan page.

const GLYPH = { red: '!', yellow: '◷', green: '✓' };

function ActionRow({ icon, title, sub, doneText, button, onClick }) {
  return (
    <div className={doneText ? 'action-row done' : 'action-row'}>
      <span className="action-icon" aria-hidden="true">{icon}</span>
      <div className="action-text">
        <strong>{title}</strong>
        <span>{doneText || sub}</span>
      </div>
      <button type="button" className={doneText ? 'btn soft small' : 'btn primary small'} onClick={onClick}>
        {button}
      </button>
    </div>
  );
}

export default function PlanPanel({ t, triage, vet, insurance, onCall }) {
  if (!triage) return null;
  const vetDone = vet ? `✓ ${t.booked} ${vet.time} · ≈ ${vet.currency || 'CHF'} ${vet.estimate}` : '';
  const insDone = insurance ? `✓ ${t.outOfPocket} ≈ ${insurance.currency || 'CHF'} ${insurance.outOfPocket}` : '';

  return (
    <div className="plan-panel">
      <div className={`level level-${triage.level}`}>
        <span className="level-glyph" aria-hidden="true">{GLYPH[triage.level]}</span>
        <div>
          <span className="level-kicker">{t.adviceTitle}</span>
          <strong className="level-title">{triage.headline || t.levels[triage.level]}</strong>
        </div>
      </div>

      <section>
        <h3>{t.nowDo}</h3>
        <ul className="steps">
          {triage.steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
        {triage.escalation && <p className="escalation">{triage.escalation}</p>}
      </section>

      <section>
        <h3>{t.transferTitle}</h3>
        <div className="actions">
          <ActionRow
            icon={t.callees.vet.icon}
            title={t.callVet}
            sub={t.callVetSub}
            doneText={vetDone}
            button={vet ? t.callAgain : t.call}
            onClick={() => onCall('vet')}
          />
          <ActionRow
            icon={t.callees.insurance.icon}
            title={t.callIns}
            sub={t.callInsSub}
            doneText={insDone}
            button={insurance ? t.callAgain : t.call}
            onClick={() => onCall('insurance')}
          />
        </div>
        <p className="ai-note">{t.aiNote}</p>
      </section>
    </div>
  );
}
