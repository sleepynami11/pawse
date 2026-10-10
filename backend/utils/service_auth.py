"""
Service-to-Service Authentication Utilities

Provides secure authentication between Worker and Agent services.
Uses HMAC-based token generation for service identity verification.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional, Dict, Tuple
from dataclasses import dataclass


@dataclass
class ServiceAuthResult:
    """Result of service authentication validation."""
    valid: bool
    service: Optional[str] = None
    error: Optional[str] = None


@dataclass
class UserContext:
    """User context extracted from service request headers."""
    id: str
    email: str
    name: Optional[str] = None


# Service names for the MyCatsHome ecosystem
class ServiceNames:
    WORKER = "mycatshome-worker"
    AGENT = "mycatshome-agent"
    MOBILE = "mycatshome-mobile"


def get_service_secret() -> str:
    """
    Get the shared service secret from environment.

    Returns:
        Shared secret key for service authentication

    Raises:
        ValueError: If SERVICE_SECRET is not configured
    """
    secret = os.environ.get("SERVICE_SECRET")
    if not secret:
        raise ValueError("SERVICE_SECRET environment variable not configured")
    return secret


def generate_service_token(
    service_name: str,
    secret: Optional[str] = None,
    expires_in: int = 300
) -> str:
    """
    Generate a service token for internal service-to-service calls.

    Args:
        service_name: Name of the calling service
        secret: Shared secret key (uses SERVICE_SECRET env if not provided)
        expires_in: Token expiration in seconds (default: 5 minutes)

    Returns:
        Service token as base64 encoded string
    """
    if secret is None:
        secret = get_service_secret()

    timestamp = int(time.time())
    expires_at = timestamp + expires_in
    payload = f"{service_name}:{timestamp}:{expires_at}"

    # Generate HMAC signature
    signature = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).digest()

    signature_base64 = base64.b64encode(signature).decode("utf-8")

    # Create token as base64 encoded JSON
    token_data = {
        "service": service_name,
        "timestamp": timestamp,
        "expiresAt": expires_at,
        "signature": signature_base64,
    }

    return base64.b64encode(json.dumps(token_data).encode("utf-8")).decode("utf-8")


def validate_service_token(
    token: str,
    expected_service: Optional[str] = None,
    secret: Optional[str] = None
) -> ServiceAuthResult:
    """
    Validate a service token.

    Args:
        token: Service token to validate
        expected_service: Expected service name (optional)
        secret: Shared secret key (uses SERVICE_SECRET env if not provided)

    Returns:
        ServiceAuthResult with validation result
    """
    if secret is None:
        secret = get_service_secret()

    try:
        # Decode token
        decoded_json = base64.b64decode(token).decode("utf-8")
        decoded = json.loads(decoded_json)

        service = decoded.get("service")
        timestamp = decoded.get("timestamp")
        expires_at = decoded.get("expiresAt")
        signature_base64 = decoded.get("signature")

        if not all([service, timestamp, expires_at, signature_base64]):
            return ServiceAuthResult(valid=False, error="Invalid token structure")

        # Check expiration
        now = int(time.time())
        if now > expires_at:
            return ServiceAuthResult(valid=False, error="Token expired")

        # Check service name if expected
        if expected_service and service != expected_service:
            return ServiceAuthResult(valid=False, error="Invalid service")

        # Verify signature
        payload = f"{service}:{timestamp}:{expires_at}"
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).digest()

        actual_signature = base64.b64decode(signature_base64)

        if not hmac.compare_digest(expected_signature, actual_signature):
            return ServiceAuthResult(valid=False, error="Invalid signature")

        return ServiceAuthResult(valid=True, service=service)

    except json.JSONDecodeError:
        return ServiceAuthResult(valid=False, error="Invalid token format")
    except Exception as e:
        return ServiceAuthResult(valid=False, error=f"Token validation error: {str(e)}")


def create_service_headers(
    service_name: str,
    secret: Optional[str] = None,
    additional_headers: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """
    Create headers for service-to-service requests.

    Args:
        service_name: Name of the calling service
        secret: Shared secret key (uses SERVICE_SECRET env if not provided)
        additional_headers: Additional headers to include

    Returns:
        Headers dictionary
    """
    token = generate_service_token(service_name, secret)

    headers = {
        "Content-Type": "application/json",
        "X-Service-Auth": token,
    }

    if additional_headers:
        headers.update(additional_headers)

    return headers


def create_user_context_headers(
    user_id: str,
    user_email: str,
    user_name: Optional[str],
    service_name: str,
    secret: Optional[str] = None
) -> Dict[str, str]:
    """
    Forward user context to another service.
    Creates headers that include user identity.

    Args:
        user_id: User ID
        user_email: User email
        user_name: User name (optional)
        service_name: Name of the calling service
        secret: Shared secret key (uses SERVICE_SECRET env if not provided)

    Returns:
        Headers dictionary with user context
    """
    token = generate_service_token(service_name, secret)

    headers = {
        "Content-Type": "application/json",
        "X-Service-Auth": token,
        "X-User-Id": user_id,
        "X-User-Email": user_email,
    }

    if user_name:
        headers["X-User-Name"] = user_name

    return headers


def extract_user_context(headers: Dict[str, str]) -> Optional[UserContext]:
    """
    Extract user context from service request headers.

    Args:
        headers: Request headers dictionary

    Returns:
        UserContext object or None if not present
    """
    user_id = headers.get("X-User-Id") or headers.get("x-user-id")
    email = headers.get("X-User-Email") or headers.get("x-user-email")
    name = headers.get("X-User-Name") or headers.get("x-user-name")

    if not user_id or not email:
        return None

    return UserContext(
        id=user_id,
        email=email,
        name=name if name else None
    )


async def require_service_auth(
    headers: Dict[str, str],
    expected_service: Optional[str] = None,
    secret: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Middleware helper to require service authentication.

    Args:
        headers: Request headers dictionary
        expected_service: Expected service name (optional)
        secret: Shared secret key (uses SERVICE_SECRET env if not provided)

    Returns:
        Tuple of (is_valid, service_name, error_message)
    """
    auth_header = headers.get("X-Service-Auth") or headers.get("x-service-auth")

    if not auth_header:
        return False, None, "Service authentication required"

    result = validate_service_token(auth_header, expected_service, secret)

    if not result.valid:
        return False, None, result.error

    return True, result.service, None
