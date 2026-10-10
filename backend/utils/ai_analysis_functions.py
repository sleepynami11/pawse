"""
AI Analysis Functions for LLM Tool Calling

This module provides AI-powered analysis functions for the cat health monitoring system.
These functions are designed to be called automatically when relevant data is available
(e.g., image provided, BCG data fetched) or when the LLM determines analysis is needed.

Usage:
    from utils.ai_analysis_functions import AI_ANALYSIS_FUNCTIONS, execute_ai_function

    # Get function definitions for LLM
    functions = AI_ANALYSIS_FUNCTIONS

    # Execute a function call from LLM
    result = await execute_ai_function("analyze_cat_image", {
        "image_url": "https://...",
        "user_id": 1,
        "cat_id": 2
    })

Architecture Note (V3.2):
    - AI functions are auto-executed when image is provided in chat
    - BCG analysis is triggered after fetching BCG data
    - Extensible design for adding more AI analysis functions
"""

import logging
import yaml
from typing import Any, Optional
from datetime import datetime

from utils.call_llm_async import async_call_vision_llm, async_call_llm

logger = logging.getLogger(__name__)


# ============================================================================
# AI Analysis Function Definitions for LLM Tool Calling
# ============================================================================

AI_ANALYSIS_FUNCTIONS = [
    {
        "name": "analyze_cat_image",
        "description": "分析图片中的猫咪，检测是否有猫、猫嘴里是否叼着东西。用于图片初步检测。",
        "auto_trigger": True,  # 有图片时自动触发
        "trigger_condition": "has_image",
        "parameters": {
            "type": "object",
            "properties": {
                "image_url": {
                    "type": "string",
                    "description": "图片URL（必需）"
                },
                "user_id": {
                    "type": "integer",
                    "description": "用户ID（用于日志记录）"
                },
                "cat_id": {
                    "type": "integer",
                    "description": "猫咪ID（用于日志记录）"
                }
            },
            "required": ["image_url"]
        }
    },
    {
        "name": "analyze_cat_health",
        "description": "分析猫咪图片中的健康状况，包括疼痛评分(Feline Grimace Scale)、情绪状态、眼睛/毛发/姿态等健康指标。",
        "auto_trigger": True,  # 有图片时自动触发（在 analyze_cat_image 之后）
        "trigger_condition": "has_image_and_cat_detected",
        "parameters": {
            "type": "object",
            "properties": {
                "image_url": {
                    "type": "string",
                    "description": "图片URL（必需）"
                },
                "cat_detection": {
                    "type": "object",
                    "description": "猫咪检测结果（来自 analyze_cat_image）",
                    "properties": {
                        "has_cat": {"type": "boolean"},
                        "has_object_in_mouth": {"type": "boolean"},
                        "object_type": {"type": "string"}
                    }
                },
                "user_id": {
                    "type": "integer",
                    "description": "用户ID"
                },
                "cat_id": {
                    "type": "integer",
                    "description": "猫咪ID"
                }
            },
            "required": ["image_url"]
        }
    },
    {
        "name": "analyze_bcg_data",
        "description": "分析BCG数据（心率、HRV、呼吸率），评估猫咪的心血管健康状况，检测异常模式。",
        "auto_trigger": True,  # 获取BCG数据后自动触发
        "trigger_condition": "has_bcg_data",
        "parameters": {
            "type": "object",
            "properties": {
                "bcg_data": {
                    "type": "array",
                    "description": "BCG数据记录列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "bpm": {"type": "number", "description": "心率 (beats per minute)"},
                            "hrv": {"type": "number", "description": "心率变异性 (ms)"},
                            "respiratory_rate": {"type": "number", "description": "呼吸率"},
                            "timestamp": {"type": "string", "description": "记录时间"}
                        }
                    }
                },
                "cat_id": {
                    "type": "integer",
                    "description": "猫咪ID"
                },
                "cat_info": {
                    "type": "object",
                    "description": "猫咪基本信息（年龄、品种等，用于参考正常范围）",
                    "properties": {
                        "age": {"type": "number"},
                        "breed": {"type": "string"},
                        "weight": {"type": "number"}
                    }
                }
            },
            "required": ["bcg_data"]
        }
    }
    # Note: analyze_activity_pattern has been removed (V3.3.1)
    # Activity data is now part of collar IMU data, not a separate analysis function
]


