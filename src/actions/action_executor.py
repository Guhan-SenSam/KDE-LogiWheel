"""
Action executor - handles executing different types of actions.
"""

import subprocess
import shlex
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from ..config.models import WheelAction, ActionType


class ActionExecutor(QObject):
    """Executes wheel actions."""

    # Signals
    action_started = pyqtSignal(WheelAction)
    action_completed = pyqtSignal(WheelAction, bool)  # action, success
    action_error = pyqtSignal(WheelAction, str)  # action, error message

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._dbus_session = None
        self._setup_dbus()

    def _setup_dbus(self) -> None:
        """Setup D-Bus connection."""
        try:
            import dbus
            self._dbus_session = dbus.SessionBus()
        except ImportError:
            print("Warning: dbus-python not installed. D-Bus actions will not work.")
        except Exception as e:
            print(f"Warning: Could not connect to D-Bus session bus: {e}")

    def execute(self, action: WheelAction) -> bool:
        """Execute an action.

        Args:
            action: The action to execute

        Returns:
            True if execution was successful
        """
        self.action_started.emit(action)

        try:
            if action.action_type == ActionType.KEYPRESS:
                success = self._execute_keypress(action)
            elif action.action_type == ActionType.COMMAND:
                success = self._execute_command(action)
            elif action.action_type == ActionType.DBUS:
                success = self._execute_dbus(action)
            else:
                # SUBMENU, BACK, CLOSE are handled by the wheel itself
                success = True

            self.action_completed.emit(action, success)
            return success

        except Exception as e:
            error_msg = str(e)
            self.action_error.emit(action, error_msg)
            self.action_completed.emit(action, False)
            return False

    def _execute_keypress(self, action: WheelAction) -> bool:
        """Execute a keypress action using xdotool or ydotool."""
        if not action.keys:
            return False

        # Convert key names to xdotool format
        key_combo = self._convert_keys_to_xdotool(action.keys)

        # Try ydotool first (for Wayland), then xdotool (for X11)
        try:
            # Check if running under Wayland
            import os
            is_wayland = os.environ.get("XDG_SESSION_TYPE") == "wayland"

            if is_wayland:
                # Try ydotool for Wayland
                try:
                    ydotool_keys = self._convert_keys_to_ydotool(action.keys)
                    result = subprocess.run(
                        ["ydotool", "key", ydotool_keys],
                        capture_output=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return True
                except FileNotFoundError:
                    pass  # ydotool not available, try alternatives

                # Try wtype for Wayland
                try:
                    wtype_keys = self._convert_keys_to_wtype(action.keys)
                    result = subprocess.run(
                        ["wtype", "-M"] + wtype_keys,
                        capture_output=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return True
                except FileNotFoundError:
                    pass

            # Fallback to xdotool (X11 or XWayland)
            result = subprocess.run(
                ["xdotool", "key", "--clearmodifiers", key_combo],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0

        except FileNotFoundError:
            # Try using KDE's D-Bus interface as last resort
            return self._execute_keypress_kde(action)
        except subprocess.TimeoutExpired:
            return False

    def _convert_keys_to_xdotool(self, keys: list[str]) -> str:
        """Convert key names to xdotool format."""
        key_map = {
            "Ctrl": "ctrl",
            "Control": "ctrl",
            "Alt": "alt",
            "Shift": "shift",
            "Super": "super",
            "Super_L": "super",
            "Super_R": "super",
            "Meta": "super",
            "Win": "super",
            "Tab": "Tab",
            "Return": "Return",
            "Enter": "Return",
            "Escape": "Escape",
            "Esc": "Escape",
            "Space": "space",
            "Backspace": "BackSpace",
            "Delete": "Delete",
            "Del": "Delete",
            "Insert": "Insert",
            "Home": "Home",
            "End": "End",
            "Page_Up": "Page_Up",
            "PageUp": "Page_Up",
            "Page_Down": "Page_Down",
            "PageDown": "Page_Down",
            "Left": "Left",
            "Right": "Right",
            "Up": "Up",
            "Down": "Down",
            "F1": "F1", "F2": "F2", "F3": "F3", "F4": "F4",
            "F5": "F5", "F6": "F6", "F7": "F7", "F8": "F8",
            "F9": "F9", "F10": "F10", "F11": "F11", "F12": "F12",
        }

        converted = []
        for key in keys:
            converted.append(key_map.get(key, key))

        return "+".join(converted)

    def _convert_keys_to_ydotool(self, keys: list[str]) -> str:
        """Convert key names to ydotool format (uses Linux keycodes)."""
        # ydotool uses different syntax: key down, key up
        key_map = {
            "Ctrl": "29",
            "Control": "29",
            "Alt": "56",
            "Shift": "42",
            "Super": "125",
            "Super_L": "125",
            "Tab": "15",
            "Return": "28",
            "Enter": "28",
            "Escape": "1",
            "Space": "57",
            "Backspace": "14",
            "Delete": "111",
            "a": "30", "b": "48", "c": "46", "d": "32", "e": "18",
            "f": "33", "g": "34", "h": "35", "i": "23", "j": "36",
            "k": "37", "l": "38", "m": "50", "n": "49", "o": "24",
            "p": "25", "q": "16", "r": "19", "s": "31", "t": "20",
            "u": "22", "v": "47", "w": "17", "x": "45", "y": "21",
            "z": "44",
            "F1": "59", "F2": "60", "F3": "61", "F4": "62",
            "F5": "63", "F6": "64", "F7": "65", "F8": "66",
            "F9": "67", "F10": "68", "F11": "87", "F12": "88",
        }

        # Build key sequence: press all, release all
        codes = []
        for key in keys:
            code = key_map.get(key, key_map.get(key.lower(), ""))
            if code:
                codes.append(f"{code}:1")  # Key down

        for key in reversed(keys):
            code = key_map.get(key, key_map.get(key.lower(), ""))
            if code:
                codes.append(f"{code}:0")  # Key up

        return " ".join(codes)

    def _convert_keys_to_wtype(self, keys: list[str]) -> list[str]:
        """Convert keys for wtype (Wayland)."""
        key_map = {
            "Ctrl": "ctrl",
            "Control": "ctrl",
            "Alt": "alt",
            "Shift": "shift",
            "Super": "logo",
            "Super_L": "logo",
        }

        result = []
        modifiers = []
        regular_keys = []

        for key in keys:
            mapped = key_map.get(key)
            if mapped:
                modifiers.append(mapped)
            else:
                regular_keys.append(key.lower())

        for mod in modifiers:
            result.extend(["-M", mod])

        if regular_keys:
            result.extend(["-k", regular_keys[0]])

        return result

    def _execute_keypress_kde(self, action: WheelAction) -> bool:
        """Execute keypress using KDE's global shortcuts D-Bus interface."""
        if not self._dbus_session:
            return False

        try:
            import dbus

            # Use KGlobalAccel to trigger shortcuts
            kglobal = self._dbus_session.get_object(
                "org.kde.kglobalaccel",
                "/kglobalaccel"
            )
            interface = dbus.Interface(kglobal, "org.kde.KGlobalAccel")

            # This is limited - can only trigger registered global shortcuts
            # For arbitrary keypresses, we need xdotool/ydotool
            return False

        except Exception:
            return False

    def _execute_command(self, action: WheelAction) -> bool:
        """Execute a shell command."""
        if not action.command:
            return False

        try:
            # Parse command safely
            args = shlex.split(action.command)

            # Execute asynchronously (don't wait for completion)
            subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return True

        except Exception as e:
            print(f"Error executing command: {e}")
            return False

    def _execute_dbus(self, action: WheelAction) -> bool:
        """Execute a D-Bus method call."""
        if not self._dbus_session:
            print("D-Bus session not available")
            return False

        if not all([action.dbus_service, action.dbus_path,
                   action.dbus_interface, action.dbus_method]):
            print("Incomplete D-Bus action configuration")
            return False

        try:
            import dbus

            # Get the object
            obj = self._dbus_session.get_object(
                action.dbus_service,
                action.dbus_path
            )

            # Get the interface
            interface = dbus.Interface(obj, action.dbus_interface)

            # Get the method
            method = getattr(interface, action.dbus_method)

            # Call with args if any
            if action.dbus_args:
                method(*action.dbus_args)
            else:
                method()

            return True

        except Exception as e:
            print(f"D-Bus error: {e}")
            return False


# Global executor instance
_executor: Optional[ActionExecutor] = None


def get_executor() -> ActionExecutor:
    """Get the global action executor instance."""
    global _executor
    if _executor is None:
        _executor = ActionExecutor()
    return _executor
