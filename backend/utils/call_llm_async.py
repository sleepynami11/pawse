# -*- coding: utf-8 -*-
"""
V3.3.9 LLM Async Client
=======================
Simplified to 2 LLM functions:
1. gpt-5-nano: End user responses + intent understanding (with Prompt Caching)
2. OpenRouter qwen/qwen3-vl-30b-a3b-thinking: Internal analysis + vision understanding

V3.3.9 Changes:
- All internal analysis prompts now use English with Chain-of-Thought (CoT)
- Aligned with English RAG knowledge base for consistent reasoning

V3.3.8 Changes:
- Replaced Novita AI with OpenRouter API
- Using OpenAI SDK compatible mode for OpenRouter calls
- Support for qwen/qwen3-vl-30b-a3b-thinking and other vision models

V3.3.7 Prompt Caching:
- Leverages OpenAI automatic Prompt Caching
- System Prompt (static): Brand info + rules + format requirements (1024+ tokens)
- User Message (dynamic): User questions + data context
- Same prefix requests automatically get 50% cost discount
- Reference: https://platform.openai.com/docs/guides/prompt-caching

All internal analysis prompts use English with CoT reasoning.
"""
from collections.abc import AsyncGenerator
from openai import AsyncOpenAI
import os
import logging
import base64

logger = logging.getLogger(__name__)

# OpenRouter API 配置
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "qwen/qwen3-vl-30b-a3b-thinking"


# =============================================================================
# Language Detection
# =============================================================================

def detect_language(text: str) -> str:
    """
    Enhanced language detection based on character and word analysis.

    Args:
        text: Input text to analyze

    Returns:
        Language code: 'zh' for Chinese, 'en' for English, 'auto' for mixed/unknown
    """
    if not text or not text.strip():
        return "auto"

    # Remove common punctuation for better analysis
    import re
    clean_text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)

    if not clean_text.strip():
        return "auto"

    # Count Chinese characters
    chinese_count = sum(1 for char in clean_text if '\u4e00' <= char <= '\u9fff')

    # Count English words (sequences of ASCII letters)
    english_words = re.findall(r'[a-zA-Z]+', clean_text)
    english_char_count = sum(len(word) for word in english_words)

    total_meaningful = chinese_count + english_char_count

    if total_meaningful == 0:
        return "auto"

    chinese_ratio = chinese_count / total_meaningful

    # More aggressive detection thresholds
    if chinese_ratio >= 0.2:  # Lowered from 0.3 - if any significant Chinese, use Chinese
        return "zh"
    elif chinese_ratio == 0 and english_char_count > 0:  # Pure English
        return "en"
    elif chinese_ratio < 0.05:  # Almost no Chinese characters
        return "en"
    else:
        return "auto"


def get_language_instruction(detected_language: str = "auto", original_text: str = "") -> str:
    """
    Get language instruction for LLM responses.

    V3.3.10: Simplified - always use unified instruction to match user's language.
    The LLM will automatically detect and respond in the same language as the user.
    Supports all major world languages.

    Args:
        detected_language: Deprecated, kept for backward compatibility (ignored)
        original_text: Deprecated, kept for backward compatibility (ignored)

    Returns:
        Unified language instruction string for multilingual support
    """
    # V3.3.10: Universal multilingual instruction - supports all major languages
    return """LANGUAGE RULE: Always respond in the EXACT SAME language as the user's question.

Supported languages (respond in user's language):
- 中文 (Chinese) → 用中文回复
- English → Reply in English
- Deutsch (German) → Auf Deutsch antworten
- Français (French) → Répondre en français
- Italiano (Italian) → Rispondere in italiano
- Español (Spanish) → Responder en español
- 日本語 (Japanese) → 日本語で回答
- 한국어 (Korean) → 한국어로 답변
- Português (Portuguese) → Responder em português
- Русский (Russian) → Отвечать на русском
- العربية (Arabic) → الرد بالعربية
- And any other language the user writes in

Match the user's language naturally and consistently throughout your response."""


