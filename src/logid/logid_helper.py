"""
Helper for integrating with logiops/logid.

Since logid doesn't have a native "execute command" action, we use a two-layer approach:
1. Configure logid to send an unusual key combination on button press
2. KDE-LogiWheel listens for that key combination to show the wheel

This module helps generate and manage logid configurations.
"""

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LogidButtonConfig:
    """Configuration for a single button in logid."""
    cid: int                        # Control ID (hex, e.g., 0x52)
    action_type: str = "Keypress"   # "Keypress", "Gestures", etc.
    keys: list[str] = field(default_factory=list)  # Key names for Keypress


@dataclass
class LogidDeviceConfig:
    """Configuration for a device in logid."""
    name: str
    buttons: list[LogidButtonConfig] = field(default_factory=list)
    smartshift_on: bool = True
    smartshift_threshold: int = 10
    dpi: int = 1000


@dataclass
class LogidConfig:
    """Complete logid configuration."""
    devices: list[LogidDeviceConfig] = field(default_factory=list)

    def to_libconfig(self) -> str:
        """Generate libconfig format string."""
        lines = ["devices: ("]

        for i, device in enumerate(self.devices):
            lines.append("  {")
            lines.append(f'    name: "{device.name}";')

            # SmartShift
            lines.append("    smartshift: {")
            lines.append(f"      on: {'true' if device.smartshift_on else 'false'};")
            lines.append(f"      threshold: {device.smartshift_threshold};")
            lines.append("    };")

            # DPI
            lines.append(f"    dpi: {device.dpi};")

            # Buttons
            if device.buttons:
                lines.append("    buttons: (")
                for j, button in enumerate(device.buttons):
                    lines.append("      {")
                    lines.append(f"        cid: 0x{button.cid:02x};")
                    lines.append("        action = {")
                    lines.append(f'          type: "{button.action_type}";')
                    if button.action_type == "Keypress" and button.keys:
                        keys_str = ", ".join(f'"{k}"' for k in button.keys)
                        lines.append(f"          keys: [{keys_str}];")
                    lines.append("        };")
                    lines.append("      }" + ("," if j < len(device.buttons) - 1 else ""))
                lines.append("    );")

            lines.append("  }" + ("," if i < len(self.devices) - 1 else ""))

        lines.append(");")
        return "\n".join(lines)


