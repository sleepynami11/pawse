from pocketflow import AsyncNode, AsyncParallelBatchNode
from utils.call_llm_async import (
    async_call_llm,
    async_call_vision_llm,
    async_call_multilingual_llm,
    async_call_novita_llm,
    async_call_openrouter_llm
    # V3.3.10: detect_language removed - LLM auto-matches user's language
)
from config.prompts import PROMPTS, get_current_date_str, BRAND_CONFIG, get_product_recommendation
from config.intent_registry import VALID_ROUTER_ACTIONS, INTENT_SKILL_MAP, get_skill_mapping, validate_action
from config.health_thresholds import HEALTH_ANOMALY_THRESHOLDS, get_thresholds_for_cat
from context_manager import SystemContext
from utils.d1_client import execute_query
from utils.r2_client import upload_file, build_r2_path_safe
from utils.chromadb_client import search_similar
from utils.embedding import generate_embedding, translate_to_english
from utils.push_notification import send_notification
import yaml
import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def safe_parse_yaml(response: str, default: dict = None) -> dict:
    """
    Safely parse YAML from LLM response with multiple fallback strategies.

    Tries multiple extraction patterns:
    1. ```yaml ... ``` block
    2. ```yml ... ``` block
    3. ``` ... ``` block (generic code block)
    4. Direct YAML parsing (no code blocks)

    Args:
        response: LLM response string that may contain YAML
        default: Default value to return if parsing fails (default: empty dict)

    Returns:
        Parsed YAML as dict, or default value if parsing fails
    """
    if default is None:
        default = {}

    if not response or not response.strip():
        logger.warning("Empty response received for YAML parsing")
        return default

    yaml_str = None

    # Strategy 1: Try ```yaml block
    if "```yaml" in response:
        try:
            yaml_str = response.split("```yaml")[1].split("```")[0].strip()
        except IndexError:
            logger.warning("Found ```yaml marker but couldn't extract content")

    # Strategy 2: Try ```yml block
    if yaml_str is None and "```yml" in response:
        try:
            yaml_str = response.split("```yml")[1].split("```")[0].strip()
        except IndexError:
            logger.warning("Found ```yml marker but couldn't extract content")

    # Strategy 3: Try generic ``` block
    if yaml_str is None and "```" in response:
        try:
            parts = response.split("```")
            if len(parts) >= 3:
                # Take the first code block content
                yaml_str = parts[1].strip()
                # Remove language identifier if present
                if yaml_str.startswith(('yaml', 'yml', 'json')):
                    yaml_str = '\n'.join(yaml_str.split('\n')[1:])
        except Exception as e:
            logger.warning(f"Failed to extract from generic code block: {e}")

    # Strategy 4: Try direct YAML parsing (no code blocks)
    if yaml_str is None:
        # Look for YAML-like content (starts with key: value pattern)
        import re
        yaml_pattern = re.search(r'(?:^|\n)([\w_]+:\s*\S.*(?:\n(?:[ \t]+.*|\s*[\w_]+:.*)?)*)', response)
        if yaml_pattern:
            yaml_str = yaml_pattern.group(1).strip()

    # Parse the extracted YAML string
    if yaml_str:
        try:
            result = yaml.safe_load(yaml_str)
            if isinstance(result, dict):
                return result
            else:
                logger.warning(f"YAML parsed but result is not a dict: {type(result)}")
                return default
        except yaml.YAMLError as e:
            logger.warning(f"YAML parse error: {e}")
            return default

    logger.warning(f"No valid YAML found in response (length={len(response)})")
    return default


__all__ = [
    'GetUserInputNode',
    'AnswerAsyncNode',
    'RouterNode',
    'RAGRetrievalNode',
    'MedicalDiagnosisNode',
    'VisionAnalysisNode',
    'StatusSummaryNode',
    'WeeklyReportNode',
    'MonthlyReportNode',
    'EmergencyAlertNode',
    'DeviceOfflineAlertNode',
    'ConversationMemoryNode',
    'MultiCatHealthAnalysisNode',
    'MultiCatComparisonNode',
    'CatDoorEventNode',
    'CollarDataIngestionNode',
    'PainDetectionNode',
    'OutdoorMonitorNode',
    'CrossDeviceAnalysisNode',
    'DailyAnalysisNode',
    'HealthSummaryNode',
    'HealthPredictionNode',
    'BehaviorPatternNode',
    'TrendAnalysisNode',
    'VetRecommendationNode',
    'DeviceStatusNode',
    'CatDetectionNode',
    # New nodes for chat flow refactoring
    'MemoryLoaderNode',
    'MemorySaverNode',
    'ResponseGeneratorNode',
    # Four-Layer RAG Architecture nodes
    'CoreRulesNode',
    'StructuredKnowledgeNode',
    # SKILL-based Progressive Loading nodes
    'IntentAnalysisNode',
    'SkillLoaderNode',
    'IoTContextNode',
    'ContextFusionNode'
]


class GetUserInputNode(AsyncNode):
    async def exec_async(self, _):
        # User input populated by HTTP/WebSocket handler before flow execution
        # No blocking input() call in async context
        return None

    async def post_async(self, shared, prep_res, exec_res):
        # Read user input from request context (populated by HTTP/WebSocket handler)
        user_input = shared['request']['user_input']
        shared["question"] = user_input
        return "default"  # Go to the next node


class AnswerAsyncNode(AsyncNode):
    async def prep_async(self, shared):
        # Read question from shared
        return shared["question"]

    async def exec_async(self, question):
        # Call async LLM to get the answer
        return await async_call_llm(question)

    async def post_async(self, shared, prep_res, exec_res):
        # Store the answer in shared
        shared["answer"] = exec_res


