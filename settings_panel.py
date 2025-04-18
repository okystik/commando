from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
                             QSpinBox, QCheckBox, QFileDialog, QColorDialog, QFormLayout,
                             QTabWidget, QWidget, QHeaderView)
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtCore import QSettings, Qt  # Added Qt import
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QImage, QPainter, QPixmap, QIconEngine
import os
from treeview import CustomTreeViewWithDrag
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Класс для кастомного движка иконок (перемещаем сюда из quick_access.py для использования в предпросмотре)
class ColoredSvgIconEngine(QIconEngine):
    def __init__(self, svg_path, color):
        super().__init__()
        self.svg_path = svg_path
        self.color = QColor(color)

    def pixmap(self, size, mode, state):
        # Создаем пустое изображение
        image = QImage(size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)

        # Рендерим SVG
        renderer = QSvgRenderer(self.svg_path)
        if not renderer.isValid():
            logging.error(f"Invalid SVG file: {self.svg_path}")
            return QPixmap()  # Возвращаем пустой QPixmap в случае ошибки

        painter = QPainter(image)
        renderer.render(painter)

        # Применяем цвет
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(image.rect(), self.color)
        painter.end()

        # Преобразуем QImage в QPixmap
        pixmap = QPixmap.fromImage(image)
        return pixmap

# Функция для создания иконки с заданным цветом
def create_colored_icon(icon_path, color):
    if not os.path.exists(icon_path):
        logging.error(f"Icon file does not exist: {icon_path}")
        return QIcon()

    # Проверяем, является ли файл SVG
    if icon_path.lower().endswith('.svg'):
        engine = ColoredSvgIconEngine(icon_path, color)
        icon = QIcon(engine)
        return icon
    else:
        logging.warning(f"Cannot change color of non-SVG icon: {icon_path}. Using original icon.")
        return QIcon(icon_path)

