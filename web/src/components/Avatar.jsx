// Pawse, the virtual avatar: an original pink cat-ish face with a sakura blossom.
// Blinks on its own; the mouth moves while `speaking`.

function Blossom({ x, y, r = 4.2 }) {
  const petals = [0, 72, 144, 216, 288].map((deg) => {
    const rad = ((deg - 90) * Math.PI) / 180;
    return <circle key={deg} cx={x + Math.cos(rad) * r} cy={y + Math.sin(rad) * r} r={r * 0.85} fill="#ffb3c8" />;
  });
  return (
    <g>
      {petals}
      <circle cx={x} cy={y} r={r * 0.55} fill="#fff1a8" />
    </g>
  );
}

export default function Avatar({ size = 96, speaking = false, listening = false, className = '' }) {
  const cls = ['pawse-avatar', speaking && 'is-speaking', listening && 'is-listening', className]
    .filter(Boolean)
    .join(' ');
  return (
    <svg className={cls} width={size} height={size} viewBox="0 0 120 120" aria-hidden="true">
      <defs>
        <radialGradient id="pawse-face" cx="50%" cy="38%" r="65%">
          <stop offset="0" stopColor="#fff6f8" />
          <stop offset="1" stopColor="#ffc9d8" />
        </radialGradient>
      </defs>

      {/* ears */}
      <path d="M20 54 L27 14 L54 36 Z" fill="#ffc9d8" stroke="#f3a9bf" strokeWidth="2" strokeLinejoin="round" />
      <path d="M27 46 L30 24 L45 36 Z" fill="#f79bb7" />
      <path d="M100 54 L93 14 L66 36 Z" fill="#ffc9d8" stroke="#f3a9bf" strokeWidth="2" strokeLinejoin="round" />
      <path d="M93 46 L90 24 L75 36 Z" fill="#f79bb7" />

      {/* face */}
      <ellipse cx="60" cy="68" rx="45" ry="40" fill="url(#pawse-face)" stroke="#f3a9bf" strokeWidth="2" />

      <Blossom x={88} y={30} />

      {/* eyes */}
      <g className="eyes">
        <ellipse cx="44" cy="64" rx="5.2" ry="6.6" fill="#3a2530" />
        <ellipse cx="76" cy="64" rx="5.2" ry="6.6" fill="#3a2530" />
        <circle cx="45.8" cy="61.4" r="1.8" fill="#fff" />
        <circle cx="77.8" cy="61.4" r="1.8" fill="#fff" />
      </g>

      {/* cheeks */}
      <ellipse cx="32" cy="78" rx="7" ry="4.5" fill="#ff9fbc" opacity="0.55" />
      <ellipse cx="88" cy="78" rx="7" ry="4.5" fill="#ff9fbc" opacity="0.55" />

      {/* nose + mouth */}
      <path d="M56.5 73 L63.5 73 L60 77 Z" fill="#e0607f" />
      <ellipse className="mouth" cx="60" cy="84" rx="5.5" ry="2.6" fill="#b83a62" />

      {/* whiskers */}
      <g stroke="#e8a0b4" strokeWidth="1.6" strokeLinecap="round">
        <line x1="14" y1="72" x2="26" y2="74" />
        <line x1="15" y1="80" x2="26" y2="79" />
        <line x1="106" y1="72" x2="94" y2="74" />
        <line x1="105" y1="80" x2="94" y2="79" />
      </g>
    </svg>
  );
}
