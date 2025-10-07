#!/usr/bin/env python3
# Copyright (c) 2022-2023 Geosiris.
# SPDX-License-Identifier: Apache-2.0

"""
Simple test script to verify the listener paradigm implementation in ETPSimpleClient.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "py_etp_client"))

from py_etp_client.serverprotocols import *  # noqa: E402
from py_etp_client.etpsimpleclient import ETPSimpleClient, EventType  # noqa: E402


def test_listener_paradigm():
    """Test the listener paradigm functionality."""

    # Storage for captured events
    captured_events = []

    def test_listener(event_type: EventType, **kwargs):
        """Test listener function that captures events."""
        captured_events.append({"event_type": event_type, "kwargs": kwargs})
        print(f"Listener called: {event_type.value} with args: {list(kwargs.keys())}")

    def error_listener(event_type: EventType, **kwargs):
        """Another test listener specifically for error events."""
        if event_type == EventType.ON_ERROR:
            print(f"Error listener triggered: {kwargs.get('error', 'Unknown error')}")

    # Create client (this won't actually connect since we're just testing the listener infrastructure)
    client = ETPSimpleClient(url="wss://example.com", spec=None)

    # Test 1: Add listeners
    print("Test 1: Adding listeners...")
    client.add_listener(EventType.ON_OPEN, test_listener)
    client.add_listener(EventType.ON_CLOSE, test_listener)
    client.add_listener(EventType.ON_ERROR, test_listener)
    client.add_listener(EventType.ON_ERROR, error_listener)  # Multiple listeners for same event
    client.add_listener(EventType.START, test_listener)

    # Verify listeners were added
    assert len(client.listeners[EventType.ON_OPEN]) == 1
    assert len(client.listeners[EventType.ON_CLOSE]) == 1
    assert len(client.listeners[EventType.ON_ERROR]) == 2  # Two listeners for error
    assert len(client.listeners[EventType.START]) == 1
    assert len(client.listeners[EventType.ON_MESSAGE]) == 0  # No listeners added
    print("✓ Listeners added successfully")

    client.add_listener(EventType.ON_MESSAGE, test_listener)

    # Test 2: Trigger listeners manually (simulating events)
    print("\nTest 2: Triggering listeners...")
    client._notify_listeners(EventType.ON_OPEN, ws="mock_ws")
    client._notify_listeners(EventType.ON_ERROR, ws="mock_ws", error="Test error")
    client._notify_listeners(EventType.START)

    # Verify events were captured
    assert len(captured_events) == 3  # 3 events triggered (on_open, on_error, start)
    assert captured_events[0]["event_type"] == EventType.ON_OPEN
    assert captured_events[1]["event_type"] == EventType.ON_ERROR
    assert captured_events[2]["event_type"] == EventType.START
    print("✓ Listeners triggered successfully")

    # Test 3: Remove listener
    print("\nTest 3: Removing listeners...")
    success = client.remove_listener(EventType.ON_ERROR, test_listener)
    assert success
    assert len(client.listeners[EventType.ON_ERROR]) == 1  # One listener remaining

    # Try to remove non-existent listener
    success = client.remove_listener(EventType.ON_ERROR, test_listener)
    assert not success  # Should return False since listener was already removed
    print("✓ Listener removal works correctly")

    # Test 4: Error handling in listeners
    print("\nTest 4: Error handling in listeners...")

    def faulty_listener(event_type: EventType, **kwargs):
        raise Exception("Intentional test error")

    client.add_listener(EventType.ON_CLOSE, faulty_listener)

    # This should not crash the client, just log an error
    client._notify_listeners(EventType.ON_CLOSE, ws="mock_ws", close_status_code=1000, close_msg="Test close")
    print("✓ Error handling in listeners works correctly")

    # Test 5: Validate EventType enum
    print("\nTest 5: EventType enum validation...")
    try:
        client.add_listener("invalid_event", test_listener)  # type: ignore
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "event_type must be an instance of EventType" in str(e)
        print("✓ EventType validation works correctly")

    print("\n🎉 All tests passed! The listener paradigm is working correctly.")

    # Test 6: on message
    print("\nTest 6: on message...")

    client._notify_listeners(EventType.ON_MESSAGE, ws="mock_ws", message="Test message")


if __name__ == "__main__":
    test_listener_paradigm()
