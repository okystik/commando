from PyQt6.QtWidgets import QMessageBox, QInputDialog, QMainWindow
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut, QKeySequence
import os
import logging
from treeview import CustomTreeViewWithDrag

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class HotkeyManager:
    def __init__(self, file_manager):
        self.file_manager = file_manager
        self.setup_shortcuts()

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Alt+Left"), self.file_manager, lambda: self.file_manager.go_back(self.file_manager.current_file_view()))
        QShortcut(QKeySequence("Alt+Right"), self.file_manager, lambda: self.file_manager.go_forward(self.file_manager.current_file_view()))
        QShortcut(QKeySequence("Alt+Up"), self.file_manager, lambda: self.file_manager.go_up(self.file_manager.current_file_view()))
        QShortcut(QKeySequence("Ctrl+D"), self.file_manager, lambda: self.file_manager.quick_access_clicked(self.file_manager.current_file_view(), self.file_manager.quick_access_panel.quick_access.item(0)))
        QShortcut(QKeySequence("Ctrl+H"), self.file_manager, lambda: self.file_manager.navigate_to(self.file_manager.current_file_view(), self.file_manager.QDir.homePath()))
        QShortcut(QKeySequence("Ctrl+R"), self.file_manager, lambda: self.file_manager.refresh_view(self.file_manager.current_file_view()))
        QShortcut(QKeySequence("F5"), self.file_manager, lambda: self.file_manager.refresh_view(self.file_manager.current_file_view()))
        QShortcut(QKeySequence("Ctrl+A"), self.file_manager, lambda: self.select_all(self.file_manager.current_file_view()))
        QShortcut(QKeySequence("Ctrl+C"), self.file_manager, self.copy_files)
        QShortcut(QKeySequence("Ctrl+X"), self.file_manager, self.cut_files)
        QShortcut(QKeySequence("Ctrl+V"), self.file_manager, self.paste_files)
        QShortcut(QKeySequence("Delete"), self.file_manager, self.delete_files)
        QShortcut(QKeySequence("F2"), self.file_manager, self.rename_file)
        QShortcut(QKeySequence("Ctrl+Q"), self.file_manager, self.file_manager.close)
        QShortcut(QKeySequence("Ctrl+T"), self.file_manager, self.new_tab)
        QShortcut(QKeySequence("Ctrl+N"), self.file_manager, self.new_folder)
        QShortcut(QKeySequence("Ctrl+Shift+N"), self.file_manager, self.new_file)
        QShortcut(QKeySequence("Ctrl+Z"), self.file_manager, self.undo_action)

    def select_all(self, file_view):
        if file_view:
            file_view.selectAll()
            logging.info("Selected all items in file view")

    def copy_files(self):
        file_view = self.file_manager.current_file_view()
        if not file_view:
            logging.warning("No file view selected for copy")
            return
        selected_indexes = file_view.selectionModel().selectedIndexes()
        self.file_manager.clipboard = []
        self.file_manager.clipboard_is_cut = False
        processed_rows = set()
        for index in selected_indexes:
            if index.column() == 0 and index.row() not in processed_rows:
                source_index = file_view.model().mapToSource(index)
                path = file_view.model().sourceModel().item(source_index.row(), 0).data(Qt.ItemDataRole.UserRole)
                self.file_manager.clipboard.append(path)
                processed_rows.add(index.row())
        logging.info(f"Copied {len(self.file_manager.clipboard)} files to clipboard")

    def cut_files(self):
        file_view = self.file_manager.current_file_view()
        if not file_view:
            logging.warning("No file view selected for cut")
            return
        selected_indexes = file_view.selectionModel().selectedIndexes()
        self.file_manager.clipboard = []
        self.file_manager.clipboard_is_cut = True
        processed_rows = set()
        for index in selected_indexes:
            if index.column() == 0 and index.row() not in processed_rows:
                source_index = file_view.model().mapToSource(index)
                path = file_view.model().sourceModel().item(source_index.row(), 0).data(Qt.ItemDataRole.UserRole)
                self.file_manager.clipboard.append(path)
                processed_rows.add(index.row())
        logging.info(f"Cut {len(self.file_manager.clipboard)} files to clipboard")

    def paste_files(self):
        file_view = self.file_manager.current_file_view()
        if not file_view or not self.file_manager.clipboard:
            logging.warning("No file view or clipboard empty for paste")
            return
        current_path = file_view.history[-1] if file_view.history else self.file_manager.QDir.homePath()
        operation = "move" if self.file_manager.clipboard_is_cut else "copy"
        self.file_manager.perform_file_operation(self.file_manager.clipboard, current_path, operation)
        # Clear clipboard after operation
        self.file_manager.clipboard = []
        self.file_manager.clipboard_is_cut = False
        logging.info(f"Pasted files to {current_path} with operation {operation}")

    def delete_files(self):
        file_view = self.file_manager.current_file_view()
        if not file_view:
            logging.warning("No file view selected for delete")
            return
        selected_indexes = file_view.selectionModel().selectedIndexes()
        if not selected_indexes:
            logging.info("No items selected for delete")
            QMessageBox.warning(self.file_manager, "Ошибка", "Выберите файлы или папки для удаления")
            return
        reply = QMessageBox.question(self.file_manager, "Удаление", "Переместить выбранные файлы в корзину?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        processed_rows = set()
        for index in selected_indexes:
            if index.column() != 0 or index.row() in processed_rows:
                continue
            source_index = file_view.model().mapToSource(index)
            path = file_view.model().sourceModel().item(source_index.row(), 0).data(Qt.ItemDataRole.UserRole)
            if not os.path.exists(path):
                logging.warning(f"Path does not exist for deletion: {path}")
                continue
            try:
                if self.file_manager.undo_manager.move_to_trash(path):
                    self.file_manager.undo_manager.add_action('DELETE', path=path)
                    logging.info(f"Moved to trash: {path}")
                else:
                    logging.error(f"Failed to move {path} to trash")
                    QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось переместить {path} в корзину")
            except Exception as e:
                logging.error(f"Error moving {path} to trash: {e}")
                QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось переместить {path} в корзину: {e}")
            processed_rows.add(index.row())
        self.file_manager.refresh_view(file_view)

    def rename_file(self):
        file_view = self.file_manager.current_file_view()
        if not file_view:
            logging.warning("No file view selected for rename")
            return
        selected_indexes = file_view.selectionModel().selectedIndexes()
        if not selected_indexes:
            logging.warning("No file selected for rename")
            QMessageBox.warning(self.file_manager, "Ошибка", "Выберите файл или папку для переименования")
            return
        index = selected_indexes[0]
        if index.column() != 0:
            logging.warning("Selected index is not in name column for rename")
            return
        source_index = file_view.model().mapToSource(index)
        path = file_view.model().sourceModel().item(source_index.row(), 0).data(Qt.ItemDataRole.UserRole)
        if not os.path.exists(path):
            logging.error(f"Cannot rename: {path} does not exist")
            QMessageBox.warning(self.file_manager, "Ошибка", f"Файл или папка не существует: {path}")
            return
        logging.info(f"Starting rename for file: {path}")
        file_view.setCurrentIndex(index)
        file_view.edit(index)

    def new_tab(self):
        file_view = self.file_manager.current_file_view()
        if not file_view:
            logging.warning("No file view selected for new tab")
            return
        current_path = file_view.history[-1] if file_view.history else self.file_manager.QDir.homePath()
        nav_bar = self.file_manager.navigation_bar1 if self.file_manager.active_zone == 1 else self.file_manager.navigation_bar2
        if nav_bar:
            nav_bar.add_new_tab(current_path)
            logging.info(f"Opened new tab at {current_path}")

    def new_folder(self):
        file_view = self.file_manager.current_file_view()
        if not file_view:
            logging.warning("No file view selected for new folder")
            return
        current_path = file_view.history[-1] if file_view.history else self.file_manager.QDir.homePath()
        folder_name, ok = QInputDialog.getText(self.file_manager, "Новая папка", "Введите имя папки:")
        if ok and folder_name:
            new_folder_path = os.path.join(current_path, folder_name)
            try:
                os.makedirs(new_folder_path, exist_ok=True)
                self.file_manager.undo_manager.add_action('CREATE_FOLDER', path=new_folder_path)
                self.file_manager.refresh_view(file_view)
                logging.info(f"Created new folder: {new_folder_path}")
            except PermissionError as e:
                logging.error(f"No permission to create folder {new_folder_path}: {e}")
                QMessageBox.warning(self.file_manager, "Ошибка", f"Нет прав на создание папки: {e}")
            except OSError as e:
                logging.error(f"Failed to create folder {new_folder_path}: {e}")
                QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось создать папку: {e}")

    def new_file(self):
        file_view = self.file_manager.current_file_view()
        if not file_view:
            logging.warning("No file view selected for new file")
            return
        current_path = file_view.history[-1] if file_view.history else self.file_manager.QDir.homePath()
        file_name, ok = QInputDialog.getText(self.file_manager, "Новый файл", "Введите имя файла:")
        if ok and file_name:
            new_file_path = os.path.join(current_path, file_name)
            try:
                with open(new_file_path, 'w') as f:
                    f.write("")
                self.file_manager.undo_manager.add_action('CREATE_FILE', path=new_file_path)
                self.file_manager.refresh_view(file_view)
                logging.info(f"Created new file: {new_file_path}")
            except PermissionError as e:
                logging.error(f"No permission to create file {new_file_path}: {e}")
                QMessageBox.warning(self.file_manager, "Ошибка", f"Нет прав на создание файла: {e}")
            except OSError as e:
                logging.error(f"Failed to create file {new_file_path}: {e}")
                QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось создать файл: {e}")

    def undo_action(self):
        try:
            self.file_manager.undo_manager.undo()
            file_view = self.file_manager.current_file_view()
            if file_view:
                self.file_manager.refresh_view(file_view)
                logging.info("Performed undo action and refreshed view")
            else:
                logging.warning("No file view to refresh after undo")
        except Exception as e:
            logging.error(f"Undo failed: {e}")
            QMessageBox.warning(self.file_manager, "Ошибка", f"Не удалось отменить действие: {e}")