class ConversationMemoryNode(AsyncNode):
    """
    Conversation context management node with D1 persistence and pronoun resolution.

    Responsibilities:
    - Create or resume sessions by session_id or user_id
    - Refresh expiration (30 minutes) on each turn
    - Resolve pronouns in the latest user message using LLM
    - Persist updated history/context back to conversation_sessions table
    """

    SESSION_TTL_MINUTES = 30

    async def prep_async(self, shared):
        request = shared.get('request', {}) if isinstance(shared, dict) else {}
        user_input = request.get('user_input') or shared.get('question', '') or ''
        session_id = request.get('session_id') or shared.get('session_id')
        user_id = request.get('user_id') or shared.get('user_id')
        cat_id = request.get('cat_id') or shared.get('cat_id')

        if not session_id and not user_id:
            raise ValueError("session_id or user_id is required for conversation memory")

        session = await self._load_active_session(session_id, user_id)
        if not session:
            session = await self._create_session(user_id, session_id)

        cat_profile = {}
        if cat_id:
            try:
                async with SystemContext(cat_id=cat_id) as ctx:
                    cat_profile = await ctx.get_cat_profile(cat_id)
            except Exception as e:
                logger.warning(f"Failed to load cat profile for pronoun resolution: {e}")

        return {
            'session': session,
            'user_input': user_input,
            'user_id': session.get('user_id') or user_id,
            'cat_id': cat_id,
            'cat_profile': cat_profile
        }

    async def exec_async(self, prep_res):
        session = prep_res['session']
        user_input = prep_res['user_input']
        history = session.get('history', [])
        context = session.get('context', {})
        cat_profile = prep_res.get('cat_profile', {})

        resolved_text, entities = await self._resolve_pronouns(
            user_input=user_input,
            history=history,
            context=context,
            cat_profile=cat_profile
        )

        return {
            'resolved_text': resolved_text,
            'entities': entities,
            'session': session,
            'user_input': user_input
        }

    async def post_async(self, shared, prep_res, exec_res):
        session = prep_res['session']
        session_id = session['session_id']
        user_id = prep_res['user_id']
        cat_profile = prep_res.get('cat_profile', {}) or {}

        user_input = prep_res['user_input']
        resolved_text = exec_res.get('resolved_text', user_input)
        entities = exec_res.get('entities', [])

        history = list(session.get('history', []))
        now_ts = datetime.now().isoformat()
        history.append({
            'role': 'user',
            'content': user_input,
            'resolved_content': resolved_text,
            'timestamp': now_ts
        })

        assistant_reply = shared.get('assistant_reply') or shared.get('answer')
        if assistant_reply:
            history.append({
                'role': 'assistant',
                'content': assistant_reply,
                'timestamp': datetime.now().isoformat()
            })

        context = dict(session.get('context', {}) or {})
        if entities:
            context['entities'] = entities
        if cat_profile:
            context['cat_profile'] = {
                'id': cat_profile.get('id'),
                'name': cat_profile.get('name'),
                'breed': cat_profile.get('breed')
            }
        context['last_updated'] = now_ts

        expires_at = (datetime.now() + timedelta(minutes=self.SESSION_TTL_MINUTES)).isoformat()

        await execute_query(
            """
            UPDATE conversation_sessions
            SET history = ?, context = ?, updated_at = ?, expires_at = ?
            WHERE session_id = ?
            """,
            [
                json.dumps(history, ensure_ascii=False),
                json.dumps(context, ensure_ascii=False),
                now_ts,
                expires_at,
                session_id
            ]
        )

        request = shared.get('request', {}) if isinstance(shared, dict) else {}
        request['user_input'] = resolved_text

        shared['request'] = request
        shared['session_id'] = session_id
        shared['user_id'] = user_id
        shared['conversation_history'] = history
        shared['conversation_context'] = context
        shared['conversation_session_expires_at'] = expires_at
        shared['original_user_input'] = user_input

        return 'conversation_ready'

    async def _load_active_session(self, session_id: str | None, user_id: str | None) -> dict | None:
        filters = []
        params = []

        if session_id:
            filters.append("session_id = ?")
            params.append(session_id)
        if user_id:
            filters.append("user_id = ?")
            params.append(user_id)

        if not filters:
            return None

        sql = f"""
            SELECT session_id, user_id, history, context, created_at, updated_at, expires_at
            FROM conversation_sessions
            WHERE ({' OR '.join(filters)}) AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY updated_at DESC
            LIMIT 1
        """
        params.append(datetime.now().isoformat())

        result = await execute_query(sql, params)

        if result.get('success') and result.get('result', {}).get('results'):
            row = result['result']['results'][0]
            history = self._safe_json_load(row.get('history'), [])
            context = self._safe_json_load(row.get('context'), {})

            return {
                'session_id': row.get('session_id'),
                'user_id': row.get('user_id') or user_id,
                'history': history,
                'context': context,
                'created_at': row.get('created_at'),
                'updated_at': row.get('updated_at'),
                'expires_at': row.get('expires_at')
            }

        return None

    async def _create_session(self, user_id: str | None, session_id: str | None = None) -> dict:
        if not user_id:
            raise ValueError("user_id is required to create a new session")

        new_session_id = session_id or uuid.uuid4().hex
        now_ts = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(minutes=self.SESSION_TTL_MINUTES)).isoformat()

        if session_id:
            existing = await execute_query(
                "SELECT session_id, created_at FROM conversation_sessions WHERE session_id = ?",
                [new_session_id]
            )

            if existing.get('success') and existing.get('result', {}).get('results'):
                existing_created_at = existing['result']['results'][0].get('created_at')
                await execute_query(
                    """
                    UPDATE conversation_sessions
                    SET user_id = ?, history = ?, context = ?, updated_at = ?, expires_at = ?
                    WHERE session_id = ?
                    """,
                    [
                        user_id,
                        json.dumps([], ensure_ascii=False),
                        json.dumps({}, ensure_ascii=False),
                        now_ts,
                        expires_at,
                        new_session_id
                    ]
                )

                return {
                    'session_id': new_session_id,
                    'user_id': user_id,
                    'history': [],
                    'context': {},
                    'created_at': existing_created_at or now_ts,
                    'updated_at': now_ts,
                    'expires_at': expires_at
                }

        await execute_query(
            """
            INSERT INTO conversation_sessions
                (session_id, user_id, history, context, created_at, updated_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                new_session_id,
                user_id,
                json.dumps([], ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
                now_ts,
                now_ts,
                expires_at
            ]
        )

        return {
            'session_id': new_session_id,
            'user_id': user_id,
            'history': [],
            'context': {},
            'created_at': now_ts,
            'updated_at': now_ts,
            'expires_at': expires_at
        }

    async def _resolve_pronouns(self, user_input: str, history: list, context: dict, cat_profile: dict) -> tuple[str, list]:
        history_snippet = json.dumps(history[-5:], ensure_ascii=False, indent=2)
        context_snippet = json.dumps(context or {}, ensure_ascii=False, indent=2)
        cat_name = (cat_profile or {}).get('name', '未知')

        prompt = f"""
你是对话指代消解助手。根据历史对话、上下文实体和已知信息，替换当前消息中的代词，让含义清晰可追溯。

【历史对话-最近5条】
{history_snippet}

【上下文实体】
{context_snippet}

【已知猫咪名称】
{cat_name}

【当前用户消息】
{user_input}

请输出严格的 JSON：
{{
  "resolved_text": "将代词替换后的完整句子",
  "entities": [
    {{"pronoun": "它", "referent": "猫咪{cat_name}", "reason": "上一轮提到的猫咪"}}
  ]
}}
只输出 JSON，不要包含多余文本。
"""

        try:
            response = await async_call_llm(prompt)
            parsed = self._parse_json_response(response)
            resolved_text = parsed.get('resolved_text') or user_input
            entities = parsed.get('entities') or []

            if not isinstance(resolved_text, str):
                resolved_text = user_input

            if not isinstance(entities, list):
                entities = []
        except Exception as e:
            logger.warning(f"Pronoun resolution failed, using original input: {e}")
            resolved_text = user_input
            entities = []

        return resolved_text, entities

    def _parse_json_response(self, response_text: str) -> dict:
        if not response_text:
            return {}

        cleaned = response_text.strip()
        if '```' in cleaned:
            segments = cleaned.split('```')
            for segment in segments:
                if '{' in segment and '}' in segment:
                    cleaned = segment
                    break

        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1:
            cleaned = cleaned[start:end + 1]

        try:
            return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}")
            return {}

    def _safe_json_load(self, raw_value, default):
        if not raw_value:
            return default

        try:
            return json.loads(raw_value)
        except Exception as e:
            logger.warning(f"Failed to parse JSON field, using default: {e}")
            return default


class CatDetectionNode(AsyncNode):
    """
    Cat detection node - First stage detection for chat media.

    V3.3.8 增强功能:
    - 支持用户上传的图片/视频检测
    - 当用户询问猫咪状态但没有提供图片时，自动获取最近的猫门图片进行分析
    - 分析猫咪健康状态、情绪、是否叼东西等

    Detection targets:
    1. has_cat (bool): Whether image contains a cat
    2. has_object_in_mouth (bool): Whether cat is holding something in mouth
    3. object_type (str): Type of object being held (mouse, bird, toy, food, etc.)
    4. cat_status (dict): 猫咪状态分析（情绪、健康、活动状态）

    Output actions:
    - 'cat_detected': Cat found, continue to VisionAnalysisNode
    - 'no_cat': No cat found, skip vision analysis
    - 'no_media': No media provided, skip detection
    - 'cat_door_analyzed': 使用猫门图片分析完成，直接返回结果
    """

    # 状态查询相关的关键词
    STATUS_KEYWORDS = [
        '状态', '怎么样', '如何', '状况', '情况', '好不好', '健康',
        '精神', '情绪', '心情', '表情', '活动', '最近',
        'how is', 'status', 'condition', 'feeling', 'mood', 'doing'
    ]

    async def prep_async(self, shared):
        self._progress_callback = shared.get('progress_callback')
        request = shared.get('request', {})
        media_url = request.get('media_url')
        media_type = request.get('media_type')
        cat_id = request.get('cat_id')
        user_id = shared.get('user_id')
        user_input = request.get('user_input', '')

        # 如果用户提供了媒体，直接使用
        if media_url:
            return {
                'media_url': media_url,
                'media_type': media_type,
                'cat_id': cat_id,
                'user_id': user_id,
                'source': 'user_upload'
            }

        # V3.3.8: 检查是否是状态查询，如果是则尝试获取猫门图片
        if self._is_status_query(user_input) and cat_id and user_id:
            cat_door_image = await self._get_latest_cat_door_image(user_id, cat_id)
            if cat_door_image:
                logger.info(f"Found cat door image for status query: {cat_door_image['image_url']}")
                return {
                    'media_url': cat_door_image['image_url'],
                    'media_type': 'image',
                    'cat_id': cat_id,
                    'user_id': user_id,
                    'source': 'cat_door',
                    'cat_door_data': cat_door_image
                }

        return None  # No media, skip detection

    def _is_status_query(self, user_input: str) -> bool:
        """检查用户输入是否是询问猫咪状态的查询"""
        if not user_input:
            return False
        lower_input = user_input.lower()
        return any(keyword in lower_input for keyword in self.STATUS_KEYWORDS)

    async def _get_latest_cat_door_image(self, user_id: str, cat_id: str, hours: int = 24) -> dict | None:
        """
        获取最近的猫门图片用于分析

        Args:
            user_id: 用户ID
            cat_id: 猫咪ID
            hours: 查询最近多少小时的记录

        Returns:
            dict: 包含 image_url, mood, pain_score 等信息的字典，或 None
        """
        try:
            # 查询最近的猫门表情日志（包含图片）
            result = await execute_query(
                """
                SELECT cdel.*, c.name as cat_name
                FROM cat_door_expression_logs cdel
                JOIN cats c ON cdel.cat_id = c.id
                WHERE c.user_id = ? AND cdel.cat_id = ?
                AND cdel.timestamp > datetime('now', '-' || ? || ' hours')
                ORDER BY cdel.timestamp DESC
                LIMIT 1
                """,
                [user_id, cat_id, hours]
            )

            if result.get("success") and result.get("result", {}).get("results"):
                log = result["result"]["results"][0]
                return {
                    'image_url': log.get('image_url'),
                    'mood': log.get('mood'),
                    'alertness': log.get('alertness'),
                    'pain_score': log.get('pain_score'),
                    'timestamp': log.get('timestamp'),
                    'cat_name': log.get('cat_name'),
                    'previous_analysis': log.get('analysis_result')
                }
            return None
        except Exception as e:
            logger.warning(f"Failed to get cat door image: {e}")
            return None

    async def exec_async(self, prep_res):
        progress_cb = getattr(self, '_progress_callback', None)

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'started',
                'message': '正在检测图像中的猫咪...'
            })

        if prep_res is None:
            result = {'has_cat': False, 'skip_reason': 'no_media'}
            if progress_cb:
                await progress_cb({
                    'type': 'progress',
                    'node': self.__class__.__name__,
                    'status': 'completed',
                    'message': '猫咪检测完成'
                })
            return result

        media_url = prep_res['media_url']
        media_type = prep_res['media_type']
        source = prep_res.get('source', 'user_upload')

        # V3.3.8: 如果是猫门图片，进行状态分析
        if source == 'cat_door':
            result = await self._analyze_cat_status(media_url, prep_res.get('cat_door_data', {}))
            if progress_cb:
                await progress_cb({
                    'type': 'progress',
                    'node': self.__class__.__name__,
                    'status': 'completed',
                    'message': '猫咪检测完成'
                })
            return result

        # Video processing: extract keyframes
        if media_type == 'video':
            try:
                from utils.video_processor import extract_video_frames
                frame_urls = await extract_video_frames(media_url, max_frames=3)
                if not frame_urls:
                    result = {'has_cat': False, 'skip_reason': 'video_processing_failed'}
                    if progress_cb:
                        await progress_cb({
                            'type': 'progress',
                            'node': self.__class__.__name__,
                            'status': 'completed',
                            'message': '猫咪检测完成'
                        })
                    return result

                # Detect each frame, take highest confidence result
                results = []
                for frame_url in frame_urls:
                    result = await self._detect_cat(frame_url)
                    results.append(result)
                final_result = self._merge_results(results)
            except Exception as e:
                logger.warning(f"Video processing failed: {e}")
                final_result = {'has_cat': False, 'skip_reason': 'video_processing_failed'}
        else:
            # Image direct detection
            final_result = await self._detect_cat(media_url)

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'completed',
                'message': '猫咪检测完成'
            })

        return final_result

    async def _analyze_cat_status(self, image_url: str, cat_door_data: dict) -> dict:
        """
        V3.3.8: 分析猫门图片中猫咪的状态

        Args:
            image_url: 猫门图片URL
            cat_door_data: 之前的猫门数据（包含历史分析结果）

        Returns:
            dict: 包含猫咪状态分析的结果
        """
        cat_name = cat_door_data.get('cat_name', '猫咪')
        previous_mood = cat_door_data.get('mood', 'unknown')
        previous_pain = cat_door_data.get('pain_score', 0)

        status_prompt = f"""
分析这张猫门拍摄的猫咪图片，评估 {cat_name} 的当前状态。

历史参考信息：
- 上次记录的情绪: {previous_mood}
- 上次疼痛评分: {previous_pain}/10

请详细分析以下内容：

1. **整体健康状态**: 猫咪看起来是否健康？
2. **情绪状态**: 开心、放松、警觉、紧张、疲惫、不适？
3. **活动状态**: 精神饱满、正常、疲倦？
4. **是否有异常**: 眼睛、耳朵、毛发、姿态是否正常？
5. **是否叼着东西**: 嘴里是否有物品？

请以 YAML 格式输出：

```yaml
has_cat: true
confidence: 0.0-1.0
cat_status:
  overall_health: "健康/一般/需关注"
  mood: "情绪描述"
  energy_level: "精神饱满/正常/疲倦"
  alertness: "警觉/正常/困倦"
  pain_indicators: "无/轻微/明显"
  estimated_pain_score: 0-10
  abnormalities: "异常描述或无"
has_object_in_mouth: true/false
object_type: "物体类型或null"
description: "详细描述猫咪当前的状态，包括外观、姿态、表情等"
recommendations: "给主人的建议"
```
"""
        try:
            result = await async_call_vision_llm(status_prompt, image_url)
            # Parse YAML using safe parser
            default_analysis = {
                'confidence': 0.9,
                'cat_status': {},
                'has_object_in_mouth': False,
                'object_type': None,
                'description': '',
                'recommendations': ''
            }
            analysis = safe_parse_yaml(result.get('text', ''), default=default_analysis)

            return {
                'has_cat': True,
                'confidence': analysis.get('confidence', 0.9),
                'source': 'cat_door',
                'cat_status': analysis.get('cat_status', {}),
                'has_object_in_mouth': analysis.get('has_object_in_mouth', False),
                'object_type': analysis.get('object_type'),
                'description': analysis.get('description', ''),
                'recommendations': analysis.get('recommendations', ''),
                'image_url': image_url,
                'cat_door_data': cat_door_data
            }
        except Exception as e:
            logger.warning(f"Cat status analysis failed: {e}")
            return {
                'has_cat': True,
                'source': 'cat_door',
                'skip_reason': f'status_analysis_failed: {str(e)}',
                'image_url': image_url
            }

    async def _detect_cat(self, image_url: str) -> dict:
        """Call vision LLM for cat detection."""
        detection_prompt = """
分析这张图片，检测以下内容：

1. 图片中是否有猫？
2. 如果有猫，猫嘴里是否叼着东西？
3. 如果叼着东西，是什么？（如：老鼠、鸟、玩具、食物、树枝等）
4. 猫咪的整体状态如何？

请以 YAML 格式输出：

```yaml
has_cat: true/false
confidence: 0.0-1.0
cat_count: 数量
has_object_in_mouth: true/false
object_type: "物体类型或null"
object_confidence: 0.0-1.0
cat_status:
  mood: "情绪描述"
  energy_level: "精神饱满/正常/疲倦"
  overall_health: "健康/一般/需关注"
description: "简短描述图片中猫的状态"
```
"""
        try:
            result = await async_call_vision_llm(detection_prompt, image_url)
            # Parse YAML using safe parser
            default_detection = {
                'has_cat': False,
                'confidence': 0.0,
                'cat_count': 0,
                'has_object_in_mouth': False,
                'object_type': None,
                'object_confidence': 0.0,
                'cat_status': {},
                'description': ''
            }
            detection = safe_parse_yaml(result.get('text', ''), default=default_detection)

            return {
                'has_cat': detection.get('has_cat', False),
                'confidence': detection.get('confidence', 0.0),
                'cat_count': detection.get('cat_count', 0),
                'has_object_in_mouth': detection.get('has_object_in_mouth', False),
                'object_type': detection.get('object_type'),
                'object_confidence': detection.get('object_confidence', 0.0),
                'cat_status': detection.get('cat_status', {}),
                'description': detection.get('description', ''),
                'source': 'user_upload'
            }
        except Exception as e:
            logger.warning(f"Cat detection failed: {e}")
            return {'has_cat': False, 'skip_reason': f'detection_failed: {str(e)}'}

    def _merge_results(self, results: list) -> dict:
        """Merge detection results from multiple frames, prioritize cat detection."""
        if not results:
            return {'has_cat': False, 'skip_reason': 'no_results'}

        # Find result with highest cat confidence
        best_cat_result = None
        best_confidence = 0.0

        for result in results:
            if result.get('has_cat') and result.get('confidence', 0) > best_confidence:
                best_confidence = result.get('confidence', 0)
                best_cat_result = result

        if best_cat_result:
            return best_cat_result

        # No cat found in any frame
        return {'has_cat': False, 'skip_reason': 'no_cat_in_video'}

    async def post_async(self, shared, prep_res, exec_res):
        # Store detection results
        shared['cat_detection'] = exec_res

        if prep_res is None:
            return 'no_media'

        # V3.3.8: 如果是猫门图片分析，直接返回结果供 LLM 生成回复
        if exec_res.get('source') == 'cat_door':
            logger.info(f"Cat door image analyzed: {exec_res.get('description', '')}")
            # 存储分析结果供 ResponseGeneratorNode 使用
            shared['cat_door_analysis'] = exec_res
            return 'cat_door_analyzed'

        if exec_res.get('has_cat', False):
            logger.info(f"Cat detected: {exec_res.get('description', '')}")
            return 'cat_detected'
        else:
            logger.info(f"No cat detected: {exec_res.get('skip_reason', 'unknown')}")
            return 'no_cat'


class RouterNode(AsyncNode):
    """
    Intent classification node using hybrid LLM + rule-based approach.

    Returns 12 user query actions:
    - Alerts: emergency_alert, device_offline
    - Medical: medical_query, comprehensive_diagnosis, vet_recommendation
    - Analysis: status_summary, daily_analysis, weekly_report, monthly_report
    - Insights: health_prediction, behavior_pattern, trend_analysis

    Note: Device webhooks (collar, cat_door) use dedicated flows and bypass RouterNode.
    """
    async def prep_async(self, shared):
        self._progress_callback = shared.get('progress_callback')
        # Extract request context
        user_input = shared['request'].get('user_input', '')
        cat_id = shared['request'].get('cat_id', '1')

        # Load recent IoT logs from SystemContext
        async with SystemContext(cat_id=cat_id) as ctx:
            recent_logs = await ctx.get_recent_iot_logs(cat_id, hours=1)

        # Get cat profile for personalized thresholds (V3.3.9)
        cat_profile = shared.get('cat_profile')
        thresholds = get_thresholds_for_cat(cat_profile)

        # Duration-based anomaly detection
        emergency_flag = False
        warning_flag = False
        anomaly_details = {}

        if recent_logs:
            # Group logs by sensor type to calculate durations
            sensor_groups = {}
            for log in recent_logs:
                sensor_type = log.get('sensor_type', '')
                if sensor_type not in sensor_groups:
                    sensor_groups[sensor_type] = []
                sensor_groups[sensor_type].append(log)

            # Check each sensor type for duration-based anomalies
            for sensor_type, logs in sensor_groups.items():
                if not logs:
                    continue

                # Sort by timestamp (most recent first)
                sorted_logs = sorted(logs, key=lambda x: x.get('timestamp', ''), reverse=True)

                # Check for continuous anomalies
                first_anomaly_time = None
                anomaly_count = 0

                for log in sorted_logs:
                    value = log.get('value', 0)
                    timestamp_str = log.get('timestamp', '')
                    is_anomaly = False

                    # Temperature anomaly check (V3.3.9: Using configured thresholds)
                    if sensor_type == 'temperature':
                        temp_threshold = thresholds['temperature']['warning_high']
                        if value > temp_threshold:
                            is_anomaly = True

                    # Heart rate anomaly check (V3.3.9: Using configured thresholds)
                    elif sensor_type == 'heart_rate':
                        hr_threshold = thresholds['heart_rate']['normal_min']
                        if value < hr_threshold:
                            is_anomaly = True

                    # Activity level anomaly check (V3.3.9: Using configured thresholds)
                    elif sensor_type == 'activity':
                        activity_threshold = thresholds['activity_level']['normal_min']
                        if value < activity_threshold:
                            is_anomaly = True

                    if is_anomaly:
                        if first_anomaly_time is None:
                            # V3.3.9: Add error handling for timestamp parsing
                            try:
                                first_anomaly_time = datetime.fromisoformat(timestamp_str)
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Invalid timestamp format '{timestamp_str}': {e}. Using current time as fallback.")
                                first_anomaly_time = datetime.now()
                        anomaly_count += 1
                    else:
                        # Reset if normal reading found
                        first_anomaly_time = None
                        anomaly_count = 0

                # Calculate duration if anomaly detected
                if first_anomaly_time and anomaly_count > 0:
                    # Get most recent anomaly timestamp (V3.3.9: Add error handling)
                    try:
                        most_recent_time = datetime.fromisoformat(sorted_logs[0].get('timestamp', ''))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid timestamp format in most recent log: {e}. Using current time as fallback.")
                        most_recent_time = datetime.now()
                    duration_seconds = (most_recent_time - first_anomaly_time).total_seconds()

                    # Ignore sensor noise (duration < 1s)
                    if duration_seconds < 1:
                        continue

                    # Classify anomaly severity based on duration
                    if sensor_type == 'temperature' and duration_seconds > 60:
                        # High fever for >60s = emergency
                        emergency_flag = True
                        anomaly_details[sensor_type] = {
                            'value': sorted_logs[0].get('value'),
                            'duration': duration_seconds,
                            'confidence': 'high',
                            'severity': 'emergency'
                        }
                    elif sensor_type == 'heart_rate' and duration_seconds > 60:
                        # Abnormal heart rate for >60s = emergency
                        emergency_flag = True
                        anomaly_details[sensor_type] = {
                            'value': sorted_logs[0].get('value'),
                            'duration': duration_seconds,
                            'confidence': 'high',
                            'severity': 'emergency'
                        }
                    elif sensor_type == 'activity' and duration_seconds > 60:
                        # Low activity for >60s = warning
                        warning_flag = True
                        anomaly_details[sensor_type] = {
                            'value': sorted_logs[0].get('value'),
                            'duration': duration_seconds,
                            'confidence': 'medium',
                            'severity': 'warning'
                        }
                    else:
                        # Duration too short, mark as low confidence
                        anomaly_details[sensor_type] = {
                            'value': sorted_logs[0].get('value'),
                            'duration': duration_seconds,
                            'confidence': 'low',
                            'severity': 'info'
                        }

        # Get vision context from shared for injection into LLM prompt
        cat_detection = shared.get('cat_detection', {})
        vision_analysis = shared.get('vision_analysis', {})
        vision_context = self._build_vision_context(cat_detection, vision_analysis)

        return {
            'user_input': user_input,
            'cat_id': cat_id,
            'recent_logs': recent_logs[:5],  # Keep only last 5 logs for context
            'emergency_flag': emergency_flag,
            'warning_flag': warning_flag,
            'anomaly_details': anomaly_details,
            'vision_context': vision_context
        }

    def _build_vision_context(self, cat_detection: dict, vision_analysis: dict) -> str:
        """Build vision context string for LLM prompt injection."""
        # No media provided
        if not cat_detection and not vision_analysis:
            return ""

        # No cat detected
        if cat_detection.get('skip_reason') == 'no_media':
            return ""

        if not cat_detection.get('has_cat', False):
            skip_reason = cat_detection.get('skip_reason', '未检测到猫')
            return f"""
### VISUAL CONTEXT
图片/视频分析: 未检测到猫咪 ({skip_reason})
"""

        # Cat detected - build comprehensive context
        context_parts = ["### VISUAL CONTEXT"]
        context_parts.append("检测到猫咪: 是")
        context_parts.append(f"置信度: {cat_detection.get('confidence', 0):.2f}")

        if cat_detection.get('has_object_in_mouth'):
            object_type = cat_detection.get('object_type', '未知物体')
            context_parts.append(f"叼东西: 是 - {object_type}")

            # Add object analysis if available
            obj_analysis = vision_analysis.get('object_analysis', {})
            if obj_analysis:
                context_parts.append(f"物体确认: {obj_analysis.get('confirmed_type', object_type)}")
                context_parts.append(f"是否猎物: {'是' if obj_analysis.get('is_prey') else '否'}")
                context_parts.append(f"吞食风险: {obj_analysis.get('swallow_risk', 'unknown')}")
                context_parts.append(f"建议动作: {obj_analysis.get('recommended_action', 'monitor')}")
        else:
            context_parts.append("叼东西: 否")

        # Add health analysis if available
        if vision_analysis:
            pain_score = vision_analysis.get('pain_score', 0)
            mood = vision_analysis.get('mood', 'unknown')
            overall_status = vision_analysis.get('overall_status', 'unknown')
            context_parts.append(f"疼痛评分: {pain_score}/10")
            context_parts.append(f"情绪状态: {mood}")
            context_parts.append(f"整体状态: {overall_status}")

        return "\n".join(context_parts)

    async def exec_async(self, prep_res):
        progress_cb = getattr(self, '_progress_callback', None)

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'started',
                'message': '正在分析问题类型...'
            })

        user_input = prep_res['user_input']
        recent_logs = prep_res['recent_logs']
        vision_context = prep_res.get('vision_context', '')

        # Build LLM prompt for intent classification using config
        logs_summary = "\n".join([
            f"- {log.get('sensor_type')}: {log.get('value')} at {log.get('timestamp')}"
            for log in recent_logs
        ]) if recent_logs else "No recent sensor data"

        # V3.3.4: Use prompt from config file
        prompt = PROMPTS['router']['intent'].format(
            user_input=user_input or '(用户只发送了图片/视频，无文字输入)',
            vision_context=vision_context,
            logs_summary=logs_summary
        )

        response = await async_call_llm(prompt)

        # Parse YAML response using safe parser
        result = safe_parse_yaml(response, default={"action": "medical_query", "reason": "parse_fallback"})

        # Validate response
        if not isinstance(result, dict) or "action" not in result:
            logger.warning(f"Invalid router response, using fallback")
            result = {"action": "medical_query", "reason": "invalid_response"}

        # V3.3.4: Use valid actions from config (includes direct_reply)
        if result["action"] not in VALID_ROUTER_ACTIONS:
            logger.warning(f"Invalid action '{result['action']}', defaulting to 'medical_query'")
            result["action"] = "medical_query"

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'completed',
                'message': '问题类型分析完成'
            })

        return result

    async def post_async(self, shared, prep_res, exec_res):
        # Store anomaly details from prep_res
        shared['router_output'] = {
            'anomaly_details': prep_res.get('anomaly_details', {}),
            'emergency_flag': prep_res.get('emergency_flag', False),
            'warning_flag': prep_res.get('warning_flag', False)
        }

        # Override with emergency if rule-based flag is set
        if prep_res['emergency_flag']:
            shared['router_action'] = 'emergency_alert'
            shared['router_reason'] = 'Rule-based anomaly detected'
            return 'emergency_alert'

        # Store LLM classification result
        shared['router_action'] = exec_res['action']
        shared['router_reason'] = exec_res.get('reason', 'LLM classified')
        shared['router_confidence'] = exec_res.get('confidence', 0.0)

        return exec_res['action']


class RAGRetrievalNode(AsyncNode):
    """
    Four-layer RAG retrieval node with hierarchical routing.

    Layers (L4 -> L1):
    - L4: 用户友好解读 (chunk_size=256)
    - L3: 日常护理建议 (chunk_size=512)
    - L2: 常见病症指南 (chunk_size=1024)
    - L1: 专业医学知识 (chunk_size=512)
    """

    LAYERS = [
        {
            'name': 'L4',
            'description': '用户友好解读',
            'index': 'rag-layer-l4-friendly',
            'chunk_size': 256,
            'weight': 0.9
        },
        {
            'name': 'L3',
            'description': '日常护理建议',
            'index': 'rag-layer-l3-care',
            'chunk_size': 512,
            'weight': 0.95
        },
        {
            'name': 'L2',
            'description': '常见病症指南',
            'index': 'rag-layer-l2-guides',
            'chunk_size': 1024,
            'weight': 1.0
        },
        {
            'name': 'L1',
            'description': '专业医学知识',
            'index': 'rag-layer-l1-medical',
            'chunk_size': 512,
            'weight': 1.1
        }
    ]

    def _estimate_complexity(self, query: str) -> float:
        q_lower = query.lower()
        token_count = len(query.split())

        length_score = min(token_count / 40, 1.0)
        clinical_terms = [
            '发烧', '呕吐', '腹泻', '慢性', '并发症', '剂量', '禁忌',
            '疫苗', '治疗', '处方', '抗生素', '手术', '指标', '体征'
        ]
        term_hits = sum(1 for term in clinical_terms if term in q_lower)
        term_score = min(term_hits / 6, 1.0)

        structure_score = 0.2 if ('?' in query or '？' in query) else 0.0

        return min(1.0, 0.5 * length_score + 0.4 * term_score + structure_score)

    def _select_layers(self, complexity: float) -> list[dict]:
        if complexity < 0.25:
            return self.LAYERS[:1]
        elif complexity < 0.5:
            return self.LAYERS[:2]
        elif complexity < 0.75:
            return self.LAYERS[:3]
        else:
            return self.LAYERS

    def _get_top_k(self, layer: dict) -> int:
        chunk_size = layer.get('chunk_size', 512)
        if chunk_size >= 1024:
            return 6
        elif chunk_size >= 512:
            return 5
        return 4

    def _fuse_results(self, results: list[dict]) -> list[dict]:
        if not results:
            return []

        fused = {}
        for item in results:
            metadata = item.get('metadata', {}) or {}
            key_source = metadata.get('id') or metadata.get('text') or metadata.get('content', '')
            key = item.get('id') or (key_source.strip().lower() if key_source else None)
            if not key:
                continue

            weight = item.get('weight', 1.0)
            score = (item.get('score') or 0.0) * weight

            if key not in fused or score > fused[key].get('rank_score', 0):
                fused[key] = {
                    **item,
                    'rank_score': score
                }

        return sorted(fused.values(), key=lambda x: x.get('rank_score', 0), reverse=True)

    async def prep_async(self, shared):
        request = shared.get('request', {}) if isinstance(shared, dict) else {}
        query = request.get('user_input') or shared.get('question', '')

        if not query:
            raise ValueError("No query provided for RAG retrieval")

        # Query Augmentation: Enhance query with visual context
        cat_detection = shared.get('cat_detection', {})
        augmented_query = query

        if cat_detection.get('has_object_in_mouth'):
            object_type = cat_detection.get('object_type', '')
            if object_type:
                # Prepend object context to improve RAG retrieval
                augmented_query = f"猫叼着{object_type} {query}"
                logger.info(f"Query augmented with object context: {augmented_query}")
        elif cat_detection.get('has_cat'):
            # If cat detected but no object, add general cat health context
            vision_analysis = shared.get('vision_analysis', {})
            overall_status = vision_analysis.get('overall_status', '')
            if overall_status and overall_status != 'healthy':
                augmented_query = f"猫健康状态:{overall_status} {query}"
                logger.info(f"Query augmented with health context: {augmented_query}")

        return {
            'query': augmented_query,
            'original_query': query,
            'has_augmentation': augmented_query != query
        }

    async def exec_async(self, prep_res):
        query = prep_res['query']

        # Translate query to English for consistent RAG retrieval
        # (Knowledge base is stored in English)
        english_query = await translate_to_english(query)

        # V3.3.10: Fallback to original query if translation returns empty
        # This prevents embedding errors when translation service fails
        if not english_query or not english_query.strip():
            logger.warning(f"Translation returned empty for '{query[:50]}...', using original query")
            english_query = query

        logger.info(f"RAG query translated: '{query[:50]}...' -> '{english_query[:50]}...'")

        # Use original query for complexity estimation (preserves language-specific terms)
        complexity = self._estimate_complexity(query)
        selected_layers = self._select_layers(complexity)

        # Generate embedding using English query for better vector matching
        query_vector = await generate_embedding(english_query)

        aggregated_results = []
        per_layer_results = []

        for layer in selected_layers:
            matches = await search_similar(
                index=layer['index'],
                query_vector=query_vector,
                top_k=self._get_top_k(layer)
            )

            annotated = [
                {
                    'id': match.get('id'),
                    'score': match.get('score', 0.0),
                    'metadata': match.get('metadata', {}) or {},
                    'layer': layer['name'],
                    'index': layer['index'],
                    'chunk_size': layer['chunk_size'],
                    'weight': layer['weight']
                }
                for match in matches or []
            ]

            per_layer_results.append({
                'layer': layer['name'],
                'description': layer['description'],
                'results': annotated
            })
            aggregated_results.extend(annotated)

        fused_results = self._fuse_results(aggregated_results)

        return {
            'query': query,
            'english_query': english_query,
            'complexity': complexity,
            'selected_layers': [l['name'] for l in selected_layers],
            'layer_results': per_layer_results,
            'fused_results': fused_results
        }

    async def post_async(self, shared, prep_res, exec_res):
        shared['rag_query'] = exec_res.get('query')
        shared['rag_english_query'] = exec_res.get('english_query')
        shared['rag_original_query'] = prep_res.get('original_query')
        shared['rag_query_augmented'] = prep_res.get('has_augmentation', False)
        shared['rag_complexity'] = exec_res.get('complexity')
        shared['rag_layers_used'] = exec_res.get('selected_layers', [])
        shared['rag_results'] = exec_res.get('fused_results', [])
        shared['rag_layer_details'] = exec_res.get('layer_results', [])

        # Route based on router_action for proper flow branching
        router_action = shared.get('router_action', '')
        if router_action == 'comprehensive_diagnosis':
            return 'rag_comprehensive'
        elif router_action == 'vet_recommendation':
            return 'rag_vet'
        elif router_action == 'medical_query':
            return 'rag_medical'
        else:
            # Default for V3.3.2 RAG intents (care_advice, dietary_consultation, etc.)
            return 'rag_retrieval_complete'


class MemoryRetrievalNode(AsyncNode):
    """
    Memory layer (L0) retrieval node for recency-based conversation search.

    Implements semantic search over conversation history stored in ChromaDB
    Memory collection with recency filtering and temporal decay scoring.

    Features:
    - Semantic search using conversation turn embeddings
    - Recency filtering (last 30 days)
    - Temporal decay: score = base_score * exp(-days_ago * 0.1)
    - Top-K retrieval with configurable limit

    Output:
    - shared['memory_results']: List of relevant conversation turns
    - shared['memory_query']: Original query text
    - shared['memory_count']: Number of results retrieved
    """

    MEMORY_TOP_K = 5
    RECENCY_WEIGHT = 1.2
    MEMORY_TTL_DAYS = 30

    async def prep_async(self, shared):
        """
        Load conversation context and prepare Memory search query.

        Extracts user_input, session_id, user_id, and conversation_history
        from shared store populated by MemoryLoaderNode.

        Returns:
            dict: Prepared context with query, user_id, session_id, history
        """
        try:
            request = shared.get('request', {}) if isinstance(shared, dict) else {}
            user_input = request.get('user_input') or shared.get('question', '')

            if not user_input:
                logger.warning("No user_input provided for Memory retrieval, using fallback")
                user_input = ""

            session_id = request.get('session_id') or shared.get('session_id')
            user_id = request.get('user_id') or shared.get('user_id')
            conversation_history = shared.get('conversation_history', [])

            if not user_id and not session_id:
                logger.warning("No user_id or session_id for Memory retrieval, will return empty results")

            return {
                'query': user_input,
                'user_id': user_id,
                'session_id': session_id,
                'history': conversation_history
            }

        except Exception as e:
            logger.warning(f"Error in MemoryRetrievalNode prep_async: {e}, using defaults")
            return {
                'query': '',
                'user_id': None,
                'session_id': None,
                'history': []
            }

    async def exec_async(self, prep_res):
        """
        Query Memory collection with semantic search and recency filtering.

        Generates embedding from query, searches ChromaDB Memory collection,
        applies temporal decay, and returns top-K results sorted by final score.

        Returns:
            dict: Memory results with metadata (timestamp, content, score)
        """
        query = prep_res.get('query', '')
        user_id = prep_res.get('user_id')

        if not query or not user_id:
            logger.info("Empty query or no user_id, returning empty Memory results")
            return {
                'memory_results': [],
                'query': query,
                'user_id': user_id
            }

        try:
            # V3.3.10: Translate query to English for consistent embedding matching
            # Knowledge base and memory are stored with English embeddings
            english_query = await translate_to_english(query)

            # V3.3.10: Fallback to original query if translation returns empty
            if not english_query or not english_query.strip():
                logger.warning(f"Translation returned empty for Memory query, using original")
                english_query = query

            logger.info(f"Translated Memory query to English: '{english_query[:50]}...'")

            query_vector = await generate_embedding(english_query)
            logger.info(f"Generated embedding for Memory query")

            memory_results = await search_similar(
                index='memory_layer_short_term',
                query_vector=query_vector,
                top_k=self.MEMORY_TOP_K
            )

            if not memory_results:
                logger.info("No Memory results found in ChromaDB")
                return {
                    'memory_results': [],
                    'query': query,
                    'user_id': user_id
                }

            now = datetime.now()
            filtered_results = []

            for result in memory_results:
                metadata = result.get('metadata', {}) or {}
                timestamp_str = metadata.get('timestamp')

                if not timestamp_str:
                    continue

                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    days_ago = (now - timestamp).days

                    if days_ago > self.MEMORY_TTL_DAYS:
                        continue

                    base_score = result.get('score', 0.0)
                    import math
                    temporal_decay = math.exp(-days_ago * 0.1)
                    final_score = base_score * temporal_decay * self.RECENCY_WEIGHT

                    filtered_results.append({
                        'id': result.get('id'),
                        'score': base_score,
                        'final_score': final_score,
                        'metadata': metadata,
                        'turn_content': metadata.get('turn_content', ''),
                        'timestamp': timestamp_str,
                        'days_ago': days_ago
                    })

                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse timestamp in Memory result: {e}")
                    continue

            filtered_results.sort(key=lambda x: x.get('final_score', 0), reverse=True)
            logger.info(f"Found {len(filtered_results)} Memory results after recency filtering")

            return {
                'memory_results': filtered_results[:self.MEMORY_TOP_K],
                'query': query,
                'user_id': user_id
            }

        except Exception as e:
            logger.error(f"Error in MemoryRetrievalNode exec_async: {e}", exc_info=True)
            return {
                'memory_results': [],
                'query': query,
                'user_id': user_id
            }

    async def post_async(self, shared, prep_res, exec_res):
        """
        Store Memory results in shared store and return routing action.

        Populates shared['memory_results'], shared['memory_query'],
        and shared['memory_count'] for downstream nodes.

        Returns:
            str: Routing action 'memory_retrieval_complete'
        """
        try:
            memory_results = exec_res.get('memory_results', [])
            query = exec_res.get('query', '')
            user_id = exec_res.get('user_id')

            shared['memory_results'] = memory_results
            shared['memory_query'] = query
            shared['memory_count'] = len(memory_results)
            shared['memory_user_id'] = user_id

            logger.info(f"Memory retrieval complete: {len(memory_results)} results for query '{query[:50]}...'")

            return 'memory_retrieval_complete'

        except Exception as e:
            logger.error(f"Error in MemoryRetrievalNode post_async: {e}", exc_info=True)
            shared['memory_results'] = []
            shared['memory_query'] = ''
            shared['memory_count'] = 0
            shared['memory_user_id'] = None
            return 'memory_retrieval_complete'


class HybridRetrievalNode(AsyncNode):
    """
    Hybrid Memory + RAG retrieval with RRF fusion and temporal weighting.

    Combines Memory layer (L0) results with RAG layer (L1-L4) results using
    Reciprocal Rank Fusion (RRF) with weighted scoring and temporal decay.

    Features:
    - RRF fusion: score = sum(weight / (k + rank_i)) for each source
    - Temporal decay: Memory results boosted by recency exp(-days_ago * 0.1)
    - Layer weights: Memory=1.2, L1=1.1, L2=1.0, L3=0.95, L4=0.9
    - Content deduplication: Merge similar results (threshold 0.9)

    Output:
    - shared['hybrid_results']: Fused and ranked results
    - shared['hybrid_memory_count']: Memory result count
    - shared['hybrid_rag_count']: RAG result count
    """

    # Layer weights for RRF fusion
    MEMORY_WEIGHT = 1.2
    L1_WEIGHT = 1.1
    L2_WEIGHT = 1.0
    L3_WEIGHT = 0.95
    L4_WEIGHT = 0.9

    # RRF parameters
    RRF_K = 60
    DECAY_RATE = 0.1

    # Deduplication threshold (content similarity)
    SIMILARITY_THRESHOLD = 0.9

    # Output limit
    HYBRID_TOP_K = 10

    async def prep_async(self, shared):
        """
        Load Memory and RAG results from shared store.

        Extracts results populated by MemoryRetrievalNode and RAGRetrievalNode
        from previous execution phases.

        Returns:
            dict: Prepared context with memory_results and rag_results
        """
        try:
            memory_results = shared.get('memory_results', [])
            rag_results = shared.get('rag_results', [])

            logger.info(f"Hybrid fusion: {len(memory_results)} memory + {len(rag_results)} RAG results")

            return {
                'memory_results': memory_results,
                'rag_results': rag_results
            }

        except Exception as e:
            logger.warning(f"Error in HybridRetrievalNode prep_async: {e}, using empty results")
            return {
                'memory_results': [],
                'rag_results': []
            }

    async def exec_async(self, prep_res):
        """
        Apply RRF fusion with temporal decay and deduplication.

        Combines Memory and RAG results using weighted RRF scoring,
        applies temporal decay to Memory results, and deduplicates
        similar content.

        Returns:
            dict: Fused results with metadata
        """
        memory_results = prep_res.get('memory_results', [])
        rag_results = prep_res.get('rag_results', [])

        if not memory_results and not rag_results:
            logger.info("No results from Memory or RAG, returning empty hybrid results")
            return {
                'hybrid_results': [],
                'memory_count': 0,
                'rag_count': 0,
                'fusion_method': 'RRF+TemporalDecay'
            }

        try:
            # Annotate Memory results with layer and weight
            annotated_memory = []
            for result in memory_results:
                annotated = {
                    **result,
                    'layer': 'Memory',
                    'weight': self.MEMORY_WEIGHT,
                    'source': 'memory'
                }
                annotated_memory.append(annotated)

            # Annotate RAG results with weights based on layer
            annotated_rag = []
            for result in rag_results:
                layer = result.get('layer', 'L2')
                weight_map = {
                    'L1': self.L1_WEIGHT,
                    'L2': self.L2_WEIGHT,
                    'L3': self.L3_WEIGHT,
                    'L4': self.L4_WEIGHT
                }
                weight = weight_map.get(layer, self.L2_WEIGHT)

                annotated = {
                    **result,
                    'weight': weight,
                    'source': 'rag'
                }
                annotated_rag.append(annotated)

            # Combine all results
            all_results = annotated_memory + annotated_rag

            # Apply temporal decay to Memory results
            all_results = self._apply_temporal_decay(all_results)

            # Apply RRF fusion
            fused_results = self._rrf_fusion(all_results, k=self.RRF_K)

            # Deduplicate by content similarity
            deduplicated_results = self._deduplicate_results(fused_results, threshold=self.SIMILARITY_THRESHOLD)

            # Sort by final score and return top K
            deduplicated_results.sort(key=lambda x: x.get('rrf_score', 0), reverse=True)
            top_results = deduplicated_results[:self.HYBRID_TOP_K]

            logger.info(f"Hybrid fusion complete: {len(top_results)} final results (after deduplication)")

            return {
                'hybrid_results': top_results,
                'memory_count': len(memory_results),
                'rag_count': len(rag_results),
                'fusion_method': 'RRF+TemporalDecay',
                'total_before_dedup': len(fused_results),
                'total_after_dedup': len(deduplicated_results)
            }

        except Exception as e:
            logger.error(f"Error in HybridRetrievalNode exec_async: {e}", exc_info=True)
            return {
                'hybrid_results': [],
                'memory_count': len(memory_results),
                'rag_count': len(rag_results),
                'fusion_method': 'RRF+TemporalDecay',
                'error': str(e)
            }

    async def post_async(self, shared, prep_res, exec_res):
        """
        Store hybrid results in shared store and return routing action.

        Populates shared['hybrid_results'], shared['hybrid_memory_count'],
        shared['hybrid_rag_count'], and fusion metadata for downstream nodes.

        Returns:
            str: Routing action 'hybrid_retrieval_complete'
        """
        try:
            hybrid_results = exec_res.get('hybrid_results', [])
            memory_count = exec_res.get('memory_count', 0)
            rag_count = exec_res.get('rag_count', 0)
            fusion_method = exec_res.get('fusion_method', 'RRF+TemporalDecay')

            shared['hybrid_results'] = hybrid_results
            shared['hybrid_memory_count'] = memory_count
            shared['hybrid_rag_count'] = rag_count
            shared['hybrid_total_count'] = len(hybrid_results)
            shared['hybrid_fusion_method'] = fusion_method

            logger.info(f"Hybrid retrieval complete: {len(hybrid_results)} results "
                       f"(Memory: {memory_count}, RAG: {rag_count})")

            return 'hybrid_retrieval_complete'

        except Exception as e:
            logger.error(f"Error in HybridRetrievalNode post_async: {e}", exc_info=True)
            shared['hybrid_results'] = []
            shared['hybrid_memory_count'] = 0
            shared['hybrid_rag_count'] = 0
            shared['hybrid_total_count'] = 0
            shared['hybrid_fusion_method'] = 'RRF+TemporalDecay'
            return 'hybrid_retrieval_complete'

    def _rrf_fusion(self, results: list[dict], k: int = 60) -> list[dict]:
        """
        Apply Reciprocal Rank Fusion (RRF) to combine multi-source results.

        Groups results by source (Memory, L1-L4), assigns ranks within each source,
        and calculates RRF score using formula: score = weight / (k + rank).

        Args:
            results: List of result dicts with 'source', 'layer', 'weight', 'score'
            k: RRF constant (default 60)

        Returns:
            List of results with added 'rrf_score' field, sorted by RRF score
        """
        if not results:
            return []

        # Group results by source and layer
        grouped = {}
        for result in results:
            source = result.get('source', 'unknown')
            layer = result.get('layer', 'unknown')
            key = f"{source}_{layer}"

            if key not in grouped:
                grouped[key] = []
            grouped[key].append(result)

        # Sort each group by original score and assign ranks
        for key, group in grouped.items():
            group.sort(key=lambda x: x.get('final_score') or x.get('score', 0), reverse=True)

        # Calculate RRF scores
        rrf_results = []
        for result in results:
            source = result.get('source', 'unknown')
            layer = result.get('layer', 'unknown')
            key = f"{source}_{layer}"

            group = grouped[key]
            rank = group.index(result) + 1  # Rank starts from 1

            weight = result.get('weight', 1.0)
            rrf_score = weight / (k + rank)

            rrf_result = {
                **result,
                'rrf_score': rrf_score,
                'rank_in_source': rank
            }
            rrf_results.append(rrf_result)

        return rrf_results

    def _apply_temporal_decay(self, results: list[dict]) -> list[dict]:
        """
        Apply time-based weighting to Memory results.

        Calculates temporal decay factor using formula:
        decay_factor = exp(-days_ago * decay_rate)

        Only applies to Memory results with timestamp metadata.

        Args:
            results: List of result dicts (Memory and RAG)

        Returns:
            List of results with temporal decay applied to Memory results
        """
        from datetime import datetime
        import math

        now = datetime.now()
        decayed_results = []

        for result in results:
            source = result.get('source', '')
            if source != 'memory':
                # No temporal decay for RAG results
                decayed_results.append(result)
                continue

            # Apply temporal decay to Memory results
            metadata = result.get('metadata', {}) or {}
            timestamp_str = metadata.get('timestamp') or result.get('timestamp')

            if not timestamp_str:
                # No timestamp, use result as-is
                decayed_results.append(result)
                continue

            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                days_ago = (now - timestamp).days

                decay_factor = math.exp(-days_ago * self.DECAY_RATE)

                # Apply decay to score
                original_score = result.get('final_score') or result.get('score', 0.0)
                decayed_score = original_score * decay_factor

                decayed_result = {
                    **result,
                    'final_score': decayed_score,
                    'temporal_decay': decay_factor,
                    'days_ago': days_ago
                }
                decayed_results.append(decayed_result)

            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse timestamp for temporal decay: {e}")
                decayed_results.append(result)

        return decayed_results

    def _deduplicate_results(self, results: list[dict], threshold: float = 0.9) -> list[dict]:
        """
        Merge similar results by content similarity.

        Compares content text using simple heuristic (normalized overlap).
        Merges duplicates by keeping higher score and combining metadata.

        Args:
            results: List of result dicts with content/text fields
            threshold: Similarity threshold (0.0-1.0) for merging

        Returns:
            List of deduplicated results
        """
        if not results:
            return []

        def normalize_text(text: str) -> str:
            """Normalize text for comparison (lowercase, no punctuation)."""
            import re
            text = text.lower()
            text = re.sub(r'[^\w\s]', '', text)
            text = ' '.join(text.split())
            return text

        def calculate_similarity(text1: str, text2: str) -> float:
            """Calculate simple overlap similarity between two texts."""
            if not text1 or not text2:
                return 0.0

            words1 = set(normalize_text(text1).split())
            words2 = set(normalize_text(text2).split())

            if not words1 or not words2:
                return 0.0

            intersection = len(words1 & words2)
            union = len(words1 | words2)

            return intersection / union if union > 0 else 0.0

        deduplicated = []
        merged_indices = set()

        for i, result in enumerate(results):
            if i in merged_indices:
                continue

            # Get content from various possible fields
            metadata = result.get('metadata', {}) or {}
            content = (
                result.get('turn_content') or
                metadata.get('content') or
                metadata.get('text') or
                metadata.get('turn_content') or
                ''
            )

            if not content:
                deduplicated.append(result)
                continue

            # Check for similar results
            merged_sources = [result.get('layer', 'unknown')]

            for j in range(i + 1, len(results)):
                if j in merged_indices:
                    continue

                other_metadata = results[j].get('metadata', {}) or {}
                other_content = (
                    results[j].get('turn_content') or
                    other_metadata.get('content') or
                    other_metadata.get('text') or
                    other_metadata.get('turn_content') or
                    ''
                )

                if not other_content:
                    continue

                similarity = calculate_similarity(content, other_content)

                if similarity >= threshold:
                    # Merge: keep higher score
                    if results[j].get('rrf_score', 0) > result.get('rrf_score', 0):
                        result = results[j]

                    merged_sources.append(results[j].get('layer', 'unknown'))
                    merged_indices.add(j)

            # Add merged_sources metadata
            result['merged_sources'] = list(set(merged_sources))
            deduplicated.append(result)

        return deduplicated


class MedicalDiagnosisNode(AsyncNode):
    """
    RAG-based medical diagnosis node using 3-phase pipeline:
    1. Keyword extraction from symptoms
    2. Vectorize semantic search for relevant medical knowledge
    3. LLM diagnosis with retrieved chunks + medical history
    """
    async def prep_async(self, shared):
        cat_id = shared['request'].get('cat_id', '1')
        user_input = shared['request']['user_input']

        # Load medical context from SystemContext
        async with SystemContext(cat_id=cat_id) as ctx:
            medical_history = await ctx.get_medical_history(cat_id)
            recent_logs = await ctx.get_recent_iot_logs(cat_id, hours=24)

        return {
            'user_input': user_input,
            'medical_history': medical_history,
            'recent_logs': recent_logs
        }

    async def exec_async(self, prep_res):
        user_input = prep_res['user_input']
        medical_history = prep_res['medical_history']
        recent_logs = prep_res['recent_logs']

        # Phase 1: Keyword extraction using LLM
        keyword_prompt = f"""
Extract medical keywords from this query for semantic search.
Return only the keywords, comma-separated.

Query: {user_input}

Keywords:
"""
        keywords_response = await async_call_llm(keyword_prompt)
        keywords = [k.strip() for k in keywords_response.split(',')]

        # Phase 2: Vectorize semantic search
        # Convert keywords to query embedding (simplified - in production, use actual embedding)
        # For now, use keywords directly in search
        search_results = await search_similar(
            index='cat-medical-knowledge',
            query_vector=[],  # In production, embed keywords first
            top_k=3
        )

        # Phase 3: LLM diagnosis with retrieved chunks
        chunks_text = "\n\n---\n\n".join([
            f"Knowledge #{i+1}:\n{chunk.get('text', '')}"
            for i, chunk in enumerate(search_results)
        ]) if search_results else "No relevant medical knowledge found"

        history_text = "\n".join([
            f"- {event.get('timestamp')}: {event.get('event_type')} - {json.dumps(event.get('details', {}))}"
            for event in medical_history[:5]
        ]) if medical_history else "No medical history available"

        diagnosis_prompt = f"""
You are a veterinary AI assistant. Provide a medical diagnosis based on:

### SYMPTOMS
{user_input}

### MEDICAL KNOWLEDGE
{chunks_text}

### MEDICAL HISTORY
{history_text}

### RECENT SENSOR DATA (last 24h)
{len(recent_logs)} sensor readings available

### OUTPUT FORMAT
Return diagnosis in YAML:

```yaml
diagnosis: <detailed diagnosis>
recommendations: <treatment recommendations>
confidence: <0.0-1.0>
urgency: <low|medium|high>
```
"""

        diagnosis_response = await async_call_llm(diagnosis_prompt)

        # Parse YAML response using safe parser
        default_diagnosis = {
            'diagnosis': 'Unable to provide diagnosis - LLM response parsing failed',
            'recommendations': 'Please consult a veterinarian for proper diagnosis.',
            'confidence': 0.3,
            'urgency': 'medium'
        }
        result = safe_parse_yaml(diagnosis_response, default=default_diagnosis)

        # Validate and ensure required fields exist
        if not isinstance(result, dict):
            logger.warning("Diagnosis result is not a dict, using default")
            result = default_diagnosis
        if "diagnosis" not in result:
            result['diagnosis'] = default_diagnosis['diagnosis']
        if "confidence" not in result:
            result['confidence'] = default_diagnosis['confidence']

        return result

    async def post_async(self, shared, prep_res, exec_res):
        # Store diagnosis in shared
        shared['diagnosis'] = exec_res

        # Return action based on confidence
        confidence = exec_res.get('confidence', 0.0)
        if confidence >= 0.8:
            return 'high_confidence'
        else:
            return 'low_confidence'


class VisionAnalysisNode(AsyncNode):
    """
    Image analysis node for cat health/behavior assessment.
    Supports dual-mode input: URL (new chat flow) and Base64 (legacy webhook).
    Calls vision LLM, stores results in D1.

    Supports:
    - General health analysis (eyes, fur, posture)
    - Facial expression analysis (mood, alertness)
    - Pain indicator detection (Feline Grimace Scale)
    - Object analysis (when cat holds something in mouth)
    """
    async def prep_async(self, shared):
        self._progress_callback = shared.get('progress_callback')
        cat_id = shared['request'].get('cat_id', '1')
        user_id = shared.get('user_id')  # Get user_id for R2 path

        # Detect image source
        image_source = shared['request'].get('image_source', 'general')
        passage_log_id = shared.get('cat_door_passage_log', {}).get('id')

        # Mode A: URL mode (new chat flow with media_url)
        media_url = shared['request'].get('media_url')
        if media_url:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Get cat detection results for enhanced analysis
            cat_detection = shared.get('cat_detection', {})
            return {
                'cat_id': cat_id,
                'user_id': user_id,
                'image_url': media_url,
                'timestamp': timestamp,
                'image_source': 'chat',  # Mark as chat source
                'passage_log_id': None,
                'cat_detection': cat_detection,
                'input_mode': 'url'
            }

        # Mode B: Base64 mode (legacy webhook flow)
        image_data = shared['request'].get('image')
        if not image_data:
            raise ValueError("No image data provided in request (neither media_url nor base64)")

        # Upload image to R2 with user_id/cat_id path structure
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{timestamp}.jpg'
        key = build_r2_path_safe(user_id, cat_id, 'images', filename)

        # Convert image_data to bytes if it's a string (base64)
        if isinstance(image_data, str):
            import base64
            image_bytes = base64.b64decode(image_data)
        else:
            image_bytes = image_data

        image_url = await upload_file(
            bucket='cat-images',
            key=key,
            data=image_bytes
        )

        return {
            'cat_id': cat_id,
            'user_id': user_id,
            'image_url': image_url,
            'timestamp': timestamp,
            'image_source': image_source,
            'passage_log_id': passage_log_id,
            'cat_detection': shared.get('cat_detection', {}),
            'input_mode': 'base64'
        }

    async def exec_async(self, prep_res):
        progress_cb = getattr(self, '_progress_callback', None)

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'started',
                'message': '正在分析猫咪健康状态...'
            })

        image_url = prep_res['image_url']
        image_source = prep_res.get('image_source', 'general')
        cat_detection = prep_res.get('cat_detection', {})

        # Build enhanced vision prompt based on source and detection
        expression_section = ""
        object_section = ""

        if image_source == 'cat_door':
            expression_section = """
4. Facial Expression (Feline Grimace Scale):
   - Ear position: forward (relaxed) / flattened (pain/fear)
   - Orbital tightening: open (normal) / squinting (discomfort)
   - Muzzle tension: relaxed / tight (pain indicator)

5. Pain Indicators:
   - Overall pain_score: 0-10 (0=no pain, 10=severe)
   - Alertness: alert / drowsy / lethargic
   - Mood: content / anxious / distressed
"""

        # Add object analysis section if cat is holding something
        if cat_detection.get('has_object_in_mouth'):
            object_type = cat_detection.get('object_type', '未知物体')
            object_section = f"""
6. Object Analysis (detected: {object_type}):
   - Object identification: Confirm or refine object type
   - Risk assessment: Is swallowing a risk? Choking hazard?
   - Cat's behavior with object: playing, eating, hunting trophy
   - Recommended action: monitor, intervene, or no concern
"""

        # For chat source, always include pain analysis
        if image_source == 'chat':
            expression_section = """
4. Facial Expression (Feline Grimace Scale):
   - Ear position: forward (relaxed) / flattened (pain/fear)
   - Orbital tightening: open (normal) / squinting (discomfort)
   - Muzzle tension: relaxed / tight (pain indicator)

5. Pain Indicators:
   - Overall pain_score: 0-10 (0=no pain, 10=severe)
   - Alertness: alert / drowsy / lethargic
   - Mood: content / anxious / distressed
"""

        vision_prompt = f"""
Analyze this cat image for health indicators and behavior.

Focus on:
1. Physical health: Eyes (clarity, discharge), fur (condition, grooming), posture
2. Behavior: Activity level, mood (alert, lethargic, anxious)
3. Environment: Safety, comfort, cleanliness
{expression_section}
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
  alertness: <alert|drowsy|lethergic>
  pain_score: <0-10>
  ear_position: <forward|flattened|sideways>
  orbital_tightening: <none|mild|moderate|severe>
# Object analysis fields (if holding something):
object_analysis:
  confirmed_type: <confirmed object type or null>
  is_prey: <true/false>
  swallow_risk: <none|low|medium|high>
  recommended_action: <monitor|intervene|no_concern>
  notes: <additional observations>
```
"""

        vision_result = await async_call_vision_llm(vision_prompt, image_url)

        # Parse YAML from vision response using safe parser
        default_analysis = {
            'expression': {
                'mood': 'unknown',
                'alertness': 'unknown',
                'pain_score': 0,
                'ear_position': 'unknown',
                'orbital_tightening': 'none'
            },
            'object_analysis': {
                'confirmed_type': None,
                'is_prey': False,
                'swallow_risk': 'none',
                'recommended_action': 'monitor',
                'notes': ''
            },
            'overall_status': 'unknown'
        }
        analysis = safe_parse_yaml(vision_result.get('text', ''), default=default_analysis)

        # Extract expression fields
        expression = analysis.get('expression', default_analysis['expression'])
        object_analysis = analysis.get('object_analysis', default_analysis['object_analysis'])

        result = {
            'analysis': analysis,
            'raw_response': vision_result,
            'image_url': prep_res['image_url'],
            'mood': expression.get('mood', 'unknown'),
            'alertness': expression.get('alertness', 'unknown'),
            'pain_score': expression.get('pain_score', 0),
            'object_analysis': object_analysis,
            'overall_status': analysis.get('overall_status', 'unknown')
        }

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'completed',
                'message': '猫咪健康分析完成'
            })

        return result

    async def post_async(self, shared, prep_res, exec_res):
        cat_id = prep_res['cat_id']
        timestamp = prep_res['timestamp']
        analysis = exec_res['analysis']
        image_url = exec_res['image_url']
        image_source = prep_res.get('image_source', 'general')
        passage_log_id = prep_res.get('passage_log_id')

        # Insert analysis into D1 vision_logs table
        await execute_query(
            """
            INSERT INTO vision_logs (cat_id, image_url, analysis_result, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            [cat_id, image_url, json.dumps(analysis), datetime.now().isoformat()]
        )

        # If from cat door, also write to cat_door_expression_logs
        if image_source == 'cat_door' and passage_log_id:
            await execute_query(
                """
                INSERT INTO cat_door_expression_logs 
                    (passage_log_id, mood, alertness, pain_score, analysis_details, image_url, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    passage_log_id,
                    exec_res.get('mood', 'unknown'),
                    exec_res.get('alertness', 'unknown'),
                    exec_res.get('pain_score', 0),
                    json.dumps(analysis),
                    image_url,
                    datetime.now().isoformat()
                ]
            )

        # Store in shared for downstream nodes
        shared['vision_analysis'] = exec_res

        # Route based on pain score
        pain_score = exec_res.get('pain_score', 0)
        if pain_score >= 6:
            return 'pain_alert'

        return 'analysis_complete' 


class DailyAnalysisNode(AsyncNode):
    """
    Daily aggregation node using SQL aggregates to reduce data transfer.
    Summarizes today's activity, BCG, and outdoor metrics from D1.
    """

    async def prep_async(self, shared):
        cat_id = shared['request'].get('cat_id', '1')

        activity_result = await execute_query(
            """
            SELECT activity_type,
                   SUM(value) AS total_value,
                   AVG(value) AS avg_value,
                   COUNT(*) AS records
            FROM collar_activity_logs
            WHERE cat_id = ? AND DATE(timestamp) = DATE('now','localtime')
            GROUP BY activity_type
            """,
            [cat_id]
        )

        activity_summary = {}
        if activity_result.get("success") and activity_result.get("result", {}).get("results"):
            for row in activity_result["result"]["results"]:
                activity_type = row.get('activity_type', 'unknown')
                activity_summary[activity_type] = {
                    'total_value': row.get('total_value', 0) or 0,
                    'avg_value': row.get('avg_value', 0) or 0,
                    'records': row.get('records', 0) or 0
                }

        bcg_result = await execute_query(
            """
            SELECT
                AVG(heart_rate_bpm) AS avg_heart_rate,
                MIN(heart_rate_bpm) AS min_heart_rate,
                MAX(heart_rate_bpm) AS max_heart_rate,
                AVG(hrv_ms) AS avg_hrv_ms,
                AVG(respiratory_rate) AS avg_respiratory_rate,
                SUM(CASE WHEN anomaly_flag = 1 THEN 1 ELSE 0 END) AS anomaly_count,
                COUNT(*) AS sample_count
            FROM collar_bcg_logs
            WHERE cat_id = ? AND DATE(timestamp) = DATE('now','localtime')
            """,
            [cat_id]
        )

        bcg_row = {}
        if bcg_result.get("success") and bcg_result.get("result", {}).get("results"):
            bcg_row = bcg_result["result"]["results"][0]

        bcg_summary = {
            'avg_heart_rate': bcg_row.get('avg_heart_rate', 0) or 0,
            'min_heart_rate': bcg_row.get('min_heart_rate', 0) or 0,
            'max_heart_rate': bcg_row.get('max_heart_rate', 0) or 0,
            'avg_hrv_ms': bcg_row.get('avg_hrv_ms', 0) or 0,
            'avg_respiratory_rate': bcg_row.get('avg_respiratory_rate', 0) or 0,
            'anomaly_count': bcg_row.get('anomaly_count', 0) or 0,
            'sample_count': bcg_row.get('sample_count', 0) or 0
        }

        outdoor_result = await execute_query(
            """
            SELECT
                SUM(CASE WHEN is_outdoor = 1 THEN 1 ELSE 0 END) AS outdoor_events,
                SUM(CASE WHEN is_outdoor = 1 THEN (JULIANDAY(COALESCE(ended_at, CURRENT_TIMESTAMP)) - JULIANDAY(started_at)) * 86400 ELSE 0 END) AS outdoor_seconds,
                MAX(started_at) AS last_started_at,
                MAX(ended_at) AS last_ended_at
            FROM collar_outdoor_logs
            WHERE cat_id = ? AND DATE(started_at) = DATE('now','localtime')
            """,
            [cat_id]
        )

        outdoor_row = {}
        if outdoor_result.get("success") and outdoor_result.get("result", {}).get("results"):
            outdoor_row = outdoor_result["result"]["results"][0]

        outdoor_seconds = outdoor_row.get('outdoor_seconds', 0) or 0
        outdoor_summary = {
            'outdoor_events': outdoor_row.get('outdoor_events', 0) or 0,
            'outdoor_seconds': outdoor_seconds,
            'outdoor_hours': outdoor_seconds / 3600 if outdoor_seconds else 0,
            'last_started_at': outdoor_row.get('last_started_at'),
            'last_ended_at': outdoor_row.get('last_ended_at')
        }

        return {
            'cat_id': cat_id,
            'activity_summary': activity_summary,
            'bcg_summary': bcg_summary,
            'outdoor_summary': outdoor_summary
        }

    async def exec_async(self, prep_res):
        activity_summary = prep_res['activity_summary']
        bcg_summary = prep_res['bcg_summary']
        outdoor_summary = prep_res['outdoor_summary']

        activity_total = sum(value.get('total_value', 0) or 0 for value in activity_summary.values())
        active_minutes = activity_summary.get('active_minutes', {}).get('total_value', 0) or 0
        sleep_minutes = activity_summary.get('sleep', {}).get('total_value', 0) or 0

        avg_heart_rate = bcg_summary.get('avg_heart_rate', 0) or 0
        heart_rate_state = 'normal'
        if avg_heart_rate and (avg_heart_rate < 100 or avg_heart_rate > 180):
            heart_rate_state = 'out_of_range'

        insights = []
        if bcg_summary.get('anomaly_count', 0) > 0:
            insights.append('BCG anomalies detected today')
        if outdoor_summary.get('outdoor_hours', 0) > 4:
            insights.append('Extended outdoor duration detected')
        if not insights:
            insights.append('Stable daily metrics recorded')

        return {
            'cat_id': prep_res['cat_id'],
            'activity_summary': activity_summary,
            'bcg_summary': bcg_summary,
            'outdoor_summary': outdoor_summary,
            'totals': {
                'activity_total': activity_total,
                'active_minutes': active_minutes,
                'sleep_minutes': sleep_minutes
            },
            'heart_rate_state': heart_rate_state,
            'insights': insights
        }

    async def post_async(self, shared, prep_res, exec_res):
        shared['daily_analysis'] = exec_res
        return 'daily_analysis_complete'


class HealthSummaryNode(AsyncNode):
    """
    Health scoring node combining activity, heart rate, and sleep metrics.
    Uses aggregated D1 queries to minimize data transfer.
    """

    async def prep_async(self, shared):
        cat_id = shared['request'].get('cat_id', '1')

        if 'daily_analysis' in shared:
            daily = shared['daily_analysis']
            return {
                'cat_id': cat_id,
                'activity_summary': daily.get('activity_summary', {}),
                'bcg_summary': daily.get('bcg_summary', {}),
                'outdoor_summary': daily.get('outdoor_summary', {})
            }

        activity_result = await execute_query(
            """
            SELECT activity_type,
                   SUM(value) AS total_value,
                   AVG(value) AS avg_value,
                   COUNT(*) AS records
            FROM collar_activity_logs
            WHERE cat_id = ? AND DATE(timestamp) = DATE('now','localtime')
            GROUP BY activity_type
            """,
            [cat_id]
        )

        activity_summary = {}
        if activity_result.get("success") and activity_result.get("result", {}).get("results"):
            for row in activity_result["result"]["results"]:
                activity_type = row.get('activity_type', 'unknown')
                activity_summary[activity_type] = {
                    'total_value': row.get('total_value', 0) or 0,
                    'avg_value': row.get('avg_value', 0) or 0,
                    'records': row.get('records', 0) or 0
                }

        bcg_result = await execute_query(
            """
            SELECT
                AVG(heart_rate_bpm) AS avg_heart_rate,
                MIN(heart_rate_bpm) AS min_heart_rate,
                MAX(heart_rate_bpm) AS max_heart_rate,
                AVG(hrv_ms) AS avg_hrv_ms,
                AVG(respiratory_rate) AS avg_respiratory_rate,
                SUM(CASE WHEN anomaly_flag = 1 THEN 1 ELSE 0 END) AS anomaly_count,
                COUNT(*) AS sample_count
            FROM collar_bcg_logs
            WHERE cat_id = ? AND DATE(timestamp) = DATE('now','localtime')
            """,
            [cat_id]
        )

        bcg_row = {}
        if bcg_result.get("success") and bcg_result.get("result", {}).get("results"):
            bcg_row = bcg_result["result"]["results"][0]

        bcg_summary = {
            'avg_heart_rate': bcg_row.get('avg_heart_rate', 0) or 0,
            'min_heart_rate': bcg_row.get('min_heart_rate', 0) or 0,
            'max_heart_rate': bcg_row.get('max_heart_rate', 0) or 0,
            'avg_hrv_ms': bcg_row.get('avg_hrv_ms', 0) or 0,
            'avg_respiratory_rate': bcg_row.get('avg_respiratory_rate', 0) or 0,
            'anomaly_count': bcg_row.get('anomaly_count', 0) or 0,
            'sample_count': bcg_row.get('sample_count', 0) or 0
        }

        outdoor_result = await execute_query(
            """
            SELECT
                SUM(CASE WHEN is_outdoor = 1 THEN 1 ELSE 0 END) AS outdoor_events,
                SUM(CASE WHEN is_outdoor = 1 THEN (JULIANDAY(COALESCE(ended_at, CURRENT_TIMESTAMP)) - JULIANDAY(started_at)) * 86400 ELSE 0 END) AS outdoor_seconds,
                MAX(started_at) AS last_started_at,
                MAX(ended_at) AS last_ended_at
            FROM collar_outdoor_logs
            WHERE cat_id = ? AND DATE(started_at) = DATE('now','localtime')
            """,
            [cat_id]
        )

        outdoor_row = {}
        if outdoor_result.get("success") and outdoor_result.get("result", {}).get("results"):
            outdoor_row = outdoor_result["result"]["results"][0]

        outdoor_seconds = outdoor_row.get('outdoor_seconds', 0) or 0
        outdoor_summary = {
            'outdoor_events': outdoor_row.get('outdoor_events', 0) or 0,
            'outdoor_seconds': outdoor_seconds,
            'outdoor_hours': outdoor_seconds / 3600 if outdoor_seconds else 0,
            'last_started_at': outdoor_row.get('last_started_at'),
            'last_ended_at': outdoor_row.get('last_ended_at')
        }

        return {
            'cat_id': cat_id,
            'activity_summary': activity_summary,
            'bcg_summary': bcg_summary,
            'outdoor_summary': outdoor_summary
        }

    async def exec_async(self, prep_res):
        activity_summary = prep_res['activity_summary']
        bcg_summary = prep_res['bcg_summary']
        outdoor_summary = prep_res['outdoor_summary']

        total_activity = sum(value.get('total_value', 0) or 0 for value in activity_summary.values())
        active_minutes = activity_summary.get('active_minutes', {}).get('total_value', 0) or 0
        sleep_minutes = activity_summary.get('sleep', {}).get('total_value', 0) or 0
        steps = activity_summary.get('steps', {}).get('total_value', 0) or 0

        avg_heart_rate = bcg_summary.get('avg_heart_rate', 0) or 0
        avg_hrv = bcg_summary.get('avg_hrv_ms', 0) or 0
        anomaly_penalty = min(bcg_summary.get('anomaly_count', 0) * 0.05, 0.3)
        outdoor_penalty = 0.1 if outdoor_summary.get('outdoor_hours', 0) > 6 else 0

        activity_score = min(max(total_activity, active_minutes * 50, steps) / 5000 if total_activity or active_minutes or steps else 0, 1.0)
        sleep_hours = sleep_minutes / 60 if sleep_minutes else 0
        sleep_score = min(sleep_hours / 12, 1.0)

        if avg_heart_rate == 0:
            heart_rate_score = 0.5
        elif 120 <= avg_heart_rate <= 180:
            heart_rate_score = 1.0
        elif 100 <= avg_heart_rate < 120 or 180 < avg_heart_rate <= 200:
            heart_rate_score = 0.7
        else:
            heart_rate_score = 0.4

        if avg_hrv and avg_hrv < 20:
            heart_rate_score = max(0.0, heart_rate_score - 0.2)

        raw_score = (
            activity_score * 0.4 +
            heart_rate_score * 0.35 +
            sleep_score * 0.25 -
            anomaly_penalty -
            outdoor_penalty
        )

        normalized_score = max(0.0, min(1.0, raw_score))
        health_score = round(normalized_score * 100, 1)

        if normalized_score >= 0.75:
            status = 'healthy'
        elif normalized_score >= 0.55:
            status = 'monitor'
        else:
            status = 'concern'

        return {
            'cat_id': prep_res['cat_id'],
            'health_score': health_score,
            'normalized_score': normalized_score,
            'status': status,
            'components': {
                'activity_score': round(activity_score, 2),
                'heart_rate_score': round(heart_rate_score, 2),
                'sleep_score': round(sleep_score, 2),
                'anomaly_penalty': round(anomaly_penalty, 2),
                'outdoor_penalty': round(outdoor_penalty, 2)
            },
            'metrics': {
                'total_activity': total_activity,
                'active_minutes': active_minutes,
                'sleep_minutes': sleep_minutes,
                'steps': steps,
                'avg_heart_rate': avg_heart_rate,
                'avg_hrv_ms': avg_hrv,
                'outdoor_hours': outdoor_summary.get('outdoor_hours', 0)
            }
        }

    async def post_async(self, shared, prep_res, exec_res):
        shared['health_summary'] = exec_res
        shared['health_score'] = exec_res.get('health_score')
        return 'health_summary_complete'


class HealthPredictionNode(AsyncNode):
    """
    Predictive health outlook node using current summaries.

    Generates short-term risk assessment and watch metrics
    based on health/daily/status summaries and router flags.
    """

    def _parse_yaml(self, response_text: str) -> dict:
        if not response_text:
            return {}

        candidate = response_text
        if '```yaml' in response_text:
            try:
                candidate = response_text.split('```yaml')[1].split('```')[0].strip()
            except Exception:
                candidate = response_text

        try:
            parsed = yaml.safe_load(candidate)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    async def prep_async(self, shared):
        request = shared.get('request', {}) if isinstance(shared, dict) else {}
        return {
            'cat_id': request.get('cat_id', '1'),
            'health_summary': shared.get('health_summary', {}),
            'daily_analysis': shared.get('daily_analysis', {}),
            'status_summary': shared.get('status_summary', {}),
            'router_flags': shared.get('router_output', {})
        }

    async def exec_async(self, prep_res):
        prompt = f"""
基于当前的健康摘要、日常分析和设备路由信号，预测未来 48-72 小时的健康走势，并给出监测重点。

【健康摘要】
{json.dumps(prep_res.get('health_summary', {}), ensure_ascii=False, indent=2)}

【日常分析】
{json.dumps(prep_res.get('daily_analysis', {}), ensure_ascii=False, indent=2)}

【状态概要】
{json.dumps(prep_res.get('status_summary', {}), ensure_ascii=False, indent=2)}

【告警标记】
{json.dumps(prep_res.get('router_flags', {}), ensure_ascii=False, indent=2)}

请输出 YAML：
```yaml
prediction:
  outlook: <improving|stable|declining>
  risk_level: <low|medium|high>
  drivers: ["原因1", "原因2"]
  recommendations: ["建议1", "建议2"]
watch_metrics: ["心率", "活动量"]
summary: <一句话预测摘要>
```
"""

        response = await async_call_llm(prompt)
        parsed = self._parse_yaml(response)
        prediction = parsed.get('prediction') or {}

        return {
            'cat_id': prep_res.get('cat_id', '1'),
            'prediction': {
                'outlook': prediction.get('outlook', 'stable'),
                'risk_level': prediction.get('risk_level', 'medium'),
                'drivers': prediction.get('drivers', []),
                'recommendations': prediction.get('recommendations', [])
            },
            'watch_metrics': parsed.get('watch_metrics', []),
            'summary': parsed.get('summary', '')
        }

    async def post_async(self, shared, prep_res, exec_res):
        shared['health_prediction'] = exec_res
        return 'health_prediction_complete'


class TrendAnalysisNode(AsyncNode):
    """
    Trend analysis node highlighting direction and risks.
    Combines daily and health summaries to surface changes.
    """

    def _parse_yaml(self, response_text: str) -> dict:
        if not response_text:
            return {}

        candidate = response_text
        if '```yaml' in response_text:
            try:
                candidate = response_text.split('```yaml')[1].split('```')[0].strip()
            except Exception:
                candidate = response_text

        try:
            parsed = yaml.safe_load(candidate)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    async def prep_async(self, shared):
        request = shared.get('request', {}) if isinstance(shared, dict) else {}
        return {
            'cat_id': request.get('cat_id', '1'),
            'health_summary': shared.get('health_summary', {}),
            'daily_analysis': shared.get('daily_analysis', {}),
            'status_summary': shared.get('status_summary', {})
        }

    async def exec_async(self, prep_res):
        prompt = f"""
请基于近期的指标生成趋势分析，指出改善/恶化的方向以及风险点。

【健康摘要】
{json.dumps(prep_res.get('health_summary', {}), ensure_ascii=False, indent=2)}

【日常分析】
{json.dumps(prep_res.get('daily_analysis', {}), ensure_ascii=False, indent=2)}

【状态概要】
{json.dumps(prep_res.get('status_summary', {}), ensure_ascii=False, indent=2)}

输出 YAML：
```yaml
trend:
  direction: <improving|stable|declining>
  highlights: ["亮点1", "亮点2"]
risks: ["风险1", "风险2"]
recommendations: ["建议1", "建议2"]
summary: <一句话总结>
```
"""

        response = await async_call_llm(prompt)
        parsed = self._parse_yaml(response)
        trend = parsed.get('trend') or {}

        return {
            'cat_id': prep_res.get('cat_id', '1'),
            'trend': {
                'direction': trend.get('direction', 'stable'),
                'highlights': trend.get('highlights', [])
            },
            'risks': parsed.get('risks', []),
            'recommendations': parsed.get('recommendations', []),
            'summary': parsed.get('summary', '')
        }

    async def post_async(self, shared, prep_res, exec_res):
        shared['trend_analysis'] = exec_res
        return 'trend_analysis_complete'


class BehaviorPatternNode(AsyncNode):
    """
    Behavior pattern analysis combining activity, status, and vision cues.
    """

    def _parse_yaml(self, response_text: str) -> dict:
        if not response_text:
            return {}

        candidate = response_text
        if '```yaml' in response_text:
            try:
                candidate = response_text.split('```yaml')[1].split('```')[0].strip()
            except Exception:
                candidate = response_text

        try:
            parsed = yaml.safe_load(candidate)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    async def prep_async(self, shared):
        request = shared.get('request', {}) if isinstance(shared, dict) else {}
        return {
            'cat_id': request.get('cat_id', '1'),
            'daily_analysis': shared.get('daily_analysis', {}),
            'status_summary': shared.get('status_summary', {}),
            'vision_analysis': shared.get('vision_analysis', {})
        }

    async def exec_async(self, prep_res):
        prompt = f"""
结合活动/健康指标与视觉分析，总结近期行为模式并提示异常。

【日常分析】
{json.dumps(prep_res.get('daily_analysis', {}), ensure_ascii=False, indent=2)}

【状态概要】
{json.dumps(prep_res.get('status_summary', {}), ensure_ascii=False, indent=2)}

【视觉分析】
{json.dumps(prep_res.get('vision_analysis', {}), ensure_ascii=False, indent=2)}

请输出 YAML：
```yaml
patterns:
  - description: <模式说明>
    confidence: <0.0-1.0>
anomalies: ["异常1", "异常2"]
recommendations: ["建议1", "建议2"]
summary: <一句话概述>
```
"""

        response = await async_call_llm(prompt)
        parsed = self._parse_yaml(response)

        return {
            'cat_id': prep_res.get('cat_id', '1'),
            'patterns': parsed.get('patterns', []),
            'anomalies': parsed.get('anomalies', []),
            'recommendations': parsed.get('recommendations', []),
            'summary': parsed.get('summary', '')
        }

    async def post_async(self, shared, prep_res, exec_res):
        shared['behavior_pattern'] = exec_res
        return 'behavior_pattern_complete'


class VetRecommendationNode(AsyncNode):
    """
    Veterinary visit recommendation node combining health scoring and pain detection.

    Evaluates visit urgency, recommends department, builds preparation checklist,
    and generates natural language guidance via LLM.
    """

    def _evaluate_urgency(self, health_summary: dict, pain_detection: dict, router_flags: dict, symptoms: str) -> dict:
        pain_score = pain_detection.get('pain_score', 0) or 0
        pain_action = pain_detection.get('recommended_action', '')
        health_status = health_summary.get('status')
        normalized_score = health_summary.get('normalized_score', 0) or 0
        anomaly_penalty = health_summary.get('components', {}).get('anomaly_penalty', 0) or 0
        bcg_anomalies = health_summary.get('bcg_summary', {}).get('anomaly_count', 0) or 0

        emergency_signals = []
        soon_signals = []
        recommended_signals = []

        if pain_score > 7 or pain_action == 'urgent_care':
            emergency_signals.append('疼痛评分高，需立即就诊')
        elif pain_score >= 5:
            soon_signals.append('疼痛评分中度，需尽快评估')
        elif pain_score >= 2:
            recommended_signals.append('轻度疼痛，建议预约检查')

        if router_flags.get('emergency_flag'):
            emergency_signals.append('实时监测发现严重异常')
        if router_flags.get('warning_flag'):
            soon_signals.append('持续监测异常，需要尽快检查')

        if health_status == 'concern' or normalized_score < 0.45 or anomaly_penalty >= 0.25:
            emergency_signals.append('健康评分偏低/异常累积，存在严重风险')
        elif health_status == 'monitor' or normalized_score < 0.6 or anomaly_penalty >= 0.1 or bcg_anomalies >= 2:
            soon_signals.append('近期指标波动，需 24-48 小时内复查')
        elif health_status == 'healthy' and symptoms:
            recommended_signals.append('健康评分正常，可按需预约确认')

        symptom_text = symptoms or ''
        routine_keywords = ['疫苗', '体检', '驱虫', '绝育', '复查', '年检']
        has_routine_intent = any(keyword in symptom_text for keyword in routine_keywords)

        visit_window_map = {
            'emergency': '立即就医，优先线下医院',
            'soon': '24-48 小时内就医',
            'recommended': '1 周内预约就诊',
            'optional': '按计划预约/咨询'
        }

        if emergency_signals:
            level = 'emergency'
            reasons = emergency_signals
        elif soon_signals:
            level = 'soon'
            reasons = soon_signals
        elif recommended_signals:
            level = 'recommended'
            reasons = recommended_signals
        elif has_routine_intent:
            level = 'optional'
            reasons = ['常规健康管理需求']
        else:
            level = 'recommended'
            reasons = ['建议常规检查确认健康状态']

        return {
            'level': level,
            'visit_window': visit_window_map.get(level, '按计划预约'),
            'reasons': reasons
        }

    def _recommend_department(self, symptoms: str, pain_detection: dict) -> dict:
        text = symptoms or ''
        lower_text = text.lower()
        department = '内科'
        reason = '综合症状评估，内科先行'

        mapping = [
            ('眼科', ['眼', '流泪', '眼睛', '视力', '结膜', '眼部分泌物']),
            ('皮肤科', ['皮肤', '掉毛', '瘙痒', '皮疹', '皮屑', '红肿']),
            ('外科', ['外伤', '伤口', '骨折', '跛', '摔', '肿块', '瘸']),
            ('口腔科', ['口腔', '牙', '牙龈', '口臭', '咬合', '流口水']),
            ('呼吸科', ['咳嗽', '喘', '呼吸', '喷嚏', '鼻涕'])
        ]

        for dept, keywords in mapping:
            if any(keyword in text or keyword in lower_text for keyword in keywords):
                department = dept
                reason = f"症状关键词指向{dept}检查"
                break

        pain_score = pain_detection.get('pain_score', 0) or 0
        if department == '内科' and (pain_score >= 6 or pain_detection.get('recommended_action') == 'urgent_care'):
            department = '外科'
            reason = '疼痛评分偏高，优先外科或急诊评估'

        return {'department': department, 'reason': reason}

    def _build_checklist(self, cat_profile: dict, urgency_level: str, health_summary: dict, pain_detection: dict) -> list[dict]:
        checklist = []
        cat_name = cat_profile.get('name', '猫咪') if cat_profile else '猫咪'
        health_score = health_summary.get('health_score')
        health_status = health_summary.get('status')

        if health_score is not None:
            checklist.append({
                'item': '近期健康报告',
                'detail': f"健康评分 {health_score}，状态 {health_status or '未知'}，附带传感器摘要"
            })

        checklist.append({
            'item': '症状与时间线',
            'detail': f"记录 {cat_name} 的症状描述、发作时间、诱因，越详细越好"
        })

        if pain_detection:
            checklist.append({
                'item': '疼痛/影像资料',
                'detail': '携带疼痛评分截图、相关照片/视频，方便医生定位问题'
            })

        checklist.extend([
            {
                'item': '既往病史与用药',
                'detail': '疫苗/驱虫记录、近期用药、过敏史、慢性病信息'
            },
            {
                'item': '运输与安抚',
                'detail': '猫笼、毛巾或熟悉的气味用品，减少就诊压力'
            },
            {
                'item': '支付与联系人',
                'detail': '携带保险/会员卡，提前确认就诊医院和联系方式'
            }
        ])

        if urgency_level in ['emergency', 'soon']:
            checklist.append({
                'item': '提前沟通与禁食提醒',
                'detail': '提前电话联系医院开通急诊通道，如需镇静请遵医嘱控制饮食'
            })

        return checklist

    async def prep_async(self, shared):
        cat_id = shared['request'].get('cat_id', '1')
        symptoms = shared['request'].get('user_input') or shared.get('question', '')
        health_summary = shared.get('health_summary', {})
        pain_detection = shared.get('pain_detection', {})
        router_flags = shared.get('router_output', {})

        async with SystemContext(cat_id=cat_id) as ctx:
            cat_profile = await ctx.get_cat_profile(cat_id)

        return {
            'cat_id': cat_id,
            'symptoms': symptoms or '',
            'health_summary': health_summary,
            'pain_detection': pain_detection,
            'router_flags': router_flags,
            'cat_profile': cat_profile
        }

    async def exec_async(self, prep_res):
        symptoms = prep_res['symptoms']
        health_summary = prep_res['health_summary']
        pain_detection = prep_res['pain_detection']
        router_flags = prep_res['router_flags']
        cat_profile = prep_res['cat_profile']

        urgency = self._evaluate_urgency(health_summary, pain_detection, router_flags, symptoms)
        department = self._recommend_department(symptoms, pain_detection)
        checklist = self._build_checklist(cat_profile, urgency['level'], health_summary, pain_detection)

        health_snapshot = {
            'health_score': health_summary.get('health_score'),
            'status': health_summary.get('status'),
            'normalized_score': health_summary.get('normalized_score'),
            'anomaly_penalty': health_summary.get('components', {}).get('anomaly_penalty')
        }

        pain_snapshot = {
            'pain_score': pain_detection.get('pain_score'),
            'pain_likelihood': pain_detection.get('pain_likelihood'),
            'recommended_action': pain_detection.get('recommended_action')
        }

        checklist_text = json.dumps(checklist, ensure_ascii=False, indent=2)
        cat_name = cat_profile.get('name', '猫咪') if cat_profile else '猫咪'
        age = cat_profile.get('age', '未知') if cat_profile else '未知'

        prompt = f"""
你是猫咪健康分诊助手，根据已有评估生成中文就诊建议。

### 基础信息
- 猫咪: {cat_name}, 年龄: {age}
- 症状描述: {symptoms or '未提供'}

### 评估结果（保持紧急度不变）
- 紧急度: {urgency['level']} （{urgency['visit_window']}）
- 依据: {', '.join(urgency['reasons'])}
- 推荐科室: {department['department']}（{department['reason']}）

### 数据摘要
- 健康评分: {json.dumps(health_snapshot, ensure_ascii=False)}
- 疼痛检测: {json.dumps(pain_snapshot, ensure_ascii=False)}

### 就诊准备清单（可润色但保持数量）
{checklist_text}

输出 YAML：

```yaml
urgency: {urgency['level']}
visit_window: "{urgency['visit_window']}"
department: "{department['department']}"
reason: <一句话概括紧急度依据>
summary: <2-3句中文建议，包含时间要求、科室和注意事项>
actions:
  - <立即行动步骤>
  - <后续安排>
checklist:
  - item: <准备事项>
    detail: <简要说明>
```

务必输出有效的 YAML，保持紧急度等级不变。
"""

        llm_response = await async_call_llm(prompt)

        # Parse YAML using safe parser
        default_parsed = {
            'urgency': urgency['urgency'],
            'visit_window': urgency['visit_window'],
            'department': department['department'],
            'reason': '解析失败，请咨询兽医获取专业建议',
            'summary': '建议尽快咨询兽医以获得专业诊断和建议。',
            'actions': ['联系兽医咨询', '观察猫咪状态变化'],
            'checklist': checklist
        }
        parsed = safe_parse_yaml(llm_response, default=default_parsed)

        if not isinstance(parsed, dict):
            logger.warning("LLM response parsing failed, using default")
            parsed = default_parsed

        parsed_checklist = parsed.get('checklist')
        if not parsed_checklist or not isinstance(parsed_checklist, list):
            parsed_checklist = checklist

        return {
            'cat_id': prep_res['cat_id'],
            'urgency': urgency,
            'department': department,
            'health_snapshot': health_snapshot,
            'pain_snapshot': pain_snapshot,
            'summary': parsed.get('summary', ''),
            'actions': parsed.get('actions', []),
            'checklist': parsed_checklist,
            'llm_reason': parsed.get('reason', ''),
            'raw_llm': llm_response
        }

    async def post_async(self, shared, prep_res, exec_res):
        shared['vet_recommendation'] = exec_res
        return 'vet_recommendation_complete'


class DeviceStatusNode(AsyncNode):
    """
    Device status checker for collar and cat door devices using D1 data.
    Evaluates online status, heartbeat freshness, and battery level.
    """

    async def prep_async(self, shared):
        cat_id = shared['request'].get('cat_id', '1')

        cat_result = await execute_query(
            """
            SELECT id, user_id, collar_device_id
            FROM cats
            WHERE id = ?
            """,
            [cat_id]
        )

        cat_row = {}
        if cat_result.get("success") and cat_result.get("result", {}).get("results"):
            cat_row = cat_result["result"]["results"][0]

        collar_status = {}
        collar_device_id = cat_row.get('collar_device_id')
        if collar_device_id:
            collar_result = await execute_query(
                """
                SELECT device_serial, battery_level, online_status, last_heartbeat
                FROM collar_devices
                WHERE id = ?
                """,
                [collar_device_id]
            )
            if collar_result.get("success") and collar_result.get("result", {}).get("results"):
                collar_status = collar_result["result"]["results"][0]

        if not collar_status:
            fallback_result = await execute_query(
                """
                SELECT device_id AS device_serial, battery_level, online_status, last_heartbeat
                FROM device_status
                WHERE cat_id = ?
                LIMIT 1
                """,
                [cat_id]
            )
            if fallback_result.get("success") and fallback_result.get("result", {}).get("results"):
                collar_status = fallback_result["result"]["results"][0]

        cat_door_status = {}
        user_id = cat_row.get('user_id')
        if user_id:
            cat_door_result = await execute_query(
                """
                SELECT device_serial, online_status, last_heartbeat
                FROM cat_door_devices
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [user_id]
            )
            if cat_door_result.get("success") and cat_door_result.get("result", {}).get("results"):
                cat_door_status = cat_door_result["result"]["results"][0]

        return {
            'cat_id': cat_id,
            'collar_status': collar_status,
            'cat_door_status': cat_door_status
        }

    async def exec_async(self, prep_res):
        def evaluate_device(status: dict, heartbeat_minutes: int, battery_required: bool = True):
            issues = []
            if not status:
                issues.append('No device record found')
                return False, issues

            online_flag = status.get('online_status', 0) == 1
            last_heartbeat = status.get('last_heartbeat')
            heartbeat_ok = False

            if last_heartbeat:
                try:
                    heartbeat_time = datetime.fromisoformat(last_heartbeat)
                    heartbeat_ok = (datetime.now() - heartbeat_time) <= timedelta(minutes=heartbeat_minutes)
                except ValueError:
                    issues.append('Invalid heartbeat timestamp')
            else:
                issues.append('Missing heartbeat timestamp')

            if not online_flag:
                issues.append('Device reports offline')

            if battery_required:
                battery = status.get('battery_level')
                if battery is not None and battery < 20:
                    issues.append(f"Low battery: {battery}%")

            return online_flag and heartbeat_ok, issues

        collar_online, collar_issues = evaluate_device(prep_res.get('collar_status', {}), heartbeat_minutes=10)
        cat_door_online, cat_door_issues = evaluate_device(prep_res.get('cat_door_status', {}), heartbeat_minutes=15, battery_required=False)

        overall_ok = collar_online and (not prep_res.get('cat_door_status') or cat_door_online)
        status = 'ok' if overall_ok else 'attention'

        collar_status = dict(prep_res.get('collar_status', {}))
        collar_status.update({'online': collar_online, 'issues': collar_issues})

        cat_door_status = dict(prep_res.get('cat_door_status', {}))
        if cat_door_status:
            cat_door_status.update({'online': cat_door_online, 'issues': cat_door_issues})

        return {
            'cat_id': prep_res['cat_id'],
            'status': status,
            'collar': collar_status,
            'cat_door': cat_door_status,
            'overall_online': overall_ok
        }

    async def post_async(self, shared, prep_res, exec_res):
        shared['device_status_report'] = exec_res
        return 'device_status_checked'


class StatusSummaryNode(AsyncNode):
    """
    Data aggregation node for generating Markdown status summary.
    Loads cat profile, IoT logs, device status and generates human-readable report.
    """
    async def prep_async(self, shared):
        cat_id = shared['request'].get('cat_id', '1')

        # Load all data from SystemContext
        async with SystemContext(cat_id=cat_id) as ctx:
            cat_profile = await ctx.get_cat_profile(cat_id)
            recent_logs = await ctx.get_recent_iot_logs(cat_id, hours=24)
            device_status = await ctx.get_device_status(cat_id)

        # Aggregate sensor data (last 24h averages)
        sensor_aggregates = {}
        for log in recent_logs:
            sensor_type = log.get('sensor_type', 'unknown')
            value = log.get('value', 0)

            if sensor_type not in sensor_aggregates:
                sensor_aggregates[sensor_type] = []
            sensor_aggregates[sensor_type].append(value)

        # Calculate averages
        averages = {}
        for sensor_type, values in sensor_aggregates.items():
            if values:
                averages[sensor_type] = sum(values) / len(values)

        return {
            'cat_profile': cat_profile,
            'device_status': device_status,
            'sensor_averages': averages,
            'total_logs': len(recent_logs)
        }

    async def exec_async(self, prep_res):
        cat_profile = prep_res['cat_profile']
        device_status = prep_res['device_status']
        averages = prep_res['sensor_averages']

        # Build context for LLM
        summary_prompt = f"""
Generate a Markdown status summary for a cat health monitoring system.

### CAT PROFILE
- Name: {cat_profile.get('name', 'Unknown')}
- Breed: {cat_profile.get('breed', 'Unknown')}
- Age: {cat_profile.get('age', 'Unknown')} years

### DEVICE STATUS
- Device ID: {device_status.get('device_id', 'Unknown')}
- Online: {'Yes' if device_status.get('online_status') == 1 else 'No'}
- Battery: {device_status.get('battery_level', 0)}%
- Health: {device_status.get('health', 'Unknown')}

### 24H SENSOR AVERAGES
{json.dumps(averages, indent=2)}

### TASK
Generate a concise Markdown report with:
1. Cat overview
2. Current health metrics
3. Device status
4. Alerts (if any)

Format as Markdown with headers and bullet points.
"""

        summary_markdown = await async_call_llm(summary_prompt)

        return summary_markdown

    async def post_async(self, shared, prep_res, exec_res):
        # Store summary in shared
        shared['status_summary'] = exec_res

        return 'summary_complete'


class WeeklyReportNode(AsyncNode):
    """
    Weekly health report generation node for automated scheduled reporting.
    Aggregates 7 days of IoT sensor data, vision analysis, and medical history
    into a comprehensive Markdown report stored in R2.
    """
    async def prep_async(self, shared):
        cat_id = shared.get('cat_id', '1')

        # Load 7 days of data from SystemContext
        async with SystemContext(cat_id=cat_id) as ctx:
            # Get cat profile
            cat_profile = await ctx.get_cat_profile(cat_id)

            # Get 7 days of IoT logs (168 hours)
            iot_logs = await ctx.get_recent_iot_logs(cat_id, hours=168)

            # Get medical history
            medical_history = await ctx.get_medical_history(cat_id)

        # Query vision logs for last 7 days
        threshold = datetime.now() - timedelta(days=7)
        threshold_str = threshold.strftime("%Y-%m-%d %H:%M:%S")

        vision_result = await execute_query(
            "SELECT * FROM vision_logs WHERE cat_id = ? AND timestamp > ? ORDER BY timestamp DESC",
            [cat_id, threshold_str]
        )

        vision_logs = []
        if vision_result.get("success") and vision_result.get("result", {}).get("results"):
            vision_logs = vision_result["result"]["results"]

        # Aggregate sensor data (7 days)
        sensor_aggregates = {}
        anomaly_counts = {}

        for log in iot_logs:
            sensor_type = log.get('sensor_type', 'unknown')
            value = log.get('value', 0)
            anomaly_flag = log.get('anomaly_flag', 0)

            # Aggregate sensor values
            if sensor_type not in sensor_aggregates:
                sensor_aggregates[sensor_type] = []
            sensor_aggregates[sensor_type].append(value)

            # Count anomalies by sensor type
            if anomaly_flag == 1:
                anomaly_key = f"{sensor_type}_anomaly"
                anomaly_counts[anomaly_key] = anomaly_counts.get(anomaly_key, 0) + 1

        # Calculate statistics
        statistics = {}
        for sensor_type, values in sensor_aggregates.items():
            if values:
                statistics[sensor_type] = {
                    'mean': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'count': len(values)
                }

        # Parse vision analysis summaries
        vision_summaries = []
        for vision_log in vision_logs[:10]:  # Latest 10 vision analyses
            analysis_json = vision_log.get('analysis_result', '{}')
            try:
                analysis = json.loads(analysis_json)
                vision_summaries.append({
                    'timestamp': vision_log.get('timestamp'),
                    'overall_status': analysis.get('overall_status', 'unknown'),
                    'concerns': analysis.get('concerns', 'none')
                })
            except json.JSONDecodeError:
                pass

        # Filter medical consultations (last 7 days only)
        recent_medical_events = []
        for event in medical_history[:20]:  # Check latest 20 events
            event_timestamp = event.get('timestamp', '')
            if event_timestamp and event_timestamp >= threshold_str:
                recent_medical_events.append(event)

        return {
            'cat_profile': cat_profile,
            'statistics': statistics,
            'anomaly_counts': anomaly_counts,
            'vision_summaries': vision_summaries,
            'medical_events': recent_medical_events,
            'total_iot_logs': len(iot_logs),
            'total_vision_logs': len(vision_logs)
        }

    async def exec_async(self, prep_res):
        cat_profile = prep_res['cat_profile']
        statistics = prep_res['statistics']
        anomaly_counts = prep_res['anomaly_counts']
        vision_summaries = prep_res['vision_summaries']
        medical_events = prep_res['medical_events']

        # Build comprehensive context for LLM report generation
        report_prompt = f"""
Generate a comprehensive weekly health report for {cat_profile.get('name', 'Unknown Cat')}.

### CAT PROFILE
- Name: {cat_profile.get('name', 'Unknown')}
- Breed: {cat_profile.get('breed', 'Unknown')}
- Age: {cat_profile.get('age', 'Unknown')} years

### HEALTH METRICS (7-Day Statistics)
{json.dumps(statistics, indent=2)}

### ANOMALY SUMMARY (7 Days)
{json.dumps(anomaly_counts, indent=2)}

### BEHAVIOR ANALYSIS (Vision Insights)
{json.dumps(vision_summaries[:5], indent=2)}

### MEDICAL CONSULTATIONS (Recent Events)
{json.dumps(medical_events[:5], indent=2)}

### TASK
Generate a Markdown report with exactly 5 sections:

## Overview
- Brief summary of cat's overall health status
- Key highlights from the week

## Health Metrics
- Temperature trends (mean, min, max)
- Heart rate analysis
- Activity level patterns

## Anomaly Summary
- List of detected anomalies by type
- Severity assessment
- Trends compared to previous weeks

## Behavior Analysis
- Vision analysis insights
- Behavioral patterns observed
- Mood and activity correlations

## Recommendations
- Health maintenance suggestions
- Monitoring priorities
- Veterinary consultation needs (if any)

Format the entire report in clean Markdown with headers and bullet points.
"""

        report_markdown = await async_call_llm(report_prompt)

        return report_markdown

    async def post_async(self, shared, prep_res, exec_res):
        cat_id = shared.get('cat_id', '1')
        user_id = shared.get('user_id')  # Get user_id for R2 path

        # Generate report filename with current date
        report_date = datetime.now().strftime('%Y-%m-%d')
        filename = f'{report_date}.md'
        report_key = build_r2_path_safe(user_id, cat_id, 'weekly-reports', filename)

        # Upload report to R2
        report_bytes = exec_res.encode('utf-8')
        report_url = await upload_file(
            bucket='cat-reports',
            key=report_key,
            data=report_bytes
        )

        # Store report metadata in shared
        shared['weekly_report'] = {
            'cat_id': cat_id,
            'user_id': user_id,
            'report_date': report_date,
            'report_url': report_url,
            'report_content': exec_res
        }

        # Log report generation (notification can be added here)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Weekly report generated for cat {cat_id}: {report_url}")

        return 'report_generated'


class MonthlyReportNode(AsyncNode):
    """
    Monthly health report generation node.

    Aggregates 30 days of IoT, vision, and medical data to produce
    a Markdown monthly health report uploaded to R2.
    """

    async def prep_async(self, shared):
        cat_id = shared.get('cat_id', '1')

        # Load 30 days of data from SystemContext
        async with SystemContext(cat_id=cat_id) as ctx:
            cat_profile = await ctx.get_cat_profile(cat_id)
            iot_logs = await ctx.get_recent_iot_logs(cat_id, hours=720)
            medical_history = await ctx.get_medical_history(cat_id)

        # Query vision logs for last 30 days
        threshold = datetime.now() - timedelta(days=30)
        threshold_str = threshold.strftime("%Y-%m-%d %H:%M:%S")

        vision_result = await execute_query(
            "SELECT * FROM vision_logs WHERE cat_id = ? AND timestamp > ? ORDER BY timestamp DESC",
            [cat_id, threshold_str]
        )

        vision_logs = []
        if vision_result.get("success") and vision_result.get("result", {}).get("results"):
            vision_logs = vision_result["result"]["results"]

        # Aggregate sensor data (30 days)
        sensor_aggregates = {}
        anomaly_counts = {}

        for log in iot_logs:
            sensor_type = log.get('sensor_type', 'unknown')
            value = log.get('value', 0)
            anomaly_flag = log.get('anomaly_flag', 0)

            if sensor_type not in sensor_aggregates:
                sensor_aggregates[sensor_type] = []
            sensor_aggregates[sensor_type].append(value)

            if anomaly_flag == 1:
                anomaly_key = f"{sensor_type}_anomaly"
                anomaly_counts[anomaly_key] = anomaly_counts.get(anomaly_key, 0) + 1

        statistics = {}
        for sensor_type, values in sensor_aggregates.items():
            if values:
                statistics[sensor_type] = {
                    'mean': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'count': len(values)
                }

        # Parse vision analysis summaries
        vision_summaries = []
        for vision_log in vision_logs[:15]:
            analysis_json = vision_log.get('analysis_result', '{}')
            try:
                analysis = json.loads(analysis_json)
                vision_summaries.append({
                    'timestamp': vision_log.get('timestamp'),
                    'overall_status': analysis.get('overall_status', 'unknown'),
                    'concerns': analysis.get('concerns', 'none')
                })
            except json.JSONDecodeError:
                continue

        # Filter medical consultations for last 30 days
        recent_medical_events = []
        for event in medical_history[:50]:
            event_timestamp = event.get('timestamp', '')
            if event_timestamp and event_timestamp >= threshold_str:
                recent_medical_events.append(event)

        return {
            'cat_profile': cat_profile,
            'statistics': statistics,
            'anomaly_counts': anomaly_counts,
            'vision_summaries': vision_summaries,
            'medical_events': recent_medical_events,
            'total_iot_logs': len(iot_logs),
            'total_vision_logs': len(vision_logs)
        }

    async def exec_async(self, prep_res):
        cat_profile = prep_res['cat_profile']
        statistics = prep_res['statistics']
        anomaly_counts = prep_res['anomaly_counts']
        vision_summaries = prep_res['vision_summaries']
        medical_events = prep_res['medical_events']

        report_prompt = f"""
Generate a monthly health report for {cat_profile.get('name', 'Unknown Cat')} covering the last 30 days.

### CAT PROFILE
- Name: {cat_profile.get('name', 'Unknown')}
- Breed: {cat_profile.get('breed', 'Unknown')}
- Age: {cat_profile.get('age', 'Unknown')} years

### HEALTH METRICS (30-Day Statistics)
{json.dumps(statistics, indent=2)}

### ANOMALY SUMMARY (30 Days)
{json.dumps(anomaly_counts, indent=2)}

### BEHAVIOR ANALYSIS (Vision Insights)
{json.dumps(vision_summaries[:8], indent=2)}

### MEDICAL CONSULTATIONS (Recent Events)
{json.dumps(medical_events[:10], indent=2)}

### TASK
Generate a Markdown report with the following sections:

## Overview
- 2-3 bullet summary of overall health and key changes this month

## Vital Trends
- Temperature, heart rate, and activity patterns with highlights of rises/drops
- Note any stability or volatility across the month

## Behavioral Insights
- Vision-based observations and mood/behavior patterns
- Notable behaviors or changes observed

## Anomalies & Events
- Significant anomalies with frequency/severity context
- Medical consultations or interventions

## Recommendations
- Concrete next-step actions for caregivers
- Monitoring focus areas for the next month

## Next Month Watchlist
- Risk factors to watch and thresholds for alerts
- Preventative suggestions

Keep formatting clean Markdown with headers and bullet points, using concise language.
"""

        report_markdown = await async_call_llm(report_prompt)

        return report_markdown

    async def post_async(self, shared, prep_res, exec_res):
        cat_id = shared.get('cat_id', '1')
        user_id = shared.get('user_id')  # Get user_id for R2 path

        report_date = datetime.now().strftime('%Y-%m-%d')
        filename = f'{report_date}.md'
        report_key = build_r2_path_safe(user_id, cat_id, 'monthly-reports', filename)

        report_bytes = exec_res.encode('utf-8')
        report_url = await upload_file(
            bucket='cat-reports',
            key=report_key,
            data=report_bytes
        )

        shared['monthly_report'] = {
            'cat_id': cat_id,
            'user_id': user_id,
            'report_date': report_date,
            'report_url': report_url,
            'report_content': exec_res
        }

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Monthly report generated for cat {cat_id}: {report_url}")

        return 'monthly_report_generated'

class EmergencyAlertNode(AsyncNode):
    """
    Emergency and device alert node for critical health anomalies.

    Generates alert messages and sends push notifications.
    Logs alerts to D1 database.

    Alert Types:
    - emergency: Critical health (high fever, abnormal heart rate)
    - pain_detected: Pain detected from facial expression/BCG
    - outdoor_extended: Cat outdoors >4 hours
    - outdoor_night: Cat outdoors during night hours (22:00-06:00)
    - device_offline: Device connectivity issues (existing)
    """

    async def prep_async(self, shared):
        cat_id = shared['request'].get('cat_id', '1')

        # Load cat profile
        async with SystemContext(cat_id=cat_id) as ctx:
            cat_profile = await ctx.get_cat_profile(cat_id)

        # Detect alert type and gather context
        alert_type = 'emergency'  # default
        alert_context = {}

        # Check for outdoor alerts
        outdoor_alerts = shared.get('outdoor_alerts', [])
        if outdoor_alerts:
            first_alert = outdoor_alerts[0]
            if first_alert.get('type') == 'extended_outdoor':
                alert_type = 'outdoor_extended'
                alert_context = {
                    'duration_hours': first_alert.get('duration_hours', 0),
                    'started_at': first_alert.get('started_at', ''),
                    'location': first_alert.get('location', {})
                }
            elif first_alert.get('type') == 'night_outdoor':
                alert_type = 'outdoor_night'
                alert_context = {
                    'started_at': first_alert.get('started_at', ''),
                    'current_hour': first_alert.get('current_hour', 0)
                }

        # Check for pain alerts
        pain_result = shared.get('pain_detection_result', {})
        if pain_result.get('pain_score', 0) >= 6:
            alert_type = 'pain_detected'
            alert_context = {
                'pain_score': pain_result.get('pain_score', 0),
                'pain_likelihood': pain_result.get('pain_likelihood', 0),
                'indicators': pain_result.get('indicators', []),
                'bcg_correlation': pain_result.get('bcg_correlation', {})
            }

        # Check for cross-device correlation alerts
        correlation_report = shared.get('correlation_report', {})
        if correlation_report.get('highest_severity') == 'health_alert':
            alert_type = 'emergency'
            alert_context = {
                'correlation_type': 'cross_device',
                'correlations': correlation_report.get('correlations', [])
            }

        # Fall back to router anomaly details
        router_output = shared.get('router_output', {})
        anomaly_details = router_output.get('anomaly_details', {})

        return {
            'cat_id': cat_id,
            'cat_name': cat_profile.get('name', 'Unknown'),
            'alert_type': alert_type,
            'alert_context': alert_context,
            'anomaly_details': anomaly_details
        }

    async def exec_async(self, prep_res):
        cat_name = prep_res['cat_name']
        alert_type = prep_res['alert_type']
        alert_context = prep_res['alert_context']
        anomaly_details = prep_res['anomaly_details']

        # Build context string based on alert type
        if alert_type == 'pain_detected':
            context_text = f"""
Pain Detection Alert:
- Pain Score: {alert_context.get('pain_score', 0)}/10
- Pain Likelihood: {alert_context.get('pain_likelihood', 0) * 100:.0f}%
- Indicators: {', '.join(alert_context.get('indicators', []))}
- BCG Correlation: Heart rate elevated during pain detection
"""
        elif alert_type == 'outdoor_extended':
            context_text = f"""
Extended Outdoor Alert:
- Duration: {alert_context.get('duration_hours', 0):.1f} hours outdoors
- Started At: {alert_context.get('started_at', 'Unknown')}
- Last Known Location: {alert_context.get('location', {})}
"""
        elif alert_type == 'outdoor_night':
            context_text = f"""
Night Outdoor Alert:
- Current Time: {alert_context.get('current_hour', 0)}:00 (Night hours: 22:00-06:00)
- Started Outdoor At: {alert_context.get('started_at', 'Unknown')}
- Safety Concern: Reduced visibility and increased risks
"""
        else:
            # Default emergency context
            anomaly_summary = []
            for sensor_type, details in anomaly_details.items():
                value = details.get('value', 0)
                duration = details.get('duration', 0)
                severity = details.get('severity', 'unknown')
                anomaly_summary.append(f"- {sensor_type}: {value} (duration: {duration:.1f}s, severity: {severity})")
            context_text = "\n".join(anomaly_summary) if anomaly_summary else "Health anomaly detected"

        # Generate alert message
        alert_prompt = f"""
Generate an alert message for a cat health/safety concern.

### CAT INFORMATION
- Name: {cat_name}

### ALERT TYPE
{alert_type}

### DETAILS
{context_text}

### TASK
Generate a clear, actionable alert message.
The message should:
1. State the concern clearly
2. Provide relevant details
3. Recommend appropriate action

Return in YAML:

```yaml
title: <short alert title>
body: <detailed alert message>
recommendation: <action to take>
urgency: <low|medium|high|critical>
```
"""

        response = await async_call_llm(alert_prompt)

        # Parse YAML using safe parser
        default_alert = {
            'title': f'{prep_res.get("alert_type", "Health").replace("_", " ").title()} Alert',
            'body': 'A health anomaly has been detected. Please check your cat.',
            'recommendation': 'Monitor your cat closely and consult a veterinarian if symptoms persist.',
            'urgency': 'medium'
        }
        alert_data = safe_parse_yaml(response, default=default_alert)

        # Ensure required fields exist
        if not isinstance(alert_data, dict):
            logger.warning("Alert data parsing failed, using default")
            alert_data = default_alert
        if "title" not in alert_data:
            alert_data['title'] = default_alert['title']
        if "body" not in alert_data:
            alert_data['body'] = default_alert['body']

        return alert_data

    async def post_async(self, shared, prep_res, exec_res):
        cat_id = prep_res['cat_id']
        alert_type = prep_res['alert_type']
        alert_context = prep_res['alert_context']
        anomaly_details = prep_res['anomaly_details']

        # Send push notification
        notification_message = {
            "type": alert_type,
            "title": exec_res.get("title", f"{alert_type.replace('_', ' ').title()} Alert"),
            "body": exec_res.get("body", ""),
            "data": {
                "alert_type": alert_type,
                "alert_context": alert_context,
                "anomaly_details": anomaly_details,
                "recommendation": exec_res.get("recommendation", ""),
                "urgency": exec_res.get("urgency", "high"),
                "timestamp": datetime.now().isoformat()
            }
        }

        notification_sent = await send_notification(cat_id, notification_message)

        # Log alert to D1 database
        await execute_query(
            """
            INSERT INTO alert_logs (cat_id, alert_type, alert_title, alert_body,
                                   anomaly_details, notification_sent, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                cat_id,
                alert_type,
                exec_res.get("title", ""),
                exec_res.get("body", ""),
                json.dumps({**anomaly_details, **alert_context}),
                1 if notification_sent else 0,
                datetime.now().isoformat()
            ]
        )

        # Store in shared
        shared['emergency_alert'] = {
            'cat_id': cat_id,
            'alert_type': alert_type,
            'alert_data': exec_res,
            'notification_sent': notification_sent,
            'timestamp': datetime.now().isoformat()
        }

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"{alert_type} alert sent for cat {cat_id}: {exec_res.get('title')}")

        return 'alert_sent'

