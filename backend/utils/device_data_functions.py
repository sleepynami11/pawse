"""
Device Data Functions for LLM Tool Calling

This module provides function definitions and execution for LLM tool calling.
Instead of external webhook endpoints, the system fetches device data internally
via database queries when the LLM determines data is needed.

Usage:
    from utils.device_data_functions import DEVICE_DATA_FUNCTIONS, execute_device_function

    # Get function definitions for LLM
    functions = DEVICE_DATA_FUNCTIONS

    # Execute a function call from LLM
    result = await execute_device_function("get_collar_activity", {
        "user_id": 1,
        "cat_id": 2,
        "device_mac": "AABBCCDDEEFF",  # V3.4: Device MAC for time-series queries
        "limit": 50
    })

Architecture Note (V3.2):
    - Replaces webhook-based data ingestion
    - Data is fetched on-demand when LLM requests it
    - All queries are user-scoped for security

Architecture Note (V3.4):
    - Time-series data (BCG, GPS, IMU, temp, events, detections) via device_service_client
    - Metadata (users, cats, health summary) via d1_client
    - Requires device_mac parameter for time-series queries
"""

import logging
from typing import Any, Optional
from datetime import datetime, timedelta

# D1 client for metadata queries (users, cats, devices, health summaries)
from utils.d1_client import (
    get_user_cats,
    get_user_cat_health_summary,
    get_user_cat_activity_logs,
    get_user_cat_bcg_logs,
    get_user_cat_outdoor_logs,
    get_user_cat_door_passages,
    get_user_cat_expression_logs,
    get_user_alerts,
    get_user_full_context
)

# Device service client for time-series data (BCG, GPS, IMU, temp, events, detections)
from utils.device_service_client import (
    get_bcg_data,
    get_gps_data,
    get_imu_data,
    get_temp_data,
    get_device_events,
    get_door_detections
)

logger = logging.getLogger(__name__)


# ============================================================================
# Function Definitions for LLM Tool Calling
# ============================================================================

