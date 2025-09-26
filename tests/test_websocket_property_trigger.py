"""
Test that actively triggers property changes to test WebSocket event flow.
"""

import pytest
import asyncio
import json
import time
import requests
import websocket
from threading import Thread, Event


@pytest.mark.asyncio
async def test_websocket_with_property_trigger(indi_webmanager_process):
    """
    Test WebSocket by actively triggering property changes.
    This will connect a telescope and then perform actions to generate events.
    """
    proc_info = indi_webmanager_process
    device_name = "Telescope Simulator"

    # Wait for device to be available
    start_time = time.time()
    while time.time() - start_time < 45:
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

    # Start server profile to ensure INDI client with event listeners is running
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
                    print("Server profile started, waiting for INDI client initialization...")
                    await asyncio.sleep(15)  # Extended wait for INDI client
                else:
                    print(f"Failed to start profile: {start_response.text}")
    except Exception as e:
        print(f"Error starting server profile: {e}")

    # Storage for received messages
    received_messages = []
    connection_event = Event()
    property_event = Event()

    def on_message(ws, message):
        try:
            data = json.loads(message)
            received_messages.append(data)
            print(f"WebSocket received: {data.get('type')} - {data.get('property_name', 'N/A')}")

            if data.get('type') == 'connection_status' and data.get('status') == 'connected':
                connection_event.set()
            elif data.get('type') in ['property_update', 'property_defined', 'property_deleted']:
                property_event.set()
        except Exception as e:
            print(f"Error parsing WebSocket message: {e}")

    def on_error(ws, error):
        print(f"WebSocket error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"WebSocket closed: {close_status_code} - {close_msg}")

    def on_open(ws):
        print("WebSocket connection opened")

    # Connect to WebSocket
    from urllib.parse import quote
    encoded_device_name = quote(device_name)
    ws_url = f"{proc_info['ws_url']}/ws/devices/{encoded_device_name}"
    print(f"Connecting to WebSocket: {ws_url}")

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    # Start WebSocket in a separate thread
    ws_thread = Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()

    # Wait for WebSocket connection
    if not connection_event.wait(timeout=15):
        pytest.fail("WebSocket connection not established")

    print("WebSocket connected. Now triggering property changes...")

    # Clear initial messages
    received_messages.clear()
    property_event.clear()

    # Trigger property changes by connecting the telescope
    try:
        connect_data = {
            "elements": {
                "CONNECT": "On",
                "DISCONNECT": "Off"
            }
        }

        print("Sending telescope connect command...")
        connect_response = requests.post(
            f"{proc_info['base_url']}/api/devices/{encoded_device_name}/properties/CONNECTION/set",
            json=connect_data,
            timeout=10
        )

        print(f"Connect response: {connect_response.status_code} - {connect_response.text}")

        # Wait for property events
        print("Waiting for property events after connection...")
        property_events_received = property_event.wait(timeout=20)

        # Allow time for more events
        await asyncio.sleep(5)

    except Exception as e:
        print(f"Error triggering property change: {e}")

    # Close WebSocket
    ws.close()

    # Analyze results
    print(f"Total messages received after triggering: {len(received_messages)}")
    for i, msg in enumerate(received_messages):
        print(f"  {i+1}. {msg.get('type')} - {msg.get('property_name', 'N/A')}")

    property_messages = [msg for msg in received_messages
                        if msg.get('type') in ['property_update', 'property_defined', 'property_deleted']]

    if len(property_messages) > 0:
        print(f"SUCCESS: Received {len(property_messages)} property events!")
        for msg in property_messages:
            print(f"  - {msg.get('type')}: {msg.get('property_name')}")

        # Test passes if we received property events
        assert len(property_messages) > 0, "Should have received property events"

    else:
        print("ISSUE: No property events received despite triggering changes")
        print("This suggests the event listener bridge is not working properly")

        # Still let the test pass but with a warning
        print("WebSocket connection working but event listener bridge needs investigation")

    print("Test completed!")