"""
Debug test to check what devices are available
"""

import pytest
import requests
import time


@pytest.mark.asyncio
async def test_check_available_devices(indi_webmanager_process):
    """Debug test to see what devices are available."""
    proc_info = indi_webmanager_process

    # Wait a bit for everything to initialize
    print("Waiting for initialization...")
    time.sleep(10)

    try:
        # Check devices endpoint
        response = requests.get(f"{proc_info['base_url']}/api/devices", timeout=10)
        print(f"Devices API status: {response.status_code}")

        if response.status_code == 200:
            devices = response.json()
            print(f"Available devices: {devices}")
            print(f"Number of devices: {len(devices) if devices else 0}")
        else:
            assert False, f"Error response: {response.text}"

        # Check server status
        try:
            status_response = requests.get(f"{proc_info['base_url']}/api/server/status", timeout=10)
            print(f"Server status: {status_response.json() if status_response.status_code == 200 else status_response.text}")
        except Exception as e:
            assert False, f"Error checking server status: {e}"

        # Try to get server info
        try:
            info_response = requests.get(f"{proc_info['base_url']}/api/server/drivers", timeout=10)
            print(f"Server drivers: {info_response.json() if info_response.status_code == 200 else info_response.text}")
        except Exception as e:
            assert False, f"Error checking server drivers: {e}"

    except Exception as e:
        assert False, f"Error: {e}"

    # Always pass this debug test
    assert True