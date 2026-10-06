# NodeX — Dashboard 1: Device & Connection Dashboard

NodeX is an automated proximity security system for Windows laptops. It continuously monitors the presence of an ESP32 BLE security token carried by the user. If the token moves out of range or disconnects while the system is **ARMED**, a grace period countdown begins. If the token is not recovered before the countdown expires, the workstation is locked (`LockWorkStation`), local audit logs are recorded, emergency alerts are dispatched, and telemetry is synced to Supabase.

---

## Key Features

- **Robust State Machine**: Six defined states (`DISARMED`, `ARMED`, `BLE_LOST`, `GRACE_PERIOD`, `RECOVERED`, `SECURITY_EVENT`, `LOCKED`).
- **RSSI Smoothing & Filtering**: Moving-average filter over a sliding window with configurable threshold and bad-reading debouncing.
- **Offline-First Event Queue**: SQLite-backed local store (`nodex_queue.db`). Events and heartbeats are recorded locally first and pushed to Supabase when connected, with exponential backoff on network failures.
- **Windows System Tray Integration**: Minimizes cleanly to the system tray (`pystray` + `Pillow`), with status indicators and quick actions.
- **PIN Protected Controls**: Arming, disarming, manual test, and quitting require a configurable SHA-256 hashed PIN.
- **Local Web UI & Live WebSocket**: Beautiful dark glassmorphism dashboard running strictly on `127.0.0.1:7878` with real-time state visualization, RSSI gauges, countdown timer, BLE scanning, and settings management.
- **Credential Security**: Passwords and tokens stored securely via Windows Credential Manager (`keyring`), never in plaintext code or config files.
- **Automated Workstation Locking**: Uses native Windows API (`ctypes.windll.user32.LockWorkStation`) on security breach.
- **Webcam Intruder Surveillance (20-Photo Ring Buffer)**: Automatically takes a webcam snapshot every 30 seconds when ARMED or under security alerts. Maintains a 20-photo circular buffer where photo 21 overwrites photo 1 locally and in the Supabase Storage bucket (`intruder-captures`). Also takes an instant emergency capture on `SECURITY_EVENT`.
- **Opt-in Telemetry**: Hardware metrics (CPU, RAM, battery, network status) collected periodically for heartbeats. IP-based location is strictly opt-in and cached.

---

## Directory Structure

```
DashBoard1/
├── nodex/
│   ├── alerts/          # Telegram & webhook notification dispatchers
│   ├── ble/             # Bleak BLE client, device scanning, RSSI smoother, mock mode
│   ├── collector/       # System metrics, battery, network, opt-in location
│   ├── config/          # Settings manager, logging configuration, hardware fingerprinting
│   ├── monitor/         # Security state machine, LockWorkStation trigger, grace period
│   ├── sync/            # SQLite offline queue, Supabase sync engine with retry backoff
│   └── ui/              # FastAPI server, WebSockets, static dashboard assets, system tray
├── scripts/
│   └── setup.py         # First-run setup wizard (Credential Manager & Task Scheduler auto-start)
├── supabase/
│   └── schema.sql       # PostgreSQL schema with Row-Level Security (RLS) policies
├── tests/               # Pytest unit tests (state machine, offline queue, BLE filter, etc.)
├── .env.example         # Template for Supabase URL and anonymous keys
├── main.py              # Application entry point with single-instance mutex
└── requirements.txt     # Python package dependencies
```

---

## Setup & Installation

### 1. Prerequisites
- Windows 10/11
- Python 3.11+
- Bluetooth 4.0+ BLE adapter

### 2. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and fill in your Supabase project credentials:
```powershell
cp .env.example .env
```
Update `.env` with:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-public-key
NODEX_USER_EMAIL=user@example.com
```

### 4. Supabase Database Schema
Run the SQL script provided in `supabase/schema.sql` inside your Supabase project's **SQL Editor**. This sets up:
- `laptops`: Hardware-fingerprinted device records
- `events`: Append-only security audit log with RLS
- `heartbeats`: Periodic device status telemetry
- `alerts`: Notification dispatch audit log

### 5. First-Run Setup Wizard
Run the setup script to store your Supabase password securely in Windows Credential Manager, set a management PIN, and optionally register Windows auto-start:
```powershell
python scripts/setup.py
```

---

## Running NodeX

### Standard Run
```powershell
python main.py
```
- Starts the background services and binds the local web UI to `http://127.0.0.1:7878`.
- Minimizes to the Windows system tray.

### Mock / Testing Mode (Without Physical ESP32)
Simulate BLE signal, RSSI fluctuations, and token disconnects without needing physical hardware:
```powershell
python main.py --mock-ble
```

### CLI Flags
- `--mock-ble`: Enables simulated BLE token device with fluctuating signal.
- `--no-tray`: Disables system tray icon (useful for headless testing or CI).
- `--port <PORT>`: Overrides the default local UI port (default: `7878`).

---

## REST & WebSocket API

The local web server binds strictly to `127.0.0.1` and provides:

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serves the interactive device dashboard |
| `/ws` | WebSocket | Real-time state updates, RSSI broadcasts, and control actions |
| `/api/status` | GET | Current system state snapshot |
| `/api/arm` | POST | Arms the monitor (requires JSON body: `{"pin": "..."}`) |
| `/api/disarm` | POST | Disarms the monitor (requires JSON body: `{"pin": "..."}`) |
| `/api/test` | POST | Simulates a test event without locking workstation |
| `/api/pair/scan` | POST | Initiates BLE scan for nearby ESP32 devices |
| `/api/pair/select` | POST | Pairs chosen BLE MAC address (`{"address": "...", "name": "..."}`) |
| `/api/settings` | GET/POST | Reads or updates runtime thresholds (RSSI threshold, grace period) |
| `/api/sync/status` | GET | SQLite queue pending items count and sync status |

---

## Testing

Run the automated test suite with pytest:
```powershell
pytest tests -v
```
All 18 unit tests cover:
- BLE RSSI sliding window filter and reset logic
- SQLite offline queue enqueueing, batching, sync confirmation, and error tracking
- State machine progression: `ARMED` → `BLE_LOST` → `GRACE_PERIOD` → `RECOVERED` / `LOCKED`
- Workstation lock trigger prevention in test mode
- Collector system metrics inspection
- PIN hashing and verification
