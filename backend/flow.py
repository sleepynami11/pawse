from pocketflow import AsyncFlow
from nodes import (
    GetUserInputNode,
    AnswerAsyncNode,
    RouterNode,
    MedicalDiagnosisNode,
    VisionAnalysisNode,
    StatusSummaryNode,
    MultiCatHealthAnalysisNode,
    EmergencyAlertNode,
    DeviceOfflineAlertNode,
    ConversationMemoryNode,
    RAGRetrievalNode,
    CatDetectionNode,
    # New nodes for chat flow refactoring
    MemoryLoaderNode,
    MemoryRetrievalNode,
    MemorySaverNode,
    ResponseGeneratorNode,
    # Four-Layer RAG Architecture nodes
    CoreRulesNode,
    StructuredKnowledgeNode,
    # SKILL-based Progressive Loading nodes
    IntentAnalysisNode,
    SkillLoaderNode,
    IoTContextNode,
    ContextFusionNode,
    # Device nodes
    CollarDataIngestionNode,
    CatDoorEventNode,
    PainDetectionNode,
    OutdoorMonitorNode,
    CrossDeviceAnalysisNode,
    DailyAnalysisNode,
    WeeklyReportNode,
    MonthlyReportNode,
    HealthSummaryNode,
    HealthPredictionNode,
    BehaviorPatternNode,
    TrendAnalysisNode,
    VetRecommendationNode
)


def create_qa_flow_async():
    """Create and return an async question-answering flow."""
    # Create nodes
    get_input_node = GetUserInputNode()
    answer_node = AnswerAsyncNode()

    # Connect nodes in sequence
    get_input_node >> answer_node

    # Create async flow starting with input node
    return AsyncFlow(start=get_input_node)


def create_medical_flow():
    """Create medical diagnosis flow using RAG-based analysis."""
    medical_node = MedicalDiagnosisNode()
    return AsyncFlow(start=medical_node)


def create_vision_flow():
    """Create vision analysis flow for image-based health assessment."""
    vision_node = VisionAnalysisNode()
    return AsyncFlow(start=vision_node)


def create_status_flow():
    """Create status summary flow for health metrics aggregation."""
    status_node = StatusSummaryNode()
    return AsyncFlow(start=status_node)


def create_comprehensive_flow():
    """Create comprehensive diagnosis flow chaining medical, vision, and status nodes."""
    medical_node = MedicalDiagnosisNode()
    vision_node = VisionAnalysisNode()
    status_node = StatusSummaryNode()

    # Chain flows: medical -> vision -> status
    # MedicalDiagnosisNode returns 'high_confidence' or 'low_confidence'
    medical_node - 'high_confidence' >> vision_node
    medical_node - 'low_confidence' >> vision_node
    # VisionAnalysisNode returns 'analysis_complete' or 'pain_alert'
    vision_node - 'analysis_complete' >> status_node
    vision_node - 'pain_alert' >> status_node

    return AsyncFlow(start=medical_node)


def create_collar_flow():
    """
    Create collar device data ingestion flow.

    Handles collar webhook data:
    - activity_data: Steps, calories, active minutes
    - outdoor_status: GPS location, indoor/outdoor tracking
    - bcg_heart_rate: Heart rate, HRV, respiratory rate

    Routes to OutdoorMonitorNode for outdoor alerts if outdoor status detected.
    """
    collar_node = CollarDataIngestionNode()
    outdoor_monitor_node = OutdoorMonitorNode()
    emergency_alert_node = EmergencyAlertNode()

    # Route BCG anomalies to emergency alert
    collar_node - 'anomaly_alert' >> emergency_alert_node

    # Route outdoor status to outdoor monitor for extended/night alerts
    collar_node - 'outdoor_status' >> outdoor_monitor_node
    outdoor_monitor_node - 'extended_outdoor' >> emergency_alert_node
    outdoor_monitor_node - 'night_outdoor' >> emergency_alert_node
    outdoor_monitor_node - 'geofence_breach' >> emergency_alert_node

    return AsyncFlow(start=collar_node)


