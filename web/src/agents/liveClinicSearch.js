// SLOT 2: clinic search against the Pawse FastAPI backend.
// Endpoint: POST /api/v1/clinics/search (same origin; Vite proxies /api to :8765). It is separate from
// /api/v1/care/requests, so it never waits on the voice agent's advice request still in flight.
// Base URL defaults to ''; override with VITE_CLINIC_SEARCH_URL (e.g. https://pawse.example.com).
//
// Consent: only coordinates and location-sharing consent are sent, never symptoms.
// The backend enforces the consent server-side as well.

import { CLINIC_SEARCH_URL } from '../config.js';

const ENDPOINT = '/api/v1/clinics/search';

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
  if (/^tel:\+[1-9]\d{6,14}$/.test(c.call_url || '')) out.callUrl = c.call_url;
  out.source = c.source; out.retrievedAt = c.retrieved_at;
  out.reasons = c.reasons || [];
  out.website = c.website;
  if (Array.isArray(c.opening_hours) && c.opening_hours.length) out.hoursList = c.opening_hours.map(String);
  return out;
}

export async function liveSearchClinics({ lang = 'en', location = null, triage = null } = {}) {
  if (!location) throw new Error('Location is needed to find nearby clinics (permission denied or unavailable).');
  const body = {
    language: /^[a-z]{2}$/.test(lang) ? lang : 'en',
    location: { lat: location.lat, lng: location.lng },
    share_location: true,
  };
  const res = await fetch((CLINIC_SEARCH_URL || '') + ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : `Clinic search failed (${res.status})`);
  }
  const data = await res.json();
  const raw = Array.isArray(data && data.clinics) ? data.clinics : [];
  if (!raw.length) {
    const why = (data && data.warnings && data.warnings.join(', ')) || 'no details';
    throw new Error(`No clinics returned by the backend (clinic provider not configured or unavailable: ${why}).`);
  }
  const clinics = raw.map((c) => mapClinic(c, location));
  // Preserve server ranking (opening status, distance, rating).
  return { clinics };
}
