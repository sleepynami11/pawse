/** Frontend convenience types for API v0.1. OpenAPI is authoritative. */
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