class LogidHelper:
    """Helper class for managing logid integration."""

    # Common Logitech mice button CIDs
    COMMON_CIDS = {
        "MX Master 3": {
            "scroll_click": 0x52,
            "back": 0x53,
            "forward": 0x56,
            "thumb_button": 0xc3,
            "mode_shift": 0xc4,
        },
        "MX Anywhere 3": {
            "scroll_click": 0x52,
            "back": 0x53,
            "forward": 0x56,
        },
        "G502": {
            "scroll_click": 0x52,
            "back": 0x53,
            "forward": 0x56,
            "dpi_up": 0x4d,
            "dpi_down": 0x4e,
            "g7": 0xd7,
            "g8": 0xd8,
        },
        "G Pro": {
            "scroll_click": 0x52,
            "back": 0x53,
            "forward": 0x56,
        },
    }

    # Special key combination for triggering the wheel
    # Using an unusual combination that's unlikely to conflict
    TRIGGER_KEYS = ["KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_F20"]

    DEFAULT_CONFIG_PATH = Path("/etc/logid.cfg")
    BACKUP_CONFIG_PATH = Path("/etc/logid.cfg.backup")

    def __init__(self):
        self._config_path = self.DEFAULT_CONFIG_PATH

    @staticmethod
    def is_logid_installed() -> bool:
        """Check if logid is installed."""
        try:
            result = subprocess.run(
                ["which", "logid"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def is_logid_running() -> bool:
        """Check if logid service is running."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "logid"],
                capture_output=True,
                text=True
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False

    @staticmethod
    def get_connected_devices() -> list[str]:
        """Get list of connected Logitech devices.

        Returns:
            List of device names
        """
        devices = []

        try:
            # Run logid in verbose mode briefly to detect devices
            result = subprocess.run(
                ["sudo", "logid", "-v"],
                capture_output=True,
                text=True,
                timeout=2
            )
            # This will fail but might output device info
        except subprocess.TimeoutExpired as e:
            output = e.stderr.decode() if e.stderr else ""
            # Parse device names from output
            for line in output.split("\n"):
                if "Device" in line and "found" in line:
                    match = re.search(r"Device (.+) found", line)
                    if match:
                        devices.append(match.group(1))
        except Exception:
            pass

        # Alternative: check /dev/hidraw* devices
        try:
            for path in Path("/sys/class/hidraw").iterdir():
                device_path = path / "device" / "uevent"
                if device_path.exists():
                    content = device_path.read_text()
                    if "046d" in content.lower():  # Logitech vendor ID
                        # Try to get device name
                        name_path = path / "device" / ".." / "name"
                        if name_path.exists():
                            devices.append(name_path.read_text().strip())
        except Exception:
            pass

        return list(set(devices))  # Remove duplicates

    def read_current_config(self) -> Optional[str]:
        """Read the current logid configuration file.

        Returns:
            Config file contents or None if not found
        """
        if self._config_path.exists():
            return self._config_path.read_text()
        return None

    def backup_config(self) -> bool:
        """Backup the current configuration.

        Returns:
            True if backup was successful
        """
        if not self._config_path.exists():
            return True

        try:
            import shutil
            shutil.copy(self._config_path, self.BACKUP_CONFIG_PATH)
            return True
        except Exception as e:
            print(f"Failed to backup config: {e}")
            return False

    def generate_wheel_trigger_config(
        self,
        device_name: str,
        button_cid: int,
        existing_config: Optional[str] = None
    ) -> str:
        """Generate a logid config that triggers the wheel.

        Args:
            device_name: Name of the Logitech device
            button_cid: Control ID of the button to use
            existing_config: Existing config to merge with

        Returns:
            Generated libconfig string
        """
        # Create button config for wheel trigger
        trigger_button = LogidButtonConfig(
            cid=button_cid,
            action_type="Keypress",
            keys=self.TRIGGER_KEYS,
        )

        # Create device config
        device = LogidDeviceConfig(
            name=device_name,
            buttons=[trigger_button],
        )

        config = LogidConfig(devices=[device])

        if existing_config:
            # TODO: Merge with existing config properly
            # For now, just append a comment
            return (
                f"# KDE-LogiWheel trigger added for button 0x{button_cid:02x}\n"
                f"# Original config preserved below\n\n"
                f"{config.to_libconfig()}\n\n"
                f"# --- Original Config ---\n"
                f"# {existing_config.replace(chr(10), chr(10) + '# ')}"
            )

        return config.to_libconfig()

    def write_config(self, config: str) -> bool:
        """Write configuration to file (requires root).

        Args:
            config: Configuration string to write

        Returns:
            True if successful
        """
        try:
            # Use sudo to write
            process = subprocess.Popen(
                ["sudo", "tee", str(self._config_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            _, stderr = process.communicate(config.encode())

            if process.returncode != 0:
                print(f"Failed to write config: {stderr.decode()}")
                return False

            return True

        except Exception as e:
            print(f"Failed to write config: {e}")
            return False

    def restart_logid(self) -> bool:
        """Restart the logid service.

        Returns:
            True if successful
        """
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "restart", "logid"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Failed to restart logid: {e}")
            return False

    def get_trigger_key_combination(self) -> list[str]:
        """Get the key combination used for triggering the wheel.

        Returns:
            List of key names
        """
        return self.TRIGGER_KEYS.copy()

    @staticmethod
    def key_name_to_qt(key_name: str) -> str:
        """Convert logid key name to Qt key name.

        Args:
            key_name: Key name in logid format (e.g., KEY_LEFTCTRL)

        Returns:
            Key name in Qt/config format (e.g., Control_L)
        """
        key_map = {
            "KEY_LEFTCTRL": "Control_L",
            "KEY_RIGHTCTRL": "Control_R",
            "KEY_LEFTALT": "Alt_L",
            "KEY_RIGHTALT": "Alt_R",
            "KEY_LEFTSHIFT": "Shift_L",
            "KEY_RIGHTSHIFT": "Shift_R",
            "KEY_LEFTMETA": "Super_L",
            "KEY_RIGHTMETA": "Super_R",
            "KEY_F1": "F1",
            "KEY_F2": "F2",
            "KEY_F3": "F3",
            "KEY_F4": "F4",
            "KEY_F5": "F5",
            "KEY_F6": "F6",
            "KEY_F7": "F7",
            "KEY_F8": "F8",
            "KEY_F9": "F9",
            "KEY_F10": "F10",
            "KEY_F11": "F11",
            "KEY_F12": "F12",
            "KEY_F13": "F13",
            "KEY_F14": "F14",
            "KEY_F15": "F15",
            "KEY_F16": "F16",
            "KEY_F17": "F17",
            "KEY_F18": "F18",
            "KEY_F19": "F19",
            "KEY_F20": "F20",
        }
        return key_map.get(key_name, key_name.replace("KEY_", ""))


def create_logid_setup_guide() -> str:
    """Create a setup guide for logid integration.

    Returns:
        Markdown formatted guide
    """
    return """
# KDE-LogiWheel Logid Integration Guide

## Overview

KDE-LogiWheel can be triggered by Logitech mouse buttons through logid (logiops).
Since logid doesn't support executing commands directly, we use a two-step approach:

1. Configure logid to send a special key combination when a button is pressed
2. KDE-LogiWheel listens for this key combination to show the wheel

## Prerequisites

1. Install logiops:
   ```bash
   # Arch Linux
   sudo pacman -S logiops

   # Ubuntu/Debian
   sudo apt install logiops

   # Fedora
   sudo dnf install logiops
   ```

2. Enable and start the service:
   ```bash
   sudo systemctl enable --now logid
   ```

## Configuration

### Step 1: Find Your Mouse's Button CIDs

Run logid in verbose mode to discover button Control IDs:
```bash
sudo logid -v
```

Press buttons on your mouse and note the CID values (e.g., 0x52, 0xc3).

### Step 2: Configure logid

Edit `/etc/logid.cfg`:
```bash
sudo nano /etc/logid.cfg
```

Add a button configuration that sends a unique key combination.
Example for MX Master 3 thumb button:

```
devices: (
  {
    name: "Wireless Mouse MX Master 3";
    buttons: (
      {
        cid: 0xc3;
        action = {
          type: "Keypress";
          keys: ["KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_F20"];
        };
      }
    );
  }
);
```

### Step 3: Configure KDE-LogiWheel

In KDE-LogiWheel settings, create a keyboard trigger with the same key combination:
- Keys: `Control_L+Alt_L+Shift_L+F20`
- Hold to show: Yes

### Step 4: Restart Services

```bash
sudo systemctl restart logid
```

## Common Button CIDs

### MX Master 3
- Scroll wheel click: 0x52
- Back button: 0x53
- Forward button: 0x56
- Thumb button: 0xc3
- Mode shift: 0xc4

### G502
- Scroll wheel click: 0x52
- G7 (thumb): 0xd7
- G8 (thumb): 0xd8
- DPI up: 0x4d
- DPI down: 0x4e

## Troubleshooting

1. **Logid not detecting mouse**: Make sure you're using the wireless receiver or Bluetooth is connected.

2. **Key combination not working**: Verify the key combination matches exactly between logid and KDE-LogiWheel.

3. **Permission issues**: Ensure the user is in the `input` group:
   ```bash
   sudo usermod -aG input $USER
   ```
   Then log out and back in.

4. **Check logid status**:
   ```bash
   sudo systemctl status logid
   journalctl -u logid
   ```
"""