# ============================================================================
# AI Analysis Function Implementations
# ============================================================================

async def analyze_cat_image(params: dict) -> dict:
    """
    Analyze image for cat detection and object-in-mouth detection.

    This is the first-stage detection that identifies:
    1. Whether there's a cat in the image
    2. Whether the cat is holding something in its mouth
    3. What type of object it is

    Args:
        params: {
            "image_url": str,
            "user_id": int (optional),
            "cat_id": int (optional)
        }

    Returns:
        dict: {
            "has_cat": bool,
            "confidence": float,
            "cat_count": int,
            "has_object_in_mouth": bool,
            "object_type": str or None,
            "object_confidence": float,
            "description": str
        }
    """
    image_url = params.get("image_url")
    if not image_url:
        return {"error": "image_url is required", "has_cat": False}

    detection_prompt = """
分析这张图片，检测以下内容：

1. 图片中是否有猫？
2. 如果有猫，猫嘴里是否叼着东西？
3. 如果叼着东西，是什么？（如：老鼠、鸟、玩具、食物、树枝等）

请以 YAML 格式输出：

```yaml
has_cat: true/false
confidence: 0.0-1.0
cat_count: 数量
has_object_in_mouth: true/false
object_type: "物体类型或null"
object_confidence: 0.0-1.0
description: "简短描述图片中猫的状态"
```
"""

    try:
        result = await async_call_vision_llm(detection_prompt, image_url)
        yaml_str = result['text'].split("```yaml")[1].split("```")[0].strip()
        detection = yaml.safe_load(yaml_str)

        return {
            'has_cat': detection.get('has_cat', False),
            'confidence': detection.get('confidence', 0.0),
            'cat_count': detection.get('cat_count', 0),
            'has_object_in_mouth': detection.get('has_object_in_mouth', False),
            'object_type': detection.get('object_type'),
            'object_confidence': detection.get('object_confidence', 0.0),
            'description': detection.get('description', ''),
            'analysis_type': 'cat_detection'
        }
    except Exception as e:
        logger.error(f"Cat detection failed: {e}")
        return {
            'has_cat': False,
            'error': str(e),
            'analysis_type': 'cat_detection'
        }


