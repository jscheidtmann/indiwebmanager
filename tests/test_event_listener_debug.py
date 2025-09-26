"""
Debug test to check if INDI event listener is actually being called.
"""

import pytest
import asyncio
import time
import requests
import threading


@pytest.mark.asyncio
async def test_event_listener_debug(indi_webmanager_process):
    """
    Debug test to see if INDI event listener is being called at all.
    """
    proc_info = indi_webmanager_process
    device_name = "Telescope Simulator"

    # Wait for device availability
    start_time = time.time()
    while time.time() - start_time < 30:
        try:
            response = requests.get(f"{proc_info['base_url']}/api/devices", timeout=5)
            if response.status_code == 200:
                devices = response.json()
                device_names = [d.get('device', d) if isinstance(d, dict) else d for d in devices]
                if device_name in device_names:
                    print(f"Device {device_name} is available")
                    break
        except:
            pass
        await asyncio.sleep(2)
    else:
        pytest.fail("Device not available")

    # Start server profile
    try:
        profiles_response = requests.get(f"{proc_info['base_url']}/api/profiles", timeout=10)
        if profiles_response.status_code == 200:
            profiles = profiles_response.json()
            if profiles:
                profile_name = profiles[0]['name']
                print(f"Starting server profile: {profile_name}")
                start_response = requests.post(
                    f"{proc_info['base_url']}/api/server/start/{profile_name}",
                    timeout=30
                )
                if start_response.status_code == 200:
                    print("Server profile started")
                    await asyncio.sleep(15)  # Wait for initialization
                else:
                    print(f"Failed to start profile: {start_response.text}")
                    pytest.fail("Could not start server profile")
    except Exception as e:
        pytest.fail(f"Error starting server profile: {e}")

    # Patch the event listener to add debugging
    def debug_event_listener(event_type, device, data):
        print(f"DEBUG: Event listener called! Type: {event_type}, Device: {device}, Property: {data.get('name', 'N/A')}")

    # Try to access the running INDI client directly
    from indiweb.indi_client import get_indi_client
    indi_client = get_indi_client()

    if not indi_client:
        pytest.fail("INDI client not available")

    if not indi_client.is_connected():
        pytest.fail("INDI client not connected")

    print(f"INDI client connected: {indi_client.is_connected()}")
    print(f"Available devices: {indi_client.get_devices()}")
    print(f"Number of registered listeners: {len(indi_client.listeners) if hasattr(indi_client, 'listeners') else 'Unknown'}")

    # Add our debug listener
    indi_client.add_listener(debug_event_listener)
    print("Debug event listener added")

    # Trigger property change
    from urllib.parse import quote
    encoded_device_name = quote(device_name)

    connect_data = {
        "elements": {
            "CONNECT": "On",
            "DISCONNECT": "Off"
        }
    }

    print("Triggering telescope connection...")
    connect_response = requests.post(
        f"{proc_info['base_url']}/api/devices/{encoded_device_name}/properties/CONNECTION/set",
        json=connect_data,
        timeout=10
    )

    print(f"Connect response: {connect_response.status_code}")

    # Wait and watch for events
    print("Waiting for events...")
    await asyncio.sleep(10)

    print("Test completed - check output above for event listener calls")

    # The test passes - we're just debugging
    assert True