def create_cat_door_flow():
    """
    Create cat door event processing flow.

    Handles cat door passage events:
    - Passage logging (entry/exit)
    - Cat identification (RFID/vision/beacon)
    - Facial expression analysis (if image available)
    - Pain detection (Feline Grimace Scale)

    Flow chain: CatDoorEvent -> VisionAnalysis (if image) -> PainDetection
    """
    cat_door_node = CatDoorEventNode()
    vision_node = VisionAnalysisNode()
    pain_node = PainDetectionNode()
    emergency_alert_node = EmergencyAlertNode()

    # If image available, route to vision analysis
    cat_door_node - 'vision_analysis' >> vision_node

    # Vision analysis routes to pain detection on pain_alert
    vision_node - 'pain_alert' >> pain_node

    # Pain detection routes to emergency alert if pain detected
    pain_node - 'pain_alert' >> emergency_alert_node

    return AsyncFlow(start=cat_door_node)


def create_cross_device_flow():
    """
    Create cross-device correlation analysis flow.

    Correlates data from collar and cat door devices to detect:
    - Fatigue: door entry + activity drop
    - Injury: outdoor return + expression anomaly
    - Health alert: BCG anomaly + activity anomaly

    Routes to EmergencyAlertNode for high-confidence correlations.
    """
    cross_device_node = CrossDeviceAnalysisNode()
    emergency_alert_node = EmergencyAlertNode()

    # Route health alerts to emergency alert
    cross_device_node - 'health_alert' >> emergency_alert_node
    cross_device_node - 'injury_alert' >> emergency_alert_node
    cross_device_node - 'fatigue_concern' >> emergency_alert_node

    return AsyncFlow(start=cross_device_node)


def create_rag_flow():
    """Create RAG retrieval flow for knowledge search."""
    rag_node = RAGRetrievalNode()
    return AsyncFlow(start=rag_node)


def create_skill_context_flow():
    """
    Create SKILL-based progressive loading context flow.

    This flow implements the three-path parallel query architecture:
    1. IntentAnalysisNode: Analyzes intent and determines SKILL loading level
    2. SkillLoaderNode: Loads SKILL content based on domains and level
    3. IoTContextNode: Aggregates IoT device data
    4. ContextFusionNode: Fuses SKILL + RAG + IoT with priority allocation

    Architecture:
        IntentAnalysis
             │
             ├── SkillLoader (渐进式SKILL知识)
             ├── IoTContext (IoT设备数据)
             └── RAG (语义检索 - 在router_flow中)
             │
        ContextFusion (三路结果融合)

    Token allocation: IoT 30% | SKILL 50% | RAG 20%
    Priority: IoT realtime data > SKILL precise match > RAG semantic supplement
    """
    intent_node = IntentAnalysisNode()
    skill_loader_node = SkillLoaderNode()
    iot_context_node = IoTContextNode()
    context_fusion_node = ContextFusionNode()

    # Intent analysis determines SKILL loading parameters
    # Then loads SKILL and IoT context in sequence (parallel in production with AsyncParallelBatchNode)
    # Each node returns its specific action
    intent_node - 'intent_analyzed' >> skill_loader_node

    # SKILL loader -> IoT context -> Context fusion
    skill_loader_node - 'skill_loaded' >> iot_context_node

    # IoT context -> Context fusion
    iot_context_node - 'iot_context_ready' >> context_fusion_node

    return AsyncFlow(start=intent_node), context_fusion_node


def create_report_flow(report_type: str) -> AsyncFlow:
    """Create report flow based on report_type (daily/weekly/monthly)."""
    if report_type == 'daily_summary':
        daily_node = DailyAnalysisNode()
        health_node = HealthSummaryNode()
        # DailyAnalysisNode returns 'daily_analysis_complete'
        daily_node - 'daily_analysis_complete' >> health_node
        return AsyncFlow(start=daily_node)

    if report_type == 'weekly_report':
        weekly_node = WeeklyReportNode()
        return AsyncFlow(start=weekly_node)

    if report_type == 'monthly_report':
        monthly_node = MonthlyReportNode()
        return AsyncFlow(start=monthly_node)

    raise ValueError(f"Unsupported report_type: {report_type}")


