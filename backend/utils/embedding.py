import os
import logging
from typing import Iterable

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


async def translate_to_english(text: str) -> str:
    """
    Translate non-English text to English for RAG retrieval.

    This ensures consistent embedding space matching since the knowledge base
    is stored in English.

    Args:
        text: Input text in any language

    Returns:
        English translation of the text, or original text if already English
    """
    if not text or not text.strip():
        return text

    # Always attempt translation - let the LLM detect if already English
    # This handles European languages (German, French, Italian, Spanish, etc.)
    # which use mostly ASCII but are not English
    try:
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", "your-api-key"))

        logger.info(f"Translating query to English: {text[:100]}...")

        response = await client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {
                    "role": "system",
                    "content": "You are a translator. Translate the user's text to English. "
                               "Only output the translation, nothing else. "
                               "Keep technical terms and cat-related terminology accurate. "
                               "If the text is already in English, return it unchanged."
                },
                {"role": "user", "content": text}
            ],
            max_completion_tokens=500
        )

        translated = response.choices[0].message.content.strip()
        logger.info(f"Translation complete: {translated[:100]}...")
        return translated

    except Exception as e:
        logger.error(f"Translation failed, using original text: {str(e)}")
        return text


async def generate_embedding(text: str, model: str = DEFAULT_EMBEDDING_MODEL) -> list[float]:
    """
    Generate embedding vector for given text using OpenAI embedding API.

    Args:
        text: Input text to embed
        model: Embedding model name (default: text-embedding-3-small)

    Returns:
        List of floats representing the embedding vector
    """
    if not text or not text.strip():
        raise ValueError("Text for embedding must be non-empty")

    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", "your-api-key"))

    logger.info(f"Generating embedding with model: {model}")
    response = await client.embeddings.create(
        model=model,
        input=text.strip()
    )

    embedding = response.data[0].embedding
    logger.info(f"Embedding generated (dimensions: {len(embedding)})")
    return embedding


async def batch_generate_embeddings(
    texts: Iterable[str],
    model: str = DEFAULT_EMBEDDING_MODEL
) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts.

    Args:
        texts: Iterable of input strings
        model: Embedding model name (default: text-embedding-3-small)

    Returns:
        List of embedding vectors corresponding to input texts order
    """
    text_list = [t for t in texts if t and t.strip()]
    if not text_list:
        raise ValueError("No valid texts provided for embedding")

    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", "your-api-key"))

    logger.info(f"Batch generating {len(text_list)} embeddings with model: {model}")
    response = await client.embeddings.create(
        model=model,
        input=text_list
    )

    embeddings = [item.embedding for item in response.data]
    logger.info("Batch embeddings generated successfully")
    return embeddings
