"""
Unit tests for the SecurityMonitor state machine.
Verifies state transitions:
  DISARMED -> ARMED -> BLE_LOST -> GRACE_PERIOD -> RECOVERED -> ARMED
  GRACE_PERIOD expiry -> SECURITY_EVENT -> LOCKED
"""
import asyncio
from unittest.mock import MagicMock, patch
import pytest

from nodex.config.settings import settings
from nodex.monitor.monitor import SecurityMonitor
from nodex.monitor.state import SecurityState


class DummyBLE:
    def __init__(self):
        self.connected = True
        self.rssi = -60
        self.rssi_smooth = -60.0
        self.firmware_version = "1.0.0"
        self.device_battery = 95
        self.on_connected = None
        self.on_disconnected = None


@pytest.fixture
def mock_queue():
    q = MagicMock()
    q.enqueue.return_value = 1
    return q


@pytest.fixture
def monitor(mock_queue):
    ble = DummyBLE()
    mon = SecurityMonitor(ble=ble, queue=mock_queue)
    return mon


def test_initial_state(monitor):
    assert monitor.state == SecurityState.DISARMED
    assert monitor.grace_remaining == 0.0


def test_arm_and_disarm(monitor, mock_queue):
    monitor.arm()
    assert monitor.state == SecurityState.ARMED
    mock_queue.enqueue.assert_called_with(
        pytest.approx_dict if hasattr(pytest, "approx_dict") else unittest_match("ARM")
    )

    monitor.disarm()
    assert monitor.state == SecurityState.DISARMED


def unittest_match(event_name):
    class Matcher:
        def __eq__(self, other):
            return isinstance(other, dict) and other.get("event_type") == event_name
    return Matcher()


def test_armed_signal_ok_stays_armed(monitor):
    async def _run():
        monitor.arm()
        assert monitor.state == SecurityState.ARMED

        # Tick 5 times with good signal
        for _ in range(5):
            await monitor._tick()
            assert monitor.state == SecurityState.ARMED
            assert monitor._bad_readings == 0

    asyncio.run(_run())


def test_signal_loss_transitions_to_ble_lost(monitor):
    async def _run():
        monitor.arm()
        # Degrade RSSI below threshold
        monitor._ble.rssi_smooth = settings.rssi_threshold - 10

        # First bad reading
        await monitor._tick()
        assert monitor.state == SecurityState.ARMED
        assert monitor._bad_readings == 1

        # Second bad reading
        await monitor._tick()
        assert monitor.state == SecurityState.ARMED
        assert monitor._bad_readings == 2

        # Third bad reading triggers BLE_LOST
        await monitor._tick()
        assert monitor.state == SecurityState.BLE_LOST

    asyncio.run(_run())


def test_ble_lost_transitions_to_grace_period(monitor):
    async def _run():
        monitor.arm()
        monitor._ble.rssi_smooth = -95
        # 3 bad readings -> BLE_LOST
        await monitor._tick()
        await monitor._tick()
        await monitor._tick()
        assert monitor.state == SecurityState.BLE_LOST

        # Next tick with bad signal moves to GRACE_PERIOD
        await monitor._tick()
        assert monitor.state == SecurityState.GRACE_PERIOD
        assert monitor._grace_start is not None

    asyncio.run(_run())


def test_recovery_during_grace_period(monitor):
    async def _run():
        monitor.arm()
        monitor._ble.rssi_smooth = -95
        for _ in range(4):
            await monitor._tick()
        assert monitor.state == SecurityState.GRACE_PERIOD

        # Signal recovers before expiry
        monitor._ble.rssi_smooth = -55
        await monitor._tick()
        # Transitions to ARMED (after transient RECOVERED)
        assert monitor.state == SecurityState.ARMED
        assert monitor._bad_readings == 0
        assert monitor._grace_start is None

    asyncio.run(_run())


def test_grace_period_expiry_locks(monitor):
    async def _run():
        monitor.arm()
        monitor._ble.rssi_smooth = -95
        for _ in range(4):
            await monitor._tick()
        assert monitor.state == SecurityState.GRACE_PERIOD

        # Simulate time passing beyond grace period
        monitor._grace_start = 0.0  # long ago

        with patch("ctypes.windll.user32.LockWorkStation") as mock_lock:
            await monitor._tick()
            assert monitor.state == SecurityState.LOCKED
            mock_lock.assert_called_once()

    asyncio.run(_run())
