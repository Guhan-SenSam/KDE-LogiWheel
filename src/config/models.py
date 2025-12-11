"""
Data models for KDE-LogiWheel configuration.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json


class ActionType(Enum):
    """Types of actions that can be performed."""
    KEYPRESS = "keypress"           # Send keyboard shortcut
    COMMAND = "command"             # Execute shell command
    DBUS = "dbus"                   # Call D-Bus method
    SUBMENU = "submenu"             # Open nested wheel menu
    BACK = "back"                   # Go back to parent menu
    CLOSE = "close"                 # Close the wheel


@dataclass
class WheelAction:
    """Represents a single action in the wheel."""
    id: str
    name: str
    icon: str                       # Icon name (freedesktop icon spec) or path
    action_type: ActionType

    # For KEYPRESS actions
    keys: list[str] = field(default_factory=list)  # e.g., ["Ctrl", "C"]

    # For COMMAND actions
    command: str = ""

    # For DBUS actions
    dbus_service: str = ""
    dbus_path: str = ""
    dbus_interface: str = ""
    dbus_method: str = ""
    dbus_args: list = field(default_factory=list)

    # For SUBMENU actions
    submenu_id: str = ""

    # Visual customization
    color: str = ""                 # Optional custom color

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "action_type": self.action_type.value,
            "keys": self.keys,
            "command": self.command,
            "dbus_service": self.dbus_service,
            "dbus_path": self.dbus_path,
            "dbus_interface": self.dbus_interface,
            "dbus_method": self.dbus_method,
            "dbus_args": self.dbus_args,
            "submenu_id": self.submenu_id,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WheelAction":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            icon=data.get("icon", ""),
            action_type=ActionType(data.get("action_type", "keypress")),
            keys=data.get("keys", []),
            command=data.get("command", ""),
            dbus_service=data.get("dbus_service", ""),
            dbus_path=data.get("dbus_path", ""),
            dbus_interface=data.get("dbus_interface", ""),
            dbus_method=data.get("dbus_method", ""),
            dbus_args=data.get("dbus_args", []),
            submenu_id=data.get("submenu_id", ""),
            color=data.get("color", ""),
        )


@dataclass
class WheelMenu:
    """Represents a wheel menu (can be main or submenu)."""
    id: str
    name: str
    actions: list[WheelAction] = field(default_factory=list)
    parent_id: str = ""            # Empty for root menu

    # Visual settings
    inner_radius: int = 50
    outer_radius: int = 150

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "actions": [a.to_dict() for a in self.actions],
            "parent_id": self.parent_id,
            "inner_radius": self.inner_radius,
            "outer_radius": self.outer_radius,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WheelMenu":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            actions=[WheelAction.from_dict(a) for a in data.get("actions", [])],
            parent_id=data.get("parent_id", ""),
            inner_radius=data.get("inner_radius", 50),
            outer_radius=data.get("outer_radius", 150),
        )


@dataclass
class WindowRule:
    """Rule for matching windows for context-aware actions."""
    id: str
    name: str

    # Matching criteria (any can be used, all specified must match)
    window_class: str = ""          # WM_CLASS
    window_title: str = ""          # Window title (supports regex)
    window_class_regex: bool = False
    window_title_regex: bool = False

    # The menu to show for matching windows
    menu_id: str = ""

    # Priority (higher = checked first)
    priority: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "window_class": self.window_class,
            "window_title": self.window_title,
            "window_class_regex": self.window_class_regex,
            "window_title_regex": self.window_title_regex,
            "menu_id": self.menu_id,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WindowRule":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            window_class=data.get("window_class", ""),
            window_title=data.get("window_title", ""),
            window_class_regex=data.get("window_class_regex", False),
            window_title_regex=data.get("window_title_regex", False),
            menu_id=data.get("menu_id", ""),
            priority=data.get("priority", 0),
        )


@dataclass
class TriggerConfig:
    """Configuration for triggering the wheel."""
    id: str
    name: str
    enabled: bool = True

    # Trigger type
    trigger_type: str = "keyboard"  # "keyboard" or "mouse"

    # For keyboard triggers
    key_combination: list[str] = field(default_factory=list)  # e.g., ["Super", "Alt", "W"]

    # For mouse triggers
    mouse_button: int = 0           # Button number (8, 9 for side buttons)

    # Behavior
    hold_to_show: bool = True       # True = hold trigger, False = toggle
    activation_delay_ms: int = 100  # Delay before showing wheel (for hold mode)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "trigger_type": self.trigger_type,
            "key_combination": self.key_combination,
            "mouse_button": self.mouse_button,
            "hold_to_show": self.hold_to_show,
            "activation_delay_ms": self.activation_delay_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TriggerConfig":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
            trigger_type=data.get("trigger_type", "keyboard"),
            key_combination=data.get("key_combination", []),
            mouse_button=data.get("mouse_button", 0),
            hold_to_show=data.get("hold_to_show", True),
            activation_delay_ms=data.get("activation_delay_ms", 100),
        )


@dataclass
class WheelProfile:
    """A complete wheel profile with menus and rules."""
    id: str
    name: str

    # All menus (main and submenus)
    menus: dict[str, WheelMenu] = field(default_factory=dict)

    # Default menu ID (used when no window rule matches)
    default_menu_id: str = ""

    # Window rules for context-aware menus
    window_rules: list[WindowRule] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "menus": {k: v.to_dict() for k, v in self.menus.items()},
            "default_menu_id": self.default_menu_id,
            "window_rules": [r.to_dict() for r in self.window_rules],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WheelProfile":
        menus = {}
        for k, v in data.get("menus", {}).items():
            menus[k] = WheelMenu.from_dict(v)

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            menus=menus,
            default_menu_id=data.get("default_menu_id", ""),
            window_rules=[WindowRule.from_dict(r) for r in data.get("window_rules", [])],
        )


@dataclass
class WheelConfig:
    """Main configuration for the entire application."""

    # Triggers
    triggers: list[TriggerConfig] = field(default_factory=list)

    # Profiles
    profiles: dict[str, WheelProfile] = field(default_factory=dict)

    # Active profile
    active_profile_id: str = ""

    # Global settings
    animation_duration_ms: int = 150
    wheel_opacity: float = 0.95
    show_labels: bool = True
    icon_size: int = 32
    font_size: int = 12

    # Theme
    background_color: str = "#2d2d2d"
    hover_color: str = "#3daee9"
    text_color: str = "#ffffff"
    border_color: str = "#4d4d4d"

    # Behavior
    close_on_action: bool = True
    center_deadzone_radius: int = 30

    def to_dict(self) -> dict:
        return {
            "triggers": [t.to_dict() for t in self.triggers],
            "profiles": {k: v.to_dict() for k, v in self.profiles.items()},
            "active_profile_id": self.active_profile_id,
            "animation_duration_ms": self.animation_duration_ms,
            "wheel_opacity": self.wheel_opacity,
            "show_labels": self.show_labels,
            "icon_size": self.icon_size,
            "font_size": self.font_size,
            "background_color": self.background_color,
            "hover_color": self.hover_color,
            "text_color": self.text_color,
            "border_color": self.border_color,
            "close_on_action": self.close_on_action,
            "center_deadzone_radius": self.center_deadzone_radius,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WheelConfig":
        profiles = {}
        for k, v in data.get("profiles", {}).items():
            profiles[k] = WheelProfile.from_dict(v)

        return cls(
            triggers=[TriggerConfig.from_dict(t) for t in data.get("triggers", [])],
            profiles=profiles,
            active_profile_id=data.get("active_profile_id", ""),
            animation_duration_ms=data.get("animation_duration_ms", 150),
            wheel_opacity=data.get("wheel_opacity", 0.95),
            show_labels=data.get("show_labels", True),
            icon_size=data.get("icon_size", 32),
            font_size=data.get("font_size", 12),
            background_color=data.get("background_color", "#2d2d2d"),
            hover_color=data.get("hover_color", "#3daee9"),
            text_color=data.get("text_color", "#ffffff"),
            border_color=data.get("border_color", "#4d4d4d"),
            close_on_action=data.get("close_on_action", True),
            center_deadzone_radius=data.get("center_deadzone_radius", 30),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "WheelConfig":
        return cls.from_dict(json.loads(json_str))
