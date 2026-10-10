"""
Device Service Async Client

This module provides async functions to interact with the device-service HTTP API
for querying TimescaleDB time-series data.

The device-service exposes REST API endpoints for retrieving sensor data collected
from IoT devices (collar, cat door). This client wraps those endpoints with proper
error handling, timeout support, and consistent response parsing.

Environment Variables:
    - DEVICE_SERVICE_URL: The base URL of device-service (default: http://device-service:8080)

Usage Example:
    import asyncio
    from utils.device_service_client import get_bcg_data, get_gps_data

    async def main():
        # Get BCG data for a device
        bcg_records = await get_bcg_data(
            mac="AABBCCDDEEFF",
            limit=100
        )

        # Get GPS data with time range
        from datetime import datetime, timedelta
        end = datetime.utcnow()
        start = end - timedelta(days=7)
        gps_records = await get_gps_data(
            mac="AABBCCDDEEFF",
            start=start,
            end=end,
            limit=50
        )

    asyncio.run(main())
"""

import httpx
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Device service base URL (Docker internal network)
DEVICE_SERVICE_URL = os.getenv("DEVICE_SERVICE_URL", "http://device-service:8080")

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 30.0


def _format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """
    Format datetime to ISO 8601 string for API queries.

    Args:
        dt: datetime object or None

    Returns:
        ISO 8601 formatted string or None
    """
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


async def _make_request(
    endpoint: str,
    mac: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    timeout: float = DEFAULT_TIMEOUT
) -> list:
    """
    Make an async HTTP GET request to device-service.

    Args:
        endpoint: API endpoint path (e.g., "/api/data/{mac}/bcg")
        mac: Device MAC address
        start: Start time filter (optional)
        end: End time filter (optional)
        limit: Maximum number of records to return
        offset: Number of records to skip
        timeout: Request timeout in seconds

    Returns:
        list: Data records from the API response

    Raises:
        httpx.HTTPError: If the API request fails
        ValueError: If the response format is invalid
    """
    url = f"{DEVICE_SERVICE_URL}{endpoint}".format(mac=mac)

    # Build query parameters
    params = {
        "limit": limit,
        "offset": offset
    }

    if start is not None:
        params["start"] = _format_datetime(start)
    if end is not None:
        params["end"] = _format_datetime(end)

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Requesting device-service: {url} with params {params}")
            response = await client.get(url, params=params, timeout=timeout)
            response.raise_for_status()

            result = response.json()

            # Validate response format
            if not isinstance(result, dict):
                logger.error(f"Invalid response format: expected dict, got {type(result)}")
                raise ValueError("Invalid response format from device-service")

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Device-service returned error: {error_msg}")
                raise ValueError(f"Device-service error: {error_msg}")

            data = result.get("data", [])
            meta = result.get("meta", {})
            logger.info(f"Device-service returned {len(data)} records (meta: {meta})")

            return data

    except httpx.TimeoutException as e:
        logger.error(f"Device-service request timeout: {url}")
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"Device-service HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except httpx.HTTPError as e:
        logger.error(f"Device-service request failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in device-service request: {str(e)}")
        raise


async def get_bcg_data(
    mac: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    timeout: float = DEFAULT_TIMEOUT
) -> list:
    """
    Get BCG (ballistocardiogram) data for a device.

    BCG data includes heart rate, HRV, and respiratory rate measurements
    from the collar sensor.

    Args:
        mac: Device MAC address (e.g., "AABBCCDDEEFF")
        start: Start time filter (optional)
        end: End time filter (optional)
        limit: Maximum number of records (default 100)
        offset: Number of records to skip (default 0)
        timeout: Request timeout in seconds (default 30.0)

    Returns:
        list: BCG data records, each containing:
            - timestamp: ISO 8601 timestamp
            - heart_rate_bpm: Heart rate in BPM
            - hrv_ms: Heart rate variability in milliseconds
            - respiratory_rate: Respiratory rate
            - anomaly_flag: Whether anomaly was detected

    Example:
        records = await get_bcg_data(mac="AABBCCDDEEFF", limit=50)
        for record in records:
            print(f"Heart rate: {record['heart_rate_bpm']} BPM")
    """
    return await _make_request(
        endpoint="/api/data/{mac}/bcg",
        mac=mac,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
        timeout=timeout
    )


async def get_gps_data(
    mac: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    timeout: float = DEFAULT_TIMEOUT
) -> list:
    """
    Get GPS location data for a device.

    GPS data includes latitude, longitude, and accuracy measurements
    from the collar's GPS module.

    Args:
        mac: Device MAC address (e.g., "AABBCCDDEEFF")
        start: Start time filter (optional)
        end: End time filter (optional)
        limit: Maximum number of records (default 100)
        offset: Number of records to skip (default 0)
        timeout: Request timeout in seconds (default 30.0)

    Returns:
        list: GPS data records, each containing:
            - timestamp: ISO 8601 timestamp
            - latitude: Latitude coordinate
            - longitude: Longitude coordinate
            - accuracy: GPS accuracy in meters
            - altitude: Altitude in meters (optional)

    Example:
        records = await get_gps_data(mac="AABBCCDDEEFF", limit=50)
        for record in records:
            print(f"Location: ({record['latitude']}, {record['longitude']})")
    """
    return await _make_request(
        endpoint="/api/data/{mac}/gps",
        mac=mac,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
        timeout=timeout
    )


