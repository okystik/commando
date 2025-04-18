import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTabWidget,
                             QMessageBox, QAbstractItemView, QPushButton, QHeaderView)
from PyQt6.QtCore import Qt, QTimer, QDir, QSettings
from PyQt6.QtGui import QIcon
from treeview import CustomTreeViewWithDrag
from settings_panel import create_colored_icon  # Импортируем функцию для цветных иконок

class NavigationBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)  # Убираем отступы

        # Верхняя панель с кнопками, адресной строкой и поиском
        self.top_layout = QHBoxLayout()
        self.top_layout.setContentsMargins(5, 5, 5, 5)  # Небольшие отступы для красоты
        self.top_layout.setSpacing(5)  # Расстояние между элементами

        # Настройки для иконок
        self.settings = QSettings("MyFileManager", "Settings")

        # Кнопки навигации
        self.back_button = QPushButton()
        self.back_button.setFixedSize(30, 30)
        self.load_back_icon()  # Загружаем иконку для кнопки "Назад"
        self.back_button.clicked.connect(lambda: self.parent.go_back(self.current_file_view()) if self.current_file_view() else None)

        self.forward_button = QPushButton()
        self.forward_button.setFixedSize(30, 30)
        self.load_forward_icon()  # Загружаем иконку для кнопки "Вперед"
        self.forward_button.clicked.connect(lambda: self.parent.go_forward(self.current_file_view()) if self.current_file_view() else None)

        self.up_button = QPushButton()
        self.up_button.setFixedSize(30, 30)
        self.load_up_icon()  # Загружаем иконку для кнопки "На слой выше"
        self.up_button.clicked.connect(lambda: self.parent.go_up(self.current_file_view()) if self.current_file_view() else None)

        # Адресная строка
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Введите путь...")
        self.path_edit.returnPressed.connect(self.on_path_entered)

        # Строка поиска
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск (Enter для поиска)...")
        self.search_edit.setFixedWidth(200)  # Фиксированная ширина 200 пикселей
        self.search_edit.returnPressed.connect(self.parent.perform_search)
        self.search_edit.textChanged.connect(self.on_search_text_changed)

        # Добавляем элементы в верхнюю панель
        self.top_layout.addWidget(self.back_button)
        self.top_layout.addWidget(self.forward_button)
        self.top_layout.addWidget(self.up_button)
        self.top_layout.addWidget(self.path_edit, 1)  # Растягиваем адресную строку
        self.top_layout.addWidget(self.search_edit)  # Поиск фиксированной ширины

        self.layout.addLayout(self.top_layout)

        # Вкладки
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.tab_widget.tabBarDoubleClicked.connect(self.duplicate_tab)
        self.layout.addWidget(self.tab_widget, 1)  # Растягиваем вкладки по высоте

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.parent.perform_search)

        self.update_style()

    def load_back_icon(self):
        back_icon_path = self.settings.value("icon_back", "img/back.svg", type=str)
        back_icon_path = os.path.abspath(back_icon_path)
        back_icon_color = self.settings.value("back_icon_color", "#FFFFFF", type=str)
        if os.path.exists(back_icon_path) and os.access(back_icon_path, os.R_OK):
            icon = create_colored_icon(back_icon_path, back_icon_color)
            self.back_button.setIcon(icon)
        else:
            self.back_button.setIcon(QIcon.fromTheme("go-previous"))

    def load_forward_icon(self):
        forward_icon_path = self.settings.value("icon_forward", "img/forward.svg", type=str)
        forward_icon_path = os.path.abspath(forward_icon_path)
        forward_icon_color = self.settings.value("forward_icon_color", "#FFFFFF", type=str)
        if os.path.exists(forward_icon_path) and os.access(forward_icon_path, os.R_OK):
            icon = create_colored_icon(forward_icon_path, forward_icon_color)
            self.forward_button.setIcon(icon)
        else:
            self.forward_button.setIcon(QIcon.fromTheme("go-next"))

    def load_up_icon(self):
        up_icon_path = self.settings.value("icon_up", "img/up.svg", type=str)
        up_icon_path = os.path.abspath(up_icon_path)
        up_icon_color = self.settings.value("up_icon_color", "#FFFFFF", type=str)
        if os.path.exists(up_icon_path) and os.access(up_icon_path, os.R_OK):
            icon = create_colored_icon(up_icon_path, up_icon_color)
            self.up_button.setIcon(icon)
        else:
            self.up_button.setIcon(QIcon.fromTheme("go-up"))

    def update_style(self):
        settings = QSettings("MyFileManager", "Settings")
        bg_color = settings.value("work_zones_bg_color", "#121314", type=str)
        active_tab_color = settings.value("active_tab_color", "#00d158", type=str)
        self.setStyleSheet(f"""
            QWidget {{
                background: transparent;  /* Avoid setting a background that overrides QTreeView */
            }}
            QTabWidget::pane {{
                background: transparent;
                border: none;
            }}
            QTabBar::tab {{
                background-color: #3A3A3A;
                color: #FFFFFF;
                padding: 6px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            QTabBar::tab:selected {{
                background-color: {active_tab_color};
            }}
            QLineEdit {{
                background-color: #3A3A3A;
                color: #FFFFFF;
                border: 1px solid #4A4A4A;
                padding: 2px;
            }}
            QPushButton {{
                background-color: #3A3A3A;
                border: none;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: #4A4A4A;
            }}
        """)

    def duplicate_tab(self, index):
        file_view = self.tab_widget.widget(index).findChild(CustomTreeViewWithDrag)
        if file_view:
            current_path = file_view.history[-1] if file_view.history else QDir.homePath()
            self.add_new_tab(current_path)

    def on_tab_changed(self):
        self.parent.set_active_zone(1 if self is self.parent.navigation_bar1 else 2)
        self.update_path_edit(self.current_file_view())

    def on_search_text_changed(self):
        if self.search_edit.text().strip():
            self.search_timer.start(3000)
        else:
            self.search_timer.stop()
            if self.parent.search_performed and self.parent.path_before_search:
                file_view = self.current_file_view()
                if file_view and isinstance(file_view.model(), self.parent.SearchModel):
                    self.parent.navigate_to(file_view, self.parent.path_before_search)
                    self.parent.search_performed = False
                    self.parent.path_before_search = None

    def on_path_entered(self):
        path = self.path_edit.text().strip()
        if os.path.exists(path) and os.path.isdir(path):
            file_view = self.current_file_view()
            if file_view:
                self.parent.navigate_to(file_view, path)
        else:
            QMessageBox.warning(self.parent, "Ошибка", f"Путь не существует или не является директорией: {path}")

    def add_new_tab(self, path):
        if not os.path.exists(path):
            path = QDir.homePath()
        work_area = QWidget()
        work_layout = QVBoxLayout(work_area)
        work_layout.setContentsMargins(0, 0, 0, 0)  # Убираем отступы

        file_view = CustomTreeViewWithDrag(self.parent)
        file_view.history = [path]
        file_view.current_index = 0

        work_layout.addWidget(file_view)

        file_view.doubleClicked.connect(lambda index: self.parent.on_double_click(file_view, index))

        tab_index = self.tab_widget.addTab(work_area, os.path.basename(path) or "Root")
        self.tab_widget.setCurrentIndex(tab_index)

        self.parent.navigate_to(file_view, path)
        self.parent.restore_column_state(file_view)
        self.update_path_edit(file_view)

    def close_tab(self, index):
        self.tab_widget.removeTab(index)
        if self.tab_widget.count() == 0:
            self.add_new_tab(QDir.homePath())
        self.update_path_edit(self.current_file_view())

    def current_file_view(self):
        current_widget = self.tab_widget.currentWidget()
        if current_widget:
            return current_widget.findChild(CustomTreeViewWithDrag)
        return None

    def update_path_edit(self, file_view):
        if file_view:
            current_path = file_view.history[-1] if file_view.history else ""
            self.path_edit.setText(current_path)
        else:
            self.path_edit.setText("")
