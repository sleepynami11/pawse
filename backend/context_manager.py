"""
SystemContext Manager - PocketFlow Shared Store Abstraction

This module implements the shared store pattern for the Cat IoT Agent System,
providing hybrid storage with in-memory request context and D1/R2 persistence.

Design Philosophy (PocketFlow):
- Separation of concerns: Data schema separate from compute logic
- Request-scoped in-memory caching for efficiency
- Cat-ID-based data isolation
- Async data loading from D1 database
- Schema migration support with backward compatibility

UPDATED (Schema Refactor):
- New methods for collar device data: get_outdoor_status(), get_bcg_metrics()
- New methods for cat door device data: get_cat_door_passages(), get_expression_analysis()
- Cross-device correlation support: get_cross_device_correlation()
- Backward compatibility: Existing queries fallback to legacy tables during migration

UPDATED (V3.4 - Device MAC Support):
- Added device_mac parameter for direct time-series queries via device_service_client
- New methods: get_bcg_data_by_mac(), get_gps_data_by_mac(), get_imu_data_by_mac()
- Device MAC enables direct TimescaleDB queries without user/cat ID mapping

Usage Example:
    from context_manager import SystemContext

    async with SystemContext(cat_id="123", device_mac="AABBCCDDEEFF") as ctx:
        # Get cat profile
        profile = await ctx.get_cat_profile("123")

        # Get recent IoT logs (collar activity)
        logs = await ctx.get_recent_iot_logs("123", hours=24)

        # Get outdoor status (NEW)
        outdoor = await ctx.get_outdoor_status("123", hours=12)

        # Get BCG heart rate metrics (NEW)
        bcg = await ctx.get_bcg_metrics("123", hours=6)

        # V3.4: Get BCG data directly by device MAC
        bcg_by_mac = await ctx.get_bcg_data_by_mac(hours=6)

        # V3.4: Get GPS data directly by device MAC
        gps_by_mac = await ctx.get_gps_data_by_mac(hours=12)

        # Get cat door passages (NEW)
        passages = await ctx.get_cat_door_passages("123", hours=24)

        # Get expression analysis for specific passage (NEW)
        expression = await ctx.get_expression_analysis(passage_id)

        # Get cross-device correlation insights (NEW)
        correlation = await ctx.get_cross_device_correlation("123", hours=12)

        # Get medical history
        history = await ctx.get_medical_history("123")

        # Get device status
        status = await ctx.get_device_status("123")
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional
from utils.d1_client import execute_query

# V3.4: Import device service client for time-series queries by MAC
from utils.device_service_client import (
    get_bcg_data,
    get_gps_data,
    get_imu_data,
    get_temp_data,
    get_device_events,
    get_door_detections
)

logger = logging.getLogger(__name__)


class SystemContext:
    """
    SystemContext implements the PocketFlow shared store pattern.

    Provides hybrid storage:
    - In-memory cache: Request-scoped data for fast access
    - D1 database: Persistent storage for cat profiles, IoT logs, medical history, device status
    - Device service (V3.4): Time-series data via device_mac for BCG, GPS, IMU, etc.

    The context manager pattern ensures proper resource cleanup and cache lifecycle management.
    """

    def __init__(self, cat_id: Optional[str] = None, device_mac: Optional[str] = None):
        """
        Initialize SystemContext with optional cat_id and device_mac.

        Args:
            cat_id: Optional cat identifier for context isolation
            device_mac: Optional device MAC address for time-series queries (V3.4)
        """
        self.cat_id = cat_id
        self.device_mac = device_mac  # V3.4: Device MAC for direct TimescaleDB queries
        self.cache = {
            "cat_profiles": {},
            "iot_logs": {},
            "medical_history": {},
            "device_status": {},
            "timeseries_data": {}  # V3.4: Cache for time-series data by MAC
        }
        logger.info(f"SystemContext initialized for cat_id={cat_id}, device_mac={device_mac}")

    async def __aenter__(self):
        """Enter async context manager"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager and cleanup cache"""
        self.cache.clear()
        logger.info("SystemContext cache cleared")

    async def get_cat_profile(self, cat_id: str) -> dict:
        """
        Get cat profile from D1 database with in-memory caching.

        Args:
            cat_id: Cat identifier

        Returns:
            dict: Cat profile containing:
                - id: Cat ID
                - name: Cat name
                - breed: Cat breed
                - age: Cat age
                - medical_history: Parsed medical history JSON
                - created_at: Profile creation timestamp

        Example:
            profile = await ctx.get_cat_profile("123")
            print(f"Cat name: {profile['name']}")
        """
        # Check cache first
        if cat_id in self.cache["cat_profiles"]:
            logger.info(f"Cache hit for cat profile: {cat_id}")
            return self.cache["cat_profiles"][cat_id]

        # Query D1 database
        logger.info(f"Querying D1 for cat profile: {cat_id}")
        result = await execute_query(
            "SELECT * FROM cats WHERE id = ?",
            [cat_id]
        )

        if not result.get("success") or not result.get("result", {}).get("results"):
            logger.warning(f"Cat profile not found: {cat_id}")
            return {}

        # Parse result
        cat_data = result["result"]["results"][0]

        # Parse medical_history_json field
        medical_history = {}
        if cat_data.get("medical_history_json"):
            try:
                medical_history = json.loads(cat_data["medical_history_json"])
            except json.JSONDecodeError:
                logger.error(f"Failed to parse medical_history_json for cat {cat_id}")
                medical_history = {}

        profile = {
            "id": cat_data.get("id"),
            "name": cat_data.get("name"),
            "breed": cat_data.get("breed"),
            "age": cat_data.get("age"),
            "medical_history": medical_history,
            "created_at": cat_data.get("created_at")
        }

        # Cache result
        self.cache["cat_profiles"][cat_id] = profile
        logger.info(f"Cached cat profile: {cat_id}")

        return profile

    async def get_recent_iot_logs(self, cat_id: str, hours: int = 24) -> list[dict]:
        """
        Get recent IoT sensor logs from D1 database.

        UPDATED: Now queries collar_activity_logs table (new schema).
        Falls back to iot_logs if collar_activity_logs query fails (backward compatibility).

        Args:
            cat_id: Cat identifier
            hours: Number of hours to look back (default: 24)

        Returns:
            list[dict]: List of IoT log entries, each containing:
                - id: Log entry ID
                - cat_id: Cat ID
                - collar_device_id: Collar device ID
                - activity_type: Activity type (motion, steps, active_time)
                - value: Activity reading value
                - unit: Value unit
                - timestamp: Log timestamp

        Example:
            logs = await ctx.get_recent_iot_logs("123", hours=12)
            for log in logs:
                print(f"{log['activity_type']}: {log['value']} {log['unit']}")
        """
        # Check cache first
        cache_key = f"{cat_id}_{hours}h"
        if cache_key in self.cache["iot_logs"]:
            logger.info(f"Cache hit for IoT logs: {cache_key}")
            return self.cache["iot_logs"][cache_key]

        # Calculate timestamp threshold
        threshold = datetime.now() - timedelta(hours=hours)
        threshold_str = threshold.strftime("%Y-%m-%d %H:%M:%S")

        # Try new schema first (collar_activity_logs)
        logger.info(f"Querying D1 for collar activity logs: cat_id={cat_id}, hours={hours}")
        result = await execute_query(
            "SELECT * FROM collar_activity_logs WHERE cat_id = ? AND timestamp > ? ORDER BY timestamp DESC",
            [cat_id, threshold_str]
        )

        # Fallback to old schema (iot_logs) if new schema query fails
        if not result.get("success") or not result.get("result", {}).get("results"):
            logger.info(f"Falling back to iot_logs table for cat {cat_id}")
            result = await execute_query(
                "SELECT * FROM iot_logs WHERE cat_id = ? AND timestamp > ? ORDER BY timestamp DESC",
                [cat_id, threshold_str]
            )

        if not result.get("success") or not result.get("result", {}).get("results"):
            logger.warning(f"No IoT logs found for cat {cat_id} in last {hours} hours")
            return []

        # Parse results
        logs = result["result"]["results"]

        # Cache result
        self.cache["iot_logs"][cache_key] = logs
        logger.info(f"Cached {len(logs)} IoT logs for {cache_key}")

        return logs

    async def get_outdoor_status(self, cat_id: str, hours: int = 24) -> list[dict]:
        """
        Get outdoor status logs from collar_outdoor_logs table.

        Args:
            cat_id: Cat identifier
            hours: Number of hours to look back (default: 24)

        Returns:
            list[dict]: List of outdoor status entries, each containing:
                - id: Log entry ID
                - collar_device_id: Collar device ID
                - cat_id: Cat ID
                - is_outdoor: Outdoor status (1=outdoor, 0=indoor)
                - location_lat: GPS latitude
                - location_lng: GPS longitude
                - started_at: Outdoor session start time
                - ended_at: Outdoor session end time

        Example:
            outdoor_logs = await ctx.get_outdoor_status("123", hours=12)
            for log in outdoor_logs:
                if log['is_outdoor']:
                    print(f"Outdoor at ({log['location_lat']}, {log['location_lng']})")
        """
        # Check cache first
        cache_key = f"outdoor_{cat_id}_{hours}h"
        if cache_key in self.cache.get("outdoor_logs", {}):
            logger.info(f"Cache hit for outdoor logs: {cache_key}")
            return self.cache["outdoor_logs"][cache_key]

        # Calculate timestamp threshold
        threshold = datetime.now() - timedelta(hours=hours)
        threshold_str = threshold.strftime("%Y-%m-%d %H:%M:%S")

        # Query D1 database
        logger.info(f"Querying D1 for outdoor status: cat_id={cat_id}, hours={hours}")
        result = await execute_query(
            "SELECT * FROM collar_outdoor_logs WHERE cat_id = ? AND started_at > ? ORDER BY started_at DESC",
            [cat_id, threshold_str]
        )

        if not result.get("success") or not result.get("result", {}).get("results"):
            logger.warning(f"No outdoor logs found for cat {cat_id} in last {hours} hours")
            return []

        # Parse results
        outdoor_logs = result["result"]["results"]

        # Initialize outdoor_logs cache if not exists
        if "outdoor_logs" not in self.cache:
            self.cache["outdoor_logs"] = {}

        # Cache result
        self.cache["outdoor_logs"][cache_key] = outdoor_logs
        logger.info(f"Cached {len(outdoor_logs)} outdoor logs for {cache_key}")

        return outdoor_logs

    async def get_bcg_metrics(self, cat_id: str, hours: int = 24) -> list[dict]:
        """
        Get BCG heart rate metrics from collar_bcg_logs table.

        Args:
            cat_id: Cat identifier
            hours: Number of hours to look back (default: 24)

        Returns:
            list[dict]: List of BCG metric entries, each containing:
                - id: Log entry ID
                - collar_device_id: Collar device ID
                - cat_id: Cat ID
                - heart_rate_bpm: Heart rate in beats per minute
                - hrv_ms: Heart rate variability in milliseconds
                - respiratory_rate: Respiratory rate
                - anomaly_flag: Anomaly detection flag (0=normal, 1=anomaly)
                - timestamp: Measurement timestamp

        Example:
            bcg_logs = await ctx.get_bcg_metrics("123", hours=6)
            anomalies = [log for log in bcg_logs if log['anomaly_flag'] == 1]
            print(f"Found {len(anomalies)} BCG anomalies")
        """
        # Check cache first
        cache_key = f"bcg_{cat_id}_{hours}h"
        if cache_key in self.cache.get("bcg_logs", {}):
            logger.info(f"Cache hit for BCG logs: {cache_key}")
            return self.cache["bcg_logs"][cache_key]

        # Calculate timestamp threshold
        threshold = datetime.now() - timedelta(hours=hours)
        threshold_str = threshold.strftime("%Y-%m-%d %H:%M:%S")

        # Query D1 database
        logger.info(f"Querying D1 for BCG metrics: cat_id={cat_id}, hours={hours}")
        result = await execute_query(
            "SELECT * FROM collar_bcg_logs WHERE cat_id = ? AND timestamp > ? ORDER BY timestamp DESC",
            [cat_id, threshold_str]
        )

        if not result.get("success") or not result.get("result", {}).get("results"):
            logger.warning(f"No BCG logs found for cat {cat_id} in last {hours} hours")
            return []

        # Parse results
        bcg_logs = result["result"]["results"]

        # Initialize bcg_logs cache if not exists
        if "bcg_logs" not in self.cache:
            self.cache["bcg_logs"] = {}

        # Cache result
        self.cache["bcg_logs"][cache_key] = bcg_logs
        logger.info(f"Cached {len(bcg_logs)} BCG logs for {cache_key}")

        return bcg_logs

    async def get_cat_door_passages(self, cat_id: str, hours: int = 24) -> list[dict]:
        """
        Get cat door passage logs from cat_door_passage_logs table.

        Args:
            cat_id: Cat identifier
            hours: Number of hours to look back (default: 24)

        Returns:
            list[dict]: List of passage entries, each containing:
                - id: Passage log ID
                - cat_door_device_id: Cat door device ID
                - cat_id: Cat ID
                - direction: Passage direction (in/out)
                - identification_method: ID method (rfid/facial/beacon)
                - identification_confidence: ID confidence score (0.0-1.0)
                - timestamp: Passage timestamp

        Example:
            passages = await ctx.get_cat_door_passages("123", hours=12)
            recent_in = [p for p in passages if p['direction'] == 'in']
            print(f"Cat entered {len(recent_in)} times in last 12 hours")
        """
        # Check cache first
        cache_key = f"passages_{cat_id}_{hours}h"
        if cache_key in self.cache.get("passage_logs", {}):
            logger.info(f"Cache hit for passage logs: {cache_key}")
            return self.cache["passage_logs"][cache_key]

        # Calculate timestamp threshold
        threshold = datetime.now() - timedelta(hours=hours)
        threshold_str = threshold.strftime("%Y-%m-%d %H:%M:%S")

        # Query D1 database
        logger.info(f"Querying D1 for cat door passages: cat_id={cat_id}, hours={hours}")
        result = await execute_query(
            "SELECT * FROM cat_door_passage_logs WHERE cat_id = ? AND timestamp > ? ORDER BY timestamp DESC",
            [cat_id, threshold_str]
        )

        if not result.get("success") or not result.get("result", {}).get("results"):
            logger.warning(f"No passage logs found for cat {cat_id} in last {hours} hours")
            return []

        # Parse results
        passage_logs = result["result"]["results"]

        # Initialize passage_logs cache if not exists
        if "passage_logs" not in self.cache:
            self.cache["passage_logs"] = {}

        # Cache result
        self.cache["passage_logs"][cache_key] = passage_logs
        logger.info(f"Cached {len(passage_logs)} passage logs for {cache_key}")

        return passage_logs

    async def get_expression_analysis(self, passage_log_id: int) -> dict:
        """
        Get facial expression analysis for a specific cat door passage.

        Args:
            passage_log_id: Passage log ID to get expression analysis for

        Returns:
            dict: Expression analysis containing:
                - id: Expression log ID
                - passage_log_id: Associated passage log ID
                - cat_id: Cat ID
                - image_url: Expression image URL
                - mood: Detected mood (happy/neutral/distressed)
                - alertness: Alertness level (alert/drowsy/lethargic)
                - pain_score: Pain score (0.0-10.0)
                - pain_indicators: JSON with pain indicator details
                - analysis_result: Full analysis JSON
                - timestamp: Analysis timestamp

        Example:
            expression = await ctx.get_expression_analysis(passage_id)
            if expression.get('pain_score', 0) > 5.0:
                print(f"High pain detected: {expression['pain_score']}")
        """
        # Check cache first
        cache_key = f"expression_{passage_log_id}"
        if cache_key in self.cache.get("expression_logs", {}):
            logger.info(f"Cache hit for expression log: {cache_key}")
            return self.cache["expression_logs"][cache_key]

        # Query D1 database
        logger.info(f"Querying D1 for expression analysis: passage_log_id={passage_log_id}")
        result = await execute_query(
            "SELECT * FROM cat_door_expression_logs WHERE passage_log_id = ?",
            [passage_log_id]
        )

        if not result.get("success") or not result.get("result", {}).get("results"):
            logger.warning(f"No expression analysis found for passage {passage_log_id}")
            return {}

        # Parse result
        expression_data = result["result"]["results"][0]

        # Parse JSON fields
        pain_indicators = {}
        if expression_data.get("pain_indicators"):
            try:
                pain_indicators = json.loads(expression_data["pain_indicators"])
            except json.JSONDecodeError:
                logger.error(f"Failed to parse pain_indicators for passage {passage_log_id}")

        analysis_result = {}
        if expression_data.get("analysis_result"):
            try:
                analysis_result = json.loads(expression_data["analysis_result"])
            except json.JSONDecodeError:
                logger.error(f"Failed to parse analysis_result for passage {passage_log_id}")

        expression = {
            "id": expression_data.get("id"),
            "passage_log_id": expression_data.get("passage_log_id"),
            "cat_id": expression_data.get("cat_id"),
            "image_url": expression_data.get("image_url"),
            "mood": expression_data.get("mood"),
            "alertness": expression_data.get("alertness"),
            "pain_score": expression_data.get("pain_score"),
            "pain_indicators": pain_indicators,
            "analysis_result": analysis_result,
            "timestamp": expression_data.get("timestamp")
        }

        # Initialize expression_logs cache if not exists
        if "expression_logs" not in self.cache:
            self.cache["expression_logs"] = {}

        # Cache result
        self.cache["expression_logs"][cache_key] = expression
        logger.info(f"Cached expression analysis for passage {passage_log_id}")

        return expression

    async def get_cross_device_correlation(self, cat_id: str, hours: int = 24) -> dict:
        """
        Get cross-device correlation data by joining collar and cat door logs.

        This method provides multi-device insights by correlating:
        - Collar activity data with cat door passages
        - Outdoor status with door entry/exit patterns
        - BCG metrics with passage timestamps

        Args:
            cat_id: Cat identifier
            hours: Number of hours to look back (default: 24)

        Returns:
            dict: Correlation data containing:
                - passages: List of passage events with correlated collar data
                - outdoor_events: List of outdoor events with entry/exit correlation
                - health_alerts: List of health-related correlations (BCG anomaly + activity)

        Example:
            correlation = await ctx.get_cross_device_correlation("123", hours=12)
            for passage in correlation['passages']:
                activity_before = passage.get('activity_before_passage')
                print(f"Activity before entry: {activity_before}")
        """
        # Check cache first
        cache_key = f"correlation_{cat_id}_{hours}h"
        if cache_key in self.cache.get("correlation_data", {}):
            logger.info(f"Cache hit for correlation data: {cache_key}")
            return self.cache["correlation_data"][cache_key]

        logger.info(f"Computing cross-device correlation for cat {cat_id}")

        # Get all device data in parallel
        activity_logs, outdoor_logs, bcg_logs, passages = await asyncio.gather(
            self.get_recent_iot_logs(cat_id, hours),
            self.get_outdoor_status(cat_id, hours),
            self.get_bcg_metrics(cat_id, hours),
            self.get_cat_door_passages(cat_id, hours),
            return_exceptions=True
        )

        # Handle exceptions from parallel queries
        if isinstance(activity_logs, Exception):
            logger.error(f"Failed to get activity logs: {activity_logs}")
            activity_logs = []
        if isinstance(outdoor_logs, Exception):
            logger.error(f"Failed to get outdoor logs: {outdoor_logs}")
            outdoor_logs = []
        if isinstance(bcg_logs, Exception):
            logger.error(f"Failed to get BCG logs: {bcg_logs}")
            bcg_logs = []
        if isinstance(passages, Exception):
            logger.error(f"Failed to get passages: {passages}")
            passages = []

        # Correlate passages with collar activity
        correlated_passages = []
        for passage in passages:
            passage_time = datetime.strptime(passage["timestamp"], "%Y-%m-%d %H:%M:%S")
            time_window_start = passage_time - timedelta(minutes=30)
            time_window_end = passage_time + timedelta(minutes=30)

            # Find activity logs within time window
            activity_before = [
                log for log in activity_logs
                if time_window_start <= datetime.strptime(log["timestamp"], "%Y-%m-%d %H:%M:%S") < passage_time
            ]

            correlated_passages.append({
                **passage,
                "activity_before_passage": activity_before[-5:] if activity_before else []
            })

        # Correlate outdoor events with door passages
        outdoor_events = []
        for outdoor_log in outdoor_logs:
            if outdoor_log.get("started_at"):
                start_time = datetime.strptime(outdoor_log["started_at"], "%Y-%m-%d %H:%M:%S")
                # Find closest door exit
                closest_exit = min(
                    (p for p in passages if p["direction"] == "out"),
                    key=lambda p: abs((datetime.strptime(p["timestamp"], "%Y-%m-%d %H:%M:%S") - start_time).total_seconds()),
                    default=None
                )
                outdoor_events.append({
                    **outdoor_log,
                    "correlated_exit": closest_exit
                })

        # Detect health alerts (BCG anomaly + activity changes)
        health_alerts = []
        bcg_anomalies = [log for log in bcg_logs if log.get("anomaly_flag") == 1]
        for anomaly in bcg_anomalies:
            anomaly_time = datetime.strptime(anomaly["timestamp"], "%Y-%m-%d %H:%M:%S")
            time_window_start = anomaly_time - timedelta(hours=1)
            time_window_end = anomaly_time + timedelta(hours=1)

            # Find activity changes around anomaly time
            activity_around = [
                log for log in activity_logs
                if time_window_start <= datetime.strptime(log["timestamp"], "%Y-%m-%d %H:%M:%S") <= time_window_end
            ]

            health_alerts.append({
                "bcg_anomaly": anomaly,
                "activity_context": activity_around,
                "alert_type": "bcg_activity_correlation"
            })

        correlation_data = {
            "passages": correlated_passages,
            "outdoor_events": outdoor_events,
            "health_alerts": health_alerts
        }

        # Initialize correlation_data cache if not exists
        if "correlation_data" not in self.cache:
            self.cache["correlation_data"] = {}

        # Cache result
        self.cache["correlation_data"][cache_key] = correlation_data
        logger.info(f"Cached correlation data for cat {cat_id}")

        return correlation_data

    async def get_medical_history(self, cat_id: str) -> list[dict]:
        """
        Get medical history from D1 database (anomaly logs + profile medical history).

        Args:
            cat_id: Cat identifier

        Returns:
            list[dict]: Chronological list of medical events containing:
                - event_type: Type of medical event (anomaly, checkup, vaccination, etc.)
                - timestamp: Event timestamp
                - details: Event details
                - source: Data source (iot_logs or cat_profile)

        Example:
            history = await ctx.get_medical_history("123")
            for event in history:
                print(f"{event['timestamp']}: {event['event_type']}")
        """
        # Check cache first
        if cat_id in self.cache["medical_history"]:
            logger.info(f"Cache hit for medical history: {cat_id}")
            return self.cache["medical_history"][cat_id]

        # Query D1 for anomaly logs
        logger.info(f"Querying D1 for medical history: {cat_id}")
        result = await execute_query(
            "SELECT * FROM iot_logs WHERE cat_id = ? AND anomaly_flag = 1 ORDER BY timestamp DESC LIMIT 50",
            [cat_id]
        )

        medical_events = []

        # Parse anomaly logs
        if result.get("success") and result.get("result", {}).get("results"):
            for log in result["result"]["results"]:
                medical_events.append({
                    "event_type": "anomaly",
                    "timestamp": log.get("timestamp"),
                    "details": {
                        "sensor_type": log.get("sensor_type"),
                        "value": log.get("value"),
                        "device_id": log.get("device_id")
                    },
                    "source": "iot_logs"
                })

        # Get cat profile medical history
        profile = await self.get_cat_profile(cat_id)
        if profile.get("medical_history"):
            # Assume medical_history is a list of events
            if isinstance(profile["medical_history"], list):
                for event in profile["medical_history"]:
                    medical_events.append({
                        "event_type": event.get("type", "medical_record"),
                        "timestamp": event.get("timestamp"),
                        "details": event.get("details", {}),
                        "source": "cat_profile"
                    })

        # Sort by timestamp (most recent first)
        medical_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Cache result
        self.cache["medical_history"][cat_id] = medical_events
        logger.info(f"Cached {len(medical_events)} medical events for cat {cat_id}")

        return medical_events

    async def get_device_status(self, cat_id: str) -> dict:
        """
        Get device status from D1 database.

        Args:
            cat_id: Cat identifier

        Returns:
            dict: Device status containing:
                - device_id: Device identifier
                - online_status: Online status (1=online, 0=offline)
                - last_heartbeat: Last heartbeat timestamp
                - battery_level: Battery percentage (0-100)
                - health: Device health flag (healthy/unhealthy)

        Example:
            status = await ctx.get_device_status("123")
            if status['health'] == 'unhealthy':
                print(f"Device {status['device_id']} needs attention")
        """
        # Check cache first
        if cat_id in self.cache["device_status"]:
            logger.info(f"Cache hit for device status: {cat_id}")
            return self.cache["device_status"][cat_id]

        # Query D1 database
        logger.info(f"Querying D1 for device status: {cat_id}")
        result = await execute_query(
            "SELECT * FROM device_status WHERE cat_id = ?",
            [cat_id]
        )

        if not result.get("success") or not result.get("result", {}).get("results"):
            logger.warning(f"Device status not found for cat {cat_id}")
            return {}

        # Parse result
        device_data = result["result"]["results"][0]

        # Calculate device health
        online = device_data.get("online_status", 0) == 1
        battery = device_data.get("battery_level", 0)
        health = "healthy" if (online and battery >= 20) else "unhealthy"

        status = {
            "device_id": device_data.get("device_id"),
            "online_status": device_data.get("online_status"),
            "last_heartbeat": device_data.get("last_heartbeat"),
            "battery_level": battery,
            "health": health
        }

        # Cache result
        self.cache["device_status"][cat_id] = status
        logger.info(f"Cached device status for cat {cat_id}: {health}")

        return status

    # =========================================================================
    # V3.4: Time-series data methods (via device_service_client)
    # =========================================================================

    async def get_bcg_data_by_mac(self, hours: int = 24, limit: int = 100) -> list:
        """
        Get BCG (heart rate) data directly by device MAC address.

        V3.4: Uses device_service_client for time-series queries.

        Args:
            hours: Number of hours to look back (default: 24)
            limit: Maximum number of records to return (default: 100)

        Returns:
            list: BCG data records containing heart_rate_bpm, hrv_ms, etc.

        Example:
            bcg_data = await ctx.get_bcg_data_by_mac(hours=6)
            for record in bcg_data:
                print(f"Heart rate: {record['heart_rate_bpm']} BPM")
        """
        if not self.device_mac:
            logger.warning("get_bcg_data_by_mac called without device_mac")
            return []

        cache_key = f"bcg_{self.device_mac}_{hours}h"
        if cache_key in self.cache["timeseries_data"]:
            logger.info(f"Cache hit for BCG data: {cache_key}")
            return self.cache["timeseries_data"][cache_key]

        try:
            end = datetime.utcnow()
            start = end - timedelta(hours=hours)

            data = await get_bcg_data(
                mac=self.device_mac,
                start=start,
                end=end,
                limit=limit
            )

            self.cache["timeseries_data"][cache_key] = data
            logger.info(f"Cached {len(data)} BCG records for {cache_key}")
            return data

        except Exception as e:
            logger.error(f"Error fetching BCG data by MAC: {e}")
            return []

    async def get_gps_data_by_mac(self, hours: int = 24, limit: int = 100) -> list:
        """
        Get GPS location data directly by device MAC address.

        V3.4: Uses device_service_client for time-series queries.

        Args:
            hours: Number of hours to look back (default: 24)
            limit: Maximum number of records to return (default: 100)

        Returns:
            list: GPS data records containing latitude, longitude, accuracy, etc.

        Example:
            gps_data = await ctx.get_gps_data_by_mac(hours=12)
            for record in gps_data:
                print(f"Location: ({record['latitude']}, {record['longitude']})")
        """
        if not self.device_mac:
            logger.warning("get_gps_data_by_mac called without device_mac")
            return []

        cache_key = f"gps_{self.device_mac}_{hours}h"
        if cache_key in self.cache["timeseries_data"]:
            logger.info(f"Cache hit for GPS data: {cache_key}")
            return self.cache["timeseries_data"][cache_key]

        try:
            end = datetime.utcnow()
            start = end - timedelta(hours=hours)

            data = await get_gps_data(
                mac=self.device_mac,
                start=start,
                end=end,
                limit=limit
            )

            self.cache["timeseries_data"][cache_key] = data
            logger.info(f"Cached {len(data)} GPS records for {cache_key}")
            return data

        except Exception as e:
            logger.error(f"Error fetching GPS data by MAC: {e}")
            return []

    async def get_imu_data_by_mac(self, hours: int = 24, limit: int = 100) -> list:
        """
        Get IMU (activity) data directly by device MAC address.

        V3.4: Uses device_service_client for time-series queries.

        Args:
            hours: Number of hours to look back (default: 24)
            limit: Maximum number of records to return (default: 100)

        Returns:
            list: IMU data records containing accelerometer/gyroscope readings.

        Example:
            imu_data = await ctx.get_imu_data_by_mac(hours=6)
            for record in imu_data:
                print(f"Activity: {record.get('activity_type', 'unknown')}")
        """
        if not self.device_mac:
            logger.warning("get_imu_data_by_mac called without device_mac")
            return []

        cache_key = f"imu_{self.device_mac}_{hours}h"
        if cache_key in self.cache["timeseries_data"]:
            logger.info(f"Cache hit for IMU data: {cache_key}")
            return self.cache["timeseries_data"][cache_key]

        try:
            end = datetime.utcnow()
            start = end - timedelta(hours=hours)

            data = await get_imu_data(
                mac=self.device_mac,
                start=start,
                end=end,
                limit=limit
            )

            self.cache["timeseries_data"][cache_key] = data
            logger.info(f"Cached {len(data)} IMU records for {cache_key}")
            return data

        except Exception as e:
            logger.error(f"Error fetching IMU data by MAC: {e}")
            return []

    async def get_temp_data_by_mac(self, hours: int = 24, limit: int = 100) -> list:
        """
        Get temperature data directly by device MAC address.

        V3.4: Uses device_service_client for time-series queries.

        Args:
            hours: Number of hours to look back (default: 24)
            limit: Maximum number of records to return (default: 100)

        Returns:
            list: Temperature data records.

        Example:
            temp_data = await ctx.get_temp_data_by_mac(hours=6)
            for record in temp_data:
                print(f"Temperature: {record['temperature']}C")
        """
        if not self.device_mac:
            logger.warning("get_temp_data_by_mac called without device_mac")
            return []

        cache_key = f"temp_{self.device_mac}_{hours}h"
        if cache_key in self.cache["timeseries_data"]:
            logger.info(f"Cache hit for temp data: {cache_key}")
            return self.cache["timeseries_data"][cache_key]

        try:
            end = datetime.utcnow()
            start = end - timedelta(hours=hours)

            data = await get_temp_data(
                mac=self.device_mac,
                start=start,
                end=end,
                limit=limit
            )

            self.cache["timeseries_data"][cache_key] = data
            logger.info(f"Cached {len(data)} temperature records for {cache_key}")
            return data

        except Exception as e:
            logger.error(f"Error fetching temperature data by MAC: {e}")
            return []

    async def get_door_detections_by_mac(self, hours: int = 24, limit: int = 100) -> list:
        """
        Get cat door detection records directly by device MAC address.

        V3.4: Uses device_service_client for time-series queries.

        Args:
            hours: Number of hours to look back (default: 24)
            limit: Maximum number of records to return (default: 100)

        Returns:
            list: Door detection records with direction, has_prey, etc.

        Example:
            detections = await ctx.get_door_detections_by_mac(hours=12)
            for record in detections:
                if record.get('has_prey'):
                    print(f"Prey detected at {record['timestamp']}")
        """
        if not self.device_mac:
            logger.warning("get_door_detections_by_mac called without device_mac")
            return []

        cache_key = f"detections_{self.device_mac}_{hours}h"
        if cache_key in self.cache["timeseries_data"]:
            logger.info(f"Cache hit for door detections: {cache_key}")
            return self.cache["timeseries_data"][cache_key]

        try:
            end = datetime.utcnow()
            start = end - timedelta(hours=hours)

            data = await get_door_detections(
                mac=self.device_mac,
                start=start,
                end=end,
                limit=limit
            )

            self.cache["timeseries_data"][cache_key] = data
            logger.info(f"Cached {len(data)} door detection records for {cache_key}")
            return data

        except Exception as e:
            logger.error(f"Error fetching door detections by MAC: {e}")
            return []