class SettingsPanel(QDialog):
    def __init__(self, file_manager, quick_access_panel, parent=None):
        super().__init__(parent)
        self.file_manager = file_manager
        self.quick_access_panel = quick_access_panel
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(400)

        self.settings = QSettings("MyFileManager", "Settings")

        self.tabs = QTabWidget()
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.tabs)

        # Вкладка "Общее"
        self.general_tab = self.create_general_tab()
        self.tabs.addTab(self.general_tab, "Общее")

        # Вкладка "Кастомизация" (новая)
        self.customization_tab = self.create_customization_tab()
        self.tabs.addTab(self.customization_tab, "Кастомизация")

        # Вкладка "Быстрый доступ"
        self.quick_access_tab = self.create_quick_access_tab()
        self.tabs.addTab(self.quick_access_tab, "Быстрый доступ")

        # Вкладка "Рабочие зоны"
        self.work_zones_tab = self.create_work_zones_tab()
        self.tabs.addTab(self.work_zones_tab, "Рабочие зоны")

        # Кнопки "Сохранить" и "Отмена"
        self.button_layout = QHBoxLayout()
        self.save_button = QPushButton("Сохранить")
        self.cancel_button = QPushButton("Отмена")
        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button.clicked.connect(self.reject)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_layout)

        self.load_settings()

    def create_general_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        # Скрывать скрытые файлы
        self.hide_hidden_files = QCheckBox("Скрывать скрытые файлы")
        layout.addRow(self.hide_hidden_files)

        return widget

    def create_customization_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        # Иконка приложения
        self.app_icon_path = QLineEdit()
        self.app_icon_button = QPushButton("Выбрать иконку приложения")
        self.app_icon_button.clicked.connect(self.choose_app_icon)
        layout.addRow("Иконка приложения:", self.app_icon_path)
        layout.addWidget(self.app_icon_button)

        # Иконка кнопки настроек
        self.settings_icon_path = QLineEdit()
        self.settings_icon_button = QPushButton("Выбрать иконку настроек")
        self.settings_icon_button.clicked.connect(self.choose_settings_icon)
        self.settings_icon_preview = QPushButton()
        self.settings_icon_preview.setFixedSize(30, 30)
        self.settings_icon_preview.setEnabled(False)  # Кнопка только для предпросмотра
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(self.settings_icon_path)
        settings_layout.addWidget(self.settings_icon_preview)
        layout.addRow("Иконка кнопки настроек:", settings_layout)
        layout.addWidget(self.settings_icon_button)

        # Цвет иконки кнопки настроек
        self.settings_icon_color = QLineEdit()
        self.settings_icon_color_button = QPushButton("Выбрать цвет иконки настроек")
        self.settings_icon_color_button.clicked.connect(self.choose_settings_icon_color)
        self.settings_icon_color.textChanged.connect(self.update_settings_icon_preview)
        layout.addRow("Цвет иконки настроек:", self.settings_icon_color)
        layout.addWidget(self.settings_icon_color_button)

        # Иконка кнопки переключения зон (включено)
        self.toggle_zone_on_icon_path = QLineEdit()
        self.toggle_zone_on_icon_button = QPushButton("Выбрать иконку (вкл)")
        self.toggle_zone_on_icon_button.clicked.connect(self.choose_toggle_zone_on_icon)
        self.toggle_zone_on_icon_preview = QPushButton()
        self.toggle_zone_on_icon_preview.setFixedSize(30, 30)
        self.toggle_zone_on_icon_preview.setEnabled(False)
        toggle_on_layout = QHBoxLayout()
        toggle_on_layout.addWidget(self.toggle_zone_on_icon_path)
        toggle_on_layout.addWidget(self.toggle_zone_on_icon_preview)
        layout.addRow("Иконка переключения зон (вкл):", toggle_on_layout)
        layout.addWidget(self.toggle_zone_on_icon_button)

        # Иконка кнопки переключения зон (выключено)
        self.toggle_zone_off_icon_path = QLineEdit()
        self.toggle_zone_off_icon_button = QPushButton("Выбрать иконку (выкл)")
        self.toggle_zone_off_icon_button.clicked.connect(self.choose_toggle_zone_off_icon)
        self.toggle_zone_off_icon_preview = QPushButton()
        self.toggle_zone_off_icon_preview.setFixedSize(30, 30)
        self.toggle_zone_off_icon_preview.setEnabled(False)
        toggle_off_layout = QHBoxLayout()
        toggle_off_layout.addWidget(self.toggle_zone_off_icon_path)
        toggle_off_layout.addWidget(self.toggle_zone_off_icon_preview)
        layout.addRow("Иконка переключения зон (выкл):", toggle_off_layout)
        layout.addWidget(self.toggle_zone_off_icon_button)

        # Цвет иконки кнопки переключения зон
        self.toggle_zone_icon_color = QLineEdit()
        self.toggle_zone_icon_color_button = QPushButton("Выбрать цвет иконки переключения зон")
        self.toggle_zone_icon_color_button.clicked.connect(self.choose_toggle_zone_icon_color)
        self.toggle_zone_icon_color.textChanged.connect(self.update_toggle_zone_icon_preview)
        layout.addRow("Цвет иконки переключения зон:", self.toggle_zone_icon_color)
        layout.addWidget(self.toggle_zone_icon_color_button)

        # Иконка кнопки корзины
        self.trash_icon_path = QLineEdit()
        self.trash_icon_button = QPushButton("Выбрать иконку корзины")
        self.trash_icon_button.clicked.connect(self.choose_trash_icon)
        self.trash_icon_preview = QPushButton()
        self.trash_icon_preview.setFixedSize(30, 30)
        self.trash_icon_preview.setEnabled(False)
        trash_layout = QHBoxLayout()
        trash_layout.addWidget(self.trash_icon_path)
        trash_layout.addWidget(self.trash_icon_preview)
        layout.addRow("Иконка кнопки корзины:", trash_layout)
        layout.addWidget(self.trash_icon_button)

        # Цвет иконки кнопки корзины
        self.trash_icon_color = QLineEdit()
        self.trash_icon_color_button = QPushButton("Выбрать цвет иконки корзины")
        self.trash_icon_color_button.clicked.connect(self.choose_trash_icon_color)
        self.trash_icon_color.textChanged.connect(self.update_trash_icon_preview)
        layout.addRow("Цвет иконки корзины:", self.trash_icon_color)
        layout.addWidget(self.trash_icon_color_button)

        # Цвет фона быстрого доступа (переносим из вкладки "Быстрый доступ")
        self.qa_bg_color = QLineEdit()
        self.qa_bg_color_button = QPushButton("Выбрать цвет фона")
        self.qa_bg_color_button.clicked.connect(self.choose_qa_bg_color)
        layout.addRow("Цвет фона быстрого доступа:", self.qa_bg_color)
        layout.addWidget(self.qa_bg_color_button)

        # Альтернативный цвет фона быстрого доступа (переносим из вкладки "Быстрый доступ")
        self.qa_alt_bg_color = QLineEdit()
        self.qa_alt_bg_color_button = QPushButton("Выбрать альт. цвет фона")
        self.qa_alt_bg_color_button.clicked.connect(self.choose_qa_alt_bg_color)
        layout.addRow("Альт. цвет фона быстрого доступа:", self.qa_alt_bg_color)
        layout.addWidget(self.qa_alt_bg_color_button)

        # Цвет фона рабочих зон (переносим из вкладки "Рабочие зоны")
        self.work_zones_bg_color = QLineEdit()
        self.work_zones_bg_color_button = QPushButton("Выбрать цвет фона")
        self.work_zones_bg_color_button.clicked.connect(self.choose_work_zones_bg_color)
        layout.addRow("Цвет фона рабочих зон:", self.work_zones_bg_color)
        layout.addWidget(self.work_zones_bg_color_button)

        # Цвет активной вкладки (новая настройка)
        self.active_tab_color = QLineEdit()
        self.active_tab_color_button = QPushButton("Выбрать цвет активной вкладки")
        self.active_tab_color_button.clicked.connect(self.choose_active_tab_color)
        layout.addRow("Цвет активной вкладки:", self.active_tab_color)
        layout.addWidget(self.active_tab_color_button)

        return widget

    def create_quick_access_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        # Размер шрифта
        self.qa_font_size = QSpinBox()
        self.qa_font_size.setRange(6, 20)
        layout.addRow("Размер шрифта:", self.qa_font_size)

        # Высота строки
        self.qa_row_height = QSpinBox()
        self.qa_row_height.setRange(10, 50)
        layout.addRow("Высота строки:", self.qa_row_height)

        return widget

    def create_work_zones_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        # Размер шрифта рабочей зоны
        self.work_zones_font_size = QSpinBox()
        self.work_zones_font_size.setRange(6, 20)
        layout.addRow("Размер шрифта рабочей зоны:", self.work_zones_font_size)

        # Высота строки рабочей зоны
        self.work_zones_row_height = QSpinBox()
        self.work_zones_row_height.setRange(10, 50)
        layout.addRow("Высота строки рабочей зоны:", self.work_zones_row_height)

        return widget

    def load_settings(self):
        # Загрузка настроек для вкладки "Общее"
        self.hide_hidden_files.setChecked(self.settings.value("hide_hidden_files", False, type=bool))

        # Загрузка настроек для вкладки "Кастомизация"
        self.app_icon_path.setText(self.settings.value("icon_appicon", "", type=str))
        self.settings_icon_path.setText(self.settings.value("icon_settings", "img/settings.svg", type=str))
        self.settings_icon_color.setText(self.settings.value("settings_icon_color", "#FFFFFF", type=str))
        self.toggle_zone_on_icon_path.setText(self.settings.value("icon_togglezoneon", "img/toggle_zone_on.svg", type=str))
        self.toggle_zone_off_icon_path.setText(self.settings.value("icon_togglezoneoff", "img/toggle_zone_off.svg", type=str))
        self.toggle_zone_icon_color.setText(self.settings.value("toggle_zone_icon_color", "#FFFFFF", type=str))
        self.trash_icon_path.setText(self.settings.value("icon_trash", "img/trash.svg", type=str))
        self.trash_icon_color.setText(self.settings.value("trash_icon_color", "#FF0000", type=str))
        self.qa_bg_color.setText(self.settings.value("quick_access_bg_color", "#2E2E2E", type=str))
        self.qa_alt_bg_color.setText(self.settings.value("quick_access_alt_bg_color", "#353535", type=str))
        self.work_zones_bg_color.setText(self.settings.value("work_zones_bg_color", "#2E2E2E", type=str))
        self.active_tab_color.setText(self.settings.value("active_tab_color", "#4A4A4A", type=str))

        # Загрузка настроек для вкладки "Быстрый доступ"
        self.qa_font_size.setValue(int(self.settings.value("quick_access_font_size", "9", type=str)))
        self.qa_row_height.setValue(int(self.settings.value("quick_access_row_height", "22", type=str)))

        # Загрузка настроек для вкладки "Рабочие зоны"
        self.work_zones_font_size.setValue(int(self.settings.value("work_zones_font_size", "9", type=str)))
        self.work_zones_row_height.setValue(int(self.settings.value("work_zones_row_height", "22", type=str)))

        # Обновляем предпросмотр иконок
        self.update_settings_icon_preview()
        self.update_toggle_zone_icon_preview()
        self.update_trash_icon_preview()

    def save_settings(self):
        # Сохранение настроек для вкладки "Общее"
        self.settings.setValue("hide_hidden_files", self.hide_hidden_files.isChecked())

        # Сохранение настроек для вкладки "Кастомизация"
        self.settings.setValue("icon_appicon", self.app_icon_path.text())
        self.settings.setValue("icon_settings", self.settings_icon_path.text())
        self.settings.setValue("settings_icon_color", self.settings_icon_color.text())
        self.settings.setValue("icon_togglezoneon", self.toggle_zone_on_icon_path.text())
        self.settings.setValue("icon_togglezoneoff", self.toggle_zone_off_icon_path.text())
        self.settings.setValue("toggle_zone_icon_color", self.toggle_zone_icon_color.text())
        self.settings.setValue("icon_trash", self.trash_icon_path.text())
        self.settings.setValue("trash_icon_color", self.trash_icon_color.text())
        self.settings.setValue("quick_access_bg_color", self.qa_bg_color.text())
        self.settings.setValue("quick_access_alt_bg_color", self.qa_alt_bg_color.text())
        self.settings.setValue("work_zones_bg_color", self.work_zones_bg_color.text())
        self.settings.setValue("active_tab_color", self.active_tab_color.text())

        # Сохранение настроек для вкладки "Быстрый доступ"
        self.settings.setValue("quick_access_font_size", str(self.qa_font_size.value()))
        self.settings.setValue("quick_access_row_height", str(self.qa_row_height.value()))

        # Сохранение настроек для вкладки "Рабочие зоны"
        self.settings.setValue("work_zones_font_size", str(self.work_zones_font_size.value()))
        self.settings.setValue("work_zones_row_height", str(self.work_zones_row_height.value()))

        self.settings.sync()

        # Обновление стилей
        self.file_manager.update_work_zones_style()
        self.quick_access_panel.update_style()

        # Обновление иконки приложения
        self.file_manager.load_icon_settings()

        # Обновление представлений
        for nav_bar in [self.file_manager.navigation_bar1, self.file_manager.navigation_bar2]:
            if nav_bar:
                nav_bar.update_style()  # Добавляем метод update_style для обновления стиля вкладок
                for i in range(nav_bar.tab_widget.count()):
                    file_view = nav_bar.tab_widget.widget(i).findChild(CustomTreeViewWithDrag)
                    if file_view:
                        self.file_manager.refresh_view(file_view)

        self.accept()

    def update_settings_icon_preview(self):
        icon_path = self.settings_icon_path.text()
        color = self.settings_icon_color.text()
        if icon_path and os.path.exists(icon_path):
            icon = create_colored_icon(icon_path, color)
            self.settings_icon_preview.setIcon(icon)
        else:
            self.settings_icon_preview.setIcon(QIcon())

    def update_toggle_zone_icon_preview(self):
        # Обновляем предпросмотр для обеих иконок (вкл и выкл)
        on_icon_path = self.toggle_zone_on_icon_path.text()
        off_icon_path = self.toggle_zone_off_icon_path.text()
        color = self.toggle_zone_icon_color.text()

        if on_icon_path and os.path.exists(on_icon_path):
            icon = create_colored_icon(on_icon_path, color)
            self.toggle_zone_on_icon_preview.setIcon(icon)
        else:
            self.toggle_zone_on_icon_preview.setIcon(QIcon())

        if off_icon_path and os.path.exists(off_icon_path):
            icon = create_colored_icon(off_icon_path, color)
            self.toggle_zone_off_icon_preview.setIcon(icon)
        else:
            self.toggle_zone_off_icon_preview.setIcon(QIcon())

    def update_trash_icon_preview(self):
        icon_path = self.trash_icon_path.text()
        color = self.trash_icon_color.text()
        if icon_path and os.path.exists(icon_path):
            icon = create_colored_icon(icon_path, color)
            self.trash_icon_preview.setIcon(icon)
        else:
            self.trash_icon_preview.setIcon(QIcon())

    def choose_app_icon(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать иконку приложения", "",
                                                  "Images (*.png *.xpm *.jpg *.svg)")
        if file_name:
            self.app_icon_path.setText(file_name)

    def choose_settings_icon(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать иконку настроек", "",
                                                  "Images (*.png *.xpm *.jpg *.svg)")
        if file_name:
            self.settings_icon_path.setText(file_name)
            self.update_settings_icon_preview()

    def choose_settings_icon_color(self):
        color = QColorDialog.getColor(QColor(self.settings_icon_color.text()), self, "Выбрать цвет иконки настроек")
        if color.isValid():
            self.settings_icon_color.setText(color.name())

    def choose_toggle_zone_on_icon(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать иконку переключения зон (вкл)", "",
                                                  "Images (*.png *.xpm *.jpg *.svg)")
        if file_name:
            self.toggle_zone_on_icon_path.setText(file_name)
            self.update_toggle_zone_icon_preview()

    def choose_toggle_zone_off_icon(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать иконку переключения зон (выкл)", "",
                                                  "Images (*.png *.xpm *.jpg *.svg)")
        if file_name:
            self.toggle_zone_off_icon_path.setText(file_name)
            self.update_toggle_zone_icon_preview()

    def choose_toggle_zone_icon_color(self):
        color = QColorDialog.getColor(QColor(self.toggle_zone_icon_color.text()), self, "Выбрать цвет иконки переключения зон")
        if color.isValid():
            self.toggle_zone_icon_color.setText(color.name())

    def choose_trash_icon(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выбрать иконку корзины", "",
                                                  "Images (*.png *.xpm *.jpg *.svg)")
        if file_name:
            self.trash_icon_path.setText(file_name)
            self.update_trash_icon_preview()

    def choose_trash_icon_color(self):
        color = QColorDialog.getColor(QColor(self.trash_icon_color.text()), self, "Выбрать цвет иконки корзины")
        if color.isValid():
            self.trash_icon_color.setText(color.name())

    def choose_qa_bg_color(self):
        color = QColorDialog.getColor(QColor(self.qa_bg_color.text()), self, "Выбрать цвет фона")
        if color.isValid():
            self.qa_bg_color.setText(color.name())

    def choose_qa_alt_bg_color(self):
        color = QColorDialog.getColor(QColor(self.qa_alt_bg_color.text()), self, "Выбрать альтернативный цвет фона")
        if color.isValid():
            self.qa_alt_bg_color.setText(color.name())

    def choose_work_zones_bg_color(self):
        color = QColorDialog.getColor(QColor(self.work_zones_bg_color.text()), self, "Выбрать цвет фона рабочих зон")
        if color.isValid():
            self.work_zones_bg_color.setText(color.name())

    def choose_active_tab_color(self):
        color = QColorDialog.getColor(QColor(self.active_tab_color.text()), self, "Выбрать цвет активной вкладки")
        if color.isValid():
            self.active_tab_color.setText(color.name())
