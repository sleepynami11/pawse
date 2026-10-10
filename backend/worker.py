"""
Cloudflare Workers Entry Point for Cat IoT Agent System

This module provides HTTP request handlers with async event loop for:
- IoT webhook processing (sensor data ingestion)
- Chat interface (user queries about cat health)

Design:
- Async request handlers for non-blocking I/O
- Per-request SystemContext initialization
- Shared store pattern for flow communication
- Error handling with proper HTTP status codes
"""

import asyncio
import json
import logging
from datetime import datetime
from flow import (
    create_master_flow,
    create_multi_cat_flow,
    create_collar_flow,
    create_cat_door_flow,
    create_analyze_flow
)
from context_manager import SystemContext
from utils.iot_websocket import handle_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_iot_webhook(request: dict) -> dict:
    """
    Handle IoT webhook requests from cat monitoring devices.

    Args:
        request: HTTP request dict containing:
            - body: JSON payload with cat_id, device_id, sensor_data

    Returns:
        dict: Response with status and action taken

    Example request body:
        {
            "cat_id": "123",
            "device_id": "collar_456",
            "sensor_data": {
                "temperature": 38.5,
                "motion": "active",
                "weight": 4.2
            }
        }
    """
    try:
        # Parse request body
        body = request.get('body', {})
        if isinstance(body, str):
            body = json.loads(body)

        cat_id = body.get('cat_id')
        device_id = body.get('device_id')
        sensor_data = body.get('sensor_data', {})

        if not cat_id or not device_id:
            return {
                'status': 'error',
                'message': 'Missing cat_id or device_id',
                'code': 400
            }

        logger.info(f"Processing IoT webhook for cat_id={cat_id}, device_id={device_id}")

        # Initialize SystemContext
        async with SystemContext(cat_id=cat_id) as ctx:
            # Populate shared store
            shared = {
                'request': {
                    'cat_id': cat_id,
                    'device_id': device_id,
                    'sensor_data': sensor_data
                },
                'cat_id': cat_id,
                'context': ctx
            }

            # Execute master flow
            master_flow = create_master_flow()
            await master_flow.run_async(shared)

            # Extract action taken from shared store
            action_taken = shared.get('action', 'processed')

            return {
                'status': 'success',
                'action_taken': action_taken,
                'cat_id': cat_id,
                'code': 200
            }

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {
            'status': 'error',
            'message': 'Invalid JSON in request body',
            'code': 400
        }
    except Exception as e:
        logger.exception(f"Error processing IoT webhook: {e}")
        return {
            'status': 'error',
            'message': 'Internal server error',
            'code': 500
        }


