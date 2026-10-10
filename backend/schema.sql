-- Cat IoT Agent System Database Schema
-- This schema defines the core data structures for IoT sensor logs, vision analysis, device status, and cat profiles

-- Table: users
-- Stores user profile and notification preferences
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT,
    notification_preferences TEXT,  -- JSON string for notification settings
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: cats
-- Stores cat profile information and medical history
CREATE TABLE cats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    breed TEXT,
    age INTEGER,
    medical_history_json TEXT,  -- JSON string containing medical records, allergies, etc.
    user_id INTEGER,            -- Owner/user association
    collar_device_id INTEGER,   -- Associated collar device
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (collar_device_id) REFERENCES collar_devices(id)
);

-- Table: iot_logs
-- Stores real-time sensor data from IoT devices monitoring cat behavior
CREATE TABLE iot_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cat_id INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    sensor_type TEXT NOT NULL,  -- e.g., motion, temperature, weight, proximity
    value REAL NOT NULL,         -- Sensor reading value
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    anomaly_flag INTEGER DEFAULT 0,  -- 0 = normal, 1 = anomaly detected
    FOREIGN KEY (cat_id) REFERENCES cats(id)
);

-- Table: vision_logs
-- Stores AI vision analysis results for cat images/videos
CREATE TABLE vision_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cat_id INTEGER NOT NULL,
    image_url TEXT NOT NULL,           -- R2 storage URL for the image/video
    analysis_result TEXT,               -- JSON string with vision analysis output
    confidence REAL,                    -- Confidence score (0.0 - 1.0)
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cat_id) REFERENCES cats(id)
);

-- Table: device_status
-- Tracks IoT device connectivity and health status
CREATE TABLE device_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL UNIQUE,
    cat_id INTEGER,                     -- Associated cat (NULL if unassigned)
    online_status INTEGER DEFAULT 1,    -- 1 = online, 0 = offline
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    battery_level INTEGER,              -- Battery percentage (0-100)
    FOREIGN KEY (cat_id) REFERENCES cats(id)
);

-- Table: collar_devices
-- Stores collar device information (refactored from device_status)
CREATE TABLE collar_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_serial TEXT NOT NULL UNIQUE,
    cat_id INTEGER,
    firmware_version TEXT,
    battery_level INTEGER,              -- Battery percentage (0-100)
    online_status INTEGER DEFAULT 1,    -- 1 = online, 0 = offline
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cat_id) REFERENCES cats(id)
);

-- Table: cat_door_devices
-- Stores cat door device information
CREATE TABLE cat_door_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_serial TEXT NOT NULL UNIQUE,
    user_id INTEGER,
    location TEXT,
    firmware_version TEXT,
    online_status INTEGER DEFAULT 1,    -- 1 = online, 0 = offline
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Table: collar_activity_logs
-- Stores activity data from collar devices (refactored from iot_logs)
CREATE TABLE collar_activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collar_device_id INTEGER NOT NULL,
    cat_id INTEGER NOT NULL,
    activity_type TEXT NOT NULL,        -- e.g., steps, active_minutes, movement
    value REAL NOT NULL,
    unit TEXT,                          -- e.g., count, minutes, meters
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collar_device_id) REFERENCES collar_devices(id),
    FOREIGN KEY (cat_id) REFERENCES cats(id)
);

-- Table: collar_outdoor_logs
-- Stores outdoor status tracking from collar devices
CREATE TABLE collar_outdoor_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collar_device_id INTEGER NOT NULL,
    cat_id INTEGER NOT NULL,
    is_outdoor INTEGER DEFAULT 0,       -- 0 = indoor, 1 = outdoor
    location_lat REAL,
    location_lng REAL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    FOREIGN KEY (collar_device_id) REFERENCES collar_devices(id),
    FOREIGN KEY (cat_id) REFERENCES cats(id)
);

-- Table: collar_bcg_logs
-- Stores BCG (Ballistocardiography) heart rate data from collar devices
CREATE TABLE collar_bcg_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collar_device_id INTEGER NOT NULL,
    cat_id INTEGER NOT NULL,
    heart_rate_bpm INTEGER,
    hrv_ms REAL,                        -- Heart rate variability in milliseconds
    respiratory_rate INTEGER,
    anomaly_flag INTEGER DEFAULT 0,     -- 0 = normal, 1 = anomaly detected
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collar_device_id) REFERENCES collar_devices(id),
    FOREIGN KEY (cat_id) REFERENCES cats(id)
);

