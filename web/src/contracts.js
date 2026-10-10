// The interfaces between this frontend and the teammates' agents.
// Keep this file the single source of truth; README.md mirrors it.

/**
 * ============================================================ 1. VOICE AGENT
 * Voice conversation between the user and Pawse. Camera and photos are optional extras.
 * Teammate replaces src/agents/liveVoiceAgent.js.
 *
 * createVoiceAgent({ lang }) returns:
 *   on(cb) -> unsubscribe
 *   start()
 *   end()                          must emit {type:'ended'} exactly once
 *   sendText(text)                 typed text, or a tapped keyword chip
 *   sendImage(file)                a photo the user took or picked (File / Blob)
 *   attachMedia({ audio, video })  MediaStreams from the page; either may be null
 *                                  (audio = mic when wantsAudio; video = only while the camera is on)
 *   setMicMuted(bool)
 *   wantsAudio: boolean            if true the page opens the microphone
 *
 * Events:
 *   {type:'transcript', role:'user'|'ai', text, simulated?}   live captions
 *   {type:'speaking', who:'user'|'ai'|'none'}                  drives the avatar
 *   {type:'listening', on:boolean}
 *   {type:'suggestions', items:string[]}                       keyword chips ([] hides them)
 *   {type:'image_received'}                                    the last photo arrived
 *   {type:'triage', level, headline, steps:string[], escalation?:string, summary:string}
 *   {type:'error', message}
 *   {type:'ended'}
 *
 * ============================================================ 2. CLINIC SEARCH
 * Finds nearby vet clinics, shown as a list before Pawse calls one.
 * Teammate replaces src/agents/liveClinicSearch.js.
 *
 * searchClinics({ lang, location, triage }) -> Promise<{ clinics: Clinic[] }>
 *   location = { lat, lng } or null (user refused / unavailable)
 *
 * Clinic = { id, name, address, distanceKm, openNow:boolean, hoursText?, emergency?:boolean,
 *            rating?:number, mapsUrl? }
 *
 * ============================================================ 3. PHONE AGENT
 * Pawse calls the chosen clinic or the insurer for the user.
 * Teammate replaces src/agents/livePhoneAgent.js.
 *
 * createPhoneCall({ target:'vet'|'insurance', lang, context }) returns:
 *   on(cb) -> unsubscribe
 *   start()
 *   hangup()
 *   setGradiumConsent?(on:boolean)   optional: change Gradium consent for the remaining lines
 *   context = { summary: string, clinic?: Clinic, estimate?: number,
 *               gradiumConsent?: boolean, voice?: 'standard'|'my_voice' }
 *   gradiumConsent === true lets the live agent speak every AI line with Gradium (one voice per call).
 *
 * Events:
 *   {type:'status', state:'dialing'|'connected'|'ended'}
 *   {type:'speaking', who:'ai'|'callee'|'none'}
 *   {type:'line', who:'ai'|'callee', original:string, text:string}   original language + translation
 *   {type:'result', ...}
 *   {type:'error', message}
 *
 * result for 'vet':       {kind:'appointment', time, place, estimate:number, currency, note?}
 * result for 'insurance': {kind:'coverage', covered, currency, deductible, rate, estimate,
 *                          reimbursed, outOfPocket, points:[{ok, text, ref?}]}
 */

export const LEVELS = ['red', 'yellow', 'green'];

/** Problems with a triage event (empty list = OK). */
export function validateTriage(e) {
  const p = [];
  if (!e || typeof e !== 'object') return ['triage is not an object'];
  if (!LEVELS.includes(e.level)) p.push(`level must be one of ${LEVELS.join('|')}`);
  if (!e.headline) p.push('headline missing');
  if (!Array.isArray(e.steps) || !e.steps.length) p.push('steps must be a non-empty array');
  if (typeof e.summary !== 'string' || !e.summary) p.push('summary missing');
  return p;
}

/** Problems with a clinic list (empty list = OK). */
export function validateClinics(res) {
  const p = [];
  if (!res || !Array.isArray(res.clinics)) return ['expected { clinics: [...] }'];
  res.clinics.forEach((c, i) => {
    if (!c.id) p.push(`clinics[${i}].id missing`);
    if (!c.name) p.push(`clinics[${i}].name missing`);
    if (typeof c.distanceKm !== 'number') p.push(`clinics[${i}].distanceKm must be a number`);
    if (typeof c.openNow !== 'boolean') p.push(`clinics[${i}].openNow must be true/false`);
  });
  return p;
}

/** Problems with a phone-call result (empty list = OK). */
export function validateResult(target, r) {
  const p = [];
  if (!r || typeof r !== 'object') return ['result is not an object'];
  if (target === 'vet') {
    if (r.kind !== 'appointment') p.push("vet result kind must be 'appointment'");
    if (!r.time) p.push('time missing');
    if (typeof r.estimate !== 'number') p.push('estimate must be a number');
  } else if (target === 'insurance') {
    if (r.kind !== 'coverage') p.push("insurance result kind must be 'coverage'");
    for (const k of ['deductible', 'rate', 'estimate', 'reimbursed', 'outOfPocket']) {
      if (typeof r[k] !== 'number') p.push(`${k} must be a number`);
    }
    if (!Array.isArray(r.points)) p.push('points must be an array');
  } else p.push(`unknown target ${target}`);
  return p;
}
