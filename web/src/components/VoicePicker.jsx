import { GRADIUM_VOICES, gradiumSupports } from '../agents/gradiumVoice.js';

// "Pawse's voice" picker for live calls: a Gradium catalog voice (default) or Gemini Live's native voice.
// value: a Gradium voice id, or null for Gemini. Changing it during a call restarts the conversation.
export default function VoicePicker({ lang, value, onChange, compact = false }) {
  const voices = GRADIUM_VOICES[lang] || [];
  return (
    <label className={`voice-picker ${compact ? 'compact' : ''}`} title="Changing the voice restarts the conversation">
      <span className="voice-picker-icon" aria-hidden="true">
        <i /><i /><i /><i />
      </span>
      <span className="voice-picker-label">Pawse's voice</span>
      <select value={value || 'gemini'} onChange={(e) => onChange(e.target.value)}>
        {gradiumSupports(lang) && (
          <optgroup label="Gradium">
            {voices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} · {v.note}
              </option>
            ))}
          </optgroup>
        )}
        <optgroup label="Gemini">
          <option value="gemini">Gemini Live · native audio</option>
        </optgroup>
      </select>
      <svg className="voice-picker-chevron" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </label>
  );
}