class DeviceOfflineAlertNode(AsyncNode):
    """
    Device offline alert node for Path B (device connectivity issues).
    
    Monitors device status and sends alerts for:
    - Device offline (last heartbeat >5 minutes ago)
    - Low battery (<10%)
    """
    
    async def prep_async(self, shared):
        cat_id = shared['request'].get('cat_id', '1')
        
        # Load device status and cat profile
        async with SystemContext(cat_id=cat_id) as ctx:
            device_status = await ctx.get_device_status(cat_id)
            cat_profile = await ctx.get_cat_profile(cat_id)
        
        # Check device offline condition
        last_heartbeat_str = device_status.get('last_heartbeat', '')
        battery_level = device_status.get('battery_level', 100)
        
        offline_issue = False
        offline_reason = []
        
        if last_heartbeat_str:
            try:
                last_heartbeat = datetime.fromisoformat(last_heartbeat_str)
                time_since_heartbeat = (datetime.now() - last_heartbeat).total_seconds()
                
                # Check if last heartbeat >5 minutes ago
                if time_since_heartbeat > 300:  # 5 minutes = 300 seconds
                    offline_issue = True
                    offline_reason.append(f"No heartbeat for {time_since_heartbeat/60:.1f} minutes")
            except ValueError:
                offline_issue = True
                offline_reason.append("Invalid heartbeat timestamp")
        else:
            offline_issue = True
            offline_reason.append("No heartbeat data available")
        
        # Check battery level
        if battery_level < 10:
            offline_issue = True
            offline_reason.append(f"Critical battery level: {battery_level}%")
        
        return {
            'cat_id': cat_id,
            'cat_name': cat_profile.get('name', 'Unknown'),
            'device_id': device_status.get('device_id', 'Unknown'),
            'offline_issue': offline_issue,
            'offline_reason': offline_reason,
            'battery_level': battery_level,
            'last_heartbeat': last_heartbeat_str
        }
    
    async def exec_async(self, prep_res):
        cat_name = prep_res['cat_name']
        device_id = prep_res['device_id']
        offline_reason = prep_res['offline_reason']
        battery_level = prep_res['battery_level']
        
        # Build offline reason text
        reason_text = "\n".join([f"- {reason}" for reason in offline_reason])
        
        # Generate alert message using LLM
        alert_prompt = f"""
Generate an alert message for a device connectivity issue.

### CAT INFORMATION
- Name: {cat_name}
- Device ID: {device_id}

### DEVICE ISSUES
{reason_text}
- Battery Level: {battery_level}%

### TASK
Generate a clear alert message for the cat owner about the device issue.
The message should:
1. Explain the connectivity problem
2. Provide device status details
3. Recommend troubleshooting steps

Return in YAML format:

```yaml
title: <short alert title>
body: <detailed alert message>
recommendation: <troubleshooting steps>
urgency: <medium|high>
```
"""
        
        response = await async_call_llm(alert_prompt)

        # Parse YAML response using safe parser
        default_alert = {
            'title': 'Device Offline Alert',
            'body': f'Device {prep_res.get("device_id", "unknown")} appears to be offline. Please check the device status.',
            'recommendation': 'Check if the device is powered on and within WiFi range. Try restarting the device.',
            'urgency': 'medium'
        }
        alert_data = safe_parse_yaml(response, default=default_alert)

        # Ensure required fields exist
        if not isinstance(alert_data, dict):
            logger.warning("Device alert parsing failed, using default")
            alert_data = default_alert
        if "title" not in alert_data:
            alert_data['title'] = default_alert['title']
        if "body" not in alert_data:
            alert_data['body'] = default_alert['body']

        return alert_data
    
    async def post_async(self, shared, prep_res, exec_res):
        cat_id = prep_res['cat_id']
        device_id = prep_res['device_id']
        offline_reason = prep_res['offline_reason']
        
        # Send push notification
        notification_message = {
            "type": "warning",
            "title": exec_res.get("title", "Device Offline Alert"),
            "body": exec_res.get("body", ""),
            "data": {
                "device_id": device_id,
                "offline_reason": offline_reason,
                "battery_level": prep_res.get('battery_level', 0),
                "recommendation": exec_res.get("recommendation", ""),
                "urgency": exec_res.get("urgency", "medium"),
                "timestamp": datetime.now().isoformat()
            }
        }
        
        notification_sent = await send_notification(cat_id, notification_message)
        
        # Log alert to D1 database
        await execute_query(
            """
            INSERT INTO alert_logs (cat_id, alert_type, alert_title, alert_body, 
                                   anomaly_details, notification_sent, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                cat_id,
                "device_offline",
                exec_res.get("title", ""),
                exec_res.get("body", ""),
                json.dumps({
                    "device_id": device_id,
                    "offline_reason": offline_reason
                }),
                1 if notification_sent else 0,
                datetime.now().isoformat()
            ]
        )
        
        # Store alert in shared
        shared['device_offline_alert'] = {
            'cat_id': cat_id,
            'device_id': device_id,
            'alert_data': exec_res,
            'notification_sent': notification_sent,
            'timestamp': datetime.now().isoformat()
        }
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Device offline alert sent for cat {cat_id}, device {device_id}")

        return 'alert_sent'


class MultiCatHealthAnalysisNode(AsyncParallelBatchNode):
    """
    Multi-cat batch processing node using AsyncParallelBatchNode.

    Analyzes health metrics for all active cats concurrently and generates
    comparative analysis report with statistical aggregation.

    Workflow:
    1. prep_async: Query D1 for all active cats
    2. exec_async: Parallel health score calculation per cat
    3. post_async: Aggregate results, generate comparative report
    """

    async def prep_async(self, shared):
        # Query D1 for all active cats
        result = await execute_query(
            "SELECT id, name FROM cats WHERE active = 1",
            []
        )

        # Extract cat data from query result
        cats = []
        if result.get("success") and result.get("result", {}).get("results"):
            cats = result["result"]["results"]

        # Return list of cat_ids (iterable for batch processing)
        cat_list = [
            {'cat_id': cat['id'], 'cat_name': cat['name']}
            for cat in cats
        ]

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Found {len(cat_list)} active cats for analysis")

        return cat_list

    async def exec_async(self, cat_data):
        """
        Execute health analysis for a single cat.

        Args:
            cat_data: dict with cat_id and cat_name

        Returns:
            dict: Health analysis result with score and metrics
        """
        cat_id = cat_data['cat_id']
        cat_name = cat_data['cat_name']

        # Load cat data from SystemContext
        async with SystemContext(cat_id=cat_id) as ctx:
            recent_logs = await ctx.get_recent_iot_logs(cat_id, hours=24)
            medical_history = await ctx.get_medical_history(cat_id)
            device_status = await ctx.get_device_status(cat_id)

        # Aggregate sensor data
        sensor_aggregates = {}
        for log in recent_logs:
            sensor_type = log.get('sensor_type', 'unknown')
            value = log.get('value', 0)

            if sensor_type not in sensor_aggregates:
                sensor_aggregates[sensor_type] = []
            sensor_aggregates[sensor_type].append(value)

        # Calculate metrics
        metrics = {}
        for sensor_type, values in sensor_aggregates.items():
            if values:
                metrics[sensor_type] = {
                    'mean': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values)
                }

        # Health scoring criteria
        temp_normal = 1.0 if metrics.get('temperature', {}).get('mean', 38.5) <= 39.2 else 0.0
        heart_rate_normal = 1.0 if 140 <= metrics.get('heart_rate', {}).get('mean', 160) <= 220 else 0.0
        activity_normal = 1.0 if metrics.get('activity', {}).get('mean', 50) >= 20 else 0.0

        # Check for anomalies
        anomaly_count = sum(1 for log in recent_logs if log.get('anomaly_flag') == 1)
        no_anomalies = 1.0 if anomaly_count == 0 else max(0.0, 1.0 - (anomaly_count / len(recent_logs)))

        # Calculate health_score: weighted formula
        health_score = (
            temp_normal * 0.3 +
            heart_rate_normal * 0.3 +
            activity_normal * 0.2 +
            no_anomalies * 0.2
        )

        # Build metrics summary
        metrics_summary = {
            'temperature': metrics.get('temperature', {}),
            'heart_rate': metrics.get('heart_rate', {}),
            'activity': metrics.get('activity', {}),
            'anomaly_count': anomaly_count,
            'medical_events_count': len(medical_history),
            'device_online': device_status.get('online_status', 0) == 1,
            'battery_level': device_status.get('battery_level', 0)
        }

        return {
            'cat_id': cat_id,
            'name': cat_name,
            'health_score': health_score,
            'metrics_summary': metrics_summary
        }

    async def post_async(self, shared, prep_res, exec_res_list):
        """
        Aggregate all cat results and generate comparative report.

        Args:
            shared: Shared store
            prep_res: List of cat data from prep_async
            exec_res_list: List of health analysis results from exec_async

        Returns:
            str: Action for flow routing
        """
        # Aggregate all cat results
        cat_count = len(exec_res_list)

        if cat_count == 0:
            shared['multi_cat_report'] = "No active cats found for analysis"
            return 'analysis_complete'

        # Calculate comparative stats
        health_scores = [result['health_score'] for result in exec_res_list]
        mean_health_score = sum(health_scores) / len(health_scores)

        # Calculate median
        sorted_scores = sorted(health_scores)
        n = len(sorted_scores)
        if n % 2 == 0:
            median = (sorted_scores[n//2 - 1] + sorted_scores[n//2]) / 2
        else:
            median = sorted_scores[n//2]

        # Calculate standard deviation
        variance = sum((x - mean_health_score) ** 2 for x in health_scores) / len(health_scores)
        std_dev = variance ** 0.5

        # Identify outliers: health_score < mean - 2*std_dev
        outlier_threshold = mean_health_score - 2 * std_dev
        outliers = [
            result for result in exec_res_list
            if result['health_score'] < outlier_threshold
        ]

        # Rank cats by health score (highest first)
        ranked_cats = sorted(exec_res_list, key=lambda x: x['health_score'], reverse=True)

        # Build context for LLM comparative report
        report_context = {
            'total_cats': cat_count,
            'mean_health_score': mean_health_score,
            'median_health_score': median,
            'std_dev': std_dev,
            'outlier_count': len(outliers),
            'ranked_cats': ranked_cats[:10],  # Top 10 for report
            'outliers': outliers
        }

        # Generate comparative report using LLM
        report_prompt = f"""
Generate a comprehensive multi-cat health analysis report.

### SUMMARY STATISTICS
- Total Cats Analyzed: {cat_count}
- Mean Health Score: {mean_health_score:.2f}
- Median Health Score: {median:.2f}
- Standard Deviation: {std_dev:.2f}
- Outliers (< mean - 2*std_dev): {len(outliers)}

### TOP PERFORMERS (Highest Health Scores)
{json.dumps(ranked_cats[:5], indent=2)}

### CATS REQUIRING ATTENTION (Outliers)
{json.dumps(outliers, indent=2)}

### TASK
Generate a Markdown report with:
1. Executive Summary - Overall health status of the cat population
2. Top Performers - Highlight cats with excellent health scores
3. Attention Required - Cats with health scores below threshold
4. Recommendations - Population-wide health improvement suggestions

Format as clean Markdown with headers and bullet points.
"""

        comparative_report = await async_call_llm(report_prompt)

        # Store in shared
        shared['multi_cat_report'] = comparative_report
        shared['multi_cat_stats'] = report_context

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Multi-cat analysis complete: {cat_count} cats analyzed, {len(outliers)} outliers detected")

        return 'analysis_complete'


class MultiCatComparisonNode(AsyncNode):
    """
    Multi-cat comparison node for cross-cat health benchmarking.

    Builds aggregated metrics for multiple cats over the last 7 days and
    generates a Markdown comparison report using LLM.
    """

    async def prep_async(self, shared):
        request_cat_ids = shared.get('request', {}).get('cat_ids') or shared.get('comparison_cat_ids')

        cat_rows = []
        if request_cat_ids:
            placeholders = ','.join(['?'] * len(request_cat_ids))
            query = f"SELECT id, name FROM cats WHERE id IN ({placeholders})"
            cat_result = await execute_query(query, request_cat_ids)
        else:
            cat_result = await execute_query(
                "SELECT id, name FROM cats WHERE active = 1",
                []
            )

        if cat_result.get("success") and cat_result.get("result", {}).get("results"):
            cat_rows = cat_result["result"]["results"]

        cat_list = [
            {'cat_id': str(cat.get('id')), 'cat_name': cat.get('name', 'Unknown')}
            for cat in cat_rows
        ]

        summaries = []
        for cat in cat_list:
            cat_id = cat['cat_id']
            cat_name = cat['cat_name']

            async with SystemContext(cat_id=cat_id) as ctx:
                recent_logs = await ctx.get_recent_iot_logs(cat_id, hours=168)
                medical_history = await ctx.get_medical_history(cat_id)
                device_status = await ctx.get_device_status(cat_id)

            sensor_aggregates = {}
            anomaly_count = 0

            for log in recent_logs:
                sensor_type = log.get('sensor_type', 'unknown')
                value = log.get('value', 0)
                anomaly_flag = log.get('anomaly_flag', 0)

                if sensor_type not in sensor_aggregates:
                    sensor_aggregates[sensor_type] = []
                sensor_aggregates[sensor_type].append(value)

                if anomaly_flag == 1:
                    anomaly_count += 1

            metrics = {}
            for sensor_type, values in sensor_aggregates.items():
                if values:
                    metrics[sensor_type] = {
                        'mean': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values),
                        'count': len(values)
                    }

            temp_mean = metrics.get('temperature', {}).get('mean', 0)
            heart_rate_mean = metrics.get('heart_rate', {}).get('mean', 0)
            activity_mean = metrics.get('activity', {}).get('mean', 0)

            no_anomaly_score = 1.0
            if recent_logs:
                no_anomaly_score = 1.0 if anomaly_count == 0 else max(0.0, 1.0 - (anomaly_count / len(recent_logs)))

            health_score = (
                (1.0 if 37.5 <= temp_mean <= 39.2 else 0.0) * 0.3 +
                (1.0 if 140 <= heart_rate_mean <= 220 else 0.0) * 0.3 +
                (1.0 if activity_mean >= 20 else 0.0) * 0.2 +
                no_anomaly_score * 0.2
            )

            summaries.append({
                'cat_id': cat_id,
                'name': cat_name,
                'health_score': health_score,
                'metrics': metrics,
                'anomaly_count': anomaly_count,
                'medical_events': len(medical_history),
                'device_online': device_status.get('online_status', 0) == 1,
                'battery_level': device_status.get('battery_level', 0)
            })

        return {
            'cat_summaries': summaries
        }

    async def exec_async(self, prep_res):
        cat_summaries = prep_res['cat_summaries']

        if not cat_summaries:
            return "No cats available for comparison"

        score_list = [entry['health_score'] for entry in cat_summaries]
        mean_score = sum(score_list) / len(score_list)

        ranked_cats = sorted(cat_summaries, key=lambda x: x['health_score'], reverse=True)
        at_risk = [entry for entry in cat_summaries if entry['health_score'] < 0.6 or entry.get('anomaly_count', 0) > 0]

        report_prompt = f"""
Generate a multi-cat comparison report in Markdown.

### POPULATION STATS
- Total cats: {len(cat_summaries)}
- Mean health score: {mean_score:.2f}
- Top cat: {ranked_cats[0]['name']} ({ranked_cats[0]['health_score']:.2f})
- Cats needing attention: {len(at_risk)}

### CAT METRICS (Last 7 Days)
{json.dumps(cat_summaries[:12], indent=2)}

### TASK
Create a Markdown report with:

## Population Overview
- Health score distribution and notable differences

## Comparative Metrics
- Temperature, heart rate, and activity comparisons across cats
- Highlight top performers and lagging metrics

## Alerts
- Cats with low scores or frequent anomalies
- Device offline or low battery cases

## Recommendations
- Group-level guidance for caregivers
- Targeted actions for at-risk cats

Use concise bullet lists and clear section headers.
"""

        comparison_report = await async_call_llm(report_prompt)

        return {
            'report': comparison_report,
            'mean_score': mean_score,
            'ranked_cats': ranked_cats,
            'at_risk': at_risk
        }

    async def post_async(self, shared, prep_res, exec_res):
        shared['multi_cat_comparison'] = exec_res.get('report') if isinstance(exec_res, dict) else exec_res
        shared['multi_cat_comparison_stats'] = exec_res if isinstance(exec_res, dict) else {}

        return 'comparison_complete'


class CollarDataIngestionNode(AsyncNode):
    """
    Collar device data ingestion node for processing webhook data from collar devices.

    Handles 3 data types:
    1. activity_data: Steps, calories, active minutes
    2. outdoor_status: GPS location, outdoor/indoor status
    3. bcg_heart_rate: Heart rate, HRV, respiratory rate with anomaly detection

    Routes data to appropriate tables:
    - activity_data -> collar_activity_logs
    - outdoor_status -> collar_outdoor_logs
    - bcg_heart_rate -> collar_bcg_logs (with anomaly detection)
    """

    async def prep_async(self, shared):
        # Extract collar webhook data from shared store
        collar_data = shared.get('collar_data', {})

        # Validate required fields
        data_type = collar_data.get('data_type')
        device_serial = collar_data.get('collar_device_id')  # This is actually device_serial from webhook
        cat_id = collar_data.get('cat_id')

        if not data_type:
            raise ValueError("Missing 'data_type' in collar_data")
        if not device_serial:
            raise ValueError("Missing 'collar_device_id' in collar_data")
        if not cat_id:
            raise ValueError("Missing 'cat_id' in collar_data")

        # Validate data_type is one of the 3 supported types
        valid_types = ['activity_data', 'outdoor_status', 'bcg_heart_rate']
        if data_type not in valid_types:
            raise ValueError(f"Invalid data_type: {data_type}. Must be one of {valid_types}")

        # Look up the internal collar_device_id from device_serial
        device_result = await execute_query(
            "SELECT id FROM collar_devices WHERE device_serial = ?",
            [device_serial]
        )

        if not device_result.get('success') or not device_result.get('result', {}).get('results'):
            raise ValueError(f"Collar device not found for serial: {device_serial}")

        collar_device_id = device_result['result']['results'][0]['id']

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Resolved collar device serial {device_serial} to id {collar_device_id}")

        return {
            'data_type': data_type,
            'collar_device_id': collar_device_id,
            'device_serial': device_serial,
            'cat_id': cat_id,
            'payload': collar_data.get('payload', {})
        }

    async def exec_async(self, prep_res):
        data_type = prep_res['data_type']
        payload = prep_res['payload']

        # Route data by type and detect anomalies
        if data_type == 'activity_data':
            # Activity data: steps, calories, active_minutes
            activity_type = payload.get('activity_type')
            value = payload.get('value')
            unit = payload.get('unit')

            if not activity_type or value is None or not unit:
                raise ValueError(f"Invalid activity_data payload: {payload}")

            return {
                'data_type': 'activity_data',
                'activity_type': activity_type,
                'value': value,
                'unit': unit,
                'anomaly_flag': 0
            }

        elif data_type == 'outdoor_status':
            # Outdoor status: GPS location, outdoor/indoor flag
            is_outdoor = payload.get('is_outdoor')
            location_lat = payload.get('location_lat')
            location_lng = payload.get('location_lng')
            started_at = payload.get('started_at')

            if is_outdoor is None:
                raise ValueError(f"Invalid outdoor_status payload: {payload}")

            return {
                'data_type': 'outdoor_status',
                'is_outdoor': is_outdoor,
                'location_lat': location_lat,
                'location_lng': location_lng,
                'started_at': started_at,
                'anomaly_flag': 0
            }

        elif data_type == 'bcg_heart_rate':
            # BCG heart rate: heart_rate_bpm, hrv_ms, respiratory_rate
            heart_rate_bpm = payload.get('heart_rate_bpm')
            hrv_ms = payload.get('hrv_ms')
            respiratory_rate = payload.get('respiratory_rate')

            if heart_rate_bpm is None:
                raise ValueError(f"Invalid bcg_heart_rate payload: {payload}")

            # Anomaly detection for BCG metrics
            anomaly_flag = 0
            anomaly_reasons = []

            # Heart rate anomaly: >180 or <100 bpm
            if heart_rate_bpm > 180:
                anomaly_flag = 1
                anomaly_reasons.append(f"High heart rate: {heart_rate_bpm} bpm (>180)")
            elif heart_rate_bpm < 100:
                anomaly_flag = 1
                anomaly_reasons.append(f"Low heart rate: {heart_rate_bpm} bpm (<100)")

            # HRV anomaly: <20ms or >100ms (if provided)
            if hrv_ms is not None:
                if hrv_ms < 20:
                    anomaly_flag = 1
                    anomaly_reasons.append(f"Low HRV: {hrv_ms} ms (<20)")
                elif hrv_ms > 100:
                    anomaly_flag = 1
                    anomaly_reasons.append(f"High HRV: {hrv_ms} ms (>100)")

            return {
                'data_type': 'bcg_heart_rate',
                'heart_rate_bpm': heart_rate_bpm,
                'hrv_ms': hrv_ms,
                'respiratory_rate': respiratory_rate,
                'anomaly_flag': anomaly_flag,
                'anomaly_reasons': anomaly_reasons
            }

        else:
            raise ValueError(f"Unsupported data_type: {data_type}")

    async def post_async(self, shared, prep_res, exec_res):
        collar_device_id = prep_res['collar_device_id']
        cat_id = prep_res['cat_id']
        data_type = exec_res['data_type']
        timestamp = datetime.now().isoformat()

        # Write to appropriate log table based on data type
        if data_type == 'activity_data':
            # Insert into collar_activity_logs
            await execute_query(
                """
                INSERT INTO collar_activity_logs
                (collar_device_id, cat_id, activity_type, value, unit, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    collar_device_id,
                    cat_id,
                    exec_res['activity_type'],
                    exec_res['value'],
                    exec_res['unit'],
                    timestamp
                ]
            )

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Activity data ingested for cat {cat_id}: {exec_res['activity_type']} = {exec_res['value']} {exec_res['unit']}")

            # Store result in shared
            shared['collar_ingestion_result'] = {
                'status': 'success',
                'data_type': 'activity_data',
                'cat_id': cat_id,
                'timestamp': timestamp
            }

            return 'default'

        elif data_type == 'outdoor_status':
            # Insert into collar_outdoor_logs
            await execute_query(
                """
                INSERT INTO collar_outdoor_logs
                (collar_device_id, cat_id, is_outdoor, location_lat, location_lng, started_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    collar_device_id,
                    cat_id,
                    exec_res['is_outdoor'],
                    exec_res.get('location_lat'),
                    exec_res.get('location_lng'),
                    exec_res.get('started_at')
                ]
            )

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Outdoor status ingested for cat {cat_id}: is_outdoor={exec_res['is_outdoor']}")

            # Store result in shared
            shared['collar_ingestion_result'] = {
                'status': 'success',
                'data_type': 'outdoor_status',
                'cat_id': cat_id,
                'is_outdoor': exec_res['is_outdoor'],
                'timestamp': timestamp
            }

            return 'default'

        elif data_type == 'bcg_heart_rate':
            # Insert into collar_bcg_logs
            await execute_query(
                """
                INSERT INTO collar_bcg_logs
                (collar_device_id, cat_id, heart_rate_bpm, hrv_ms, respiratory_rate, anomaly_flag, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    collar_device_id,
                    cat_id,
                    exec_res['heart_rate_bpm'],
                    exec_res.get('hrv_ms'),
                    exec_res.get('respiratory_rate'),
                    exec_res['anomaly_flag'],
                    timestamp
                ]
            )

            import logging
            logger = logging.getLogger(__name__)

            if exec_res['anomaly_flag'] == 1:
                anomaly_reasons = exec_res.get('anomaly_reasons', [])
                logger.warning(f"BCG anomaly detected for cat {cat_id}: {', '.join(anomaly_reasons)}")

                # Store result in shared
                shared['collar_ingestion_result'] = {
                    'status': 'anomaly_detected',
                    'data_type': 'bcg_heart_rate',
                    'cat_id': cat_id,
                    'heart_rate_bpm': exec_res['heart_rate_bpm'],
                    'anomaly_reasons': anomaly_reasons,
                    'timestamp': timestamp
                }

                return 'anomaly_alert'
            else:
                logger.info(f"BCG data ingested for cat {cat_id}: heart_rate={exec_res['heart_rate_bpm']} bpm")

                # Store result in shared
                shared['collar_ingestion_result'] = {
                    'status': 'success',
                    'data_type': 'bcg_heart_rate',
                    'cat_id': cat_id,
                    'heart_rate_bpm': exec_res['heart_rate_bpm'],
                    'timestamp': timestamp
                }

                return 'default'

        else:
            raise ValueError(f"Unsupported data_type: {data_type}")


