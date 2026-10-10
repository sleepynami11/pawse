"""
Cloudflare D1 Database Async Client

This module provides async functions to interact with Cloudflare D1 SQL database
via REST API.

Environment Variables Required:
    - D1_DATABASE_ID: The D1 database ID
    - CLOUDFLARE_API_TOKEN: Cloudflare API token with D1 permissions
    - CLOUDFLARE_ACCOUNT_ID: Cloudflare account ID

Test Mode:
    Set TEST_MODE=true to use mock data instead of real D1 database.

Usage Example:
    import asyncio
    from utils.d1_client import execute_query, execute_batch

    async def main():
        # Single query
        result = await execute_query(
            "SELECT * FROM users WHERE id = ?",
            [123]
        )

        # Batch queries
        results = await execute_batch([
            {"sql": "INSERT INTO logs (message) VALUES (?)", "params": ["log1"]},
            {"sql": "INSERT INTO logs (message) VALUES (?)", "params": ["log2"]}
        ])

    asyncio.run(main())
"""

import httpx
import os
import logging

logger = logging.getLogger(__name__)

# Test mode flag
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

if TEST_MODE:
    logger.info("[D1 Client] Running in TEST_MODE - using mock data")
    from utils.mock_data import MockQueryRouter

# Load environment variables
D1_DATABASE_ID = os.getenv("D1_DATABASE_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")