async def get_imu_data(
    mac: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    timeout: float = DEFAULT_TIMEOUT
) -> list:
    """
    Get IMU (Inertial Measurement Unit) data for a device.

    IMU data includes accelerometer and gyroscope readings used for
    activity detection and motion analysis.

    Args:
        mac: Device MAC address (e.g., "AABBCCDDEEFF")
        start: Start time filter (optional)
        end: End time filter (optional)
        limit: Maximum number of records (default 100)
        offset: Number of records to skip (default 0)
        timeout: Request timeout in seconds (default 30.0)

    Returns:
        list: IMU data records, each containing:
            - timestamp: ISO 8601 timestamp
            - accel_x, accel_y, accel_z: Accelerometer readings
            - gyro_x, gyro_y, gyro_z: Gyroscope readings
            - activity_type: Detected activity type (optional)

    Example:
        records = await get_imu_data(mac="AABBCCDDEEFF", limit=50)
        for record in records:
            print(f"Activity: {record.get('activity_type', 'unknown')}")
    """
    return await _make_request(
        endpoint="/api/data/{mac}/imu",
        mac=mac,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
        timeout=timeout
    )


async def get_temp_data(
    mac: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    timeout: float = DEFAULT_TIMEOUT
) -> list:
    """
    Get temperature data for a device.

    Temperature data includes ambient and body temperature readings
    from the collar's temperature sensor.

    Args:
        mac: Device MAC address (e.g., "AABBCCDDEEFF")
        start: Start time filter (optional)
        end: End time filter (optional)
        limit: Maximum number of records (default 100)
        offset: Number of records to skip (default 0)
        timeout: Request timeout in seconds (default 30.0)

    Returns:
        list: Temperature data records, each containing:
            - timestamp: ISO 8601 timestamp
            - temperature: Temperature value in Celsius
            - sensor_type: Type of temperature sensor

    Example:
        records = await get_temp_data(mac="AABBCCDDEEFF", limit=50)
        for record in records:
            print(f"Temperature: {record['temperature']}C")
    """
    return await _make_request(
        endpoint="/api/data/{mac}/temp",
        mac=mac,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
        timeout=timeout
    )


async def get_device_events(
    mac: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    timeout: float = DEFAULT_TIMEOUT
) -> list:
    """
    Get device events for a device.

    Device events include system events like power on/off, connectivity
    changes, firmware updates, and other device-level occurrences.

    Args:
        mac: Device MAC address (e.g., "AABBCCDDEEFF")
        start: Start time filter (optional)
        end: End time filter (optional)
        limit: Maximum number of records (default 100)
        offset: Number of records to skip (default 0)
        timeout: Request timeout in seconds (default 30.0)

    Returns:
        list: Event records, each containing:
            - timestamp: ISO 8601 timestamp
            - event_type: Type of event
            - event_data: Additional event data (JSON)
            - severity: Event severity level

    Example:
        records = await get_device_events(mac="AABBCCDDEEFF", limit=50)
        for record in records:
            print(f"Event: {record['event_type']} at {record['timestamp']}")
    """
    return await _make_request(
        endpoint="/api/data/{mac}/events",
        mac=mac,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
        timeout=timeout
    )


async def get_door_detections(
    mac: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    timeout: float = DEFAULT_TIMEOUT
) -> list:
    """
    Get cat door detection records for a device.

    Door detection data includes AI-based detection results for cat
    passages through the door, including prey detection.

    Args:
        mac: Device MAC address (e.g., "AABBCCDDEEFF")
        start: Start time filter (optional)
        end: End time filter (optional)
        limit: Maximum number of records (default 100)
        offset: Number of records to skip (default 0)
        timeout: Request timeout in seconds (default 30.0)

    Returns:
        list: Detection records, each containing:
            - timestamp: ISO 8601 timestamp
            - detection_type: Type of detection (cat, prey, etc.)
            - confidence: Detection confidence score
            - direction: Direction of movement (in/out)
            - image_url: URL to captured image (optional)
            - has_prey: Whether prey was detected

    Example:
        records = await get_door_detections(mac="AABBCCDDEEFF", limit=50)
        for record in records:
            if record.get('has_prey'):
                print(f"Prey detected at {record['timestamp']}")
    """
    return await _make_request(
        endpoint="/api/data/{mac}/door-detections",
        mac=mac,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
        timeout=timeout
    )


if __name__ == "__main__":
    import asyncio

    async def test():
        """Test device-service client with example queries"""
        try:
            # Test BCG data
            print("Testing BCG data query...")
            bcg_data = await get_bcg_data(mac="AABBCCDDEEFF", limit=10)
            print(f"BCG data: {len(bcg_data)} records")

            # Test GPS data
            print("Testing GPS data query...")
            gps_data = await get_gps_data(mac="AABBCCDDEEFF", limit=10)
            print(f"GPS data: {len(gps_data)} records")

            # Test IMU data
            print("Testing IMU data query...")
            imu_data = await get_imu_data(mac="AABBCCDDEEFF", limit=10)
            print(f"IMU data: {len(imu_data)} records")

            # Test temperature data
            print("Testing temperature data query...")
            temp_data = await get_temp_data(mac="AABBCCDDEEFF", limit=10)
            print(f"Temperature data: {len(temp_data)} records")

            # Test device events
            print("Testing device events query...")
            events = await get_device_events(mac="AABBCCDDEEFF", limit=10)
            print(f"Device events: {len(events)} records")

            # Test door detections
            print("Testing door detections query...")
            detections = await get_door_detections(mac="AABBCCDDEEFF", limit=10)
            print(f"Door detections: {len(detections)} records")

            print("\nAll tests completed successfully!")

        except Exception as e:
            print(f"Test failed: {e}")

    asyncio.run(test())