class CatDoorEventNode(AsyncNode):
    """
    Cat door event processing node for passage activity and cat identification.

    Processes two types of events:
    1. passage_activity: Cat entering/exiting through the door
    2. cat_identification: Identifying which cat passed through (RFID/vision/beacon)

    Data Flow:
    - Reads cat door event from shared store
    - Extracts passage details (direction, cat_id, identification method)
    - Writes to cat_door_passage_logs table
    - Triggers VisionAnalysisNode if image_url available for facial expression analysis
    """

    async def prep_async(self, shared):
        """
        Extract cat door event data from shared store.

        Returns:
            dict: Cat door event with fields:
                - cat_door_device_id: Internal device ID (resolved from device_serial)
                - device_serial: Original device serial from webhook
                - cat_id: Identified cat ID (from RFID/vision/beacon)
                - direction: 'in' or 'out'
                - identification_method: 'rfid', 'vision', or 'beacon'
                - identification_confidence: 0.0-1.0 confidence score
                - image_url: Optional - image captured during passage
                - timestamp: Event timestamp
        """
        cat_door_event = shared.get('cat_door_event', {})

        # Validate required fields
        if not cat_door_event:
            raise ValueError("No cat_door_event found in shared store")

        required_fields = ['cat_door_device_id', 'cat_id', 'direction',
                          'identification_method', 'identification_confidence']
        missing_fields = [field for field in required_fields if field not in cat_door_event]

        if missing_fields:
            raise ValueError(f"Missing required fields in cat_door_event: {missing_fields}")

        # Validate direction
        direction = cat_door_event.get('direction', '').lower()
        if direction not in ['in', 'out']:
            raise ValueError(f"Invalid direction: {direction}. Must be 'in' or 'out'")

        # Validate identification_method
        identification_method = cat_door_event.get('identification_method', '').lower()
        valid_methods = ['rfid', 'vision', 'beacon']
        if identification_method not in valid_methods:
            raise ValueError(f"Invalid identification_method: {identification_method}. Must be one of {valid_methods}")

        # Validate confidence range
        confidence = cat_door_event.get('identification_confidence', 0.0)
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Invalid identification_confidence: {confidence}. Must be between 0.0 and 1.0")

        # Look up the internal cat_door_device_id from device_serial
        device_serial = cat_door_event['cat_door_device_id']  # This is actually device_serial from webhook
        device_result = await execute_query(
            "SELECT id FROM cat_door_devices WHERE device_serial = ?",
            [device_serial]
        )

        if not device_result.get('success') or not device_result.get('result', {}).get('results'):
            raise ValueError(f"Cat door device not found for serial: {device_serial}")

        cat_door_device_id = device_result['result']['results'][0]['id']

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Processing cat door event: cat_id={cat_door_event.get('cat_id')}, "
                   f"direction={direction}, method={identification_method}, "
                   f"confidence={confidence:.2f}, device_id={cat_door_device_id}")

        # Return event with resolved internal device ID
        resolved_event = cat_door_event.copy()
        resolved_event['device_serial'] = device_serial
        resolved_event['cat_door_device_id'] = cat_door_device_id

        return resolved_event

    async def exec_async(self, event_data):
        """
        Process cat door passage event.

        Args:
            event_data: Validated cat door event data

        Returns:
            dict: Processed passage log data ready for database insertion
        """
        # Extract event fields
        cat_door_device_id = event_data['cat_door_device_id']
        cat_id = event_data['cat_id']
        direction = event_data['direction'].lower()
        identification_method = event_data['identification_method'].lower()
        identification_confidence = event_data['identification_confidence']
        image_url = event_data.get('image_url', None)
        timestamp = event_data.get('timestamp', datetime.now().isoformat())

        # Prepare passage log data
        passage_log = {
            'cat_door_device_id': cat_door_device_id,
            'cat_id': cat_id,
            'direction': direction,
            'identification_method': identification_method,
            'identification_confidence': identification_confidence,
            'timestamp': timestamp,
            'image_url': image_url
        }

        return passage_log

    async def post_async(self, shared, prep_res, exec_res):
        """
        Write passage log to database and determine next action.

        Args:
            shared: Shared store
            prep_res: Original event data from prep_async
            exec_res: Processed passage log from exec_async

        Returns:
            str: Action for flow routing
                - 'vision_analysis': If image_url present (trigger facial expression analysis)
                - 'default': No image, passage logged only
        """
        # Write to cat_door_passage_logs table with RETURNING id
        insert_result = await execute_query(
            """
            INSERT INTO cat_door_passage_logs
                (cat_door_device_id, cat_id, direction, identification_method,
                 identification_confidence, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            [
                exec_res['cat_door_device_id'],
                exec_res['cat_id'],
                exec_res['direction'],
                exec_res['identification_method'],
                exec_res['identification_confidence'],
                exec_res['timestamp']
            ]
        )

        # Extract passage_log_id from RETURNING clause
        passage_log_id = None
        if insert_result.get('success') and insert_result.get('result', {}).get('results'):
            passage_log_id = insert_result['result']['results'][0].get('id')

        # Store passage log in shared for downstream nodes (with id)
        exec_res['id'] = passage_log_id
        shared['cat_door_passage_log'] = exec_res
        shared['passage_log_id'] = passage_log_id

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Cat door passage logged: cat_id={exec_res['cat_id']}, "
                   f"direction={exec_res['direction']}, "
                   f"device_id={exec_res['cat_door_device_id']}")

        # Determine next action based on image availability
        if exec_res.get('image_url'):
            # Image available - trigger vision analysis for facial expression/pain detection
            logger.info(f"Image available for cat {exec_res['cat_id']}, triggering vision analysis")
            shared['request']['image'] = exec_res['image_url']
            return 'vision_analysis'
        else:
            # No image - passage logging complete
            logger.info(f"No image available for cat {exec_res['cat_id']}, passage logging complete")
            return 'default'


class PainDetectionNode(AsyncNode):
    """
    Pain detection node for analyzing cat door passage images.

    Correlates facial expression indicators with BCG heart rate data
    to assess pain likelihood and severity.

    Pain indicators analyzed:
    - Facial Grimace Scale (FGS): ear position, orbital tightening, muzzle tension
    - Posture: hunched, guarded areas, reluctant movement
    - Movement Hesitation: delayed response, careful gait

    Outputs:
    - pain_score (0-10): Severity of pain
    - pain_likelihood (0.0-1.0): Confidence in pain assessment
    - recommended_action: monitor|vet_consultation|urgent_care
    """

    async def prep_async(self, shared):
        cat_id = shared.get('cat_id')
        image_url = shared.get('image_url')

        if not cat_id:
            raise ValueError("cat_id required for pain detection")

        if not image_url:
            raise ValueError("image_url required for pain detection")

        # Query recent BCG heart rate data for correlation
        threshold = datetime.now() - timedelta(minutes=5)
        threshold_str = threshold.strftime("%Y-%m-%d %H:%M:%S")

        bcg_result = await execute_query(
            """
            SELECT heart_rate_bpm, hrv_ms, anomaly_flag, timestamp
            FROM collar_bcg_logs
            WHERE cat_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 10
            """,
            [cat_id, threshold_str]
        )

        bcg_logs = []
        if bcg_result.get("success") and bcg_result.get("result", {}).get("results"):
            bcg_logs = bcg_result["result"]["results"]

        # Analyze BCG anomalies for correlation
        bcg_context = {
            'has_data': len(bcg_logs) > 0,
            'anomaly_count': sum(1 for log in bcg_logs if log.get('anomaly_flag', 0) == 1),
            'avg_heart_rate': sum(log.get('heart_rate_bpm', 0) for log in bcg_logs) / len(bcg_logs) if bcg_logs else 0,
            'recent_logs': bcg_logs[:3]
        }

        return {
            'cat_id': cat_id,
            'image_url': image_url,
            'bcg_context': bcg_context
        }

    async def exec_async(self, prep_res):
        image_url = prep_res['image_url']
        bcg_context = prep_res['bcg_context']

        # Build BCG context for prompt
        bcg_text = "No recent BCG data available"
        if bcg_context['has_data']:
            bcg_text = f"""
Recent BCG data (last 5 minutes):
- Average heart rate: {bcg_context['avg_heart_rate']:.1f} bpm
- Anomaly count: {bcg_context['anomaly_count']} / {len(bcg_context['recent_logs'])} readings
- Latest readings: {json.dumps(bcg_context['recent_logs'], indent=2)}

Note: Abnormal heart rate combined with facial grimace indicates higher pain likelihood.
"""

        # Pain detection prompt using Feline Grimace Scale (FGS)
        pain_detection_prompt = f"""
Analyze this cat image for pain indicators using the Feline Grimace Scale (FGS).

### PAIN INDICATORS TO ASSESS

1. **Facial Grimace Scale (0-10)**
   - Ear Position: flattened/drawn back = pain
   - Orbital Tightening: squinting/narrowed eyes = pain
   - Muzzle Tension: tight whiskers/cheek tension = pain
   - Head Position: lowered/tucked = pain

2. **Posture Analysis**
   - Hunched position: body curled or tense
   - Guarded areas: protecting specific body parts
   - Reluctant movement: hesitation to move normally

3. **Movement Hesitation**
   - Delayed response: slow to move or react
   - Careful gait: cautious walking pattern
   - Stiffness: reduced fluidity of movement

### BCG CORRELATION CONTEXT
{bcg_text}

### TASK
Analyze the image and provide a structured pain assessment.

Return in YAML format:

```yaml
facial_grimace_details:
  ear_position: <normal|slightly_flattened|flattened>
  orbital_tightening: <none|mild|moderate|severe>
  muzzle_tension: <relaxed|tense|very_tense>
  head_position: <normal|slightly_lowered|lowered>
posture_analysis:
  hunched: <true|false>
  guarded_areas: <none|specific areas>
  reluctant_movement: <true|false>
movement_hesitation:
  delayed_response: <true|false>
  careful_gait: <true|false>
  stiffness: <none|mild|moderate|severe>
pain_score: <0-10>
pain_likelihood: <0.0-1.0>
bcg_correlation: <none|weak|moderate|strong>
recommended_action: <monitor|vet_consultation|urgent_care>
reasoning: <brief explanation of assessment>
```
"""

        vision_result = await async_call_vision_llm(pain_detection_prompt, image_url)

        # Parse YAML from vision response using safe parser
        default_analysis = {
            'facial_indicators': {
                'ears': 'forward',
                'eyes': 'open',
                'muzzle_tension': 'none',
                'whiskers': 'relaxed'
            },
            'body_posture': {
                'hunched': False,
                'guarded_areas': 'none',
                'reluctant_movement': False
            },
            'movement_hesitation': {
                'delayed_response': False,
                'careful_gait': False,
                'stiffness': 'none'
            },
            'pain_score': 0,
            'pain_likelihood': 0.0,
            'bcg_correlation': 'none',
            'recommended_action': 'monitor',
            'reasoning': 'Unable to analyze - using default values'
        }
        analysis = safe_parse_yaml(vision_result.get('text', ''), default=default_analysis)

        # Ensure required fields exist with safe defaults
        if not isinstance(analysis, dict):
            logger.warning("Pain analysis parsing failed, using default")
            analysis = default_analysis

        # Set defaults for missing fields
        if "pain_score" not in analysis:
            analysis['pain_score'] = default_analysis['pain_score']
        if "pain_likelihood" not in analysis:
            analysis['pain_likelihood'] = default_analysis['pain_likelihood']
        if "recommended_action" not in analysis:
            analysis['recommended_action'] = default_analysis['recommended_action']

        # Validate and clamp ranges
        try:
            pain_score = float(analysis['pain_score'])
            analysis['pain_score'] = max(0, min(10, pain_score))
        except (ValueError, TypeError):
            analysis['pain_score'] = 0

        try:
            pain_likelihood = float(analysis['pain_likelihood'])
            analysis['pain_likelihood'] = max(0.0, min(1.0, pain_likelihood))
        except (ValueError, TypeError):
            analysis['pain_likelihood'] = 0.0

        if analysis['recommended_action'] not in ['monitor', 'vet_consultation', 'urgent_care']:
            analysis['recommended_action'] = 'monitor'

        return {
            'analysis': analysis,
            'raw_response': vision_result,
            'image_url': image_url
        }

    async def post_async(self, shared, prep_res, exec_res):
        cat_id = prep_res['cat_id']
        analysis = exec_res['analysis']
        image_url = exec_res['image_url']

        # Get passage_log_id from shared if available (for FK constraint)
        passage_log_id = shared.get('passage_log_id')

        # Insert pain detection results into cat_door_expression_logs
        await execute_query(
            """
            INSERT INTO cat_door_expression_logs
            (passage_log_id, cat_id, image_url, mood, alertness, pain_score, pain_indicators, analysis_result, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                passage_log_id,
                cat_id,
                image_url,
                analysis.get('mood', 'unknown'),
                analysis.get('alertness', 'unknown'),
                analysis.get('pain_score', 0),
                json.dumps({
                    'facial_grimace_details': analysis.get('facial_grimace_details', {}),
                    'posture_analysis': analysis.get('posture_analysis', {}),
                    'movement_hesitation': analysis.get('movement_hesitation', {})
                }),
                json.dumps(analysis),
                datetime.now().isoformat()
            ]
        )

        # Store in shared for downstream nodes
        shared['pain_detection'] = {
            'cat_id': cat_id,
            'pain_score': analysis.get('pain_score', 0),
            'pain_likelihood': analysis.get('pain_likelihood', 0.0),
            'recommended_action': analysis.get('recommended_action', 'monitor'),
            'analysis': analysis
        }

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Pain detection complete for cat {cat_id}: "
            f"score={analysis.get('pain_score')}, "
            f"likelihood={analysis.get('pain_likelihood')}, "
            f"action={analysis.get('recommended_action')}"
        )

        # Return action based on pain severity
        pain_score = analysis.get('pain_score', 0)
        if pain_score >= 7:
            return 'pain_alert'
        elif pain_score >= 4:
            return 'pain_concern'
        else:
            return 'default'