async def analyze_cat_health(params: dict) -> dict:
    """
    Analyze cat health from image using Feline Grimace Scale and visual indicators.

    This is the second-stage analysis that evaluates:
    1. Physical health indicators (eyes, fur, posture)
    2. Facial expression (mood, alertness)
    3. Pain indicators (Feline Grimace Scale: 0-10)
    4. Object analysis (if cat is holding something)

    Args:
        params: {
            "image_url": str,
            "cat_detection": dict (optional, from analyze_cat_image),
            "user_id": int (optional),
            "cat_id": int (optional)
        }

    Returns:
        dict: {
            "health_indicators": {...},
            "expression": {...},
            "pain_score": int,
            "overall_status": str,
            "concerns": list,
            "object_analysis": dict (if applicable)
        }
    """
    image_url = params.get("image_url")
    if not image_url:
        return {"error": "image_url is required"}

    cat_detection = params.get("cat_detection", {})

    # Build enhanced prompt based on detection results
    object_section = ""
    if cat_detection.get('has_object_in_mouth'):
        object_type = cat_detection.get('object_type', '未知物体')
        object_section = f"""
6. Object Analysis (detected: {object_type}):
   - Object identification: Confirm or refine object type
   - Risk assessment: Is swallowing a risk? Choking hazard?
   - Cat's behavior with object: playing, eating, hunting trophy
   - Recommended action: monitor, intervene, or no concern
"""

    vision_prompt = f"""
Analyze this cat image for health indicators and behavior.

Focus on:
1. Physical health: Eyes (clarity, discharge), fur (condition, grooming), posture
2. Behavior: Activity level, mood (alert, lethargic, anxious)
3. Environment: Safety, comfort, cleanliness

4. Facial Expression (Feline Grimace Scale):
   - Ear position: forward (relaxed) / flattened (pain/fear)
   - Orbital tightening: open (normal) / squinting (discomfort)
   - Muzzle tension: relaxed / tight (pain indicator)

5. Pain Indicators:
   - Overall pain_score: 0-10 (0=no pain, 10=severe)
   - Alertness: alert / drowsy / lethargic
   - Mood: content / anxious / distressed
{object_section}

Provide analysis in YAML:

```yaml
health_indicators:
  eyes: <condition>
  fur: <condition>
  posture: <condition>
behavior:
  activity: <level>
  mood: <description>
concerns: <list of concerns or 'none'>
overall_status: <healthy|monitor|concern>
expression:
  mood: <content|anxious|distressed|calm>
  alertness: <alert|drowsy|lethargic>
  pain_score: <0-10>
  ear_position: <forward|flattened|sideways>
  orbital_tightening: <none|mild|moderate|severe>
object_analysis:
  confirmed_type: <confirmed object type or null>
  is_prey: <true/false>
  swallow_risk: <none|low|medium|high>
  recommended_action: <monitor|intervene|no_concern>
  notes: <additional observations>
```
"""

    try:
        result = await async_call_vision_llm(vision_prompt, image_url)
        yaml_str = result['text'].split("```yaml")[1].split("```")[0].strip()
        analysis = yaml.safe_load(yaml_str)

        expression = analysis.get('expression', {})
        object_analysis = analysis.get('object_analysis', {})

        return {
            'health_indicators': analysis.get('health_indicators', {}),
            'behavior': analysis.get('behavior', {}),
            'expression': expression,
            'pain_score': expression.get('pain_score', 0),
            'mood': expression.get('mood', 'unknown'),
            'alertness': expression.get('alertness', 'unknown'),
            'overall_status': analysis.get('overall_status', 'unknown'),
            'concerns': analysis.get('concerns', []),
            'object_analysis': object_analysis,
            'analysis_type': 'health_analysis'
        }
    except Exception as e:
        logger.error(f"Health analysis failed: {e}")
        return {
            'error': str(e),
            'overall_status': 'unknown',
            'analysis_type': 'health_analysis'
        }