def create_prediction_flow(prediction_type: str) -> AsyncFlow:
    """Create prediction/analysis flows for health or behavior insights."""
    if prediction_type == 'health_prediction':
        daily_node = DailyAnalysisNode()
        health_node = HealthSummaryNode()
        prediction_node = HealthPredictionNode()
        # DailyAnalysisNode -> 'daily_analysis_complete' -> HealthSummaryNode
        # HealthSummaryNode -> 'health_summary_complete' -> HealthPredictionNode
        daily_node - 'daily_analysis_complete' >> health_node
        health_node - 'health_summary_complete' >> prediction_node
        return AsyncFlow(start=daily_node)

    if prediction_type == 'trend_analysis':
        daily_node = DailyAnalysisNode()
        health_node = HealthSummaryNode()
        trend_node = TrendAnalysisNode()
        daily_node - 'daily_analysis_complete' >> health_node
        health_node - 'health_summary_complete' >> trend_node
        return AsyncFlow(start=daily_node)

    if prediction_type == 'behavior_pattern':
        daily_node = DailyAnalysisNode()
        status_node = StatusSummaryNode()
        behavior_node = BehaviorPatternNode()
        # DailyAnalysisNode -> 'daily_analysis_complete' -> StatusSummaryNode
        # StatusSummaryNode -> 'summary_complete' -> BehaviorPatternNode
        daily_node - 'daily_analysis_complete' >> status_node
        status_node - 'summary_complete' >> behavior_node
        return AsyncFlow(start=daily_node)

    if prediction_type == 'vet_recommendation':
        daily_node = DailyAnalysisNode()
        health_node = HealthSummaryNode()
        vet_node = VetRecommendationNode()
        daily_node - 'daily_analysis_complete' >> health_node
        health_node - 'health_summary_complete' >> vet_node
        return AsyncFlow(start=daily_node)

    raise ValueError(f"Unsupported prediction_type: {prediction_type}")


