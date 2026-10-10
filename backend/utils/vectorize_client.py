"""
Cloudflare Vectorize Async Client

This module provides async functions to interact with Cloudflare Vectorize
vector search service via REST API.

Environment Variables Required:
    - VECTORIZE_INDEX_NAME: The Vectorize index name
    - CLOUDFLARE_API_TOKEN: Cloudflare API token with Vectorize permissions
    - CLOUDFLARE_ACCOUNT_ID: Cloudflare account ID

Usage Example:
    import asyncio
    from utils.vectorize_client import insert_embeddings, search_similar

    async def main():
        # Insert embeddings
        success = await insert_embeddings("my-index", [
            {"id": "1", "values": [0.1, 0.2, 0.3], "metadata": {"text": "hello"}},
            {"id": "2", "values": [0.4, 0.5, 0.6], "metadata": {"text": "world"}}
        ])

        # Search similar vectors
        results = await search_similar("my-index", [0.1, 0.2, 0.3], top_k=5)

    asyncio.run(main())
"""

import httpx
import os
import logging

logger = logging.getLogger(__name__)

# Load environment variables
VECTORIZE_INDEX_NAME = os.getenv("VECTORIZE_INDEX_NAME")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")


async def insert_embeddings(index: str, embeddings: list[dict]) -> bool:
    """
    Insert vector embeddings into Cloudflare Vectorize index.

    Args:
        index: Vectorize index name
        embeddings: List of embedding dictionaries, each containing:
            - id (str): Unique identifier for the vector
            - values (list[float]): Vector embedding values
            - metadata (dict, optional): Additional metadata

    Returns:
        bool: True if insertion succeeded

    Raises:
        httpx.HTTPError: If API request fails
        ValueError: If required environment variables are missing

    Example:
        success = await insert_embeddings("my-index", [
            {
                "id": "doc-1",
                "values": [0.1, 0.2, 0.3, ...],
                "metadata": {"title": "Document 1", "category": "tech"}
            },
            {
                "id": "doc-2",
                "values": [0.4, 0.5, 0.6, ...],
                "metadata": {"title": "Document 2", "category": "science"}
            }
        ])
    """
    if not all([CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID]):
        error_msg = "Missing required environment variables: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID"
        logger.error(error_msg)
        raise ValueError(error_msg)

    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/vectorize/indexes/{index}/insert"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {"vectors": embeddings}

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Inserting {len(embeddings)} embeddings into Vectorize index: {index}")
            response = await client.post(url, json=payload, headers=headers, timeout=60.0)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Embeddings inserted successfully into Vectorize")
            return result.get("success", True)

    except httpx.HTTPError as e:
        logger.error(f"Vectorize insert failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Vectorize insert: {str(e)}")
        raise


async def search_similar(index: str, query_vector: list[float], top_k: int = 3) -> list[dict]:
    """
    Search for similar vectors in Cloudflare Vectorize index.

    Args:
        index: Vectorize index name
        query_vector: Query vector embedding (list of floats)
        top_k: Number of most similar results to return (default: 3)

    Returns:
        list[dict]: List of similar vectors, each containing:
            - id (str): Vector ID
            - score (float): Similarity score
            - metadata (dict): Associated metadata

    Raises:
        httpx.HTTPError: If API request fails
        ValueError: If required environment variables are missing

    Example:
        query_embedding = [0.1, 0.2, 0.3, ...]
        results = await search_similar("my-index", query_embedding, top_k=5)

        for result in results:
            print(f"ID: {result['id']}, Score: {result['score']}")
            print(f"Metadata: {result['metadata']}")
    """
    if not all([CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID]):
        error_msg = "Missing required environment variables: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID"
        logger.error(error_msg)
        raise ValueError(error_msg)

    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/vectorize/indexes/{index}/query"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "vector": query_vector,
        "top_k": top_k,
        "return_metadata": True
    }

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Searching Vectorize index: {index} (top_k={top_k})")
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()

            result = response.json()
            matches = result.get("result", {}).get("matches", [])
            logger.info(f"Found {len(matches)} similar vectors in Vectorize")
            return matches

    except httpx.HTTPError as e:
        logger.error(f"Vectorize search failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Vectorize search: {str(e)}")
        raise


if __name__ == "__main__":
    import asyncio

    async def test():
        """Test Vectorize client with example operations"""
        try:
            # Test insert
            test_embeddings = [
                {
                    "id": "test-1",
                    "values": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "metadata": {"text": "test document 1"}
                },
                {
                    "id": "test-2",
                    "values": [0.6, 0.7, 0.8, 0.9, 1.0],
                    "metadata": {"text": "test document 2"}
                }
            ]
            success = await insert_embeddings("test-index", test_embeddings)
            print(f"Insert successful: {success}")

            # Test search
            query_vector = [0.1, 0.2, 0.3, 0.4, 0.5]
            results = await search_similar("test-index", query_vector, top_k=2)
            print(f"Search results: {results}")

        except Exception as e:
            print(f"Test failed: {e}")

    asyncio.run(test())