async def analyze_bcg_data(params: dict) -> dict:
    """
    Analyze BCG (Ballistocardiography) data for cardiovascular health assessment.

    Evaluates:
    1. Heart rate patterns (normal range: 120-180 bpm for cats)
    2. Heart rate variability (HRV) - indicator of autonomic nervous system health
    3. Respiratory rate patterns
    4. Anomaly detection and trend analysis

    Args:
        params: {
            "bcg_data": list of BCG records,
            "cat_id": int (optional),
            "cat_info": dict with age, breed, weight (optional)
        }

    Returns:
        dict: {
            "heart_rate_analysis": {...},
            "hrv_analysis": {...},
            "respiratory_analysis": {...},
            "anomalies": list,
            "overall_assessment": str,
            "recommendations": list
        }
    """
    bcg_data = params.get("bcg_data", [])
    if not bcg_data:
        return {"error": "bcg_data is required", "analysis_type": "bcg_analysis"}

    cat_info = params.get("cat_info", {})

    # Calculate statistics from BCG data
    bpm_values = [r.get('bpm', 0) for r in bcg_data if r.get('bpm')]
    hrv_values = [r.get('hrv', 0) for r in bcg_data if r.get('hrv')]
    resp_values = [r.get('respiratory_rate', 0) for r in bcg_data if r.get('respiratory_rate')]

    stats = {
        'bpm': {
            'avg': sum(bpm_values) / len(bpm_values) if bpm_values else 0,
            'min': min(bpm_values) if bpm_values else 0,
            'max': max(bpm_values) if bpm_values else 0,
            'count': len(bpm_values)
        },
        'hrv': {
            'avg': sum(hrv_values) / len(hrv_values) if hrv_values else 0,
            'min': min(hrv_values) if hrv_values else 0,
            'max': max(hrv_values) if hrv_values else 0,
            'count': len(hrv_values)
        },
        'respiratory': {
            'avg': sum(resp_values) / len(resp_values) if resp_values else 0,
            'min': min(resp_values) if resp_values else 0,
            'max': max(resp_values) if resp_values else 0,
            'count': len(resp_values)
        }
    }

    # Prepare data summary for LLM analysis
    data_summary = f"""
BCG Data Summary ({len(bcg_data)} records):

Heart Rate (BPM):
- Average: {stats['bpm']['avg']:.1f}
- Range: {stats['bpm']['min']:.0f} - {stats['bpm']['max']:.0f}
- Normal range for cats: 120-180 bpm

Heart Rate Variability (HRV):
- Average: {stats['hrv']['avg']:.1f} ms
- Range: {stats['hrv']['min']:.0f} - {stats['hrv']['max']:.0f} ms

Respiratory Rate:
- Average: {stats['respiratory']['avg']:.1f} breaths/min
- Range: {stats['respiratory']['min']:.0f} - {stats['respiratory']['max']:.0f}
- Normal range for cats: 20-30 breaths/min

Cat Info: {cat_info if cat_info else 'Not provided'}
"""

    analysis_prompt = f"""
作为猫咪心血管健康专家，请分析以下BCG数据：

{data_summary}

请评估：
1. 心率是否在正常范围内？是否有心动过速或心动过缓的迹象？
2. HRV水平如何？低HRV可能表示压力或健康问题
3. 呼吸率是否正常？
4. 是否有任何异常模式需要关注？

请以YAML格式输出分析结果：

```yaml
heart_rate_analysis:
  status: <normal|elevated|low|concerning>
  assessment: "详细评估"
  risk_level: <low|medium|high>

hrv_analysis:
  status: <good|moderate|poor>
  assessment: "HRV评估说明"
  stress_indicator: <low|moderate|high>

respiratory_analysis:
  status: <normal|elevated|low>
  assessment: "呼吸评估"

anomalies:
  - type: "异常类型"
    severity: <mild|moderate|severe>
    description: "描述"

overall_assessment: <healthy|monitor|concern|urgent>
assessment_summary: "整体评估摘要"

recommendations:
  - "建议1"
  - "建议2"
```
"""

    try:
        result = await async_call_llm(analysis_prompt)
        yaml_str = result.split("```yaml")[1].split("```")[0].strip()
        analysis = yaml.safe_load(yaml_str)

        return {
            'statistics': stats,
            'heart_rate_analysis': analysis.get('heart_rate_analysis', {}),
            'hrv_analysis': analysis.get('hrv_analysis', {}),
            'respiratory_analysis': analysis.get('respiratory_analysis', {}),
            'anomalies': analysis.get('anomalies', []),
            'overall_assessment': analysis.get('overall_assessment', 'unknown'),
            'assessment_summary': analysis.get('assessment_summary', ''),
            'recommendations': analysis.get('recommendations', []),
            'analysis_type': 'bcg_analysis'
        }
    except Exception as e:
        logger.error(f"BCG analysis failed: {e}")
        return {
            'statistics': stats,
            'error': str(e),
            'overall_assessment': 'unknown',
            'analysis_type': 'bcg_analysis'
        }


# ============================================================================
# Function Execution Router
# ============================================================================

