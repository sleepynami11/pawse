// Demo clinic search: returns fictional Zurich clinics after a short pause.
// Implements the CLINIC SEARCH contract in ../contracts.js.

import { demoClinics } from './mockScripts.js';

export function mockSearchClinics({ lang = 'zh', speed = 1 } = {}) {
  const L = (o) => (o && typeof o === 'object' ? o[lang] ?? o.en : o);
  return new Promise((resolve) => {
    setTimeout(() => {
      const clinics = demoClinics
        .map((c) => ({
          ...c,
          hoursText: L(c.hoursText),
          mapsUrl: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(c.address)}`,
        }))
        .sort((a, b) => a.distanceKm - b.distanceKm);
      resolve({ clinics });
    }, 1100 / speed);
  });
}
