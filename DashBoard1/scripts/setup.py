"""
NodeX First-Run Setup Script
=============================
Run ONCE to:
  1. Store the Supabase password in Windows Credential Manager (via keyring)
  2. Optionally set a PIN
  3. Register a Task Scheduler entry for auto-start at login
  4. Open the dashboard

Usage:
    python scripts/setup.py
"""
from __future__ import annotations

import getpass
import os
import subprocess
import sys
from pathlib import Path

# Ensure DashBoard1 root is on path
_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

# Ensure safe encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import keyring
from nodex.config.settings import settings
from nodex.sync.supabase_sync import KEYRING_SERVICE, KEYRING_USER_PWD


TASK_NAME = "NodeX_Dashboard1"


def store_credentials() -> None:
    email = settings.nodex_user_email
    if not email:
        print("\n[!] NODEX_USER_EMAIL not set in .env")
        email = input("Enter your Supabase email: ").strip()

    password = getpass.getpass(f"Enter Supabase password for {email}: ")
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER_PWD, password)
    print(f"[+] Password stored in Windows Credential Manager (service={KEYRING_SERVICE})")


def set_pin() -> None:
    choice = input("\nSet a security PIN? (y/N): ").strip().lower()
    if choice == 'y':
        pin = getpass.getpass("Enter new PIN: ")
        confirm = getpass.getpass("Confirm PIN: ")
        if pin != confirm:
            print("[-] PINs do not match - skipping")
            return
        settings.set_pin(pin)
        print("[+] PIN set and hashed in nodex_config.json")
    else:
        print("Skipped - no PIN set (disarm/quit will not require PIN)")


def create_task_scheduler_entry() -> None:
    """Create a Windows Task Scheduler task that starts NodeX at login."""
    python_exe = sys.executable
    main_py    = (_HERE / "main.py").resolve()

    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>NodeX Dashboard 1 — BLE Proximity Security Monitor</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{python_exe}</Command>
      <Arguments>"{main_py}"</Arguments>
      <WorkingDirectory>{_HERE}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    xml_path = _HERE / "data" / "nodex_task.xml"
    xml_path.parent.mkdir(exist_ok=True)
    xml_path.write_text(xml, encoding="utf-16")

    try:
        subprocess.run(
            ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml_path), "/F"],
            check=True, capture_output=True,
        )
        print(f"[+] Task Scheduler entry '{TASK_NAME}' created")
        print(f"   NodeX will start automatically at next login")
    except subprocess.CalledProcessError as e:
        print(f"[-] Task Scheduler creation failed: {e.stderr.decode(errors='replace') if e.stderr else e}")
        print(f"   You can manually import: {xml_path}")


def remove_autostart() -> None:
    """Remove the Task Scheduler entry."""
    try:
        subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], check=True)
        print(f"[+] Auto-start task '{TASK_NAME}' removed")
    except subprocess.CalledProcessError:
        print(f"Task '{TASK_NAME}' not found or could not be removed")


def main() -> None:
    print("========================================")
    print("    NodeX Dashboard 1 - Setup Wizard    ")
    print("========================================\n")

    # 1. Check .env
    env_file = _HERE / ".env"
    if not env_file.exists():
        example = _HERE / ".env.example"
        print(f"[!] .env not found. Copy {example} to {env_file} and fill in values.")
        create = input("Create from .env.example now? (Y/n): ").strip().lower()
        if create != 'n' and example.exists():
            import shutil
            shutil.copy(example, env_file)
            print(f"[+] Copied .env.example -> .env (edit it now before continuing)")
            input("Press Enter when .env is filled in...")

    # 2. Credentials
    store_credentials()

    # 3. PIN
    set_pin()

    # 4. Auto-start
    choice = input("\nInstall Task Scheduler auto-start at login? (Y/n): ").strip().lower()
    if choice != 'n':
        create_task_scheduler_entry()

    print("\n[+] Setup complete!")
    print(f"   Run with:  python {_HERE / 'main.py'}")
    print(f"   Mock mode: python {_HERE / 'main.py'} --mock")


if __name__ == "__main__":
    main()
