"""
MyCatsHome Domain Models

Pydantic models matching the TypeScript shared-types package.
Ensures type consistency across mobile, worker, and agent services.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# ============================================================================
# COMMON TYPES
# ============================================================================

class SyncMetadata(BaseModel):
    """Metadata for offline sync tracking."""
    syncVersion: int = Field(..., description="Incremental version number for sync")
    lastSyncedAt: Optional[str] = Field(None, description="ISO 8601 timestamp of last sync")
    pendingChanges: bool = Field(False, description="Whether there are local changes pending sync")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(20, ge=1, le=100, description="Items per page")
    sortBy: Optional[str] = Field(None, description="Field to sort by")
    sortOrder: Optional[str] = Field("asc", description="Sort order: asc or desc")


class PaginationMeta(BaseModel):
    """Pagination metadata in API responses."""
    currentPage: int = Field(..., description="Current page number")
    totalPages: int = Field(..., description="Total number of pages")
    totalCount: int = Field(..., description="Total number of items")
    hasNext: bool = Field(..., description="Whether there are more pages")
    hasPrev: bool = Field(..., description="Whether there are previous pages")
    timestamp: Optional[str] = Field(None, description="Response timestamp")


# ============================================================================
# USER MODELS
# ============================================================================

class User(BaseModel):
    """User profile model."""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: Optional[str] = Field(None, description="Display name")
    image: Optional[str] = Field(None, description="Avatar URL")
    createdAt: str = Field(..., description="Account creation timestamp")
    updatedAt: str = Field(..., description="Last update timestamp")


class UserSettings(BaseModel):
    """User settings model."""
    language: str = Field("en", description="Preferred language code")
    timezone: str = Field("UTC", description="User timezone")
    temperatureUnit: str = Field("celsius", description="Temperature unit: celsius or fahrenheit")
    distanceUnit: str = Field("metric", description="Distance unit: metric or imperial")


class NotificationSettings(BaseModel):
    """Notification preferences."""
    pushEnabled: bool = Field(True, description="Global push notification toggle")
    emailEnabled: bool = Field(True, description="Email notification toggle")
    alertTypes: Dict[str, bool] = Field(
        default_factory=lambda: {
            "door_events": True,
            "health_alerts": True,
            "location_alerts": True,
            "task_reminders": True,
        },
        description="Per-alert-type toggles"
    )
    quietHours: Optional[Dict[str, Any]] = Field(
        None,
        description="Quiet hours configuration with start, end, and timezone"
    )


# ============================================================================
# CAT MODELS
# ============================================================================

class Cat(BaseModel):
    """Cat profile model."""
    id: str = Field(..., description="Cat ID")
    userId: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Cat name")
    breed: Optional[str] = Field(None, description="Cat breed")
    birthDate: Optional[str] = Field(None, description="Birth date")
    weight: Optional[float] = Field(None, ge=0, description="Weight in kg")
    color: Optional[str] = Field(None, description="Fur color")
    gender: Optional[str] = Field(None, description="Gender: male, female, or unknown")
    photoUrl: Optional[str] = Field(None, description="Profile photo URL")
    notes: Optional[str] = Field(None, description="Additional notes")
    createdAt: str = Field(..., description="Creation timestamp")
    updatedAt: str = Field(..., description="Last update timestamp")


class CatWithHealth(Cat):
    """Cat with health summary."""
    healthSummary: Optional["HealthSummary"] = Field(None, description="Latest health summary")
    boundDevices: Optional[List["DeviceWithDetails"]] = Field(None, description="Bound devices")


class CatCreateInput(BaseModel):
    """Input for creating a cat."""
    name: str = Field(..., min_length=1, max_length=50, description="Cat name")
    breed: Optional[str] = Field(None, max_length=50, description="Cat breed")
    birthDate: Optional[str] = Field(None, description="Birth date (ISO 8601)")
    weight: Optional[float] = Field(None, ge=0, le=50, description="Weight in kg")
    color: Optional[str] = Field(None, max_length=50, description="Fur color")
    gender: Optional[str] = Field(None, description="Gender: male, female, or unknown")
    photoUrl: Optional[str] = Field(None, description="Profile photo URL")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")


class CatUpdateInput(BaseModel):
    """Input for updating a cat."""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="Cat name")
    breed: Optional[str] = Field(None, max_length=50, description="Cat breed")
    birthDate: Optional[str] = Field(None, description="Birth date (ISO 8601)")
    weight: Optional[float] = Field(None, ge=0, le=50, description="Weight in kg")
    color: Optional[str] = Field(None, max_length=50, description="Fur color")
    gender: Optional[str] = Field(None, description="Gender: male, female, or unknown")
    photoUrl: Optional[str] = Field(None, description="Profile photo URL")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")


# ============================================================================
# DEVICE MODELS
# ============================================================================

class DeviceType(str, Enum):
    """Device type enumeration."""
    SMART_DOOR = "smart_door"
    HEALTH_COLLAR = "health_collar"


class DeviceStatus(str, Enum):
    """Device connection status."""
    ONLINE = "online"
    OFFLINE = "offline"
    CONNECTING = "connecting"
    ERROR = "error"


class DoorMode(str, Enum):
    """Cat door operating mode."""
    AUTO = "auto"
    LOCKED_IN = "locked_in"
    LOCKED_OUT = "locked_out"
    LOCKED_BOTH = "locked_both"
    UNLOCKED = "unlocked"


class DoorStatus(str, Enum):
    """Cat door physical status."""
    OPEN = "open"
    CLOSED = "closed"
    JAMMED = "jammed"


class CollarStatus(str, Enum):
    """Health collar status."""
    ACTIVE = "active"
    SLEEPING = "sleeping"
    CHARGING = "charging"
    LOW_BATTERY = "low_battery"


class Device(BaseModel):
    """Base device model."""
    id: str = Field(..., description="Device ID")
    userId: str = Field(..., description="Owner user ID")
    deviceMac: str = Field(..., description="Device MAC address")
    deviceType: DeviceType = Field(..., description="Device type")
    name: Optional[str] = Field(None, description="Device display name")
    status: DeviceStatus = Field(DeviceStatus.OFFLINE, description="Connection status")
    lastSeenAt: Optional[str] = Field(None, description="Last activity timestamp")
    firmwareVersion: Optional[str] = Field(None, description="Current firmware version")
    createdAt: str = Field(..., description="Registration timestamp")
    updatedAt: str = Field(..., description="Last update timestamp")


class DoorConfig(BaseModel):
    """Smart door configuration."""
    mode: DoorMode = Field(DoorMode.AUTO, description="Operating mode")
    sensitivity: int = Field(5, ge=1, le=10, description="Detection sensitivity")
    nightModeEnabled: bool = Field(False, description="Night mode toggle")
    nightModeStart: Optional[str] = Field(None, description="Night mode start time (HH:MM)")
    nightModeEnd: Optional[str] = Field(None, description="Night mode end time (HH:MM)")
    preyDetectionEnabled: bool = Field(True, description="Prey detection toggle")
    autoLockDelay: int = Field(5, ge=0, le=60, description="Auto-lock delay in seconds")


class CollarConfig(BaseModel):
    """Health collar configuration."""
    trackingInterval: int = Field(300, ge=60, le=3600, description="GPS tracking interval in seconds")
    healthMonitoringEnabled: bool = Field(True, description="Health monitoring toggle")
    bcgEnabled: bool = Field(True, description="BCG sensor toggle")
    activityTrackingEnabled: bool = Field(True, description="Activity tracking toggle")
    geofenceAlertEnabled: bool = Field(True, description="Geofence alert toggle")


class SmartDoor(Device):
    """Smart door device."""
    deviceType: Literal[DeviceType.SMART_DOOR] = DeviceType.SMART_DOOR
    doorStatus: DoorStatus = Field(DoorStatus.CLOSED, description="Physical door status")
    config: Optional[DoorConfig] = Field(None, description="Door configuration")
    batteryLevel: Optional[int] = Field(None, ge=0, le=100, description="Battery level percentage")


class HealthCollar(Device):
    """Health collar device."""
    deviceType: Literal[DeviceType.HEALTH_COLLAR] = DeviceType.HEALTH_COLLAR
    collarStatus: CollarStatus = Field(CollarStatus.ACTIVE, description="Collar status")
    config: Optional[CollarConfig] = Field(None, description="Collar configuration")
    batteryLevel: Optional[int] = Field(None, ge=0, le=100, description="Battery level percentage")
    catId: Optional[str] = Field(None, description="Bound cat ID")


class DeviceWithDetails(Device):
    """Device with full details including bound cat."""
    boundCat: Optional[Cat] = Field(None, description="Bound cat profile")
    config: Optional[Dict[str, Any]] = Field(None, description="Device-specific configuration")
    batteryLevel: Optional[int] = Field(None, ge=0, le=100, description="Battery level percentage")


# ============================================================================
# ALERT MODELS
# ============================================================================

class AlertType(str, Enum):
    """Alert type enumeration."""
    DOOR_EVENT = "door_event"
    PREY_DETECTED = "prey_detected"
    HEALTH_WARNING = "health_warning"
    LOCATION_ALERT = "location_alert"
    DEVICE_OFFLINE = "device_offline"
    LOW_BATTERY = "low_battery"
    GEOFENCE_BREACH = "geofence_breach"
    ANOMALY_DETECTED = "anomaly_detected"


class AlertSeverity(str, Enum):
    """Alert severity level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Alert(BaseModel):
    """Alert notification model."""
    id: str = Field(..., description="Alert ID")
    userId: str = Field(..., description="User ID")
    catId: Optional[str] = Field(None, description="Related cat ID")
    deviceId: Optional[str] = Field(None, description="Related device ID")
    type: AlertType = Field(..., description="Alert type")
    severity: AlertSeverity = Field(AlertSeverity.MEDIUM, description="Alert severity")
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional alert data")
    read: bool = Field(False, description="Read status")
    createdAt: str = Field(..., description="Alert timestamp")


