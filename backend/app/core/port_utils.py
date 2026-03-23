"""
? Port Utility Functions
==========================

Utilities for checking port availability and finding free ports
on systems where socket binding might fail due to permissions.

Features:
- Check if a specific port is available
- Find the next available port
- Provide detailed error diagnostics
- Support for Windows permission issues
"""

import socket
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Try to import psutil for process info, but make it optional
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None


def is_port_available(host: str = "127.0.0.1", port: int = 8000) -> bool:
    """
    Check if a port is available for binding.
    
    Args:
        host: Hostname/IP to bind to (default: 127.0.0.1)
        port: Port number to check (default: 8000)
        
    Returns:
        True if port is available, False otherwise
        
    Example:
        if is_port_available("127.0.0.1", 8000):
            print("Port 8000 is free")
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.close()
        return True
    except (OSError, PermissionError) as e:
        logger.debug(f"Port {port} check failed: {e}")
        return False


def find_free_port(host: str = "127.0.0.1", start_port: int = 8000, max_attempts: int = 10) -> int:
    """
    Find a free port starting from start_port.
    
    Args:
        host: Hostname/IP to check
        start_port: Port to start checking from (default: 8000)
        max_attempts: Maximum number of ports to try (default: 10)
        
    Returns:
        First available port found
        
    Raises:
        RuntimeError: If no free port found after max_attempts
        
    Example:
        port = find_free_port(start_port=8000)
        print(f"Using port {port}")
    """
    for port_offset in range(max_attempts):
        current_port = start_port + port_offset
        if is_port_available(host, current_port):
            logger.info(f"? Found available port: {current_port}")
            return current_port
    
    raise RuntimeError(
        f"? Could not find a free port in range {start_port}-{start_port + max_attempts - 1}. "
        f"Please manually free a port or specify a higher starting port."
    )


def get_process_using_port(port: int) -> Optional[Tuple[int, str]]:
    """
    Identify which process is using a specific port.
    
    Args:
        port: Port number to check
        
    Returns:
        Tuple of (PID, Process Name) if a process is found, None otherwise
        
    Example:
        pid, name = get_process_using_port(8000)
        print(f"Port 8000 is used by PID {pid} ({name})")
    """
    if not PSUTIL_AVAILABLE:
        logger.debug("psutil not installed, skipping process identification")
        return None
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                for conn in proc.connections():
                    if conn.laddr.port == port:
                        return (proc.pid, proc.name())
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass
    except Exception as e:
        logger.debug(f"Error identifying process on port {port}: {e}")
    
    return None


def get_socket_error_diagnosis(host: str, port: int, error: Exception) -> str:
    """
    Provide detailed diagnosis of socket binding errors.
    
    Args:
        host: Host that was being bound to
        port: Port that was being bound to
        error: The exception that was raised
        
    Returns:
        Detailed error message with suggestions
        
    Example:
        try:
            sock.bind((host, port))
        except OSError as e:
            diagnosis = get_socket_error_diagnosis(host, port, e)
            logger.error(diagnosis)
    """
    error_msg = str(error)
    diagnosis = f"\n{'='*60}\n"
    diagnosis += f"? SOCKET BINDING ERROR\n"
    diagnosis += f"{'='*60}\n\n"
    diagnosis += f"Failed to bind to: {host}:{port}\n"
    diagnosis += f"Error: {error_msg}\n\n"
    
    # Windows-specific error (WinError 10013)
    if "10013" in error_msg or "permission" in error_msg.lower():
        diagnosis += "? POSSIBLE CAUSES (Windows):\n"
        diagnosis += "  1. Firewall/Antivirus blocking the port\n"
        diagnosis += "  2. Port is reserved/in-use by another service\n"
        diagnosis += "  3. Insufficient permissions to bind to the port\n\n"
        
        process_info = get_process_using_port(port)
        if process_info:
            pid, name = process_info
            diagnosis += f"??  Found process using port {port}:\n"
            diagnosis += f"    PID: {pid} | Name: {name}\n"
            diagnosis += f"    Kill it with: taskkill /f /pid {pid}\n\n"
        
        diagnosis += "? SOLUTIONS:\n"
        diagnosis += f"  ? Try port 8001, 8002, etc: python run_server.py --port 8001\n"
        diagnosis += f"  ? Or run with automatic port finding: python run_server.py --auto-port\n"
        diagnosis += f"  ? Or disable firewall temporarily\n"
        diagnosis += f"  ? Or run as Administrator\n"
        diagnosis += f"  ? Or use localhost (127.0.0.1) instead of 0.0.0.0\n"
    
    # Port already in use
    elif "already in use" in error_msg.lower() or "Address already in use" in error_msg:
        diagnosis += "??  PORT IS ALREADY IN USE\n\n"
        
        process_info = get_process_using_port(port)
        if process_info:
            pid, name = process_info
            diagnosis += f"Found process using port {port}:\n"
            diagnosis += f"  PID: {pid} | Name: {name}\n"
            diagnosis += f"  Kill it with: taskkill /f /pid {pid}\n\n"
        
        diagnosis += "? SOLUTIONS:\n"
        diagnosis += f"  ? Kill the process using the port above\n"
        diagnosis += f"  ? Use the next available port: python run_server.py --port 8001\n"
        diagnosis += f"  ? Use automatic port finding: python run_server.py --auto-port\n"
    
    diagnosis += "\n" + "="*60 + "\n"
    return diagnosis


def print_startup_info(host: str, port: int, reload: bool = False, workers: int = 1) -> None:
    """
    Print beautiful startup information.
    
    Args:
        host: Host the server is binding to
        port: Port the server is binding to
        reload: Whether auto-reload is enabled
        workers: Number of workers
    """
    print("\n" + "="*70)
    print("? CRYPTO TRADE HUB - FASTAPI SERVER")
    print("="*70)
    print(f"\n? Server Configuration:")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Auto-reload: {'ON' if reload else 'OFF'}")
    print(f"   Workers: {workers}")
    print(f"\n? API Documentation:")
    print(f"   Swagger UI: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/docs")
    print(f"   ReDoc: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/redoc")
    print(f"   OpenAPI JSON: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/openapi.json")
    print(f"\n? Debug Info:")
    print(f"   Health Check: curl http://{host if host != '0.0.0.0' else 'localhost'}:{port}/health")
    print(f"\n??  Press CTRL+C to stop the server")
    print("="*70 + "\n")
