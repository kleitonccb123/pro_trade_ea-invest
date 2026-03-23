#!/usr/bin/env python3
"""
? Quick Backend Health Check
Testa se o servidor est? inicializando corretamente
"""

import subprocess
import sys
import time
import socket
from pathlib import Path

def port_is_open(host="127.0.0.1", port=8000, timeout=1):
    """Check if a port is open and responding"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def test_server():
    """Test if server can start"""
    print("? Testing Backend Startup...\n")
    
    # Find backend directory
    backend_dir = Path(__file__).parent
    print(f"? Backend directory: {backend_dir}\n")
    
    # Test port 8000
    print("? Checking if port 8000 is available...")
    if port_is_open("127.0.0.1", 8000):
        print("? Port 8000 is OCCUPIED")
        print("   Will try auto-port mode...\n")
    else:
        print("? Port 8000 is FREE\n")
    
    # Try to import port_utils
    print("? Checking port_utils module...")
    try:
        sys.path.insert(0, str(backend_dir))
        from app.core.port_utils import is_port_available, find_free_port
        print("? port_utils imported successfully\n")
    except Exception as e:
        print(f"? Failed to import port_utils: {e}\n")
        return False
    
    # Test finding a free port
    print("? Finding available port...")
    try:
        port = find_free_port("127.0.0.1", start_port=8000, max_attempts=10)
        print(f"? Found available port: {port}\n")
    except RuntimeError as e:
        print(f"? {e}\n")
        return False
    
    # Try to start the server briefly
    print(f"? Attempting to start server on port {port}...")
    print("? Waiting 10 seconds... (Press Ctrl+C to test early)\n")
    
    try:
        proc = subprocess.Popen(
            [sys.executable, "run_server.py", "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        for i in range(10):
            time.sleep(1)
            if port_is_open("127.0.0.1", port):
                print(f"\n? SERVER STARTED SUCCESSFULLY ON PORT {port}!")
                print(f"? Access Swagger UI: http://127.0.0.1:{port}/docs\n")
                proc.terminate()
                return True
            print(f"? Still waiting... ({i+1}/10)")
        
        # If we get here, server didn't respond
        print(f"\n??  Server process is running but not responding on port {port}")
        print("This might indicate a startup initialization issue.\n")
        
        # Try to get any error output
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)
        
        if stderr:
            print("? Error output:")
            print(stderr)
            return False
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n??  Test interrupted by user")
        proc.terminate()
        return False
    except Exception as e:
        print(f"\n? Error during startup test: {e}\n")
        return False


if __name__ == "__main__":
    success = test_server()
    sys.exit(0 if success else 1)
