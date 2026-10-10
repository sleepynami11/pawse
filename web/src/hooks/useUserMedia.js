import { useEffect, useState } from 'react';

/**
 * Opens the camera and/or microphone while `enabled`.
 * Returns { stream, error } – error is set when the device can't be opened
 * (no device, permission denied, or plain http on a phone).
 */
export default function useUserMedia({ enabled = true, video = false, audio = false, facing = 'environment' } = {}) {
  const [stream, setStream] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!enabled || (!video && !audio)) {
      setStream(null);
      setError(null);
      return undefined;
    }
    const md = typeof navigator !== 'undefined' ? navigator.mediaDevices : null;
    if (!md || !md.getUserMedia) {
      setError('unsupported');
      return undefined;
    }

    let cancelled = false;
    let current = null;
    setError(null);
    md.getUserMedia({ video: video ? { facingMode: { ideal: facing } } : false, audio })
      .then((s) => {
        if (cancelled) {
          s.getTracks().forEach((tr) => tr.stop());
          return;
        }
        current = s;
        setStream(s);
      })
      .catch((e) => {
        if (!cancelled) setError(e && e.name ? e.name : 'error');
      });

    return () => {
      cancelled = true;
      if (current) current.getTracks().forEach((tr) => tr.stop());
      setStream(null);
    };
  }, [enabled, video, audio, facing]);

  return { stream, error };
}
