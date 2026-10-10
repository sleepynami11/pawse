// Owner location for clinic search: ask the browser, fall back to central Zurich.
export const ZURICH = { lat: 47.3769, lng: 8.5417 };

/** Best-effort browser location; resolves null if refused, unavailable or slow. */
export function getLocation({ timeout = 5000 } = {}) {
  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => resolve(null),
      { timeout, maximumAge: 120000 }
    );
  });
}
