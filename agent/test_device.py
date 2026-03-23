#!/usr/bin/env python3
"""
Direct ADB device test script.

This script tests direct ADB communication with a connected Android device
without requiring the full backend stack.
"""

import asyncio
import subprocess
import sys
import time


def run_cmd(cmd: list) -> tuple:
    """Run shell command and return output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


async def get_device_info(serial: str) -> dict:
    """Get device information via ADB."""
    info = {}

    # Model
    stdout, _, _ = run_cmd(["adb", "-s", serial, "shell", "getprop", "ro.product.model"])
    info["model"] = stdout.strip()

    # Android version
    stdout, _, _ = run_cmd(["adb", "-s", serial, "shell", "getprop", "ro.build.version.release"])
    info["android_version"] = stdout.strip()

    # Screen resolution
    stdout, _, _ = run_cmd(["adb", "-s", serial, "shell", "wm", "size"])
    if "Physical" in stdout:
        parts = stdout.split(":")[1].strip().split("x")
        info["resolution"] = {"width": int(parts[0]), "height": int(parts[1])}

    # Brand
    stdout, _, _ = run_cmd(["adb", "-s", serial, "shell", "getprop", "ro.product.brand"])
    info["brand"] = stdout.strip()

    # Serial
    info["serial"] = serial

    return info


async def test_tap(serial: str, x: int, y: int):
    """Test tap at coordinates."""
    print(f"  Tapping at ({x}, {y})...")
    stdout, stderr, code = run_cmd(["adb", "-s", serial, "shell", "input", "tap", str(x), str(y)])
    if code == 0:
        print(f"  ✓ Tap successful")
    else:
        print(f"  ✗ Tap failed: {stderr}")
    return code == 0


async def test_swipe(serial: str):
    """Test swipe gesture."""
    print("  Testing swipe (up)...")
    stdout, stderr, code = run_cmd([
        "adb", "-s", serial, "shell", "input", "swipe", "540", "1500", "540", "500", "500"
    ])
    if code == 0:
        print(f"  ✓ Swipe successful")
    else:
        print(f"  ✗ Swipe failed: {stderr}")
    return code == 0


async def test_input_text(serial: str):
    """Test text input."""
    print("  Testing text input...")
    stdout, stderr, code = run_cmd([
        "adb", "-s", serial, "shell", "input", "text", "HelloAutoTest"
    ])
    if code == 0:
        print(f"  ✓ Input text successful")
    else:
        print(f"  ✗ Input text failed: {stderr}")
    return code == 0


async def test_screenshot(serial: str):
    """Test screenshot."""
    print("  Testing screenshot...")
    local_path = "/tmp/test_screenshot.png"

    # Take screenshot on device
    stdout, stderr, code = run_cmd([
        "adb", "-s", serial, "shell", "screencap", "-p", "/sdcard/screen.png"
    ])
    if code != 0:
        print(f"  ✗ Screenshot failed: {stderr}")
        return False

    # Pull to local
    stdout, stderr, code = run_cmd([
        "adb", "-s", serial, "pull", "/sdcard/screen.png", local_path
    ])
    if code == 0:
        print(f"  ✓ Screenshot saved to {local_path}")
        return True
    else:
        print(f"  ✗ Pull failed: {stderr}")
        return False


async def test_key_event(serial: str):
    """Test key event."""
    print("  Testing key event (HOME)...")
    stdout, stderr, code = run_cmd([
        "adb", "-s", serial, "shell", "input", "keyevent", "3"
    ])
    if code == 0:
        print(f"  ✓ Key event successful")
    else:
        print(f"  ✗ Key event failed: {stderr}")
    return code == 0


async def test_current_app(serial: str):
    """Get current top app."""
    print("  Getting current app...")
    stdout, stderr, code = run_cmd([
        "adb", "-s", serial, "shell", "dumpsys", "activity", "activities"
    ])
    if code == 0:
        for line in stdout.split("\n"):
            if "mResumedActivity" in line:
                parts = line.split("=")[1].split()[0]
                package, activity = parts.split("/")
                print(f"  ✓ Current app: {package}")
                return package
    print("  ✗ Could not determine current app")
    return None


async def main():
    print("=" * 60)
    print("ADB Device Connection Test")
    print("=" * 60)

    # Check ADB
    print("\n[1] Checking ADB...")
    stdout, stderr, code = run_cmd(["adb", "version"])
    if code == 0:
        print(f"  ✓ ADB Version: {stdout.split()[4] if len(stdout.split()) > 4 else 'unknown'}")
    else:
        print(f"  ✗ ADB not found: {stderr}")
        sys.exit(1)

    # List devices
    print("\n[2] Listing connected devices...")
    stdout, stderr, code = run_cmd(["adb", "devices", "-l"])
    print(f"  {stdout}")

    devices = []
    for line in stdout.split("\n"):
        if "device " in line and "List" not in line:
            serial = line.split()[0]
            devices.append(serial)

    if not devices:
        print("\n✗ No devices found!")
        sys.exit(1)

    # Use first device
    serial = devices[0]
    print(f"\n[3] Using device: {serial}")

    # Get device info
    print("\n[4] Getting device information...")
    info = await get_device_info(serial)
    print(f"  Model: {info.get('model', 'N/A')}")
    print(f"  Brand: {info.get('brand', 'N/A')}")
    print(f"  Android: {info.get('android_version', 'N/A')}")
    if "resolution" in info:
        print(f"  Resolution: {info['resolution']['width']}x{info['resolution']['height']}")

    # Run tests
    print("\n[5] Running ADB tests...")

    await test_current_app(serial)
    await test_key_event(serial)
    await test_tap(serial, 540, 1000)
    await test_swipe(serial)
    await test_input_text(serial)
    await test_screenshot(serial)

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

    # Cleanup
    print("\n[6] Cleanup...")
    run_cmd(["adb", "-s", serial, "shell", "rm", "-f", "/sdcard/screen.png"])
    print("  ✓ Done")


if __name__ == "__main__":
    asyncio.run(main())
