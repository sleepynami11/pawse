"""
MyCatsHome Shared Types for Python

This module provides Pydantic models that match the TypeScript shared-types package.
These types ensure consistency between the mobile app, worker API, and agent service.

Generated to match: @mycatshome/shared-types
"""

from .models import (
    # Common
    SyncMetadata,
    PaginationParams,
    PaginationMeta,

    # User
    User,
    UserSettings,
    NotificationSettings,

    # Cat
    Cat,
    CatWithHealth,
    CatCreateInput,
    CatUpdateInput,

    # Device
    DeviceType,
    DeviceStatus,
    DoorMode,
    DoorStatus,
    CollarStatus,
    Device,
    SmartDoor,
    HealthCollar,
    DoorConfig,
    CollarConfig,
    DeviceWithDetails,

    # Alert
    AlertType,
    AlertSeverity,
    Alert,
    AlertWithDetails,

    # Health
    HealthStatus,
    ActivityLevel,
    SleepQuality,
    HealthSummary,
    HeartRateData,
    BcgData,

    # Detection
    CarryStatus,
    Direction,
    RecentDetection,
    CatDoorEvent,
    Geofence,
    GeofenceCreateInput,
    GeofenceUpdateInput,

    # Chat
    ChatConversation,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    AISuggestion,
    HealthAnalysisRequest,

    # Task
    TaskType,
    TaskPriority,
    TaskStatus,
    Task,
    TaskWithCat,
    TaskCreateInput,
    TaskUpdateInput,
)

from .api import (
    # Response types
    ApiResponse,
    ApiErrorResponse,
    ErrorDetail,
    ERROR_CODES,
    # Helper functions
    create_success_response,
    create_error_response,
    get_error_code_for_status,
)

__all__ = [
    # Common
    "SyncMetadata",
    "PaginationParams",
    "PaginationMeta",

    # User
    "User",
    "UserSettings",
    "NotificationSettings",

    # Cat
    "Cat",
    "CatWithHealth",
    "CatCreateInput",
    "CatUpdateInput",

    # Device
    "DeviceType",
    "DeviceStatus",
    "DoorMode",
    "DoorStatus",
    "CollarStatus",
    "Device",
    "SmartDoor",
    "HealthCollar",
    "DoorConfig",
    "CollarConfig",
    "DeviceWithDetails",

    # Alert
    "AlertType",
    "AlertSeverity",
    "Alert",
    "AlertWithDetails",

    # Health
    "HealthStatus",
    "ActivityLevel",
    "SleepQuality",
    "HealthSummary",
    "HeartRateData",
    "BcgData",

    # Detection
    "CarryStatus",
    "Direction",
    "RecentDetection",
    "CatDoorEvent",
    "Geofence",
    "GeofenceCreateInput",
    "GeofenceUpdateInput",

    # Chat
    "ChatConversation",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "AISuggestion",
    "HealthAnalysisRequest",

    # Task
    "TaskType",
    "TaskPriority",
    "TaskStatus",
    "Task",
    "TaskWithCat",
    "TaskCreateInput",
    "TaskUpdateInput",

    # API Response
    "ApiResponse",
    "ApiErrorResponse",
    "ErrorDetail",
    "ERROR_CODES",
    "create_success_response",
    "create_error_response",
    "get_error_code_for_status",
]
