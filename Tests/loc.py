import requests

url = "https://location.services.mozilla.com/v1/geolocate?key=test"

payload = {
    "wifiAccessPoints": [
        {
            "macAddress": "AA:BB:CC:DD:EE:FF",
            "signalStrength": -45
        },
        {
            "macAddress": "11:22:33:44:55:66",
            "signalStrength": -62
        }
    ]
}

response = requests.post(url, json=payload)
print("Status:", response.status_code)
print("Headers:", response.headers)
print("Body:")
print(response.text)