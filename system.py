import platform
import socket
from datetime import datetime

import psutil
import cpuinfo
import GPUtil
import requests

print("========== PC INFORMATION ==========")

# PC Name
print("PC Name:", socket.gethostname())

# Operating System
print("Operating System:", platform.system())
print("OS Version:", platform.version())

# Processor
cpu = cpuinfo.get_cpu_info()
print("Processor:", cpu["brand_raw"])

# CPU Cores
print("Physical Cores:", psutil.cpu_count(logical=False))
print("Logical Cores:", psutil.cpu_count(logical=True))

# RAM
ram = psutil.virtual_memory()
print("RAM Total: {:.2f} GB".format(ram.total / (1024**3)))
print("RAM Usage:", ram.percent, "%")

# Storage
disk = psutil.disk_usage('/')
print("Storage Total: {:.2f} GB".format(disk.total / (1024**3)))
print("Storage Free: {:.2f} GB".format(disk.free / (1024**3)))

# GPU
gpus = GPUtil.getGPUs()
if gpus:
    for gpu in gpus:
        print("GPU:", gpu.name)
        print("GPU Memory:", gpu.memoryTotal, "MB")
else:
    print("GPU: Not Found")

print("\n========== BATTERY ==========")

battery = psutil.sensors_battery()
if battery:
    print("Battery:", battery.percent, "%")
    print("Charging:", battery.power_plugged)
else:
    print("Battery information not available.")

print("\n========== DATE & TIME ==========")

now = datetime.now()
print("Date:", now.strftime("%d-%m-%Y"))
print("Time:", now.strftime("%H:%M:%S"))

print("\n========== LOCATION ==========")

try:
    data = requests.get("https://ipapi.co/json/").json()

    print("Public IP:", data.get("ip"))
    print("City:", data.get("city"))
    print("Region:", data.get("region"))
    print("Country:", data.get("country_name"))
    print("Latitude:", data.get("latitude"))
    print("Longitude:", data.get("longitude"))
except:
    print("Unable to fetch location.")