DEVICE_DATA_FUNCTIONS = [
    # ============================================================================
    # Time-series data functions (V3.4: via device_service_client, requires device_mac)
    # ============================================================================
    {
        "name": "get_collar_activity",
        "description": "获取猫咪项圈的IMU活动数据（Mode1模式），包括加速度计检测的活动状态、运动强度、静止/活跃时间等。用于了解猫咪的日常活动水平和运动量。需要提供设备MAC地址。",
        "parameters": {
            "type": "object",
            "properties": {
                "device_mac": {
                    "type": "string",
                    "description": "设备MAC地址（必需，用于查询时序数据）"
                },
                "user_id": {
                    "type": "integer",
                    "description": "用户ID（可选，用于数据访问控制）"
                },
                "cat_id": {
                    "type": "integer",
                    "description": "猫咪ID（可选）"
                },
                "hours": {
                    "type": "integer",
                    "description": "查询最近多少小时的数据，默认24小时",
                    "default": 24
                },
                "limit": {
                    "type": "integer",
                    "description": "返回记录数量，默认100条",
                    "default": 100
                }
            },
            "required": ["device_mac"]
        }
    },
    {
        "name": "get_collar_bcg",
        "description": "获取猫咪项圈的BCG生理数据，包括心率(BPM)、心率变异性(HRV)、呼吸率等。用于监测猫咪的心脏健康和呼吸状况。需要提供设备MAC地址。",
        "parameters": {
            "type": "object",
            "properties": {
                "device_mac": {
                    "type": "string",
                    "description": "设备MAC地址（必需，用于查询时序数据）"
                },
                "user_id": {
                    "type": "integer",
                    "description": "用户ID（可选）"
                },
                "cat_id": {
                    "type": "integer",
                    "description": "猫咪ID（可选）"
                },
                "hours": {
                    "type": "integer",
                    "description": "查询最近多少小时的数据，默认24小时",
                    "default": 24
                },
                "limit": {
                    "type": "integer",
                    "description": "返回记录数量，默认100条",
                    "default": 100
                }
            },
            "required": ["device_mac"]
        }
    },
    {
        "name": "get_collar_outdoor",
        "description": "获取猫咪离家后的GPS定位记录，包括GPS位置、外出时间、离家距离等。用于追踪猫咪的户外行为模式和位置安全。需要提供设备MAC地址。",
        "parameters": {
            "type": "object",
            "properties": {
                "device_mac": {
                    "type": "string",
                    "description": "设备MAC地址（必需，用于查询时序数据）"
                },
                "user_id": {
                    "type": "integer",
                    "description": "用户ID（可选）"
                },
                "cat_id": {
                    "type": "integer",
                    "description": "猫咪ID（可选）"
                },
                "hours": {
                    "type": "integer",
                    "description": "查询最近多少小时的数据，默认24小时",
                    "default": 24
                },
                "limit": {
                    "type": "integer",
                    "description": "返回记录数量，默认50条",
                    "default": 50
                }
            },
            "required": ["device_mac"]
        }
    },
    {
        "name": "get_collar_temperature",
        "description": "获取猫咪项圈的温度数据，包括环境温度和体表温度。用于监测猫咪的体温变化。需要提供设备MAC地址。",
        "parameters": {
            "type": "object",
            "properties": {
                "device_mac": {
                    "type": "string",
                    "description": "设备MAC地址（必需，用于查询时序数据）"
                },
                "hours": {
                    "type": "integer",
                    "description": "查询最近多少小时的数据，默认24小时",
                    "default": 24
                },
                "limit": {
                    "type": "integer",
                    "description": "返回记录数量，默认100条",
                    "default": 100
                }
            },
            "required": ["device_mac"]
        }
    },
    {
        "name": "get_device_events",
        "description": "获取设备事件记录，包括开机/关机、连接状态变化、固件更新等系统事件。需要提供设备MAC地址。",
        "parameters": {
            "type": "object",
            "properties": {
                "device_mac": {
                    "type": "string",
                    "description": "设备MAC地址（必需，用于查询时序数据）"
                },
                "hours": {
                    "type": "integer",
                    "description": "查询最近多少小时的数据，默认24小时",
                    "default": 24
                },
                "limit": {
                    "type": "integer",
                    "description": "返回记录数量，默认100条",
                    "default": 100
                }
            },
            "required": ["device_mac"]
        }
    },
    {
        "name": "get_cat_door_passages",
        "description": "获取猫门进出记录，包括进出方向、时间、AI检测结果、是否叼有猎物等。用于了解猫咪的进出频率和时间模式。需要提供设备MAC地址。",
        "parameters": {
            "type": "object",
            "properties": {
                "device_mac": {
                    "type": "string",
                    "description": "设备MAC地址（必需，用于查询时序数据）"
                },
                "user_id": {
                    "type": "integer",
                    "description": "用户ID（可选，用于备用D1查询）"
                },
                "cat_id": {
                    "type": "integer",
                    "description": "猫咪ID（可选，用于备用D1查询）"
                },
                "hours": {
                    "type": "integer",
                    "description": "查询最近多少小时的数据，默认24小时",
                    "default": 24
                },
                "limit": {
                    "type": "integer",
                    "description": "返回记录数量，默认50条",
                    "default": 50
                }
            },
            "required": ["device_mac"]
        }
    },
    # ============================================================================
    # Metadata functions (via d1_client, user-scoped queries)
    # ============================================================================
    {
        "name": "get_cat_expressions",
        "description": "获取猫咪表情分析记录，包括疼痛评分(0-10)、情绪状态、面部特征分析等。用于评估猫咪的舒适度和疼痛水平。",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "用户ID（必需）"
                },
                "cat_id": {
                    "type": "integer",
                    "description": "猫咪ID（可选）"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回记录数量，默认50条",
                    "default": 50
                },
                "pain_threshold": {
                    "type": "number",
                    "description": "疼痛评分阈值，只返回高于此分数的记录"
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "get_health_summary",
        "description": "获取猫咪健康摘要，聚合指定天数内的心率、活动、表情等数据。用于生成健康报告或趋势分析。",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "用户ID（必需）"
                },
                "cat_id": {
                    "type": "integer",
                    "description": "猫咪ID（可选，不指定则返回用户所有猫咪的摘要）"
                },
                "days": {
                    "type": "integer",
                    "description": "统计天数，默认7天",
                    "default": 7
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "get_alerts",
        "description": "获取猫咪的警报记录，包括健康异常、设备告警等。用于查看历史告警和未处理的提醒。",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "用户ID（必需）"
                },
                "cat_id": {
                    "type": "integer",
                    "description": "猫咪ID（可选）"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回记录数量，默认50条",
                    "default": 50
                },
                "unread_only": {
                    "type": "boolean",
                    "description": "是否只返回未读警报",
                    "default": False
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "get_user_cats",
        "description": "获取用户的所有猫咪信息，包括名字、品种、年龄、绑定设备等。用于列出用户的猫咪或获取猫咪基本信息。",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "用户ID（必需）"
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "get_full_context",
        "description": "获取用户完整上下文，包括用户信息、所有猫咪、设备、最近警报和健康摘要。用于初始化对话或需要全面了解用户情况时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "用户ID（必需）"
                }
            },
            "required": ["user_id"]
        }
    }
]


