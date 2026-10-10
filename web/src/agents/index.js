import { VOICE_AGENT, CLINIC_SEARCH, PHONE_AGENT, MOCK_SPEED } from '../config.js';
import { createMockVoiceAgent } from './mockVoiceAgent.js';
import { createLiveVoiceAgent } from './liveVoiceAgent.js';
import { mockSearchClinics } from './mockClinicSearch.js';
import { liveSearchClinics } from './liveClinicSearch.js';
import { createMockPhoneCall } from './mockPhoneAgent.js';
import { createLivePhoneCall } from './livePhoneAgent.js';

export const IS_LIVE_VOICE = VOICE_AGENT === 'live';
export const IS_LIVE_CLINICS = CLINIC_SEARCH === 'live';
export const IS_LIVE_PHONE = PHONE_AGENT === 'live';
export const IS_MOCK = !IS_LIVE_VOICE || !IS_LIVE_CLINICS || !IS_LIVE_PHONE;

/** The page opens the microphone only if the active voice agent wants audio. */
export const VOICE_WANTS_AUDIO = IS_LIVE_VOICE;

/** 1. Voice conversation with Pawse. */
export function createVoiceAgent(opts) {
  return IS_LIVE_VOICE ? createLiveVoiceAgent(opts) : createMockVoiceAgent({ speed: MOCK_SPEED, ...opts });
}

/** 2. Nearby vet clinics. */
export function searchClinics(opts) {
  return IS_LIVE_CLINICS ? liveSearchClinics(opts) : mockSearchClinics({ speed: MOCK_SPEED, ...opts });
}

/** 3. Pawse calls the clinic or the insurer. */
export function createPhoneCall(opts) {
  return IS_LIVE_PHONE ? createLivePhoneCall(opts) : createMockPhoneCall({ speed: MOCK_SPEED, ...opts });
}
