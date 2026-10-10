import Avatar from '../components/Avatar.jsx';
import Icon from '../components/Icon.jsx';
import { IS_MOCK } from '../agents/index.js';

const PETALS = [
  { left: '8%', delay: '0s', dur: '11s', size: 12 },
  { left: '24%', delay: '3s', dur: '13s', size: 9 },
  { left: '46%', delay: '6s', dur: '12s', size: 14 },
  { left: '67%', delay: '1.5s', dur: '14s', size: 10 },
  { left: '84%', delay: '4.5s', dur: '10s', size: 13 },
];

export default function Home({ t, lang, setLang, onStart }) {
  return (
    <main className="home">
      <div className="petals" aria-hidden="true">
        {PETALS.map((p, i) => (
          <span
            key={i}
            className="petal"
            style={{ left: p.left, animationDelay: p.delay, animationDuration: p.dur, width: p.size, height: p.size }}
          />
        ))}
      </div>

      <header className="topbar">
        <span className="brand">{t.appName}</span>
        <div className="lang-switch" role="group" aria-label="Language">
          {['zh', 'en'].map((l) => (
            <button
              key={l}
              type="button"
              className={l === lang ? 'chip on' : 'chip'}
              aria-pressed={l === lang}
              onClick={() => setLang(l)}
            >
              {l === 'zh' ? '中文' : 'EN'}
            </button>
          ))}
        </div>
      </header>

      <section className="home-hero">
        <div className="home-avatar">
          <Avatar size={150} />
        </div>
        <h1>
          {t.tagline.split('\n').map((line, i) => (
            <span key={i}>{line}</span>
          ))}
        </h1>
        <button type="button" className="start-btn" onClick={onStart}>
          <Icon name="phone" size={24} />
          {t.startCall}
        </button>
        <p className="muted">{t.startHint}</p>
        {IS_MOCK && <span className="badge">{t.mockBadge}</span>}
      </section>

      <footer className="disclaimer">{t.disclaimer}</footer>
    </main>
  );
}
