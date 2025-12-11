"""
Window detection for context-aware actions.
Supports both X11 and Wayland (via KWin).
"""

import os
import subprocess
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QObject


@dataclass
class WindowInfo:
    """Information about a window."""
    window_id: str
    window_class: str
    window_title: str
    app_name: str
    pid: int = 0


class WindowDetector(QObject):
    """Detects and provides information about the currently focused window."""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._session_type = os.environ.get("XDG_SESSION_TYPE", "x11")
        self._dbus_session = None
        self._setup_dbus()

    def _setup_dbus(self) -> None:
        """Setup D-Bus connection."""
        try:
            import dbus
            self._dbus_session = dbus.SessionBus()
        except ImportError:
            print("Warning: dbus-python not installed.")
        except Exception as e:
            print(f"Warning: Could not connect to D-Bus: {e}")

    def get_active_window(self) -> Optional[WindowInfo]:
        """Get information about the currently active/focused window.

        Returns:
            WindowInfo if successful, None otherwise
        """
        if self._session_type == "wayland":
            return self._get_active_window_wayland()
        else:
            return self._get_active_window_x11()

    def _get_active_window_wayland(self) -> Optional[WindowInfo]:
        """Get active window info on Wayland using KWin D-Bus API."""
        if not self._dbus_session:
            return None

        try:
            import dbus

            # Try KWin scripting interface
            kwin = self._dbus_session.get_object(
                "org.kde.KWin",
                "/KWin"
            )
            kwin_iface = dbus.Interface(kwin, "org.kde.KWin")

            # Get active client
            # Note: KWin's D-Bus API is limited for privacy reasons
            # We'll use the scripting interface

            # Alternative: Use kdotool or other tools
            try:
                result = subprocess.run(
                    ["kdotool", "getactivewindow"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    window_id = result.stdout.strip()

                    # Get window info
                    name_result = subprocess.run(
                        ["kdotool", "getwindowname", window_id],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )

                    class_result = subprocess.run(
                        ["kdotool", "getwindowclassname", window_id],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )

                    return WindowInfo(
                        window_id=window_id,
                        window_class=class_result.stdout.strip() if class_result.returncode == 0 else "",
                        window_title=name_result.stdout.strip() if name_result.returncode == 0 else "",
                        app_name=class_result.stdout.strip() if class_result.returncode == 0 else "",
                    )
            except FileNotFoundError:
                pass

            # Fallback: Try to get info from KWin using script
            return self._get_window_via_kwin_script()

        except Exception as e:
            print(f"Error getting window info (Wayland): {e}")
            return None

    def _get_window_via_kwin_script(self) -> Optional[WindowInfo]:
        """Get window info by running a KWin script."""
        if not self._dbus_session:
            return None

        try:
            import dbus
            import tempfile
            import time

            # Create a simple KWin script to get active window info
            script_content = """
            var client = workspace.activeClient;
            if (client) {
                print("CLASS:" + client.resourceClass);
                print("NAME:" + client.resourceName);
                print("TITLE:" + client.caption);
            }
            """

            # Write script to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(script_content)
                script_path = f.name

            try:
                # Load and run the script
                kwin = self._dbus_session.get_object(
                    "org.kde.KWin",
                    "/Scripting"
                )
                scripting = dbus.Interface(kwin, "org.kde.kwin.Scripting")

                script_id = scripting.loadScript(script_path)
                scripting.start()

                # Give it a moment to execute
                time.sleep(0.1)

                # The output would be in KWin's log, which is not directly accessible
                # This approach has limitations

            finally:
                os.unlink(script_path)

            # Since direct scripting output is hard to capture, fall back to qdbus
            try:
                result = subprocess.run(
                    ["qdbus", "org.kde.KWin", "/KWin", "org.kde.KWin.activeClient"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                # Parse result if available
            except Exception:
                pass

            return None

        except Exception as e:
            print(f"Error with KWin script: {e}")
            return None

    def _get_active_window_x11(self) -> Optional[WindowInfo]:
        """Get active window info on X11 using xdotool/xprop."""
        try:
            # Get active window ID
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode != 0:
                return None

            window_id = result.stdout.strip()

            # Get window name
            name_result = subprocess.run(
                ["xdotool", "getwindowname", window_id],
                capture_output=True,
                text=True,
                timeout=2
            )

            # Get window class using xprop
            class_result = subprocess.run(
                ["xprop", "-id", window_id, "WM_CLASS"],
                capture_output=True,
                text=True,
                timeout=2
            )

            window_class = ""
            app_name = ""
            if class_result.returncode == 0:
                # Parse WM_CLASS output: WM_CLASS(STRING) = "instance", "class"
                output = class_result.stdout.strip()
                if "=" in output:
                    values = output.split("=")[1].strip()
                    parts = values.split(",")
                    if len(parts) >= 2:
                        app_name = parts[0].strip().strip('"')
                        window_class = parts[1].strip().strip('"')
                    elif len(parts) == 1:
                        window_class = parts[0].strip().strip('"')

            # Get PID
            pid = 0
            pid_result = subprocess.run(
                ["xdotool", "getwindowpid", window_id],
                capture_output=True,
                text=True,
                timeout=2
            )
            if pid_result.returncode == 0:
                try:
                    pid = int(pid_result.stdout.strip())
                except ValueError:
                    pass

            return WindowInfo(
                window_id=window_id,
                window_class=window_class,
                window_title=name_result.stdout.strip() if name_result.returncode == 0 else "",
                app_name=app_name,
                pid=pid,
            )

        except FileNotFoundError:
            print("xdotool not found. Please install xdotool for X11 window detection.")
            return None
        except subprocess.TimeoutExpired:
            return None
        except Exception as e:
            print(f"Error getting window info (X11): {e}")
            return None

    def get_window_under_cursor(self) -> Optional[WindowInfo]:
        """Get window under the mouse cursor.

        Returns:
            WindowInfo if successful, None otherwise
        """
        if self._session_type == "wayland":
            # On Wayland, this is restricted for security
            # Fall back to active window
            return self.get_active_window()
        else:
            return self._get_window_under_cursor_x11()

    def _get_window_under_cursor_x11(self) -> Optional[WindowInfo]:
        """Get window under cursor on X11."""
        try:
            # Get window under cursor
            result = subprocess.run(
                ["xdotool", "getmouselocation", "--shell"],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode != 0:
                return None

            # Parse output to get WINDOW
            window_id = None
            for line in result.stdout.strip().split("\n"):
                if line.startswith("WINDOW="):
                    window_id = line.split("=")[1]
                    break

            if not window_id:
                return self.get_active_window()

            # Get window info similar to active window
            name_result = subprocess.run(
                ["xdotool", "getwindowname", window_id],
                capture_output=True,
                text=True,
                timeout=2
            )

            class_result = subprocess.run(
                ["xprop", "-id", window_id, "WM_CLASS"],
                capture_output=True,
                text=True,
                timeout=2
            )

            window_class = ""
            app_name = ""
            if class_result.returncode == 0:
                output = class_result.stdout.strip()
                if "=" in output:
                    values = output.split("=")[1].strip()
                    parts = values.split(",")
                    if len(parts) >= 2:
                        app_name = parts[0].strip().strip('"')
                        window_class = parts[1].strip().strip('"')

            return WindowInfo(
                window_id=window_id,
                window_class=window_class,
                window_title=name_result.stdout.strip() if name_result.returncode == 0 else "",
                app_name=app_name,
            )

        except Exception as e:
            print(f"Error getting window under cursor: {e}")
            return self.get_active_window()


# Global instance
_detector: Optional[WindowDetector] = None


def get_window_detector() -> WindowDetector:
    """Get the global window detector instance."""
    global _detector
    if _detector is None:
        _detector = WindowDetector()
    return _detector