async def handle_chat(request: dict) -> dict:
    """
    Handle chat requests from users about cat health.

    Args:
        request: HTTP request dict containing:
            - body: JSON payload with user_id, cat_id, user_input, optional session_id

    Returns:
        dict: Response with answer

    Example request body:
        {
            "user_id": "u_42",
            "cat_id": "123",
            "user_input": "How is my cat's health today?",
            "session_id": "session-abc"
        }
    """
    try:
        # Parse request body
        body = request.get('body', {})
        if isinstance(body, str):
            body = json.loads(body)

        cat_id = str(body.get('cat_id')) if body.get('cat_id') is not None else None
        user_input = body.get('user_input')
        user_id = body.get('user_id')
        session_id = body.get('session_id')

        if not cat_id or not user_input or not user_id:
            return {
                'status': 'error',
                'message': 'Missing cat_id, user_id or user_input',
                'code': 400
            }

        logger.info(f"Processing chat request for cat_id={cat_id}, user_id={user_id}")

        def _select_answer(shared_store: dict):
            candidates = [
                shared_store.get('answer'),
                shared_store.get('status_summary'),
                shared_store.get('health_summary'),
                shared_store.get('daily_analysis'),
                shared_store.get('weekly_report'),
                shared_store.get('monthly_report'),
                shared_store.get('trend_analysis'),
                shared_store.get('health_prediction'),
                shared_store.get('behavior_pattern'),
                shared_store.get('vet_recommendation'),
                shared_store.get('multi_cat_report')
            ]

            for value in candidates:
                if value:
                    if isinstance(value, str):
                        return value
                    if isinstance(value, dict):
                        if 'report_content' in value:
                            return value.get('report_content')
                        return json.dumps(value, ensure_ascii=False)
                    return str(value)

            return 'Unable to process request'

        # Support multi-cat query mode
        if cat_id == 'all':
            shared = {
                'request': {
                    'cat_id': cat_id,
                    'user_input': user_input,
                    'user_id': user_id,
                    'session_id': session_id
                },
                'question': user_input,
                'user_id': user_id,
                'session_id': session_id
            }

            flow = create_multi_cat_flow()
            await flow.run_async(shared)

            answer = _select_answer(shared)

            return {
                'status': 'success',
                'answer': answer,
                'cat_id': cat_id,
                'statistics': shared.get('multi_cat_stats'),
                'code': 200
            }

        # Initialize SystemContext
        async with SystemContext(cat_id=cat_id) as ctx:
            # Populate shared store
            shared = {
                'request': {
                    'cat_id': cat_id,
                    'user_input': user_input,
                    'user_id': user_id,
                    'session_id': session_id
                },
                'cat_id': cat_id,
                'question': user_input,
                'user_id': user_id,
                'session_id': session_id,
                'context': ctx
            }

            # Execute master flow
            master_flow = create_master_flow()
            await master_flow.run_async(shared)

            # Extract answer from shared store
            answer = _select_answer(shared)

            return {
                'status': 'success',
                'answer': answer,
                'cat_id': cat_id,
                'user_id': user_id,
                'session_id': shared.get('session_id') or session_id,
                'code': 200
            }

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {
            'status': 'error',
            'message': 'Invalid JSON in request body',
            'code': 400
        }
    except Exception as e:
        logger.exception(f"Error processing chat request: {e}")
        return {
            'status': 'error',
            'message': 'Internal server error',
            'code': 500
        }


