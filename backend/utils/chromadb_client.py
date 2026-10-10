"""
ChromaDB Local Vector Database Client

This module provides async functions to interact with ChromaDB for local
vector search operations, replacing Cloudflare Vectorize.

Features:
- Persistent storage in ./rag/vectordb directory
- Four-layer knowledge base support (L1-L4)
- Compatible API with the original vectorize_client

Usage Example:
    import asyncio
    from utils.chromadb_client import insert_embeddings, search_similar

    async def main():
        # Insert embeddings
        success = await insert_embeddings("rag-layer-l4-friendly", [
            {"id": "1", "values": [0.1, 0.2, ...], "metadata": {"text": "hello"}},
            {"id": "2", "values": [0.4, 0.5, ...], "metadata": {"text": "world"}}
        ])

        # Search similar vectors
        results = await search_similar("rag-layer-l4-friendly", [0.1, 0.2, ...], top_k=5)

    asyncio.run(main())
"""

import logging
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

# Persistent storage directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_PERSIST_DIR = os.getenv(
    "CHROMA_PERSIST_DIR",
    str(PROJECT_ROOT / "rag" / "vectordb")
)

# Map Cloudflare Vectorize index names to ChromaDB collection names
LAYER_COLLECTIONS = {
    "rag-layer-l4-friendly": "l4_user_friendly",
    "rag-layer-l3-care": "l3_daily_care",
    "rag-layer-l2-guides": "l2_clinical",
    "rag-layer-l1-medical": "l1_professional",
    # Memory layer for conversation embeddings (L0)
    "memory-layer-short-term": "memory_layer_short_term",
}

# Global client instance (lazy initialization)
from typing import Optional
_client: Optional[chromadb.PersistentClient] = None


def _get_client() -> chromadb.PersistentClient:
    """Get or create the ChromaDB persistent client."""
    global _client
    if _client is None:
        Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        logger.info(f"ChromaDB client initialized at: {CHROMA_PERSIST_DIR}")
    return _client


def get_collection(index: str) -> chromadb.Collection:
    """
    Get or create a ChromaDB collection for the given index.

    Args:
        index: The index name (Cloudflare Vectorize style or ChromaDB collection name)

    Returns:
        chromadb.Collection: The collection object
    """
    client = _get_client()
    collection_name = LAYER_COLLECTIONS.get(index, index)

    # Ensure collection name is valid (alphanumeric with underscores)
    collection_name = collection_name.replace("-", "_")

    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )


def get_user_memory_collection(user_id: str) -> chromadb.Collection:
    """
    Get or create a user-scoped Memory collection.

    Args:
        user_id: User ID for collection scoping

    Returns:
        chromadb.Collection: The user's memory collection

    Example:
        collection = get_user_memory_collection("user123")
    """
    client = _get_client()

    # Construct valid collection name (alphanumeric with underscores)
    # Replace hyphens and ensure alphanumeric
    collection_name = f"memory_{user_id}".replace("-", "_")

    # Validate collection name (ChromaDB requirement)
    if not collection_name.replace("_", "").isalnum():
        raise ValueError(f"Invalid user_id for collection name: {user_id}")

    return client.get_or_create_collection(
        name=collection_name,
        metadata={
            "hnsw:space": "cosine",
            "type": "memory",
            "user_id": user_id
        }
    )


def _clean_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """
    Clean metadata to ensure ChromaDB compatibility.

    ChromaDB only supports str, int, float, bool values in metadata.
    Lists, dicts, and None values need to be converted or removed.
    """
    if not metadata:
        return {}

    cleaned = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        elif isinstance(value, (list, dict)):
            # Convert complex types to JSON string
            import json
            cleaned[key] = json.dumps(value, ensure_ascii=False)
        else:
            # Convert other types to string
            cleaned[key] = str(value)
    return cleaned


async def insert_embeddings(index: str, embeddings: list[dict]) -> bool:
    """
    Insert vector embeddings into ChromaDB collection.

    Args:
        index: Collection/index name
        embeddings: List of embedding dictionaries, each containing:
            - id (str): Unique identifier for the vector
            - values (list[float]): Vector embedding values
            - metadata (dict, optional): Additional metadata

    Returns:
        bool: True if insertion succeeded

    Example:
        success = await insert_embeddings("rag-layer-l4-friendly", [
            {
                "id": "doc-1",
                "values": [0.1, 0.2, 0.3, ...],
                "metadata": {"text": "Document 1", "level": "L4"}
            }
        ])
    """
    try:
        collection = get_collection(index)

        ids = []
        vectors = []
        metadatas = []

        for emb in embeddings:
            ids.append(emb["id"])
            vectors.append(emb["values"])
            metadatas.append(_clean_metadata(emb.get("metadata", {})))

        logger.info(f"Inserting {len(embeddings)} embeddings into collection: {index}")

        # Batch upsert to avoid ChromaDB max batch size limit (5461)
        BATCH_SIZE = 5000
        total = len(ids)
        for i in range(0, total, BATCH_SIZE):
            batch_end = min(i + BATCH_SIZE, total)
            collection.upsert(
                ids=ids[i:batch_end],
                embeddings=vectors[i:batch_end],
                metadatas=metadatas[i:batch_end]
            )
            logger.info(f"Upserted batch {i}-{batch_end} of {total}")

        logger.info(f"Successfully inserted {len(embeddings)} embeddings into {index}")
        return True

    except Exception as e:
        logger.error(f"ChromaDB insert failed: {str(e)}")
        raise