def create_router_flow_with_response():
    """
    Create router flow with action-based branching and response generation.

    This flow includes:
    1. RouterNode: Intent classification
    2. RAG (conditional): Only for knowledge-intensive intents
    3. Business nodes: Domain-specific processing
    4. ResponseGeneratorNode: Convert structured data to natural language

    Router actions map to specialized flows including:
    - Knowledge-intensive: medical_query, comprehensive_diagnosis, vet_recommendation (with RAG)
    - Analysis: daily_analysis, weekly_report, monthly_report, health_prediction, etc. (no RAG)
    - Alerts: emergency_alert, device_offline (direct response)
    """
    # Instantiate nodes
    router_node = RouterNode()
    rag_node = RAGRetrievalNode()
    memory_retrieval_node = MemoryRetrievalNode()
    response_generator = ResponseGeneratorNode()
    emergency_alert_node = EmergencyAlertNode()
    device_offline_alert_node = DeviceOfflineAlertNode()

    # Get specialized sub-flows for user queries
    medical_flow = create_medical_flow()
    status_flow = create_status_flow()
    comprehensive_flow = create_comprehensive_flow()
    daily_flow = create_report_flow('daily_summary')
    weekly_report_flow = create_report_flow('weekly_report')
    monthly_report_flow = create_report_flow('monthly_report')
    health_prediction_flow = create_prediction_flow('health_prediction')
    behavior_pattern_flow = create_prediction_flow('behavior_pattern')
    trend_analysis_flow = create_prediction_flow('trend_analysis')
    vet_recommendation_flow = create_prediction_flow('vet_recommendation')

    # Get specialized sub-flows for device webhooks
    collar_flow = create_collar_flow()
    cat_door_flow = create_cat_door_flow()

    # ===== Knowledge-intensive intents: Router -> RAG -> Business -> Response =====
    # medical_query: needs RAG for professional knowledge
    router_node - 'medical_query' >> rag_node
    rag_node - 'rag_medical' >> medical_flow
    # MedicalDiagnosisNode returns 'high_confidence' or 'low_confidence'
    medical_flow - 'high_confidence' >> response_generator
    medical_flow - 'low_confidence' >> response_generator

    # comprehensive_diagnosis: needs RAG -> comprehensive multi-node chain
    router_node - 'comprehensive_diagnosis' >> rag_node
    rag_node - 'rag_comprehensive' >> comprehensive_flow
    # comprehensive_flow terminal is StatusSummaryNode -> 'summary_complete'
    comprehensive_flow - 'summary_complete' >> response_generator

    # vet_recommendation: needs RAG -> vet recommendation flow
    router_node - 'vet_recommendation' >> rag_node
    rag_node - 'rag_vet' >> vet_recommendation_flow
    vet_recommendation_flow - 'vet_recommendation_complete' >> response_generator

    # ===== V3.3.2 新增 RAG 意图 =====
    # All V3.3.2 RAG intents follow pattern: Router -> RAG -> Status -> Response
    # care_advice: 日常养护建议 (需要RAG)
    router_node - 'care_advice' >> rag_node

    # dietary_consultation: 饮食营养咨询 (需要RAG)
    router_node - 'dietary_consultation' >> rag_node

    # behavior_training: 行为训练指导 (需要RAG)
    router_node - 'behavior_training' >> rag_node

    # prevention_care: 预防保健 (需要RAG)
    router_node - 'prevention_care' >> rag_node

    # Complete V3.3.2 RAG flows: RAG -> Status -> Response
    # V3.3.10: 明确指定 rag_retrieval_complete action 连接到 status_flow
    rag_node - 'rag_retrieval_complete' >> status_flow
    rag_node >> status_flow  # 保留默认连接作为fallback

    # ===== V3.3.2 新增数据库查询意图 - Memory branch for recency-based intents =====
    # All memory-based intents route to the same flow, only define connection once
    router_node - 'status_summary' >> memory_retrieval_node   # 状态总结
    router_node - 'prey_query' >> memory_retrieval_node       # 叼东西查询
    router_node - 'location_query' >> memory_retrieval_node   # 位置查询
    # Single connection from memory_retrieval to status_flow (避免重复连接警告)
    memory_retrieval_node - 'memory_retrieval_complete' >> status_flow

    # Connect status_flow to ResponseGenerator (for RAG and Memory branches)
    status_flow - 'summary_complete' >> response_generator

    # Connect Memory to ResponseGenerator (direct fallback)
    memory_retrieval_node >> response_generator

    # ===== Analysis intents: Router -> Business -> Response (no RAG) =====
    # status_summary now uses Memory branch above, no duplicate needed

    router_node - 'daily_analysis' >> daily_flow
    daily_flow - 'health_summary_complete' >> response_generator

    router_node - 'weekly_report' >> weekly_report_flow
    weekly_report_flow - 'report_generated' >> response_generator

    router_node - 'monthly_report' >> monthly_report_flow
    monthly_report_flow - 'monthly_report_generated' >> response_generator

    router_node - 'health_prediction' >> health_prediction_flow
    health_prediction_flow - 'health_prediction_complete' >> response_generator

    router_node - 'behavior_pattern' >> behavior_pattern_flow
    behavior_pattern_flow - 'behavior_pattern_complete' >> response_generator

    router_node - 'trend_analysis' >> trend_analysis_flow
    trend_analysis_flow - 'trend_analysis_complete' >> response_generator

    # ===== Alert intents: Router -> Alert -> Response =====
    router_node - 'emergency_alert' >> emergency_alert_node
    emergency_alert_node - 'alert_sent' >> response_generator

    router_node - 'device_offline' >> device_offline_alert_node
    device_offline_alert_node - 'alert_sent' >> response_generator

    # ===== Device webhook intents: Router -> Device Flow (no response generator) =====
    router_node - 'collar_ingestion' >> collar_flow
    router_node - 'cat_door_event' >> cat_door_flow
    router_node - 'pain_detection' >> cat_door_flow

    # ===== V3.3.4 Direct reply intent: Router -> Response (skip analysis) =====
    # For simple questions, greetings, and chitchat that don't need data analysis
    router_node - 'direct_reply' >> response_generator

    # ===== Default/chat intent: Router -> Response (simple chat) =====
    # Using only one default connection to avoid duplicate warnings
    router_node >> response_generator

    return AsyncFlow(start=router_node), response_generator


