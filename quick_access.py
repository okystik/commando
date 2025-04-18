from PyQt6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QInputDialog,
                             QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QStyle, QColorDialog, QAbstractItemView)
from PyQt6.QtGui import QAction, QIcon, QBrush, QColor
from PyQt6.QtCore import Qt, QDir, QSettings
from settings_panel import SettingsPanel, create_colored_icon
import os
import shutil
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CustomQuickAccessList(QTreeWidget):
    def __init__(self, file_manager, parent=None):
        super().__init__(parent)
        self.file_manager = file_manager
        # Убираем фиксированную максимальную ширину
        # self.setMaximumWidth(150)
        self.setHeaderHidden(True)  # Скрываем заголовок
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(False)
        self.setWordWrap(False)  # Отключаем перенос текста
        self.itemExpanded.connect(self.on_item_expanded)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.itemClicked.connect(self.quick_access_clicked)
        self.update_style()

    def update_style(self):
        settings = QSettings("MyFileManager", "Settings")
        qa_font_size = settings.value("quick_access_font_size", "9", type=str)
        qa_row_height = settings.value("quick_access_row_height", "22", type=str)
        qa_bg_color = settings.value("quick_access_bg_color", "#2E2E2E", type=str)
        qa_alt_bg_color = settings.value("quick_access_alt_bg_color", "#353535", type=str)
        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {qa_bg_color};
                color: #FFFFFF;
                border: none;
                font-size: {qa_font_size}pt;
            }}
            QTreeWidget::item {{
                padding: 2px 5px;  /* Уменьшенный отступ для текста */
                min-height: {qa_row_height}px;
            }}
            QTreeWidget::item:selected {{
                background-color: #4A4A4A;
            }}
        """)
        # Подгоняем ширину столбца под содержимое
        self.adjust_column_width()
        # Применяем чередующиеся цвета
        self.apply_alternating_colors(qa_bg_color, qa_alt_bg_color)

    def adjust_column_width(self):
        """Подгоняем ширину столбца под содержимое, но не больше ширины виджета."""
        self.resizeColumnToContents(0)
        max_width = self.width() - 15  # Уменьшенный отступ для иконок и границ
        current_width = self.columnWidth(0)
        if current_width > max_width:
            self.setColumnWidth(0, max_width)
        elif current_width < max_width:
            self.setColumnWidth(0, max_width)

    def resizeEvent(self, event):
        """Обновляем ширину столбца при изменении размера виджета."""
        super().resizeEvent(event)
        self.adjust_column_width()

    def apply_alternating_colors(self, bg_color, alt_bg_color):
        """Применяем чередующиеся цвета для всех элементов в порядке их следования."""
        def traverse_and_color(item, depth=0):
            nonlocal index
            # Применяем цвет в зависимости от глобального индекса
            item.setBackground(0, QBrush(QColor(bg_color if index % 2 == 0 else alt_bg_color)))
            index += 1
            # Рекурсивно обходим дочерние элементы
            for i in range(item.childCount()):
                child = item.child(i)
                if child.text(0) != "":  # Пропускаем пустые (dummy) элементы
                    traverse_and_color(child, depth + 1)

        index = 0  # Глобальный индекс для чередования цветов
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            traverse_and_color(item)

    def on_item_expanded(self, item):
        """Обновляем содержимое папки при разворачивании."""
        if item.childCount() == 1 and item.child(0).text(0) == "":
            item.removeChild(item.child(0))
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if os.path.isdir(path):
                self.load_folder_contents(item, path)
        self.update_style()

    def load_folder_contents(self, parent_item, path):
        """Загружаем содержимое папки как дочерние элементы с сортировкой."""
        try:
            # Собираем все элементы в список
            entries = []
            for entry in os.scandir(path):
                entries.append({
                    'name': entry.name,
                    'path': entry.path,
                    'is_dir': entry.is_dir()
                })

            # Сортируем: сначала папки, затем файлы, внутри каждого типа — по имени (A-Z)
            entries.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))

            # Добавляем отсортированные элементы в дерево
            for entry in entries:
                item = QTreeWidgetItem(parent_item)
                item.setText(0, entry['name'])
                item.setData(0, Qt.ItemDataRole.UserRole, entry['path'])
                item.setData(0, Qt.ItemDataRole.UserRole + 1, False)  # Не фиксирован
                item.setData(0, Qt.ItemDataRole.UserRole + 2, entry['is_dir'])  # Флаг директории
                if entry['is_dir']:
                    item.setIcon(0, QIcon.fromTheme("folder"))
                    dummy = QTreeWidgetItem(item)
                    dummy.setText(0, "")
                else:
                    item.setIcon(0, QIcon.fromTheme("text-x-generic"))
            self.update_style()
        except PermissionError as e:
            logging.error(f"No access to {path}: {e}")
            QMessageBox.warning(self.file_manager, "Ошибка", f"Нет доступа к {path}: {e}")
        except OSError as e:
            logging.error(f"Failed to read {path}: {e}")
            QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось прочитать {path}: {e}")

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    for i in range(self.topLevelItemCount()):
                        item = self.topLevelItem(i)
                        if item.data(0, Qt.ItemDataRole.UserRole) == path:
                            QMessageBox.warning(self.file_manager, "Ошибка", "Этот путь уже есть в быстром доступе")
                            event.ignore()
                            return
                    item = QTreeWidgetItem(self)
                    item.setText(0, os.path.basename(path) or "Root")
                    item.setData(0, Qt.ItemDataRole.UserRole, path)
                    item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
                    item.setData(0, Qt.ItemDataRole.UserRole + 2, True)  # Директория
                    item.setIcon(0, QIcon.fromTheme("folder"))
                    dummy = QTreeWidgetItem(item)
                    dummy.setText(0, "")
                    self.file_manager.quick_access_panel.save_state()
                else:
                    QMessageBox.warning(self.file_manager, "Ошибка", "Можно добавлять только директории")
            event.acceptProposedAction()
        else:
            source_item = self.currentItem()
            if source_item and source_item.data(0, Qt.ItemDataRole.UserRole + 1):
                QMessageBox.warning(self.file_manager, "Ошибка", "Нельзя перемещать зафиксированный путь")
                event.ignore()
            elif source_item and source_item.data(0, Qt.ItemDataRole.UserRole + 2):
                super().dropEvent(event)
                self.file_manager.quick_access_panel.save_state()
        self.update_style()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        file_view = self.file_manager.current_file_view()

        if key == Qt.Key.Key_Delete:
            selected_items = self.selectedItems()
            if selected_items:
                item = selected_items[0]
                if item.data(0, Qt.ItemDataRole.UserRole + 1):
                    QMessageBox.warning(self.file_manager, "Ошибка", "Нельзя удалить зафиксированный путь")
                    return
                if item.parent() is None:
                    reply = QMessageBox.question(self.file_manager, "Удаление",
                                               f"Вы уверены, что хотите удалить путь '{item.text(0)}' из быстрого доступа?",
                                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.Yes:
                        parent = item.parent() or self.invisibleRootItem()
                        parent.removeChild(item)
                        self.file_manager.quick_access_panel.save_state()
                        self.update_style()

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_C:
            selected_items = self.selectedItems()
            if selected_items:
                item = selected_items[0]
                path = item.data(0, Qt.ItemDataRole.UserRole)
                self.file_manager.clipboard = [path]
                self.file_manager.clipboard_is_cut = False

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_X:
            selected_items = self.selectedItems()
            if selected_items:
                item = selected_items[0]
                path = item.data(0, Qt.ItemDataRole.UserRole)
                self.file_manager.clipboard = [path]
                self.file_manager.clipboard_is_cut = True

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_V:
            if self.file_manager.clipboard and file_view:
                current_path = file_view.history[-1] if file_view.history else self.file_manager.QDir.homePath()
                for src_path in self.file_manager.clipboard:
                    if not os.path.exists(src_path):
                        continue
                    base_name = os.path.basename(src_path)
                    dest_path = os.path.join(current_path, base_name)
                    if os.path.exists(dest_path):
                        dest_path = os.path.join(current_path, f"Копия - {base_name}")
                    try:
                        if os.path.isdir(src_path):
                            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                        else:
                            shutil.copy2(src_path, dest_path)
                        if self.file_manager.clipboard_is_cut and os.path.exists(src_path):
                            try:
                                shutil.rmtree(src_path) if os.path.isdir(src_path) else os.remove(src_path)
                            except PermissionError as e:
                                QMessageBox.warning(self.file_manager, "Ошибка", f"Нет прав на удаление: {e}")
                            except OSError as e:
                                QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось удалить исходный файл: {e}")
                    except PermissionError as e:
                        QMessageBox.warning(self.file_manager, "Ошибка", f"Нет прав на операцию: {e}")
                    except OSError as e:
                        QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось выполнить операцию: {e}")
                if self.file_manager.clipboard_is_cut:
                    self.file_manager.clipboard = []
                    self.file_manager.clipboard_is_cut = False
                self.file_manager.refresh_view(file_view)

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_A:
            self.selectAll()

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_H:
            if file_view:
                self.file_manager.navigate_to(file_view, QDir.homePath())

        elif (modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_R) or key == Qt.Key.Key_F5:
            self.file_manager.quick_access_panel.load_state()

        elif modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_N:
            folder_path, ok = QInputDialog.getText(self.file_manager, "Добавить папку", "Введите путь к папке:")
            if ok and folder_path and os.path.isdir(folder_path):
                for i in range(self.topLevelItemCount()):
                    item = self.topLevelItem(i)
                    if item.data(0, Qt.ItemDataRole.UserRole) == folder_path:
                        QMessageBox.warning(self.file_manager, "Ошибка", "Этот путь уже есть в быстром доступе")
                        return
                item = QTreeWidgetItem(self)
                item.setText(0, os.path.basename(folder_path) or "Root")
                item.setData(0, Qt.ItemDataRole.UserRole, folder_path)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
                item.setData(0, Qt.ItemDataRole.UserRole + 2, True)
                item.setIcon(0, QIcon.fromTheme("folder"))
                dummy = QTreeWidgetItem(item)
                dummy.setText(0, "")
                self.file_manager.quick_access_panel.save_state()
                self.update_style()
            elif ok and folder_path:
                QMessageBox.warning(self.file_manager, "Ошибка", "Указанный путь не является папкой или не существует")

        elif modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier) and key == Qt.Key.Key_N:
            path, ok = QInputDialog.getText(self.file_manager, "Добавить путь", "Введите путь:")
            if ok and path and os.path.exists(path) and os.path.isdir(path):
                for i in range(self.topLevelItemCount()):
                    item = self.topLevelItem(i)
                    if item.data(0, Qt.ItemDataRole.UserRole) == path:
                        QMessageBox.warning(self.file_manager, "Ошибка", "Этот путь уже есть в быстром доступе")
                        return
                item = QTreeWidgetItem(self)
                item.setText(0, os.path.basename(path) or "Root")
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
                item.setData(0, Qt.ItemDataRole.UserRole + 2, True)
                item.setIcon(0, QIcon.fromTheme("folder"))
                dummy = QTreeWidgetItem(item)
                dummy.setText(0, "")
                self.file_manager.quick_access_panel.save_state()
                self.update_style()
            elif ok and path:
                QMessageBox.warning(self.file_manager, "Ошибка", "Указанный путь не является папкой или не существует")

        elif key == Qt.Key.Key_F2:
            selected_items = self.selectedItems()
            if selected_items:
                item = selected_items[0]
                old_name = item.text(0)
                new_name, ok = QInputDialog.getText(self.file_manager, "Переименовать", "Введите новое имя:", text=old_name)
                if ok and new_name:
                    item.setText(0, new_name)
                    self.file_manager.quick_access_panel.save_state()
                    self.update_style()

        super().keyPressEvent(event)

    def show_context_menu(self, position):
        item = self.itemAt(position)
        if not item:
            return
        menu = QMenu()
        if item.parent() is None:
            detach_action = QAction("Открепить путь", self)
            fix_action = QAction("Зафиксировать путь", self) if not item.data(0, Qt.ItemDataRole.UserRole + 1) else QAction("Снять фиксацию", self)
            detach_action.triggered.connect(lambda: self.detach_path(item))
            fix_action.triggered.connect(lambda: self.toggle_fix_path(item))
            menu.addAction(detach_action)
            menu.addAction(fix_action)
        else:
            open_action = QAction("Открыть", self)
            copy_action = QAction("Копировать", self)
            cut_action = QAction("Вырезать", self)
            open_action.triggered.connect(lambda: self.open_item(item))
            copy_action.triggered.connect(lambda: self.copy_item(item))
            cut_action.triggered.connect(lambda: self.cut_item(item))
            menu.addAction(open_action)
            menu.addAction(copy_action)
            menu.addAction(cut_action)
        # Используем viewport() для корректного преобразования координат
        global_pos = self.viewport().mapToGlobal(position)
        menu.exec(global_pos)

    def detach_path(self, item):
        if item.data(0, Qt.ItemDataRole.UserRole + 1):
            QMessageBox.warning(self.file_manager, "Ошибка", "Сначала снимите фиксацию с пути")
            return
        parent = item.parent() or self.invisibleRootItem()
        parent.removeChild(item)
        self.file_manager.quick_access_panel.save_state()
        self.update_style()

    def toggle_fix_path(self, item):
        current_state = item.data(0, Qt.ItemDataRole.UserRole + 1)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, not current_state)
        self.file_manager.quick_access_panel.save_state()
        self.update_style()

    def open_item(self, item):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.exists(path):
            file_view = self.file_manager.current_file_view()
            if file_view:
                self.file_manager.navigate_to(file_view, path)
        else:
            QMessageBox.warning(self.file_manager, "Ошибка", f"Путь больше не существует: {path}")

    def copy_item(self, item):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        self.file_manager.clipboard = [path]
        self.file_manager.clipboard_is_cut = False

    def cut_item(self, item):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        self.file_manager.clipboard = [path]
        self.file_manager.clipboard_is_cut = True

    def quick_access_clicked(self, item, column):
        # Получаем позицию клика относительно области просмотра
        pos = self.mapFromGlobal(self.cursor().pos())
        self.file_manager.quick_access_panel.show_zone_selection_menu(item, self.viewport().mapToGlobal(pos))

class QuickAccessPanel:
    def __init__(self, file_manager):
        self.file_manager = file_manager
        self.widget = QWidget()
        self.layout = QVBoxLayout(self.widget)

        self.quick_access = CustomQuickAccessList(file_manager, self.widget)
        self.layout.addWidget(self.quick_access)

        self.button_layout = QHBoxLayout()
        self.button_layout.setContentsMargins(6, 0, 0, 5)
        self.settings_button = QPushButton()
        self.zone_toggle_button = QPushButton()
        self.trash_button = QPushButton()

        self.settings_button.setFixedSize(30, 30)
        self.zone_toggle_button.setFixedSize(30, 30)
        self.trash_button.setFixedSize(30, 30)

        self.settings_button.clicked.connect(self.open_settings)
        self.zone_toggle_button.clicked.connect(self.toggle_second_zone)
        self.trash_button.clicked.connect(self.open_trash)
        self.trash_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.trash_button.customContextMenuRequested.connect(self.show_trash_context_menu)

        self.button_layout.addWidget(self.settings_button)
        self.button_layout.addWidget(self.zone_toggle_button)
        self.button_layout.addWidget(self.trash_button)
        self.button_layout.addStretch()
        self.layout.addLayout(self.button_layout)

        # Подключаем сигнал изменения размера виджета
        self.widget.resizeEvent = self.on_resize

        self.update_style()
        self.load_icons()
        self.load_state()

    def on_resize(self, event):
        """Обновляем ширину столбца при изменении размера панели."""
        self.quick_access.adjust_column_width()
        event.accept()

    def update_style(self):
        settings = QSettings("MyFileManager", "Settings")
        bg_color = settings.value("quick_access_bg_color", "#2E2E2E", type=str)

        self.widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
            }}
        """)
        self.settings_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
        """)
        self.zone_toggle_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
        """)
        self.trash_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
        """)
        self.quick_access.update_style()

    def load_icons(self):
        settings = QSettings("MyFileManager", "Settings")
        settings_icon_path = settings.value("icon_settings", "img/settings.svg", type=str)
        settings_icon_path = os.path.abspath(settings_icon_path)
        settings_icon_color = settings.value("settings_icon_color", "#FFFFFF", type=str)
        if os.path.exists(settings_icon_path) and os.access(settings_icon_path, os.R_OK):
            icon = create_colored_icon(settings_icon_path, settings_icon_color)
            self.settings_button.setIcon(icon)
        else:
            logging.warning(f"Settings icon not found at {settings_icon_path}, using default.")
            self.settings_button.setIcon(self.widget.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        toggle_icon_on = settings.value("icon_togglezoneon", "img/toggle_zone_on.svg", type=str)
        toggle_icon_off = settings.value("icon_togglezoneoff", "img/toggle_zone_off.svg", type=str)
        toggle_icon_color = settings.value("toggle_zone_icon_color", "#FFFFFF", type=str)
        toggle_icon_on = os.path.abspath(toggle_icon_on)
        toggle_icon_off = os.path.abspath(toggle_icon_off)
        toggle_icon_path = toggle_icon_on if not self.file_manager.second_zone_active else toggle_icon_off
        if os.path.exists(toggle_icon_path) and os.access(toggle_icon_path, os.R_OK):
            icon = create_colored_icon(toggle_icon_path, toggle_icon_color)
            self.zone_toggle_button.setIcon(icon)
        else:
            logging.warning(f"Toggle zone icon not found at {toggle_icon_path}, using default.")
            self.zone_toggle_button.setIcon(self.widget.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))

        trash_icon_path = settings.value("icon_trash", "img/trash.svg", type=str)
        trash_icon_path = os.path.abspath(trash_icon_path)
        trash_icon_color = settings.value("trash_icon_color", "#FF0000", type=str)
        if os.path.exists(trash_icon_path) and os.access(trash_icon_path, os.R_OK):
            icon = create_colored_icon(trash_icon_path, trash_icon_color)
            self.trash_button.setIcon(icon)
        else:
            logging.warning(f"Trash icon not found at {trash_icon_path}, using default.")
            self.trash_button.setIcon(self.widget.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

    def open_trash(self):
        trash_path = os.path.expanduser("~/.local/share/Trash/files")
        os.makedirs(trash_path, exist_ok=True)
        nav_bar = self.file_manager.navigation_bar1 if self.file_manager.active_zone == 1 else self.file_manager.navigation_bar2
        if nav_bar:
            nav_bar.add_new_tab(trash_path)
        logging.info(f"Opened trash at {trash_path}")

    def show_trash_context_menu(self, position):
        menu = QMenu(self.trash_button)
        clear_action = QAction("Очистить корзину", self.trash_button)
        clear_action.triggered.connect(self.clear_trash)
        menu.addAction(clear_action)
        # Корректное преобразование координат для кнопки
        global_pos = self.trash_button.mapToGlobal(position)
        menu.exec(global_pos)

    def clear_trash(self):
        reply = QMessageBox.question(self.file_manager, "Очистка корзины",
                                    "Вы уверены, что хотите безвозвратно очистить корзину?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.file_manager.undo_manager.clear_trash():
                QMessageBox.information(self.file_manager, "Корзина очищена",
                                        "Корзина успешно очищена.")
                for i in range(self.file_manager.navigation_bar1.tab_widget.count()):
                    file_view = self.file_manager.navigation_bar1.tab_widget.widget(i).findChild(CustomTreeViewWithDrag)
                    if file_view and self.file_manager.current_path(file_view) == os.path.expanduser("~/.local/share/Trash/files"):
                        self.file_manager.refresh_view(file_view)
                if self.file_manager.second_zone_active and self.file_manager.navigation_bar2:
                    for i in range(self.file_manager.navigation_bar2.tab_widget.count()):
                        file_view = self.file_manager.navigation_bar2.tab_widget.widget(i).findChild(CustomTreeViewWithDrag)
                        if file_view and self.file_manager.current_path(file_view) == os.path.expanduser("~/.local/share/Trash/files"):
                            self.file_manager.refresh_view(file_view)
            else:
                QMessageBox.warning(self.file_manager, "Ошибка",
                                    "Не удалось очистить корзину.")

    def show_zone_selection_menu(self, item, position):
        menu = QMenu()
        open_in_zone1_action = QAction("Открыть в зоне 1", self.quick_access)
        open_in_zone2_action = QAction("Открыть в зоне 2", self.quick_access)

        open_in_zone1_action.triggered.connect(lambda: self.open_in_zone(1, item))
        open_in_zone2_action.triggered.connect(lambda: self.open_in_zone(2, item))

        menu.addAction(open_in_zone1_action)
        if self.file_manager.second_zone_active:
            menu.addAction(open_in_zone2_action)

        # Отображаем меню в правильной позиции
        menu.exec(position)

    def open_in_zone(self, zone, item):
        if not item:
            return
        self.file_manager.set_active_zone(zone)
        file_view = self.file_manager.get_file_view(zone)
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.exists(path):
            if file_view:
                self.file_manager.navigate_to(file_view, path)
            else:
                nav_bar = self.file_manager.navigation_bar1 if zone == 1 else self.file_manager.navigation_bar2
                if nav_bar:
                    nav_bar.add_new_tab(path)
        else:
            QMessageBox.warning(self.file_manager, "Ошибка", f"Путь больше не существует: {path}")

    def open_settings(self):
        settings_dialog = SettingsPanel(self.file_manager, self)
        settings_dialog.exec()
        self.quick_access.update_style()
        self.update_style()
        self.load_icons()

    def toggle_second_zone(self):
        self.file_manager.toggle_second_zone()
        self.load_icons()

    def save_state(self):
        settings = QSettings("MyFileManager", "Settings")
        quick_access_items = []
        for i in range(self.quick_access.topLevelItemCount()):
            item = self.quick_access.topLevelItem(i)
            path = item.data(0, Qt.ItemDataRole.UserRole)
            is_fixed = item.data(0, Qt.ItemDataRole.UserRole + 1)
            is_expanded = item.isExpanded()
            quick_access_items.append((path, is_fixed, is_expanded))
        settings.setValue("quickAccessItems", quick_access_items)
        settings.sync()

    def load_state(self):
        settings = QSettings("MyFileManager", "Settings")
        quick_access_items = settings.value("quickAccessItems", [])
        if quick_access_items is None:
            quick_access_items = []

        self.quick_access.clear()

        for item_data in quick_access_items:
            try:
                path, is_fixed, is_expanded = item_data
                if os.path.exists(path) and os.path.isdir(path):
                    item = QTreeWidgetItem(self.quick_access)
                    item.setText(0, os.path.basename(path) or "Root")
                    item.setData(0, Qt.ItemDataRole.UserRole, path)
                    item.setData(0, Qt.ItemDataRole.UserRole + 1, is_fixed)
                    item.setData(0, Qt.ItemDataRole.UserRole + 2, True)
                    item.setIcon(0, QIcon.fromTheme("folder"))
                    dummy = QTreeWidgetItem(item)
                    dummy.setText(0, "")
                    if is_expanded:
                        item.setExpanded(True)
            except (ValueError, TypeError):
                continue

        self.load_icons()
        self.quick_access.update_style()

    def get_widget(self):
        return self.widget
