"""
Main configuration window for KDE-LogiWheel.
"""

import sys
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
    QColorDialog,
    QGroupBox,
    QFormLayout,
    QSplitter,
    QStackedWidget,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QScrollArea,
    QFrame,
    QApplication,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QColor, QFont

from ..config import ConfigManager, WheelConfig, WheelProfile, WheelMenu, WheelAction, ActionType, TriggerConfig, WindowRule


class ColorButton(QPushButton):
    """Button that displays and allows selecting a color."""

    color_changed = pyqtSignal(str)

    def __init__(self, color: str = "#ffffff", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._color = color
        self._update_style()
        self.clicked.connect(self._pick_color)
        self.setFixedSize(60, 30)

    def _update_style(self) -> None:
        self.setStyleSheet(
            f"background-color: {self._color}; border: 1px solid #666; border-radius: 3px;"
        )

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Select Color")
        if color.isValid():
            self._color = color.name()
            self._update_style()
            self.color_changed.emit(self._color)

    def get_color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = color
        self._update_style()


class TriggerEditor(QWidget):
    """Widget for editing a trigger configuration."""

    changed = pyqtSignal()

    def __init__(self, trigger: Optional[TriggerConfig] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._trigger = trigger

        layout = QFormLayout(self)

        # Name
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self.changed)
        layout.addRow("Name:", self.name_edit)

        # Enabled
        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.stateChanged.connect(self.changed)
        layout.addRow("", self.enabled_check)

        # Trigger type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Keyboard", "Mouse Button"])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.type_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        layout.addRow("Type:", self.type_combo)

        # Keyboard trigger settings
        self.keyboard_group = QGroupBox("Keyboard Shortcut")
        keyboard_layout = QFormLayout(self.keyboard_group)

        self.keys_edit = QLineEdit()
        self.keys_edit.setPlaceholderText("e.g., Super_L+Alt_L+w")
        self.keys_edit.textChanged.connect(self.changed)
        keyboard_layout.addRow("Keys:", self.keys_edit)

        layout.addRow(self.keyboard_group)

        # Mouse trigger settings
        self.mouse_group = QGroupBox("Mouse Button")
        mouse_layout = QFormLayout(self.mouse_group)

        self.button_spin = QSpinBox()
        self.button_spin.setRange(1, 20)
        self.button_spin.setValue(8)
        self.button_spin.valueChanged.connect(self.changed)
        mouse_layout.addRow("Button Number:", self.button_spin)

        button_help = QLabel("Common: 8=Back, 9=Forward side buttons")
        button_help.setStyleSheet("color: gray; font-size: 10px;")
        mouse_layout.addRow("", button_help)

        layout.addRow(self.mouse_group)

        # Behavior
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QFormLayout(behavior_group)

        self.hold_check = QCheckBox("Hold to show (release to select)")
        self.hold_check.stateChanged.connect(self.changed)
        behavior_layout.addRow("", self.hold_check)

        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 1000)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.valueChanged.connect(self.changed)
        behavior_layout.addRow("Activation Delay:", self.delay_spin)

        layout.addRow(behavior_group)

        # Load initial data
        if trigger:
            self.load_trigger(trigger)
        self._on_type_changed()

    def _on_type_changed(self) -> None:
        is_keyboard = self.type_combo.currentIndex() == 0
        self.keyboard_group.setVisible(is_keyboard)
        self.mouse_group.setVisible(not is_keyboard)

    def load_trigger(self, trigger: TriggerConfig) -> None:
        self._trigger = trigger
        self.name_edit.setText(trigger.name)
        self.enabled_check.setChecked(trigger.enabled)
        self.type_combo.setCurrentIndex(0 if trigger.trigger_type == "keyboard" else 1)
        self.keys_edit.setText("+".join(trigger.key_combination))
        self.button_spin.setValue(trigger.mouse_button)
        self.hold_check.setChecked(trigger.hold_to_show)
        self.delay_spin.setValue(trigger.activation_delay_ms)
        self._on_type_changed()

    def save_trigger(self) -> TriggerConfig:
        if self._trigger is None:
            self._trigger = TriggerConfig(
                id=ConfigManager.generate_id(),
                name=self.name_edit.text(),
            )

        self._trigger.name = self.name_edit.text()
        self._trigger.enabled = self.enabled_check.isChecked()
        self._trigger.trigger_type = "keyboard" if self.type_combo.currentIndex() == 0 else "mouse"
        self._trigger.key_combination = [k.strip() for k in self.keys_edit.text().split("+") if k.strip()]
        self._trigger.mouse_button = self.button_spin.value()
        self._trigger.hold_to_show = self.hold_check.isChecked()
        self._trigger.activation_delay_ms = self.delay_spin.value()

        return self._trigger


