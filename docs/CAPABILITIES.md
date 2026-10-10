# Existing CatAgent capability inventory

This inventory synchronizes all 25 intent definitions and 14 registered device/AI tools found in the imported source. It does not certify that their dependencies are running. The new app exposes the full inventory and ten existing analysis types through `GET /api/v1/capabilities`.

## Intents

All intents enter through the existing chat router via `POST /api/v1/agent/requests` with `mode=chat`. Intent selection remains the legacy router's responsibility, not a promise that every prompt reaches a particular node.

| Intent | Purpose | Knowledge dependency declared |
| --- | --- | --- |
| `emergency_alert` | Emergency health alert | Other runtime dependencies may apply |
| `device_offline` | Device offline alert | Other runtime dependencies may apply |
| `health_consultation` | Health consultation (comprehensive) | RAG required |
| `medical_query` | Medical health query | RAG required |
| `comprehensive_diagnosis` | Comprehensive diagnosis | RAG required |
| `vet_recommendation` | Veterinary recommendation | RAG required |
| `status_query` | Status query (current or daily) | Other runtime dependencies may apply |
| `daily_analysis` | Daily analysis report | Other runtime dependencies may apply |
| `weekly_report` | Weekly report | Other runtime dependencies may apply |
| `monthly_report` | Monthly report | Other runtime dependencies may apply |
| `health_prediction` | Health prediction | Other runtime dependencies may apply |
| `behavior_pattern` | Behavior pattern analysis | Other runtime dependencies may apply |
| `trend_analysis` | Trend analysis | Other runtime dependencies may apply |
| `daily_care_advice` | Daily care and nutrition advice | RAG required |
| `care_advice` | Daily care advice | RAG required |
| `dietary_consultation` | Dietary consultation | RAG required |
| `behavior_training` | Behavior training | RAG required |
| `prevention_care` | Prevention care | RAG required |
| `status_summary` | Status summary | Other runtime dependencies may apply |
| `prey_query` | Prey detection query | Other runtime dependencies may apply |
| `location_query` | Location query | Other runtime dependencies may apply |
| `collar_ingestion` | Collar data ingestion | Other runtime dependencies may apply |
| `cat_door_event` | Cat door event processing | Other runtime dependencies may apply |
| `pain_detection` | Pain detection alert | RAG required |
| `direct_reply` | Direct reply | Other runtime dependencies may apply |

## Registered tools

These execute inside the existing chat flow. They are not exposed as unrestricted public function-execution endpoints.

| Tool | Module | Readiness |
| --- | --- | --- |
| `get_collar_activity` | `device_data_functions` | Legacy runtime and service configuration required |
| `get_collar_bcg` | `device_data_functions` | Legacy runtime and service configuration required |
| `get_collar_outdoor` | `device_data_functions` | Legacy runtime and service configuration required |
| `get_collar_temperature` | `device_data_functions` | Legacy runtime and service configuration required |
| `get_device_events` | `device_data_functions` | Legacy runtime and service configuration required |
| `get_cat_door_passages` | `device_data_functions` | Legacy runtime and service configuration required |
| `get_cat_expressions` | `device_data_functions` | Legacy runtime and service configuration required |
| `get_health_summary` | `device_data_functions` | Legacy runtime and service configuration required |
| `get_alerts` | `device_data_functions` | Legacy runtime and service configuration required |
| `get_user_cats` | `device_data_functions` | Legacy runtime and service configuration required |
| `get_full_context` | `device_data_functions` | Legacy runtime and service configuration required |
| `analyze_cat_image` | `ai_analysis_functions` | Legacy runtime and service configuration required |
| `analyze_cat_health` | `ai_analysis_functions` | Legacy runtime and service configuration required |
| `analyze_bcg_data` | `ai_analysis_functions` | Legacy runtime and service configuration required |

## Report and analysis routes

The new bridge accepts all ten values supported by `create_analyze_flow`: daily summary, weekly report, monthly report, health prediction, trend analysis, behavior pattern, vet recommendation, comparison, multi-cat comparison and anomaly detection. Their outputs are passed through as existing-agent results; they are not newly validated medical predictions.

## Not enabled automatically

- Book-derived RAG, skills and memory content remain excluded from this public repository.
- Cloudflare D1/R2/Vectorize, the device service, Chroma data and legacy model credentials are not supplied by the Gemini key.
- Legacy WebSocket push, device webhooks, direct tool execution and video ingestion remain in source but are not exposed through the new gateway.
- The legacy chat/report bridge is contract-tested; a running legacy backend has not been configured or verified here.

For the hackathon demo, use the new Gemini care-navigation flow first, then enable only legacy flows whose dependencies you have actually tested.
