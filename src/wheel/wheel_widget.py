"""
Radial wheel widget for displaying actions.
"""

import math
from typing import Optional, Callable

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import (
    QPainter,
    QPainterPath,
    QColor,
    QBrush,
    QPen,
    QFont,
    QFontMetrics,
    QIcon,
    QPixmap,
    QRadialGradient,
    QCursor,
)

from ..config.models import WheelMenu, WheelAction, ActionType


class WheelWidget(QWidget):
    """A radial wheel menu widget."""

    # Signals
    action_selected = pyqtSignal(WheelAction)  # Emitted when an action is selected
    action_hovered = pyqtSignal(object)  # Emitted when hovering over an action (or None)
    submenu_requested = pyqtSignal(str)  # Emitted when a submenu should be opened
    back_requested = pyqtSignal()  # Emitted when user wants to go back
    close_requested = pyqtSignal()  # Emitted when wheel should close

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        inner_radius: int = 50,
        outer_radius: int = 150,
    ):
        super().__init__(parent)

        # Geometry
        self._inner_radius = inner_radius
        self._outer_radius = outer_radius
        self._center = QPointF(outer_radius + 20, outer_radius + 20)

        # State
        self._menu: Optional[WheelMenu] = None
        self._hovered_index: int = -1
        self._selected_index: int = -1

        # Animation
        self._scale = 0.0
        self._target_scale = 1.0
        self._animation: Optional[QPropertyAnimation] = None

        # Theme colors (will be set from config)
        self._bg_color = QColor("#2d2d2d")
        self._hover_color = QColor("#3daee9")
        self._text_color = QColor("#ffffff")
        self._border_color = QColor("#4d4d4d")
        self._icon_size = 32
        self._font_size = 12
        self._show_labels = True

        # Setup widget
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self._update_size()

    def _update_size(self) -> None:
        """Update widget size based on radii."""
        size = (self._outer_radius + 20) * 2
        self.setFixedSize(size, size)
        self._center = QPointF(size / 2, size / 2)

    @pyqtProperty(float)
    def scale(self) -> float:
        return self._scale

    @scale.setter
    def scale(self, value: float) -> None:
        self._scale = value
        self.update()

    def set_menu(self, menu: WheelMenu) -> None:
        """Set the menu to display."""
        self._menu = menu
        self._inner_radius = menu.inner_radius
        self._outer_radius = menu.outer_radius
        self._hovered_index = -1
        self._update_size()
        self.update()

    def set_theme(
        self,
        bg_color: str,
        hover_color: str,
        text_color: str,
        border_color: str,
        icon_size: int,
        font_size: int,
        show_labels: bool,
    ) -> None:
        """Set theme colors and options."""
        self._bg_color = QColor(bg_color)
        self._hover_color = QColor(hover_color)
        self._text_color = QColor(text_color)
        self._border_color = QColor(border_color)
        self._icon_size = icon_size
        self._font_size = font_size
        self._show_labels = show_labels
        self.update()

    def animate_show(self, duration_ms: int = 150) -> None:
        """Animate the wheel appearing."""
        if self._animation is not None:
            self._animation.stop()

        self._animation = QPropertyAnimation(self, b"scale")
        self._animation.setDuration(duration_ms)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutBack)
        self._animation.start()

    def animate_hide(self, duration_ms: int = 100, callback: Optional[Callable] = None) -> None:
        """Animate the wheel disappearing."""
        if self._animation is not None:
            self._animation.stop()

        self._animation = QPropertyAnimation(self, b"scale")
        self._animation.setDuration(duration_ms)
        self._animation.setStartValue(self._scale)
        self._animation.setEndValue(0.0)
        self._animation.setEasingCurve(QEasingCurve.Type.InBack)
        if callback:
            self._animation.finished.connect(callback)
        self._animation.start()

    def _get_sector_at_point(self, point: QPointF) -> int:
        """Get the sector index at the given point, or -1 if none."""
        if self._menu is None or not self._menu.actions:
            return -1

        # Calculate distance from center
        dx = point.x() - self._center.x()
        dy = point.y() - self._center.y()
        distance = math.sqrt(dx * dx + dy * dy)

        # Check if within ring
        scaled_inner = self._inner_radius * self._scale
        scaled_outer = self._outer_radius * self._scale

        if distance < scaled_inner or distance > scaled_outer:
            return -1

        # Calculate angle (0 at top, clockwise)
        angle = math.degrees(math.atan2(dx, -dy))
        if angle < 0:
            angle += 360

        # Calculate sector
        num_actions = len(self._menu.actions)
        sector_angle = 360 / num_actions
        sector_index = int(angle / sector_angle)

        return sector_index % num_actions

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse movement for hover effects."""
        point = QPointF(event.position())
        new_index = self._get_sector_at_point(point)

        if new_index != self._hovered_index:
            self._hovered_index = new_index
            if new_index >= 0 and self._menu:
                self.action_hovered.emit(self._menu.actions[new_index])
            else:
                self.action_hovered.emit(None)
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release for selection."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        point = QPointF(event.position())
        index = self._get_sector_at_point(point)

        if index >= 0 and self._menu:
            action = self._menu.actions[index]
            self._selected_index = index
            self.update()

            # Handle different action types
            if action.action_type == ActionType.SUBMENU:
                self.submenu_requested.emit(action.submenu_id)
            elif action.action_type == ActionType.BACK:
                self.back_requested.emit()
            elif action.action_type == ActionType.CLOSE:
                self.close_requested.emit()
            else:
                self.action_selected.emit(action)

        # Check if clicked in center (close)
        dx = point.x() - self._center.x()
        dy = point.y() - self._center.y()
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < self._inner_radius * self._scale * 0.7:
            self.close_requested.emit()

    def paintEvent(self, event) -> None:
        """Paint the wheel."""
        if self._menu is None or not self._menu.actions:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Apply scale transform
        painter.translate(self._center)
        painter.scale(self._scale, self._scale)
        painter.translate(-self._center)

        num_actions = len(self._menu.actions)
        sector_angle = 360 / num_actions

        # Draw sectors
        for i, action in enumerate(self._menu.actions):
            self._draw_sector(painter, i, action, sector_angle)

        # Draw center circle
        self._draw_center(painter)

        painter.end()

    def _draw_sector(
        self, painter: QPainter, index: int, action: WheelAction, sector_angle: float
    ) -> None:
        """Draw a single sector."""
        start_angle = index * sector_angle - 90 - sector_angle / 2
        is_hovered = index == self._hovered_index

        # Create sector path
        path = QPainterPath()

        # Outer arc
        outer_rect = QRectF(
            self._center.x() - self._outer_radius,
            self._center.y() - self._outer_radius,
            self._outer_radius * 2,
            self._outer_radius * 2,
        )

        inner_rect = QRectF(
            self._center.x() - self._inner_radius,
            self._center.y() - self._inner_radius,
            self._inner_radius * 2,
            self._inner_radius * 2,
        )

        # Calculate arc points
        start_rad = math.radians(start_angle)
        end_rad = math.radians(start_angle + sector_angle)

        outer_start = QPointF(
            self._center.x() + self._outer_radius * math.cos(start_rad),
            self._center.y() + self._outer_radius * math.sin(start_rad),
        )
        inner_start = QPointF(
            self._center.x() + self._inner_radius * math.cos(start_rad),
            self._center.y() + self._inner_radius * math.sin(start_rad),
        )
        inner_end = QPointF(
            self._center.x() + self._inner_radius * math.cos(end_rad),
            self._center.y() + self._inner_radius * math.sin(end_rad),
        )

        # Build path
        path.moveTo(inner_start)
        path.lineTo(outer_start)
        path.arcTo(outer_rect, -start_angle, -sector_angle)
        path.lineTo(inner_end)
        path.arcTo(inner_rect, -(start_angle + sector_angle), sector_angle)
        path.closeSubpath()

        # Fill color
        if action.color:
            fill_color = QColor(action.color)
            if is_hovered:
                fill_color = fill_color.lighter(120)
        else:
            fill_color = self._hover_color if is_hovered else self._bg_color

        # Add slight gradient
        mid_radius = (self._inner_radius + self._outer_radius) / 2
        gradient = QRadialGradient(self._center, self._outer_radius)
        gradient.setColorAt(0, fill_color.lighter(110))
        gradient.setColorAt(1, fill_color)

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(self._border_color, 1))
        painter.drawPath(path)

        # Draw icon and label
        mid_angle = math.radians(start_angle + sector_angle / 2)
        mid_distance = (self._inner_radius + self._outer_radius) / 2

        icon_center = QPointF(
            self._center.x() + mid_distance * math.cos(mid_angle),
            self._center.y() + mid_distance * math.sin(mid_angle),
        )

        # Draw icon
        icon = QIcon.fromTheme(action.icon)
        if not icon.isNull():
            pixmap = icon.pixmap(self._icon_size, self._icon_size)
            icon_rect = QRectF(
                icon_center.x() - self._icon_size / 2,
                icon_center.y() - self._icon_size / 2 - (8 if self._show_labels else 0),
                self._icon_size,
                self._icon_size,
            )
            painter.drawPixmap(icon_rect.toRect(), pixmap)

        # Draw label
        if self._show_labels:
            font = QFont()
            font.setPointSize(self._font_size)
            font.setBold(is_hovered)
            painter.setFont(font)
            painter.setPen(self._text_color)

            # Calculate text position
            text_center = QPointF(
                icon_center.x(),
                icon_center.y() + self._icon_size / 2 + 2,
            )

            # Draw text centered
            fm = QFontMetrics(font)
            text_width = fm.horizontalAdvance(action.name)
            text_rect = QRectF(
                text_center.x() - text_width / 2 - 2,
                text_center.y(),
                text_width + 4,
                fm.height(),
            )
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, action.name)

    def _draw_center(self, painter: QPainter) -> None:
        """Draw the center circle."""
        center_radius = self._inner_radius * 0.7

        # Draw filled circle
        gradient = QRadialGradient(self._center, center_radius)
        gradient.setColorAt(0, self._bg_color.lighter(130))
        gradient.setColorAt(1, self._bg_color)

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(self._border_color, 2))
        painter.drawEllipse(self._center, center_radius, center_radius)

        # Draw close icon/hint
        painter.setPen(QPen(self._text_color.darker(130), 2))
        cross_size = center_radius * 0.4
        painter.drawLine(
            QPointF(self._center.x() - cross_size, self._center.y() - cross_size),
            QPointF(self._center.x() + cross_size, self._center.y() + cross_size),
        )
        painter.drawLine(
            QPointF(self._center.x() + cross_size, self._center.y() - cross_size),
            QPointF(self._center.x() - cross_size, self._center.y() + cross_size),
        )

    def get_selected_action(self) -> Optional[WheelAction]:
        """Get the currently selected action."""
        if self._menu and 0 <= self._selected_index < len(self._menu.actions):
            return self._menu.actions[self._selected_index]
        return None
