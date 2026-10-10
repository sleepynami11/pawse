"""
Video Processing Utility for Cat IoT Health Monitoring System

Extracts keyframes from videos for AI analysis.
Supports fallback mechanisms when ffmpeg/opencv are not available.
"""

import logging
import tempfile
import os
from typing import List, Optional
from datetime import datetime

import aiohttp
import asyncio

from utils.r2_client import upload_file, build_r2_path_safe

logger = logging.getLogger(__name__)


async def extract_video_frames(
    video_url: str,
    max_frames: int = 3,
    user_id: Optional[int] = None,
    cat_id: Optional[int] = None
) -> List[str]:
    """
    Extract keyframes from a video URL.

    Strategy:
    1. Download video to temp file
    2. Extract frames using opencv (preferred) or ffmpeg
    3. Upload frames to R2
    4. Return list of frame URLs

    Args:
        video_url: URL of the video to process
        max_frames: Maximum number of frames to extract (default: 3)
        user_id: User ID for R2 path (optional)
        cat_id: Cat ID for R2 path (optional)

    Returns:
        List of R2 URLs for extracted frames
    """
    try:
        # Download video to temp file
        video_path = await _download_video(video_url)
        if not video_path:
            logger.warning(f"Failed to download video: {video_url}")
            return []

        # Try opencv first, then ffmpeg
        frames = await _extract_frames_opencv(video_path, max_frames)
        if not frames:
            frames = await _extract_frames_ffmpeg(video_path, max_frames)

        if not frames:
            logger.warning("Failed to extract frames from video")
            return []

        # Upload frames to R2
        frame_urls = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        for i, frame_data in enumerate(frames):
            filename = f'{timestamp}_frame_{i}.jpg'
            key = build_r2_path_safe(user_id, cat_id, 'video_frames', filename)

            try:
                frame_url = await upload_file(
                    bucket='cat-images',
                    key=key,
                    data=frame_data,
                    content_type='image/jpeg'
                )
                frame_urls.append(frame_url)
            except Exception as e:
                logger.warning(f"Failed to upload frame {i}: {e}")

        # Cleanup temp file
        try:
            os.unlink(video_path)
        except Exception:
            pass

        return frame_urls

    except Exception as e:
        logger.exception(f"Error extracting video frames: {e}")
        return []


async def _download_video(video_url: str) -> Optional[str]:
    """Download video to temporary file."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url) as response:
                if response.status != 200:
                    logger.warning(f"Failed to download video: HTTP {response.status}")
                    return None

                # Create temp file
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                    content = await response.read()
                    tmp.write(content)
                    return tmp.name

    except Exception as e:
        logger.warning(f"Error downloading video: {e}")
        return None


async def _extract_frames_opencv(video_path: str, max_frames: int) -> List[bytes]:
    """Extract frames using OpenCV (preferred method)."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        logger.info("OpenCV not available, will try ffmpeg")
        return []

    frames = []
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning("Failed to open video with OpenCV")
            return []

        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0

        if total_frames <= 0:
            logger.warning("Video has no frames")
            cap.release()
            return []

        # Calculate frame positions (start, middle, end)
        if max_frames == 1:
            positions = [total_frames // 2]  # Middle frame only
        elif max_frames == 2:
            positions = [0, total_frames - 1]  # First and last
        else:
            # Evenly distribute frames
            step = total_frames // max_frames
            positions = [i * step for i in range(max_frames)]
            # Ensure we include the last frame area
            if positions[-1] < total_frames - step // 2:
                positions[-1] = total_frames - 1

        for pos in positions[:max_frames]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ret, frame = cap.read()
            if ret:
                # Encode frame to JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                frames.append(buffer.tobytes())

        cap.release()
        logger.info(f"Extracted {len(frames)} frames using OpenCV")
        return frames

    except Exception as e:
        logger.warning(f"OpenCV frame extraction failed: {e}")
        return []


async def _extract_frames_ffmpeg(video_path: str, max_frames: int) -> List[bytes]:
    """Extract frames using ffmpeg (fallback method)."""
    try:
        import subprocess
    except ImportError:
        return []

    frames = []
    try:
        # Get video duration first
        probe_cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]

        result = await asyncio.create_subprocess_exec(
            *probe_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await result.communicate()

        try:
            duration = float(stdout.decode().strip())
        except ValueError:
            duration = 10.0  # Default assumption

        # Calculate timestamps
        if max_frames == 1:
            timestamps = [duration / 2]
        elif max_frames == 2:
            timestamps = [0.5, duration - 0.5]
        else:
            step = duration / max_frames
            timestamps = [i * step + step / 2 for i in range(max_frames)]

        # Extract frames at each timestamp
        for i, ts in enumerate(timestamps):
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                output_path = tmp.name

            extract_cmd = [
                'ffmpeg', '-y',
                '-ss', str(ts),
                '-i', video_path,
                '-vframes', '1',
                '-q:v', '2',
                output_path
            ]

            process = await asyncio.create_subprocess_exec(
                *extract_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                with open(output_path, 'rb') as f:
                    frames.append(f.read())
                os.unlink(output_path)
            else:
                try:
                    os.unlink(output_path)
                except Exception:
                    pass

        logger.info(f"Extracted {len(frames)} frames using ffmpeg")
        return frames

    except FileNotFoundError:
        logger.info("ffmpeg not available")
        return []
    except Exception as e:
        logger.warning(f"ffmpeg frame extraction failed: {e}")
        return []


async def get_video_duration(video_url: str) -> Optional[float]:
    """Get video duration in seconds."""
    try:
        video_path = await _download_video(video_url)
        if not video_path:
            return None

        # Try opencv
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                duration = frames / fps if fps > 0 else None
                cap.release()
                os.unlink(video_path)
                return duration
        except ImportError:
            pass

        # Try ffprobe
        try:
            probe_cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result = await asyncio.create_subprocess_exec(
                *probe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            duration = float(stdout.decode().strip())
            os.unlink(video_path)
            return duration
        except Exception:
            pass

        os.unlink(video_path)
        return None

    except Exception as e:
        logger.warning(f"Error getting video duration: {e}")
        return None
