"""
Mock 数据模块

为测试环境提供模拟数据，避免调用真实的 D1 数据库和 R2 存储服务。
通过 TEST_MODE 环境变量控制是否启用测试模式。

使用方式:
    # 设置环境变量启用测试模式
    export TEST_MODE=true

    # 或在代码中检查
    from utils.mock_data import is_test_mode, MockDataFactory

    if is_test_mode():
        data = MockDataFactory.cat_data()
"""

import os
import logging
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)


def is_test_mode() -> bool:
    """检查是否处于测试模式"""
    return os.getenv("TEST_MODE", "false").lower() == "true"


class MockDataFactory:
    """
    Mock 数据工厂类

    提供各种类型的模拟数据生成方法，所有数据格式与真实数据库 schema 一致。

    V3.3.9: 支持多样化 Mock 数据场景
    - HEALTHY_CAT: 健康猫咪数据（默认）
    - SICK_CAT: 生病猫咪数据（异常指标）
    - PAIN_CAT: 疼痛猫咪数据（高疼痛评分）
    - LOW_BATTERY: 设备低电量场景
    """

    # 数据场景模式
    _scenario: str = "HEALTHY_CAT"

    @classmethod
    def set_scenario(cls, scenario: str):
        """
        设置 Mock 数据场景

        Args:
            scenario: 场景名称
                - HEALTHY_CAT: 健康猫咪（默认）
                - SICK_CAT: 生病猫咪（异常生理指标）
                - PAIN_CAT: 疼痛猫咪（高疼痛评分 >= 6）
                - LOW_BATTERY: 设备低电量
        """
        valid_scenarios = ["HEALTHY_CAT", "SICK_CAT", "PAIN_CAT", "LOW_BATTERY"]
        if scenario not in valid_scenarios:
            raise ValueError(f"Invalid scenario: {scenario}. Valid: {valid_scenarios}")
        cls._scenario = scenario
        logger.info(f"[MockDataFactory] Scenario set to: {scenario}")

    @classmethod
    def reset_scenario(cls):
        """重置为默认场景"""
        cls._scenario = "HEALTHY_CAT"

    @classmethod
    def get_scenario(cls) -> str:
        """获取当前场景"""
        return cls._scenario

    # =========================================
    # 基础数据
    # =========================================

    @staticmethod
    def user_data(user_id: int = 1) -> list[dict]:
        """生成模拟用户数据"""
        return [
            {
                "id": user_id,
                "email": f"user{user_id}@example.com",
                "name": f"测试用户{user_id}",
                "timezone": "Asia/Shanghai",
                "language": "zh",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": datetime.now().isoformat()
            }
        ]

    @staticmethod
    def cat_data(user_id: int = 1, cat_id: int = None) -> list[dict]:
        """
        生成模拟猫咪数据

        Args:
            user_id: 用户ID
            cat_id: 如果指定，只返回该猫咪；否则返回所有猫咪

        Returns:
            list[dict]: 猫咪数据列表
        """
        cats = [
            {
                "id": 1,
                "user_id": user_id,
                "name": "咪咪",
                "breed": "橘猫",
                "age": 3,
                "weight": 5.2,
                "collar_device_id": 1,
                "collar_serial": "COLLAR-001",
                "collar_battery": 85,
                "medical_history_json": '{"vaccinations": ["狂犬病", "猫三联"], "allergies": [], "conditions": []}',
                "created_at": "2024-01-15T10:30:00Z"
            },
            {
                "id": 2,
                "user_id": user_id,
                "name": "小花",
                "breed": "狸花猫",
                "age": 2,
                "weight": 4.1,
                "collar_device_id": 2,
                "collar_serial": "COLLAR-002",
                "collar_battery": 92,
                "medical_history_json": '{"vaccinations": ["猫三联"], "allergies": ["鸡肉"], "conditions": []}',
                "created_at": "2024-03-20T14:00:00Z"
            },
            {
                "id": 3,
                "user_id": user_id,
                "name": "大黄",
                "breed": "英短",
                "age": 5,
                "weight": 6.8,
                "collar_device_id": 3,
                "collar_serial": "COLLAR-003",
                "collar_battery": 45,
                "medical_history_json": '{"vaccinations": ["狂犬病", "猫三联", "猫白血病"], "allergies": [], "conditions": ["轻微关节炎"]}',
                "created_at": "2023-06-10T09:00:00Z"
            }
        ]

        if cat_id is not None:
            return [cat for cat in cats if cat["id"] == cat_id]
        return cats

    @classmethod
    def collar_device_data(cls, cat_id: int = None) -> list[dict]:
        """
        生成模拟项圈设备数据

        场景差异:
            - LOW_BATTERY: 所有设备电量 < 15%
            - 其他场景: 正常电量
        """
        scenario = cls._scenario

        if scenario == "LOW_BATTERY":
            battery_levels = [8, 5, 12]  # 低电量
        else:
            battery_levels = [85, 92, 45]  # 正常电量

        devices = [
            {
                "id": 1,
                "device_serial": "COLLAR-001",
                "cat_id": 1,
                "battery_level": battery_levels[0],
                "firmware_version": "2.1.0",
                "last_sync": datetime.now().isoformat(),
                "created_at": "2024-01-15T10:30:00Z"
            },
            {
                "id": 2,
                "device_serial": "COLLAR-002",
                "cat_id": 2,
                "battery_level": battery_levels[1],
                "firmware_version": "2.1.0",
                "last_sync": datetime.now().isoformat(),
                "created_at": "2024-03-20T14:00:00Z"
            },
            {
                "id": 3,
                "device_serial": "COLLAR-003",
                "cat_id": 3,
                "battery_level": battery_levels[2],
                "firmware_version": "2.0.5",
                "last_sync": (datetime.now() - timedelta(hours=2)).isoformat(),
                "created_at": "2023-06-10T09:00:00Z"
            }
        ]

        if cat_id is not None:
            return [d for d in devices if d["cat_id"] == cat_id]
        return devices

    @classmethod
    def cat_door_device_data(cls, user_id: int = 1) -> list[dict]:
        """
        生成模拟猫门设备数据

        场景差异:
            - LOW_BATTERY: 所有设备电量 < 15%
            - 其他场景: 正常电量
        """
        scenario = cls._scenario

        if scenario == "LOW_BATTERY":
            battery_levels = [10, 7]  # 低电量
        else:
            battery_levels = [78, 95]  # 正常电量

        return [
            {
                "id": 1,
                "device_serial": "DOOR-001",
                "user_id": user_id,
                "location": "后院门",
                "firmware_version": "1.5.0",
                "battery_level": battery_levels[0],
                "last_sync": datetime.now().isoformat(),
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": 2,
                "device_serial": "DOOR-002",
                "user_id": user_id,
                "location": "阳台门",
                "firmware_version": "1.5.0",
                "battery_level": battery_levels[1],
                "last_sync": datetime.now().isoformat(),
                "created_at": "2024-02-15T00:00:00Z"
            }
        ]

    # =========================================
    # 健康数据
    # =========================================

    @classmethod
    def health_summary(cls, user_id: int = 1, cat_id: int = None, days: int = 7) -> list[dict]:
        """
        生成模拟健康摘要数据

        Args:
            user_id: 用户ID
            cat_id: 猫咪ID（可选）
            days: 统计天数

        Returns:
            list[dict]: 健康摘要数据

        场景差异:
            - HEALTHY_CAT: 正常指标
            - SICK_CAT: 异常心率、低活动量、高异常计数
            - PAIN_CAT: 高疼痛评分 (6-9)
            - LOW_BATTERY: 正常健康指标
        """
        cats = cls.cat_data(user_id, cat_id)
        summaries = []
        scenario = cls._scenario

        for cat in cats:
            if scenario == "SICK_CAT":
                # 生病猫咪：异常生理指标
                summary = {
                    "cat_id": cat["id"],
                    "cat_name": cat["name"],
                    "avg_heart_rate": round(random.uniform(200, 240), 1),  # 高心率
                    "avg_hrv": round(random.uniform(8, 15), 1),  # 低 HRV
                    "avg_respiratory_rate": round(random.uniform(45, 60), 1),  # 高呼吸
                    "bcg_anomaly_count": random.randint(8, 15),  # 多次异常
                    "total_steps": random.randint(500, 2000),  # 低活动
                    "total_active_minutes": random.randint(10, 40),  # 低活动时间
                    "avg_pain_score": round(random.uniform(3, 5), 1),  # 中等疼痛
                    "expression_count": random.randint(5, 15)
                }
            elif scenario == "PAIN_CAT":
                # 疼痛猫咪：高疼痛评分
                summary = {
                    "cat_id": cat["id"],
                    "cat_name": cat["name"],
                    "avg_heart_rate": round(random.uniform(150, 190), 1),
                    "avg_hrv": round(random.uniform(15, 25), 1),
                    "avg_respiratory_rate": round(random.uniform(30, 45), 1),
                    "bcg_anomaly_count": random.randint(2, 6),
                    "total_steps": random.randint(2000, 5000),
                    "total_active_minutes": random.randint(30, 80),
                    "avg_pain_score": round(random.uniform(6, 9), 1),  # 高疼痛 >= 6
                    "expression_count": random.randint(20, 40)
                }
            else:
                # HEALTHY_CAT / LOW_BATTERY: 正常指标
                summary = {
                    "cat_id": cat["id"],
                    "cat_name": cat["name"],
                    "avg_heart_rate": round(random.uniform(120, 180), 1),
                    "avg_hrv": round(random.uniform(20, 50), 1),
                    "avg_respiratory_rate": round(random.uniform(20, 40), 1),
                    "bcg_anomaly_count": random.randint(0, 3),
                    "total_steps": random.randint(5000, 15000),
                    "total_active_minutes": random.randint(60, 240),
                    "avg_pain_score": round(random.uniform(0, 3), 1),
                    "expression_count": random.randint(10, 50)
                }
            summaries.append(summary)

        return summaries

    @classmethod
    def bcg_logs(cls, cat_id: int = 1, limit: int = 100, anomaly_only: bool = False) -> list[dict]:
        """
        生成模拟 BCG（心率）日志数据

        Args:
            cat_id: 猫咪ID
            limit: 返回记录数量
            anomaly_only: 是否只返回异常记录

        Returns:
            list[dict]: BCG 日志数据

        场景差异:
            - HEALTHY_CAT: 10% 异常率，正常心率
            - SICK_CAT: 60% 异常率，高/低心率
            - PAIN_CAT: 30% 异常率，偏高心率
            - LOW_BATTERY: 同 HEALTHY_CAT
        """
        logs = []
        base_time = datetime.now()
        scenario = cls._scenario

        # 场景参数配置
        if scenario == "SICK_CAT":
            anomaly_rate = 0.6
            hr_normal = (180, 240)
            hr_anomaly = (40, 280)
            hrv_range = (5, 15)
            resp_range = (40, 65)
        elif scenario == "PAIN_CAT":
            anomaly_rate = 0.3
            hr_normal = (150, 200)
            hr_anomaly = (60, 230)
            hrv_range = (12, 25)
            resp_range = (30, 50)
        else:  # HEALTHY_CAT / LOW_BATTERY
            anomaly_rate = 0.1
            hr_normal = (100, 200)
            hr_anomaly = (50, 250)
            hrv_range = (15, 60)
            resp_range = (15, 45)

        for i in range(limit * 2):  # 生成更多以应对 anomaly_only
            is_anomaly = random.random() < anomaly_rate

            if anomaly_only and not is_anomaly:
                continue

            log = {
                "id": i + 1,
                "cat_id": cat_id,
                "collar_device_id": cat_id,
                "heart_rate_bpm": random.randint(*hr_normal) if not is_anomaly else random.randint(*hr_anomaly),
                "hrv_ms": round(random.uniform(*hrv_range), 1),
                "respiratory_rate": random.randint(*resp_range),
                "anomaly_flag": 1 if is_anomaly else 0,
                "anomaly_type": "heart_rate_high" if is_anomaly else None,
                "timestamp": (base_time - timedelta(minutes=i * 15)).isoformat()
            }
            logs.append(log)

            if len(logs) >= limit:
                break

        return logs

    @staticmethod
    def activity_logs(cat_id: int = 1, limit: int = 100) -> list[dict]:
        """
        生成模拟活动日志数据

        Args:
            cat_id: 猫咪ID
            limit: 返回记录数量

        Returns:
            list[dict]: 活动日志数据
        """
        activity_types = ["steps", "active_minutes", "sleep_minutes", "rest_minutes"]
        logs = []
        base_time = datetime.now()

        for i in range(limit):
            activity_type = random.choice(activity_types)
            value = {
                "steps": random.randint(50, 500),
                "active_minutes": random.randint(5, 30),
                "sleep_minutes": random.randint(30, 120),
                "rest_minutes": random.randint(10, 60)
            }.get(activity_type, 0)

            logs.append({
                "id": i + 1,
                "cat_id": cat_id,
                "collar_device_id": cat_id,
                "activity_type": activity_type,
                "value": value,
                "timestamp": (base_time - timedelta(hours=i)).isoformat()
            })

        return logs

    @staticmethod
    def outdoor_logs(cat_id: int = 1, limit: int = 50) -> list[dict]:
        """生成模拟户外日志数据"""
        logs = []
        base_time = datetime.now()

        for i in range(limit):
            is_outdoor = random.choice([0, 1])
            duration = random.randint(10, 180) if is_outdoor else 0

            logs.append({
                "id": i + 1,
                "cat_id": cat_id,
                "collar_device_id": cat_id,
                "is_outdoor": is_outdoor,
                "duration_minutes": duration,
                "started_at": (base_time - timedelta(hours=i * 4)).isoformat(),
                "ended_at": (base_time - timedelta(hours=i * 4) + timedelta(minutes=duration)).isoformat() if is_outdoor else None
            })

        return logs

    # =========================================
    # 猫门相关数据
    # =========================================

    @staticmethod
    def passage_logs(cat_id: int = None, limit: int = 50) -> list[dict]:
        """生成模拟猫门通过日志"""
        logs = []
        base_time = datetime.now()
        cat_ids = [1, 2, 3] if cat_id is None else [cat_id]
        cat_names = {1: "咪咪", 2: "小花", 3: "大黄"}

        for i in range(limit):
            cid = random.choice(cat_ids)
            direction = random.choice(["in", "out"])

            logs.append({
                "id": i + 1,
                "cat_id": cid,
                "cat_name": cat_names.get(cid, "未知"),
                "cat_door_device_id": 1,
                "door_location": "后院门",
                "direction": direction,
                "has_prey": random.random() < 0.05,  # 5% 概率携带猎物
                "image_url": f"https://mock-r2.example.com/passages/{i+1}.jpg",
                "timestamp": (base_time - timedelta(hours=i * 2)).isoformat()
            })

        return logs

    @classmethod
    def expression_logs(cls, cat_id: int = None, limit: int = 50, pain_threshold: float = None) -> list[dict]:
        """
        生成模拟表情分析日志

        场景差异:
            - HEALTHY_CAT: 疼痛评分 0-3，mood 以 happy/relaxed 为主
            - SICK_CAT: 疼痛评分 2-6，mood 以 anxious/alert 为主
            - PAIN_CAT: 疼痛评分 6-9，mood 以 anxious 为主，含疼痛指标
            - LOW_BATTERY: 同 HEALTHY_CAT
        """
        logs = []
        base_time = datetime.now()
        cat_ids = [1, 2, 3] if cat_id is None else [cat_id]
        cat_names = {1: "咪咪", 2: "小花", 3: "大黄"}
        scenario = cls._scenario

        # 场景参数配置
        if scenario == "PAIN_CAT":
            pain_range = (6.0, 9.0)  # 高疼痛评分
            moods = ["anxious", "anxious", "alert", "anxious"]  # 焦虑为主
            pain_indicators_choices = [
                ["眯眼", "耳朵后压", "胡须紧绷"],
                ["眯眼", "耳朵后压", "鼻子紧缩"],
                ["眯眼", "耳朵后压"],
                ["胡须紧绷", "鼻子紧缩", "眯眼"]
            ]
        elif scenario == "SICK_CAT":
            pain_range = (2.0, 6.0)  # 中等疼痛
            moods = ["anxious", "alert", "alert", "sleepy"]
            pain_indicators_choices = [
                ["眯眼"],
                ["耳朵后压"],
                [],
                ["眯眼", "耳朵后压"]
            ]
        else:  # HEALTHY_CAT / LOW_BATTERY
            pain_range = (0.0, 3.0)  # 低疼痛
            moods = ["happy", "relaxed", "happy", "sleepy", "alert"]
            pain_indicators_choices = [[], [], [], []]

        for i in range(limit * 2):
            cid = random.choice(cat_ids)
            pain_score = round(random.uniform(*pain_range), 1)

            if pain_threshold is not None and pain_score < pain_threshold:
                continue

            logs.append({
                "id": i + 1,
                "cat_id": cid,
                "cat_name": cat_names.get(cid, "未知"),
                "passage_log_id": i + 1,
                "mood": random.choice(moods),
                "mood_confidence": round(random.uniform(0.7, 0.99), 2),
                "pain_score": pain_score,
                "pain_indicators": random.choice(pain_indicators_choices) if pain_score > 5 else [],
                "image_url": f"https://mock-r2.example.com/expressions/{i+1}.jpg",
                "analysis_json": '{"details": "mock analysis"}',
                "timestamp": (base_time - timedelta(hours=i * 3)).isoformat()
            })

            if len(logs) >= limit:
                break

        return logs

    # =========================================
    # 告警和通知
    # =========================================

    @staticmethod
    def alert_logs(cat_id: int = None, limit: int = 50, unread_only: bool = False) -> list[dict]:
        """生成模拟告警日志"""
        alert_types = ["health_anomaly", "prey_detected", "long_absence", "low_battery", "unusual_activity"]
        severities = ["info", "warning", "critical"]
        logs = []
        base_time = datetime.now()
        cat_ids = [1, 2, 3] if cat_id is None else [cat_id]
        cat_names = {1: "咪咪", 2: "小花", 3: "大黄"}

        for i in range(limit):
            cid = random.choice(cat_ids)
            notification_sent = random.choice([0, 1])

            if unread_only and notification_sent:
                continue

            alert_type = random.choice(alert_types)
            severity = "critical" if alert_type == "health_anomaly" else random.choice(severities)

            logs.append({
                "id": i + 1,
                "cat_id": cid,
                "cat_name": cat_names.get(cid, "未知"),
                "alert_type": alert_type,
                "severity": severity,
                "title": f"{alert_type} 告警",
                "message": f"检测到 {cat_names.get(cid)} 的 {alert_type} 事件",
                "notification_sent": notification_sent,
                "timestamp": (base_time - timedelta(hours=i * 6)).isoformat()
            })

            if len(logs) >= limit:
                break

        return logs

    # =========================================
    # 会话数据
    # =========================================

    @staticmethod
    def conversation_sessions(user_id: int = 1, limit: int = 10) -> list[dict]:
        """生成模拟会话数据"""
        sessions = []
        base_time = datetime.now()

        for i in range(limit):
            sessions.append({
                "id": i + 1,
                "user_id": user_id,
                "session_id": f"session-{user_id}-{i+1}",
                "title": f"关于猫咪的对话 #{i+1}",
                "message_count": random.randint(2, 20),
                "last_message_preview": "这是最后一条消息的预览...",
                "created_at": (base_time - timedelta(days=i)).isoformat(),
                "updated_at": (base_time - timedelta(days=i, hours=random.randint(0, 12))).isoformat()
            })

        return sessions

    @staticmethod
    def vision_logs(cat_id: int = None, limit: int = 50) -> list[dict]:
        """生成模拟视觉分析日志"""
        logs = []
        base_time = datetime.now()
        cat_ids = [1, 2, 3] if cat_id is None else [cat_id]
        cat_names = {1: "咪咪", 2: "小花", 3: "大黄"}

        for i in range(limit):
            cid = random.choice(cat_ids)

            logs.append({
                "id": i + 1,
                "cat_id": cid,
                "cat_name": cat_names.get(cid, "未知"),
                "image_url": f"https://mock-r2.example.com/vision/{i+1}.jpg",
                "analysis_type": random.choice(["health_check", "behavior", "expression"]),
                "analysis_result": '{"summary": "猫咪状态良好", "details": {}}',
                "confidence": round(random.uniform(0.8, 0.99), 2),
                "timestamp": (base_time - timedelta(hours=i * 4)).isoformat()
            })

        return logs

    # =========================================
    # D1 响应包装
    # =========================================

    @staticmethod
    def db_response(results: list[dict], success: bool = True) -> dict:
        """
        将数据包装为 D1 API 响应格式

        D1 API 返回格式:
        {
            "success": true,
            "result": {                    # dict, not list!
                "results": [...],
                "success": true,
                "meta": {...}
            }
        }

        Args:
            results: 查询结果数据
            success: 是否成功

        Returns:
            dict: D1 API 格式的响应
        """
        return {
            "success": success,
            "result": {
                "results": results,
                "success": success,
                "meta": {
                    "duration": random.uniform(0.5, 5.0),
                    "changes": 0,
                    "last_row_id": len(results) if results else 0,
                    "served_by": "mock"
                }
            },
            "errors": [],
            "messages": []
        }

    # =========================================
    # 完整上下文
    # =========================================

    @staticmethod
    def full_user_context(user_id: int = 1) -> dict:
        """
        生成完整的用户上下文数据

        与 d1_client.get_user_full_context() 返回格式一致
        """
        cats = MockDataFactory.cat_data(user_id)

        return {
            "user": MockDataFactory.user_data(user_id)[0] if MockDataFactory.user_data(user_id) else None,
            "cats": cats,
            "devices": MockDataFactory.cat_door_device_data(user_id),
            "recent_alerts": MockDataFactory.alert_logs(limit=10),
            "health_summary": MockDataFactory.health_summary(user_id)
        }