async def handle_analyze(request: dict) -> dict:
    """
    Handle analysis requests for various report types.

    Args:
        request: HTTP request dict containing body with user_id, analysis_type, optional cat_id

    Returns:
        dict: Response with unified analysis payload
    """
    analysis_type = ''

    def extract_analysis_data(shared_store: dict, analysis_type_value: str):
        if analysis_type_value == 'daily_summary':
            return shared_store.get('daily_analysis') or shared_store.get('health_summary') or {}
        elif analysis_type_value == 'weekly_report':
            return shared_store.get('weekly_report', {})
        elif analysis_type_value == 'monthly_report':
            data = {}
            if 'monthly_report' in shared_store:
                data['report'] = shared_store.get('monthly_report')
            if 'health_summary' in shared_store:
                data['health_summary'] = shared_store.get('health_summary')
            return data or {}
        elif analysis_type_value == 'trend_analysis':
            data = {}
            if 'trend_analysis' in shared_store:
                data['trend_analysis'] = shared_store.get('trend_analysis')
            if 'health_summary' in shared_store:
                data['health_summary'] = shared_store.get('health_summary')
            if 'status_summary' in shared_store:
                data['status_summary'] = shared_store.get('status_summary')
            if 'daily_analysis' in shared_store:
                data['daily_analysis'] = shared_store.get('daily_analysis')
            return data or {}
        elif analysis_type_value == 'comparison':
            data = {}
            if 'health_summary' in shared_store:
                data['health_summary'] = shared_store.get('health_summary')
            if 'daily_analysis' in shared_store:
                data['daily_analysis'] = shared_store.get('daily_analysis')
            return data or {}
        elif analysis_type_value == 'multi_cat_comparison':
            data = {}
            if shared_store.get('multi_cat_report') is not None:
                data['report'] = shared_store.get('multi_cat_report')
            if shared_store.get('multi_cat_stats') is not None:
                data['statistics'] = shared_store.get('multi_cat_stats')
            return data or {}
        elif analysis_type_value == 'health_prediction':
            return shared_store.get('health_prediction') or shared_store.get('health_summary') or {}
        elif analysis_type_value == 'behavior_pattern':
            data = {}
            if 'behavior_pattern' in shared_store:
                data['behavior_pattern'] = shared_store.get('behavior_pattern')
            if 'status_summary' in shared_store:
                data['status_summary'] = shared_store.get('status_summary')
            if 'daily_analysis' in shared_store:
                data['daily_analysis'] = shared_store.get('daily_analysis')
            return data or {}
        elif analysis_type_value == 'vet_recommendation':
            return shared_store.get('vet_recommendation') or shared_store.get('health_summary') or {}
        elif analysis_type_value == 'anomaly_detection':
            data = {}
            if 'daily_analysis' in shared_store:
                data['daily_analysis'] = shared_store.get('daily_analysis')
            if 'health_summary' in shared_store:
                data['health_summary'] = shared_store.get('health_summary')
            return data or {}
        return {}

    try:
        body = request.get('body', {}) or {}
        if isinstance(body, str):
            body = json.loads(body)

        user_id = body.get('user_id')
        cat_id = str(body.get('cat_id', '1'))
        analysis_type = body.get('analysis_type', '')

        valid_types = [
            'daily_summary',
            'weekly_report',
            'monthly_report',
            'trend_analysis',
            'comparison',
            'multi_cat_comparison',
            'health_prediction',
            'behavior_pattern',
            'vet_recommendation',
            'anomaly_detection'
        ]

        if not user_id:
            return {
                'success': False,
                'analysis_type': analysis_type,
                'data': {'error': 'Missing user_id'},
                'timestamp': datetime.now().isoformat(),
                'code': 400
            }

        if not analysis_type:
            return {
                'success': False,
                'analysis_type': analysis_type,
                'data': {'error': 'Missing analysis_type'},
                'timestamp': datetime.now().isoformat(),
                'code': 400
            }

        if analysis_type not in valid_types:
            return {
                'success': False,
                'analysis_type': analysis_type,
                'data': {'error': f'Invalid analysis_type. Must be one of {valid_types}'},
                'timestamp': datetime.now().isoformat(),
                'code': 400
            }

        logger.info(f"Processing analysis request: user_id={user_id}, cat_id={cat_id}, analysis_type={analysis_type}")

        shared = {
            'request': {
                'user_id': user_id,
                'cat_id': cat_id,
                'analysis_type': analysis_type
            },
            'cat_id': cat_id,
            'user_id': user_id,
            'analysis_type': analysis_type
        }

        analysis_flow = create_analyze_flow(analysis_type)
        await analysis_flow.run_async(shared)

        data = extract_analysis_data(shared, analysis_type)

        return {
            'success': True,
            'analysis_type': analysis_type,
            'data': data,
            'timestamp': datetime.now().isoformat(),
            'code': 200
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in analysis: {e}")
        return {
            'success': False,
            'analysis_type': analysis_type,
            'data': {'error': 'Invalid JSON in request body'},
            'timestamp': datetime.now().isoformat(),
            'code': 400
        }
    except ValueError as e:
        logger.error(f"Invalid analysis configuration: {e}")
        return {
            'success': False,
            'analysis_type': analysis_type,
            'data': {'error': str(e)},
            'timestamp': datetime.now().isoformat(),
            'code': 400
        }
    except Exception as e:
        logger.exception(f"Error processing analysis request: {e}")
        return {
            'success': False,
            'analysis_type': analysis_type,
            'data': {'error': 'Internal server error'},
            'timestamp': datetime.now().isoformat(),
            'code': 500
        }


async def handle_collar_webhook(request: dict) -> dict:
    """
    Handle POST /webhook/collar - Collar device data ingestion.

    Args:
        request: HTTP request dict containing:
            - body: JSON payload with device_serial, cat_id, data_type, payload

    Returns:
        dict: Response with processing status

    Supported data_type values:
        - activity_data: Steps, calories, active minutes
        - outdoor_status: GPS location, indoor/outdoor tracking
        - bcg_heart_rate: Heart rate, HRV, respiratory rate
    """
    try:
        body = request.get('body', {})
        if isinstance(body, str):
            body = json.loads(body)

        # Validate required fields
        device_serial = body.get('device_serial')
        cat_id = body.get('cat_id')
        data_type = body.get('data_type')
        payload = body.get('payload', {})

        if not device_serial or not cat_id or not data_type:
            return {
                'status': 'error',
                'message': 'Missing required fields: device_serial, cat_id, data_type',
                'code': 400
            }

        # Validate data_type
        valid_data_types = ['activity_data', 'outdoor_status', 'bcg_heart_rate']
        if data_type not in valid_data_types:
            return {
                'status': 'error',
                'message': f'Invalid data_type. Must be one of: {valid_data_types}',
                'code': 400
            }

        logger.info(f"Processing collar webhook: cat_id={cat_id}, data_type={data_type}")

        # Build shared context for collar flow
        shared = {
            'request': {
                'cat_id': cat_id,
                'webhook_type': 'collar'
            },
            'collar_data': {
                'collar_device_id': device_serial,
                'cat_id': cat_id,
                'data_type': data_type,
                'payload': payload
            },
            'cat_id': cat_id
        }

        # Execute collar flow
        collar_flow = create_collar_flow()
        await collar_flow.run_async(shared)

        # Extract result
        result = shared.get('collar_ingestion_result', {})

        return {
            'status': 'success',
            'data_type': data_type,
            'cat_id': cat_id,
            'result': result,
            'code': 200
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {
            'status': 'error',
            'message': 'Invalid JSON in request body',
            'code': 400
        }
    except Exception as e:
        logger.exception(f"Error processing collar webhook: {e}")
        return {
            'status': 'error',
            'message': 'Internal server error',
            'code': 500
        }


async def handle_cat_door_webhook(request: dict) -> dict:
    """
    Handle POST /webhook/cat-door - Cat door event processing.

    Args:
        request: HTTP request dict containing:
            - body: JSON payload with device_serial, cat_id, event_type, direction, image_url (optional)

    Returns:
        dict: Response with processing status

    Supported event_type values:
        - passage: Cat entering/exiting through the door
        - identification: Cat identification event
    """
    try:
        body = request.get('body', {})
        if isinstance(body, str):
            body = json.loads(body)

        # Validate required fields
        device_serial = body.get('device_serial')
        cat_id = body.get('cat_id')
        event_type = body.get('event_type')
        direction = body.get('direction')
        identification_method = body.get('identification_method', 'rfid')
        identification_confidence = body.get('identification_confidence', 0.95)
        image_url = body.get('image_url')

        if not device_serial or not cat_id or not event_type:
            return {
                'status': 'error',
                'message': 'Missing required fields: device_serial, cat_id, event_type',
                'code': 400
            }

        # Validate event_type
        valid_event_types = ['passage', 'identification']
        if event_type not in valid_event_types:
            return {
                'status': 'error',
                'message': f'Invalid event_type. Must be one of: {valid_event_types}',
                'code': 400
            }

        # Validate direction for passage events
        if event_type == 'passage' and direction not in ['in', 'out']:
            return {
                'status': 'error',
                'message': 'Invalid direction. Must be "in" or "out" for passage events',
                'code': 400
            }

        logger.info(f"Processing cat door webhook: cat_id={cat_id}, event_type={event_type}")

        # Build shared context for cat door flow
        shared = {
            'request': {
                'cat_id': cat_id,
                'webhook_type': 'cat_door',
                'image': image_url,
                'image_source': 'cat_door' if image_url else None
            },
            'cat_door_event': {
                'cat_door_device_id': device_serial,
                'cat_id': cat_id,
                'direction': direction or 'in',
                'identification_method': identification_method,
                'identification_confidence': identification_confidence,
                'image_url': image_url,
                'timestamp': datetime.now().isoformat()
            },
            'cat_id': cat_id
        }

        # Execute cat door flow
        cat_door_flow = create_cat_door_flow()
        await cat_door_flow.run_async(shared)

        # Extract result
        passage_log = shared.get('cat_door_passage_log', {})
        vision_analysis = shared.get('vision_analysis', {})

        return {
            'status': 'success',
            'event_type': event_type,
            'cat_id': cat_id,
            'passage_log': passage_log,
            'vision_analysis': vision_analysis if image_url else None,
            'code': 200
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {
            'status': 'error',
            'message': 'Invalid JSON in request body',
            'code': 400
        }
    except Exception as e:
        logger.exception(f"Error processing cat door webhook: {e}")
        return {
            'status': 'error',
            'message': 'Internal server error',
            'code': 500
        }


async def handle_request(request: dict) -> dict:
    """
    Route incoming HTTP requests to appropriate handlers.

    Args:
        request: HTTP request dict containing:
            - method: HTTP method (GET, POST, etc.)
            - path: Request path
            - body: Request body
            - headers: Request headers (optional)
            - websocket: WebSocket connection object (for WebSocket upgrades)

    Returns:
        dict: HTTP response with status code

    Routes:
        - POST /webhook/iot -> handle_iot_webhook() (legacy IoT webhook)
        - POST /chat -> handle_chat() (user chat interface)
        - POST /analyze -> handle_analyze() (analysis router)
        - POST /webhook/collar -> handle_collar_webhook() (collar device data)
        - POST /webhook/cat-door -> handle_cat_door_webhook() (cat door events)
        - WebSocket /ws/iot/* -> handle_connection() (WebSocket upgrade)
        - Otherwise: 404 Not Found
    """
    try:
        method = request.get('method', 'GET')
        path = request.get('path', '/')
        headers = request.get('headers', {})

        logger.info(f"Routing request: {method} {path}")

        # Check for WebSocket upgrade
        if headers.get('Upgrade', '').lower() == 'websocket' and path.startswith('/ws/iot'):
            logger.info(f"Upgrading to WebSocket connection: {path}")
            websocket = request.get('websocket')
            if websocket:
                await handle_connection(websocket, path)
                return {
                    'status': 'websocket_upgraded',
                    'message': 'WebSocket connection established',
                    'code': 101
                }
            else:
                return {
                    'status': 'error',
                    'message': 'WebSocket upgrade failed - no websocket object provided',
                    'code': 400
                }

        # Route based on path
        if method == 'POST' and path == '/webhook/iot':
            return await handle_iot_webhook(request)
        elif method == 'POST' and path == '/chat':
            return await handle_chat(request)
        elif method == 'POST' and path == '/analyze':
            return await handle_analyze(request)
        # Device webhook endpoints
        elif method == 'POST' and path == '/webhook/collar':
            return await handle_collar_webhook(request)
        elif method == 'POST' and path == '/webhook/cat-door':
            return await handle_cat_door_webhook(request)
        else:
            return {
                'status': 'error',
                'message': 'Not found',
                'code': 404
            }

    except Exception as e:
        logger.exception(f"Error routing request: {e}")
        return {
            'status': 'error',
            'message': 'Internal server error',
            'code': 500
        }


def main():
    """
    Main entry point for local testing.

    Simulates a sample chat request and prints the response.
    """
    # Sample chat request
    sample_request = {
        'method': 'POST',
        'path': '/chat',
        'body': {
            'cat_id': '1',
            'user_input': 'How is my cat doing today?'
        }
    }

    print("=== Testing Cloudflare Workers Entry Point ===")
    print(f"Request: {json.dumps(sample_request, indent=2)}")
    print("\n--- Processing ---\n")

    # Execute async handler
    response = asyncio.run(handle_request(sample_request))

    print("\n--- Response ---")
    print(json.dumps(response, indent=2))


if __name__ == '__main__':
    main()