def create_router_flow():
    """
    Create router flow with action-based branching (legacy, without response generator).

    For backward compatibility with webhook flows that don't need response generation.
    """
    # Instantiate router and special case nodes
    router_node = RouterNode()
    emergency_alert_node = EmergencyAlertNode()
    device_offline_alert_node = DeviceOfflineAlertNode()

    # Get specialized sub-flows for user queries
    medical_flow = create_medical_flow()
    status_flow = create_status_flow()
    comprehensive_flow = create_comprehensive_flow()
    daily_flow = create_report_flow('daily_summary')
    weekly_report_flow = create_report_flow('weekly_report')
    monthly_report_flow = create_report_flow('monthly_report')
    health_prediction_flow = create_prediction_flow('health_prediction')
    behavior_pattern_flow = create_prediction_flow('behavior_pattern')
    trend_analysis_flow = create_prediction_flow('trend_analysis')
    vet_recommendation_flow = create_prediction_flow('vet_recommendation')

    # Get specialized sub-flows for device webhooks
    collar_flow = create_collar_flow()
    cat_door_flow = create_cat_door_flow()

    # Connect router to nodes/flows using action-based branching
    router_node - 'emergency_alert' >> emergency_alert_node
    router_node - 'device_offline' >> device_offline_alert_node
    router_node - 'medical_query' >> medical_flow
    router_node - 'status_summary' >> status_flow
    router_node - 'comprehensive_diagnosis' >> comprehensive_flow
    router_node - 'daily_analysis' >> daily_flow
    router_node - 'weekly_report' >> weekly_report_flow
    router_node - 'monthly_report' >> monthly_report_flow
    router_node - 'health_prediction' >> health_prediction_flow
    router_node - 'behavior_pattern' >> behavior_pattern_flow
    router_node - 'trend_analysis' >> trend_analysis_flow
    router_node - 'vet_recommendation' >> vet_recommendation_flow

    # Device webhook actions
    router_node - 'collar_ingestion' >> collar_flow
    router_node - 'cat_door_event' >> cat_door_flow
    router_node - 'pain_detection' >> cat_door_flow

    return AsyncFlow(start=router_node)