# =========================================
# SQL 解析器（用于智能返回 mock 数据）
# =========================================

class MockQueryRouter:
    """
    根据 SQL 查询智能路由到对应的 mock 数据
    """

    @staticmethod
    def route_query(sql: str, params: list = None) -> dict:
        """
        根据 SQL 语句返回对应的 mock 数据

        Args:
            sql: SQL 查询语句
            params: 查询参数

        Returns:
            dict: D1 API 格式的响应
        """
        sql_lower = sql.lower()

        # 提取可能的 user_id 和 cat_id
        user_id = 1
        cat_id = None
        limit = 100

        if params:
            # 简单的参数解析
            for i, p in enumerate(params):
                if isinstance(p, int) and p > 0:
                    if "user_id" in sql_lower or "c.user_id" in sql_lower:
                        user_id = p
                    elif "cat_id" in sql_lower and cat_id is None:
                        cat_id = p

        # 根据表名路由
        if "cats" in sql_lower and "collar" not in sql_lower and "door" not in sql_lower:
            return MockDataFactory.db_response(MockDataFactory.cat_data(user_id, cat_id))

        elif "users" in sql_lower:
            return MockDataFactory.db_response(MockDataFactory.user_data(user_id))

        elif "collar_bcg_logs" in sql_lower:
            anomaly_only = "anomaly_flag = 1" in sql_lower
            return MockDataFactory.db_response(MockDataFactory.bcg_logs(cat_id or 1, limit, anomaly_only))

        elif "collar_activity_logs" in sql_lower:
            return MockDataFactory.db_response(MockDataFactory.activity_logs(cat_id or 1, limit))

        elif "collar_outdoor_logs" in sql_lower:
            return MockDataFactory.db_response(MockDataFactory.outdoor_logs(cat_id or 1, 50))

        elif "collar_devices" in sql_lower:
            return MockDataFactory.db_response(MockDataFactory.collar_device_data(cat_id))

        elif "cat_door_passage_logs" in sql_lower:
            return MockDataFactory.db_response(MockDataFactory.passage_logs(cat_id, 50))

        elif "cat_door_expression_logs" in sql_lower:
            pain_threshold = None
            if "pain_score >=" in sql_lower:
                # 尝试提取 pain_threshold
                import re
                match = re.search(r"pain_score >= (\d+\.?\d*)", sql_lower)
                if match:
                    pain_threshold = float(match.group(1))
            return MockDataFactory.db_response(MockDataFactory.expression_logs(cat_id, 50, pain_threshold))

        elif "cat_door_devices" in sql_lower:
            return MockDataFactory.db_response(MockDataFactory.cat_door_device_data(user_id))

        elif "alert_logs" in sql_lower:
            unread_only = "notification_sent = 0" in sql_lower
            return MockDataFactory.db_response(MockDataFactory.alert_logs(cat_id, 50, unread_only))

        elif "vision_logs" in sql_lower:
            return MockDataFactory.db_response(MockDataFactory.vision_logs(cat_id, 50))

        elif "conversation_sessions" in sql_lower:
            return MockDataFactory.db_response(MockDataFactory.conversation_sessions(user_id, 10))

        elif "select 1" in sql_lower:
            # 简单测试查询
            return MockDataFactory.db_response([{"test": 1}])

        # 健康摘要（复杂聚合查询）
        elif "avg(" in sql_lower or "sum(" in sql_lower:
            return MockDataFactory.db_response(MockDataFactory.health_summary(user_id, cat_id))

        # 默认返回空结果
        logger.warning(f"[MockQueryRouter] Unknown query pattern, returning empty result: {sql[:100]}...")
        return MockDataFactory.db_response([])


