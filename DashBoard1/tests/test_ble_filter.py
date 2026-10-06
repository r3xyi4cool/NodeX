"""
Unit tests for BLE RSSI filtering and smoothing.
"""
from nodex.ble.manager import RssiSmoother


def test_smoother_initial_state():
    smoother = RssiSmoother(window=5)
    assert smoother.current is None


def test_smoother_moving_average():
    smoother = RssiSmoother(window=4)

    # First value
    avg1 = smoother.add(-70)
    assert avg1 == -70.0
    assert smoother.current == -70.0

    # Second value
    avg2 = smoother.add(-80)
    assert avg2 == -75.0
    assert smoother.current == -75.0

    # Add two more
    smoother.add(-60)
    avg4 = smoother.add(-70)
    # Average of [-70, -80, -60, -70] = -280 / 4 = -70.0
    assert avg4 == -70.0

    # Fifth value rolls out the first (-70)
    avg5 = smoother.add(-50)
    # Window now contains [-80, -60, -70, -50] = -260 / 4 = -65.0
    assert avg5 == -65.0
    assert smoother.current == -65.0


def test_smoother_reset():
    smoother = RssiSmoother(window=3)
    smoother.add(-60)
    smoother.add(-70)
    assert smoother.current is not None

    smoother.reset()
    assert smoother.current is None
