"""
? Crypto Trade Hub - FastAPI Backend Startup Script

Features:
- Automatic port detection and resolution
- Detailed error diagnostics
- Windows socket permission handling
- Environment variable configuration support
"""

from __future__ import annotations

import os
import sys
import argparse
import logging

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure backend package is importable when run from other directories
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import uvicorn
from app.core.port_utils import (
    is_port_available,
    find_free_port,
    get_socket_error_diagnosis,
    print_startup_info,
)


def main(
    host: str | None = None,
    port: int | None = None,
    reload: bool = False,
    auto_port: bool = False,
    workers: int = 1,
) -> None:
    """
    Start the FastAPI server with robust error handling.
    
    Args:
        host: Server host (default from env or 0.0.0.0)
        port: Server port (default from env or 8000)
        reload: Enable auto-reload on code changes
        auto_port: Automatically find free port if default is occupied
        workers: Number of Uvicorn workers
    """
    
    # Get configuration from arguments, environment, or defaults
    host = host or os.getenv("SERVER_HOST", "0.0.0.0")
    port = port or int(os.getenv("SERVER_PORT", "8000"))
    auto_port = auto_port or os.getenv("AUTO_PORT", "").lower() in ("true", "1", "yes")
    
    logger.info(f"? Starting Crypto Trade Hub Backend...")
    logger.info(f"   Host: {host} | Port: {port} | Auto-port: {auto_port} | Reload: {reload}")
    
    # Check port availability
    if not is_port_available(host, port):
        logger.warning(f"??  Port {port} is not available")
        
        if auto_port:
            logger.info(f"? Attempting to find available port...")
            try:
                port = find_free_port(host, start_port=port, max_attempts=10)
                logger.info(f"? Found available port: {port}")
            except RuntimeError as e:
                logger.error(str(e))
                sys.exit(1)
        else:
            logger.error(
                f"? Port {port} is not available. "
                f"Use --auto-port or --port to specify a different port.\n"
                f"Example: python run_server.py --auto-port"
            )
            sys.exit(1)
    else:
        logger.info(f"? Port {port} is available")
    
    # Print startup info
    print_startup_info(host, port, reload=reload, workers=workers)
    
    # Start the server with error handling
    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,  # Disable workers in reload mode
            log_level="info",
            access_log=True,
        )
    except (OSError, PermissionError) as e:
        # Provide detailed diagnosis for socket errors
        diagnosis = get_socket_error_diagnosis(host, port, e)
        logger.error(diagnosis)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n??  Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"? Unexpected error: {e}", exc_info=True)
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Start the Crypto Trade Hub FastAPI backend server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_server.py                    # Start with defaults (0.0.0.0:8000)
  python run_server.py --port 8001        # Use specific port
  python run_server.py --auto-port        # Auto-detect free port
  python run_server.py --host 127.0.0.1   # Bind to localhost only
  python run_server.py --reload            # Enable auto-reload for development
  python run_server.py --reload --auto-port # Dev mode with auto port
        """
    )
    
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind to (default: 0.0.0.0 from env or defaults)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: 8000 from env or defaults)",
    )
    parser.add_argument(
        "--auto-port",
        action="store_true",
        help="Automatically find free port if default is occupied",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (dev mode)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of Uvicorn workers (default: 1)",
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(
        host=args.host,
        port=args.port,
        reload=args.reload,
        auto_port=args.auto_port,
        workers=args.workers,
    )
