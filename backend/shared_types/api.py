"""
MyCatsHome API Response Types

Standardized API response format matching the worker and api-client packages.
"""

from typing import TypeVar, Generic, Optional, Dict, List, Any, Literal
from pydantic import BaseModel, Field


# Generic type variable for response data
T = TypeVar('T')


# ============================================================================
# ERROR CODES
# ============================================================================

ERROR_CODES = {
    # Authentication errors
    "UNAUTHORIZED": "UNAUTHORIZED",
    "INVALID_TOKEN": "INVALID_TOKEN",
    "TOKEN_EXPIRED": "TOKEN_EXPIRED",
    "FORBIDDEN": "FORBIDDEN",

    # Validation errors
    "VALIDATION_ERROR": "VALIDATION_ERROR",
    "INVALID_INPUT": "INVALID_INPUT",
    "MISSING_FIELD": "MISSING_FIELD",

    # Resource errors
    "NOT_FOUND": "NOT_FOUND",
    "ALREADY_EXISTS": "ALREADY_EXISTS",
    "CONFLICT": "CONFLICT",

    # Server errors
    "INTERNAL_ERROR": "INTERNAL_ERROR",
    "SERVICE_UNAVAILABLE": "SERVICE_UNAVAILABLE",
    "RATE_LIMITED": "RATE_LIMITED",

    # Business logic errors
    "DEVICE_OFFLINE": "DEVICE_OFFLINE",
    "DEVICE_NOT_BOUND": "DEVICE_NOT_BOUND",
    "CAT_NOT_FOUND": "CAT_NOT_FOUND",
    "INVALID_OPERATION": "INVALID_OPERATION",
}


# ============================================================================
# ERROR DETAIL
# ============================================================================

class ErrorDetail(BaseModel):
    """Error detail model for API error responses."""
    code: str = Field(..., description="Error code from ERROR_CODES")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Field-specific validation errors"
    )


# ============================================================================
# API RESPONSE TYPES
# ============================================================================

class ApiResponse(BaseModel, Generic[T]):
    """
    Standard API success response wrapper.

    All successful API responses follow this format:
    {
        "success": true,
        "data": <T>,
        "meta": { "timestamp": "..." }
    }
    """
    success: Literal[True] = True
    data: Any = Field(..., description="Response payload")
    meta: Optional[Dict[str, Any]] = Field(
        None,
        description="Response metadata including pagination and timestamps"
    )


class ApiErrorResponse(BaseModel):
    """
    Standard API error response wrapper.

    All error responses follow this format:
    {
        "success": false,
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "details": { "field": ["error1", "error2"] }
        }
    }
    """
    success: Literal[False] = False
    error: ErrorDetail = Field(..., description="Error details")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_success_response(
    data: Any,
    meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized success response.

    Args:
        data: Response payload
        meta: Optional metadata (pagination, timestamps, etc.)

    Returns:
        Dictionary matching ApiResponse structure
    """
    from datetime import datetime

    response = {
        "success": True,
        "data": data,
    }

    if meta:
        response["meta"] = {
            **meta,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    else:
        response["meta"] = {
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    return response


def create_error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, List[str]]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        code: Error code from ERROR_CODES
        message: Human-readable error message
        details: Optional field-specific validation errors

    Returns:
        Dictionary matching ApiErrorResponse structure
    """
    error = {
        "code": code,
        "message": message,
    }

    if details:
        error["details"] = details

    return {
        "success": False,
        "error": error
    }


def get_error_code_for_status(status: int) -> str:
    """
    Get default error code for HTTP status code.

    Args:
        status: HTTP status code

    Returns:
        Appropriate error code from ERROR_CODES
    """
    status_to_code = {
        400: ERROR_CODES["VALIDATION_ERROR"],
        401: ERROR_CODES["UNAUTHORIZED"],
        403: ERROR_CODES["FORBIDDEN"],
        404: ERROR_CODES["NOT_FOUND"],
        409: ERROR_CODES["CONFLICT"],
        429: ERROR_CODES["RATE_LIMITED"],
        500: ERROR_CODES["INTERNAL_ERROR"],
        503: ERROR_CODES["SERVICE_UNAVAILABLE"],
    }

    return status_to_code.get(status, ERROR_CODES["INTERNAL_ERROR"])
