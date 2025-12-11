"""
Configuration manager for KDE-LogiWheel.
Handles loading, saving, and managing configuration files.
"""

import json
import os
from pathlib import Path
from typing import Optional
import uuid

from .models import (
    WheelConfig,
    WheelProfile,
    WheelMenu,
    WheelAction,
    ActionType,
    TriggerConfig,
    WindowRule,
)


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the configuration manager.

        Args:
            config_dir: Custom config directory. Defaults to ~/.config/kde-logiwheel/
        """
        if config_dir is None:
            config_dir = Path.home() / ".config" / "kde-logiwheel"

        self.config_dir = config_dir
        self.config_file = config_dir / "config.json"
        self._config: Optional[WheelConfig] = None

    def ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> WheelConfig:
        """Load configuration from file, or create default if not exists."""
        if self._config is not None:
            return self._config

        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                self._config = WheelConfig.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error loading config: {e}. Using defaults.")
                self._config = self.create_default_config()
                self.save()
        else:
            self._config = self.create_default_config()
            self.save()

        return self._config

    def save(self, config: Optional[WheelConfig] = None) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save. Uses current config if not provided.
        """
        if config is not None:
            self._config = config

        if self._config is None:
            return

        self.ensure_config_dir()

        with open(self.config_file, "w") as f:
            json.dump(self._config.to_dict(), f, indent=2)

    def reload(self) -> WheelConfig:
        """Force reload configuration from file."""
        self._config = None
        return self.load()

    def get_config(self) -> WheelConfig:
        """Get current configuration."""
        if self._config is None:
            return self.load()
        return self._config

    def get_active_profile(self) -> Optional[WheelProfile]:
        """Get the currently active profile."""
        config = self.get_config()
        if config.active_profile_id and config.active_profile_id in config.profiles:
            return config.profiles[config.active_profile_id]
        # Return first profile if active not set
        if config.profiles:
            return list(config.profiles.values())[0]
        return None

    def get_menu_for_window(
        self, window_class: str, window_title: str
    ) -> Optional[WheelMenu]:
        """Get the appropriate menu for a given window.

        Args:
            window_class: The window's WM_CLASS
            window_title: The window's title

        Returns:
            The matching WheelMenu, or default menu if no match
        """
        import re

        profile = self.get_active_profile()
        if profile is None:
            return None

        # Sort rules by priority (highest first)
        sorted_rules = sorted(
            profile.window_rules, key=lambda r: r.priority, reverse=True
        )

        for rule in sorted_rules:
            match = True

            # Check window class
            if rule.window_class:
                if rule.window_class_regex:
                    if not re.search(rule.window_class, window_class, re.IGNORECASE):
                        match = False
                else:
                    if rule.window_class.lower() not in window_class.lower():
                        match = False

            # Check window title
            if match and rule.window_title:
                if rule.window_title_regex:
                    if not re.search(rule.window_title, window_title, re.IGNORECASE):
                        match = False
                else:
                    if rule.window_title.lower() not in window_title.lower():
                        match = False

            if match and rule.menu_id in profile.menus:
                return profile.menus[rule.menu_id]

        # Return default menu
        if profile.default_menu_id and profile.default_menu_id in profile.menus:
            return profile.menus[profile.default_menu_id]

        # Return first menu as fallback
        if profile.menus:
            return list(profile.menus.values())[0]

        return None

    @staticmethod
    def generate_id() -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())[:8]

    @staticmethod
    def create_default_config() -> WheelConfig:
        """Create a default configuration with useful presets."""

        # Create default trigger (Super+Alt+W)
        default_trigger = TriggerConfig(
            id=ConfigManager.generate_id(),
            name="Default Trigger",
            enabled=True,
            trigger_type="keyboard",
            key_combination=["Super_L", "Alt_L", "w"],
            hold_to_show=True,
            activation_delay_ms=100,
        )

        # Create mouse button trigger (button 8 - forward side button)
        mouse_trigger = TriggerConfig(
            id=ConfigManager.generate_id(),
            name="Mouse Side Button",
            enabled=True,
            trigger_type="mouse",
            mouse_button=8,
            hold_to_show=True,
            activation_delay_ms=50,
        )

        # Create default actions for main menu
        default_actions = [
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Copy",
                icon="edit-copy",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "c"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Paste",
                icon="edit-paste",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "v"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Cut",
                icon="edit-cut",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "x"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Undo",
                icon="edit-undo",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "z"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Redo",
                icon="edit-redo",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "Shift", "z"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Select All",
                icon="edit-select-all",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "a"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Window Tools",
                icon="preferences-system-windows",
                action_type=ActionType.SUBMENU,
                submenu_id="window_tools",
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="System",
                icon="preferences-system",
                action_type=ActionType.SUBMENU,
                submenu_id="system_menu",
            ),
        ]

        # Create window tools submenu
        window_tools_actions = [
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Close Window",
                icon="window-close",
                action_type=ActionType.KEYPRESS,
                keys=["Alt", "F4"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Minimize",
                icon="window-minimize",
                action_type=ActionType.DBUS,
                dbus_service="org.kde.KWin",
                dbus_path="/KWin",
                dbus_interface="org.kde.KWin",
                dbus_method="activeWindow",
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Maximize",
                icon="window-maximize",
                action_type=ActionType.KEYPRESS,
                keys=["Super", "Page_Up"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Tile Left",
                icon="view-left-new",
                action_type=ActionType.KEYPRESS,
                keys=["Super", "Left"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Tile Right",
                icon="view-right-new",
                action_type=ActionType.KEYPRESS,
                keys=["Super", "Right"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Back",
                icon="go-previous",
                action_type=ActionType.BACK,
            ),
        ]

        # Create system submenu
        system_actions = [
            WheelAction(
                id=ConfigManager.generate_id(),
                name="System Settings",
                icon="systemsettings",
                action_type=ActionType.COMMAND,
                command="systemsettings5",
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="File Manager",
                icon="system-file-manager",
                action_type=ActionType.COMMAND,
                command="dolphin",
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Terminal",
                icon="utilities-terminal",
                action_type=ActionType.COMMAND,
                command="konsole",
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Screenshot",
                icon="spectacle",
                action_type=ActionType.COMMAND,
                command="spectacle",
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Lock Screen",
                icon="system-lock-screen",
                action_type=ActionType.DBUS,
                dbus_service="org.freedesktop.ScreenSaver",
                dbus_path="/ScreenSaver",
                dbus_interface="org.freedesktop.ScreenSaver",
                dbus_method="Lock",
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Back",
                icon="go-previous",
                action_type=ActionType.BACK,
            ),
        ]

        # Create menus
        main_menu_id = "main"
        main_menu = WheelMenu(
            id=main_menu_id,
            name="Main Menu",
            actions=default_actions,
            inner_radius=50,
            outer_radius=150,
        )

        window_tools_menu = WheelMenu(
            id="window_tools",
            name="Window Tools",
            actions=window_tools_actions,
            parent_id=main_menu_id,
            inner_radius=50,
            outer_radius=150,
        )

        system_menu = WheelMenu(
            id="system_menu",
            name="System",
            actions=system_actions,
            parent_id=main_menu_id,
            inner_radius=50,
            outer_radius=150,
        )

        # Create browser-specific menu
        browser_actions = [
            WheelAction(
                id=ConfigManager.generate_id(),
                name="New Tab",
                icon="tab-new",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "t"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Close Tab",
                icon="tab-close",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "w"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Reopen Tab",
                icon="edit-undo",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "Shift", "t"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Refresh",
                icon="view-refresh",
                action_type=ActionType.KEYPRESS,
                keys=["F5"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Back",
                icon="go-previous",
                action_type=ActionType.KEYPRESS,
                keys=["Alt", "Left"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Forward",
                icon="go-next",
                action_type=ActionType.KEYPRESS,
                keys=["Alt", "Right"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Bookmarks",
                icon="bookmarks",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "d"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="History",
                icon="view-history",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "h"],
            ),
        ]

        browser_menu = WheelMenu(
            id="browser_menu",
            name="Browser Menu",
            actions=browser_actions,
            inner_radius=50,
            outer_radius=150,
        )

        # Create IDE/code editor specific menu
        ide_actions = [
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Go to Definition",
                icon="go-jump",
                action_type=ActionType.KEYPRESS,
                keys=["F12"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Find References",
                icon="edit-find",
                action_type=ActionType.KEYPRESS,
                keys=["Shift", "F12"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Rename",
                icon="edit-rename",
                action_type=ActionType.KEYPRESS,
                keys=["F2"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Comment",
                icon="format-text-code",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "/"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Format",
                icon="format-text-bold",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "Shift", "i"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Quick Fix",
                icon="dialog-ok-apply",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "."],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="Terminal",
                icon="utilities-terminal",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "`"],
            ),
            WheelAction(
                id=ConfigManager.generate_id(),
                name="File Explorer",
                icon="folder",
                action_type=ActionType.KEYPRESS,
                keys=["Ctrl", "Shift", "e"],
            ),
        ]

        ide_menu = WheelMenu(
            id="ide_menu",
            name="IDE Menu",
            actions=ide_actions,
            inner_radius=50,
            outer_radius=150,
        )

        # Create default profile
        default_profile = WheelProfile(
            id="default",
            name="Default Profile",
            menus={
                main_menu_id: main_menu,
                "window_tools": window_tools_menu,
                "system_menu": system_menu,
                "browser_menu": browser_menu,
                "ide_menu": ide_menu,
            },
            default_menu_id=main_menu_id,
            window_rules=[
                WindowRule(
                    id=ConfigManager.generate_id(),
                    name="Firefox",
                    window_class="firefox",
                    menu_id="browser_menu",
                    priority=10,
                ),
                WindowRule(
                    id=ConfigManager.generate_id(),
                    name="Chrome",
                    window_class="google-chrome",
                    menu_id="browser_menu",
                    priority=10,
                ),
                WindowRule(
                    id=ConfigManager.generate_id(),
                    name="Chromium",
                    window_class="chromium",
                    menu_id="browser_menu",
                    priority=10,
                ),
                WindowRule(
                    id=ConfigManager.generate_id(),
                    name="VS Code",
                    window_class="code",
                    menu_id="ide_menu",
                    priority=10,
                ),
                WindowRule(
                    id=ConfigManager.generate_id(),
                    name="Kate",
                    window_class="kate",
                    menu_id="ide_menu",
                    priority=10,
                ),
                WindowRule(
                    id=ConfigManager.generate_id(),
                    name="KDevelop",
                    window_class="kdevelop",
                    menu_id="ide_menu",
                    priority=10,
                ),
            ],
        )

        # Create the full config
        return WheelConfig(
            triggers=[default_trigger, mouse_trigger],
            profiles={"default": default_profile},
            active_profile_id="default",
            animation_duration_ms=150,
            wheel_opacity=0.95,
            show_labels=True,
            icon_size=32,
            font_size=12,
            background_color="#2d2d2d",
            hover_color="#3daee9",
            text_color="#ffffff",
            border_color="#4d4d4d",
            close_on_action=True,
            center_deadzone_radius=30,
        )


# Export convenience functions
def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    if not hasattr(get_config_manager, "_instance"):
        get_config_manager._instance = ConfigManager()
    return get_config_manager._instance
