/** Frontend convenience types for API v0.2. OpenAPI is authoritative. */
export type Urgency = "emergency" | "contact_vet" | "unknown";
export type RedFlag =
  | "breathing_difficulty"
  | "collapse"
  | "seizure"
  | "unable_to_urinate"
  | "suspected_poisoning"
  | "major_trauma";
export interface Location {
  lat: number;
  lng: number;
}
export interface CareRequest {
  query?: string;
  cat_name?: string;
  location?: Location | null;
  radius_km?: number;
  language?: string;
  red_flags?: RedFlag[];
  photo?: {
    mime_type: "image/jpeg" | "image/png" | "image/webp";
    data: string;
  } | null;
  insurance?: { company: string; phone: string } | null;
  share_with_ai?: boolean;
  share_location?: boolean;
}
export interface Assessment {
  urgency: Urgency;
  summary: string;
  questions: string[];
  services_to_ask_about: string[];
  source: "reported_warning_signs" | "gemini" | "fallback";
  disclaimer: string;
}
export interface Clinic {
  id: string;
  name: string;
  address: string;
  phone: string | null;
  call_url: string | null;
  maps_url: string | null;
  website: string | null;
  location: Location | null;
  distance_km: number | null;
  rating: number | null;
  open_now: boolean | null;
  emergency_service: "unknown" | "provider_reported";
  services: string[];
  reasons: string[];
  source: "google_places" | "mapify";
  retrieved_at: string;
  availability_note: string;
}
export interface InsuranceContact {
  company: string;
  phone: string;
  call_url: string;
  source: "user_provided";
  coverage: "unconfirmed";
  questions: string[];
  note: string;
}
export interface CareResult {
  type: "result";
  request_id: string;
  status: "complete" | "partial";
  assessment: Assessment;
  clinics: Clinic[];
  insurance: InsuranceContact | null;
  handoff: string;
  warnings: string[];
  providers: Record<string, string>;
  elapsed_ms: number;
  target_seconds: number;
  search_url: string;
  completeness: string;
}
export type CareEvent =
  | { type: "created"; request_id: string }
  | { type: "safety" | "assessment"; assessment: Assessment }
  | { type: "insurance"; insurance: InsuranceContact | null }
  | { type: "clinics"; clinics: Clinic[] }
  | { type: "progress"; agent: "assessment" | "clinics"; status: string }
  | { type: "heartbeat" }
  | CareResult;
export type AnalysisType =
  | "daily_summary"
  | "weekly_report"
  | "monthly_report"
  | "health_prediction"
  | "trend_analysis"
  | "behavior_pattern"
  | "vet_recommendation"
  | "comparison"
  | "multi_cat_comparison"
  | "anomaly_detection";
export interface LegacyRequest {
  mode: "chat" | "analysis";
  cat_id: number;
  message?: string;
  analysis_type?: AnalysisType | null;
  time_range?: "24h" | "7d" | "30d";
}

/** API v0.2 voice and evidence additions. OpenAPI remains authoritative. */
export type InputLanguage = "en" | "zh" | "de" | "hi";
export interface WavAudio {
  data: string;
}
export interface TranscriptionRequest {
  audio: WavAudio;
  language?: InputLanguage;
  share_with_gemini: true;
}
export interface ScriptRequest {
  message: string;
  input_language?: InputLanguage;
  subtitle_language?: InputLanguage;
  target_language?: "de";
  recipient?: "vet" | "insurer" | "taxi";
  share_with_gemini: true;
}
export interface CallScript {
  lines: Array<{ german: string; subtitle: string }>;
  target_language: "de";
  status: "draft_not_sent";
}
export interface CloneRequest {
  audio: WavAudio;
  sample_language?: "en" | "de" | "fr" | "es" | "pt";
  own_voice_consent: true;
  share_with_gradium: true;
}
export interface SpeechRequest {
  text: string;
  language?: "de";
  voice?: "my_voice" | "standard";
  share_with_gradium: true;
  /** From the X-Pawse-Call-Id header of an earlier line in the same call; the server then skips the disclosure it already spoke. */
  call_id?: string | null;
}
export type AgentId =
  | "intake"
  | "care_guidance"
  | "nearby_vets"
  | "policy_evidence"
  | "ranking"
  | "communication"
  | "orchestrator";
export interface AgentRunResult {
  run_id: string;
  mode: "bounded_workflow";
  status: "complete" | "partial";
  care: CareResult;
  trace: Array<{
    agent_id: AgentId;
    state:
      | "pending"
      | "running"
      | "complete"
      | "unavailable"
      | "timeout"
      | "skipped"
      | "review_required"
      | "evidence_required";
    detail: string;
    elapsed_ms: number;
  }>;
  actions: Array<{
    id:
      | "german_script"
      | "insurance_coverage"
      | "outbound_call"
      | "appointment"
      | "calendar"
      | "taxi";
    state: "review_required" | "evidence_required" | "not_connected";
    required: string[];
    endpoint: string | null;
  }>;
  external_actions_performed: false;
  note: string;
}
export interface KnowledgeQuery {
  query: string;
  top_k?: number;
  scope?: "synthetic_demo";
}
export interface KnowledgeResult {
  scope: "synthetic_demo";
  synthetic: true;
  method: "lexical";
  insurance_approval: "not_obtained";
  corpus_version: string;
  status: "evidence_found" | "no_evidence";
  evidence: Array<{
    evidence_id: string;
    source_id: "pawse-demo-policy" | "pawse-demo-avb";
    source_path: string;
    source_sha256: string;
    section: string;
    title: string;
    snippet: string;
    synthetic: true;
    score: number;
  }>;
  disclaimer: string;
}