class AlertWithDetails(Alert):
    """Alert with related entity details."""
    cat: Optional[Cat] = Field(None, description="Related cat")
    device: Optional[Device] = Field(None, description="Related device")


# ============================================================================
# HEALTH MODELS
# ============================================================================

class HealthStatus(str, Enum):
    """Overall health status."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class ActivityLevel(str, Enum):
    """Activity level classification."""
    SEDENTARY = "sedentary"
    LOW = "low"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class SleepQuality(str, Enum):
    """Sleep quality assessment."""
    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"


class HealthSummary(BaseModel):
    """Health summary for a cat."""
    catId: str = Field(..., description="Cat ID")
    status: HealthStatus = Field(..., description="Overall health status")
    score: int = Field(..., ge=0, le=100, description="Health score 0-100")
    activityLevel: ActivityLevel = Field(..., description="Current activity level")
    sleepQuality: Optional[SleepQuality] = Field(None, description="Recent sleep quality")
    lastHeartRate: Optional[int] = Field(None, ge=30, le=300, description="Last heart rate BPM")
    lastRespiratoryRate: Optional[int] = Field(None, ge=10, le=60, description="Last respiratory rate")
    stepsToday: Optional[int] = Field(None, ge=0, description="Steps today")
    sleepHoursToday: Optional[float] = Field(None, ge=0, le=24, description="Sleep hours today")
    outdoorTimeToday: Optional[float] = Field(None, ge=0, le=24, description="Outdoor time today in hours")
    recommendations: Optional[List[str]] = Field(None, description="Health recommendations")
    updatedAt: str = Field(..., description="Summary timestamp")


class HeartRateData(BaseModel):
    """Heart rate measurement data."""
    timestamp: str = Field(..., description="Measurement timestamp")
    bpm: int = Field(..., ge=30, le=300, description="Beats per minute")
    quality: Optional[str] = Field(None, description="Signal quality indicator")


class BcgData(BaseModel):
    """BCG (Ballistocardiography) sensor data."""
    timestamp: str = Field(..., description="Measurement timestamp")
    heartRate: int = Field(..., ge=30, le=300, description="Derived heart rate")
    respiratoryRate: int = Field(..., ge=10, le=60, description="Respiratory rate")
    hrvMs: Optional[float] = Field(None, ge=0, description="Heart rate variability in ms")
    signalQuality: Optional[int] = Field(None, ge=0, le=100, description="Signal quality 0-100")
    rawData: Optional[List[float]] = Field(None, description="Raw BCG waveform data")


# ============================================================================
# DETECTION MODELS
# ============================================================================

class CarryStatus(str, Enum):
    """Prey/object carry detection status."""
    NONE = "none"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"


class Direction(str, Enum):
    """Movement direction through door."""
    IN = "in"
    OUT = "out"
    UNKNOWN = "unknown"


class RecentDetection(BaseModel):
    """Recent detection event from cat door."""
    id: str = Field(..., description="Detection ID")
    deviceId: str = Field(..., description="Device ID")
    catId: Optional[str] = Field(None, description="Detected cat ID")
    direction: Direction = Field(..., description="Movement direction")
    carryStatus: CarryStatus = Field(CarryStatus.NONE, description="Carry detection status")
    confidence: float = Field(..., ge=0, le=1, description="Detection confidence 0-1")
    imageUrl: Optional[str] = Field(None, description="Detection image URL")
    timestamp: str = Field(..., description="Detection timestamp")


class CatDoorEvent(BaseModel):
    """Cat door passage event."""
    id: str = Field(..., description="Event ID")
    deviceId: str = Field(..., description="Door device ID")
    catId: Optional[str] = Field(None, description="Cat ID (if identified)")
    direction: Direction = Field(..., description="Movement direction")
    carryStatus: CarryStatus = Field(CarryStatus.NONE, description="Object carry status")
    preyType: Optional[str] = Field(None, description="Detected prey type if any")
    blocked: bool = Field(False, description="Whether entry was blocked")
    imageUrl: Optional[str] = Field(None, description="Event image URL")
    videoUrl: Optional[str] = Field(None, description="Event video URL")
    timestamp: str = Field(..., description="Event timestamp")
    createdAt: str = Field(..., description="Record creation timestamp")


class Geofence(BaseModel):
    """Geofence definition."""
    id: str = Field(..., description="Geofence ID")
    deviceId: str = Field(..., description="Associated collar device ID")
    name: str = Field(..., description="Geofence name")
    latitude: float = Field(..., ge=-90, le=90, description="Center latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Center longitude")
    radius: int = Field(..., ge=10, le=10000, description="Radius in meters")
    isActive: bool = Field(True, description="Whether geofence is active")
    alertOnExit: bool = Field(True, description="Alert when cat exits")
    alertOnEnter: bool = Field(False, description="Alert when cat enters")
    createdAt: str = Field(..., description="Creation timestamp")
    updatedAt: str = Field(..., description="Last update timestamp")


class GeofenceCreateInput(BaseModel):
    """Input for creating a geofence."""
    name: str = Field(..., min_length=1, max_length=50, description="Geofence name")
    latitude: float = Field(..., ge=-90, le=90, description="Center latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Center longitude")
    radius: int = Field(..., ge=10, le=10000, description="Radius in meters")
    isActive: bool = Field(True, description="Whether geofence is active")
    alertOnExit: bool = Field(True, description="Alert when cat exits")
    alertOnEnter: bool = Field(False, description="Alert when cat enters")


class GeofenceUpdateInput(BaseModel):
    """Input for updating a geofence."""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="Geofence name")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Center latitude")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Center longitude")
    radius: Optional[int] = Field(None, ge=10, le=10000, description="Radius in meters")
    isActive: Optional[bool] = Field(None, description="Whether geofence is active")
    alertOnExit: Optional[bool] = Field(None, description="Alert when cat exits")
    alertOnEnter: Optional[bool] = Field(None, description="Alert when cat enters")


# ============================================================================
# CHAT MODELS
# ============================================================================

class ChatConversation(BaseModel):
    """Chat conversation model."""
    id: str = Field(..., description="Conversation ID")
    userId: str = Field(..., description="User ID")
    title: str = Field(..., description="Conversation title")
    contextType: Optional[str] = Field(None, description="Context type: cat, device, general")
    contextId: Optional[str] = Field(None, description="Related entity ID")
    lastMessageAt: Optional[str] = Field(None, description="Last message timestamp")
    createdAt: str = Field(..., description="Creation timestamp")
    updatedAt: str = Field(..., description="Last update timestamp")


class ChatMessage(BaseModel):
    """Chat message model."""
    id: str = Field(..., description="Message ID")
    conversationId: str = Field(..., description="Parent conversation ID")
    role: str = Field(..., description="Message role: user, assistant, system")
    content: str = Field(..., description="Message content")
    mediaUrl: Optional[str] = Field(None, description="Attached media URL")
    mediaType: Optional[str] = Field(None, description="Media type: image, video")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    createdAt: str = Field(..., description="Message timestamp")


class ChatRequest(BaseModel):
    """Chat request to AI butler."""
    userId: str = Field(..., description="User ID")
    catId: Optional[str] = Field(None, description="Related cat ID")
    conversationId: Optional[str] = Field(None, description="Existing conversation ID")
    message: str = Field(..., min_length=1, description="User message")
    mediaUrl: Optional[str] = Field(None, description="Media URL for analysis")
    mediaType: Optional[str] = Field(None, description="Media type: image, video")
    contextType: Optional[str] = Field(None, description="Context type for new conversation")


class ChatResponse(BaseModel):
    """Chat response from AI butler."""
    conversationId: str = Field(..., description="Conversation ID")
    messageId: str = Field(..., description="Response message ID")
    content: str = Field(..., description="AI response content")
    suggestions: Optional[List[str]] = Field(None, description="Follow-up suggestions")
    actions: Optional[List[Dict[str, Any]]] = Field(None, description="Suggested actions")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Response metadata")


class AISuggestion(BaseModel):
    """AI butler proactive suggestion."""
    id: str = Field(..., description="Suggestion ID")
    userId: str = Field(..., description="User ID")
    catId: Optional[str] = Field(None, description="Related cat ID")
    type: str = Field(..., description="Suggestion type")
    title: str = Field(..., description="Suggestion title")
    message: str = Field(..., description="Suggestion content")
    actionType: Optional[str] = Field(None, description="Suggested action type")
    actionData: Optional[Dict[str, Any]] = Field(None, description="Action parameters")
    priority: int = Field(0, ge=0, le=10, description="Priority 0-10")
    expiresAt: Optional[str] = Field(None, description="Suggestion expiration")
    createdAt: str = Field(..., description="Creation timestamp")


class HealthAnalysisRequest(BaseModel):
    """Request for health analysis."""
    userId: str = Field(..., description="User ID")
    catId: str = Field(..., description="Cat ID to analyze")
    analysisType: str = Field(..., description="Analysis type")
    timeRange: Optional[str] = Field("24h", description="Time range for analysis")
    includeRecommendations: bool = Field(True, description="Include health recommendations")


# ============================================================================
# TASK MODELS
# ============================================================================

class TaskType(str, Enum):
    """Task type enumeration."""
    FEEDING = "feeding"
    MEDICATION = "medication"
    GROOMING = "grooming"
    VET_VISIT = "vet_visit"
    VACCINATION = "vaccination"
    WEIGHT_CHECK = "weight_check"
    PLAY_TIME = "play_time"
    CUSTOM = "custom"


class TaskPriority(str, Enum):
    """Task priority level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(str, Enum):
    """Task completion status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    OVERDUE = "overdue"


class Task(BaseModel):
    """Task/reminder model."""
    id: str = Field(..., description="Task ID")
    userId: str = Field(..., description="User ID")
    catId: Optional[str] = Field(None, description="Related cat ID")
    type: TaskType = Field(..., description="Task type")
    title: str = Field(..., description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="Task priority")
    status: TaskStatus = Field(TaskStatus.PENDING, description="Task status")
    dueDate: Optional[str] = Field(None, description="Due date")
    dueTime: Optional[str] = Field(None, description="Due time (HH:MM)")
    recurrence: Optional[str] = Field(None, description="Recurrence rule: daily, weekly, monthly")
    completedAt: Optional[str] = Field(None, description="Completion timestamp")
    createdAt: str = Field(..., description="Creation timestamp")
    updatedAt: str = Field(..., description="Last update timestamp")


class TaskWithCat(Task):
    """Task with related cat details."""
    cat: Optional[Cat] = Field(None, description="Related cat profile")


class TaskCreateInput(BaseModel):
    """Input for creating a task."""
    catId: Optional[str] = Field(None, description="Related cat ID")
    type: TaskType = Field(..., description="Task type")
    title: str = Field(..., min_length=1, max_length=100, description="Task title")
    description: Optional[str] = Field(None, max_length=500, description="Task description")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="Task priority")
    dueDate: Optional[str] = Field(None, description="Due date (ISO 8601)")
    dueTime: Optional[str] = Field(None, description="Due time (HH:MM)")
    recurrence: Optional[str] = Field(None, description="Recurrence: daily, weekly, monthly")


class TaskUpdateInput(BaseModel):
    """Input for updating a task."""
    catId: Optional[str] = Field(None, description="Related cat ID")
    type: Optional[TaskType] = Field(None, description="Task type")
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="Task title")
    description: Optional[str] = Field(None, max_length=500, description="Task description")
    priority: Optional[TaskPriority] = Field(None, description="Task priority")
    status: Optional[TaskStatus] = Field(None, description="Task status")
    dueDate: Optional[str] = Field(None, description="Due date (ISO 8601)")
    dueTime: Optional[str] = Field(None, description="Due time (HH:MM)")
    recurrence: Optional[str] = Field(None, description="Recurrence: daily, weekly, monthly")


# Forward references for self-referential types
CatWithHealth.model_rebuild()
DeviceWithDetails.model_rebuild()
AlertWithDetails.model_rebuild()
TaskWithCat.model_rebuild()
