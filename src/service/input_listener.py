"""
Input listener for detecting trigger keys/buttons.
Supports keyboard shortcuts and mouse buttons.
"""

import os
from typing import Optional, Callable, Set
from threading import Thread, Event

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from ..config.models import TriggerConfig


class InputListener(QObject):
    """Listens for input events to trigger the wheel."""

    # Signals
    trigger_activated = pyqtSignal(TriggerConfig)  # Emitted when trigger is pressed
    trigger_released = pyqtSignal(TriggerConfig)   # Emitted when trigger is released

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._triggers: list[TriggerConfig] = []
        self._active_triggers: Set[str] = set()
        self._listener_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._pynput_listener = None
        self._evdev_devices = []

        # Activation delay timers
        self._delay_timers: dict[str, QTimer] = {}

        # Track pressed keys/buttons
        self._pressed_keys: Set[str] = set()
        self._pressed_buttons: Set[int] = set()

        # Determine session type
        self._session_type = os.environ.get("XDG_SESSION_TYPE", "x11")

    def set_triggers(self, triggers: list[TriggerConfig]) -> None:
        """Set the triggers to listen for.

        Args:
            triggers: List of trigger configurations
        """
        self._triggers = [t for t in triggers if t.enabled]

        # Create delay timers for each trigger
        for trigger in self._triggers:
            if trigger.id not in self._delay_timers:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(
                    lambda t=trigger: self._on_delay_complete(t)
                )
                self._delay_timers[trigger.id] = timer

    def start(self) -> None:
        """Start listening for input events."""
        if self._listener_thread is not None:
            return

        self._stop_event.clear()

        # Try different input methods
        if self._session_type == "wayland":
            # On Wayland, we need special handling
            self._start_wayland_listener()
        else:
            # X11 - use pynput or evdev
            self._start_x11_listener()

    def stop(self) -> None:
        """Stop listening for input events."""
        self._stop_event.set()

        if self._pynput_listener:
            self._pynput_listener.stop()
            self._pynput_listener = None

        for device in self._evdev_devices:
            try:
                device.close()
            except Exception:
                pass
        self._evdev_devices.clear()

        if self._listener_thread:
            self._listener_thread.join(timeout=1)
            self._listener_thread = None

        # Stop all timers
        for timer in self._delay_timers.values():
            timer.stop()

    def _start_x11_listener(self) -> None:
        """Start listener for X11 using pynput."""
        try:
            from pynput import keyboard, mouse

            def on_key_press(key):
                key_name = self._get_key_name(key)
                if key_name:
                    self._pressed_keys.add(key_name)
                    self._check_keyboard_triggers()

            def on_key_release(key):
                key_name = self._get_key_name(key)
                if key_name and key_name in self._pressed_keys:
                    self._pressed_keys.discard(key_name)
                    self._check_keyboard_trigger_release()

            def on_mouse_click(x, y, button, pressed):
                button_num = self._get_button_number(button)
                if pressed:
                    self._pressed_buttons.add(button_num)
                    self._check_mouse_triggers(button_num)
                else:
                    self._pressed_buttons.discard(button_num)
                    self._check_mouse_trigger_release(button_num)

            # Start keyboard listener
            self._keyboard_listener = keyboard.Listener(
                on_press=on_key_press,
                on_release=on_key_release
            )
            self._keyboard_listener.start()

            # Start mouse listener
            self._mouse_listener = mouse.Listener(
                on_click=on_mouse_click
            )
            self._mouse_listener.start()

        except ImportError:
            print("pynput not available, trying evdev...")
            self._start_evdev_listener()

    def _start_wayland_listener(self) -> None:
        """Start listener for Wayland.

        On Wayland, direct input capture is restricted for security.
        We use libinput/evdev with appropriate permissions, or rely on
        global shortcuts registered with KDE.
        """
        # Try evdev first (requires input group membership)
        self._start_evdev_listener()

    def _start_evdev_listener(self) -> None:
        """Start listener using evdev (Linux input subsystem)."""
        try:
            import evdev
            from evdev import ecodes

            # Find all input devices
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

            # Filter for keyboard and mouse devices
            for device in devices:
                caps = device.capabilities()
                # Check for keyboard (has EV_KEY with letter keys)
                if ecodes.EV_KEY in caps:
                    keys = caps[ecodes.EV_KEY]
                    # Check if it's a keyboard (has letter keys) or mouse (has buttons)
                    has_letters = any(k for k in keys if ecodes.KEY_A <= k <= ecodes.KEY_Z)
                    has_mouse_buttons = any(
                        k for k in keys
                        if k in [ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE,
                                ecodes.BTN_SIDE, ecodes.BTN_EXTRA, ecodes.BTN_FORWARD,
                                ecodes.BTN_BACK]
                    )

                    if has_letters or has_mouse_buttons:
                        self._evdev_devices.append(device)

            if not self._evdev_devices:
                print("No input devices found. Make sure you have permissions (input group).")
                return

            # Start listener thread
            self._listener_thread = Thread(target=self._evdev_listener_loop, daemon=True)
            self._listener_thread.start()

        except ImportError:
            print("evdev not available. Please install python-evdev.")
        except PermissionError:
            print("Permission denied accessing input devices. Add user to 'input' group.")
        except Exception as e:
            print(f"Error starting evdev listener: {e}")

    def _evdev_listener_loop(self) -> None:
        """Main loop for evdev listener."""
        import evdev
        from evdev import ecodes
        import select

        try:
            while not self._stop_event.is_set():
                # Use select to wait for events from any device
                r, w, x = select.select(self._evdev_devices, [], [], 0.1)

                for device in r:
                    try:
                        for event in device.read():
                            if event.type == ecodes.EV_KEY:
                                self._handle_evdev_key_event(event)
                    except Exception:
                        pass

        except Exception as e:
            print(f"Error in evdev listener: {e}")

    def _handle_evdev_key_event(self, event) -> None:
        """Handle an evdev key event."""
        from evdev import ecodes

        key_name = self._evdev_key_to_name(event.code)
        is_press = event.value in [1, 2]  # 1 = press, 2 = repeat
        is_release = event.value == 0

        # Check if it's a mouse button
        is_mouse = event.code in [
            ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE,
            ecodes.BTN_SIDE, ecodes.BTN_EXTRA, ecodes.BTN_FORWARD,
            ecodes.BTN_BACK, ecodes.BTN_TASK
        ]

        if is_mouse:
            button_num = self._evdev_button_to_number(event.code)
            if is_press:
                self._pressed_buttons.add(button_num)
                # Use QTimer.singleShot for thread safety
                QTimer.singleShot(0, lambda: self._check_mouse_triggers(button_num))
            elif is_release:
                self._pressed_buttons.discard(button_num)
                QTimer.singleShot(0, lambda: self._check_mouse_trigger_release(button_num))
        else:
            if is_press and key_name:
                self._pressed_keys.add(key_name)
                QTimer.singleShot(0, self._check_keyboard_triggers)
            elif is_release and key_name:
                self._pressed_keys.discard(key_name)
                QTimer.singleShot(0, self._check_keyboard_trigger_release)

    def _evdev_key_to_name(self, code: int) -> str:
        """Convert evdev key code to key name."""
        from evdev import ecodes

        key_map = {
            ecodes.KEY_LEFTCTRL: "Control_L",
            ecodes.KEY_RIGHTCTRL: "Control_R",
            ecodes.KEY_LEFTALT: "Alt_L",
            ecodes.KEY_RIGHTALT: "Alt_R",
            ecodes.KEY_LEFTSHIFT: "Shift_L",
            ecodes.KEY_RIGHTSHIFT: "Shift_R",
            ecodes.KEY_LEFTMETA: "Super_L",
            ecodes.KEY_RIGHTMETA: "Super_R",
            ecodes.KEY_TAB: "Tab",
            ecodes.KEY_ENTER: "Return",
            ecodes.KEY_ESC: "Escape",
            ecodes.KEY_SPACE: "space",
            ecodes.KEY_BACKSPACE: "BackSpace",
            ecodes.KEY_DELETE: "Delete",
            ecodes.KEY_HOME: "Home",
            ecodes.KEY_END: "End",
            ecodes.KEY_PAGEUP: "Page_Up",
            ecodes.KEY_PAGEDOWN: "Page_Down",
            ecodes.KEY_LEFT: "Left",
            ecodes.KEY_RIGHT: "Right",
            ecodes.KEY_UP: "Up",
            ecodes.KEY_DOWN: "Down",
        }

        if code in key_map:
            return key_map[code]

        # Letter keys
        if ecodes.KEY_A <= code <= ecodes.KEY_Z:
            return chr(ord('a') + (code - ecodes.KEY_A))

        # Number keys
        if ecodes.KEY_1 <= code <= ecodes.KEY_0:
            if code == ecodes.KEY_0:
                return "0"
            return str(code - ecodes.KEY_1 + 1)

        # Function keys
        if ecodes.KEY_F1 <= code <= ecodes.KEY_F12:
            return f"F{code - ecodes.KEY_F1 + 1}"

        return ""

    def _evdev_button_to_number(self, code: int) -> int:
        """Convert evdev button code to button number."""
        from evdev import ecodes

        button_map = {
            ecodes.BTN_LEFT: 1,
            ecodes.BTN_RIGHT: 3,
            ecodes.BTN_MIDDLE: 2,
            ecodes.BTN_SIDE: 8,
            ecodes.BTN_EXTRA: 9,
            ecodes.BTN_FORWARD: 9,
            ecodes.BTN_BACK: 8,
        }

        return button_map.get(code, code - ecodes.BTN_MOUSE + 1)

    def _get_key_name(self, key) -> str:
        """Convert pynput key to string name."""
        try:
            from pynput.keyboard import Key

            key_map = {
                Key.ctrl_l: "Control_L",
                Key.ctrl_r: "Control_R",
                Key.ctrl: "Control_L",
                Key.alt_l: "Alt_L",
                Key.alt_r: "Alt_R",
                Key.alt: "Alt_L",
                Key.shift_l: "Shift_L",
                Key.shift_r: "Shift_R",
                Key.shift: "Shift_L",
                Key.cmd_l: "Super_L",
                Key.cmd_r: "Super_R",
                Key.cmd: "Super_L",
                Key.tab: "Tab",
                Key.enter: "Return",
                Key.esc: "Escape",
                Key.space: "space",
                Key.backspace: "BackSpace",
                Key.delete: "Delete",
                Key.home: "Home",
                Key.end: "End",
                Key.page_up: "Page_Up",
                Key.page_down: "Page_Down",
                Key.left: "Left",
                Key.right: "Right",
                Key.up: "Up",
                Key.down: "Down",
            }

            if key in key_map:
                return key_map[key]

            # Handle function keys
            for i in range(1, 13):
                if hasattr(Key, f'f{i}') and key == getattr(Key, f'f{i}'):
                    return f"F{i}"

            # Handle character keys
            if hasattr(key, 'char') and key.char:
                return key.char

        except Exception:
            pass

        return ""

    def _get_button_number(self, button) -> int:
        """Convert pynput button to number."""
        try:
            from pynput.mouse import Button

            button_map = {
                Button.left: 1,
                Button.right: 3,
                Button.middle: 2,
            }

            if button in button_map:
                return button_map[button]

            # Handle extra buttons (x1, x2, etc.)
            if hasattr(button, 'value'):
                return button.value

        except Exception:
            pass

        return 0

    def _check_keyboard_triggers(self) -> None:
        """Check if any keyboard trigger is activated."""
        for trigger in self._triggers:
            if trigger.trigger_type != "keyboard":
                continue

            # Normalize key names for comparison
            trigger_keys = set(self._normalize_key(k) for k in trigger.key_combination)
            pressed_normalized = set(self._normalize_key(k) for k in self._pressed_keys)

            if trigger_keys <= pressed_normalized:
                # All trigger keys are pressed
                if trigger.id not in self._active_triggers:
                    if trigger.hold_to_show and trigger.activation_delay_ms > 0:
                        # Start delay timer
                        self._delay_timers[trigger.id].start(trigger.activation_delay_ms)
                    else:
                        self._activate_trigger(trigger)

    def _check_keyboard_trigger_release(self) -> None:
        """Check if any keyboard trigger is released."""
        for trigger in self._triggers:
            if trigger.trigger_type != "keyboard":
                continue
            if trigger.id not in self._active_triggers:
                # Cancel delay timer if running
                if trigger.id in self._delay_timers:
                    self._delay_timers[trigger.id].stop()
                continue

            # Check if trigger keys are still pressed
            trigger_keys = set(self._normalize_key(k) for k in trigger.key_combination)
            pressed_normalized = set(self._normalize_key(k) for k in self._pressed_keys)

            if not (trigger_keys <= pressed_normalized):
                self._deactivate_trigger(trigger)

    def _check_mouse_triggers(self, button: int) -> None:
        """Check if a mouse trigger is activated."""
        for trigger in self._triggers:
            if trigger.trigger_type != "mouse":
                continue
            if trigger.mouse_button != button:
                continue

            if trigger.id not in self._active_triggers:
                if trigger.hold_to_show and trigger.activation_delay_ms > 0:
                    self._delay_timers[trigger.id].start(trigger.activation_delay_ms)
                else:
                    self._activate_trigger(trigger)

    def _check_mouse_trigger_release(self, button: int) -> None:
        """Check if a mouse trigger is released."""
        for trigger in self._triggers:
            if trigger.trigger_type != "mouse":
                continue
            if trigger.mouse_button != button:
                continue
            if trigger.id not in self._active_triggers:
                if trigger.id in self._delay_timers:
                    self._delay_timers[trigger.id].stop()
                continue

            self._deactivate_trigger(trigger)

    def _normalize_key(self, key: str) -> str:
        """Normalize key name for comparison."""
        key_map = {
            "ctrl": "control_l",
            "control": "control_l",
            "control_l": "control_l",
            "control_r": "control_r",
            "alt": "alt_l",
            "alt_l": "alt_l",
            "alt_r": "alt_r",
            "shift": "shift_l",
            "shift_l": "shift_l",
            "shift_r": "shift_r",
            "super": "super_l",
            "super_l": "super_l",
            "super_r": "super_r",
            "meta": "super_l",
            "win": "super_l",
        }
        return key_map.get(key.lower(), key.lower())

    def _on_delay_complete(self, trigger: TriggerConfig) -> None:
        """Called when activation delay timer completes."""
        # Verify trigger keys/button are still pressed
        if trigger.trigger_type == "keyboard":
            trigger_keys = set(self._normalize_key(k) for k in trigger.key_combination)
            pressed_normalized = set(self._normalize_key(k) for k in self._pressed_keys)
            if trigger_keys <= pressed_normalized:
                self._activate_trigger(trigger)
        elif trigger.trigger_type == "mouse":
            if trigger.mouse_button in self._pressed_buttons:
                self._activate_trigger(trigger)

    def _activate_trigger(self, trigger: TriggerConfig) -> None:
        """Activate a trigger."""
        if trigger.id in self._active_triggers:
            return
        self._active_triggers.add(trigger.id)
        self.trigger_activated.emit(trigger)

    def _deactivate_trigger(self, trigger: TriggerConfig) -> None:
        """Deactivate a trigger."""
        if trigger.id not in self._active_triggers:
            return
        self._active_triggers.discard(trigger.id)
        self.trigger_released.emit(trigger)