class ActionEditor(QDialog):
    """Dialog for editing an action."""

    def __init__(self, action: Optional[WheelAction] = None, menus: dict = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._action = action
        self._menus = menus or {}

        self.setWindowTitle("Edit Action" if action else "New Action")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Form
        form = QFormLayout()

        # Name
        self.name_edit = QLineEdit()
        if action:
            self.name_edit.setText(action.name)
        form.addRow("Name:", self.name_edit)

        # Icon
        icon_layout = QHBoxLayout()
        self.icon_edit = QLineEdit()
        if action:
            self.icon_edit.setText(action.icon)
        self.icon_edit.setPlaceholderText("Icon name (e.g., edit-copy)")
        icon_layout.addWidget(self.icon_edit)

        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(32, 32)
        icon_layout.addWidget(self.icon_preview)
        self.icon_edit.textChanged.connect(self._update_icon_preview)

        form.addRow("Icon:", icon_layout)

        # Action type
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Keypress",
            "Command",
            "D-Bus Call",
            "Submenu",
            "Back",
            "Close"
        ])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Action Type:", self.type_combo)

        layout.addLayout(form)

        # Stacked widget for type-specific options
        self.stack = QStackedWidget()

        # Keypress options
        keypress_widget = QWidget()
        keypress_layout = QFormLayout(keypress_widget)
        self.keys_edit = QLineEdit()
        self.keys_edit.setPlaceholderText("e.g., Ctrl+c")
        keypress_layout.addRow("Keys:", self.keys_edit)
        self.stack.addWidget(keypress_widget)

        # Command options
        command_widget = QWidget()
        command_layout = QFormLayout(command_widget)
        self.command_edit = QLineEdit()
        self.command_edit.setPlaceholderText("e.g., dolphin /home")
        command_layout.addRow("Command:", self.command_edit)
        self.stack.addWidget(command_widget)

        # D-Bus options
        dbus_widget = QWidget()
        dbus_layout = QFormLayout(dbus_widget)
        self.dbus_service = QLineEdit()
        self.dbus_service.setPlaceholderText("org.kde.KWin")
        dbus_layout.addRow("Service:", self.dbus_service)
        self.dbus_path = QLineEdit()
        self.dbus_path.setPlaceholderText("/KWin")
        dbus_layout.addRow("Path:", self.dbus_path)
        self.dbus_interface = QLineEdit()
        self.dbus_interface.setPlaceholderText("org.kde.KWin")
        dbus_layout.addRow("Interface:", self.dbus_interface)
        self.dbus_method = QLineEdit()
        self.dbus_method.setPlaceholderText("activeWindow")
        dbus_layout.addRow("Method:", self.dbus_method)
        self.stack.addWidget(dbus_widget)

        # Submenu options
        submenu_widget = QWidget()
        submenu_layout = QFormLayout(submenu_widget)
        self.submenu_combo = QComboBox()
        for menu_id, menu in self._menus.items():
            self.submenu_combo.addItem(menu.name, menu_id)
        submenu_layout.addRow("Submenu:", self.submenu_combo)
        self.stack.addWidget(submenu_widget)

        # Empty widgets for Back and Close
        self.stack.addWidget(QWidget())  # Back
        self.stack.addWidget(QWidget())  # Close

        layout.addWidget(self.stack)

        # Color
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Custom Color (optional):"))
        self.color_button = ColorButton("#3daee9")
        self.color_check = QCheckBox("Use custom color")
        color_layout.addWidget(self.color_check)
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        layout.addLayout(color_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Load existing action
        if action:
            self._load_action(action)
        else:
            self._on_type_changed()

        self._update_icon_preview()

    def _update_icon_preview(self) -> None:
        icon = QIcon.fromTheme(self.icon_edit.text())
        if not icon.isNull():
            self.icon_preview.setPixmap(icon.pixmap(32, 32))
        else:
            self.icon_preview.clear()

    def _on_type_changed(self) -> None:
        self.stack.setCurrentIndex(self.type_combo.currentIndex())

    def _load_action(self, action: WheelAction) -> None:
        self.name_edit.setText(action.name)
        self.icon_edit.setText(action.icon)

        type_map = {
            ActionType.KEYPRESS: 0,
            ActionType.COMMAND: 1,
            ActionType.DBUS: 2,
            ActionType.SUBMENU: 3,
            ActionType.BACK: 4,
            ActionType.CLOSE: 5,
        }
        self.type_combo.setCurrentIndex(type_map.get(action.action_type, 0))

        self.keys_edit.setText("+".join(action.keys))
        self.command_edit.setText(action.command)
        self.dbus_service.setText(action.dbus_service)
        self.dbus_path.setText(action.dbus_path)
        self.dbus_interface.setText(action.dbus_interface)
        self.dbus_method.setText(action.dbus_method)

        if action.submenu_id:
            idx = self.submenu_combo.findData(action.submenu_id)
            if idx >= 0:
                self.submenu_combo.setCurrentIndex(idx)

        if action.color:
            self.color_check.setChecked(True)
            self.color_button.set_color(action.color)

        self._on_type_changed()

    def get_action(self) -> WheelAction:
        type_map = {
            0: ActionType.KEYPRESS,
            1: ActionType.COMMAND,
            2: ActionType.DBUS,
            3: ActionType.SUBMENU,
            4: ActionType.BACK,
            5: ActionType.CLOSE,
        }

        action_id = self._action.id if self._action else ConfigManager.generate_id()

        return WheelAction(
            id=action_id,
            name=self.name_edit.text(),
            icon=self.icon_edit.text(),
            action_type=type_map[self.type_combo.currentIndex()],
            keys=[k.strip() for k in self.keys_edit.text().split("+") if k.strip()],
            command=self.command_edit.text(),
            dbus_service=self.dbus_service.text(),
            dbus_path=self.dbus_path.text(),
            dbus_interface=self.dbus_interface.text(),
            dbus_method=self.dbus_method.text(),
            submenu_id=self.submenu_combo.currentData() if self.type_combo.currentIndex() == 3 else "",
            color=self.color_button.get_color() if self.color_check.isChecked() else "",
        )


class MenuEditor(QWidget):
    """Widget for editing a wheel menu."""

    changed = pyqtSignal()

    def __init__(self, menu: Optional[WheelMenu] = None, all_menus: dict = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._menu = menu
        self._all_menus = all_menus or {}

        layout = QVBoxLayout(self)

        # Menu name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Menu Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self.changed)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # Size settings
        size_group = QGroupBox("Size")
        size_layout = QFormLayout(size_group)

        self.inner_radius = QSpinBox()
        self.inner_radius.setRange(20, 200)
        self.inner_radius.valueChanged.connect(self.changed)
        size_layout.addRow("Inner Radius:", self.inner_radius)

        self.outer_radius = QSpinBox()
        self.outer_radius.setRange(50, 400)
        self.outer_radius.valueChanged.connect(self.changed)
        size_layout.addRow("Outer Radius:", self.outer_radius)

        layout.addWidget(size_group)

        # Actions list
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)

        self.actions_list = QListWidget()
        self.actions_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.actions_list.model().rowsMoved.connect(self.changed)
        actions_layout.addWidget(self.actions_list)

        # Action buttons
        action_buttons = QHBoxLayout()

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_action)
        action_buttons.addWidget(add_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_action)
        action_buttons.addWidget(edit_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_action)
        action_buttons.addWidget(remove_btn)

        action_buttons.addStretch()

        move_up_btn = QPushButton("Move Up")
        move_up_btn.clicked.connect(self._move_action_up)
        action_buttons.addWidget(move_up_btn)

        move_down_btn = QPushButton("Move Down")
        move_down_btn.clicked.connect(self._move_action_down)
        action_buttons.addWidget(move_down_btn)

        actions_layout.addLayout(action_buttons)
        layout.addWidget(actions_group)

        if menu:
            self.load_menu(menu)

    def load_menu(self, menu: WheelMenu) -> None:
        self._menu = menu
        self.name_edit.setText(menu.name)
        self.inner_radius.setValue(menu.inner_radius)
        self.outer_radius.setValue(menu.outer_radius)

        self.actions_list.clear()
        for action in menu.actions:
            item = QListWidgetItem(f"{action.name} ({action.action_type.value})")
            item.setData(Qt.ItemDataRole.UserRole, action)
            icon = QIcon.fromTheme(action.icon)
            if not icon.isNull():
                item.setIcon(icon)
            self.actions_list.addItem(item)

    def save_menu(self) -> WheelMenu:
        if self._menu is None:
            self._menu = WheelMenu(
                id=ConfigManager.generate_id(),
                name=self.name_edit.text(),
            )

        self._menu.name = self.name_edit.text()
        self._menu.inner_radius = self.inner_radius.value()
        self._menu.outer_radius = self.outer_radius.value()

        # Get actions from list
        actions = []
        for i in range(self.actions_list.count()):
            item = self.actions_list.item(i)
            action = item.data(Qt.ItemDataRole.UserRole)
            if action:
                actions.append(action)
        self._menu.actions = actions

        return self._menu

    def _add_action(self) -> None:
        dialog = ActionEditor(menus=self._all_menus, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            action = dialog.get_action()
            item = QListWidgetItem(f"{action.name} ({action.action_type.value})")
            item.setData(Qt.ItemDataRole.UserRole, action)
            icon = QIcon.fromTheme(action.icon)
            if not icon.isNull():
                item.setIcon(icon)
            self.actions_list.addItem(item)
            self.changed.emit()

    def _edit_action(self) -> None:
        item = self.actions_list.currentItem()
        if not item:
            return

        action = item.data(Qt.ItemDataRole.UserRole)
        dialog = ActionEditor(action=action, menus=self._all_menus, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_action = dialog.get_action()
            item.setText(f"{new_action.name} ({new_action.action_type.value})")
            item.setData(Qt.ItemDataRole.UserRole, new_action)
            icon = QIcon.fromTheme(new_action.icon)
            if not icon.isNull():
                item.setIcon(icon)
            self.changed.emit()

    def _remove_action(self) -> None:
        row = self.actions_list.currentRow()
        if row >= 0:
            self.actions_list.takeItem(row)
            self.changed.emit()

    def _move_action_up(self) -> None:
        row = self.actions_list.currentRow()
        if row > 0:
            item = self.actions_list.takeItem(row)
            self.actions_list.insertItem(row - 1, item)
            self.actions_list.setCurrentRow(row - 1)
            self.changed.emit()

    def _move_action_down(self) -> None:
        row = self.actions_list.currentRow()
        if row < self.actions_list.count() - 1:
            item = self.actions_list.takeItem(row)
            self.actions_list.insertItem(row + 1, item)
            self.actions_list.setCurrentRow(row + 1)
            self.changed.emit()


class WindowRuleEditor(QDialog):
    """Dialog for editing a window rule."""

    def __init__(self, rule: Optional[WindowRule] = None, menus: dict = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._rule = rule
        self._menus = menus or {}

        self.setWindowTitle("Edit Window Rule" if rule else "New Window Rule")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Name
        self.name_edit = QLineEdit()
        if rule:
            self.name_edit.setText(rule.name)
        form.addRow("Name:", self.name_edit)

        # Window class
        self.class_edit = QLineEdit()
        self.class_edit.setPlaceholderText("e.g., firefox, code, dolphin")
        if rule:
            self.class_edit.setText(rule.window_class)
        form.addRow("Window Class:", self.class_edit)

        self.class_regex = QCheckBox("Use regex")
        if rule:
            self.class_regex.setChecked(rule.window_class_regex)
        form.addRow("", self.class_regex)

        # Window title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g., Visual Studio Code")
        if rule:
            self.title_edit.setText(rule.window_title)
        form.addRow("Window Title:", self.title_edit)

        self.title_regex = QCheckBox("Use regex")
        if rule:
            self.title_regex.setChecked(rule.window_title_regex)
        form.addRow("", self.title_regex)

        # Menu to show
        self.menu_combo = QComboBox()
        for menu_id, menu in self._menus.items():
            self.menu_combo.addItem(menu.name, menu_id)
        if rule and rule.menu_id:
            idx = self.menu_combo.findData(rule.menu_id)
            if idx >= 0:
                self.menu_combo.setCurrentIndex(idx)
        form.addRow("Menu:", self.menu_combo)

        # Priority
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(0, 100)
        if rule:
            self.priority_spin.setValue(rule.priority)
        form.addRow("Priority:", self.priority_spin)

        layout.addLayout(form)

        # Help text
        help_label = QLabel(
            "Higher priority rules are checked first.\n"
            "Both class and title must match if specified."
        )
        help_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(help_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_rule(self) -> WindowRule:
        rule_id = self._rule.id if self._rule else ConfigManager.generate_id()

        return WindowRule(
            id=rule_id,
            name=self.name_edit.text(),
            window_class=self.class_edit.text(),
            window_title=self.title_edit.text(),
            window_class_regex=self.class_regex.isChecked(),
            window_title_regex=self.title_regex.isChecked(),
            menu_id=self.menu_combo.currentData(),
            priority=self.priority_spin.value(),
        )


class ConfigWindow(QMainWindow):
    """Main configuration window."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        super().__init__()

        self._config_manager = config_manager or ConfigManager()
        self._config = self._config_manager.load()
        self._unsaved_changes = False

        self.setWindowTitle("KDE LogiWheel Settings")
        self.setMinimumSize(900, 600)

        # Central widget with tabs
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Create tabs
        self._create_triggers_tab()
        self._create_menus_tab()
        self._create_window_rules_tab()
        self._create_appearance_tab()
        self._create_about_tab()

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._apply_changes)
        button_layout.addWidget(self.apply_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_changes)
        button_layout.addWidget(self.save_btn)

        button_layout.addStretch()

        self.reload_btn = QPushButton("Reload from Disk")
        self.reload_btn.clicked.connect(self._reload_config)
        button_layout.addWidget(self.reload_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        # Load data
        self._load_config()

    def _create_triggers_tab(self) -> None:
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Left: trigger list
        left = QVBoxLayout()
        left.addWidget(QLabel("Triggers:"))

        self.triggers_list = QListWidget()
        self.triggers_list.currentRowChanged.connect(self._on_trigger_selected)
        left.addWidget(self.triggers_list)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_trigger)
        btn_layout.addWidget(add_btn)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_trigger)
        btn_layout.addWidget(remove_btn)
        left.addLayout(btn_layout)

        layout.addLayout(left, 1)

        # Right: trigger editor
        self.trigger_editor = TriggerEditor()
        self.trigger_editor.changed.connect(self._mark_unsaved)
        layout.addWidget(self.trigger_editor, 2)

        self.tabs.addTab(widget, "Triggers")

    def _create_menus_tab(self) -> None:
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Left: menu list
        left = QVBoxLayout()
        left.addWidget(QLabel("Menus:"))

        self.menus_list = QListWidget()
        self.menus_list.currentRowChanged.connect(self._on_menu_selected)
        left.addWidget(self.menus_list)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_menu)
        btn_layout.addWidget(add_btn)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_menu)
        btn_layout.addWidget(remove_btn)
        left.addLayout(btn_layout)

        # Default menu selector
        left.addWidget(QLabel("Default Menu:"))
        self.default_menu_combo = QComboBox()
        self.default_menu_combo.currentIndexChanged.connect(self._mark_unsaved)
        left.addWidget(self.default_menu_combo)

        layout.addLayout(left, 1)

        # Right: menu editor
        self.menu_editor = MenuEditor()
        self.menu_editor.changed.connect(self._mark_unsaved)
        layout.addWidget(self.menu_editor, 2)

        self.tabs.addTab(widget, "Menus")

    def _create_window_rules_tab(self) -> None:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Window-specific menus (higher priority rules are checked first):"))

        self.rules_list = QListWidget()
        layout.addWidget(self.rules_list)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Rule")
        add_btn.clicked.connect(self._add_window_rule)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton("Edit Rule")
        edit_btn.clicked.connect(self._edit_window_rule)
        btn_layout.addWidget(edit_btn)
        remove_btn = QPushButton("Remove Rule")
        remove_btn.clicked.connect(self._remove_window_rule)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.tabs.addTab(widget, "Window Rules")

    def _create_appearance_tab(self) -> None:
        widget = QWidget()
        layout = QFormLayout(widget)

        # Animation
        self.animation_spin = QSpinBox()
        self.animation_spin.setRange(0, 1000)
        self.animation_spin.setSuffix(" ms")
        self.animation_spin.valueChanged.connect(self._mark_unsaved)
        layout.addRow("Animation Duration:", self.animation_spin)

        # Opacity
        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setRange(0.1, 1.0)
        self.opacity_spin.setSingleStep(0.05)
        self.opacity_spin.valueChanged.connect(self._mark_unsaved)
        layout.addRow("Wheel Opacity:", self.opacity_spin)

        # Show labels
        self.labels_check = QCheckBox()
        self.labels_check.stateChanged.connect(self._mark_unsaved)
        layout.addRow("Show Labels:", self.labels_check)

        # Icon size
        self.icon_size_spin = QSpinBox()
        self.icon_size_spin.setRange(16, 64)
        self.icon_size_spin.valueChanged.connect(self._mark_unsaved)
        layout.addRow("Icon Size:", self.icon_size_spin)

        # Font size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.valueChanged.connect(self._mark_unsaved)
        layout.addRow("Font Size:", self.font_size_spin)

        # Colors
        layout.addRow(QLabel("Colors:"))

        self.bg_color = ColorButton()
        self.bg_color.color_changed.connect(self._mark_unsaved)
        layout.addRow("Background:", self.bg_color)

        self.hover_color = ColorButton()
        self.hover_color.color_changed.connect(self._mark_unsaved)
        layout.addRow("Hover:", self.hover_color)

        self.text_color = ColorButton()
        self.text_color.color_changed.connect(self._mark_unsaved)
        layout.addRow("Text:", self.text_color)

        self.border_color = ColorButton()
        self.border_color.color_changed.connect(self._mark_unsaved)
        layout.addRow("Border:", self.border_color)

        # Behavior
        layout.addRow(QLabel("Behavior:"))

        self.close_on_action = QCheckBox()
        self.close_on_action.stateChanged.connect(self._mark_unsaved)
        layout.addRow("Close on Action:", self.close_on_action)

        self.deadzone_spin = QSpinBox()
        self.deadzone_spin.setRange(10, 100)
        self.deadzone_spin.valueChanged.connect(self._mark_unsaved)
        layout.addRow("Center Deadzone:", self.deadzone_spin)

        self.tabs.addTab(widget, "Appearance")

    def _create_about_tab(self) -> None:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("KDE LogiWheel")
        title.setFont(QFont("", 18, QFont.Weight.Bold))
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        version = QLabel("Version 1.0.0")
        layout.addWidget(version, alignment=Qt.AlignmentFlag.AlignCenter)

        desc = QLabel(
            "A Logitech-style shortcut wheel for KDE.\n\n"
            "Configure triggers, create nested menus,\n"
            "and set window-specific actions."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(20)

        info = QLabel(
            "Usage:\n"
            "1. Configure triggers (keyboard or mouse button)\n"
            "2. Create menus with your desired actions\n"
            "3. Optionally set window-specific menus\n"
            "4. Start the daemon: kde-logiwheel-daemon"
        )
        layout.addWidget(info)

        self.tabs.addTab(widget, "About")

    def _load_config(self) -> None:
        """Load configuration into UI."""
        # Load triggers
        self.triggers_list.clear()
        for trigger in self._config.triggers:
            self.triggers_list.addItem(trigger.name)

        # Load menus
        profile = self._config_manager.get_active_profile()
        if profile:
            self.menus_list.clear()
            self.default_menu_combo.clear()

            for menu_id, menu in profile.menus.items():
                self.menus_list.addItem(menu.name)
                self.menus_list.item(self.menus_list.count() - 1).setData(
                    Qt.ItemDataRole.UserRole, menu_id
                )
                self.default_menu_combo.addItem(menu.name, menu_id)

            # Set default menu
            if profile.default_menu_id:
                idx = self.default_menu_combo.findData(profile.default_menu_id)
                if idx >= 0:
                    self.default_menu_combo.setCurrentIndex(idx)

            # Load window rules
            self.rules_list.clear()
            for rule in profile.window_rules:
                item_text = f"{rule.name}: {rule.window_class or rule.window_title} → {rule.menu_id}"
                self.rules_list.addItem(item_text)
                self.rules_list.item(self.rules_list.count() - 1).setData(
                    Qt.ItemDataRole.UserRole, rule
                )

        # Load appearance
        self.animation_spin.setValue(self._config.animation_duration_ms)
        self.opacity_spin.setValue(self._config.wheel_opacity)
        self.labels_check.setChecked(self._config.show_labels)
        self.icon_size_spin.setValue(self._config.icon_size)
        self.font_size_spin.setValue(self._config.font_size)
        self.bg_color.set_color(self._config.background_color)
        self.hover_color.set_color(self._config.hover_color)
        self.text_color.set_color(self._config.text_color)
        self.border_color.set_color(self._config.border_color)
        self.close_on_action.setChecked(self._config.close_on_action)
        self.deadzone_spin.setValue(self._config.center_deadzone_radius)

        self._unsaved_changes = False

    def _save_config(self) -> None:
        """Save UI state to config."""
        # Save appearance settings
        self._config.animation_duration_ms = self.animation_spin.value()
        self._config.wheel_opacity = self.opacity_spin.value()
        self._config.show_labels = self.labels_check.isChecked()
        self._config.icon_size = self.icon_size_spin.value()
        self._config.font_size = self.font_size_spin.value()
        self._config.background_color = self.bg_color.get_color()
        self._config.hover_color = self.hover_color.get_color()
        self._config.text_color = self.text_color.get_color()
        self._config.border_color = self.border_color.get_color()
        self._config.close_on_action = self.close_on_action.isChecked()
        self._config.center_deadzone_radius = self.deadzone_spin.value()

        # Save triggers
        # (triggers are saved when edited)

        # Save profile default menu
        profile = self._config_manager.get_active_profile()
        if profile:
            profile.default_menu_id = self.default_menu_combo.currentData()

    def _on_trigger_selected(self, row: int) -> None:
        if 0 <= row < len(self._config.triggers):
            self.trigger_editor.load_trigger(self._config.triggers[row])

    def _add_trigger(self) -> None:
        trigger = TriggerConfig(
            id=ConfigManager.generate_id(),
            name="New Trigger",
        )
        self._config.triggers.append(trigger)
        self.triggers_list.addItem(trigger.name)
        self.triggers_list.setCurrentRow(self.triggers_list.count() - 1)
        self._mark_unsaved()

    def _remove_trigger(self) -> None:
        row = self.triggers_list.currentRow()
        if 0 <= row < len(self._config.triggers):
            self._config.triggers.pop(row)
            self.triggers_list.takeItem(row)
            self._mark_unsaved()

    def _on_menu_selected(self, row: int) -> None:
        if row < 0:
            return

        profile = self._config_manager.get_active_profile()
        if not profile:
            return

        item = self.menus_list.item(row)
        if item:
            menu_id = item.data(Qt.ItemDataRole.UserRole)
            if menu_id in profile.menus:
                self.menu_editor.load_menu(profile.menus[menu_id])
                self.menu_editor._all_menus = profile.menus

    def _add_menu(self) -> None:
        profile = self._config_manager.get_active_profile()
        if not profile:
            return

        menu = WheelMenu(
            id=ConfigManager.generate_id(),
            name="New Menu",
        )
        profile.menus[menu.id] = menu

        self.menus_list.addItem(menu.name)
        self.menus_list.item(self.menus_list.count() - 1).setData(
            Qt.ItemDataRole.UserRole, menu.id
        )
        self.default_menu_combo.addItem(menu.name, menu.id)
        self.menus_list.setCurrentRow(self.menus_list.count() - 1)
        self._mark_unsaved()

    def _remove_menu(self) -> None:
        row = self.menus_list.currentRow()
        if row < 0:
            return

        profile = self._config_manager.get_active_profile()
        if not profile:
            return

        item = self.menus_list.item(row)
        if item:
            menu_id = item.data(Qt.ItemDataRole.UserRole)
            if menu_id in profile.menus:
                del profile.menus[menu_id]
                self.menus_list.takeItem(row)

                # Update default menu combo
                idx = self.default_menu_combo.findData(menu_id)
                if idx >= 0:
                    self.default_menu_combo.removeItem(idx)

                self._mark_unsaved()

    def _add_window_rule(self) -> None:
        profile = self._config_manager.get_active_profile()
        if not profile:
            return

        dialog = WindowRuleEditor(menus=profile.menus, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            rule = dialog.get_rule()
            profile.window_rules.append(rule)

            item_text = f"{rule.name}: {rule.window_class or rule.window_title} → {rule.menu_id}"
            self.rules_list.addItem(item_text)
            self.rules_list.item(self.rules_list.count() - 1).setData(
                Qt.ItemDataRole.UserRole, rule
            )
            self._mark_unsaved()

    def _edit_window_rule(self) -> None:
        row = self.rules_list.currentRow()
        if row < 0:
            return

        profile = self._config_manager.get_active_profile()
        if not profile:
            return

        item = self.rules_list.item(row)
        rule = item.data(Qt.ItemDataRole.UserRole)

        dialog = WindowRuleEditor(rule=rule, menus=profile.menus, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_rule = dialog.get_rule()
            profile.window_rules[row] = new_rule

            item_text = f"{new_rule.name}: {new_rule.window_class or new_rule.window_title} → {new_rule.menu_id}"
            item.setText(item_text)
            item.setData(Qt.ItemDataRole.UserRole, new_rule)
            self._mark_unsaved()

    def _remove_window_rule(self) -> None:
        row = self.rules_list.currentRow()
        if row < 0:
            return

        profile = self._config_manager.get_active_profile()
        if not profile:
            return

        profile.window_rules.pop(row)
        self.rules_list.takeItem(row)
        self._mark_unsaved()

    def _mark_unsaved(self) -> None:
        self._unsaved_changes = True
        self.setWindowTitle("KDE LogiWheel Settings *")

    def _apply_changes(self) -> None:
        """Apply changes without saving to disk."""
        # Save current trigger
        if self.triggers_list.currentRow() >= 0:
            trigger = self.trigger_editor.save_trigger()
            self._config.triggers[self.triggers_list.currentRow()] = trigger
            self.triggers_list.currentItem().setText(trigger.name)

        # Save current menu
        if self.menus_list.currentRow() >= 0:
            profile = self._config_manager.get_active_profile()
            if profile:
                menu = self.menu_editor.save_menu()
                profile.menus[menu.id] = menu
                self.menus_list.currentItem().setText(menu.name)

        self._save_config()

        # Notify daemon to reload
        try:
            import dbus
            bus = dbus.SessionBus()
            obj = bus.get_object("org.kde.LogiWheel", "/org/kde/LogiWheel")
            interface = dbus.Interface(obj, "org.kde.LogiWheel")
            interface.ReloadConfig()
        except Exception:
            pass

    def _save_changes(self) -> None:
        """Apply and save changes to disk."""
        self._apply_changes()
        self._config_manager.save(self._config)
        self._unsaved_changes = False
        self.setWindowTitle("KDE LogiWheel Settings")
        QMessageBox.information(self, "Saved", "Configuration saved successfully.")

    def _reload_config(self) -> None:
        """Reload configuration from disk."""
        if self._unsaved_changes:
            result = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Reload anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if result != QMessageBox.StandardButton.Yes:
                return

        self._config = self._config_manager.reload()
        self._load_config()

    def closeEvent(self, event) -> None:
        if self._unsaved_changes:
            result = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Save changes before closing?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel
            )
            if result == QMessageBox.StandardButton.Yes:
                self._save_changes()
            elif result == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()


def main():
    """Main entry point for the config UI."""
    app = QApplication(sys.argv)
    app.setApplicationName("KDE-LogiWheel Settings")

    window = ConfigWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
