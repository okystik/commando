import sys
import os
import shutil
import platform
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QSplitter, QAbstractItemView, QProgressDialog, QMenu,
                            QListWidget, QListWidgetItem, QMessageBox, QPushButton)
from PyQt6.QtCore import Qt, QDir, QTimer, QSettings, QByteArray, QUrl, QAbstractItemModel, QModelIndex, QThread, pyqtSignal
from PyQt6.QtGui import QFileSystemModel, QDesktopServices, QIcon, QAction, QStandardItemModel, QStandardItem, QMouseEvent
from hotkey import HotkeyManager
from navigation import NavigationBar
from quick_access import QuickAccessPanel
from treeview import CustomTreeViewWithDrag
from undo_manager import UndoManager
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Resource path for bundled assets
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class SearchModel(QAbstractItemModel):
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.results = results
        self.headers = ["Имя", "Путь"]

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.results)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return os.path.basename(self.results[index.row()])
            elif index.column() == 1:
                return self.results[index.row()]
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.headers[section]
        return None

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(self, index):
        return QModelIndex()

class FileOperationThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, src_paths, dest_path, operation="copy"):
        super().__init__()
        self.src_paths = src_paths
        self.dest_path = dest_path
        self.operation = operation

    def run(self):
        total = len(self.src_paths)
        for i, src_path in enumerate(self.src_paths):
            if not os.path.exists(src_path):
                logging.warning(f"Source path does not exist for {self.operation}: {src_path}")
                continue
            base_name = os.path.basename(src_path)
            dest = os.path.join(self.dest_path, base_name)
            if os.path.exists(dest):
                dest = os.path.join(self.dest_path, f"Копия - {base_name}")
            try:
                if self.operation == "copy":
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src_path, dest)
                elif self.operation == "move":
                    shutil.move(src_path, dest)
                self.progress.emit(int((i + 1) / total * 100))
                logging.info(f"Performed {self.operation}: {src_path} -> {dest}")
            except PermissionError as e:
                self.error.emit(f"Нет прав на {self.operation} {src_path}: {e}")
                logging.error(f"No permission for {self.operation} {src_path}: {e}")
            except OSError as e:
                self.error.emit(f"Ошибка при {self.operation} {src_path}: {e}")
                logging.error(f"Failed {self.operation} {src_path}: {e}")
        self.finished.emit()