async def execute_query(sql: str, params: list = None) -> dict:
    """
    Execute a single SQL query on Cloudflare D1 database.

    Args:
        sql: SQL query string (supports parameterized queries with ?)
        params: List of parameters for parameterized query (optional)

    Returns:
        dict: Query result containing:
            - success (bool): Whether query succeeded
            - results (list): Query results
            - meta (dict): Query metadata (duration, rows affected, etc.)

    Raises:
        httpx.HTTPError: If API request fails
        ValueError: If required environment variables are missing

    Example:
        result = await execute_query(
            "SELECT * FROM users WHERE id = ?",
            [123]
        )
    """
    # TEST_MODE: Return mock data instead of calling real D1
    if TEST_MODE:
        logger.info(f"[TEST_MODE] Routing query to mock: {sql[:80]}...")
        return MockQueryRouter.route_query(sql, params)

    if not all([D1_DATABASE_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID]):
        error_msg = "Missing required environment variables: D1_DATABASE_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID"
        logger.error(error_msg)
        raise ValueError(error_msg)

    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/d1/database/{D1_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {"sql": sql}
    if params:
        payload["params"] = params

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Executing D1 query: {sql[:100]}...")
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()

            result = response.json()
            logger.info(f"D1 query executed successfully")
            return result

    except httpx.HTTPError as e:
        logger.error(f"D1 query failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in D1 query: {str(e)}")
        raise


async def execute_batch(queries: list[dict]) -> list[dict]:
    """
    Execute multiple SQL queries in a batch on Cloudflare D1 database.

    Args:
        queries: List of query dictionaries, each containing:
            - sql (str): SQL query string
            - params (list, optional): Query parameters

    Returns:
        list[dict]: List of query results, one per query

    Raises:
        httpx.HTTPError: If API request fails
        ValueError: If required environment variables are missing

    Example:
        results = await execute_batch([
            {"sql": "INSERT INTO logs (message) VALUES (?)", "params": ["log1"]},
            {"sql": "UPDATE users SET active = ? WHERE id = ?", "params": [True, 123]}
        ])
    """
    # TEST_MODE: Return mock data for each query
    if TEST_MODE:
        logger.info(f"[TEST_MODE] Routing batch of {len(queries)} queries to mock")
        results = []
        for q in queries:
            result = MockQueryRouter.route_query(q.get("sql", ""), q.get("params"))
            results.append(result)
        return results

    if not all([D1_DATABASE_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID]):
        error_msg = "Missing required environment variables: D1_DATABASE_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID"
        logger.error(error_msg)
        raise ValueError(error_msg)

    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/d1/database/{D1_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Executing D1 batch with {len(queries)} queries")
            response = await client.post(url, json=queries, headers=headers, timeout=60.0)
            response.raise_for_status()

            results = response.json()
            logger.info(f"D1 batch executed successfully")
            return results

    except httpx.HTTPError as e:
        logger.error(f"D1 batch failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in D1 batch: {str(e)}")
        raise


async def query_collar_activity(cat_id: int = None, device_id: int = None, activity_type: str = None, time_range: tuple = None) -> dict:
    """
    Query collar activity logs with optional filters.

    Args:
        cat_id: Filter by cat ID (optional)
        device_id: Filter by collar device ID (optional)
        activity_type: Filter by activity type (optional)
        time_range: Tuple of (start_timestamp, end_timestamp) (optional)

    Returns:
        dict: Query result with activity log records

    Example:
        result = await query_collar_activity(cat_id=1, activity_type="walking")
    """
    sql = "SELECT * FROM collar_activity_logs WHERE 1=1"
    params = []

    if cat_id is not None:
        sql += " AND cat_id = ?"
        params.append(cat_id)
    if device_id is not None:
        sql += " AND collar_device_id = ?"
        params.append(device_id)
    if activity_type is not None:
        sql += " AND activity_type = ?"
        params.append(activity_type)
    if time_range is not None:
        sql += " AND timestamp BETWEEN ? AND ?"
        params.extend(time_range)

    sql += " ORDER BY timestamp DESC"
    return await execute_query(sql, params)


async def query_collar_outdoor(cat_id: int = None, device_id: int = None, is_outdoor: int = None, time_range: tuple = None) -> dict:
    """
    Query collar outdoor logs with optional filters.

    Args:
        cat_id: Filter by cat ID (optional)
        device_id: Filter by collar device ID (optional)
        is_outdoor: Filter by outdoor status (1=outdoor, 0=indoor) (optional)
        time_range: Tuple of (start_timestamp, end_timestamp) (optional)

    Returns:
        dict: Query result with outdoor log records

    Example:
        result = await query_collar_outdoor(cat_id=1, is_outdoor=1)
    """
    sql = "SELECT * FROM collar_outdoor_logs WHERE 1=1"
    params = []

    if cat_id is not None:
        sql += " AND cat_id = ?"
        params.append(cat_id)
    if device_id is not None:
        sql += " AND collar_device_id = ?"
        params.append(device_id)
    if is_outdoor is not None:
        sql += " AND is_outdoor = ?"
        params.append(is_outdoor)
    if time_range is not None:
        sql += " AND started_at BETWEEN ? AND ?"
        params.extend(time_range)

    sql += " ORDER BY started_at DESC"
    return await execute_query(sql, params)


async def query_collar_bcg(cat_id: int = None, device_id: int = None, anomaly_flag: int = None, time_range: tuple = None) -> dict:
    """
    Query collar BCG (heart rate) logs with optional filters.

    Args:
        cat_id: Filter by cat ID (optional)
        device_id: Filter by collar device ID (optional)
        anomaly_flag: Filter by anomaly flag (1=anomaly detected, 0=normal) (optional)
        time_range: Tuple of (start_timestamp, end_timestamp) (optional)

    Returns:
        dict: Query result with BCG log records

    Example:
        result = await query_collar_bcg(cat_id=1, anomaly_flag=1)
    """
    sql = "SELECT * FROM collar_bcg_logs WHERE 1=1"
    params = []

    if cat_id is not None:
        sql += " AND cat_id = ?"
        params.append(cat_id)
    if device_id is not None:
        sql += " AND collar_device_id = ?"
        params.append(device_id)
    if anomaly_flag is not None:
        sql += " AND anomaly_flag = ?"
        params.append(anomaly_flag)
    if time_range is not None:
        sql += " AND timestamp BETWEEN ? AND ?"
        params.extend(time_range)

    sql += " ORDER BY timestamp DESC"
    return await execute_query(sql, params)


async def query_cat_door_passage(cat_id: int = None, device_id: int = None, direction: str = None, time_range: tuple = None) -> dict:
    """
    Query cat door passage logs with optional filters.

    Args:
        cat_id: Filter by cat ID (optional)
        device_id: Filter by cat door device ID (optional)
        direction: Filter by direction (e.g., "in", "out") (optional)
        time_range: Tuple of (start_timestamp, end_timestamp) (optional)

    Returns:
        dict: Query result with passage log records

    Example:
        result = await query_cat_door_passage(cat_id=1, direction="in")
    """
    sql = "SELECT * FROM cat_door_passage_logs WHERE 1=1"
    params = []

    if cat_id is not None:
        sql += " AND cat_id = ?"
        params.append(cat_id)
    if device_id is not None:
        sql += " AND cat_door_device_id = ?"
        params.append(device_id)
    if direction is not None:
        sql += " AND direction = ?"
        params.append(direction)
    if time_range is not None:
        sql += " AND timestamp BETWEEN ? AND ?"
        params.extend(time_range)

    sql += " ORDER BY timestamp DESC"
    return await execute_query(sql, params)


async def query_cat_door_expression(passage_log_id: int = None, cat_id: int = None, pain_score_min: float = None) -> dict:
    """
    Query cat door expression logs with optional filters.

    Args:
        passage_log_id: Filter by passage log ID (optional)
        cat_id: Filter by cat ID (optional)
        pain_score_min: Filter by minimum pain score (optional)

    Returns:
        dict: Query result with expression log records

    Example:
        result = await query_cat_door_expression(cat_id=1, pain_score_min=5.0)
    """
    sql = "SELECT * FROM cat_door_expression_logs WHERE 1=1"
    params = []

    if passage_log_id is not None:
        sql += " AND passage_log_id = ?"
        params.append(passage_log_id)
    if cat_id is not None:
        sql += " AND cat_id = ?"
        params.append(cat_id)
    if pain_score_min is not None:
        sql += " AND pain_score >= ?"
        params.append(pain_score_min)

    sql += " ORDER BY timestamp DESC"
    return await execute_query(sql, params)


async def query_users(user_id: int = None, email: str = None) -> dict:
    """
    Query users table with optional filters.

    Args:
        user_id: Filter by user ID (optional)
        email: Filter by email address (optional)

    Returns:
        dict: Query result with user records

    Example:
        result = await query_users(email="user@example.com")
    """
    sql = "SELECT * FROM users WHERE 1=1"
    params = []

    if user_id is not None:
        sql += " AND id = ?"
        params.append(user_id)
    if email is not None:
        sql += " AND email = ?"
        params.append(email)

    sql += " ORDER BY created_at DESC"
    return await execute_query(sql, params)


async def query_collar_devices(device_serial: str = None, cat_id: int = None) -> dict:
    """
    Query collar devices table with optional filters.

    Args:
        device_serial: Filter by device serial number (optional)
        cat_id: Filter by cat ID (optional)

    Returns:
        dict: Query result with collar device records

    Example:
        result = await query_collar_devices(cat_id=1)
    """
    sql = "SELECT * FROM collar_devices WHERE 1=1"
    params = []

    if device_serial is not None:
        sql += " AND device_serial = ?"
        params.append(device_serial)
    if cat_id is not None:
        sql += " AND cat_id = ?"
        params.append(cat_id)

    sql += " ORDER BY created_at DESC"
    return await execute_query(sql, params)


async def query_cat_door_devices(device_serial: str = None, user_id: int = None) -> dict:
    """
    Query cat door devices table with optional filters.

    Args:
        device_serial: Filter by device serial number (optional)
        user_id: Filter by user ID (optional)

    Returns:
        dict: Query result with cat door device records

    Example:
        result = await query_cat_door_devices(user_id=1)
    """
    sql = "SELECT * FROM cat_door_devices WHERE 1=1"
    params = []

    if device_serial is not None:
        sql += " AND device_serial = ?"
        params.append(device_serial)
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)

    sql += " ORDER BY created_at DESC"
    return await execute_query(sql, params)


# =========================================
# User-scoped query functions
# All data access based on user_id
# =========================================

async def get_user_cats(user_id: int) -> dict:
    """
    Get all cats owned by a user.

    Args:
        user_id: User ID

    Returns:
        dict: Query result with cat records including:
            - id, name, breed, age, medical_history_json
            - collar_device_id, created_at

    Example:
        result = await get_user_cats(user_id=1)
        cats = result.get('result', [{}])[0].get('results', [])
    """
    sql = """
        SELECT c.*, cd.device_serial as collar_serial, cd.battery_level as collar_battery
        FROM cats c
        LEFT JOIN collar_devices cd ON c.collar_device_id = cd.id
        WHERE c.user_id = ?
        ORDER BY c.created_at DESC
    """
    return await execute_query(sql, [user_id])


async def get_user_profile(user_id: int) -> dict:
    """
    Get user profile information.

    Args:
        user_id: User ID

    Returns:
        dict: Query result with user profile

    Example:
        result = await get_user_profile(user_id=1)
    """
    sql = "SELECT * FROM users WHERE id = ?"
    return await execute_query(sql, [user_id])


async def get_user_devices(user_id: int) -> dict:
    """
    Get all devices (cat doors) owned by a user.

    Args:
        user_id: User ID

    Returns:
        dict: Query result with cat door device records

    Example:
        result = await get_user_devices(user_id=1)
    """
    sql = """
        SELECT * FROM cat_door_devices
        WHERE user_id = ?
        ORDER BY created_at DESC
    """
    return await execute_query(sql, [user_id])


async def get_user_cat_health_summary(user_id: int, cat_id: int = None, days: int = 7) -> dict:
    """
    Get health summary for user's cat(s) over specified days.

    Args:
        user_id: User ID (required for access control)
        cat_id: Specific cat ID (optional, if None returns all user's cats)
        days: Number of days to look back (default 7)

    Returns:
        dict: Query result with aggregated health data including:
            - BCG logs (heart rate, HRV, respiratory)
            - Activity logs
            - Expression logs (mood, pain scores)

    Example:
        result = await get_user_cat_health_summary(user_id=1, cat_id=2, days=7)
    """
    # First verify cat belongs to user
    if cat_id:
        verify_sql = "SELECT id FROM cats WHERE id = ? AND user_id = ?"
        verify_result = await execute_query(verify_sql, [cat_id, user_id])
        if not verify_result.get('result', [{}])[0].get('results'):
            return {"error": "Cat not found or access denied", "results": []}

    # Build query for health summary
    sql = """
        SELECT
            c.id as cat_id,
            c.name as cat_name,
            -- BCG averages
            AVG(bcg.heart_rate_bpm) as avg_heart_rate,
            AVG(bcg.hrv_ms) as avg_hrv,
            AVG(bcg.respiratory_rate) as avg_respiratory_rate,
            SUM(CASE WHEN bcg.anomaly_flag = 1 THEN 1 ELSE 0 END) as bcg_anomaly_count,
            -- Activity totals
            SUM(CASE WHEN act.activity_type = 'steps' THEN act.value ELSE 0 END) as total_steps,
            SUM(CASE WHEN act.activity_type = 'active_minutes' THEN act.value ELSE 0 END) as total_active_minutes,
            -- Expression analysis
            AVG(expr.pain_score) as avg_pain_score,
            COUNT(expr.id) as expression_count
        FROM cats c
        LEFT JOIN collar_bcg_logs bcg ON c.id = bcg.cat_id
            AND bcg.timestamp >= datetime('now', '-' || ? || ' days')
        LEFT JOIN collar_activity_logs act ON c.id = act.cat_id
            AND act.timestamp >= datetime('now', '-' || ? || ' days')
        LEFT JOIN cat_door_expression_logs expr ON c.id = expr.cat_id
            AND expr.timestamp >= datetime('now', '-' || ? || ' days')
        WHERE c.user_id = ?
    """
    params = [days, days, days, user_id]

    if cat_id:
        sql += " AND c.id = ?"
        params.append(cat_id)

    sql += " GROUP BY c.id, c.name"

    return await execute_query(sql, params)


async def get_user_cat_activity_logs(user_id: int, cat_id: int, limit: int = 100, time_range: tuple = None) -> dict:
    """
    Get activity logs for a specific cat (with user access control).

    Args:
        user_id: User ID (required for access control)
        cat_id: Cat ID
        limit: Maximum number of records (default 100)
        time_range: Tuple of (start_timestamp, end_timestamp) (optional)

    Returns:
        dict: Query result with activity log records

    Example:
        result = await get_user_cat_activity_logs(user_id=1, cat_id=2, limit=50)
    """
    # Join with cats to verify ownership
    sql = """
        SELECT cal.*
        FROM collar_activity_logs cal
        JOIN cats c ON cal.cat_id = c.id
        WHERE c.user_id = ? AND cal.cat_id = ?
    """
    params = [user_id, cat_id]

    if time_range:
        sql += " AND cal.timestamp BETWEEN ? AND ?"
        params.extend(time_range)

    sql += f" ORDER BY cal.timestamp DESC LIMIT {limit}"

    return await execute_query(sql, params)


async def get_user_cat_bcg_logs(user_id: int, cat_id: int, limit: int = 100, anomaly_only: bool = False) -> dict:
    """
    Get BCG (heart rate) logs for a specific cat (with user access control).

    Args:
        user_id: User ID (required for access control)
        cat_id: Cat ID
        limit: Maximum number of records (default 100)
        anomaly_only: If True, only return anomaly records

    Returns:
        dict: Query result with BCG log records

    Example:
        result = await get_user_cat_bcg_logs(user_id=1, cat_id=2, anomaly_only=True)
    """
    sql = """
        SELECT bcg.*
        FROM collar_bcg_logs bcg
        JOIN cats c ON bcg.cat_id = c.id
        WHERE c.user_id = ? AND bcg.cat_id = ?
    """
    params = [user_id, cat_id]

    if anomaly_only:
        sql += " AND bcg.anomaly_flag = 1"

    sql += f" ORDER BY bcg.timestamp DESC LIMIT {limit}"

    return await execute_query(sql, params)


async def get_user_cat_outdoor_logs(user_id: int, cat_id: int, limit: int = 50) -> dict:
    """
    Get outdoor logs for a specific cat (with user access control).

    Args:
        user_id: User ID (required for access control)
        cat_id: Cat ID
        limit: Maximum number of records (default 50)

    Returns:
        dict: Query result with outdoor log records

    Example:
        result = await get_user_cat_outdoor_logs(user_id=1, cat_id=2)
    """
    sql = """
        SELECT col.*
        FROM collar_outdoor_logs col
        JOIN cats c ON col.cat_id = c.id
        WHERE c.user_id = ? AND col.cat_id = ?
        ORDER BY col.started_at DESC
        LIMIT ?
    """
    return await execute_query(sql, [user_id, cat_id, limit])


async def get_user_cat_door_passages(user_id: int, cat_id: int = None, limit: int = 50) -> dict:
    """
    Get cat door passage logs for user's cats.

    Args:
        user_id: User ID (required for access control)
        cat_id: Specific cat ID (optional)
        limit: Maximum number of records (default 50)

    Returns:
        dict: Query result with passage log records

    Example:
        result = await get_user_cat_door_passages(user_id=1, cat_id=2)
    """
    sql = """
        SELECT cdp.*, c.name as cat_name, cdd.location as door_location
        FROM cat_door_passage_logs cdp
        JOIN cats c ON cdp.cat_id = c.id
        JOIN cat_door_devices cdd ON cdp.cat_door_device_id = cdd.id
        WHERE c.user_id = ?
    """
    params = [user_id]

    if cat_id:
        sql += " AND cdp.cat_id = ?"
        params.append(cat_id)

    sql += f" ORDER BY cdp.timestamp DESC LIMIT {limit}"

    return await execute_query(sql, params)


async def get_user_cat_expression_logs(user_id: int, cat_id: int = None, limit: int = 50, pain_threshold: float = None) -> dict:
    """
    Get expression analysis logs for user's cats.

    Args:
        user_id: User ID (required for access control)
        cat_id: Specific cat ID (optional)
        limit: Maximum number of records (default 50)
        pain_threshold: Minimum pain score to filter (optional)

    Returns:
        dict: Query result with expression log records including mood, pain scores

    Example:
        result = await get_user_cat_expression_logs(user_id=1, pain_threshold=5.0)
    """
    sql = """
        SELECT cdel.*, c.name as cat_name
        FROM cat_door_expression_logs cdel
        JOIN cats c ON cdel.cat_id = c.id
        WHERE c.user_id = ?
    """
    params = [user_id]

    if cat_id:
        sql += " AND cdel.cat_id = ?"
        params.append(cat_id)

    if pain_threshold is not None:
        sql += " AND cdel.pain_score >= ?"
        params.append(pain_threshold)

    sql += f" ORDER BY cdel.timestamp DESC LIMIT {limit}"

    return await execute_query(sql, params)


async def get_user_alerts(user_id: int, cat_id: int = None, limit: int = 50, unread_only: bool = False) -> dict:
    """
    Get alert logs for user's cats.

    Args:
        user_id: User ID (required for access control)
        cat_id: Specific cat ID (optional)
        limit: Maximum number of records (default 50)
        unread_only: If True, only return unsent notifications

    Returns:
        dict: Query result with alert log records

    Example:
        result = await get_user_alerts(user_id=1, unread_only=True)
    """
    sql = """
        SELECT al.*, c.name as cat_name
        FROM alert_logs al
        JOIN cats c ON al.cat_id = c.id
        WHERE c.user_id = ?
    """
    params = [user_id]

    if cat_id:
        sql += " AND al.cat_id = ?"
        params.append(cat_id)

    if unread_only:
        sql += " AND al.notification_sent = 0"

    sql += f" ORDER BY al.timestamp DESC LIMIT {limit}"

    return await execute_query(sql, params)


async def get_user_vision_logs(user_id: int, cat_id: int = None, limit: int = 50) -> dict:
    """
    Get vision analysis logs for user's cats.

    Args:
        user_id: User ID (required for access control)
        cat_id: Specific cat ID (optional)
        limit: Maximum number of records (default 50)

    Returns:
        dict: Query result with vision log records including image URLs and analysis results

    Example:
        result = await get_user_vision_logs(user_id=1, cat_id=2)
    """
    sql = """
        SELECT vl.*, c.name as cat_name
        FROM vision_logs vl
        JOIN cats c ON vl.cat_id = c.id
        WHERE c.user_id = ?
    """
    params = [user_id]

    if cat_id:
        sql += " AND vl.cat_id = ?"
        params.append(cat_id)

    sql += f" ORDER BY vl.timestamp DESC LIMIT {limit}"

    return await execute_query(sql, params)


async def get_user_conversation_sessions(user_id: int, limit: int = 10) -> dict:
    """
    Get conversation sessions for a user.

    Args:
        user_id: User ID
        limit: Maximum number of sessions (default 10)

    Returns:
        dict: Query result with conversation session records

    Example:
        result = await get_user_conversation_sessions(user_id=1)
    """
    sql = """
        SELECT * FROM conversation_sessions
        WHERE user_id = ?
        ORDER BY updated_at DESC
        LIMIT ?
    """
    return await execute_query(sql, [user_id, limit])


async def get_user_id_from_cat(cat_id: int) -> int:
    """
    Get user_id from cat_id (for webhook flows).

    Args:
        cat_id: Cat ID

    Returns:
        int: User ID or None if not found

    Example:
        user_id = await get_user_id_from_cat(cat_id=2)
    """
    sql = "SELECT user_id FROM cats WHERE id = ?"
    result = await execute_query(sql, [cat_id])

    try:
        results = result.get('result', [{}])[0].get('results', [])
        if results:
            return results[0].get('user_id')
    except (IndexError, KeyError):
        pass

    return None


async def get_user_full_context(user_id: int) -> dict:
    """
    Get complete user context including profile, cats, devices, and recent activity.
    Useful for building conversation context.

    Args:
        user_id: User ID

    Returns:
        dict: Complete user context with:
            - user: User profile
            - cats: List of cats with their devices
            - devices: Cat door devices
            - recent_alerts: Recent alerts
            - health_summary: Health summary for all cats

    Example:
        context = await get_user_full_context(user_id=1)
    """
    # Execute all queries in parallel-like fashion
    user_result = await get_user_profile(user_id)
    cats_result = await get_user_cats(user_id)
    devices_result = await get_user_devices(user_id)
    alerts_result = await get_user_alerts(user_id, limit=10)
    health_result = await get_user_cat_health_summary(user_id, days=7)

    # Extract results
    def extract_results(result):
        try:
            return result.get('result', [{}])[0].get('results', [])
        except (IndexError, KeyError):
            return []

    return {
        "user": extract_results(user_result)[0] if extract_results(user_result) else None,
        "cats": extract_results(cats_result),
        "devices": extract_results(devices_result),
        "recent_alerts": extract_results(alerts_result),
        "health_summary": extract_results(health_result)
    }


if __name__ == "__main__":
    import asyncio

    async def test():
        """Test D1 client with example queries"""
        try:
            # Test single query
            result = await execute_query("SELECT 1 as test")
            print("Single query result:", result)

            # Test batch queries
            batch_results = await execute_batch([
                {"sql": "SELECT 1 as test1"},
                {"sql": "SELECT 2 as test2"}
            ])
            print("Batch query results:", batch_results)

            # Test new query methods
            print("\nTesting new query methods...")
            collar_activity = await query_collar_activity(cat_id=1)
            print("Collar activity query:", collar_activity)

            # Test user-scoped queries
            print("\nTesting user-scoped queries...")
            user_cats = await get_user_cats(user_id=1)
            print("User cats:", user_cats)

            user_context = await get_user_full_context(user_id=1)
            print("User full context:", user_context)

        except Exception as e:
            print(f"Test failed: {e}")

    asyncio.run(test())
