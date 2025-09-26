"""
Test INDI client backend events during device disconnect.

This test checks what events the INDI client actually receives from PyIndi
when a device is connected and then disconnected.
"""

import pytest
import asyncio
import time
import requests
import threading
from unittest.mock import Mock, patch


@pytest.mark.asyncio
class TestIndiClientEvents:
    """Test INDI client event handling during device operations."""

    async def test_indi_client_events_on_disconnect(self, indi_webmanager_process):
        """
        Test what events the INDI client receives when disconnecting a device.

        This test:
        1. Starts INDI Web Manager with simulators
        2. Patches the INDI client event listener to capture all events
        3. Connects then disconnects the Telescope Simulator
        4. Analyzes what events were actually received by the backend
        """
        proc_info = indi_webmanager_process
        device_name = "Telescope Simulator"

        # Wait for the INDI server and simulators to be ready
        await self._wait_for_device_availability(proc_info, device_name)

        # Start a server profile to ensure INDI client is connected
        await self._start_server_profile(proc_info)

        # Storage for captured INDI client events
        captured_events = []
        event_lock = threading.Lock()

        def capture_event(event_type, device, data):
            """Capture all events sent to INDI client listeners."""
            with event_lock:
                captured_events.append({
                    'timestamp': time.time(),
                    'event_type': event_type,
                    'device': device,
                    'data': data
                })
                print(f"INDI Client Event: {event_type} - Device: {device} - Data: {data}")

        # Access the running INDI client and add our event listener
        from indiweb.indi_client import get_indi_client

        # Wait a bit to ensure INDI client is fully initialized
        await asyncio.sleep(5)

        indi_client = get_indi_client()
        if not indi_client:
            pytest.fail("INDI client not available")

        print(f"INDI client status: connected={indi_client.is_connected()}")

        # If not connected, try to connect manually
        if not indi_client.is_connected():
            print("INDI client not connected, attempting to connect...")
            from indiweb.indi_client import start_indi_client

            # Try to start the INDI client manually (use the test fixture port)
            indi_port = proc_info['indi_port']
            print(f"Attempting to connect INDI client to localhost:{indi_port}")
            success = start_indi_client('localhost', indi_port)
            if success:
                await asyncio.sleep(5)  # Wait for connection
                print(f"Manual connection attempt result: {indi_client.is_connected()}")

        if not indi_client.is_connected():
            pytest.fail("INDI client still not connected after manual attempt")

        print(f"INDI client connected: {indi_client.is_connected()}")
        print(f"Available devices: {indi_client.get_devices()}")

        # Add our event listener
        indi_client.add_listener(capture_event)
        print("Event listener added to INDI client")

        # Clear any initial events
        captured_events.clear()

        # First, connect the telescope to ensure it has properties
        print("Connecting Telescope Simulator...")
        connect_success = await self._connect_device(proc_info, device_name)
        if not connect_success:
            pytest.fail("Failed to connect device")

        # Wait for connection events
        await asyncio.sleep(10)

        connect_events = len(captured_events)
        print(f"Events captured during connection: {connect_events}")
        for i, event in enumerate(captured_events):
            print(f"  Connect Event {i+1}: {event['event_type']} - {event['data'].get('name', 'N/A')}")

        # Clear events before disconnect
        captured_events.clear()

        # Now disconnect the telescope
        print("Disconnecting Telescope Simulator...")
        disconnect_success = await self._disconnect_device(proc_info, device_name)
        if not disconnect_success:
            pytest.fail("Failed to disconnect device")

        # Wait for disconnect events
        print("Waiting for disconnect events...")
        await asyncio.sleep(15)

        disconnect_events = len(captured_events)
        print(f"Events captured during disconnect: {disconnect_events}")

        # Analyze the events
        property_updated_events = []
        property_defined_events = []
        property_deleted_events = []
        message_events = []

        for event in captured_events:
            event_type = event['event_type']
            if event_type == 'property_updated':
                property_updated_events.append(event)
            elif event_type == 'property_defined':
                property_defined_events.append(event)
            elif event_type == 'property_deleted':
                property_deleted_events.append(event)
            elif event_type == 'message':
                message_events.append(event)

        print(f"\n=== Event Analysis ===")
        print(f"Total events: {disconnect_events}")
        print(f"Property Updated: {len(property_updated_events)}")
        print(f"Property Defined: {len(property_defined_events)}")
        print(f"Property Deleted: {len(property_deleted_events)}")
        print(f"Messages: {len(message_events)}")

        print(f"\n=== Detailed Events ===")
        for i, event in enumerate(captured_events):
            event_data = event['data']
            property_name = event_data.get('name', 'N/A')
            print(f"{i+1}. {event['event_type']} - Device: {event['device']} - Property: {property_name}")

        # Check for CONNECTION property updates
        connection_events = [e for e in captured_events
                           if e['data'].get('name') == 'CONNECTION']
        print(f"\nCONNECTION property events: {len(connection_events)}")
        for event in connection_events:
            print(f"  CONNECTION {event['event_type']}: {event['data']}")

        # Remove our listener
        indi_client.remove_listener(capture_event)

        # Assertions
        assert disconnect_events > 0, "No events were captured during disconnect"

        # At minimum, we should see a CONNECTION property update
        assert len(connection_events) > 0, "No CONNECTION property events received"

        # Check if we received any property deletion events
        if len(property_deleted_events) > 0:
            print(f"SUCCESS: {len(property_deleted_events)} property deletion events received")
            for event in property_deleted_events:
                print(f"  Deleted property: {event['data'].get('name')}")
        else:
            print("INFO: No property deletion events - this may be normal INDI behavior")

        # The test passes if we received events (even if no deletions)
        print(f"\nTest completed: {disconnect_events} total events captured from INDI client")

    async def _wait_for_device_availability(self, proc_info, device_name, timeout=30):
        """Wait for the device to be available via HTTP API."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{proc_info['base_url']}/api/devices", timeout=5)
                if response.status_code == 200:
                    devices = response.json()
                    device_names = [d.get('device', d) if isinstance(d, dict) else d for d in devices]
                    if device_name in device_names:
                        print(f"Device {device_name} is available")
                        return True
            except requests.RequestException as e:
                print(f"Error checking device availability: {e}")

            await asyncio.sleep(1)

        pytest.fail(f"Device {device_name} not available within {timeout}s")

    async def _start_server_profile(self, proc_info):
        """Start the default server profile to initialize INDI client."""
        try:
            profiles_response = requests.get(f"{proc_info['base_url']}/api/profiles", timeout=10)
            if profiles_response.status_code != 200:
                print(f"Failed to get profiles: {profiles_response.text}")
                return False

            profiles = profiles_response.json()
            if not profiles:
                print("No profiles available")
                return False

            profile_name = profiles[0]['name']
            print(f"Starting profile: {profile_name}")

            start_response = requests.post(
                f"{proc_info['base_url']}/api/server/start/{profile_name}",
                timeout=30
            )

            print(f"Start server response: {start_response.status_code}")
            if start_response.status_code == 200:
                await asyncio.sleep(10)  # Wait for INDI client to connect
                return True
            else:
                print(f"Failed to start server: {start_response.text}")
                return False

        except requests.RequestException as e:
            print(f"Error starting server profile: {e}")
            return False

    async def _connect_device(self, proc_info, device_name):
        """Connect a device by setting its CONNECTION property."""
        try:
            from urllib.parse import quote
            encoded_device_name = quote(device_name)

            connect_data = {
                "elements": {
                    "CONNECT": "On",
                    "DISCONNECT": "Off"
                }
            }

            response = requests.post(
                f"{proc_info['base_url']}/api/devices/{encoded_device_name}/properties/CONNECTION/set",
                json=connect_data,
                timeout=10
            )

            print(f"Connect response status: {response.status_code}")
            return response.status_code == 200

        except requests.RequestException as e:
            print(f"Error connecting device: {e}")
            return False

    async def _disconnect_device(self, proc_info, device_name):
        """Disconnect a device by setting its CONNECTION property."""
        try:
            from urllib.parse import quote
            encoded_device_name = quote(device_name)

            disconnect_data = {
                "elements": {
                    "CONNECT": "Off",
                    "DISCONNECT": "On"
                }
            }

            response = requests.post(
                f"{proc_info['base_url']}/api/devices/{encoded_device_name}/properties/CONNECTION/set",
                json=disconnect_data,
                timeout=10
            )

            print(f"Disconnect response status: {response.status_code}")
            return response.status_code == 200

        except requests.RequestException as e:
            print(f"Error disconnecting device: {e}")
            return False