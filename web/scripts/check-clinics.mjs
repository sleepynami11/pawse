// Plain-Node check for the live clinic search mapping. Run: node web/scripts/check-clinics.mjs
import assert from 'node:assert/strict';
import { liveSearchClinics } from '../src/agents/liveClinicSearch.js';
import { validateClinics } from '../src/contracts.js';

const loc = { lat: 47.3769, lng: 8.5417 };
const backend = {
  status: 'complete', warnings: [], elapsed_ms: 5,
  clinics: [
    { id: 'far', name: 'Far Vet', address: 'B', location: { lat: 47.45, lng: 8.55 }, open_now: true, rating: 4.5,
      maps_url: 'https://maps.example/far', phone: '+41445550000', emergency_service: 'unknown', source: 'google_places' },
    { id: 'near', name: 'Near Vet', address: 'A', distance_km: 0.8, open_now: null, emergency_service: 'provider_reported', source: 'mapify' },
    { id: 'nodist', name: 'No Coords', address: 'C', open_now: false, source: 'mapify' },
  ],
};
let calls = [];
let reply = { ok: true, status: 200, json: async () => backend };
globalThis.fetch = async (url, init) => { calls.push({ url, body: JSON.parse(init.body) }); return reply; };

const res = await liveSearchClinics({ lang: 'en', location: loc, triage: { level: 'yellow' } });
assert.equal(calls[0].url, '/api/v1/clinics/search');
assert.equal(calls[0].body.share_location, true);
assert.equal('share_with_ai' in calls[0].body, false); assert.equal('query' in calls[0].body, false);
assert.deepEqual(calls[0].body.location, loc);
assert.deepEqual(validateClinics(res), []);
assert.deepEqual(res.clinics.map((c) => c.id), ['far', 'near', 'nodist']);
const [far, near, nodist] = res.clinics;
assert.equal(near.openNow, false); assert.equal(near.openUnknown, true);
assert.match(near.hoursText, /unknown/i); assert.equal(near.emergency, true);
assert.equal(far.openNow, true); assert.equal(far.openUnknown, undefined);
assert.ok(far.distanceKm > 8 && far.distanceKm < 8.5, `haversine ${far.distanceKm}`);
assert.equal(far.mapsUrl, 'https://maps.example/far'); assert.equal(far.phone, '+41445550000');
assert.ok(Number.isNaN(nodist.distanceKm)); assert.equal(nodist.openUnknown, undefined);

// empty -> clear error
backend.clinics = [];
await assert.rejects(() => liveSearchClinics({ location: loc }), /No clinics returned/);
// no location -> error, no request
calls = [];
await assert.rejects(() => liveSearchClinics({ location: null }), /Location is needed/);
assert.equal(calls.length, 0);
// http error
reply = { ok: false, status: 422, json: async () => ({}) };
await assert.rejects(() => liveSearchClinics({ location: loc }), /422/);
console.log('check-clinics: OK');
