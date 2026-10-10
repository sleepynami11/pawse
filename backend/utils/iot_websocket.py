"""
WebSocket Handler for Real-time IoT Data Streaming

This module provides WebSocket server functionality for real-time bi-directional
communication with IoT cat monitoring devices.

Features:
- Connection pool management for multiple devices
- Real-time sensor data ingestion
- Anomaly detection with configurable thresholds
- Message acknowledgment and error handling
- Broadcast messaging to specific cats

Usage Example:
    # Start WebSocket server endpoint
    from utils.iot_websocket import handle_connection

    # In your WebSocket server:
    async def websocket_handler(websocket, path):
        await handle_connection(websocket, path)
"""

import asyncio
import json
import logging
from typing import Dict, Optional
from datetime import datetime

# Import D1 client for database operations
from utils.d1_client import execute_query

logger = logging.getLogger(__name__)

# Connection pool: cat_id -> list of websocket connections
active_connections: Dict[str, list] = {}

# Anomaly detection thresholds
ANOMALY_THRESHOLDS = {
    'temperature': {'min': 37.5, 'max': 39.5},  # Normal cat body temp range (Celsius)
    'heart_rate': {'min': 120, 'max': 220},      # Normal cat heart rate (bpm)
    'activity': {'min': 0, 'max': 100}           # Activity level percentage
}

# Valid sensor types
VALID_SENSOR_TYPES = ['temperature', 'heart_rate', 'activity', 'motion', 'weight', 'proximity']


def check_anomaly(sensor_type: str, value: float) -> bool:
    """
    Check if sensor value is anomalous based on predefined thresholds.

    Args:
        sensor_type: Type of sensor (e.g., 'temperature', 'heart_rate')
        value: Sensor reading value

    Returns:
        bool: True if anomaly detected, False otherwise
    """
    if sensor_type not in ANOMALY_THRESHOLDS:
        return False

    thresholds = ANOMALY_THRESHOLDS[sensor_type]
    return value < thresholds['min'] or value > thresholds['max']