def create_chat_flow():
    """
    Create chat flow with SKILL-based Progressive Loading Architecture.

    SKILL-based Architecture (upgraded from Four-Layer RAG):
    - SKILL System: Progressive loading knowledge packages (2K/5K/10K/40K tokens)
    - Three-path Parallel Query: SKILL + RAG + IoT data
    - Token Budget Management: Intent-driven dynamic allocation
    - IoT-first Priority: IoT 30% | SKILL 50% | RAG 20%

    Legacy Layers (maintained for compatibility):
    - Layer 1 (CoreRulesNode): 100% loaded every conversation - system rules
    - Layer 2 (StructuredKnowledgeNode): Precise keyword matching
    - Layer 3 (RAGRetrievalNode): Semantic vector search (now part of fusion)

    Flow structure:
    1. GetUserInputNode: Reads user request from HTTP context
    2. CoreRulesNode: Load core rules (Layer 1 - always loaded)
    3. MemoryLoaderNode: Load conversation history and resolve pronouns
    4. StructuredKnowledgeNode: Keyword matching (Layer 2)
    5. CatDetectionNode: First-stage detection for images/videos
    6. VisionAnalysisNode: Health/pain analysis (if cat detected)
    7. RouterNode: Intent classification
    8. IntentAnalysisNode: Determine SKILL domains and loading level
    9. SkillLoaderNode: Load progressive SKILL content
    10. IoTContextNode: Aggregate IoT device data
    11. ContextFusionNode: Fuse SKILL + RAG + IoT contexts
    12. Business Nodes: Domain-specific processing
    13. ResponseGeneratorNode: Generate natural language response
    14. MemorySaverNode: Save conversation with assistant response

    Key architecture improvements:
    - Progressive SKILL loading reduces token usage for simple queries
    - IoT data has highest priority (30% token allocation)
    - Intent-driven context selection improves relevance
    - Three-path parallel architecture enables comprehensive answers
    - Transport-agnostic: accepts progress_callback for live status streaming

    SSE/WebSocket progress tracking:
    The flow supports both SSE (POST /chat + GET /chat/stream/{stream_id}) and
    WebSocket (/ws/chat) transports through a unified progress_callback mechanism.

    Progress-enabled nodes (8 total):
    - CatDetectionNode: Image/video cat detection status
    - VisionAnalysisNode: Health and pain analysis progress
    - IntentAnalysisNode: User intent understanding status
    - SkillLoaderNode: Knowledge loading progress
    - IoTContextNode: Device data aggregation status
    - ContextFusionNode: Context merging progress
    - RouterNode: Intent routing status
    - ResponseGeneratorNode: LLM response generation with token streaming

    SSE Message Format (transformed by api.py):
    All nodes emit messages via progress_callback(msg: dict) with this format:
    - Progress events: {type: 'progress', node: str, status: str, message: str}
    - Streaming tokens: {type: 'streaming', node: str, token: str}
    - Final answer: {type: 'final_answer', response: str, cat_id: int, session_id: str, ...}
    - Errors: {type: 'error', message: str, code: int}

    The api.py layer transforms these dict messages into SSE format:
    'event: {type}\\ndata: {json}\\n\\n'

    progress_callback is read from shared['progress_callback'] in prep_async() and
    invoked during exec_async() to stream updates to connected clients.
    """
    # Instantiate nodes
    input_node = GetUserInputNode()
    core_rules_node = CoreRulesNode()          # Layer 1: Core Rules
    memory_loader = MemoryLoaderNode()
    structured_knowledge_node = StructuredKnowledgeNode()  # Layer 2: Structured Knowledge
    cat_detection_node = CatDetectionNode()
    vision_node = VisionAnalysisNode()
    memory_saver = MemorySaverNode()

    # SKILL-based Progressive Loading nodes
    intent_analysis_node = IntentAnalysisNode()
    skill_loader_node = SkillLoaderNode()
    iot_context_node = IoTContextNode()
    context_fusion_node = ContextFusionNode()

    # Get router flow with response generator (includes Layer 3 RAG)
    router_flow, response_generator = create_router_flow_with_response()

    # ===== Stage 1: Input and Core Rules Loading (Layer 1) =====
    # input -> core_rules (Layer 1 - 100% loaded)
    input_node >> core_rules_node
    # CoreRulesLoaderNode returns 'core_rules_loaded'
    core_rules_node - 'core_rules_loaded' >> memory_loader

    # ===== Stage 2: Memory Loading =====
    # MemoryLoaderNode returns 'memory_loaded'
    memory_loader - 'memory_loaded' >> structured_knowledge_node

    # ===== Stage 3: Structured Knowledge Matching (Layer 2) =====
    # StructuredKnowledgeLoaderNode returns 'structured_knowledge_loaded'
    structured_knowledge_node - 'structured_knowledge_loaded' >> cat_detection_node

    # ===== Stage 4: Media Detection and Vision Analysis =====
    # cat_detected -> vision analysis -> intent_analysis (SKILL path)
    cat_detection_node - 'cat_detected' >> vision_node
    # vision_node uses default action for main path
    vision_node >> intent_analysis_node
    # pain_alert goes to intent_analysis for further processing
    vision_node - 'pain_alert' >> intent_analysis_node

    # no_cat -> skip vision, go to intent_analysis
    cat_detection_node - 'no_cat' >> intent_analysis_node

    # no_media -> skip detection and vision, go to intent_analysis
    cat_detection_node - 'no_media' >> intent_analysis_node

    # V3.3.8: cat_door_analyzed -> 猫门图片分析完成，直接到 response generator
    cat_detection_node - 'cat_door_analyzed' >> response_generator

    # ===== Stage 5: SKILL-based Context Building =====
    # Intent analysis -> SKILL loader -> IoT context -> Context fusion
    # Each node returns its specific action
    intent_analysis_node - 'intent_analyzed' >> skill_loader_node
    skill_loader_node - 'skill_loaded' >> iot_context_node
    iot_context_node - 'iot_context_ready' >> context_fusion_node

    # ===== Stage 6: Context Fusion -> Router =====
    # Context fusion enriches shared context, then proceeds to router
    context_fusion_node - 'context_fused' >> router_flow

    # ===== Stage 7: Response Generation -> Memory Saving =====
    # ResponseGenerator is connected inside router_flow_with_response
    # Now receives fused context (SKILL + RAG + IoT)
    response_generator - 'response_generated' >> memory_saver

    return AsyncFlow(start=input_node)