if __name__ == "__main__":
    # Test SystemContext
    async def test():
        """Test SystemContext with example queries"""
        try:
            # Test with cat_id only (D1 metadata queries)
            async with SystemContext(cat_id="1") as ctx:
                # Test get_cat_profile
                print("\n=== Testing get_cat_profile ===")
                profile = await ctx.get_cat_profile("1")
                print(f"Profile: {profile}")

                # Test get_recent_iot_logs
                print("\n=== Testing get_recent_iot_logs ===")
                logs = await ctx.get_recent_iot_logs("1", hours=24)
                print(f"Found {len(logs)} IoT logs")
                if logs:
                    print(f"First log: {logs[0]}")

                # Test get_medical_history
                print("\n=== Testing get_medical_history ===")
                history = await ctx.get_medical_history("1")
                print(f"Found {len(history)} medical events")
                if history:
                    print(f"First event: {history[0]}")

                # Test get_device_status
                print("\n=== Testing get_device_status ===")
                status = await ctx.get_device_status("1")
                print(f"Device status: {status}")

            # Test with device_mac (V3.4 time-series queries)
            print("\n=== Testing V3.4 time-series queries by MAC ===")
            async with SystemContext(cat_id="1", device_mac="AABBCCDDEEFF") as ctx:
                # Test get_bcg_data_by_mac
                print("\n=== Testing get_bcg_data_by_mac ===")
                bcg_data = await ctx.get_bcg_data_by_mac(hours=6)
                print(f"Found {len(bcg_data)} BCG records")

                # Test get_gps_data_by_mac
                print("\n=== Testing get_gps_data_by_mac ===")
                gps_data = await ctx.get_gps_data_by_mac(hours=12)
                print(f"Found {len(gps_data)} GPS records")

                # Test get_imu_data_by_mac
                print("\n=== Testing get_imu_data_by_mac ===")
                imu_data = await ctx.get_imu_data_by_mac(hours=6)
                print(f"Found {len(imu_data)} IMU records")

                # Test get_door_detections_by_mac
                print("\n=== Testing get_door_detections_by_mac ===")
                detections = await ctx.get_door_detections_by_mac(hours=24)
                print(f"Found {len(detections)} door detection records")

        except Exception as e:
            print(f"Test failed: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(test())