class FileManager(QMainWindow):
    SearchModel = SearchModel

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Простой файловый менеджер")
        self.setGeometry(100, 100, 800, 600)

        # Initialize settings
        self.settings = QSettings("MyFileManager", "Settings")
        self.load_icon_settings()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)

        self.second_zone_active = False
        self.active_zone = 1
        self.clipboard = []
        self.clipboard_is_cut = False
        self.QDir = QDir

        self.undo_manager = UndoManager()

        self.quick_access_panel = QuickAccessPanel(self)
        self.splitter.addWidget(self.quick_access_panel.get_widget())

        self.zones_widget = QWidget()
        self.zones_layout = QHBoxLayout(self.zones_widget)
        self.splitter.addWidget(self.zones_widget)

        self.navigation_bar1 = NavigationBar(self)
        self.zones_layout.addWidget(self.navigation_bar1)

        self.navigation_bar2 = None

        self.hotkey_manager = HotkeyManager(self)

        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.save_state)
        self.save_timer.start(15000)

        self.path_before_search = None
        self.search_performed = False

        self.active_threads = []

        self.setStyleSheet("""
            QMainWindow {
                background-color: #2E2E2E;
            }
        """)

        self.load_state()
        self.update_work_zones_style()

    def load_icon_settings(self):
        app_icon_path = self.settings.value("icon_appicon", "", type=str)
        app_icon_path = os.path.abspath(app_icon_path) if app_icon_path else ""
        default_app_icon_path = resource_path(os.path.join("img", "appicon.png"))
        if app_icon_path and os.path.exists(app_icon_path) and os.access(app_icon_path, os.R_OK):
            self.setWindowIcon(QIcon(app_icon_path))
        elif os.path.exists(default_app_icon_path):
            self.setWindowIcon(QIcon(default_app_icon_path))

    def update_work_zones_style(self):
        settings = QSettings("MyFileManager", "Settings")
        bg_color = settings.value("work_zones_bg_color", "#2E2E2E", type=str)
        self.zones_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
            }}
        """)
        if self.navigation_bar1:
            self.navigation_bar1.update_style()
        if self.navigation_bar2:
            self.navigation_bar2.update_style()

    def toggle_second_zone(self):
        if self.second_zone_active:
            self.navigation_bar2.setParent(None)
            self.zones_layout.removeWidget(self.navigation_bar2)
            self.navigation_bar2.deleteLater()
            self.navigation_bar2 = None
            self.second_zone_active = False
        else:
            self.navigation_bar2 = NavigationBar(self)
            self.navigation_bar2.add_new_tab(QDir.homePath())
            self.zones_layout.addWidget(self.navigation_bar2)
            self.second_zone_active = True
        self.save_state()
        self.update_work_zones_style()

    def get_file_view(self, zone):
        return self.navigation_bar1.current_file_view() if zone == 1 else (self.navigation_bar2.current_file_view() if self.second_zone_active else None)

    def current_file_view(self):
        return self.get_file_view(self.active_zone)

    def current_path(self, file_view):
        return file_view.history[-1] if file_view.history else QDir.homePath()

    def set_active_zone(self, zone):
        self.active_zone = zone
        logging.info(f"Active zone set to {zone}")

    def update_active_zone(self, file_view):
        if file_view in self.navigation_bar1.findChildren(CustomTreeViewWithDrag):
            self.active_zone = 1
        elif self.second_zone_active and file_view in self.navigation_bar2.findChildren(CustomTreeViewWithDrag):
            self.active_zone = 2
        logging.info(f"Updated active zone to {self.active_zone}")

    def perform_file_operation(self, src_paths, dest_path, operation):
        thread = FileOperationThread(src_paths, dest_path, operation)
        self.active_threads.append(thread)
        progress_dialog = QProgressDialog(f"{operation.capitalize()} файлов...", "Отмена", 0, 100, self)
        progress_dialog.setWindowModality(Qt.WindowModality.NonModal)
        thread.progress.connect(progress_dialog.setValue)
        thread.finished.connect(progress_dialog.close)
        thread.finished.connect(lambda: self.refresh_view(self.current_file_view()) if self.current_file_view() else None)
        thread.finished.connect(lambda: self.active_threads.remove(thread))
        thread.error.connect(lambda msg: QMessageBox.warning(self, "Ошибка", msg))
        thread.start()
        progress_dialog.show()

        # Add undo actions
        for src_path in src_paths:
            if not os.path.exists(src_path):
                logging.warning(f"Source path does not exist for undo logging: {src_path}")
                continue
            base_name = os.path.basename(src_path)
            dest = os.path.join(dest_path, base_name)
            if os.path.exists(dest):
                dest = os.path.join(dest_path, f"Копия - {base_name}")
            if operation == "copy":
                self.undo_manager.add_action('COPY', dest_path=dest)
            elif operation == "move":
                self.undo_manager.add_action('MOVE', src_path=src_path, dest_path=dest)
            logging.info(f"Added undo action for {operation}: {src_path} -> {dest}")

    def go_back(self, file_view):
        if file_view and file_view.current_index > 0:
            file_view.current_index -= 1
            new_path = file_view.history[file_view.current_index]
            self.navigate_to(file_view, new_path)
            logging.info(f"Navigated back to {new_path}")

    def go_forward(self, file_view):
        if file_view and file_view.current_index < len(file_view.history) - 1:
            file_view.current_index += 1
            new_path = file_view.history[file_view.current_index]
            self.navigate_to(file_view, new_path)
            logging.info(f"Navigated forward to {new_path}")

    def go_up(self, file_view):
        if file_view:
            current_path = self.current_path(file_view)
            parent_path = os.path.dirname(current_path)
            if parent_path != current_path:
                self.navigate_to(file_view, parent_path)
                logging.info(f"Navigated up to {parent_path}")

    def on_double_click(self, file_view, index):
        if not file_view or not index.isValid():
            logging.warning("Invalid file view or index for double click")
            return

        if isinstance(file_view.model(), self.SearchModel):
            path = file_view.model().data(file_view.model().index(index.row(), 1), Qt.ItemDataRole.DisplayRole)
        else:
            source_index = file_view.proxy_model.mapToSource(index)
            path = file_view.proxy_model.sourceModel().item(source_index.row(), 0).data(Qt.ItemDataRole.UserRole)

        if not os.path.exists(path):
            logging.error(f"Path does not exist: {path}")
            QMessageBox.warning(self, "Ошибка", f"Путь не существует: {path}")
            return

        if os.path.isdir(path):
            self.navigate_to(file_view, path)
            logging.info(f"Navigated to directory: {path}")
        else:
            absolute_path = os.path.abspath(path)
            url = QUrl.fromLocalFile(absolute_path)
            success = QDesktopServices.openUrl(url)
            if not success:
                try:
                    if platform.system() == "Windows":
                        os.startfile(absolute_path)
                    elif platform.system() == "Linux":
                        os.system(f"xdg-open \"{absolute_path}\"")
                    elif platform.system() == "Darwin":
                        os.system(f"open \"{absolute_path}\"")
                    else:
                        logging.error(f"Unsupported OS for opening file: {absolute_path}")
                        QMessageBox.warning(self, "Ошибка", f"Не поддерживаемая ОС для открытия файла: {absolute_path}")
                except Exception as e:
                    logging.error(f"Failed to open file {absolute_path}: {e}")
                    QMessageBox.warning(self, "Ошибка", f"Не удалось открыть файл {absolute_path}: {str(e)}")

    def navigate_to(self, file_view, path):
        if not file_view or not os.path.exists(path):
            logging.error(f"Cannot navigate: file_view={file_view}, path={path} does not exist")
            return

        if file_view.current_index < len(file_view.history) - 1:
            file_view.history = file_view.history[:file_view.current_index + 1]
        file_view.history.append(path)
        file_view.current_index = len(file_view.history) - 1

        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Name", "Size", "Type", "Date Modified"])

        dir_entries = []
        settings = QSettings("MyFileManager", "Settings")
        hide_hidden_files = settings.value("hide_hidden_files", False, type=bool)

        try:
            for entry in os.scandir(path):
                try:
                    if hide_hidden_files and entry.name.startswith('.'):
                        continue

                    is_dir = entry.is_dir()
                    name = entry.name
                    size = os.path.getsize(entry.path) if not is_dir else 0
                    mtime = os.path.getmtime(entry.path)
                    file_type = "Folder" if is_dir else (os.path.splitext(name)[1][1:].upper() or "File")
                    dir_entries.append({
                        'name': name,
                        'path': entry.path,
                        'is_dir': is_dir,
                        'size': size,
                        'type': file_type,
                        'date': mtime
                    })
                    logging.debug(f"Added entry {name}: is_dir={is_dir}, size={size}, type={file_type}, date={mtime}")
                except PermissionError as e:
                    logging.warning(f"No access to {entry.path}: {e}")
                    continue
                except OSError as e:
                    logging.error(f"Error processing {entry.path}: {e}")
                    continue
        except PermissionError as e:
            logging.error(f"No access to {path}: {e}")
            QMessageBox.warning(self, "Ошибка", f"Нет доступа к {path}: {e}")
            return
        except OSError as e:
            logging.error(f"Failed to open {path}: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть {path}: {e}")
            return

        for entry in dir_entries:
            name_item = QStandardItem(entry['name'])
            name_item.setData(entry['path'], Qt.ItemDataRole.UserRole)
            name_item.setData(0 if entry['is_dir'] else 1, Qt.ItemDataRole.UserRole + 1)
            name_item.setData(entry['name'].lower(), Qt.ItemDataRole.UserRole + 2)
            name_item.setEditable(True)

            size_item = QStandardItem(file_view.format_size(entry['size']) if not entry['is_dir'] else "")
            size_item.setData(entry['size'], Qt.ItemDataRole.UserRole)
            size_item.setData(entry['size'] if not entry['is_dir'] else -1, Qt.ItemDataRole.UserRole + 1)
            size_item.setEditable(False)

            type_item = QStandardItem(entry['type'])
            type_item.setData(entry['type'].lower(), Qt.ItemDataRole.UserRole + 1)
            type_item.setEditable(False)

            date_item = QStandardItem(datetime.fromtimestamp(entry['date']).strftime('%d.%m.%Y %H:%M') if entry['date'] else "")
            date_item.setData(entry['date'], Qt.ItemDataRole.UserRole)
            date_item.setData(entry['date'], Qt.ItemDataRole.UserRole + 1)
            date_item.setEditable(False)

            if entry['is_dir']:
                name_item.setIcon(QIcon.fromTheme("folder"))
            else:
                name_item.setIcon(QIcon.fromTheme("text-x-generic"))

            model.appendRow([name_item, size_item, type_item, date_item])

        file_view.setModel(model)
        file_view.setColumnHidden(1, False)
        file_view.setColumnHidden(2, False)
        file_view.setColumnHidden(3, False)

        nav_bar = self.navigation_bar1 if file_view in self.navigation_bar1.findChildren(CustomTreeViewWithDrag) else self.navigation_bar2
        nav_bar.tab_widget.setTabText(nav_bar.tab_widget.currentIndex(), os.path.basename(path) or "Root")
        nav_bar.update_path_edit(file_view)
        self.update_active_zone(file_view)
        self.restore_column_state(file_view)
        file_view.update_style()

        column = file_view.header().sortIndicatorSection()
        order = file_view.header().sortIndicatorOrder()
        logging.info(f"Sorting by column {column}, order: {'Ascending' if order == Qt.SortOrder.AscendingOrder else 'Descending'}")
        file_view.proxy_model.setSortOrder(order)
        file_view.proxy_model.sort(column, order)

    def refresh_view(self, file_view):
        if not file_view:
            logging.warning("No file view to refresh")
            return
        current_path = self.current_path(file_view)
        if os.path.exists(current_path):
            self.navigate_to(file_view, current_path)
            logging.info(f"Refreshed view at {current_path}")

    def quick_access_clicked(self, file_view, item):
        if not item or not file_view:
            logging.warning("Invalid item or file view for quick access click")
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if os.path.exists(path):
            self.navigate_to(file_view, path)
            logging.info(f"Navigated to quick access path: {path}")
        else:
            logging.error(f"Quick access path does not exist: {path}")
            QMessageBox.warning(self, "Ошибка", f"Путь больше не существует: {path}")

    def on_data_changed(self, file_view, index):
        if not file_view or not index.isValid():
            logging.error("Invalid file view or index for data changed")
            return
        if not isinstance(file_view.proxy_model.sourceModel(), QStandardItemModel):
            logging.error("Model is not QStandardItemModel")
            return
        if index.column() != 0:
            logging.debug("Data changed in non-name column, ignoring")
            return

        source_index = file_view.proxy_model.mapToSource(index)
        item = file_view.proxy_model.sourceModel().item(source_index.row(), 0)
        if not item:
            logging.error("No item at source index")
            return

        old_path = item.data(Qt.ItemDataRole.UserRole)
        new_name = item.text().strip()
        if not old_path or not new_name:
            logging.error(f"Invalid old_path: {old_path} or new_name: {new_name}")
            return

        new_path = os.path.join(os.path.dirname(old_path), new_name)
        logging.debug(f"Checking rename: old_path={old_path}, new_path={new_path}")

        if old_path == new_path:
            logging.debug("No rename needed: paths are identical")
            return

        if not os.path.exists(old_path):
            logging.error(f"Cannot rename: {old_path} does not exist")
            QMessageBox.warning(self, "Ошибка", f"Файл или папка не существует: {old_path}")
            return

        if os.path.exists(new_path):
            logging.warning(f"Cannot rename: {new_path} already exists")
            QMessageBox.warning(self, "Ошибка", f"Файл или папка уже существует: {new_path}")
            return

        logging.info(f"Attempting to rename: {old_path} -> {new_path}")
        try:
            os.rename(old_path, new_path)
            item.setData(new_path, Qt.ItemDataRole.UserRole)
            item.setData(new_name.lower(), Qt.ItemDataRole.UserRole + 2)
            self.undo_manager.add_action('RENAME', old_path=old_path, new_path=new_path)
            logging.info(f"Successfully renamed: {old_path} -> {new_path}")
        except PermissionError as e:
            logging.error(f"No permission to rename: {e}")
            QMessageBox.warning(self, "Ошибка", f"Нет прав на переименование: {e}")
        except OSError as e:
            logging.error(f"Failed to rename: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось переименовать: {e}")
        self.refresh_view(file_view)

    def handle_data_changed(self, topLeft, bottomRight, roles):
        logging.debug(f"Data changed signal received at index: {topLeft.row()},{topLeft.column()}, roles: {roles}")
        file_view = self.current_file_view()
        if not file_view:
            logging.warning("No file view for data changed")
            return
        if Qt.ItemDataRole.EditRole in roles and topLeft.column() == 0:
            logging.info(f"Editing detected at index: {topLeft.row()},{topLeft.column()}")
            self.on_data_changed(file_view, topLeft)

    def perform_search(self):
        nav_bar = self.navigation_bar1 if self.active_zone == 1 else self.navigation_bar2
        if not nav_bar:
            logging.warning("No navigation bar for search")
            return
        search_text = nav_bar.search_edit.text().strip().lower()
        if not search_text:
            logging.info("Empty search text")
            QMessageBox.warning(self, "Ошибка", "Введите текст для поиска")
            return

        file_view = self.current_file_view()
        if not file_view:
            logging.warning("No file view for search")
            return
        current_path = self.current_path(file_view)

        self.path_before_search = current_path
        self.search_performed = True

        if os.path.splitdrive(current_path)[1] in ["/", "\\"]:
            search_root = current_path
        else:
            search_root = current_path

        results = []

        def search_recursive(directory, depth=0, max_depth=5):
            if depth > max_depth:
                return
            try:
                for entry in os.scandir(directory):
                    try:
                        if search_text in entry.name.lower():
                            results.append(entry.path)
                        if entry.is_dir():
                            search_recursive(entry.path, depth + 1, max_depth)
                    except PermissionError:
                        pass
            except PermissionError:
                pass

        search_recursive(search_root)

        if not results:
            logging.info("No search results found")
            QMessageBox.information(self, "Поиск", "Ничего не найдено")
            return

        search_model = self.SearchModel(results)
        file_view.setModel(search_model)
        file_view.setRootIndex(QModelIndex())
        file_view.setColumnHidden(2, True)
        file_view.setColumnHidden(3, True)
        file_view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        file_view.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        file_view.update_style()
        logging.info(f"Displayed {len(results)} search results")

    def save_state(self):
        settings = QSettings("MyFileManager", "Settings")
        settings.setValue("geometry", self.geometry())
        settings.setValue("splitterSizes", self.splitter.sizes())
        settings.setValue("secondZoneActive", self.second_zone_active)

        open_tabs1 = []
        for i in range(self.navigation_bar1.tab_widget.count()):
            file_view = self.navigation_bar1.tab_widget.widget(i).findChild(CustomTreeViewWithDrag)
            path = self.current_path(file_view)
            open_tabs1.append(path)
            settings.setValue(f"tab1_{i}_columnState", file_view.header().saveState())
        settings.setValue("openTabs1", open_tabs1)
        settings.setValue("currentTabIndex1", self.navigation_bar1.tab_widget.currentIndex())

        if self.second_zone_active and self.navigation_bar2:
            open_tabs2 = []
            for i in range(self.navigation_bar2.tab_widget.count()):
                file_view = self.navigation_bar2.tab_widget.widget(i).findChild(CustomTreeViewWithDrag)
                path = self.current_path(file_view)
                open_tabs2.append(path)
                settings.setValue(f"tab2_{i}_columnState", file_view.header().saveState())
            settings.setValue("openTabs2", open_tabs2)
            settings.setValue("currentTabIndex2", self.navigation_bar2.tab_widget.currentIndex())

        self.quick_access_panel.save_state()
        logging.debug("Saved application state")

    def restore_column_state(self, file_view):
        if not file_view:
            logging.warning("No file view to restore column state")
            return
        settings = QSettings("MyFileManager", "Settings")
        nav_bar = self.navigation_bar1 if file_view in self.navigation_bar1.findChildren(CustomTreeViewWithDrag) else self.navigation_bar2
        tab_index = nav_bar.tab_widget.indexOf(file_view.parent())
        zone_prefix = "tab1" if nav_bar == self.navigation_bar1 else "tab2"
        column_state = settings.value(f"{zone_prefix}_{tab_index}_columnState")

        if column_state:
            file_view.header().restoreState(column_state)
        else:
            header = file_view.header()
            header.resizeSection(0, 200)
            header.resizeSection(1, 100)
            header.resizeSection(2, 100)
            header.resizeSection(3, 150)
            header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        file_view.update_style()
        logging.debug("Restored column state for file view")

    def load_state(self):
        settings = QSettings("MyFileManager", "Settings")
        geometry = settings.value("geometry")
        if geometry:
            self.setGeometry(geometry)

        splitter_sizes = settings.value("splitterSizes")
        if splitter_sizes:
            self.splitter.setSizes([int(size) for size in splitter_sizes])

        open_tabs1 = settings.value("openTabs1", [])
        if open_tabs1 is None:
            open_tabs1 = []
        if open_tabs1:
            for path in open_tabs1:
                if os.path.exists(path):
                    self.navigation_bar1.add_new_tab(path)
                else:
                    self.navigation_bar1.add_new_tab(QDir.homePath())
        else:
            self.navigation_bar1.add_new_tab(QDir.homePath())

        self.second_zone_active = settings.value("secondZoneActive", False, type=bool)
        if self.second_zone_active:
            self.navigation_bar2 = NavigationBar(self)
            self.zones_layout.addWidget(self.navigation_bar2)
            open_tabs2 = settings.value("openTabs2", [])
            if open_tabs2 is None:
                open_tabs2 = []
            if open_tabs2:
                for path in open_tabs2:
                    if os.path.exists(path):
                        self.navigation_bar2.add_new_tab(path)
                    else:
                        self.navigation_bar2.add_new_tab(QDir.homePath())
            else:
                self.navigation_bar2.add_new_tab(QDir.homePath())

        for nav_bar in [self.navigation_bar1, self.navigation_bar2]:
            if nav_bar:
                for i in range(nav_bar.tab_widget.count()):
                    file_view = nav_bar.tab_widget.widget(i).findChild(CustomTreeViewWithDrag)
                    if file_view:
                        file_view.update_style()
                        file_view.proxy_model.sourceModel().dataChanged.connect(self.handle_data_changed)
        logging.info("Loaded application state")

    def closeEvent(self, event):
        self.save_state()
        for thread in self.active_threads[:]:
            thread.quit()
            thread.wait()
        super().closeEvent(event)
        logging.info("Application closed")

if __name__ == "__main__":
    print(f"Current working directory: {os.getcwd()}")
    app = QApplication(sys.argv)
    window = FileManager()
    window.show()
    sys.exit(app.exec())
