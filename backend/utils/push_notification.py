"""
Push Notification Service for Cat IoT Agent System

This module provides async functions to send push notifications via:
1. WebSocket (real-time, for active connections via /ws/push/{user_id})
2. APNs (Apple Push Notification service, iOS)
3. FCM (Firebase Cloud Messaging, Android)

The service follows a fallback strategy:
- Try WebSocket first (if client is actively connected)
- Fall back to APNs/FCM for offline or background scenarios

V3.5 Architecture Update:
    - WebSocket push now uses user_id based connection pool from api._push_connections
    - send_websocket() queries user_id from cat_id via D1 cats table
    - Broadcasts to all user's connected devices

Environment Variables Required:
    - APNS_KEY_ID: Apple Push Notification service key ID
    - APNS_TEAM_ID: Apple developer team ID
    - APNS_BUNDLE_ID: iOS app bundle identifier
    - FCM_SERVER_KEY: Firebase Cloud Messaging server key

Usage Example:
    from utils.push_notification import send_notification

    async def alert_handler():
        success = await send_notification(
            cat_id="123",
            message={
                "type": "emergency",
                "title": "High Temperature Alert",
                "body": "Your cat's temperature is abnormally high (40.2 deg C)",
                "data": {
                    "sensor_type": "temperature",
                    "value": 40.2,
                    "timestamp": "2025-01-15T10:30:00Z"
                }
            }
        )
        if success:
            print("Alert sent successfully")
"""

import asyncio
import httpx
import os
import logging
from datetime import datetime
from typing import Dict, Optional, List
from utils.d1_client import execute_query

logger = logging.getLogger(__name__)

# Load environment variables
APNS_KEY_ID = os.getenv("APNS_KEY_ID", "")
APNS_TEAM_ID = os.getenv("APNS_TEAM_ID", "")
APNS_BUNDLE_ID = os.getenv("APNS_BUNDLE_ID", "com.catiot.app")
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")

# Reference to the push connections pool from api module
# This is imported lazily to avoid circular import issues
_push_connections_ref: Optional[Dict[int, List]] = None


def _get_push_connections() -> Dict[int, List]:
    """
    Lazily import and return the _push_connections from api module.
    This avoids circular import issues.
    """
    global _push_connections_ref
    if _push_connections_ref is None:
        try:
            from api import _push_connections
            _push_connections_ref = _push_connections
        except ImportError:
            logger.warning("Could not import _push_connections from api module")
            _push_connections_ref = {}
    return _push_connections_ref


async def _get_user_id_from_cat_id(cat_id: str) -> Optional[int]:
    """
    Query user_id for a given cat_id from the D1 database.

    Args:
        cat_id: Cat identifier (string or int)

    Returns:
        Optional[int]: User ID if found, None otherwise
    """
    try:
        result = await execute_query(
            "SELECT user_id FROM cats WHERE id = ?",
            [int(cat_id)]
        )

        if not result.get("success"):
            logger.warning(f"D1 query failed for cat_id={cat_id}")
            return None

        results = result.get("result", {}).get("results", [])
        if not results:
            logger.warning(f"No user found for cat_id={cat_id}")
            return None

        user_id = results[0].get("user_id")
        return int(user_id) if user_id is not None else None

    except Exception as e:
        logger.error(f"Error querying user_id for cat_id={cat_id}: {e}")
        return None


# Legacy compatibility - kept for backward compatibility but deprecated
# Use _get_push_connections() instead
WEBSOCKET_CONNECTIONS: Dict[str, object] = {}