class CrossDeviceAnalysisNode(AsyncNode):
    """
    Cross-device correlation analysis node for multi-device health insights.

    Correlates data from collar devices and cat door devices to detect patterns:
    1. Fatigue: Door entry + activity drop within 30 mins
    2. Injury: Outdoor return + expression anomaly (pain detection)
    3. Health Alert: BCG anomaly + activity anomaly

    Queries 5 tables:
    - cat_door_passage_logs: Door entry/exit events
    - collar_activity_logs: Activity data from collar
    - collar_bcg_logs: BCG heart rate data
    - collar_outdoor_logs: Outdoor status tracking
    - cat_door_expression_logs: Facial expression and pain analysis

    Outputs structured correlation report with confidence scores.
    """

    async def prep_async(self, shared):
        cat_id = shared.get('cat_id')

        if not cat_id:
            raise ValueError("cat_id required for cross-device analysis")

        # Define time window for correlation (30 minutes)
        time_window = 30
        threshold = datetime.now() - timedelta(minutes=time_window)
        threshold_str = threshold.strftime("%Y-%m-%d %H:%M:%S")

        # Query 1: Cat door passage logs (recent entry/exit events)
        passage_result = await execute_query(
            """
            SELECT id, cat_id, direction, timestamp
            FROM cat_door_passage_logs
            WHERE cat_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 10
            """,
            [cat_id, threshold_str]
        )

        passage_logs = []
        if passage_result.get("success") and passage_result.get("result", {}).get("results"):
            passage_logs = passage_result["result"]["results"]

        # Query 2: Collar activity logs (recent activity data)
        activity_result = await execute_query(
            """
            SELECT activity_type, value, unit, timestamp
            FROM collar_activity_logs
            WHERE cat_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 50
            """,
            [cat_id, threshold_str]
        )

        activity_logs = []
        if activity_result.get("success") and activity_result.get("result", {}).get("results"):
            activity_logs = activity_result["result"]["results"]

        # Query 3: Collar BCG logs (heart rate data with anomaly flags)
        bcg_result = await execute_query(
            """
            SELECT heart_rate_bpm, hrv_ms, respiratory_rate, anomaly_flag, timestamp
            FROM collar_bcg_logs
            WHERE cat_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 50
            """,
            [cat_id, threshold_str]
        )

        bcg_logs = []
        if bcg_result.get("success") and bcg_result.get("result", {}).get("results"):
            bcg_logs = bcg_result["result"]["results"]

        # Query 4: Collar outdoor logs (outdoor status)
        outdoor_result = await execute_query(
            """
            SELECT is_outdoor, started_at, ended_at, timestamp
            FROM collar_outdoor_logs
            WHERE cat_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 10
            """,
            [cat_id, threshold_str]
        )

        outdoor_logs = []
        if outdoor_result.get("success") and outdoor_result.get("result", {}).get("results"):
            outdoor_logs = outdoor_result["result"]["results"]

        # Query 5: Cat door expression logs (facial expression and pain data)
        expression_result = await execute_query(
            """
            SELECT cat_id, pain_score, pain_indicators, mood, alertness, timestamp
            FROM cat_door_expression_logs
            WHERE cat_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 10
            """,
            [cat_id, threshold_str]
        )

        expression_logs = []
        if expression_result.get("success") and expression_result.get("result", {}).get("results"):
            expression_logs = expression_result["result"]["results"]

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Cross-device analysis data loaded for cat {cat_id}: "
            f"passage={len(passage_logs)}, activity={len(activity_logs)}, "
            f"bcg={len(bcg_logs)}, outdoor={len(outdoor_logs)}, "
            f"expression={len(expression_logs)}"
        )

        return {
            'cat_id': cat_id,
            'time_window': time_window,
            'passage_logs': passage_logs,
            'activity_logs': activity_logs,
            'bcg_logs': bcg_logs,
            'outdoor_logs': outdoor_logs,
            'expression_logs': expression_logs
        }

    async def exec_async(self, prep_res):
        cat_id = prep_res['cat_id']
        time_window = prep_res['time_window']
        passage_logs = prep_res['passage_logs']
        activity_logs = prep_res['activity_logs']
        bcg_logs = prep_res['bcg_logs']
        outdoor_logs = prep_res['outdoor_logs']
        expression_logs = prep_res['expression_logs']

        correlations = []

        # Pattern 1: Fatigue Detection
        # Door entry + activity drop within 30 mins = likely tired
        for passage in passage_logs:
            if passage.get('direction') != 'in':
                continue

            passage_time = datetime.fromisoformat(passage.get('timestamp', ''))

            # Find activity logs within 30 mins after door entry
            post_entry_activity = []
            for activity in activity_logs:
                activity_time = datetime.fromisoformat(activity.get('timestamp', ''))
                time_diff = (activity_time - passage_time).total_seconds() / 60

                if 0 <= time_diff <= time_window:
                    post_entry_activity.append(activity)

            if post_entry_activity:
                # Calculate activity drop: compare avg activity before vs after entry
                # For simplicity, check if recent activity values are low
                low_activity_count = sum(
                    1 for a in post_entry_activity
                    if a.get('activity_type') == 'activity' and a.get('value', 100) < 20
                )

                if low_activity_count >= 3:
                    confidence = min(0.9, 0.5 + (low_activity_count * 0.1))
                    correlations.append({
                        'pattern': 'fatigue',
                        'description': f"Door entry at {passage.get('timestamp')} followed by activity drop",
                        'confidence': confidence,
                        'evidence': {
                            'door_entry_time': passage.get('timestamp'),
                            'low_activity_readings': low_activity_count,
                            'post_entry_activity_count': len(post_entry_activity)
                        }
                    })

        # Pattern 2: Injury Detection
        # Outdoor return + expression anomaly (pain detection) = possible injury
        outdoor_returns = [log for log in outdoor_logs if log.get('is_outdoor') == 0]

        for outdoor_return in outdoor_returns:
            return_time = datetime.fromisoformat(outdoor_return.get('timestamp', ''))

            # Find expression logs within 30 mins after outdoor return
            post_return_expressions = []
            for expression in expression_logs:
                expression_time = datetime.fromisoformat(expression.get('timestamp', ''))
                time_diff = (expression_time - return_time).total_seconds() / 60

                if 0 <= time_diff <= time_window:
                    post_return_expressions.append(expression)

            # Check for pain indicators in expressions
            for expression in post_return_expressions:
                pain_score = expression.get('pain_score', 0)

                if pain_score >= 4:
                    confidence = min(0.95, 0.6 + (pain_score / 10) * 0.3)
                    correlations.append({
                        'pattern': 'injury',
                        'description': f"Outdoor return at {outdoor_return.get('timestamp')} followed by pain detection",
                        'confidence': confidence,
                        'evidence': {
                            'outdoor_return_time': outdoor_return.get('timestamp'),
                            'pain_score': pain_score,
                            'expression_mood': expression.get('mood'),
                            'expression_time': expression.get('timestamp')
                        }
                    })

        # Pattern 3: Health Alert
        # BCG anomaly + activity anomaly = health concern
        bcg_anomalies = [log for log in bcg_logs if log.get('anomaly_flag') == 1]

        if bcg_anomalies:
            # Calculate recent activity average
            recent_activity_values = [
                a.get('value', 50)
                for a in activity_logs[:10]
                if a.get('activity_type') == 'activity'
            ]

            avg_activity = sum(recent_activity_values) / len(recent_activity_values) if recent_activity_values else 50

            # Check for concurrent low activity
            if avg_activity < 20 and len(bcg_anomalies) >= 2:
                # Calculate confidence based on number of anomalies and activity level
                anomaly_ratio = len(bcg_anomalies) / len(bcg_logs) if bcg_logs else 0
                activity_severity = (20 - avg_activity) / 20
                confidence = min(0.95, 0.5 + (anomaly_ratio * 0.2) + (activity_severity * 0.25))

                correlations.append({
                    'pattern': 'health_alert',
                    'description': f"BCG anomalies ({len(bcg_anomalies)}) combined with low activity ({avg_activity:.1f})",
                    'confidence': confidence,
                    'evidence': {
                        'bcg_anomaly_count': len(bcg_anomalies),
                        'total_bcg_readings': len(bcg_logs),
                        'avg_activity_level': avg_activity,
                        'bcg_anomaly_details': [
                            {
                                'heart_rate_bpm': a.get('heart_rate_bpm'),
                                'hrv_ms': a.get('hrv_ms'),
                                'timestamp': a.get('timestamp')
                            }
                            for a in bcg_anomalies[:3]
                        ]
                    }
                })

        # Calculate overall confidence scores by pattern
        confidence_scores = {
            'fatigue': max([c['confidence'] for c in correlations if c['pattern'] == 'fatigue'], default=0.0),
            'injury': max([c['confidence'] for c in correlations if c['pattern'] == 'injury'], default=0.0),
            'health_alert': max([c['confidence'] for c in correlations if c['pattern'] == 'health_alert'], default=0.0)
        }

        return {
            'correlations': correlations,
            'confidence_scores': confidence_scores,
            'summary': {
                'total_correlations': len(correlations),
                'patterns_detected': list(set(c['pattern'] for c in correlations)),
                'highest_confidence_pattern': max(confidence_scores, key=confidence_scores.get) if confidence_scores else None
            }
        }

    async def post_async(self, shared, prep_res, exec_res):
        cat_id = prep_res['cat_id']
        correlations = exec_res['correlations']
        confidence_scores = exec_res['confidence_scores']
        summary = exec_res['summary']

        # Store correlation report in shared
        shared['cross_device_analysis'] = {
            'cat_id': cat_id,
            'correlations': correlations,
            'confidence_scores': confidence_scores,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        }

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Cross-device analysis complete for cat {cat_id}: "
            f"{summary['total_correlations']} correlations detected, "
            f"patterns={summary['patterns_detected']}"
        )

        # Determine action based on highest priority alert
        if confidence_scores.get('health_alert', 0.0) >= 0.7:
            return 'health_alert'
        elif confidence_scores.get('injury', 0.0) >= 0.7:
            return 'injury_alert'
        elif confidence_scores.get('fatigue', 0.0) >= 0.7:
            return 'fatigue_concern'
        else:
            return 'default'


class OutdoorMonitorNode(AsyncNode):
    """
    Outdoor activity monitoring node for detecting extended outdoor duration and night outdoor alerts.

    Monitors 2 conditions:
    1. Extended outdoor duration (>4 hours)
    2. Night outdoor activity (22:00-06:00)
    3. Geofence breach (GPS location outside safe radius)

    Generates 3 types of alerts:
    - extended_outdoor: Cat has been outdoors for >4 hours
    - night_outdoor: Cat is outdoor during night hours (22:00-06:00)
    - geofence_breach: Cat GPS location is outside safe radius

    Data sources:
    - collar_outdoor_logs: Current outdoor status, GPS coordinates, started_at timestamp
    """

    def __init__(self, max_outdoor_hours=4, night_start_hour=22, night_end_hour=6,
                 safe_radius_meters=100, home_lat=None, home_lng=None, **kwargs):
        """
        Initialize OutdoorMonitorNode with configurable thresholds.

        Args:
            max_outdoor_hours: Maximum outdoor duration before alert (default: 4 hours)
            night_start_hour: Night period start hour (0-23, default: 22)
            night_end_hour: Night period end hour (0-23, default: 6)
            safe_radius_meters: Safe radius from home location in meters (default: 100)
            home_lat: Home latitude for geofence (optional)
            home_lng: Home longitude for geofence (optional)
        """
        super().__init__(**kwargs)
        self.max_outdoor_hours = max_outdoor_hours
        self.night_start_hour = night_start_hour
        self.night_end_hour = night_end_hour
        self.safe_radius_meters = safe_radius_meters
        self.home_lat = home_lat
        self.home_lng = home_lng

    async def prep_async(self, shared):
        """
        Query most recent outdoor logs for the cat.

        Returns:
            dict: Cat outdoor status with fields:
                - cat_id: Cat identifier
                - outdoor_logs: List of recent outdoor records
        """
        cat_id = shared.get('cat_id')

        if not cat_id:
            raise ValueError("cat_id required for outdoor monitoring")

        # Query most recent outdoor log where is_outdoor=1 and ended_at is NULL
        result = await execute_query(
            """
            SELECT id, collar_device_id, cat_id, is_outdoor, location_lat, location_lng,
                   started_at, ended_at
            FROM collar_outdoor_logs
            WHERE cat_id = ? AND is_outdoor = 1 AND ended_at IS NULL
            ORDER BY started_at DESC
            LIMIT 1
            """,
            [cat_id]
        )

        outdoor_logs = []
        if result.get("success") and result.get("result", {}).get("results"):
            outdoor_logs = result["result"]["results"]

        import logging
        logger = logging.getLogger(__name__)

        if outdoor_logs:
            logger.info(f"Found active outdoor session for cat {cat_id}: started at {outdoor_logs[0].get('started_at')}")
        else:
            logger.info(f"No active outdoor session for cat {cat_id}")

        return {
            'cat_id': cat_id,
            'outdoor_logs': outdoor_logs
        }

    async def exec_async(self, prep_res):
        """
        Analyze outdoor status and detect alert conditions.

        Checks:
        1. Duration: If outdoor duration > max_outdoor_hours
        2. Night activity: If current time is between night_start_hour and night_end_hour
        3. Geofence: If GPS coordinates are outside safe radius (if available)

        Returns:
            dict: Alert assessment with fields:
                - alert_type: extended_outdoor|night_outdoor|geofence_breach|none
                - duration_hours: Hours outdoor (if applicable)
                - current_location: GPS coordinates (if available)
                - distance_from_home: Distance in meters (if geofence enabled)
                - alert_details: Additional context
        """
        cat_id = prep_res['cat_id']
        outdoor_logs = prep_res['outdoor_logs']

        # No active outdoor session
        if not outdoor_logs:
            return {
                'alert_type': 'none',
                'reason': 'No active outdoor session'
            }

        current_log = outdoor_logs[0]
        started_at_str = current_log.get('started_at')
        location_lat = current_log.get('location_lat')
        location_lng = current_log.get('location_lng')

        # Parse started_at timestamp
        if not started_at_str:
            return {
                'alert_type': 'none',
                'reason': 'Invalid started_at timestamp'
            }

        try:
            started_at = datetime.fromisoformat(started_at_str)
        except ValueError:
            return {
                'alert_type': 'none',
                'reason': 'Failed to parse started_at timestamp'
            }

        # Calculate outdoor duration
        current_time = datetime.now()
        duration = current_time - started_at
        duration_hours = duration.total_seconds() / 3600

        # Check alert conditions in priority order

        # 1. Check geofence breach (highest priority if GPS available)
        if location_lat is not None and location_lng is not None and \
           self.home_lat is not None and self.home_lng is not None:
            distance_meters = self._calculate_distance(
                self.home_lat, self.home_lng,
                location_lat, location_lng
            )

            if distance_meters > self.safe_radius_meters:
                return {
                    'alert_type': 'geofence_breach',
                    'duration_hours': duration_hours,
                    'current_location': {'lat': location_lat, 'lng': location_lng},
                    'distance_from_home': distance_meters,
                    'alert_details': f"Cat is {distance_meters:.1f}m from home (safe radius: {self.safe_radius_meters}m)"
                }

        # 2. Check extended outdoor duration
        if duration_hours > self.max_outdoor_hours:
            return {
                'alert_type': 'extended_outdoor',
                'duration_hours': duration_hours,
                'current_location': {'lat': location_lat, 'lng': location_lng} if location_lat else None,
                'alert_details': f"Cat has been outdoor for {duration_hours:.1f} hours (threshold: {self.max_outdoor_hours}h)"
            }

        # 3. Check night outdoor activity
        current_hour = current_time.hour
        is_night = False

        if self.night_start_hour > self.night_end_hour:
            # Night period crosses midnight (e.g., 22:00-06:00)
            is_night = current_hour >= self.night_start_hour or current_hour < self.night_end_hour
        else:
            # Night period within same day
            is_night = self.night_start_hour <= current_hour < self.night_end_hour

        if is_night:
            return {
                'alert_type': 'night_outdoor',
                'duration_hours': duration_hours,
                'current_location': {'lat': location_lat, 'lng': location_lng} if location_lat else None,
                'alert_details': f"Cat is outdoor during night hours ({self.night_start_hour}:00-{self.night_end_hour:02d}:00)"
            }

        # No alerts triggered
        return {
            'alert_type': 'none',
            'duration_hours': duration_hours,
            'current_location': {'lat': location_lat, 'lng': location_lng} if location_lat else None,
            'reason': 'Outdoor session within normal parameters'
        }

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate distance between two GPS coordinates using Haversine formula.

        Args:
            lat1, lon1: Home coordinates
            lat2, lon2: Current coordinates

        Returns:
            float: Distance in meters
        """
        from math import radians, sin, cos, sqrt, atan2

        # Earth radius in meters
        R = 6371000

        # Convert to radians
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)

        # Haversine formula
        a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c

        return distance

    async def post_async(self, shared, prep_res, exec_res):
        """
        Store outdoor monitoring results and determine routing action.

        Args:
            shared: Shared store
            prep_res: Prep results with cat_id and outdoor_logs
            exec_res: Alert assessment from exec_async

        Returns:
            str: Action for flow routing
                - 'extended_outdoor': Extended outdoor duration alert
                - 'night_outdoor': Night outdoor activity alert
                - 'geofence_breach': Geofence breach alert
                - 'default': No alerts
        """
        cat_id = prep_res['cat_id']
        alert_type = exec_res['alert_type']

        # Store monitoring result in shared
        shared['outdoor_monitoring'] = {
            'cat_id': cat_id,
            'alert_type': alert_type,
            'duration_hours': exec_res.get('duration_hours'),
            'current_location': exec_res.get('current_location'),
            'distance_from_home': exec_res.get('distance_from_home'),
            'alert_details': exec_res.get('alert_details'),
            'reason': exec_res.get('reason'),
            'timestamp': datetime.now().isoformat()
        }

        import logging
        logger = logging.getLogger(__name__)

        if alert_type == 'none':
            logger.info(f"Outdoor monitoring for cat {cat_id}: {exec_res.get('reason')}")
            return 'default'

        # Log alert
        logger.warning(f"Outdoor alert for cat {cat_id}: {alert_type} - {exec_res.get('alert_details')}")

        # Insert alert into alert_logs table
        await execute_query(
            """
            INSERT INTO alert_logs (cat_id, alert_type, alert_title, alert_body,
                                   anomaly_details, notification_sent, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                cat_id,
                alert_type,
                f"Outdoor {alert_type.replace('_', ' ').title()} Alert",
                exec_res.get('alert_details', ''),
                json.dumps({
                    'duration_hours': exec_res.get('duration_hours'),
                    'current_location': exec_res.get('current_location'),
                    'distance_from_home': exec_res.get('distance_from_home')
                }),
                0,
                datetime.now().isoformat()
            ]
        )

        # Return appropriate routing action based on alert type
        return alert_type


