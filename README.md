# KDE-LogiWheel

A Logitech-style radial shortcut wheel for KDE Plasma. Create customizable action wheels that appear around your cursor, triggered by keyboard shortcuts or Logitech mouse buttons.

![KDE-LogiWheel](https://img.shields.io/badge/KDE-Plasma-blue) ![Python](https://img.shields.io/badge/Python-3.10+-green) ![License](https://img.shields.io/badge/License-GPL--3.0-orange)

## Features

- **Radial Wheel Menu**: Beautiful, animated wheel menu that appears around your cursor
- **Multiple Trigger Methods**:
  - Keyboard shortcuts (e.g., Super+Alt+W)
  - Logitech mouse buttons (via logid integration)
  - D-Bus commands for scripting
- **Nested Menus**: Create multi-layer menus for organizing many actions
- **Context-Aware**: Different menus for different applications (browser, IDE, file manager, etc.)
- **Action Types**:
  - Keyboard shortcuts (Ctrl+C, Alt+F4, etc.)
  - Shell commands (launch apps, run scripts)
  - D-Bus calls (KDE/system integration)
- **Full Customization**:
  - Colors, sizes, animations
  - Custom icons (freedesktop icon theme)
  - Per-action styling
- **Background Service**: Runs quietly in the system tray
- **Native KDE Integration**: Uses Qt6 and KDE Frameworks

## Screenshots

*Coming soon*

## Installation

### Quick Install

```bash
git clone https://github.com/Guhan-SenSam/KDE-LogiWheel.git
cd KDE-LogiWheel
./install.sh
```

### Manual Installation

1. **Install dependencies**:

   ```bash
   # Arch Linux
   sudo pacman -S python python-pip python-pyqt6 python-dbus xdotool

   # Ubuntu/Debian
   sudo apt install python3 python3-pip python3-pyqt6 python3-dbus xdotool

   # Fedora
   sudo dnf install python3 python3-pip python3-qt6 python3-dbus xdotool
   ```

2. **Install the package**:

   ```bash
   pip install --user -e .
   ```

3. **Install optional input handlers** (recommended for Wayland):

   ```bash
   pip install --user pynput evdev
   ```

4. **Add user to input group** (for evdev on Wayland):

   ```bash
   sudo usermod -aG input $USER
   # Log out and back in
   ```

## Usage

### Starting the Daemon

```bash
# Run directly
kde-logiwheel-daemon

# Or enable as a user service
systemctl --user enable --now kde-logiwheel
```

The daemon runs in the background and shows an icon in the system tray.

### Opening the Configuration UI

```bash
kde-logiwheel-config
```

Or find "KDE LogiWheel" in your application menu.

### Default Controls

- **Super + Alt + W** (hold): Show the wheel
- **Mouse movement**: Hover over actions
- **Release trigger**: Execute hovered action
- **Click center**: Close without action
- **Escape**: Close the wheel

### Command Line

```bash
# Show wheel
kde-logiwheel show

# Hide wheel
kde-logiwheel hide

# Toggle wheel
kde-logiwheel toggle

# Generate logid config
kde-logiwheel logid-config --device "Wireless Mouse MX Master 3" --button 0xc3
```

## Logitech Mouse Integration

KDE-LogiWheel can be triggered by Logitech mouse buttons using [logiops](https://github.com/PixlOne/logiops).

### Setup

1. **Install logiops**:

   ```bash
   # Arch Linux
   sudo pacman -S logiops

   # Ubuntu
   sudo apt install logiops
   ```

2. **Find your mouse's button CIDs**:

   ```bash
   sudo logid -v
   # Press buttons to see their Control IDs
   ```

3. **Configure logid** (`/etc/logid.cfg`):

   ```
   devices: (
     {
       name: "Wireless Mouse MX Master 3";
       buttons: (
         {
           cid: 0xc3;  # Thumb button
           action = {
             type: "Keypress";
             keys: ["KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_F20"];
           };
         }
       );
     }
   );
   ```

4. **Configure KDE-LogiWheel** to use the same key combination:
   - Open Settings → Triggers
   - Add keyboard trigger: `Control_L+Alt_L+Shift_L+F20`
   - Enable "Hold to show"

5. **Restart services**:

   ```bash
   sudo systemctl restart logid
   ```

### Common Button CIDs

| Mouse | Button | CID |
|-------|--------|-----|
| MX Master 3 | Thumb button | 0xc3 |
| MX Master 3 | Scroll click | 0x52 |
| MX Master 3 | Back | 0x53 |
| MX Master 3 | Forward | 0x56 |
| G502 | G7 (thumb) | 0xd7 |
| G502 | G8 (thumb) | 0xd8 |

## Configuration

Configuration is stored in `~/.config/kde-logiwheel/config.json`.

### Triggers

```json
{
  "triggers": [
    {
      "name": "Keyboard Trigger",
      "enabled": true,
      "trigger_type": "keyboard",
      "key_combination": ["Super_L", "Alt_L", "w"],
      "hold_to_show": true,
      "activation_delay_ms": 100
    },
    {
      "name": "Mouse Button",
      "enabled": true,
      "trigger_type": "mouse",
      "mouse_button": 8,
      "hold_to_show": true
    }
  ]
}
```

### Actions

```json
{
  "actions": [
    {
      "name": "Copy",
      "icon": "edit-copy",
      "action_type": "keypress",
      "keys": ["Ctrl", "c"]
    },
    {
      "name": "Terminal",
      "icon": "utilities-terminal",
      "action_type": "command",
      "command": "konsole"
    },
    {
      "name": "Lock Screen",
      "icon": "system-lock-screen",
      "action_type": "dbus",
      "dbus_service": "org.freedesktop.ScreenSaver",
      "dbus_path": "/ScreenSaver",
      "dbus_interface": "org.freedesktop.ScreenSaver",
      "dbus_method": "Lock"
    }
  ]
}
```

### Window Rules

```json
{
  "window_rules": [
    {
      "name": "Firefox",
      "window_class": "firefox",
      "menu_id": "browser_menu",
      "priority": 10
    }
  ]
}
```

## D-Bus API

Control KDE-LogiWheel from scripts:

```bash
# Show wheel
dbus-send --session --type=method_call \
  --dest=org.kde.LogiWheel /org/kde/LogiWheel \
  org.kde.LogiWheel.ShowWheel

# Toggle wheel
dbus-send --session --type=method_call \
  --dest=org.kde.LogiWheel /org/kde/LogiWheel \
  org.kde.LogiWheel.ToggleWheel

# Reload config
dbus-send --session --type=method_call \
  --dest=org.kde.LogiWheel /org/kde/LogiWheel \
  org.kde.LogiWheel.ReloadConfig
```

## Troubleshooting

### Wheel doesn't appear

1. Check if daemon is running: `pgrep -f kde-logiwheel-daemon`
2. Check logs: `journalctl --user -u kde-logiwheel`
3. Try running daemon manually: `kde-logiwheel-daemon`

### Key combination not detected

1. On Wayland, ensure user is in `input` group
2. Install `evdev` or `pynput`: `pip install --user evdev pynput`
3. Check if another app is grabbing the keys

### Mouse button not working

1. Verify logid configuration: `sudo logid -v`
2. Check logid service: `sudo systemctl status logid`
3. Ensure key combination matches between logid and KDE-LogiWheel

### Actions not executing

1. For keypresses: Install `xdotool` (X11) or `ydotool`/`wtype` (Wayland)
2. For D-Bus: Check service is available: `qdbus org.kde.KWin`
3. For commands: Verify command works in terminal

## Development

```bash
# Clone repository
git clone https://github.com/Guhan-SenSam/KDE-LogiWheel.git
cd KDE-LogiWheel

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
```

## Architecture

```
src/
├── config/          # Configuration management
│   ├── models.py    # Data models (WheelAction, WheelMenu, etc.)
│   └── config_manager.py
├── wheel/           # Wheel widget
│   ├── wheel_widget.py    # Radial menu rendering
│   └── wheel_overlay.py   # Fullscreen overlay window
├── actions/         # Action execution
│   └── action_executor.py # Keypress, command, D-Bus handlers
├── window/          # Window detection
│   └── window_detector.py # X11/Wayland window info
├── service/         # Background daemon
│   ├── daemon.py          # Main service
│   └── input_listener.py  # Trigger detection
├── logid/           # Logiops integration
│   └── logid_helper.py    # Config generation
└── ui/              # Settings UI
    └── main_window.py     # Configuration interface
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by Logitech Options+ shortcut wheel
- Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- Logitech mouse support via [logiops](https://github.com/PixlOne/logiops)
