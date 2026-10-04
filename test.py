from winrt.windows.devices.geolocation import Geolocator
import asyncio

async def test():
    locator = Geolocator()
    print("Location Status:", locator.location_status)

asyncio.run(test())