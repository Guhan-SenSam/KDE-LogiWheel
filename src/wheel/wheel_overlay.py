"""
Wheel overlay window - transparent fullscreen window that hosts the wheel widget.
"""

from typing import Optional, Callable
import subprocess

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QCursor, QScreen

from .wheel_widget import WheelWidget
from ..config.models import WheelMenu, WheelAction, ActionType, WheelConfig, WheelProfile


class WheelOverlay(QWidget):
    """Transparent overlay window that displays the wheel at cursor position."""

    # Signals
    action_triggered = pyqtSignal(WheelAction)  # Emitted when an action is executed
    closed = pyqtSignal()  # Emitted when the overlay is closed

    def __init__(self, config: WheelConfig, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._config = config
        self._profile: Optional[WheelProfile] = None
        self._menu_stack: list[str] = []  # Stack of menu IDs for navigation
        self._wheel: Optional[WheelWidget] = None
        self._cursor_pos = QPoint()
        self._close_callback: Optional[Callable] = None

        # Setup window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.X11BypassWindowManagerHint  # Important for KDE
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        # Set to cover all screens
        self._update_geometry()

        # Create wheel widget
        self._wheel = WheelWidget(self)
        self._apply_theme()

        # Connect signals
        self._wheel.action_selected.connect(self._on_action_selected)
        self._wheel.submenu_requested.connect(self._on_submenu_requested)
        self._wheel.back_requested.connect(self._on_back_requested)
        self._wheel.close_requested.connect(self.hide_wheel)
        self._wheel.action_hovered.connect(self._on_action_hovered)

    def _update_geometry(self) -> None:
        """Update geometry to cover all screens."""
        # Get combined geometry of all screens
        screens = QApplication.screens()
        if not screens:
            return

        combined = screens[0].geometry()
        for screen in screens[1:]:
            combined = combined.united(screen.geometry())

        self.setGeometry(combined)

    def _apply_theme(self) -> None:
        """Apply theme from config to wheel widget."""
        if self._wheel:
            self._wheel.set_theme(
                bg_color=self._config.background_color,
                hover_color=self._config.hover_color,
                text_color=self._config.text_color,
                border_color=self._config.border_color,
                icon_size=self._config.icon_size,
                font_size=self._config.font_size,
                show_labels=self._config.show_labels,
            )

    def set_config(self, config: WheelConfig) -> None:
        """Update configuration."""
        self._config = config
        self._apply_theme()

    def set_profile(self, profile: WheelProfile) -> None:
        """Set the active profile."""
        self._profile = profile

    def show_wheel(
        self,
        menu: WheelMenu,
        position: Optional[QPoint] = None,
        callback: Optional[Callable] = None
    ) -> None:
        """Show the wheel at the specified position.

        Args:
            menu: The menu to display
            position: Position to show wheel at. Uses cursor position if None.
            callback: Optional callback when wheel closes
        """
        if position is None:
            position = QCursor.pos()

        self._cursor_pos = position
        self._close_callback = callback
        self._menu_stack = [menu.id]

        # Position wheel at cursor
        self._wheel.set_menu(menu)
        wheel_size = self._wheel.size()

        # Convert global position to local
        local_pos = self.mapFromGlobal(position)

        self._wheel.move(
            local_pos.x() - wheel_size.width() // 2,
            local_pos.y() - wheel_size.height() // 2,
        )

        # Show overlay and wheel
        self.show()
        self.raise_()
        self._wheel.show()
        self._wheel.animate_show(self._config.animation_duration_ms)

        # Grab mouse to ensure we get all events
        self.grabMouse()

    def hide_wheel(self) -> None:
        """Hide the wheel with animation."""
        if self._wheel:
            self._wheel.animate_hide(
                self._config.animation_duration_ms // 2,
                callback=self._finish_hide
            )

    def _finish_hide(self) -> None:
        """Complete the hide operation."""
        self.releaseMouse()
        self.hide()
        self._menu_stack.clear()
        self.closed.emit()
        if self._close_callback:
            self._close_callback()
            self._close_callback = None

    def _on_action_selected(self, action: WheelAction) -> None:
        """Handle action selection."""
        self.action_triggered.emit(action)

        if self._config.close_on_action:
            self.hide_wheel()

    def _on_submenu_requested(self, submenu_id: str) -> None:
        """Handle submenu navigation."""
        if self._profile and submenu_id in self._profile.menus:
            self._menu_stack.append(submenu_id)
            menu = self._profile.menus[submenu_id]

            # Animate transition
            self._wheel.animate_hide(
                self._config.animation_duration_ms // 2,
                callback=lambda: self._show_menu(menu)
            )

    def _show_menu(self, menu: WheelMenu) -> None:
        """Show a menu (used for transitions)."""
        self._wheel.set_menu(menu)
        self._wheel.animate_show(self._config.animation_duration_ms)

    def _on_back_requested(self) -> None:
        """Handle back navigation."""
        if len(self._menu_stack) > 1:
            self._menu_stack.pop()
            parent_menu_id = self._menu_stack[-1]

            if self._profile and parent_menu_id in self._profile.menus:
                menu = self._profile.menus[parent_menu_id]
                self._wheel.animate_hide(
                    self._config.animation_duration_ms // 2,
                    callback=lambda: self._show_menu(menu)
                )
        else:
            self.hide_wheel()

    def _on_action_hovered(self, action: Optional[WheelAction]) -> None:
        """Handle action hover (could show tooltip or preview)."""
        pass  # Could implement hover feedback here

    def paintEvent(self, event) -> None:
        """Paint semi-transparent background."""
        painter = QPainter(self)

        # Draw semi-transparent overlay
        overlay_color = QColor(0, 0, 0, 100)  # Semi-transparent black
        painter.fillRect(self.rect(), overlay_color)

        painter.end()

    def mousePressEvent(self, event) -> None:
        """Handle mouse press outside wheel to close."""
        # Forward to wheel if within wheel bounds
        wheel_rect = self._wheel.geometry()
        if wheel_rect.contains(event.pos()):
            # Convert to wheel coordinates
            wheel_pos = event.pos() - wheel_rect.topLeft()
            self._wheel.mousePressEvent(event)
        else:
            # Click outside - close wheel
            self.hide_wheel()

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release."""
        wheel_rect = self._wheel.geometry()
        if wheel_rect.contains(event.pos()):
            self._wheel.mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Forward mouse move to wheel."""
        wheel_rect = self._wheel.geometry()
        if wheel_rect.contains(event.pos()):
            # Create a new event with coordinates relative to wheel
            from PyQt6.QtGui import QMouseEvent
            from PyQt6.QtCore import QPointF

            wheel_pos = event.pos() - wheel_rect.topLeft()
            new_event = QMouseEvent(
                event.type(),
                QPointF(wheel_pos),
                event.globalPosition(),
                event.button(),
                event.buttons(),
                event.modifiers()
            )
            self._wheel.mouseMoveEvent(new_event)
        else:
            # Clear hover when outside wheel
            self._wheel._hovered_index = -1
            self._wheel.update()

    def keyPressEvent(self, event) -> None:
        """Handle key presses (Escape to close)."""
        if event.key() == Qt.Key.Key_Escape:
            self.hide_wheel()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event) -> None:
        """Handle show event."""
        super().showEvent(event)
        self._update_geometry()
