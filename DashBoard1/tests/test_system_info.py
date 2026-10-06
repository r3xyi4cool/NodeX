import asyncio
from nodex.collector.system_info import collect_snapshot


def test_collect_snapshot():
    async def _run():
        snapshot = await collect_snapshot()
        assert isinstance(snapshot, dict)
        expected_keys = [
            "laptop_name",
            "os",
            "cpu_percent",
            "ram_percent",
            "ram_total_gb",
            "battery_percent",
            "charging",
            "network_online",
            "network_ip",
            "timestamp",
        ]
        for key in expected_keys:
            assert key in snapshot, f"Missing key {key} in snapshot"

        assert isinstance(snapshot["cpu_percent"], (int, float))
        assert isinstance(snapshot["ram_percent"], (int, float))
        assert isinstance(snapshot["network_online"], bool)

    asyncio.run(_run())