def _build_system_prompt_and_messages(prompt: str, system_prompt: str | None, detected_language: str = "auto") -> tuple[str, list[dict], bool, int]:
    """
    Build system prompt with language instruction and return chat messages plus cache hints.

    V3.3.10: Simplified - uses unified language instruction regardless of detected_language.
    LLM automatically matches user's language based on the instruction.
    """
    language_instruction = get_language_instruction()  # V3.3.10: No params needed

    if system_prompt is None:
        # V3.3.10: Use bilingual default prompt
        system_prompt = f"You are a professional and friendly cat health assistant. 你是专业友好的猫咪健康助手。\n\n{language_instruction}"
    else:
        # Append language instruction to existing system prompt
        system_prompt = f"{system_prompt}\n\n{language_instruction}"

    system_tokens_estimate = len(system_prompt) // 4  # Rough estimate
    cache_eligible = system_tokens_estimate >= 1024

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    return system_prompt, messages, cache_eligible, system_tokens_estimate


# =============================================================================
# LLM 1: OpenAI gpt-5-nano (用户回复 + 意图理解)
# =============================================================================
# V3.3.7 Prompt Caching Strategy:
# - system_prompt: 静态内容 (品牌 + 规则 + 格式) - 自动缓存
# - prompt (user_message): 动态内容 (用户问题 + 数据) - 不缓存
# - OpenAI 自动缓存相同前缀的 system_prompt，降低 50% 成本
# =============================================================================

async def async_call_llm(
    prompt: str,
    system_prompt: str = None,
    detected_language: str = "auto",
    model: str = "gpt-5-nano",
    stream: bool = False
) -> str | AsyncGenerator[str, None]:
    """
    Async wrapper for OpenAI LLM calls with Prompt Caching support.
    用于: 最终用户回复、意图理解

    V3.3.10 Simplified Language Handling:
    - LLM automatically responds in the same language as user's input
    - No need to detect language beforehand - unified instruction handles it
    - detected_language parameter kept for backward compatibility (ignored)

    V3.3.7 Prompt Caching:
    - 传入长的静态 system_prompt (1024+ tokens) 可自动触发缓存
    - prompt 作为 user message，包含动态数据
    - 相同 system_prompt 前缀的请求自动获得 50% 成本折扣

    Args:
        prompt: The user message (dynamic content: user question + data)
        system_prompt: Static system prompt for caching (brand + rules + format)
                       If None, uses bilingual default (not cached)
        detected_language: Deprecated in V3.3.10 - kept for backward compatibility
        model: The model to use (default: gpt-5-nano)
        stream: Whether to stream tokens. If True, returns an AsyncGenerator

    Returns:
        The LLM response text, or an AsyncGenerator when stream=True

    Example:
        # Simple call - LLM auto-matches user's language
        response = await async_call_llm("你好，我的猫咪怎么样？")  # Returns Chinese
        response = await async_call_llm("How is my cat?")  # Returns English
    """
    if stream:
        return await async_call_llm_stream(
            prompt=prompt,
            system_prompt=system_prompt,
            detected_language=detected_language,
            model=model
        )

    try:
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", "your-api-key"))

        # Build system prompt based on language if not provided
        # Note: Short system prompts won't trigger caching (need 1024+ tokens)
        # V3.3.9: Enhanced language instructions for better multilingual response
        system_prompt, messages, cache_eligible, system_tokens_estimate = _build_system_prompt_and_messages(
            prompt, system_prompt, detected_language
        )
        # V3.3.7: Log caching eligibility (1024+ tokens needed)
        logger.info(f"Calling OpenAI LLM: model={model}, lang={detected_language}, cache_eligible={cache_eligible} (~{system_tokens_estimate} tokens)")

        response = await client.chat.completions.create(
            model=model,
            messages=messages
        )

        result = response.choices[0].message.content

        # V3.3.7: Log cache status if available in response
        usage = response.usage
        if usage and hasattr(usage, 'prompt_tokens_details'):
            cached = getattr(usage.prompt_tokens_details, 'cached_tokens', 0)
            logger.info(f"Response received: length={len(result)}, cached_tokens={cached}")
        else:
            logger.info(f"Received response from OpenAI LLM (length: {len(result)})")

        return result

    except Exception as e:
        logger.error(f"Error in async_call_llm: {str(e)}")
        raise


