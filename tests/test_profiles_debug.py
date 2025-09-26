"""Debug test to check profiles API response"""

import pytest
import requests


@pytest.mark.asyncio
async def test_check_profiles(indi_webmanager_process):
    """Debug test to see profiles API response."""
    proc_info = indi_webmanager_process

    try:
        # Check profiles endpoint
        response = requests.get(f"{proc_info['base_url']}/api/profiles", timeout=10)
        print(f"Profiles API status: {response.status_code}")
        print(f"Profiles response: {response.json()}")
        print(f"Profiles type: {type(response.json())}")

    except Exception as e:
        print(f"Error: {e}")

    # Always pass this debug test
    assert True