"""
Cloudflare R2 Object Storage Async Client

This module provides async functions to interact with Cloudflare R2 storage
using S3-compatible API via aiobotocore.

Environment Variables Required:
    - R2_ACCESS_KEY_ID: R2 access key ID
    - R2_SECRET_ACCESS_KEY: R2 secret access key
    - R2_ENDPOINT_URL: R2 endpoint URL (format: https://<account-id>.r2.cloudflarestorage.com)

Test Mode:
    Set TEST_MODE=true to use mock storage instead of real R2.

Usage Example:
    import asyncio
    from utils.r2_client import upload_file, get_file, delete_file

    async def main():
        # Upload file
        url = await upload_file("my-bucket", "path/to/file.jpg", image_bytes)

        # Download file
        data = await get_file("my-bucket", "path/to/file.jpg")

        # Delete file
        success = await delete_file("my-bucket", "path/to/file.jpg")

    asyncio.run(main())
"""

import os
import logging
from contextlib import asynccontextmanager

# Test mode flag
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

if TEST_MODE:
    from utils.mock_data import MockR2

try:
    from aiobotocore.session import get_session
except ImportError:
    raise ImportError(
        "aiobotocore is required for R2 client. Install with: pip install aiobotocore"
    )

logger = logging.getLogger(__name__)


def build_r2_path(
    user_id: int,
    cat_id: int,
    resource_type: str,
    filename: str
) -> str:
    """
    Build a standardized R2 storage path with user_id/cat_id hierarchy.

    This function ensures consistent path structure for all R2 uploads,
    enabling proper data isolation per user and per cat.

    Args:
        user_id: User ID for the top-level folder
        cat_id: Cat ID for the second-level folder
        resource_type: Type of resource (e.g., 'images', 'weekly-reports', 'monthly-reports')
        filename: Name of the file to store

    Returns:
        str: Formatted path string 'user_id/cat_id/resource_type/filename'

    Raises:
        ValueError: If user_id, cat_id, resource_type, or filename is empty/None

    Examples:
        >>> build_r2_path(1, 2, 'images', '20231210.jpg')
        '1/2/images/20231210.jpg'

        >>> build_r2_path(100, 5, 'weekly-reports', '2024-W01.md')
        '100/5/weekly-reports/2024-W01.md'

        >>> build_r2_path(100, 5, 'monthly-reports', '2024-01.md')
        '100/5/monthly-reports/2024-01.md'
    """
    # Validate inputs
    if user_id is None:
        raise ValueError("user_id cannot be None")
    if cat_id is None:
        raise ValueError("cat_id cannot be None")
    if not resource_type:
        raise ValueError("resource_type cannot be empty")
    if not filename:
        raise ValueError("filename cannot be empty")

    # Build and return the path
    path = f"{user_id}/{cat_id}/{resource_type}/{filename}"
    logger.debug(f"Built R2 path: {path}")
    return path


def build_r2_path_safe(
    user_id: int | None,
    cat_id: int,
    resource_type: str,
    filename: str,
    fallback_to_legacy: bool = True
) -> str:
    """
    Build R2 path with fallback to legacy format if user_id is unavailable.

    This is useful for webhook flows where user_id might not be available,
    allowing graceful degradation to the old path format.

    Args:
        user_id: User ID (can be None for fallback)
        cat_id: Cat ID
        resource_type: Type of resource
        filename: Name of the file
        fallback_to_legacy: If True and user_id is None, use legacy format

    Returns:
        str: Either 'user_id/cat_id/resource_type/filename' or 'cat_id/resource_type/filename'

    Examples:
        >>> build_r2_path_safe(1, 2, 'images', 'photo.jpg')
        '1/2/images/photo.jpg'

        >>> build_r2_path_safe(None, 2, 'images', 'photo.jpg')
        '2/images/photo.jpg'  # Legacy format fallback
    """
    if user_id is not None:
        return build_r2_path(user_id, cat_id, resource_type, filename)

    if fallback_to_legacy:
        # Legacy format: cat_id/resource_type/filename
        legacy_path = f"{cat_id}/{resource_type}/{filename}"
        logger.warning(f"user_id unavailable, using legacy R2 path: {legacy_path}")
        return legacy_path

    raise ValueError("user_id cannot be None when fallback_to_legacy is False")


# Load environment variables
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")


@asynccontextmanager
async def _get_r2_client():
    """
    Internal context manager to create R2 S3-compatible client.

    Yields:
        S3 client instance configured for Cloudflare R2
    """
    if not all([R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL]):
        error_msg = "Missing required environment variables: R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL"
        logger.error(error_msg)
        raise ValueError(error_msg)

    session = get_session()
    async with session.create_client(
        "s3",
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",  # R2 uses "auto" for region
    ) as client:
        yield client