async def async_call_llm_stream(
    prompt: str,
    system_prompt: str = None,
    detected_language: str = "auto",
    model: str = "gpt-5-nano"
) -> AsyncGenerator[str, None]:
    """
    Streaming wrapper for OpenAI LLM calls.
    Returns an AsyncGenerator that yields tokens as they arrive.

    Args:
        prompt: The user message (dynamic content: user question + data)
        system_prompt: Static system prompt for caching (brand + rules + format)
        detected_language: User's detected language for response (zh/en/auto)
        model: The model to use (default: gpt-5-nano)

    Returns:
        AsyncGenerator yielding response tokens
    """
    try:
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", "your-api-key"))

        system_prompt, messages, cache_eligible, system_tokens_estimate = _build_system_prompt_and_messages(
            prompt, system_prompt, detected_language
        )
        logger.info(f"Streaming OpenAI LLM: model={model}, lang={detected_language}, cache_eligible={cache_eligible} (~{system_tokens_estimate} tokens)")

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True
        )

        async def token_generator() -> AsyncGenerator[str, None]:
            async for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if not content:
                    continue
                # OpenAI SDK returns string content for text delta
                if isinstance(content, list):
                    for part in content:
                        text = getattr(part, "text", None) or (part.get("text") if isinstance(part, dict) else None)
                        if text:
                            yield text
                else:
                    yield content

        return token_generator()

    except Exception as e:
        logger.error(f"Error in async_call_llm_stream: {str(e)}")
        raise


# =============================================================================
# LLM 2: OpenRouter qwen3-vl-30b (Internal Analysis + Vision Understanding)
# V3.3.9: English prompts with Chain-of-Thought reasoning
# =============================================================================

async def async_call_openrouter_llm(
    prompt: str,
    system_prompt: str = "You are a professional cat health analysis expert. Analyze systematically using Chain-of-Thought reasoning. Think step by step.",
    model: str = None,
    max_tokens: int = 32768,
    temperature: float = 0.7,
    image_data: str | bytes = None
) -> str:
    """
    Async wrapper for OpenRouter LLM calls using OpenAI SDK.
    Used for: Internal analysis research, vision understanding

    V3.3.9: Uses English prompts with Chain-of-Thought (CoT) reasoning
    - Aligned with English RAG knowledge base
    - Step-by-step analytical reasoning

    V3.3.8: Using OpenRouter API (OpenAI SDK compatible mode)
    - Supports qwen/qwen3-vl-30b-a3b-thinking and other vision models
    - Fully compatible with OpenAI SDK

    Args:
        prompt: The text prompt to send to the LLM (English with CoT recommended)
        system_prompt: System prompt to set context (default: English CoT expert)
        model: The model to use (default: qwen/qwen3-vl-30b-a3b-thinking)
        max_tokens: Maximum tokens in response (default: 32768)
        temperature: Temperature for generation (default: 0.7)
        image_data: Optional image data (URL string or bytes) for vision tasks

    Returns:
        The LLM response text
    """
    if model is None:
        model = OPENROUTER_DEFAULT_MODEL

    try:
        # 使用 OpenAI SDK 调用 OpenRouter API
        # 支持大小写两种环境变量名 (OPENROUTER_API_KEY 或 openrouter_api_key)
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("openrouter_api_key")
        if not api_key:
            raise ValueError("OpenRouter API key not found. Set OPENROUTER_API_KEY or openrouter_api_key in .env")

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": os.environ.get("OPENROUTER_REFERER", "https://catiot.app"),
                "X-Title": os.environ.get("OPENROUTER_TITLE", "Cat IoT Health Monitor")
            }
        )

        logger.info(f"Calling OpenRouter with model: {model}")

        # Build messages
        if image_data:
            # Vision mode - multimodal message
            content = [{"type": "text", "text": prompt}]

            # Prepare image content based on input type
            if isinstance(image_data, str) and (image_data.startswith('http://') or image_data.startswith('https://')):
                # Image URL
                content.append({
                    "type": "image_url",
                    "image_url": {"url": image_data}
                })
            elif isinstance(image_data, bytes):
                # Base64-encoded image
                base64_image = base64.b64encode(image_data).decode('utf-8')
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                })
            elif isinstance(image_data, str) and image_data.startswith('data:'):
                # Already base64-encoded with data URI
                content.append({
                    "type": "image_url",
                    "image_url": {"url": image_data}
                })
            else:
                raise ValueError("image_data must be a URL string or bytes")

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ]
        else:
            # Text-only mode
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        result = response.choices[0].message.content
        logger.info(f"Received response from OpenRouter (length: {len(result)})")

        return result

    except Exception as e:
        logger.error(f"Error in async_call_openrouter_llm: {str(e)}")
        raise


