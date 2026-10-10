// SLOT 2: clinic search against the Pawse FastAPI backend.
// Endpoint: POST /api/v1/care/requests (same origin; Vite proxies /api to :8765).
// Base URL defaults to ''; override with VITE_CLINIC_SEARCH_URL (e.g. https://pawse.example.com).
//
// Consent: only location sharing is sent (share_location=true, and only when a location exists).
// share_with_ai stays false and the query is a generic string, so no symptoms leave the device
// for a clinic lookup. The backend enforces consent server-side as well.

import { CLINIC_SEARCH_URL } from '../config.js';

const ENDPOINT = '/api/v1/care/requests';

export function haversineKm(a, b) {
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371.0088 * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Map one backend Clinic to the frontend Clinic. Never invents hours or distance. */
export function mapClinic(c, location) {
  let distanceKm = Number.NaN; // unknown; the page shows a dash
  if (typeof c.distance_km === 'number') distanceKm = c.distance_km;
  else if (location && c.location && typeof c.location.lat === 'number') distanceKm = haversineKm(location, c.location);
  const openUnknown = typeof c.open_now !== 'boolean';
  const out = {
    id: c.id,
    name: c.name,
    address: c.address || '',
    distanceKm,
    openNow: c.open_now === true,
    hoursText: openUnknown ? 'Hours unknown, call to confirm' : (c.open_now ? 'Reported open now by provider, call to confirm' : 'Reported closed by provider'),
  };
  if (openUnknown) out.openUnknown = true;
  if (c.emergency_service === 'provider_reported') out.emergency = true;
  if (typeof c.rating === 'number') out.rating = c.rating;
  if (c.maps_url) out.mapsUrl = c.maps_url;
  if (c.phone) out.phone = c.phone;
  return out;
}

export async function liveSearchClinics({ lang = 'en', location = null, triage = null } = {}) {
  if (!location) throw new Error('Location is needed to find nearby clinics (permission denied or unavailable).');
  const body = {
    query: 'Find nearby veterinary clinics for a cat.',
    language: /^[a-z]{2}$/.test(lang) ? lang : 'en',
    location: { lat: location.lat, lng: location.lng },
    share_location: true,
    share_with_ai: false,
  };
  const res = await fetch((CLINIC_SEARCH_URL || '') + ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Clinic search failed (${res.status})`);
  const data = await res.json();
  const raw = Array.isArray(data && data.clinics) ? data.clinics : [];
  if (!raw.length) {
    const why = (data && data.warnings && data.warnings.join(', ')) || (data && data.providers && JSON.stringify(data.providers)) || 'no details';
    throw new Error(`No clinics returned by the backend (clinic provider not configured or unavailable: ${why}).`);
  }
  const clinics = raw.map((c) => mapClinic(c, location));
  // Nearest first; unknown distances last. Stable otherwise.
  clinics.sort((a, b) => (Number.isNaN(a.distanceKm) - Number.isNaN(b.distanceKm)) || (a.distanceKm - b.distanceKm) || 0);
  return { clinics };
}
