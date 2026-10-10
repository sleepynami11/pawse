// Owner insurance profile: device-only, trimmed, bounded, clearable.
import assert from 'node:assert/strict';
import { loadInsuranceProfile, saveInsuranceProfile, normalizeInsuranceProfile } from '../src/agents/insuranceProfile.js';

const store = new Map();
const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: (k) => store.delete(k) };
assert.equal(normalizeInsuranceProfile({ company: '  ' }), null);
assert.deepEqual(saveInsuranceProfile({ company: ' Example ', plan: ' ' }, storage), { company: 'Example' });
assert.deepEqual(loadInsuranceProfile(storage), { company: 'Example' });
assert.deepEqual(saveInsuranceProfile({ company: 'Example', plan: 'Accident' }, storage), { company: 'Example', plan: 'Accident' });
assert.equal(normalizeInsuranceProfile({ company: 'x'.repeat(300) }).company.length, 100);
assert.equal(saveInsuranceProfile({ company: '' }, storage), null);
assert.equal(loadInsuranceProfile(storage), null);
store.set('pawse.insurance', '{broken');
assert.equal(loadInsuranceProfile(storage), null);
console.log('insurance profile ok');