# =========================================
# R2 Mock 数据
# =========================================

class MockR2:
    """R2 存储的 mock 实现"""

    # 模拟的存储桶
    _storage: dict[str, dict[str, bytes]] = {}

    @classmethod
    def upload_file(cls, bucket: str, key: str, data: bytes) -> str:
        """模拟文件上传"""
        if bucket not in cls._storage:
            cls._storage[bucket] = {}
        cls._storage[bucket][key] = data

        # 返回模拟 URL
        mock_url = f"https://mock-r2.example.com/{bucket}/{key}"
        logger.info(f"[MockR2] File uploaded: {mock_url} ({len(data)} bytes)")
        return mock_url

    @classmethod
    def get_file(cls, bucket: str, key: str) -> bytes:
        """模拟文件下载"""
        if bucket in cls._storage and key in cls._storage[bucket]:
            data = cls._storage[bucket][key]
            logger.info(f"[MockR2] File downloaded: {bucket}/{key} ({len(data)} bytes)")
            return data

        # 返回模拟数据
        logger.info(f"[MockR2] File not in mock storage, returning placeholder: {bucket}/{key}")
        return b"mock file content"

    @classmethod
    def delete_file(cls, bucket: str, key: str) -> bool:
        """模拟文件删除"""
        if bucket in cls._storage and key in cls._storage[bucket]:
            del cls._storage[bucket][key]
            logger.info(f"[MockR2] File deleted: {bucket}/{key}")
        return True

    @classmethod
    def clear(cls):
        """清空所有模拟存储"""
        cls._storage = {}
        logger.info("[MockR2] Storage cleared")
