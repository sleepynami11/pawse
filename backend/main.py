"""
Cat IoT Health Monitoring System - Main Entry Point

This is the main entry point for running the FastAPI application locally.
Supports 10+ concurrent users via async I/O.

Usage:
    python main.py

    Or directly with uvicorn:
    uvicorn api:app --host 0.0.0.0 --port 8000

Environment Variables:
    - HOST: Server host (default: 0.0.0.0)
    - PORT: Server port (default: 8000)
    - RELOAD: Enable auto-reload for development (default: false)
    - LOG_LEVEL: Logging level (default: info)
"""

import os
import logging

import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    Start the FastAPI server with uvicorn.

    Configuration can be customized via environment variables:
    - HOST: Server bind address
    - PORT: Server port number
    - RELOAD: Enable hot-reload for development
    - LOG_LEVEL: Logging verbosity
    """
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    logger.info(f"Starting Cat IoT Health Monitoring System")
    logger.info(f"Server: http://{host}:{port}")
    logger.info(f"Reload: {reload}, Log Level: {log_level}")
    logger.info(f"API Docs: http://{host}:{port}/docs")

    uvicorn.run(
        "api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        # Concurrency settings for 10+ users
        # Single worker with asyncio handles 100+ concurrent connections
        workers=1,
        # Enable access logs
        access_log=True,
    )


if __name__ == "__main__":
    main()