async def handle_connection(websocket, path: str):
    """
    Handle WebSocket connection for IoT device.

    This function manages the entire lifecycle of a WebSocket connection:
    1. Parse connection path to extract cat_id and device_id
    2. Add connection to active pool
    3. Listen for incoming sensor data messages
    4. Validate and store data in D1 database
    5. Send acknowledgments back to device
    6. Clean up on disconnect

    Args:
        websocket: WebSocket connection object
        path: Connection path (format: /ws/iot/{cat_id}/{device_id})

    Message Format (incoming):
        {
            "type": "sensor_data",
            "sensor_type": "temperature",
            "value": 38.5,
            "timestamp": "2025-12-08T10:30:00Z"
        }

    Acknowledgment Format (outgoing):
        {
            "type": "ack",
            "message": "Data received",
            "anomaly_detected": false
        }
    """
    cat_id = None
    device_id = None

    try:
        # Parse path to extract cat_id and device_id
        # Expected format: /ws/iot/{cat_id}/{device_id}
        path_parts = path.strip('/').split('/')
        if len(path_parts) >= 3 and path_parts[0] == 'ws' and path_parts[1] == 'iot':
            cat_id = path_parts[2]
            device_id = path_parts[3] if len(path_parts) > 3 else 'unknown'
        else:
            logger.error(f"Invalid WebSocket path format: {path}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid path format. Expected: /ws/iot/{cat_id}/{device_id}"
            }))
            return

        logger.info(f"WebSocket connection established: cat_id={cat_id}, device_id={device_id}")

        # Add to connection pool
        if cat_id not in active_connections:
            active_connections[cat_id] = []
        active_connections[cat_id].append(websocket)

        # Send connection confirmation
        await websocket.send(json.dumps({
            "type": "connected",
            "message": f"Connected to cat {cat_id}",
            "cat_id": cat_id,
            "device_id": device_id
        }))

        # Message loop - listen for incoming messages
        async for message in websocket:
            try:
                # Parse incoming message
                data = json.loads(message)
                msg_type = data.get('type')

                if msg_type == 'sensor_data':
                    # Extract sensor data
                    sensor_type = data.get('sensor_type')
                    value = data.get('value')
                    timestamp = data.get('timestamp', datetime.utcnow().isoformat())

                    # Validate sensor type
                    if sensor_type not in VALID_SENSOR_TYPES:
                        logger.warning(f"Invalid sensor type: {sensor_type}")
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": f"Invalid sensor type. Valid types: {', '.join(VALID_SENSOR_TYPES)}"
                        }))
                        continue

                    # Validate value
                    if value is None or not isinstance(value, (int, float)):
                        logger.warning(f"Invalid sensor value: {value}")
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": "Invalid sensor value. Must be a number."
                        }))
                        continue

                    # Check for anomaly
                    anomaly_flag = 1 if check_anomaly(sensor_type, value) else 0

                    logger.info(f"Received sensor data: cat_id={cat_id}, sensor={sensor_type}, value={value}, anomaly={anomaly_flag}")

                    # Store in D1 database
                    try:
                        await execute_query(
                            """
                            INSERT INTO iot_logs (cat_id, device_id, sensor_type, value, timestamp, anomaly_flag)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            [int(cat_id), device_id, sensor_type, float(value), timestamp, anomaly_flag]
                        )

                        # Send acknowledgment
                        await websocket.send(json.dumps({
                            "type": "ack",
                            "message": "Data received and stored",
                            "anomaly_detected": bool(anomaly_flag),
                            "timestamp": timestamp
                        }))

                        # Log anomaly if detected
                        if anomaly_flag:
                            logger.warning(f"ANOMALY DETECTED: cat_id={cat_id}, sensor={sensor_type}, value={value}")

                    except Exception as db_error:
                        logger.error(f"Database error: {db_error}")
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": "Failed to store data in database"
                        }))

                elif msg_type == 'heartbeat':
                    # Respond to heartbeat ping
                    await websocket.send(json.dumps({
                        "type": "heartbeat_ack",
                        "timestamp": datetime.utcnow().isoformat()
                    }))

                else:
                    logger.warning(f"Unknown message type: {msg_type}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}"
                    }))

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Failed to process message"
                }))

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")

    finally:
        # Clean up on disconnect
        if cat_id and cat_id in active_connections:
            try:
                active_connections[cat_id].remove(websocket)
                if not active_connections[cat_id]:
                    del active_connections[cat_id]
                logger.info(f"WebSocket connection closed: cat_id={cat_id}, device_id={device_id}")
            except ValueError:
                pass


async def send_message(cat_id: str, message: dict) -> bool:
    """
    Send a message to a specific cat's first active connection.

    Args:
        cat_id: Cat identifier
        message: Message dictionary to send (will be JSON serialized)

    Returns:
        bool: True if message sent successfully, False otherwise

    Example:
        success = await send_message("123", {
            "type": "alert",
            "message": "Anomaly detected in heart rate"
        })
    """
    if cat_id not in active_connections or not active_connections[cat_id]:
        logger.warning(f"No active connections for cat_id={cat_id}")
        return False

    try:
        websocket = active_connections[cat_id][0]
        await websocket.send(json.dumps(message))
        logger.info(f"Message sent to cat_id={cat_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send message to cat_id={cat_id}: {e}")
        return False


async def broadcast_to_cat(cat_id: str, message: dict) -> int:
    """
    Broadcast a message to all active connections for a specific cat.

    Args:
        cat_id: Cat identifier
        message: Message dictionary to broadcast (will be JSON serialized)

    Returns:
        int: Number of successful sends

    Example:
        count = await broadcast_to_cat("123", {
            "type": "notification",
            "message": "System maintenance scheduled"
        })
    """
    if cat_id not in active_connections or not active_connections[cat_id]:
        logger.warning(f"No active connections for cat_id={cat_id}")
        return 0

    success_count = 0
    message_json = json.dumps(message)

    for websocket in active_connections[cat_id]:
        try:
            await websocket.send(message_json)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send message to one connection: {e}")

    logger.info(f"Broadcast to cat_id={cat_id}: {success_count}/{len(active_connections[cat_id])} successful")
    return success_count


if __name__ == "__main__":
    # Test module
    print("IoT WebSocket Handler Module")
    print(f"Valid sensor types: {', '.join(VALID_SENSOR_TYPES)}")
    print(f"Anomaly thresholds: {json.dumps(ANOMALY_THRESHOLDS, indent=2)}")

    # Test anomaly detection
    test_cases = [
        ('temperature', 38.0, False),
        ('temperature', 40.0, True),
        ('heart_rate', 150, False),
        ('heart_rate', 250, True),
    ]

    print("\nAnomaly Detection Tests:")
    for sensor_type, value, expected in test_cases:
        result = check_anomaly(sensor_type, value)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] {sensor_type}={value} -> anomaly={result} (expected={expected})")
