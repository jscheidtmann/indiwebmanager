"""
Pytest configuration and fixtures for INDI Web Manager tests.
"""

import pytest
import asyncio
import subprocess
import time
import os
import signal
import tempfile
import shutil
from pathlib import Path


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_indi_config():
    """Create a temporary INDI configuration directory with default config."""
    temp_dir = tempfile.mkdtemp(prefix="indi_test_")

    # Copy all files from ~/.indi to temporary directory
    indi_config_dir = Path.home() / ".indi"
    if indi_config_dir.exists():
        shutil.copytree(indi_config_dir, temp_dir, dirs_exist_ok=True)

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def free_port():
    """Find a free port for testing."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture
def indi_webmanager_process(free_port, temp_indi_config):
    """
    Start INDI Web Manager in a separate process for testing.

    Returns:
        dict: Contains process info and connection details
    """
    # Find the virtual environment python
    venv_python = os.path.join(os.getcwd(), '.venv', 'bin', 'python')
    if not os.path.exists(venv_python):
        pytest.skip("Virtual environment not found")

    web_port = free_port
    indi_port = free_port + 1
    fifo_path = os.path.join(temp_indi_config, 'indiFIFO')

    # Start the web manager
    cmd = [
        venv_python, '-m', 'indiweb.main',
        '--port', str(web_port),
        '--indi-port', str(indi_port),
        '--conf', temp_indi_config,
        '--fifo', fifo_path,
        '--verbose'
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd(),
        env=os.environ.copy()
    )

    # Wait for the server to start by trying to connect to the web port
    start_time = time.time()
    server_started = False

    while time.time() - start_time < 30:  # 30 second timeout
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            pytest.fail(f"INDI Web Manager failed to start: {stderr.decode()}")

        # Check if server has started by trying to connect to the port
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', web_port))
                if result == 0:
                    server_started = True
                    break
        except:
            pass

        time.sleep(0.5)

    if not server_started:
        process.terminate()
        process.wait()
        pytest.fail("INDI Web Manager did not start within timeout")

    # Give it a moment more to fully initialize INDI simulators
    time.sleep(15)  # Increased time for event listener registration

    yield {
        'process': process,
        'web_port': web_port,
        'indi_port': indi_port,
        'host': 'localhost',
        'base_url': f'http://localhost:{web_port}',
        'ws_url': f'ws://localhost:{web_port}'
    }

    # Cleanup
    try:
        process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()