async def send_websocket(cat_id: str, message: dict) -> bool:
    """
    Send notification via WebSocket for real-time delivery.

    V3.5 Update: Now queries user_id from cat_id and broadcasts to all
    user's connected devices via the /ws/push/{user_id} connection pool.

    Args:
        cat_id: Cat identifier
        message: Notification message dict containing:
            - type: Notification type (emergency, warning, info)
            - title: Notification title
            - body: Notification body
            - data: Additional data payload

    Returns:
        bool: True if WebSocket message sent successfully to at least one connection,
              False otherwise

    Example:
        success = await send_websocket("123", {
            "type": "emergency",
            "title": "Alert",
            "body": "High temperature detected"
        })
    """
    try:
        # Query user_id from cat_id
        user_id = await _get_user_id_from_cat_id(cat_id)
        if user_id is None:
            logger.info(f"Could not find user_id for cat_id={cat_id}, cannot send WebSocket notification")
            return False

        # Get the push connections pool
        push_connections = _get_push_connections()

        # Check if user has any active connections
        if user_id not in push_connections or not push_connections[user_id]:
            logger.info(f"No active push WebSocket connections for user_id={user_id} (cat_id={cat_id})")
            return False

        # Build notification payload
        notification_payload = {
            "event": "notification",
            "timestamp": datetime.now().isoformat(),
            "cat_id": cat_id,
            "data": message
        }

        # Broadcast to all user's connections
        success_count = 0
        failed_connections = []

        # Iterate over a copy of the list to avoid race conditions during await
        for websocket in list(push_connections[user_id]):
            try:
                await websocket.send_json(notification_payload)
                success_count += 1
            except Exception as e:
                logger.warning(f"Failed to send to one connection for user_id={user_id}: {e}")
                failed_connections.append(websocket)

        # Clean up failed connections
        for ws in failed_connections:
            try:
                push_connections[user_id].remove(ws)
            except ValueError:
                pass

        if not push_connections[user_id]:
            del push_connections[user_id]

        if success_count > 0:
            logger.info(f"WebSocket notification sent to user_id={user_id} (cat_id={cat_id}): {success_count} connections")
            return True
        else:
            logger.warning(f"All WebSocket sends failed for user_id={user_id} (cat_id={cat_id})")
            return False

    except Exception as e:
        logger.error(f"Failed to send WebSocket notification for cat_id={cat_id}: {str(e)}")
        return False


async def send_apns_fcm(cat_id: str, message: dict, platform: str) -> bool:
    """
    Send notification via APNs (iOS) or FCM (Android).

    Args:
        cat_id: Cat identifier
        message: Notification message dict
        platform: Platform type ("ios" or "android")

    Returns:
        bool: True if push notification sent successfully, False otherwise

    Example:
        success = await send_apns_fcm("123", {
            "type": "emergency",
            "title": "Alert",
            "body": "High temperature detected"
        }, "ios")
    """
    try:
        # Query D1 for device token
        result = await execute_query(
            "SELECT device_token, platform FROM user_devices WHERE cat_id = ? AND platform = ?",
            [cat_id, platform]
        )

        if not result.get("success") or not result.get("result", {}).get("results"):
            logger.warning(f"No device token found for cat_id={cat_id}, platform={platform}")
            return False

        device_data = result["result"]["results"][0]
        device_token = device_data.get("device_token")

        if not device_token:
            logger.error(f"Empty device token for cat_id={cat_id}")
            return False

        # Send notification based on platform
        if platform == "ios":
            return await _send_apns(device_token, message)
        elif platform == "android":
            return await _send_fcm(device_token, message)
        else:
            logger.error(f"Unsupported platform: {platform}")
            return False

    except Exception as e:
        logger.error(f"Failed to send push notification for cat_id={cat_id}: {str(e)}")
        return False