class MemoryLoaderNode(AsyncNode):
    """
    Memory loading node - loads conversation history and resolves pronouns.

    Extracted from ConversationMemoryNode to fix timing issue.
    This node runs at the START of the flow to load context.

    Output:
    - shared['session_id']: Session identifier
    - shared['conversation_history']: Loaded history
    - shared['conversation_context']: Session context with entities
    - shared['original_user_input']: Original input before resolution
    - shared['request']['user_input']: Resolved input with pronouns replaced
    """

    SESSION_TTL_MINUTES = 30

    async def prep_async(self, shared):
        request = shared.get('request', {}) if isinstance(shared, dict) else {}
        user_input = request.get('user_input') or shared.get('question', '') or ''
        session_id = request.get('session_id') or shared.get('session_id')
        user_id = request.get('user_id') or shared.get('user_id')
        cat_id = request.get('cat_id') or shared.get('cat_id')

        if not session_id and not user_id:
            raise ValueError("session_id or user_id is required for conversation memory")

        session = await self._load_active_session(session_id, user_id)
        if not session:
            session = await self._create_session(user_id, session_id)

        cat_profile = {}
        if cat_id:
            try:
                async with SystemContext(cat_id=cat_id) as ctx:
                    cat_profile = await ctx.get_cat_profile(cat_id)
            except Exception as e:
                logger.warning(f"Failed to load cat profile for pronoun resolution: {e}")

        return {
            'session': session,
            'user_input': user_input,
            'user_id': session.get('user_id') or user_id,
            'cat_id': cat_id,
            'cat_profile': cat_profile
        }

    async def exec_async(self, prep_res):
        session = prep_res['session']
        user_input = prep_res['user_input']
        history = session.get('history', [])
        context = session.get('context', {})
        cat_profile = prep_res.get('cat_profile', {})

        resolved_text, entities = await self._resolve_pronouns(
            user_input=user_input,
            history=history,
            context=context,
            cat_profile=cat_profile
        )

        return {
            'resolved_text': resolved_text,
            'entities': entities,
            'session': session,
            'user_input': user_input
        }

    async def post_async(self, shared, prep_res, exec_res):
        session = prep_res['session']
        session_id = session['session_id']
        user_id = prep_res['user_id']
        cat_profile = prep_res.get('cat_profile', {}) or {}

        user_input = prep_res['user_input']
        resolved_text = exec_res.get('resolved_text', user_input)
        entities = exec_res.get('entities', [])

        history = list(session.get('history', []))
        context = dict(session.get('context', {}) or {})

        if entities:
            context['entities'] = entities
        if cat_profile:
            context['cat_profile'] = {
                'id': cat_profile.get('id'),
                'name': cat_profile.get('name'),
                'breed': cat_profile.get('breed')
            }

        request = shared.get('request', {}) if isinstance(shared, dict) else {}
        request['user_input'] = resolved_text

        shared['request'] = request
        shared['session_id'] = session_id
        shared['user_id'] = user_id
        shared['conversation_history'] = history
        shared['conversation_context'] = context
        shared['original_user_input'] = user_input
        shared['_memory_session'] = session

        return 'memory_loaded'

    async def _load_active_session(self, session_id, user_id):
        filters = []
        params = []

        if session_id:
            filters.append("session_id = ?")
            params.append(session_id)
        if user_id:
            filters.append("user_id = ?")
            params.append(user_id)

        if not filters:
            return None

        sql = f"""
            SELECT session_id, user_id, history, context, created_at, updated_at, expires_at
            FROM conversation_sessions
            WHERE ({' OR '.join(filters)}) AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY updated_at DESC
            LIMIT 1
        """
        params.append(datetime.now().isoformat())

        result = await execute_query(sql, params)

        if result.get('success') and result.get('result', {}).get('results'):
            row = result['result']['results'][0]
            history = self._safe_json_load(row.get('history'), [])
            context = self._safe_json_load(row.get('context'), {})

            return {
                'session_id': row.get('session_id'),
                'user_id': row.get('user_id') or user_id,
                'history': history,
                'context': context,
                'created_at': row.get('created_at'),
                'updated_at': row.get('updated_at'),
                'expires_at': row.get('expires_at')
            }

        return None

    async def _create_session(self, user_id, session_id=None):
        if not user_id:
            raise ValueError("user_id is required to create a new session")

        new_session_id = session_id or uuid.uuid4().hex
        now_ts = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(minutes=self.SESSION_TTL_MINUTES)).isoformat()

        if session_id:
            existing = await execute_query(
                "SELECT session_id, created_at FROM conversation_sessions WHERE session_id = ?",
                [new_session_id]
            )

            if existing.get('success') and existing.get('result', {}).get('results'):
                existing_created_at = existing['result']['results'][0].get('created_at')
                await execute_query(
                    """
                    UPDATE conversation_sessions
                    SET user_id = ?, history = ?, context = ?, updated_at = ?, expires_at = ?
                    WHERE session_id = ?
                    """,
                    [
                        user_id,
                        json.dumps([], ensure_ascii=False),
                        json.dumps({}, ensure_ascii=False),
                        now_ts,
                        expires_at,
                        new_session_id
                    ]
                )

                return {
                    'session_id': new_session_id,
                    'user_id': user_id,
                    'history': [],
                    'context': {},
                    'created_at': existing_created_at or now_ts,
                    'updated_at': now_ts,
                    'expires_at': expires_at
                }

        await execute_query(
            """
            INSERT INTO conversation_sessions
                (session_id, user_id, history, context, created_at, updated_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                new_session_id,
                user_id,
                json.dumps([], ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
                now_ts,
                now_ts,
                expires_at
            ]
        )

        return {
            'session_id': new_session_id,
            'user_id': user_id,
            'history': [],
            'context': {},
            'created_at': now_ts,
            'updated_at': now_ts,
            'expires_at': expires_at
        }

    async def _resolve_pronouns(self, user_input, history, context, cat_profile):
        history_snippet = json.dumps(history[-5:], ensure_ascii=False, indent=2)
        context_snippet = json.dumps(context or {}, ensure_ascii=False, indent=2)
        cat_name = (cat_profile or {}).get('name', '未知')

        prompt = f"""
你是对话指代消解助手。根据历史对话、上下文实体和已知信息，替换当前消息中的代词，让含义清晰可追溯。

【历史对话-最近5条】
{history_snippet}

【上下文实体】
{context_snippet}

【已知猫咪名称】
{cat_name}

【当前用户消息】
{user_input}

请输出严格的 JSON：
{{
  "resolved_text": "将代词替换后的完整句子",
  "entities": [
    {{"pronoun": "它", "referent": "猫咪{cat_name}", "reason": "上一轮提到的猫咪"}}
  ]
}}
只输出 JSON，不要包含多余文本。
"""

        try:
            response = await async_call_llm(prompt)
            parsed = self._parse_json_response(response)
            resolved_text = parsed.get('resolved_text') or user_input
            entities = parsed.get('entities') or []

            if not isinstance(resolved_text, str):
                resolved_text = user_input

            if not isinstance(entities, list):
                entities = []
        except Exception as e:
            logger.warning(f"Pronoun resolution failed, using original input: {e}")
            resolved_text = user_input
            entities = []

        return resolved_text, entities

    def _parse_json_response(self, response_text):
        if not response_text:
            return {}

        cleaned = response_text.strip()
        if '```' in cleaned:
            segments = cleaned.split('```')
            for segment in segments:
                if '{' in segment and '}' in segment:
                    cleaned = segment
                    break

        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1:
            cleaned = cleaned[start:end + 1]

        try:
            return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}")
            return {}

    def _safe_json_load(self, raw_value, default):
        if not raw_value:
            return default

        try:
            return json.loads(raw_value)
        except Exception as e:
            logger.warning(f"Failed to parse JSON field, using default: {e}")
            return default


class MemorySaverNode(AsyncNode):
    """
    Memory saving node - saves conversation with assistant response.

    Extracted from ConversationMemoryNode to fix timing issue.
    This node runs at the END of the flow AFTER ResponseGeneratorNode.

    Input:
    - shared['response']: Generated assistant response
    - shared['session_id']: Session identifier
    - shared['conversation_history']: Current history
    - shared['original_user_input']: Original user input
    """

    SESSION_TTL_MINUTES = 30

    async def prep_async(self, shared):
        return {
            'session_id': shared.get('session_id'),
            'user_id': shared.get('user_id'),
            'response': shared.get('response', ''),
            'history': shared.get('conversation_history', []),
            'context': shared.get('conversation_context', {}),
            'original_user_input': shared.get('original_user_input', ''),
            'resolved_user_input': shared.get('request', {}).get('user_input', '')
        }

    async def exec_async(self, prep_res):
        history = list(prep_res.get('history', []))
        now_ts = datetime.now().isoformat()

        history.append({
            'role': 'user',
            'content': prep_res['original_user_input'],
            'resolved_content': prep_res['resolved_user_input'],
            'timestamp': now_ts
        })

        if prep_res['response']:
            history.append({
                'role': 'assistant',
                'content': prep_res['response'],
                'timestamp': now_ts
            })

        context = dict(prep_res.get('context', {}) or {})
        context['last_updated'] = now_ts

        return {
            'history': history,
            'context': context
        }

    async def post_async(self, shared, prep_res, exec_res):
        session_id = prep_res['session_id']
        if not session_id:
            logger.warning("No session_id available for memory save")
            return 'default'

        history = exec_res['history']
        context = exec_res['context']
        now_ts = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(minutes=self.SESSION_TTL_MINUTES)).isoformat()

        await execute_query(
            """
            UPDATE conversation_sessions
            SET history = ?, context = ?, updated_at = ?, expires_at = ?
            WHERE session_id = ?
            """,
            [
                json.dumps(history, ensure_ascii=False),
                json.dumps(context, ensure_ascii=False),
                now_ts,
                expires_at,
                session_id
            ]
        )

        shared['conversation_history'] = history
        shared['conversation_context'] = context
        shared['conversation_session_expires_at'] = expires_at

        logger.info(f"Conversation saved for session {session_id}")
        return 'memory_saved'


class ResponseGeneratorNode(AsyncNode):
    """
    Unified response generator node - converts structured data to natural language.

    This node reads the router_action to determine which structured data key to read,
    then uses LLM to generate a natural language response.

    Input:
    - shared['router_action']: Action from RouterNode (e.g., 'medical_query', 'daily_analysis')
    - shared['diagnosis'], shared['daily_analysis'], etc.: Structured business data

    Output:
    - shared['response']: Natural language response for API return
    """

    ACTION_TO_KEY = {
        'medical_query': 'diagnosis',
        'comprehensive_diagnosis': 'diagnosis',
        'daily_analysis': 'daily_analysis',
        'status_summary': 'status_summary',
        'weekly_report': 'weekly_report',
        'monthly_report': 'monthly_report',
        'health_prediction': 'health_prediction',
        'behavior_pattern': 'behavior_pattern',
        'trend_analysis': 'trend_analysis',
        'vet_recommendation': 'vet_recommendation',
        'emergency_alert': 'emergency_alert',
        'device_offline': 'device_offline_alert',
        'collar_ingestion': 'collar_data',
        'cat_door_event': 'cat_door_event',
        'pain_detection': 'pain_detection',
        # V3.3.8: 猫门图片状态分析
        'cat_door_status': 'cat_door_analysis'
    }

    # V3.3.10: Universal alert templates with emoji - LLM will adapt to user's language
    # Keep templates simple with keywords that work across languages
    IOT_ALERT_RESPONSE_TEMPLATES = {
        'high_heart_rate': '⚠️ [ALERT: High heart rate / 心率偏高] - Monitor closely',
        'low_heart_rate': '⚠️ [ALERT: Low heart rate / 心率偏低] - Please monitor',
        'low_battery': '🔋 [ALERT: Low battery / 电量不足] - Please charge',
        'long_outdoor': '🏠 [ALERT: Long time outdoors / 外出较久] - Stay safe',
        'prey_detected': '🐭 [ALERT: Prey detected / 检测到猎物] - Check for cleanup',
        'low_activity': '😴 [ALERT: Low activity / 活动量低] - Please monitor',
        'high_activity': '🏃 [INFO: Very active today / 今天很活跃!]'
    }

    # V3.3.10: Universal degraded prompts - simple format for all languages
    DEGRADED_PROMPTS = {
        'missing_cat_id': '🔗 [Please bind device / 请绑定设备 / Gerät verbinden / Connecter appareil]',
        'timeout': '🔄 [Device unavailable / 设备无响应 / Gerät nicht verfügbar / Appareil indisponible] - Retry later'
    }

    async def prep_async(self, shared):
        self._progress_callback = shared.get('progress_callback')
        router_action = shared.get('router_action', 'default')

        # V3.3.8: 检查是否有猫门分析结果（来自 CatDetectionNode）
        cat_door_analysis = shared.get('cat_door_analysis')
        if cat_door_analysis:
            router_action = 'cat_door_status'

        data_key = self.ACTION_TO_KEY.get(router_action)

        structured_data = None
        if data_key:
            structured_data = shared.get(data_key)

        if not structured_data:
            for key in self.ACTION_TO_KEY.values():
                if shared.get(key):
                    structured_data = shared.get(key)
                    break

        # Detect pain_alert state from vision_analysis or cat_door_analysis
        vision_analysis = shared.get('vision_analysis') or {}
        pain_score = vision_analysis.get('pain_score', 0)

        # V3.3.8: 也检查猫门分析中的疼痛评分
        if cat_door_analysis:
            cat_status = cat_door_analysis.get('cat_status', {})
            cat_door_pain = cat_status.get('estimated_pain_score', 0)
            pain_score = max(pain_score, cat_door_pain)

        has_pain_alert = pain_score >= 6

        # V3.3.10: Simplified - no language detection needed
        # LLM automatically responds in user's language via unified instruction
        user_input = shared.get('request', {}).get('user_input', '')

        # Extract Memory results from hybrid_results (IMPL-005)
        hybrid_results = shared.get('hybrid_results', [])
        memory_results = shared.get('memory_results', [])
        if hybrid_results:
            # Filter results where layer == 'Memory'
            hybrid_memory = [r for r in hybrid_results if r.get('layer') == 'Memory']
            if memory_results:
                memory_results.extend(hybrid_memory)
            else:
                memory_results = hybrid_memory

        # Four-Layer RAG: Build structured_matches from Layer 2 components
        structured_matches = {
            'symptoms': shared.get('symptom_matches', []),
            'breeds': shared.get('breed_matches', []),
            'medications': shared.get('medication_matches', []),
            'vaccination': shared.get('vaccination_info')
        }

        return {
            'router_action': router_action,
            'structured_data': structured_data,
            'user_input': user_input,
            'cat_name': shared.get('cat_profile', {}).get('name', '您的猫咪'),
            'vision_analysis': shared.get('vision_analysis'),
            'rag_results': shared.get('rag_results'),
            'conversation_history': shared.get('conversation_history', [])[-3:],
            # Pain alert detection
            'has_pain_alert': has_pain_alert,
            'pain_score': pain_score,
            # V3.3.10: Simplified - LLM auto-matches user's language
            'detected_language': 'auto',  # Kept for backward compatibility
            # V3.3.8: 猫门分析结果
            'cat_door_analysis': cat_door_analysis,
            # IMPL-005: Memory results from hybrid retrieval
            'memory_results': memory_results,
            # Four-Layer RAG: Layer 1 Core Rules and Layer 2 Structured Knowledge
            'core_rules': shared.get('core_rules', {}),
            'structured_matches': structured_matches,
            # V3.3.9: SKILL/IoT Context Integration
            'skill_context': shared.get('skill_context', ''),
            'iot_context': shared.get('iot_context', ''),
            'fused_context': shared.get('fused_context', ''),
            'iot_summary': shared.get('iot_summary', {}),
            'iot_load_degraded': shared.get('iot_load_degraded', False),
            'iot_errors': shared.get('iot_load_errors', []),
            'iot_error_types': shared.get('iot_load_error_types', []),
            'missing_cat_id': not bool(shared.get('request', {}).get('cat_id') or shared.get('cat_id')),
            # V3.3.10: Emergency and device offline alert data for bilingual response generation
            'emergency_alert': shared.get('emergency_alert', {}),
            'device_offline_alert': shared.get('device_offline_alert', {})
        }

    async def exec_async(self, prep_res):
        progress_cb = getattr(self, '_progress_callback', None)

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'started',
                'message': '正在生成回复...'
            })

        router_action = prep_res['router_action']
        structured_data = prep_res['structured_data']
        user_input = prep_res['user_input']
        cat_name = prep_res['cat_name']
        vision_analysis = prep_res.get('vision_analysis')
        rag_results = prep_res.get('rag_results')
        has_pain_alert = prep_res.get('has_pain_alert', False)
        pain_score = prep_res.get('pain_score', 0)
        detected_language = prep_res.get('detected_language', 'auto')
        cat_door_analysis = prep_res.get('cat_door_analysis')
        iot_summary = prep_res.get('iot_summary', {})

        result = None

        try:
            # HIGHEST PRIORITY: Pain alert takes precedence over all other actions
            if has_pain_alert:
                result = await self._generate_pain_alert_response(
                    cat_name=cat_name,
                    pain_score=pain_score,
                    vision_analysis=vision_analysis,
                    user_input=user_input,
                    detected_language=detected_language
                )
                result = self._apply_response_enhancements(result, prep_res)
                return result

            # V3.3.8: 猫门图片状态分析响应
            if router_action == 'cat_door_status' and cat_door_analysis:
                result = await self._generate_cat_door_status_response(
                    cat_name=cat_name,
                    cat_door_analysis=cat_door_analysis,
                    user_input=user_input,
                    detected_language=detected_language
                )
                result = self._apply_response_enhancements(result, prep_res)
                return result

            # V3.3.10: Emergency and device offline - use LLM for bilingual response
            # Alert data is passed via prep_res from prep_async
            if router_action == 'emergency_alert':
                # Use LLM for proper bilingual emergency response
                emergency_data = prep_res.get('emergency_alert', {})
                result = await self._generate_emergency_response(
                    cat_name, user_input, emergency_data, detected_language
                )
                result = self._apply_response_enhancements(result, prep_res)
                return result

            if router_action == 'device_offline':
                # Use LLM for proper bilingual device offline response
                offline_data = prep_res.get('device_offline_alert', {})
                result = await self._generate_device_offline_response(
                    cat_name, user_input, offline_data, detected_language
                )
                result = self._apply_response_enhancements(result, prep_res)
                return result

            # V3.3.4: Direct reply for simple questions (skip all analysis)
            if router_action == 'direct_reply':
                result = await self._generate_direct_reply(user_input, cat_name, detected_language)
                result = self._apply_response_enhancements(result, prep_res)
                return result

            if not structured_data and not vision_analysis and not rag_results:
                result = await self._generate_simple_response(user_input, cat_name, prep_res.get('conversation_history', []), detected_language)
                result = self._apply_response_enhancements(result, prep_res)
                return result

            # V3.3.8: Two-Stage Generation - LLM2 analysis + LLM1 output
            # Four-Layer RAG: Include Layer 1 Core Rules and Layer 2 Structured Knowledge
            try:
                response = await self._two_stage_generate(
                    router_action=router_action,
                    structured_data=structured_data,
                    user_input=user_input,
                    cat_name=cat_name,
                    vision_analysis=vision_analysis,
                    rag_results=rag_results,
                    detected_language=detected_language,
                    memory_results=prep_res.get('memory_results', []),
                    core_rules=prep_res.get('core_rules', {}),
                    structured_matches=prep_res.get('structured_matches', {}),
                    # V3.3.9: SKILL/IoT Context
                    skill_context=prep_res.get('skill_context', ''),
                    iot_context=prep_res.get('iot_context', ''),
                    fused_context=prep_res.get('fused_context', ''),
                    iot_summary=iot_summary
                )
                result = self._apply_response_enhancements(response.strip(), prep_res)
            except Exception as e:
                logger.error(f"Two-stage generation failed: {e}")
                result = self._generate_fallback_response(router_action, structured_data, cat_name, detected_language)
                result = self._apply_response_enhancements(result, prep_res)

            return result
        finally:
            if progress_cb and result is not None:
                await progress_cb({
                    'type': 'progress',
                    'node': self.__class__.__name__,
                    'status': 'completed',
                    'message': '回复生成完成'
                })

    async def post_async(self, shared, prep_res, exec_res):
        shared['response'] = exec_res
        shared['assistant_reply'] = exec_res
        return 'response_generated'

    async def _generate_cat_door_status_response(
        self,
        cat_name: str,
        cat_door_analysis: dict,
        user_input: str,
        detected_language: str = 'auto'
    ) -> str:
        """
        V3.3.8: 生成猫门图片状态分析的自然语言响应

        Args:
            cat_name: 猫咪名字
            cat_door_analysis: CatDetectionNode 返回的分析结果
            user_input: 用户原始输入
            detected_language: 检测到的语言

        Returns:
            str: 自然语言响应
        """
        cat_status = cat_door_analysis.get('cat_status', {})
        description = cat_door_analysis.get('description', '')
        recommendations = cat_door_analysis.get('recommendations', '')
        has_object = cat_door_analysis.get('has_object_in_mouth', False)
        object_type = cat_door_analysis.get('object_type', '')
        cat_door_data = cat_door_analysis.get('cat_door_data', {})
        image_timestamp = cat_door_data.get('timestamp', '最近')

        # 构建状态摘要
        status_summary = f"""
猫咪状态分析结果（基于猫门拍摄的图片，时间: {image_timestamp}）:

**整体健康**: {cat_status.get('overall_health', '未知')}
**情绪状态**: {cat_status.get('mood', '未知')}
**精神状态**: {cat_status.get('energy_level', '未知')}
**警觉程度**: {cat_status.get('alertness', '未知')}
**疼痛指标**: {cat_status.get('pain_indicators', '无')}
**估计疼痛评分**: {cat_status.get('estimated_pain_score', 0)}/10
**异常情况**: {cat_status.get('abnormalities', '无')}

**详细描述**: {description}

**是否叼着东西**: {'是 - ' + object_type if has_object else '否'}

**建议**: {recommendations}
"""

        prompt = f"""
用户询问: {user_input}

以下是基于猫门摄像头拍摄的 {cat_name} 的最新状态分析:

{status_summary}

请根据以上分析结果，用友好、专业的语气回复用户的问题。
- 如果猫咪状态良好，给予积极的反馈
- 如果有任何需要关注的地方，温和地提醒主人
- 如果猫咪叼着东西，描述一下这个有趣的情况
- 回复要自然、亲切，像一个关心猫咪的朋友
"""

        try:
            response = await async_call_llm(
                prompt,
                system_prompt="你是专业的猫咪健康顾问，正在根据猫门摄像头的图片分析结果回答主人的问题。",
                detected_language=detected_language
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Cat door status response generation failed: {e}")
            # Fallback response
            health = cat_status.get('overall_health', '正常')
            mood = cat_status.get('mood', '良好')
            return f"根据猫门摄像头的最新图片，{cat_name}看起来{health}，情绪{mood}。{recommendations}"

    async def _generate_simple_response(self, user_input, cat_name, history, detected_language='auto'):
        """
        Generate simple response with language-aware output.

        V3.3.7: Uses Prompt Caching - static system prompt + dynamic user message.
        """
        history_context = ""
        if history:
            history_context = "\n".join([
                f"{h['role']}: {h['content']}"
                for h in history[-3:]
            ])

        # Get current date (always English format for template)
        current_date = get_current_date_str('en')

        # V3.3.7: Use cacheable system prompt (static) + user message (dynamic)
        system_prompt = PROMPTS['cacheable_system']['simple']
        user_message = PROMPTS['user_message']['simple'].format(
            history_context=history_context or "None",
            user_input=user_input,
            cat_name=cat_name,
            current_date=current_date
        )

        try:
            response = await async_call_llm(user_message, system_prompt=system_prompt, detected_language=detected_language)
            return response.strip()
        except Exception as e:
            logger.error(f"Simple response generation failed: {e}")
            # Fallback - simple response without brand intro
            return f"I've received your question about {cat_name}. For health concerns, please consult a professional veterinarian."

    async def _generate_direct_reply(self, user_input, cat_name, detected_language='auto'):
        """
        V3.3.7: Generate direct reply for simple questions without data analysis.

        For greetings, chitchat, and simple questions that don't need health data.
        Uses Prompt Caching - static system prompt + dynamic user message.
        """
        current_date = get_current_date_str('en')

        # V3.3.7: Use cacheable system prompt (static) + user message (dynamic)
        system_prompt = PROMPTS['cacheable_system']['direct']
        user_message = PROMPTS['user_message']['direct'].format(
            user_input=user_input,
            cat_name=cat_name,
            current_date=current_date
        )

        try:
            response = await async_call_llm(user_message, system_prompt=system_prompt, detected_language=detected_language)
            return response.strip()
        except Exception as e:
            logger.error(f"Direct reply generation failed: {e}")
            # V3.3.7: Fallback without brand intro
            return f"Hi! How can I help you with {cat_name} today?"

    async def _generate_emergency_response(self, cat_name, user_input, emergency_data, detected_language='auto'):
        """
        V3.3.10: Generate emergency alert response using LLM for proper bilingual support.

        Args:
            cat_name: Cat's name
            user_input: User's original question
            emergency_data: Emergency alert data from shared store
            detected_language: Detected user language

        Returns:
            str: Natural language emergency response
        """
        alert_type = emergency_data.get('type', 'health_alert')
        severity = emergency_data.get('severity', 'high')
        details = emergency_data.get('details', '')

        system_prompt = """你是专业的猫咪健康紧急顾问。
回复用户的紧急健康问题时：
1. 先确认问题的严重性
2. 提供立即可执行的步骤
3. 明确是否需要立即就医
4. 保持冷静但紧迫的语气

IMPORTANT: 用用户提问的语言回复。"""

        user_message = f"""用户问题: {user_input}
猫咪名字: {cat_name}
警报类型: {alert_type}
严重程度: {severity}
详情: {details}

请根据以上信息，用用户的语言提供紧急健康建议。包括：
- 问题评估
- 立即行动步骤
- 是否需要就医
- 注意事项"""

        try:
            response = await async_call_llm(user_message, system_prompt=system_prompt, detected_language=detected_language)
            return response.strip()
        except Exception as e:
            logger.error(f"Emergency response generation failed: {e}")
            # Bilingual fallback
            return f"⚠️ 紧急提醒 | Emergency Alert\n\n{cat_name}可能需要紧急关注。请立即联系兽医。\n{cat_name} may need urgent attention. Please contact a veterinarian immediately."

    async def _generate_device_offline_response(self, cat_name, user_input, offline_data, detected_language='auto'):
        """
        V3.3.10: Generate device offline response using LLM for proper bilingual support.

        Args:
            cat_name: Cat's name
            user_input: User's original question
            offline_data: Device offline alert data from shared store
            detected_language: Detected user language

        Returns:
            str: Natural language device offline response
        """
        device_type = offline_data.get('device_type', 'collar')
        last_seen = offline_data.get('last_seen', 'unknown')
        battery_level = offline_data.get('battery_level', 'unknown')

        system_prompt = """你是智能猫咪设备的技术支持助手。
当用户询问设备离线问题时：
1. 解释可能的原因
2. 提供排障步骤
3. 建议解决方案

IMPORTANT: 用用户提问的语言回复。"""

        user_message = f"""用户问题: {user_input}
猫咪名字: {cat_name}
设备类型: {device_type}
最后在线时间: {last_seen}
电池电量: {battery_level}

请根据以上信息，用用户的语言提供设备排障建议。包括：
- 可能的离线原因
- 检查步骤
- 解决方案"""

        try:
            response = await async_call_llm(user_message, system_prompt=system_prompt, detected_language=detected_language)
            return response.strip()
        except Exception as e:
            logger.error(f"Device offline response generation failed: {e}")
            # Bilingual fallback
            return f"📡 设备状态 | Device Status\n\n{cat_name}的设备暂时离线。请检查设备电量和网络连接。\n{cat_name}'s device is temporarily offline. Please check battery and network connection."

    async def _generate_pain_alert_response(self, cat_name, pain_score, vision_analysis, user_input, detected_language='auto'):
        """
        Generate pain alert response with professional advice.

        V3.3.7: Uses Prompt Caching - static system prompt + dynamic user message.
        """
        mood = vision_analysis.get('mood', 'unknown') if vision_analysis else 'unknown'
        alertness = vision_analysis.get('alertness', 'unknown') if vision_analysis else 'unknown'
        analysis_details = vision_analysis.get('analysis', {}) if vision_analysis else {}

        # Get current date (always English format for template)
        current_date = get_current_date_str('en')

        # Extract specific pain indicators
        pain_indicators = []
        if analysis_details:
            if 'ear_position' in str(analysis_details):
                pain_indicators.append("abnormal ear position")
            if 'orbital_tightening' in str(analysis_details) or 'squinting' in str(analysis_details).lower():
                pain_indicators.append("squinting eyes")
            if 'muzzle_tension' in str(analysis_details):
                pain_indicators.append("facial tension")

        pain_indicators_text = ", ".join(pain_indicators) if pain_indicators else "overall facial expression shows discomfort"

        # V3.3.7: Use cacheable system prompt (static) + user message (dynamic)
        system_prompt = PROMPTS['cacheable_system']['pain_alert']
        user_message = PROMPTS['user_message']['pain_alert'].format(
            pain_score=pain_score,
            mood=mood,
            alertness=alertness,
            pain_indicators=pain_indicators_text,
            analysis_details=json.dumps(analysis_details, ensure_ascii=False) if analysis_details else 'None',
            cat_name=cat_name,
            user_input=user_input if user_input else '(User sent image/video)',
            current_date=current_date
        )

        try:
            # V3.3.7: Use Prompt Caching - LLM auto-responds in user's language
            response = await async_call_llm(user_message, system_prompt=system_prompt, detected_language=detected_language)
            return response.strip()
        except Exception as e:
            logger.error(f"Pain alert response generation failed: {e}")
            # V3.3.7: Fallback response without brand intro
            severity = "severe" if pain_score >= 8 else "significant"
            return f"""⚠️ Urgent Notice: {cat_name}'s pain score is {pain_score}/10, showing {severity} signs of discomfort.

🔍 Analysis: Detected {pain_indicators_text}, mood state is {mood}.

💊 Recommendations:
1. Immediately check for any injuries or abnormalities
2. Monitor for decreased appetite or hiding behavior
3. If symptoms persist beyond 24 hours, seek veterinary care promptly

Feel free to ask if you have other questions."""

    def _normalize_alert_key(self, alert) -> tuple:
        """
        Normalize IoT alert keys to template keys and return optional description.

        Returns:
            (normalized_key, description)
        """
        alias_map = {
            'heart_rate_high': 'high_heart_rate',
            'hr_high': 'high_heart_rate',
            'heart_rate_low': 'low_heart_rate',
            'hr_low': 'low_heart_rate',
            'battery_low': 'low_battery',
            'activity_low': 'low_activity',
            'activity_high': 'high_activity'
        }

        description = ''
        if isinstance(alert, dict):
            raw_key = alert.get('type') or alert.get('alert') or alert.get('code') or alert.get('name') or ''
            description = alert.get('message') or alert.get('description') or alert.get('detail') or ''
        else:
            raw_key = str(alert) if alert is not None else ''

        key_lower = raw_key.lower()
        normalized_key = alias_map.get(key_lower, key_lower)
        return normalized_key, description or raw_key

    # V3.3.10: Intents where prey_detected alert should be shown
    # Only show prey alerts for relevant IoT/status queries, not emergency or simple greetings
    PREY_ALERT_ALLOWED_INTENTS = {
        'prey_query', 'daily_analysis', 'status_summary', 'cat_door_event',
        'cat_door_status', 'weekly_report', 'monthly_report', 'behavior_pattern'
    }

    def _format_alert_prefix(self, iot_summary: dict, router_action: str = '') -> str:
        """Format IoT alerts for response prefix.

        V3.3.10: Prey alerts are only shown for relevant intents to avoid
        cluttering emergency responses or simple greetings with unrelated alerts.
        """
        if not iot_summary:
            return ""

        alerts = iot_summary.get('alerts') or []
        if isinstance(alerts, dict):
            alerts = [alerts]
        elif not isinstance(alerts, (list, tuple)):
            alerts = [alerts]

        alert_messages = []
        for alert in alerts:
            key, description = self._normalize_alert_key(alert)
            if not key and not description:
                continue

            # V3.3.10: Filter prey_detected alerts based on intent
            # Only show prey alerts for relevant intents (status queries, daily analysis, etc.)
            if key == 'prey_detected' and router_action not in self.PREY_ALERT_ALLOWED_INTENTS:
                logger.debug(f"Skipping prey_detected alert for intent: {router_action}")
                continue

            template = self.IOT_ALERT_RESPONSE_TEMPLATES.get(key)
            if template:
                alert_messages.append(template)
            elif description:
                alert_messages.append(f"⚠️ {description}")
            else:
                alert_messages.append(f"⚠️ Alert: {key}")

        return "\n".join(alert_messages)

    def _format_trend_summary(self, trends) -> str:
        """Format IoT trends for prompt/response inclusion."""
        if not trends:
            return ""

        trend_parts = []
        if isinstance(trends, dict):
            hr_trend = trends.get('heart_rate') or trends.get('heart_rate_trend') or trends.get('hr')
            activity_trend = trends.get('activity') or trends.get('activity_level')
            sleep_trend = trends.get('sleep')
            outdoor_trend = trends.get('outdoor')
            # V3.3.10: Universal trend labels (emoji + English)
            if hr_trend:
                trend_parts.append(f"❤️ HR: {hr_trend}")
            if activity_trend:
                trend_parts.append(f"🏃 Activity: {activity_trend}")
            if sleep_trend:
                trend_parts.append(f"😴 Sleep: {sleep_trend}")
            if outdoor_trend:
                trend_parts.append(f"🏠 Outdoor: {outdoor_trend}")
        elif isinstance(trends, list):
            for item in trends[:3]:
                trend_parts.append(str(item))
        else:
            trend_parts.append(str(trends))

        if not trend_parts:
            return ""

        # V3.3.10: Universal trend label
        return "📊 Trends: " + ", ".join(trend_parts)

    def _format_degraded_notice(self, prep_res: dict) -> str:
        """Format user-friendly notice when IoT data is missing or degraded."""
        if not prep_res:
            return ""

        if prep_res.get('missing_cat_id'):
            return self.DEGRADED_PROMPTS.get('missing_cat_id', '')

        if prep_res.get('iot_load_degraded'):
            error_types = prep_res.get('iot_error_types') or []
            errors = prep_res.get('iot_errors') or []
            combined = [str(e).lower() for e in (error_types + errors)]
            if any('timeout' in e for e in combined):
                return self.DEGRADED_PROMPTS.get('timeout', '')
            # V3.3.10: Universal fallback message
            return "⚠️ [Data loading issue / 数据加载波动] - Using available info"

        return ""

    def _format_product_recommendation(self, prep_res: dict) -> str:
        """
        V3.4.0: Generate product recommendation when user has no devices or cats.

        Args:
            prep_res: Preparation result dict containing device/cat status

        Returns:
            str: Formatted product recommendation or empty string if not applicable
        """
        if not prep_res:
            return ""

        # Check if user has no devices (missing_cat_id indicates no cat/device bound)
        has_no_device = prep_res.get('missing_cat_id', False)
        # Check if IoT context is empty/degraded (indicating no active devices)
        has_no_iot_data = not prep_res.get('iot_context') or prep_res.get('iot_context') == '无 IoT 设备数据'
        # Check if there's no cat profile
        has_no_cat = prep_res.get('cat_name') in ['您的猫咪', 'Your cat', None, '']

        # Determine recommendation type
        recommendation_type = None
        if has_no_device or has_no_iot_data:
            recommendation_type = 'no_device'
        elif has_no_cat:
            recommendation_type = 'no_cat'

        if not recommendation_type:
            return ""

        # Detect language from user input
        user_input = prep_res.get('user_input', '')
        # Simple language detection: check for Chinese characters
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in user_input)
        lang = 'zh' if has_chinese else 'en'

        try:
            return get_product_recommendation(recommendation_type, lang)
        except Exception as e:
            logger.error(f"Failed to generate product recommendation: {e}")
            return ""

    def _apply_response_enhancements(self, response: str, prep_res: dict) -> str:
        """
        Inject IoT alerts, trends, degraded notices, and product recommendations into final response.

        Alerts are placed at the top to highlight urgent information.
        Product recommendations are placed at the end to guide users to purchase.

        V3.3.10: Prey alerts are filtered based on router_action to avoid
        showing irrelevant alerts for emergency or simple greeting responses.

        V3.4.0: Added product recommendation for users without devices or cats.
        """
        if not response:
            return response

        iot_summary = prep_res.get('iot_summary', {}) if isinstance(prep_res, dict) else {}
        router_action = prep_res.get('router_action', '') if isinstance(prep_res, dict) else ''

        # V3.3.10: Pass router_action to filter prey alerts appropriately
        alert_prefix = self._format_alert_prefix(iot_summary, router_action)
        trend_note = self._format_trend_summary((iot_summary or {}).get('trends'))
        degraded_note = self._format_degraded_notice(prep_res)

        # V3.4.0: Generate product recommendation for users without devices/cats
        product_recommendation = self._format_product_recommendation(prep_res)

        # Build prefix parts (alerts, degraded notice, trends)
        prefix_parts = []
        if alert_prefix:
            prefix_parts.append(alert_prefix)
        if degraded_note:
            prefix_parts.append(degraded_note)
        if trend_note:
            prefix_parts.append(trend_note)

        # Apply prefix
        if prefix_parts:
            response = "\n\n".join(prefix_parts) + "\n\n" + response

        # V3.4.0: Append product recommendation at the end (non-intrusive)
        if product_recommendation:
            response = response + "\n\n---\n\n" + product_recommendation

        return response

    def _format_memory_context(self, memory_results, limit: int = 3, header: str = None):
        """
        Format Memory results for prompt inclusion.

        Args:
            memory_results: List of Memory result dicts with timestamp, turn_content, similarity_score
            limit: Max number of conversation turns to include
            header: Optional header text, supports {count} placeholder

        Returns:
            str: Formatted Memory context or empty string if no results
        """
        if not memory_results:
            return ""

        # Limit to top 3 results to avoid prompt bloat
        top_results = memory_results[:limit]

        formatted_turns = []
        for idx, result in enumerate(top_results, 1):
            # Extract metadata from Memory result
            timestamp = result.get('timestamp', 'Unknown time')
            turn_content = result.get('turn_content', '')

            # Parse turn_content if it's a JSON string
            if isinstance(turn_content, str):
                try:
                    turn_data = json.loads(turn_content)
                    user_input = turn_data.get('user_input', '')
                    assistant_response = turn_data.get('assistant_response', '')
                except:
                    # If parsing fails, use raw content
                    user_input = turn_content
                    assistant_response = ''
            elif isinstance(turn_content, dict):
                user_input = turn_content.get('user_input', '')
                assistant_response = turn_content.get('assistant_response', '')
            else:
                continue

            # Format conversational turn
            if user_input and assistant_response:
                formatted_turn = f"Turn {idx} ({timestamp}):\nUser: {user_input}\nAssistant: {assistant_response}"
                formatted_turns.append(formatted_turn)

        if not formatted_turns:
            return ""

        count = len(formatted_turns)
        if header:
            try:
                header_text = header.format(count=count)
            except Exception:
                header_text = header
        else:
            header_text = f"Recent {count} conversation turns"

        memory_context = f"{header_text}:\n\n" + "\n\n".join(formatted_turns)

        return memory_context

    def _format_core_rules_context(self, core_rules: dict) -> str:
        """
        Format Layer 1 Core Rules for prompt inclusion.

        Args:
            core_rules: Dict containing core rules from CoreRulesNode

        Returns:
            str: Formatted core rules context, prioritizing emergency and safety info
        """
        if not core_rules:
            return ""

        context_parts = []

        # Emergency protocol is highest priority
        emergency = core_rules.get('emergency_protocol', '')
        if emergency:
            # Extract critical sections only
            context_parts.append("**Emergency Guidelines:**")
            context_parts.append("- Refer to emergency protocol for critical symptoms")
            context_parts.append("- Prioritize: breathing issues, inability to urinate, severe bleeding, poisoning")

        # Toxic foods - always include summary
        toxic = core_rules.get('toxic_foods', '')
        if toxic:
            context_parts.append("\n**Toxic Substances Warning:**")
            context_parts.append("- FATAL: Lilies, onions, garlic, xylitol, acetaminophen")
            context_parts.append("- HIGH RISK: Chocolate, grapes, alcohol, caffeine")
            context_parts.append("- If ingestion suspected: DO NOT induce vomiting, contact vet immediately")

        # Health thresholds
        health = core_rules.get('health_warnings', '')
        if health:
            context_parts.append("\n**Health Thresholds:**")
            context_parts.append("- Normal temp: 38.1-39.2°C (100.5-102.5°F)")
            context_parts.append("- Emergency temp: >40.5°C or <37.5°C")
            context_parts.append("- No urination >24h: EMERGENCY (especially male cats)")

        return "\n".join(context_parts) if context_parts else ""

    def _format_structured_matches_context(self, structured_matches: dict) -> str:
        """
        Format Layer 2 Structured Knowledge matches for prompt inclusion.

        Args:
            structured_matches: Dict containing matches from StructuredKnowledgeNode

        Returns:
            str: Formatted structured matches context
        """
        if not structured_matches:
            return ""

        context_parts = []

        # Symptom matches
        symptoms = structured_matches.get('symptoms', [])
        if symptoms:
            context_parts.append("**Symptom Matches:**")
            for match in symptoms[:3]:  # Limit to top 3
                context_parts.append(f"- {match.get('matched_symptom')}: Possible {match.get('condition_name_zh')} ({match.get('condition_name_en')})")
                context_parts.append(f"  Urgency: {match.get('urgency', 'unknown')}")
                home_care = match.get('home_care', [])
                if home_care:
                    context_parts.append(f"  Home care: {', '.join(home_care[:2])}")
                vet_triggers = match.get('vet_triggers', [])
                if vet_triggers:
                    context_parts.append(f"  Vet triggers: {', '.join(vet_triggers[:2])}")

        # Breed matches
        breeds = structured_matches.get('breeds', [])
        if breeds:
            context_parts.append("\n**Breed Information:**")
            for breed in breeds[:2]:  # Limit to top 2
                context_parts.append(f"- {breed.get('name_zh')} ({breed.get('name_en')})")
                health_concerns = breed.get('health_concerns', [])
                if health_concerns:
                    concern_names = [c.get('condition', c) if isinstance(c, dict) else str(c) for c in health_concerns[:3]]
                    context_parts.append(f"  Health concerns: {', '.join(concern_names)}")
                notes = breed.get('special_notes')
                if notes:
                    context_parts.append(f"  Note: {notes[:100]}...")

        # Medication matches (especially banned ones)
        medications = structured_matches.get('medications', [])
        if medications:
            context_parts.append("\n**Medication Information:**")
            for med in medications[:3]:
                if med.get('type') == 'BANNED':
                    context_parts.append(f"- **BANNED**: {med.get('name')} - {med.get('reason')}")
                else:
                    context_parts.append(f"- {med.get('name')}: {med.get('dosage')} ({med.get('route')})")
                    warnings = med.get('warnings', [])
                    if warnings:
                        context_parts.append(f"  Warnings: {', '.join(warnings[:2])}")

        # Vaccination info
        vaccination = structured_matches.get('vaccination')
        if vaccination:
            context_parts.append("\n**Vaccination Info Available:** Yes - refer to structured data for schedule")

        return "\n".join(context_parts) if context_parts else ""

    def _generate_fallback_response(self, router_action, structured_data, cat_name, detected_language='auto'):
        """
        Generate fallback response when LLM call fails.

        V3.3.10: Bilingual fallback responses for better user experience.
        """
        # V3.3.10: Intent-specific bilingual fallbacks
        fallbacks = {
            'medical_query': f"关于{cat_name}的健康问题，我已完成初步分析。如症状持续，建议咨询专业兽医。\nRegarding {cat_name}'s health issue, I've completed a preliminary analysis. If symptoms persist, please consult a veterinarian.",
            'daily_analysis': f"{cat_name}今天整体状态良好，继续保持规律的饮食和活动！\n{cat_name} is doing well today. Keep up the regular diet and activity!",
            'status_summary': f"{cat_name}当前状态正常。如需详细信息，请告诉我您想了解哪个方面。\n{cat_name}'s current status is normal. Let me know which aspect you'd like to learn about.",
            'weekly_report': f"本周{cat_name}的整体表现良好。详细的健康趋势分析请稍后查看。\nThis week {cat_name} performed well overall. Detailed health trend analysis will be available shortly.",
            'monthly_report': f"本月{cat_name}的健康数据已记录。月度报告正在生成中。\nThis month's health data for {cat_name} has been recorded. Monthly report is being generated.",
            'behavior_pattern': f"{cat_name}的行为模式分析正在处理中。\nBehavior pattern analysis for {cat_name} is being processed.",
            'care_advice': f"关于{cat_name}的护理建议，请确保充足的饮水和适当的活动。\nFor {cat_name}'s care, ensure adequate water and appropriate activity.",
            'dietary_consultation': f"关于{cat_name}的饮食，建议选择适龄的优质猫粮。\nFor {cat_name}'s diet, recommend age-appropriate quality cat food.",
            'prey_query': f"已查询{cat_name}的猫门记录。\nQueried {cat_name}'s cat door records.",
            'location_query': f"已查询{cat_name}的位置信息。\nQueried {cat_name}'s location information.",
            'collar_ingestion': f"已获取{cat_name}的项圈数据。\nRetrieved {cat_name}'s collar data.",
            'direct_reply': f"你好！有什么可以帮助{cat_name}的吗？\nHi! How can I help with {cat_name}?",
        }
        return fallbacks.get(router_action, f"已收到关于{cat_name}的信息。如有其他问题，请随时提问。\nReceived information about {cat_name}. Feel free to ask other questions.")

    async def _two_stage_generate(
        self,
        router_action,
        structured_data,
        user_input,
        cat_name,
        vision_analysis,
        rag_results,
        detected_language='auto',
        memory_results=None,
        core_rules=None,
        structured_matches=None,
        skill_context=None,
        iot_context=None,
        fused_context=None,
        iot_summary=None
    ):
        """
        V3.3.9: Two-stage response generation with fused context + IoT alerts/trends.

        Stage 1: LLM2 (Novita AI qwen3-vl) generates Chinese analysis content
        Stage 2: LLM1 (gpt-5-nano) converts to user's language naturally

        Context Sources (V3.3.9 Three-Path Architecture):
        - Fused context (IoT+SKILL+RAG prioritized) when available
        - SKILL: Progressive loading knowledge (skill_context)
        - IoT: Real-time device data (iot_context) + alerts/trends
        - RAG: Semantic search results (rag_results)
        - Layer 1: core_rules (emergency protocols, toxic foods)
        - Layer 2: structured_matches (symptom matches, medication info)
        - Memory: Historical consultations (memory_results)
        """
        progress_cb = getattr(self, '_progress_callback', None)

        # Prepare data summaries
        data_summary = ""
        if structured_data:
            if isinstance(structured_data, dict):
                data_summary = json.dumps(structured_data, ensure_ascii=False, indent=2)
            else:
                data_summary = str(structured_data)

        vision_context = ""
        if vision_analysis:
            vision_context = json.dumps(vision_analysis, ensure_ascii=False, indent=2)

        rag_context = ""
        if rag_results:
            rag_context = json.dumps(rag_results[:3] if isinstance(rag_results, list) else rag_results, ensure_ascii=False, indent=2)

        alerts_present = bool((iot_summary or {}).get('alerts'))

        # IMPL-005: Format Memory context (prioritize alerts with concise history)
        memory_context = self._format_memory_context(
            memory_results or [],
            limit=2 if alerts_present else 3,
            header="历史参考（相似咨询）{count}条" if alerts_present else None
        )
        logger.debug(f"Memory context length: {len(memory_context)} chars")

        # Four-Layer RAG: Format Layer 1 (Core Rules) context
        core_rules_context = self._format_core_rules_context(core_rules or {})
        logger.debug(f"Core rules context length: {len(core_rules_context)} chars")

        # Four-Layer RAG: Format Layer 2 (Structured Knowledge) context
        structured_matches_context = self._format_structured_matches_context(structured_matches or {})
        logger.debug(f"Structured matches context length: {len(structured_matches_context)} chars")

        # V3.3.9: Format SKILL and IoT context
        fused_context_str = (fused_context or "").strip()
        skill_context_str = skill_context or "无 SKILL 知识加载"
        iot_context_str = iot_context or "无 IoT 设备数据"
        trend_context = self._format_trend_summary((iot_summary or {}).get('trends'))
        alert_context = self._format_alert_prefix(iot_summary or {})

        # Prioritize fused context when available to avoid fragmented prompts
        primary_context_sections = []
        if fused_context_str:
            primary_context_sections.append(f"## 融合上下文 (优先)\n{fused_context_str}")
            skill_context_str = "内容已汇总于融合上下文"
            iot_context_str = "内容已汇总于融合上下文"

        # Add IoT alerts/trends explicitly
        if alert_context:
            primary_context_sections.append(f"## IoT Alerts\n{alert_context}")
        if trend_context:
            primary_context_sections.append(f"## 近期趋势\n{trend_context}")
            if not fused_context_str and iot_context_str:
                iot_context_str = f"{iot_context_str}\n{trend_context}"

        # ===== Stage 1: LLM2 generates Chinese analysis =====
        llm2_system = PROMPTS['two_stage']['llm2_system']
        llm2_user = PROMPTS['two_stage']['llm2_user'].format(
            user_input=user_input,
            cat_name=cat_name,
            core_rules=core_rules_context or "无核心规则匹配",
            structured_matches=structured_matches_context or "无结构化知识匹配",
            data_summary=data_summary or "无分析数据",
            vision_context=vision_context or "无图像分析",
            rag_context=rag_context or "无知识库参考",
            memory_context=memory_context or "无历史对话上下文",
            # V3.3.9: SKILL/IoT Context
            skill_context=skill_context_str,
            iot_context=iot_context_str
        )

        if primary_context_sections:
            llm2_user = "\n\n".join(primary_context_sections + [llm2_user])

        logger.info(f"Two-stage Stage 1: LLM2 generating Chinese analysis for {router_action}")
        analysis_content = await async_call_novita_llm(
            prompt=llm2_user,
            system_prompt=llm2_system,
            temperature=0.7
        )
        logger.info(f"Two-stage Stage 1 complete: analysis length={len(analysis_content)}")

        # ===== Stage 2: LLM1 converts to user's language =====
        # Determine target language hint
        target_language = "the same language as the user's input"
        if detected_language == 'zh':
            target_language = "Chinese (中文)"
        elif detected_language == 'en':
            target_language = "English"

        llm1_system = PROMPTS['two_stage']['llm1_system']
        llm1_user = PROMPTS['two_stage']['llm1_user'].format(
            user_input=user_input,
            cat_name=cat_name,
            analysis_content=analysis_content,
            target_language=target_language
        )

        logger.info(f"Two-stage Stage 2: LLM1 converting to {detected_language}")
        if progress_cb:
            tokens = []
            token_stream = await async_call_llm(
                prompt=llm1_user,
                system_prompt=llm1_system,
                detected_language=detected_language,
                stream=True
            )
            async for token in token_stream:
                tokens.append(token)
                await progress_cb({
                    'type': 'streaming',
                    'node': self.__class__.__name__,
                    'token': token
                })
            final_response = ''.join(tokens)
        else:
            final_response = await async_call_llm(
                prompt=llm1_user,
                system_prompt=llm1_system,
                detected_language=detected_language
            )
        logger.info(f"Two-stage Stage 2 complete: response length={len(final_response)}")

        return final_response


# =============================================================================
# Four-Layer RAG Architecture - Layer 1 & Layer 2 Nodes
# =============================================================================

class CoreRulesNode(AsyncNode):
    """
    Layer 1: Core Rules Node - 100% loaded every conversation.

    Loads system rules, emergency protocols, toxic food lists, and health warnings
    from config/core_rules/ directory. These rules are always available and take
    priority over other knowledge sources.

    Output:
    - shared['core_rules']: Dict containing all core rule categories
    - shared['emergency_keywords']: List of emergency trigger keywords
    - shared['toxic_items']: Quick-lookup dict for toxic substances
    """

    CORE_RULES_DIR = "config/core_rules"

    # Emergency keywords for quick detection
    EMERGENCY_KEYWORDS = [
        # Chinese
        "无法排尿", "不能排尿", "排不出尿", "尿不出来",
        "呼吸困难", "喘不过气", "无法呼吸",
        "大量出血", "止不住血", "流血不止",
        "中毒", "吃了毒", "误食",
        "抽搐", "癫痫", "痉挛",
        "昏迷", "失去意识", "晕倒",
        "高烧", "体温过高", "发烧40",
        # English
        "can't urinate", "unable to urinate", "not urinating",
        "difficulty breathing", "can't breathe",
        "heavy bleeding", "won't stop bleeding",
        "poisoned", "ate poison", "ingested toxic",
        "seizure", "convulsion",
        "unconscious", "collapsed",
        "high fever", "temperature over 40"
    ]

    async def prep_async(self, shared):
        """Load all core rule files from config/core_rules/."""
        import os
        from pathlib import Path

        rules_dir = Path(self.CORE_RULES_DIR)
        core_rules = {}

        # Expected rule files
        rule_files = {
            'system_rules': 'system_rules.md',
            'emergency_protocol': 'emergency_protocol.md',
            'toxic_foods': 'toxic_foods.md',
            'health_warnings': 'health_warnings.md'
        }

        for key, filename in rule_files.items():
            file_path = rules_dir / filename
            try:
                if file_path.exists():
                    content = file_path.read_text(encoding='utf-8')
                    core_rules[key] = content
                    logger.debug(f"Loaded core rule: {filename} ({len(content)} chars)")
                else:
                    logger.warning(f"Core rule file not found: {file_path}")
                    core_rules[key] = ""
            except Exception as e:
                logger.error(f"Failed to load core rule {filename}: {e}")
                core_rules[key] = ""

        return {
            'core_rules': core_rules,
            'rules_loaded': len([v for v in core_rules.values() if v])
        }

    async def exec_async(self, prep_res):
        """Process core rules and extract quick-lookup data."""
        core_rules = prep_res['core_rules']

        # Build toxic items quick-lookup from toxic_foods content
        toxic_items = self._extract_toxic_items(core_rules.get('toxic_foods', ''))

        # Build emergency triggers from emergency_protocol
        emergency_triggers = self._extract_emergency_triggers(
            core_rules.get('emergency_protocol', '')
        )

        return {
            'core_rules': core_rules,
            'toxic_items': toxic_items,
            'emergency_triggers': emergency_triggers,
            'rules_loaded': prep_res['rules_loaded']
        }

    async def post_async(self, shared, prep_res, exec_res):
        """Store core rules in shared context."""
        shared['core_rules'] = exec_res['core_rules']
        shared['emergency_keywords'] = self.EMERGENCY_KEYWORDS
        shared['toxic_items'] = exec_res['toxic_items']
        shared['emergency_triggers'] = exec_res['emergency_triggers']

        logger.info(f"CoreRulesNode: Loaded {exec_res['rules_loaded']} rule files, "
                   f"{len(exec_res['toxic_items'])} toxic items indexed")

        return 'core_rules_loaded'

    def _extract_toxic_items(self, toxic_content: str) -> dict:
        """
        Dynamically extract toxic items from markdown content.

        Parses markdown tables in toxic_foods.md to build quick-lookup dictionary.
        Falls back to hardcoded values if parsing fails.
        """
        import re

        toxic_items = {
            'highly_toxic': [],
            'toxic_plants': [],
            'toxic_medications': []
        }

        if not toxic_content:
            logger.warning("No toxic content provided, using fallback values")
            return self._get_fallback_toxic_items()

        try:
            # Parse markdown tables for toxic items
            # Table row pattern: | **ItemName** | ... | ... | ... |
            table_row_pattern = re.compile(r'\|\s*\*\*([^*|]+)\*\*[^|]*\|')

            lines = toxic_content.split('\n')
            current_section = None

            for line in lines:
                line_lower = line.lower().strip()

                # Detect section headers
                if '### foods' in line_lower or 'highly toxic' in line_lower:
                    current_section = 'highly_toxic'
                elif '### plants' in line_lower:
                    current_section = 'toxic_plants'
                elif '### medications' in line_lower:
                    current_section = 'toxic_medications'
                elif '## moderately' in line_lower or '## safe' in line_lower:
                    current_section = None  # Stop parsing highly toxic section

                # Parse table rows
                if current_section and line.startswith('|'):
                    match = table_row_pattern.search(line)
                    if match:
                        item_name = match.group(1).strip()
                        # Skip header rows
                        if item_name.lower() not in ['substance', 'plant', 'medication']:
                            # Extract primary name (before any parentheses or slash)
                            primary_name = re.split(r'[(/]', item_name)[0].strip().lower()
                            if primary_name and primary_name not in toxic_items[current_section]:
                                toxic_items[current_section].append(primary_name)
                                # Also add full item name for better matching
                                full_lower = item_name.lower()
                                if full_lower not in toxic_items[current_section]:
                                    toxic_items[current_section].append(full_lower)

            # Verify we extracted items, fall back if empty
            total_items = sum(len(v) for v in toxic_items.values())
            if total_items == 0:
                logger.warning("No toxic items parsed from markdown, using fallback")
                return self._get_fallback_toxic_items()

            logger.debug(f"Extracted toxic items: {sum(len(v) for v in toxic_items.values())} total")
            return toxic_items

        except Exception as e:
            logger.error(f"Failed to parse toxic content: {e}, using fallback")
            return self._get_fallback_toxic_items()

    def _get_fallback_toxic_items(self) -> dict:
        """Fallback hardcoded toxic items if parsing fails."""
        return {
            'highly_toxic': [
                'onion', 'garlic', 'leek', 'grape', 'raisin', 'chocolate',
                'xylitol', 'alcohol', 'caffeine', 'raw dough',
                '洋葱', '大蒜', '韭菜', '葡萄', '葡萄干', '巧克力',
                '木糖醇', '酒精', '咖啡因', '生面团'
            ],
            'toxic_plants': [
                'lily', 'sago palm', 'tulip', 'azalea', 'oleander',
                '百合', '苏铁', '郁金香', '杜鹃花', '夹竹桃'
            ],
            'toxic_medications': [
                'acetaminophen', 'tylenol', 'ibuprofen', 'advil', 'aspirin',
                '对乙酰氨基酚', '泰诺', '布洛芬', '阿司匹林'
            ]
        }

    def _extract_emergency_triggers(self, emergency_content: str) -> list:
        """
        Dynamically extract emergency triggers from markdown content.

        Parses emergency_protocol.md to build emergency trigger conditions.
        Falls back to hardcoded values if parsing fails.
        """
        import re

        if not emergency_content:
            logger.warning("No emergency content provided, using fallback values")
            return self._get_fallback_emergency_triggers()

        try:
            triggers = []
            lines = emergency_content.split('\n')
            in_critical_section = False

            # Define keyword mappings for recognized conditions
            condition_mappings = {
                'breathing': {'condition': 'breathing_difficulty', 'urgency': 'critical'},
                'breath': {'condition': 'breathing_difficulty', 'urgency': 'critical'},
                'urinate': {'condition': 'urinary_blockage', 'urgency': 'critical'},
                'urine': {'condition': 'urinary_blockage', 'urgency': 'critical'},
                'bleeding': {'condition': 'severe_bleeding', 'urgency': 'critical'},
                'poison': {'condition': 'poisoning', 'urgency': 'critical'},
                'seizure': {'condition': 'seizure', 'urgency': 'critical'},
                'convulsion': {'condition': 'seizure', 'urgency': 'critical'},
                'collapse': {'condition': 'collapse', 'urgency': 'critical'},
                'unconscious': {'condition': 'collapse', 'urgency': 'critical'},
                'temperature': {'condition': 'temperature_emergency', 'urgency': 'critical'},
                'trauma': {'condition': 'trauma', 'urgency': 'critical'},
                'labor': {'condition': 'birth_emergency', 'urgency': 'critical'},
            }

            found_conditions = set()

            for line in lines:
                line_lower = line.lower().strip()

                # Detect CRITICAL section
                if '### critical' in line_lower or 'immediate' in line_lower:
                    in_critical_section = True
                elif line.startswith('### ') and 'critical' not in line_lower:
                    in_critical_section = False

                # Parse list items in critical section (lines starting with -)
                if in_critical_section and line.strip().startswith('-'):
                    symptom_text = line.strip('- ').strip()

                    # Match against known conditions
                    for keyword, mapping in condition_mappings.items():
                        if keyword in line_lower and mapping['condition'] not in found_conditions:
                            found_conditions.add(mapping['condition'])
                            # Extract keywords from the symptom text
                            keywords = [symptom_text.split('(')[0].strip().lower()]
                            triggers.append({
                                'condition': mapping['condition'],
                                'urgency': mapping['urgency'],
                                'keywords': keywords,
                                'source_text': symptom_text
                            })
                            break

            if not triggers:
                logger.warning("No emergency triggers parsed from markdown, using fallback")
                return self._get_fallback_emergency_triggers()

            logger.debug(f"Extracted {len(triggers)} emergency triggers from markdown")
            return triggers

        except Exception as e:
            logger.error(f"Failed to parse emergency content: {e}, using fallback")
            return self._get_fallback_emergency_triggers()

    def _get_fallback_emergency_triggers(self) -> list:
        """Fallback hardcoded emergency triggers if parsing fails."""
        return [
            {'condition': 'urinary_blockage', 'urgency': 'critical',
             'keywords': ['无法排尿', "can't urinate", '24小时没尿']},
            {'condition': 'breathing_difficulty', 'urgency': 'critical',
             'keywords': ['呼吸困难', 'difficulty breathing', '张嘴呼吸']},
            {'condition': 'poisoning', 'urgency': 'critical',
             'keywords': ['中毒', 'poisoned', '误食']},
            {'condition': 'seizure', 'urgency': 'critical',
             'keywords': ['抽搐', 'seizure', '癫痫']},
            {'condition': 'severe_bleeding', 'urgency': 'critical',
             'keywords': ['大量出血', 'heavy bleeding', '止不住血']},
            {'condition': 'collapse', 'urgency': 'critical',
             'keywords': ['昏迷', 'collapsed', '失去意识']}
        ]


class StructuredKnowledgeNode(AsyncNode):
    """
    Layer 2: Structured Knowledge Node - Precise keyword matching.

    Loads structured data from .memory/categories/ for exact matching queries.
    This layer handles:
    - Symptom-disease mapping (symptoms.json)
    - Vaccination schedules (vaccination.md)
    - Medication dosages (medication_dosage.json)
    - Breed information (breed_info.json)

    Output:
    - shared['structured_knowledge']: Dict with all structured data
    - shared['symptom_matches']: Matched symptoms from user query
    - shared['breed_matches']: Matched breed info if applicable
    """

    MEMORY_DIR = ".memory"
    INDEX_FILE = ".memory/index.json"

    async def prep_async(self, shared):
        """Load index and prepare for query matching."""
        from pathlib import Path

        request = shared.get('request', {}) if isinstance(shared, dict) else {}
        user_input = request.get('user_input') or shared.get('question', '')

        # Load index
        index_path = Path(self.INDEX_FILE)
        index = {}
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding='utf-8'))
            except Exception as e:
                logger.warning(f"Failed to load memory index: {e}")

        return {
            'user_input': user_input,
            'index': index,
            'memory_dir': Path(self.MEMORY_DIR)
        }

    async def exec_async(self, prep_res):
        """Load and match structured knowledge based on user query."""
        user_input = prep_res['user_input']
        index = prep_res['index']
        memory_dir = prep_res['memory_dir']

        # Type guard: ensure user_input is a string for .lower() calls
        if not isinstance(user_input, str):
            user_input = str(user_input) if user_input else ''

        structured_data = {}
        matches = {
            'symptoms': [],
            'breeds': [],
            'medications': [],
            'vaccination': None
        }

        # Load each category based on index
        categories = index.get('categories', {})

        for cat_key, cat_info in categories.items():
            file_path = memory_dir / cat_info.get('file', '')
            if not file_path.exists():
                continue

            try:
                content = file_path.read_text(encoding='utf-8')

                if cat_info.get('type') == 'json':
                    data = json.loads(content)
                    structured_data[cat_key] = data

                    # Perform matching based on category
                    if cat_key == 'symptoms':
                        matches['symptoms'] = self._match_symptoms(user_input, data)
                    elif cat_key == 'breed_info':
                        matches['breeds'] = self._match_breeds(user_input, data)
                    elif cat_key == 'medication_dosage':
                        matches['medications'] = self._match_medications(user_input, data)

                elif cat_info.get('type') == 'markdown':
                    structured_data[cat_key] = content

                    # Check if vaccination query
                    if cat_key == 'vaccination' and self._is_vaccination_query(user_input):
                        matches['vaccination'] = content

            except Exception as e:
                logger.warning(f"Failed to load structured data {cat_key}: {e}")

        return {
            'structured_data': structured_data,
            'matches': matches,
            'has_matches': any([
                matches['symptoms'],
                matches['breeds'],
                matches['medications'],
                matches['vaccination']
            ])
        }

    async def post_async(self, shared, prep_res, exec_res):
        """Store structured knowledge and matches in shared context."""
        shared['structured_knowledge'] = exec_res['structured_data']
        shared['symptom_matches'] = exec_res['matches']['symptoms']
        shared['breed_matches'] = exec_res['matches']['breeds']
        shared['medication_matches'] = exec_res['matches']['medications']
        shared['vaccination_info'] = exec_res['matches']['vaccination']
        shared['has_structured_matches'] = exec_res['has_matches']

        match_summary = []
        if exec_res['matches']['symptoms']:
            match_summary.append(f"{len(exec_res['matches']['symptoms'])} symptoms")
        if exec_res['matches']['breeds']:
            match_summary.append(f"{len(exec_res['matches']['breeds'])} breeds")
        if exec_res['matches']['medications']:
            match_summary.append(f"{len(exec_res['matches']['medications'])} medications")
        if exec_res['matches']['vaccination']:
            match_summary.append("vaccination info")

        logger.info(f"StructuredKnowledgeNode: Matches found - {', '.join(match_summary) or 'none'}")

        return 'structured_knowledge_loaded'

    def _match_symptoms(self, query: str, symptoms_data: dict) -> list:
        """Match symptoms from user query against symptom index."""
        matches = []
        query_lower = query.lower()

        symptom_index = symptoms_data.get('symptom_index', {})
        categories = symptoms_data.get('categories', {})

        # Check each symptom keyword
        for symptom, condition_ids in symptom_index.items():
            if symptom.lower() in query_lower:
                for cond_id in condition_ids:
                    # Find condition details
                    for cat_key, cat_data in categories.items():
                        for condition in cat_data.get('conditions', []):
                            if condition.get('id') == cond_id:
                                matches.append({
                                    'matched_symptom': symptom,
                                    'condition_id': cond_id,
                                    'condition_name_zh': condition.get('name_zh'),
                                    'condition_name_en': condition.get('name_en'),
                                    'urgency': condition.get('urgency'),
                                    'home_care': condition.get('home_care', []),
                                    'vet_triggers': condition.get('vet_triggers', []),
                                    'category': cat_key
                                })

        return matches

    def _match_breeds(self, query: str, breed_data: dict) -> list:
        """Match breed names from user query."""
        matches = []
        query_lower = query.lower()

        breeds = breed_data.get('categories', {}).get('common_breeds', [])

        for breed in breeds:
            # Check name_zh, name_en, and aliases
            names_to_check = [
                breed.get('name_zh', ''),
                breed.get('name_en', ''),
                *breed.get('aliases', [])
            ]

            for name in names_to_check:
                if name and name.lower() in query_lower:
                    matches.append({
                        'breed_id': breed.get('id'),
                        'name_zh': breed.get('name_zh'),
                        'name_en': breed.get('name_en'),
                        'weight_range_kg': breed.get('weight_range_kg'),
                        'health_concerns': breed.get('health_concerns', []),
                        'temperament': breed.get('temperament', []),
                        'special_notes': breed.get('special_notes')
                    })
                    break  # Found match for this breed

        return matches

    def _match_medications(self, query: str, med_data: dict) -> list:
        """Match medication names from user query."""
        matches = []
        query_lower = query.lower()

        # Check banned medications first (important safety info)
        banned = med_data.get('categories', {}).get('pain_relief', {}).get('banned_for_cats', [])
        for med in banned:
            names = [med.get('name', ''), med.get('name_en', ''), med.get('brand', '')]
            for name in names:
                if name and name.lower() in query_lower:
                    matches.append({
                        'type': 'BANNED',
                        'name': med.get('name'),
                        'name_en': med.get('name_en'),
                        'reason': med.get('reason'),
                        'toxicity': med.get('toxicity')
                    })
                    break

        # Check safe medications
        for cat_key, cat_data in med_data.get('categories', {}).items():
            medications = cat_data.get('medications', [])
            for med in medications:
                names = [med.get('name', ''), med.get('name_en', ''), med.get('brand', '')]
                for name in names:
                    if name and name.lower() in query_lower:
                        matches.append({
                            'type': 'safe',
                            'category': cat_key,
                            'name': med.get('name'),
                            'name_en': med.get('name_en'),
                            'dosage': med.get('dosage'),
                            'route': med.get('route'),
                            'frequency': med.get('frequency'),
                            'warnings': med.get('warnings', [])
                        })
                        break

        return matches

    def _is_vaccination_query(self, query: str) -> bool:
        """Check if query is about vaccination."""
        vaccination_keywords = [
            '疫苗', '接种', '打针', '免疫', 'FVRCP', '猫三联', '狂犬',
            'vaccine', 'vaccination', 'immunization', 'shot', 'rabies'
        ]
        query_lower = query.lower()
        return any(kw.lower() in query_lower for kw in vaccination_keywords)


# =============================================================================
# SKILL-based Progressive Loading System Nodes
# =============================================================================

class IntentAnalysisNode(AsyncNode):
    """
    Analyzes user intent to determine SKILL loading level and relevant domains.

    This node performs intent analysis to decide:
    1. Which SKILL domains to load (cat-health, emergency, daily-care, breed-info, iot-devices)
    2. What loading level to use (0-3 based on complexity)
    3. Token budget allocation

    Output:
    - shared['intent_analysis']: Dict with intent details
    - shared['skill_domains']: List of relevant SKILL domains
    - shared['skill_level']: Loading level 0-3
    - shared['token_budget']: Token budget for context
    """

    # Token budgets by level (INTENT_SKILL_MAP now imported from config.intent_registry)
    TOKEN_BUDGETS = {
        0: 2000,   # Quick overview
        1: 5000,   # Module specific
        2: 10000,  # Detailed
        3: 40000,  # Complete
    }

    # IoT context detection keywords
    IOT_KEYWORDS = {
        'zh': ['设备', '项圈', '猫门', '心率', '活动量', '出入', '进出', '在线', '离线', '电量', '叼'],
        'en': ['device', 'collar', 'cat door', 'heart rate', 'activity', 'entry', 'exit', 'online', 'offline', 'battery', 'prey']
    }

    async def prep_async(self, shared):
        """Prepare intent analysis data."""
        self._progress_callback = shared.get('progress_callback')
        request = shared.get('request', {}) if isinstance(shared, dict) else {}
        user_input = request.get('user_input') or shared.get('question', '')

        # Get existing router action if available
        router_action = shared.get('router_action', '')

        # Check for IoT data in shared context
        has_iot_data = bool(
            shared.get('iot_data') or
            shared.get('device_data') or
            shared.get('collar_data') or
            shared.get('cat_door_events') or
            shared.get('prey_detected')
        )

        return {
            'user_input': user_input if isinstance(user_input, str) else str(user_input or ''),
            'router_action': router_action,
            'has_iot_data': has_iot_data,
            'cat_profile': shared.get('cat_profile', {})
        }

    async def exec_async(self, prep_res):
        """Analyze intent and determine SKILL loading parameters."""
        progress_cb = getattr(self, '_progress_callback', None)

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'started',
                'message': '正在理解您的意图...'
            })

        user_input = prep_res['user_input']
        router_action = prep_res['router_action']
        has_iot_data = prep_res['has_iot_data']
        user_lower = user_input.lower()

        # Check for IoT context in user message
        has_iot_keywords = any(
            kw in user_lower
            for keywords in self.IOT_KEYWORDS.values()
            for kw in keywords
        )

        # Determine SKILL config based on router action
        if router_action and validate_action(router_action):
            skill_config = get_skill_mapping(router_action)
        else:
            # Fallback detection for unknown actions
            skill_config = self._detect_intent_fallback(user_lower)

        # Add IoT domain if IoT context detected
        domains = list(skill_config['domains'])
        if (has_iot_data or has_iot_keywords) and 'iot-devices' not in domains:
            domains.insert(0, 'iot-devices')  # IoT has priority when relevant

        # Determine final level (may be elevated for IoT correlation)
        level = skill_config['level']
        if has_iot_data and 'iot-devices' in domains and len(domains) > 1:
            # Elevate to level 2 for cross-device correlation
            level = max(level, 2)

        result = {
            'intent': router_action or 'fallback',
            'domains': domains,
            'level': level,
            'token_budget': self.TOKEN_BUDGETS.get(level, 5000),
            'priority': skill_config['priority'],
            'has_iot_context': has_iot_data or has_iot_keywords
        }

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'completed',
                'message': '意图分析完成'
            })

        return result

    async def post_async(self, shared, prep_res, exec_res):
        """Store intent analysis results in shared context."""
        shared['intent_analysis'] = exec_res
        shared['skill_domains'] = exec_res['domains']
        shared['skill_level'] = exec_res['level']
        shared['token_budget'] = exec_res['token_budget']
        shared['has_iot_context'] = exec_res['has_iot_context']

        logger.info(
            f"IntentAnalysisNode: intent={exec_res['intent']}, "
            f"domains={exec_res['domains']}, level={exec_res['level']}, "
            f"budget={exec_res['token_budget']}, iot_context={exec_res['has_iot_context']}"
        )

        return 'intent_analyzed'

    def _detect_intent_fallback(self, user_input: str) -> dict:
        """Fallback intent detection when router_action is not available."""
        # Emergency keywords
        emergency_kw = ['紧急', '急救', '中毒', 'emergency', 'poison', 'urgent', '危险']
        if any(kw in user_input for kw in emergency_kw):
            return get_skill_mapping('emergency_alert')

        # Health keywords
        health_kw = ['生病', '症状', '不舒服', 'sick', 'symptom', 'ill', '呕吐', '腹泻']
        if any(kw in user_input for kw in health_kw):
            return get_skill_mapping('medical_query')

        # Daily care keywords
        care_kw = ['喂食', '猫粮', '洗澡', 'feed', 'food', 'bath', 'groom']
        if any(kw in user_input for kw in care_kw):
            return get_skill_mapping('care_advice')

        # Greeting keywords
        greeting_kw = ['你好', 'hello', 'hi', '嗨']
        if any(kw in user_input for kw in greeting_kw):
            return get_skill_mapping('direct_reply')

        # Default fallback
        return get_skill_mapping('direct_reply')


class SkillLoaderNode(AsyncNode):
    """
    Loads SKILL content based on intent analysis.

    Implements progressive loading from .skills/ directory:
    - Level 0: ~2K tokens (quick overview)
    - Level 1: ~5K tokens (module specific)
    - Level 2: ~10K tokens (detailed)
    - Level 3: ~40K tokens (complete)

    Output:
    - shared['skill_context']: Combined SKILL content string
    - shared['skill_metadata']: Metadata about loaded SKILLs
    """

    SKILLS_DIR = Path(__file__).parent / ".skills"

    # Level to file mapping (suffix patterns)
    LEVEL_FILES = {
        0: ['level-0-'],
        1: ['level-0-', 'level-1-'],
        2: ['level-0-', 'level-1-', 'level-2-'],
        3: ['level-0-', 'level-1-', 'level-2-', 'level-3-'],
    }

    async def prep_async(self, shared):
        """Prepare SKILL loading parameters."""
        self._progress_callback = shared.get('progress_callback')
        # Get intent analysis results if available
        intent_analysis = shared.get('intent_analysis', {})

        # Use intent_analysis fields if direct fields not set
        domains = shared.get('skill_domains') or intent_analysis.get('domains', [])
        level = shared.get('skill_level') if shared.get('skill_level') is not None else intent_analysis.get('level', 1)
        token_budget = shared.get('token_budget') or intent_analysis.get('token_budget', 5000)

        return {
            'domains': domains,
            'level': level,
            'token_budget': token_budget,
            'user_input': shared.get('question', '')
        }

    async def exec_async(self, prep_res):
        """Load SKILL content based on domains and level."""
        progress_cb = getattr(self, '_progress_callback', None)

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'started',
                'message': '正在加载相关知识...'
            })

        domains = prep_res['domains']
        level = prep_res['level']
        token_budget = prep_res['token_budget']

        skills_dir = Path(self.SKILLS_DIR)
        loaded_content = []
        metadata = {
            'domains_loaded': [],
            'files_loaded': [],
            'total_chars': 0,
            'level': level
        }

        # Check if SKILL directory exists
        if not skills_dir.exists():
            error_msg = f"SKILL directory not found at absolute path: {skills_dir.absolute()}"
            logger.error(error_msg)
            result = {
                'content': '',
                'metadata': metadata,
                'error': 'skill_dir_not_found',
                'error_message': error_msg
            }
            if progress_cb:
                await progress_cb({
                    'type': 'progress',
                    'node': self.__class__.__name__,
                    'status': 'error',
                    'message': f'知识库目录未找到: {skills_dir.absolute()}'
                })
            return result

        # Determine which file prefixes to load based on level
        file_prefixes = self.LEVEL_FILES.get(level, self.LEVEL_FILES[1])

        for domain in domains:
            domain_dir = skills_dir / domain
            if not domain_dir.exists():
                logger.warning(f"SKILL domain not found: {domain}")
                continue

            domain_content = []

            # Load SKILL.md index first (always)
            skill_index = domain_dir / 'SKILL.md'
            if skill_index.exists():
                try:
                    index_content = skill_index.read_text(encoding='utf-8')
                    # Only include Description and Auto-Trigger Keywords sections
                    # to keep index lightweight
                    domain_content.append(f"## {domain.upper()} SKILL\n")
                    metadata['files_loaded'].append(str(skill_index))
                except Exception as e:
                    logger.warning(f"Failed to read SKILL index {skill_index}: {e}")

            # Load level files based on prefixes
            for file_path in sorted(domain_dir.glob('level-*.md')):
                file_name = file_path.name

                # Check if this file matches any of the level prefixes we want
                should_load = any(file_name.startswith(prefix) for prefix in file_prefixes)

                if should_load:
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        domain_content.append(content)
                        metadata['files_loaded'].append(str(file_path))
                    except Exception as e:
                        logger.warning(f"Failed to read SKILL file {file_path}: {e}")

            if domain_content:
                loaded_content.append('\n\n'.join(domain_content))
                metadata['domains_loaded'].append(domain)

        # Combine all content
        final_content = '\n\n---\n\n'.join(loaded_content)
        metadata['total_chars'] = len(final_content)

        # Estimate tokens (rough: 1 token ~ 4 chars for mixed content)
        estimated_tokens = len(final_content) // 4

        # Truncate if exceeds budget
        if estimated_tokens > token_budget:
            # Truncate to approximate token budget (budget * 4 chars)
            max_chars = token_budget * 4
            final_content = final_content[:max_chars] + "\n\n[Content truncated due to token budget]"
            metadata['truncated'] = True
            logger.info(f"SKILL content truncated from {estimated_tokens} to ~{token_budget} tokens")

        # Add warning if content is empty
        if not final_content.strip():
            logger.warning("SKILL content is empty - no matching domains or files found")
            metadata['warning'] = 'empty_content'

        result = {
            'content': final_content,
            'metadata': metadata
        }

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'completed',
                'message': '知识加载完成'
            })

        return result

    async def post_async(self, shared, prep_res, exec_res):
        """Store SKILL content in shared context."""
        shared['skill_context'] = exec_res['content']
        shared['skill_metadata'] = exec_res['metadata']

        logger.info(
            f"SkillLoaderNode: Loaded {len(exec_res['metadata']['domains_loaded'])} domains, "
            f"{len(exec_res['metadata']['files_loaded'])} files, "
            f"~{exec_res['metadata']['total_chars'] // 4} tokens"
        )

        return 'skill_loaded'


class IoTContextNode(AsyncNode):
    """
    Aggregates IoT device data - actively queries database if not in shared context.

    V3.3.9 Enhancement: Now actively loads data from database when user asks
    about their cat or devices, instead of only reading from shared context.

    Collects and formats:
    - Collar data: heart rate, activity, location, sleep
    - Cat door data: entry/exit events, prey detection, images
    - Device status: online/offline, battery levels

    Output:
    - shared['iot_context']: Formatted IoT context string
    - shared['iot_summary']: Summary dict of IoT data
    """

    async def prep_async(self, shared):
        """
        Collect IoT data - actively query database if not in shared context.

        V3.3.9: Now proactively loads device data from database when user
        asks about their cat, ensuring real-time data is always available.
        """
        self._progress_callback = shared.get('progress_callback')

        # Get cat_id from request or shared - MUST be explicitly provided
        request = shared.get('request', {}) if isinstance(shared, dict) else {}
        cat_id = request.get('cat_id') or shared.get('cat_id')

        # V3.3.9: If no cat_id, skip database load but still use data from shared context
        if not cat_id:
            logger.warning("IoTContextNode: No cat_id provided, skipping database load (using shared data if available)")
            # Fall through to collect data from shared context instead of returning empty
            # Only skip the database load, not the data collection from shared

        # Check which data types are missing - V3.3.9 incremental loading
        has_collar_data = bool(
            shared.get('collar_data') or
            shared.get('heart_rate') or
            shared.get('activity_level')
        )
        has_door_data = bool(shared.get('cat_door_events'))
        has_device_status = bool(shared.get('device_status'))

        # Determine what needs to be loaded
        needs_collar = not has_collar_data
        needs_door = not has_door_data
        needs_device = not has_device_status

        # V3.3.9: Incremental loading - only load missing data types (requires cat_id)
        if cat_id and (needs_collar or needs_door or needs_device):
            missing = []
            if needs_collar:
                missing.append('collar')
            if needs_door:
                missing.append('door')
            if needs_device:
                missing.append('device')
            logger.info(f"IoTContextNode: Loading missing data [{', '.join(missing)}] for cat {cat_id}")
            try:
                await self._load_iot_data_from_db(
                    shared, cat_id,
                    load_collar=needs_collar,
                    load_door=needs_door,
                    load_device=needs_device
                )
            except Exception as e:
                logger.warning(f"Failed to load IoT data from database: {e}")

        # Now collect all data (either from shared or freshly loaded)
        result = {
            # Collar data
            'collar_data': shared.get('collar_data', {}),
            'heart_rate': shared.get('heart_rate'),
            'activity_level': shared.get('activity_level'),
            'activity_score': shared.get('activity_score'),
            'sleep_data': shared.get('sleep_data', {}),

            # Cat door data
            'cat_door_events': shared.get('cat_door_events', []),
            'prey_detected': shared.get('prey_detected', False),
            'prey_type': shared.get('prey_type'),
            'prey_image_url': shared.get('prey_image_url'),
            'last_outdoor_time': shared.get('last_outdoor_time'),

            # Device status
            'device_status': shared.get('device_status', {}),
            'collar_battery': shared.get('collar_battery'),
            'collar_online': shared.get('collar_online'),

            # Vision analysis results (if from cat door)
            'vision_analysis': shared.get('vision_analysis', {}),

            # Cat profile for context
            'cat_profile': shared.get('cat_profile', {}),
            'cat_name': shared.get('cat_name', '猫咪')
        }

        # Add error marking fields for downstream nodes
        has_data = bool(
            result['collar_data'] or
            result['cat_door_events'] or
            result['device_status']
        )

        # Check for errors
        if shared.get('iot_load_errors'):
            result['error'] = '; '.join(shared.get('iot_load_errors', []))
            result['error_type'] = shared.get('iot_load_error_types', [])
            result['iot_load_degraded'] = True
            result['data_status'] = 'partial' if has_data else 'error'
        elif not has_data:
            # No errors but also no data - mark as empty
            result['data_status'] = 'empty'
            result['iot_load_degraded'] = False
        else:
            # Success - has data and no errors
            result['data_status'] = 'success'
            result['iot_load_degraded'] = False

        return result

    def _classify_exception(self, exc: Exception) -> str:
        """
        Classify exception type for error handling.

        Returns:
            error_type: 'timeout', 'auth', 'not_found', 'network', 'database', 'unknown'
        """
        exc_str = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        # Timeout errors
        if 'timeout' in exc_str or 'timeout' in exc_type:
            return 'timeout'

        # Authentication/Authorization errors
        if any(keyword in exc_str for keyword in ['auth', 'permission', 'unauthorized', 'forbidden']):
            return 'auth'

        # Not found errors
        if 'not found' in exc_str or '404' in exc_str or 'notfound' in exc_type:
            return 'not_found'

        # Network errors
        if any(keyword in exc_str for keyword in ['connection', 'network', 'refused', 'unreachable']):
            return 'network'

        # Database errors
        if any(keyword in exc_type for keyword in ['database', 'sql', 'query']):
            return 'database'

        return 'unknown'

    async def _load_iot_data_from_db(
        self,
        shared,
        cat_id: str,
        load_collar: bool = True,
        load_door: bool = True,
        load_device: bool = True
    ):
        """
        Load IoT data from database and populate shared context.

        V3.3.9: Supports incremental loading - only loads requested data types.

        Args:
            shared: Shared context dictionary
            cat_id: Cat ID for data lookup
            load_collar: Whether to load collar/IoT data
            load_door: Whether to load cat door events
            load_device: Whether to load device status
        """
        import asyncio

        async with SystemContext(cat_id=cat_id) as ctx:
            # Build list of tasks based on what's needed
            tasks = []
            task_names = []

            if load_collar:
                tasks.append(ctx.get_recent_iot_logs(cat_id, hours=24))
                task_names.append('iot_logs')
                tasks.append(ctx.get_bcg_metrics(cat_id, hours=24))
                task_names.append('bcg_metrics')

            if load_door:
                tasks.append(ctx.get_cat_door_passages(cat_id, hours=24))
                task_names.append('door_passages')
                tasks.append(ctx.get_outdoor_status(cat_id, hours=24))
                task_names.append('outdoor_status')

            if load_device:
                tasks.append(ctx.get_device_status(cat_id))
                task_names.append('device_status')

            if not tasks:
                return

            # Execute only required queries in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Track errors and their types
            errors = []
            error_types = []

            # Map results back to named variables
            result_map = {}
            for name, result in zip(task_names, results):
                if isinstance(result, Exception):
                    error_type = self._classify_exception(result)
                    logger.warning(f"Failed to load {name}: {result} (type: {error_type})")
                    errors.append(f"{name}:{error_type}")
                    error_types.append(error_type)
                    result_map[name] = [] if name != 'device_status' else {}
                else:
                    result_map[name] = result

            # Store error information in shared for downstream nodes
            if errors:
                shared['iot_load_errors'] = errors
                shared['iot_load_error_types'] = error_types
                shared['iot_load_degraded'] = True
                logger.warning(f"IoT data loading degraded: {', '.join(errors)}")

            # Parse and store collar data
            if load_collar:
                iot_logs = result_map.get('iot_logs', [])
                bcg_metrics = result_map.get('bcg_metrics', [])
                device_status_for_collar = result_map.get('device_status', {}) if load_device else {}
                collar_data = self._parse_collar_data(iot_logs, bcg_metrics, device_status_for_collar)
                if collar_data:
                    shared['collar_data'] = collar_data
                    # Also set top-level fields for backward compatibility
                    if collar_data.get('heart_rate'):
                        shared['heart_rate'] = collar_data['heart_rate']
                    if collar_data.get('activity_level'):
                        shared['activity_level'] = collar_data['activity_level']
                    if collar_data.get('activity_score'):
                        shared['activity_score'] = collar_data['activity_score']
                    if collar_data.get('battery'):
                        shared['collar_battery'] = collar_data['battery']
                    if 'online' in collar_data:
                        shared['collar_online'] = collar_data['online']

            # Parse and store cat door events
            if load_door:
                door_passages = result_map.get('door_passages', [])
                cat_door_events = self._parse_door_passages(door_passages)
                if cat_door_events:
                    shared['cat_door_events'] = cat_door_events
                    # Check for prey detection
                    for event in cat_door_events:
                        if event.get('prey_detected'):
                            shared['prey_detected'] = True
                            shared['prey_type'] = event.get('prey_type')
                            break

                # Parse outdoor status for last outdoor time
                outdoor_status = result_map.get('outdoor_status', [])
                if outdoor_status:
                    last_outdoor = self._get_last_outdoor_time(outdoor_status)
                    if last_outdoor:
                        shared['last_outdoor_time'] = last_outdoor

            # Store device status
            if load_device:
                device_status = result_map.get('device_status', {})
                if device_status:
                    shared['device_status'] = device_status

            # Log what was loaded
            loaded_items = []
            if load_collar:
                loaded_items.append(f"iot={len(result_map.get('iot_logs', []))}")
                loaded_items.append(f"bcg={len(result_map.get('bcg_metrics', []))}")
            if load_door:
                loaded_items.append(f"passages={len(result_map.get('door_passages', []))}")
            if load_device:
                loaded_items.append(f"device={bool(result_map.get('device_status'))}")
            logger.info(f"IoTContextNode: Loaded from DB - {', '.join(loaded_items)}")

    def _parse_collar_data(self, iot_logs: list, bcg_metrics: list, device_status: dict) -> dict:
        """Parse IoT logs and BCG metrics into collar_data format."""
        collar_data = {}

        # Get latest activity from IoT logs
        if iot_logs:
            # Aggregate activity data
            activity_values = []
            for log in iot_logs:
                activity_type = log.get('activity_type', '')
                value = log.get('value', 0)
                if activity_type in ['walking', 'running', 'playing', 'active']:
                    activity_values.append(value)
                elif activity_type == 'activity_score':
                    collar_data['activity_score'] = value

            if activity_values:
                avg_activity = sum(activity_values) / len(activity_values)
                if avg_activity < 30:
                    collar_data['activity_level'] = 'low'
                elif avg_activity > 70:
                    collar_data['activity_level'] = 'high'
                else:
                    collar_data['activity_level'] = 'moderate'
                collar_data['activity_score'] = int(avg_activity)

        # Get latest heart rate from BCG metrics
        if bcg_metrics:
            # Get most recent BCG reading
            latest_bcg = bcg_metrics[0] if bcg_metrics else {}
            if latest_bcg.get('heart_rate_bpm'):
                collar_data['heart_rate'] = latest_bcg['heart_rate_bpm']
            elif latest_bcg.get('heart_rate'):
                collar_data['heart_rate'] = latest_bcg['heart_rate']

            # Calculate average heart rate if multiple readings
            hr_values = [m.get('heart_rate_bpm') or m.get('heart_rate', 0) for m in bcg_metrics if m.get('heart_rate_bpm') or m.get('heart_rate')]
            if hr_values:
                collar_data['avg_heart_rate'] = int(sum(hr_values) / len(hr_values))

        # Get device status
        if device_status:
            collar_data['battery'] = device_status.get('battery_level', device_status.get('battery'))
            collar_data['online'] = device_status.get('online', True)
            collar_data['last_seen'] = device_status.get('last_heartbeat', device_status.get('last_seen'))

            # Check location from device status
            if device_status.get('location'):
                collar_data['location'] = device_status['location']

        return collar_data

    def _parse_door_passages(self, passages: list) -> list:
        """Parse cat door passages into event format."""
        events = []
        for passage in passages[:10]:  # Limit to 10 most recent
            event = {
                'type': passage.get('direction', passage.get('type', 'unknown')),
                'timestamp': passage.get('timestamp', passage.get('time', '')),
                'prey_detected': passage.get('prey_detected', False),
                'prey_type': passage.get('prey_type'),
                'image_url': passage.get('image_url', passage.get('snapshot_url'))
            }

            # Normalize direction to type
            direction = event['type'].lower() if event['type'] else ''
            if direction in ['in', 'inbound', 'entering']:
                event['type'] = 'entry'
            elif direction in ['out', 'outbound', 'leaving']:
                event['type'] = 'exit'

            events.append(event)

        return events

    def _get_last_outdoor_time(self, outdoor_status: list) -> str:
        """Get the most recent outdoor time from outdoor status logs."""
        for status in outdoor_status:
            if status.get('location') == 'outdoor' or status.get('is_outdoor'):
                return status.get('timestamp', status.get('time', ''))
        return ''

    async def exec_async(self, prep_res):
        """Format IoT data into context string."""
        progress_cb = getattr(self, '_progress_callback', None)

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'started',
                'message': '正在获取设备数据...'
            })

        context_parts = []
        summary = {
            'has_collar_data': False,
            'has_door_data': False,
            'has_prey_detection': False,
            'devices_online': [],
            'alerts': []
        }

        cat_name = prep_res['cat_name']

        # Process collar data - extract from collar_data dict or top-level fields
        collar_data = prep_res['collar_data'] or {}

        # Get values from collar_data dict first, fallback to top-level fields
        heart_rate = collar_data.get('heart_rate') or prep_res.get('heart_rate')
        activity_level = collar_data.get('activity_level') or prep_res.get('activity_level')
        activity_score = collar_data.get('activity_score') or prep_res.get('activity_score')
        collar_battery = collar_data.get('battery') or prep_res.get('collar_battery')
        collar_location = collar_data.get('location')
        collar_online = collar_data.get('online') if 'online' in collar_data else prep_res.get('collar_online')

        if collar_data or heart_rate or activity_level:
            summary['has_collar_data'] = True
            summary['devices_online'].append('collar')

            collar_context = f"## {cat_name} 项圈数据 (IoT Smart Collar)\n"

            if heart_rate:
                hr = heart_rate
                collar_context += f"- 心率 (Heart Rate): {hr} bpm"
                # Add interpretation
                if hr > 240:
                    collar_context += " (偏高，需关注)"
                    summary['alerts'].append('heart_rate_high')
                elif hr < 120:
                    collar_context += " (偏低，需关注)"
                    summary['alerts'].append('heart_rate_low')
                else:
                    collar_context += " (正常范围 140-220)"
                collar_context += "\n"

            if activity_level or activity_score:
                activity = activity_score or activity_level
                collar_context += f"- 活动量 (Activity): {activity}"
                if isinstance(activity, (int, float)):
                    if activity < 30:
                        collar_context += " (较低)"
                    elif activity > 80:
                        collar_context += " (活跃)"
                    else:
                        collar_context += " (正常)"
                elif isinstance(activity, str):
                    level_map = {'low': '较低', 'moderate': '中等', 'high': '活跃', 'sleeping': '睡眠中'}
                    collar_context += f" ({level_map.get(activity.lower(), activity)})"
                collar_context += "\n"

            if collar_location:
                location_map = {'indoor': '室内 (indoor)', 'outdoor': '室外 (outdoor)', 'unknown': '未知'}
                loc_display = location_map.get(collar_location.lower(), collar_location) if isinstance(collar_location, str) else collar_location
                collar_context += f"- 位置 (Location): {loc_display}\n"

            if collar_battery:
                battery = collar_battery
                collar_context += f"- 电量 (Battery): {battery}%"
                if battery < 20:
                    collar_context += " (需充电)"
                    summary['alerts'].append('low_battery')
                collar_context += "\n"

            if collar_online is not None:
                status = "在线" if collar_online else "离线"
                collar_context += f"- 连接状态: {status}\n"

            context_parts.append(collar_context)

        # Process cat door data
        door_events = prep_res['cat_door_events']
        prey_detected = prep_res['prey_detected']

        # Also check for prey in door events
        if door_events:
            for event in door_events:
                if event.get('prey_detected'):
                    prey_detected = True
                    break

        if door_events or prey_detected:
            summary['has_door_data'] = True
            summary['devices_online'].append('cat_door')

            door_context = f"## {cat_name} 猫门数据 (IoT Smart Cat Door)\n"

            if door_events:
                recent_events = door_events[:5] if isinstance(door_events, list) else []
                event_type_map = {'entry': '进入', 'exit': '外出', 'blocked': '被阻止'}
                for event in recent_events:
                    event_type = event.get('type', 'unknown')
                    event_type_zh = event_type_map.get(event_type, event_type)
                    # Support both 'timestamp' and 'time' fields
                    timestamp = event.get('timestamp') or event.get('time', '')
                    door_context += f"- {event_type_zh} ({event_type}): {timestamp}"

                    # Check for prey in this event
                    if event.get('prey_detected'):
                        prey_type = event.get('prey_type', '未知物品')
                        door_context += f" - 叼物检测 (prey: {prey_type})"
                        summary['has_prey_detection'] = True
                    door_context += "\n"

            if prey_detected:
                summary['has_prey_detection'] = True
                summary['alerts'].append('prey_detected')
                door_context += "- **叼物检测 (Prey Detected)**: 检测到猫咪叼着物品进入\n"
                if prep_res.get('prey_type'):
                    door_context += f"- 物品类型 (Prey Type): {prep_res['prey_type']}\n"
                if prep_res['prey_image_url']:
                    door_context += f"- 图片: {prep_res['prey_image_url']}\n"

            if prep_res['last_outdoor_time']:
                door_context += f"- 最近外出时间: {prep_res['last_outdoor_time']}\n"

            context_parts.append(door_context)

        # Process vision analysis from cat door
        vision = prep_res['vision_analysis']
        if vision and isinstance(vision, dict):
            if vision.get('prey_detected') or vision.get('object_in_mouth'):
                summary['has_prey_detection'] = True
                vision_context = "## 图像分析结果\n"
                if vision.get('prey_type'):
                    vision_context += f"- 检测到物品类型: {vision['prey_type']}\n"
                if vision.get('confidence'):
                    vision_context += f"- 置信度: {vision['confidence']}\n"
                if vision.get('recommendation'):
                    vision_context += f"- 建议: {vision['recommendation']}\n"
                context_parts.append(vision_context)

        # Combine all context
        final_context = '\n'.join(context_parts) if context_parts else ''

        result = {
            'context': final_context,
            'summary': summary
        }

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'completed',
                'message': '设备数据获取完成'
            })

        return result

    async def post_async(self, shared, prep_res, exec_res):
        """Store IoT context in shared."""
        shared['iot_context'] = exec_res['context']
        shared['iot_summary'] = exec_res['summary']

        logger.info(
            f"IoTContextNode: collar={exec_res['summary']['has_collar_data']}, "
            f"door={exec_res['summary']['has_door_data']}, "
            f"prey={exec_res['summary']['has_prey_detection']}, "
            f"alerts={exec_res['summary']['alerts']}"
        )

        return 'iot_context_ready'


class ContextFusionNode(AsyncNode):
    """
    Fuses SKILL, RAG, and IoT context with priority-based allocation.

    Priority: IoT realtime data > SKILL precise match > RAG semantic supplement
    Token allocation: IoT 30% | SKILL 50% | RAG 20%

    Output:
    - shared['fused_context']: Combined context string ready for LLM
    - shared['context_sources']: List of sources included
    """

    # Default token allocation percentages
    ALLOCATION = {
        'iot': 0.30,      # 30% for IoT data (highest priority)
        'skill': 0.50,    # 50% for SKILL knowledge
        'rag': 0.20       # 20% for RAG supplement
    }

    def _truncate_with_awareness(self, text: str, max_chars: int) -> str:
        """
        智能截断文本，避免在句子中间断裂

        策略：
        1. 如果文本长度 < max_chars，返回原文
        2. 否则，在 max_chars 前找到最后一个完整段落结尾 (\n\n)
        3. 如果找不到段落边界，找到最后一个句子结尾 (。！？\n)
        4. 如果都找不到，才在 word 边界截断
        """
        if len(text) <= max_chars:
            return text

        # 在 max_chars 位置前查找边界
        search_text = text[:max_chars]

        # 优先级 1：段落边界（最好）- 保留至少70%
        last_para = search_text.rfind('\n\n')
        if last_para > max_chars * 0.7:
            return text[:last_para] + "\n\n[内容已截断，详见完整知识库]"

        # 优先级 2：句子边界（较好）- 保留至少80%
        for ending in ['。\n', '。', '！\n', '！', '？\n', '？', '\n']:
            last_sent = search_text.rfind(ending)
            if last_sent > max_chars * 0.8:
                return text[:last_sent + len(ending)] + "\n[内容已截断]"

        # 优先级 3：单词边界（最后手段）- 保留至少90%
        last_space = search_text.rfind(' ')
        if last_space > max_chars * 0.9:
            return text[:last_space] + "\n[内容已截断]"

        # 最后才硬截断
        return text[:max_chars] + "\n[内容已截断]"

    async def prep_async(self, shared):
        """Collect all context sources."""
        self._progress_callback = shared.get('progress_callback')
        return {
            'skill_context': shared.get('skill_context', ''),
            'rag_context': shared.get('rag_context', ''),
            'iot_context': shared.get('iot_context', ''),
            'iot_summary': shared.get('iot_summary', {}),
            'token_budget': shared.get('token_budget', 5000),
            'has_iot_context': shared.get('has_iot_context', False),

            # Additional context that may exist
            'core_rules_context': shared.get('core_rules', {}).get('system_rules', ''),
            'structured_matches': shared.get('symptom_matches', []),
        }

    async def exec_async(self, prep_res):
        """Fuse contexts with priority allocation."""
        progress_cb = getattr(self, '_progress_callback', None)

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'started',
                'message': '正在整合上下文...'
            })

        total_budget = prep_res['token_budget']
        # Check for IoT context - either explicit flag or non-empty content
        has_iot = prep_res['has_iot_context'] or bool(prep_res['iot_context'].strip())

        # Adjust allocation if no IoT context
        if has_iot:
            allocations = self.ALLOCATION.copy()
        else:
            # Redistribute IoT allocation to SKILL and RAG
            allocations = {
                'iot': 0,
                'skill': 0.65,
                'rag': 0.35
            }

        # Calculate character budgets (rough: 4 chars per token)
        char_budget = {
            source: int(total_budget * alloc * 4)
            for source, alloc in allocations.items()
        }

        fused_parts = []
        sources = []

        # 1. IoT Context (highest priority - no truncation if within budget)
        if has_iot:
            iot_ctx = prep_res['iot_context']
            if len(iot_ctx) <= char_budget['iot']:
                fused_parts.append(f"# 设备实时数据\n{iot_ctx}")
            else:
                truncated = self._truncate_with_awareness(iot_ctx, char_budget['iot'])
                fused_parts.append(f"# 设备实时数据\n{truncated}")
            sources.append('iot')

            # Add any IoT alerts prominently
            iot_summary = prep_res['iot_summary']
            if iot_summary.get('alerts'):
                alert_text = ", ".join(iot_summary['alerts'])
                fused_parts.insert(0, f"**IoT 警报**: {alert_text}\n")

        # 2. SKILL Context (primary knowledge)
        skill_ctx = prep_res['skill_context']
        if skill_ctx:
            if len(skill_ctx) <= char_budget['skill']:
                fused_parts.append(f"# 知识库参考\n{skill_ctx}")
            else:
                truncated = self._truncate_with_awareness(skill_ctx, char_budget['skill'])
                fused_parts.append(f"# 知识库参考\n{truncated}")
            sources.append('skill')

        # 3. RAG Context (semantic supplement)
        rag_ctx = prep_res['rag_context']
        if rag_ctx:
            if len(rag_ctx) <= char_budget['rag']:
                fused_parts.append(f"# 补充参考资料\n{rag_ctx}")
            else:
                truncated = self._truncate_with_awareness(rag_ctx, char_budget['rag'])
                fused_parts.append(f"# 补充参考资料\n{truncated}")
            sources.append('rag')

        # 4. Add structured matches if relevant and space permits
        structured = prep_res['structured_matches']
        if structured and len(fused_parts) > 0:
            # Add compact structured match summary
            match_summary = []
            for match in structured[:3]:  # Limit to top 3
                match_summary.append(
                    f"- {match.get('condition_name_zh', match.get('condition_id'))}: "
                    f"{match.get('urgency', 'unknown')} urgency"
                )
            if match_summary:
                fused_parts.append(
                    "# 症状匹配\n" + "\n".join(match_summary)
                )
                sources.append('structured')

        # Combine all parts
        final_context = "\n\n---\n\n".join(fused_parts) if fused_parts else ""

        result = {
            'fused_context': final_context,
            'sources': sources,
            'total_chars': len(final_context),
            'estimated_tokens': len(final_context) // 4
        }

        if progress_cb:
            await progress_cb({
                'type': 'progress',
                'node': self.__class__.__name__,
                'status': 'completed',
                'message': '上下文整合完成'
            })

        return result

    async def post_async(self, shared, prep_res, exec_res):
        """Store fused context in shared."""
        shared['fused_context'] = exec_res['fused_context']
        shared['context_sources'] = exec_res['sources']

        logger.info(
            f"ContextFusionNode: sources={exec_res['sources']}, "
            f"~{exec_res['estimated_tokens']} tokens"
        )

        return 'context_fused'
