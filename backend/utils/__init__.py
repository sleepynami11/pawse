"""
Utility functions for Cloudflare services and LLM operations.

This module exports async clients for:
- D1 Database (SQL queries)
- R2 Object Storage (file operations)
- ChromaDB (local vector search, replaces Cloudflare Vectorize)
- LLM calls (OpenAI + OpenRouter)
- WebSocket IoT handler (real-time data streaming)
"""

from utils.call_llm import call_llm
from utils.call_llm_async import async_call_llm, async_call_vision_llm
from utils.embedding import generate_embedding, batch_generate_embeddings

# D1 Database client
from utils.d1_client import (
    execute_query,
    execute_batch,
    # User-scoped query functions
    get_user_cats,
    get_user_profile,
    get_user_devices,
    get_user_cat_health_summary,
    get_user_cat_activity_logs,
    get_user_cat_bcg_logs,
    get_user_cat_outdoor_logs,
    get_user_cat_door_passages,
    get_user_cat_expression_logs,
    get_user_alerts,
    get_user_vision_logs,
    get_user_conversation_sessions,
    get_user_id_from_cat,
    get_user_full_context,
)

# R2 Object Storage client
from utils.r2_client import (
    upload_file,
    get_file,
    delete_file,
    build_r2_path,
    build_r2_path_safe
)

# Vector search client (ChromaDB local storage)
from utils.chromadb_client import (
    insert_embeddings,
    search_similar,
    get_collection_info,
    delete_collection
)

# WebSocket IoT handler
from utils.iot_websocket import (
    handle_connection,
    send_message,
    broadcast_to_cat
)

# Push notification service
from utils.push_notification import (
    send_notification,
    send_websocket,
    send_apns_fcm
)

# Device Service client (TimescaleDB time-series data via device-service API)
from utils.device_service_client import (
    get_bcg_data,
    get_gps_data,
    get_imu_data,
    get_temp_data,
    get_device_events,
    get_door_detections
)

__all__ = [
    # LLM
    'call_llm',
    'async_call_llm',
    'async_call_vision_llm',
    'generate_embedding',
    'batch_generate_embeddings',
    # D1 Database - Core
    'execute_query',
    'execute_batch',
    # D1 Database - User-scoped queries
    'get_user_cats',
    'get_user_profile',
    'get_user_devices',
    'get_user_cat_health_summary',
    'get_user_cat_activity_logs',
    'get_user_cat_bcg_logs',
    'get_user_cat_outdoor_logs',
    'get_user_cat_door_passages',
    'get_user_cat_expression_logs',
    'get_user_alerts',
    'get_user_vision_logs',
    'get_user_conversation_sessions',
    'get_user_id_from_cat',
    'get_user_full_context',
    # R2 Object Storage
    'upload_file',
    'get_file',
    'delete_file',
    'build_r2_path',
    'build_r2_path_safe',
    # Vector Search (ChromaDB)
    'insert_embeddings',
    'search_similar',
    'get_collection_info',
    'delete_collection',
    # WebSocket IoT
    'handle_connection',
    'send_message',
    'broadcast_to_cat',
    # Push Notifications
    'send_notification',
    'send_websocket',
    'send_apns_fcm',
    # Device Service (TimescaleDB time-series data)
    'get_bcg_data',
    'get_gps_data',
    'get_imu_data',
    'get_temp_data',
    'get_device_events',
    'get_door_detections',
]