async def upload_file(bucket: str, key: str, data: bytes, content_type: str = None) -> str:
    """
    Upload a file to Cloudflare R2 storage.

    Args:
        bucket: R2 bucket name
        key: Object key (path) in the bucket
        data: File data as bytes
        content_type: Optional MIME type for the file

    Returns:
        str: Public URL of uploaded file (if bucket is public)

    Raises:
        ValueError: If required environment variables are missing
        Exception: If upload fails

    Example:
        with open("image.jpg", "rb") as f:
            image_data = f.read()
        url = await upload_file("my-bucket", "images/photo.jpg", image_data)
    """
    # TEST_MODE: Use mock storage
    if TEST_MODE:
        logger.info(f"[TEST_MODE] Mock uploading file: {bucket}/{key} ({len(data)} bytes)")
        return MockR2.upload_file(bucket, key, data)

    try:
        async with _get_r2_client() as client:
            logger.info(f"Uploading file to R2: {bucket}/{key} ({len(data)} bytes)")
            put_kwargs = {"Bucket": bucket, "Key": key, "Body": data}
            if content_type:
                put_kwargs["ContentType"] = content_type
            await client.put_object(**put_kwargs)

            # Construct public URL (works if bucket is public)
            url = f"{R2_ENDPOINT_URL}/{bucket}/{key}"
            logger.info(f"File uploaded successfully to R2: {url}")
            return url

    except Exception as e:
        logger.error(f"R2 upload failed for {bucket}/{key}: {str(e)}")
        raise


async def get_file(bucket: str, key: str) -> bytes:
    """
    Download a file from Cloudflare R2 storage.

    Args:
        bucket: R2 bucket name
        key: Object key (path) in the bucket

    Returns:
        bytes: File data

    Raises:
        ValueError: If required environment variables are missing
        Exception: If download fails or file not found

    Example:
        image_data = await get_file("my-bucket", "images/photo.jpg")
        with open("downloaded.jpg", "wb") as f:
            f.write(image_data)
    """
    # TEST_MODE: Use mock storage
    if TEST_MODE:
        logger.info(f"[TEST_MODE] Mock downloading file: {bucket}/{key}")
        return MockR2.get_file(bucket, key)

    try:
        async with _get_r2_client() as client:
            logger.info(f"Downloading file from R2: {bucket}/{key}")
            response = await client.get_object(Bucket=bucket, Key=key)

            async with response["Body"] as stream:
                data = await stream.read()

            logger.info(f"File downloaded successfully from R2: {len(data)} bytes")
            return data

    except Exception as e:
        logger.error(f"R2 download failed for {bucket}/{key}: {str(e)}")
        raise


async def delete_file(bucket: str, key: str) -> bool:
    """
    Delete a file from Cloudflare R2 storage.

    Args:
        bucket: R2 bucket name
        key: Object key (path) in the bucket

    Returns:
        bool: True if deletion succeeded

    Raises:
        ValueError: If required environment variables are missing
        Exception: If deletion fails

    Example:
        success = await delete_file("my-bucket", "images/photo.jpg")
        if success:
            print("File deleted successfully")
    """
    # TEST_MODE: Use mock storage
    if TEST_MODE:
        logger.info(f"[TEST_MODE] Mock deleting file: {bucket}/{key}")
        return MockR2.delete_file(bucket, key)

    try:
        async with _get_r2_client() as client:
            logger.info(f"Deleting file from R2: {bucket}/{key}")
            await client.delete_object(Bucket=bucket, Key=key)

            logger.info(f"File deleted successfully from R2")
            return True

    except Exception as e:
        logger.error(f"R2 deletion failed for {bucket}/{key}: {str(e)}")
        raise


if __name__ == "__main__":
    import asyncio

    async def test():
        """Test R2 client with example operations"""
        try:
            # Test upload
            test_data = b"Hello, Cloudflare R2!"
            url = await upload_file("test-bucket", "test/hello.txt", test_data)
            print(f"Upload successful: {url}")

            # Test download
            downloaded = await get_file("test-bucket", "test/hello.txt")
            print(f"Downloaded: {downloaded.decode()}")

            # Test delete
            success = await delete_file("test-bucket", "test/hello.txt")
            print(f"Delete successful: {success}")

        except Exception as e:
            print(f"Test failed: {e}")

    asyncio.run(test())