-- Table: cat_door_passage_logs
-- Stores passage events from cat door devices
CREATE TABLE cat_door_passage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cat_door_device_id INTEGER NOT NULL,
    cat_id INTEGER,
    direction TEXT NOT NULL,            -- 'in' or 'out'
    identification_method TEXT,         -- e.g., rfid, facial, collar_beacon
    identification_confidence REAL,     -- Confidence score (0.0 - 1.0)
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cat_door_device_id) REFERENCES cat_door_devices(id),
    FOREIGN KEY (cat_id) REFERENCES cats(id)
);

-- Table: cat_door_expression_logs
-- Stores facial expression and pain detection analysis from cat door
CREATE TABLE cat_door_expression_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    passage_log_id INTEGER NOT NULL,
    cat_id INTEGER NOT NULL,
    image_url TEXT NOT NULL,            -- R2 storage URL for the captured image
    mood TEXT,                          -- e.g., happy, stressed, neutral
    alertness TEXT,                     -- e.g., alert, drowsy, normal
    pain_score REAL,                    -- Pain level score (0.0 - 10.0)
    pain_indicators TEXT,               -- JSON string with pain indicators
    analysis_result TEXT,               -- JSON string with full analysis
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (passage_log_id) REFERENCES cat_door_passage_logs(id),
    FOREIGN KEY (cat_id) REFERENCES cats(id)
);

-- Indexes for query performance optimization

-- Indexes for users table
CREATE INDEX idx_users_email ON users(email);

-- Indexes for cats table
CREATE INDEX idx_cats_user_id ON cats(user_id);
CREATE INDEX idx_cats_collar_device_id ON cats(collar_device_id);

-- Index on cat_id for iot_logs (frequent queries by cat)
CREATE INDEX idx_iot_logs_cat_id ON iot_logs(cat_id);

-- Index on timestamp for iot_logs (time-series queries)
CREATE INDEX idx_iot_logs_timestamp ON iot_logs(timestamp);

-- Index on cat_id for vision_logs (frequent queries by cat)
CREATE INDEX idx_vision_logs_cat_id ON vision_logs(cat_id);

-- Index on timestamp for vision_logs (time-series queries)
CREATE INDEX idx_vision_logs_timestamp ON vision_logs(timestamp);

-- Index on device_id for device_status (device lookup)
CREATE INDEX idx_device_status_device_id ON device_status(device_id);

-- Indexes for collar_devices table
CREATE INDEX idx_collar_devices_cat_id ON collar_devices(cat_id);
CREATE INDEX idx_collar_devices_device_serial ON collar_devices(device_serial);
CREATE INDEX idx_collar_devices_online_status ON collar_devices(online_status);

-- Indexes for cat_door_devices table
CREATE INDEX idx_cat_door_devices_user_id ON cat_door_devices(user_id);
CREATE INDEX idx_cat_door_devices_device_serial ON cat_door_devices(device_serial);

-- Indexes for collar_activity_logs table
CREATE INDEX idx_collar_activity_logs_collar_device_id ON collar_activity_logs(collar_device_id);
CREATE INDEX idx_collar_activity_logs_cat_id ON collar_activity_logs(cat_id);
CREATE INDEX idx_collar_activity_logs_timestamp ON collar_activity_logs(timestamp);

-- Indexes for collar_outdoor_logs table
CREATE INDEX idx_collar_outdoor_logs_collar_device_id ON collar_outdoor_logs(collar_device_id);
CREATE INDEX idx_collar_outdoor_logs_cat_id ON collar_outdoor_logs(cat_id);
CREATE INDEX idx_collar_outdoor_logs_started_at ON collar_outdoor_logs(started_at);

-- Indexes for collar_bcg_logs table
CREATE INDEX idx_collar_bcg_logs_collar_device_id ON collar_bcg_logs(collar_device_id);
CREATE INDEX idx_collar_bcg_logs_cat_id ON collar_bcg_logs(cat_id);
CREATE INDEX idx_collar_bcg_logs_timestamp ON collar_bcg_logs(timestamp);
CREATE INDEX idx_collar_bcg_logs_anomaly_flag ON collar_bcg_logs(anomaly_flag);