async def search_similar(index: str, query_vector: list[float], top_k: int = 3) -> list[dict]:
    """
    Search for similar vectors in ChromaDB collection.

    Args:
        index: Collection/index name
        query_vector: Query vector embedding (list of floats)
        top_k: Number of most similar results to return (default: 3)

    Returns:
        list[dict]: List of similar vectors, each containing:
            - id (str): Vector ID
            - score (float): Similarity score (0-1, higher is more similar)
            - metadata (dict): Associated metadata

    Example:
        query_embedding = [0.1, 0.2, 0.3, ...]
        results = await search_similar("rag-layer-l4-friendly", query_embedding, top_k=5)

        for result in results:
            print(f"ID: {result['id']}, Score: {result['score']}")
    """
    try:
        collection = get_collection(index)

        logger.info(f"Searching collection: {index} (top_k={top_k})")

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["metadatas", "distances"]
        )

        # Convert ChromaDB results to the expected format
        matches = []
        if results["ids"] and results["ids"][0]:
            ids = results["ids"][0]
            distances = results["distances"][0] if results["distances"] else [0] * len(ids)
            metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)

            for i, (doc_id, distance, metadata) in enumerate(zip(ids, distances, metadatas)):
                # ChromaDB returns L2 distance by default, convert to similarity score
                # For cosine distance: similarity = 1 - distance (since we use cosine space)
                # ChromaDB cosine distance is in range [0, 2], so normalize
                score = max(0, 1 - distance / 2) if distance else 1.0

                matches.append({
                    "id": doc_id,
                    "score": score,
                    "metadata": metadata or {}
                })

        logger.info(f"Found {len(matches)} similar vectors in {index}")
        return matches

    except Exception as e:
        logger.error(f"ChromaDB search failed: {str(e)}")
        raise


async def insert_conversation_turn(user_id: str, turn_data: dict) -> bool:
    """
    Insert a conversation turn into user-scoped Memory collection.

    Args:
        user_id: User ID for collection scoping
        turn_data: Dictionary containing:
            - timestamp (str): ISO 8601 timestamp of the conversation turn
            - user_input (str): User's input text
            - assistant_response (str): Assistant's response text
            - embedding (list[float]): Embedding vector for the turn

    Returns:
        bool: True if insertion succeeded

    Example:
        success = await insert_conversation_turn("user123", {
            "timestamp": "2025-12-18T10:00:00Z",
            "user_input": "How is my cat today?",
            "assistant_response": "Your cat is doing well...",
            "embedding": [0.1, 0.2, ...]
        })
    """
    try:
        # Validate required fields
        required_fields = ["timestamp", "user_input", "embedding"]
        for field in required_fields:
            if field not in turn_data:
                raise ValueError(f"Missing required field: {field}")

        # Get or create user-scoped collection
        collection = get_user_memory_collection(user_id)

        # Generate unique ID from user_id and timestamp
        turn_id = f"{user_id}_{turn_data['timestamp'].replace(':', '-').replace('.', '-')}"

        # Clean metadata (ChromaDB only supports str/int/float/bool)
        metadata = _clean_metadata({
            "timestamp": turn_data["timestamp"],
            "user_input": turn_data["user_input"],
            "assistant_response": turn_data.get("assistant_response", ""),
            "user_id": user_id
        })

        # Insert embedding with metadata
        collection.upsert(
            ids=[turn_id],
            embeddings=[turn_data["embedding"]],
            metadatas=[metadata]
        )

        logger.info(f"Inserted conversation turn for user {user_id} at {turn_data['timestamp']}")
        return True

    except Exception as e:
        logger.error(f"Failed to insert conversation turn for user {user_id}: {str(e)}")
        raise


