"""
Main daemon service for KDE-LogiWheel.
Runs in the background and manages the wheel overlay.
"""

import sys
import signal
from typing import Optional

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from ..config import ConfigManager, WheelConfig, TriggerConfig
from ..wheel import WheelOverlay
from ..window import WindowDetector, get_window_detector
from ..actions import ActionExecutor, get_executor
from .input_listener import InputListener


class LogiWheelDaemon(QObject):
    """Main daemon that manages the wheel overlay and input listening."""

    # Signals
    config_changed = pyqtSignal()
    wheel_shown = pyqtSignal()
    wheel_hidden = pyqtSignal()

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        super().__init__()

        # Initialize components
        self._config_manager = config_manager or ConfigManager()
        self._config = self._config_manager.load()

        self._app: Optional[QApplication] = None
        self._overlay: Optional[WheelOverlay] = None
        self._input_listener: Optional[InputListener] = None
        self._tray_icon: Optional[QSystemTrayIcon] = None

        self._window_detector = get_window_detector()
        self._action_executor = get_executor()

        self._active_trigger: Optional[TriggerConfig] = None
        self._is_wheel_visible = False

    def run(self) -> int:
        """Run the daemon.

        Returns:
            Exit code
        """
        # Create Qt application
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setApplicationName("KDE-LogiWheel")
        self._app.setApplicationDisplayName("KDE LogiWheel")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Create overlay
        self._overlay = WheelOverlay(self._config)
        self._overlay.action_triggered.connect(self._on_action_triggered)
        self._overlay.closed.connect(self._on_wheel_closed)

        # Create input listener
        self._input_listener = InputListener()
        self._input_listener.set_triggers(self._config.triggers)
        self._input_listener.trigger_activated.connect(self._on_trigger_activated)
        self._input_listener.trigger_released.connect(self._on_trigger_released)

        # Create system tray icon
        self._setup_tray_icon()

        # Start listening for input
        self._input_listener.start()

        # Setup D-Bus service for external control
        self._setup_dbus_service()

        print("KDE-LogiWheel daemon started")
        print(f"Triggers: {len(self._config.triggers)} configured")

        # Run event loop
        return self._app.exec()

    def stop(self) -> None:
        """Stop the daemon."""
        print("Stopping KDE-LogiWheel daemon...")

        if self._input_listener:
            self._input_listener.stop()

        if self._overlay:
            self._overlay.hide()

        if self._tray_icon:
            self._tray_icon.hide()

        if self._app:
            self._app.quit()

    def _signal_handler(self, signum, frame) -> None:
        """Handle system signals."""
        self.stop()

    def _setup_tray_icon(self) -> None:
        """Setup the system tray icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("System tray not available")
            return

        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(QIcon.fromTheme("input-mouse", QIcon.fromTheme("preferences-desktop-peripherals")))
        self._tray_icon.setToolTip("KDE LogiWheel")

        # Create menu
        menu = QMenu()

        # Show wheel action
        show_action = menu.addAction("Show Wheel")
        show_action.triggered.connect(self._show_wheel_at_cursor)

        menu.addSeparator()

        # Settings action
        settings_action = menu.addAction("Settings...")
        settings_action.triggered.connect(self._open_settings)

        # Reload config action
        reload_action = menu.addAction("Reload Config")
        reload_action.triggered.connect(self._reload_config)

        menu.addSeparator()

        # Quit action
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.stop)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _setup_dbus_service(self) -> None:
        """Setup D-Bus service for external control."""
        try:
            import dbus
            import dbus.service
            from dbus.mainloop.pyqt6 import DBusQtMainLoop

            DBusQtMainLoop(set_as_default=True)

            class LogiWheelDBusService(dbus.service.Object):
                def __init__(self, daemon, bus_name):
                    self._daemon = daemon
                    bus_path = "/org/kde/LogiWheel"
                    dbus.service.Object.__init__(self, bus_name, bus_path)

                @dbus.service.method("org.kde.LogiWheel", in_signature='', out_signature='')
                def ShowWheel(self):
                    QTimer.singleShot(0, self._daemon._show_wheel_at_cursor)

                @dbus.service.method("org.kde.LogiWheel", in_signature='', out_signature='')
                def HideWheel(self):
                    QTimer.singleShot(0, self._daemon._hide_wheel)

                @dbus.service.method("org.kde.LogiWheel", in_signature='', out_signature='')
                def ToggleWheel(self):
                    if self._daemon._is_wheel_visible:
                        QTimer.singleShot(0, self._daemon._hide_wheel)
                    else:
                        QTimer.singleShot(0, self._daemon._show_wheel_at_cursor)

                @dbus.service.method("org.kde.LogiWheel", in_signature='', out_signature='')
                def ReloadConfig(self):
                    QTimer.singleShot(0, self._daemon._reload_config)

                @dbus.service.method("org.kde.LogiWheel", in_signature='s', out_signature='')
                def ShowMenu(self, menu_id):
                    QTimer.singleShot(0, lambda: self._daemon._show_specific_menu(menu_id))

            session_bus = dbus.SessionBus()
            bus_name = dbus.service.BusName("org.kde.LogiWheel", session_bus)
            self._dbus_service = LogiWheelDBusService(self, bus_name)
            print("D-Bus service registered: org.kde.LogiWheel")

        except ImportError:
            print("D-Bus Python bindings not available. External control disabled.")
        except Exception as e:
            print(f"Could not setup D-Bus service: {e}")

    def _on_tray_activated(self, reason) -> None:
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_wheel_at_cursor()

    def _on_trigger_activated(self, trigger: TriggerConfig) -> None:
        """Handle trigger activation."""
        self._active_trigger = trigger
        self._show_wheel_at_cursor()

    def _on_trigger_released(self, trigger: TriggerConfig) -> None:
        """Handle trigger release."""
        if self._active_trigger and self._active_trigger.id == trigger.id:
            if trigger.hold_to_show and self._is_wheel_visible:
                # Select hovered action and close
                self._overlay._wheel.mouseReleaseEvent(
                    type('Event', (), {
                        'button': lambda: __import__('PyQt6.QtCore', fromlist=['Qt']).Qt.MouseButton.LeftButton,
                        'position': lambda: self._overlay._wheel.mapFromGlobal(QCursor.pos())
                    })()
                )
            self._active_trigger = None

    def _show_wheel_at_cursor(self) -> None:
        """Show the wheel at the current cursor position."""
        if self._is_wheel_visible:
            return

        # Get the appropriate menu based on focused window
        window_info = self._window_detector.get_active_window()
        window_class = window_info.window_class if window_info else ""
        window_title = window_info.window_title if window_info else ""

        menu = self._config_manager.get_menu_for_window(window_class, window_title)
        if menu is None:
            print("No menu configured")
            return

        profile = self._config_manager.get_active_profile()
        if profile:
            self._overlay.set_profile(profile)

        self._overlay.show_wheel(menu, QCursor.pos())
        self._is_wheel_visible = True
        self.wheel_shown.emit()

    def _show_specific_menu(self, menu_id: str) -> None:
        """Show a specific menu by ID."""
        profile = self._config_manager.get_active_profile()
        if profile and menu_id in profile.menus:
            self._overlay.set_profile(profile)
            self._overlay.show_wheel(profile.menus[menu_id], QCursor.pos())
            self._is_wheel_visible = True
            self.wheel_shown.emit()

    def _hide_wheel(self) -> None:
        """Hide the wheel."""
        if self._overlay and self._is_wheel_visible:
            self._overlay.hide_wheel()

    def _on_wheel_closed(self) -> None:
        """Handle wheel close."""
        self._is_wheel_visible = False
        self.wheel_hidden.emit()

    def _on_action_triggered(self, action) -> None:
        """Handle action triggered from wheel."""
        self._action_executor.execute(action)

    def _reload_config(self) -> None:
        """Reload configuration from file."""
        self._config = self._config_manager.reload()

        # Update components
        self._overlay.set_config(self._config)
        self._input_listener.set_triggers(self._config.triggers)

        print("Configuration reloaded")
        self.config_changed.emit()

    def _open_settings(self) -> None:
        """Open the settings UI."""
        import subprocess
        try:
            subprocess.Popen(
                [sys.executable, "-m", "kde_logiwheel.config_ui"],
                start_new_session=True
            )
        except Exception as e:
            print(f"Could not open settings: {e}")


def main():
    """Main entry point for the daemon."""
    daemon = LogiWheelDaemon()
    sys.exit(daemon.run())


if __name__ == "__main__":
    main()