# ============================================================================
# Function Execution
# ============================================================================

def _calculate_time_range(hours: int) -> tuple:
    """
    Calculate start and end datetime for time range queries.

    Args:
        hours: Number of hours to look back

    Returns:
        tuple: (start_datetime, end_datetime)
    """
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    return start, end


async def execute_device_function(function_name: str, params: dict) -> dict:
    """
    Execute a device data function by name.

    This function routes LLM tool calls to the appropriate data source:
    - Time-series data (BCG, GPS, IMU, etc.): device_service_client (requires device_mac)
    - Metadata (users, cats, health summary): d1_client (requires user_id)

    Args:
        function_name: Name of the function to execute (from DEVICE_DATA_FUNCTIONS)
        params: Parameters for the function call

    Returns:
        dict: Query result from the database or device service

    Raises:
        ValueError: If function_name is not recognized or required params missing

    Example:
        # Time-series query (V3.4)
        result = await execute_device_function("get_collar_activity", {
            "device_mac": "AABBCCDDEEFF",
            "hours": 24,
            "limit": 50
        })

        # Metadata query
        result = await execute_device_function("get_user_cats", {
            "user_id": 1
        })
    """
    logger.info(f"Executing device function: {function_name} with params: {params}")

    try:
        # ====================================================================
        # Time-series data functions (V3.4: via device_service_client)
        # ====================================================================

        if function_name == "get_collar_activity":
            device_mac = params.get("device_mac")
            if not device_mac:
                return {"error": "device_mac is required for time-series queries", "function": function_name}

            hours = params.get("hours", 24)
            limit = params.get("limit", 100)
            start, end = _calculate_time_range(hours)

            data = await get_imu_data(
                mac=device_mac,
                start=start,
                end=end,
                limit=limit
            )
            return {"success": True, "data": data, "count": len(data)}

        elif function_name == "get_collar_bcg":
            device_mac = params.get("device_mac")
            if not device_mac:
                return {"error": "device_mac is required for time-series queries", "function": function_name}

            hours = params.get("hours", 24)
            limit = params.get("limit", 100)
            start, end = _calculate_time_range(hours)

            data = await get_bcg_data(
                mac=device_mac,
                start=start,
                end=end,
                limit=limit
            )
            return {"success": True, "data": data, "count": len(data)}

        elif function_name == "get_collar_outdoor":
            device_mac = params.get("device_mac")
            if not device_mac:
                return {"error": "device_mac is required for time-series queries", "function": function_name}

            hours = params.get("hours", 24)
            limit = params.get("limit", 50)
            start, end = _calculate_time_range(hours)

            data = await get_gps_data(
                mac=device_mac,
                start=start,
                end=end,
                limit=limit
            )
            return {"success": True, "data": data, "count": len(data)}

        elif function_name == "get_collar_temperature":
            device_mac = params.get("device_mac")
            if not device_mac:
                return {"error": "device_mac is required for time-series queries", "function": function_name}

            hours = params.get("hours", 24)
            limit = params.get("limit", 100)
            start, end = _calculate_time_range(hours)

            data = await get_temp_data(
                mac=device_mac,
                start=start,
                end=end,
                limit=limit
            )
            return {"success": True, "data": data, "count": len(data)}

        elif function_name == "get_device_events":
            device_mac = params.get("device_mac")
            if not device_mac:
                return {"error": "device_mac is required for time-series queries", "function": function_name}

            hours = params.get("hours", 24)
            limit = params.get("limit", 100)
            start, end = _calculate_time_range(hours)

            data = await get_device_events(
                mac=device_mac,
                start=start,
                end=end,
                limit=limit
            )
            return {"success": True, "data": data, "count": len(data)}

        elif function_name == "get_cat_door_passages":
            device_mac = params.get("device_mac")
            if not device_mac:
                # Fallback to D1 if no device_mac provided
                user_id = params.get("user_id")
                if not user_id:
                    return {"error": "device_mac or user_id is required", "function": function_name}
                return await get_user_cat_door_passages(
                    user_id=user_id,
                    cat_id=params.get("cat_id"),
                    limit=params.get("limit", 50)
                )

            hours = params.get("hours", 24)
            limit = params.get("limit", 50)
            start, end = _calculate_time_range(hours)

            data = await get_door_detections(
                mac=device_mac,
                start=start,
                end=end,
                limit=limit
            )
            return {"success": True, "data": data, "count": len(data)}

        # ====================================================================
        # Metadata functions (via d1_client, user-scoped)
        # ====================================================================

        elif function_name == "get_cat_expressions":
            return await get_user_cat_expression_logs(
                user_id=params["user_id"],
                cat_id=params.get("cat_id"),
                limit=params.get("limit", 50),
                pain_threshold=params.get("pain_threshold")
            )

        elif function_name == "get_health_summary":
            return await get_user_cat_health_summary(
                user_id=params["user_id"],
                cat_id=params.get("cat_id"),
                days=params.get("days", 7)
            )

        elif function_name == "get_alerts":
            return await get_user_alerts(
                user_id=params["user_id"],
                cat_id=params.get("cat_id"),
                limit=params.get("limit", 50),
                unread_only=params.get("unread_only", False)
            )

        elif function_name == "get_user_cats":
            return await get_user_cats(
                user_id=params["user_id"]
            )

        elif function_name == "get_full_context":
            return await get_user_full_context(
                user_id=params["user_id"]
            )

        else:
            raise ValueError(f"Unknown function: {function_name}")

    except Exception as e:
        logger.error(f"Error executing device function {function_name}: {e}")
        return {"error": str(e), "function": function_name, "params": params}


def get_function_definitions() -> list:
    """
    Get function definitions in OpenAI tool format.

    Returns function definitions suitable for passing to OpenAI's
    chat completions API with function calling.

    Returns:
        list: List of function definitions in OpenAI format
    """
    return [
        {
            "type": "function",
            "function": {
                "name": func["name"],
                "description": func["description"],
                "parameters": func["parameters"]
            }
        }
        for func in DEVICE_DATA_FUNCTIONS
    ]


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        """Test device data functions"""
        print("Device Data Functions:")
        for func in DEVICE_DATA_FUNCTIONS:
            print(f"  - {func['name']}: {func['description'][:50]}...")

        print("\nOpenAI Format:")
        for func in get_function_definitions():
            print(f"  - {func['function']['name']}")

    asyncio.run(test())