async def search_conversation_memory(
    user_id: str,
    query_vector: list[float],
    top_k: int = 5,
    recency_days: int = 30
) -> list[dict]:
    """
    Search conversation memory for user-scoped collection with recency filtering.

    Args:
        user_id: User ID for collection scoping
        query_vector: Query embedding vector
        top_k: Number of results to return (default 5)
        recency_days: Only return results from last N days (default 30)

    Returns:
        list[dict]: List of conversation turns sorted by temporal-weighted score:
            - id (str): Turn ID
            - score (float): Similarity score with temporal decay
            - metadata (dict): Turn metadata (timestamp, user_input, assistant_response)

    Example:
        results = await search_conversation_memory(
            user_id="user123",
            query_vector=[0.1, 0.2, ...],
            top_k=5,
            recency_days=30
        )
    """
    try:
        from datetime import datetime, timedelta
        import math

        # Get user-scoped collection
        try:
            collection = get_user_memory_collection(user_id)
            if collection.count() == 0:
                logger.info(f"Empty memory collection for user {user_id}")
                return []
        except Exception as e:
            logger.warning(f"Memory collection not found for user {user_id}: {str(e)}")
            return []

        # Query with larger limit for filtering
        logger.info(f"Searching memory for user {user_id} (top_k={top_k}, recency_days={recency_days})")

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k * 2,  # Fetch more for recency filtering
            include=["metadatas", "distances"]
        )

        if not results["ids"] or not results["ids"][0]:
            logger.info(f"No memory results found for user {user_id}")
            return []

        # Calculate recency filter timestamp
        now = datetime.utcnow()
        min_timestamp = (now - timedelta(days=recency_days)).isoformat()

        # Process and filter results
        matches = []
        ids = results["ids"][0]
        distances = results["distances"][0] if results["distances"] else [0] * len(ids)
        metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)

        for doc_id, distance, metadata in zip(ids, distances, metadatas):
            # Parse timestamp
            timestamp_str = metadata.get("timestamp", "")
            if not timestamp_str:
                continue

            # Apply recency filter
            if timestamp_str < min_timestamp:
                continue

            # Calculate base similarity score (cosine)
            base_score = max(0, 1 - distance / 2) if distance else 1.0

            # Apply temporal decay: score = base_score * exp(-days_ago * 0.1)
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                days_ago = (now - timestamp).total_seconds() / 86400
                decay_factor = math.exp(-days_ago * 0.1)
                final_score = base_score * decay_factor
            except Exception as e:
                logger.warning(f"Failed to parse timestamp {timestamp_str}: {str(e)}")
                final_score = base_score

            matches.append({
                "id": doc_id,
                "score": final_score,
                "metadata": metadata
            })

        # Sort by final score and return top_k
        matches.sort(key=lambda x: x["score"], reverse=True)
        results_list = matches[:top_k]

        logger.info(f"Found {len(results_list)} memory results for user {user_id}")
        return results_list

    except Exception as e:
        logger.error(f"Memory search failed for user {user_id}: {str(e)}")
        return []


async def delete_collection(index: str) -> bool:
    """
    Delete an entire collection from ChromaDB.

    Args:
        index: Collection/index name to delete

    Returns:
        bool: True if deletion succeeded
    """
    try:
        client = _get_client()
        collection_name = LAYER_COLLECTIONS.get(index, index).replace("-", "_")

        client.delete_collection(name=collection_name)
        logger.info(f"Deleted collection: {collection_name}")
        return True

    except Exception as e:
        logger.error(f"ChromaDB delete collection failed: {str(e)}")
        raise


async def get_collection_info(index: str) -> dict:
    """
    Get information about a collection.

    Args:
        index: Collection/index name

    Returns:
        dict: Collection information including count
    """
    try:
        collection = get_collection(index)
        count = collection.count()
        return {
            "name": collection.name,
            "count": count,
            "metadata": collection.metadata
        }
    except Exception as e:
        logger.error(f"ChromaDB get collection info failed: {str(e)}")
        raise


def reset_database() -> bool:
    """
    Reset the entire ChromaDB database. Use with caution!

    Returns:
        bool: True if reset succeeded
    """
    global _client
    try:
        client = _get_client()
        client.reset()
        _client = None  # Force re-initialization
        logger.warning("ChromaDB database has been reset!")
        return True
    except Exception as e:
        logger.error(f"ChromaDB reset failed: {str(e)}")
        raise


if __name__ == "__main__":
    import asyncio

    async def test():
        """Test ChromaDB client with example operations"""
        try:
            # Test insert
            test_embeddings = [
                {
                    "id": "test-1",
                    "values": [0.1] * 1536,  # text-embedding-3-small dimension
                    "metadata": {"text": "test document 1", "level": "L4"}
                },
                {
                    "id": "test-2",
                    "values": [0.2] * 1536,
                    "metadata": {"text": "test document 2", "level": "L4"}
                }
            ]
            success = await insert_embeddings("rag-layer-l4-friendly", test_embeddings)
            print(f"Insert successful: {success}")

            # Test search
            query_vector = [0.15] * 1536
            results = await search_similar("rag-layer-l4-friendly", query_vector, top_k=2)
            print(f"Search results: {results}")

            # Test collection info
            info = await get_collection_info("rag-layer-l4-friendly")
            print(f"Collection info: {info}")

        except Exception as e:
            print(f"Test failed: {e}")

    asyncio.run(test())
