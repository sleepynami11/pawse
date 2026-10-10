// The owner's insurer and plan, as they told Pawse. Stored on this device only; never proof of cover.
const KEY = 'pawse.insurance';

function clean(value, max) {
  return typeof value === 'string' ? value.trim().slice(0, max) : '';
}

export function normalizeInsuranceProfile(raw) {
  const company = clean(raw?.company, 100);
  if (!company) return null;
  const plan = clean(raw?.plan, 120);
  return plan ? { company, plan } : { company };
}

export function loadInsuranceProfile(storage = globalThis.localStorage) {
  try {
    return normalizeInsuranceProfile(JSON.parse(storage?.getItem(KEY) || 'null'));
  } catch {
    return null;
  }
}

export function saveInsuranceProfile(raw, storage = globalThis.localStorage) {
  const profile = normalizeInsuranceProfile(raw);
  try {
    if (profile) storage?.setItem(KEY, JSON.stringify(profile));
    else storage?.removeItem(KEY);
  } catch {}
  return profile;
}
