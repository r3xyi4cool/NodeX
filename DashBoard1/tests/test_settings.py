"""
Unit tests for Settings and PIN management.
"""
from nodex.config.settings import Settings


def test_pin_verification():
    s = Settings()
    # When no PIN is configured, verify_pin always returns True
    s.arm_pin_hash = None
    assert s.verify_pin("1234") is True
    assert s.verify_pin("") is True

    # Set a PIN
    s.set_pin("1234")
    assert s.arm_pin_hash is not None
    assert s.verify_pin("1234") is True
    assert s.verify_pin("9999") is False
    assert s.verify_pin("") is False

    # Clean up
    s.arm_pin_hash = None