# Backward compatibility alias: async_call_novita_llm -> async_call_openrouter_llm
async def async_call_novita_llm(
    prompt: str,
    system_prompt: str = "You are a professional cat health analysis expert. Analyze systematically using Chain-of-Thought reasoning. Think step by step.",
    model: str = None,
    max_tokens: int = 32768,
    temperature: float = 0.7,
    image_data: str | bytes = None
) -> str:
    """
    Backward compatibility alias for async_call_openrouter_llm.
    V3.3.8: Now uses OpenRouter API instead of Novita AI.
    V3.3.9: Uses English prompts with CoT reasoning.
    """
    return await async_call_openrouter_llm(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        image_data=image_data
    )


# =============================================================================
# 兼容性别名 (Backward Compatibility)
# =============================================================================

async def async_call_multilingual_llm(
    prompt: str,
    detected_language: str = "auto",
    model: str = "gpt-5-nano"
) -> str:
    """
    Backward compatibility alias for async_call_llm.
    保持与 V3.3.3 的兼容性。
    """
    return await async_call_llm(prompt, detected_language=detected_language, model=model)


async def async_call_vision_llm(
    prompt: str,
    image_data: str | bytes,
    model: str = None
) -> dict:
    """
    Async wrapper for vision LLM calls.
    V3.3.9: Uses English prompts with Chain-of-Thought reasoning for vision analysis.
    V3.3.8: Using OpenRouter API (qwen/qwen3-vl-30b-a3b-thinking) for vision analysis.

    Args:
        prompt: The text prompt to send to the LLM
        image_data: Either a URL string or base64-encoded image bytes
        model: The model to use (default: qwen/qwen3-vl-30b-a3b-thinking)

    Returns:
        Dictionary with:
            - text: The LLM response text
            - confidence: Confidence score (default 1.0)
            - raw_response: Raw response metadata
    """
    if model is None:
        model = OPENROUTER_DEFAULT_MODEL

    try:
        # Use OpenRouter API for vision analysis with English CoT
        text_response = await async_call_openrouter_llm(
            prompt=prompt,
            system_prompt="You are a cat vision analysis expert. Analyze the image content step by step using Chain-of-Thought reasoning. Evaluate the cat's health status, behavior, body condition, and emotional state systematically.",
            model=model,
            image_data=image_data
        )

        # Construct structured response for backward compatibility
        result = {
            "text": text_response,
            "confidence": 1.0,
            "raw_response": {
                "model": model,
                "provider": "openrouter"
            }
        }

        return result

    except Exception as e:
        logger.error(f"Error in async_call_vision_llm: {str(e)}")
        raise


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def test_llms():
        # Test 1: User response (gpt-5-nano)
        print("=" * 50)
        print("Test 1: User Response LLM (gpt-5-nano)")
        print("=" * 50)

        prompt_zh = "我的猫今天不太精神，是怎么回事？"
        response_zh = await async_call_llm(prompt_zh, detected_language="zh")
        print(f"Chinese response: {response_zh[:200]}...")

        prompt_en = "My cat seems tired today, what's wrong?"
        response_en = await async_call_llm(prompt_en, detected_language="en")
        print(f"English response: {response_en[:200]}...")

        # Test 2: Internal analysis (OpenRouter) - V3.3.9 English CoT
        print("\n" + "=" * 50)
        print("Test 2: Internal Analysis LLM (OpenRouter) - English CoT")
        print("=" * 50)

        analysis_prompt = """
Let's analyze the following cat health data step by step:

Health Metrics:
- Heart rate: 180 bpm (normal range: 140-220)
- Respiratory rate: 28/min (normal range: 20-30)
- Activity level: Moderate

Please evaluate the health status and provide recommendations using Chain-of-Thought reasoning.
"""
        analysis = await async_call_openrouter_llm(analysis_prompt)
        print(f"Analysis: {analysis[:300]}...")

        # Test 3: Vision analysis (OpenRouter) - V3.3.9 English CoT
        print("\n" + "=" * 50)
        print("Test 3: Vision Analysis LLM (OpenRouter) - English CoT")
        print("=" * 50)

        image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/1200px-Cat03.jpg"
        vision_prompt = "Analyze this cat image step by step. Evaluate the cat's health status, body condition, and emotional state."
        vision_result = await async_call_vision_llm(vision_prompt, image_url)
        print(f"Vision result: {vision_result['text'][:300]}...")

    asyncio.run(test_llms())