-- Indexes for cat_door_passage_logs table
CREATE INDEX idx_cat_door_passage_logs_cat_door_device_id ON cat_door_passage_logs(cat_door_device_id);
CREATE INDEX idx_cat_door_passage_logs_cat_id ON cat_door_passage_logs(cat_id);
CREATE INDEX idx_cat_door_passage_logs_timestamp ON cat_door_passage_logs(timestamp);

-- Indexes for cat_door_expression_logs table
CREATE INDEX idx_cat_door_expression_logs_passage_log_id ON cat_door_expression_logs(passage_log_id);
CREATE INDEX idx_cat_door_expression_logs_cat_id ON cat_door_expression_logs(cat_id);
CREATE INDEX idx_cat_door_expression_logs_timestamp ON cat_door_expression_logs(timestamp);

-- Table: alert_logs
-- Stores alert history for emergency and device offline notifications
CREATE TABLE alert_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cat_id INTEGER NOT NULL,
    alert_type TEXT NOT NULL,            -- e.g., emergency, device_offline, warning
    alert_title TEXT,                    -- Short alert title
    alert_body TEXT,                     -- Detailed alert message
    anomaly_details TEXT,                -- JSON string with anomaly specifics
    notification_sent INTEGER DEFAULT 0, -- 1 = sent, 0 = failed
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cat_id) REFERENCES cats(id)
);

-- Index on cat_id for alert_logs (frequent queries by cat)
CREATE INDEX idx_alert_logs_cat_id ON alert_logs(cat_id);

-- Index on timestamp for alert_logs (time-series queries)
CREATE INDEX idx_alert_logs_timestamp ON alert_logs(timestamp);

-- Table: user_devices
-- Stores user device tokens for push notifications
CREATE TABLE user_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cat_id INTEGER NOT NULL,
    device_token TEXT NOT NULL,          -- APNs/FCM device token
    platform TEXT NOT NULL,              -- 'ios' or 'android'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cat_id) REFERENCES cats(id)
);

-- Index on cat_id for user_devices
CREATE INDEX idx_user_devices_cat_id ON user_devices(cat_id);

-- Table: conversation_sessions
-- Stores multi-turn conversation history and context per user/session
CREATE TABLE conversation_sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    history TEXT,                     -- JSON array of dialog turns
    context TEXT,                     -- JSON object for resolved entities/context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Indexes for conversation_sessions
CREATE INDEX idx_conversation_sessions_user_id ON conversation_sessions(user_id);
CREATE INDEX idx_conversation_sessions_expires_at ON conversation_sessions(expires_at);

-- =========================================
-- Composite indexes for performance optimization
-- (Added based on code review recommendations)
-- =========================================

-- Composite index for collar_activity_logs: frequently queried by cat_id + timestamp
CREATE INDEX IF NOT EXISTS idx_collar_activity_cat_ts ON collar_activity_logs(cat_id, timestamp);

-- Composite index for collar_outdoor_logs: frequently queried by cat_id + started_at
CREATE INDEX IF NOT EXISTS idx_collar_outdoor_cat_ts ON collar_outdoor_logs(cat_id, started_at);

-- Composite index for collar_bcg_logs: frequently queried by cat_id + timestamp
CREATE INDEX IF NOT EXISTS idx_collar_bcg_cat_ts ON collar_bcg_logs(cat_id, timestamp);

-- Composite index for cat_door_passage_logs: frequently queried by cat_id + timestamp
CREATE INDEX IF NOT EXISTS idx_passage_cat_ts ON cat_door_passage_logs(cat_id, timestamp);

-- Composite index for cat_door_passage_logs: WebSocket queries by device_id + timestamp
CREATE INDEX IF NOT EXISTS idx_passage_device_ts ON cat_door_passage_logs(cat_door_device_id, timestamp);

-- Composite index for collar_bcg_logs: anomaly queries by cat_id + anomaly_flag + timestamp
CREATE INDEX IF NOT EXISTS idx_collar_bcg_anomaly ON collar_bcg_logs(cat_id, anomaly_flag, timestamp);