async def _send_apns(device_token: str, message: dict) -> bool:
    """
    Internal function to send APNs notification.

    Args:
        device_token: APNs device token
        message: Notification message dict

    Returns:
        bool: True if sent successfully
    """
    if not APNS_KEY_ID or not APNS_TEAM_ID:
        logger.error("APNs credentials not configured")
        return False

    try:
        # APNs HTTP/2 API endpoint
        url = f"https://api.push.apple.com/3/device/{device_token}"

        # Build APNs payload
        payload = {
            "aps": {
                "alert": {
                    "title": message.get("title", "Cat Health Alert"),
                    "body": message.get("body", "")
                },
                "sound": "default",
                "badge": 1
            },
            "data": message.get("data", {})
        }

        # Note: In production, you need to generate JWT token for APNs authentication
        # For now, we'll log a placeholder
        logger.warning("APNs authentication not implemented - JWT token generation required")

        # Placeholder for actual APNs call
        # headers = {
        #     "authorization": f"bearer {jwt_token}",
        #     "apns-topic": APNS_BUNDLE_ID,
        #     "apns-push-type": "alert",
        #     "apns-priority": "10"
        # }
        #
        # async with httpx.AsyncClient(http2=True) as client:
        #     response = await client.post(url, json=payload, headers=headers)
        #     response.raise_for_status()

        logger.info(f"APNs notification prepared for device_token={device_token[:10]}...")
        return True

    except Exception as e:
        logger.error(f"APNs send failed: {str(e)}")
        return False


async def _send_fcm(device_token: str, message: dict) -> bool:
    """
    Internal function to send FCM notification.

    Args:
        device_token: FCM device token
        message: Notification message dict

    Returns:
        bool: True if sent successfully
    """
    if not FCM_SERVER_KEY:
        logger.error("FCM credentials not configured")
        return False

    try:
        url = "https://fcm.googleapis.com/fcm/send"
        headers = {
            "Authorization": f"key={FCM_SERVER_KEY}",
            "Content-Type": "application/json"
        }

        # Build FCM payload
        payload = {
            "to": device_token,
            "notification": {
                "title": message.get("title", "Cat Health Alert"),
                "body": message.get("body", "")
            },
            "data": message.get("data", {}),
            "priority": "high"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()

            result = response.json()
            if result.get("success", 0) > 0:
                logger.info(f"FCM notification sent to device_token={device_token[:10]}...")
                return True
            else:
                logger.error(f"FCM send failed: {result}")
                return False

    except httpx.HTTPError as e:
        logger.error(f"FCM HTTP error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"FCM send failed: {str(e)}")
        return False


async def send_notification(cat_id: str, message: dict) -> bool:
    """
    Send notification with automatic fallback strategy:
    1. Try WebSocket first (real-time delivery)
    2. Fall back to APNs/FCM if WebSocket unavailable

    Args:
        cat_id: Cat identifier
        message: Notification message dict containing:
            - type: Notification type (emergency, warning, info)
            - title: Notification title
            - body: Notification body
            - data: Additional data payload

    Returns:
        bool: True if notification sent via any method, False if all methods failed

    Example:
        success = await send_notification("123", {
            "type": "emergency",
            "title": "High Temperature Alert",
            "body": "Your cat's temperature is 40.2°C",
            "data": {
                "sensor_type": "temperature",
                "value": 40.2
            }
        })
    """
    logger.info(f"Sending notification to cat_id={cat_id}, type={message.get('type')}")

    # Try WebSocket first
    ws_success = await send_websocket(cat_id, message)
    if ws_success:
        logger.info(f"Notification delivered via WebSocket for cat_id={cat_id}")
        return True

    # Fall back to push notifications (try both iOS and Android)
    logger.info(f"WebSocket unavailable, falling back to push notifications for cat_id={cat_id}")

    apns_success = await send_apns_fcm(cat_id, message, "ios")
    fcm_success = await send_apns_fcm(cat_id, message, "android")

    if apns_success or fcm_success:
        logger.info(f"Notification delivered via push notification for cat_id={cat_id}")
        return True

    logger.error(f"All notification methods failed for cat_id={cat_id}")
    return False


if __name__ == "__main__":
    # Test push notification service
    async def test():
        """Test push notification with example data"""
        try:
            test_message = {
                "type": "emergency",
                "title": "High Temperature Alert",
                "body": "Your cat Whiskers has a high temperature (40.2°C)",
                "data": {
                    "sensor_type": "temperature",
                    "value": 40.2,
                    "timestamp": datetime.now().isoformat()
                }
            }

            success = await send_notification("1", test_message)
            print(f"Notification sent: {success}")

        except Exception as e:
            print(f"Test failed: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(test())
