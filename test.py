
import asyncio
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
STATUS_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"


async def main():
    print("Scanning for NodeX...")

    devices = await BleakScanner.discover(timeout=10)

    nodex = next(
        (device for device in devices if device.name == "NodeX"),
        None
    )

    if nodex is None:
        print("NodeX not found.")
        return

    print(f"Found NodeX: {nodex.address}")

    async with BleakClient(nodex.address, timeout=20) as client:
        print("Connected:", client.is_connected)

        services = client.services
        service = services.get_service(SERVICE_UUID)

        if service is None:
            print("NodeX service not found.")
            print("Available services:")
            for item in services:
                print(item.uuid)
            return

        characteristic = service.get_characteristic(STATUS_UUID)

        if characteristic is None:
            print("Status characteristic not found.")
            return

        value = await client.read_gatt_char(characteristic)
        print("ESP32 status:", value.decode("utf-8"))

    print("Disconnected from NodeX")


asyncio.run(main())
