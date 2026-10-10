"""
FastAPI Application for Cat IoT Health Monitoring System

This module provides a FastAPI-based HTTP API for the cat health monitoring system,
replacing the Cloudflare Workers entry point for local deployment.

Endpoints:
    - GET /health: Health check
    - WebSocket /ws/chat: Real-time chat with progress streaming
    - POST /chat: Initialize SSE chat stream, returns stream_id
    - GET /chat/stream/{stream_id}: SSE endpoint for streaming chat responses
    - GET /chat/result/{session_id}: Fetch cached result after disconnect
    - POST /analyze/{user_id}: SSE streaming analysis for user's cats
    - WebSocket /ws/push/{user_id}: Real-time push notifications

Architecture Notes (V3.5):
    - SSE (POST /chat + GET /chat/stream/{stream_id}) for chat streaming
    - SSE (POST /analyze/{user_id}) for analysis streaming with progress updates
    - WebSocket /ws/push/{user_id} for server push notifications
    - WebSocket /ws/chat retained for backward compatibility
    - Media uploads via HTTP are removed; clients provide media_url directly
    - Data fetching is internal (via d1_client functions)
    - /analyze/{user_id} returns SSE stream with progress and result events

Usage:
    uvicorn api:app --host 0.0.0.0 --port 8000

    For development:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import logging
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

import asyncio

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uuid
import time

from flow import (
    create_chat_flow,
    create_analyze_flow
)

logger = logging.getLogger(__name__)

# 简单的内存缓存用于断开重连获取结果
# NOTE: This is single-worker only. For multi-worker deployment, use Redis or external cache.
# Supports lookup by both session_id and stream_id for SSE reconnection
# Format: {id: {result: dict, created_at: float}}
_session_result_cache: dict[str, dict] = {}
_RESULT_CACHE_TTL_SECONDS = 300  # 5-minute TTL for cached results

# SSE pending streams cache with TTL (stream_id -> {request_data, created_at})
# TTL: 5 minutes (300 seconds)
_pending_streams: dict[str, dict] = {}
_STREAM_TTL_SECONDS = 300

# WebSocket Push Connection Pool: user_id -> list of WebSocket connections
# Supports multiple connections per user (e.g., multiple devices)
_push_connections: dict[int, list] = {}

# Push WebSocket heartbeat configuration
_PUSH_HEARTBEAT_INTERVAL = 30  # Expect ping every 30 seconds
_PUSH_HEARTBEAT_TIMEOUT = 60   # Disconnect after 60 seconds of inactivity


# ============================================================================
# Pydantic Models
# ============================================================================

class ChatRequest(BaseModel):
    """
    Deprecated: legacy HTTP /chat request model retained for documentation only.
    """
    user_id: int = Field(..., description="User ID for data access control")
    cat_id: int = Field(..., description="Cat ID to query about")
    user_input: str = Field("", description="User's question or message (can be empty if media provided)")
    session_id: Optional[str] = Field(None, description="Conversation session ID")
    media_url: Optional[str] = Field(None, description="Media URL (if already uploaded)")
    media_type: Optional[str] = Field(None, description="Media type: 'image' or 'video'")


class AlertData(BaseModel):
    """Alert data structure for /chat response (V3.3.8)."""
    type: str = Field(..., description="Alert type: emergency, pain_detected, outdoor_extended, outdoor_night, device_offline")
    title: str = Field(..., description="Alert title for display")
    body: str = Field(..., description="Detailed alert message")
    urgency: str = Field("high", description="Urgency level: low, medium, high, critical")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    recommendation: Optional[str] = Field(None, description="Recommended action")


class ChatResponse(BaseModel):
    """
    Deprecated: legacy HTTP /chat response model retained for documentation.

    V3.3.8: Added `alerts` field for structured alert data.
    - `response`: Normal conversation reply (no alert text embedded)
    - `alerts`: Structured alert data for App to display separately
    """
    status: str
    response: Optional[str] = None
    cat_id: int
    session_id: Optional[str] = None
    alerts: Optional[List[AlertData]] = Field(None, description="Structured alert data (V3.3.8)")
    media_analysis: Optional[dict] = None
    code: int = 200


class MediaUploadResponse(BaseModel):
    """Deprecated: legacy /upload/media response model retained for documentation."""
    status: str
    media_url: str
    media_type: str
    code: int = 200


class AnalyzeRequest(BaseModel):
    """Request model for /analyze/{user_id} endpoint."""
    cat_id: Optional[int] = Field(None, description="Cat ID to analyze (None for all user's cats)")
    analysis_type: str = Field(..., description="Type of analysis: daily_summary, weekly_report, monthly_report, health_prediction, trend_analysis, behavior_pattern, vet_recommendation, comparison, multi_cat_comparison, anomaly_detection")
    time_range: Optional[str] = Field("24h", description="Time range for analysis")


class ChatStreamRequest(BaseModel):
    """Request model for POST /chat SSE endpoint."""
    user_id: int = Field(..., description="User ID for data access control")
    cat_id: int = Field(..., description="Cat ID to query about")
    user_input: str = Field("", description="User's question or message (can be empty if media provided)")
    session_id: Optional[str] = Field(None, description="Conversation session ID")
    media_url: Optional[str] = Field(None, description="Media URL (if already uploaded)")
    media_type: Optional[str] = Field(None, description="Media type: 'image' or 'video'")
    device_mac: Optional[str] = Field(None, description="Device MAC address for time-series queries")


class ChatStreamInitResponse(BaseModel):
    """Response model for POST /chat endpoint returning stream_id."""
    stream_id: str = Field(..., description="Unique stream ID for SSE connection")


class AnalyzeResponse(BaseModel):
    """Response model for /analyze endpoint."""
    status: str
    analysis_type: str
    cat_id: int
    result: Optional[dict] = None
    code: int = 200




# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    logger.info("Starting Cat IoT Health Monitoring System...")
    yield
    logger.info("Shutting down Cat IoT Health Monitoring System...")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Cat IoT Health Monitoring System",
    description="AI-powered cat health monitoring with IoT device integration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ============================================================================
# WebSocket Chat Endpoint
# ============================================================================


@app.websocket('/ws/chat')
async def websocket_chat(websocket: WebSocket):
    """
    [DEPRECATED] WebSocket chat endpoint with real-time progress streaming.

    DEPRECATION NOTICE (V3.5):
        This endpoint is deprecated and will be removed in v4.0.
        Please migrate to the new SSE-based endpoints:
        - POST /chat: Initialize chat stream, returns stream_id
        - GET /chat/stream/{stream_id}: SSE endpoint for streaming responses

    Message format (JSON):
    - Request: {user_id, cat_id, user_input, session_id?, media_url?, media_type?, device_mac?}
    - Progress: {type: 'progress', node: str, status: str, message: str}
    - Streaming: {type: 'streaming', token: str}
    - Final: {type: 'final_answer', response: str, cat_id: int, session_id: str, alerts?: list}
    - Error: {type: 'error', message: str, code: int}

    device_mac (V3.4):
        Optional device MAC address for querying time-series data from device-service.
        When provided, enables direct device data queries via device_service_client.
    """
    # DEPRECATION WARNING: Log usage for migration tracking
    logger.warning(
        'DEPRECATED: /ws/chat will be removed in v4.0. '
        'Use POST /chat + GET /chat/stream/{stream_id} for SSE-based streaming.'
    )

    await websocket.accept()

    try:
        data = await websocket.receive_json()

        user_id = data.get('user_id')
        cat_id = data.get('cat_id')
        user_input = data.get('user_input', '')
        session_id = data.get('session_id')
        media_url = data.get('media_url')
        media_type = data.get('media_type')
        device_mac = data.get('device_mac')  # V3.4: Device MAC for time-series queries

        if session_id and session_id in _session_result_cache:
            cached = _session_result_cache.pop(session_id)
            await websocket.send_json(cached)
            await websocket.close()
            return

        if not user_id or not cat_id:
            await websocket.send_json({
                'type': 'error',
                'message': 'user_id and cat_id are required',
                'code': 400
            })
            await websocket.close()
            return

        if not user_input and not media_url:
            await websocket.send_json({
                'type': 'error',
                'message': 'Either user_input or media_url must be provided',
                'code': 400
            })
            await websocket.close()
            return

        logger.info(f'WebSocket chat: user_id={user_id}, cat_id={cat_id}, device_mac={device_mac}, has_media={bool(media_url)}')

        progress_queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(msg: dict):
            await progress_queue.put(msg)

        shared = {
            'request': {
                'user_id': user_id,
                'cat_id': cat_id,
                'user_input': user_input,
                'session_id': session_id,
                'media_url': media_url,
                'media_type': media_type,
                'device_mac': device_mac  # V3.4: Device MAC for time-series queries
            },
            'user_id': user_id,
            'cat_id': cat_id,
            'user_input': user_input,
            'session_id': session_id,
            'device_mac': device_mac,  # V3.4: Accessible at top level for device_data_functions
            'progress_callback': progress_callback
        }

        chat_flow = create_chat_flow()
        flow_task = asyncio.create_task(chat_flow.run_async(shared))

        client_connected = True

        # Efficient event-driven loop using asyncio.wait instead of polling
        async def consume_queue():
            """Consume progress messages and send to WebSocket."""
            nonlocal client_connected
            while True:
                try:
                    msg = await progress_queue.get()
                    if msg is None:  # Sentinel value to stop
                        break
                    if client_connected:
                        await websocket.send_json(msg)
                except WebSocketDisconnect:
                    client_connected = False
                    logger.info(f'WebSocket disconnected during flow execution: session_id={session_id}')

        queue_task = asyncio.create_task(consume_queue())

        # Wait for flow to complete
        await flow_task

        # Signal queue consumer to stop and drain remaining messages
        await progress_queue.put(None)
        await queue_task

        response_text = shared.get('response', shared.get('chat_response', ''))
        final_session_id = shared.get('session_id', session_id)

        alerts = []
        emergency_alert = shared.get('emergency_alert')
        if emergency_alert:
            alert_data = emergency_alert.get('alert_data', {})
            alerts.append({
                'type': emergency_alert.get('alert_type', 'emergency'),
                'title': alert_data.get('title', 'Emergency Alert'),
                'body': alert_data.get('body', ''),
                'urgency': alert_data.get('urgency', 'high'),
                'timestamp': emergency_alert.get('timestamp', datetime.now().isoformat()),
                'recommendation': alert_data.get('recommendation')
            })

        media_analysis = None
        if media_url:
            cat_detection = shared.get('cat_detection', {})
            vision_analysis = shared.get('vision_analysis', {})
            if cat_detection or vision_analysis:
                media_analysis = {
                    'has_cat': cat_detection.get('has_cat', False),
                    'has_object_in_mouth': cat_detection.get('has_object_in_mouth', False),
                    'object_type': cat_detection.get('object_type'),
                    'pain_score': vision_analysis.get('pain_score'),
                    'overall_status': vision_analysis.get('overall_status'),
                    'mood': vision_analysis.get('mood')
                }

        final_result = {
            'type': 'final_answer',
            'status': 'success',
            'response': response_text,
            'cat_id': cat_id,
            'session_id': final_session_id,
            'alerts': alerts if alerts else None,
            'media_analysis': media_analysis
        }

        # Cache with TTL format for consistency with SSE caching
        if final_session_id:
            cache_entry = {'result': final_result, 'created_at': time.time()}
            _session_result_cache[final_session_id] = cache_entry

        if client_connected:
            await websocket.send_json(final_result)

    except WebSocketDisconnect:
        logger.info('WebSocket disconnected')
    except Exception as e:
        logger.exception(f'WebSocket error: {e}')
        try:
            await websocket.send_json({
                'type': 'error',
                'message': str(e),
                'code': 500
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.get('/chat/result/{id}')
async def get_cached_result(id: str):
    """
    Get cached result for a disconnected session or SSE stream.

    This endpoint supports lookup by both session_id and stream_id,
    enabling SSE clients to retrieve cached results after reconnection.

    Args:
        id: Either a session_id or stream_id to lookup cached result

    Returns:
        Cached final_answer result if found and not expired (5-minute TTL)

    Raises:
        HTTPException(404): If result not found or expired
    """
    # Cleanup expired cache entries periodically
    _cleanup_expired_result_cache()

    cache_entry = _session_result_cache.pop(id, None)
    if cache_entry:
        # Handle both old format (direct result) and new format ({result, created_at})
        if isinstance(cache_entry, dict) and 'result' in cache_entry:
            # Check TTL
            if time.time() - cache_entry.get('created_at', 0) <= _RESULT_CACHE_TTL_SECONDS:
                return cache_entry['result']
            else:
                raise HTTPException(status_code=404, detail='Session result expired')
        else:
            # Legacy format (backward compatibility with WebSocket cache)
            return cache_entry

    raise HTTPException(status_code=404, detail='Session result not found or expired')


# ============================================================================
# SSE Chat Endpoints
# ============================================================================

def _cleanup_expired_streams():
    """Remove expired pending streams (TTL 5 minutes)."""
    current_time = time.time()
    expired_keys = [
        stream_id for stream_id, data in _pending_streams.items()
        if current_time - data.get('created_at', 0) > _STREAM_TTL_SECONDS
    ]
    for key in expired_keys:
        del _pending_streams[key]
        logger.debug(f'Expired stream cleaned up: {key}')


def _cleanup_expired_result_cache():
    """Remove expired result cache entries (TTL 5 minutes)."""
    current_time = time.time()
    expired_keys = [
        cache_id for cache_id, data in _session_result_cache.items()
        if current_time - data.get('created_at', 0) > _RESULT_CACHE_TTL_SECONDS
    ]
    for key in expired_keys:
        del _session_result_cache[key]
        logger.debug(f'Expired result cache cleaned up: {key}')


@app.post('/chat', response_model=ChatStreamInitResponse)
async def create_chat_stream(request: ChatStreamRequest):
    """
    Initialize a chat stream and return a stream_id for SSE connection.

    This endpoint validates the request and returns a stream_id that can be used
    to connect to the SSE endpoint GET /chat/stream/{stream_id}.

    The stream_id is valid for 5 minutes. After that, it expires and cannot be used.

    Args:
        request: Chat request with user_id, cat_id, user_input, etc.

    Returns:
        ChatStreamInitResponse with stream_id
    """
    # Cleanup expired streams periodically
    _cleanup_expired_streams()

    # Validate request
    if not request.user_input and not request.media_url:
        raise HTTPException(
            status_code=400,
            detail='Either user_input or media_url must be provided'
        )

    # Generate stream_id
    stream_id = str(uuid.uuid4())

    # Store request in pending streams cache
    _pending_streams[stream_id] = {
        'request': request.model_dump(),
        'created_at': time.time()
    }

    logger.info(f'Chat stream created: stream_id={stream_id}, user_id={request.user_id}, cat_id={request.cat_id}')

    return ChatStreamInitResponse(stream_id=stream_id)


async def _sse_event_generator(stream_id: str):
    """
    Async generator that produces SSE events for a chat stream.

    Event types:
    - progress: Flow node progress updates
    - streaming: LLM token streaming
    - final_answer: Complete response with all data
    - error: Error messages

    SSE format: 'event: {type}\\ndata: {json}\\n\\n'
    """
    import json

    # Retrieve request from pending streams
    stream_data = _pending_streams.pop(stream_id, None)
    if not stream_data:
        error_event = {
            'type': 'error',
            'message': 'Stream not found or expired',
            'code': 404
        }
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
        return

    request_data = stream_data['request']
    user_id = request_data.get('user_id')
    cat_id = request_data.get('cat_id')
    user_input = request_data.get('user_input', '')
    session_id = request_data.get('session_id')
    media_url = request_data.get('media_url')
    media_type = request_data.get('media_type')
    device_mac = request_data.get('device_mac')

    logger.info(f'SSE stream started: stream_id={stream_id}, user_id={user_id}, cat_id={cat_id}')

    try:
        progress_queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(msg: dict):
            await progress_queue.put(msg)

        shared = {
            'request': {
                'user_id': user_id,
                'cat_id': cat_id,
                'user_input': user_input,
                'session_id': session_id,
                'media_url': media_url,
                'media_type': media_type,
                'device_mac': device_mac
            },
            'user_id': user_id,
            'cat_id': cat_id,
            'user_input': user_input,
            'session_id': session_id,
            'device_mac': device_mac,
            'progress_callback': progress_callback
        }

        chat_flow = create_chat_flow()

        # Run flow in background task
        async def run_flow():
            try:
                await chat_flow.run_async(shared)
            except Exception as e:
                logger.exception(f'Flow execution error: {e}')
                await progress_queue.put({
                    'type': 'error',
                    'message': str(e),
                    'code': 500
                })
            finally:
                await progress_queue.put(None)  # Sentinel to signal completion

        flow_task = asyncio.create_task(run_flow())

        # Consume progress queue and yield SSE events
        while True:
            msg = await progress_queue.get()
            if msg is None:  # Sentinel - flow completed
                break

            event_type = msg.get('type', 'progress')
            yield f"event: {event_type}\ndata: {json.dumps(msg)}\n\n"

        # Wait for flow task to complete
        await flow_task

        # Build final answer
        response_text = shared.get('response', shared.get('chat_response', ''))
        final_session_id = shared.get('session_id', session_id)

        alerts = []
        emergency_alert = shared.get('emergency_alert')
        if emergency_alert:
            alert_data = emergency_alert.get('alert_data', {})
            alerts.append({
                'type': emergency_alert.get('alert_type', 'emergency'),
                'title': alert_data.get('title', 'Emergency Alert'),
                'body': alert_data.get('body', ''),
                'urgency': alert_data.get('urgency', 'high'),
                'timestamp': emergency_alert.get('timestamp', datetime.now().isoformat()),
                'recommendation': alert_data.get('recommendation')
            })

        media_analysis = None
        if media_url:
            cat_detection = shared.get('cat_detection', {})
            vision_analysis = shared.get('vision_analysis', {})
            if cat_detection or vision_analysis:
                media_analysis = {
                    'has_cat': cat_detection.get('has_cat', False),
                    'has_object_in_mouth': cat_detection.get('has_object_in_mouth', False),
                    'object_type': cat_detection.get('object_type'),
                    'pain_score': vision_analysis.get('pain_score'),
                    'overall_status': vision_analysis.get('overall_status'),
                    'mood': vision_analysis.get('mood')
                }

        final_result = {
            'type': 'final_answer',
            'status': 'success',
            'response': response_text,
            'cat_id': cat_id,
            'session_id': final_session_id,
            'stream_id': stream_id,  # Include stream_id for SSE reconnection reference
            'alerts': alerts if alerts else None,
            'media_analysis': media_analysis
        }

        # Cache result for potential retrieval by both stream_id and session_id
        # Format: {result: dict, created_at: float} with 5-minute TTL
        cache_entry = {'result': final_result, 'created_at': time.time()}
        _session_result_cache[stream_id] = cache_entry  # Primary key for SSE
        if final_session_id:
            _session_result_cache[final_session_id] = cache_entry  # Secondary key

        yield f"event: final_answer\ndata: {json.dumps(final_result)}\n\n"

    except Exception as e:
        logger.exception(f'SSE stream error: {e}')
        error_event = {
            'type': 'error',
            'message': str(e),
            'code': 500
        }
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"


@app.get('/chat/stream/{stream_id}')
async def get_chat_stream(stream_id: str):
    """
    SSE endpoint for streaming chat responses.

    Connect to this endpoint with the stream_id obtained from POST /chat.
    The connection will stream events until the chat is complete.

    Event types:
    - progress: {type: 'progress', node: str, status: str, message: str}
    - streaming: {type: 'streaming', token: str}
    - final_answer: {type: 'final_answer', response: str, cat_id: int, session_id: str, alerts?: list}
    - error: {type: 'error', message: str, code: int}

    Args:
        stream_id: The stream ID from POST /chat

    Returns:
        StreamingResponse with SSE events
    """
    # Check if stream exists before starting SSE
    if stream_id not in _pending_streams:
        raise HTTPException(status_code=404, detail='Stream not found or expired')

    return StreamingResponse(
        _sse_event_generator(stream_id),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering
        }
    )


# ============================================================================
# Analysis Endpoint (SSE Streaming)
# ============================================================================

async def _analyze_event_generator(user_id: int, request: AnalyzeRequest):
    """
    Async generator that produces SSE events for analysis streaming.

    Event types:
    - progress: Analysis node execution status updates
    - result: Final analysis result with complete data
    - error: Error messages

    SSE format: 'event: {type}\\ndata: {json}\\n\\n'

    Args:
        user_id: User ID from URL path
        request: Analysis request parameters

    Yields:
        SSE formatted event strings
    """
    # Validate analysis type
    valid_types = [
        'daily_summary', 'weekly_report', 'monthly_report',  # report flows
        'health_prediction', 'trend_analysis', 'behavior_pattern', 'vet_recommendation',  # prediction flows
        'comparison', 'multi_cat_comparison', 'anomaly_detection'  # special flows
    ]
    if request.analysis_type not in valid_types:
        error_event = {
            'type': 'error',
            'message': f"Invalid analysis_type. Must be one of: {valid_types}",
            'code': 400
        }
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
        return

    logger.info(f"Analysis SSE stream started: user_id={user_id}, cat_id={request.cat_id}, type={request.analysis_type}")

    try:
        progress_queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(msg: dict):
            """Progress callback for analysis flow nodes."""
            await progress_queue.put(msg)

        # Build shared context with user_id from path and progress_callback
        shared = {
            'request': {
                'user_id': user_id,
                'cat_id': request.cat_id,
                'analysis_type': request.analysis_type,
                'time_range': request.time_range
            },
            'user_id': user_id,
            'cat_id': request.cat_id,
            'analysis_type': request.analysis_type,
            'time_range': request.time_range,
            'progress_callback': progress_callback
        }

        # Run analysis flow in background task
        async def run_analysis_flow():
            try:
                analysis_flow = create_analyze_flow(request.analysis_type)
                await analysis_flow.run_async(shared)
            except Exception as e:
                logger.exception(f'Analysis flow execution error: {e}')
                await progress_queue.put({
                    'type': 'error',
                    'message': str(e),
                    'code': 500
                })
            finally:
                await progress_queue.put(None)  # Sentinel to signal completion

        flow_task = asyncio.create_task(run_analysis_flow())

        # Consume progress queue and yield SSE events
        while True:
            msg = await progress_queue.get()
            if msg is None:  # Sentinel - flow completed
                break

            event_type = msg.get('type', 'progress')
            yield f"event: {event_type}\ndata: {json.dumps(msg)}\n\n"

        # Wait for flow task to complete
        await flow_task

        # Build final result
        result = shared.get('analysis_result', shared.get('health_summary', {}))

        final_result = {
            'type': 'result',
            'status': 'success',
            'analysis_type': request.analysis_type,
            'cat_id': request.cat_id,
            'user_id': user_id,
            'result': result,
            'timestamp': datetime.now().isoformat()
        }

        yield f"event: result\ndata: {json.dumps(final_result)}\n\n"

        logger.info(f"Analysis SSE stream completed: user_id={user_id}, cat_id={request.cat_id}, type={request.analysis_type}")

    except Exception as e:
        logger.exception(f'Analysis SSE stream error: {e}')
        error_event = {
            'type': 'error',
            'message': str(e),
            'code': 500
        }
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"


@app.post("/analyze/{user_id}")
async def analyze(user_id: int, request: AnalyzeRequest):
    """
    Server-scheduled analysis endpoint for user's cats with SSE streaming.

    This endpoint returns a Server-Sent Events (SSE) stream instead of a
    synchronous JSON response, enabling real-time progress visibility
    during long-running analysis flows.

    This endpoint is called by scheduled server tasks to:
    - Generate daily health summaries
    - Create weekly/monthly reports
    - Send health reminders
    - Detect anomalies and generate alerts

    The system fetches device data internally via database queries,
    no external webhook required.

    Supports analysis types:
    - daily_summary: Daily health summary with key metrics
    - weekly_report: Weekly trend analysis
    - monthly_report: Monthly trend analysis
    - health_prediction: Health prediction based on trends
    - trend_analysis: Trend analysis over time
    - behavior_pattern: Behavioral pattern analysis
    - vet_recommendation: Veterinary recommendations
    - comparison: Comparison analysis
    - multi_cat_comparison: Multi-cat comparison analysis
    - anomaly_detection: Anomaly detection analysis

    SSE Event Types:
    - progress: {type: 'progress', node: str, status: str, message: str}
        Analysis node execution status updates
    - result: {type: 'result', status: str, analysis_type: str, cat_id: int, result: dict}
        Final analysis result with complete data
    - error: {type: 'error', message: str, code: int}
        Error messages

    Args:
        user_id: User ID from URL path (for server scheduled calls)
        request: Analysis parameters (cat_id optional, analysis_type required)

    Returns:
        StreamingResponse with Content-Type: text/event-stream
    """
    return StreamingResponse(
        _analyze_event_generator(user_id, request),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering
        }
    )


# ============================================================================
# WebSocket Push Notification Endpoint
# ============================================================================

async def broadcast_to_user(user_id: int, message: dict) -> int:
    """
    Broadcast a message to all active WebSocket connections for a specific user.

    Args:
        user_id: User identifier
        message: Message dictionary to broadcast (will be JSON serialized)

    Returns:
        int: Number of successful sends

    Example:
        count = await broadcast_to_user(123, {
            "event": "notification",
            "data": {"type": "emergency", "title": "Alert", "body": "..."}
        })
    """
    import json

    if user_id not in _push_connections or not _push_connections[user_id]:
        logger.debug(f"No active push connections for user_id={user_id}")
        return 0

    success_count = 0
    failed_connections = []

    # Iterate over a copy of the list to avoid race conditions during await
    for websocket in list(_push_connections[user_id]):
        try:
            await websocket.send_json(message)
            success_count += 1
        except Exception as e:
            logger.warning(f"Failed to send push message to user_id={user_id}: {e}")
            failed_connections.append(websocket)

    # Clean up failed connections
    for ws in failed_connections:
        try:
            _push_connections[user_id].remove(ws)
        except ValueError:
            pass

    if not _push_connections[user_id]:
        del _push_connections[user_id]

    logger.info(f"Push broadcast to user_id={user_id}: {success_count}/{success_count + len(failed_connections)} successful")
    return success_count


@app.websocket('/ws/push/{user_id}')
async def websocket_push(websocket: WebSocket, user_id: int):
    """
    WebSocket endpoint for IoT push notifications.

    This endpoint provides a dedicated channel for receiving real-time IoT
    notifications such as health alerts, device status updates, and emergency
    notifications.

    Connection lifecycle:
    1. Client connects with user_id path parameter
    2. Server accepts and registers connection in pool
    3. Client must send ping every 30 seconds to maintain connection
    4. Server responds with pong to heartbeat pings
    5. Connection is closed after 60 seconds of inactivity
    6. On disconnect, connection is removed from pool

    Message format (incoming):
    - Heartbeat: {"type": "ping"}

    Message format (outgoing):
    - Heartbeat response: {"type": "pong", "timestamp": "ISO8601"}
    - Notification: {"event": "notification", "timestamp": "ISO8601", "data": {...}}
    - Connected: {"type": "connected", "user_id": int, "message": str}
    - Error: {"type": "error", "message": str}

    Args:
        websocket: WebSocket connection object
        user_id: User ID from URL path parameter
    """
    await websocket.accept()

    # Register connection in pool
    if user_id not in _push_connections:
        _push_connections[user_id] = []
    _push_connections[user_id].append(websocket)

    logger.info(f"Push WebSocket connected: user_id={user_id}, total_connections={len(_push_connections[user_id])}")

    # Send connection confirmation
    try:
        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
            "message": f"Connected to push channel for user {user_id}",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to send connection confirmation: {e}")

    last_activity = time.time()

    try:
        while True:
            # Wait for message with timeout for heartbeat check
            try:
                # Use asyncio.wait_for to implement timeout
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=_PUSH_HEARTBEAT_TIMEOUT
                )

                last_activity = time.time()
                msg_type = message.get('type', '')

                if msg_type == 'ping':
                    # Respond to heartbeat ping
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
                    logger.debug(f"Push heartbeat pong sent to user_id={user_id}")
                else:
                    # Unknown message type - log and ignore
                    logger.debug(f"Push WebSocket received unknown message type from user_id={user_id}: {msg_type}")

            except asyncio.TimeoutError:
                # Check if we've exceeded the heartbeat timeout
                if time.time() - last_activity > _PUSH_HEARTBEAT_TIMEOUT:
                    logger.warning(f"Push WebSocket heartbeat timeout for user_id={user_id}")
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Heartbeat timeout - connection closing",
                            "timestamp": datetime.now().isoformat()
                        })
                    except Exception:
                        pass
                    break

    except WebSocketDisconnect:
        logger.info(f"Push WebSocket disconnected: user_id={user_id}")
    except Exception as e:
        logger.exception(f"Push WebSocket error for user_id={user_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            })
        except Exception:
            pass
    finally:
        # Clean up connection from pool
        if user_id in _push_connections:
            try:
                _push_connections[user_id].remove(websocket)
                if not _push_connections[user_id]:
                    del _push_connections[user_id]
                logger.info(f"Push WebSocket cleaned up: user_id={user_id}, remaining_connections={len(_push_connections.get(user_id, []))}")
            except ValueError:
                pass

        try:
            await websocket.close()
        except Exception:
            pass


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