def create_master_flow():
    """
    Create master orchestration flow with SKILL-based Progressive Loading Architecture.

    Architecture Overview:
    - SKILL System: Progressive loading knowledge packages (2K/5K/10K/40K tokens)
    - Three-Path Parallel Query: SKILL + RAG + IoT data simultaneous retrieval
    - Context Fusion: Priority-based allocation (IoT 30% | SKILL 50% | RAG 20%)

    SKILL Domains:
    - cat-health: Health knowledge (symptoms, diagnosis, treatment)
    - emergency: Emergency protocols and toxic substances
    - daily-care: Daily care and feeding guidelines
    - breed-info: Breed-specific information
    - iot-devices: IoT device data interpretation (collar, cat door)

    Progressive Loading Levels:
    - Level 0 (~2K tokens): Quick overview, status checks
    - Level 1 (~5K tokens): Module-specific knowledge
    - Level 2 (~10K tokens): Detailed analysis guides
    - Level 3 (~40K tokens): Complete in-depth knowledge

    Flow Structure:
    1. GetUserInputNode: Reads user request from HTTP/WebSocket context
    2. CoreRulesNode: Load core rules (system rules, emergency protocols)
    3. MemoryLoaderNode: Load conversation history and resolve pronouns
    4. StructuredKnowledgeNode: Keyword matching (symptoms, medications)
    5. CatDetectionNode: First-stage detection for images/videos
    6. VisionAnalysisNode: Health/pain analysis (if cat detected)
    7. IntentAnalysisNode: Analyze intent → determine SKILL level & domains
    8. SkillLoaderNode: Load SKILL content based on intent analysis
    9. IoTContextNode: Aggregate real-time IoT device data
    10. ContextFusionNode: Fuse SKILL + RAG + IoT with priority allocation
    11. RouterNode: Intent classification and routing
    12. Business Nodes: Domain-specific processing (RAG, IoT, etc.)
    13. ResponseGeneratorNode: Convert structured data to natural language
    14. MemorySaverNode: Save conversation with assistant response

    Transport Architecture (V3.5 SSE+WebSocket Hybrid):
    - SSE: POST /chat + GET /chat/stream/{stream_id} for chat streaming
    - WebSocket /ws/push/{user_id}: Dedicated IoT push notification channel
    - WebSocket /ws/chat: Legacy endpoint (deprecated, maintained for compatibility)

    Progress Callback Mechanism:
    - progress_callback is injected into shared context by api.py
    - Signature: async def progress_callback(msg: dict)
    - Transport-agnostic: same callback works for both SSE and WebSocket
    - 8 nodes emit progress updates (see create_chat_flow docstring for details)
    """
    return create_chat_flow()


def create_multi_cat_flow():
    """Create multi-cat batch flow for parallel health analysis."""
    batch_node = MultiCatHealthAnalysisNode()
    return AsyncFlow(start=batch_node)


def create_analyze_flow(analysis_type: str) -> AsyncFlow:
    """Factory for analysis flows based on analysis_type."""
    if analysis_type in {'daily_summary', 'weekly_report', 'monthly_report'}:
        return create_report_flow(analysis_type)

    if analysis_type in {'health_prediction', 'trend_analysis', 'behavior_pattern', 'vet_recommendation'}:
        return create_prediction_flow(analysis_type)

    if analysis_type == 'comparison':
        daily_node = DailyAnalysisNode()
        health_node = HealthSummaryNode()
        daily_node >> health_node
        return AsyncFlow(start=daily_node)

    if analysis_type == 'multi_cat_comparison':
        multi_cat_node = MultiCatHealthAnalysisNode()
        return AsyncFlow(start=multi_cat_node)

    if analysis_type == 'anomaly_detection':
        anomaly_node = DailyAnalysisNode()
        return AsyncFlow(start=anomaly_node)

    raise ValueError(f"Unsupported analysis_type: {analysis_type}")


# Export master flow for use in main.py
master_flow = create_master_flow()