async def execute_ai_function(function_name: str, params: dict) -> dict:
    """
    Execute an AI analysis function by name.

    This function routes LLM tool calls to the appropriate AI analysis function.

    Args:
        function_name: Name of the function to execute (from AI_ANALYSIS_FUNCTIONS)
        params: Parameters for the function call

    Returns:
        dict: Analysis result from the AI function

    Raises:
        ValueError: If function_name is not recognized

    Example:
        result = await execute_ai_function("analyze_cat_image", {
            "image_url": "https://example.com/cat.jpg",
            "user_id": 1,
            "cat_id": 2
        })
    """
    logger.info(f"Executing AI function: {function_name} with params: {list(params.keys())}")

    try:
        if function_name == "analyze_cat_image":
            return await analyze_cat_image(params)

        elif function_name == "analyze_cat_health":
            return await analyze_cat_health(params)

        elif function_name == "analyze_bcg_data":
            return await analyze_bcg_data(params)

        else:
            raise ValueError(f"Unknown AI function: {function_name}")

    except Exception as e:
        logger.error(f"Error executing AI function {function_name}: {e}")
        return {"error": str(e), "function": function_name}


async def execute_auto_triggered_functions(
    image_url: Optional[str] = None,
    bcg_data: Optional[list] = None,
    **kwargs
) -> dict:
    """
    Execute all auto-triggered AI functions based on available data.

    This function is called automatically during chat processing to run
    relevant AI analyses based on what data is available.

    Auto-triggered functions:
    - analyze_cat_image: When image_url is provided
    - analyze_cat_health: When cat is detected in image
    - analyze_bcg_data: When bcg_data is provided

    Args:
        image_url: If provided, triggers image analysis functions
        bcg_data: If provided, triggers BCG analysis (auto-triggered in V3.3.1)
        **kwargs: Additional parameters (user_id, cat_id, cat_info, etc.)

    Returns:
        dict: Combined results from all triggered analyses
    """
    results = {}

    # Image-based analyses
    if image_url:
        # Step 1: Cat detection
        cat_detection = await analyze_cat_image({
            "image_url": image_url,
            **kwargs
        })
        results['cat_detection'] = cat_detection

        # Step 2: Health analysis (if cat detected)
        if cat_detection.get('has_cat', False):
            health_analysis = await analyze_cat_health({
                "image_url": image_url,
                "cat_detection": cat_detection,
                **kwargs
            })
            results['health_analysis'] = health_analysis

    # BCG data analysis (auto-triggered when bcg_data is provided)
    if bcg_data:
        bcg_analysis = await analyze_bcg_data({
            "bcg_data": bcg_data,
            **kwargs
        })
        results['bcg_analysis'] = bcg_analysis

    return results


def get_function_definitions() -> list:
    """
    Get AI function definitions in OpenAI tool format.

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
        for func in AI_ANALYSIS_FUNCTIONS
    ]


def get_auto_trigger_functions() -> list:
    """
    Get list of functions that should be auto-triggered.

    Returns:
        list: Function names and their trigger conditions
    """
    return [
        {
            "name": func["name"],
            "trigger_condition": func.get("trigger_condition", "manual")
        }
        for func in AI_ANALYSIS_FUNCTIONS
        if func.get("auto_trigger", False)
    ]


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        """Test AI analysis functions"""
        print("AI Analysis Functions:")
        for func in AI_ANALYSIS_FUNCTIONS:
            auto = "AUTO" if func.get("auto_trigger") else "MANUAL"
            print(f"  [{auto}] {func['name']}: {func['description'][:50]}...")

        print("\nOpenAI Format:")
        for func in get_function_definitions():
            print(f"  - {func['function']['name']}")

        print("\nAuto-Trigger Functions:")
        for func in get_auto_trigger_functions():
            print(f"  - {func['name']} (trigger: {func['trigger_condition']})")

    asyncio.run(test())
