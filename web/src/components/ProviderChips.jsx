// Small "powered by" row: which AI or provider does each step. Items come from agents/providers.js.
export default function ProviderChips({ t, items, className = '' }) {
  if (!items || !items.length) return null;
  return (
    <ul className={`prov ${className}`} aria-label={t.prov.title}>
      {items.map((p, i) => {
        const detail = p.model || p.name;
        return (
          <li key={`${p.step}-${p.key}-${i}`} className={`prov-chip prov-${p.key}`}>
            <span className="prov-step">{t.prov.steps[p.step] || p.step}</span>
            <strong>{t.prov.keys[p.key] || p.key}</strong>
            {detail && <span className="prov-detail">{detail}</span>}
            {p.pending && <span className="prov-detail">{t.prov.pending}</span>}
          </li>
        );
      })}
    </ul>
  );
}
