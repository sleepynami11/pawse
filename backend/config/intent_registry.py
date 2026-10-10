# -*- coding: utf-8 -*-
"""
Intent Registry - 统一意图管理中心 (V3.3.9)
==========================================

单一数据源 (SSOT) 管理所有意图配置：
- 意图验证
- SKILL 加载配置
- 流程路由配置
- RAG 检索配置

新增意图只需在 INTENT_CATALOG 中添加一条记录。
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class IntentCategory(Enum):
    """意图分类"""
    EMERGENCY = "emergency"      # 紧急警报类
    HEALTH = "health"            # 健康诊断类
    ANALYSIS = "analysis"        # 数据分析类
    CARE = "care"                # 日常护理类
    IOT = "iot"                  # 设备查询类
    SIMPLE = "simple"            # 简单交互类


class FlowType(Enum):
    """流程类型"""
    RAG = "rag"                  # 需要 RAG 检索
    MEMORY = "memory"            # 需要 Memory 检索
    ANALYSIS = "analysis"        # 直接分析流程
    DIRECT = "direct"            # 直接响应
    ALERT = "alert"              # 警报流程
    DEVICE = "device"            # 设备数据流程


class Priority(Enum):
    """优先级"""
    CRITICAL = "critical"        # 紧急
    HIGH = "high"                # 高
    MEDIUM = "medium"            # 中
    LOW = "low"                  # 低


@dataclass
class IntentConfig:
    """意图配置"""
    name: str                                    # 意图名称
    category: IntentCategory                     # 分类
    flow_type: FlowType                          # 流程类型
    priority: Priority                           # 优先级

    # SKILL 配置
    skill_domains: List[str] = field(default_factory=list)  # SKILL 领域
    skill_level: int = 1                         # 加载级别 (0-3)

    # RAG 配置
    needs_rag: bool = False                      # 是否需要 RAG
    rag_collections: List[str] = field(default_factory=list)  # RAG 集合

    # 流程配置
    flow_node: Optional[str] = None              # 目标流程节点
    terminal_action: Optional[str] = None        # 终端 action（用于连接 ResponseGenerator）

    # 描述
    description_zh: str = ""                     # 中文描述
    description_en: str = ""                     # 英文描述


# =============================================================================
# 意图目录 (SSOT)
# =============================================================================

INTENT_CATALOG: Dict[str, IntentConfig] = {
    # =========================================================================
    # 紧急警报类
    # =========================================================================
    "emergency_alert": IntentConfig(
        name="emergency_alert",
        category=IntentCategory.EMERGENCY,
        flow_type=FlowType.ALERT,
        priority=Priority.CRITICAL,
        skill_domains=["emergency", "cat-health"],
        skill_level=2,
        needs_rag=False,
        flow_node="emergency_alert_node",
        terminal_action="alert_sent",
        description_zh="紧急健康警报",
        description_en="Emergency health alert"
    ),

    "device_offline": IntentConfig(
        name="device_offline",
        category=IntentCategory.EMERGENCY,
        flow_type=FlowType.ALERT,
        priority=Priority.HIGH,
        skill_domains=["iot-devices"],
        skill_level=1,
        needs_rag=False,
        flow_node="device_offline_alert_node",
        terminal_action="alert_sent",
        description_zh="设备离线警报",
        description_en="Device offline alert"
    ),

    # =========================================================================
    # 健康诊断类
    # =========================================================================
    "health_consultation": IntentConfig(
        name="health_consultation",
        category=IntentCategory.HEALTH,
        flow_type=FlowType.RAG,
        priority=Priority.HIGH,
        skill_domains=["cat-health", "emergency", "breed-info"],
        skill_level=3,
        needs_rag=True,
        rag_collections=["cat-medical-knowledge", "breed-info"],
        flow_node="medical_flow",
        terminal_action="high_confidence",
        description_zh="健康咨询（综合诊断）",
        description_en="Health consultation (comprehensive)"
    ),

    "medical_query": IntentConfig(
        name="medical_query",
        category=IntentCategory.HEALTH,
        flow_type=FlowType.RAG,
        priority=Priority.HIGH,
        skill_domains=["cat-health", "emergency"],
        skill_level=2,
        needs_rag=True,
        rag_collections=["cat-medical-knowledge"],
        flow_node="medical_flow",
        terminal_action="high_confidence",  # 或 low_confidence
        description_zh="医疗健康咨询",
        description_en="Medical health query"
    ),

    "comprehensive_diagnosis": IntentConfig(
        name="comprehensive_diagnosis",
        category=IntentCategory.HEALTH,
        flow_type=FlowType.RAG,
        priority=Priority.HIGH,
        skill_domains=["cat-health", "emergency", "breed-info"],
        skill_level=3,
        needs_rag=True,
        rag_collections=["cat-medical-knowledge", "breed-info"],
        flow_node="comprehensive_flow",
        terminal_action="summary_complete",
        description_zh="综合健康诊断",
        description_en="Comprehensive diagnosis"
    ),

    "vet_recommendation": IntentConfig(
        name="vet_recommendation",
        category=IntentCategory.HEALTH,
        flow_type=FlowType.RAG,
        priority=Priority.MEDIUM,
        skill_domains=["cat-health"],
        skill_level=2,
        needs_rag=True,
        rag_collections=["cat-medical-knowledge"],
        flow_node="vet_recommendation_flow",
        terminal_action="vet_recommendation_complete",
        description_zh="就医建议",
        description_en="Veterinary recommendation"
    ),

    # =========================================================================
    # 数据分析类
    # =========================================================================
    "status_query": IntentConfig(
        name="status_query",
        category=IntentCategory.ANALYSIS,
        flow_type=FlowType.MEMORY,
        priority=Priority.MEDIUM,
        skill_domains=["iot-devices", "cat-health"],
        skill_level=1,
        needs_rag=False,
        flow_node="status_flow",
        terminal_action="summary_complete",
        description_zh="状态查询（当前状态/今日汇总）",
        description_en="Status query (current or daily)"
    ),

    "daily_analysis": IntentConfig(
        name="daily_analysis",
        category=IntentCategory.ANALYSIS,
        flow_type=FlowType.ANALYSIS,
        priority=Priority.MEDIUM,
        skill_domains=["iot-devices", "cat-health"],
        skill_level=1,
        needs_rag=False,
        flow_node="daily_flow",
        terminal_action="health_summary_complete",
        description_zh="日常分析报告",
        description_en="Daily analysis report"
    ),

    "weekly_report": IntentConfig(
        name="weekly_report",
        category=IntentCategory.ANALYSIS,
        flow_type=FlowType.ANALYSIS,
        priority=Priority.LOW,
        skill_domains=["iot-devices", "cat-health"],
        skill_level=1,
        needs_rag=False,
        flow_node="weekly_report_flow",
        terminal_action="report_generated",
        description_zh="周报",
        description_en="Weekly report"
    ),

    "monthly_report": IntentConfig(
        name="monthly_report",
        category=IntentCategory.ANALYSIS,
        flow_type=FlowType.ANALYSIS,
        priority=Priority.LOW,
        skill_domains=["iot-devices", "cat-health"],
        skill_level=1,
        needs_rag=False,
        flow_node="monthly_report_flow",
        terminal_action="monthly_report_generated",
        description_zh="月报",
        description_en="Monthly report"
    ),

    "health_prediction": IntentConfig(
        name="health_prediction",
        category=IntentCategory.ANALYSIS,
        flow_type=FlowType.ANALYSIS,
        priority=Priority.MEDIUM,
        skill_domains=["cat-health", "iot-devices"],
        skill_level=2,
        needs_rag=False,
        flow_node="health_prediction_flow",
        terminal_action="health_prediction_complete",
        description_zh="健康预测",
        description_en="Health prediction"
    ),

    "behavior_pattern": IntentConfig(
        name="behavior_pattern",
        category=IntentCategory.ANALYSIS,
        flow_type=FlowType.ANALYSIS,
        priority=Priority.MEDIUM,
        skill_domains=["behavior", "iot-devices", "daily-care"],  # V3.3.10: Added behavior domain
        skill_level=2,  # V3.3.10: Increased for detailed behavior analysis
        needs_rag=False,
        flow_node="behavior_pattern_flow",
        terminal_action="behavior_pattern_complete",
        description_zh="行为模式分析",
        description_en="Behavior pattern analysis"
    ),

    "trend_analysis": IntentConfig(
        name="trend_analysis",
        category=IntentCategory.ANALYSIS,
        flow_type=FlowType.ANALYSIS,
        priority=Priority.MEDIUM,
        skill_domains=["iot-devices", "cat-health"],
        skill_level=2,
        needs_rag=False,
        flow_node="trend_analysis_flow",
        terminal_action="trend_analysis_complete",
        description_zh="趋势分析",
        description_en="Trend analysis"
    ),

    # =========================================================================
    # 日常护理类 (V3.3.2 新增)
    # =========================================================================
    "daily_care_advice": IntentConfig(
        name="daily_care_advice",
        category=IntentCategory.CARE,
        flow_type=FlowType.RAG,
        priority=Priority.MEDIUM,
        skill_domains=["daily-care", "cat-health", "nutrition"],
        skill_level=2,
        needs_rag=True,
        rag_collections=["daily-care", "l3_daily_care", "l4_user_friendly"],
        flow_node="status_flow",
        terminal_action="summary_complete",
        description_zh="日常护理与饮食建议",
        description_en="Daily care and nutrition advice"
    ),

    "care_advice": IntentConfig(
        name="care_advice",
        category=IntentCategory.CARE,
        flow_type=FlowType.RAG,
        priority=Priority.MEDIUM,
        skill_domains=["daily-care", "cat-health"],
        skill_level=1,
        needs_rag=True,
        rag_collections=["daily-care"],
        flow_node="status_flow",
        terminal_action="summary_complete",
        description_zh="日常养护建议",
        description_en="Daily care advice"
    ),

    "dietary_consultation": IntentConfig(
        name="dietary_consultation",
        category=IntentCategory.CARE,
        flow_type=FlowType.RAG,
        priority=Priority.LOW,
        skill_domains=["nutrition", "daily-care"],  # V3.3.10: Added nutrition domain
        skill_level=2,  # V3.3.10: Increased for detailed nutrition knowledge
        needs_rag=True,
        rag_collections=["daily-care", "l3_daily_care", "l4_user_friendly"],
        flow_node="status_flow",
        terminal_action="summary_complete",
        description_zh="饮食营养咨询",
        description_en="Dietary consultation"
    ),

    "behavior_training": IntentConfig(
        name="behavior_training",
        category=IntentCategory.CARE,
        flow_type=FlowType.RAG,
        priority=Priority.LOW,
        skill_domains=["behavior", "daily-care"],  # V3.3.10: Added behavior domain
        skill_level=2,  # V3.3.10: Increased for detailed behavior knowledge
        needs_rag=True,
        rag_collections=["daily-care", "l2_clinical", "l3_daily_care"],
        flow_node="status_flow",
        terminal_action="summary_complete",
        description_zh="行为训练指导",
        description_en="Behavior training"
    ),

    "prevention_care": IntentConfig(
        name="prevention_care",
        category=IntentCategory.CARE,
        flow_type=FlowType.RAG,
        priority=Priority.MEDIUM,
        skill_domains=["cat-health", "daily-care"],
        skill_level=1,
        needs_rag=True,
        rag_collections=["cat-medical-knowledge", "daily-care"],
        flow_node="status_flow",
        terminal_action="summary_complete",
        description_zh="预防保健",
        description_en="Prevention care"
    ),

    # =========================================================================
    # IoT 设备查询类
    # =========================================================================
    "status_summary": IntentConfig(
        name="status_summary",
        category=IntentCategory.IOT,
        flow_type=FlowType.MEMORY,
        priority=Priority.MEDIUM,
        skill_domains=["iot-devices"],
        skill_level=0,
        needs_rag=False,
        flow_node="status_flow",
        terminal_action="summary_complete",
        description_zh="状态总结",
        description_en="Status summary"
    ),

    "prey_query": IntentConfig(
        name="prey_query",
        category=IntentCategory.IOT,
        flow_type=FlowType.MEMORY,
        priority=Priority.HIGH,
        skill_domains=["emergency", "iot-devices"],
        skill_level=1,
        needs_rag=False,
        flow_node="status_flow",
        terminal_action="summary_complete",
        description_zh="叼东西查询",
        description_en="Prey detection query"
    ),

    "location_query": IntentConfig(
        name="location_query",
        category=IntentCategory.IOT,
        flow_type=FlowType.MEMORY,
        priority=Priority.MEDIUM,
        skill_domains=["iot-devices"],
        skill_level=0,
        needs_rag=False,
        flow_node="status_flow",
        terminal_action="summary_complete",
        description_zh="位置查询",
        description_en="Location query"
    ),

    # =========================================================================
    # 设备 Webhook 类 (V3.3.9 新增)
    # 用于接收设备主动推送的数据，并可供用户查询
    # =========================================================================
    "collar_ingestion": IntentConfig(
        name="collar_ingestion",
        category=IntentCategory.IOT,
        flow_type=FlowType.DEVICE,
        priority=Priority.MEDIUM,
        skill_domains=["iot-devices"],
        skill_level=1,
        needs_rag=False,
        flow_node="collar_ingestion_node",
        terminal_action="data_ingested",
        description_zh="项圈数据摄入",
        description_en="Collar data ingestion"
    ),

    "cat_door_event": IntentConfig(
        name="cat_door_event",
        category=IntentCategory.IOT,
        flow_type=FlowType.DEVICE,
        priority=Priority.HIGH,
        skill_domains=["iot-devices", "emergency"],
        skill_level=1,
        needs_rag=False,
        flow_node="cat_door_node",
        terminal_action="event_processed",
        description_zh="猫门事件处理",
        description_en="Cat door event processing"
    ),

    "pain_detection": IntentConfig(
        name="pain_detection",
        category=IntentCategory.EMERGENCY,
        flow_type=FlowType.ALERT,
        priority=Priority.CRITICAL,
        skill_domains=["emergency", "cat-health"],
        skill_level=2,
        needs_rag=True,
        rag_collections=["cat-medical-knowledge"],
        flow_node="pain_detection_node",
        terminal_action="alert_sent",
        description_zh="疼痛检测警报",
        description_en="Pain detection alert"
    ),

    # =========================================================================
    # 简单交互类 (V3.3.4 新增)
    # =========================================================================
    "direct_reply": IntentConfig(
        name="direct_reply",
        category=IntentCategory.SIMPLE,
        flow_type=FlowType.DIRECT,
        priority=Priority.LOW,
        skill_domains=[],
        skill_level=0,
        needs_rag=False,
        flow_node=None,  # 直接到 response_generator
        terminal_action=None,
        description_zh="直接回复",
        description_en="Direct reply"
    ),
}


# =============================================================================
# 便捷访问函数
# =============================================================================

def get_valid_actions() -> List[str]:
    """获取所有有效的 router action 列表"""
    return list(INTENT_CATALOG.keys())


def get_intent_config(action: str) -> Optional[IntentConfig]:
    """获取指定意图的配置"""
    return INTENT_CATALOG.get(action)


def get_skill_mapping(action: str) -> Dict[str, Any]:
    """获取指定意图的 SKILL 加载配置（兼容旧格式）"""
    config = INTENT_CATALOG.get(action)
    if not config:
        return {
            'domains': ['cat-health', 'daily-care'],
            'level': 1,
            'priority': 'low'
        }
    return {
        'domains': config.skill_domains,
        'level': config.skill_level,
        'priority': config.priority.value
    }


def get_all_skill_mappings() -> Dict[str, Dict[str, Any]]:
    """获取所有意图的 SKILL 映射（用于替换 INTENT_SKILL_MAP）"""
    return {name: get_skill_mapping(name) for name in INTENT_CATALOG}


def get_intents_by_category(category: IntentCategory) -> List[str]:
    """获取指定分类的所有意图"""
    return [name for name, config in INTENT_CATALOG.items() if config.category == category]


def get_intents_by_flow_type(flow_type: FlowType) -> List[str]:
    """获取指定流程类型的所有意图"""
    return [name for name, config in INTENT_CATALOG.items() if config.flow_type == flow_type]


def get_rag_intents() -> List[str]:
    """获取需要 RAG 的意图列表"""
    return [name for name, config in INTENT_CATALOG.items() if config.needs_rag]


def get_memory_intents() -> List[str]:
    """获取需要 Memory 检索的意图列表"""
    return get_intents_by_flow_type(FlowType.MEMORY)


def validate_action(action: str) -> bool:
    """验证 action 是否有效"""
    return action in INTENT_CATALOG


# =============================================================================
# 向后兼容导出
# =============================================================================

# 用于替换 config/prompts.py 中的 VALID_ROUTER_ACTIONS
VALID_ROUTER_ACTIONS = get_valid_actions()

# 用于替换 nodes.py 中的 INTENT_SKILL_MAP
INTENT_SKILL_MAP = get_all_skill_mappings()


# =============================================================================
# 验证白名单
# =============================================================================

# Valid SKILL domains (must exist in .skills/ directory)
VALID_SKILL_DOMAINS = [
    'cat-health',
    'emergency',
    'daily-care',
    'breed-info',
    'iot-devices',
    'behavior',      # V3.3.10: Cat behavior knowledge (training, psychology)
    'nutrition'      # V3.3.10: Cat nutrition knowledge (diet, feeding)
]

# Valid RAG collections (must exist in ChromaDB)
# Based on LAYER_COLLECTIONS in utils/chromadb_client.py
VALID_RAG_COLLECTIONS = [
    'cat-medical-knowledge',
    'daily-care',
    'breed-info',
    'l1_professional',
    'l2_clinical',
    'l3_daily_care',
    'l4_user_friendly'
]


# =============================================================================
# 验证
# =============================================================================

def validate_registry() -> List[str]:
    """验证注册表完整性，返回问题列表"""
    issues = []

    for name, config in INTENT_CATALOG.items():
        # 检查 SKILL 配置
        if config.skill_level > 0 and not config.skill_domains:
            issues.append(f"{name}: skill_level > 0 but no skill_domains")

        # 检查 RAG 配置
        if config.needs_rag and not config.rag_collections:
            issues.append(f"{name}: needs_rag=True but no rag_collections")

        # 检查流程配置
        # Note: FlowType.DIRECT is the only flow type that doesn't require flow_node
        if config.flow_type != FlowType.DIRECT and not config.flow_node:
            issues.append(f"{name}: non-direct flow but no flow_node")

        # 验证 SKILL domains 白名单
        for domain in config.skill_domains:
            if domain not in VALID_SKILL_DOMAINS:
                issues.append(f"{name}: invalid skill_domain '{domain}' (valid: {VALID_SKILL_DOMAINS})")

        # 验证 RAG collections 白名单
        for collection in config.rag_collections:
            if collection not in VALID_RAG_COLLECTIONS:
                issues.append(f"{name}: invalid rag_collection '{collection}' (valid: {VALID_RAG_COLLECTIONS})")

    return issues


def validate_registry_complete() -> Dict[str, List[str]]:
    """
    完整验证注册表，返回分类的问题列表

    Returns:
        Dict with categorized issues:
        - 'config_errors': SKILL/RAG configuration errors
        - 'whitelist_errors': Invalid domains/collections
        - 'flow_errors': Flow configuration errors
    """
    result = {
        'config_errors': [],
        'whitelist_errors': [],
        'flow_errors': []
    }

    for name, config in INTENT_CATALOG.items():
        # 检查 SKILL 配置
        if config.skill_level > 0 and not config.skill_domains:
            result['config_errors'].append(f"{name}: skill_level > 0 but no skill_domains")

        # 检查 RAG 配置
        if config.needs_rag and not config.rag_collections:
            result['config_errors'].append(f"{name}: needs_rag=True but no rag_collections")

        # 检查流程配置
        if config.flow_type != FlowType.DIRECT and not config.flow_node:
            result['flow_errors'].append(f"{name}: non-direct flow but no flow_node")

        # 验证 SKILL domains 白名单
        for domain in config.skill_domains:
            if domain not in VALID_SKILL_DOMAINS:
                result['whitelist_errors'].append(
                    f"{name}: invalid skill_domain '{domain}' (valid: {VALID_SKILL_DOMAINS})"
                )

        # 验证 RAG collections 白名单
        for collection in config.rag_collections:
            if collection not in VALID_RAG_COLLECTIONS:
                result['whitelist_errors'].append(
                    f"{name}: invalid rag_collection '{collection}' (valid: {VALID_RAG_COLLECTIONS})"
                )

    return result


def validate_flow_consistency(flow_actions: List[str]) -> Dict[str, List[str]]:
    """
    验证注册表与 Flow 路由的一致性 (V3.3.9)

    Args:
        flow_actions: flow.py 中 RouterNode 连接的 action 列表

    Returns:
        Dict with 'missing_in_registry' and 'missing_in_flow' lists
    """
    registry_actions = set(INTENT_CATALOG.keys())
    flow_action_set = set(flow_actions)

    return {
        'missing_in_registry': sorted(flow_action_set - registry_actions),
        'missing_in_flow': sorted(registry_actions - flow_action_set),
        'matched': sorted(registry_actions & flow_action_set)
    }


def get_flow_node_mapping() -> Dict[str, str]:
    """
    获取所有意图到流程节点的映射 (V3.3.9)

    Returns:
        Dict mapping intent name to flow_node
    """
    return {
        name: config.flow_node
        for name, config in INTENT_CATALOG.items()
        if config.flow_node
    }


if __name__ == "__main__":
    print("=" * 70)
    print("Intent Registry Validation Report")
    print("=" * 70)

    # 运行完整验证
    validation_result = validate_registry_complete()
    total_issues = sum(len(errors) for errors in validation_result.values())

    if total_issues == 0:
        print("\n✅ All validations passed!")
    else:
        print(f"\n⚠️  Found {total_issues} issue(s):\n")

        # 显示配置错误
        if validation_result['config_errors']:
            print(f"🔴 Configuration Errors ({len(validation_result['config_errors'])}):")
            for issue in validation_result['config_errors']:
                print(f"  - {issue}")
            print()

        # 显示白名单错误
        if validation_result['whitelist_errors']:
            print(f"🔴 Whitelist Errors ({len(validation_result['whitelist_errors'])}):")
            for issue in validation_result['whitelist_errors']:
                print(f"  - {issue}")
            print()

        # 显示流程错误
        if validation_result['flow_errors']:
            print(f"🔴 Flow Configuration Errors ({len(validation_result['flow_errors'])}):")
            for issue in validation_result['flow_errors']:
                print(f"  - {issue}")
            print()

    # 显示统计信息
    print("=" * 70)
    print("Registry Statistics")
    print("=" * 70)
    print(f"\nTotal intents: {len(INTENT_CATALOG)}")
    print(f"Categories: {[c.value for c in IntentCategory]}")
    print(f"Flow types: {[f.value for f in FlowType]}")

    print(f"\nIntents by category:")
    for cat in IntentCategory:
        intents = get_intents_by_category(cat)
        print(f"  {cat.value}: {len(intents)} - {intents}")

    # 显示白名单信息
    print("\n" + "=" * 70)
    print("Whitelist Configuration")
    print("=" * 70)
    print(f"\nValid SKILL domains ({len(VALID_SKILL_DOMAINS)}):")
    for domain in VALID_SKILL_DOMAINS:
        print(f"  - {domain}")

    print(f"\nValid RAG collections ({len(VALID_RAG_COLLECTIONS)}):")
    for collection in VALID_RAG_COLLECTIONS:
        print(f"  - {collection}")

    # V3.3.9: Flow consistency check
    print("\n" + "=" * 70)
    print("Flow Consistency Check")
    print("=" * 70)

    # These are the actions defined in flow.py router connections
    # Update this list when flow.py changes
    FLOW_ACTIONS = [
        # Emergency
        "emergency_alert", "device_offline",
        # Health
        "medical_query", "comprehensive_diagnosis", "vet_recommendation",
        # Analysis
        "daily_analysis", "weekly_report", "monthly_report",
        "health_prediction", "behavior_pattern", "trend_analysis",
        # Care
        "care_advice", "dietary_consultation", "behavior_training", "prevention_care",
        # IoT
        "status_summary", "prey_query", "location_query",
        # Device Webhook
        "collar_ingestion", "cat_door_event", "pain_detection",
        # Simple
        "direct_reply"
    ]

    consistency = validate_flow_consistency(FLOW_ACTIONS)
    if consistency['missing_in_registry']:
        print(f"\n⚠️  In flow.py but not in registry:")
        for action in consistency['missing_in_registry']:
            print(f"    - {action}")
    if consistency['missing_in_flow']:
        print(f"\n⚠️  In registry but not in flow.py:")
        for action in consistency['missing_in_flow']:
            print(f"    - {action}")
    if not consistency['missing_in_registry'] and not consistency['missing_in_flow']:
        print(f"\n✅ Registry and flow.py are fully consistent!")
        print(f"   Matched actions: {len(consistency['matched'])}")

    print("\n" + "=" * 70)
